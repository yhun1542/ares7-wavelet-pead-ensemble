# research/pead/run_ares8_overlay.py

import pandas as pd
import numpy as np

from .config import (
    PRICES_PATHS,
    SPX_CLOSE_PATH,
    REAL_EVAL_SPLIT,
)
from .price_loader import load_price_matrix, load_benchmark
from .event_table_builder_v1 import build_eps_events
from .signal_builder import build_daily_signal
from .overlay_engine import apply_overlay_budget, compute_portfolio_returns

# ARES7 base weight CSV 경로 (Jason이 export 해둘 파일)
BASE_WEIGHTS_PATH = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv"
SF1_EPS_PATH = "/home/ubuntu/ares7-ensemble/data/sf1_eps.csv"

OUTPUT_PREFIX = "ares8_overlay"


def load_base_weights(path: str) -> pd.DataFrame:
    """
    ARES7 base weights CSV 로딩.
    기대 포맷:
        date, symbol, weight
    """
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError("base weights CSV에 'date' 컬럼이 필요합니다.")
    if "symbol" not in df.columns:
        raise ValueError("base weights CSV에 'symbol' 컬럼이 필요합니다.")
    if "weight" not in df.columns:
        raise ValueError("base weights CSV에 'weight' 컬럼이 필요합니다.")

    df["date"] = pd.to_datetime(df["date"])
    w = df.pivot(index="date", columns="symbol", values="weight").sort_index()
    w = w.fillna(0.0)
    # 각 날짜별 정규화 (혹시 합이 1이 아니면)
    ssum = w.sum(axis=1).replace(0, np.nan)
    w = w.div(ssum, axis=0).fillna(0.0)
    return w


def compute_stats(ret: pd.Series, name: str, split_cfg: dict) -> pd.DataFrame:
    """
    Sharpe, 연환산 수익/변동성, MDD를 전체/스플릿별로 계산.
    """
    def _stats(series: pd.Series):
        series = series.dropna()
        if len(series) < 10:
            return {
                "n_days": len(series),
                "ann_return": np.nan,
                "ann_vol": np.nan,
                "sharpe": np.nan,
                "mdd": np.nan,
            }
        mean = series.mean()
        vol = series.std()
        ann_ret = mean * 252
        ann_vol = vol * np.sqrt(252)
        sharpe = (mean / (vol + 1e-9)) * np.sqrt(252)
        # MDD
        curve = (1 + series).cumprod()
        peak = curve.cummax()
        dd = curve / peak - 1
        mdd = dd.min()
        return {
            "n_days": len(series),
            "ann_return": ann_ret,
            "ann_vol": ann_vol,
            "sharpe": sharpe,
            "mdd": mdd,
        }

    rows = []

    # 전체
    s_all = _stats(ret)
    s_all.update({"name": name, "split": "all"})
    rows.append(s_all)

    # split 단위
    for split_name, (start, end) in split_cfg.items():
        mask = (ret.index >= start) & (ret.index <= end)
        s = _stats(ret[mask])
        s.update({"name": name, "split": split_name})
        rows.append(s)

    return pd.DataFrame(rows)


def main(
    horizon: int = 5,
    budget: float = 0.1,
    fee_rate: float = 0.001,
    mode: str = "strength",
):

    print("=== ARES8 v1 Overlay Backtest ===")
    print(f"Horizon={horizon}, Budget={budget}, fee_rate={fee_rate}, mode={mode}")

    # 1) 가격/벤치마크 로드
    print("Loading prices / benchmark...")
    px = load_price_matrix(PRICES_PATHS)  # date x symbol (symbol 컬럼 기준)
    bm = load_benchmark(SPX_CLOSE_PATH)

    # 2) ARES7 base weights 로드
    print("Loading ARES7 base weights...")
    w_base = load_base_weights(BASE_WEIGHTS_PATH)

    # 3) EPS 이벤트 테이블 생성
    print("Building EPS events...")

    # eps 이벤트는 ticker 기준 → symbol로 rename
    events = build_eps_events(
        SF1_EPS_PATH,
        price_index=px.index,
        split_cfg=REAL_EVAL_SPLIT,
    )
    events = events.rename(columns={"ticker": "symbol"})

    print(f"Total EPS events: {len(events)}")

    # 4) 일별 PEAD 시그널 생성
    print("Building daily PEAD signal...")
    signal = build_daily_signal(
        events=events,
        price_index=px.index,
        horizon=horizon,
        bucket_col="bucket",
        rank_col="surprise_rank",
        min_rank=0.8,
    )

    # base / signal 공통 심볼/날짜로 align
    common_dates = px.index.intersection(w_base.index).intersection(signal.index)
    common_symbols = sorted(set(px.columns) & set(w_base.columns) & set(signal.columns))

    px_aligned = px.reindex(index=common_dates, columns=common_symbols)
    w_base_aligned = w_base.reindex(index=common_dates, columns=common_symbols).fillna(0.0)
    signal_aligned = signal.reindex(index=common_dates, columns=common_symbols).fillna(0.0)

    # 5) Overlay weight 계산
    print("Applying overlay budget...")
    w_overlay = apply_overlay_budget(
        w_base=w_base_aligned,
        signal=signal_aligned,
        budget=budget,
        mode=mode,
        cap_single=0.05,
    )

    # 6) 포트폴리오 수익률 계산 (Base / Overlay)
    print("Computing portfolio returns...")
    base_ret = compute_portfolio_returns(w_base_aligned, px_aligned, fee_rate=fee_rate)
    overlay_ret = compute_portfolio_returns(w_overlay, px_aligned, fee_rate=fee_rate)
    incr_ret = overlay_ret - base_ret  # overlay incremental PnL

    base_ret.name = "base"
    overlay_ret.name = "overlay"
    incr_ret.name = "incremental"

    # 7) 성능 통계 요약
    print("Summarizing performance stats...")
    stats_base = compute_stats(base_ret, "base", REAL_EVAL_SPLIT)
    stats_overlay = compute_stats(overlay_ret, "overlay", REAL_EVAL_SPLIT)
    stats_incr = compute_stats(incr_ret, "incremental", REAL_EVAL_SPLIT)

    stats_all = pd.concat([stats_base, stats_overlay, stats_incr], ignore_index=True)

    print(stats_all)

    # 8) 결과 저장
    stats_all.to_csv(f"{OUTPUT_PREFIX}_stats.csv", index=False)
    base_ret.to_csv(f"{OUTPUT_PREFIX}_base_ret.csv", header=True)
    overlay_ret.to_csv(f"{OUTPUT_PREFIX}_overlay_ret.csv", header=True)
    incr_ret.to_csv(f"{OUTPUT_PREFIX}_incremental_ret.csv", header=True)

    print(f"\nSaved overlay results with prefix: {OUTPUT_PREFIX}_*")
    print("=== Done ===")
    
    return stats_all


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ARES8 v1 Overlay Backtest")
    parser.add_argument("--budget", type=float, default=0.1,
                        help="Overlay budget (default: 0.10)")
    parser.add_argument("--horizon", type=int, default=5,
                        help="PEAD holding horizon in days (default: 5)")
    parser.add_argument("--fee", type=float, default=0.001,
                        help="One-way transaction fee rate (default: 0.001)")
    parser.add_argument("--mode", type=str, default="strength",
                        choices=["strength", "equal"],
                        help="Overlay weight mode (strength/equal)")

    args = parser.parse_args()

    main(
        horizon=args.horizon,
        budget=args.budget,
        fee_rate=args.fee,
        mode=args.mode,
    )
