#!/usr/bin/env python3
"""
Buyback Event Builder
8-K 공시 데이터를 이벤트 테이블로 변환
"""

import pandas as pd
import numpy as np


def build_buyback_events(
    raw_bb_df: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    split_cfg: dict,
    use_mc_ratio: bool = False,  # 시가총액 데이터가 없으므로 False로 기본값 설정
) -> pd.DataFrame:
    """
    Buyback 이벤트 테이블 생성.

    Parameters
    ----------
    raw_bb_df : DataFrame
        최소 컬럼:
        - ticker        : 티커
        - date          : 공시일 (string/datetime)
        - buyback_amount: 발표된 바이백 금액 (USD)
        옵션:
        - marketcap_usd : 공시 시점 시가총액(있으면 사용)

    price_index : DatetimeIndex
        가격 데이터 날짜 인덱스 (px.index)
    split_cfg : dict
        Train/Val/Test 스플릿 설정
        예: {"train":("2016-01-01","2019-12-31"), ...}
    use_mc_ratio : bool
        True 면 buyback_amount / marketcap_usd 로 signal_raw 생성
        False 면 buyback_amount 자체로 signal_raw (단면 rank만 쓸 때).

    Returns
    -------
    events : DataFrame
        컬럼:
        ['ticker', 'event_date', 'filing_date',
         'amount_usd', 'signal_raw', 'signal_rank',
         'bucket', 'split']
    """
    df = raw_bb_df.copy()

    # 기본 컬럼 체크 및 매핑
    if "date" in df.columns and "filing_date" not in df.columns:
        df["filing_date"] = df["date"]
    if "buyback_amount" in df.columns and "amount_usd" not in df.columns:
        df["amount_usd"] = df["buyback_amount"]

    for col in ["ticker", "filing_date", "amount_usd"]:
        if col not in df.columns:
            raise ValueError(f"raw_bb_df에 '{col}' 컬럼이 필요합니다.")

    df["filing_date"] = pd.to_datetime(df["filing_date"])
    df = df.sort_values(["ticker", "filing_date"])

    # event_date = filing_date 이후 첫 거래일로 스냅
    dates = pd.Series(price_index).sort_values().reset_index(drop=True)

    def snap_to_trading(d):
        idx = dates.searchsorted(d)
        if idx >= len(dates):
            return pd.NaT
        return dates.iloc[idx]

    df["event_date"] = df["filing_date"].apply(snap_to_trading)
    df = df.dropna(subset=["event_date"])

    # signal_raw 정의
    if use_mc_ratio and "marketcap_usd" in df.columns:
        # 시총 대비 바이백 비율 (% of market cap)
        df["signal_raw"] = df["amount_usd"] / (df["marketcap_usd"].replace(0, np.nan))
    else:
        # 금액 자체를 사용 (단면 rank만 쓸 때도 충분히 의미 있음)
        df["signal_raw"] = df["amount_usd"]

    # 음수/0/NaN 정리
    df["signal_raw"] = df["signal_raw"].replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=["signal_raw"])
    df = df[df["signal_raw"] > 0]

    # event_date별 cross-sectional rank
    df["signal_rank"] = (
        df.groupby("event_date")["signal_raw"]
          .rank(method="first", pct=True)
    )

    # bucket: 상위 10%만 bb_top
    def bucketize(r):
        if pd.isna(r):
            return "neutral"
        return "bb_top" if r >= 0.9 else "neutral"

    df["bucket"] = df["signal_rank"].apply(bucketize)

    # split 할당
    def assign_split(d):
        d_str = str(pd.to_datetime(d).date())
        for name, (s, e) in split_cfg.items():
            if s <= d_str <= e:
                return name
        return "out"

    df["split"] = df["event_date"].apply(assign_split)

    events = df[
        [
            "ticker", "event_date", "filing_date",
            "amount_usd", "signal_raw",
            "signal_rank", "bucket", "split",
        ]
    ].copy()

    return events


if __name__ == "__main__":
    # 테스트
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent.parent
    
    # Buyback raw 데이터 로드
    bb_raw = pd.read_csv(project_root / "data" / "buyback" / "buyback_events_v6_test10.csv")
    
    # Prices 로드
    px_long = pd.read_csv(project_root / "data" / "prices.csv")
    px_long['timestamp'] = pd.to_datetime(px_long['timestamp'])
    px = px_long.pivot(index='timestamp', columns='symbol', values='close')
    
    # Split config
    split_cfg = {
        "train": ("2016-01-01", "2019-12-31"),
        "val": ("2020-01-01", "2021-12-31"),
        "test": ("2022-01-01", "2025-12-31"),
    }
    
    # Build events
    events = build_buyback_events(bb_raw, px.index, split_cfg, use_mc_ratio=False)
    
    print(f"Total events: {len(events)}")
    print(f"bb_top events: {(events['bucket'] == 'bb_top').sum()}")
    print(f"\nSplit distribution:")
    print(events['split'].value_counts())
    print(f"\nFirst 5 events:")
    print(events.head())
    
    # 저장
    output_path = project_root / "data" / "buyback_events.csv"
    events.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")
