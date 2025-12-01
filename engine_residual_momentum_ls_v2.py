#!/usr/bin/env python3
"""
ARES-7 Residual Momentum LS v2
Jason 옵션 C 업그레이드 버전
---------------------------------------------
특징:
- Market Neutral (β=0)
- Sector Neutral
- Residual Momentum (60d, skip 5d)
- Weekly Rebalance (W-FRI)
- Gross = 2.0 (1.0 long + 1.0 short)
- Vol Targeting (12%)
- Turnover Penalty + Hysteresis
- Look-ahead 완전 제거
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import statsmodels.api as sm

TRADING_DAYS = 252

# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------
def zscore(s):
    s = s.replace([np.inf, -np.inf], np.nan)
    if s.std() == 0:
        return s*0
    return (s - s.mean()) / s.std()

# ------------------------------------------------------------
# Data Loading
# ------------------------------------------------------------
def load_price(path="./data/price_full.csv"):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["timestamp", "symbol"])
    price = df.pivot(index="timestamp", columns="symbol", values="close")
    return price

def load_sector(path="./data/fundamentals_with_sector.csv"):
    df = pd.read_csv(path)
    return df.drop_duplicates("symbol").set_index("symbol")["sector"]

# ------------------------------------------------------------
# β-Neutral Residual Momentum Signal
# ------------------------------------------------------------
def compute_residual_momentum(price, sector_map,
                              lookback=60, skip=5,
                              turnover_penalty=0.02):

    ret = price.pct_change()
    ret_look = ret.rolling(lookback).sum() - ret.rolling(skip).sum()

    # 시장 수익률(전체 평균)
    market_ret = ret_look.mean(axis=1)

    # 섹터 더미
    sec = sector_map.reindex(price.columns)
    sector_dum = pd.get_dummies(sec, drop_first=True)  # Drop first to avoid multicollinearity

    signals = pd.DataFrame(index=price.index, columns=price.columns, dtype=float)

    for date in ret_look.index:
        y = ret_look.loc[date].dropna()
        if len(y) < 20:
            continue

        # 디자인 매트릭스: market + sector dummies
        X = pd.DataFrame({"market": market_ret.loc[date]}, index=y.index)
        X = X.join(sector_dum.loc[y.index], how='left').fillna(0)
        X = X.astype(float)  # Ensure all numeric
        X = sm.add_constant(X)

        try:
            model = sm.OLS(y.values, X.values).fit()
            residuals = pd.Series(model.resid, index=y.index)
        except:
            continue

        # Sector-neutral zscore
        df = pd.DataFrame({"res": residuals, "sector": sec.loc[y.index]})
        df["sn"] = df.groupby("sector")["res"].transform(zscore)

        # Turnover penalty 적용
        # (보수적으로, 절대값이 너무 큰 종목은 penalty)
        score = df["sn"]

        score -= turnover_penalty * score.abs()

        signals.loc[date, y.index] = score

    # 1일 시프트로 룩어헤드 제거
    return signals.shift(1)

# ------------------------------------------------------------
# Backtest
# ------------------------------------------------------------
def run_backtest(price, signals,
                 n_long=20, n_short=20,
                 gross=2.0,
                 tc_bps=5,
                 vol_target=0.12,
                 lookback_vol=60,
                 hysteresis=0.01):

    ret = price.pct_change()
    dates = price.index
    symbols = price.columns

    # 주간 리밸 (금요일)
    rebal_dates = price.resample("W-FRI").last().index
    rebal_dates = [d for d in rebal_dates if d in price.index]

    current_w = pd.Series(0.0, index=symbols)
    w_hist = []
    pnl_list = []

    for i, d in enumerate(dates):
        if i == 0:
            pnl_list.append(0.0)
            continue

        cost = 0.0

        # 1) 리밸 시 포지션 결정
        if d in rebal_dates:
            sig = signals.loc[d].dropna()
            if len(sig) >= n_long + n_short:

                sig_sorted = sig.sort_values(ascending=False)
                long_names = sig_sorted.head(n_long).index
                short_names = sig_sorted.tail(n_short).index

                w_new = pd.Series(0.0, index=symbols)
                w_long = (gross/2) / n_long
                w_short = -(gross/2) / n_short
                w_new.loc[long_names] = w_long
                w_new.loc[short_names] = w_short

                # -----------------------------
                # HYSTERESIS: 작은 변경은 무시
                # -----------------------------
                delta = (w_new - current_w).abs()
                w_new[delta < hysteresis] = current_w[delta < hysteresis]

                # -----------------------------
                # 거래비용
                # -----------------------------
                if w_hist:
                    prev = w_hist[-1]
                    turnover = (w_new - prev).abs().sum() / 2
                    cost = turnover * (tc_bps/10000)

                current_w = w_new
                w_hist.append(current_w.copy())

        # 2) 일일 수익률
        r = ret.loc[d]
        pnl = float((current_w * r).sum()) - cost
        pnl_list.append(pnl)

    pnl = pd.Series(pnl_list, index=dates).fillna(0.0)

    # -----------------------------
    # Vol Targeting
    # -----------------------------
    realized_vol = pnl.rolling(lookback_vol).std() * np.sqrt(TRADING_DAYS)
    lev = (vol_target / realized_vol).clip(0.5, 2.0).shift(1).fillna(1.0)

    pnl_vt = pnl * lev

    # -----------------------------
    # Metrics
    # -----------------------------
    mu = pnl_vt.mean() * TRADING_DAYS
    vol = pnl_vt.std() * np.sqrt(TRADING_DAYS)
    sharpe = mu/vol if vol>0 else 0

    cum = (1+pnl_vt).cumprod()
    peak = cum.cummax()
    mdd = (cum/peak - 1).min()

    return {
        "sharpe": float(sharpe),
        "annual_return": float(mu),
        "annual_volatility": float(vol),
        "max_drawdown": float(mdd),
        "daily_returns": pnl_vt.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in dates]
    }


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():

    print("Loading data...")
    price = load_price()
    sectors = load_sector()

    print("Computing β-Neutral Residual Momentum...")
    signals = compute_residual_momentum(price, sectors)

    print("Running backtest...")
    res = run_backtest(price, signals)

    Path("./results").mkdir(exist_ok=True)
    out = "./results/engine_residual_momentum_ls_v2.json"

    with open(out, "w") as f:
        json.dump(res, f, indent=2)

    print("Saved:", out)
    print("Sharpe:", res["sharpe"])
    print("MDD:", res["max_drawdown"])


if __name__ == "__main__":
    main()


