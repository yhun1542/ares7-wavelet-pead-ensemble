#!/usr/bin/env python3
"""
ARES-7 Multiple Pairs Trading v1
Market-Neutral High-Sharpe Strategy

특징:
- 10-20개 페어 동시 거래
- 각 페어 독립적 신호 생성
- Cointegration 기반 페어 선택
- Z-score 기반 진입/청산
- 거래비용 포함
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.stattools import coint
import warnings
warnings.filterwarnings('ignore')

TRADING_DAYS = 252

# ------------------------------------------------------------
# Data Loading
# ------------------------------------------------------------
def load_price(path="./data/price_full.csv"):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["timestamp", "symbol"])
    price = df.pivot(index="timestamp", columns="symbol", values="close")
    return price

# ------------------------------------------------------------
# Pair Selection (Cointegration)
# ------------------------------------------------------------
def find_cointegrated_pairs(prices, max_pairs=20, pvalue_threshold=0.05):
    """
    Find cointegrated pairs using Engle-Granger test
    """
    symbols = prices.columns
    n = len(symbols)
    
    pairs = []
    
    for i in range(n):
        for j in range(i+1, n):
            s1 = symbols[i]
            s2 = symbols[j]
            
            # Skip if too many NaN
            if prices[[s1, s2]].isna().sum().sum() > 100:
                continue
            
            # Cointegration test
            try:
                score, pvalue, _ = coint(prices[s1].dropna(), prices[s2].dropna())
                
                if pvalue < pvalue_threshold:
                    pairs.append((s1, s2, pvalue, score))
            except:
                continue
    
    # Sort by p-value (lower is better)
    pairs = sorted(pairs, key=lambda x: x[2])[:max_pairs]
    
    return [(p[0], p[1]) for p in pairs]

# ------------------------------------------------------------
# Single Pair Trading
# ------------------------------------------------------------
def trade_single_pair(prices, pair1, pair2, entry_z=2.0, exit_z=0.5, cost_bps=5):
    """
    Trade a single pair using z-score strategy
    """
    df = prices[[pair1, pair2]].dropna().copy()
    
    if len(df) < 100:
        return pd.Series(0.0, index=prices.index)
    
    # Log prices
    df['log1'] = np.log(df[pair1])
    df['log2'] = np.log(df[pair2])
    
    # Hedge ratio (OLS)
    X = df['log2'].values.reshape(-1, 1)
    y = df['log1'].values
    reg = LinearRegression().fit(X, y)
    hedge = reg.coef_[0]
    
    # Spread
    df['spread'] = df['log1'] - hedge * df['log2']
    
    # Rolling z-score (60-day window)
    df['spread_mean'] = df['spread'].rolling(60).mean()
    df['spread_std'] = df['spread'].rolling(60).std()
    df['zscore'] = (df['spread'] - df['spread_mean']) / df['spread_std']
    
    # Positions
    df['position'] = 0.0
    pos = 0.0
    
    for i in range(1, len(df)):
        z = df['zscore'].iloc[i]
        
        if pd.isna(z):
            df['position'].iloc[i] = pos
            continue
        
        if pos == 0:
            if z > entry_z:
                pos = -1.0  # Short spread
            elif z < -entry_z:
                pos = 1.0   # Long spread
        elif pos == 1.0:
            if z > exit_z:
                pos = 0.0
        elif pos == -1.0:
            if z < -exit_z:
                pos = 0.0
        
        df['position'].iloc[i] = pos
    
    # Returns
    df[f'ret1'] = df[pair1].pct_change()
    df[f'ret2'] = df[pair2].pct_change()
    
    # Strategy return (spread return)
    df['strat_ret'] = df['position'].shift(1) * (df[f'ret1'] - hedge * df[f'ret2'])
    
    # Trading costs
    df['trade'] = (df['position'] != df['position'].shift(1)).astype(float)
    df['strat_ret'] -= df['trade'] * (cost_bps / 10000) * 2  # Both legs
    
    # Reindex to full price index
    ret_full = pd.Series(0.0, index=prices.index)
    ret_full.loc[df.index] = df['strat_ret'].fillna(0.0)
    
    return ret_full

# ------------------------------------------------------------
# Multiple Pairs Portfolio
# ------------------------------------------------------------
def trade_multiple_pairs(prices, pairs, entry_z=2.0, exit_z=0.5, cost_bps=5):
    """
    Trade multiple pairs with equal weight
    """
    all_returns = []
    
    print(f"Trading {len(pairs)} pairs...")
    
    for i, (p1, p2) in enumerate(pairs):
        print(f"  {i+1}/{len(pairs)}: {p1} vs {p2}")
        
        ret = trade_single_pair(prices, p1, p2, entry_z, exit_z, cost_bps)
        all_returns.append(ret)
    
    # Equal weight portfolio
    portfolio_ret = pd.concat(all_returns, axis=1).mean(axis=1)
    
    return portfolio_ret

# ------------------------------------------------------------
# Metrics
# ------------------------------------------------------------
def compute_metrics(returns):
    """
    Compute performance metrics
    """
    ret = returns.dropna()
    
    if len(ret) == 0 or ret.std() == 0:
        return {
            "sharpe": 0.0,
            "annual_return": 0.0,
            "annual_volatility": 0.0,
            "max_drawdown": 0.0,
        }
    
    mu = ret.mean() * TRADING_DAYS
    vol = ret.std() * np.sqrt(TRADING_DAYS)
    sharpe = mu / vol if vol > 0 else 0.0
    
    cum = (1 + ret).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1.0
    mdd = dd.min()
    
    return {
        "sharpe": float(sharpe),
        "annual_return": float(mu),
        "annual_volatility": float(vol),
        "max_drawdown": float(mdd),
    }

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    print("="*70)
    print("ARES-7 Multiple Pairs Trading v1")
    print("="*70)
    
    # Load data
    print("\nLoading price data...")
    prices = load_price()
    print(f"  Loaded: {prices.shape[0]} days, {prices.shape[1]} symbols")
    
    # Find cointegrated pairs
    print("\nFinding cointegrated pairs...")
    pairs = find_cointegrated_pairs(prices, max_pairs=15, pvalue_threshold=0.05)
    print(f"  Found {len(pairs)} cointegrated pairs")
    
    if len(pairs) == 0:
        print("❌ No cointegrated pairs found!")
        return
    
    for i, (p1, p2) in enumerate(pairs[:10]):
        print(f"    {i+1}. {p1} vs {p2}")
    
    # Trade multiple pairs
    print("\nBacktesting...")
    portfolio_ret = trade_multiple_pairs(prices, pairs)
    
    # Compute metrics
    metrics = compute_metrics(portfolio_ret)
    
    print("\n" + "="*70)
    print("Results:")
    print("="*70)
    print(f"  Sharpe Ratio:      {metrics['sharpe']:.4f}")
    print(f"  Annual Return:     {metrics['annual_return']:.2%}")
    print(f"  Annual Volatility: {metrics['annual_volatility']:.2%}")
    print(f"  Max Drawdown:      {metrics['max_drawdown']:.2%}")
    print("="*70)
    
    # Save results
    result = {
        **metrics,
        "config": {
            "n_pairs": len(pairs),
            "entry_z": 2.0,
            "exit_z": 0.5,
            "cost_bps": 5,
        },
        "pairs": [f"{p1}-{p2}" for p1, p2 in pairs],
        "daily_returns": portfolio_ret.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in prices.index],
    }
    
    Path("./results").mkdir(exist_ok=True)
    out_path = "./results/engine_multi_pairs_trading_v1.json"
    
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\n✅ Results saved to: {out_path}")

if __name__ == "__main__":
    main()
