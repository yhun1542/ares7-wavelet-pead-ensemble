#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARES7-Best Real Data Backtest
==============================
실제 ARES7-Best 데이터로 4축 튜닝 백테스트 실행
"""

import sys
import os
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Add paths
sys.path.append(str(Path(__file__).parent))

from risk.transaction_cost_model_v2 import TransactionCostModelV2, TCCoeffs
from risk.global_risk_scaler import GlobalRiskScaler, GlobalRiskConfig
from modules.vix_global_guard import VIXGlobalGuard, VIXGuardConfig, load_vix_data


def load_ares7_best_data():
    """Load ARES7-Best results"""
    results_file = Path(__file__).parent / 'results' / 'ares7_best_ensemble_results.json'
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    # Extract daily returns
    returns_data = data['daily_returns']
    dates = [r['date'] for r in returns_data]
    rets = [r['ret'] for r in returns_data]
    
    returns = pd.Series(rets, index=pd.to_datetime(dates), name='returns')
    returns = returns.sort_index()
    
    print(f"✅ ARES7-Best data loaded:")
    print(f"   Period: {returns.index[0].date()} ~ {returns.index[-1].date()}")
    print(f"   Days: {len(returns)}")
    print(f"   Sharpe: {data['sharpe']:.3f}")
    print(f"   Annual Return: {data['annual_return']*100:.2f}%")
    print(f"   Annual Vol: {data['annual_volatility']*100:.2f}%")
    print(f"   Max DD: {data['max_drawdown']*100:.2f}%")
    
    return returns, data


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
    
    # Sortino
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


def run_axis2_risk_scaler(returns, config_name, target_vol, max_leverage):
    """Run Axis 2: Risk Scaler"""
    print(f"\n{'='*80}")
    print(f"Axis 2: Risk Scaler ({config_name})")
    print(f"{'='*80}")
    
    risk_config = GlobalRiskConfig(
        target_vol=target_vol,
        lookback_days=63,
        max_leverage=max_leverage,
        min_leverage=0.5,
        enable_dd_reduction=True,
        dd_threshold_1=-0.10,
        dd_threshold_2=-0.15,
        dd_reduction_1=0.75,
        dd_reduction_2=0.50,
    )
    
    scaler = GlobalRiskScaler(risk_config)
    scaled_returns = scaler.apply(returns)
    
    return scaled_returns


def run_axis4_vix_guard(returns, config_name, vix_data, level_1, level_2, level_3, 
                        factor_1, factor_2, factor_3):
    """Run Axis 4: VIX Guard"""
    print(f"\n{'='*80}")
    print(f"Axis 4: VIX Guard ({config_name})")
    print(f"{'='*80}")
    
    vix_config = VIXGuardConfig(
        enabled=True,
        level_reduce_1=level_1,
        level_reduce_2=level_2,
        level_reduce_3=level_3,
        reduce_factor_1=factor_1,
        reduce_factor_2=factor_2,
        reduce_factor_3=factor_3,
        enable_spike_detection=True,
        spike_zscore_threshold=2.0,
        spike_reduction_factor=0.50,
    )
    
    guard = VIXGlobalGuard(vix_config)
    guard.initialize(vix_data)
    
    guarded_returns = guard.apply(returns)
    
    # Stats
    stats = guard.get_statistics(returns.index)
    print(f"   VIX Guard Stats:")
    print(f"     Avg Exposure Scale: {stats['scale_mean']:.3f}")
    print(f"     Days Reduced: {stats['days_reduced']} / {len(returns)} ({stats['days_reduced']/len(returns)*100:.1f}%)")
    print(f"     VIX Mean: {stats['vix_mean']:.2f}, Max: {stats['vix_max']:.2f}")
    
    return guarded_returns


def run_combined(returns, config_name, vix_data, target_vol, max_leverage,
                 vix_level_1, vix_level_2, vix_level_3,
                 vix_factor_1, vix_factor_2, vix_factor_3):
    """Run combined (Axis 2 + Axis 4)"""
    print(f"\n{'='*80}")
    print(f"Combined: Risk Scaler + VIX Guard ({config_name})")
    print(f"{'='*80}")
    
    # Axis 2: Risk Scaler
    risk_config = GlobalRiskConfig(
        target_vol=target_vol,
        lookback_days=63,
        max_leverage=max_leverage,
        min_leverage=0.5,
        enable_dd_reduction=True,
        dd_threshold_1=-0.10,
        dd_threshold_2=-0.15,
        dd_reduction_1=0.75,
        dd_reduction_2=0.50,
    )
    
    scaler = GlobalRiskScaler(risk_config)
    scaled_returns = scaler.apply(returns)
    
    # Axis 4: VIX Guard
    vix_config = VIXGuardConfig(
        enabled=True,
        level_reduce_1=vix_level_1,
        level_reduce_2=vix_level_2,
        level_reduce_3=vix_level_3,
        reduce_factor_1=vix_factor_1,
        reduce_factor_2=vix_factor_2,
        reduce_factor_3=vix_factor_3,
        enable_spike_detection=True,
        spike_zscore_threshold=2.0,
        spike_reduction_factor=0.50,
    )
    
    guard = VIXGlobalGuard(vix_config)
    guard.initialize(vix_data)
    
    combined_returns = guard.apply(scaled_returns)
    
    return combined_returns


def print_results_table(baseline, results_dict):
    """Print results comparison table"""
    print(f"\n{'='*100}")
    print("ARES7-Best Tuning Backtest Results")
    print(f"{'='*100}\n")
    
    # Header
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
        print(f"{res['name']:<30} {res['sharpe']:>10.3f} {res['sortino']:>10.3f} "
              f"{res['ann_return']*100:>9.2f}% {res['ann_vol']*100:>9.2f}% "
              f"{res['max_dd']*100:>9.2f}% {res['calmar']:>10.3f}  (Δ Sharpe: {sharpe_delta:+.3f})")
    
    print(f"{'='*100}\n")


def plot_results(baseline, results_dict, output_file):
    """Plot cumulative returns comparison"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Cumulative Returns
    ax = axes[0, 0]
    cum_baseline = (1 + baseline['returns']).cumprod()
    ax.plot(cum_baseline.index, cum_baseline.values, label='Baseline', linewidth=2, color='black')
    
    colors = ['blue', 'green', 'red', 'purple', 'orange', 'brown']
    for i, (key, res) in enumerate(results_dict.items()):
        cum_ret = (1 + res['returns']).cumprod()
        ax.plot(cum_ret.index, cum_ret.values, label=res['name'], 
                linewidth=1.5, alpha=0.7, color=colors[i % len(colors)])
    
    ax.set_title('Cumulative Returns', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Cumulative Return')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Drawdown
    ax = axes[0, 1]
    cum_baseline = (1 + baseline['returns']).cumprod()
    running_max = cum_baseline.expanding().max()
    dd_baseline = (cum_baseline / running_max - 1.0) * 100
    ax.fill_between(dd_baseline.index, dd_baseline.values, 0, alpha=0.3, color='black', label='Baseline')
    
    for i, (key, res) in enumerate(results_dict.items()):
        cum_ret = (1 + res['returns']).cumprod()
        running_max = cum_ret.expanding().max()
        dd = (cum_ret / running_max - 1.0) * 100
        ax.plot(dd.index, dd.values, label=res['name'], linewidth=1.5, alpha=0.7, color=colors[i % len(colors)])
    
    ax.set_title('Drawdown (%)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Drawdown (%)')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Sharpe Comparison
    ax = axes[1, 0]
    names = ['Baseline'] + [res['name'] for res in results_dict.values()]
    sharpes = [baseline['sharpe']] + [res['sharpe'] for res in results_dict.values()]
    bars = ax.bar(range(len(names)), sharpes, color=['black'] + colors[:len(results_dict)])
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha='right')
    ax.set_ylabel('Sharpe Ratio')
    ax.set_title('Sharpe Ratio Comparison', fontsize=14, fontweight='bold')
    ax.axhline(y=2.0, color='red', linestyle='--', linewidth=2, label='Target (2.0)')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}', ha='center', va='bottom', fontsize=10)
    
    # Plot 4: Metrics Comparison
    ax = axes[1, 1]
    metrics = ['Sharpe', 'Sortino', 'Calmar']
    baseline_metrics = [baseline['sharpe'], baseline['sortino'], baseline['calmar']]
    
    x = np.arange(len(metrics))
    width = 0.15
    
    ax.bar(x - width*2, baseline_metrics, width, label='Baseline', color='black')
    
    for i, (key, res) in enumerate(results_dict.items()):
        res_metrics = [res['sharpe'], res['sortino'], res['calmar']]
        ax.bar(x + width*(i-1), res_metrics, width, label=res['name'], color=colors[i % len(colors)])
    
    ax.set_ylabel('Ratio')
    ax.set_title('Risk-Adjusted Metrics Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n✅ Plot saved: {output_file}")


def main():
    print("="*100)
    print("ARES7-Best Real Data Backtest - 4-Axis Tuning")
    print("="*100)
    
    # 1. Load ARES7-Best data
    print("\n1. Loading ARES7-Best Data...")
    print("-" * 100)
    returns, ares7_data = load_ares7_best_data()
    
    # 2. Load VIX data from CSV
    print("\n2. Loading VIX Data...")
    print("-" * 100)
    vix_file = '/home/ubuntu/ares7-ensemble/data/vix_data.csv'
    vix_data = pd.read_csv(vix_file, index_col=0, parse_dates=True)['vix_close']
    print(f"✅ VIX data loaded from CSV: {len(vix_data)} days")
    print(f"   Period: {vix_data.index[0].date()} ~ {vix_data.index[-1].date()}")
    print(f"   Mean: {vix_data.mean():.2f}, Max: {vix_data.max():.2f}")
    
    # 3. Baseline metrics
    print("\n3. Computing Baseline Metrics...")
    print("-" * 100)
    baseline = compute_metrics(returns, "Baseline (ARES7-Best)")
    
    # 4. Run backtests
    results = {}
    
    # Conservative
    print("\n4. Running Conservative Configuration...")
    print("=" * 100)
    cons_risk = run_axis2_risk_scaler(returns, "Conservative", target_vol=0.08, max_leverage=1.5)
    cons_vix = run_axis4_vix_guard(returns, "Conservative", vix_data, 
                                     level_1=20.0, level_2=25.0, level_3=30.0,
                                     factor_1=0.80, factor_2=0.60, factor_3=0.40)
    cons_combined = run_combined(returns, "Conservative", vix_data,
                                  target_vol=0.08, max_leverage=1.5,
                                  vix_level_1=20.0, vix_level_2=25.0, vix_level_3=30.0,
                                  vix_factor_1=0.80, vix_factor_2=0.60, vix_factor_3=0.40)
    
    results['cons_combined'] = compute_metrics(cons_combined, "Conservative (Combined)")
    
    # Moderate
    print("\n5. Running Moderate Configuration...")
    print("=" * 100)
    mod_risk = run_axis2_risk_scaler(returns, "Moderate", target_vol=0.10, max_leverage=2.0)
    mod_vix = run_axis4_vix_guard(returns, "Moderate", vix_data,
                                    level_1=25.0, level_2=30.0, level_3=35.0,
                                    factor_1=0.75, factor_2=0.50, factor_3=0.25)
    mod_combined = run_combined(returns, "Moderate", vix_data,
                                 target_vol=0.10, max_leverage=2.0,
                                 vix_level_1=25.0, vix_level_2=30.0, vix_level_3=35.0,
                                 vix_factor_1=0.75, vix_factor_2=0.50, vix_factor_3=0.25)
    
    results['mod_combined'] = compute_metrics(mod_combined, "Moderate (Combined)")
    
    # Aggressive
    print("\n6. Running Aggressive Configuration...")
    print("=" * 100)
    agg_risk = run_axis2_risk_scaler(returns, "Aggressive", target_vol=0.12, max_leverage=2.5)
    agg_vix = run_axis4_vix_guard(returns, "Aggressive", vix_data,
                                    level_1=30.0, level_2=35.0, level_3=40.0,
                                    factor_1=0.70, factor_2=0.40, factor_3=0.20)
    agg_combined = run_combined(returns, "Aggressive", vix_data,
                                 target_vol=0.12, max_leverage=2.5,
                                 vix_level_1=30.0, vix_level_2=35.0, vix_level_3=40.0,
                                 vix_factor_1=0.70, vix_factor_2=0.40, vix_factor_3=0.20)
    
    results['agg_combined'] = compute_metrics(agg_combined, "Aggressive (Combined)")
    
    # 5. Print results
    print_results_table(baseline, results)
    
    # 6. Plot results
    output_file = Path(__file__).parent / 'tuning' / 'results' / 'ares7_tuning_results.png'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plot_results(baseline, results, str(output_file))
    
    # 7. Save results
    results_file = Path(__file__).parent / 'tuning' / 'results' / 'ares7_tuning_results.json'
    results_data = {
        'baseline': {k: v for k, v in baseline.items() if k != 'returns'},
        'conservative': {k: v for k, v in results['cons_combined'].items() if k != 'returns'},
        'moderate': {k: v for k, v in results['mod_combined'].items() if k != 'returns'},
        'aggressive': {k: v for k, v in results['agg_combined'].items() if k != 'returns'},
    }
    
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"✅ Results saved: {results_file}")
    
    print("\n" + "="*100)
    print("✅ ARES7-Best Tuning Backtest Complete!")
    print("="*100)


if __name__ == "__main__":
    main()
