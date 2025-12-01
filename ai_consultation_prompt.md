# AI Consultation: Buyback Event Data Collection

## Context

We are trying to extract **Stock Buyback (Share Repurchase) events** from SEC 8-K filings for quantitative alpha analysis.

## Problem

**Attempted approaches that FAILED**:

1. **SEC-API Full-Text Search** - The `fullText` field is empty or incomplete
2. **SEC-API Query with Item filtering** - Item 8.01 filter found 0 events
3. **SEC-API Download All 8-Ks + Local Search** - `fullText` field is still empty

**Root cause**: SEC-API does not provide the actual document content in the `fullText` field. It only provides metadata.

## Available Resources

- **SEC-API KEY**: Active Research License ($55/mo) with access to all APIs
- **Python 3.11** environment with standard libraries
- **API Keys**: Alpha Vantage, Polygon.io, SHARADAR, etc.
- **Universe**: SP100 (99 tickers)
- **Period**: 2015-2025

## Question

**What is the BEST method to extract Buyback events from SEC 8-K filings?**

Requirements:
1. Must work with available APIs/tools
2. Must be implementable in Python
3. Must scale to 99 tickers × 10 years
4. Must extract: date, ticker, buyback amount (if available)

## Constraints

- Cannot use Bloomberg Terminal, FactSet, or other expensive institutional data
- Cannot manually parse thousands of HTML files
- Need automated, scalable solution

## Expected Output

Please provide:
1. **Recommended approach** (step-by-step)
2. **Code snippet** (if applicable)
3. **Expected success rate** (% of buyback events captured)
4. **Estimated time** (implementation + execution)
5. **Alternative approaches** (if primary fails)

---

**Please provide your expert recommendation.**
