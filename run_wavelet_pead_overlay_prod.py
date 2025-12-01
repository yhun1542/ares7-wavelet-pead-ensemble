#!/usr/bin/env python3
"""
run_wavelet_pead_overlay_prod.py

================================================================================
Wavelet + PEAD Overlay Combiner (PRODUCTION)
================================================================================

역할:
  - Wavelet overlay 파일 + PEAD overlay 파일을 읽어서
    최적 가중치(w_wavelet=0.54, w_pead=0.46)로 합성한 최종 overlay 계산
  - ARES7 시스템이 사용할 최종 overlay CSV를 생성

전제:
  - ensemble_outputs/wavelet_overlay_latest.csv
  - ensemble_outputs/pead_overlay_latest.csv

입력 형식:
  wavelet_overlay_latest.csv:
      symbol,tilt_wavelet
      AAPL,0.0123
      MSFT,-0.0045
      ...

  pead_overlay_latest.csv:
      symbol,tilt_pead
      AAPL,0.0060
      MSFT,0.0010
      ...

출력:
  - ensemble_outputs/wavelet_pead_overlay_prod_YYYYMMDD.csv
      date,symbol,tilt_final

실행:
  python3 run_wavelet_pead_overlay_prod.py

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
Version: PRODUCTION v1.0
================================================================================
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "ensemble_outputs"
LOG_DIR = BASE_DIR / "logs"

# 입력 파일 경로
WAVELET_FILE = OUT_DIR / "wavelet_overlay_latest.csv"
PEAD_FILE = OUT_DIR / "pead_overlay_latest.csv"

# 최적 가중치 (Train+Val 기준 최적화 결과)
# Test Sharpe: 0.775, Base+Overlay: 0.990
W_WAVELET = 0.540  # 54%
W_PEAD = 0.460     # 46%

# Logging
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"wavelet_pead_combiner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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

def main():
    log_message("=" * 80)
    log_message("Wavelet + PEAD Overlay Combiner (PRODUCTION)")
    log_message("=" * 80)
    log_message(f"Wavelet overlay file: {WAVELET_FILE}")
    log_message(f"PEAD overlay file: {PEAD_FILE}")
    log_message(f"Weight Wavelet: {W_WAVELET:.3f} (LOCKED)")
    log_message(f"Weight PEAD: {W_PEAD:.3f} (LOCKED)")
    log_message("=" * 80)
    
    # Check input files
    if not WAVELET_FILE.exists():
        raise FileNotFoundError(f"Wavelet overlay file not found: {WAVELET_FILE}")
    if not PEAD_FILE.exists():
        raise FileNotFoundError(f"PEAD overlay file not found: {PEAD_FILE}")
    
    # Load overlay files
    log_message("Loading overlay files...")
    wv = pd.read_csv(WAVELET_FILE)
    pe = pd.read_csv(PEAD_FILE)
    
    log_message(f"  Wavelet overlay: {len(wv)} symbols")
    log_message(f"  PEAD overlay: {len(pe)} symbols")
    
    # Validate and normalize column names
    if "symbol" not in wv.columns:
        raise ValueError("wavelet_overlay_latest.csv requires 'symbol' column")
    
    # Handle tilt column naming
    if "tilt" in wv.columns and "tilt_wavelet" not in wv.columns:
        wv = wv.rename(columns={"tilt": "tilt_wavelet"})
    if "tilt_wavelet" not in wv.columns:
        raise ValueError("wavelet_overlay_latest.csv requires 'tilt_wavelet' or 'tilt' column")
    
    if "symbol" not in pe.columns:
        raise ValueError("pead_overlay_latest.csv requires 'symbol' column")
    
    if "tilt" in pe.columns and "tilt_pead" not in pe.columns:
        pe = pe.rename(columns={"tilt": "tilt_pead"})
    if "tilt_pead" not in pe.columns:
        raise ValueError("pead_overlay_latest.csv requires 'tilt_pead' or 'tilt' column")
    
    # Merge overlays (outer join, fill missing with 0)
    log_message("Merging overlays...")
    df = pd.merge(
        wv[["symbol", "tilt_wavelet"]],
        pe[["symbol", "tilt_pead"]],
        on="symbol",
        how="outer",
    ).fillna(0.0)
    
    log_message(f"  Combined symbols: {len(df)}")
    
    # Calculate final combined overlay
    log_message("Calculating final overlay...")
    df["tilt_final"] = W_WAVELET * df["tilt_wavelet"] + W_PEAD * df["tilt_pead"]
    
    # Statistics
    log_message("\nOverlay Statistics:")
    log_message(f"  Wavelet tilt range: [{df['tilt_wavelet'].min():.6f}, {df['tilt_wavelet'].max():.6f}]")
    log_message(f"  PEAD tilt range: [{df['tilt_pead'].min():.6f}, {df['tilt_pead'].max():.6f}]")
    log_message(f"  Final tilt range: [{df['tilt_final'].min():.6f}, {df['tilt_final'].max():.6f}]")
    log_message(f"  Final tilt mean: {df['tilt_final'].mean():.6f}")
    log_message(f"  Final tilt std: {df['tilt_final'].std():.6f}")
    
    # Prepare output
    today = datetime.utcnow().strftime("%Y%m%d")
    OUT_DIR.mkdir(exist_ok=True)
    
    out_path = OUT_DIR / f"wavelet_pead_overlay_prod_{today}.csv"
    df_out = df[["symbol", "tilt_final"]].copy()
    df_out.insert(0, "date", datetime.utcnow().strftime("%Y-%m-%d"))
    
    # Save to CSV
    df_out.to_csv(out_path, index=False)
    
    log_message("\n" + "=" * 80)
    log_message("Output Summary")
    log_message("=" * 80)
    log_message(f"Final overlay saved to: {out_path}")
    log_message(f"  Symbols: {len(df_out)}")
    log_message(f"  Date: {df_out['date'].iloc[0]}")
    log_message(f"  Weight Wavelet: {W_WAVELET:.3f}")
    log_message(f"  Weight PEAD: {W_PEAD:.3f}")
    
    # Sample output
    log_message("\nSample output (first 5 rows):")
    log_message("\n" + df_out.head().to_string(index=False))
    
    log_message("\n" + "=" * 80)
    log_message("✅ Wavelet + PEAD Overlay Combination Complete")
    log_message("=" * 80)
    log_message(f"Log file: {LOG_FILE}")
    
    # Return path for automation scripts
    return out_path


if __name__ == "__main__":
    main()
