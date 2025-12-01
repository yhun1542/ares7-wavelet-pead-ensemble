#!/usr/bin/env python3
"""
ARES-7 C1 v6 Engine (Simple Version)
=====================================
Short-term mean reversion strategy without optimization

Approach:
- Calculate mean reversion signals
- Select top N stocks (short) and bottom N stocks (long)
- Equal weight or signal-weighted positions
- Weekly rebalancing

Target: Sharpe 0.9+
"""

import pandas as pd
import numpy as np
import json
import argparse
from pathlib import Path


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


def calculate_signals(returns, signal_span=3, reversion=True):
    """
    Calculate signals
    
    If reversion=True (mean reversion):
        Signal = -1 * cumulative return
        Positive signal = stock went down → expect reversion up → LONG
        Negative signal = stock went up → expect reversion down → SHORT
    
    If reversion=False (momentum):
        Signal = cumulative return
        Positive signal = stock went up → expect continuation → LONG
        Negative signal = stock went down → expect continuation → SHORT
    """
    cum_ret = returns.rolling(signal_span).sum()
    if reversion:
        signals = -cum_ret  # Bet on reversion
    else:
        signals = cum_ret  # Bet on momentum
    return signals


def calculate_volatility(returns, vol_window=60):
    """Calculate rolling volatility"""
    vol = returns.rolling(vol_window, min_periods=20).std() * np.sqrt(252)
    return vol


def filter_by_volatility(signals, volatility, vol_percentile_low=10, vol_percentile_high=90):
    """
    Filter out stocks with extreme volatility
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


def select_positions(signals, n_long=20, n_short=20, gross_exposure=2.0, weight_by_signal=False):
    """
    Select long and short positions based on signals
    
    Top signals (most positive) → LONG (expect reversion up)
    Bottom signals (most negative) → SHORT (expect reversion down)
    """
    signals = signals.dropna()
    
    if len(signals) < n_long + n_short:
        return {}
    
    # Sort by signal
    sorted_signals = signals.sort_values(ascending=False)
    
    # Select long (top signals)
    long_symbols = sorted_signals.head(n_long).index.tolist()
    
    # Select short (bottom signals)
    short_symbols = sorted_signals.tail(n_short).index.tolist()
    
    positions = {}
    
    if weight_by_signal:
        # Weight by signal strength
        long_signals = sorted_signals.head(n_long)
        short_signals = sorted_signals.tail(n_short)
        
        # Normalize
        long_weights = long_signals / long_signals.abs().sum()
        short_weights = short_signals / short_signals.abs().sum()
        
        # Scale to target exposure
        for sym, w in long_weights.items():
            positions[sym] = w * (gross_exposure / 2.0)
        
        for sym, w in short_weights.items():
            positions[sym] = w * (gross_exposure / 2.0)
    else:
        # Equal weight
        long_weight = (gross_exposure / 2.0) / n_long
        short_weight = -(gross_exposure / 2.0) / n_short
        
        for sym in long_symbols:
            positions[sym] = long_weight
        
        for sym in short_symbols:
            positions[sym] = short_weight
    
    return positions


def backtest_c1_v6(price, 
                   signal_span=3,
                   rebal_freq=7,
                   n_long=20,
                   n_short=20,
                   gross_exposure=2.0,
                   vol_window=60,
                   vol_filter=True,
                   weight_by_signal=False):
    """
    Backtest C1 v6 strategy
    """
    print(f"Calculating returns...")
    returns = calculate_returns(price)
    
    print(f"Calculating signals (span={signal_span})...")
    signals = calculate_signals(returns, signal_span, reversion=False)  # Try momentum first
    
    # Shift signals by 1 day to avoid look-ahead bias
    # We use yesterday's signal to trade today
    signals = signals.shift(1)
    
    if vol_filter:
        print(f"Calculating volatility...")
        volatility = calculate_volatility(returns, vol_window)
        
        print(f"Applying volatility filter...")
        signals = filter_by_volatility(signals, volatility)
    
    # Get rebalance dates
    rebal_dates = price.index[::rebal_freq]
    rebal_dates = [d for d in rebal_dates if d in signals.index]
    
    print(f"Backtesting ({len(rebal_dates)} rebalance dates)...")
    
    # Backtest
    portfolio_value = [1.0]
    daily_returns_list = []
    current_positions = {}
    
    for i, date in enumerate(price.index):
        # Rebalance if needed
        if date in rebal_dates:
            signal_row = signals.loc[date]
            
            current_positions = select_positions(
                signal_row, n_long, n_short, gross_exposure, weight_by_signal
            )
            
            if i % 50 == 0:
                n_long_pos = sum(1 for w in current_positions.values() if w > 0)
                n_short_pos = sum(1 for w in current_positions.values() if w < 0)
                print(f"  Date {date.date()}: {n_long_pos} long, {n_short_pos} short")
        
        # Calculate daily return
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
    
    # Turnover (approximate)
    avg_turnover = gross_exposure * len(rebal_dates) / len(price)
    
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
    parser = argparse.ArgumentParser(description='ARES-7 C1 v6 Engine (Simple)')
    parser.add_argument('--price', default='./data/price_full.csv')
    parser.add_argument('--signal_span', type=int, default=3, help='Signal span in days')
    parser.add_argument('--rebal_freq', type=int, default=7, help='Rebalance frequency in days')
    parser.add_argument('--n_long', type=int, default=20, help='Number of long positions')
    parser.add_argument('--n_short', type=int, default=20, help='Number of short positions')
    parser.add_argument('--gross', type=float, default=2.0, help='Gross exposure')
    parser.add_argument('--vol_filter', action='store_true', help='Apply volatility filter')
    parser.add_argument('--weight_by_signal', action='store_true', help='Weight by signal strength')
    parser.add_argument('--out', default='./results/engine_c1_v6_results.json')
    
    # Existing engines for correlation
    parser.add_argument('--a_json', default='./results/engine_ls_enhanced_results.json')
    parser.add_argument('--lv_json', default='./results/engine_c_lowvol_v2_final_results.json')
    parser.add_argument('--fv2_json', default='./results/engine_factor_v2_best.json')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ARES-7 C1 v6 Engine (Simple)")
    print("=" * 60)
    print(f"Config:")
    print(f"  Signal span: {args.signal_span}")
    print(f"  Rebalance freq: {args.rebal_freq} days")
    print(f"  N long: {args.n_long}")
    print(f"  N short: {args.n_short}")
    print(f"  Gross exposure: {args.gross}")
    print(f"  Vol filter: {args.vol_filter}")
    print(f"  Weight by signal: {args.weight_by_signal}")
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
        n_long=args.n_long,
        n_short=args.n_short,
        gross_exposure=args.gross,
        vol_filter=args.vol_filter,
        weight_by_signal=args.weight_by_signal
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
            'n_long': args.n_long,
            'n_short': args.n_short,
            'gross_exposure': args.gross,
            'vol_filter': args.vol_filter,
            'weight_by_signal': args.weight_by_signal
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
