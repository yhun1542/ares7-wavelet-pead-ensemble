#!/usr/bin/env python3
"""
ARES-7 Factor Long-Short Engine v1

Strategy:
- Multi-factor: Value + Quality + Momentum
- Sector-neutral Long-Short
- Long top quintile, Short bottom quintile within each sector
- Monthly rebalancing (20 days)
- Gross exposure 2.0 (1.0 long + 1.0 short)
- NO look-ahead bias (weights.shift(1))

Designed to have low correlation with long-only engines
"""

import argparse
import pandas as pd
import numpy as np
import json


def load_data(price_csv, fund_csv):
    """Load and prepare data"""
    print("Loading data...")
    
    # Price data
    price_df = pd.read_csv(price_csv)
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
    price_df = price_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    pivot_close = price_df.pivot(index='timestamp', columns='symbol', values='close')
    pivot_ret = pivot_close.pct_change()
    
    print(f"  Price data: {len(pivot_close)} days, {len(pivot_close.columns)} symbols")
    
    # Fundamental data
    fund_df = pd.read_csv(fund_csv)
    fund_df['report_date'] = pd.to_datetime(fund_df['report_date'])
    
    print(f"  Fundamental data: {len(fund_df)} rows")
    
    return pivot_close, pivot_ret, fund_df


def assign_sectors(symbols):
    """
    Assign sectors to symbols (simple heuristic)
    In production, use proper sector classification
    """
    # Simple sector assignment based on symbol patterns
    # This is a placeholder - in production use proper sector data
    sectors = {}
    
    # Tech
    tech_symbols = ['AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'CSCO', 
                   'ORCL', 'IBM', 'QCOM', 'TXN', 'AVGO', 'ADBE', 'CRM', 'NOW']
    # Finance
    fin_symbols = ['JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP', 'USB', 
                  'PNC', 'TFC', 'COF', 'BK', 'STT']
    # Healthcare
    health_symbols = ['JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'DHR', 'LLY', 'BMY', 
                     'AMGN', 'GILD', 'CVS', 'CI', 'HUM']
    # Consumer
    consumer_symbols = ['AMZN', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW', 'TJX', 'DG', 'ROST',
                       'KO', 'PEP', 'WMT', 'COST', 'PG']
    # Energy
    energy_symbols = ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HAL']
    # Industrial
    industrial_symbols = ['BA', 'CAT', 'GE', 'HON', 'UPS', 'RTX', 'LMT', 'MMM', 'DE', 'UNP']
    
    for sym in symbols:
        if sym in tech_symbols:
            sectors[sym] = 'Tech'
        elif sym in fin_symbols:
            sectors[sym] = 'Finance'
        elif sym in health_symbols:
            sectors[sym] = 'Healthcare'
        elif sym in consumer_symbols:
            sectors[sym] = 'Consumer'
        elif sym in energy_symbols:
            sectors[sym] = 'Energy'
        elif sym in industrial_symbols:
            sectors[sym] = 'Industrial'
        else:
            sectors[sym] = 'Other'
    
    return sectors


def calculate_factors(pivot_close, pivot_ret, fund_df, date):
    """
    Calculate multi-factor scores for a given date
    
    Factors:
    1. Value: P/B ratio (lower is better)
    2. Quality: ROE (higher is better)
    3. Momentum: 12-month return (skip 1 month)
    """
    # Momentum (252 days ago to 21 days ago)
    if date not in pivot_close.index:
        return pd.DataFrame()
    
    idx = pivot_close.index.get_loc(date)
    
    if idx < 252:
        return pd.DataFrame()
    
    # Momentum
    price_start = pivot_close.iloc[idx - 252]
    price_end = pivot_close.iloc[idx - 21]
    momentum = (price_end / price_start) - 1
    
    # Fundamentals
    fund_recent = fund_df[fund_df['report_date'] <= date].copy()
    fund_recent = fund_recent.sort_values('report_date').groupby('symbol').last()
    
    # Combine
    scores = pd.DataFrame({
        'momentum': momentum,
        'pbr': fund_recent['PBR'] if 'PBR' in fund_recent.columns else np.nan,
        'roe': fund_recent['ROE'] if 'ROE' in fund_recent.columns else np.nan
    })
    
    scores = scores.dropna()
    
    if len(scores) < 20:
        return pd.DataFrame()
    
    # Rank percentile (0-1)
    scores['momentum_rank'] = scores['momentum'].rank(pct=True)
    scores['value_rank'] = 1 - scores['pbr'].rank(pct=True)  # Lower P/B is better
    scores['quality_rank'] = scores['roe'].rank(pct=True)
    
    # Combined score (equal weight)
    scores['combined'] = (scores['momentum_rank'] + scores['value_rank'] + scores['quality_rank']) / 3
    
    return scores


def backtest_factor_longshort(pivot_ret, pivot_close, fund_df, 
                              rebal_days=20, quintile=0.2, cost=0.0005):
    """
    Backtest factor long-short strategy
    
    Args:
        pivot_ret: Daily returns
        pivot_close: Close prices
        fund_df: Fundamental data
        rebal_days: Rebalancing frequency
        quintile: Top/bottom quintile to long/short
        cost: Transaction cost
    
    Returns:
        Dictionary with results
    """
    dates = pivot_ret.index
    symbols = pivot_ret.columns.tolist()
    
    # Assign sectors
    sectors = assign_sectors(symbols)
    
    # Rebalancing schedule
    rebal_dates = dates[::rebal_days]
    
    # Initialize weights
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)
    
    print(f"\nBacktesting: rebal_days={rebal_days}, quintile={quintile}, cost={cost}")
    print(f"  Rebalancing dates: {len(rebal_dates)}")
    
    for i, rebal_date in enumerate(rebal_dates):
        # Calculate factor scores
        scores = calculate_factors(pivot_close, pivot_ret, fund_df, rebal_date)
        
        if len(scores) < 20:
            continue
        
        # Add sector information
        scores['sector'] = scores.index.map(sectors)
        
        # Sector-neutral: Long/Short within each sector
        long_symbols = []
        short_symbols = []
        
        for sector in scores['sector'].unique():
            sector_scores = scores[scores['sector'] == sector]
            
            if len(sector_scores) < 5:  # Need at least 5 stocks per sector
                continue
            
            n_select = max(1, int(len(sector_scores) * quintile))
            
            # Long top quintile
            top = sector_scores.nlargest(n_select, 'combined')
            long_symbols.extend(top.index.tolist())
            
            # Short bottom quintile
            bottom = sector_scores.nsmallest(n_select, 'combined')
            short_symbols.extend(bottom.index.tolist())
        
        if len(long_symbols) == 0 or len(short_symbols) == 0:
            continue
        
        # Equal weight within long and short
        long_weight = 1.0 / len(long_symbols)
        short_weight = -1.0 / len(short_symbols)
        
        # Determine period
        if i < len(rebal_dates) - 1:
            next_rebal = rebal_dates[i + 1]
            end_idx = dates.get_loc(next_rebal)
        else:
            end_idx = len(dates)
        
        start_idx = dates.get_loc(rebal_date)
        
        # Set weights
        weights.iloc[start_idx:end_idx, :] = 0.0
        for sym in long_symbols:
            if sym in weights.columns:
                weights.loc[dates[start_idx]:dates[end_idx-1], sym] = long_weight
        for sym in short_symbols:
            if sym in weights.columns:
                weights.loc[dates[start_idx]:dates[end_idx-1], sym] = short_weight
    
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
    
    # Average gross exposure
    avg_gross = weights.abs().sum(axis=1).mean()
    
    print(f"\nResults:")
    print(f"  Sharpe: {sharpe:.3f}")
    print(f"  Annual Return: {annual_return:.2%}")
    print(f"  Annual Vol: {annual_vol:.2%}")
    print(f"  MDD: {max_dd:.2%}")
    print(f"  Avg Turnover: {avg_turnover:.4f}")
    print(f"  Avg Gross Exposure: {avg_gross:.2f}")
    
    return {
        'sharpe': float(sharpe),
        'annual_return': float(annual_return),
        'annual_volatility': float(annual_vol),
        'max_drawdown': float(max_dd),
        'avg_turnover': float(avg_turnover),
        'avg_gross_exposure': float(avg_gross),
        'daily_returns': [
            {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
            for d, r in net_ret.items()
        ]
    }


def main():
    parser = argparse.ArgumentParser(description='ARES-7 Factor Long-Short Engine v1')
    parser.add_argument('--price_csv', default='./data/price_full.csv')
    parser.add_argument('--fund_csv', default='./data/fundamentals.csv')
    parser.add_argument('--out', default='./results/engine_factor_longshort_v1_results.json')
    parser.add_argument('--rebal_days', type=int, default=20)
    parser.add_argument('--quintile', type=float, default=0.2)
    parser.add_argument('--cost', type=float, default=0.0005)
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 Factor Long-Short Engine v1")
    print("=" * 70)
    
    # Load data
    pivot_close, pivot_ret, fund_df = load_data(args.price_csv, args.fund_csv)
    
    # Backtest
    results = backtest_factor_longshort(
        pivot_ret, pivot_close, fund_df,
        rebal_days=args.rebal_days,
        quintile=args.quintile,
        cost=args.cost
    )
    
    # Save results
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")
    print("\n" + "=" * 70)
    print("Factor Long-Short Engine v1 Complete")
    print("=" * 70)


if __name__ == '__main__':
    main()
