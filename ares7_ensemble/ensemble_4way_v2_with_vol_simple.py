#!/usr/bin/env python3
"""
ARES-7 4-Way Ensemble v2 with Volatility Targeting (12%)
"""

import pandas as pd
import numpy as np
import json

def calculate_stats(returns):
    """Calculate performance statistics"""
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    annual_return = returns.mean() * 252
    annual_vol = returns.std() * np.sqrt(252)
    
    cumret = (1 + returns).cumprod()
    cummax = cumret.expanding().max()
    dd = (cumret - cummax) / cummax
    max_dd = dd.min()
    
    max_daily_loss = returns.min()
    
    return {
        'sharpe': float(sharpe),
        'annual_return': float(annual_return),
        'annual_volatility': float(annual_vol),
        'max_drawdown': float(max_dd),
        'max_daily_loss': float(max_daily_loss)
    }

def main():
    print("=" * 70)
    print("ARES-7 4-Way Ensemble v2 + Volatility Targeting (12%)")
    print("=" * 70)
    
    # Load 4-Way v2 results
    print("\nLoading 4-Way v2 results...")
    with open('./results/ensemble_4way_v2_summary.json', 'r') as f:
        data = json.load(f)
    
    # Get fixed portfolio returns
    fixed_returns = pd.Series({
        pd.Timestamp(d['date']): d['ret']
        for d in data['fixed_v2']['daily_returns']
    })
    
    print(f"  Loaded {len(fixed_returns)} days")
    print(f"  Base Sharpe: {data['fixed_v2']['stats']['sharpe']:.3f}")
    
    # Apply volatility targeting
    print("\nApplying Volatility Targeting (12%)...")
    
    target_vol = 0.12
    window = 60
    
    # Calculate rolling volatility
    rolling_vol = fixed_returns.rolling(window).std() * np.sqrt(252)
    
    # Calculate leverage
    leverage_raw = target_vol / rolling_vol
    leverage = leverage_raw.clip(0.5, 1.5)  # Clip to [0.5, 1.5]
    
    # Apply leverage with 1-day lag
    overlay_ret = leverage.shift(1) * fixed_returns
    overlay_ret = overlay_ret.dropna()
    
    # Calculate stats
    stats = calculate_stats(overlay_ret)
    avg_leverage = leverage.mean()
    
    print(f"\nResults:")
    print(f"  Sharpe: {stats['sharpe']:.3f}")
    print(f"  Annual Return: {stats['annual_return']:.2%}")
    print(f"  Annual Vol: {stats['annual_volatility']:.2%}")
    print(f"  MDD: {stats['max_drawdown']:.2%}")
    print(f"  Max Daily Loss: {stats['max_daily_loss']:.2%}")
    print(f"  Average Leverage: {avg_leverage:.2f}x")
    
    # Save results
    output = {
        'sharpe': stats['sharpe'],
        'annual_return': stats['annual_return'],
        'annual_volatility': stats['annual_volatility'],
        'max_drawdown': stats['max_drawdown'],
        'max_daily_loss': stats['max_daily_loss'],
        'avg_leverage': float(avg_leverage),
        'vol_target': target_vol,
        'daily_returns': [
            {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
            for d, r in overlay_ret.items()
        ]
    }
    
    with open('./results/ensemble_4way_v2_with_vol_summary.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Results saved to ./results/ensemble_4way_v2_with_vol_summary.json")

if __name__ == '__main__':
    main()
