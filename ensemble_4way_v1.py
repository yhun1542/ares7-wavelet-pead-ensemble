#!/usr/bin/env python3.11
"""
ARES-7 4-Way Ensemble v1
========================

Equal-weight ensemble of 4 engines:
- A+LS Enhanced (Sharpe 0.947)
- C1 Final v5 (Sharpe 0.715)
- Low-Vol v2 Final (Sharpe 0.808)
- Factor (Value Only) (Sharpe 0.555)

Expected Performance:
- Sharpe: 1.22-1.26
- Return: 13-14%
- Vol: 10-11%
- MDD: -16% ~ -17%

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
    print("ARES-7 4-Way Ensemble v1")
    print("="*80)
    
    # Load engines
    engines = {
        'A+LS': 'ares7_ensemble/results/engine_ls_enhanced_results.json',
        'C1': 'ares7_ensemble/results/C1_final_v5.json',
        'LV2': 'ares7_ensemble/results/engine_c_lowvol_v2_final_results.json',
        'Factor': 'results/engine_factor_value_only.json'
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
    
    print(f"\n{'Engine':<10} {'Sharpe':>8} {'Return':>8} {'Vol':>8} {'MDD':>8}")
    print("-"*80)
    
    for name in engines.keys():
        metrics = calculate_metrics(returns_dict[name])
        print(f"{name:<10} {metrics['sharpe']:>8.4f} {metrics['return']:>7.2%} {metrics['vol']:>7.2%} {metrics['mdd']:>7.2%}")
    
    # Equal-weight ensemble
    weights = np.array([0.25, 0.25, 0.25, 0.25])
    ensemble_returns = (returns_df * weights).sum(axis=1)
    
    ensemble_metrics = calculate_metrics(ensemble_returns)
    
    print("\n" + "="*80)
    print("4-Way Ensemble (Equal Weight)")
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
    
    # Calculate diversification benefit
    avg_individual_sharpe = np.mean([calculate_metrics(returns_dict[name])['sharpe'] for name in engines.keys()])
    diversification_benefit = (ensemble_metrics['sharpe'] - avg_individual_sharpe) / avg_individual_sharpe * 100
    
    print(f"\n{'Average Individual Sharpe':<20} {avg_individual_sharpe:>10.4f}")
    print(f"{'Diversification Benefit':<20} {diversification_benefit:>9.1f}%")
    
    # Save results
    results = {
        'ensemble_name': '4-Way Equal Weight',
        'engines': list(engines.keys()),
        'weights': weights.tolist(),
        'metrics': ensemble_metrics,
        'correlation_matrix': corr_matrix.to_dict(),
        'avg_individual_sharpe': avg_individual_sharpe,
        'diversification_benefit_pct': diversification_benefit,
        'daily_returns': ensemble_returns.tolist(),
        'timestamp': datetime.now().isoformat()
    }
    
    with open('results/ensemble_4way_v1.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved: results/ensemble_4way_v1.json")

if __name__ == '__main__':
    main()
