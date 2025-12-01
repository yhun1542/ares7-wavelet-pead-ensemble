#!/usr/bin/env python3
"""
SF1 테이블의 컬럼 목록 확인
"""

import nasdaqdatalink

# API Key 설정
API_KEY = "H6zH4Q2CDr9uTFk9koqJ"
nasdaqdatalink.ApiConfig.api_key = API_KEY

# SF1 메타데이터 가져오기
print("=== Fetching SF1 Metadata ===")

try:
    # 샘플 데이터 1개만 가져와서 컬럼 확인
    df = nasdaqdatalink.get_table(
        'SHARADAR/SF1',
        ticker='AAPL',
        paginate=True
    )
    
    print(f"\nTotal columns: {len(df.columns)}")
    print("\nAll columns:")
    for i, col in enumerate(df.columns, 1):
        print(f"{i:3d}. {col}")
    
    # Guidance 관련 컬럼 검색
    print("\n=== Searching for 'guidance' related columns ===")
    guidance_cols = [col for col in df.columns if 'guid' in col.lower()]
    if guidance_cols:
        print(f"Found {len(guidance_cols)} columns:")
        for col in guidance_cols:
            print(f"  - {col}")
    else:
        print("No 'guidance' related columns found")
    
    # EPS 관련 컬럼 검색
    print("\n=== Searching for 'eps' related columns ===")
    eps_cols = [col for col in df.columns if 'eps' in col.lower()]
    if eps_cols:
        print(f"Found {len(eps_cols)} columns:")
        for col in eps_cols:
            print(f"  - {col}")
    
    # Revenue 관련 컬럼 검색
    print("\n=== Searching for 'revenue' related columns ===")
    rev_cols = [col for col in df.columns if 'rev' in col.lower()]
    if rev_cols:
        print(f"Found {len(rev_cols)} columns:")
        for col in rev_cols:
            print(f"  - {col}")
    
    # 샘플 데이터
    print("\n=== Sample Data (first 5 rows) ===")
    print(df.head())
    
except Exception as e:
    print(f"Error: {e}")
