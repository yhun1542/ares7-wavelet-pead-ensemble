#!/usr/bin/env python3
"""
ARES-7 ETF Time-Series Momentum Engine v1

Strategy:
- Universe: 18 ETFs (broad market, sectors, international, bonds, commodities)
- Signal: 100-day MA vs 200-day MA
- Rebalance: Every 10 days
- Long-only, equal-weight selected ETFs
"""

import argparse
import pandas as pd
import numpy as np
import json

def load_etf_data(csv_path):
    """Load ETF price data"""
    print("Loading ETF data...")
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
    df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Pivot
    pivot_close = df.pivot(index='timestamp', columns='symbol', values='close')
    pivot_ret = pivot_close.pct_change()
    
    print(f"  Loaded {len(pivot_close)} days, {len(pivot_close.columns)} symbols")
    print(f"  Symbols: {', '.join(pivot_close.columns.tolist())}")
    
    return pivot_close, pivot_ret

def calculate_momentum_signals(pivot_close):
    """Calculate time-series momentum signals"""
    print("\nCalculating momentum signals...")
    
    # Moving averages
    ma_fast = pivot_close.rolling(100).mean()
    ma_slow = pivot_close.rolling(200).mean()
    
    # Signal: 1 if fast > slow, 0 otherwise
    signal_raw = (ma_fast > ma_slow).astype(int)
    
    # Shift 1 day to avoid look-ahead bias
    signal = signal_raw.shift(1)
    
    print("  100/200 MA signals calculated")
    
    return signal

def backtest_etf_momentum(pivot_ret, signal, rebal_days=10, cost=0.0003):
    """Backtest ETF momentum strategy"""
    print(f"\nBacktesting with rebalance every {rebal_days} days...")
    
    dates = pivot_ret.index
    symbols = pivot_ret.columns.tolist()
    
    # Rebalancing schedule
    rebal_dates = dates[::rebal_days]
    
    # Initialize weights
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)
    
    for i, rebal_date in enumerate(rebal_dates):
        if rebal_date not in signal.index:
            continue
        
        # Get signals for this date
        signals_today = signal.loc[rebal_date]
        
        # Select ETFs with signal = 1
        selected = signals_today[signals_today == 1].index.tolist()
        
        if len(selected) == 0:
            # Full cash if no signals
            continue
        
        # Equal weight
        w = 1.0 / len(selected)
        
        # Determine end date
        if i < len(rebal_dates) - 1:
            next_rebal = rebal_dates[i + 1]
            end_idx = dates.get_loc(next_rebal)
        else:
            end_idx = len(dates)
        
        start_idx = dates.get_loc(rebal_date)
        
        # Set weights
        weights.iloc[start_idx:end_idx, :] = 0.0
        for sym in selected:
            if sym in weights.columns:
                weights.loc[dates[start_idx]:dates[end_idx-1], sym] = w
    
    # Calculate returns
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
    
    # Average number of holdings
    avg_holdings = (weights > 0).sum(axis=1).mean()
    
    print(f"\n  Sharpe: {sharpe:.3f}")
    print(f"  Annual Return: {annual_return:.2%}")
    print(f"  Annual Vol: {annual_vol:.2%}")
    print(f"  MDD: {max_dd:.2%}")
    print(f"  Avg Turnover: {avg_turnover:.4f}")
    print(f"  Avg Holdings: {avg_holdings:.1f} ETFs")
    
    return {
        'sharpe': float(sharpe),
        'annual_return': float(annual_return),
        'annual_volatility': float(annual_vol),
        'max_drawdown': float(max_dd),
        'avg_turnover': float(avg_turnover),
        'avg_holdings': float(avg_holdings),
        'daily_returns': net_ret
    }

def calculate_correlations(etf_returns, engine_paths):
    """Calculate correlations with existing engines"""
    print("\nCalculating correlations with existing engines...")
    
    correlations = {}
    
    for name, path in engine_paths.items():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            engine_returns = pd.Series({
                pd.Timestamp(d['date']): d['ret']
                for d in data['daily_returns']
            })
            
            # Find common dates
            common = etf_returns.index.intersection(engine_returns.index)
            
            if len(common) > 100:
                corr = etf_returns.loc[common].corr(engine_returns.loc[common])
                correlations[name] = float(corr)
                print(f"  Corr({name}): {corr:.3f}")
            else:
                correlations[name] = None
                print(f"  Corr({name}): N/A (insufficient common dates)")
        
        except Exception as e:
            correlations[name] = None
            print(f"  Corr({name}): Error - {str(e)}")
    
    return correlations

def main():
    parser = argparse.ArgumentParser(description='ARES-7 ETF Momentum Engine v1')
    parser.add_argument('--price_csv', default='./data/etf_price.csv')
    parser.add_argument('--out', default='./results/engine_etf_mom_v1_results.json')
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 ETF Time-Series Momentum Engine v1")
    print("=" * 70)
    
    # Load data
    pivot_close, pivot_ret = load_etf_data(args.price_csv)
    
    # Calculate signals
    signal = calculate_momentum_signals(pivot_close)
    
    # Backtest
    result = backtest_etf_momentum(pivot_ret, signal)
    
    # Calculate correlations with existing engines
    engine_paths = {
        'A+LS': './results/engine_ls_enhanced_results.json',
        'C1': './results/C1_final_v5.json',
        'LV2': './results/engine_c_lowvol_v2_final_results.json',
        'Factor': './results/engine_factor_final_results.json'
    }
    
    correlations = calculate_correlations(result['daily_returns'], engine_paths)
    
    # Save results
    output = {
        'sharpe': result['sharpe'],
        'annual_return': result['annual_return'],
        'annual_volatility': result['annual_volatility'],
        'max_drawdown': result['max_drawdown'],
        'avg_turnover': result['avg_turnover'],
        'avg_holdings': result['avg_holdings'],
        'corr_with_A': correlations.get('A+LS'),
        'corr_with_C1': correlations.get('C1'),
        'corr_with_LV2': correlations.get('LV2'),
        'corr_with_F': correlations.get('Factor'),
        'daily_returns': [
            {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
            for d, r in result['daily_returns'].items()
        ]
    }
    
    with open(args.out, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")
    
    # Assessment
    print("\n" + "=" * 70)
    print("Assessment")
    print("=" * 70)
    
    max_corr = max([c for c in correlations.values() if c is not None], default=0)
    
    if result['sharpe'] >= 0.7 and max_corr <= 0.3:
        print("✅ ETF Momentum Layer is PROMISING as 5th engine/layer")
        print(f"   - Sharpe {result['sharpe']:.3f} >= 0.7 ✅")
        print(f"   - Max correlation {max_corr:.3f} <= 0.3 ✅")
    elif result['sharpe'] >= 0.7:
        print("⚠️  ETF Momentum has good Sharpe but high correlation")
        print(f"   - Sharpe {result['sharpe']:.3f} >= 0.7 ✅")
        print(f"   - Max correlation {max_corr:.3f} > 0.3 ❌")
    elif max_corr <= 0.3:
        print("⚠️  ETF Momentum has low correlation but insufficient Sharpe")
        print(f"   - Sharpe {result['sharpe']:.3f} < 0.7 ❌")
        print(f"   - Max correlation {max_corr:.3f} <= 0.3 ✅")
    else:
        print("❌ ETF Momentum alpha is INSUFFICIENT for current settings")
        print(f"   - Sharpe {result['sharpe']:.3f} < 0.7 ❌")
        print(f"   - Max correlation {max_corr:.3f} > 0.3 ❌")

if __name__ == '__main__':
    main()
