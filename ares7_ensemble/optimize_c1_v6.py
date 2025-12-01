#!/usr/bin/env python3
"""
Optimize C1 v6 parameters
"""

import subprocess
import json
import pandas as pd
from pathlib import Path


def run_c1_v6(signal_span, n_long, n_short, gross, vol_filter, output_path):
    """Run C1 v6 with specific parameters"""
    cmd = [
        'python3.11', 'engine_c1_v6_simple.py',
        '--signal_span', str(signal_span),
        '--n_long', str(n_long),
        '--n_short', str(n_short),
        '--gross', str(gross),
        '--out', output_path
    ]
    
    if vol_filter:
        cmd.append('--vol_filter')
    
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
    print("C1 v6 Parameter Optimization")
    print("=" * 60)
    print()
    
    # Parameter grid
    signal_span_values = [3, 5, 7, 10]
    n_long_values = [15, 20, 25]
    n_short_values = [15, 20, 25]
    gross_values = [1.5, 2.0, 2.5]
    vol_filter_values = [True, False]
    
    results = []
    
    total_tests = len(signal_span_values) * len(n_long_values) * len(n_short_values) * len(gross_values) * len(vol_filter_values)
    test_num = 0
    
    for signal_span in signal_span_values:
        for n_long in n_long_values:
            for n_short in n_short_values:
                for gross in gross_values:
                    for vol_filter in vol_filter_values:
                        test_num += 1
                        
                        config_str = f"Span={signal_span}, Long={n_long}, Short={n_short}, Gross={gross}, VolFilter={vol_filter}"
                        print(f"[{test_num}/{total_tests}] Testing {config_str}...")
                        
                        output_path = f"./results/c1_v6_opt_s{signal_span}_l{n_long}_s{n_short}_g{gross}_v{int(vol_filter)}.json"
                        
                        data = run_c1_v6(signal_span, n_long, n_short, gross, vol_filter, output_path)
                        
                        if data:
                            results.append({
                                'signal_span': signal_span,
                                'n_long': n_long,
                                'n_short': n_short,
                                'gross': gross,
                                'vol_filter': vol_filter,
                                'sharpe': data['sharpe'],
                                'annual_return': data['annual_return'],
                                'annual_volatility': data['annual_volatility'],
                                'max_drawdown': data['max_drawdown'],
                                'avg_turnover': data['avg_turnover'],
                                'corr_ALS': data['correlations'].get('A+LS', None),
                                'corr_LV2': data['correlations'].get('LV2', None),
                                'corr_FV2': data['correlations'].get('FactorV2', None),
                                'output_file': output_path
                            })
                            
                            print(f"  Sharpe: {data['sharpe']:.3f}, Return: {data['annual_return']*100:.2f}%, "
                                  f"MDD: {data['max_drawdown']*100:.2f}%")
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
    
    print(df.head(10)[['signal_span', 'n_long', 'n_short', 'gross', 'vol_filter', 'sharpe', 'annual_return', 'max_drawdown']].to_string(index=False))
    print()
    
    # Save results
    df.to_csv('./results/c1_v6_optimization_results.csv', index=False)
    print(f"Full results saved to: ./results/c1_v6_optimization_results.csv")
    
    # Best config
    best = df.iloc[0]
    print()
    print("=" * 60)
    print("Best Configuration")
    print("=" * 60)
    print(f"  Signal span: {best['signal_span']}")
    print(f"  N long: {best['n_long']}")
    print(f"  N short: {best['n_short']}")
    print(f"  Gross: {best['gross']}")
    print(f"  Vol filter: {best['vol_filter']}")
    print(f"  Sharpe: {best['sharpe']:.3f}")
    print(f"  Annual Return: {best['annual_return']*100:.2f}%")
    print(f"  Volatility: {best['annual_volatility']*100:.2f}%")
    print(f"  Max Drawdown: {best['max_drawdown']*100:.2f}%")
    print(f"  Avg Turnover: {best['avg_turnover']:.2f}")
    print(f"  Corr with A+LS: {best['corr_ALS']:.3f}")
    print(f"  Corr with LV2: {best['corr_LV2']:.3f}")
    print(f"  Corr with FactorV2: {best['corr_FV2']:.3f}")
    print(f"  Output: {best['output_file']}")
    print("=" * 60)


if __name__ == '__main__':
    main()
