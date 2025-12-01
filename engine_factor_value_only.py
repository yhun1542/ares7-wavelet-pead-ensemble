"""
Factor Engine (Value Only) - Final Version
Target: Sharpe 0.555

Specifications:
- Value 100% (PER + PBR)
- Quality 0%
- Monthly Rebalancing
- Winsorization (2.5% / 97.5%)
- Universe: 100 stocks
- Gross Leverage: 2.0
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

TRADING_DAYS = 252

def winsorize(s, lower=0.025, upper=0.975):
    """Winsorize series at specified percentiles"""
    s = s.copy()
    lower_val = s.quantile(lower)
    upper_val = s.quantile(upper)
    s[s < lower_val] = lower_val
    s[s > upper_val] = upper_val
    return s

def zscore(s):
    """Calculate z-score"""
    s = s.replace([np.inf, -np.inf], np.nan)
    m = s.mean()
    v = s.std()
    if v == 0 or np.isnan(v):
        return s * 0.0
    return (s - m) / v

def load_price(path="./data/price_full.csv"):
    """Load price data"""
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["timestamp", "symbol"])
    price = df.pivot(index="timestamp", columns="symbol", values="close")
    return price

def load_fund(path="./data/fundamentals_with_sector.csv"):
    """Load fundamentals data"""
    df = pd.read_csv(path)
    df["report_date"] = pd.to_datetime(df["report_date"]).dt.normalize()
    return df

def get_pit_fund(fund, as_of, lag_days=90):
    """Get point-in-time fundamentals"""
    cutoff = as_of - pd.Timedelta(days=lag_days)
    f = fund[fund["report_date"] <= cutoff]
    if f.empty:
        return pd.DataFrame()
    idx = f.groupby("symbol")["report_date"].idxmax()
    return f.loc[idx].set_index("symbol")

def build_value_signals(price, fund, lag_days=90):
    """Build Value-only signals with winsorization"""
    
    # Monthly rebalancing (first trading day of each month)
    rebal_dates = price.resample("MS").first().index
    rebal_dates = [d for d in rebal_dates if d in price.index]
    
    scores = {}
    
    for d in rebal_dates:
        pit = get_pit_fund(fund, d, lag_days=lag_days)
        if pit.empty:
            continue
        
        common = price.columns.intersection(pit.index)
        if len(common) < 40:
            continue
        
        # Value factors
        f = pit.loc[common]
        
        pe = f["pe"].replace(0, np.nan)
        pb = f["pb"].replace(0, np.nan)
        
        # Winsorize
        pe = winsorize(pe, 0.025, 0.975)
        pb = winsorize(pb, 0.025, 0.975)
        
        # Value score (low PE/PB is good)
        value_pe = zscore(-pe)
        value_pb = zscore(-pb)
        
        # Combined value score (equal weight)
        value_score = (value_pe + value_pb) / 2.0
        
        scores[d] = value_score.dropna()
    
    # Convert to DataFrame
    all_dates = sorted(scores.keys())
    sig_df = pd.DataFrame(index=all_dates, columns=price.columns, dtype=float)
    for d, s in scores.items():
        sig_df.loc[d, s.index] = s.values
    
    return sig_df

def run_backtest(price, signals,
                 n_long=20, n_short=20,
                 gross=2.0, tc_bps=5):
    """Run backtest with long-short strategy"""
    
    ret = price.pct_change()
    dates = price.index
    
    current_w = pd.Series(0.0, index=price.columns)
    daily_pnl = []
    w_history = []
    
    rebal_dates = list(signals.index)
    
    for i, d in enumerate(dates):
        if i == 0:
            daily_pnl.append(0.0)
            continue
        
        cost = 0.0
        
        # Rebalance
        if d in rebal_dates:
            sig = signals.loc[d].dropna()
            if len(sig) >= n_long + n_short:
                sig = sig.sort_values(ascending=False)
                long_names = sig.head(n_long).index
                short_names = sig.tail(n_short).index
                
                w_new = pd.Series(0.0, index=price.columns)
                long_w = (gross / 2.0) / n_long
                short_w = -(gross / 2.0) / n_short
                
                w_new.loc[long_names] = long_w
                w_new.loc[short_names] = short_w
                
                if w_history:
                    prev_w = w_history[-1]
                    turnover = (w_new - prev_w).abs().sum() / 2.0
                    cost = turnover * (tc_bps / 10000.0)
                
                current_w = w_new
                w_history.append(current_w.copy())
        
        # Calculate PnL
        r_t = ret.loc[d]
        pnl_t = float((current_w * r_t).sum()) - cost
        daily_pnl.append(pnl_t)
    
    pnl = pd.Series(daily_pnl, index=dates).fillna(0.0)
    
    # Calculate metrics
    ann = TRADING_DAYS
    mu = pnl.mean() * ann
    vol = pnl.std() * np.sqrt(ann)
    sharpe = mu / vol if vol > 0 else 0.0
    
    # MDD
    cum = (1 + pnl).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1.0
    mdd = dd.min()
    
    # Turnover
    if w_history:
        turnovers = []
        for i in range(1, len(w_history)):
            to = (w_history[i] - w_history[i-1]).abs().sum() / 2.0
            turnovers.append(to)
        avg_turnover = np.mean(turnovers) if turnovers else 0.0
    else:
        avg_turnover = 0.0
    
    return {
        "sharpe": float(sharpe),
        "annual_return": float(mu),
        "annual_volatility": float(vol),
        "max_drawdown": float(mdd),
        "avg_turnover": float(avg_turnover),
        "daily_returns": pnl.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in pnl.index]
    }

def main():
    print("="*70)
    print("Factor Engine (Value Only) - Final Version")
    print("="*70)
    
    price = load_price()
    fund = load_fund()
    
    print(f"\nPrice data: {price.shape}")
    print(f"Fundamentals: {fund.shape}")
    
    print("\nBuilding Value-only signals...")
    signals = build_value_signals(price, fund, lag_days=90)
    print(f"  Signals: {signals.shape}")
    print(f"  Rebalance dates: {len(signals)}")
    
    print("\nRunning backtest...")
    res = run_backtest(price, signals)
    
    print("\n" + "="*70)
    print("Results:")
    print("="*70)
    print(f"  Sharpe Ratio: {res['sharpe']:.4f}")
    print(f"  Annual Return: {res['annual_return']:.2%}")
    print(f"  Annual Volatility: {res['annual_volatility']:.2%}")
    print(f"  Max Drawdown: {res['max_drawdown']:.2%}")
    print(f"  Avg Turnover: {res['avg_turnover']:.3f}")
    
    # Save results
    Path("./results").mkdir(exist_ok=True)
    with open("./results/engine_factor_value_only.json", "w") as f:
        json.dump(res, f, indent=2)
    
    print(f"\nResults saved to: ./results/engine_factor_value_only.json")
    print("="*70)

if __name__ == "__main__":
    main()
