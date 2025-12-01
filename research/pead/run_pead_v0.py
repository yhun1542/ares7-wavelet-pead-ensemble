
import pandas as pd

from .config import (
    FUNDAMENTALS_PATH,
    PRICES_PATHS,
    SPX_CLOSE_PATH,
    REAL_EVAL_SPLIT,
)
from .price_loader import load_price_matrix, load_benchmark
from .event_table_builder_v0 import build_fundamental_events
from .forward_return import attach_forward_returns
from .stats import summarize_pead_events
from .portfolio import build_event_portfolios, summarize_portfolio_returns
from .label_shuffle import run_label_shuffle


def main():
    # 1) 가격/벤치마크 로드
    print("Loading prices / benchmark...")
    px = load_price_matrix(PRICES_PATHS)
    bm = load_benchmark(SPX_CLOSE_PATH)

    # 2) 이벤트 생성
    print("Building fundamental events...")
    events = build_fundamental_events(
        FUNDAMENTALS_PATH,
        price_index=px.index,
        split_cfg=REAL_EVAL_SPLIT,
    )

    print(f"Total events: {len(events)}")

    # 3) forward returns 부착
    print("Attaching forward returns...")
    events_ret = attach_forward_returns(events, px, bm, horizons=(3,5,10))

    # 4) 이벤트 단위 통계
    print("Summarizing event-level PEAD stats...")
    summary_events = summarize_pead_events(events_ret, horizons=(3,5,10))
    print(summary_events)

    # 5) Label Shuffle
    print("Running label shuffle...")
    shuffle_result = run_label_shuffle(events_ret, horizons=(3,5,10), n_iter=200)
    print("\nLabel Shuffle Result:")
    print(shuffle_result)

    # 6) 이벤트 포트폴리오 수익률
    print("Building event portfolios...")
    portfolios = build_event_portfolios(events, px, bm, horizons=(3,5,10))
    summary_ports = summarize_portfolio_returns(portfolios)
    print("\nPortfolio-level PEAD stats:")
    print(summary_ports)

    # 필요하면 CSV로 저장
    summary_events.to_csv("pead_v0_event_stats.csv", index=False)
    shuffle_result.to_csv("pead_v0_label_shuffle.csv", index=False)
    summary_ports.to_csv("pead_v0_portfolio_stats.csv", index=False)

    print("\nDone.")


if __name__ == "__main__":
    main()
