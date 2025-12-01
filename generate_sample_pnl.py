#!/usr/bin/env python3
"""
Generate Sample PnL Data for Testing Wavelet+PEAD Optimizer

이 스크립트는 테스트용 샘플 PnL 데이터를 생성합니다.
실제 데이터가 준비되면 이 스크립트는 사용하지 않아도 됩니다.

실행:
  python3 generate_sample_pnl.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR_WAVELET = BASE_DIR / "research" / "wavelet"
OUTPUT_DIR_PEAD = BASE_DIR / "research" / "pead"
OUTPUT_DIR_BASE = BASE_DIR / "research" / "base"

# Create directories
OUTPUT_DIR_WAVELET.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR_PEAD.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR_BASE.mkdir(parents=True, exist_ok=True)

# Date range
START_DATE = "2016-01-01"
END_DATE = "2025-11-30"

# ============================================================================
# Generate Sample Data
# ============================================================================

def generate_sample_pnl():
    """Generate synthetic PnL data with realistic characteristics"""
    
    # Generate date range (business days only)
    dates = pd.bdate_range(start=START_DATE, end=END_DATE)
    n_days = len(dates)
    
    print(f"Generating sample PnL data for {n_days} business days...")
    
    # Wavelet PnL: Sharpe ~0.6-0.7
    # Mean daily return: 0.05% (12.6% annualized)
    # Daily vol: 0.8% (12.7% annualized)
    wavelet_mean = 0.0005
    wavelet_vol = 0.008
    wavelet_pnl = np.random.normal(wavelet_mean, wavelet_vol, n_days)
    
    # PEAD PnL: Sharpe ~0.5
    # Mean daily return: 0.03% (7.6% annualized)
    # Daily vol: 0.6% (9.5% annualized)
    pead_mean = 0.0003
    pead_vol = 0.006
    pead_pnl = np.random.normal(pead_mean, pead_vol, n_days)
    
    # Add some correlation (0.3)
    correlation = 0.3
    pead_pnl = correlation * wavelet_pnl + np.sqrt(1 - correlation**2) * pead_pnl
    
    # Base portfolio: Sharpe ~0.9
    # Mean daily return: 0.06% (15.1% annualized)
    # Daily vol: 0.7% (11.1% annualized)
    base_mean = 0.0006
    base_vol = 0.007
    base_pnl = np.random.normal(base_mean, base_vol, n_days)
    
    # Create DataFrames
    wavelet_df = pd.DataFrame({
        'date': dates,
        'pnl': wavelet_pnl
    })
    
    pead_df = pd.DataFrame({
        'date': dates,
        'pnl': pead_pnl
    })
    
    base_df = pd.DataFrame({
        'date': dates,
        'pnl': base_pnl
    })
    
    # Save to CSV
    wavelet_path = OUTPUT_DIR_WAVELET / "wavelet_pnl.csv"
    pead_path = OUTPUT_DIR_PEAD / "pead_pnl.csv"
    base_path = OUTPUT_DIR_BASE / "base_pnl.csv"
    
    wavelet_df.to_csv(wavelet_path, index=False)
    pead_df.to_csv(pead_path, index=False)
    base_df.to_csv(base_path, index=False)
    
    print(f"\n✅ Sample PnL data generated:")
    print(f"  Wavelet: {wavelet_path} ({len(wavelet_df)} days)")
    print(f"  PEAD:    {pead_path} ({len(pead_df)} days)")
    print(f"  Base:    {base_path} ({len(base_df)} days)")
    
    # Calculate expected Sharpe ratios
    wavelet_sharpe = wavelet_mean / wavelet_vol * np.sqrt(252)
    pead_sharpe = pead_mean / pead_vol * np.sqrt(252)
    base_sharpe = base_mean / base_vol * np.sqrt(252)
    
    print(f"\n📊 Expected Sharpe Ratios (theoretical):")
    print(f"  Wavelet: {wavelet_sharpe:.3f}")
    print(f"  PEAD:    {pead_sharpe:.3f}")
    print(f"  Base:    {base_sharpe:.3f}")
    
    print(f"\n💡 Note: These are synthetic data for testing only.")
    print(f"   Replace with actual PnL data from your backtests.")


if __name__ == "__main__":
    generate_sample_pnl()
