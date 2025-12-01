#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_spy_tlt.py

yfinance를 사용하여 SPY/TLT 가격 데이터 다운로드
"""

import pandas as pd
import yfinance as yf

def main():
    start_date = "2015-11-23"
    end_date = "2025-11-22"
    
    print("SPY/TLT 데이터 다운로드 중...\n")
    
    # SPY 다운로드
    print("1. SPY 다운로드...")
    spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
    # 멀티인덱스 컬럼 처리
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    spy = spy[['Close']].reset_index()
    spy['symbol'] = 'SPY'
    spy = spy.rename(columns={'Date': 'timestamp', 'Close': 'close'})
    spy = spy[['symbol', 'timestamp', 'close']]
    print(f"   ✅ {len(spy)} 레코드")
    
    # TLT 다운로드
    print("\n2. TLT 다운로드...")
    tlt = yf.download("TLT", start=start_date, end=end_date, progress=False)
    # 멀티인덱스 컬럼 처리
    if isinstance(tlt.columns, pd.MultiIndex):
        tlt.columns = tlt.columns.get_level_values(0)
    tlt = tlt[['Close']].reset_index()
    tlt['symbol'] = 'TLT'
    tlt = tlt.rename(columns={'Date': 'timestamp', 'Close': 'close'})
    tlt = tlt[['symbol', 'timestamp', 'close']]
    print(f"   ✅ {len(tlt)} 레코드")
    
    # 병합
    df = pd.concat([spy, tlt], ignore_index=True)
    df = df.sort_values(['symbol', 'timestamp'])
    
    # 저장
    output_path = "data/spy_tlt_price.csv"
    df.to_csv(output_path, index=False)
    
    print(f"\n✅ SPY/TLT 데이터 저장 완료: {output_path}")
    print(f"   총 {len(df)} 레코드")
    print(f"   SPY: {len(spy)} 레코드")
    print(f"   TLT: {len(tlt)} 레코드")
    print(f"\n샘플 데이터:")
    print(df.head(10))

if __name__ == "__main__":
    main()
