#!/usr/bin/env python3
"""
ARES-7 5-Way Ensemble with Factor v2
=====================================
Combine 5 engines:
1. A+LS Enhanced
2. C1 Final v5
3. Low-Vol v2 Final
4. Factor v2 Best
5. (Optional) Additional engine

Target: Sharpe 2.0+
"""

import pandas as pd
import numpy as np
import json
import argparse
from pathlib import Path


def load_engine_results(path, name):
    """Load engine results from JSON"""
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Convert daily_returns to Series
    if isinstance(data['daily_returns'], list):
        if len(data['daily_returns']) > 0 and isinstance(data['daily_returns'][0], dict):
            # Format: [{'date': ..., 'ret': ...}, ...]
            returns = pd.Series({
                pd.Timestamp(d['date']): d['ret']
                for d in data['daily_returns']
            })
        else:
            # Format: [0.01, 0.02, ...]
            # Need dates from 'dates' field
            if 'dates' in data:
                returns = pd.Series(data['daily_returns'], index=pd.to_datetime(data['dates']))
            else:
                returns = pd.Series(data['daily_returns'])
    else:
        raise ValueError(f"Invalid daily_returns format in {path}")
    
    # Get stats
    stats = {
        'sharpe': data.get('sharpe', np.nan),
        'annual_return': data.get('annual_return', np.nan),
        'annual_volatility': data.get('annual_volatility', np.nan),
        'max_drawdown': data.get('max_drawdown', np.nan)
    }
    
    print(f"  {name}: {len(returns)} days, Sharpe {stats['sharpe']:.3f}")
    
    return returns, stats


def calculate_ensemble_metrics(combined_returns):
    """Calculate performance metrics"""
    annual_return = combined_returns.mean() * 252
    annual_volatility = combined_returns.std() * np.sqrt(252)
    sharpe = annual_return / annual_volatility if annual_volatility > 0 else 0
    
    # Max drawdown
    cumulative = (1 + combined_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()
    
    return {
        'sharpe': sharpe,
        'annual_return': annual_return,
        'annual_volatility': annual_volatility,
        'max_drawdown': max_drawdown
    }


def apply_volatility_target(combined_returns, target_vol=0.12):
    """Apply volatility targeting"""
    # Calculate rolling volatility (60-day)
    rolling_vol = combined_returns.rolling(60, min_periods=20).std() * np.sqrt(252)
    
    # Calculate leverage
    leverage = target_vol / rolling_vol
    leverage = leverage.fillna(1.0)
    leverage = leverage.clip(0.5, 2.0)  # Limit leverage
    
    # Apply leverage
    scaled_returns = combined_returns * leverage
    
    return scaled_returns


def main():
    parser = argparse.ArgumentParser(description='ARES-7 5-Way Ensemble with Factor v2')
    parser.add_argument('--a', default='./results/A+LS_enhanced_results.json')
    parser.add_argument('--c1', default='./results/C1_final_v5.json')
    parser.add_argument('--lv', default='./results/engine_c_lowvol_v2_final_results.json')
    parser.add_argument('--fv2', default='./results/engine_factor_v2_best.json')
    parser.add_argument('--vol_target', type=float, default=0.12, help='Target volatility (default: 12%)')
    parser.add_argument('--out_json', default='./results/ensemble_5way_factor_v2_summary.json')
    parser.add_argument('--out_csv', default='./results/ensemble_5way_factor_v2_results.csv')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ARES-7 5-Way Ensemble with Factor v2")
    print("=" * 60)
    print()
    
    # Load engines
    print("Loading engines...")
    engines = {}
    engine_stats = {}
    
    engine_paths = {
        'A+LS': args.a,
        'C1': args.c1,
        'LV2': args.lv,
        'FactorV2': args.fv2
    }
    
    for name, path in engine_paths.items():
        if Path(path).exists():
            returns, stats = load_engine_results(path, name)
            engines[name] = returns
            engine_stats[name] = stats
        else:
            print(f"  WARNING: {name} not found at {path}")
    
    print()
    
    if len(engines) < 3:
        print("ERROR: Need at least 3 engines")
        return
    
    # Align all returns
    print("Aligning returns...")
    all_returns = pd.DataFrame(engines)
    all_returns = all_returns.dropna()
    
    print(f"  Aligned period: {all_returns.index[0]} to {all_returns.index[-1]}")
    print(f"  Total days: {len(all_returns)}")
    print()
    
    # Calculate correlations
    print("Correlation Matrix:")
    corr_matrix = all_returns.corr()
    print(corr_matrix.to_string())
    print()
    
    # Equal-weight ensemble
    print("=" * 60)
    print("Equal-Weight Ensemble (No Vol Targeting)")
    print("=" * 60)
    
    combined_returns = all_returns.mean(axis=1)
    metrics = calculate_ensemble_metrics(combined_returns)
    
    print(f"  Sharpe Ratio: {metrics['sharpe']:.3f}")
    print(f"  Annual Return: {metrics['annual_return']*100:.2f}%")
    print(f"  Annual Volatility: {metrics['annual_volatility']*100:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
    print()
    
    # With volatility targeting
    print("=" * 60)
    print(f"Equal-Weight Ensemble (Vol Target {args.vol_target*100:.0f}%)")
    print("=" * 60)
    
    scaled_returns = apply_volatility_target(combined_returns, args.vol_target)
    metrics_vol = calculate_ensemble_metrics(scaled_returns)
    
    print(f"  Sharpe Ratio: {metrics_vol['sharpe']:.3f}")
    print(f"  Annual Return: {metrics_vol['annual_return']*100:.2f}%")
    print(f"  Annual Volatility: {metrics_vol['annual_volatility']*100:.2f}%")
    print(f"  Max Drawdown: {metrics_vol['max_drawdown']*100:.2f}%")
    print()
    
    # Save results
    output = {
        'ensemble_type': '5-Way Equal-Weight with Factor v2',
        'engines': list(engines.keys()),
        'engine_stats': engine_stats,
        'correlation_matrix': corr_matrix.to_dict(),
        'no_vol_targeting': metrics,
        'with_vol_targeting': metrics_vol,
        'vol_target': args.vol_target,
        'daily_returns': scaled_returns.tolist(),
        'dates': [d.strftime('%Y-%m-%d') for d in scaled_returns.index]
    }
    
    with open(args.out_json, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Results saved to: {args.out_json}")
    
    # Save CSV
    results_df = pd.DataFrame({
        'date': scaled_returns.index,
        'return': scaled_returns.values,
        'cumulative': (1 + scaled_returns).cumprod().values
    })
    results_df.to_csv(args.out_csv, index=False)
    print(f"CSV saved to: {args.out_csv}")
    
    print("=" * 60)
    
    # Compare with 4-Way
    print()
    print("=" * 60)
    print("Comparison with 4-Way Ensemble")
    print("=" * 60)
    
    if Path('./results/ensemble_4way_v2_with_vol_summary.json').exists():
        with open('./results/ensemble_4way_v2_with_vol_summary.json', 'r') as f:
            old_ensemble = json.load(f)
        
        print(f"  4-Way Sharpe: {old_ensemble['with_vol_targeting']['sharpe']:.3f}")
        print(f"  5-Way Sharpe: {metrics_vol['sharpe']:.3f}")
        print(f"  Improvement: {(metrics_vol['sharpe'] - old_ensemble['with_vol_targeting']['sharpe']):.3f} "
              f"({(metrics_vol['sharpe'] / old_ensemble['with_vol_targeting']['sharpe'] - 1)*100:.1f}%)")
        print()
        print(f"  4-Way MDD: {old_ensemble['with_vol_targeting']['max_drawdown']*100:.2f}%")
        print(f"  5-Way MDD: {metrics_vol['max_drawdown']*100:.2f}%")
        print(f"  Improvement: {(metrics_vol['max_drawdown'] - old_ensemble['with_vol_targeting']['max_drawdown'])*100:.2f}%")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
