#!/usr/bin/env python3
"""
Polygon Flatfiles S3에서 티커 정보 다운로드하여 섹터 정보 추가
"""

import pandas as pd
import boto3
from pathlib import Path
import io

# Polygon S3 credentials
AWS_ACCESS_KEY_ID = "f0bc904a-9d5c-476b-af56-2cb4a2455a3e"
AWS_SECRET_ACCESS_KEY = "w7KprL4_lK7uutSH0dYGARkucXHOFXCN"
S3_ENDPOINT = "https://files.polygon.io"
BUCKET = "flatfiles"

def download_tickers_from_s3():
    """Polygon Flatfiles S3에서 최신 티커 정보 다운로드"""
    print("Connecting to Polygon Flatfiles S3...")
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=S3_ENDPOINT
    )
    
    # List available ticker files
    print("Listing available ticker files...")
    response = s3_client.list_objects_v2(
        Bucket=BUCKET,
        Prefix='us_stocks_sip/ticker_'
    )
    
    if 'Contents' not in response:
        print("No ticker files found")
        return None
    
    # Get the latest ticker file
    files = sorted([obj['Key'] for obj in response['Contents']], reverse=True)
    latest_file = files[0]
    print(f"Downloading latest ticker file: {latest_file}")
    
    # Download file
    obj = s3_client.get_object(Bucket=BUCKET, Key=latest_file)
    content = obj['Body'].read()
    
    # Parse CSV
    df = pd.read_csv(io.BytesIO(content))
    print(f"Loaded {len(df)} tickers")
    
    return df

def map_sic_to_sector(sic_description):
    """SIC description을 간단한 섹터로 매핑"""
    if pd.isna(sic_description):
        return "Unknown"
    
    desc = str(sic_description).lower()
    
    # Technology
    if any(x in desc for x in ['computer', 'software', 'electronic', 'semiconductor', 'internet', 'technology']):
        return "Technology"
    
    # Healthcare
    if any(x in desc for x in ['pharmaceutical', 'medical', 'health', 'biotechnology', 'drug']):
        return "Healthcare"
    
    # Financial
    if any(x in desc for x in ['bank', 'insurance', 'financial', 'investment', 'securities']):
        return "Financials"
    
    # Consumer
    if any(x in desc for x in ['retail', 'restaurant', 'food', 'beverage', 'consumer']):
        return "Consumer"
    
    # Industrial
    if any(x in desc for x in ['manufacturing', 'industrial', 'machinery', 'equipment', 'construction']):
        return "Industrials"
    
    # Energy
    if any(x in desc for x in ['oil', 'gas', 'energy', 'petroleum', 'coal']):
        return "Energy"
    
    # Materials
    if any(x in desc for x in ['chemical', 'mining', 'metal', 'paper', 'materials']):
        return "Materials"
    
    # Utilities
    if any(x in desc for x in ['electric', 'utility', 'water', 'gas distribution']):
        return "Utilities"
    
    # Communication
    if any(x in desc for x in ['telecommunication', 'broadcasting', 'media', 'communication']):
        return "Communication"
    
    # Real Estate
    if any(x in desc for x in ['real estate', 'reit']):
        return "Real Estate"
    
    return "Other"

def main():
    # Download tickers from S3
    tickers_df = download_tickers_from_s3()
    
    if tickers_df is None:
        print("Failed to download ticker data")
        return
    
    # Load fundamentals
    fund_path = Path("./data/fundamentals.csv")
    fund_df = pd.read_csv(fund_path)
    print(f"\nLoaded {len(fund_df)} rows from fundamentals.csv")
    
    # Get unique symbols
    symbols = fund_df["symbol"].unique()
    print(f"Found {len(symbols)} unique symbols")
    
    # Filter tickers for our symbols
    tickers_df = tickers_df[tickers_df['ticker'].isin(symbols)].copy()
    print(f"Matched {len(tickers_df)} symbols in Polygon data")
    
    # Map SIC description to sector
    tickers_df['sector'] = tickers_df['sic_description'].apply(map_sic_to_sector)
    
    # Create mapping
    sector_map = dict(zip(tickers_df['ticker'], tickers_df['sector']))
    sic_map = dict(zip(tickers_df['ticker'], tickers_df['sic_description'].fillna('Unknown')))
    
    # Add sector to fundamentals
    fund_df['sector'] = fund_df['symbol'].map(sector_map).fillna('Unknown')
    fund_df['sic_description'] = fund_df['symbol'].map(sic_map).fillna('Unknown')
    
    # Save updated fundamentals
    fund_df.to_csv(fund_path, index=False)
    print(f"\n✅ Updated fundamentals.csv with sector info")
    
    # Summary
    print("\nSector distribution:")
    sector_counts = fund_df.groupby('sector')['symbol'].nunique().sort_values(ascending=False)
    print(sector_counts)
    
    print("\nSample mappings:")
    sample = fund_df[['symbol', 'sector', 'sic_description']].drop_duplicates().head(10)
    print(sample.to_string(index=False))

if __name__ == "__main__":
    main()
