
import pandas as pd
import numpy as np
from .config import POS_PCT, NEG_PCT

def build_fundamental_events(
    fundamentals_path: str,
    price_index: pd.DatetimeIndex,
    split_cfg: dict,
):
    """
    fundamentals.csv 로부터 이벤트(재무 공시) 테이블 생성.

    - 이벤트: (symbol, report_date)
    - 서프라이즈: ΔROE, Δgross_margin, Δdebt_to_equity 기반 멀티팩터 score
    - bucket_B: pos_top / neg_bottom / neutral
    - split: train / val / test / out
    """
    df = pd.read_csv(fundamentals_path)

    # 1) 타입 정리
    df['report_date'] = pd.to_datetime(df['report_date'])
    df = df.sort_values(['symbol', 'report_date'])

    # 2) Δ 계산 (종목별)
    grp = df.groupby('symbol')
    df['d_ROE'] = grp['ROE'].diff()
    df['d_gm'] = grp['gross_margin'].diff()
    df['d_de'] = grp['debt_to_equity'].diff()

    # 3) Surprise Score 정의
    # Approach A: ΔROE 단독
    df['surprise_A'] = df['d_ROE']

    # Approach B: 멀티팩터 z-score 합
    for col in ['d_ROE', 'd_gm', 'd_de']:
        mu = df[col].mean()
        sigma = df[col].std()
        df[f'z_{col}'] = (df[col] - mu) / (sigma + 1e-9)

    df['surprise_B'] = df['z_d_ROE'] + df['z_d_gm'] - df['z_d_de']

    # 4) event_date = report_date를 이후 첫 거래일로 스냅
    price_dates = pd.Series(price_index).sort_values().reset_index(drop=True)

    def snap_to_trading_day(d):
        idx = price_dates.searchsorted(d)
        if idx >= len(price_dates):
            return pd.NaT
        return price_dates.iloc[idx]

    df['event_date'] = df['report_date'].apply(snap_to_trading_day)
    df = df.dropna(subset=['event_date'])

    # 5) 단면 rank (surprise_B 기준)
    df['cs_rank_B'] = (
        df.groupby('event_date')['surprise_B']
          .rank(method='first', pct=True)
    )

    def bucket_from_rank(r):
        if pd.isna(r):
            return 'neutral'
        if r >= POS_PCT:
            return 'pos_top'
        if r <= NEG_PCT:
            return 'neg_bottom'
        return 'neutral'

    df['bucket_B'] = df['cs_rank_B'].apply(bucket_from_rank)

    # 6) split 할당
    def assign_split(d):
        d_str = str(pd.to_datetime(d).date())
        for name, (s, e) in split_cfg.items():
            if s <= d_str <= e:
                return name
        return 'out'

    df['split'] = df['event_date'].apply(assign_split)

    events = df[
        [
            'symbol', 'event_date', 'report_date',
            'ROE', 'gross_margin', 'debt_to_equity',
            'd_ROE', 'd_gm', 'd_de',
            'surprise_A', 'surprise_B',
            'cs_rank_B', 'bucket_B', 'split'
        ]
    ].copy()

    return events
