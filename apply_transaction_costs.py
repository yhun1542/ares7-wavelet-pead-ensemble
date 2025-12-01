#!/usr/bin/env python3
"""
거래 비용 반영 (TC Model)
=========================
1. Turnover 계산
2. 거래 비용 모델 적용
3. Net returns 계산
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics
from step2_oos_grid_search import merge_sf1_pit

BASE_DIR = Path(__file__).parent


def calculate_turnover(weights_df):
    """
    Calculate portfolio turnover
    
    Parameters
    ----------
    weights_df : pd.DataFrame
        Portfolio weights (dates × symbols)
    
    Returns
    -------
    turnover : pd.Series
        Daily turnover (sum of absolute weight changes)
    """
    
    # Weight changes
    weight_changes = weights_df.diff().abs()
    
    # Turnover = sum of absolute changes
    turnover = weight_changes.sum(axis=1)
    
    return turnover


def apply_transaction_costs(returns, turnover, cost_bps=10):
    """
    Apply transaction costs to returns
    
    Parameters
    ----------
    returns : pd.Series
        Gross returns (before costs)
    turnover : pd.Series
        Daily turnover
    cost_bps : float
        Transaction cost in basis points (default: 10 bps)
    
    Returns
    -------
    net_returns : pd.Series
        Net returns (after costs)
    total_costs : float
        Total transaction costs (annualized %)
    """
    
    # Cost per day = turnover × cost_bps / 10000
    daily_costs = turnover * (cost_bps / 10000)
    
    # Net returns = gross returns - costs
    net_returns = returns - daily_costs
    
    # Total costs (annualized)
    total_costs = daily_costs.mean() * 252
    
    return net_returns, total_costs


def run_tc_analysis():
    """Run transaction cost analysis"""
    
    print("\n" + "="*80)
    print("Transaction Cost Analysis")
    print("="*80)
    
    # Load best config
    results_file = BASE_DIR / 'tuning' / 'results' / 'step6_final_results.json'
    with open(results_file) as f:
        data = json.load(f)
    
    best_config = data['best_config']
    exposure_scale = data['exposure_scale']
    
    print(f"\n📊 Best Config:")
    print(f"   overlay_strength: {best_config['overlay_strength']:.2f}")
    print(f"   top_frac: {best_config['top_frac']:.2f}")
    print(f"   bottom_frac: {best_config['bottom_frac']:.2f}")
    print(f"   exposure_scale: {exposure_scale:.4f}")
    print(f"   regime_filter: BULL only")
    
    # Load data
    print(f"\n📂 Loading data...")
    
    # Baseline returns
    baseline_file = BASE_DIR / 'results' / 'ares7_best_ensemble_results.json'
    with open(baseline_file) as f:
        baseline_data = json.load(f)
    
    dates = [item['date'] for item in baseline_data['daily_returns']]
    returns = [item['ret'] for item in baseline_data['daily_returns']]
    
    baseline_returns = pd.Series(
        returns,
        index=pd.to_datetime(dates),
        name='baseline'
    )
    
    # Stock returns
    prices_file = BASE_DIR / 'data' / 'prices.csv'
    df = pd.read_csv(prices_file)
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
    
    prices = df.pivot(index='timestamp', columns='symbol', values='close')
    stock_returns = prices.pct_change().fillna(0.0)
    
    # Align dates
    common_dates = baseline_returns.index.intersection(stock_returns.index)
    baseline_returns = baseline_returns.loc[common_dates]
    stock_returns = stock_returns.loc[common_dates]
    
    # Load fixed SF1 data
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals_pit90d.csv'
    sf1_df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    # Merge SF1
    quality_df = merge_sf1_pit(stock_returns, sf1_df)
    
    # Load BULL regime
    regime_file = BASE_DIR / 'data' / 'bull_regime.csv'
    bull_regime = pd.read_csv(regime_file, parse_dates=[0], index_col=0).squeeze()
    bull_regime = bull_regime.reindex(common_dates, fill_value=False)
    
    # Initialize engine
    engine = OptimizedBacktestEngine(train_window=2520)
    
    # Run backtest (get weights)
    print(f"\n" + "="*80)
    print("Running Backtest (with weights)...")
    print("="*80)
    
    result = engine.run_qm_overlay_backtest(
        stock_returns,
        quality_df,
        **best_config
    )
    
    # Get weights
    weights_df = result['weights']
    
    # Apply regime filter to weights
    # Where regime is NOT BULL, set weights to baseline (equal weight)
    baseline_weight = 1.0 / len(stock_returns.columns)
    
    for date in weights_df.index:
        if not bull_regime.loc[date]:
            weights_df.loc[date, :] = baseline_weight
    
    # Calculate turnover
    print(f"\n📊 Calculating turnover...")
    
    turnover = calculate_turnover(weights_df)
    
    # Statistics
    mean_turnover = turnover.mean()
    median_turnover = turnover.median()
    max_turnover = turnover.max()
    
    print(f"   Mean daily turnover: {mean_turnover*100:.2f}%")
    print(f"   Median daily turnover: {median_turnover*100:.2f}%")
    print(f"   Max daily turnover: {max_turnover*100:.2f}%")
    print(f"   Annual turnover: {mean_turnover*252*100:.1f}%")
    
    # Apply transaction costs
    print(f"\n💰 Applying transaction costs...")
    
    # Get gross returns
    overlay_returns = result['returns'].copy()
    overlay_returns[~bull_regime] = baseline_returns[~bull_regime]
    
    # Apply exposure scaling
    gross_returns = overlay_returns * exposure_scale
    
    # Calculate net returns (after costs)
    cost_scenarios = [5, 10, 15, 20]  # bps
    
    print(f"\n{'Cost (bps)':<12} {'Total Cost (ann)':<20} {'Gross Sharpe':<15} {'Net Sharpe':<15} {'Delta':<10}")
    print("-" * 80)
    
    gross_metrics = calculate_metrics(gross_returns)
    
    tc_results = {}
    
    for cost_bps in cost_scenarios:
        net_returns, total_costs = apply_transaction_costs(
            gross_returns,
            turnover * exposure_scale,  # Scale turnover too
            cost_bps=cost_bps
        )
        
        net_metrics = calculate_metrics(net_returns)
        
        delta_sharpe = net_metrics['sharpe'] - gross_metrics['sharpe']
        
        tc_results[f'{cost_bps}bps'] = {
            'cost_bps': cost_bps,
            'total_costs_ann': float(total_costs),
            'gross_sharpe': float(gross_metrics['sharpe']),
            'net_sharpe': float(net_metrics['sharpe']),
            'delta_sharpe': float(delta_sharpe),
            'net_ann_return': float(net_metrics['ann_return']),
            'net_ann_vol': float(net_metrics['ann_vol']),
            'net_max_dd': float(net_metrics['max_dd'])
        }
        
        print(f"{cost_bps:<12} {total_costs*100:>18.2f}% {gross_metrics['sharpe']:>14.4f} "
              f"{net_metrics['sharpe']:>14.4f} {delta_sharpe:>+9.4f}")
    
    # Recommended scenario: 10 bps
    recommended_cost = 10
    net_returns_10bps, total_costs_10bps = apply_transaction_costs(
        gross_returns,
        turnover * exposure_scale,
        cost_bps=recommended_cost
    )
    
    net_metrics_10bps = calculate_metrics(net_returns_10bps)
    
    print(f"\n" + "="*80)
    print(f"Recommended Scenario: {recommended_cost} bps")
    print("="*80)
    
    print(f"\n📊 Performance (After {recommended_cost} bps TC):")
    print(f"   Gross Sharpe: {gross_metrics['sharpe']:.4f}")
    print(f"   Net Sharpe: {net_metrics_10bps['sharpe']:.4f}")
    print(f"   Delta: {net_metrics_10bps['sharpe'] - gross_metrics['sharpe']:+.4f}")
    print(f"   Total TC (ann): {total_costs_10bps*100:.2f}%")
    print(f"   Net Ann Return: {net_metrics_10bps['ann_return']*100:.2f}%")
    print(f"   Net Ann Vol: {net_metrics_10bps['ann_vol']*100:.2f}%")
    print(f"   Net Max DD: {net_metrics_10bps['max_dd']*100:.2f}%")
    print(f"   Net Calmar: {net_metrics_10bps['calmar']:.4f}")
    
    # OOS validation with TC
    print(f"\n" + "="*80)
    print(f"OOS Validation (After {recommended_cost} bps TC)")
    print("="*80)
    
    splits = {
        'train': ('2015-11-25', '2019-12-31'),
        'oos1': ('2020-01-01', '2021-12-31'),
        'oos2': ('2022-01-01', '2024-12-31'),
        'oos3': ('2025-01-01', '2025-11-18')
    }
    
    oos_tc_results = {}
    
    for split_name, (start, end) in splits.items():
        start_date = pd.Timestamp(start)
        end_date = pd.Timestamp(end)
        
        mask = (gross_returns.index >= start_date) & (gross_returns.index <= end_date)
        split_gross = gross_returns[mask]
        split_turnover = turnover[mask] * exposure_scale
        
        if len(split_gross) == 0:
            continue
        
        # Net returns
        split_net, split_tc = apply_transaction_costs(
            split_gross,
            split_turnover,
            cost_bps=recommended_cost
        )
        
        # Metrics
        split_gross_metrics = calculate_metrics(split_gross)
        split_net_metrics = calculate_metrics(split_net)
        
        oos_tc_results[split_name] = {
            'gross_sharpe': split_gross_metrics['sharpe'],
            'net_sharpe': split_net_metrics['sharpe'],
            'delta_sharpe': split_net_metrics['sharpe'] - split_gross_metrics['sharpe'],
            'total_tc_ann': split_tc
        }
        
        print(f"\n{split_name.upper()}:")
        print(f"   Gross Sharpe: {split_gross_metrics['sharpe']:.4f}")
        print(f"   Net Sharpe: {split_net_metrics['sharpe']:.4f}")
        print(f"   Delta: {oos_tc_results[split_name]['delta_sharpe']:+.4f}")
        print(f"   TC (ann): {split_tc*100:.2f}%")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tc_analysis_results = {
        'turnover_stats': {
            'mean_daily': float(mean_turnover),
            'median_daily': float(median_turnover),
            'max_daily': float(max_turnover),
            'annual': float(mean_turnover * 252)
        },
        'cost_scenarios': tc_results,
        'recommended_scenario': {
            'cost_bps': recommended_cost,
            'total_costs_ann': float(total_costs_10bps),
            'gross_sharpe': float(gross_metrics['sharpe']),
            'net_sharpe': float(net_metrics_10bps['sharpe']),
            'delta_sharpe': float(net_metrics_10bps['sharpe'] - gross_metrics['sharpe']),
            'net_metrics': {k: float(v) for k, v in net_metrics_10bps.items()}
        },
        'oos_results': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in oos_tc_results.items()}
    }
    
    results_file = output_dir / 'transaction_cost_analysis.json'
    with open(results_file, 'w') as f:
        json.dump(tc_analysis_results, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    print(f"\n" + "="*80)
    print("✅ Transaction Cost Analysis Complete")
    print("="*80)
    
    return tc_analysis_results


if __name__ == "__main__":
    results = run_tc_analysis()
    print(f"\n📌 Next: Final Report")
