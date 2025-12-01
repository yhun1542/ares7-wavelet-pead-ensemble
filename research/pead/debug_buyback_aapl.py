#!/usr/bin/env python3
"""
AAPL Buyback 추출 디버깅
"""

import os
os.environ['SEC_API_KEY'] = 'c2c08a95c67793b5a8bbba1e51611ed466900124e70c0615badefea2c6d429f9'

from sec_api import QueryApi
import requests
import re

queryApi = QueryApi(api_key=os.environ['SEC_API_KEY'])

# Query AAPL 8-K filings
query = {
    "query": 'ticker:AAPL AND formType:"8-K" AND filedAt:[2015-01-01 TO 2024-12-31]',
    "from": "0",
    "size": "10"  # Only 10 for debugging
}

response = queryApi.get_filings(query)
filings = response.get('filings', [])

print(f"Found {len(filings)} AAPL 8-K filings\n")

for i, filing in enumerate(filings, 1):
    filing_date = filing.get('filedAt', '')[:10]
    accession_no = filing.get('accessionNo', '')
    text_url = filing.get('linkToTxt', '')
    
    print(f"[{i}] {filing_date} - {accession_no}")
    print(f"    URL: {text_url}")
    
    if not text_url:
        print("    ❌ No text URL")
        continue
    
    try:
        # Download text
        response = requests.get(text_url, timeout=30)
        text = response.text
        
        print(f"    ✅ Downloaded {len(text)} chars")
        
        # Check for buyback keywords
        buyback_keywords = [
            r'share\s+(?:repurchase|buyback)',
            r'stock\s+(?:repurchase|buyback)',
            r'repurchase\s+program',
            r'buyback\s+program'
        ]
        
        found_keywords = []
        for pattern in buyback_keywords:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                found_keywords.append(f"{pattern}: {len(matches)} matches")
        
        if found_keywords:
            print(f"    ✅ Keywords found:")
            for kw in found_keywords:
                print(f"       - {kw}")
            
            # Extract amounts
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
                print(f"    ✅ Amounts found: {len(amounts)}")
                print(f"       Max: ${max(amounts)/1e9:.2f}B")
                print(f"       All: {[f'${a/1e9:.2f}B' for a in amounts[:5]]}")
            else:
                print(f"    ❌ No amounts extracted")
                # Show sample text around keywords
                for pattern in buyback_keywords:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        start = max(0, match.start() - 200)
                        end = min(len(text), match.end() + 200)
                        sample = text[start:end]
                        print(f"\n    Sample text around '{pattern}':")
                        print(f"    {sample[:400]}")
                        break
        else:
            print(f"    ❌ No buyback keywords found")
            # Show first 500 chars
            print(f"\n    First 500 chars:")
            print(f"    {text[:500]}")
    
    except Exception as e:
        print(f"    ❌ Error: {e}")
    
    print()
