#!/usr/bin/env python3
"""
Step 6: 최종 결과 분석 및 검증
==============================
레짐 필터 + Best Config + Exposure Scaling
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics
from step2_oos_grid_search import merge_sf1_pit

BASE_DIR = Path(__file__).parent


def run_final_validation():
    """Run final validation with regime filter + exposure scaling"""
    
    print("\n" + "="*80)
    print("Step 6: 최종 결과 분석 및 검증")
    print("="*80)
    
    # Load best config
    results_file = BASE_DIR / 'tuning' / 'results' / 'step5_regime_grid_search_results.json'
    with open(results_file) as f:
        data = json.load(f)
    
    best_config = data['best_config']['config']
    
    print(f"\n📊 Best Config (from Step 5):")
    print(f"   overlay_strength: {best_config['overlay_strength']:.2f}")
    print(f"   top_frac: {best_config['top_frac']:.2f}")
    print(f"   bottom_frac: {best_config['bottom_frac']:.2f}")
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
    
    # Load fixed SF1 data (90-day delay)
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
    
    # Run full sample backtest
    print(f"\n" + "="*80)
    print("Running Full Sample Backtest (Regime Filter)...")
    print("="*80)
    
    result = engine.run_qm_overlay_backtest(
        stock_returns,
        quality_df,
        **best_config
    )
    
    # Apply regime filter
    overlay_returns = result['returns'].copy()
    overlay_returns[~bull_regime] = baseline_returns[~bull_regime]
    
    # Calculate metrics
    baseline_metrics = calculate_metrics(baseline_returns)
    overlay_metrics = calculate_metrics(overlay_returns)
    
    print(f"\n📊 Full Sample (Regime Filter, No Scaling):")
    print(f"   Baseline Sharpe: {baseline_metrics['sharpe']:.4f}")
    print(f"   Overlay Sharpe: {overlay_metrics['sharpe']:.4f}")
    print(f"   Delta: {overlay_metrics['sharpe'] - baseline_metrics['sharpe']:+.4f}")
    print(f"   Overlay Vol: {overlay_metrics['ann_vol']*100:.2f}%")
    print(f"   Overlay MDD: {overlay_metrics['max_dd']*100:.2f}%")
    print(f"   BULL days: {bull_regime.sum()} ({bull_regime.sum()/len(bull_regime)*100:.1f}%)")
    
    # Calculate exposure scale
    target_vol = 0.12  # 12%
    overlay_vol = overlay_metrics['ann_vol']
    exposure_scale = target_vol / overlay_vol
    
    print(f"\n🎯 Target Vol: {target_vol*100:.2f}%")
    print(f"   Overlay Vol: {overlay_vol*100:.2f}%")
    print(f"   Exposure Scale: {exposure_scale:.4f}")
    
    # Apply exposure scaling
    balanced_returns = overlay_returns * exposure_scale
    balanced_metrics = calculate_metrics(balanced_returns)
    
    print(f"\n📊 Balanced Profile (Regime Filter + Scaled):")
    print(f"   Sharpe: {balanced_metrics['sharpe']:.4f}")
    print(f"   Ann Return: {balanced_metrics['ann_return']*100:.2f}%")
    print(f"   Ann Vol: {balanced_metrics['ann_vol']*100:.2f}%")
    print(f"   Max DD: {balanced_metrics['max_dd']*100:.2f}%")
    print(f"   Calmar: {balanced_metrics['calmar']:.4f}")
    
    # OOS validation
    print(f"\n" + "="*80)
    print("OOS Validation (Regime Filter + Balanced)")
    print("="*80)
    
    splits = {
        'train': ('2015-11-25', '2019-12-31'),
        'oos1': ('2020-01-01', '2021-12-31'),
        'oos2': ('2022-01-01', '2024-12-31'),
        'oos3': ('2025-01-01', '2025-11-18')
    }
    
    oos_results = {}
    
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
        split_result = engine.run_qm_overlay_backtest(
            split_stock_returns,
            split_quality,
            **best_config
        )
        
        # Apply regime filter
        split_overlay_returns = split_result['returns'].copy()
        split_overlay_returns[~split_regime] = split_baseline[~split_regime]
        
        # Apply exposure scaling
        split_balanced_returns = split_overlay_returns * exposure_scale
        
        # Calculate metrics
        split_baseline_metrics = calculate_metrics(split_baseline)
        split_balanced_metrics = calculate_metrics(split_balanced_returns)
        
        bull_pct = split_regime.sum() / len(split_regime) * 100
        
        oos_results[split_name] = {
            'baseline_sharpe': split_baseline_metrics['sharpe'],
            'balanced_sharpe': split_balanced_metrics['sharpe'],
            'delta_sharpe': split_balanced_metrics['sharpe'] - split_baseline_metrics['sharpe'],
            'balanced_vol': split_balanced_metrics['ann_vol'],
            'balanced_mdd': split_balanced_metrics['max_dd'],
            'bull_pct': bull_pct
        }
        
        print(f"\n{split_name.upper()}:")
        print(f"   Baseline Sharpe: {split_baseline_metrics['sharpe']:.4f}")
        print(f"   Balanced Sharpe: {split_balanced_metrics['sharpe']:.4f}")
        print(f"   Delta: {oos_results[split_name]['delta_sharpe']:+.4f}")
        print(f"   Vol: {split_balanced_metrics['ann_vol']*100:.2f}%")
        print(f"   MDD: {split_balanced_metrics['max_dd']*100:.2f}%")
        print(f"   BULL: {bull_pct:.1f}%")
    
    # Summary
    print(f"\n" + "="*80)
    print("Summary: Baseline vs Balanced (Regime Filter)")
    print("="*80)
    
    print(f"\n{'Period':<15} {'Baseline':<12} {'Balanced':<12} {'Delta':<12} {'Vol':<10} {'MDD':<10} {'BULL%':<10}")
    print("-" * 100)
    
    for split_name, res in oos_results.items():
        print(f"{split_name.upper():<15} {res['baseline_sharpe']:>11.4f} {res['balanced_sharpe']:>11.4f} "
              f"{res['delta_sharpe']:>+11.4f} {res['balanced_vol']*100:>9.2f}% {res['balanced_mdd']*100:>9.2f}% {res['bull_pct']:>9.1f}%")
    
    # OOS analysis
    oos_sharpes = [
        oos_results['oos1']['balanced_sharpe'],
        oos_results['oos2']['balanced_sharpe'],
        oos_results['oos3']['balanced_sharpe']
    ]
    
    oos_deltas = [
        oos_results['oos1']['delta_sharpe'],
        oos_results['oos2']['delta_sharpe'],
        oos_results['oos3']['delta_sharpe']
    ]
    
    oos_min = min(oos_sharpes)
    oos_avg = np.mean(oos_sharpes)
    train_sharpe = oos_results['train']['balanced_sharpe']
    degradation = train_sharpe - oos_avg
    degradation_pct = degradation / train_sharpe * 100
    
    all_oos_positive = all(d > 0 for d in oos_deltas)
    
    print(f"\n📊 Overfitting Analysis:")
    print(f"   Train Sharpe: {train_sharpe:.4f}")
    print(f"   OOS min Sharpe: {oos_min:.4f}")
    print(f"   OOS avg Sharpe: {oos_avg:.4f}")
    print(f"   Degradation: {degradation:+.4f} ({degradation_pct:+.1f}%)")
    
    if abs(degradation_pct) < 10:
        print(f"   ✅ LOW overfitting (< 10%)")
    elif abs(degradation_pct) < 20:
        print(f"   ⚠️  MODERATE overfitting (10-20%)")
    else:
        print(f"   ❌ HIGH overfitting (> 20%)")
    
    print(f"\n📊 OOS Validation:")
    if all_oos_positive:
        print(f"   ✅ All OOS periods > baseline")
    else:
        print(f"   ❌ Some OOS periods < baseline")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    final_results = {
        'best_config': best_config,
        'exposure_scale': float(exposure_scale),
        'target_vol': float(target_vol),
        'regime_filter': 'BULL only',
        'full_sample': {
            'baseline': {k: float(v) for k, v in baseline_metrics.items()},
            'balanced': {k: float(v) for k, v in balanced_metrics.items()}
        },
        'oos_results': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in oos_results.items()},
        'overfitting': {
            'train_sharpe': float(train_sharpe),
            'oos_min_sharpe': float(oos_min),
            'oos_avg_sharpe': float(oos_avg),
            'degradation': float(degradation),
            'degradation_pct': float(degradation_pct),
            'all_oos_positive': all_oos_positive
        }
    }
    
    results_file = output_dir / 'step6_final_results.json'
    with open(results_file, 'w') as f:
        json.dump(final_results, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    # Visualization
    print(f"\n📊 Generating plot...")
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # Cumulative returns
    ax = axes[0]
    
    baseline_cum = (1 + baseline_returns).cumprod()
    balanced_cum = (1 + balanced_returns).cumprod()
    
    ax.plot(baseline_cum.index, baseline_cum.values, label='Baseline', linewidth=2, alpha=0.8)
    ax.plot(balanced_cum.index, balanced_cum.values, label='Balanced (Regime Filter + PIT 90d)', linewidth=2, alpha=0.8)
    
    ax.set_ylabel('Cumulative Return', fontsize=12)
    ax.set_title('Cumulative Returns: Baseline vs Balanced (FINAL)', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    # Rolling Sharpe
    ax = axes[1]
    
    window = 252
    baseline_rolling = baseline_returns.rolling(window).apply(
        lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
    )
    balanced_rolling = balanced_returns.rolling(window).apply(
        lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
    )
    
    ax.plot(baseline_rolling.index, baseline_rolling.values, label='Baseline', linewidth=2, alpha=0.8)
    ax.plot(balanced_rolling.index, balanced_rolling.values, label='Balanced', linewidth=2, alpha=0.8)
    
    ax.axhline(y=2.0, color='green', linestyle='--', alpha=0.5, label='Target Sharpe 2.0')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Rolling 252-Day Sharpe', fontsize=12)
    ax.set_title('Rolling Sharpe Ratio', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    plot_file = output_dir / 'step6_final_comparison.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"   Saved: {plot_file}")
    
    print(f"\n" + "="*80)
    print("✅ Step 6 Complete: 최종 결과 분석 및 검증")
    print("="*80)
    
    return final_results


if __name__ == "__main__":
    results = run_final_validation()
    print(f"\n📌 Next: Final Report")
