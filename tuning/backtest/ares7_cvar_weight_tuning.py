# tuning/backtest/ares7_cvar_weight_tuning.py

from __future__ import annotations
from pathlib import Path
from typing import Dict
import sys

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import numpy as np
import pandas as pd

from ensemble.weight_optimizer_cvar import grid_search_cvar


BASE_DIR = Path(__file__).resolve().parents[2]


def load_engine_returns() -> pd.DataFrame:
    """
    세 엔진(QM, LowVol, Defensive)의 일간 수익률을 로드.
    예시 경로:
      results/ret_qm.csv
      results/ret_lowvol.csv
      results/ret_defensive.csv
    """
    def _load(path: Path, name: str) -> pd.Series:
        if not path.exists():
            print(f"Warning: {path} not found, creating dummy data")
            # Create dummy data for testing
            dates = pd.date_range('2020-01-01', '2024-12-31', freq='D')
            returns = pd.Series(
                np.random.randn(len(dates)) * 0.01,
                index=dates,
                name=name
            )
            return returns
        
        df = pd.read_csv(path, parse_dates=["date"])
        df = df.set_index("date").sort_index()
        s = df["ret"].rename(name)
        return s

    ret_qm = _load(BASE_DIR / "results" / "ret_qm.csv", "qm")
    ret_lv = _load(BASE_DIR / "results" / "ret_lowvol.csv", "lv")
    ret_def = _load(BASE_DIR / "results" / "ret_defensive.csv", "def")

    df = pd.concat([ret_qm, ret_lv, ret_def], axis=1).dropna()
    return df


def main():
    print("="*80)
    print("ARES7 CVaR-Based Weight Optimization")
    print("="*80)
    
    returns_df = load_engine_returns()
    print(f"\nLoaded returns data:")
    print(f"  Date range: {returns_df.index[0]} to {returns_df.index[-1]}")
    print(f"  Total days: {len(returns_df)}")
    print(f"  Engines: {list(returns_df.columns)}")

    # 예시: 전체 기간 기준 weight 후보 찾기
    print("\nRunning grid search with CVaR optimization...")
    print("  Step size: 0.1")
    print("  CVaR lambda: 0.5")
    
    results = grid_search_cvar(
        returns_df,
        step=0.1,
        cvar_lambda=0.5,
    )

    top10 = results[:10]
    print("\n" + "="*80)
    print("Top 10 weights by Sharpe - λ*CVaR")
    print("="*80)
    for i, r in enumerate(top10, 1):
        print(f"\n{i}. Score: {r['score']:.4f}")
        print(f"   Weights: {r['engine_weights']}")
        print(f"   Sharpe: {r['sharpe']:.4f}, CVaR: {r['cvar']:.4f}")
        print(f"   Ann. Return: {r['ann_return']:.2%}, Ann. Vol: {r['ann_vol']:.2%}")

    out_path = BASE_DIR / "tuning" / "results" / "cvar_weight_search.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Saved CVaR weight search results to:")
    print(f"  {out_path}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
