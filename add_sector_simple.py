#!/usr/bin/env python3
"""
간단한 섹터 매핑으로 fundamentals.csv에 섹터 정보 추가
"""

import pandas as pd
from pathlib import Path

# 주요 100개 종목의 섹터 매핑 (일반적인 분류)
SECTOR_MAP = {
    # Technology
    'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'GOOG': 'Technology',
    'NVDA': 'Technology', 'META': 'Technology', 'AVGO': 'Technology', 'ORCL': 'Technology',
    'CSCO': 'Technology', 'ADBE': 'Technology', 'CRM': 'Technology', 'ACN': 'Technology',
    'AMD': 'Technology', 'IBM': 'Technology', 'INTC': 'Technology', 'QCOM': 'Technology',
    'TXN': 'Technology', 'INTU': 'Technology', 'NOW': 'Technology', 'AMAT': 'Technology',
    
    # Healthcare
    'LLY': 'Healthcare', 'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'ABBV': 'Healthcare',
    'MRK': 'Healthcare', 'ABT': 'Healthcare', 'TMO': 'Healthcare', 'PFE': 'Healthcare',
    'DHR': 'Healthcare', 'AMGN': 'Healthcare', 'BMY': 'Healthcare', 'GILD': 'Healthcare',
    'CVS': 'Healthcare', 'CI': 'Healthcare', 'ELV': 'Healthcare', 'ISRG': 'Healthcare',
    
    # Financials
    'BRK.B': 'Financials', 'JPM': 'Financials', 'V': 'Financials', 'MA': 'Financials',
    'BAC': 'Financials', 'WFC': 'Financials', 'GS': 'Financials', 'MS': 'Financials',
    'AXP': 'Financials', 'BLK': 'Financials', 'C': 'Financials', 'SCHW': 'Financials',
    'CB': 'Financials', 'PGR': 'Financials', 'MMC': 'Financials', 'SPGI': 'Financials',
    
    # Consumer Discretionary
    'AMZN': 'Consumer Discretionary', 'TSLA': 'Consumer Discretionary', 'HD': 'Consumer Discretionary',
    'MCD': 'Consumer Discretionary', 'NKE': 'Consumer Discretionary', 'LOW': 'Consumer Discretionary',
    'SBUX': 'Consumer Discretionary', 'TJX': 'Consumer Discretionary', 'BKNG': 'Consumer Discretionary',
    
    # Consumer Staples
    'WMT': 'Consumer Staples', 'PG': 'Consumer Staples', 'KO': 'Consumer Staples',
    'PEP': 'Consumer Staples', 'COST': 'Consumer Staples', 'PM': 'Consumer Staples',
    'MO': 'Consumer Staples', 'CL': 'Consumer Staples', 'MDLZ': 'Consumer Staples',
    
    # Industrials
    'CAT': 'Industrials', 'BA': 'Industrials', 'HON': 'Industrials', 'UNP': 'Industrials',
    'RTX': 'Industrials', 'GE': 'Industrials', 'LMT': 'Industrials', 'DE': 'Industrials',
    'MMM': 'Industrials', 'UPS': 'Industrials', 'FDX': 'Industrials', 'WM': 'Industrials',
    
    # Energy
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'SLB': 'Energy',
    'EOG': 'Energy', 'MPC': 'Energy', 'PSX': 'Energy', 'VLO': 'Energy',
    
    # Materials
    'LIN': 'Materials', 'APD': 'Materials', 'SHW': 'Materials', 'FCX': 'Materials',
    'NEM': 'Materials', 'ECL': 'Materials', 'DD': 'Materials',
    
    # Utilities
    'NEE': 'Utilities', 'DUK': 'Utilities', 'SO': 'Utilities', 'D': 'Utilities',
    'AEP': 'Utilities', 'EXC': 'Utilities', 'SRE': 'Utilities',
    
    # Communication Services
    'NFLX': 'Communication Services', 'DIS': 'Communication Services', 'CMCSA': 'Communication Services',
    'T': 'Communication Services', 'VZ': 'Communication Services', 'TMUS': 'Communication Services',
    
    # Real Estate
    'PLD': 'Real Estate', 'AMT': 'Real Estate', 'CCI': 'Real Estate', 'EQIX': 'Real Estate',
}

def main():
    # Load fundamentals
    fund_path = Path("./data/fundamentals.csv")
    fund_df = pd.read_csv(fund_path)
    
    print(f"Loaded {len(fund_df)} rows from fundamentals.csv")
    
    # Get unique symbols
    symbols = fund_df["symbol"].unique()
    print(f"Found {len(symbols)} unique symbols")
    
    # Add sector
    fund_df['sector'] = fund_df['symbol'].map(SECTOR_MAP).fillna('Other')
    
    # Save updated fundamentals
    fund_df.to_csv(fund_path, index=False)
    print(f"\n✅ Updated fundamentals.csv with sector info")
    
    # Summary
    print("\nSector distribution:")
    sector_counts = fund_df.groupby('sector')['symbol'].nunique().sort_values(ascending=False)
    print(sector_counts)
    
    print("\nSample mappings:")
    sample = fund_df[['symbol', 'sector']].drop_duplicates().head(20)
    print(sample.to_string(index=False))
    
    # Check unmapped
    unmapped = fund_df[fund_df['sector'] == 'Other']['symbol'].unique()
    if len(unmapped) > 0:
        print(f"\n⚠️  {len(unmapped)} symbols mapped to 'Other': {list(unmapped[:10])}")

if __name__ == "__main__":
    main()
