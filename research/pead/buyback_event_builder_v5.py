#!/usr/bin/env python3
"""
Buyback Event Builder v5 - Direct EDGAR Download + Text Parsing
Based on recommendations from Gemini and Grok AI models

Approach:
1. Use SEC-API to get 8-K filing metadata (accession number, CIK, date)
2. Download full-text from EDGAR directly
3. Parse text with regex to extract buyback information
4. Store results in CSV format

Expected Success Rate: 70-90%
Execution Time: 3-8 hours for SP100 × 10 years
"""

import os
import sys
import time
import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
from sec_api import QueryApi
from datetime import datetime
import json

# Configuration
SEC_API_KEY = os.environ.get('SEC_API_KEY', 'c7e1d8f6b3e5a0c4d2f9e8b7a6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7')
DATA_DIR = '/home/ubuntu/ares7-ensemble/data'
UNIVERSE_FILE = f'{DATA_DIR}/universe/sp100.csv'
OUTPUT_FILE = f'{DATA_DIR}/buyback/buyback_events_v5.csv'
LOG_FILE = f'{DATA_DIR}/buyback/extraction_log_v5.json'

# Initialize SEC-API
query_api = QueryApi(api_key=SEC_API_KEY)

# Keywords for buyback identification
KEYWORDS = [
    r'share repurchase',
    r'stock repurchase',
    r'buyback',
    r'repurchase program',
    r'share buyback',
    r'stock buyback',
    r'repurchase authorization'
]

# Amount patterns (more comprehensive)
AMOUNT_PATTERNS = [
    # $X million/billion
    r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion)',
    # repurchase up to $X million/billion
    r'repurchase\s+(?:up\s+to\s+)?\$\s*(\d+(?:\.\d+)?)\s*(million|billion)',
    # authorized $X million/billion ... repurchase
    r'authorized.*?\$\s*(\d+(?:\.\d+)?)\s*(million|billion).*?repurchase',
    # repurchase program of $X million/billion
    r'repurchase\s+program\s+of\s+\$\s*(\d+(?:\.\d+)?)\s*(million|billion)',
    # $X million/billion share repurchase
    r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion).*?share\s+repurchase',
]

# Share count patterns
SHARE_PATTERNS = [
    r'repurchase\s+(?:up\s+to\s+)?(\d+(?:,\d+)*(?:\.\d+)?)\s*million\s+shares',
    r'repurchase\s+(\d+(?:,\d+)*)\s+shares',
    r'buyback\s+(?:of\s+)?(\d+(?:,\d+)*(?:\.\d+)?)\s*million\s+shares',
]


def get_sp100_tickers():
    """Load SP100 ticker list"""
    if not os.path.exists(UNIVERSE_FILE):
        print(f"❌ Universe file not found: {UNIVERSE_FILE}")
        sys.exit(1)
    
    df = pd.read_csv(UNIVERSE_FILE)
    tickers = df['symbol'].tolist()
    print(f"✅ Loaded {len(tickers)} tickers from SP100")
    return tickers


def get_8k_filings(ticker, start_year=2015, end_year=2025):
    """
    Get all 8-K filings for a ticker within date range
    
    Returns:
        List of dicts with keys: ticker, date, accessionNo, cik, url
    """
    query = {
        "query": f'ticker:{ticker} AND formType:"8-K"',
        "from": "0",
        "size": "200",  # Max per request
        "sort": [{"filedAt": {"order": "desc"}}]
    }
    
    filings = []
    try:
        response = query_api.get_filings(query)
        
        if 'filings' not in response:
            print(f"  ⚠️  No filings found for {ticker}")
            return filings
        
        for filing in response['filings']:
            filed_at = filing['filedAt'][:10]  # YYYY-MM-DD
            year = int(filed_at[:4])
            
            if start_year <= year <= end_year:
                filings.append({
                    'ticker': ticker,
                    'date': filed_at,
                    'accessionNo': filing['accessionNo'],
                    'cik': filing['cik'],
                    'url': filing.get('linkToFilingDetails', '')
                })
        
        print(f"  ✅ Found {len(filings)} 8-K filings for {ticker} ({start_year}-{end_year})")
        
    except Exception as e:
        print(f"  ❌ Error fetching {ticker}: {e}")
    
    return filings


def download_edgar_text(cik, accession_no, max_retries=3):
    """
    Download full text from EDGAR
    
    Args:
        cik: Company CIK number
        accession_no: Accession number (format: 0000000000-00-000000)
        max_retries: Maximum number of retry attempts
    
    Returns:
        Full text content or None if failed
    """
    # Remove hyphens from accession number for directory name
    acc_clean = accession_no.replace('-', '')
    
    # EDGAR URL format
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{accession_no}.txt"
    
    # SEC requires User-Agent header
    headers = {
        'User-Agent': 'ARES Research ares@research.com',
        'Accept-Encoding': 'gzip, deflate',
        'Host': 'www.sec.gov'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Try alternative URL format
                url_alt = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{accession_no}-index.htm"
                try:
                    response = requests.get(url_alt, headers=headers, timeout=15)
                    response.raise_for_status()
                    return response.text
                except:
                    pass
            
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"    ⚠️  HTTP {e.response.status_code} for {accession_no}")
                return None
        
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"    ⚠️  Download error for {accession_no}: {e}")
                return None
    
    return None


def extract_buyback_info(text):
    """
    Extract buyback information from filing text
    
    Returns:
        Dict with keys: has_buyback, amount, shares, confidence
        Or None if no buyback detected
    """
    if not text:
        return None
    
    # Preprocess text
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text(separator=' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text_lower = text.lower()
    
    # Check for buyback keywords
    keyword_matches = []
    for keyword in KEYWORDS:
        if re.search(keyword, text_lower):
            keyword_matches.append(keyword)
    
    if not keyword_matches:
        return None
    
    # Extract dollar amounts
    amounts = []
    for pattern in AMOUNT_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            try:
                value = float(match[0])
                unit = match[1]
                
                if unit == 'billion':
                    value *= 1e9
                elif unit == 'million':
                    value *= 1e6
                
                amounts.append(value)
            except (ValueError, IndexError):
                continue
    
    # Extract share counts
    shares = []
    for pattern in SHARE_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            try:
                # Remove commas and convert
                share_str = match.replace(',', '')
                share_count = float(share_str)
                
                # If pattern includes "million", multiply
                if 'million' in pattern:
                    share_count *= 1e6
                
                shares.append(share_count)
            except (ValueError, AttributeError):
                continue
    
    # Determine confidence level
    confidence = 'low'
    if amounts and shares:
        confidence = 'high'
    elif amounts or shares:
        confidence = 'medium'
    
    # Return extracted information
    return {
        'has_buyback': True,
        'amount': max(amounts) if amounts else None,
        'shares': max(shares) if shares else None,
        'confidence': confidence,
        'keyword_count': len(keyword_matches)
    }


def main():
    """Main execution function"""
    print("=" * 80)
    print("Buyback Event Builder v5 - Direct EDGAR Download + Text Parsing")
    print("=" * 80)
    print()
    
    # Load tickers
    tickers = get_sp100_tickers()
    
    # Configuration
    start_year = 2015
    end_year = 2025
    
    print(f"📅 Date Range: {start_year}-{end_year}")
    print(f"🎯 Target: {len(tickers)} tickers")
    print()
    
    # Storage
    all_events = []
    extraction_log = {
        'start_time': datetime.now().isoformat(),
        'tickers_processed': 0,
        'filings_checked': 0,
        'buybacks_found': 0,
        'errors': []
    }
    
    # Process each ticker
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Processing {ticker}...")
        
        try:
            # Get 8-K filings
            filings = get_8k_filings(ticker, start_year, end_year)
            extraction_log['filings_checked'] += len(filings)
            
            # Process each filing
            for filing in filings:
                # Download full text
                text = download_edgar_text(filing['cik'], filing['accessionNo'])
                
                if text:
                    # Extract buyback info
                    buyback_info = extract_buyback_info(text)
                    
                    if buyback_info and buyback_info['has_buyback']:
                        event = {
                            'date': filing['date'],
                            'ticker': filing['ticker'],
                            'buyback_amount': buyback_info['amount'],
                            'share_count': buyback_info['shares'],
                            'confidence': buyback_info['confidence'],
                            'keyword_count': buyback_info['keyword_count'],
                            'accessionNo': filing['accessionNo'],
                            'url': filing['url']
                        }
                        all_events.append(event)
                        extraction_log['buybacks_found'] += 1
                        
                        print(f"    ✅ BUYBACK FOUND: {filing['date']} - ${buyback_info['amount']:,.0f}" if buyback_info['amount'] else f"    ✅ BUYBACK FOUND: {filing['date']} (no amount)")
                
                # Rate limiting (SEC allows 10 requests/second)
                time.sleep(0.15)
            
            extraction_log['tickers_processed'] += 1
            
        except Exception as e:
            error_msg = f"Error processing {ticker}: {e}"
            print(f"  ❌ {error_msg}")
            extraction_log['errors'].append(error_msg)
        
        # Save intermediate results every 10 tickers
        if i % 10 == 0:
            df_temp = pd.DataFrame(all_events)
            df_temp.to_csv(OUTPUT_FILE.replace('.csv', '_temp.csv'), index=False)
            print(f"  💾 Intermediate save: {len(all_events)} events")
    
    # Final save
    print()
    print("=" * 80)
    print("Saving results...")
    print("=" * 80)
    
    df = pd.DataFrame(all_events)
    df.to_csv(OUTPUT_FILE, index=False)
    
    # Save extraction log
    extraction_log['end_time'] = datetime.now().isoformat()
    extraction_log['total_events'] = len(all_events)
    
    with open(LOG_FILE, 'w') as f:
        json.dump(extraction_log, f, indent=2)
    
    # Summary statistics
    print()
    print("📊 EXTRACTION SUMMARY")
    print("-" * 80)
    print(f"Tickers Processed:    {extraction_log['tickers_processed']}")
    print(f"Filings Checked:      {extraction_log['filings_checked']}")
    print(f"Buybacks Found:       {extraction_log['buybacks_found']}")
    print(f"Errors:               {len(extraction_log['errors'])}")
    print()
    
    if len(df) > 0:
        print("📈 EVENT STATISTICS")
        print("-" * 80)
        print(f"Total Events:         {len(df)}")
        print(f"Date Range:           {df['date'].min()} to {df['date'].max()}")
        print(f"Unique Tickers:       {df['ticker'].nunique()}")
        print()
        print("Confidence Distribution:")
        print(df['confidence'].value_counts())
        print()
        print("Events with Amount:   ", df['buyback_amount'].notna().sum())
        print("Events with Shares:   ", df['share_count'].notna().sum())
        print()
        
        if df['buyback_amount'].notna().sum() > 0:
            print("Amount Statistics (USD):")
            print(f"  Mean:   ${df['buyback_amount'].mean():,.0f}")
            print(f"  Median: ${df['buyback_amount'].median():,.0f}")
            print(f"  Min:    ${df['buyback_amount'].min():,.0f}")
            print(f"  Max:    ${df['buyback_amount'].max():,.0f}")
    
    print()
    print(f"✅ Results saved to: {OUTPUT_FILE}")
    print(f"✅ Log saved to: {LOG_FILE}")
    print()


if __name__ == "__main__":
    main()
