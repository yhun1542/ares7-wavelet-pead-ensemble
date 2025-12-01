#!/usr/bin/env python3
"""
Buyback Event Builder v6 - Direct EDGAR Access (No SEC-API)
Based on recommendations from Gemini and Grok AI models

Approach:
1. Use SEC EDGAR Company Search to get CIK
2. Use SEC EDGAR RSS feeds / index files to find 8-K filings
3. Download full-text from EDGAR directly
4. Parse text with regex to extract buyback information
5. Store results in CSV format

No API key required - completely free and open access
Expected Success Rate: 70-90%
"""

import os
import sys
import time
import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json
from urllib.parse import urljoin

# Configuration
DATA_DIR = '/home/ubuntu/ares7-ensemble/data'
UNIVERSE_FILE = f'{DATA_DIR}/universe/sp100.csv'
OUTPUT_FILE = f'{DATA_DIR}/buyback/buyback_events_v6.csv'
LOG_FILE = f'{DATA_DIR}/buyback/extraction_log_v6.json'

# SEC EDGAR base URL
EDGAR_BASE = 'https://www.sec.gov'

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

# Amount patterns
AMOUNT_PATTERNS = [
    r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion)',
    r'repurchase\s+(?:up\s+to\s+)?\$\s*(\d+(?:\.\d+)?)\s*(million|billion)',
    r'authorized.*?\$\s*(\d+(?:\.\d+)?)\s*(million|billion).*?repurchase',
    r'repurchase\s+program\s+of\s+\$\s*(\d+(?:\.\d+)?)\s*(million|billion)',
    r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion).*?share\s+repurchase',
]

# Share count patterns
SHARE_PATTERNS = [
    r'repurchase\s+(?:up\s+to\s+)?(\d+(?:,\d+)*(?:\.\d+)?)\s*million\s+shares',
    r'repurchase\s+(\d+(?:,\d+)*)\s+shares',
    r'buyback\s+(?:of\s+)?(\d+(?:,\d+)*(?:\.\d+)?)\s*million\s+shares',
]

# User-Agent header (required by SEC)
HEADERS = {
    'User-Agent': 'ARES Research ares@research.com',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.sec.gov'
}


def get_sp100_tickers():
    """Load SP100 ticker list"""
    if not os.path.exists(UNIVERSE_FILE):
        print(f"❌ Universe file not found: {UNIVERSE_FILE}")
        sys.exit(1)
    
    df = pd.read_csv(UNIVERSE_FILE)
    tickers = df['symbol'].tolist()
    print(f"✅ Loaded {len(tickers)} tickers from SP100")
    return tickers


def get_cik_from_ticker(ticker):
    """
    Get CIK number from ticker symbol using SEC company search
    
    Returns:
        CIK as string (zero-padded to 10 digits) or None
    """
    # SEC company tickers JSON (updated daily)
    url = 'https://www.sec.gov/files/company_tickers.json'
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Search for ticker
        for entry in data.values():
            if entry['ticker'].upper() == ticker.upper():
                cik = str(entry['cik_str']).zfill(10)
                return cik
        
        print(f"  ⚠️  CIK not found for {ticker}")
        return None
    
    except Exception as e:
        print(f"  ⚠️  Error getting CIK for {ticker}: {e}")
        return None


def get_8k_filings_from_edgar(ticker, cik, start_year=2015, end_year=2025):
    """
    Get 8-K filings directly from SEC EDGAR
    
    Uses the company filings index page
    
    Returns:
        List of dicts with keys: ticker, date, accessionNo, cik, url
    """
    filings = []
    
    # EDGAR company filings URL
    # Format: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=8-K&dateb=&owner=exclude&count=100
    base_url = f'{EDGAR_BASE}/cgi-bin/browse-edgar'
    
    params = {
        'action': 'getcompany',
        'CIK': cik,
        'type': '8-K',
        'dateb': '',  # End date (empty = today)
        'owner': 'exclude',
        'count': '100',  # Max results per page
        'search_text': ''
    }
    
    try:
        response = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the filings table
        table = soup.find('table', {'class': 'tableFile2'})
        if not table:
            print(f"  ⚠️  No filings table found for {ticker}")
            return filings
        
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4:
                continue
            
            # Extract filing information
            filing_type = cols[0].text.strip()
            filing_date = cols[3].text.strip()  # Format: YYYY-MM-DD
            
            # Check date range
            try:
                year = int(filing_date[:4])
                if not (start_year <= year <= end_year):
                    continue
            except:
                continue
            
            # Extract accession number from text
            # Format: "Acc-no: 0000320193-25-000077"
            text = cols[2].text
            match = re.search(r'Acc-no:\s*([\d-]+)', text)
            if not match:
                continue
            
            accession_no = match.group(1)
            
            # Get document link for URL
            doc_link = cols[1].find('a', {'id': 'documentsbutton'})
            if doc_link:
                doc_url = urljoin(EDGAR_BASE, doc_link['href'])
            else:
                doc_url = f"{EDGAR_BASE}/cgi-bin/viewer?action=view&cik={cik}&accession_number={accession_no}"
            
            filings.append({
                'ticker': ticker,
                'date': filing_date,
                'accessionNo': accession_no,
                'cik': cik,
                'url': doc_url
            })
        
        print(f"  ✅ Found {len(filings)} 8-K filings for {ticker} ({start_year}-{end_year})")
        
    except Exception as e:
        print(f"  ❌ Error fetching filings for {ticker}: {e}")
    
    return filings


def download_edgar_text(cik, accession_no, max_retries=3):
    """
    Download full text from EDGAR
    
    Args:
        cik: Company CIK number (10 digits)
        accession_no: Accession number (format: 0000000000-00-000000)
        max_retries: Maximum number of retry attempts
    
    Returns:
        Full text content or None if failed
    """
    # Remove hyphens from accession number for directory name
    acc_clean = accession_no.replace('-', '')
    
    # EDGAR URL format
    url = f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{acc_clean}/{accession_no}.txt"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            return response.text
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Try alternative formats
                alternatives = [
                    f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{acc_clean}/{accession_no}-index.htm",
                    f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{acc_clean}/primary_doc.html",
                ]
                
                for alt_url in alternatives:
                    try:
                        response = requests.get(alt_url, headers=HEADERS, timeout=15)
                        response.raise_for_status()
                        return response.text
                    except:
                        continue
            
            if attempt < max_retries - 1:
                time.sleep(1)
        
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
    
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
    
    # Preprocess text with error handling
    try:
        soup = BeautifulSoup(text, 'lxml')
        text = soup.get_text(separator=' ')
    except:
        # Fallback: use raw text if parsing fails
        pass
    
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
                share_str = match.replace(',', '')
                share_count = float(share_str)
                
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
    print("Buyback Event Builder v6 - Direct EDGAR Access (No API Key)")
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
            # Get CIK
            cik = get_cik_from_ticker(ticker)
            if not cik:
                extraction_log['errors'].append(f"CIK not found for {ticker}")
                continue
            
            print(f"  CIK: {cik}")
            
            # Get 8-K filings
            filings = get_8k_filings_from_edgar(ticker, cik, start_year, end_year)
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
                        
                        amount_str = f"${buyback_info['amount']:,.0f}" if buyback_info['amount'] else "no amount"
                        print(f"    ✅ BUYBACK: {filing['date']} - {amount_str}")
                
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
        print(f"Events with Amount:   {df['buyback_amount'].notna().sum()}")
        print(f"Events with Shares:   {df['share_count'].notna().sum()}")
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
