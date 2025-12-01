#!/usr/bin/env python3
"""
ARES-7 Factor v2 Engine
=======================
Multi-factor long/short strategy with sector neutrality

Improvements over Factor Final:
1. Multi-factor: Value + Quality + Momentum (equal weight)
2. Stricter selection: Q=0.1 (top/bottom 10%)
3. Sector neutral: Equal sector exposure in long/short
4. Weekly rebalancing: Better factor timing

Target: Sharpe 0.8+, Low correlation with existing engines
"""

import pandas as pd
import numpy as np
import json
import argparse
from pathlib import Path


def load_data(price_path, fundamentals_path):
    """Load price and fundamentals data"""
    # Load price data
    price_df = pd.read_csv(price_path)
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
    price_df = price_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Pivot to get price matrix (dates x symbols)
    price = price_df.pivot(index='timestamp', columns='symbol', values='close')
    
    # Load fundamentals
    fundamentals = pd.read_csv(fundamentals_path)
    
    # Ensure fundamentals has sector info
    if 'sector' not in fundamentals.columns:
        raise ValueError("Fundamentals must have 'sector' column")
    
    # Keep only the latest report for each symbol
    if 'report_date' in fundamentals.columns:
        fundamentals = fundamentals.sort_values('report_date', ascending=False)
        fundamentals = fundamentals.drop_duplicates('symbol', keep='first')
    
    return price, fundamentals


def calculate_factors(price, fundamentals, lookback_momentum=60):
    """
    Calculate factor scores for each stock
    
    Factors:
    - Value: Low PER + Low PBR
    - Quality: High ROE + High Gross Margin + Low Debt/Equity
    - Momentum: 60-day price momentum
    """
    # Get fundamentals dict
    fund_dict = fundamentals.set_index('symbol').to_dict('index')
    
    # Calculate momentum for each stock
    momentum = price.pct_change(lookback_momentum)
    
    factor_scores = {}
    
    for ticker in price.columns:
        if ticker not in fund_dict:
            continue
            
        fund = fund_dict[ticker]
        
        # Value score (lower is better, so we negate)
        per = fund.get('PER', np.nan)
        pbr = fund.get('PBR', np.nan)
        value_score = 0
        if not np.isnan(per) and per > 0:
            value_score -= per  # Lower PER is better
        if not np.isnan(pbr) and pbr > 0:
            value_score -= pbr  # Lower PBR is better
        
        # Quality score (higher is better)
        roe = fund.get('ROE', np.nan)
        gross_margin = fund.get('gross_margin', np.nan)
        debt_to_equity = fund.get('debt_to_equity', np.nan)
        quality_score = 0
        if not np.isnan(roe):
            quality_score += roe
        if not np.isnan(gross_margin):
            quality_score += gross_margin
        if not np.isnan(debt_to_equity) and debt_to_equity >= 0:
            quality_score -= debt_to_equity  # Lower debt is better
        
        # Sector
        sector = fund.get('sector', 'Unknown')
        
        factor_scores[ticker] = {
            'value': value_score,
            'quality': quality_score,
            'sector': sector
        }
    
    return factor_scores, momentum


def rank_stocks_by_composite(factor_scores, momentum, date, equal_weight=True):
    """
    Rank stocks by composite factor score
    
    Composite = Value + Quality + Momentum (all normalized)
    """
    # Get momentum at this date
    if date not in momentum.index:
        return None
    
    mom_series = momentum.loc[date]
    
    # Collect scores
    scores = []
    for ticker, factors in factor_scores.items():
        if ticker not in mom_series.index:
            continue
        
        mom_val = mom_series[ticker]
        if np.isnan(mom_val):
            continue
        
        # Composite score (all factors equally weighted)
        if equal_weight:
            composite = factors['value'] + factors['quality'] + mom_val
        else:
            # Could add different weights here
            composite = factors['value'] + factors['quality'] + mom_val
        
        scores.append({
            'symbol': ticker,
            'composite': composite,
            'value': factors['value'],
            'quality': factors['quality'],
            'momentum': mom_val,
            'sector': factors['sector']
        })
    
    if not scores:
        return None
    
    df = pd.DataFrame(scores)
    
    # Normalize each factor to z-score
    for col in ['value', 'quality', 'momentum']:
        mean = df[col].mean()
        std = df[col].std()
        if std > 0:
            df[col + '_z'] = (df[col] - mean) / std
        else:
            df[col + '_z'] = 0
    
    # Recalculate composite with normalized scores
    df['composite_z'] = df['value_z'] + df['quality_z'] + df['momentum_z']
    
    df = df.sort_values('composite_z', ascending=False)
    
    return df


def select_sector_neutral(ranked_df, q=0.1, gross_exposure=2.0):
    """
    Select top/bottom stocks with sector neutrality
    
    q: quantile for selection (0.1 = top/bottom 10%)
    gross_exposure: total gross exposure (2.0 = 100% long + 100% short)
    """
    if ranked_df is None or len(ranked_df) == 0:
        return {}, {}
    
    n_stocks = len(ranked_df)
    n_select = max(1, int(n_stocks * q))
    
    # Get sectors
    sectors = ranked_df['sector'].unique()
    
    long_positions = {}
    short_positions = {}
    
    # For each sector, select proportionally
    for sector in sectors:
        sector_df = ranked_df[ranked_df['sector'] == sector]
        n_sector = len(sector_df)
        
        if n_sector == 0:
            continue
        
        # Number to select from this sector
        n_sector_select = max(1, int(n_sector * q))
        
        # Top stocks (long)
        top_stocks = sector_df.head(n_sector_select)['symbol'].tolist()
        for ticker in top_stocks:
            long_positions[ticker] = 1.0 / n_select  # Equal weight
        
        # Bottom stocks (short)
        bottom_stocks = sector_df.tail(n_sector_select)['symbol'].tolist()
        for ticker in bottom_stocks:
            short_positions[ticker] = -1.0 / n_select  # Equal weight
    
    # Normalize to target gross exposure
    total_long = sum(abs(w) for w in long_positions.values())
    total_short = sum(abs(w) for w in short_positions.values())
    
    target_each = gross_exposure / 2.0
    
    if total_long > 0:
        for ticker in long_positions:
            long_positions[ticker] *= target_each / total_long
    
    if total_short > 0:
        for ticker in short_positions:
            short_positions[ticker] *= target_each / total_short
    
    # Combine
    positions = {**long_positions, **short_positions}
    
    return positions, {'long': long_positions, 'short': short_positions}


def backtest_factor_v2(price, fundamentals, 
                       q=0.1, 
                       rebalance_freq='W',  # 'W' for weekly, 'M' for monthly
                       lookback_momentum=60,
                       gross_exposure=2.0):
    """
    Backtest Factor v2 strategy
    """
    # Calculate factors
    factor_scores, momentum = calculate_factors(price, fundamentals, lookback_momentum)
    
    # Get rebalance dates
    if rebalance_freq == 'W':
        # Weekly: every Friday
        rebal_dates = price.resample('W-FRI').last().index
    elif rebalance_freq == 'M':
        # Monthly: last trading day of month
        rebal_dates = price.resample('M').last().index
    else:
        raise ValueError(f"Invalid rebalance_freq: {rebalance_freq}")
    
    rebal_dates = [d for d in rebal_dates if d in price.index]
    
    # Backtest
    portfolio_value = [1.0]
    daily_returns = []
    current_positions = {}
    
    for i, date in enumerate(price.index):
        # Rebalance if needed
        if date in rebal_dates:
            ranked = rank_stocks_by_composite(factor_scores, momentum, date)
            current_positions, _ = select_sector_neutral(ranked, q, gross_exposure)
        
        # Calculate daily return
        if i == 0:
            daily_returns.append(0.0)
            continue
        
        prev_date = price.index[i-1]
        
        ret = 0.0
        for ticker, weight in current_positions.items():
            if ticker in price.columns:
                p_prev = price.loc[prev_date, ticker]
                p_curr = price.loc[date, ticker]
                
                if not np.isnan(p_prev) and not np.isnan(p_curr) and p_prev > 0:
                    stock_ret = (p_curr - p_prev) / p_prev
                    ret += weight * stock_ret
        
        daily_returns.append(ret)
        portfolio_value.append(portfolio_value[-1] * (1 + ret))
    
    # Calculate metrics
    returns_series = pd.Series(daily_returns, index=price.index)
    
    annual_return = returns_series.mean() * 252
    annual_volatility = returns_series.std() * np.sqrt(252)
    sharpe = annual_return / annual_volatility if annual_volatility > 0 else 0
    
    # Max drawdown
    cumulative = (1 + returns_series).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # Turnover
    turnover_list = []
    prev_positions = {}
    for date in rebal_dates:
        ranked = rank_stocks_by_composite(factor_scores, momentum, date)
        positions, _ = select_sector_neutral(ranked, q, gross_exposure)
        
        if prev_positions:
            # Calculate turnover
            all_tickers = set(prev_positions.keys()) | set(positions.keys())
            turnover = sum(abs(positions.get(t, 0) - prev_positions.get(t, 0)) for t in all_tickers)
            turnover_list.append(turnover)
        
        prev_positions = positions
    
    avg_turnover = np.mean(turnover_list) if turnover_list else 0
    
    return {
        'sharpe': sharpe,
        'annual_return': annual_return,
        'annual_volatility': annual_volatility,
        'max_drawdown': max_drawdown,
        'avg_turnover': avg_turnover,
        'daily_returns': returns_series.tolist(),
        'dates': [d.strftime('%Y-%m-%d') for d in price.index],
        'portfolio_value': portfolio_value
    }


def calculate_correlation_with_existing(returns_series, existing_engines):
    """Calculate correlation with existing engines"""
    correlations = {}
    
    for name, path in existing_engines.items():
        if not Path(path).exists():
            continue
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        if 'daily_returns' not in data:
            continue
        
        # Handle different formats
        if isinstance(data['daily_returns'], list):
            if len(data['daily_returns']) > 0 and isinstance(data['daily_returns'][0], dict):
                # Format: [{'date': ..., 'ret': ...}, ...]
                other_returns = pd.Series([d['ret'] for d in data['daily_returns']])
            else:
                # Format: [0.01, 0.02, ...]
                other_returns = pd.Series(data['daily_returns'])
        else:
            continue
        
        # Align
        min_len = min(len(returns_series), len(other_returns))
        corr = returns_series.iloc[:min_len].corr(other_returns.iloc[:min_len])
        correlations[name] = corr
    
    return correlations


def main():
    parser = argparse.ArgumentParser(description='ARES-7 Factor v2 Engine')
    parser.add_argument('--price', default='./data/price_full.csv')
    parser.add_argument('--fundamentals', default='./data/fundamentals.csv')
    parser.add_argument('--q', type=float, default=0.1, help='Quantile for selection (0.1 = top/bottom 10%)')
    parser.add_argument('--rebalance', default='W', choices=['W', 'M'], help='Rebalance frequency')
    parser.add_argument('--lookback_mom', type=int, default=60, help='Momentum lookback period')
    parser.add_argument('--gross', type=float, default=2.0, help='Gross exposure')
    parser.add_argument('--out', default='./results/engine_factor_v2_results.json')
    
    # Existing engines for correlation
    parser.add_argument('--a_json', default='./results/A+LS_enhanced_results.json')
    parser.add_argument('--c1_json', default='./results/C1_final_v5.json')
    parser.add_argument('--lv_json', default='./results/engine_c_lowvol_v2_final_results.json')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ARES-7 Factor v2 Engine")
    print("=" * 60)
    print(f"Config:")
    print(f"  Q: {args.q}")
    print(f"  Rebalance: {args.rebalance}")
    print(f"  Momentum lookback: {args.lookback_mom}")
    print(f"  Gross exposure: {args.gross}")
    print()
    
    # Load data
    print("Loading data...")
    price, fundamentals = load_data(args.price, args.fundamentals)
    print(f"  Price: {price.shape}")
    print(f"  Fundamentals: {fundamentals.shape}")
    print(f"  Sectors: {fundamentals['sector'].nunique()}")
    print()
    
    # Backtest
    print("Running backtest...")
    results = backtest_factor_v2(
        price, fundamentals,
        q=args.q,
        rebalance_freq=args.rebalance,
        lookback_momentum=args.lookback_mom,
        gross_exposure=args.gross
    )
    
    print()
    print("=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"  Sharpe Ratio: {results['sharpe']:.3f}")
    print(f"  Annual Return: {results['annual_return']*100:.2f}%")
    print(f"  Annual Volatility: {results['annual_volatility']*100:.2f}%")
    print(f"  Max Drawdown: {results['max_drawdown']*100:.2f}%")
    print(f"  Avg Turnover: {results['avg_turnover']:.2f}")
    print()
    
    # Calculate correlation with existing engines
    print("Calculating correlations with existing engines...")
    returns_series = pd.Series(results['daily_returns'])
    
    existing_engines = {
        'A+LS': args.a_json,
        'C1': args.c1_json,
        'LV2': args.lv_json
    }
    
    correlations = calculate_correlation_with_existing(returns_series, existing_engines)
    
    print("Correlations:")
    for name, corr in correlations.items():
        print(f"  {name}: {corr:.3f}")
    print()
    
    # Save results
    output = {
        'sharpe': results['sharpe'],
        'annual_return': results['annual_return'],
        'annual_volatility': results['annual_volatility'],
        'max_drawdown': results['max_drawdown'],
        'avg_turnover': results['avg_turnover'],
        'correlations': correlations,
        'config': {
            'q': args.q,
            'rebalance': args.rebalance,
            'lookback_momentum': args.lookback_mom,
            'gross_exposure': args.gross
        },
        'daily_returns': results['daily_returns'],
        'dates': results['dates']
    }
    
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Results saved to: {args.out}")
    print("=" * 60)


if __name__ == '__main__':
    main()
