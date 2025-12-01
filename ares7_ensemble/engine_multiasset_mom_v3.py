#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_multiasset_mom_v3.py

M1 v3: US Multi-Asset Momentum with Multi-Horizon & Asset-Class Weights

- 1M/3M/6M/12M 모멘텀 + 절대 모멘텀 필터
- 자산군별 타깃 비중 (EQUITY/BOND/COMMODITY)
- 클래스 내 1/Vol 기반 Risk-Parity
- Long-only, 월간 리밸런싱, 레버리지 ~1.0

입력:
  --price_csv: ./data/multi_price.csv (symbol,timestamp,close)
  --meta_csv : ./data/asset_meta.csv (symbol,asset_class)
  --e1_json  : ./results/engine_ls_enhanced_results.json
  --c1_json  : ./results/C1_final_v5.json
  --lv_json  : ./results/engine_c_lowvol_v2_final_results.json
  --f_json   : ./results/engine_factor_final_results.json
  --out      : ./results/engine_multiasset_mom_v3_results.json
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class M1v3Config:
    lookback_1m: int = 21     # 1M
    lookback_3m: int = 63     # 3M
    lookback_6m: int = 126    # 6M
    lookback_12m: int = 252   # 12M
    vol_lookback: int = 63    # 3M
    rebalance_freq_days: int = 20
    leverage_target: float = 1.0
    cost: float = 0.0003
    class_weights: dict = None  # {"EQUITY":0.2,"BOND":0.5,"COMMODITY":0.3}


def load_multi_price(price_csv: str) -> pd.DataFrame:
    df = pd.read_csv(price_csv)
    if not {"symbol", "timestamp", "close"}.issubset(df.columns):
        raise ValueError("multi_price.csv 에는 symbol,timestamp,close 컬럼이 필요합니다.")
    df = df.sort_values(["symbol", "timestamp"]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df["ret"] = df.groupby("symbol")["close"].pct_change()
    pivot_ret = df.pivot(index="timestamp", columns="symbol", values="ret")
    pivot_ret = pivot_ret.sort_index()
    return pivot_ret


def load_asset_meta(meta_csv: str, symbols: pd.Index) -> pd.Series:
    meta = pd.read_csv(meta_csv)
    if not {"symbol", "asset_class"}.issubset(meta.columns):
        raise ValueError("asset_meta.csv 에는 symbol,asset_class 컬럼이 필요합니다.")
    meta = meta.set_index("symbol")["asset_class"]
    asset_class = meta.reindex(symbols).fillna("OTHER")
    return asset_class


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


def build_m1v3_weights(
    pivot_ret: pd.DataFrame,
    asset_class: pd.Series,
    cfg: M1v3Config,
) -> (pd.DataFrame, float):
    dates = pivot_ret.index
    symbols = pivot_ret.columns
    returns = pivot_ret.values
    n_dates, _ = returns.shape

    weights = pd.DataFrame(0.0, index=dates, columns=symbols)

    # 리밸 날짜: rebalance_freq_days 간격
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

    class_weights = cfg.class_weights or {"EQUITY": 0.2, "BOND": 0.5, "COMMODITY": 0.3}
    cw_base = pd.Series(class_weights, dtype=float)
    cw_base = cw_base / cw_base.sum()  # 안전하게 정규화

    for i in rebal_idx:
        if i < max(cfg.lookback_1m, cfg.lookback_3m, cfg.lookback_6m, cfg.lookback_12m, cfg.vol_lookback):
            continue
        date = dates[i]

        # 모멘텀 윈도우들
        w_1m = returns[i - cfg.lookback_1m : i, :]
        w_3m = returns[i - cfg.lookback_3m : i, :]
        w_6m = returns[i - cfg.lookback_6m : i, :]
        w_12m = returns[i - cfg.lookback_12m : i, :]

        # 각 기간 누적 수익 (합 근사)
        mom_1m = np.nanmean(w_1m, axis=0) * cfg.lookback_1m
        mom_3m = np.nanmean(w_3m, axis=0) * cfg.lookback_3m
        mom_6m = np.nanmean(w_6m, axis=0) * cfg.lookback_6m
        mom_12m = np.nanmean(w_12m, axis=0) * cfg.lookback_12m

        # 멀티-호라이즌 모멘텀 스코어
        mom_score = (
            0.1 * mom_1m
            + 0.2 * mom_3m
            + 0.3 * mom_6m
            + 0.4 * mom_12m
        )

        mom = pd.Series(mom_score, index=symbols).replace([np.inf, -np.inf], np.nan).dropna()
        if mom.empty:
            continue

        # 절대 모멘텀 필터
        mom_pos = mom[mom > 0]
        if mom_pos.empty:
            continue

        # 변동성 (vol_lookback)
        vol_window = returns[i - cfg.vol_lookback : i, :]
        vol = np.nanstd(vol_window, axis=0)
        vol_ser = pd.Series(vol, index=symbols).replace([np.inf, -np.inf], np.nan)

        w_date = pd.Series(0.0, index=symbols)
        cw = cw_base.copy()

        # 클래스별 타깃 비중 처리
        for cls in cw.index:
            cls_syms = symbols[asset_class == cls]
            if len(cls_syms) == 0:
                cw[cls] = 0.0
                continue

            mom_cls = mom_pos.reindex(cls_syms).dropna()
            if mom_cls.empty:
                cw[cls] = 0.0
                continue

            vol_cls = vol_ser.reindex(mom_cls.index)
            mask = vol_cls > 1e-6
            mom_cls = mom_cls[mask]
            vol_cls = vol_cls[mask]

            if mom_cls.empty:
                cw[cls] = 0.0
                continue

            inv_vol = 1.0 / vol_cls
            inv_vol = inv_vol / inv_vol.sum()

            w_cls_total = cw[cls]
            if w_cls_total <= 0:
                continue

            w_date.loc[mom_cls.index] += inv_vol.values * w_cls_total

        # 전체 타깃 비중이 줄었을 수 있으므로 전체 w_date 정규화
        gross = np.abs(w_date).sum()
        if gross > 1e-8:
            w_date = w_date * (cfg.leverage_target / gross)

        weights.loc[date] = w_date

    # 리밸 사이 구간은 직전 weight 유지
    weights = weights.replace(0.0, np.nan)
    weights = weights.ffill().fillna(0.0)

    active_counts = (weights.abs() > 1e-8).sum(axis=1)
    avg_n_assets = float(active_counts.mean())
    return weights, avg_n_assets


def backtest_from_weights(
    pivot_ret: pd.DataFrame,
    weights: pd.DataFrame,
    cfg: M1v3Config,
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
    dr = d.get("daily_returns", [])
    if not dr:
        return pd.Series(dtype=float)
    s = pd.Series(
        {pd.to_datetime(x["date"]): float(x["ret"]) for x in dr}
    ).sort_index()
    return s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--price_csv", default="./data/multi_price.csv")
    parser.add_argument("--meta_csv", default="./data/asset_meta.csv")
    parser.add_argument("--e1_json", default="./results/engine_ls_enhanced_results.json")
    parser.add_argument("--c1_json", default="./results/C1_final_v5.json")
    parser.add_argument("--lv_json", default="./results/engine_c_lowvol_v2_final_results.json")
    parser.add_argument("--f_json", default="./results/engine_factor_final_results.json")
    parser.add_argument("--out", default="./results/engine_multiasset_mom_v3_results.json")
    args = parser.parse_args()

    cfg = M1v3Config(
        class_weights={"EQUITY": 0.2, "BOND": 0.5, "COMMODITY": 0.3},
        leverage_target=1.0,
        cost=0.0003,
    )

    pivot_ret = load_multi_price(args.price_csv)
    asset_class = load_asset_meta(args.meta_csv, pivot_ret.columns)
    weights, avg_n_assets = build_m1v3_weights(pivot_ret, asset_class, cfg)
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
                daily_ret.rename("M1v3"),
                ret_A.rename("A"),
                ret_C1.rename("C1"),
                ret_LV.rename("LV"),
                ret_F.rename("F"),
            ],
            axis=1,
        ).dropna()

        if not df_corr.empty:
            corr_with_A = float(df_corr["M1v3"].corr(df_corr["A"]))
            corr_with_C1 = float(df_corr["M1v3"].corr(df_corr["C1"]))
            corr_with_LV = float(df_corr["M1v3"].corr(df_corr["LV"]))
            corr_with_F = float(df_corr["M1v3"].corr(df_corr["F"]))
        else:
            corr_with_A = corr_with_C1 = corr_with_LV = corr_with_F = 0.0
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
            "lookback_1m": cfg.lookback_1m,
            "lookback_3m": cfg.lookback_3m,
            "lookback_6m": cfg.lookback_6m,
            "lookback_12m": cfg.lookback_12m,
            "vol_lookback": cfg.vol_lookback,
            "rebalance_freq_days": cfg.rebalance_freq_days,
            "leverage_target": cfg.leverage_target,
            "cost": cfg.cost,
            "class_weights": cfg.class_weights,
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

    print(f"[M1 v3 Multi-Asset Mom] 결과 저장 → {out_path}")
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
