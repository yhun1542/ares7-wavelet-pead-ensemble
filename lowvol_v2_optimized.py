#!/usr/bin/env python3
"""
ARES-7 Low-Vol v2 Engine - Optimized Version

Simplified approach to avoid performance issues:
- Use simpler risk metrics
- Pre-compute all factors efficiently
- Avoid DataFrame fragmentation
"""

import argparse
import pandas as pd
import numpy as np
import json
from datetime import datetime

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
    """Calculate risk metrics efficiently using vectorized operations"""
    print("Calculating risk metrics...")
    
    # Market returns (equal-weighted)
    market_ret = pivot_ret.mean(axis=1)
    
    # 1. Volatility (180-day)
    vol_180 = pivot_ret.rolling(180).std() * np.sqrt(252)
    
    # 2. Downside volatility (180-day) - simplified
    downside_ret = pivot_ret.copy()
    downside_ret[downside_ret > 0] = 0
    down_vol_180 = downside_ret.rolling(180).std() * np.sqrt(252)
    
    # 3. Beta (252-day) - simplified correlation-based
    def calc_beta_series(ret_series):
        corr = ret_series.rolling(252).corr(market_ret)
        vol_ratio = ret_series.rolling(252).std() / market_ret.rolling(252).std()
        return corr * vol_ratio
    
    beta_252 = pivot_ret.apply(calc_beta_series, axis=0)
    
    # 4. Max drawdown (252-day)
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
        'vol_180': vol_180,
        'down_vol_180': down_vol_180,
        'beta_252': beta_252,
        'mdd_252': mdd_252
    }

def prepare_fundamentals(fund_df, dates):
    """Prepare fundamental data aligned to trading dates"""
    print("Preparing fundamental data...")
    
    # Remove duplicates (keep first occurrence)
    fund_df = fund_df.drop_duplicates(subset=['symbol', 'report_date'], keep='first')
    
    symbols = fund_df['symbol'].unique()
    
    # Initialize DataFrames for each metric
    metrics = {}
    for col in ['ROE', 'gross_margin', 'debt_to_equity']:
        metrics[col] = pd.DataFrame(index=dates, columns=symbols, dtype=float)
    
    # Forward-fill fundamentals for each symbol
    for symbol in symbols:
        symbol_data = fund_df[fund_df['symbol'] == symbol].copy()
        symbol_data = symbol_data.sort_values('report_date').set_index('report_date')
        
        for col in metrics.keys():
            if col in symbol_data.columns:
                # Reindex to all dates with forward fill
                series = symbol_data[col].reindex(dates, method='ffill')
                metrics[col][symbol] = series
    
    print("  Fundamentals aligned")
    
    return metrics

def calculate_composite_scores(risk_metrics, fund_metrics, date, lr_weight=0.7, q_weight=0.3):
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

def backtest_strategy(pivot_ret, risk_metrics, fund_metrics, 
                     lr_weight, q_weight, rebal_days, top_n, cost=0.0005):
    """Backtest a single strategy configuration"""
    
    dates = pivot_ret.index
    symbols = pivot_ret.columns.tolist()
    
    # Rebalancing schedule
    rebal_dates = dates[::rebal_days]
    
    # Initialize weights
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)
    
    for i, rebal_date in enumerate(rebal_dates):
        # Calculate scores
        scores = calculate_composite_scores(risk_metrics, fund_metrics, rebal_date,
                                           lr_weight, q_weight)
        
        if len(scores) < top_n:
            continue
        
        # Select top N
        top_symbols = scores.nlargest(top_n).index.tolist()
        
        # Equal weight
        w = 1.0 / len(top_symbols)
        
        # Determine end date for this rebalancing period
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
    
    if len(net_ret) < 100:
        return None
    
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
    
    return {
        'sharpe': sharpe,
        'annual_return': annual_return,
        'annual_volatility': annual_vol,
        'max_drawdown': max_dd,
        'avg_turnover': avg_turnover,
        'daily_returns': net_ret
    }

def main():
    parser = argparse.ArgumentParser(description='ARES-7 Low-Vol v2 Engine (Optimized)')
    parser.add_argument('--price_csv', default='./data/price_full.csv')
    parser.add_argument('--fund_csv', default='./data/fundamentals.csv')
    parser.add_argument('--out', default='./results/engine_c_lowvol_v2_results.json')
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 Low-Vol v2 Engine - Optimized")
    print("=" * 70)
    
    # Load data
    pivot_close, pivot_ret, fund_df = load_and_prepare_data(args.price_csv, args.fund_csv)
    
    # Calculate risk metrics
    risk_metrics = calculate_risk_metrics(pivot_ret, pivot_close)
    
    # Prepare fundamentals
    fund_metrics = prepare_fundamentals(fund_df, pivot_ret.index)
    
    # Load existing results for correlation
    print("\nLoading existing engine results...")
    with open('./results/engine_ls_enhanced_results.json', 'r') as f:
        als_data = json.load(f)
        als_returns = pd.Series({
            pd.Timestamp(d['date']): d['ret']
            for d in als_data['daily_returns']
        })
    
    with open('./results/engine_c_lowvol_v1_results.json', 'r') as f:
        lv1_data = json.load(f)
        lv1_returns = pd.Series({
            pd.Timestamp(d['date']): d['ret']
            for d in lv1_data['daily_returns']
        })
    
    # Test configurations
    print("\n" + "=" * 70)
    print("Testing Configurations")
    print("=" * 70)
    
    configs = [
        (0.7, 0.3, 60, 25, "A_lr0.7_q0.3_reb60_n25"),
        (0.6, 0.4, 60, 25, "B_lr0.6_q0.4_reb60_n25"),
        (0.5, 0.5, 60, 25, "C_lr0.5_q0.5_reb60_n25"),
        (0.8, 0.2, 60, 25, "D_lr0.8_q0.2_reb60_n25"),
        (0.7, 0.3, 20, 25, "E_lr0.7_q0.3_reb20_n25"),
        (0.7, 0.3, 60, 30, "F_lr0.7_q0.3_reb60_n30"),
    ]
    
    variants = []
    
    for lr_w, q_w, reb_days, top_n, name in configs:
        print(f"\n{name}: LR={lr_w}, Q={q_w}, Rebal={reb_days}d, Top={top_n}")
        
        result = backtest_strategy(pivot_ret, risk_metrics, fund_metrics,
                                   lr_w, q_w, reb_days, top_n)
        
        if result is None:
            print("  ❌ Failed")
            continue
        
        # Calculate correlations
        common_dates = result['daily_returns'].index.intersection(als_returns.index)
        if len(common_dates) > 100:
            corr_als = result['daily_returns'].loc[common_dates].corr(als_returns.loc[common_dates])
        else:
            corr_als = np.nan
        
        common_dates = result['daily_returns'].index.intersection(lv1_returns.index)
        if len(common_dates) > 100:
            corr_lv1 = result['daily_returns'].loc[common_dates].corr(lv1_returns.loc[common_dates])
        else:
            corr_lv1 = np.nan
        
        print(f"  Sharpe: {result['sharpe']:.3f}")
        print(f"  Annual Return: {result['annual_return']:.2%}")
        print(f"  Annual Vol: {result['annual_volatility']:.2%}")
        print(f"  MDD: {result['max_drawdown']:.2%}")
        print(f"  Avg Turnover: {result['avg_turnover']:.4f}")
        print(f"  Corr(A+LS): {corr_als:.3f}")
        print(f"  Corr(LV v1): {corr_lv1:.3f}")
        
        # Save variant
        variants.append({
            'name': name,
            'weights': {'lr': lr_w, 'q': q_w, 'rebalance_days': reb_days, 'top_n': top_n},
            'stats': {
                'sharpe': float(result['sharpe']),
                'annual_return': float(result['annual_return']),
                'annual_volatility': float(result['annual_volatility']),
                'max_drawdown': float(result['max_drawdown']),
                'avg_turnover': float(result['avg_turnover']),
                'corr_with_A': float(corr_als) if not np.isnan(corr_als) else None,
                'corr_with_lowvol_v1': float(corr_lv1) if not np.isnan(corr_lv1) else None
            },
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in result['daily_returns'].items()
            ]
        })
    
    # Save results
    print("\n" + "=" * 70)
    print("Saving results...")
    
    output = {'variants': variants}
    with open(args.out, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Saved to {args.out}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    # Find candidates
    candidates = [
        v for v in variants
        if v['stats']['sharpe'] >= 0.7 and 
           v['stats']['corr_with_A'] is not None and
           v['stats']['corr_with_A'] <= 0.5
    ]
    
    if candidates:
        best = max(candidates, key=lambda x: x['stats']['sharpe'])
        print(f"\n✅ Best candidate: {best['name']}")
        print(f"   Sharpe: {best['stats']['sharpe']:.3f}")
        print(f"   Corr(A+LS): {best['stats']['corr_with_A']:.3f}")
        print(f"   MDD: {best['stats']['max_drawdown']:.2%}")
    else:
        print("\n⚠️  No variant meets criteria (Sharpe >= 0.7 AND Corr <= 0.5)")
        if variants:
            best = max(variants, key=lambda x: x['stats']['sharpe'])
            print(f"   Best by Sharpe: {best['name']}")
            print(f"   Sharpe: {best['stats']['sharpe']:.3f}")
            corr_a = best['stats']['corr_with_A']
            if corr_a is not None:
                print(f"   Corr(A+LS): {corr_a:.3f}")

if __name__ == '__main__':
    main()
