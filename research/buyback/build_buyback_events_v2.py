#!/usr/bin/env python3.11
"""
Buyback Event Table Builder v2 - Text-based keyword search
No Item filtering, comprehensive keyword patterns
"""

import os
import sys
import time
import argparse
import requests
import pandas as pd
import numpy as np
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
from functools import partial
import asyncio
import aiohttp

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
    "return of capital through share repurchases",
    "issuer repurchases of equity securities",
]

class TurboSECAPIClient:
    """Async SEC-API client with connection pooling"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": api_key}
        self.session = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=4)
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def query_filings_async(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Async API query with rate limiting"""
        
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.sleep(RATE_LIMIT_DELAY)
                
                async with self.session.post(BASE_URL, json=query) as resp:
                    resp.raise_for_status()
                    return await resp.json()
                    
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                
    async def fetch_html_async(self, url: str) -> str:
        """Async HTML fetch"""
        
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.sleep(RATE_LIMIT_DELAY)
                
                async with self.session.get(url) as resp:
                    resp.raise_for_status()
                    return await resp.text()
                    
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return ""
                await asyncio.sleep(2 ** attempt)
        
        return ""


def extract_items(text: str) -> List[str]:
    """Extract Item numbers from 8-K text"""
    
    # Pattern: ITEM 2.02, Item 8.01, etc.
    pattern = r'ITEM\s+(\d+\.\d+)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    return list(set(matches))  # Remove duplicates


def check_buyback_keywords(text: str) -> Tuple[bool, Optional[str], List[str]]:
    """Check if text contains buyback keywords"""
    
    text_lower = text.lower()
    matched_keywords = []
    snippet = None
    
    for keyword in BUYBACK_KEYWORDS:
        if keyword in text_lower:
            matched_keywords.append(keyword)
            
            # Extract snippet around first match
            if snippet is None:
                idx = text_lower.find(keyword)
                start = max(0, idx - 100)
                end = min(len(text), idx + 200)
                snippet = text[start:end].replace('\n', ' ').strip()
    
    has_buyback = len(matched_keywords) > 0
    return has_buyback, snippet, matched_keywords


def extract_buyback_amount(text: str) -> Optional[float]:
    """Extract buyback amount from text"""
    
    # Look for patterns like "$X billion", "$X million"
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


async def process_ticker_async(
    ticker: str,
    start_date: str,
    end_date: str,
    api_key: str,
    max_filings: int,
    verbose: bool
) -> List[Dict[str, Any]]:
    """Process single ticker asynchronously"""
    
    events = []
    
    async with TurboSECAPIClient(api_key) as client:
        # Query 8-K filings (NO Item filtering)
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
        
        try:
            result = await client.query_filings_async(query)
            filings = result.get("filings", [])
            
            if verbose:
                print(f"  {ticker}: Found {len(filings)} 8-K filings")
            
            # Process each filing
            for filing in filings:
                # Get filing text
                filing_url = filing.get("linkToFilingDetails", "")
                if not filing_url:
                    continue
                
                # Fetch HTML
                html = await client.fetch_html_async(filing_url)
                if not html:
                    continue
                
                # Extract Items
                items = extract_items(html)
                
                # Check for buyback keywords
                has_buyback, snippet, matched_keywords = check_buyback_keywords(html)
                
                if not has_buyback:
                    continue
                
                # Extract buyback amount
                amount = extract_buyback_amount(html)
                
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
                    "url": filing_url
                }
                
                events.append(event)
                
        except Exception as e:
            if verbose:
                print(f"  {ticker}: Error - {str(e)}")
    
    return events


def process_ticker_sync(args):
    """Sync wrapper for async processing"""
    
    ticker, start_date, end_date, api_key, max_filings, verbose = args
    
    # Run async function in new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        events = loop.run_until_complete(
            process_ticker_async(ticker, start_date, end_date, api_key, max_filings, verbose)
        )
        return events
    finally:
        loop.close()


def build_buyback_events_v2(
    universe_path: str,
    start_date: str,
    end_date: str,
    output_path: str,
    api_key: str,
    max_filings_per_ticker: int = 150,
    n_workers: int = None,
    verbose: bool = True
):
    """Build buyback event table with text-based keyword search"""
    
    # Load universe
    universe = pd.read_csv(universe_path)
    tickers = universe['symbol'].unique().tolist()
    
    if verbose:
        print(f"🚀 Buyback Event Builder v2 (Text-based)")
        print(f"📊 Universe: {len(tickers)} tickers")
        print(f"📅 Period: {start_date} to {end_date}")
        print(f"💻 CPU cores: {mp.cpu_count()}")
        print(f"🔍 Keywords: {len(BUYBACK_KEYWORDS)}")
    
    # Determine number of workers
    if n_workers is None:
        n_workers = min(mp.cpu_count(), len(tickers), 8)  # Max 8 workers
    
    if verbose:
        print(f"🔧 Using {n_workers} parallel workers")
    
    # Prepare arguments
    args_list = [
        (ticker, start_date, end_date, api_key, max_filings_per_ticker, verbose)
        for ticker in tickers
    ]
    
    # Process in parallel
    all_events = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(process_ticker_sync, args): args[0] for args in args_list}
        
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
        print(f"⏱️  Time: {elapsed/60:.1f} minutes")
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
                            item_counts[item] = item_counts.get(item, 0) + 1
                
                print(f"\n📋 Item Distribution:")
                for item, count in sorted(item_counts.items(), key=lambda x: -x[1])[:10]:
                    print(f"  Item {item}: {count}")
    else:
        if verbose:
            print("⚠️  No events found")


def main():
    parser = argparse.ArgumentParser(description="Buyback Event Builder v2")
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
    
    build_buyback_events_v2(
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
