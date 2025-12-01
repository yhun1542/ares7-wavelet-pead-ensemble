
import numpy as np
import pandas as pd

def summarize_pead_events(events_with_returns: pd.DataFrame,
                          horizons=(3, 5, 10),
                          bucket_col='bucket') -> pd.DataFrame:
    """
    이벤트 단위 PEAD 통계 요약.
    - split: train/val/test
    - bucket: pos_top / neg_bottom
    - horizon: 3/5/10
    """
    rows = []
    for split in ['train', 'val', 'test']:
        for bucket in ['pos_top', 'neg_bottom']:
            df = events_with_returns[
                (events_with_returns['split'] == split) &
                (events_with_returns[bucket_col] == bucket)
            ]
            if df.empty:
                continue

            for h in horizons:
                col_er = f'excess_ret_{h}d'
                x = df[col_er].dropna()
                if len(x) < 10:
                    continue

                mean = x.mean()
                std = x.std()
                sharpe = mean / (std + 1e-9)
                t_stat = mean / (std / np.sqrt(len(x)) + 1e-9)

                if bucket == 'pos_top':
                    win_rate = (x > 0).mean()
                else:
                    win_rate = (x < 0).mean()

                rows.append({
                    'split': split,
                    'bucket': bucket,
                    'horizon': h,
                    'n_events': len(x),
                    'mean_excess_ret': mean,
                    'std_excess_ret': std,
                    'sharpe': sharpe,
                    't_stat': t_stat,
                    'win_rate': win_rate,
                })

    return pd.DataFrame(rows)
