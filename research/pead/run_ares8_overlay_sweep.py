# research/pead/run_ares8_overlay_sweep.py

import itertools
import numpy as np
import pandas as pd

from .config import (
    PRICES_PATHS,
    SPX_CLOSE_PATH,
    REAL_EVAL_SPLIT,
)
from .price_loader import load_price_matrix, load_benchmark
from .event_table_builder_v1 import build_eps_events
from .signal_builder import build_daily_signal
from .overlay_engine import apply_overlay_budget, compute_portfolio_returns
from .run_ares8_overlay import load_base_weights, compute_stats

BASE_WEIGHTS_PATH = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv"
SF1_EPS_PATH = "/home/ubuntu/ares7-ensemble/data/sf1_eps.csv"

OUTPUT_SWEEP = "ares8_overlay_sweep_stats.csv"


def main():
    print("=== ARES8 Overlay Sweep (Budget x Horizon x MinRank) ===")

    # 1) 공통 리소스 로드
    print("Loading prices / base weights / EPS events...")
    px = load_price_matrix(PRICES_PATHS)
    w_base = load_base_weights(BASE_WEIGHTS_PATH)

    events = build_eps_events(
        SF1_EPS_PATH,
        price_index=px.index,
        split_cfg=REAL_EVAL_SPLIT,
    ).rename(columns={"ticker": "symbol"})

    # 공통 유니버스/날짜 align
    common_dates = px.index.intersection(w_base.index)
    common_symbols = sorted(set(px.columns) & set(w_base.columns))

    px = px.reindex(index=common_dates, columns=common_symbols)
    w_base = w_base.reindex(index=common_dates, columns=common_symbols).fillna(0.0)

    # 파라미터 그리드
    budgets = [0.03, 0.05, 0.10, 0.15]
    horizons = [3, 5, 10, 15]
    min_ranks = [0.8, 0.9]  # 상위 20% vs 상위 10%

    results = []

    for budget, horizon, min_rank in itertools.product(budgets, horizons, min_ranks):
        print(f"\n>>> Running combo: budget={budget}, horizon={horizon}, min_rank={min_rank}")

        # 2) 시그널 생성
        signal = build_daily_signal(
            events=events,
            price_index=px.index,
            horizon=horizon,
            bucket_col="bucket",
            rank_col="surprise_rank",
            min_rank=min_rank,
        )
        signal = signal.reindex(index=common_dates, columns=common_symbols).fillna(0.0)

        # 3) Overlay 계산
        w_overlay = apply_overlay_budget(
            w_base=w_base,
            signal=signal,
            budget=budget,
            mode="strength",
            cap_single=0.05,
        )

        # 4) 수익률 계산
        base_ret = compute_portfolio_returns(w_base, px, fee_rate=0.001)
        overlay_ret = compute_portfolio_returns(w_overlay, px, fee_rate=0.001)
        incr_ret = overlay_ret - base_ret

        # 5) 성능 통계
        stats_base = compute_stats(base_ret, "base", REAL_EVAL_SPLIT)
        stats_overlay = compute_stats(overlay_ret, "overlay", REAL_EVAL_SPLIT)
        stats_incr = compute_stats(incr_ret, "incremental", REAL_EVAL_SPLIT)

        # incremental all / split 요약만 뽑아서 기록
        for _, row in stats_incr.iterrows():
            results.append({
                "budget": budget,
                "horizon": horizon,
                "min_rank": min_rank,
                "split": row["split"],
                "n_days": row["n_days"],
                "ann_return_incr": row["ann_return"],
                "ann_vol_incr": row["ann_vol"],
                "sharpe_incr": row["sharpe"],
                "mdd_incr": row["mdd"],
            })

    df_res = pd.DataFrame(results)
    df_res.to_csv(OUTPUT_SWEEP, index=False)
    print(f"\nSaved sweep results to {OUTPUT_SWEEP}")
    print("=== Done ===")


if __name__ == "__main__":
    main()
