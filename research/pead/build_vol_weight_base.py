#!/usr/bin/env python3
"""
Volatility-Weighted Base Weights 생성 스크립트

- 입력: PRICES_PATHS (config.py) 기반 가격 데이터
- 처리:
    1) 가격 → 일간 수익률
    2) 롤링 변동성(lookback 일수) 계산 (과거 데이터만 사용, PIT-safe)
    3) inverse volatility (1 / vol) → 날짜별 정규화
    4) 초기 구간(vol 부족)은 Equal-Weight 사용
- 출력:
    /home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv

실행 예시:
    cd /home/ubuntu/ares7-ensemble
    python -m research.pead.build_vol_weight_base
"""

import os
import sys
import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.pead.config import PRICES_PATHS
from research.pead.price_loader import load_price_matrix


OUTPUT_PATH = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv"


def build_vol_weight_base(
    price_paths,
    lookback: int = 63,
    min_obs: int = 42,
) -> pd.DataFrame:
    """
    Volatility-Weighted Base Weights 생성.

    Parameters
    ----------
    price_paths : list[str]
        Polygon 스타일 price CSV 경로 리스트 (config.PRICES_PATHS)
    lookback : int
        롤링 변동성 계산 윈도우 (거래일 기준, 기본 63일 ≈ 3개월)
    min_obs : int
        유효한 롤링 윈도우로 인정할 최소 데이터 개수 (lookback보다 조금 작게 허용)

    Returns
    -------
    weights_df : DataFrame
        columns = ['date', 'symbol', 'weight']
    """
    # 1) 가격 로딩: date x symbol matrix (close)
    print("[build_vol_weight_base] Loading price matrix...")
    px = load_price_matrix(price_paths)  # index=date, columns=symbol
    px = px.sort_index()
    
    print(f"  Loaded {len(px)} dates, {len(px.columns)} symbols")
    print(f"  Date range: {px.index.min()} to {px.index.max()}")

    # 2) 일간 수익률 계산
    print("[build_vol_weight_base] Calculating daily returns...")
    ret = px.pct_change()
    # 너무 초기 NaN은 나중에 처리

    # 3) 롤링 변동성 계산 (과거 데이터만)
    print(f"[build_vol_weight_base] Calculating rolling volatility (lookback={lookback})...")
    # rolling(std) 자체가 과거 구간만 사용하므로 PIT-safe
    vol = ret.rolling(window=lookback, min_periods=min_obs).std()

    # 4) inverse volatility → 날짜별 정규화
    # vol == 0 또는 NaN → 나중에 Equal-Weight fallback
    inv_vol = 1.0 / vol
    inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan)

    weights_list = []
    
    print("[build_vol_weight_base] Generating weights...")
    total_dates = len(inv_vol.index)

    for i, dt in enumerate(inv_vol.index):
        if (i + 1) % 500 == 0:
            print(f"  Progress: {i+1}/{total_dates} dates")
            
        row = inv_vol.loc[dt]

        # 유효 값만 선택
        valid = row.dropna()
        if valid.empty:
            # 모든 값이 NaN → 해당 날짜는 skip (또는 나중에 ffill도 가능)
            continue

        # 날짜별 inverse-vol 합
        total_inv = valid.sum()

        if total_inv <= 0:
            # inverse-vol 합이 이상하면 Equal-Weight
            syms = valid.index
            w = np.ones(len(syms)) / len(syms)
            weights = dict(zip(syms, w))
        else:
            w = valid / total_inv
            weights = w.to_dict()

        for symbol, weight in weights.items():
            weights_list.append(
                {
                    "date": dt,
                    "symbol": symbol,
                    "weight": float(weight),
                }
            )

    weights_df = pd.DataFrame(weights_list)
    weights_df["date"] = pd.to_datetime(weights_df["date"])
    weights_df = weights_df.sort_values(["date", "symbol"])

    # 안전용: 날짜별 weight 합이 1이 되도록 한 번 더 normalize
    weights_df["weight"] = weights_df.groupby("date")["weight"].transform(
        lambda x: x / x.sum() if x.sum() != 0 else x
    )

    return weights_df


def main():
    print("=" * 80)
    print("Build Volatility-Weighted Base Weights")
    print("=" * 80)
    print(f"Using PRICES_PATHS: {PRICES_PATHS}")
    print()

    weights_df = build_vol_weight_base(
        PRICES_PATHS,
        lookback=63,
        min_obs=42,
    )

    if weights_df.empty:
        print("[build_vol_weight_base] WARNING: weights_df is empty. Check price data.")
        return

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    weights_df.to_csv(OUTPUT_PATH, index=False)

    print()
    print("=" * 80)
    print("✅ Volatility-Weighted Base Weights Created")
    print("=" * 80)
    print(f"Output file: {OUTPUT_PATH}")
    print(f"Total records: {len(weights_df):,}")
    print(f"Date range: {weights_df['date'].min()} to {weights_df['date'].max()}")
    print(f"Unique tickers: {weights_df['symbol'].nunique()}")
    print()
    
    # Summary statistics
    print("Weight Statistics:")
    print(f"  Mean:   {weights_df['weight'].mean():.4f}")
    print(f"  Median: {weights_df['weight'].median():.4f}")
    print(f"  Min:    {weights_df['weight'].min():.6f}")
    print(f"  Max:    {weights_df['weight'].max():.4f}")
    print()
    
    # Top 5 average weights
    print("Top 5 Average Weights:")
    top_weights = weights_df.groupby('symbol')['weight'].mean().sort_values(ascending=False).head(5)
    for ticker, w in top_weights.items():
        print(f"  {ticker}: {w*100:.2f}%")
    print()
    
    print("Next step:")
    print("  python -m research.pead.run_ares8_overlay --budget 0.03 --horizon 15")
    print()


if __name__ == "__main__":
    main()
