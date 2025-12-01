#!/usr/bin/env python3
"""
ARES7 Adaptive Asymmetric Risk Management 백테스트
수익률 유지하면서 MDD -10% 이하 달성
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from risk.adaptive_asymmetric_risk_manager import (
    apply_adaptive_risk_management,
    calculate_performance_metrics
)


def main():
    print("="*100)
    print("ARES7 Adaptive Asymmetric Risk Management 백테스트")
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
    
    # Prices 생성 (cumulative returns)
    prices = (1 + ensemble_returns).cumprod() * 100
    
    print(f"  데이터: {len(ensemble_returns)} days, {ensemble_returns.index[0]} ~ {ensemble_returns.index[-1]}\n")
    
    # 2. 기존 성능 (개선 전)
    print("="*100)
    print("기존 ARES7 Dynamic Ensemble 성능")
    print("="*100)
    
    metrics_before = calculate_performance_metrics(ensemble_returns)
    print(f"  Sharpe Ratio: {metrics_before['sharpe_ratio']:.2f}")
    print(f"  Ann. Return: {metrics_before['annualized_return']:.2%}")
    print(f"  Ann. Vol: {metrics_before['annualized_volatility']:.2%}")
    print(f"  MDD: {metrics_before['max_drawdown']:.2%}")
    print(f"  CVaR (95%): {metrics_before['cvar_95']:.4f}")
    print(f"  Sortino Ratio: {metrics_before['sortino_ratio']:.2f}\n")
    
    # 3. Adaptive Asymmetric Risk Management 적용
    print("="*100)
    print("Adaptive Asymmetric Risk Management 적용 중...")
    print("="*100)
    
    # 파라미터 그리드 서치
    param_grid = [
        # (base_leverage, max_leverage, target_vol)
        (1.0, 1.8, 0.20),
        (1.1, 2.0, 0.20),
        (1.2, 2.2, 0.20),
        (1.0, 2.0, 0.18),
        (1.0, 2.0, 0.22),
        (1.1, 2.0, 0.18),
    ]
    
    results_list = []
    
    for base_lev, max_lev, target_vol in param_grid:
        # AARM 적용 (코드 수정 필요 - 파라미터 전달)
        from risk.adaptive_asymmetric_risk_manager import AdaptiveAsymmetricRiskManager
        
        arm = AdaptiveAsymmetricRiskManager(
            base_leverage=base_lev,
            max_leverage=max_lev,
            target_vol=target_vol,
            max_dd_threshold=-0.10
        )
        
        # 수동으로 적용
        cum_returns = (1 + ensemble_returns).cumprod()
        rolling_max = cum_returns.expanding().max()
        drawdowns = (cum_returns - rolling_max) / rolling_max
        
        managed_returns = []
        
        for i in range(arm.lookback_days, len(ensemble_returns)):
            current_returns = ensemble_returns.iloc[:i+1]
            current_prices = prices.iloc[:i+1]
            current_dd = drawdowns.iloc[i]
            
            position_info = arm.calculate_adaptive_position_size(
                current_returns, 
                current_prices, 
                current_dd
            )
            
            managed_return = ensemble_returns.iloc[i] * position_info['position_size']
            managed_returns.append(managed_return)
        
        # 초기 기간은 base leverage 적용
        initial_returns = ensemble_returns.iloc[:arm.lookback_days] * base_lev
        full_managed_returns = pd.concat([initial_returns, pd.Series(managed_returns, index=ensemble_returns.index[arm.lookback_days:])])
        
        # 성능 계산
        metrics = calculate_performance_metrics(full_managed_returns)
        metrics['params'] = {
            'base_leverage': base_lev,
            'max_leverage': max_lev,
            'target_vol': target_vol
        }
        results_list.append(metrics)
        
        print(f"  Base={base_lev:.1f}, Max={max_lev:.1f}, Vol={target_vol:.2f}: "
              f"Sharpe={metrics['sharpe_ratio']:.2f}, Return={metrics['annualized_return']:.2%}, MDD={metrics['max_drawdown']:.2%}")
    
    # 4. 최적 파라미터 선정
    print("\n" + "="*100)
    print("최적 파라미터 선정")
    print("="*100)
    
    # MDD -10% 이하 + 수익률 최대화
    valid_results = [r for r in results_list if r['max_drawdown'] >= -0.10]
    
    if valid_results:
        best_result = max(valid_results, key=lambda x: x['annualized_return'])
        print(f"\n✓ MDD -10% 목표 달성하면서 수익률 최대화!")
    else:
        # MDD가 가장 좋으면서 수익률도 높은 것
        best_result = max(results_list, key=lambda x: (x['max_drawdown'], x['annualized_return']))
        print(f"\n⚠ MDD -10% 미달성, 최선의 결과 선택")
    
    print(f"  최적 파라미터:")
    print(f"    Base Leverage: {best_result['params']['base_leverage']:.1f}")
    print(f"    Max Leverage: {best_result['params']['max_leverage']:.1f}")
    print(f"    Target Vol: {best_result['params']['target_vol']:.2%}")
    
    # 5. 최적 파라미터로 최종 백테스트
    print("\n" + "="*100)
    print("최종 백테스트 (최적 파라미터)")
    print("="*100)
    
    arm_final = AdaptiveAsymmetricRiskManager(
        base_leverage=best_result['params']['base_leverage'],
        max_leverage=best_result['params']['max_leverage'],
        target_vol=best_result['params']['target_vol'],
        max_dd_threshold=-0.10
    )
    
    # 최종 적용
    cum_returns = (1 + ensemble_returns).cumprod()
    rolling_max = cum_returns.expanding().max()
    drawdowns = (cum_returns - rolling_max) / rolling_max
    
    final_managed_returns = []
    
    for i in range(arm_final.lookback_days, len(ensemble_returns)):
        current_returns = ensemble_returns.iloc[:i+1]
        current_prices = prices.iloc[:i+1]
        current_dd = drawdowns.iloc[i]
        
        position_info = arm_final.calculate_adaptive_position_size(
            current_returns, 
            current_prices, 
            current_dd
        )
        
        managed_return = ensemble_returns.iloc[i] * position_info['position_size']
        final_managed_returns.append(managed_return)
    
    initial_returns = ensemble_returns.iloc[:arm_final.lookback_days] * best_result['params']['base_leverage']
    full_final_returns = pd.concat([initial_returns, pd.Series(final_managed_returns, index=ensemble_returns.index[arm_final.lookback_days:])])
    
    metrics_after = calculate_performance_metrics(full_final_returns)
    
    print(f"  Sharpe Ratio: {metrics_after['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {metrics_after['sortino_ratio']:.2f}")
    print(f"  Ann. Return: {metrics_after['annualized_return']:.2%}")
    print(f"  Ann. Vol: {metrics_after['annualized_volatility']:.2%}")
    print(f"  MDD: {metrics_after['max_drawdown']:.2%}")
    print(f"  CVaR (95%): {metrics_after['cvar_95']:.4f}\n")
    
    # 6. 성능 비교
    print("="*100)
    print("성능 비교 요약")
    print("="*100)
    print(f"{'Metric':<25} {'Before':<20} {'After':<20} {'Change':<15}")
    print("-"*100)
    print(f"{'Sharpe Ratio':<25} {metrics_before['sharpe_ratio']:>19.2f} {metrics_after['sharpe_ratio']:>19.2f} {(metrics_after['sharpe_ratio']-metrics_before['sharpe_ratio']):>14.2f}")
    print(f"{'Sortino Ratio':<25} {metrics_before['sortino_ratio']:>19.2f} {metrics_after['sortino_ratio']:>19.2f} {(metrics_after['sortino_ratio']-metrics_before['sortino_ratio']):>14.2f}")
    print(f"{'Ann. Return':<25} {metrics_before['annualized_return']:>18.2%} {metrics_after['annualized_return']:>18.2%} {(metrics_after['annualized_return']-metrics_before['annualized_return']):>13.2%}")
    print(f"{'Ann. Vol':<25} {metrics_before['annualized_volatility']:>18.2%} {metrics_after['annualized_volatility']:>18.2%} {(metrics_after['annualized_volatility']-metrics_before['annualized_volatility']):>13.2%}")
    print(f"{'MDD':<25} {metrics_before['max_drawdown']:>18.2%} {metrics_after['max_drawdown']:>18.2%} {(metrics_after['max_drawdown']-metrics_before['max_drawdown']):>13.2%}")
    print(f"{'CVaR (95%)':<25} {metrics_before['cvar_95']:>19.4f} {metrics_after['cvar_95']:>19.4f} {(metrics_after['cvar_95']-metrics_before['cvar_95']):>14.4f}")
    print("="*100)
    
    # 7. 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "optimal_params": best_result['params'],
        "performance_before": metrics_before,
        "performance_after": metrics_after,
        "all_param_results": results_list
    }
    
    output_path = Path('results/aarm_backtest_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    # 개선된 수익률 저장
    full_final_returns.to_csv('results/ensemble_returns_aarm.csv')
    
    print(f"\n결과 저장 완료:")
    print(f"  {output_path}")
    print(f"  results/ensemble_returns_aarm.csv")
    print("\n" + "="*100)


if __name__ == "__main__":
    main()
