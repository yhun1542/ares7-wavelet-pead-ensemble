#!/usr/bin/env python3
"""
ARES7 AARM 백테스트 (룩어헤드 바이어스 수정 + 거래 비용 반영 + OOS 검증)
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from risk.adaptive_asymmetric_risk_manager import (
    AdaptiveAsymmetricRiskManager,
    calculate_performance_metrics
)


def backtest_with_costs(returns: pd.Series, 
                       prices: pd.Series,
                       arm: AdaptiveAsymmetricRiskManager,
                       transaction_cost: float = 0.001) -> pd.DataFrame:
    """
    룩어헤드 바이어스 제거 + 거래 비용 반영 백테스트
    
    Args:
        returns: 일간 수익률
        prices: 가격 시리즈
        arm: AARM 인스턴스
        transaction_cost: 거래 비용 (0.001 = 0.1% = 편도 10bp)
    """
    # Drawdown 계산
    cum_returns = (1 + returns).cumprod()
    rolling_max = cum_returns.expanding().max()
    drawdowns = (cum_returns - rolling_max) / rolling_max
    
    managed_returns = []
    position_sizes = []
    turnover_list = []
    prev_position = arm.base_leverage
    
    # 룩어헤드 바이어스 제거: i-1번째 데이터로 계산한 포지션을 i번째 수익률에 적용
    for i in range(arm.lookback_days + 1, len(returns)):
        # i-1번째까지의 데이터만 사용 (i번째 수익률은 아직 모름)
        current_returns = returns.iloc[:i]  # i-1번째까지
        current_prices = prices.iloc[:i]
        current_dd = drawdowns.iloc[i-1]  # i-1번째 drawdown
        
        # i-1번째 데이터로 포지션 크기 계산
        position_info = arm.calculate_adaptive_position_size(
            current_returns, 
            current_prices, 
            current_dd
        )
        
        position_size = position_info['position_size']
        
        # 거래 비용 계산 (포지션 변화량에 비례)
        turnover = abs(position_size - prev_position)
        cost = turnover * transaction_cost
        
        # i번째 수익률에 포지션 적용 (룩어헤드 바이어스 제거)
        managed_return = returns.iloc[i] * position_size - cost
        
        managed_returns.append(managed_return)
        position_sizes.append(position_size)
        turnover_list.append(turnover)
        prev_position = position_size
    
    # 초기 기간 (base leverage 적용)
    initial_returns = returns.iloc[:arm.lookback_days + 1] * arm.base_leverage
    full_managed_returns = pd.concat([
        initial_returns, 
        pd.Series(managed_returns, index=returns.index[arm.lookback_days + 1:])
    ])
    
    # 통계 정보
    avg_turnover = np.mean(turnover_list)
    total_costs = sum([t * transaction_cost for t in turnover_list])
    
    return full_managed_returns, {
        'avg_turnover': avg_turnover,
        'total_costs': total_costs,
        'avg_position_size': np.mean(position_sizes)
    }


def main():
    print("="*100)
    print("ARES7 AARM 백테스트 (룩어헤드 바이어스 수정 + 거래 비용 반영 + OOS 검증)")
    print("="*100)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 데이터 로드
    print("데이터 로드 중...")
    ensemble_returns = pd.read_csv(
        'results/ensemble_returns_optimized.csv',
        index_col=0,
        parse_dates=[0]
    )
    
    if isinstance(ensemble_returns, pd.DataFrame):
        ensemble_returns = ensemble_returns.iloc[:, 0]
    
    ensemble_returns = ensemble_returns.dropna()
    prices = (1 + ensemble_returns).cumprod() * 100
    
    print(f"  전체 데이터: {len(ensemble_returns)} days, {ensemble_returns.index[0]} ~ {ensemble_returns.index[-1]}\n")
    
    # 2. Train/Test 분할 (70/30)
    split_idx = int(len(ensemble_returns) * 0.7)
    train_returns = ensemble_returns.iloc[:split_idx]
    test_returns = ensemble_returns.iloc[split_idx:]
    
    train_prices = prices.iloc[:split_idx]
    test_prices = prices.iloc[split_idx:]
    
    print("="*100)
    print("Train/Test 분할")
    print("="*100)
    print(f"  Train: {len(train_returns)} days ({train_returns.index[0]} ~ {train_returns.index[-1]})")
    print(f"  Test (OOS): {len(test_returns)} days ({test_returns.index[0]} ~ {test_returns.index[-1]})\n")
    
    # 3. 기존 성능 (개선 전)
    print("="*100)
    print("기존 ARES7 성능 (Train)")
    print("="*100)
    
    metrics_before_train = calculate_performance_metrics(train_returns)
    print(f"  Sharpe: {metrics_before_train['sharpe_ratio']:.2f}, "
          f"Return: {metrics_before_train['annualized_return']:.2%}, "
          f"MDD: {metrics_before_train['max_drawdown']:.2%}\n")
    
    print("기존 ARES7 성능 (Test/OOS)")
    print("-"*100)
    metrics_before_test = calculate_performance_metrics(test_returns)
    print(f"  Sharpe: {metrics_before_test['sharpe_ratio']:.2f}, "
          f"Return: {metrics_before_test['annualized_return']:.2%}, "
          f"MDD: {metrics_before_test['max_drawdown']:.2%}\n")
    
    # 4. Train에서 최적 파라미터 찾기
    print("="*100)
    print("Train 데이터에서 최적 파라미터 탐색")
    print("="*100)
    
    param_grid = [
        (1.0, 1.8, 0.20, 0.001),  # (base_lev, max_lev, target_vol, tx_cost)
        (1.1, 2.0, 0.20, 0.001),
        (1.0, 2.0, 0.18, 0.001),
        (1.0, 1.5, 0.20, 0.001),  # 보수적
    ]
    
    train_results = []
    
    for base_lev, max_lev, target_vol, tx_cost in param_grid:
        arm = AdaptiveAsymmetricRiskManager(
            base_leverage=base_lev,
            max_leverage=max_lev,
            target_vol=target_vol,
            max_dd_threshold=-0.10
        )
        
        managed_returns, stats = backtest_with_costs(
            train_returns, train_prices, arm, tx_cost
        )
        
        metrics = calculate_performance_metrics(managed_returns)
        metrics['params'] = {
            'base_leverage': base_lev,
            'max_leverage': max_lev,
            'target_vol': target_vol,
            'tx_cost': tx_cost
        }
        metrics['stats'] = stats
        train_results.append(metrics)
        
        print(f"  Base={base_lev:.1f}, Max={max_lev:.1f}, Vol={target_vol:.2f}, Cost={tx_cost:.3f}: "
              f"Sharpe={metrics['sharpe_ratio']:.2f}, Return={metrics['annualized_return']:.2%}, "
              f"MDD={metrics['max_drawdown']:.2%}, Turnover={stats['avg_turnover']:.3f}")
    
    # 최적 파라미터 선정 (MDD -10% 이하 + Sharpe 최대)
    valid_results = [r for r in train_results if r['max_drawdown'] >= -0.10]
    
    if valid_results:
        best_result = max(valid_results, key=lambda x: x['sharpe_ratio'])
        print(f"\n✓ 최적 파라미터 (Train): Base={best_result['params']['base_leverage']:.1f}, "
              f"Max={best_result['params']['max_leverage']:.1f}, Vol={best_result['params']['target_vol']:.2f}")
    else:
        best_result = max(train_results, key=lambda x: (x['max_drawdown'], x['sharpe_ratio']))
        print(f"\n⚠ MDD -10% 미달성, 최선의 결과 선택")
    
    # 5. Test (OOS) 검증
    print("\n" + "="*100)
    print("OOS (Out-of-Sample) 검증")
    print("="*100)
    
    arm_oos = AdaptiveAsymmetricRiskManager(
        base_leverage=best_result['params']['base_leverage'],
        max_leverage=best_result['params']['max_leverage'],
        target_vol=best_result['params']['target_vol'],
        max_dd_threshold=-0.10
    )
    
    # OOS 백테스트 (전체 데이터 사용하되, Test 기간만 평가)
    full_managed_returns, full_stats = backtest_with_costs(
        ensemble_returns, prices, arm_oos, best_result['params']['tx_cost']
    )
    
    # Test 기간만 추출
    test_managed_returns = full_managed_returns.loc[test_returns.index]
    
    metrics_after_test = calculate_performance_metrics(test_managed_returns)
    
    print(f"Train 성능: Sharpe={best_result['sharpe_ratio']:.2f}, "
          f"Return={best_result['annualized_return']:.2%}, MDD={best_result['max_drawdown']:.2%}")
    print(f"OOS 성능:   Sharpe={metrics_after_test['sharpe_ratio']:.2f}, "
          f"Return={metrics_after_test['annualized_return']:.2%}, MDD={metrics_after_test['max_drawdown']:.2%}")
    
    # 과적합 여부 판단
    sharpe_diff = metrics_after_test['sharpe_ratio'] - best_result['sharpe_ratio']
    if sharpe_diff < -0.5:
        print(f"\n⚠ 과적합 가능성: OOS Sharpe가 Train보다 {abs(sharpe_diff):.2f} 낮음")
    else:
        print(f"\n✓ 과적합 없음: OOS Sharpe 차이 {sharpe_diff:+.2f}")
    
    # 6. 전체 기간 최종 성능
    print("\n" + "="*100)
    print("전체 기간 최종 성능 (룩어헤드 바이어스 수정 + 거래 비용 반영)")
    print("="*100)
    
    metrics_after_full = calculate_performance_metrics(full_managed_returns)
    
    print(f"  Sharpe Ratio: {metrics_after_full['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {metrics_after_full['sortino_ratio']:.2f}")
    print(f"  Ann. Return: {metrics_after_full['annualized_return']:.2%}")
    print(f"  Ann. Vol: {metrics_after_full['annualized_volatility']:.2%}")
    print(f"  MDD: {metrics_after_full['max_drawdown']:.2%}")
    print(f"  CVaR (95%): {metrics_after_full['cvar_95']:.4f}")
    print(f"  Avg Turnover: {full_stats['avg_turnover']:.3f}")
    print(f"  Total Costs: {full_stats['total_costs']:.4f}\n")
    
    # 7. Before/After 비교
    metrics_before_full = calculate_performance_metrics(ensemble_returns)
    
    print("="*100)
    print("Before/After 비교 (전체 기간)")
    print("="*100)
    print(f"{'Metric':<25} {'Before':<20} {'After (Fixed)':<20} {'Change':<15}")
    print("-"*100)
    print(f"{'Sharpe Ratio':<25} {metrics_before_full['sharpe_ratio']:>19.2f} {metrics_after_full['sharpe_ratio']:>19.2f} {(metrics_after_full['sharpe_ratio']-metrics_before_full['sharpe_ratio']):>14.2f}")
    print(f"{'Ann. Return':<25} {metrics_before_full['annualized_return']:>18.2%} {metrics_after_full['annualized_return']:>18.2%} {(metrics_after_full['annualized_return']-metrics_before_full['annualized_return']):>13.2%}")
    print(f"{'MDD':<25} {metrics_before_full['max_drawdown']:>18.2%} {metrics_after_full['max_drawdown']:>18.2%} {(metrics_after_full['max_drawdown']-metrics_before_full['max_drawdown']):>13.2%}")
    print("="*100)
    
    # 8. 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "lookahead_bias": "FIXED",
        "transaction_costs": "INCLUDED",
        "oos_validation": "PASSED" if sharpe_diff >= -0.5 else "FAILED",
        "optimal_params": best_result['params'],
        "performance_train": best_result,
        "performance_oos": metrics_after_test,
        "performance_full": metrics_after_full,
        "statistics": full_stats
    }
    
    with open('results/aarm_backtest_fixed_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    full_managed_returns.to_csv('results/ensemble_returns_aarm_fixed.csv')
    
    print(f"\n결과 저장 완료:")
    print(f"  results/aarm_backtest_fixed_results.json")
    print(f"  results/ensemble_returns_aarm_fixed.csv\n")


if __name__ == "__main__":
    main()
