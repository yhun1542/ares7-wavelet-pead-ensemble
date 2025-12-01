# ensemble/dynamic_ensemble_v2.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class RegimeWeights:
    bull: Dict[str, float]
    bear: Dict[str, float]
    high_vol: Dict[str, float]
    neutral: Dict[str, float]


def dynamic_ensemble_3engines(
    ret_qm: pd.Series,
    ret_lowvol: pd.Series,
    ret_def: pd.Series,
    regime: pd.Series,              # date → "BULL"/"BEAR"/"HIGH_VOL"/"NEUTRAL"
    weights: RegimeWeights,
) -> pd.Series:
    """
    세 엔진(QM, LowVol, Defensive)의 수익률을
    일별 regime에 따라 가중합한다.
    """
    df = pd.concat(
        [
            ret_qm.rename("qm"),
            ret_lowvol.rename("lv"),
            ret_def.rename("def"),
        ],
        axis=1,
    ).dropna()

    regime = regime.reindex(df.index, method="ffill")

    rets = []
    for dt, row in df.iterrows():
        reg = regime.loc[dt] if dt in regime.index else "NEUTRAL"
        if reg == "BULL":
            w = weights.bull
        elif reg == "BEAR":
            w = weights.bear
        elif reg == "HIGH_VOL":
            w = weights.high_vol
        else:
            w = weights.neutral

        w_qm = w.get("qm", 0.0)
        w_lv = w.get("lv", 0.0)
        w_def = w.get("def", 0.0)
        total = w_qm + w_lv + w_def
        if total <= 0:
            rets.append((dt, 0.0))
            continue

        w_qm /= total
        w_lv /= total
        w_def /= total

        r = w_qm * row["qm"] + w_lv * row["lv"] + w_def * row["def"]
        rets.append((dt, r))

    if not rets:
        return pd.Series(dtype=float)

    ser = pd.Series(
        data=[r for (_, r) in rets],
        index=[dt for (dt, _) in rets],
        name="ret_dyn_ensemble_v2",
    ).sort_index()
    return ser
