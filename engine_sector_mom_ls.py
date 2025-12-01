#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_sector_mom_ls.py

S1: Sector Cross-Section Momentum Long/Short Engine

- 섹터 지수/ETF 수익률 기반 크로스섹션 모멘텀 전략
- 최근 60일 모멘텀으로 섹터 랭킹
- 상위 N개 섹터 롱, 하위 N개 섹터 숏 (equal-weight, gross ≈ 2.0)
- 리밸: 20영업일(약 1개월)
- 비용: 0.0005 (수수료+슬리피지 합)

입력:
  --price_csv: 섹터 가격 CSV (symbol, timestamp, close)
  --e1_json  : A+LS Enhanced 결과 JSON
  --c1_json  : C1 Final v5 결과 JSON
  --lv_json  : Low-Vol v2 Final 결과 JSON
  --f_json   : Factor Final 결과 JSON
  --out      : 출력 JSON 경로

출력 JSON 예:
  {
    "sharpe": ...,
    "annual_return": ...,
    "annual_volatility": ...,
    "max_drawdown": ...,
    "avg_turnover": ...,
    "avg_num_longs": ...,
    "avg_num_shorts": ...,
    "corr_with_A": ...,
    "corr_with_C1": ...,
    "corr_with_LV": ...,
    "corr_with_F": ...,
    "config": {...},
    "daily_returns": [
      {"date":"YYYY-MM-DD","ret":float}, ...
    ]
  }
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class SectorMomConfig:
    momentum_lookback: int = 60         # 모멘텀 lookback
    rebalance_freq_days: int = 20       # 리밸 주기 (20 영업일)
    top_k: int = 3                      # 상위/하위 섹터 개수
    gross_target: float = 2.0           # 롱+숏 gross
    cost: float = 0.0005                # 거래비용
    min_days_for_stats: int = 252       # 통계 최소 영업일


def load_sector_price(price_csv: str) -> pd.DataFrame:
    df = pd.read_csv(price_csv)
    if not {"symbol", "timestamp", "close"}.issubset(df.columns):
        raise ValueError("sector_price.csv 에는 symbol, timestamp, close 컬럼이 필요합니다.")
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


def build_sector_mom_weights(
    pivot_ret: pd.DataFrame,
    cfg: SectorMomConfig,
) -> (pd.DataFrame, float, float):
    dates = pivot_ret.index
    symbols = pivot_ret.columns
    n_dates = len(dates)

    weights = pd.DataFrame(0.0, index=dates, columns=symbols)

    # 리밸 날짜: rebalance_freq_days 간격으로 선택
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

    # 모멘텀: 최근 momentum_lookback 일 수익률 합 or 누적
    ret_np = pivot_ret.values

    num_longs_list = []
    num_shorts_list = []

    for i in rebal_idx:
        # lookback window
        if i < cfg.momentum_lookback:
            continue
        date = dates[i]

        window = ret_np[i - cfg.momentum_lookback : i, :]
        # 각 섹터별 모멘텀: 단순 누적 수익률
        # (1+ret) 곱-1 대신, 합으로 approximation
        mom = np.nanmean(window, axis=0) * cfg.momentum_lookback
        mom_series = pd.Series(mom, index=symbols).dropna()

        if mom_series.empty or len(mom_series) < cfg.top_k * 2:
            continue

        # 랭킹
        mom_sorted = mom_series.sort_values(ascending=False)
        longs = mom_sorted.index[: cfg.top_k]
        shorts = mom_sorted.index[-cfg.top_k :]

        num_longs_list.append(len(longs))
        num_shorts_list.append(len(shorts))

        w_date = pd.Series(0.0, index=symbols)

        # 롱/숏 각각 equal weight
        if len(longs) > 0:
            w_long_each = +1.0 / len(longs)
            w_date.loc[longs] = w_long_each
        if len(shorts) > 0:
            w_short_each = -1.0 / len(shorts)
            w_date.loc[shorts] = w_short_each

        # gross 스케일 → target gross
        gross = np.abs(w_date).sum()
        if gross > 1e-8:
            w_date = w_date * (cfg.gross_target / gross)

        weights.loc[date] = w_date

    # 리밸 사이 기간은 직전 weight 유지
    weights = weights.replace(0.0, np.nan)
    weights = weights.ffill().fillna(0.0)

    avg_longs = float(np.nanmean(num_longs_list)) if num_longs_list else 0.0
    avg_shorts = float(np.nanmean(num_shorts_list)) if num_shorts_list else 0.0
    return weights, avg_longs, avg_shorts


def backtest_from_weights(
    pivot_ret: pd.DataFrame,
    weights: pd.DataFrame,
    cfg: SectorMomConfig,
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
    parser.add_argument("--price_csv", default="./data/sector_price.csv")
    parser.add_argument("--e1_json", default="./results/engine_ls_enhanced_results.json")
    parser.add_argument("--c1_json", default="./results/C1_final_v5.json")
    parser.add_argument("--lv_json", default="./results/engine_c_lowvol_v2_final_results.json")
    parser.add_argument("--f_json", default="./results/engine_factor_final_results.json")
    parser.add_argument("--out", default="./results/engine_sector_mom_ls_results.json")
    args = parser.parse_args()

    cfg = SectorMomConfig()

    pivot_ret = load_sector_price(args.price_csv)
    weights, avg_longs, avg_shorts = build_sector_mom_weights(pivot_ret, cfg)
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
                daily_ret.rename("S1"),
                ret_A.rename("A"),
                ret_C1.rename("C1"),
                ret_LV.rename("LV"),
                ret_F.rename("F"),
            ],
            axis=1,
        ).dropna()

        corr_with_A = float(df_corr["S1"].corr(df_corr["A"]))
        corr_with_C1 = float(df_corr["S1"].corr(df_corr["C1"]))
        corr_with_LV = float(df_corr["S1"].corr(df_corr["LV"]))
        corr_with_F = float(df_corr["S1"].corr(df_corr["F"]))
    except Exception:
        corr_with_A = corr_with_C1 = corr_with_LV = corr_with_F = 0.0

    result = {
        **stats,
        "avg_turnover": float(avg_turnover),
        "avg_num_longs": float(avg_longs),
        "avg_num_shorts": float(avg_shorts),
        "corr_with_A": corr_with_A,
        "corr_with_C1": corr_with_C1,
        "corr_with_LV": corr_with_LV,
        "corr_with_F": corr_with_F,
        "config": {
            "momentum_lookback": cfg.momentum_lookback,
            "rebalance_freq_days": cfg.rebalance_freq_days,
            "top_k": cfg.top_k,
            "gross_target": cfg.gross_target,
            "cost": cfg.cost,
        },
        "daily_returns": [
            {
                "date": d.date().isoformat(),
                "ret": float(r),
            }
            for d, r in daily_ret.items()
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[S1 Sector Mom L/S] 결과 저장 → {out_path}")
    print(
        "Sharpe={sh:.3f}, AnnRet={ar:.2%}, AnnVol={av:.2%}, MDD={mdd:.2%}, "
        "AvgTurnover={to:.3f}, AvgLongs={nl:.1f}, AvgShorts={ns:.1f}".format(
            sh=result["sharpe"],
            ar=result["annual_return"],
            av=result["annual_volatility"],
            mdd=result["max_drawdown"],
            to=result["avg_turnover"],
            nl=result["avg_num_longs"],
            ns=result["avg_num_shorts"],
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
