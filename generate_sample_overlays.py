#!/usr/bin/env python3
"""
Generate Sample Overlay Files for Testing

이 스크립트는 테스트용 샘플 overlay 파일을 생성합니다.
실제 Wavelet/PEAD overlay 파일이 준비되면 이 스크립트는 사용하지 않아도 됩니다.

실행:
  python3 generate_sample_overlays.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "ensemble_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Sample symbols (S&P 100 subset)
SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "UNH", "JNJ",
    "JPM", "V", "PG", "XOM", "MA", "HD", "CVX", "MRK", "ABBV", "PFE",
    "KO", "AVGO", "PEP", "COST", "TMO", "MCD", "CSCO", "ABT", "ACN", "DHR",
    "WMT", "ADBE", "CRM", "NFLX", "NKE", "LIN", "TXN", "PM", "NEE", "UPS",
    "RTX", "ORCL", "HON", "QCOM", "INTU", "LOW", "AMD", "UNP", "IBM", "AMGN",
]

# ============================================================================
# Generate Sample Data
# ============================================================================

def generate_sample_overlays():
    """Generate synthetic overlay data with realistic characteristics"""
    
    print(f"Generating sample overlay files for {len(SYMBOLS)} symbols...")
    
    # Wavelet overlay: mean=0, std=0.01
    # Realistic tilt range: [-0.03, +0.03]
    wavelet_tilts = np.random.normal(0, 0.01, len(SYMBOLS))
    wavelet_tilts = np.clip(wavelet_tilts, -0.03, 0.03)
    
    # PEAD overlay: mean=0, std=0.008
    # Realistic tilt range: [-0.02, +0.02]
    pead_tilts = np.random.normal(0, 0.008, len(SYMBOLS))
    pead_tilts = np.clip(pead_tilts, -0.02, 0.02)
    
    # Add some correlation (0.2)
    correlation = 0.2
    pead_tilts = correlation * wavelet_tilts + np.sqrt(1 - correlation**2) * pead_tilts
    
    # Create DataFrames
    wavelet_df = pd.DataFrame({
        'symbol': SYMBOLS,
        'tilt_wavelet': wavelet_tilts
    })
    
    pead_df = pd.DataFrame({
        'symbol': SYMBOLS,
        'tilt_pead': pead_tilts
    })
    
    # Save to CSV
    wavelet_path = OUTPUT_DIR / "wavelet_overlay_latest.csv"
    pead_path = OUTPUT_DIR / "pead_overlay_latest.csv"
    
    wavelet_df.to_csv(wavelet_path, index=False)
    pead_df.to_csv(pead_path, index=False)
    
    print(f"\n✅ Sample overlay files generated:")
    print(f"  Wavelet: {wavelet_path} ({len(wavelet_df)} symbols)")
    print(f"  PEAD:    {pead_path} ({len(pead_df)} symbols)")
    
    # Statistics
    print(f"\n📊 Wavelet Overlay Statistics:")
    print(f"  Range: [{wavelet_tilts.min():.6f}, {wavelet_tilts.max():.6f}]")
    print(f"  Mean: {wavelet_tilts.mean():.6f}")
    print(f"  Std: {wavelet_tilts.std():.6f}")
    
    print(f"\n📊 PEAD Overlay Statistics:")
    print(f"  Range: [{pead_tilts.min():.6f}, {pead_tilts.max():.6f}]")
    print(f"  Mean: {pead_tilts.mean():.6f}")
    print(f"  Std: {pead_tilts.std():.6f}")
    
    print(f"\n💡 Note: These are synthetic data for testing only.")
    print(f"   Replace with actual overlay files from your strategies.")


if __name__ == "__main__":
    generate_sample_overlays()
