#!/usr/bin/env python3
"""
ARES-7 Low-Vol v2 Engine - Defensive Factor Redesign

Goal:
1. Sharpe >= 0.7 (maintain or improve from v1)
2. Correlation with A+LS Enhanced <= 0.5 (reduce from ~0.85)
3. MDD maintain or improve from v1 (~-30%)
4. Low turnover with quarterly rebalancing

Strategy:
- Low Risk Score (70%): down_vol_180, beta_252, dd_252
- Quality Score (30%): ROE, gross_margin, debt_to_equity
- Long-only, equal-weight top N stocks
- Quarterly rebalancing (60 days)
"""

import argparse
import pandas as pd
import numpy as np
import json
from datetime import datetime

def load_price_data(csv_path):
    """Load and prepare price data"""
    print("Loading price data...")
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Calculate returns
    df['ret1'] = df.groupby('symbol')['close'].pct_change()
    
    print(f"  Loaded {len(df):,} rows, {df['symbol'].nunique()} symbols")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df

def calculate_market_returns(price_df):
    """Calculate equal-weighted market returns"""
    print("Calculating market returns...")
    
    # Pivot returns
    pivot_ret = price_df.pivot(index='timestamp', columns='symbol', values='ret1')
    
    # Market return = equal-weighted average
    market_ret = pivot_ret.mean(axis=1)
    
    return pivot_ret, market_ret

def calculate_risk_factors(pivot_ret, pivot_close, market_ret):
    """Calculate risk-based factors for all stocks"""
    print("Calculating risk factors...")
    
    factors = pd.DataFrame(index=pivot_ret.index)
    
    for symbol in pivot_ret.columns:
        ret_series = pivot_ret[symbol]
        close_series = pivot_close[symbol]
        
        # 1. Downside volatility (180 days)
        down_vol_180 = ret_series.rolling(180).apply(
            lambda x: x[x < 0].std() * np.sqrt(252) if len(x[x < 0]) > 0 else np.nan
        )
        
        # 2. Beta (252 days)
        def rolling_beta(window):
            if len(window) < 60:
                return np.nan
            stock_ret = ret_series.loc[window.index]
            mkt_ret = market_ret.loc[window.index]
            valid = stock_ret.notna() & mkt_ret.notna()
            if valid.sum() < 60:
                return np.nan
            cov = np.cov(stock_ret[valid], mkt_ret[valid])[0, 1]
            var = np.var(mkt_ret[valid])
            return cov / var if var > 0 else np.nan
        
        beta_252 = ret_series.rolling(252).apply(
            lambda x: rolling_beta(x) if len(x) >= 60 else np.nan,
            raw=False
        )
        
        # Simplified beta calculation
        beta_252 = ret_series.rolling(252).corr(market_ret) * (
            ret_series.rolling(252).std() / market_ret.rolling(252).std()
        )
        
        # 3. Maximum drawdown (252 days)
        def rolling_max_dd(prices):
            if len(prices) < 60:
                return np.nan
            cummax = prices.expanding().max()
            dd = (prices - cummax) / cummax
            return dd.min()
        
        dd_252 = close_series.rolling(252).apply(rolling_max_dd, raw=False)
        
        # Store factors
        factors[f'{symbol}_down_vol'] = down_vol_180
        factors[f'{symbol}_beta'] = beta_252
        factors[f'{symbol}_dd'] = dd_252.abs()  # Use absolute value for ranking
    
    return factors

def load_fundamentals(csv_path):
    """Load fundamental data"""
    print("Loading fundamental data...")
    df = pd.read_csv(csv_path)
    df['report_date'] = pd.to_datetime(df['report_date'])
    df = df.sort_values(['symbol', 'report_date']).reset_index(drop=True)
    
    print(f"  Loaded {len(df):,} rows, {df['symbol'].nunique()} symbols")
    
    return df

def align_fundamentals_to_dates(fund_df, dates):
    """Forward-fill fundamentals to align with trading dates"""
    print("Aligning fundamentals to trading dates...")
    
    symbols = fund_df['symbol'].unique()
    result = pd.DataFrame(index=dates)
    
    for symbol in symbols:
        symbol_data = fund_df[fund_df['symbol'] == symbol].copy()
        symbol_data = symbol_data.set_index('report_date')
        
        # Forward fill to all dates
        for col in ['ROE', 'gross_margin', 'debt_to_equity', 'PER', 'PBR']:
            if col in symbol_data.columns:
                series = symbol_data[col].reindex(dates, method='ffill')
                result[f'{symbol}_{col}'] = series
    
    return result

def calculate_scores(risk_factors, fund_aligned, symbols, date, 
                     lr_weight=0.7, q_weight=0.3):
    """Calculate Low Risk Score and Quality Score for a given date"""
    
    scores = {}
    
    for symbol in symbols:
        # Low Risk Score components
        down_vol = risk_factors.loc[date, f'{symbol}_down_vol']
        beta = risk_factors.loc[date, f'{symbol}_beta']
        dd = risk_factors.loc[date, f'{symbol}_dd']
        
        # Quality Score components
        roe = fund_aligned.loc[date, f'{symbol}_ROE']
        gross_margin = fund_aligned.loc[date, f'{symbol}_gross_margin']
        debt_to_equity = fund_aligned.loc[date, f'{symbol}_debt_to_equity']
        
        # Check if all values are available
        if pd.isna([down_vol, beta, dd, roe, gross_margin, debt_to_equity]).any():
            continue
        
        scores[symbol] = {
            'down_vol': down_vol,
            'beta': beta,
            'dd': dd,
            'roe': roe,
            'gross_margin': gross_margin,
            'debt_to_equity': debt_to_equity
        }
    
    if len(scores) == 0:
        return {}
    
    # Convert to DataFrame for ranking
    score_df = pd.DataFrame(scores).T
    
    # Rank percentile (0 to 1)
    def rank_pct(series):
        return series.rank(pct=True)
    
    # Low Risk Score (lower is better, so invert)
    lr1 = 1 - rank_pct(score_df['down_vol'])
    lr2 = 1 - rank_pct(score_df['beta'])
    lr3 = 1 - rank_pct(score_df['dd'])
    score_lr = (lr1 + lr2 + lr3) / 3
    
    # Quality Score (higher is better, except debt)
    q1 = rank_pct(score_df['roe'])
    q2 = rank_pct(score_df['gross_margin'])
    q3 = 1 - rank_pct(score_df['debt_to_equity'])
    score_q = (q1 + q2 + q3) / 3
    
    # Final Score
    final_score = lr_weight * score_lr + q_weight * score_q
    
    return final_score.to_dict()

def backtest_variant(pivot_ret, risk_factors, fund_aligned, 
                     lr_weight, q_weight, rebal_days, top_n, cost=0.0005):
    """Backtest a single variant configuration"""
    
    dates = pivot_ret.index
    symbols = pivot_ret.columns.tolist()
    
    # Generate rebalancing schedule
    rebal_dates = dates[::rebal_days]
    
    # Portfolio weights
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)
    
    for rebal_date in rebal_dates:
        if rebal_date not in risk_factors.index or rebal_date not in fund_aligned.index:
            continue
        
        # Calculate scores
        scores = calculate_scores(risk_factors, fund_aligned, symbols, rebal_date,
                                 lr_weight, q_weight)
        
        if len(scores) < top_n:
            continue
        
        # Select top N
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = [s[0] for s in sorted_scores[:top_n]]
        
        # Equal weight
        w = 1.0 / len(selected)
        
        # Apply weights from rebal_date until next rebal
        next_rebal_idx = dates.get_loc(rebal_date) + rebal_days
        end_date = dates[min(next_rebal_idx, len(dates)-1)]
        
        weights.loc[rebal_date:end_date, selected] = w
        weights.loc[rebal_date:end_date, [s for s in symbols if s not in selected]] = 0.0
    
    # Calculate portfolio returns
    port_ret = (weights.shift(1) * pivot_ret).sum(axis=1)
    
    # Calculate turnover
    turnover = weights.diff().abs().sum(axis=1)
    turnover_cost = turnover * cost
    
    # Net returns
    net_ret = port_ret - turnover_cost
    
    # Performance metrics
    valid_ret = net_ret.dropna()
    
    if len(valid_ret) == 0:
        return None
    
    sharpe = valid_ret.mean() / valid_ret.std() * np.sqrt(252) if valid_ret.std() > 0 else 0
    annual_return = valid_ret.mean() * 252
    annual_vol = valid_ret.std() * np.sqrt(252)
    
    # Max drawdown
    cumret = (1 + valid_ret).cumprod()
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

def calculate_correlation(returns1, returns2):
    """Calculate correlation between two return series"""
    df = pd.DataFrame({'r1': returns1, 'r2': returns2})
    df = df.dropna()
    if len(df) < 100:
        return np.nan
    return df['r1'].corr(df['r2'])

def main():
    parser = argparse.ArgumentParser(description='ARES-7 Low-Vol v2 Engine')
    parser.add_argument('--price_csv', default='./data/price_full.csv')
    parser.add_argument('--fund_csv', default='./data/fundamentals.csv')
    parser.add_argument('--out', default='./results/engine_c_lowvol_v2_results.json')
    args = parser.parse_args()
    
    print("=" * 70)
    print("ARES-7 Low-Vol v2 Engine - Defensive Factor Redesign")
    print("=" * 70)
    
    # Load data
    price_df = load_price_data(args.price_csv)
    pivot_ret, market_ret = calculate_market_returns(price_df)
    pivot_close = price_df.pivot(index='timestamp', columns='symbol', values='close')
    
    # Calculate risk factors
    risk_factors = calculate_risk_factors(pivot_ret, pivot_close, market_ret)
    
    # Load and align fundamentals
    fund_df = load_fundamentals(args.fund_csv)
    fund_aligned = align_fundamentals_to_dates(fund_df, pivot_ret.index)
    
    # Load existing engine results for correlation
    print("\nLoading existing engine results...")
    with open('./results/engine_ls_enhanced_results.json', 'r') as f:
        als_results = json.load(f)
        als_returns = pd.Series({
            datetime.strptime(d['date'], '%Y-%m-%d'): d['ret']
            for d in als_results['daily_returns']
        })
    
    with open('./results/engine_c_lowvol_v1_results.json', 'r') as f:
        lv1_results = json.load(f)
        lv1_returns = pd.Series({
            datetime.strptime(d['date'], '%Y-%m-%d'): d['ret']
            for d in lv1_results['daily_returns']
        })
    
    # Test variants
    print("\n" + "=" * 70)
    print("Testing Variants")
    print("=" * 70)
    
    variants = []
    
    # Variant configurations
    configs = [
        # (lr_weight, q_weight, rebal_days, top_n, name)
        (0.7, 0.3, 60, 25, "A_lr0.7_q0.3_reb60_n25"),
        (0.6, 0.4, 60, 25, "B_lr0.6_q0.4_reb60_n25"),
        (0.5, 0.5, 60, 25, "C_lr0.5_q0.5_reb60_n25"),
        (0.7, 0.3, 20, 25, "D_lr0.7_q0.3_reb20_n25"),
        (0.7, 0.3, 60, 30, "E_lr0.7_q0.3_reb60_n30"),
    ]
    
    for lr_w, q_w, reb_days, top_n, name in configs:
        print(f"\nTesting {name}...")
        print(f"  LR={lr_w}, Q={q_w}, Rebal={reb_days}d, Top={top_n}")
        
        result = backtest_variant(pivot_ret, risk_factors, fund_aligned,
                                 lr_w, q_w, reb_days, top_n)
        
        if result is None:
            print(f"  ❌ Failed to backtest")
            continue
        
        # Calculate correlations
        corr_als = calculate_correlation(result['daily_returns'], als_returns)
        corr_lv1 = calculate_correlation(result['daily_returns'], lv1_returns)
        
        print(f"  Sharpe: {result['sharpe']:.3f}")
        print(f"  Annual Return: {result['annual_return']:.2%}")
        print(f"  Annual Vol: {result['annual_volatility']:.2%}")
        print(f"  MDD: {result['max_drawdown']:.2%}")
        print(f"  Avg Turnover: {result['avg_turnover']:.4f}")
        print(f"  Corr with A+LS: {corr_als:.3f}")
        print(f"  Corr with LV v1: {corr_lv1:.3f}")
        
        # Save variant
        variants.append({
            'name': name,
            'weights': {'lr': lr_w, 'q': q_w, 'rebalance_days': reb_days, 'top_n': top_n},
            'stats': {
                'sharpe': result['sharpe'],
                'annual_return': result['annual_return'],
                'annual_volatility': result['annual_volatility'],
                'max_drawdown': result['max_drawdown'],
                'avg_turnover': result['avg_turnover'],
                'corr_with_A': corr_als,
                'corr_with_lowvol_v1': corr_lv1
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
    
    print(f"✅ Results saved to {args.out}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    # Find best variant meeting criteria
    candidates = [
        v for v in variants
        if v['stats']['sharpe'] >= 0.7 and v['stats']['corr_with_A'] <= 0.5
    ]
    
    if candidates:
        best = max(candidates, key=lambda x: x['stats']['sharpe'])
        print(f"\n✅ Best candidate: {best['name']}")
        print(f"   Sharpe: {best['stats']['sharpe']:.3f}")
        print(f"   Corr with A+LS: {best['stats']['corr_with_A']:.3f}")
        print(f"   MDD: {best['stats']['max_drawdown']:.2%}")
    else:
        print("\n⚠️  No variant meets criteria (Sharpe >= 0.7 AND Corr <= 0.5)")
        print("   Showing best by Sharpe:")
        if variants:
            best = max(variants, key=lambda x: x['stats']['sharpe'])
            print(f"   {best['name']}: Sharpe {best['stats']['sharpe']:.3f}, Corr {best['stats']['corr_with_A']:.3f}")

if __name__ == '__main__':
    main()
