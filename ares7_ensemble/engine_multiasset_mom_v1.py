#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_multiasset_mom_v1.py

M1: Multi-Asset Time-Series Momentum / Allocation Engine

- 여러 자산(주식 인덱스, 채권, 원자재, FX 등)으로 구성된 유니버스에 대해
  6M/12M 모멘텀 + 절대 모멘텀 필터 + 간단 Risk-Parity 비중으로 포트폴리오 구성.
- Long-only, 월간 리밸런싱, 목표 레버리지 ~1.0

입력:
  --price_csv: multi_price.csv (symbol,timestamp,close)
  --e1_json  : A+LS Enhanced 결과 JSON
  --c1_json  : C1 Final v5 결과 JSON
  --lv_json  : Low-Vol v2 Final 결과 JSON
  --f_json   : Factor Final 결과 JSON
  --out      : 결과 JSON 경로

출력 JSON 구조:
{
  "sharpe": ...,
  "annual_return": ...,
  "annual_volatility": ...,
  "max_drawdown": ...,
  "avg_turnover": ...,
  "corr_with_A": ...,
  "corr_with_C1": ...,
  "corr_with_LV": ...,
  "corr_with_F": ...,
  "config": {...},
  "daily_returns": [ {"date":"YYYY-MM-DD","ret":float}, ... ]
}
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class M1Config:
    lookback_short: int = 126   # 6M
    lookback_long: int = 252    # 12M
    vol_lookback: int = 63      # 3M vol
    rebalance_freq_days: int = 20  # 약 월간 리밸
    leverage_target: float = 1.0   # 총 레버리지
    cost: float = 0.0003           # 거래비용
    min_days_for_stats: int = 252  # 통계 최소 일수


def load_multi_price(price_csv: str) -> pd.DataFrame:
    df = pd.read_csv(price_csv)
    if not {"symbol", "timestamp", "close"}.issubset(df.columns):
        raise ValueError("multi_price.csv 에는 symbol, timestamp, close 컬럼이 필요합니다.")
    df = df.sort_values(["symbol", "timestamp"]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df["ret"] = df.groupby("symbol")["close"].pct_change()
    pivot_ret = df.pivot(index="timestamp", columns="symbol", values="ret")
    pivot_ret = pivot_ret.sort_index()
    return pivot_ret


def compute_stats(ret_series: pd.Series) -> dict:
    ret = ret_series.dropna()
    if len(ret) == 0:
        return {
            "sharpe": 0.0,
            "annual_return": 0.0,
            "annual_volatility": 0.0,
            "max_drawdown": 0.0,
        }
    ann = 252.0
    mu = ret.mean() * ann
    sigma = ret.std(ddof=0) * np.sqrt(ann)
    sharpe = mu / sigma if sigma > 1e-8 else 0.0
    cum = (1 + ret).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1.0
    mdd = dd.min()
    return {
        "sharpe": float(sharpe),
        "annual_return": float(mu),
        "annual_volatility": float(sigma),
        "max_drawdown": float(mdd),
    }


def build_m1_weights(pivot_ret: pd.DataFrame, cfg: M1Config) -> (pd.DataFrame, float):
    dates = pivot_ret.index
    symbols = pivot_ret.columns
    n_dates = len(dates)
    returns = pivot_ret.values

    weights = pd.DataFrame(0.0, index=dates, columns=symbols)

    # 리밸 날짜: rebalance_freq_days 간격으로
    rebal_idx = []
    last_i = 0
    for i, d in enumerate(dates):
        if i == 0:
            rebal_idx.append(i)
            last_i = 0
        else:
            if last_i >= cfg.rebalance_freq_days:
                rebal_idx.append(i)
                last_i = 0
            else:
                last_i += 1

    rebal_idx = np.array(rebal_idx, dtype=int)

    for i in rebal_idx:
        if i < max(cfg.lookback_short, cfg.lookback_long, cfg.vol_lookback):
            continue
        date = dates[i]

        # 모멘텀 구간
        w_short = returns[i - cfg.lookback_short : i, :]
        w_long = returns[i - cfg.lookback_long : i, :]

        # 누적 수익 (합으로 approximation)
        mom_short = np.nanmean(w_short, axis=0) * cfg.lookback_short
        mom_long = np.nanmean(w_long, axis=0) * cfg.lookback_long
        mom_score = 0.5 * mom_short + 0.5 * mom_long

        mom = pd.Series(mom_score, index=symbols).replace([np.inf, -np.inf], np.nan).dropna()
        if mom.empty:
            continue

        # 절대 모멘텀 필터: mom > 0 인 자산만
        mom_pos = mom[mom > 0]
        if mom_pos.empty:
            # 올 캐시
            continue

        # 변동성 (vol_lookback)
        vol_window = returns[i - cfg.vol_lookback : i, :]
        vol = np.nanstd(vol_window, axis=0)
        vol_ser = pd.Series(vol, index=symbols).replace([np.inf, -np.inf], np.nan)

        # 필터된 자산 집합
        universe = mom_pos.index
        vol_sel = vol_ser.loc[universe]
        # vol가 너무 작거나 0이면 제거
        mask = vol_sel > 1e-6
        universe = vol_sel[mask].index

        if len(universe) == 0:
            continue

        mom_sel = mom_pos.loc[universe]
        vol_sel = vol_sel.loc[universe]

        # risk-parity 스타일: 1/vol
        inv_vol = 1.0 / vol_sel
        inv_vol = inv_vol / inv_vol.sum()

        # 모멘텀 강도 반영 (옵션): 여기선 단순 1/vol만 사용 (복잡도 낮추기)
        w_date = pd.Series(0.0, index=symbols)
        w_date.loc[universe] = inv_vol.values

        # leverage_target으로 스케일
        gross = np.abs(w_date).sum()
        if gross > 1e-8:
            w_date = w_date * (cfg.leverage_target / gross)

        weights.loc[date] = w_date

    # 리밸 사이 기간은 직전 weight 유지
    weights = weights.replace(0.0, np.nan)
    weights = weights.ffill().fillna(0.0)

    # 평균 투자종목 수
    active_counts = (weights.abs() > 1e-8).sum(axis=1)
    avg_n_assets = float(active_counts.mean())
    return weights, avg_n_assets


def backtest_from_weights(
    pivot_ret: pd.DataFrame,
    weights: pd.DataFrame,
    cfg: M1Config,
) -> (pd.Series, float):
    dates = pivot_ret.index
    symbols = pivot_ret.columns

    w = weights.reindex(index=dates, columns=symbols).fillna(0.0)
    w_prev = w.shift(1).fillna(0.0)

    daily_gross = (w_prev * pivot_ret).sum(axis=1)
    turnover = (w - w_prev).abs().sum(axis=1)

    cost = turnover * cfg.cost
    daily_ret = daily_gross - cost

    avg_turnover = float(turnover.mean())
    return daily_ret, avg_turnover


def load_engine_returns(json_path: str) -> pd.Series:
    with open(json_path, "r") as f:
        d = json.load(f)
    dr = d["daily_returns"]
    s = pd.Series(
        {pd.to_datetime(x["date"]): float(x["ret"]) for x in dr}
    ).sort_index()
    return s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--price_csv", default="./data/multi_price.csv")
    parser.add_argument("--e1_json", default="./results/engine_ls_enhanced_results.json")
    parser.add_argument("--c1_json", default="./results/C1_final_v5.json")
    parser.add_argument("--lv_json", default="./results/engine_c_lowvol_v2_final_results.json")
    parser.add_argument("--f_json", default="./results/engine_factor_final_results.json")
    parser.add_argument("--out", default="./results/engine_multiasset_mom_v1_results.json")
    args = parser.parse_args()

    cfg = M1Config()

    pivot_ret = load_multi_price(args.price_csv)
    weights, avg_n_assets = build_m1_weights(pivot_ret, cfg)
    daily_ret, avg_turnover = backtest_from_weights(pivot_ret, weights, cfg)
    stats = compute_stats(daily_ret)

    # 기존 엔진과 상관
    try:
        ret_A = load_engine_returns(args.e1_json)
        ret_C1 = load_engine_returns(args.c1_json)
        ret_LV = load_engine_returns(args.lv_json)
        ret_F = load_engine_returns(args.f_json)

        df_corr = pd.concat(
            [
                daily_ret.rename("M1"),
                ret_A.rename("A"),
                ret_C1.rename("C1"),
                ret_LV.rename("LV"),
                ret_F.rename("F"),
            ],
            axis=1,
        ).dropna()

        corr_with_A = float(df_corr["M1"].corr(df_corr["A"]))
        corr_with_C1 = float(df_corr["M1"].corr(df_corr["C1"]))
        corr_with_LV = float(df_corr["M1"].corr(df_corr["LV"]))
        corr_with_F = float(df_corr["M1"].corr(df_corr["F"]))
    except Exception:
        corr_with_A = corr_with_C1 = corr_with_LV = corr_with_F = 0.0

    result = {
        **stats,
        "avg_turnover": float(avg_turnover),
        "avg_num_assets": float(avg_n_assets),
        "corr_with_A": corr_with_A,
        "corr_with_C1": corr_with_C1,
        "corr_with_LV": corr_with_LV,
        "corr_with_F": corr_with_F,
        "config": {
            "lookback_short": cfg.lookback_short,
            "lookback_long": cfg.lookback_long,
            "vol_lookback": cfg.vol_lookback,
            "rebalance_freq_days": cfg.rebalance_freq_days,
            "leverage_target": cfg.leverage_target,
            "cost": cfg.cost,
        },
        "daily_returns": [
            {"date": d.date().isoformat(), "ret": float(r)}
            for d, r in daily_ret.items()
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[M1 Multi-Asset Mom] 결과 저장 → {out_path}")
    print(
        "Sharpe={sh:.3f}, AnnRet={ar:.2%}, AnnVol={av:.2%}, MDD={mdd:.2%}, "
        "AvgTurnover={to:.3f}, AvgAssets={na:.1f}".format(
            sh=result["sharpe"],
            ar=result["annual_return"],
            av=result["annual_volatility"],
            mdd=result["max_drawdown"],
            to=result["avg_turnover"],
            na=result["avg_num_assets"],
        )
    )
    print(
        "Corr(A)={ca:.3f}, Corr(C1)={cc1:.3f}, Corr(LV)={clv:.3f}, Corr(F)={cf:.3f}".format(
            ca=corr_with_A,
            cc1=corr_with_C1,
            clv=corr_with_LV,
            cf=corr_with_F,
        )
    )


if __name__ == "__main__":
    main()
