#!/usr/bin/env python3
"""
Polygon API로 섹터 정보를 다운로드하여 fundamentals.csv에 추가
"""

import pandas as pd
import requests
import time
from pathlib import Path

API_KEY = "fU0WLG3dSetGMOyGxe1FZqt_y8OfhQlV"

def get_ticker_details(symbol):
    """Polygon API로 티커 상세 정보 가져오기"""
    url = f"https://api.polygon.io/v3/reference/tickers/{symbol}"
    params = {"apiKey": API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "results" in data:
                results = data["results"]
                sector = results.get("sic_description", "Unknown")
                industry = results.get("industry", "Unknown")
                return sector, industry
        return "Unknown", "Unknown"
    except Exception as e:
        print(f"  Error for {symbol}: {e}")
        return "Unknown", "Unknown"

def main():
    # Load fundamentals
    fund_path = Path("./data/fundamentals.csv")
    fund_df = pd.read_csv(fund_path)
    
    print(f"Loaded {len(fund_df)} rows from fundamentals.csv")
    
    # Get unique symbols
    symbols = fund_df["symbol"].unique()
    print(f"Found {len(symbols)} unique symbols")
    
    # Download sector info
    sector_map = {}
    industry_map = {}
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] Fetching {symbol}...", end=" ")
        sector, industry = get_ticker_details(symbol)
        sector_map[symbol] = sector
        industry_map[symbol] = industry
        print(f"Sector: {sector}, Industry: {industry}")
        
        # Small delay to avoid overwhelming API
        time.sleep(0.1)
    
    # Add sector and industry to fundamentals
    fund_df["sector"] = fund_df["symbol"].map(sector_map)
    fund_df["industry"] = fund_df["symbol"].map(industry_map)
    
    # Save updated fundamentals
    fund_df.to_csv(fund_path, index=False)
    print(f"\n✅ Updated fundamentals.csv with sector and industry info")
    
    # Summary
    print("\nSector distribution:")
    print(fund_df.groupby("sector")["symbol"].nunique().sort_values(ascending=False))

if __name__ == "__main__":
    main()
