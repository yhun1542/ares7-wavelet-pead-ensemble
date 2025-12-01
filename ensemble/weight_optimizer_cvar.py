# ensemble/weight_optimizer_cvar.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def compute_cvar(ret: pd.Series, alpha: float = 0.95) -> float:
    """
    ret: 일간 수익률
    alpha: CVaR 신뢰수준 (0.95 → 하위 5% tail 평균)
    """
    ret = ret.dropna()
    if ret.empty:
        return 0.0
    losses = -ret.values
    var = np.quantile(losses, alpha)
    tail = losses[losses >= var]
    if tail.size == 0:
        return 0.0
    return float(tail.mean())


def evaluate_weights(
    returns_df: pd.DataFrame,
    weights: np.ndarray,
    risk_free: float = 0.0,
    cvar_lambda: float = 0.5,
) -> Dict:
    """
    returns_df: columns = 엔진들, index = date
    weights: 엔진 가중치 벡터 (합 1, 비음수)
    """
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()

    port_ret = returns_df.dot(weights)
    port_ret = port_ret.dropna()
    if port_ret.empty:
        return {"weights": weights, "sharpe": 0.0, "cvar": 0.0, "score": -1e9}

    days = (port_ret.index[-1] - port_ret.index[0]).days
    years = days / 365.25
    if years <= 0:
        return {"weights": weights, "sharpe": 0.0, "cvar": 0.0, "score": -1e9}

    mean_ret = port_ret.mean()
    vol = port_ret.std(ddof=0)
    ann_ret = (1 + mean_ret) ** 252 - 1
    ann_vol = vol * np.sqrt(252)
    sharpe = (mean_ret - risk_free / 252) / vol if vol > 0 else 0.0

    cvar = compute_cvar(port_ret, alpha=0.95)
    score = sharpe - cvar_lambda * cvar

    return {
        "weights": weights.tolist(),
        "sharpe": float(sharpe),
        "cvar": float(cvar),
        "ann_return": float(ann_ret),
        "ann_vol": float(ann_vol),
        "score": float(score),
    }


def grid_search_cvar(
    returns_df: pd.DataFrame,
    step: float = 0.1,
    cvar_lambda: float = 0.5,
) -> List[Dict]:
    """
    단순 3엔진 가정 (columns 3개), w ≥ 0, ∑w=1 그리드 서치.
    필요시 확장 가능.
    """
    cols = list(returns_df.columns)
    if len(cols) != 3:
        raise ValueError("grid_search_cvar: 현재 버전은 엔진 3개만 지원합니다.")

    results: List[Dict] = []

    ws = np.arange(0.0, 1.0 + 1e-9, step)
    for w0 in ws:
        for w1 in ws:
            w2 = 1.0 - w0 - w1
            if w2 < -1e-9:
                continue
            if w2 < 0:
                w2 = 0.0
            weights = np.array([w0, w1, w2], dtype=float)
            res = evaluate_weights(returns_df, weights, cvar_lambda=cvar_lambda)
            res["engine_weights"] = dict(zip(cols, res["weights"]))
            results.append(res)

    results_sorted = sorted(results, key=lambda r: r["score"], reverse=True)
    return results_sorted
