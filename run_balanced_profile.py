#!/usr/bin/env python3
"""
Balanced Profile Backtest
==========================
Apply global_exposure_scale to Best QM Overlay
Target: Sharpe ~2.36, Vol ~12%, MDD ~-12%
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics
from merge_sf1_optimized import merge_sf1_optimized

BASE_DIR = Path(__file__).parent


def load_data():
    """Load all required data"""
    
    print("📂 Loading data...")
    
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
    
    # SF1 fundamentals
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    sf1_df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    # Align dates
    common_dates = baseline_returns.index.intersection(stock_returns.index)
    baseline_returns = baseline_returns.loc[common_dates]
    stock_returns = stock_returns.loc[common_dates]
    
    print(f"   Dates: {len(common_dates)}")
    print(f"   Symbols: {len(stock_returns.columns)}")
    
    return baseline_returns, stock_returns, sf1_df, common_dates


def run_balanced_profile():
    """Run balanced profile with global exposure scaling"""
    
    print("\n" + "="*80)
    print("Balanced Profile Backtest")
    print("="*80)
    
    # Load data
    baseline_returns, stock_returns, sf1_df, common_dates = load_data()
    
    # Merge SF1 data
    print("\n🔗 Merging SF1 data...")
    quality_df = merge_sf1_optimized(stock_returns, sf1_df)
    
    # Initialize engine
    engine = OptimizedBacktestEngine(train_window=2520)
    
    # Best QM config
    best_config = {
        'overlay_strength': 0.05,
        'top_frac': 0.20,
        'bottom_frac': 0.20
    }
    
    print(f"\n📊 Best QM Config:")
    print(f"   overlay_strength: {best_config['overlay_strength']}")
    print(f"   top_frac: {best_config['top_frac']}")
    print(f"   bottom_frac: {best_config['bottom_frac']}")
    
    # Run aggressive profile (no scaling)
    print(f"\n" + "="*80)
    print("Running Aggressive Profile (no scaling)...")
    print("="*80)
    
    aggressive_result = engine.run_qm_overlay_backtest(
        stock_returns,
        quality_df,
        **best_config
    )
    
    aggressive_metrics = calculate_metrics(aggressive_result['returns'])
    
    print(f"\n📊 Aggressive Profile:")
    for k, v in aggressive_metrics.items():
        print(f"   {k:<15}: {v:>10.4f}")
    
    # Calculate target exposure scale
    aggressive_vol = aggressive_metrics['ann_vol']
    target_vol = 0.12  # 12%
    exposure_scale = target_vol / aggressive_vol
    
    print(f"\n🎯 Target Vol: {target_vol*100:.2f}%")
    print(f"   Aggressive Vol: {aggressive_vol*100:.2f}%")
    print(f"   Exposure Scale: {exposure_scale:.4f}")
    
    # Run balanced profile (with scaling)
    print(f"\n" + "="*80)
    print(f"Running Balanced Profile (exposure_scale={exposure_scale:.4f})...")
    print("="*80)
    
    # Scale returns
    balanced_returns = aggressive_result['returns'] * exposure_scale
    balanced_metrics = calculate_metrics(balanced_returns)
    
    print(f"\n📊 Balanced Profile:")
    for k, v in balanced_metrics.items():
        print(f"   {k:<15}: {v:>10.4f}")
    
    # Baseline metrics
    baseline_metrics = calculate_metrics(baseline_returns)
    
    # Comparison
    print(f"\n" + "="*80)
    print("Performance Comparison")
    print("="*80)
    
    print(f"\n{'Metric':<15} {'Baseline':<12} {'Aggressive':<12} {'Balanced':<12}")
    print("-" * 80)
    
    for metric in ['sharpe', 'sortino', 'ann_return', 'ann_vol', 'max_dd', 'calmar']:
        baseline_val = baseline_metrics[metric]
        aggressive_val = aggressive_metrics[metric]
        balanced_val = balanced_metrics[metric]
        
        print(f"{metric:<15} {baseline_val:>11.4f} {aggressive_val:>11.4f} {balanced_val:>11.4f}")
    
    # Delta comparison
    print(f"\n{'Metric':<15} {'Aggressive Δ':<15} {'Balanced Δ':<15}")
    print("-" * 80)
    
    for metric in ['sharpe', 'sortino', 'ann_return', 'ann_vol', 'max_dd', 'calmar']:
        baseline_val = baseline_metrics[metric]
        aggressive_delta = aggressive_metrics[metric] - baseline_val
        balanced_delta = balanced_metrics[metric] - baseline_val
        
        aggressive_pct = aggressive_delta / abs(baseline_val) * 100 if baseline_val != 0 else 0
        balanced_pct = balanced_delta / abs(baseline_val) * 100 if baseline_val != 0 else 0
        
        print(f"{metric:<15} {aggressive_delta:>+7.4f} ({aggressive_pct:>+6.1f}%) "
              f"{balanced_delta:>+7.4f} ({balanced_pct:>+6.1f}%)")
    
    # Visualization
    print(f"\n📊 Generating plot...")
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # Cumulative returns
    ax = axes[0]
    
    baseline_cum = (1 + baseline_returns).cumprod()
    aggressive_cum = (1 + aggressive_result['returns']).cumprod()
    balanced_cum = (1 + balanced_returns).cumprod()
    
    ax.plot(baseline_cum.index, baseline_cum.values, label='Baseline', linewidth=2, alpha=0.8)
    ax.plot(aggressive_cum.index, aggressive_cum.values, label='Aggressive', linewidth=2, alpha=0.8)
    ax.plot(balanced_cum.index, balanced_cum.values, label='Balanced', linewidth=2, alpha=0.8)
    
    ax.set_ylabel('Cumulative Return', fontsize=12)
    ax.set_title('Cumulative Returns: Baseline vs Aggressive vs Balanced', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    # Rolling Sharpe
    ax = axes[1]
    
    window = 252
    baseline_rolling = baseline_returns.rolling(window).apply(
        lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
    )
    aggressive_rolling = aggressive_result['returns'].rolling(window).apply(
        lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
    )
    balanced_rolling = balanced_returns.rolling(window).apply(
        lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
    )
    
    ax.plot(baseline_rolling.index, baseline_rolling.values, label='Baseline', linewidth=2, alpha=0.8)
    ax.plot(aggressive_rolling.index, aggressive_rolling.values, label='Aggressive', linewidth=2, alpha=0.8)
    ax.plot(balanced_rolling.index, balanced_rolling.values, label='Balanced', linewidth=2, alpha=0.8)
    
    ax.axhline(y=2.0, color='green', linestyle='--', alpha=0.5, label='Target Sharpe 2.0')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Rolling 252-Day Sharpe', fontsize=12)
    ax.set_title('Rolling Sharpe Ratio', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    plot_file = output_dir / 'balanced_profile_comparison.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"   Saved: {plot_file}")
    
    # Save results
    results = {
        'baseline': {k: float(v) for k, v in baseline_metrics.items()},
        'aggressive': {k: float(v) for k, v in aggressive_metrics.items()},
        'balanced': {k: float(v) for k, v in balanced_metrics.items()},
        'config': {
            'qm_overlay': best_config,
            'exposure_scale': float(exposure_scale),
            'target_vol': float(target_vol)
        }
    }
    
    results_file = output_dir / 'balanced_profile_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    # Save returns
    returns_df = pd.DataFrame({
        'date': baseline_returns.index,
        'baseline': baseline_returns.values,
        'aggressive': aggressive_result['returns'].values,
        'balanced': balanced_returns.values
    })
    
    returns_file = output_dir / 'balanced_profile_returns.csv'
    returns_df.to_csv(returns_file, index=False)
    print(f"✅ Returns saved: {returns_file}")
    
    print(f"\n" + "="*80)
    print("✅ Balanced Profile Backtest Complete!")
    print("="*80)
    
    return results


if __name__ == "__main__":
    results = run_balanced_profile()
