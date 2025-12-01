#!/usr/bin/env python3
"""
ares7_integrate_overlay.py

================================================================================
ARES7 + Wavelet + PEAD Overlay Integration (PRODUCTION)
================================================================================

역할:
  - ARES7 Base weights + Wavelet+PEAD Overlay를 통합
  - λ=1.0 고정 (100% overlay 적용)
  - 리스크 가드: 종목당 tilt cap (±2%)
  - 최종 weights 계산 및 저장

전제:
  - ares7_base_weights.csv (symbol, weight)
  - wavelet_pead_overlay_prod_YYYYMMDD.csv (date, symbol, tilt_final)

출력:
  - ares7_final_weights_YYYYMMDD.csv (date, symbol, weight_base, tilt_final, weight_final)

실행:
  python3 ares7_integrate_overlay.py

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
Version: PRODUCTION v1.0
================================================================================
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ensemble_outputs"
LOG_DIR = BASE_DIR / "logs"

# Input files
BASE_WEIGHTS_FILE = DATA_DIR / "ares7_base_weights.csv"
# Overlay file: use latest wavelet_pead_overlay_prod_*.csv
OVERLAY_FILE_PATTERN = "wavelet_pead_overlay_prod_*.csv"

# Parameters
LAMBDA_OVERLAY = 1.0  # 100% overlay (FIXED)
MAX_TILT = 0.02       # ±2% cap per symbol

# Logging
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"ares7_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ============================================================================
# Logging
# ============================================================================

def log_message(msg: str, to_file: bool = True, to_console: bool = True):
    """Log message to file and/or console"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {msg}"
    
    if to_console:
        print(log_line)
    
    if to_file:
        with open(LOG_FILE, 'a') as f:
            f.write(log_line + '\n')

# ============================================================================
# Main Logic
# ============================================================================

def find_latest_overlay_file():
    """Find the latest wavelet_pead_overlay_prod_*.csv file"""
    overlay_files = sorted(OUTPUT_DIR.glob(OVERLAY_FILE_PATTERN), reverse=True)
    if not overlay_files:
        raise FileNotFoundError(f"No overlay files found matching {OVERLAY_FILE_PATTERN}")
    return overlay_files[0]


def main():
    log_message("=" * 80)
    log_message("ARES7 + Wavelet + PEAD Overlay Integration (PRODUCTION)")
    log_message("=" * 80)
    log_message(f"Lambda Overlay: {LAMBDA_OVERLAY} (100% FIXED)")
    log_message(f"Max Tilt per Symbol: ±{MAX_TILT*100:.1f}%")
    log_message("=" * 80)
    
    # 1. Load base weights
    log_message("\n[Step 1] Loading ARES7 base weights...")
    
    if not BASE_WEIGHTS_FILE.exists():
        log_message(f"ERROR: Base weights file not found: {BASE_WEIGHTS_FILE}")
        log_message("Please create ares7_base_weights.csv with columns: symbol, weight")
        sys.exit(1)
    
    base_weights = pd.read_csv(BASE_WEIGHTS_FILE)
    
    if "symbol" not in base_weights.columns or "weight" not in base_weights.columns:
        log_message("ERROR: Base weights file must have columns: symbol, weight")
        sys.exit(1)
    
    log_message(f"  Base weights loaded: {len(base_weights)} symbols")
    log_message(f"  Total base weight: {base_weights['weight'].sum():.6f}")
    
    # 2. Load overlay
    log_message("\n[Step 2] Loading Wavelet+PEAD overlay...")
    
    overlay_file = find_latest_overlay_file()
    log_message(f"  Using overlay file: {overlay_file.name}")
    
    overlay_df = pd.read_csv(overlay_file)
    
    if "symbol" not in overlay_df.columns or "tilt_final" not in overlay_df.columns:
        log_message("ERROR: Overlay file must have columns: symbol, tilt_final")
        sys.exit(1)
    
    log_message(f"  Overlay loaded: {len(overlay_df)} symbols")
    log_message(f"  Overlay date: {overlay_df['date'].iloc[0] if 'date' in overlay_df.columns else 'N/A'}")
    
    # 3. Merge base weights with overlay
    log_message("\n[Step 3] Merging base weights with overlay...")
    
    df = base_weights.merge(
        overlay_df[["symbol", "tilt_final"]], 
        on="symbol", 
        how="left"
    ).fillna({"tilt_final": 0.0})
    
    log_message(f"  Merged: {len(df)} symbols")
    log_message(f"  Symbols with overlay: {(df['tilt_final'] != 0).sum()}")
    log_message(f"  Symbols without overlay: {(df['tilt_final'] == 0).sum()}")
    
    # 4. Apply tilt cap (risk guard)
    log_message("\n[Step 4] Applying tilt cap (risk guard)...")
    
    df["tilt_original"] = df["tilt_final"]
    df["tilt_final_capped"] = df["tilt_final"].clip(lower=-MAX_TILT, upper=MAX_TILT)
    
    capped_count = (df["tilt_original"] != df["tilt_final_capped"]).sum()
    log_message(f"  Symbols capped: {capped_count}")
    
    if capped_count > 0:
        log_message(f"  Max tilt before cap: {df['tilt_original'].abs().max():.6f}")
        log_message(f"  Max tilt after cap: {df['tilt_final_capped'].abs().max():.6f}")
    
    # 5. Calculate final weights (λ=1.0)
    log_message("\n[Step 5] Calculating final weights (λ=1.0)...")
    
    df["weight_final"] = df["weight"] + LAMBDA_OVERLAY * df["tilt_final_capped"]
    
    log_message(f"  Lambda overlay: {LAMBDA_OVERLAY} (100%)")
    log_message(f"  Total final weight (before normalize): {df['weight_final'].sum():.6f}")
    
    # 6. Normalize (optional)
    log_message("\n[Step 6] Normalizing final weights...")
    
    total = df["weight_final"].sum()
    if total != 0:
        df["weight_final_normalized"] = df["weight_final"] / total
    else:
        log_message("WARNING: Total weight is 0, skipping normalization")
        df["weight_final_normalized"] = df["weight_final"]
    
    log_message(f"  Total final weight (after normalize): {df['weight_final_normalized'].sum():.6f}")
    
    # 7. Statistics
    log_message("\n" + "=" * 80)
    log_message("STATISTICS")
    log_message("=" * 80)
    
    log_message(f"Base weights:")
    log_message(f"  Mean: {df['weight'].mean():.6f}")
    log_message(f"  Std: {df['weight'].std():.6f}")
    log_message(f"  Min: {df['weight'].min():.6f}")
    log_message(f"  Max: {df['weight'].max():.6f}")
    
    log_message(f"\nOverlay tilts (capped):")
    log_message(f"  Mean: {df['tilt_final_capped'].mean():.6f}")
    log_message(f"  Std: {df['tilt_final_capped'].std():.6f}")
    log_message(f"  Min: {df['tilt_final_capped'].min():.6f}")
    log_message(f"  Max: {df['tilt_final_capped'].max():.6f}")
    
    log_message(f"\nFinal weights (normalized):")
    log_message(f"  Mean: {df['weight_final_normalized'].mean():.6f}")
    log_message(f"  Std: {df['weight_final_normalized'].std():.6f}")
    log_message(f"  Min: {df['weight_final_normalized'].min():.6f}")
    log_message(f"  Max: {df['weight_final_normalized'].max():.6f}")
    
    # 8. Save results
    log_message("\n" + "=" * 80)
    log_message("SAVING RESULTS")
    log_message("=" * 80)
    
    today = datetime.now().strftime("%Y%m%d")
    output_path = OUTPUT_DIR / f"ares7_final_weights_{today}.csv"
    
    # Prepare output
    df_out = df[[
        "symbol", 
        "weight", 
        "tilt_final_capped", 
        "weight_final_normalized"
    ]].copy()
    
    df_out = df_out.rename(columns={
        "weight": "weight_base",
        "tilt_final_capped": "tilt_final",
        "weight_final_normalized": "weight_final"
    })
    
    df_out.insert(0, "date", datetime.now().strftime("%Y-%m-%d"))
    
    # Save
    OUTPUT_DIR.mkdir(exist_ok=True)
    df_out.to_csv(output_path, index=False)
    
    log_message(f"Final weights saved to: {output_path}")
    log_message(f"  Symbols: {len(df_out)}")
    log_message(f"  Total weight: {df_out['weight_final'].sum():.6f}")
    
    # Sample output
    log_message("\nSample output (first 10 rows):")
    log_message("\n" + df_out.head(10).to_string(index=False))
    
    log_message("\n" + "=" * 80)
    log_message("✅ ARES7 + Wavelet + PEAD Integration Complete")
    log_message("=" * 80)
    log_message(f"Log file: {LOG_FILE}")
    
    return output_path


if __name__ == "__main__":
    main()
