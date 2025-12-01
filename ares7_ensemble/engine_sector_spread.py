#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_sector_spread.py

C2: Sector Value Spread Stat-Arb Engine

- 섹터별로 Value Score(PER + PBR) 기준 상위/하위 종목으로 롱/숏 스프레드 구성
- 월 1회 리밸런싱
- 섹터별 dollar-neutral, 전체 gross ≈ 2.0
- 비용: 0.0005 (수수료+슬리피지 합)

입력:
  --price_csv: 가격 데이터 CSV (symbol, timestamp, close, ...)
  --fund_csv : 펀더멘털 CSV (symbol, report_date, sector, PER, PBR, ...)
  --e1_json  : A+LS Enhanced 결과 JSON
  --c1_json  : C1 Final v5 결과 JSON
  --lv_json  : LowVol v2 Final 결과 JSON
  --f_json   : Factor Final 결과 JSON
  --out      : 출력 JSON 경로

출력 JSON 예:
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
class SectorSpreadConfig:
    rebalance_freq_days: int = 20   # 약 월 1회
    top_frac: float = 0.2           # 섹터 내 상위/하위 20%
    min_stocks_per_sector: int = 5
    gross_target: float = 2.0       # 전체 gross (롱+숏)
    cost: float = 0.0005            # 거래 비용 (수수료+슬리피지)
    min_days_for_stats: int = 252   # 통계 계산 최소 거래일 수


def load_price_data(price_csv: str):
    df = pd.read_csv(price_csv)
    df = df.sort_values(["symbol", "timestamp"]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df["ret"] = df.groupby("symbol")["close"].pct_change()
    pivot_ret = df.pivot(index="timestamp", columns="symbol", values="ret")
    pivot_ret = pivot_ret.sort_index()
    return pivot_ret


def align_fundamentals(price_index: pd.Index, fund_csv: str) -> pd.DataFrame:
    """
    각 symbol의 펀더멘털을 report_date 기준으로 price_index 날짜에 forward-fill.
    반환: DataFrame(symbol, timestamp, sector, PER, PBR)
    """
    fund = pd.read_csv(fund_csv)
    if "report_date" not in fund.columns:
        raise ValueError("fundamentals.csv 에 'report_date' 컬럼이 필요합니다.")

    required_cols = ["symbol", "report_date", "sector", "PER", "PBR"]
    for c in required_cols:
        if c not in fund.columns:
            raise ValueError(f"fundamentals.csv 에 '{c}' 컬럼이 필요합니다.")

    fund["report_date"] = pd.to_datetime(fund["report_date"]).dt.normalize()
    fund = fund.sort_values(["symbol", "report_date"]).reset_index(drop=True)

    # 각 symbol별로 처리
    result_list = []
    for symbol in fund["symbol"].unique():
        symbol_fund = fund[fund["symbol"] == symbol].copy()
        # 중복 report_date 제거 (최신 데이터 유지)
        symbol_fund = symbol_fund.drop_duplicates(subset=["report_date"], keep="last")
        symbol_fund = symbol_fund.sort_values("report_date").set_index("report_date")
        
        # Forward fill to price dates
        symbol_aligned = symbol_fund[["sector", "PER", "PBR"]].reindex(
            price_index, method="ffill"
        )
        symbol_aligned["symbol"] = symbol
        symbol_aligned["timestamp"] = price_index
        
        result_list.append(symbol_aligned)
    
    aligned = pd.concat(result_list, ignore_index=True)
    aligned = aligned[["symbol", "timestamp", "sector", "PER", "PBR"]].copy()
    return aligned


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


def build_sector_spread_weights(
    pivot_ret: pd.DataFrame,
    aligned_fund: pd.DataFrame,
    cfg: SectorSpreadConfig,
) -> pd.DataFrame:
    dates = pivot_ret.index
    symbols = pivot_ret.columns
    weights = pd.DataFrame(0.0, index=dates, columns=symbols)

    # 리밸 날짜: 달이 바뀌는 첫 영업일 기준 + rebalance_freq_days 보정
    # 단순하게: 인덱스에서 월변경된 날짜들만 리밸로 사용
    months = dates.to_series().dt.to_period("M")
    rebal_dates = dates[(months != months.shift(1))]

    # rebalance_freq_days 적용 (예: 20일 간격)
    if cfg.rebalance_freq_days is not None and cfg.rebalance_freq_days > 1:
        rebal_idx = []
        last_idx = 0
        for d in dates:
            if len(rebal_idx) == 0:
                rebal_idx.append(d)
                last_idx = 0
            else:
                if (len(rebal_idx) == 1 and d in rebal_dates) or (last_idx >= cfg.rebalance_freq_days):
                    rebal_idx.append(d)
                    last_idx = 0
                else:
                    last_idx += 1
        rebal_dates = pd.Index(rebal_idx)

    # aligned_fund: symbol, timestamp, sector, PER, PBR
    aligned_fund = aligned_fund.set_index(["timestamp", "symbol"]).sort_index()

    for date in rebal_dates:
        if date not in dates:
            continue

        try:
            cs = aligned_fund.loc[date].reset_index()
        except KeyError:
            # 해당 날짜에 펀더멘털 없음
            continue

        cs = cs.dropna(subset=["PER", "PBR", "sector"])
        if cs.empty:
            continue

        # ValueScore: 섹터 내에서 PER,PBR 낮을수록 좋은 점수
        weights_date = pd.Series(0.0, index=symbols)
        sectors = cs["sector"].value_counts()
        active_sectors = [sec for sec, cnt in sectors.items() if cnt >= cfg.min_stocks_per_sector]
        if not active_sectors:
            continue

        n_sectors = len(active_sectors)
        sector_gross = cfg.gross_target / n_sectors  # 섹터당 gross (롱+숏)

        for sec in active_sectors:
            sub = cs[cs["sector"] == sec].copy()
            n = len(sub)
            if n < cfg.min_stocks_per_sector:
                continue

            # 섹터 내 rank
            # 낮은 PER/PBR -> 높은 score
            sub["rank_per"] = sub["PER"].rank(pct=True, ascending=True)
            sub["rank_pbr"] = sub["PBR"].rank(pct=True, ascending=True)
            sub["value_score"] = (1 - sub["rank_per"] + 1 - sub["rank_pbr"]) / 2

            sub = sub.sort_values("value_score", ascending=False).reset_index(drop=True)
            k = max(int(n * cfg.top_frac), 1)
            longs = sub.iloc[:k]
            shorts = sub.iloc[-k:]

            if longs.empty or shorts.empty:
                continue

            w_long_total = sector_gross / 2.0
            w_short_total = -sector_gross / 2.0

            w_long_each = w_long_total / len(longs)
            w_short_each = w_short_total / len(shorts)

            weights_date.loc[longs["symbol"]] += w_long_each
            weights_date.loc[shorts["symbol"]] += w_short_each

        # 날짜별 weight 설정
        weights.loc[date] = weights_date

    # 리밸 사이 구간은 직전 weight 유지 (forward-fill)
    weights = weights.replace(0.0, np.nan)
    weights = weights.ffill().fillna(0.0)
    return weights


def backtest_from_weights(
    pivot_ret: pd.DataFrame,
    weights: pd.DataFrame,
    cfg: SectorSpreadConfig,
) -> (pd.Series, float):
    """
    t-1 weight로 t 수익률, 거래비용 포함 백테스트
    """
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
    parser.add_argument("--price_csv", default="./data/price_full.csv")
    parser.add_argument("--fund_csv", default="./data/fundamentals.csv")
    parser.add_argument("--e1_json", default="./results/engine_ls_enhanced_results.json")
    parser.add_argument("--c1_json", default="./results/C1_final_v5.json")
    parser.add_argument("--lv_json", default="./results/engine_c_lowvol_v2_final_results.json")
    parser.add_argument("--f_json", default="./results/engine_factor_final_results.json")
    parser.add_argument("--out", default="./results/engine_sector_spread_results.json")
    args = parser.parse_args()

    cfg = SectorSpreadConfig()

    pivot_ret = load_price_data(args.price_csv)
    aligned_fund = align_fundamentals(pivot_ret.index, args.fund_csv)
    weights = build_sector_spread_weights(pivot_ret, aligned_fund, cfg)
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
                daily_ret.rename("C2"),
                ret_A.rename("A"),
                ret_C1.rename("C1"),
                ret_LV.rename("LV"),
                ret_F.rename("F"),
            ],
            axis=1,
        ).dropna()

        corr_with_A = float(df_corr["C2"].corr(df_corr["A"]))
        corr_with_C1 = float(df_corr["C2"].corr(df_corr["C1"]))
        corr_with_LV = float(df_corr["C2"].corr(df_corr["LV"]))
        corr_with_F = float(df_corr["C2"].corr(df_corr["F"]))
    except Exception:
        corr_with_A = corr_with_C1 = corr_with_LV = corr_with_F = 0.0

    result = {
        **stats,
        "avg_turnover": float(avg_turnover),
        "corr_with_A": corr_with_A,
        "corr_with_C1": corr_with_C1,
        "corr_with_LV": corr_with_LV,
        "corr_with_F": corr_with_F,
        "config": {
            "rebalance_freq_days": cfg.rebalance_freq_days,
            "top_frac": cfg.top_frac,
            "min_stocks_per_sector": cfg.min_stocks_per_sector,
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

    print(f"[C2 Sector Spread] 결과 저장 → {out_path}")
    print(
        "Sharpe={sh:.3f}, AnnRet={ar:.2%}, AnnVol={av:.2%}, MDD={mdd:.2%}, "
        "AvgTurnover={to:.3f}".format(
            sh=result["sharpe"],
            ar=result["annual_return"],
            av=result["annual_volatility"],
            mdd=result["max_drawdown"],
            to=result["avg_turnover"],
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
