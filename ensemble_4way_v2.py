#!/usr/bin/env python3
"""
ARES-7 4-Way Ensemble v2
Replaces Low-Vol v1 with v2 Final
"""

import argparse
import pandas as pd
import numpy as np
import json

def load_engine_results(path, name):
    """Load engine results from JSON"""
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Convert daily_returns to Series
    returns = pd.Series({
        pd.Timestamp(d['date']): d['ret']
        for d in data['daily_returns']
    })
    
    # Get stats
    stats = {
        'sharpe': data.get('sharpe', np.nan),
        'annual_return': data.get('annual_return', np.nan),
        'annual_volatility': data.get('annual_volatility', np.nan),
        'max_drawdown': data.get('max_drawdown', np.nan)
    }
    
    print(f"  {name}: {len(returns)} days, Sharpe {stats['sharpe']:.3f}")
    
    return returns, stats

def calculate_stats(returns):
    """Calculate performance statistics"""
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    annual_return = returns.mean() * 252
    annual_vol = returns.std() * np.sqrt(252)
    
    cumret = (1 + returns).cumprod()
    cummax = cumret.expanding().max()
    dd = (cumret - cummax) / cummax
    max_dd = dd.min()
    
    return {
        'sharpe': float(sharpe),
        'annual_return': float(annual_return),
        'annual_volatility': float(annual_vol),
        'max_drawdown': float(max_dd)
    }

def main():
    parser = argparse.ArgumentParser(description='ARES-7 4-Way Ensemble v2')
    parser.add_argument('--e1', default='./results/engine_ls_enhanced_results.json')
    parser.add_argument('--c1', default='./results/C1_final_v5.json')
    parser.add_argument('--lv', default='./results/engine_c_lowvol_v2_final_results.json')
    parser.add_argument('--f', default='./results/engine_factor_final_results.json')
    parser.add_argument('--out_json', default='./results/ensemble_4way_v2_summary.json')
    parser.add_argument('--out_csv', default='./results/ensemble_4way_v2_results.csv')
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 4-Way Ensemble v2 (with Low-Vol v2 Final)")
    print("=" * 70)
    
    # Load engines
    print("\nLoading engines...")
    e1_ret, e1_stats = load_engine_results(args.e1, "A+LS Enhanced")
    c1_ret, c1_stats = load_engine_results(args.c1, "C1 Final v5")
    lv_ret, lv_stats = load_engine_results(args.lv, "Low-Vol v2 Final")
    f_ret, f_stats = load_engine_results(args.f, "Factor Final")
    
    # Combine returns
    print("\nCombining returns...")
    df = pd.DataFrame({
        'E1': e1_ret,
        'C1': c1_ret,
        'LV': lv_ret,
        'F': f_ret
    })
    df = df.dropna()
    
    print(f"  Common dates: {len(df)}")
    
    # Recalculate individual stats on common dates
    print("\nRecalculating individual engine stats...")
    engine_stats = {}
    for col in df.columns:
        stats = calculate_stats(df[col])
        engine_stats[col] = stats
        print(f"  {col}: Sharpe {stats['sharpe']:.3f}, Return {stats['annual_return']:.2%}, MDD {stats['max_drawdown']:.2%}")
    
    # Correlation matrix
    print("\nCalculating correlation matrix...")
    corr_matrix = df.corr()
    print(corr_matrix.to_string())
    
    # Fixed portfolio v2
    print("\n" + "=" * 70)
    print("Fixed Portfolio v2")
    print("=" * 70)
    
    weights_fixed = np.array([0.30, 0.20, 0.20, 0.30])  # [E1, C1, LV, F]
    print(f"Weights: A+LS={weights_fixed[0]:.0%}, C1={weights_fixed[1]:.0%}, LV={weights_fixed[2]:.0%}, F={weights_fixed[3]:.0%}")
    
    ret_fixed = df.values @ weights_fixed
    ret_fixed_series = pd.Series(ret_fixed, index=df.index)
    
    stats_fixed = calculate_stats(ret_fixed_series)
    
    print(f"\nFixed Portfolio v2 Stats:")
    print(f"  Sharpe: {stats_fixed['sharpe']:.3f}")
    print(f"  Annual Return: {stats_fixed['annual_return']:.2%}")
    print(f"  Annual Vol: {stats_fixed['annual_volatility']:.2%}")
    print(f"  MDD: {stats_fixed['max_drawdown']:.2%}")
    
    # Save results
    print("\n" + "=" * 70)
    print("Saving results...")
    
    # JSON summary
    output = {
        'engine_stats': engine_stats,
        'correlation': corr_matrix.to_dict(),
        'fixed_v2': {
            'weights': {
                'wE1': weights_fixed[0],
                'wC1': weights_fixed[1],
                'wLV': weights_fixed[2],
                'wF': weights_fixed[3]
            },
            'stats': stats_fixed,
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in ret_fixed_series.items()
            ]
        }
    }
    
    with open(args.out_json, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ JSON saved to {args.out_json}")
    
    # CSV detailed results
    df_out = df.copy()
    df_out['Fixed_v2'] = ret_fixed_series
    df_out.to_csv(args.out_csv)
    
    print(f"✅ CSV saved to {args.out_csv}")

if __name__ == '__main__':
    main()
