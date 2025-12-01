#!/usr/bin/env python3
"""
ARES-7 Simple Momentum Engine v1

Strategy:
- 12-month momentum (skip most recent month to avoid reversal)
- Long-only, equal-weight top N stocks
- Monthly rebalancing (20 days)
- NO look-ahead bias (weights.shift(1))

Designed to complement Low-Vol v2 (low correlation expected)
"""

import argparse
import pandas as pd
import numpy as np
import json


def load_data(price_csv):
    """Load and prepare price data"""
    print("Loading data...")
    
    price_df = pd.read_csv(price_csv)
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
    price_df = price_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Pivot data
    pivot_close = price_df.pivot(index='timestamp', columns='symbol', values='close')
    pivot_ret = pivot_close.pct_change()
    
    print(f"  Price data: {len(pivot_close)} days, {len(pivot_close.columns)} symbols")
    
    return pivot_close, pivot_ret


def calculate_momentum(pivot_close, lookback=252, skip=21):
    """
    Calculate momentum: return from (t-lookback) to (t-skip)
    
    Args:
        pivot_close: Close prices
        lookback: Total lookback period (252 days = 12 months)
        skip: Skip recent days (21 days = 1 month) to avoid reversal
    
    Returns:
        DataFrame of momentum scores
    """
    print(f"Calculating momentum (lookback={lookback}, skip={skip})...")
    
    # Price lookback days ago
    price_start = pivot_close.shift(lookback)
    
    # Price skip days ago
    price_end = pivot_close.shift(skip)
    
    # Momentum = (price_end / price_start) - 1
    momentum = (price_end / price_start) - 1
    
    return momentum


def backtest_momentum(pivot_ret, momentum, top_n=20, rebal_days=20, cost=0.0005):
    """
    Backtest momentum strategy
    
    Args:
        pivot_ret: Daily returns
        momentum: Momentum scores
        top_n: Number of stocks to hold
        rebal_days: Rebalancing frequency
        cost: Transaction cost
    
    Returns:
        Dictionary with results
    """
    dates = pivot_ret.index
    symbols = pivot_ret.columns.tolist()
    
    # Rebalancing schedule
    rebal_dates = dates[::rebal_days]
    
    # Initialize weights
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)
    
    print(f"\nBacktesting: top_n={top_n}, rebal_days={rebal_days}, cost={cost}")
    print(f"  Rebalancing dates: {len(rebal_dates)}")
    
    for i, rebal_date in enumerate(rebal_dates):
        if rebal_date not in momentum.index:
            continue
        
        # Get momentum scores for this date
        mom_scores = momentum.loc[rebal_date]
        
        # Remove NaN
        mom_scores = mom_scores.dropna()
        
        if len(mom_scores) < top_n:
            continue
        
        # Select top N by momentum
        top_symbols = mom_scores.nlargest(top_n).index.tolist()
        
        # Equal weight
        w = 1.0 / len(top_symbols)
        
        # Determine period
        if i < len(rebal_dates) - 1:
            next_rebal = rebal_dates[i + 1]
            end_idx = dates.get_loc(next_rebal)
        else:
            end_idx = len(dates)
        
        start_idx = dates.get_loc(rebal_date)
        
        # Set weights
        weights.iloc[start_idx:end_idx, :] = 0.0
        for sym in top_symbols:
            if sym in weights.columns:
                weights.loc[dates[start_idx]:dates[end_idx-1], sym] = w
    
    # Calculate returns with proper timing (NO LOOK-AHEAD)
    port_ret = (weights.shift(1) * pivot_ret).sum(axis=1)
    
    # Turnover
    turnover = weights.diff().abs().sum(axis=1)
    turnover_cost = turnover * cost
    
    # Net returns
    net_ret = port_ret - turnover_cost
    net_ret = net_ret.dropna()
    
    # Performance metrics
    sharpe = net_ret.mean() / net_ret.std() * np.sqrt(252) if net_ret.std() > 0 else 0
    annual_return = net_ret.mean() * 252
    annual_vol = net_ret.std() * np.sqrt(252)
    
    # Max drawdown
    cumret = (1 + net_ret).cumprod()
    cummax = cumret.expanding().max()
    dd = (cumret - cummax) / cummax
    max_dd = dd.min()
    
    # Average turnover
    avg_turnover = turnover.mean()
    
    print(f"\nResults:")
    print(f"  Sharpe: {sharpe:.3f}")
    print(f"  Annual Return: {annual_return:.2%}")
    print(f"  Annual Vol: {annual_vol:.2%}")
    print(f"  MDD: {max_dd:.2%}")
    print(f"  Avg Turnover: {avg_turnover:.4f}")
    
    return {
        'sharpe': float(sharpe),
        'annual_return': float(annual_return),
        'annual_volatility': float(annual_vol),
        'max_drawdown': float(max_dd),
        'avg_turnover': float(avg_turnover),
        'daily_returns': [
            {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
            for d, r in net_ret.items()
        ]
    }


def main():
    parser = argparse.ArgumentParser(description='ARES-7 Simple Momentum Engine v1')
    parser.add_argument('--price_csv', default='./data/price_full.csv')
    parser.add_argument('--out', default='./results/engine_momentum_simple_v1_results.json')
    parser.add_argument('--top_n', type=int, default=20)
    parser.add_argument('--rebal_days', type=int, default=20)
    parser.add_argument('--lookback', type=int, default=252)
    parser.add_argument('--skip', type=int, default=21)
    parser.add_argument('--cost', type=float, default=0.0005)
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 Simple Momentum Engine v1")
    print("=" * 70)
    
    # Load data
    pivot_close, pivot_ret = load_data(args.price_csv)
    
    # Calculate momentum
    momentum = calculate_momentum(pivot_close, args.lookback, args.skip)
    
    # Backtest
    results = backtest_momentum(
        pivot_ret, momentum, 
        top_n=args.top_n, 
        rebal_days=args.rebal_days, 
        cost=args.cost
    )
    
    # Save results
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")
    print("\n" + "=" * 70)
    print("Simple Momentum Engine v1 Complete")
    print("=" * 70)


if __name__ == '__main__':
    main()
