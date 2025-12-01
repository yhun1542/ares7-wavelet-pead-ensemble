#!/usr/bin/env python3.11
"""
ARES-7 7-Way Ensemble with Optimal Weights
===========================================

Optimal-weight ensemble of 7 engines:
- A+LS Enhanced: 8.7% (Sharpe 0.947)
- C1 Final v5: 9.0% (Sharpe 0.715)
- Low-Vol v2: 11.7% (Sharpe 0.808)
- Factor (Value): 14.9% (Sharpe 0.555)
- FV2_1 (q=0.15): 42.9% (Sharpe 1.430)
- FV2_2 (q=0.20): 8.4% (Sharpe 1.356)
- FV2_3 (q=0.05): 4.5% (Sharpe 1.155)

Expected Performance:
- Sharpe: 1.89-1.90
- Return: 13-14%
- Vol: 6-7%
- MDD: -6% ~ -7%

Optimization Method: Grid Search (105 combinations)
Best Found: Random_44

Author: Jason (yhun1542)
Date: 2025-11-26
Version: 1.0.0
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime

def load_engine_returns(path):
    """Load engine returns from JSON file"""
    with open(path) as f:
        data = json.load(f)
    
    if 'daily_returns' in data:
        if isinstance(data['daily_returns'], list):
            if isinstance(data['daily_returns'][0], dict):
                returns = [d['ret'] for d in data['daily_returns']]
            else:
                returns = data['daily_returns']
        return pd.Series(returns)
    
    return None

def calculate_metrics(returns):
    """Calculate performance metrics"""
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    annual_ret = (1 + returns).prod() ** (252 / len(returns)) - 1
    annual_vol = returns.std() * np.sqrt(252)
    
    cum_ret = (1 + returns).cumprod()
    running_max = cum_ret.expanding().max()
    drawdown = (cum_ret - running_max) / running_max
    mdd = drawdown.min()
    
    win_rate = (returns > 0).sum() / len(returns)
    
    calmar = annual_ret / abs(mdd) if mdd != 0 else 0
    
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
    sortino = annual_ret / downside_std if downside_std > 0 else 0
    
    return {
        'sharpe': sharpe,
        'return': annual_ret,
        'vol': annual_vol,
        'mdd': mdd,
        'win_rate': win_rate,
        'calmar': calmar,
        'sortino': sortino
    }

def main():
    print("="*80)
    print("ARES-7 7-Way Ensemble with Optimal Weights")
    print("="*80)
    
    # Load engines
    engines = {
        'A+LS': 'ares7_ensemble/results/engine_ls_enhanced_results.json',
        'C1': 'ares7_ensemble/results/C1_final_v5.json',
        'LV2': 'ares7_ensemble/results/engine_c_lowvol_v2_final_results.json',
        'Factor': 'results/engine_factor_value_only.json',
        'FV2_1': 'results/factor_v2_opt_q0.15_rW_l40_g2.0.json',
        'FV2_2': 'results/factor_v2_opt_q0.2_rW_l40_g1.5.json',
        'FV2_3': 'results/factor_v2_opt_q0.05_rW_l40_g2.0.json',
    }
    
    # Optimal weights from grid search
    optimal_weights = {
        'A+LS': 0.087,
        'C1': 0.090,
        'LV2': 0.117,
        'Factor': 0.149,
        'FV2_1': 0.429,
        'FV2_2': 0.084,
        'FV2_3': 0.045
    }
    
    returns_dict = {}
    
    print("\nLoading engines...")
    for name, path in engines.items():
        returns = load_engine_returns(path)
        if returns is not None:
            returns_dict[name] = returns
            print(f"  ✅ {name}: {len(returns)} days")
        else:
            print(f"  ❌ {name}: Failed to load")
    
    # Align returns
    min_len = min(len(r) for r in returns_dict.values())
    for name in returns_dict:
        returns_dict[name] = returns_dict[name][:min_len]
    
    print(f"\nAligned to {min_len} days")
    
    # Convert to DataFrame
    returns_df = pd.DataFrame(returns_dict)
    
    # Calculate correlation matrix
    corr_matrix = returns_df.corr()
    
    print("\n" + "="*80)
    print("Correlation Matrix")
    print("="*80)
    print(corr_matrix.round(3))
    
    # Calculate individual metrics
    print("\n" + "="*80)
    print("Individual Engine Performance")
    print("="*80)
    
    print(f"\n{'Engine':<10} {'Weight':>8} {'Sharpe':>8} {'Return':>8} {'Vol':>8} {'MDD':>8}")
    print("-"*80)
    
    for name in engines.keys():
        metrics = calculate_metrics(returns_dict[name])
        weight = optimal_weights[name]
        print(f"{name:<10} {weight:>7.1%} {metrics['sharpe']:>8.4f} {metrics['return']:>7.2%} {metrics['vol']:>7.2%} {metrics['mdd']:>7.2%}")
    
    # Apply optimal weights
    weights_array = np.array([optimal_weights[name] for name in engines.keys()])
    ensemble_returns = (returns_df * weights_array).sum(axis=1)
    
    ensemble_metrics = calculate_metrics(ensemble_returns)
    
    print("\n" + "="*80)
    print("7-Way Ensemble (Optimal Weights)")
    print("="*80)
    
    print(f"\n{'Metric':<20} {'Value':>10}")
    print("-"*40)
    print(f"{'Sharpe Ratio':<20} {ensemble_metrics['sharpe']:>10.4f}")
    print(f"{'Annual Return':<20} {ensemble_metrics['return']:>9.2%}")
    print(f"{'Annual Volatility':<20} {ensemble_metrics['vol']:>9.2%}")
    print(f"{'Maximum Drawdown':<20} {ensemble_metrics['mdd']:>9.2%}")
    print(f"{'Win Rate':<20} {ensemble_metrics['win_rate']:>9.2%}")
    print(f"{'Calmar Ratio':<20} {ensemble_metrics['calmar']:>10.2f}")
    print(f"{'Sortino Ratio':<20} {ensemble_metrics['sortino']:>10.2f}")
    
    # Compare with equal weight
    equal_weights = np.array([1/7] * 7)
    equal_ensemble_returns = (returns_df * equal_weights).sum(axis=1)
    equal_metrics = calculate_metrics(equal_ensemble_returns)
    
    improvement = (ensemble_metrics['sharpe'] - equal_metrics['sharpe']) / equal_metrics['sharpe'] * 100
    
    print(f"\n{'Equal Weight Sharpe':<20} {equal_metrics['sharpe']:>10.4f}")
    print(f"{'Optimal Weight Sharpe':<20} {ensemble_metrics['sharpe']:>10.4f}")
    print(f"{'Improvement':<20} {improvement:>9.1f}%")
    
    # Weight concentration
    print("\n" + "="*80)
    print("Weight Analysis")
    print("="*80)
    
    print(f"\nTop 3 Engines:")
    sorted_weights = sorted(optimal_weights.items(), key=lambda x: x[1], reverse=True)
    for i, (name, weight) in enumerate(sorted_weights[:3], 1):
        print(f"  {i}. {name}: {weight:.1%}")
    
    top3_concentration = sum([w for _, w in sorted_weights[:3]])
    print(f"\nTop 3 Concentration: {top3_concentration:.1%}")
    
    # Factor engines concentration
    factor_engines = ['Factor', 'FV2_1', 'FV2_2', 'FV2_3']
    factor_weight = sum([optimal_weights[name] for name in factor_engines])
    print(f"Factor Engines Total: {factor_weight:.1%}")
    
    # Save results
    results = {
        'ensemble_name': '7-Way Optimal Weight',
        'engines': list(engines.keys()),
        'weights': optimal_weights,
        'metrics': ensemble_metrics,
        'equal_weight_metrics': equal_metrics,
        'improvement_pct': improvement,
        'correlation_matrix': corr_matrix.to_dict(),
        'top3_concentration': top3_concentration,
        'factor_engines_weight': factor_weight,
        'daily_returns': ensemble_returns.tolist(),
        'optimization_method': 'Grid Search (105 combinations)',
        'best_combination': 'Random_44',
        'timestamp': datetime.now().isoformat()
    }
    
    with open('results/ensemble_7way_optimal.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved: results/ensemble_7way_optimal.json")

if __name__ == '__main__':
    main()
