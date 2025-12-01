
import numpy as np
import pandas as pd

def attach_forward_returns(
    events: pd.DataFrame,
    px: pd.DataFrame,
    bm: pd.Series,
    horizons=(3, 5, 10),
) -> pd.DataFrame:
    """
    각 이벤트(event_date, symbol)에 대해
    3/5/10일 누적 수익률 및 벤치마크 초과 수익률을 붙인다.

    px: date x symbol price matrix
    bm: date-index benchmark close series
    """
    events = events.copy()
    px = px.sort_index()
    bm = bm.reindex(px.index).sort_index()

    px_ret = px.pct_change()
    bm_ret = bm.pct_change()
    
    debug_count = 0
    success_count = 0

    for h in horizons:
        col_r = f'ret_{h}d'
        col_er = f'excess_ret_{h}d'

        rets = []
        ex_rets = []

        for idx, row in events.iterrows():
            t = row['event_date']
            symbol = row.get('ticker') or row.get('symbol')
            
            if debug_count < 3:
                print(f"    Debug event {idx}: t={t}, symbol={symbol}, t in px_ret.index={t in px_ret.index}")
                debug_count += 1

            if t not in px_ret.index:
                rets.append(np.nan)
                ex_rets.append(np.nan)
                continue

            # t+1 ~ t+h 수익률
            try:
                ret_path = px_ret.loc[t:].iloc[1:h+1][symbol]
                bm_path = bm_ret.loc[t:].iloc[1:h+1]
            except Exception as e:
                if debug_count < 5:
                    print(f"      Exception for {symbol} at {t}: {e}")
                    debug_count += 1
                rets.append(np.nan)
                ex_rets.append(np.nan)
                continue

            if ret_path.isna().any() or bm_path.isna().any():
                if debug_count < 5:
                    print(f"      NaN found for {symbol} at {t}: ret_path has NaN={ret_path.isna().any()}, bm_path has NaN={bm_path.isna().any()}")
                    debug_count += 1
                rets.append(np.nan)
                ex_rets.append(np.nan)
                continue

            cum_ret = (1 + ret_path).prod() - 1
            cum_bm = (1 + bm_path).prod() - 1

            rets.append(cum_ret)
            ex_rets.append(cum_ret - cum_bm)
            success_count += 1

        events[col_r] = rets
        events[col_er] = ex_rets

    return events
