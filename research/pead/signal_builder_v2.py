#!/usr/bin/env python3
"""
Daily Signal Builder v2
이벤트 → 일별 시그널 매트릭스 변환 (PEAD + Buyback)
기존 signal_builder.py 유지하고 확장 버전
"""

import pandas as pd
import numpy as np


def build_daily_signal_generic(
    events: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    horizon: int,
    bucket_col: str,
    rank_col: str,
    target_bucket: str,
    min_rank: float = 0.8,
) -> pd.DataFrame:
    """
    Generic 이벤트 → 일별 시그널 매트릭스 (date x ticker).

    - events: 최소 ['ticker','event_date',bucket_col,rank_col]
    - horizon: event 이후 보유 일수
    - target_bucket: 사용할 이벤트 버킷 이름 (예: 'pos_top', 'bb_top')
    - rank_col: rank 기반 strength (0~1)
    """
    dates = pd.DatetimeIndex(price_index).sort_values()
    events = events.copy()
    events["event_date"] = pd.to_datetime(events["event_date"])

    if "ticker" not in events.columns:
        # symbol → ticker 변환 시도
        if "symbol" in events.columns:
            events = events.rename(columns={"symbol": "ticker"})
        else:
            raise ValueError("events에 'ticker' 또는 'symbol' 컬럼이 필요합니다.")

    tickers = sorted(events["ticker"].unique())
    signal = pd.DataFrame(0.0, index=dates, columns=tickers)

    sub = events[events[bucket_col] == target_bucket].copy()
    if sub.empty:
        return signal

    for _, row in sub.iterrows():
        t0 = pd.to_datetime(row["event_date"])
        # 타임존 제거하여 비교
        t0 = t0.tz_localize(None) if t0.tz is not None else t0
        
        # 가장 가까운 날짜 찾기
        if t0 not in dates:
            # t0 이후 첫 거래일 찾기
            future_dates = dates[dates >= t0]
            if len(future_dates) == 0:
                continue
            t0 = future_dates[0]
        
        try:
            idx = dates.get_loc(t0)
        except KeyError:
            continue

        start = idx + 1  # 이벤트 다음 거래일부터
        end = min(idx + horizon, len(dates) - 1)
        if start > end:
            continue

        active_dates = dates[start:end+1]

        rank = float(row[rank_col])
        # min_rank 이하면 strength 0
        strength = max(0.0, (rank - min_rank) / (1.0 - min_rank)) if rank >= min_rank else 0.0
        if strength <= 0:
            continue

        ticker = row["ticker"]
        if ticker not in signal.columns:
            continue

        signal.loc[active_dates, ticker] += strength

    # 중첩 이벤트 시 1 이상일 수 있음 → 클립
    signal = signal.clip(0.0, 1.0)
    return signal


def build_daily_signal_pead(
    events_pead: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    horizon: int = 30,
    min_rank: float = 0.8,
) -> pd.DataFrame:
    """
    PEAD용 daily signal (pos_top only, Positive Surprise Only 전제).
    """
    events_pead = events_pead.copy()
    
    # date → event_date 변환
    if "date" in events_pead.columns and "event_date" not in events_pead.columns:
        events_pead = events_pead.rename(columns={"date": "event_date"})
    
    # bucket 컬럼이 없으면 surprise_rank로 생성
    if "bucket" not in events_pead.columns:
        events_pead["bucket"] = events_pead["surprise_rank"].apply(
            lambda r: "pos_top" if r >= 0.9 else "neutral"
        )
    
    return build_daily_signal_generic(
        events=events_pead,
        price_index=price_index,
        horizon=horizon,
        bucket_col="bucket",
        rank_col="surprise_rank",
        target_bucket="pos_top",
        min_rank=min_rank,
    )


def build_daily_signal_buyback(
    events_bb: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    horizon: int = 30,
    min_rank: float = 0.8,
) -> pd.DataFrame:
    """
    Buyback용 daily signal (bb_top only).
    """
    return build_daily_signal_generic(
        events=events_bb,
        price_index=price_index,
        horizon=horizon,
        bucket_col="bucket",
        rank_col="signal_rank",
        target_bucket="bb_top",
        min_rank=min_rank,
    )


if __name__ == "__main__":
    # 테스트
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent.parent
    
    # Prices 로드
    px_long = pd.read_csv(project_root / "data" / "prices.csv")
    px_long['timestamp'] = pd.to_datetime(px_long['timestamp'])
    px = px_long.pivot(index='timestamp', columns='symbol', values='close')
    
    # PEAD events 로드
    events_pead = pd.read_csv(project_root / "data" / "pead_event_table_positive.csv", parse_dates=['date'])
    
    # Buyback events 로드
    events_bb = pd.read_csv(project_root / "data" / "buyback_events.csv", parse_dates=['event_date'])
    
    # Build signals
    print("Building PEAD signal...")
    signal_pead = build_daily_signal_pead(events_pead, px.index, horizon=30, min_rank=0.8)
    
    print("Building Buyback signal...")
    signal_bb = build_daily_signal_buyback(events_bb, px.index, horizon=30, min_rank=0.8)
    
    print(f"\nPEAD signal shape: {signal_pead.shape}")
    print(f"PEAD non-zero signals: {(signal_pead > 0).sum().sum()}")
    print(f"PEAD signal range: [{signal_pead.min().min():.4f}, {signal_pead.max().max():.4f}]")
    
    print(f"\nBuyback signal shape: {signal_bb.shape}")
    print(f"Buyback non-zero signals: {(signal_bb > 0).sum().sum()}")
    print(f"Buyback signal range: [{signal_bb.min().min():.4f}, {signal_bb.max().max():.4f}]")
    
    # 저장
    signal_pead.to_csv(project_root / "data" / "signal_pead.csv")
    signal_bb.to_csv(project_root / "data" / "signal_buyback.csv")
    
    print("\nSaved signals to data/")
    print("Done!")
