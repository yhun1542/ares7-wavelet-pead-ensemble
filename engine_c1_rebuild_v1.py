import pandas as pd
import numpy as np
import json
from pathlib import Path

TRADING_DAYS = 252

def load_price(path="./data/price_full.csv"):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["timestamp", "symbol"])
    price = df.pivot(index="timestamp", columns="symbol", values="close")
    return price

def run_c1_rebuild(price,
                   lookback=5,
                   rebal_days=5,
                   n_long=20,
                   n_short=20,
                   gross=2.0,
                   tc_bps=5):
    ret = price.pct_change()
    dates = price.index
    symbols = price.columns

    # 최근 5일 수익률 (rolling sum)
    r_5d = ret.rolling(lookback).sum()

    current_w = pd.Series(0.0, index=symbols)
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)
    daily_pnl = []
    w_history = []

    rebal_dates = dates[::rebal_days]

    for i, d in enumerate(dates):
        if i == 0:
            daily_pnl.append(0.0)
            continue

        cost = 0.0

        if d in rebal_dates:
            sig = r_5d.loc[d]
            sig = sig.dropna()
            if len(sig) >= n_long + n_short:
                # mean reversion: 최근 많이 오른 종목은 숏, 많이 떨어진 종목은 롱
                sig_sorted = sig.sort_values(ascending=True)
                long_names = sig_sorted.head(n_long).index
                short_names = sig_sorted.tail(n_short).index

                w_new = pd.Series(0.0, index=symbols)
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

        r_t = ret.loc[d]
        pnl_t = float((current_w * r_t).sum()) - cost
        daily_pnl.append(pnl_t)
        weights.loc[d] = current_w

    pnl = pd.Series(daily_pnl, index=dates).fillna(0.0)

    ann = TRADING_DAYS
    mu = pnl.mean() * ann
    vol = pnl.std() * np.sqrt(ann)
    sharpe = mu / vol if vol > 0 else 0.0

    cum = (1 + pnl).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1.0
    mdd = dd.min()

    return {
        "sharpe": float(sharpe),
        "annual_return": float(mu),
        "annual_volatility": float(vol),
        "max_drawdown": float(mdd),
        "daily_returns": pnl.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in pnl.index]
    }

def main():
    price = load_price()
    res = run_c1_rebuild(price)

    Path("./results").mkdir(exist_ok=True)
    with open("./results/C1_rebuild_v1.json", "w") as f:
        json.dump(res, f, indent=2)

if __name__ == "__main__":
    main()