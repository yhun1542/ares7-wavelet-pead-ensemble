#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_defensive_switch_v1.py

Defensive Switch v1: 포트폴리오 레벨 SPY↔TLT 리스크 스위치

- 입력:
  --port_json : 기존 포트폴리오 결과 JSON (daily_returns 포함)
  --spy_tlt_csv : SPY/TLT 가격 CSV (symbol,timestamp,close)
  --out       : 결과 JSON 경로

- 전략:
  1) SPY 200일 MA, 60일 수익률, 포트 MDD 기반 리스크 ON/OFF 구분
  2) 리스크-ON: 기존 포트 100%, TLT 0%
     리스크-OFF: 기존 포트 70%, TLT 30%
  3) t-1의 스위치 상태로 t 수익률 계산 (룩어헤드 방지)
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_portfolio_returns(port_json: str) -> pd.Series:
    with open(port_json, "r") as f:
        d = json.load(f)
    dr = d.get("fixed_v2", d).get("daily_returns", [])
    # 위 줄은 fixed_v2 구조 또는 바로 루트 구조 둘 다 대응하도록 처리
    if not dr:
        dr = d.get("daily_returns", [])
    if not dr:
        return pd.Series(dtype=float, name="PORT")

    s = pd.Series(
        {pd.to_datetime(x["date"]): float(x["ret"]) for x in dr}
    ).sort_index()
    s.name = "PORT"
    return s


def load_spy_tlt(spy_tlt_csv: str) -> (pd.Series, pd.Series):
    df = pd.read_csv(spy_tlt_csv)
    if not {"symbol", "timestamp", "close"}.issubset(df.columns):
        raise ValueError("spy_tlt_price.csv 에는 symbol,timestamp,close 컬럼이 필요합니다.")
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["symbol", "timestamp"])

    spy = df[df["symbol"].str.upper() == "SPY"].set_index("timestamp")["close"].sort_index()
    tlt = df[df["symbol"].str.upper() == "TLT"].set_index("timestamp")["close"].sort_index()

    if spy.empty or tlt.empty:
        raise ValueError("spy_tlt_price.csv 에 SPY와 TLT 데이터가 모두 있어야 합니다.")

    return spy, tlt


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


def defensive_switch(
    port_ret: pd.Series,
    spy_price: pd.Series,
    tlt_price: pd.Series,
    spy_ma_window: int = 200,
    spy_ret_window: int = 60,
    mdd_threshold: float = -0.10,
    spy_ret_threshold: float = -0.05,
    on_leverage: float = 1.0,
    off_leverage: float = 0.7,
    off_bond_weight: float = 0.3,
) -> (pd.Series, pd.DataFrame):
    """
    리스크-ON/OFF 스위치 적용.

    - port_ret: 기존 포트 수익률
    - spy_price / tlt_price: SPY/TLT 종가 시계열
    """

    # 날짜 align
    df = pd.concat(
        [
            port_ret.rename("PORT"),
            spy_price.rename("SPY_PRICE"),
            tlt_price.rename("TLT_PRICE"),
        ],
        axis=1,
    ).dropna()

    # SPY 지표
    df["SPY_RET"] = df["SPY_PRICE"].pct_change()
    df["SPY_MA"] = df["SPY_PRICE"].rolling(spy_ma_window, min_periods=spy_ma_window).mean()
    df["SPY_R60"] = df["SPY_PRICE"] / df["SPY_PRICE"].shift(spy_ret_window) - 1.0

    # 포트 롤링 MDD
    df["PORT_RET"] = df["PORT"]
    equity = (1 + df["PORT_RET"]).cumprod()
    peak = equity.cummax()
    df["DD"] = equity / peak - 1.0

    # 리스크 ON/OFF 조건
    cond_ma = df["SPY_PRICE"] > df["SPY_MA"]
    cond_r60 = df["SPY_R60"] > spy_ret_threshold
    cond_dd = df["DD"] > mdd_threshold

    df["RISK_ON"] = (cond_ma & cond_r60 & cond_dd).astype(int)

    # TLT 수익률
    df["TLT_RET"] = df["TLT_PRICE"].pct_change().fillna(0.0)

    # 포지션 (룩어헤드 방지: t-1 상태로 t 수익률)
    df["L_port_raw"] = np.where(df["RISK_ON"] == 1, on_leverage, off_leverage)
    df["w_bond_raw"] = np.where(df["RISK_ON"] == 1, 0.0, off_bond_weight)

    df["L_port"] = df["L_port_raw"].shift(1).fillna(on_leverage)
    df["w_bond"] = df["w_bond_raw"].shift(1).fillna(0.0)

    # Defensive 수익률
    df["RET_def"] = df["L_port"] * df["PORT_RET"] + df["w_bond"] * df["TLT_RET"]

    return df["RET_def"], df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port_json", default="./results/ensemble_4way_v2_with_vol_summary.json")
    parser.add_argument("--spy_tlt_csv", default="./data/spy_tlt_price.csv")
    parser.add_argument("--out", default="./results/engine_defensive_switch_v1_results.json")
    args = parser.parse_args()

    port_ret = load_portfolio_returns(args.port_json)
    spy_price, tlt_price = load_spy_tlt(args.spy_tlt_csv)

    # 스위치 적용
    ret_def, df_debug = defensive_switch(port_ret, spy_price, tlt_price)

    # 원본 포트와 Defensive 포트 성과 비교
    # align by dates
    df_all = pd.concat(
        [port_ret.rename("PORT"), ret_def.rename("DEF")],
        axis=1,
    ).dropna()

    stats_port = compute_stats(df_all["PORT"])
    stats_def = compute_stats(df_all["DEF"])

    result = {
        "baseline_portfolio": stats_port,
        "defensive_portfolio": stats_def,
        "config": {
            "spy_ma_window": 200,
            "spy_ret_window": 60,
            "mdd_threshold": -0.10,
            "spy_ret_threshold": -0.05,
            "on_leverage": 1.0,
            "off_leverage": 0.7,
            "off_bond_weight": 0.3,
        },
        "daily_returns": [
            {
                "date": d.date().isoformat(),
                "ret_port": float(r["PORT"]),
                "ret_def": float(r["DEF"]),
            }
            for d, r in df_all.iterrows()
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[Defensive Switch v1] 결과 저장 → {out_path}")
    print("Baseline  : Sharpe={sh:.3f}, AnnRet={ar:.2%}, AnnVol={av:.2%}, MDD={mdd:.2%}".format(
        sh=stats_port["sharpe"],
        ar=stats_port["annual_return"],
        av=stats_port["annual_volatility"],
        mdd=stats_port["max_drawdown"],
    ))
    print("Defensive : Sharpe={sh:.3f}, AnnRet={ar:.2%}, AnnVol={av:.2%}, MDD={mdd:.2%}".format(
        sh=stats_def["sharpe"],
        ar=stats_def["annual_return"],
        av=stats_def["annual_volatility"],
        mdd=stats_def["max_drawdown"],
    ))


if __name__ == "__main__":
    main()
