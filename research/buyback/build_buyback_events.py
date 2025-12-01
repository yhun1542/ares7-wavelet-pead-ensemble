#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build buyback (share repurchase) event table from SEC-API 8-K filings.

Usage example:

    python -m research.buyback.build_buyback_events \
        --universe_path data/universe/sp100.csv \
        --start_date 2015-01-01 \
        --end_date 2025-12-01 \
        --output data/buyback/buyback_events.parquet \
        --max_filings_per_ticker 200

Requirements:
    - SEC-API account + API key in environment variable: SEC_API_KEY
    - pip: requests, pandas, pyarrow (for parquet)
"""

import argparse
import os
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any

import requests
import pandas as pd

BASE_URL = "https://api.sec-api.io"


# ---- Keyword logic --------------------------------------------------------- #

DEFAULT_BUYBACK_KEYWORDS = [
    "share repurchase",
    "repurchase program",
    "repurchase authorization",
    "repurchase authorisation",
    "share buyback",
    "stock buyback",
    "repurchase up to",
    "repurchase of up to",
    "repurchase shares",
    "repurchase common stock",
]


def normalize_text(s: str) -> str:
    """Simple normalization: lower + strip."""
    return (s or "").lower()


def detect_buyback(text: str, keywords: List[str]) -> Dict[str, Any]:
    """
    Return dict with has_buyback flag and matched keywords.
    """
    text_norm = normalize_text(text)
    matched = [kw for kw in keywords if kw in text_norm]
    return {
        "has_buyback": len(matched) > 0,
        "matched_keywords": matched,
    }


# ---- SEC-API client -------------------------------------------------------- #

class SecApiClient:
    def __init__(self, api_key: str, rate_limit_per_sec: float = 4.0):
        """
        rate_limit_per_sec: approximate requests per second to SEC-API.
        """
        self.api_key = api_key
        self.headers = {"Authorization": api_key}
        self.min_interval = 1.0 / rate_limit_per_sec
        self._last_call_ts = 0.0

    def _throttle(self):
        import time as _time
        now = _time.time()
        dt = now - self._last_call_ts
        if dt < self.min_interval:
            _time.sleep(self.min_interval - dt)
        self._last_call_ts = _time.time()

    def query_filings(self, query: Dict[str, Any]) -> Dict[str, Any]:
        self._throttle()
        resp = requests.post(BASE_URL, json=query, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def fetch_html(self, url: str) -> str:
        self._throttle()
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return ""
        return resp.text


# ---- Core logic ------------------------------------------------------------ #

def search_8k_buyback_filings(
    client: SecApiClient,
    ticker: str,
    start_date: str,
    end_date: str,
    max_filings: int = 200,
    batch_size: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch 8-K filings for a given ticker and date range (filedAt),
    filtering by Items 8.01 and 2.02 in the SEC-API query.

    Returns raw filings list (dicts) from SEC-API.
    """
    filings: List[Dict[str, Any]] = []
    offset = 0

    while True:
        size = min(batch_size, max_filings - len(filings))
        if size <= 0:
            break

        query = {
            "query": (
                f'formType:"8-K" AND ticker:"{ticker}" '
                f'AND (items:"8.01" OR items:"2.02") '
                f'AND filedAt:[{start_date} TO {end_date}]'
            ),
            "from": offset,
            "size": size,
            "sort": [{"filedAt": {"order": "desc"}}],
        }

        data = client.query_filings(query)
        batch = data.get("filings", [])
        if not batch:
            break

        filings.extend(batch)
        offset += len(batch)

        # If fewer than requested, no more pages
        if len(batch) < size:
            break

    return filings[:max_filings]


def build_buyback_events_for_ticker(
    client: SecApiClient,
    ticker: str,
    start_date: str,
    end_date: str,
    keywords: List[str],
    max_filings_per_ticker: int,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    filings = search_8k_buyback_filings(
        client=client,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        max_filings=max_filings_per_ticker,
    )

    events: List[Dict[str, Any]] = []

    if verbose:
        print(f"[{ticker}] fetched {len(filings)} candidate 8-K filings")

    for f in filings:
        filed_at = f.get("filedAt")
        if not filed_at:
            continue
        filing_date = filed_at[:10]  # 'YYYY-MM-DD'

        filing_url = f.get("linkToFilingDetails") or f.get("linkToFiling")
        if not filing_url:
            continue

        html = client.fetch_html(filing_url)
        if not html:
            continue

        det = detect_buyback(html, keywords)
        if not det["has_buyback"]:
            continue

        # small hash to identify text version; we avoid storing full HTML
        text_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]

        events.append(
            {
                "date": filing_date,
                "symbol": ticker,
                "companyName": f.get("companyName"),
                "cik": f.get("cik"),
                "filedAt": filed_at,
                "formType": f.get("formType"),
                "items": ",".join(f.get("items", [])),
                "filing_url": filing_url,
                "text_hash": text_hash,
                "matched_keywords": "|".join(det["matched_keywords"]),
                "event_type": "BUYBACK",
            }
        )

        if verbose:
            print(f"  [+] BUYBACK detected: {ticker} {filing_date} {filing_url}")

    return events


def build_buyback_events(
    universe: List[str],
    start_date: str,
    end_date: str,
    api_key: str,
    max_filings_per_ticker: int = 200,
    keywords: List[str] = None,
    verbose: bool = False,
) -> pd.DataFrame:
    if keywords is None:
        keywords = DEFAULT_BUYBACK_KEYWORDS

    client = SecApiClient(api_key=api_key, rate_limit_per_sec=4.0)
    all_events: List[Dict[str, Any]] = []

    t0 = time.time()
    for i, ticker in enumerate(universe, start=1):
        if verbose:
            print(f"[{i}/{len(universe)}] Ticker={ticker}")
        try:
            evs = build_buyback_events_for_ticker(
                client=client,
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                keywords=keywords,
                max_filings_per_ticker=max_filings_per_ticker,
                verbose=verbose,
            )
            all_events.extend(evs)
        except Exception as e:
            # 로깅만 하고 계속 진행
            print(f"[WARN] Error processing {ticker}: {e}")

    t1 = time.time()
    print(f"Total events found: {len(all_events)} in {t1 - t0:.1f}s")

    if not all_events:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "companyName",
                "cik",
                "filedAt",
                "formType",
                "items",
                "filing_url",
                "text_hash",
                "matched_keywords",
                "event_type",
            ]
        )

    df = pd.DataFrame(all_events)
    df["date"] = pd.to_datetime(df["date"])
    df["filedAt"] = pd.to_datetime(df["filedAt"])
    df = df.sort_values(["date", "symbol"])
    return df


# ---- CLI ------------------------------------------------------------------- #

def parse_args():
    p = argparse.ArgumentParser(description="Build buyback event table from SEC-API 8-K filings.")
    p.add_argument(
        "--universe_path",
        type=str,
        required=True,
        help="CSV with at least a 'symbol' column (e.g., SP100 or ARES7 universe).",
    )
    p.add_argument(
        "--start_date",
        type=str,
        required=True,
        help="Start date for filedAt filter, e.g. 2010-01-01",
    )
    p.add_argument(
        "--end_date",
        type=str,
        required=True,
        help="End date for filedAt filter, e.g. 2025-12-01",
    )
    p.add_argument(
        "--output",
        type=str,
        default="data/buyback/buyback_events.parquet",
        help="Output path (.parquet or .csv).",
    )
    p.add_argument(
        "--max_filings_per_ticker",
        type=int,
        default=200,
        help="Maximum number of 8-K filings per ticker to scan.",
    )
    p.add_argument(
        "--rate_limit_per_sec",
        type=float,
        default=4.0,
        help="Approximate SEC-API requests per second (throttling).",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress per ticker / event.",
    )
    return p.parse_args()


def main():
    args = parse_args()

    api_key = os.getenv("SEC_API_KEY")
    if not api_key:
        raise RuntimeError("Environment variable SEC_API_KEY is not set.")

    universe_df = pd.read_csv(args.universe_path)
    if "symbol" not in universe_df.columns:
        raise ValueError("universe CSV must contain a 'symbol' column.")
    universe = sorted(universe_df["symbol"].dropna().unique().tolist())

    print(f"Universe size: {len(universe)} symbols")
    print(f"Date range: {args.start_date} ~ {args.end_date}")

    df = build_buyback_events(
        universe=universe,
        start_date=args.start_date,
        end_date=args.end_date,
        api_key=api_key,
        max_filings_per_ticker=args.max_filings_per_ticker,
        verbose=args.verbose,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix == ".parquet":
        df.to_parquet(out_path, index=False)
    else:
        df.to_csv(out_path, index=False)

    print(f"Saved buyback events → {out_path} (n={len(df)})")


if __name__ == "__main__":
    main()
