#!/usr/bin/env python3
"""
ARES-7 C1 v6 Engine
===================
Short-term mean reversion strategy with improvements

Improvements over C1 Final v5:
1. Optimized signal span (3-5 days instead of 2)
2. Volatility filter to exclude extreme volatility stocks
3. Adjusted risk aversion for better stability
4. Reduced number of stocks for better concentration

Target: Sharpe 0.9+, Low correlation with existing engines
"""

import pandas as pd
import numpy as np
import json
import argparse
from pathlib import Path
import cvxpy as cp


def load_data(price_path):
    """Load price data"""
    price_df = pd.read_csv(price_path)
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
    price_df = price_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Pivot to get price matrix
    price = price_df.pivot(index='timestamp', columns='symbol', values='close')
    
    return price


def calculate_returns(price):
    """Calculate returns"""
    returns = price.pct_change()
    return returns


def calculate_signals(returns, signal_span=3):
    """
    Calculate mean reversion signals
    
    Signal = -1 * cumulative return over signal_span days
    (negative because we bet on reversion)
    """
    cum_ret = returns.rolling(signal_span).sum()
    signals = -cum_ret  # Bet on reversion
    return signals


def calculate_volatility(returns, vol_window=60):
    """Calculate rolling volatility"""
    vol = returns.rolling(vol_window, min_periods=20).std() * np.sqrt(252)
    return vol


def filter_by_volatility(signals, volatility, vol_percentile_low=10, vol_percentile_high=90):
    """
    Filter out stocks with extreme volatility
    
    Only keep stocks with volatility between 10th and 90th percentile
    """
    filtered_signals = signals.copy()
    
    for date in signals.index:
        if date not in volatility.index:
            continue
        
        vol_row = volatility.loc[date]
        vol_row = vol_row.dropna()
        
        if len(vol_row) == 0:
            continue
        
        low_thresh = np.percentile(vol_row, vol_percentile_low)
        high_thresh = np.percentile(vol_row, vol_percentile_high)
        
        # Set signal to NaN for extreme volatility stocks
        mask = (vol_row < low_thresh) | (vol_row > high_thresh)
        filtered_signals.loc[date, mask.index[mask]] = np.nan
    
    return filtered_signals


def optimize_portfolio(signals, returns, cov_matrix, 
                       target_leverage=3.0, 
                       risk_aversion=0.5,
                       max_position=0.15,
                       n_symbols=40):
    """
    Optimize portfolio using mean-variance optimization
    
    Maximize: signal * weight - risk_aversion * portfolio_variance
    Subject to:
    - Sum of absolute weights = target_leverage
    - Each weight <= max_position
    - Market neutral: sum of weights = 0
    """
    signals = signals.dropna()
    
    if len(signals) < 5:
        return {}
    
    # Select top n_symbols by absolute signal
    top_signals = signals.abs().nlargest(n_symbols)
    selected_symbols = top_signals.index.tolist()
    
    signals = signals[selected_symbols]
    
    # Get covariance matrix for selected symbols
    cov = cov_matrix.loc[selected_symbols, selected_symbols]
    
    # Fill NaN with small positive value on diagonal
    cov = cov.fillna(0)
    for sym in selected_symbols:
        if cov.loc[sym, sym] == 0:
            cov.loc[sym, sym] = 0.0001
    
    # Convert to numpy
    mu = signals.values
    Sigma = cov.values
    
    n = len(selected_symbols)
    
    # Optimization variables
    w = cp.Variable(n)
    
    # Objective: maximize expected return - risk penalty
    ret = mu @ w
    risk = cp.quad_form(w, Sigma)
    objective = cp.Maximize(ret - risk_aversion * risk)
    
    # Constraints
    constraints = [
        cp.sum(w) == 0,  # Market neutral
        cp.sum(cp.abs(w)) == target_leverage,  # Leverage constraint
        w <= max_position,  # Max long position
        w >= -max_position  # Max short position
    ]
    
    # Solve
    prob = cp.Problem(objective, constraints)
    
    try:
        prob.solve(solver=cp.ECOS, max_iters=1000)
        
        if prob.status == 'optimal':
            weights = dict(zip(selected_symbols, w.value))
            return weights
        else:
            return {}
    except:
        return {}


def backtest_c1_v6(price, 
                   signal_span=3,
                   rebal_freq=7,
                   target_leverage=3.0,
                   risk_aversion=0.5,
                   cov_lookback=60,
                   vol_window=60,
                   max_position=0.15,
                   n_symbols=40,
                   vol_filter=True):
    """
    Backtest C1 v6 strategy
    """
    print(f"Calculating returns...")
    returns = calculate_returns(price)
    
    print(f"Calculating signals (span={signal_span})...")
    signals = calculate_signals(returns, signal_span)
    
    print(f"Calculating volatility...")
    volatility = calculate_volatility(returns, vol_window)
    
    if vol_filter:
        print(f"Applying volatility filter...")
        signals = filter_by_volatility(signals, volatility)
    
    # Get rebalance dates
    rebal_dates = price.index[::rebal_freq]
    rebal_dates = [d for d in rebal_dates if d in signals.index]
    
    print(f"Backtesting ({len(rebal_dates)} rebalance dates)...")
    
    # Backtest
    portfolio_value = [1.0]
    daily_returns_list = []
    current_weights = {}
    
    for i, date in enumerate(price.index):
        # Rebalance if needed
        if date in rebal_dates:
            # Get signals for this date
            signal_row = signals.loc[date].dropna()
            
            # Calculate covariance matrix
            if i >= cov_lookback:
                ret_window = returns.iloc[i-cov_lookback:i]
                cov_matrix = ret_window.cov() * 252  # Annualized
            else:
                cov_matrix = returns.iloc[:i].cov() * 252
            
            # Optimize portfolio
            current_weights = optimize_portfolio(
                signal_row, returns, cov_matrix,
                target_leverage, risk_aversion, max_position, n_symbols
            )
            
            if i % 50 == 0:
                print(f"  Date {date.date()}: {len(current_weights)} positions")
        
        # Calculate daily return
        if i == 0:
            daily_returns_list.append(0.0)
            continue
        
        prev_date = price.index[i-1]
        
        ret = 0.0
        for symbol, weight in current_weights.items():
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
    
    # Turnover (approximate)
    avg_turnover = target_leverage * len(rebal_dates) / len(price)
    
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
    parser = argparse.ArgumentParser(description='ARES-7 C1 v6 Engine')
    parser.add_argument('--price', default='./data/price_full.csv')
    parser.add_argument('--signal_span', type=int, default=3, help='Signal span in days')
    parser.add_argument('--rebal_freq', type=int, default=7, help='Rebalance frequency in days')
    parser.add_argument('--leverage', type=float, default=3.0, help='Target leverage')
    parser.add_argument('--risk_aversion', type=float, default=0.5, help='Risk aversion coefficient')
    parser.add_argument('--n_symbols', type=int, default=40, help='Number of symbols to trade')
    parser.add_argument('--vol_filter', action='store_true', help='Apply volatility filter')
    parser.add_argument('--out', default='./results/engine_c1_v6_results.json')
    
    # Existing engines for correlation
    parser.add_argument('--a_json', default='./results/engine_ls_enhanced_results.json')
    parser.add_argument('--lv_json', default='./results/engine_c_lowvol_v2_final_results.json')
    parser.add_argument('--fv2_json', default='./results/engine_factor_v2_best.json')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ARES-7 C1 v6 Engine")
    print("=" * 60)
    print(f"Config:")
    print(f"  Signal span: {args.signal_span}")
    print(f"  Rebalance freq: {args.rebal_freq} days")
    print(f"  Leverage: {args.leverage}")
    print(f"  Risk aversion: {args.risk_aversion}")
    print(f"  N symbols: {args.n_symbols}")
    print(f"  Vol filter: {args.vol_filter}")
    print()
    
    # Load data
    print("Loading data...")
    price = load_data(args.price)
    print(f"  Price: {price.shape}")
    print()
    
    # Backtest
    print("Running backtest...")
    results = backtest_c1_v6(
        price,
        signal_span=args.signal_span,
        rebal_freq=args.rebal_freq,
        target_leverage=args.leverage,
        risk_aversion=args.risk_aversion,
        n_symbols=args.n_symbols,
        vol_filter=args.vol_filter
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
        'LV2': args.lv_json,
        'FactorV2': args.fv2_json
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
            'signal_span': args.signal_span,
            'rebal_freq': args.rebal_freq,
            'leverage': args.leverage,
            'risk_aversion': args.risk_aversion,
            'n_symbols': args.n_symbols,
            'vol_filter': args.vol_filter
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
