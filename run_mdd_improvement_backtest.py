#!/usr/bin/env python3
"""
ARES7 MDD 개선 백테스트
4개 AI 모델 제안 기법 적용 및 성능 검증
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from risk.mdd_improvement import apply_mdd_improvement, calculate_mdd


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
    print("ARES7 MDD 개선 백테스트 (4개 AI 모델 제안 통합)")
    print("="*100)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 실제 앙상블 수익률 로드
    print("실제 ARES7 앙상블 수익률 로드 중...")
    ensemble_returns = pd.read_csv(
        'results/ensemble_returns_optimized.csv',
        index_col=0,
        parse_dates=[0]
    )
    
    if isinstance(ensemble_returns, pd.DataFrame):
        ensemble_returns = ensemble_returns.iloc[:, 0]
    
    ensemble_returns = ensemble_returns.dropna()
    print(f"  데이터: {len(ensemble_returns)} days, {ensemble_returns.index[0]} ~ {ensemble_returns.index[-1]}\n")
    
    # 2. 기존 성능 (MDD 개선 전)
    print("="*100)
    print("기존 ARES7 Dynamic Ensemble 성능 (MDD 개선 전)")
    print("="*100)
    
    metrics_before = compute_metrics(ensemble_returns, "Before MDD Improvement")
    print(f"  Sharpe Ratio: {metrics_before['sharpe']:.2f}")
    print(f"  Ann. Return: {metrics_before['ann_return']:.2%}")
    print(f"  Ann. Vol: {metrics_before['ann_vol']:.2%}")
    print(f"  MDD: {metrics_before['mdd']:.2%}")
    print(f"  CVaR (95%): {metrics_before['cvar']:.4f}\n")
    
    # 3. MDD 개선 기법 적용 (파라미터 그리드 서치)
    print("="*100)
    print("MDD 개선 파라미터 그리드 서치")
    print("="*100)
    
    param_grid = [
        # (target_vol, mdd_threshold, defensive_exposure)
        (0.10, -0.08, 0.3),
        (0.12, -0.08, 0.3),
        (0.15, -0.08, 0.3),
        (0.12, -0.06, 0.3),
        (0.12, -0.10, 0.3),
        (0.12, -0.08, 0.2),
        (0.12, -0.08, 0.4),
        (0.12, -0.08, 0.5),
    ]
    
    results = []
    
    for target_vol, mdd_thresh, def_exp in param_grid:
        improved_returns = apply_mdd_improvement(
            ensemble_returns,
            target_volatility=target_vol,
            mdd_threshold=mdd_thresh,
            defensive_exposure=def_exp
        )
        
        metrics = compute_metrics(improved_returns, f"Vol={target_vol}, MDD={mdd_thresh}, Def={def_exp}")
        metrics['params'] = {
            'target_vol': target_vol,
            'mdd_threshold': mdd_thresh,
            'defensive_exposure': def_exp
        }
        results.append(metrics)
        
        print(f"  Vol={target_vol:.2f}, MDD_thresh={mdd_thresh:.2%}, Def_exp={def_exp:.1%}: "
              f"Sharpe={metrics['sharpe']:.2f}, MDD={metrics['mdd']:.2%}")
    
    # 4. 최적 파라미터 선정 (MDD 목표 달성 + Sharpe 최대화)
    print("\n" + "="*100)
    print("최적 파라미터 선정")
    print("="*100)
    
    # MDD -10% 이하 달성한 결과만 필터링
    valid_results = [r for r in results if r['mdd'] >= -0.10]
    
    if valid_results:
        # Sharpe가 가장 높은 것 선택
        best_result = max(valid_results, key=lambda x: x['sharpe'])
        print(f"\n✓ MDD -10% 목표 달성 가능!")
        print(f"  최적 파라미터:")
        print(f"    Target Volatility: {best_result['params']['target_vol']:.2%}")
        print(f"    MDD Threshold: {best_result['params']['mdd_threshold']:.2%}")
        print(f"    Defensive Exposure: {best_result['params']['defensive_exposure']:.1%}")
    else:
        # MDD 개선이 가장 큰 것 선택
        best_result = max(results, key=lambda x: x['mdd'])
        print(f"\n⚠ MDD -10% 목표 미달성, 최대 개선 결과 선택")
        print(f"  최적 파라미터:")
        print(f"    Target Volatility: {best_result['params']['target_vol']:.2%}")
        print(f"    MDD Threshold: {best_result['params']['mdd_threshold']:.2%}")
        print(f"    Defensive Exposure: {best_result['params']['defensive_exposure']:.1%}")
    
    # 5. 최적 파라미터로 최종 백테스트
    print("\n" + "="*100)
    print("최종 MDD 개선 백테스트 (최적 파라미터)")
    print("="*100)
    
    final_improved_returns = apply_mdd_improvement(
        ensemble_returns,
        target_volatility=best_result['params']['target_vol'],
        mdd_threshold=best_result['params']['mdd_threshold'],
        defensive_exposure=best_result['params']['defensive_exposure']
    )
    
    metrics_after = compute_metrics(final_improved_returns, "After MDD Improvement")
    print(f"  Sharpe Ratio: {metrics_after['sharpe']:.2f}")
    print(f"  Ann. Return: {metrics_after['ann_return']:.2%}")
    print(f"  Ann. Vol: {metrics_after['ann_vol']:.2%}")
    print(f"  MDD: {metrics_after['mdd']:.2%}")
    print(f"  CVaR (95%): {metrics_after['cvar']:.4f}\n")
    
    # 6. 성능 비교
    print("="*100)
    print("성능 비교 요약")
    print("="*100)
    print(f"{'Metric':<20} {'Before':<20} {'After':<20} {'Change':<15}")
    print("-"*100)
    print(f"{'Sharpe Ratio':<20} {metrics_before['sharpe']:>19.2f} {metrics_after['sharpe']:>19.2f} {(metrics_after['sharpe']-metrics_before['sharpe']):>14.2f}")
    print(f"{'Ann. Return':<20} {metrics_before['ann_return']:>18.2%} {metrics_after['ann_return']:>18.2%} {(metrics_after['ann_return']-metrics_before['ann_return']):>13.2%}")
    print(f"{'Ann. Vol':<20} {metrics_before['ann_vol']:>18.2%} {metrics_after['ann_vol']:>18.2%} {(metrics_after['ann_vol']-metrics_before['ann_vol']):>13.2%}")
    print(f"{'MDD':<20} {metrics_before['mdd']:>18.2%} {metrics_after['mdd']:>18.2%} {(metrics_after['mdd']-metrics_before['mdd']):>13.2%}")
    print(f"{'CVaR':<20} {metrics_before['cvar']:>19.4f} {metrics_after['cvar']:>19.4f} {(metrics_after['cvar']-metrics_before['cvar']):>14.4f}")
    print("="*100)
    
    # 7. 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "optimal_params": best_result['params'],
        "performance_before": metrics_before,
        "performance_after": metrics_after,
        "all_param_results": results
    }
    
    output_path = Path('results/mdd_improvement_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    # 개선된 수익률 저장
    final_improved_returns.to_csv('results/ensemble_returns_mdd_improved.csv')
    
    print(f"\n결과 저장 완료:")
    print(f"  {output_path}")
    print(f"  results/ensemble_returns_mdd_improved.csv")
    print("\n" + "="*100)


if __name__ == "__main__":
    main()
