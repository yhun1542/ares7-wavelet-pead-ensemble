#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_pairs_data.py

yfinance를 사용하여 페어 트레이딩용 주식 데이터 다운로드
"""

import pandas as pd
import yfinance as yf

def main():
    start_date = "2015-01-01"
    end_date = "2025-11-25"
    
    # 다운로드할 페어들
    symbols = ["KO", "PEP", "GLD", "SLV", "XOM", "CVX", "MS", "GS"]
    
    print(f"Pairs 데이터 다운로드 중 ({len(symbols)}개 심볼)...\n")
    
    all_data = []
    
    for symbol in symbols:
        print(f"{symbol} 다운로드...")
        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            
            # 멀티인덱스 컬럼 처리
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            data = data[['Close']].reset_index()
            data['symbol'] = symbol
            data = data.rename(columns={'Date': 'timestamp', 'Close': 'close'})
            data = data[['symbol', 'timestamp', 'close']]
            
            all_data.append(data)
            print(f"   ✅ {len(data)} 레코드")
        except Exception as e:
            print(f"   ❌ 오류: {e}")
    
    # 병합
    df = pd.concat(all_data, ignore_index=True)
    df = df.sort_values(['symbol', 'timestamp'])
    
    # 저장
    output_path = "data/pairs_price.csv"
    df.to_csv(output_path, index=False)
    
    print(f"\n✅ Pairs 데이터 저장 완료: {output_path}")
    print(f"   총 {len(df)} 레코드")
    print(f"   심볼별 레코드 수:")
    print(df.groupby('symbol').size())
    print(f"\n샘플 데이터:")
    print(df.head(10))

if __name__ == "__main__":
    main()
