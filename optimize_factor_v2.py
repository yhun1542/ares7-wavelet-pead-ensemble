#!/usr/bin/env python3
"""
Optimize Factor v2 parameters
Test different combinations of Q and rebalance frequency
"""

import subprocess
import json
import pandas as pd
from pathlib import Path


def run_factor_v2(q, rebalance, lookback_mom, gross, output_path):
    """Run Factor v2 with specific parameters"""
    cmd = [
        'python3.11', 'engine_factor_v2.py',
        '--q', str(q),
        '--rebalance', rebalance,
        '--lookback_mom', str(lookback_mom),
        '--gross', str(gross),
        '--out', output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:200]}")
        return None
    
    # Load results
    with open(output_path, 'r') as f:
        data = json.load(f)
    
    return data


def main():
    print("=" * 60)
    print("Factor v2 Parameter Optimization")
    print("=" * 60)
    print()
    
    # Parameter grid
    q_values = [0.05, 0.1, 0.15, 0.2]
    rebalance_values = ['W', 'M']
    lookback_values = [40, 60, 80]
    gross_values = [1.5, 2.0, 2.5]
    
    results = []
    
    total_tests = len(q_values) * len(rebalance_values) * len(lookback_values) * len(gross_values)
    test_num = 0
    
    for q in q_values:
        for rebal in rebalance_values:
            for lookback in lookback_values:
                for gross in gross_values:
                    test_num += 1
                    
                    config_str = f"Q={q}, Rebal={rebal}, Lookback={lookback}, Gross={gross}"
                    print(f"[{test_num}/{total_tests}] Testing {config_str}...")
                    
                    output_path = f"./results/factor_v2_opt_q{q}_r{rebal}_l{lookback}_g{gross}.json"
                    
                    data = run_factor_v2(q, rebal, lookback, gross, output_path)
                    
                    if data:
                        results.append({
                            'q': q,
                            'rebalance': rebal,
                            'lookback': lookback,
                            'gross': gross,
                            'sharpe': data['sharpe'],
                            'annual_return': data['annual_return'],
                            'annual_volatility': data['annual_volatility'],
                            'max_drawdown': data['max_drawdown'],
                            'avg_turnover': data['avg_turnover'],
                            'corr_C1': data['correlations'].get('C1', None),
                            'corr_LV2': data['correlations'].get('LV2', None),
                            'output_file': output_path
                        })
                        
                        print(f"  Sharpe: {data['sharpe']:.3f}, Return: {data['annual_return']*100:.2f}%, "
                              f"Vol: {data['annual_volatility']*100:.2f}%, MDD: {data['max_drawdown']*100:.2f}%")
                    else:
                        print(f"  FAILED")
                    
                    print()
    
    # Create results DataFrame
    df = pd.DataFrame(results)
    
    # Sort by Sharpe
    df = df.sort_values('sharpe', ascending=False)
    
    print("=" * 60)
    print("Top 10 Configurations by Sharpe Ratio")
    print("=" * 60)
    print()
    
    print(df.head(10).to_string(index=False))
    print()
    
    # Save results
    df.to_csv('./results/factor_v2_optimization_results.csv', index=False)
    print(f"Full results saved to: ./results/factor_v2_optimization_results.csv")
    
    # Best config
    best = df.iloc[0]
    print()
    print("=" * 60)
    print("Best Configuration")
    print("=" * 60)
    print(f"  Q: {best['q']}")
    print(f"  Rebalance: {best['rebalance']}")
    print(f"  Lookback: {best['lookback']}")
    print(f"  Gross: {best['gross']}")
    print(f"  Sharpe: {best['sharpe']:.3f}")
    print(f"  Annual Return: {best['annual_return']*100:.2f}%")
    print(f"  Volatility: {best['annual_volatility']*100:.2f}%")
    print(f"  Max Drawdown: {best['max_drawdown']*100:.2f}%")
    print(f"  Avg Turnover: {best['avg_turnover']:.2f}")
    print(f"  Corr with C1: {best['corr_C1']:.3f}")
    print(f"  Corr with LV2: {best['corr_LV2']:.3f}")
    print(f"  Output: {best['output_file']}")
    print("=" * 60)


if __name__ == '__main__':
    main()
