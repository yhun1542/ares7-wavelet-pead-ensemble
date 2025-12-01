#!/usr/bin/env python3
"""
ARES-7 Factor v4 Engine
=======================
Multi-factor long/short strategy with CORRECT timing and longer lookback

Key features:
1. Longer momentum lookback (60-120 days) for medium-term trends
2. Monthly rebalancing (lower turnover, less noise)
3. Correct timing: Use previous day's data
4. Sector neutrality

Target: Sharpe 0.8+ (realistic)
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
    fundamentals['report_date'] = pd.to_datetime(fundamentals['report_date'])
    
    # Ensure fundamentals has sector info
    if 'sector' not in fundamentals.columns:
        raise ValueError("Fundamentals must have 'sector' column")
    
    # Sort by symbol and report_date
    fundamentals = fundamentals.sort_values(['symbol', 'report_date'])
    
    return price, fundamentals


def get_point_in_time_fundamentals(fundamentals, as_of_date, lag_days=90):
    """Get point-in-time fundamentals as of a specific date"""
    # Adjust for reporting lag
    cutoff_date = as_of_date - pd.Timedelta(days=lag_days)
    
    # Filter fundamentals up to cutoff date
    available = fundamentals[fundamentals['report_date'] <= cutoff_date].copy()
    
    if len(available) == 0:
        return None
    
    # Get the latest report for each symbol
    latest = available.sort_values('report_date').groupby('symbol').tail(1)
    
    return latest


def calculate_factors_v4(price, fundamentals, decision_date, lookback_momentum=90, lag_days=90):
    """
    Calculate factor scores using CORRECT timing
    
    decision_date: The date we make the decision (e.g., month-end)
    We use data up to the PREVIOUS day
    """
    # Get point-in-time fundamentals as of decision date
    pit_fund = get_point_in_time_fundamentals(fundamentals, decision_date, lag_days)
    
    if pit_fund is None or len(pit_fund) == 0:
        return None
    
    # Get fundamentals dict
    fund_dict = pit_fund.set_index('symbol').to_dict('index')
    
    # Calculate momentum using data up to PREVIOUS day
    if decision_date not in price.index:
        return None
    
    date_idx = price.index.get_loc(decision_date)
    if date_idx < 1:  # Need at least 1 previous day
        return None
    
    # Use PREVIOUS day's price for momentum calculation
    signal_date_idx = date_idx - 1
    
    if signal_date_idx < lookback_momentum:
        return None
    
    start_idx = signal_date_idx - lookback_momentum
    momentum = (price.iloc[signal_date_idx] / price.iloc[start_idx] - 1)
    
    # Calculate factor scores
    factor_scores = {}
    
    for symbol in price.columns:
        if symbol not in fund_dict:
            continue
        
        fund = fund_dict[symbol]
        
        # Value score (lower is better, so we negate)
        per = fund.get('PER', np.nan)
        pbr = fund.get('PBR', np.nan)
        value_score = 0
        if not np.isnan(per) and per > 0:
            value_score -= per
        if not np.isnan(pbr) and pbr > 0:
            value_score -= pbr
        
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
            quality_score -= debt_to_equity
        
        # Momentum score
        mom_val = momentum.get(symbol, np.nan)
        if np.isnan(mom_val):
            continue
        
        # Sector
        sector = fund.get('sector', 'Unknown')
        
        factor_scores[symbol] = {
            'value': value_score,
            'quality': quality_score,
            'momentum': mom_val,
            'sector': sector
        }
    
    return factor_scores


def rank_stocks_by_composite(factor_scores):
    """Rank stocks by composite factor score"""
    if not factor_scores:
        return None
    
    scores = []
    for symbol, factors in factor_scores.items():
        scores.append({
            'symbol': symbol,
            'value': factors['value'],
            'quality': factors['quality'],
            'momentum': factors['momentum'],
            'sector': factors['sector']
        })
    
    df = pd.DataFrame(scores)
    
    # Normalize each factor to z-score
    for col in ['value', 'quality', 'momentum']:
        mean = df[col].mean()
        std = df[col].std()
        if std > 0:
            df[col + '_z'] = (df[col] - mean) / std
        else:
            df[col + '_z'] = 0
    
    # Composite score
    df['composite_z'] = df['value_z'] + df['quality_z'] + df['momentum_z']
    
    df = df.sort_values('composite_z', ascending=False)
    
    return df


def select_sector_neutral(ranked_df, q=0.15, gross_exposure=2.0):
    """Select top/bottom stocks with sector neutrality"""
    if ranked_df is None or len(ranked_df) == 0:
        return {}
    
    n_stocks = len(ranked_df)
    n_select = max(1, int(n_stocks * q))
    
    sectors = ranked_df['sector'].unique()
    
    long_positions = {}
    short_positions = {}
    
    for sector in sectors:
        sector_df = ranked_df[ranked_df['sector'] == sector]
        n_sector = len(sector_df)
        
        if n_sector == 0:
            continue
        
        n_sector_select = max(1, int(n_sector * q))
        
        # Top stocks (long)
        top_stocks = sector_df.head(n_sector_select)['symbol'].tolist()
        for symbol in top_stocks:
            long_positions[symbol] = 1.0 / n_select
        
        # Bottom stocks (short)
        bottom_stocks = sector_df.tail(n_sector_select)['symbol'].tolist()
        for symbol in bottom_stocks:
            short_positions[symbol] = -1.0 / n_select
    
    # Normalize to target gross exposure
    total_long = sum(abs(w) for w in long_positions.values())
    total_short = sum(abs(w) for w in short_positions.values())
    
    target_each = gross_exposure / 2.0
    
    if total_long > 0:
        for symbol in long_positions:
            long_positions[symbol] *= target_each / total_long
    
    if total_short > 0:
        for symbol in short_positions:
            short_positions[symbol] *= target_each / total_short
    
    # Combine
    positions = {**long_positions, **short_positions}
    
    return positions


def backtest_factor_v4(price, fundamentals, 
                       q=0.15, 
                       rebalance_freq='M',
                       lookback_momentum=90,
                       gross_exposure=2.0,
                       lag_days=90):
    """Backtest Factor v4 strategy with CORRECT timing"""
    # Calculate returns
    returns = price.pct_change()
    
    # Get rebalance dates (month-end)
    if rebalance_freq == 'M':
        rebal_dates = price.resample('M').last().index
    elif rebalance_freq == 'W':
        rebal_dates = price.resample('W-FRI').last().index
    else:
        raise ValueError(f"Invalid rebalance_freq: {rebalance_freq}")
    
    rebal_dates = [d for d in rebal_dates if d in price.index]
    
    # Backtest
    portfolio_value = [1.0]
    daily_returns_list = []
    current_positions = {}
    next_positions = {}  # Positions to apply next day
    
    print(f"Backtesting with {len(rebal_dates)} rebalance dates...")
    
    for i, date in enumerate(price.index):
        # Apply positions decided yesterday
        if next_positions:
            current_positions = next_positions
            next_positions = {}
        
        # Decide positions for tomorrow
        if date in rebal_dates:
            factor_scores = calculate_factors_v4(
                price, fundamentals, date, lookback_momentum, lag_days
            )
            
            if factor_scores:
                ranked = rank_stocks_by_composite(factor_scores)
                next_positions = select_sector_neutral(ranked, q, gross_exposure)
            
            if i % 10 == 0:
                print(f"  {date.date()}: Decided {len(next_positions)} positions for tomorrow")
        
        # Calculate daily return with current positions
        if i == 0:
            daily_returns_list.append(0.0)
            continue
        
        ret = 0.0
        for symbol, weight in current_positions.items():
            if symbol in returns.columns:
                stock_ret = returns.loc[date, symbol]
                
                if not np.isnan(stock_ret):
                    ret += weight * stock_ret
        
        daily_returns_list.append(ret)
        portfolio_value.append(portfolio_value[-1] * (1 + ret))
    
    # Calculate metrics
    returns_series = pd.Series(daily_returns_list, index=price.index)
    
    annual_return = returns_series.mean() * 252
    annual_volatility = returns_series.std() * np.sqrt(252)
    sharpe = annual_return / annual_volatility if annual_volatility > 0 else 0
    
    # Max drawdown
    cumulative = (1 + returns_series).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # Turnover
    avg_turnover = gross_exposure * len(rebal_dates) / len(price)
    
    return {
        'sharpe': sharpe,
        'annual_return': annual_return,
        'annual_volatility': annual_volatility,
        'max_drawdown': max_drawdown,
        'avg_turnover': avg_turnover,
        'daily_returns': returns_series.tolist(),
        'dates': [d.strftime('%Y-%m-%d') for d in price.index]
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
                other_returns = pd.Series([d['ret'] for d in data['daily_returns']])
            else:
                other_returns = pd.Series(data['daily_returns'])
        else:
            continue
        
        # Align
        min_len = min(len(returns_series), len(other_returns))
        corr = returns_series.iloc[:min_len].corr(other_returns.iloc[:min_len])
        correlations[name] = corr
    
    return correlations


def main():
    parser = argparse.ArgumentParser(description='ARES-7 Factor v4 Engine')
    parser.add_argument('--price', default='./data/price_full.csv')
    parser.add_argument('--fundamentals', default='./data/fundamentals.csv')
    parser.add_argument('--q', type=float, default=0.15)
    parser.add_argument('--rebalance', default='M', choices=['W', 'M'])
    parser.add_argument('--lookback_mom', type=int, default=90)
    parser.add_argument('--gross', type=float, default=2.0)
    parser.add_argument('--lag_days', type=int, default=90, help='Reporting lag in days')
    parser.add_argument('--out', default='./results/engine_factor_v4_results.json')
    
    # Existing engines for correlation
    parser.add_argument('--a_json', default='./results/engine_ls_enhanced_results.json')
    parser.add_argument('--c1_json', default='./results/C1_final_v5.json')
    parser.add_argument('--lv_json', default='./results/engine_c_lowvol_v2_final_results.json')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ARES-7 Factor v4 Engine (Longer Lookback)")
    print("=" * 60)
    print(f"Config:")
    print(f"  Q: {args.q}")
    print(f"  Rebalance: {args.rebalance}")
    print(f"  Momentum lookback: {args.lookback_mom} days")
    print(f"  Gross exposure: {args.gross}")
    print(f"  Reporting lag: {args.lag_days} days")
    print()
    
    # Load data
    print("Loading data...")
    price, fundamentals = load_data(args.price, args.fundamentals)
    print(f"  Price: {price.shape}")
    print(f"  Fundamentals: {len(fundamentals)} records")
    print()
    
    # Backtest
    print("Running backtest...")
    results = backtest_factor_v4(
        price, fundamentals,
        q=args.q,
        rebalance_freq=args.rebalance,
        lookback_momentum=args.lookback_mom,
        gross_exposure=args.gross,
        lag_days=args.lag_days
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
            'gross_exposure': args.gross,
            'lag_days': args.lag_days,
            'timing_correct': True,
            'version': 'v4'
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
