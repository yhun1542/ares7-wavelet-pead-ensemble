#!/usr/bin/env python3
"""
SF1 Guidance 데이터 다운로드 스크립트
"""

import os
import pandas as pd
import nasdaqdatalink

# API Key 설정
API_KEY = "H6zH4Q2CDr9uTFk9koqJ"
nasdaqdatalink.ApiConfig.api_key = API_KEY

# Universe (PEAD와 동일)
UNIVERSE = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'BRK.B', 'V', 'JNJ',
    'WMT', 'JPM', 'MA', 'PG', 'UNH', 'HD', 'DIS', 'BAC', 'ADBE', 'CRM',
    'NFLX', 'XOM', 'PFE', 'CSCO', 'KO', 'ABT', 'AVGO', 'PEP', 'TMO', 'COST',
    'ACN', 'NKE', 'MRK', 'DHR', 'LLY', 'TXN', 'NEE', 'MDT', 'UNP', 'ORCL',
    'PM', 'HON', 'QCOM', 'LOW', 'UPS', 'BMY', 'RTX', 'AMGN', 'SBUX', 'INTU',
    'CVX', 'BA', 'GE', 'IBM', 'CAT', 'AMD', 'ISRG', 'DE', 'GS', 'AXP',
    'SPGI', 'BLK', 'MMM', 'BKNG', 'GILD', 'TJX', 'MDLZ', 'ADP', 'ZTS', 'CI',
    'SYK', 'MO', 'VRTX', 'TGT', 'CVS', 'CB', 'PLD', 'REGN', 'DUK', 'SO',
    'CL', 'USB', 'SCHW', 'BDX', 'ITW', 'NOC', 'MMC', 'EOG', 'HUM', 'CSX',
    'PNC', 'BSX', 'AON', 'SHW', 'CCI', 'EL', 'NSC', 'CME', 'ICE', 'WM'
]

def download_sf1_guidance():
    """SF1 Guidance 데이터 다운로드"""
    print("=== Downloading SF1 Guidance Data ===")
    print(f"Universe: {len(UNIVERSE)} tickers")
    
    all_data = []
    
    for i, ticker in enumerate(UNIVERSE, 1):
        print(f"[{i}/{len(UNIVERSE)}] {ticker}...", end=" ", flush=True)
        
        try:
            # SF1 테이블에서 guidance 관련 컬럼 가져오기
            # 주요 컬럼: calendardate, dimension, epsguidance, revenueguidance
            df = nasdaqdatalink.get_table(
                'SHARADAR/SF1',
                ticker=ticker,
                qopts={'columns': ['ticker', 'calendardate', 'dimension', 'epsguidance', 'revenueguidance']},
                paginate=True
            )
            
            if not df.empty:
                all_data.append(df)
                print(f"✓ {len(df)} records")
            else:
                print("✗ No data")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            continue
    
    if not all_data:
        print("\n⚠️  No data downloaded!")
        return None
    
    # 전체 데이터 병합
    df_all = pd.concat(all_data, ignore_index=True)
    
    print(f"\n=== Download Complete ===")
    print(f"Total records: {len(df_all)}")
    print(f"Date range: {df_all['calendardate'].min()} ~ {df_all['calendardate'].max()}")
    print(f"Tickers: {df_all['ticker'].nunique()}")
    
    # NaN 확인
    print(f"\nNaN counts:")
    print(f"  epsguidance: {df_all['epsguidance'].isna().sum()} ({df_all['epsguidance'].isna().sum()/len(df_all)*100:.1f}%)")
    print(f"  revenueguidance: {df_all['revenueguidance'].isna().sum()} ({df_all['revenueguidance'].isna().sum()/len(df_all)*100:.1f}%)")
    
    # 저장
    output_path = "/home/ubuntu/ares7-ensemble/data/sf1_guidance.csv"
    df_all.to_csv(output_path, index=False)
    print(f"\n✅ Saved to: {output_path}")
    
    # 샘플 출력
    print("\nSample data:")
    print(df_all.head(10))
    
    return df_all


if __name__ == "__main__":
    download_sf1_guidance()
