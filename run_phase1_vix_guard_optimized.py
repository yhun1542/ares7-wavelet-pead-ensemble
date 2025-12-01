#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1: VIX Guard Optimized Backtest
======================================
VIX 임계값 상향 (20 → 30+)
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).parent))

from modules.vix_global_guard import VIXGlobalGuard, VIXGuardConfig


def load_ares7_data():
    """Load ARES7-Best results"""
    results_file = Path(__file__).parent / 'results' / 'ares7_best_ensemble_results.json'
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    returns_data = data['daily_returns']
    dates = [r['date'] for r in returns_data]
    rets = [r['ret'] for r in returns_data]
    
    returns = pd.Series(rets, index=pd.to_datetime(dates), name='returns')
    returns = returns.sort_index()
    
    return returns, data


def load_vix_data():
    """Load VIX data"""
    vix_file = Path(__file__).parent / 'data' / 'vix_data.csv'
    vix_data = pd.read_csv(vix_file, index_col=0, parse_dates=True)['vix_close']
    return vix_data


def compute_metrics(returns, name="Strategy"):
    """Compute performance metrics"""
    sharpe = returns.mean() / returns.std() * np.sqrt(252)
    ann_ret = returns.mean() * 252
    ann_vol = returns.std() * np.sqrt(252)
    
    cum_returns = (1 + returns).cumprod()
    running_max = cum_returns.expanding().max()
    drawdown = cum_returns / running_max - 1.0
    max_dd = drawdown.min()
    
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0.0
    
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252)
    sortino = ann_ret / downside_std if downside_std > 0 else 0.0
    
    return {
        'name': name,
        'sharpe': sharpe,
        'sortino': sortino,
        'ann_return': ann_ret,
        'ann_vol': ann_vol,
        'max_dd': max_dd,
        'calmar': calmar,
        'returns': returns,
    }


def run_vix_guard(returns, vix_data, config_name, level_1, level_2, level_3,
                  factor_1, factor_2, factor_3):
    """Run VIX Guard with specified config"""
    print(f"\n{'='*80}")
    print(f"VIX Guard: {config_name}")
    print(f"{'='*80}")
    print(f"  Thresholds: {level_1} / {level_2} / {level_3}")
    print(f"  Factors: {factor_1} / {factor_2} / {factor_3}")
    
    config = VIXGuardConfig(
        enabled=True,
        level_reduce_1=level_1,
        level_reduce_2=level_2,
        level_reduce_3=level_3,
        reduce_factor_1=factor_1,
        reduce_factor_2=factor_2,
        reduce_factor_3=factor_3,
        enable_spike_detection=True,
        spike_zscore_threshold=2.5,
        spike_reduction_factor=0.70,
    )
    
    guard = VIXGlobalGuard(config)
    guard.initialize(vix_data)
    
    guarded_returns = guard.apply(returns)
    
    # Stats
    stats = guard.get_statistics(returns.index)
    print(f"\n  VIX Guard Stats:")
    print(f"    Avg Exposure: {stats['scale_mean']:.3f}")
    print(f"    Days Reduced: {stats['days_reduced']} / {len(returns)} ({stats['days_reduced']/len(returns)*100:.1f}%)")
    print(f"    VIX Mean: {stats['vix_mean']:.2f}, Max: {stats['vix_max']:.2f}")
    
    return guarded_returns, stats


def print_results(baseline, results_dict):
    """Print comparison table"""
    print(f"\n{'='*100}")
    print("Phase 1: VIX Guard Optimized - Results")
    print(f"{'='*100}\n")
    
    print(f"{'Configuration':<30} {'Sharpe':>10} {'Sortino':>10} {'Ann Ret':>10} {'Ann Vol':>10} {'Max DD':>10} {'Calmar':>10}")
    print("-" * 100)
    
    # Baseline
    print(f"{baseline['name']:<30} {baseline['sharpe']:>10.3f} {baseline['sortino']:>10.3f} "
          f"{baseline['ann_return']*100:>9.2f}% {baseline['ann_vol']*100:>9.2f}% "
          f"{baseline['max_dd']*100:>9.2f}% {baseline['calmar']:>10.3f}")
    
    print("-" * 100)
    
    # Results
    for key, res in results_dict.items():
        sharpe_delta = res['sharpe'] - baseline['sharpe']
        status = "✅" if sharpe_delta >= 0 else "❌"
        print(f"{res['name']:<30} {res['sharpe']:>10.3f} {res['sortino']:>10.3f} "
              f"{res['ann_return']*100:>9.2f}% {res['ann_vol']*100:>9.2f}% "
              f"{res['max_dd']*100:>9.2f}% {res['calmar']:>10.3f}  (Δ: {sharpe_delta:+.3f} {status})")
    
    print(f"{'='*100}\n")


def main():
    print("="*100)
    print("Phase 1: VIX Guard Optimized Backtest")
    print("="*100)
    
    # Load data
    print("\n1. Loading Data...")
    print("-" * 100)
    returns, ares7_data = load_ares7_data()
    vix_data = load_vix_data()
    
    print(f"✅ ARES7-Best: {len(returns)} days, Sharpe {ares7_data['sharpe']:.3f}")
    print(f"✅ VIX: {len(vix_data)} days, Mean {vix_data.mean():.2f}")
    
    # Baseline
    print("\n2. Computing Baseline...")
    print("-" * 100)
    baseline = compute_metrics(returns, "Baseline (ARES7-Best)")
    
    # Run optimized configs
    results = {}
    
    # Original (for comparison)
    print("\n3. Running Original VIX Guard (20+)...")
    print("-" * 100)
    orig_returns, orig_stats = run_vix_guard(
        returns, vix_data, "Original (20/25/30)",
        level_1=20.0, level_2=25.0, level_3=30.0,
        factor_1=0.80, factor_2=0.60, factor_3=0.40
    )
    results['original'] = compute_metrics(orig_returns, "Original (VIX 20+)")
    
    # Optimized 1: Conservative (30+)
    print("\n4. Running Optimized Conservative (30+)...")
    print("-" * 100)
    opt1_returns, opt1_stats = run_vix_guard(
        returns, vix_data, "Optimized Conservative (30/40/50)",
        level_1=30.0, level_2=40.0, level_3=50.0,
        factor_1=0.85, factor_2=0.65, factor_3=0.45
    )
    results['opt_conservative'] = compute_metrics(opt1_returns, "Optimized Conservative (30+)")
    
    # Optimized 2: Moderate (32+)
    print("\n5. Running Optimized Moderate (32+)...")
    print("-" * 100)
    opt2_returns, opt2_stats = run_vix_guard(
        returns, vix_data, "Optimized Moderate (32/42/52)",
        level_1=32.0, level_2=42.0, level_3=52.0,
        factor_1=0.88, factor_2=0.70, factor_3=0.50
    )
    results['opt_moderate'] = compute_metrics(opt2_returns, "Optimized Moderate (32+)")
    
    # Optimized 3: Aggressive (35+)
    print("\n6. Running Optimized Aggressive (35+)...")
    print("-" * 100)
    opt3_returns, opt3_stats = run_vix_guard(
        returns, vix_data, "Optimized Aggressive (35/45/55)",
        level_1=35.0, level_2=45.0, level_3=55.0,
        factor_1=0.90, factor_2=0.75, factor_3=0.55
    )
    results['opt_aggressive'] = compute_metrics(opt3_returns, "Optimized Aggressive (35+)")
    
    # Print results
    print_results(baseline, results)
    
    # Find best
    best_key = max(results.keys(), key=lambda k: results[k]['sharpe'])
    best_result = results[best_key]
    
    print(f"🏆 Best Configuration: {best_result['name']}")
    print(f"   Sharpe: {best_result['sharpe']:.3f} (Δ: {best_result['sharpe'] - baseline['sharpe']:+.3f})")
    print(f"   Ann Return: {best_result['ann_return']*100:.2f}%")
    print(f"   Max DD: {best_result['max_dd']*100:.2f}%")
    
    # Save results
    output_dir = Path(__file__).parent / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = output_dir / 'phase1_vix_guard_optimized_results.json'
    results_data = {
        'baseline': {k: v for k, v in baseline.items() if k != 'returns'},
        'original': {k: v for k, v in results['original'].items() if k != 'returns'},
        'opt_conservative': {k: v for k, v in results['opt_conservative'].items() if k != 'returns'},
        'opt_moderate': {k: v for k, v in results['opt_moderate'].items() if k != 'returns'},
        'opt_aggressive': {k: v for k, v in results['opt_aggressive'].items() if k != 'returns'},
        'best': best_key,
    }
    
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    print("\n" + "="*100)
    print("✅ Phase 1: VIX Guard Optimized - Complete!")
    print("="*100)


if __name__ == "__main__":
    main()
