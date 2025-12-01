#!/usr/bin/env python3
"""
전체 SP100 Buyback 추출
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from existing v6 script
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime

# Get SP100 tickers
px_long = pd.read_csv(project_root / "data" / "prices.csv")
tickers = sorted(px_long['symbol'].unique())

print(f"Total tickers to process: {len(tickers)}")
print(f"Tickers: {tickers}")

# Buyback extraction function (from v6)
def extract_buyback_from_8k(ticker, max_filings=100):
    """Extract buyback announcements from 8-K filings"""
    results = []
    
    # SEC EDGAR search URL
    base_url = f"https://www.sec.gov/cgi-bin/browse-edgar"
    params = {
        'action': 'getcompany',
        'CIK': ticker,
        'type': '8-K',
        'dateb': '',
        'owner': 'exclude',
        'count': max_filings,
        'search_text': ''
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0; +http://example.com/bot)'
    }
    
    try:
        # Get list of 8-K filings
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Find all filing links
        rows = soup.find_all('tr')
        
        filing_count = 0
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 4:
                continue
            
            # Check if it's an 8-K filing
            if '8-K' not in cells[0].text:
                continue
            
            filing_count += 1
            
            # Get filing date
            filing_date = cells[3].text.strip()
            
            # Get document link
            doc_link = cells[1].find('a')
            if not doc_link:
                continue
            
            doc_url = 'https://www.sec.gov' + doc_link['href']
            
            # Get accession number
            accession_match = re.search(r'(\d{10}-\d{2}-\d{6})', doc_url)
            if not accession_match:
                continue
            
            accession_no = accession_match.group(1)
            
            # Download and parse the document
            try:
                doc_response = requests.get(doc_url, headers=headers, timeout=30)
                doc_response.raise_for_status()
                
                doc_soup = BeautifulSoup(doc_response.content, 'lxml')
                text = doc_soup.get_text()
                
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
                    if re.search(pattern, text, re.IGNORECASE):
                        found_keyword = True
                        keyword_count += len(re.findall(pattern, text, re.IGNORECASE))
                
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
                    matches = re.findall(pattern, text, re.IGNORECASE)
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
                        'url': doc_url
                    })
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"  Error processing document {doc_url}: {e}")
                continue
        
        print(f"  {ticker}: Found {len(results)} buyback events from {filing_count} 8-K filings")
        
    except Exception as e:
        print(f"  Error fetching filings for {ticker}: {e}")
    
    return results

# Process all tickers
all_results = []
start_time = time.time()

for i, ticker in enumerate(tickers, 1):
    print(f"\n[{i}/{len(tickers)}] Processing {ticker}...")
    
    results = extract_buyback_from_8k(ticker, max_filings=100)
    all_results.extend(results)
    
    # Progress update
    if i % 10 == 0:
        elapsed = time.time() - start_time
        avg_time = elapsed / i
        remaining = avg_time * (len(tickers) - i)
        print(f"\nProgress: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%)")
        print(f"Elapsed: {elapsed/3600:.2f}h, Remaining: {remaining/3600:.2f}h")
        print(f"Total events found: {len(all_results)}")

# Save results
df = pd.DataFrame(all_results)
output_path = project_root / "data" / "buyback" / "buyback_events_sp100_full.csv"
df.to_csv(output_path, index=False)

print(f"\n{'='*80}")
print(f"Buyback extraction completed!")
print(f"Total events: {len(df)}")
print(f"Tickers with events: {df['ticker'].nunique()}")
print(f"Output: {output_path}")
print(f"{'='*80}")
