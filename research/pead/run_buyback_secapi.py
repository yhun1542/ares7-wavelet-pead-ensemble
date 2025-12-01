#!/usr/bin/env python3
"""
SEC-API 기반 전체 SP100 Buyback 추출
"""

import sys
from pathlib import Path
import os

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from sec_api import QueryApi
import re
import time
from datetime import datetime, timedelta

# SEC-API 키 설정
SEC_API_KEY = os.getenv('SEC_API_KEY', 'c2c08a95c67793b5a8bbba1e51611ed466900124e70c0615badefea2c6d429f9')

queryApi = QueryApi(api_key=SEC_API_KEY)
# ExtractorApi not needed - we'll download text directly

# Get SP100 tickers (limit to 20 for testing)
px_long = pd.read_csv(project_root / "data" / "prices.csv")
tickers = sorted(px_long['symbol'].unique())[:20]

print(f"Total tickers to process: {len(tickers)}")
print(f"Using SEC-API with key: {SEC_API_KEY[:10]}...")

def extract_buyback_from_ticker(ticker, start_date='2015-01-01', end_date='2024-12-31'):
    """Extract buyback announcements using SEC-API"""
    results = []
    
    try:
        # Query 8-K filings
        query = {
            "query": f'ticker:{ticker} AND formType:"8-K" AND filedAt:[{start_date} TO {end_date}]',
            "from": "0",
            "size": "100",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        response = queryApi.get_filings(query)
        filings = response.get('filings', [])
        
        print(f"  {ticker}: Found {len(filings)} 8-K filings")
        
        for filing in filings:
            filing_date = filing.get('filedAt', '')[:10]  # YYYY-MM-DD
            accession_no = filing.get('accessionNo', '')
            filing_url = filing.get('linkToFilingDetails', '')
            
            # Get filing text
            try:
                text_url = filing.get('linkToTxt', '')
                if not text_url:
                    continue
                
                # Download full text directly with proper User-Agent
                import requests
                headers = {
                    'User-Agent': 'Seohan Corp Research yhjun@seohancorp.com',
                    'Accept-Encoding': 'gzip, deflate',
                    'Host': 'www.sec.gov'
                }
                response = requests.get(text_url, headers=headers, timeout=30)
                section_text = response.text
                
                # Search for buyback keywords
                buyback_keywords = [
                    r'share\s+(?:repurchase|buyback)',
                    r'stock\s+(?:repurchase|buyback)',
                    r'repurchase\s+program',
                    r'buyback\s+program'
                ]
                
                found_keyword = False
                keyword_count = 0
                for pattern in buyback_keywords:
                    if re.search(pattern, section_text, re.IGNORECASE):
                        found_keyword = True
                        keyword_count += len(re.findall(pattern, section_text, re.IGNORECASE))
                
                if not found_keyword:
                    continue
                
                # Extract buyback amount
                amount_patterns = [
                    r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B)',
                    r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|M)',
                    r'([\d,]+(?:\.\d+)?)\s*billion\s*dollar',
                    r'([\d,]+(?:\.\d+)?)\s*million\s*dollar'
                ]
                
                amounts = []
                for pattern in amount_patterns:
                    matches = re.findall(pattern, section_text, re.IGNORECASE)
                    for match in matches:
                        amount_str = match.replace(',', '')
                        try:
                            amount = float(amount_str)
                            if 'billion' in pattern.lower() or 'B' in pattern:
                                amount *= 1e9
                            elif 'million' in pattern.lower() or 'M' in pattern:
                                amount *= 1e6
                            amounts.append(amount)
                        except:
                            pass
                
                if amounts:
                    # Use the largest amount (most likely the program size)
                    buyback_amount = max(amounts)
                    
                    confidence = 'high' if keyword_count >= 3 else 'medium' if keyword_count >= 2 else 'low'
                    
                    results.append({
                        'date': filing_date,
                        'ticker': ticker,
                        'buyback_amount': buyback_amount,
                        'share_count': None,
                        'confidence': confidence,
                        'keyword_count': keyword_count,
                        'accessionNo': accession_no,
                        'url': filing_url
                    })
                
                time.sleep(1.0)  # Rate limiting (SEC requires 1 req/sec)
                
            except Exception as e:
                print(f"    Error processing filing {accession_no}: {e}")
                continue
        
        print(f"  {ticker}: Found {len(results)} buyback events")
        
    except Exception as e:
        print(f"  Error fetching filings for {ticker}: {e}")
    
    return results

# Process all tickers
all_results = []
start_time = time.time()

for i, ticker in enumerate(tickers, 1):
    print(f"\n[{i}/{len(tickers)}] Processing {ticker}...")
    
    results = extract_buyback_from_ticker(ticker)
    all_results.extend(results)
    
    # Progress update
    if i % 10 == 0:
        elapsed = time.time() - start_time
        avg_time = elapsed / i
        remaining = avg_time * (len(tickers) - i)
        print(f"\nProgress: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%)")
        print(f"Elapsed: {elapsed/60:.1f}min, Remaining: {remaining/60:.1f}min")
        print(f"Total events found: {len(all_results)}")

# Save results
df = pd.DataFrame(all_results)
output_path = project_root / "data" / "buyback" / "buyback_events_sp100_secapi.csv"
df.to_csv(output_path, index=False)

print(f"\n{'='*80}")
print(f"Buyback extraction completed!")
print(f"Total events: {len(df)}")
print(f"Tickers with events: {df['ticker'].nunique()}")
print(f"Output: {output_path}")
print(f"{'='*80}")
