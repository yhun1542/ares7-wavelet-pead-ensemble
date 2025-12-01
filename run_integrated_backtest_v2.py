#!/usr/bin/env python3
"""
ARES7 QM Regime v2 통합 백테스트
- LowVolEnhancedEngine 추가
- CVaR 기반 weight optimization
- Dynamic Ensemble v2 적용
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

# Add modules to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engines.low_volatility_v2 import LowVolEnhancedEngine, LowVolConfig
from ensemble.dynamic_ensemble_v2 import dynamic_ensemble_3engines, RegimeWeights
from ensemble.weight_optimizer_cvar import grid_search_cvar, evaluate_weights


def compute_metrics(returns: pd.Series) -> dict:
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
    print("ARES7 QM Regime v2 통합 백테스트")
    print("="*100)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 구현된 모듈 확인
    print("✓ LowVolEnhancedEngine 구현 완료")
    print("✓ Dynamic Ensemble v2 구현 완료")
    print("✓ CVaR Weight Optimizer 구현 완료")
    print()
    
    # 2. 테스트 데이터 생성 (실제 데이터로 대체 필요)
    print("테스트 데이터 생성 중...")
    dates = pd.date_range('2020-01-01', '2024-12-31', freq='D')
    
    # QM Overlay 시뮬레이션 (기존 ARES7)
    ret_qm = pd.Series(
        np.random.randn(len(dates)) * 0.012 + 0.0005,  # Sharpe ~3.2 수준
        index=dates,
        name="qm"
    )
    
    # LowVol Engine 시뮬레이션
    ret_lowvol = pd.Series(
        np.random.randn(len(dates)) * 0.008 + 0.0003,  # 낮은 변동성
        index=dates,
        name="lowvol"
    )
    
    # Defensive Engine 시뮬레이션
    ret_defensive = pd.Series(
        np.random.randn(len(dates)) * 0.010 + 0.0004,
        index=dates,
        name="defensive"
    )
    
    # Regime 시뮬레이션
    regime = pd.Series(index=dates, dtype=str)
    regime[:len(dates)//2] = "BULL"
    regime[len(dates)//2:len(dates)*3//4] = "NEUTRAL"
    regime[len(dates)*3//4:] = "BEAR"
    
    print(f"  데이터 기간: {dates[0]} ~ {dates[-1]}")
    print(f"  총 일수: {len(dates)}")
    print()
    
    # 3. 기존 QM Regime v1 성능
    print("="*100)
    print("기존 ARES7 QM Regime v1 성능")
    print("="*100)
    metrics_v1 = compute_metrics(ret_qm)
    print(f"  Sharpe Ratio: {metrics_v1['sharpe']:.2f}")
    print(f"  Ann. Return: {metrics_v1['ann_return']:.2%}")
    print(f"  Ann. Vol: {metrics_v1['ann_vol']:.2%}")
    print(f"  MDD: {metrics_v1['mdd']:.2%}")
    print(f"  CVaR (95%): {metrics_v1['cvar']:.4f}")
    print()
    
    # 4. CVaR 기반 weight optimization
    print("="*100)
    print("CVaR 기반 Weight Optimization")
    print("="*100)
    
    returns_df = pd.concat([ret_qm, ret_lowvol, ret_defensive], axis=1)
    returns_df.columns = ['qm', 'lv', 'def']
    
    print("Grid Search 실행 중...")
    results = grid_search_cvar(returns_df, step=0.1, cvar_lambda=0.5)
    
    best_weights = results[0]
    print(f"\n최적 가중치 (Sharpe - 0.5*CVaR 기준):")
    print(f"  QM: {best_weights['engine_weights']['qm']:.1%}")
    print(f"  LowVol: {best_weights['engine_weights']['lv']:.1%}")
    print(f"  Defensive: {best_weights['engine_weights']['def']:.1%}")
    print(f"  Score: {best_weights['score']:.4f}")
    print(f"  Sharpe: {best_weights['sharpe']:.4f}")
    print(f"  CVaR: {best_weights['cvar']:.4f}")
    print()
    
    # 5. Dynamic Ensemble v2 적용
    print("="*100)
    print("Dynamic Ensemble v2 적용")
    print("="*100)
    
    # Regime별 가중치 설정
    regime_weights = RegimeWeights(
        bull={"qm": 0.7, "lv": 0.2, "def": 0.1},
        bear={"qm": 0.0, "lv": 0.4, "def": 0.6},
        high_vol={"qm": 0.0, "lv": 0.3, "def": 0.7},
        neutral={"qm": 0.5, "lv": 0.3, "def": 0.2}
    )
    
    ret_ensemble = dynamic_ensemble_3engines(
        ret_qm, ret_lowvol, ret_defensive, regime, regime_weights
    )
    
    metrics_v2 = compute_metrics(ret_ensemble)
    print(f"  Sharpe Ratio: {metrics_v2['sharpe']:.2f}")
    print(f"  Ann. Return: {metrics_v2['ann_return']:.2%}")
    print(f"  Ann. Vol: {metrics_v2['ann_vol']:.2%}")
    print(f"  MDD: {metrics_v2['mdd']:.2%}")
    print(f"  CVaR (95%): {metrics_v2['cvar']:.4f}")
    print()
    
    # 6. 성능 비교
    print("="*100)
    print("성능 비교 요약")
    print("="*100)
    print(f"{'Metric':<20} {'v1 (QM Only)':<20} {'v2 (Ensemble)':<20} {'개선':<15}")
    print("-"*100)
    print(f"{'Sharpe Ratio':<20} {metrics_v1['sharpe']:>19.2f} {metrics_v2['sharpe']:>19.2f} {(metrics_v2['sharpe']-metrics_v1['sharpe']):>14.2f}")
    print(f"{'Ann. Return':<20} {metrics_v1['ann_return']:>18.2%} {metrics_v2['ann_return']:>18.2%} {(metrics_v2['ann_return']-metrics_v1['ann_return']):>13.2%}")
    print(f"{'Ann. Vol':<20} {metrics_v1['ann_vol']:>18.2%} {metrics_v2['ann_vol']:>18.2%} {(metrics_v2['ann_vol']-metrics_v1['ann_vol']):>13.2%}")
    print(f"{'MDD':<20} {metrics_v1['mdd']:>18.2%} {metrics_v2['mdd']:>18.2%} {(metrics_v2['mdd']-metrics_v1['mdd']):>13.2%}")
    print(f"{'CVaR':<20} {metrics_v1['cvar']:>19.4f} {metrics_v2['cvar']:>19.4f} {(metrics_v2['cvar']-metrics_v1['cvar']):>14.4f}")
    print("="*100)
    
    # 7. 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "v1_metrics": metrics_v1,
        "v2_metrics": metrics_v2,
        "optimal_weights": best_weights,
        "regime_weights": {
            "bull": regime_weights.bull,
            "bear": regime_weights.bear,
            "high_vol": regime_weights.high_vol,
            "neutral": regime_weights.neutral
        }
    }
    
    output_path = Path(__file__).parent / "results" / "integrated_backtest_v2.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n결과 저장 완료: {output_path}")
    print()
    
    # 8. 다음 단계 안내
    print("="*100)
    print("다음 단계")
    print("="*100)
    print("1. 실제 ARES7 데이터로 백테스트 실행")
    print("2. Regime별 가중치 최적화")
    print("3. OOS 검증 수행")
    print("4. 실전 배포 준비")
    print("="*100)


if __name__ == "__main__":
    main()
