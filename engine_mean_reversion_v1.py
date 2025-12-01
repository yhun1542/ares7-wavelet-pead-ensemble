#!/usr/bin/env python3
"""
ARES-7 Mean Reversion Engine v1

Strategy:
- Short-term mean reversion (RSI-based)
- Buy oversold stocks (RSI < 30)
- Long-only, equal-weight
- Weekly rebalancing (5 days)
- NO look-ahead bias (weights.shift(1))

Designed to have low correlation with Momentum
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


def calculate_rsi(prices, period=14):
    """
    Calculate RSI (Relative Strength Index)
    
    Args:
        prices: Price DataFrame
        period: RSI period (default 14)
    
    Returns:
        DataFrame of RSI values (0-100)
    """
    print(f"Calculating RSI (period={period})...")
    
    # Calculate price changes
    delta = prices.diff()
    
    # Separate gains and losses
    gain = delta.copy()
    loss = delta.copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0
    loss = abs(loss)
    
    # Calculate average gain and loss
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def backtest_mean_reversion(pivot_ret, rsi, top_n=20, rebal_days=5, 
                            rsi_threshold=30, cost=0.0005):
    """
    Backtest mean reversion strategy
    
    Args:
        pivot_ret: Daily returns
        rsi: RSI values
        top_n: Number of stocks to hold
        rebal_days: Rebalancing frequency
        rsi_threshold: RSI threshold for oversold (default 30)
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
    
    print(f"\nBacktesting: top_n={top_n}, rebal_days={rebal_days}, rsi_threshold={rsi_threshold}, cost={cost}")
    print(f"  Rebalancing dates: {len(rebal_dates)}")
    
    for i, rebal_date in enumerate(rebal_dates):
        if rebal_date not in rsi.index:
            continue
        
        # Get RSI for this date
        rsi_values = rsi.loc[rebal_date]
        
        # Remove NaN
        rsi_values = rsi_values.dropna()
        
        if len(rsi_values) == 0:
            continue
        
        # Select oversold stocks (RSI < threshold)
        oversold = rsi_values[rsi_values < rsi_threshold]
        
        if len(oversold) == 0:
            # If no oversold stocks, select lowest RSI stocks
            oversold = rsi_values.nsmallest(top_n)
        elif len(oversold) > top_n:
            # If too many oversold, select lowest RSI
            oversold = oversold.nsmallest(top_n)
        
        top_symbols = oversold.index.tolist()
        
        if len(top_symbols) == 0:
            continue
        
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
    parser = argparse.ArgumentParser(description='ARES-7 Mean Reversion Engine v1')
    parser.add_argument('--price_csv', default='./data/price_full.csv')
    parser.add_argument('--out', default='./results/engine_mean_reversion_v1_results.json')
    parser.add_argument('--top_n', type=int, default=20)
    parser.add_argument('--rebal_days', type=int, default=5)
    parser.add_argument('--rsi_period', type=int, default=14)
    parser.add_argument('--rsi_threshold', type=float, default=30)
    parser.add_argument('--cost', type=float, default=0.0005)
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 Mean Reversion Engine v1")
    print("=" * 70)
    
    # Load data
    pivot_close, pivot_ret = load_data(args.price_csv)
    
    # Calculate RSI
    rsi = calculate_rsi(pivot_close, args.rsi_period)
    
    # Backtest
    results = backtest_mean_reversion(
        pivot_ret, rsi, 
        top_n=args.top_n, 
        rebal_days=args.rebal_days, 
        rsi_threshold=args.rsi_threshold,
        cost=args.cost
    )
    
    # Save results
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")
    print("\n" + "=" * 70)
    print("Mean Reversion Engine v1 Complete")
    print("=" * 70)


if __name__ == '__main__':
    main()
