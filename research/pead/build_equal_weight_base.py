# research/pead/build_equal_weight_base.py

"""
가격 + EPS 이벤트를 기반으로
Equal-Weight 베이스 포트폴리오를 생성해서

/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv

로 저장하는 스크립트.

이 파일을 만들고 나면:
    python -m research.pead.run_ares8_overlay
로 바로 ARES8 오버레이 백테스트 가능.
"""

import os
import numpy as np
import pandas as pd

from .config import PRICES_PATHS
from .price_loader import load_price_matrix
from .event_table_builder_v1 import build_eps_events

SF1_EPS_PATH = "/home/ubuntu/ares7-ensemble/data/sf1_eps.csv"
OUTPUT_PATH = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv"


def main():
    print("=== Build Equal-Weight Base Weights (Pseudo ARES7) ===")

    # 1) 가격 데이터 로딩
    print("Loading prices...")
    px = load_price_matrix(PRICES_PATHS)  # date x symbol
    px = px.sort_index()
    print(f"Price matrix shape: {px.shape}")

    # 2) EPS 이벤트 로딩 → 유니버스 정제
    print("Loading EPS events...")
    events = build_eps_events(
        SF1_EPS_PATH,
        price_index=px.index,
        split_cfg={},  # split은 여기선 필요 없음
    )
    events = events.rename(columns={"ticker": "symbol"})

    symbols_eps = set(events["symbol"].unique())
    symbols_px = set(px.columns)

    # 가격 + EPS 둘 다 있는 종목만 사용
    universe = sorted(symbols_eps & symbols_px)
    print(f"Universe size (px ∩ eps): {len(universe)}")

    if not universe:
        print("No overlap between price symbols and EPS symbols. Check data.")
        return

    px_u = px[universe].copy()

    # 3) Equal-weight weight matrix 생성
    # 각 날짜별로, 유효한 가격이 있는 심볼들에 동일 비중 부여
    print("Building equal-weight weights...")
    w_list = []

    for dt, row in px_u.iterrows():
        # NaN 아닌 심볼만
        valid = row.dropna()
        if valid.empty:
            continue
        n = len(valid)
        w = pd.Series(1.0 / n, index=valid.index)
        w_df = pd.DataFrame({
            "date": [dt] * n,
            "symbol": w.index,
            "weight": w.values,
        })
        w_list.append(w_df)

    if not w_list:
        print("No valid weights generated. Check price data.")
        return

    w_all = pd.concat(w_list, ignore_index=True)
    w_all["date"] = pd.to_datetime(w_all["date"])

    # 4) 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    w_all.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved equal-weight base weights to: {OUTPUT_PATH}")
    print("=== Done ===")


if __name__ == "__main__":
    main()
