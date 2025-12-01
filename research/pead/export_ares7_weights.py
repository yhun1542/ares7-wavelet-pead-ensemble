# research/pead/export_ares7_weights.py

"""
ARES7 Base Weight를 CSV로 Export하는 헬퍼 함수 및 가이드.

사용법:
1. ARES7 백테스트/리밸 모듈에서 일별 weight matrix를 가져옵니다.
2. export_ares7_weights() 함수를 호출하여 CSV로 저장합니다.
3. 생성된 CSV를 ARES8 Overlay 엔진에서 사용합니다.
"""

import pandas as pd
import numpy as np
import os


def export_ares7_weights(
    w: pd.DataFrame,
    output_path: str = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv",
    validate: bool = True,
    save_sample: bool = True,
) -> None:
    """
    ARES7 weight DataFrame을 CSV로 export합니다.
    
    Args:
        w: date x symbol weight DataFrame
           - index: 날짜 (pd.DatetimeIndex)
           - columns: 종목 심볼 (str)
           - values: weight (float, 합계 ≈ 1)
        output_path: 저장할 CSV 경로
        validate: True이면 데이터 검증 수행
        save_sample: True이면 샘플 CSV도 저장
    
    Returns:
        None (CSV 파일 저장)
    
    Example:
        >>> # ARES7 백테스트에서 weight matrix 가져오기
        >>> w = ares7_backtest.get_daily_weights()  # date x symbol DataFrame
        >>> 
        >>> # CSV로 export
        >>> export_ares7_weights(w)
        >>> 
        >>> # ARES8 Overlay에서 사용
        >>> python -m research.pead.run_ares8_overlay_v2 \
        >>>     --base_type ares7 \
        >>>     --budget 0.05 --horizon 10
    """
    print("=== Export ARES7 Base Weights to CSV ===")
    
    # 1. 입력 검증
    if not isinstance(w, pd.DataFrame):
        raise TypeError("w must be a pandas DataFrame")
    
    if not isinstance(w.index, pd.DatetimeIndex):
        print("Warning: index is not DatetimeIndex, converting...")
        w.index = pd.to_datetime(w.index)
    
    print(f"Input shape: {w.shape}")
    print(f"Date range: {w.index.min()} ~ {w.index.max()}")
    print(f"Symbols: {len(w.columns)}")
    
    # 2. 데이터 검증
    if validate:
        print("\nValidating data...")
        
        # 2-1. NaN 체크
        nan_count = w.isna().sum().sum()
        if nan_count > 0:
            print(f"Warning: {nan_count} NaN values found, filling with 0")
            w = w.fillna(0.0)
        
        # 2-2. 음수 weight 체크
        neg_count = (w < 0).sum().sum()
        if neg_count > 0:
            print(f"Warning: {neg_count} negative weights found")
            print("Sample negative weights:")
            for col in w.columns:
                neg_vals = w[col][w[col] < 0]
                if len(neg_vals) > 0:
                    print(f"  {col}: min={neg_vals.min():.4f}, count={len(neg_vals)}")
                    if len(neg_vals) > 5:
                        break
        
        # 2-3. 날짜별 weight 합 체크
        sums = w.sum(axis=1)
        sum_min, sum_max = sums.min(), sums.max()
        sum_mean = sums.mean()
        
        print(f"\nWeight sum per date:")
        print(f"  Min: {sum_min:.6f}")
        print(f"  Max: {sum_max:.6f}")
        print(f"  Mean: {sum_mean:.6f}")
        
        if sum_min < 0.95 or sum_max > 1.05:
            print("Warning: Weight sum deviates significantly from 1.0")
            print("Dates with unusual sums:")
            unusual = sums[(sums < 0.95) | (sums > 1.05)]
            print(unusual.head(10))
        
        # 2-4. 극단적으로 큰 weight 체크
        max_weights = w.max(axis=1)
        extreme_dates = max_weights[max_weights > 0.10]
        if len(extreme_dates) > 0:
            print(f"\nWarning: {len(extreme_dates)} dates have weight > 10%")
            print("Sample dates with extreme weights:")
            print(extreme_dates.head(10))
    
    # 3. Long format으로 변환
    print("\nConverting to long format...")
    w_reset = w.reset_index()
    # index 이름이 'date'가 아닐 수 있으므로 명시적으로 설정
    if w_reset.columns[0] != 'date':
        w_reset = w_reset.rename(columns={w_reset.columns[0]: 'date'})
    w_reset = w_reset.melt(
        id_vars='date',
        var_name='symbol',
        value_name='weight'
    )
    
    # 4. 저장
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    w_reset.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")
    print(f"Total records: {len(w_reset):,}")
    
    # 5. 샘플 CSV 저장 (검증용)
    if save_sample:
        sample_path = output_path.replace(".csv", "_sample.csv")
        
        # 3일치만 샘플로 저장
        sample_dates = w.index[:3]
        w_sample = w.loc[sample_dates]
        w_sample_reset = w_sample.reset_index()
        # index 이름이 'date'가 아닐 수 있으므로 명시적으로 설정
        if w_sample_reset.columns[0] != 'date':
            w_sample_reset = w_sample_reset.rename(columns={w_sample_reset.columns[0]: 'date'})
        w_sample_reset = w_sample_reset.melt(
            id_vars='date',
            var_name='symbol',
            value_name='weight'
        )
        w_sample_reset.to_csv(sample_path, index=False)
        print(f"\nSaved sample to: {sample_path}")
        print("Sample preview:")
        print(w_sample_reset.head(10))
    
    print("\n=== Done ===")


def load_and_validate_ares7_weights(
    path: str = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv",
) -> pd.DataFrame:
    """
    ARES7 base weights CSV를 로딩하고 검증합니다.
    
    Args:
        path: CSV 파일 경로
    
    Returns:
        date x symbol weight DataFrame
    """
    print(f"Loading ARES7 base weights from {path}...")
    
    df = pd.read_csv(path)
    
    # 필수 컬럼 체크
    required_cols = ["date", "symbol", "weight"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Pivot to wide format
    df["date"] = pd.to_datetime(df["date"])
    w = df.pivot(index="date", columns="symbol", values="weight").sort_index()
    w = w.fillna(0.0)
    
    print(f"Loaded shape: {w.shape}")
    print(f"Date range: {w.index.min()} ~ {w.index.max()}")
    print(f"Symbols: {len(w.columns)}")
    
    # 검증
    sums = w.sum(axis=1)
    print(f"Weight sum: min={sums.min():.4f}, max={sums.max():.4f}, mean={sums.mean():.4f}")
    
    return w


# ===== 사용 예시 =====

def example_usage():
    """
    ARES7 weight export 사용 예시.
    """
    # 1. ARES7 백테스트에서 weight matrix 가져오기 (예시)
    # w = ares7_backtest.get_daily_weights()  # date x symbol DataFrame
    
    # 2. 더미 데이터로 테스트
    dates = pd.date_range("2015-01-01", "2025-01-01", freq="D")
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    
    # 랜덤 weight 생성 (합계 = 1)
    np.random.seed(42)
    w_data = np.random.dirichlet(np.ones(len(symbols)), size=len(dates))
    w = pd.DataFrame(w_data, index=dates, columns=symbols)
    
    # 3. CSV로 export
    export_ares7_weights(
        w,
        output_path="/home/ubuntu/ares7-ensemble/data/ares7_base_weights_example.csv",
        validate=True,
        save_sample=True,
    )
    
    # 4. 로딩 및 검증
    w_loaded = load_and_validate_ares7_weights(
        "/home/ubuntu/ares7-ensemble/data/ares7_base_weights_example.csv"
    )
    
    print("\nLoaded weight matrix:")
    print(w_loaded.head())


if __name__ == "__main__":
    example_usage()
