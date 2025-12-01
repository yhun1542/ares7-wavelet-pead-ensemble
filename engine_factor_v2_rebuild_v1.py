import pandas as pd
import numpy as np
import json
from pathlib import Path

TRADING_DAYS = 252

def zscore(s):
    s = s.replace([np.inf, -np.inf], np.nan)
    m = s.mean()
    v = s.std()
    if v == 0 or np.isnan(v):
        return s * 0.0
    return (s - m) / v

def load_price(path="./data/price_full.csv"):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["timestamp", "symbol"])
    price = df.pivot(index="timestamp", columns="symbol", values="close")
    return price

def load_fund(path="./data/fundamentals_with_sector.csv"):
    df = pd.read_csv(path)
    df["report_date"] = pd.to_datetime(df["report_date"]).dt.normalize()
    return df

def get_pit_fund(fund, as_of, lag_days=90):
    cutoff = as_of - pd.Timedelta(days=lag_days)
    f = fund[fund["report_date"] <= cutoff]
    if f.empty:
        return pd.DataFrame()
    idx = f.groupby("symbol")["report_date"].idxmax()
    return f.loc[idx].set_index("symbol")

def build_factorv2_signals(price, fund, lag_days=90):
    ret = price.pct_change()
    # 모멘텀용 252/21 수익률
    mom_252 = (price / price.shift(252)) - 1
    mom_21  = (price / price.shift(21)) - 1
    mom = mom_252 - mom_21

    vol_126 = ret.rolling(126).std() * np.sqrt(TRADING_DAYS)

    rebal_dates = price.resample("W-FRI").last().index
    rebal_dates = [d for d in rebal_dates if d in price.index]

    scores = {}

    for d in rebal_dates:
        pit = get_pit_fund(fund, d, lag_days=lag_days)
        if pit.empty:
            continue

        common = price.columns.intersection(pit.index)
        if len(common) < 40:
            continue

        # 팩터 계산
        f = pit.loc[common]
        sector = f["sector"]

        pe = f["pe"].replace(0, np.nan)
        pb = f["pb"].replace(0, np.nan)
        roe = f["roe"]

        value = zscore(-pe) + zscore(1.0/pb)
        quality = zscore(roe)

        m = mom.loc[d, common]
        m = zscore(m)

        lv = zscore(-vol_126.loc[d, common])  # 저변동성 선호

        score_raw = (
            0.30 * value +
            0.30 * quality +
            0.25 * m +
            0.15 * lv
        )

        # 섹터 중립: 섹터 내 zscore
        df = pd.DataFrame({"score": score_raw, "sector": sector})
        df = df.dropna(subset=["score"])

        def sector_neutral_z(x):
            return zscore(x)

        df["score_sec_neutral"] = df.groupby("sector")["score"].transform(sector_neutral_z)

        scores[d] = df["score_sec_neutral"]

    # scores dict -> DataFrame (index=dates, columns=symbols)
    all_dates = sorted(scores.keys())
    sig_df = pd.DataFrame(index=all_dates, columns=price.columns, dtype=float)
    for d, s in scores.items():
        sig_df.loc[d, s.index] = s.values

    return sig_df

def run_backtest(price, signals,
                 n_long=20, n_short=20,
                 gross=2.0, tc_bps=5):
    ret = price.pct_change()
    dates = price.index
    weights = pd.DataFrame(0.0, index=dates, columns=price.columns)

    # 리밸 날짜: signals index 사용
    rebal_dates = list(signals.index)

    current_w = pd.Series(0.0, index=price.columns)
    w_history = []
    daily_pnl = []

    for i, d in enumerate(dates):
        if i == 0:
            daily_pnl.append(0.0)
            continue

        cost = 0.0

        # 리밸일이면 포지션 업데이트 (어제까지 정보로 계산된 signals[d]라고 가정)
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

        r_t = ret.loc[d]
        pnl_t = float((current_w * r_t).sum()) - cost
        daily_pnl.append(pnl_t)
        weights.loc[d] = current_w

    pnl = pd.Series(daily_pnl, index=dates).fillna(0.0)

    ann = TRADING_DAYS
    mu = pnl.mean() * ann
    vol = pnl.std() * np.sqrt(ann)
    sharpe = mu / vol if vol > 0 else 0.0

    # MDD
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
    fund = load_fund()
    signals = build_factorv2_signals(price, fund, lag_days=90)
    res = run_backtest(price, signals)

    Path("./results").mkdir(exist_ok=True)
    with open("./results/engine_factor_v2_rebuild_v1.json", "w") as f:
        json.dump(res, f, indent=2)

if __name__ == "__main__":
    main()