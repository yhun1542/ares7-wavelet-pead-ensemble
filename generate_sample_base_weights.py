#!/usr/bin/env python3
"""
Generate Sample ARES7 Base Weights for Testing

이 스크립트는 테스트용 샘플 base weights를 생성합니다.
실제 ARES7 base weights가 준비되면 이 스크립트는 사용하지 않아도 됩니다.

실행:
  python3 generate_sample_base_weights.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

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

def generate_sample_base_weights():
    """Generate synthetic base weights with realistic characteristics"""
    
    print(f"Generating sample ARES7 base weights for {len(SYMBOLS)} symbols...")
    
    # Generate random weights (uniform distribution)
    weights = np.random.uniform(0.005, 0.03, len(SYMBOLS))
    
    # Normalize to sum to 1.0
    weights = weights / weights.sum()
    
    # Create DataFrame
    df = pd.DataFrame({
        'symbol': SYMBOLS,
        'weight': weights
    })
    
    # Sort by weight descending
    df = df.sort_values('weight', ascending=False).reset_index(drop=True)
    
    # Save to CSV
    output_path = DATA_DIR / "ares7_base_weights.csv"
    df.to_csv(output_path, index=False)
    
    print(f"\n✅ Sample ARES7 base weights generated:")
    print(f"  File: {output_path}")
    print(f"  Symbols: {len(df)}")
    print(f"  Total weight: {df['weight'].sum():.6f}")
    
    # Statistics
    print(f"\n📊 Base Weights Statistics:")
    print(f"  Mean: {df['weight'].mean():.6f}")
    print(f"  Std: {df['weight'].std():.6f}")
    print(f"  Min: {df['weight'].min():.6f}")
    print(f"  Max: {df['weight'].max():.6f}")
    
    # Sample output
    print(f"\nSample output (first 10 rows):")
    print(df.head(10).to_string(index=False))
    
    print(f"\n💡 Note: These are synthetic data for testing only.")
    print(f"   Replace with actual ARES7 base weights from your system.")


if __name__ == "__main__":
    generate_sample_base_weights()
