#!/usr/bin/env python3.11
"""
Buyback Event Table Builder v4 - Download all 8-Ks + Local text search
Final version: No filtering, comprehensive local search
"""

import os
import sys
import time
import argparse
import requests
import pandas as pd
import re
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Constants
BASE_URL = "https://api.sec-api.io"
RATE_LIMIT_DELAY = 0.25  # 4 req/sec
MAX_RETRIES = 3
TIMEOUT = 30

# Comprehensive buyback keywords
BUYBACK_KEYWORDS = [
    "buyback",
    "share repurchase",
    "stock repurchase",
    "repurchase program",
    "repurchase of up to",
    "repurchase authorization",
    "authorized the repurchase",
]


def query_sec_api(query: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Query SEC-API with rate limiting"""
    
    headers = {"Authorization": api_key}
    
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_DELAY)
            
            resp = requests.post(
                BASE_URL,
                json=query,
                headers=headers,
                timeout=TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
            
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {}
            time.sleep(2 ** attempt)
    
    return {}


def extract_items(text: str) -> List[str]:
    """Extract Item numbers from text"""
    
    pattern = r'ITEM\s+(\d+\.\d+)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    return list(set(matches))


def check_buyback_keywords(text: str) -> Tuple[bool, Optional[str], List[str]]:
    """Check if text contains buyback keywords"""
    
    text_lower = text.lower()
    matched_keywords = []
    snippet = None
    
    for keyword in BUYBACK_KEYWORDS:
        if keyword in text_lower:
            matched_keywords.append(keyword)
            
            if snippet is None:
                idx = text_lower.find(keyword)
                start = max(0, idx - 100)
                end = min(len(text), idx + 200)
                snippet = text[start:end].replace('\n', ' ').strip()
    
    has_buyback = len(matched_keywords) > 0
    return has_buyback, snippet, matched_keywords


def extract_buyback_amount(text: str) -> Optional[float]:
    """Extract buyback amount from text"""
    
    patterns = [
        (r'\$\s*(\d+(?:\.\d+)?)\s*billion', 1e9),
        (r'\$\s*(\d+(?:\.\d+)?)\s*million', 1e6),
        (r'(\d+(?:\.\d+)?)\s*billion\s*dollars?', 1e9),
        (r'(\d+(?:\.\d+)?)\s*million\s*dollars?', 1e6),
    ]
    
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = float(match.group(1)) * multiplier
            return amount
    
    return None


def process_ticker(args):
    """Process single ticker - download all 8-Ks and search locally"""
    
    ticker, start_date, end_date, api_key, max_filings, verbose = args
    
    events = []
    
    try:
        # Query ALL 8-K filings (NO keyword filtering)
        query = {
            "query": {
                "query_string": {
                    "query": f'ticker:{ticker} AND formType:"8-K" AND filedAt:[{start_date} TO {end_date}]'
                }
            },
            "from": 0,
            "size": max_filings,
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        result = query_sec_api(query, api_key)
        filings = result.get("filings", [])
        
        if verbose:
            print(f"  {ticker}: Scanning {len(filings)} 8-K filings...")
        
        # Process each filing
        buyback_count = 0
        for filing in filings:
            # Get full text
            full_text = filing.get("fullText", "")
            if not full_text:
                continue
            
            # Local keyword search
            has_buyback, snippet, matched_keywords = check_buyback_keywords(full_text)
            
            if not has_buyback:
                continue
            
            buyback_count += 1
            
            # Extract Items
            items = extract_items(full_text)
            
            # Extract buyback amount
            amount = extract_buyback_amount(full_text)
            
            # Create event
            event = {
                "ticker": ticker,
                "filing_date": filing.get("filedAt", ""),
                "accession_number": filing.get("accessionNo", ""),
                "form_type": filing.get("formType", ""),
                "items": ",".join(items),
                "matched_keywords": ",".join(matched_keywords),
                "snippet": snippet,
                "buyback_amount": amount,
                "url": filing.get("linkToFilingDetails", "")
            }
            
            events.append(event)
        
        if verbose:
            print(f"  {ticker}: Found {buyback_count} buyback events")
            
    except Exception as e:
        if verbose:
            print(f"  {ticker}: Error - {str(e)}")
    
    return events


def build_buyback_events_v4(
    universe_path: str,
    start_date: str,
    end_date: str,
    output_path: str,
    api_key: str,
    max_filings_per_ticker: int = 150,
    n_workers: int = None,
    verbose: bool = True
):
    """Build buyback event table - download all 8-Ks + local search"""
    
    # Load universe
    universe = pd.read_csv(universe_path)
    tickers = universe['symbol'].unique().tolist()
    
    if verbose:
        print(f"🚀 Buyback Event Builder v4 (Download All + Local Search)")
        print(f"📊 Universe: {len(tickers)} tickers")
        print(f"📅 Period: {start_date} to {end_date}")
        print(f"💻 CPU cores: {mp.cpu_count()}")
        print(f"🔍 Keywords: {len(BUYBACK_KEYWORDS)}")
    
    # Determine number of workers
    if n_workers is None:
        n_workers = min(mp.cpu_count(), len(tickers), 4)
    
    if verbose:
        print(f"🔧 Using {n_workers} parallel workers")
        print(f"⚠️  This will download ~{len(tickers) * max_filings_per_ticker / 1000:.1f}k 8-K filings")
    
    # Prepare arguments
    args_list = [
        (ticker, start_date, end_date, api_key, max_filings_per_ticker, verbose)
        for ticker in tickers
    ]
    
    # Process in parallel
    all_events = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(process_ticker, args): args[0] for args in args_list}
        
        for i, future in enumerate(as_completed(futures), 1):
            ticker = futures[future]
            try:
                events = future.result()
                all_events.extend(events)
                
                if verbose and i % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = i / elapsed
                    eta = (len(tickers) - i) / rate if rate > 0 else 0
                    print(f"  Progress: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%) - Events: {len(all_events)} - ETA: {eta/60:.1f}min")
                    
            except Exception as e:
                if verbose:
                    print(f"  {ticker}: Failed - {str(e)}")
    
    elapsed = time.time() - start_time
    
    if verbose:
        print(f"\n✅ Complete!")
        print(f"⏱️  Time: {elapsed/60:.1f} minutes ({elapsed:.1f} seconds)")
        print(f"📊 Total events: {len(all_events)}")
    
    # Save results
    if all_events:
        df = pd.DataFrame(all_events)
        
        # Create output directory
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save to parquet
        df.to_parquet(output_path, index=False)
        
        if verbose:
            print(f"💾 Saved to: {output_path}")
            print(f"📈 Events per ticker: {len(df) / len(tickers):.1f}")
            
            # Item distribution
            if 'items' in df.columns:
                item_counts = {}
                for items_str in df['items']:
                    if pd.notna(items_str) and items_str:
                        for item in items_str.split(','):
                            item = item.strip()
                            if item:
                                item_counts[item] = item_counts.get(item, 0) + 1
                
                if item_counts:
                    print(f"\n📋 Item Distribution:")
                    for item, count in sorted(item_counts.items(), key=lambda x: -x[1])[:10]:
                        print(f"  Item {item}: {count}")
            
            # Keyword distribution
            if 'matched_keywords' in df.columns:
                keyword_counts = {}
                for keywords_str in df['matched_keywords']:
                    if pd.notna(keywords_str) and keywords_str:
                        for kw in keywords_str.split(','):
                            kw = kw.strip()
                            if kw:
                                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
                
                if keyword_counts:
                    print(f"\n🔍 Keyword Distribution:")
                    for kw, count in sorted(keyword_counts.items(), key=lambda x: -x[1]):
                        print(f"  '{kw}': {count}")
            
            # Amount statistics
            if 'buyback_amount' in df.columns:
                amounts = df['buyback_amount'].dropna()
                if len(amounts) > 0:
                    print(f"\n💰 Buyback Amount Statistics:")
                    print(f"  Total: ${amounts.sum()/1e9:.1f}B")
                    print(f"  Mean: ${amounts.mean()/1e9:.2f}B")
                    print(f"  Median: ${amounts.median()/1e9:.2f}B")
                    print(f"  Max: ${amounts.max()/1e9:.2f}B")
    else:
        if verbose:
            print("⚠️  No events found")


def main():
    parser = argparse.ArgumentParser(description="Buyback Event Builder v4")
    parser.add_argument("--universe_path", required=True, help="Path to universe CSV")
    parser.add_argument("--start_date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end_date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Output parquet path")
    parser.add_argument("--max_filings_per_ticker", type=int, default=150)
    parser.add_argument("--n_workers", type=int, default=None)
    parser.add_argument("--verbose", action="store_true", default=False)
    
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = os.environ.get("SEC_API_KEY")
    if not api_key:
        print("Error: SEC_API_KEY environment variable not set")
        sys.exit(1)
    
    build_buyback_events_v4(
        universe_path=args.universe_path,
        start_date=args.start_date,
        end_date=args.end_date,
        output_path=args.output,
        api_key=api_key,
        max_filings_per_ticker=args.max_filings_per_ticker,
        n_workers=args.n_workers,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
