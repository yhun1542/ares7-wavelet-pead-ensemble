#!/usr/bin/env python3
"""
Create test universe files for buyback extraction testing
"""

import pandas as pd

DATA_DIR = '/home/ubuntu/ares7-ensemble/data/universe'

# 10 diverse tickers from SP100
test_10 = [
    'AAPL',   # Tech - Already tested (19 buybacks)
    'MSFT',   # Tech
    'GOOGL',  # Tech
    'JPM',    # Finance
    'BAC',    # Finance
    'JNJ',    # Healthcare
    'PFE',    # Healthcare
    'XOM',    # Energy
    'CVX',    # Energy
    'WMT'     # Retail
]

# Save
df = pd.DataFrame({'symbol': test_10})
df.to_csv(f'{DATA_DIR}/sp100_test10.csv', index=False)

print(f"✅ Created test universe with {len(test_10)} tickers:")
print(", ".join(test_10))
