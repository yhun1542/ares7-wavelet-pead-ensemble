#!/usr/bin/env python3.11
"""
run_buyback_v2_real.py

================================================================================
⚠️  WARNING: RESEARCH & DEVELOPMENT ONLY - DO NOT USE IN PRODUCTION
================================================================================

용도:
  - buyback_events.csv + prices.csv 기반으로
    Buyback 단독 연구(Sharpe, label shuffle 등)를 수행하는 R&D 전용 스크립트.
  - 프로덕션 포트폴리오에는 **절대 연결하지 마세요**.
  - 자동 매매 파이프라인에 **절대 포함하지 마세요**.

제약사항:
  - 이 스크립트는 연구/분석 목적으로만 사용됩니다.
  - Buyback 전략은 통계적 유의성이 없습니다 (Test p-value=1.0).
  - 실전 포트폴리오에는 PEAD Only를 사용하세요.

실행 방법:
  - 수동 실행만 허용: python3.11 run_buyback_v2_real.py
  - cron, Airflow 등 자동화 금지

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
Version: R&D v1.0
================================================================================
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple

# Project root
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from research.pead.forward_return import attach_forward_returns

# ============================================================================
# Configuration
# ============================================================================

# Paths
DATA_DIR = project_root / "data"
BUYBACK_PATH = DATA_DIR / "buyback_events.csv"
PRICES_PATH = DATA_DIR / "prices.csv"

# Output
OUTPUT_DIR = project_root / "buyback_v2_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Split config (aligned with PEAD research)
SPLIT_CONFIG = {
    "train": ("2016-01-01", "2018-12-31"),
    "val": ("2019-01-01", "2021-12-31"),
    "test": ("2022-01-01", "2025-11-18"),
}

# Research parameters
HORIZONS = [10, 20, 30, 40]
N_SHUFFLES = 100

# ============================================================================
# Data Loading
# ============================================================================

def load_prices() -> pd.DataFrame:
    """
    prices.csv
    cols: symbol,timestamp,open,high,low,close,volume,vwap
    -> timestamp를 normalize한 뒤 wide format (date × symbol)으로 변환.
    """
    print("Loading prices...")
    df = pd.read_csv(PRICES_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["timestamp", "symbol"])

    px = df.pivot(index="timestamp", columns="symbol", values="close")
    px.index.name = "date"
    px.columns.name = "symbol"

    # Forward fill missing values
    px = px.ffill()
    
    print(f"  Shape: {px.shape}")
    print(f"  Date range: {px.index.min()} to {px.index.max()}")
    print(f"  Symbols: {len(px.columns)}")
    
    return px


def load_benchmark(px: pd.DataFrame) -> pd.Series:
    """
    간단 equal-weight benchmark.
    TODO: SPY/IVV 등 실제 인덱스 가격이 있으면 그쪽으로 교체.
    """
    print("Creating equal-weight benchmark...")
    bm = px.mean(axis=1)
    bm.name = "benchmark"
    return bm


def load_buyback_events(px: pd.DataFrame) -> pd.DataFrame:
    """
    buyback_events.csv
    cols: event_date,ticker,amount_usd,signal_rank,bucket,split

    - event_date normalize
    - prices 유니버스에 없는 날짜/티커 삭제 (BAC, PFE 등 자동 필터)
    """
    print("Loading buyback events...")
    df = pd.read_csv(BUYBACK_PATH)
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.normalize()

    valid_dates = set(px.index)
    valid_symbols = set(px.columns)

    before_n = len(df)
    df = df[df["event_date"].isin(valid_dates)]
    df = df[df["ticker"].isin(valid_symbols)]
    after_n = len(df)

    print(f"  Raw events: {before_n}")
    print(f"  Filtered events: {after_n} (dropped: {before_n - after_n})")
    print(f"  Tickers: {sorted(df['ticker'].unique())}")
    
    # Rename for consistency
    df = df.rename(columns={"event_date": "date"})
    
    return df


# ============================================================================
# Research Functions
# ============================================================================

def compute_forward_returns(
    events: pd.DataFrame,
    px: pd.DataFrame,
    bm: pd.Series,
    horizons: list
) -> pd.DataFrame:
    """
    Attach forward returns to buyback events.
    """
    print(f"\nComputing forward returns for horizons: {horizons}...")
    
    # Prepare for forward_return module
    events_copy = events.copy()
    
    # Rename date column for forward_return module
    events_copy = events_copy.rename(columns={"date": "event_date"})
    
    # Compute returns
    events_with_ret = attach_forward_returns(
        events=events_copy,
        px=px,
        bm=bm,
        horizons=horizons
    )
    
    print(f"  Events with returns: {len(events_with_ret)}")
    
    return events_with_ret


def summarize_performance(
    events: pd.DataFrame,
    horizons: list
) -> pd.DataFrame:
    """
    Buyback 이벤트 단위 성과 요약 (split / horizon별).
    bucket == 'bb_top' 만 사용.
    """
    print("\nSummarizing performance...")
    
    rows = []
    for split in ["train", "val", "test"]:
        df_split = events[
            (events["split"] == split) &
            (events["bucket"] == "bb_top")
        ]
        
        if df_split.empty:
            print(f"  {split}: no bb_top events")
            continue

        for h in horizons:
            col_er = f"excess_ret_{h}d"
            if col_er not in df_split.columns:
                continue

            x = df_split[col_er].dropna()
            if len(x) < 3:
                continue

            mean = x.mean()
            std = x.std()
            sharpe = mean / (std + 1e-9)
            t_stat = mean / (std / np.sqrt(len(x)) + 1e-9)
            win_rate = (x > 0).mean()

            rows.append({
                "split": split,
                "horizon": h,
                "n_events": len(x),
                "mean_excess_ret": mean,
                "std_excess_ret": std,
                "sharpe": sharpe,
                "t_stat": t_stat,
                "win_rate": win_rate,
            })
            
            print(f"  {split} {h}d: n={len(x)}, sharpe={sharpe:.3f}, t_stat={t_stat:.2f}")

    return pd.DataFrame(rows)


def label_shuffle_test(
    events: pd.DataFrame,
    horizons: list,
    n_shuffles: int = 100
) -> pd.DataFrame:
    """
    Label shuffle validation.
    Randomly permute excess returns within each split and recompute Sharpe.
    """
    print(f"\nRunning label shuffle test (n={n_shuffles})...")
    
    results = []
    
    for split in ["train", "val", "test"]:
        df_split = events[
            (events["split"] == split) &
            (events["bucket"] == "bb_top")
        ]
        
        if df_split.empty:
            continue
        
        for h in horizons:
            col_er = f"excess_ret_{h}d"
            if col_er not in df_split.columns:
                continue
            
            x = df_split[col_er].dropna()
            if len(x) < 3:
                continue
            
            # Real Sharpe
            real_sharpe = x.mean() / (x.std() + 1e-9)
            
            # Shuffle
            shuffle_sharpes = []
            for _ in range(n_shuffles):
                x_shuffle = x.sample(frac=1.0, replace=False).values
                sharpe_shuffle = x_shuffle.mean() / (x_shuffle.std() + 1e-9)
                shuffle_sharpes.append(sharpe_shuffle)
            
            shuffle_sharpes = np.array(shuffle_sharpes)
            
            # P-value (two-tailed)
            p_value = (np.abs(shuffle_sharpes) >= np.abs(real_sharpe)).mean()
            
            results.append({
                "split": split,
                "horizon": h,
                "n_events": len(x),
                "real_sharpe": real_sharpe,
                "shuffle_mean": shuffle_sharpes.mean(),
                "shuffle_std": shuffle_sharpes.std(),
                "p_value": p_value,
            })
            
            print(f"  {split} {h}d: real_sharpe={real_sharpe:.3f}, p_value={p_value:.3f}")
    
    return pd.DataFrame(results)


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 80)
    print("⚠️  BUYBACK v2 RESEARCH - R&D ONLY")
    print("=" * 80)
    print("WARNING: This script is for RESEARCH purposes only.")
    print("DO NOT connect to production portfolio or automated trading pipeline.")
    print("Buyback strategy has NO statistical significance (Test p-value=1.0).")
    print("For production deployment, use PEAD Only strategy.")
    print("=" * 80)
    
    # 1) Load data
    px = load_prices()
    bm = load_benchmark(px)
    events = load_buyback_events(px)
    
    # 2) Compute forward returns
    events_with_ret = compute_forward_returns(
        events=events,
        px=px,
        bm=bm,
        horizons=HORIZONS
    )
    
    # 3) Summarize performance
    summary = summarize_performance(
        events=events_with_ret,
        horizons=HORIZONS
    )
    
    # 4) Label shuffle test
    shuffle_results = label_shuffle_test(
        events=events_with_ret,
        horizons=HORIZONS,
        n_shuffles=N_SHUFFLES
    )
    
    # 5) Display results
    print("\n" + "=" * 80)
    print("BUYBACK v2 SUMMARY")
    print("=" * 80)
    if not summary.empty:
        print(summary.to_string(index=False))
    else:
        print("(No results)")
    
    print("\n" + "=" * 80)
    print("BUYBACK v2 LABEL SHUFFLE RESULTS")
    print("=" * 80)
    if not shuffle_results.empty:
        print(shuffle_results.to_string(index=False))
    else:
        print("(No results)")
    
    # 6) Save to CSV
    summary_path = OUTPUT_DIR / "summary_v2.csv"
    shuffle_path = OUTPUT_DIR / "shuffle_v2.csv"
    
    summary.to_csv(summary_path, index=False)
    shuffle_results.to_csv(shuffle_path, index=False)
    
    print(f"\n[INFO] Results saved to:")
    print(f"  - {summary_path}")
    print(f"  - {shuffle_path}")
    
    print("\n" + "=" * 80)
    print("BUYBACK v2 RESEARCH COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
