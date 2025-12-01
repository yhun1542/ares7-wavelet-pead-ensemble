# research/pead/signal_builder.py

import pandas as pd
import numpy as np


def build_daily_signal(
    events: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    horizon: int = 5,
    bucket_col: str = "bucket",
    rank_col: str = "surprise_rank",
    min_rank: float = 0.8,
) -> pd.DataFrame:
    """
    EPS 이벤트 테이블 → 일별 PEAD 시그널 (date x symbol)

    Parameters
    ----------
    events : DataFrame
        build_eps_events 결과 (v1 이벤트), 최소 컬럼:
        - symbol (이 함수 들어오기 전에 ticker → symbol rename)
        - event_date
        - bucket (pos_top / neutral / neg_bottom)
        - surprise_rank (0~1)
    price_index : DatetimeIndex
        가격 데이터의 날짜 인덱스 (px.index)
    horizon : int
        이벤트 이후 시그널 유지 일수 (예: 3 또는 5)
    min_rank : float
        상위 몇 %를 PEAD로 볼지 기준 (0.8 → 상위 20%)

    Returns
    -------
    signal : DataFrame
        index=date, columns=symbol, values in [0, 1]
    """

    dates = pd.DatetimeIndex(price_index).sort_values()
    events = events.copy()
    events["event_date"] = pd.to_datetime(events["event_date"])

    if "symbol" not in events.columns:
        raise ValueError("events에는 'symbol' 컬럼이 필요합니다. (ticker → symbol rename 필요)")

    tickers = sorted(events["symbol"].unique())
    signal = pd.DataFrame(0.0, index=dates, columns=tickers)

    # pos_top 이벤트만 사용
    pos_events = events[events[bucket_col] == "pos_top"].copy()

    for _, row in pos_events.iterrows():
        t0 = pd.to_datetime(row["event_date"])
        if t0 not in dates:
            continue

        try:
            idx = dates.get_loc(t0)
        except KeyError:
            continue

        start = idx + 1  # 이벤트 다음 날부터
        end = min(idx + horizon, len(dates) - 1)
        if start > end:
            continue

        active_dates = dates[start : end + 1]

        rank = float(row[rank_col])
        # 상위 min_rank 이상만 0~1 스케일
        # rank=0.8 → 0, rank=1.0 → 1
        strength = max(0.0, (rank - min_rank) / (1.0 - min_rank))
        if strength <= 0:
            continue

        sym = row["symbol"]
        if sym not in signal.columns:
            continue

        signal.loc[active_dates, sym] += strength

    # 중첩 이벤트로 1 초과할 수 있으니 클립
    signal = signal.clip(0.0, 1.0)

    return signal
