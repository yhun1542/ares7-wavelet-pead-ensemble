#!/usr/bin/env python3
"""
Wavelet + PEAD Overlay Weight Optimizer

목표:
  - Wavelet overlay PnL + PEAD overlay PnL을 사용해
    Train+Val 구간에서 Sharpe 최대가 되도록 weight 최적화
  - Test 구간에서 Sharpe가 실제로 얼마나 나오는지 확인

전제:
  - research/wavelet/wavelet_pnl.csv  : date,pnl
  - research/pead/pead_pnl.csv        : date,pnl
  - (선택) research/base/base_pnl.csv : date,pnl  (있으면 최종 포트폴리오 Sharpe도 같이 계산)

실행:
  python3 run_wavelet_pead_optimizer.py

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
Version: 1.0
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
WAVELET_PNL_PATH = BASE_DIR / "research" / "wavelet" / "wavelet_pnl.csv"
PEAD_PNL_PATH    = BASE_DIR / "research" / "pead" / "pead_pnl.csv"
BASE_PNL_PATH    = BASE_DIR / "research" / "base" / "base_pnl.csv"  # optional

# Train/Val/Test 기간 (ARES7/8 프로젝트 구간)
TRAIN_START = "2016-01-01"
TRAIN_END   = "2019-12-31"

VAL_START   = "2020-01-01"
VAL_END     = "2021-12-31"

TEST_START  = "2022-01-01"
TEST_END    = "2025-12-31"

# Output
OUTPUT_DIR = BASE_DIR / "ensemble_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================================
# Utility Functions
# ============================================================================

def load_pnl(path: Path, col_name: str) -> pd.Series:
    """Load PnL CSV file and return as Series"""
    if not path.exists():
        raise FileNotFoundError(f"PnL file not found: {path}")
    
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError(f"{path} requires 'date' column")
    if "pnl" not in df.columns:
        raise ValueError(f"{path} requires 'pnl' column")

    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date")
    s = df.set_index("date")["pnl"].rename(col_name)
    
    print(f"  Loaded {col_name}: {len(s)} days, range {s.index.min().date()} ~ {s.index.max().date()}")
    
    return s


def sharpe(series: pd.Series) -> float:
    """Calculate annualized Sharpe ratio"""
    series = series.dropna()
    if len(series) < 2:
        return np.nan
    mu = series.mean()
    sigma = series.std()
    if sigma <= 0:
        return np.nan
    # Annualized Sharpe (assuming daily returns)
    return float(mu / sigma * np.sqrt(252))


def split_by_period(df: pd.DataFrame):
    """Split dataframe into Train/Val/Test periods"""
    df = df.sort_index()

    train = df.loc[TRAIN_START:TRAIN_END]
    val   = df.loc[VAL_START:VAL_END]
    test  = df.loc[TEST_START:TEST_END]

    return train, val, test


def optimize_weights(trainval: pd.DataFrame) -> dict:
    """
    Optimize Wavelet/PEAD overlay weights using Train+Val data
    
    Method 1: Theoretical optimization (Σ^-1 μ)
    Method 2: Grid search (fallback)
    """
    sub = trainval[["wv", "pead"]].dropna()
    if len(sub) < 30:
        raise ValueError("Insufficient Train+Val data (need both wv and pead)")

    X = sub.values
    mu = X.mean(axis=0)             # [E(wv), E(pead)]
    cov = np.cov(X, rowvar=False)   # 2x2

    # Theoretical optimization: w ∝ Σ^-1 μ
    try:
        w_raw = np.linalg.solve(cov, mu)
        if not np.all(np.isfinite(w_raw)):
            raise ValueError("Non-finite weights from solve")
    except Exception as e:
        print(f"  Warning: Theoretical optimization failed ({e}), using grid search")
        # Fallback: Grid search
        best = None
        for w in np.linspace(0.0, 1.0, 51):  # w: PEAD weight, (1-w): Wavelet weight
            overlay = (1 - w) * sub["wv"] + w * sub["pead"]
            s = sharpe(overlay)
            if best is None or s > best["sharpe"]:
                best = {"w_pead": float(w), "w_wv": float(1 - w), "sharpe": float(s)}
        return {
            "w_wv": best["w_wv"],
            "w_pead": best["w_pead"],
            "source": "grid",
            "trainval_sharpe": best["sharpe"],
        }

    # Normalize Σ^-1 μ result (sum to 1)
    if np.allclose(w_raw.sum(), 0):
        # If sum is 0, fallback to Wavelet 1.0, PEAD 0.0
        w_norm = np.array([1.0, 0.0])
    else:
        w_norm = w_raw / w_raw.sum()

    w_wv, w_pead = float(w_norm[0]), float(w_norm[1])

    # Calculate Train+Val Sharpe
    overlay_trainval = w_wv * trainval["wv"] + w_pead * trainval["pead"]
    s_trainval = sharpe(overlay_trainval)

    return {
        "w_wv": w_wv,
        "w_pead": w_pead,
        "source": "Sigma^-1 mu",
        "trainval_sharpe": float(s_trainval),
    }


# ============================================================================
# Main Logic
# ============================================================================

def main():
    print("=" * 80)
    print("Wavelet + PEAD Overlay Weight Optimizer")
    print("=" * 80)
    print()

    # 1) Load PnL data
    print("Loading PnL data...")
    wv = load_pnl(WAVELET_PNL_PATH, "wv")
    pe = load_pnl(PEAD_PNL_PATH, "pead")

    df = pd.concat([wv, pe], axis=1).dropna()

    base = None
    if BASE_PNL_PATH.exists():
        base = load_pnl(BASE_PNL_PATH, "base")
        df = pd.concat([df, base], axis=1)
    else:
        print("  Note: base_pnl.csv not found, skipping Base+Overlay analysis")

    print(f"\nCommon days: {len(df)}")
    print()

    # 2) Split into Train/Val/Test
    train, val, test = split_by_period(df)

    print("Period splits:")
    print(f"  Train: {train.index.min().date()} ~ {train.index.max().date()}, n={len(train)}")
    print(f"  Val:   {val.index.min().date()} ~ {val.index.max().date()}, n={len(val)}")
    print(f"  Test:  {test.index.min().date()} ~ {test.index.max().date()}, n={len(test)}")
    print()

    # 3) Individual Sharpe ratios
    print("=" * 80)
    print("Individual Strategy Sharpe Ratios")
    print("=" * 80)
    for name, sub in [("Train", train), ("Val", val), ("Test", test)]:
        s_wv = sharpe(sub["wv"])
        s_pd = sharpe(sub["pead"])
        print(f"[{name:5s}] Wavelet: {s_wv:6.3f}, PEAD: {s_pd:6.3f}")
    print()

    # 4) Optimize weights on Train+Val
    print("=" * 80)
    print("Optimizing Overlay Weights (Train+Val)")
    print("=" * 80)
    trainval = pd.concat([train, val]).sort_index()
    opt = optimize_weights(trainval)

    print(f"Optimization method: {opt['source']}")
    print(f"  w_wavelet : {opt['w_wv']:7.3f}")
    print(f"  w_pead    : {opt['w_pead']:7.3f}")
    print(f"  Sharpe(T+V): {opt['trainval_sharpe']:6.3f}")
    print()

    # 5) Evaluate Test performance
    w_wv = opt["w_wv"]
    w_pead = opt["w_pead"]

    overlay_train = w_wv * train["wv"] + w_pead * train["pead"]
    overlay_val   = w_wv * val["wv"] + w_pead * val["pead"]
    overlay_test  = w_wv * test["wv"] + w_pead * test["pead"]

    print("=" * 80)
    print("Overlay Sharpe (Wavelet + PEAD Combination)")
    print("=" * 80)
    print(f"  Train Sharpe: {sharpe(overlay_train):6.3f}")
    print(f"  Val Sharpe  : {sharpe(overlay_val):6.3f}")
    print(f"  Test Sharpe : {sharpe(overlay_test):6.3f}")
    print()

    # Target check
    test_sharpe = sharpe(overlay_test)
    if 0.7 <= test_sharpe <= 0.8:
        print("✅ Test Sharpe is in target range [0.7, 0.8]")
    elif test_sharpe > 0.8:
        print("🎉 Test Sharpe exceeds 0.8!")
    else:
        print("⚠️  Test Sharpe is below 0.7")
    print()

    if base is not None:
        # Base + Overlay portfolio Sharpe
        print("=" * 80)
        print("Base + Overlay Portfolio Sharpe")
        print("=" * 80)
        
        overlay_all = w_wv * df["wv"] + w_pead * df["pead"]
        full_train, full_val, full_test = split_by_period(
            pd.concat([df["base"], overlay_all.rename("overlay")], axis=1)
        )

        for name, sub in [("Train", full_train), ("Val", full_val), ("Test", full_test)]:
            base_s = sharpe(sub["base"])
            full_s = sharpe(sub["base"] + sub["overlay"])
            incr_s = full_s - base_s
            print(f"[{name:5s}] Base: {base_s:6.3f}, Base+Overlay: {full_s:6.3f}, Incremental: {incr_s:+6.3f}")
        print()

    # 6) Save results to CSV
    print("=" * 80)
    print("Saving Results")
    print("=" * 80)
    
    overlay_df = pd.DataFrame({
        "wv": df["wv"],
        "pead": df["pead"],
        "overlay_opt": w_wv * df["wv"] + w_pead * df["pead"],
    })
    
    if base is not None:
        overlay_df["base"] = df["base"]
        overlay_df["base_plus_overlay"] = overlay_df["base"] + overlay_df["overlay_opt"]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = OUTPUT_DIR / f"wavelet_pead_overlay_optimized_{timestamp}.csv"
    overlay_df.to_csv(out_path, index_label="date")
    print(f"  Optimized Overlay PnL saved to: {out_path}")
    
    # Save weights to summary file
    summary_path = OUTPUT_DIR / f"wavelet_pead_weights_{timestamp}.txt"
    with open(summary_path, 'w') as f:
        f.write("Wavelet + PEAD Overlay Weight Optimization\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Optimization method: {opt['source']}\n")
        f.write(f"w_wavelet : {opt['w_wv']:.6f}\n")
        f.write(f"w_pead    : {opt['w_pead']:.6f}\n\n")
        f.write(f"Train+Val Sharpe: {opt['trainval_sharpe']:.6f}\n\n")
        f.write("Test Performance:\n")
        f.write(f"  Overlay Test Sharpe: {sharpe(overlay_test):.6f}\n")
        if base is not None:
            base_test_s = sharpe(full_test["base"])
            full_test_s = sharpe(full_test["base"] + full_test["overlay"])
            f.write(f"  Base Test Sharpe: {base_test_s:.6f}\n")
            f.write(f"  Base+Overlay Test Sharpe: {full_test_s:.6f}\n")
    
    print(f"  Weight summary saved to: {summary_path}")
    print()

    print("=" * 80)
    print("Optimization Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
