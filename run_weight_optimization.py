#!/usr/bin/env python3
"""
ARES7 QM Regime v2 - CVaR Lambda 및 Regime 가중치 최적화
Train/OOS 윈도우 분리하여 최적화 및 검증
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ensemble.dynamic_ensemble_v2 import dynamic_ensemble_3engines, RegimeWeights
from ensemble.weight_optimizer_cvar import grid_search_cvar, evaluate_weights


def compute_metrics(returns: pd.Series, name: str = "") -> dict:
    """백테스트 성능 지표 계산"""
    returns = returns.dropna()
    if returns.empty:
        return {}
    
    cum_ret = (1 + returns).cumprod()
    total_ret = cum_ret.iloc[-1] - 1
    
    days = (returns.index[-1] - returns.index[0]).days
    years = days / 365.25
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    
    vol = returns.std() * np.sqrt(252)
    sharpe = ann_ret / vol if vol > 0 else 0
    
    cum_max = cum_ret.cummax()
    drawdown = (cum_ret - cum_max) / cum_max
    mdd = drawdown.min()
    
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
    print("ARES7 QM Regime v2 - CVaR Lambda 및 Regime 가중치 최적화")
    print("="*100)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 실제 데이터 로드
    print("실제 엔진 수익률 데이터 로드 중...")
    returns_df = pd.read_csv('results/engine_returns_real_data.csv', 
                             index_col=0, parse_dates=[0])
    print(f"  데이터: {returns_df.shape}, 기간: {returns_df.index[0]} ~ {returns_df.index[-1]}")
    print(f"  엔진: {list(returns_df.columns)}\n")
    
    # 2. Train/OOS 분리 (70/30)
    split_date = returns_df.index[int(len(returns_df) * 0.7)]
    train_df = returns_df[returns_df.index < split_date]
    oos_df = returns_df[returns_df.index >= split_date]
    
    print(f"Train 기간: {train_df.index[0]} ~ {train_df.index[-1]} ({len(train_df)} days)")
    print(f"OOS 기간: {oos_df.index[0]} ~ {oos_df.index[-1]} ({len(oos_df)} days)\n")
    
    # 3. CVaR Lambda 그리드 서치 (Train 기간)
    print("="*100)
    print("CVaR Lambda 그리드 서치 (Train 기간)")
    print("="*100)
    
    lambda_values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    best_lambda_results = []
    
    for lam in lambda_values:
        results = grid_search_cvar(train_df, step=0.1, cvar_lambda=lam)
        best = results[0]
        best_lambda_results.append({
            'lambda': lam,
            'weights': best['engine_weights'],
            'sharpe': best['sharpe'],
            'cvar': best['cvar'],
            'score': best['score']
        })
        print(f"  λ={lam:.1f}: Score={best['score']:.4f}, Sharpe={best['sharpe']:.4f}, CVaR={best['cvar']:.4f}")
    
    # 최적 lambda 선택
    best_lambda_result = max(best_lambda_results, key=lambda x: x['score'])
    optimal_lambda = best_lambda_result['lambda']
    optimal_weights = best_lambda_result['weights']
    
    print(f"\n최적 CVaR Lambda: {optimal_lambda}")
    print(f"최적 가중치: {optimal_weights}")
    print(f"Train Sharpe: {best_lambda_result['sharpe']:.4f}")
    print(f"Train CVaR: {best_lambda_result['cvar']:.4f}\n")
    
    # 4. OOS 검증
    print("="*100)
    print("OOS 검증")
    print("="*100)
    
    # 최적 가중치로 OOS 성능 계산
    weights_array = np.array([optimal_weights['qm'], optimal_weights['lv'], optimal_weights['def']])
    oos_result = evaluate_weights(oos_df, weights_array, cvar_lambda=optimal_lambda)
    
    print(f"OOS Sharpe: {oos_result['sharpe']:.4f}")
    print(f"OOS CVaR: {oos_result['cvar']:.4f}")
    print(f"OOS Ann. Return: {oos_result['ann_return']:.2%}")
    print(f"OOS Ann. Vol: {oos_result['ann_vol']:.2%}\n")
    
    # 5. Regime별 가중치 최적화
    print("="*100)
    print("Regime별 가중치 최적화")
    print("="*100)
    
    # Regime 데이터 로드
    regime = pd.read_csv('data/bull_regime.csv', index_col=0, parse_dates=[0])
    regime.index = pd.to_datetime(regime.index).normalize()
    regime = regime.reindex(train_df.index, method='ffill')
    
    # BULL/BEAR 레짐 분리
    bull_mask = regime.iloc[:, 0] == True
    bear_mask = regime.iloc[:, 0] == False
    
    train_bull = train_df[bull_mask]
    train_bear = train_df[bear_mask]
    
    print(f"BULL 기간: {len(train_bull)} days")
    print(f"BEAR 기간: {len(train_bear)} days\n")
    
    # BULL 레짐 최적 가중치
    if len(train_bull) > 100:
        print("BULL 레짐 최적화...")
        bull_results = grid_search_cvar(train_bull, step=0.1, cvar_lambda=optimal_lambda)
        bull_best = bull_results[0]
        bull_weights = bull_best['engine_weights']
        print(f"  BULL 가중치: {bull_weights}")
        print(f"  BULL Sharpe: {bull_best['sharpe']:.4f}, CVaR: {bull_best['cvar']:.4f}\n")
    else:
        bull_weights = optimal_weights
        print(f"  BULL 데이터 부족, 전체 최적 가중치 사용: {bull_weights}\n")
    
    # BEAR 레짐 최적 가중치
    if len(train_bear) > 100:
        print("BEAR 레짐 최적화...")
        bear_results = grid_search_cvar(train_bear, step=0.1, cvar_lambda=optimal_lambda)
        bear_best = bear_results[0]
        bear_weights = bear_best['engine_weights']
        print(f"  BEAR 가중치: {bear_weights}")
        print(f"  BEAR Sharpe: {bear_best['sharpe']:.4f}, CVaR: {bear_best['cvar']:.4f}\n")
    else:
        bear_weights = optimal_weights
        print(f"  BEAR 데이터 부족, 전체 최적 가중치 사용: {bear_weights}\n")
    
    # 6. Dynamic Ensemble 백테스트 (전체 기간)
    print("="*100)
    print("Dynamic Ensemble 백테스트 (전체 기간)")
    print("="*100)
    
    # Regime 시리즈 생성
    regime_full = pd.read_csv('data/bull_regime.csv', index_col=0, parse_dates=[0])
    regime_full.index = pd.to_datetime(regime_full.index).normalize()
    regime_full = regime_full.reindex(returns_df.index, method='ffill')
    regime_series = regime_full.iloc[:, 0].map({True: 'BULL', False: 'BEAR'})
    
    # Regime 가중치 설정
    regime_weights = RegimeWeights(
        bull=bull_weights,
        bear=bear_weights,
        high_vol=bear_weights,  # HIGH_VOL은 BEAR와 동일하게 처리
        neutral=optimal_weights  # NEUTRAL은 전체 최적 가중치 사용
    )
    
    # Dynamic Ensemble 수익률 계산
    ret_ensemble = dynamic_ensemble_3engines(
        returns_df['qm'],
        returns_df['lv'],
        returns_df['def'],
        regime_series,
        regime_weights
    )
    
    # 전체 기간 성능
    metrics_ensemble = compute_metrics(ret_ensemble, "Dynamic Ensemble")
    print(f"\n전체 기간 성능:")
    print(f"  Sharpe: {metrics_ensemble['sharpe']:.2f}")
    print(f"  Ann. Return: {metrics_ensemble['ann_return']:.2%}")
    print(f"  Ann. Vol: {metrics_ensemble['ann_vol']:.2%}")
    print(f"  MDD: {metrics_ensemble['mdd']:.2%}")
    print(f"  CVaR: {metrics_ensemble['cvar']:.4f}\n")
    
    # Train/OOS 분리 성능
    ret_ensemble_train = ret_ensemble[ret_ensemble.index < split_date]
    ret_ensemble_oos = ret_ensemble[ret_ensemble.index >= split_date]
    
    metrics_train = compute_metrics(ret_ensemble_train, "Train")
    metrics_oos = compute_metrics(ret_ensemble_oos, "OOS")
    
    print(f"Train 성능:")
    print(f"  Sharpe: {metrics_train['sharpe']:.2f}, MDD: {metrics_train['mdd']:.2%}, CVaR: {metrics_train['cvar']:.4f}")
    print(f"\nOOS 성능:")
    print(f"  Sharpe: {metrics_oos['sharpe']:.2f}, MDD: {metrics_oos['mdd']:.2%}, CVaR: {metrics_oos['cvar']:.4f}\n")
    
    # 7. 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "optimal_lambda": optimal_lambda,
        "optimal_weights": optimal_weights,
        "regime_weights": {
            "bull": bull_weights,
            "bear": bear_weights,
            "high_vol": bear_weights,
            "neutral": optimal_weights
        },
        "performance": {
            "full": metrics_ensemble,
            "train": metrics_train,
            "oos": metrics_oos
        },
        "lambda_search_results": best_lambda_results
    }
    
    output_path = Path('results/weight_optimization_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    # 앙상블 수익률 저장
    ret_ensemble.to_csv('results/ensemble_returns_optimized.csv')
    
    print(f"결과 저장 완료:")
    print(f"  {output_path}")
    print(f"  results/ensemble_returns_optimized.csv")
    print("\n" + "="*100)


if __name__ == "__main__":
    main()
