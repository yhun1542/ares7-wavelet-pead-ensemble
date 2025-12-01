# research/pead/overlay_engine.py

import pandas as pd
import numpy as np


def apply_overlay_budget(
    w_base: pd.DataFrame,
    signal: pd.DataFrame,
    budget: float = 0.1,
    mode: str = "strength",   # "strength" or "equal"
    cap_single: float | None = 0.05,
) -> pd.DataFrame:
    """
    ARES7 base weight + PEAD signal → Overlay 적용 최종 weight.

    Parameters
    ----------
    w_base : DataFrame
        date x symbol, 각 날짜별 합계 ≈ 1 (롱온리)
    signal : DataFrame
        date x symbol, 0~1 범위 (build_daily_signal 결과)
    budget : float
        Overlay Budget B (0.0~0.3 정도 권장)
    mode : {"strength", "equal"}
        - "strength": signal 비율대로 overlay 비중 배분
        - "equal": active 심볼들에 동일 비중
    cap_single : float or None
        종목별 최대 비중 캡 (예: 0.05 → 5%)

    Returns
    -------
    w_final : DataFrame
        Overlay 적용 후 최종 weight (date x symbol, sum(row)=1)
    """

    w_base = w_base.sort_index().copy()
    signal = signal.copy()

    # index / columns align
    signal = signal.reindex(index=w_base.index, columns=w_base.columns).fillna(0.0)

    w_final = pd.DataFrame(index=w_base.index, columns=w_base.columns, dtype=float)

    for t in w_base.index:
        wb = w_base.loc[t].astype(float).fillna(0.0)
        s = signal.loc[t].astype(float).fillna(0.0)

        # base 축소
        wb_shrunk = wb * (1.0 - budget)

        # active 종목
        active = s[s > 0]
        if active.empty or budget <= 0.0:
            wf = wb_shrunk
        else:
            if mode == "strength":
                weights_raw = active / active.sum()
            else:  # "equal"
                weights_raw = pd.Series(1.0 / len(active), index=active.index)

            w_pead = pd.Series(0.0, index=wb.index)
            w_pead[weights_raw.index] = budget * weights_raw

            wf = wb_shrunk + w_pead

        # 단일 종목 cap 적용
        if cap_single is not None:
            over = wf > cap_single
            if over.any():
                excess = (wf[over] - cap_single).sum()
                wf[over] = cap_single
                if excess > 0:
                    under = ~over
                    if under.any():
                        wf_under = wf[under]
                        wf[under] = wf_under + excess * wf_under / wf_under.sum()

        # normalize
        ssum = wf.sum()
        if ssum > 0:
            wf = wf / ssum

        w_final.loc[t] = wf

    return w_final


def compute_portfolio_returns(
    weights: pd.DataFrame,
    prices: pd.DataFrame,
    fee_rate: float = 0.001,
) -> pd.Series:
    """
    weights & prices로 일별 포트폴리오 수익률 계산 (거래비용 포함).

    가정:
    - weights.index, prices.index는 거래일 기준으로 align 가능
    - t일 weight로 t→t+1 수익률을 먹는 구조를
      (실무에선 t-1 close에서 w_t 결정, t close까지 수익)로 해석.

    Parameters
    ----------
    weights : DataFrame
        date x symbol, sum(row) ≈ 1
    prices : DataFrame
        date x symbol, 종가 (close)
    fee_rate : float
        편도 거래 비용 (예: 0.001 → 0.1%)

    Returns
    -------
    ret_net : Series
        일별 순수익률 (거래비용 차감 후)
    """

    # align
    px = prices.sort_index()
    w = weights.sort_index()

    # prices 기준으로 reindex, weight는 ffill
    w = w.reindex(px.index).ffill().fillna(0.0)

    # 일일 수익률
    r = px.pct_change(fill_method=None).fillna(0.0)

    # 포트폴리오 수익률: 전일 weight * 당일 개별 수익률
    w_shift = w.shift(1).fillna(0.0)
    ret_gross = (w_shift * r).sum(axis=1)

    # turnover 기반 거래비용 (단순화 버전)
    # 일별 체결 비중 ≈ Σ |w_t - w_{t-1}|
    dw = (w - w.shift(1)).abs().fillna(0.0)
    turnover = dw.sum(axis=1)
    trading_cost = fee_rate * turnover

    ret_net = ret_gross - trading_cost

    return ret_net
