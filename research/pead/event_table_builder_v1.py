# research/pead/event_table_builder_v1.py

import pandas as pd
import numpy as np
from .config import POS_PCT, NEG_PCT

def build_eps_events(
    sf1_path: str,
    price_index: pd.DatetimeIndex,
    split_cfg: dict,
):
    """
    SF1 EPS Raw 기반 이벤트 테이블 생성 (ARES8 v1 정식 PEAD)
    - 이벤트: (ticker, datekey) = 실적 발표일
    - EPS Surprise 정의 3종:
        1) surprise_raw: eps_actual - eps_prev
        2) surprise_ma4: eps_actual - eps_MA4
        3) surprise_rank: cross-sectional rank on datekey
    """

    # 1) SF1 로드
    df = pd.read_csv(sf1_path)

    # 필수 컬럼 검증
    required = ['ticker', 'datekey', 'calendardate', 'reportperiod', 'eps']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing SF1 column: {col}")

    # 타입 정리
    df['datekey'] = pd.to_datetime(df['datekey'])
    df['calendardate'] = pd.to_datetime(df['calendardate'])
    df['reportperiod'] = pd.to_datetime(df['reportperiod'])

    df = df.sort_values(['ticker', 'datekey'])

    # 2) EPS 기반 Estimate Proxy 생성
    grp = df.groupby('ticker')

    # 이전 분기 EPS (SUE 레벨1)
    df['eps_prev'] = grp['eps'].shift(1)

    # MA4 EPS (SUE 레벨2)
    df['eps_MA4'] = grp['eps'].rolling(4).mean().reset_index(level=0, drop=True)

    # 3) Surprise 계산
    df['surprise_raw'] = df['eps'] - df['eps_prev']
    df['surprise_ma4'] = df['eps'] - df['eps_MA4']

    # 4) 이벤트 날짜 = datekey → 이후 첫 거래일로 스냅
    price_dates = pd.Series(price_index).sort_values().reset_index(drop=True)

    def snap_day(d):
        idx = price_dates.searchsorted(d)
        if idx >= len(price_dates):
            return pd.NaT
        return price_dates.iloc[idx]

    df['event_date'] = df['datekey'].apply(snap_day)
    df = df.dropna(subset=['event_date'])

    # 5) Cross-sectional rank (surprise_raw 중심)
    df['surprise_rank'] = (
        df.groupby('event_date')['surprise_raw']
          .rank(method='first', pct=True)
    )

    # 6) bucket 정의
    def bucketize(r):
        if pd.isna(r): return 'neutral'
        if r >= POS_PCT: return 'pos_top'
        if r <= NEG_PCT: return 'neg_bottom'
        return 'neutral'

    df['bucket'] = df['surprise_rank'].apply(bucketize)

    # 7) split 할당
    def assign_split(d):
        d = str(pd.to_datetime(d).date())
        for name, (s, e) in split_cfg.items():
            if s <= d <= e:
                return name
        return 'out'

    df['split'] = df['event_date'].apply(assign_split)

    # 8) 필요한 컬럼만 반환
    events = df[
        [
            'ticker', 'event_date', 'datekey', 'reportperiod',
            'eps', 'eps_prev', 'eps_MA4',
            'surprise_raw', 'surprise_ma4',
            'surprise_rank', 'bucket', 'split'
        ]
    ].copy()

    return events
