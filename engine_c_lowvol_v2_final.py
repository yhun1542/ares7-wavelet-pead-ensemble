#!/usr/bin/env python3
"""
ARES-7 Low-Vol v2 Final Engine

Selected configuration: C_lr0.5_q0.5_reb60_n25
- Low Risk Weight: 0.5
- Quality Weight: 0.5
- Rebalance: 60 days (quarterly)
- Top N: 25 stocks
"""

import argparse
import pandas as pd
import numpy as np
import json

# Fixed configuration (best from research)
CONFIG = {
    'lr_weight': 0.5,
    'q_weight': 0.5,
    'rebalance_days': 60,
    'top_n': 25,
    'cost': 0.0005
}

def load_and_prepare_data(price_csv, fund_csv):
    """Load and prepare all data"""
    print("Loading data...")
    
    # Load price data
    price_df = pd.read_csv(price_csv)
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
    price_df = price_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Pivot data
    pivot_close = price_df.pivot(index='timestamp', columns='symbol', values='close')
    pivot_ret = pivot_close.pct_change()
    
    print(f"  Price data: {len(pivot_close)} days, {len(pivot_close.columns)} symbols")
    
    # Load fundamentals
    fund_df = pd.read_csv(fund_csv)
    fund_df['report_date'] = pd.to_datetime(fund_df['report_date'])
    
    print(f"  Fundamental data: {len(fund_df)} rows")
    
    return pivot_close, pivot_ret, fund_df

def calculate_risk_metrics(pivot_ret, pivot_close):
    """Calculate risk metrics efficiently"""
    print("Calculating risk metrics...")
    
    # Market returns (equal-weighted)
    market_ret = pivot_ret.mean(axis=1)
    
    # 1. Downside volatility (180-day)
    downside_ret = pivot_ret.copy()
    downside_ret[downside_ret > 0] = 0
    down_vol_180 = downside_ret.rolling(180).std() * np.sqrt(252)
    
    # 2. Beta (252-day)
    def calc_beta_series(ret_series):
        corr = ret_series.rolling(252).corr(market_ret)
        vol_ratio = ret_series.rolling(252).std() / market_ret.rolling(252).std()
        return corr * vol_ratio
    
    beta_252 = pivot_ret.apply(calc_beta_series, axis=0)
    
    # 3. Max drawdown (252-day)
    def calc_rolling_mdd(close_series):
        def mdd_window(window):
            if len(window) < 60:
                return np.nan
            cummax = np.maximum.accumulate(window)
            dd = (window - cummax) / cummax
            return dd.min()
        return close_series.rolling(252).apply(mdd_window, raw=True)
    
    mdd_252 = pivot_close.apply(calc_rolling_mdd, axis=0).abs()
    
    print("  Risk metrics calculated")
    
    return {
        'down_vol_180': down_vol_180,
        'beta_252': beta_252,
        'mdd_252': mdd_252
    }

def prepare_fundamentals(fund_df, dates):
    """Prepare fundamental data aligned to trading dates"""
    print("Preparing fundamental data...")
    
    # Remove duplicates
    fund_df = fund_df.drop_duplicates(subset=['symbol', 'report_date'], keep='first')
    
    symbols = fund_df['symbol'].unique()
    
    # Initialize DataFrames
    metrics = {}
    for col in ['ROE', 'gross_margin', 'debt_to_equity']:
        metrics[col] = pd.DataFrame(index=dates, columns=symbols, dtype=float)
    
    # Forward-fill fundamentals
    for symbol in symbols:
        symbol_data = fund_df[fund_df['symbol'] == symbol].copy()
        symbol_data = symbol_data.sort_values('report_date').set_index('report_date')
        
        for col in metrics.keys():
            if col in symbol_data.columns:
                series = symbol_data[col].reindex(dates, method='ffill')
                metrics[col][symbol] = series
    
    print("  Fundamentals aligned")
    
    return metrics

def calculate_composite_scores(risk_metrics, fund_metrics, date, lr_weight, q_weight):
    """Calculate composite scores for a specific date"""
    
    # Get data for this date
    down_vol = risk_metrics['down_vol_180'].loc[date]
    beta = risk_metrics['beta_252'].loc[date]
    mdd = risk_metrics['mdd_252'].loc[date]
    
    roe = fund_metrics['ROE'].loc[date]
    gross_margin = fund_metrics['gross_margin'].loc[date]
    debt_to_equity = fund_metrics['debt_to_equity'].loc[date]
    
    # Combine into DataFrame
    df = pd.DataFrame({
        'down_vol': down_vol,
        'beta': beta,
        'mdd': mdd,
        'roe': roe,
        'gross_margin': gross_margin,
        'debt_to_equity': debt_to_equity
    })
    
    # Drop symbols with missing data
    df = df.dropna()
    
    if len(df) < 20:
        return pd.Series(dtype=float)
    
    # Rank percentile
    def rank_pct(series):
        return series.rank(pct=True)
    
    # Low Risk Score (lower is better, so invert)
    lr1 = 1 - rank_pct(df['down_vol'])
    lr2 = 1 - rank_pct(df['beta'])
    lr3 = 1 - rank_pct(df['mdd'])
    score_lr = (lr1 + lr2 + lr3) / 3
    
    # Quality Score (higher is better, except debt)
    q1 = rank_pct(df['roe'])
    q2 = rank_pct(df['gross_margin'])
    q3 = 1 - rank_pct(df['debt_to_equity'])
    score_q = (q1 + q2 + q3) / 3
    
    # Final Score
    final_score = lr_weight * score_lr + q_weight * score_q
    
    return final_score

def backtest_strategy(pivot_ret, risk_metrics, fund_metrics, config):
    """Backtest the strategy with fixed configuration"""
    
    dates = pivot_ret.index
    symbols = pivot_ret.columns.tolist()
    
    lr_weight = config['lr_weight']
    q_weight = config['q_weight']
    rebal_days = config['rebalance_days']
    top_n = config['top_n']
    cost = config['cost']
    
    # Rebalancing schedule
    rebal_dates = dates[::rebal_days]
    
    # Initialize weights
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)
    
    print(f"\nBacktesting with config: LR={lr_weight}, Q={q_weight}, Rebal={rebal_days}d, Top={top_n}")
    
    for i, rebal_date in enumerate(rebal_dates):
        if rebal_date not in risk_metrics['down_vol_180'].index or rebal_date not in fund_metrics['ROE'].index:
            continue
        
        # Calculate scores
        scores = calculate_composite_scores(risk_metrics, fund_metrics, rebal_date,
                                           lr_weight, q_weight)
        
        if len(scores) < top_n:
            continue
        
        # Select top N
        top_symbols = scores.nlargest(top_n).index.tolist()
        
        # Equal weight
        w = 1.0 / len(top_symbols)
        
        # Determine end date
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
    parser = argparse.ArgumentParser(description='ARES-7 Low-Vol v2 Final Engine')
    parser.add_argument('--price_csv', default='./data/price_full.csv')
    parser.add_argument('--fund_csv', default='./data/fundamentals.csv')
    parser.add_argument('--out', default='./results/engine_c_lowvol_v2_final_results.json')
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 Low-Vol v2 Final Engine")
    print("=" * 70)
    print(f"Configuration: {CONFIG}")
    print("=" * 70)
    
    # Load data
    pivot_close, pivot_ret, fund_df = load_and_prepare_data(args.price_csv, args.fund_csv)
    
    # Calculate risk metrics
    risk_metrics = calculate_risk_metrics(pivot_ret, pivot_close)
    
    # Prepare fundamentals
    fund_metrics = prepare_fundamentals(fund_df, pivot_ret.index)
    
    # Backtest
    result = backtest_strategy(pivot_ret, risk_metrics, fund_metrics, CONFIG)
    
    # Save results
    output = {
        'config': CONFIG,
        'sharpe': result['sharpe'],
        'annual_return': result['annual_return'],
        'annual_volatility': result['annual_volatility'],
        'max_drawdown': result['max_drawdown'],
        'avg_turnover': result['avg_turnover'],
        'daily_returns': result['daily_returns']
    }
    
    with open(args.out, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")

if __name__ == '__main__':
    main()
