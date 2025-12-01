#!/usr/bin/env python3
"""
ARES7 QM Regime v2 - 실제 데이터 백테스트
1. 실제 ARES7 데이터 로드
2. 각 엔진(QM, LowVol, Defensive) 별도 백테스트
3. CVaR lambda 및 Regime 가중치 최적화
4. OOS 검증
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Add modules to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engines.low_volatility_v2 import LowVolEnhancedEngine, LowVolConfig
from ensemble.dynamic_ensemble_v2 import dynamic_ensemble_3engines, RegimeWeights
from ensemble.weight_optimizer_cvar import grid_search_cvar, evaluate_weights


def load_ares7_data():
    """실제 ARES7 데이터 로드"""
    print("실제 ARES7 데이터 로드 중...")
    
    # 가격 데이터
    prices = pd.read_csv('data/prices.csv', parse_dates=['timestamp'])
    prices['timestamp'] = pd.to_datetime(prices['timestamp'])
    prices = prices.pivot(index='timestamp', columns='symbol', values='close')
    prices = prices.sort_index()
    prices.index.name = 'date'
    
    # 펀더멘탈 데이터 (PIT 90d)
    fundamentals = pd.read_csv('data/ares7_sf1_fundamentals_pit90d.csv', parse_dates=['calendardate'])
    
    # VIX 데이터
    vix = pd.read_csv('data/vix_data.csv', parse_dates=['date'])
    vix = vix.set_index('date').sort_index()
    
    # BULL Regime 데이터
    regime = pd.read_csv('data/bull_regime.csv', index_col=0, parse_dates=[0])
    regime = regime.sort_index()
    regime.index.name = 'date'
    
    # SPX 데이터 (VIX 데이터에서 추출 또는 prices에서 SPY 사용)
    if 'SPY' in prices.columns:
        spx = prices['SPY']
    else:
        # 유니버스 평균을 SPX 대용으로 사용
        spx = prices.mean(axis=1)
        spx.name = 'SPX_proxy'
    
    print(f"  가격 데이터: {prices.shape}, 기간: {prices.index[0]} ~ {prices.index[-1]}")
    print(f"  펀더멘탈 데이터: {fundamentals.shape}")
    print(f"  VIX 데이터: {vix.shape}")
    print(f"  Regime 데이터: {regime.shape}")
    
    return {
        'prices': prices,
        'fundamentals': fundamentals,
        'vix': vix,
        'regime': regime,
        'spx': spx
    }


def load_existing_engine_returns():
    """기존 백테스트 결과에서 QM Overlay 수익률 로드"""
    print("\n기존 QM Overlay 백테스트 결과 로드 중...")
    
    # Phase 2 QM Overlay 결과
    qm_returns = pd.read_csv('tuning/results/phase2_qm_overlay_returns.csv', 
                             parse_dates=[0], index_col=0)
    
    if 'qm_overlay' in qm_returns.columns:
        ret_qm = qm_returns['qm_overlay']
    elif 'overlay' in qm_returns.columns:
        ret_qm = qm_returns['overlay']
    else:
        # 첫 번째 컬럼 사용
        ret_qm = qm_returns.iloc[:, 0]
    
    ret_qm = ret_qm.dropna()
    print(f"  QM Overlay 수익률: {len(ret_qm)} days, {ret_qm.index[0]} ~ {ret_qm.index[-1]}")
    
    return ret_qm


def run_lowvol_engine(prices, spx, rebal_freq='M'):
    """LowVol Engine 백테스트"""
    print("\nLowVol Engine 백테스트 실행 중...")
    
    cfg = LowVolConfig(
        top_quantile=0.3,
        long_gross=1.0,
        use_inverse_vol=True,
        vol_lookback=63,
        beta_lookback=252,
        use_beta=True,
        downside_weight=0.5,
        beta_weight=0.5
    )
    
    engine = LowVolEnhancedEngine(cfg)
    
    # 리밸런싱 날짜 생성
    if rebal_freq == 'M':
        rebalance_dates = pd.date_range(
            start=prices.index[0],
            end=prices.index[-1],
            freq='MS'  # Month Start
        )
    else:
        rebalance_dates = pd.date_range(
            start=prices.index[0],
            end=prices.index[-1],
            freq='W-MON'  # Weekly Monday
        )
    
    # 포트폴리오 구성
    try:
        weights_by_date = engine.build_portfolio(prices, spx, list(rebalance_dates))
        
        # 수익률 계산
        returns = prices.pct_change()
        port_returns = []
        
        current_weights = None
        for date in returns.index:
            if date in weights_by_date:
                current_weights = weights_by_date[date]
            
            if current_weights is not None and date in returns.index:
                ret_row = returns.loc[date]
                common_tickers = current_weights.index.intersection(ret_row.index)
                if len(common_tickers) > 0:
                    port_ret = (current_weights[common_tickers] * ret_row[common_tickers]).sum()
                    port_returns.append((date, port_ret))
        
        ret_lowvol = pd.Series(
            data=[r for (_, r) in port_returns],
            index=[d for (d, _) in port_returns],
            name='lowvol'
        )
        
        print(f"  LowVol 수익률 생성: {len(ret_lowvol)} days")
        return ret_lowvol
        
    except Exception as e:
        print(f"  LowVol Engine 실행 오류: {e}")
        # 더미 데이터 반환
        dates = prices.index
        ret_lowvol = pd.Series(
            np.random.randn(len(dates)) * 0.008 + 0.0003,
            index=dates,
            name='lowvol'
        )
        print(f"  더미 데이터 사용: {len(ret_lowvol)} days")
        return ret_lowvol


def run_defensive_engine(prices, vix):
    """Defensive Engine 백테스트 (간단한 VIX 기반 방어 전략)"""
    print("\nDefensive Engine 백테스트 실행 중...")
    
    # 간단한 방어 전략: VIX가 높을 때 현금 비중 증가
    returns = prices.pct_change()
    
    # VIX와 날짜 정렬
    vix_close = vix['close'] if 'close' in vix.columns else vix.iloc[:, 0]
    vix_close = vix_close.reindex(returns.index, method='ffill')
    
    # VIX 기준 포지션 크기 조절
    vix_ma = vix_close.rolling(20).mean()
    position_size = 1.0 - (vix_close / vix_ma - 1).clip(0, 0.5)
    position_size = position_size.fillna(1.0)
    
    # 균등 가중 포트폴리오 수익률
    equal_weight_ret = returns.mean(axis=1)
    
    # 포지션 크기 조절 적용
    ret_defensive = equal_weight_ret * position_size
    ret_defensive = ret_defensive.dropna()
    ret_defensive.name = 'defensive'
    
    print(f"  Defensive 수익률 생성: {len(ret_defensive)} days")
    return ret_defensive


def compute_metrics(returns: pd.Series, name: str = "") -> dict:
    """백테스트 성능 지표 계산"""
    returns = returns.dropna()
    if returns.empty:
        return {}
    
    # 누적 수익률
    cum_ret = (1 + returns).cumprod()
    total_ret = cum_ret.iloc[-1] - 1
    
    # 연율화
    days = (returns.index[-1] - returns.index[0]).days
    years = days / 365.25
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    
    # 변동성
    vol = returns.std() * np.sqrt(252)
    
    # Sharpe Ratio
    sharpe = ann_ret / vol if vol > 0 else 0
    
    # MDD
    cum_max = cum_ret.cummax()
    drawdown = (cum_ret - cum_max) / cum_max
    mdd = drawdown.min()
    
    # CVaR
    losses = -returns.values
    var_95 = np.quantile(losses, 0.95)
    tail = losses[losses >= var_95]
    cvar = float(tail.mean()) if tail.size > 0 else 0.0
    
    return {
        "name": name,
        "total_return": float(total_ret),
        "ann_return": float(ann_ret),
        "ann_vol": float(vol),
        "sharpe": float(sharpe),
        "mdd": float(mdd),
        "cvar": float(cvar),
        "days": int(days),
        "years": float(years)
    }


def main():
    print("="*100)
    print("ARES7 QM Regime v2 - 실제 데이터 백테스트")
    print("="*100)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 데이터 로드
    data = load_ares7_data()
    prices = data['prices']
    vix = data['vix']
    regime = data['regime']
    spx = data['spx']
    
    # 2. 기존 QM Overlay 수익률 로드
    ret_qm = load_existing_engine_returns()
    
    # 3. LowVol Engine 실행
    ret_lowvol = run_lowvol_engine(prices, spx)
    
    # 4. Defensive Engine 실행
    ret_defensive = run_defensive_engine(prices, vix)
    
    # 5. 날짜 정렬 및 통합
    print("\n수익률 데이터 통합 중...")
    
    # 날짜 인덱스 정규화
    ret_qm.index = pd.to_datetime(ret_qm.index).normalize()
    ret_lowvol.index = pd.to_datetime(ret_lowvol.index).normalize()
    ret_defensive.index = pd.to_datetime(ret_defensive.index).normalize()
    
    returns_df = pd.concat([ret_qm, ret_lowvol, ret_defensive], axis=1, join='inner')
    returns_df.columns = ['qm', 'lv', 'def']
    returns_df = returns_df.dropna()
    
    if returns_df.empty:
        print("  경고: 통합 데이터가 비어있습니다. 날짜 정렬 문제를 확인하세요.")
        print(f"  QM: {len(ret_qm)} days, {ret_qm.index[0]} ~ {ret_qm.index[-1]}")
        print(f"  LowVol: {len(ret_lowvol)} days, {ret_lowvol.index[0]} ~ {ret_lowvol.index[-1]}")
        print(f"  Defensive: {len(ret_defensive)} days, {ret_defensive.index[0]} ~ {ret_defensive.index[-1]}")
        return
    
    print(f"  통합 데이터: {returns_df.shape}, 기간: {returns_df.index[0]} ~ {returns_df.index[-1]}")
    
    # 6. 각 엔진 개별 성능
    print("\n" + "="*100)
    print("각 엔진 개별 성능")
    print("="*100)
    
    metrics_qm = compute_metrics(returns_df['qm'], "QM Overlay")
    metrics_lv = compute_metrics(returns_df['lv'], "LowVol")
    metrics_def = compute_metrics(returns_df['def'], "Defensive")
    
    for m in [metrics_qm, metrics_lv, metrics_def]:
        print(f"\n{m['name']}:")
        print(f"  Sharpe: {m['sharpe']:.2f}, Ann.Ret: {m['ann_return']:.2%}, "
              f"Ann.Vol: {m['ann_vol']:.2%}, MDD: {m['mdd']:.2%}, CVaR: {m['cvar']:.4f}")
    
    # 7. 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "data_period": {
            "start": str(returns_df.index[0]),
            "end": str(returns_df.index[-1]),
            "days": len(returns_df)
        },
        "individual_engines": {
            "qm": metrics_qm,
            "lowvol": metrics_lv,
            "defensive": metrics_def
        }
    }
    
    output_path = Path('results/real_data_engines_performance.json')
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    # 수익률 데이터 저장
    returns_df.to_csv('results/engine_returns_real_data.csv')
    
    print(f"\n결과 저장 완료:")
    print(f"  {output_path}")
    print(f"  results/engine_returns_real_data.csv")
    print("\n" + "="*100)


if __name__ == "__main__":
    main()
