
import numpy as np
import pandas as pd

def build_event_portfolios(
    events: pd.DataFrame,
    px: pd.DataFrame,
    bm: pd.Series,
    horizons=(3, 5, 10),
    bucket_col='bucket',
):
    """
    이벤트 기반 포트폴리오 일별 수익률 생성.
    - 각 이벤트: event_date 다음 날부터 h일 동안 보유
    - 각 날짜: 활성 이벤트 종목들을 동일비중으로 보유
    - bucket별 & horizon별 포트폴리오 수익률 시계열 반환
    """
    px = px.sort_index()
    bm = bm.reindex(px.index).sort_index()
    px_ret = px.pct_change()
    bm_ret = bm.pct_change()

    portfolios = {}  # key: (bucket, horizon) -> DataFrame(date, ['ret', 'bm_ret', 'excess'])

    dates = px_ret.index

    for bucket in ['pos_top', 'neg_bottom']:
        df_bucket = events[events[bucket_col] == bucket].copy()
        if df_bucket.empty:
            continue

        for h in horizons:
            # 각 이벤트에 대해 active 기간 [t+1, t+h] 설정
            records = []
            for _, row in df_bucket.iterrows():
                t = row['event_date']
                if t not in dates:
                    continue
                # t 위치 찾기
                pos = dates.get_loc(t)
                start_idx = pos + 1
                end_idx = pos + h
                if start_idx >= len(dates):
                    continue
                end_idx = min(end_idx, len(dates) - 1)
                active_dates = dates[start_idx:end_idx+1]
                for d in active_dates:
                    symbol = row.get('ticker') or row.get('symbol')
                    records.append((d, symbol))

            if len(records) == 0:
                continue

            active_df = pd.DataFrame(records, columns=['date', 'symbol'])
            # date별 보유 심볼 리스트
            grouped = active_df.groupby('date')['symbol'].apply(list)

            port_ret = []
            port_bm = []
            idx_list = []

            for d, syms in grouped.items():
                if d not in px_ret.index:
                    continue
                r = px_ret.loc[d, syms].dropna()
                if r.empty:
                    continue
                mean_r = r.mean()
                bm_r = bm_ret.loc[d]
                port_ret.append(mean_r)
                port_bm.append(bm_r)
                idx_list.append(d)

            if not idx_list:
                continue

            df_port = pd.DataFrame({
                'ret': port_ret,
                'bm_ret': port_bm,
            }, index=pd.to_datetime(idx_list).sort_values())

            df_port['excess'] = df_port['ret'] - df_port['bm_ret']
            portfolios[(bucket, h)] = df_port

    return portfolios


def summarize_portfolio_returns(portfolios: dict) -> pd.DataFrame:
    """
    포트폴리오 일별 수익률 시계열을 Sharpe / MDD / 연환산수익 등으로 요약.
    """
    rows = []

    for (bucket, h), df in portfolios.items():
        r = df['ret'].dropna()
        er = df['excess'].dropna()
        if len(r) < 30:
            continue

        # 단순히 252 영업일 가정
        mean = r.mean()
        vol = r.std()
        sharpe = (mean / (vol + 1e-9)) * np.sqrt(252)

        mean_ex = er.mean()
        vol_ex = er.std()
        sharpe_ex = (mean_ex / (vol_ex + 1e-9)) * np.sqrt(252)

        cum = (1 + r).prod() - 1
        # MDD 계산
        cum_curve = (1 + r).cumprod()
        peak = cum_curve.cummax()
        dd = (cum_curve / peak) - 1
        mdd = dd.min()

        rows.append({
            'bucket': bucket,
            'horizon': h,
            'n_days': len(r),
            'ann_return': mean * 252,
            'ann_vol': vol * np.sqrt(252),
            'sharpe': sharpe,
            'ann_excess': mean_ex * 252,
            'sharpe_excess': sharpe_ex,
            'mdd': mdd,
            'total_return': cum,
        })

    return pd.DataFrame(rows)
