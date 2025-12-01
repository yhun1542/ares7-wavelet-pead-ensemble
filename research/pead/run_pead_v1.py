# research/pead/run_pead_v1.py

from .config import (
    PRICES_PATHS,
    SPX_CLOSE_PATH,
    REAL_EVAL_SPLIT,
)

from .price_loader import load_price_matrix, load_benchmark
from .event_table_builder_v1 import build_eps_events
from .forward_return import attach_forward_returns
from .stats import summarize_pead_events
from .portfolio import build_event_portfolios, summarize_portfolio_returns
from .label_shuffle import run_label_shuffle


SF1_EPS_PATH = "/home/ubuntu/ares7-ensemble/data/sf1_eps.csv"


def main():
    print("=== ARES8 v1: EPS Surprise PEAD Analysis ===")

    # 1) 가격/벤치마크
    print("Loading prices...")
    px = load_price_matrix(PRICES_PATHS)
    bm = load_benchmark(SPX_CLOSE_PATH)

    # 2) EPS 이벤트 테이블 생성
    print("Building EPS-based event table...")
    events = build_eps_events(
        SF1_EPS_PATH,
        price_index=px.index,
        split_cfg=REAL_EVAL_SPLIT,
    )
    print(f"Total EPS events: {len(events)}")

    # 3) forward returns
    print("Attaching forward returns...")
    events_ret = attach_forward_returns(events, px, bm, horizons=(3,5,10))

    # 4) Event-level stats
    print("Event-level PEAD stats:")
    summary_events = summarize_pead_events(events_ret, horizons=(3,5,10))
    print(summary_events)
    summary_events.to_csv("pead_v1_event_stats.csv", index=False)

    # 5) Label Shuffle
    print("Running label shuffle...")
    shuffle_result = run_label_shuffle(events_ret, horizons=(3,5,10), n_iter=200)
    print(shuffle_result)
    shuffle_result.to_csv("pead_v1_label_shuffle.csv", index=False)

    # 6) Event portfolio returns
    print("Building event portfolios...")
    portfolios = build_event_portfolios(events, px, bm, horizons=(3,5,10))
    summary_ports = summarize_portfolio_returns(portfolios)
    print(summary_ports)
    summary_ports.to_csv("pead_v1_portfolio_stats.csv", index=False)

    print("\n=== ARES8 v1 EPS Surprise PEAD Completed ===")


if __name__ == "__main__":
    main()
