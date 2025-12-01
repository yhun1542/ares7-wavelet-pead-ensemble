#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_vix_convexity_v1.py

V1: US VIX Convexity + Trend Engine

- VIX 현물 + 근월/차월 VIX 선물(F1,F2)을 활용한 테일/볼 엔진.
- 조건:
  1) contango = F2/F1 - 1 < -0.02  (강한 백워데이션)
  2) vix_mom_126 = VIX / VIX.shift(126) - 1 > 0 (6개월 상승 추세)
  3) VIX > 15
- 위 3조건 모두 만족 시 근월물 F1 롱 (레버리지 1.0), 아니면 캐시.

입력:
  --vix_csv: ./data/vix_futures.csv  (date,VIX,F1,F2)
  --e1_json: ./results/engine_ls_enhanced_results.json
  --c1_json: ./results/C1_final_v5.json
  --lv_json: ./results/engine_c_lowvol_v2_final_results.json
  --f_json : ./results/engine_factor_final_results.json
  --out    : ./results/engine_vix_convexity_v1_results.json

출력 JSON:
{
  "sharpe": ...,
  "annual_return": ...,
  "annual_volatility": ...,
  "max_drawdown": ...,
  "avg_leverage": ...,
  "corr_with_A": ...,
  "corr_with_C1": ...,
  "corr_with_LV": ...,
  "corr_with_F": ...,
  "description": "...",
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


def load_vix_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values("date").set_index("date")
    required = {"VIX", "F1", "F2"}
    if not required.issubset(df.columns):
        raise ValueError(f"vix_futures.csv 에 {required} 컬럼이 필요합니다.")
    return df


def compute_stats(ret_series: pd.Series) -> dict:
    ret = ret_series.dropna()
    if len(ret) < 100:
        return {
            "sharpe": 0.0,
            "annual_return": 0.0,
            "annual_volatility": 0.0,
            "max_drawdown": 0.0,
        }
    ann = 252
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


def load_engine_returns(json_path: str) -> pd.Series:
    with open(json_path, "r") as f:
        d = json.load(f)
    dr = d.get("daily_returns", [])
    if not dr:
        return pd.Series(dtype=float)
    s = pd.Series(
        {pd.to_datetime(x["date"]): float(x["ret"]) for x in dr}
    ).sort_index()
    return s


def build_vix_strategy(df: pd.DataFrame, leverage: float = 1.0) -> pd.Series:
    out = df.copy()

    # 근월물 수익률
    out["F1_ret"] = out["F1"].pct_change().fillna(0.0)

    # 컨탱고: F2/F1 - 1  (양수=컨탱고, 음수=백워데이션)
    out["contango"] = out["F2"] / out["F1"] - 1.0

    # VIX 126일 모멘텀
    out["vix_mom_126"] = out["VIX"] / out["VIX"].shift(126) - 1.0

    # 조건 정의
    cond = (
        (out["contango"] < -0.02)    # 강한 백워데이션
        & (out["vix_mom_126"] > 0.0) # 상승 추세
        & (out["VIX"] > 15.0)        # 너무 낮은 Vol 회피
    )

    # raw signal: 1 또는 0
    out["signal_raw"] = np.where(cond, 1.0, 0.0)

    # 노이즈 제거: 5일 이동평균
    out["signal_smooth"] = out["signal_raw"].rolling(5, min_periods=1).mean()

    # 룩어헤드 방지: t-1 시그널로 t 수익률 적용
    out["position"] = out["signal_smooth"].shift(1).fillna(0.0)

    # 전략 수익률
    strat_ret = out["position"] * out["F1_ret"] * leverage
    return strat_ret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vix_csv", default="./data/vix_futures.csv")
    parser.add_argument("--e1_json", default="./results/engine_ls_enhanced_results.json")
    parser.add_argument("--c1_json", default="./results/C1_final_v5.json")
    parser.add_argument("--lv_json", default="./results/engine_c_lowvol_v2_final_results.json")
    parser.add_argument("--f_json", default="./results/engine_factor_final_results.json")
    parser.add_argument("--out", default="./results/engine_vix_convexity_v1_results.json")
    args = parser.parse_args()

    df = load_vix_data(args.vix_csv)

    leverage = 1.0
    daily_ret = build_vix_strategy(df, leverage=leverage)
    stats = compute_stats(daily_ret)

    # 기존 엔진과 상관 계산
    try:
        ret_A = load_engine_returns(args.e1_json)
        ret_C1 = load_engine_returns(args.c1_json)
        ret_LV = load_engine_returns(args.lv_json)
        ret_F = load_engine_returns(args.f_json)

        df_corr = pd.concat(
            [
                daily_ret.rename("V1"),
                ret_A.rename("A"),
                ret_C1.rename("C1"),
                ret_LV.rename("LV"),
                ret_F.rename("F"),
            ],
            axis=1,
        ).dropna()

        if not df_corr.empty:
            corr_with_A = float(df_corr["V1"].corr(df_corr["A"]))
            corr_with_C1 = float(df_corr["V1"].corr(df_corr["C1"]))
            corr_with_LV = float(df_corr["V1"].corr(df_corr["LV"]))
            corr_with_F = float(df_corr["V1"].corr(df_corr["F"]))
        else:
            corr_with_A = corr_with_C1 = corr_with_LV = corr_with_F = 0.0
    except Exception:
        corr_with_A = corr_with_C1 = corr_with_LV = corr_with_F = 0.0

    result = {
        **stats,
        "avg_leverage": leverage,
        "corr_with_A": corr_with_A,
        "corr_with_C1": corr_with_C1,
        "corr_with_LV": corr_with_LV,
        "corr_with_F": corr_with_F,
        "description": "US VIX Convexity + Trend (contango<-2%, vix_mom_126>0, VIX>15 → F1 롱, 레버리지 1.0)",
        "daily_returns": [
            {"date": d.date().isoformat(), "ret": float(r)}
            for d, r in daily_ret.dropna().items()
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("[V1 VIX Convexity + Trend] 결과 저장 →", out_path)
    print(
        "Sharpe={sh:.3f}, AnnRet={ar:.2%}, AnnVol={av:.2%}, MDD={mdd:.2%}, "
        "AvgLev={lev:.2f}, Corr(A)={ca:.3f}, Corr(C1)={cc1:.3f}, Corr(LV)={clv:.3f}, Corr(F)={cf:.3f}".format(
            sh=result["sharpe"],
            ar=result["annual_return"],
            av=result["annual_volatility"],
            mdd=result["max_drawdown"],
            lev=result["avg_leverage"],
            ca=result["corr_with_A"],
            cc1=result["corr_with_C1"],
            clv=result["corr_with_LV"],
            cf=result["corr_with_F"],
        )
    )


if __name__ == "__main__":
    main()
