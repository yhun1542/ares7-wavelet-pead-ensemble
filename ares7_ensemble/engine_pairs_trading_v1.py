#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_pairs_trading_v1.py

Simple Pairs Trading Engine v1: Market Neutral High Sharpe Candidate

전략 개요:
- 두 종목 (pair1, pair2)의 주가 시계열을 이용해 스프레드를 정의하고,
  스프레드가 평균에서 크게 벗어났을 때(±2σ) 진입, 평균 부근(0)에서 청산하는
  간단한 페어 트레이딩(시장 중립) 전략.

입력:
  --pair1     : 첫 번째 자산 심볼 (예: KO)
  --pair2     : 두 번째 자산 심볼 (예: PEP)
  --data_csv  : 가격 데이터 CSV (symbol,timestamp,close)
  --start_date: 시작 날짜 (YYYY-MM-DD, CSV 내부에서 필터)
  --end_date  : 종료 날짜 (YYYY-MM-DD)
  --out       : 결과 JSON 경로

CSV 기대 형식:
  symbol,timestamp,close
  KO,2015-01-02,41.23
  KO,2015-01-05,41.10
  PEP,2015-01-02,95.34
  ...

출력 JSON (예):
{
  "stats": {
    "sharpe": ...,
    "annual_return": ...,
    "annual_volatility": ...,
    "max_drawdown": ...
  },
  "config": {...},
  "daily_returns": [
    {"date":"YYYY-MM-DD","ret":float}, ...
  ]
}
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def load_prices(
    pair1: str,
    pair2: str,
    data_csv: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """CSV에서 두 종목의 종가 시계열을 로드."""
    df = pd.read_csv(data_csv)
    required = {"symbol", "timestamp", "close"}
    if not required.issubset(df.columns):
        raise ValueError("data_csv 에는 symbol,timestamp,close 컬럼이 필요합니다.")

    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    mask = (df["timestamp"] >= pd.to_datetime(start_date)) & (
        df["timestamp"] <= pd.to_datetime(end_date)
    )
    df = df.loc[mask].copy()
    df = df.sort_values(["symbol", "timestamp"])

    p1 = df[df["symbol"].str.upper() == pair1.upper()].set_index("timestamp")["close"]
    p2 = df[df["symbol"].str.upper() == pair2.upper()].set_index("timestamp")["close"]

    prices = pd.concat([p1.rename(pair1), p2.rename(pair2)], axis=1).dropna()
    if prices.empty:
        raise ValueError("두 종목의 공통 구간 데이터가 없습니다. CSV/기간/심볼을 확인하세요.")
    return prices


def compute_stats(ret: pd.Series) -> dict:
    r = ret.dropna()
    if len(r) == 0:
        return {
            "sharpe": 0.0,
            "annual_return": 0.0,
            "annual_volatility": 0.0,
            "max_drawdown": 0.0,
        }
    ann = 252.0
    mu = r.mean() * ann
    sigma = r.std(ddof=0) * np.sqrt(ann)
    sharpe = mu / sigma if sigma > 1e-8 else 0.0

    cum = (1 + r).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1.0
    mdd = dd.min()

    return {
        "sharpe": float(sharpe),
        "annual_return": float(mu),
        "annual_volatility": float(sigma),
        "max_drawdown": float(mdd),
    }


def pairs_trading(
    prices: pd.DataFrame,
    pair1: str,
    pair2: str,
    entry_z: float = 2.0,
    exit_z: float = 0.0,
    cost: float = 0.0001,  # 0.01% (왕복 0.02% 수준)
) -> (pd.Series, pd.DataFrame):
    """
    간단한 페어 트레이딩 로직.
    - position: +1 (스프레드 롱), -1 (스프레드 숏), 0 (노포지션)
    - 수익률: position_{t-1} * (r1_t - hedge * r2_t) - 거래 비용
    """

    df = prices.copy()
    df["log1"] = np.log(df[pair1])
    df["log2"] = np.log(df[pair2])

    # 1) 헷지 비율 (전체 기간 OLS) – v1에선 단순하게 전체 구간 사용
    X = df["log2"].values.reshape(-1, 1)
    y = df["log1"].values
    reg = LinearRegression().fit(X, y)
    hedge = float(reg.coef_[0])

    # 2) 스프레드 계산
    df["spread"] = df["log1"] - hedge * df["log2"]

    # 3) Z-score: 전체 평균/표준편차 기준 (v1)
    mean_s = df["spread"].mean()
    std_s = df["spread"].std(ddof=0)
    if std_s < 1e-8:
        raise ValueError("스프레드의 변동성이 너무 작습니다. 다른 페어를 사용하세요.")

    df["zscore"] = (df["spread"] - mean_s) / std_s

    # 4) 포지션 생성 (룰 베이스)
    df["position"] = 0.0
    pos = 0.0
    for i in range(1, len(df)):
        z = df["zscore"].iloc[i]
        if pos == 0.0:
            # 진입 조건
            if z > entry_z:
                pos = -1.0  # spread high -> short spread
            elif z < -entry_z:
                pos = 1.0   # spread low -> long spread
        else:
            # 청산 조건
            if pos == 1.0 and z > exit_z:
                pos = 0.0
            elif pos == -1.0 and z < exit_z:
                pos = 0.0
        df.iloc[i, df.columns.get_loc("position")] = pos

    # 5) 수익률 계산
    df[f"{pair1}_ret"] = df[pair1].pct_change().fillna(0.0)
    df[f"{pair2}_ret"] = df[pair2].pct_change().fillna(0.0)

    # t-1 포지션으로 t 수익률
    pos_shift = df["position"].shift(1).fillna(0.0)
    df["gross_ret"] = pos_shift * (df[f"{pair1}_ret"] - hedge * df[f"{pair2}_ret"])

    # 거래 비용: 포지션 변경이 있을 때만 양 다리 모두 거래한다고 가정
    df["trade"] = df["position"].diff().abs().fillna(0.0) > 1e-8
    df["cost"] = df["trade"].astype(float) * cost * 2  # 양쪽 다리

    df["strat_ret"] = df["gross_ret"] - df["cost"]

    return df["strat_ret"], df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair1", default="KO")
    parser.add_argument("--pair2", default="PEP")
    parser.add_argument("--data_csv", default="./data/pairs_price.csv")
    parser.add_argument("--start_date", default="2015-01-01")
    parser.add_argument("--end_date", default="2025-11-25")
    parser.add_argument("--out", default="./results/engine_pairs_trading_v1_results.json")
    args = parser.parse_args()

    prices = load_prices(args.pair1, args.pair2, args.data_csv, args.start_date, args.end_date)
    ret_strat, df_debug = pairs_trading(prices, args.pair1, args.pair2)

    stats = compute_stats(ret_strat)

    result = {
        "stats": stats,
        "config": {
            "pair1": args.pair1,
            "pair2": args.pair2,
            "entry_z": 2.0,
            "exit_z": 0.0,
            "cost": 0.0001,
            "start_date": args.start_date,
            "end_date": args.end_date,
        },
        "daily_returns": [
            {"date": d.date().isoformat(), "ret": float(r)}
            for d, r in ret_strat.items()
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[Pairs Trading v1] 결과 저장 → {out_path}")
    print(
        "Sharpe={sh:.3f}, AnnRet={ar:.2%}, AnnVol={av:.2%}, MDD={mdd:.2%}".format(
            sh=stats["sharpe"],
            ar=stats["annual_return"],
            av=stats["annual_volatility"],
            mdd=stats["max_drawdown"],
        )
    )


if __name__ == "__main__":
    main()
