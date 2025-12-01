
import pandas as pd

def load_price_matrix(price_paths, symbol_col="symbol"):
    """
    여러 Polygon 스타일 CSV를 합쳐서
    date x symbol close price matrix로 반환.
    """
    dfs = []
    for path in price_paths:
        df = pd.read_csv(path)
        
        # 날짜 컬럼 처리
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        elif 'timestamp' in df.columns:
            # timestamp가 문자열이면 그대로 파싱, 숫자면 ms로 변환
            if df['timestamp'].dtype == 'object':
                df['date'] = pd.to_datetime(df['timestamp'])
            else:
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        else:
            raise ValueError(f"{path} 에 date/timestamp 컬럼이 없습니다.")
        
        # Wide format (date, AAPL, MSFT, ...) vs Long format (symbol, date, close)
        if symbol_col in df.columns and 'close' in df.columns:
            # Long format
            dfs.append(df[[symbol_col, 'date', 'close']])
        else:
            # Wide format: date를 index로 설정하고 그대로 추가
            df = df.set_index('date')
            dfs.append(df)

    # Wide format이면 concat로 합치고, Long format이면 pivot
    if dfs and isinstance(dfs[0], pd.DataFrame) and dfs[0].index.name == 'date':
        # Wide format들을 합침
        px = pd.concat(dfs, axis=0)
        px = px.groupby(px.index).first()  # 중복 제거
    else:
        # Long format을 pivot
        df_all = pd.concat(dfs, ignore_index=True)
        df_all = df_all.drop_duplicates(subset=[symbol_col, 'date'])
        px = df_all.pivot(index='date', columns=symbol_col, values='close')
    
    px = px.sort_index()
    return px


def load_benchmark(spx_path):
    """
    SPX 벤치마크 종가 시계열 로딩.
    """
    spx = pd.read_csv(spx_path)
    if 'date' in spx.columns:
        spx['date'] = pd.to_datetime(spx['date'])
        # 'close' 또는 'SPX' 컬럼 찾기
        if 'close' in spx.columns:
            spx = spx.set_index('date')['close'].sort_index()
        elif 'SPX' in spx.columns:
            spx = spx.set_index('date')['SPX'].sort_index()
        else:
            raise ValueError("spx_close.csv 에 close 또는 SPX 컬럼이 필요합니다.")
    else:
        raise ValueError("spx_close.csv 에 date 컬럼이 필요합니다.")
    return spx
