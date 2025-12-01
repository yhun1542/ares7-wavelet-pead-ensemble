# research/pead/create_dummy_ares7_weights.py

"""
더미 ARES7 weight 생성 및 파이프라인 스모크 테스트용 스크립트.
"""

import pandas as pd
import numpy as np
from export_ares7_weights import export_ares7_weights


def create_dummy_ares7_weights():
    """
    더미 ARES7 weight matrix 생성.
    
    Returns:
        date x symbol DataFrame (weight)
    """
    print("=== Creating Dummy ARES7 Weights ===")
    
    # 1. 더미 날짜/심볼 정의 (3개월 영업일)
    dates = pd.date_range("2020-01-01", "2020-03-31", freq="B")
    symbols = ["AAPL", "MSFT", "GOOG", "AMZN", "META"]
    
    print(f"Dates: {len(dates)} business days")
    print(f"Symbols: {symbols}")
    
    # 2. 랜덤 weight 생성 (롱온리 + sum=1)
    rng = np.random.default_rng(42)
    W = rng.random((len(dates), len(symbols)))
    W = W / W.sum(axis=1, keepdims=True)
    
    w_dummy = pd.DataFrame(W, index=dates, columns=symbols)
    
    # 3. 검증
    print(f"\nWeight matrix shape: {w_dummy.shape}")
    print(f"Weight sum per date: min={w_dummy.sum(axis=1).min():.6f}, max={w_dummy.sum(axis=1).max():.6f}")
    print(f"Weight range: min={w_dummy.min().min():.6f}, max={w_dummy.max().max():.6f}")
    
    print("\nSample weights (first 5 dates):")
    print(w_dummy.head())
    
    return w_dummy


if __name__ == "__main__":
    # 1. 더미 weight 생성
    w_dummy = create_dummy_ares7_weights()
    
    # 2. CSV export
    export_ares7_weights(
        w_dummy,
        output_path="/home/ubuntu/ares7-ensemble/data/ares7_base_weights_dummy.csv",
        validate=True,
        save_sample=True,
    )
    
    print("\n=== Dummy ARES7 Weights Created Successfully ===")
