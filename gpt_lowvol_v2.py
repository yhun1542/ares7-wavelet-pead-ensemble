#!/usr/bin/env python3
"""
GPT Low-Vol v2 Engine
Reimplementation of Low-Vol v2 Final using GPT Backtester v4

Strategy:
- Low Risk Score (70%): downside_vol_180, beta_252, max_dd_252
- Quality Score (30%): ROE, gross_margin, debt_to_equity
- Long-only, equal-weight top N stocks
- Rebalance every 60 days
"""

import argparse
import pandas as pd
import numpy as np
from gpt_backtester_v4 import GPTBacktester, load_data


def compute_lowvol_signals(date, prices, returns, fundamentals, 
                           rebal_freq=60, top_n=20, risk_weight=0.7, 
                           quality_weight=0.3, **kwargs):
    """
    Compute Low-Vol v2 signals
    
    Args:
        date: Current date
        prices: Price data up to current date
        returns: Return data up to current date
        fundamentals: Fundamental data
        rebal_freq: Rebalancing frequency in days
        top_n: Number of stocks to hold
        risk_weight: Weight for risk score
        quality_weight: Weight for quality score
    
    Returns:
        pd.Series: Weights for each symbol (sum to 1.0)
    """
    # Check if rebalancing day
    dates = returns.index
    current_idx = dates.get_loc(date)
    
    if current_idx < 252:  # Need at least 1 year of data
        return pd.Series(0.0, index=returns.columns)
    
    if current_idx % rebal_freq != 0:
        # Not a rebalancing day - return None to keep previous weights
        return None
    
    # Calculate risk metrics
    symbols = returns.columns
    risk_scores = []
    quality_scores = []
    valid_symbols = []
    
    for symbol in symbols:
        ret = returns[symbol].iloc[-252:]  # Last 252 days
        
        if ret.isna().sum() > 50:  # Skip if too many missing values
            continue
        
        ret = ret.dropna()
        
        if len(ret) < 180:
            continue
        
        # Risk metrics
        # 1. Downside volatility (180 days)
        downside_ret = ret.iloc[-180:][ret.iloc[-180:] < 0]
        downside_vol = downside_ret.std() * np.sqrt(252) if len(downside_ret) > 10 else ret.iloc[-180:].std() * np.sqrt(252)
        
        # 2. Beta (252 days)
        market_ret = returns.mean(axis=1).iloc[-252:]  # Equal-weighted market
        cov = ret.cov(market_ret)
        var = market_ret.var()
        beta = cov / var if var > 0 else 1.0
        
        # 3. Max drawdown (252 days)
        cumret = (1 + ret).cumprod()
        cummax = cumret.expanding().max()
        dd = (cumret - cummax) / cummax
        max_dd = abs(dd.min())
        
        # Risk score (lower is better, so negate for ranking)
        risk_score = -(downside_vol + abs(beta) + max_dd) / 3.0
        
        # Quality metrics from fundamentals
        quality_score = 0.0
        if fundamentals is not None:
            # Get latest fundamental data for this symbol before current date
            fund = fundamentals[(fundamentals['symbol'] == symbol) & 
                               (fundamentals['report_date'] <= date)]
            
            if len(fund) > 0:
                fund = fund.iloc[-1]  # Most recent
                
                # ROE, gross margin, debt/equity
                roe = fund.get('ROE', 0) if not pd.isna(fund.get('ROE', np.nan)) else 0
                gross_margin = fund.get('gross_margin', 0) if not pd.isna(fund.get('gross_margin', np.nan)) else 0
                de = fund.get('debt_to_equity', 1) if not pd.isna(fund.get('debt_to_equity', np.nan)) else 1
                
                # Quality score (higher is better)
                quality_score = (roe / 100.0 + gross_margin - de / 10.0) / 3.0
        
        # Combined score
        combined_score = risk_weight * risk_score + quality_weight * quality_score
        
        risk_scores.append(risk_score)
        quality_scores.append(quality_score)
        valid_symbols.append(symbol)
    
    if len(valid_symbols) < top_n:
        return pd.Series(0.0, index=returns.columns)
    
    # Create DataFrame for ranking
    score_df = pd.DataFrame({
        'symbol': valid_symbols,
        'risk_score': risk_scores,
        'quality_score': quality_scores,
        'combined_score': [risk_weight * r + quality_weight * q 
                          for r, q in zip(risk_scores, quality_scores)]
    })
    
    # Rank by combined score
    score_df = score_df.sort_values('combined_score', ascending=False)
    
    # Select top N
    selected = score_df.head(top_n)['symbol'].tolist()
    
    # Equal weight
    weights = pd.Series(0.0, index=returns.columns)
    weights[selected] = 1.0 / len(selected)
    
    return weights


def main():
    parser = argparse.ArgumentParser(description='GPT Low-Vol v2 Engine')
    parser.add_argument('--price_csv', default='./price_full.csv')
    parser.add_argument('--fundamentals_csv', default='./fundamentals.csv')
    parser.add_argument('--out_json', default='./results/gpt_lowvol_v2_results.json')
    parser.add_argument('--rebal_freq', type=int, default=60)
    parser.add_argument('--top_n', type=int, default=20)
    parser.add_argument('--risk_weight', type=float, default=0.7)
    parser.add_argument('--quality_weight', type=float, default=0.3)
    args = parser.parse_args()
    
    print("=" * 70)
    print("GPT Low-Vol v2 Engine")
    print("=" * 70)
    
    # Load data
    price_df, fundamentals_df = load_data(args.price_csv, args.fundamentals_csv)
    
    # Initialize backtester
    backtester = GPTBacktester(price_df, fundamentals_df)
    
    # Run backtest
    results = backtester.run(
        compute_lowvol_signals,
        rebal_freq=args.rebal_freq,
        top_n=args.top_n,
        risk_weight=args.risk_weight,
        quality_weight=args.quality_weight
    )
    
    # Save results
    backtester.save_results(results, args.out_json)
    
    print("\n" + "=" * 70)
    print("GPT Low-Vol v2 Complete")
    print("=" * 70)


if __name__ == '__main__':
    main()
