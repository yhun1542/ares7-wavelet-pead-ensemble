#!/usr/bin/env python3
"""
Ensemble Signal Builder
PEAD + Buyback 시그널을 단일 앙상블 시그널로 합성
"""

import pandas as pd


def build_ensemble_signal(
    signal_pead: pd.DataFrame,
    signal_bb: pd.DataFrame,
    w_pead: float = 0.6,
    w_bb: float = 0.4,
) -> pd.DataFrame:
    """
    PEAD + Buyback 시그널을 단일 앙상블 시그널로 합성.

    Parameters
    ----------
    signal_pead : DataFrame
        date x ticker, 0~1 범위
    signal_bb : DataFrame
        date x ticker, 0~1 범위
    w_pead : float
        PEAD 가중치
    w_bb : float
        Buyback 가중치

    Returns
    -------
    signal_ens : DataFrame
        date x ticker, 0~1 범위 (없으면 0)
    """
    # 공통 index/columns align
    idx = signal_pead.index.union(signal_bb.index)
    cols = signal_pead.columns.union(signal_bb.columns)

    pead = signal_pead.reindex(index=idx, columns=cols).fillna(0.0)
    bb   = signal_bb.reindex(index=idx, columns=cols).fillna(0.0)

    signal_ens = w_pead * pead + w_bb * bb

    # 0~1 범위 클립
    signal_ens = signal_ens.clip(0.0, 1.0)
    return signal_ens


if __name__ == "__main__":
    # 테스트
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent.parent
    
    # Signals 로드
    signal_pead = pd.read_csv(project_root / "data" / "signal_pead.csv", index_col=0, parse_dates=True)
    signal_bb = pd.read_csv(project_root / "data" / "signal_buyback.csv", index_col=0, parse_dates=True)
    
    print(f"PEAD signal shape: {signal_pead.shape}")
    print(f"Buyback signal shape: {signal_bb.shape}")
    
    # Ensemble
    signal_ens = build_ensemble_signal(signal_pead, signal_bb, w_pead=0.6, w_bb=0.4)
    
    print(f"\nEnsemble signal shape: {signal_ens.shape}")
    print(f"Ensemble non-zero signals: {(signal_ens > 0).sum().sum()}")
    print(f"Ensemble signal range: [{signal_ens.min().min():.4f}, {signal_ens.max().max():.4f}]")
    
    # 저장
    signal_ens.to_csv(project_root / "data" / "signal_ensemble.csv")
    print("\nSaved ensemble signal to data/signal_ensemble.csv")
    print("Done!")
