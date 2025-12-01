#!/usr/bin/env python3
"""
Step 5: 레짐 필터 + Overlay Grid Search
=======================================
BULL 레짐에서만 QM Overlay 적용 + OOS 기반 선택
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics
from step2_oos_grid_search import merge_sf1_pit

BASE_DIR = Path(__file__).parent


def run_regime_grid_search():
    """Run Grid Search with regime filter"""
    
    print("\n" + "="*80)
    print("Step 5: 레짐 필터 + Overlay Grid Search")
    print("="*80)
    
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
    
    print(f"   Total dates: {len(common_dates)}")
    
    # Load fixed SF1 data (90-day delay)
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals_pit90d.csv'
    sf1_df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    # Merge SF1 (point-in-time, bias-free)
    quality_df = merge_sf1_pit(stock_returns, sf1_df)
    
    # Load BULL regime
    regime_file = BASE_DIR / 'data' / 'bull_regime.csv'
    bull_regime = pd.read_csv(regime_file, parse_dates=[0], index_col=0).squeeze()
    bull_regime = bull_regime.reindex(common_dates, fill_value=False)
    
    print(f"   BULL days: {bull_regime.sum()} ({bull_regime.sum()/len(bull_regime)*100:.1f}%)")
    
    # Define train/OOS splits
    splits = {
        'train': ('2015-11-25', '2019-12-31'),
        'oos1': ('2020-01-01', '2021-12-31'),
        'oos2': ('2022-01-01', '2024-12-31'),
        'oos3': ('2025-01-01', '2025-11-18')
    }
    
    # Grid Search parameters (conservative + regime filter)
    param_grid = {
        'overlay_strength': [0.03, 0.04],
        'top_frac': [0.20],
        'bottom_frac': [0.20]
    }
    
    print(f"\n📊 Grid Search Parameters:")
    print(f"   overlay_strength: {param_grid['overlay_strength']}")
    print(f"   top_frac: {param_grid['top_frac']}")
    print(f"   bottom_frac: {param_grid['bottom_frac']}")
    print(f"   regime_filter: BULL only")
    print(f"   Total combinations: {len(param_grid['overlay_strength']) * len(param_grid['top_frac']) * len(param_grid['bottom_frac'])}")
    
    # Initialize engine
    engine = OptimizedBacktestEngine(train_window=2520)
    
    # Run Grid Search
    results = []
    
    print(f"\n" + "="*80)
    print("Running Grid Search with Regime Filter...")
    print("="*80)
    
    for strength in param_grid['overlay_strength']:
        for top_frac in param_grid['top_frac']:
            for bottom_frac in param_grid['bottom_frac']:
                
                config = {
                    'overlay_strength': strength,
                    'top_frac': top_frac,
                    'bottom_frac': bottom_frac
                }
                
                print(f"\n📊 Config: strength={strength:.2f}, top={top_frac:.2f}, bottom={bottom_frac:.2f}")
                
                split_results = {}
                
                for split_name, (start, end) in splits.items():
                    start_date = pd.Timestamp(start)
                    end_date = pd.Timestamp(end)
                    
                    mask = (stock_returns.index >= start_date) & (stock_returns.index <= end_date)
                    split_stock_returns = stock_returns[mask]
                    split_quality = quality_df[mask]
                    split_baseline = baseline_returns[mask]
                    split_regime = bull_regime[mask]
                    
                    if len(split_stock_returns) == 0:
                        continue
                    
                    # Run QM overlay backtest
                    result = engine.run_qm_overlay_backtest(
                        split_stock_returns,
                        split_quality,
                        **config
                    )
                    
                    # Apply regime filter
                    overlay_returns = result['returns'].copy()
                    
                    # Where regime is NOT BULL, use baseline returns
                    overlay_returns[~split_regime] = split_baseline[~split_regime]
                    
                    # Calculate metrics
                    baseline_metrics = calculate_metrics(split_baseline)
                    overlay_metrics = calculate_metrics(overlay_returns)
                    
                    bull_pct = split_regime.sum() / len(split_regime) * 100
                    
                    split_results[split_name] = {
                        'baseline_sharpe': baseline_metrics['sharpe'],
                        'overlay_sharpe': overlay_metrics['sharpe'],
                        'delta_sharpe': overlay_metrics['sharpe'] - baseline_metrics['sharpe'],
                        'bull_pct': bull_pct
                    }
                    
                    print(f"   {split_name.upper()}: baseline={baseline_metrics['sharpe']:.4f}, "
                          f"overlay={overlay_metrics['sharpe']:.4f}, delta={split_results[split_name]['delta_sharpe']:+.4f}, "
                          f"BULL={bull_pct:.1f}%")
                
                # Calculate OOS score
                oos_sharpes = [
                    split_results['oos1']['overlay_sharpe'],
                    split_results['oos2']['overlay_sharpe'],
                    split_results['oos3']['overlay_sharpe']
                ]
                
                oos_deltas = [
                    split_results['oos1']['delta_sharpe'],
                    split_results['oos2']['delta_sharpe'],
                    split_results['oos3']['delta_sharpe']
                ]
                
                oos_min_sharpe = min(oos_sharpes)
                oos_avg_sharpe = np.mean(oos_sharpes)
                oos_std_sharpe = np.std(oos_sharpes)
                
                # Check if all OOS > baseline
                all_oos_positive = all(d > 0 for d in oos_deltas)
                
                # Calculate degradation
                train_sharpe = split_results['train']['overlay_sharpe']
                degradation = train_sharpe - oos_avg_sharpe
                degradation_pct = degradation / train_sharpe * 100
                
                # Score = min(OOS Sharpe)
                score = oos_min_sharpe
                
                print(f"   OOS min Sharpe: {oos_min_sharpe:.4f}")
                print(f"   OOS avg Sharpe: {oos_avg_sharpe:.4f}")
                print(f"   All OOS > baseline: {all_oos_positive}")
                print(f"   Train Sharpe: {train_sharpe:.4f}")
                print(f"   Degradation: {degradation:+.4f} ({degradation_pct:+.1f}%)")
                print(f"   Score: {score:.4f}")
                
                results.append({
                    'config': config,
                    'train_sharpe': split_results['train']['overlay_sharpe'],
                    'oos1_sharpe': split_results['oos1']['overlay_sharpe'],
                    'oos2_sharpe': split_results['oos2']['overlay_sharpe'],
                    'oos3_sharpe': split_results['oos3']['overlay_sharpe'],
                    'oos_min_sharpe': oos_min_sharpe,
                    'oos_avg_sharpe': oos_avg_sharpe,
                    'oos_std_sharpe': oos_std_sharpe,
                    'all_oos_positive': all_oos_positive,
                    'degradation': degradation,
                    'degradation_pct': degradation_pct,
                    'score': score
                })
    
    # Sort by score (OOS min Sharpe)
    results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # Summary
    print(f"\n" + "="*80)
    print("Grid Search Results (sorted by OOS min Sharpe)")
    print("="*80)
    
    print(f"\n{'Rank':<6} {'Strength':<10} {'Train':<8} {'OOS1':<8} {'OOS2':<8} {'OOS3':<8} {'Min':<8} {'Avg':<8} {'Degrad%':<10} {'All+?':<8}")
    print("-" * 120)
    
    for i, res in enumerate(results, 1):
        cfg = res['config']
        all_pos = "✅" if res['all_oos_positive'] else "❌"
        print(f"{i:<6} {cfg['overlay_strength']:<10.2f} "
              f"{res['train_sharpe']:<8.4f} {res['oos1_sharpe']:<8.4f} {res['oos2_sharpe']:<8.4f} {res['oos3_sharpe']:<8.4f} "
              f"{res['oos_min_sharpe']:<8.4f} {res['oos_avg_sharpe']:<8.4f} {res['degradation_pct']:<+10.1f} {all_pos:<8}")
    
    # Best config
    best = results[0]
    
    print(f"\n" + "="*80)
    print("Best Config (OOS min Sharpe + Regime Filter)")
    print("="*80)
    
    print(f"\n📊 Config:")
    print(f"   overlay_strength: {best['config']['overlay_strength']:.2f}")
    print(f"   top_frac: {best['config']['top_frac']:.2f}")
    print(f"   bottom_frac: {best['config']['bottom_frac']:.2f}")
    print(f"   regime_filter: BULL only")
    
    print(f"\n📈 Performance:")
    print(f"   Train Sharpe: {best['train_sharpe']:.4f}")
    print(f"   OOS 1 Sharpe: {best['oos1_sharpe']:.4f}")
    print(f"   OOS 2 Sharpe: {best['oos2_sharpe']:.4f}")
    print(f"   OOS 3 Sharpe: {best['oos3_sharpe']:.4f}")
    print(f"   OOS min Sharpe: {best['oos_min_sharpe']:.4f}")
    print(f"   OOS avg Sharpe: {best['oos_avg_sharpe']:.4f}")
    
    print(f"\n📊 Overfitting:")
    print(f"   Degradation: {best['degradation']:+.4f} ({best['degradation_pct']:+.1f}%)")
    
    if abs(best['degradation_pct']) < 10:
        print(f"   ✅ LOW overfitting (< 10%)")
    elif abs(best['degradation_pct']) < 20:
        print(f"   ⚠️  MODERATE overfitting (10-20%)")
    else:
        print(f"   ❌ HIGH overfitting (> 20%)")
    
    print(f"\n📊 OOS Validation:")
    if best['all_oos_positive']:
        print(f"   ✅ All OOS periods > baseline")
    else:
        print(f"   ❌ Some OOS periods < baseline")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = output_dir / 'step5_regime_grid_search_results.json'
    with open(results_file, 'w') as f:
        json.dump({
            'grid_search_results': results,
            'best_config': best
        }, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    print(f"\n" + "="*80)
    print("✅ Step 5 Complete: 레짐 필터 + Overlay Grid Search")
    print("="*80)
    
    return results, best


if __name__ == "__main__":
    results, best = run_regime_grid_search()
    print(f"\n📌 Next: Apply Global Exposure Scale to Best Config")
