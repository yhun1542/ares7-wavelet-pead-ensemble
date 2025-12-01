
import numpy as np
import pandas as pd
from .stats import summarize_pead_events
from .config import POS_PCT, NEG_PCT

def _bucket_from_rank(r):
    if pd.isna(r):
        return 'neutral'
    if r >= POS_PCT:
        return 'pos_top'
    if r <= NEG_PCT:
        return 'neg_bottom'
    return 'neutral'


def run_label_shuffle(
    events_with_returns: pd.DataFrame,
    horizons=(3, 5, 10),
    n_iter=200,
    rank_col='surprise_rank',
    bucket_col='bucket',
    random_state: int | None = 42,
) -> pd.DataFrame:
    """
    Label Shuffle:
    - 각 event_date 내에서 rank를 랜덤으로 섞고
    - bucket을 새로 매핑
    - 이벤트 통계(summarize_pead_events)를 n_iter번 계산
    - 원본 대비 p-value 계산
    """
    rng = np.random.default_rng(random_state)

    base_summary = summarize_pead_events(events_with_returns, horizons, bucket_col)

    # 구조: dict[(split, bucket, horizon)] -> list[mean_excess_ret]
    shuffled_means = {}

    for i in range(n_iter):
        shuffled = events_with_returns.copy()

        # event_date 그룹별 rank 셔플
        def shuffle_rank(x):
            vals = x[rank_col].values
            rng.shuffle(vals)
            x[rank_col] = vals
            return x

        shuffled = shuffled.groupby('event_date', group_keys=False).apply(shuffle_rank)
        shuffled[bucket_col] = shuffled[rank_col].apply(_bucket_from_rank)

        sum_i = summarize_pead_events(shuffled, horizons, bucket_col)

        for _, row in sum_i.iterrows():
            key = (row['split'], row['bucket'], row['horizon'])
            shuffled_means.setdefault(key, []).append(row['mean_excess_ret'])

    # p-value 계산
    records = []
    for _, row in base_summary.iterrows():
        key = (row['split'], row['bucket'], row['horizon'])
        dist = np.array(shuffled_means.get(key, []))
        if dist.size == 0:
            continue

        obs = row['mean_excess_ret']

        if row['bucket'] == 'pos_top':
            # 양의 알파 기대 → obs가 셔플 분포보다 큰지
            p = (dist >= obs).mean()
        else:
            # 음의 알파 기대 → obs가 셔플 분포보다 작은지
            p = (dist <= obs).mean()

        records.append({
            'split': row['split'],
            'bucket': row['bucket'],
            'horizon': row['horizon'],
            'n_events': row['n_events'],
            'mean_excess_ret': obs,
            'sharpe': row['sharpe'],
            't_stat': row['t_stat'],
            'win_rate': row['win_rate'],
            'p_value': p,
        })

    return pd.DataFrame(records)
