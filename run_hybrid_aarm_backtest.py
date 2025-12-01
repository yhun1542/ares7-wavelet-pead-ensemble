#!/usr/bin/env python3
"""
ARES7 Hybrid AARM: 기존 AARM + MDD Circuit Breaker
Sharpe 유지하면서 MDD만 선택적으로 개선
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from risk.adaptive_asymmetric_risk_manager import AdaptiveAsymmetricRiskManager


class HybridAARMStrategy(AdaptiveAsymmetricRiskManager):
    """
    Hybrid AARM: 기존 AARM + MDD Circuit Breaker
    - 평상시: 기존 AARM 로직 사용 (공격적)
    - MDD 근접 시: Circuit Breaker 발동 (방어적)
    """
    
    def __init__(self, 
                 base_leverage: float = 1.0,
                 max_leverage: float = 2.0,
                 target_vol: float = 0.18,
                 mdd_threshold: float = -0.10,
                 circuit_breaker_trigger: float = -0.08):
        
        super().__init__(base_leverage, max_leverage, target_vol, mdd_threshold)
        
        self.circuit_breaker_trigger = circuit_breaker_trigger
        self.circuit_breaker_active = False
        
    def calculate_position_with_circuit_breaker(self,
                                                returns: pd.Series,
                                                prices: pd.Series,
                                                current_drawdown: float) -> dict:
        """Circuit Breaker 포함 포지션 계산"""
        
        # 기존 AARM 포지션 계산
        base_position_info = self.calculate_adaptive_position_size(
            returns, prices, current_drawdown
        )
        
        position_size = base_position_info['position_size']
        
        # Circuit Breaker 로직
        if current_drawdown <= self.circuit_breaker_trigger:
            # Circuit Breaker 발동: 급격한 포지션 축소
            self.circuit_breaker_active = True
            
            # MDD 근접도에 따라 포지션 축소
            proximity_to_mdd = (current_drawdown - self.circuit_breaker_trigger) / \
                              (self.max_dd_threshold - self.circuit_breaker_trigger)
            
            # 0 (trigger) → 1 (MDD)로 갈수록 포지션 축소
            circuit_breaker_factor = max(0.2, 1.0 - proximity_to_mdd * 0.8)
            
            position_size *= circuit_breaker_factor
            
            base_position_info['circuit_breaker'] = True
            base_position_info['cb_factor'] = circuit_breaker_factor
        else:
            # Circuit Breaker 해제 조건: DD가 -5% 이상 회복
            if current_drawdown > -0.05:
                self.circuit_breaker_active = False
            
            # Circuit Breaker가 활성화되어 있으면 보수적 유지
            if self.circuit_breaker_active:
                position_size *= 0.7
                base_position_info['circuit_breaker'] = True
                base_position_info['cb_factor'] = 0.7
            else:
                base_position_info['circuit_breaker'] = False
        
        base_position_info['position_size'] = position_size
        
        return base_position_info


def backtest_hybrid_aarm(returns: pd.Series, 
                         strategy: HybridAARMStrategy,
                         transaction_cost: float = 0.001) -> tuple:
    """Hybrid AARM 백테스트"""
    
    cum_returns = (1 + returns).cumprod()
    rolling_max = cum_returns.expanding().max()
    drawdowns = (cum_returns - rolling_max) / rolling_max
    
    prices = cum_returns * 100
    
    managed_returns = []
    position_sizes = []
    cb_activations = []
    prev_position = strategy.base_leverage
    
    for i in range(strategy.lookback_days + 1, len(returns)):
        current_returns = returns.iloc[:i]
        current_prices = prices.iloc[:i]
        current_dd = drawdowns.iloc[i-1]
        
        position_info = strategy.calculate_position_with_circuit_breaker(
            current_returns,
            current_prices,
            current_dd
        )
        
        position_size = position_info['position_size']
        
        # 거래 비용
        turnover = abs(position_size - prev_position)
        cost = turnover * transaction_cost
        
        managed_return = returns.iloc[i] * position_size - cost
        
        managed_returns.append(managed_return)
        position_sizes.append(position_size)
        cb_activations.append(1 if position_info.get('circuit_breaker', False) else 0)
        prev_position = position_size
    
    initial_returns = returns.iloc[:strategy.lookback_days + 1] * strategy.base_leverage
    full_managed_returns = pd.concat([
        initial_returns,
        pd.Series(managed_returns, index=returns.index[strategy.lookback_days + 1:])
    ])
    
    cb_activation_rate = np.mean(cb_activations)
    
    return full_managed_returns, position_sizes, cb_activation_rate


def calculate_metrics(returns: pd.Series) -> dict:
    """성능 지표 계산"""
    cum_returns = (1 + returns).cumprod()
    
    n_years = len(returns) / 252
    total_return = cum_returns.iloc[-1] - 1
    ann_return = (1 + total_return) ** (1/n_years) - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0
    
    rolling_max = cum_returns.expanding().max()
    drawdowns = (cum_returns - rolling_max) / rolling_max
    max_dd = drawdowns.min()
    
    var_95 = returns.quantile(0.05)
    cvar_95 = returns[returns <= var_95].mean()
    
    downside_returns = returns[returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
    sortino = ann_return / downside_vol if downside_vol > 0 else 0
    
    return {
        'annualized_return': ann_return,
        'annualized_volatility': ann_vol,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'max_drawdown': max_dd,
        'cvar_95': cvar_95
    }


def main():
    print("="*100)
    print("ARES7 Hybrid AARM: 기존 AARM + MDD Circuit Breaker")
    print("="*100)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 데이터 로드
    ensemble_returns = pd.read_csv(
        'results/ensemble_returns_optimized.csv',
        index_col=0,
        parse_dates=[0]
    )
    
    if isinstance(ensemble_returns, pd.DataFrame):
        ensemble_returns = ensemble_returns.iloc[:, 0]
    
    ensemble_returns = ensemble_returns.dropna()
    
    print(f"데이터: {len(ensemble_returns)} days\n")
    
    # Train/Test 분할
    split_idx = int(len(ensemble_returns) * 0.7)
    train_returns = ensemble_returns.iloc[:split_idx]
    test_returns = ensemble_returns.iloc[split_idx:]
    
    print("="*100)
    print("파라미터 최적화 (Train)")
    print("="*100)
    
    param_grid = [
        (1.0, 1.5, 0.18, -0.08),  # (base, max, vol, cb_trigger)
        (1.0, 1.5, 0.18, -0.07),
        (1.0, 1.5, 0.18, -0.09),
        (1.1, 1.5, 0.18, -0.08),
        (1.0, 1.8, 0.18, -0.08),
    ]
    
    train_results = []
    
    for base_lev, max_lev, target_vol, cb_trigger in param_grid:
        strategy = HybridAARMStrategy(
            base_leverage=base_lev,
            max_leverage=max_lev,
            target_vol=target_vol,
            mdd_threshold=-0.10,
            circuit_breaker_trigger=cb_trigger
        )
        
        managed_returns, _, cb_rate = backtest_hybrid_aarm(train_returns, strategy)
        metrics = calculate_metrics(managed_returns)
        metrics['params'] = {
            'base': base_lev,
            'max': max_lev,
            'vol': target_vol,
            'cb_trigger': cb_trigger
        }
        metrics['cb_activation_rate'] = cb_rate
        train_results.append(metrics)
        
        print(f"  Base={base_lev:.1f}, Max={max_lev:.1f}, CB={cb_trigger:.2f}: "
              f"Sharpe={metrics['sharpe_ratio']:.2f}, "
              f"Return={metrics['annualized_return']:.2%}, "
              f"MDD={metrics['max_drawdown']:.2%}, "
              f"CB활성={cb_rate:.1%}")
    
    # 최적 파라미터 선정
    valid_results = [r for r in train_results if r['max_drawdown'] >= -0.10]
    
    if valid_results:
        best_result = max(valid_results, key=lambda x: x['sharpe_ratio'])
        print(f"\n✓ MDD -10% 달성!")
    else:
        best_result = max(train_results, key=lambda x: (x['max_drawdown'], x['sharpe_ratio']))
        print(f"\n⚠ MDD -10% 미달성")
    
    # OOS 검증
    print("\n" + "="*100)
    print("OOS 검증")
    print("="*100)
    
    strategy_oos = HybridAARMStrategy(
        base_leverage=best_result['params']['base'],
        max_leverage=best_result['params']['max'],
        target_vol=best_result['params']['vol'],
        mdd_threshold=-0.10,
        circuit_breaker_trigger=best_result['params']['cb_trigger']
    )
    
    full_managed_returns, _, cb_rate_full = backtest_hybrid_aarm(ensemble_returns, strategy_oos)
    test_managed_returns = full_managed_returns.loc[test_returns.index]
    
    metrics_oos = calculate_metrics(test_managed_returns)
    
    print(f"Train: Sharpe={best_result['sharpe_ratio']:.2f}, MDD={best_result['max_drawdown']:.2%}")
    print(f"OOS:   Sharpe={metrics_oos['sharpe_ratio']:.2f}, MDD={metrics_oos['max_drawdown']:.2%}\n")
    
    # 최종 성능
    print("="*100)
    print("최종 성능")
    print("="*100)
    
    metrics_final = calculate_metrics(full_managed_returns)
    metrics_before = calculate_metrics(ensemble_returns)
    
    print(f"  Sharpe Ratio: {metrics_final['sharpe_ratio']:.2f}")
    print(f"  Ann. Return: {metrics_final['annualized_return']:.2%}")
    print(f"  MDD: {metrics_final['max_drawdown']:.2%}")
    print(f"  Circuit Breaker 활성률: {cb_rate_full:.1%}\n")
    
    print("="*100)
    print("Before/After 비교")
    print("="*100)
    print(f"{'Metric':<25} {'Before':<20} {'After':<20} {'Change':<15}")
    print("-"*100)
    print(f"{'Sharpe Ratio':<25} {metrics_before['sharpe_ratio']:>19.2f} {metrics_final['sharpe_ratio']:>19.2f} {(metrics_final['sharpe_ratio']-metrics_before['sharpe_ratio']):>14.2f}")
    print(f"{'Ann. Return':<25} {metrics_before['annualized_return']:>18.2%} {metrics_final['annualized_return']:>18.2%} {(metrics_final['annualized_return']-metrics_before['annualized_return']):>13.2%}")
    print(f"{'MDD':<25} {metrics_before['max_drawdown']:>18.2%} {metrics_final['max_drawdown']:>18.2%} {(metrics_final['max_drawdown']-metrics_before['max_drawdown']):>13.2%}")
    print("="*100)
    
    # 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "optimal_params": best_result['params'],
        "performance_full": metrics_final,
        "circuit_breaker_activation_rate": cb_rate_full
    }
    
    with open('results/hybrid_aarm_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    full_managed_returns.to_csv('results/ensemble_returns_hybrid_aarm.csv')
    
    print(f"\n결과 저장 완료!")


if __name__ == "__main__":
    main()
