#!/usr/bin/env python3
"""
ARES7 Enhanced AARM 백테스트
MDD -10% 목표 달성 + Sharpe 유지/상승
"""

from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Enhanced AARM 코드가 완전하지 않을 수 있으므로, 직접 구현
class EnhancedAARMStrategy:
    """Enhanced AARM with Dynamic Risk Budget + Adaptive Leverage Ceiling"""
    
    def __init__(self, 
                 target_mdd: float = 0.10,
                 base_leverage: float = 1.0,
                 max_leverage: float = 1.5,
                 transaction_cost: float = 0.001):
        
        self.target_mdd = target_mdd
        self.base_leverage = base_leverage
        self.max_leverage = max_leverage
        self.transaction_cost = transaction_cost
        
        self.lookback_days = 60
        
    def calculate_position_size(self, 
                                returns: pd.Series,
                                current_drawdown: float,
                                time_since_peak: int) -> float:
        """Calculate adaptive position size"""
        
        if len(returns) < self.lookback_days:
            return self.base_leverage
        
        recent_returns = returns.tail(self.lookback_days)
        
        # 1. Dynamic Risk Budget (Drawdown Velocity)
        cumulative = (1 + recent_returns.tail(20)).cumprod()
        x = np.arange(len(cumulative))
        slope = np.polyfit(x, cumulative.values, 1)[0]
        drawdown_velocity = max(0, -slope)  # Positive when losing
        
        # Risk budget decreases with drawdown velocity
        velocity_factor = 1.0 - min(1.0, drawdown_velocity / 0.02) * 0.5
        
        # 2. Adaptive Leverage Ceiling (Volatility Term Structure)
        vol_fast = recent_returns.tail(10).std() * np.sqrt(252)
        vol_slow = recent_returns.std() * np.sqrt(252)
        vol_ratio = vol_fast / (vol_slow + 1e-6)
        
        # Reduce leverage when volatility is increasing
        vol_factor = 1.0 - max(0, min(1, (vol_ratio - 1.0) / 0.5)) * 0.3
        
        # 3. Drawdown-based position reduction (Progressive)
        if current_drawdown >= 0:
            dd_factor = 1.0
        elif current_drawdown > -0.05:
            dd_factor = 1.0 - abs(current_drawdown) * 2  # 0-10% reduction
        elif current_drawdown > -0.08:
            dd_factor = 0.9 - (abs(current_drawdown) - 0.05) * 4  # 10-22% reduction
        elif current_drawdown > self.target_mdd:
            dd_factor = 0.78 - (abs(current_drawdown) - 0.08) * 8  # 22-38% reduction
        else:
            # Hard limit: MDD threshold reached
            dd_factor = 0.4  # 60% reduction
        
        dd_factor = max(0.3, dd_factor)
        
        # 4. Combine all factors
        position_size = self.base_leverage * velocity_factor * vol_factor * dd_factor
        
        # Apply max leverage cap
        position_size = min(position_size, self.max_leverage)
        
        return position_size


def backtest_enhanced_aarm(returns: pd.Series, 
                          strategy: EnhancedAARMStrategy) -> tuple:
    """Enhanced AARM 백테스트 (룩어헤드 바이어스 제거)"""
    
    cum_returns = (1 + returns).cumprod()
    rolling_max = cum_returns.expanding().max()
    drawdowns = (cum_returns - rolling_max) / rolling_max
    
    managed_returns = []
    position_sizes = []
    prev_position = strategy.base_leverage
    
    peak_idx = 0
    
    for i in range(strategy.lookback_days + 1, len(returns)):
        # i-1번째까지의 데이터만 사용
        current_returns = returns.iloc[:i]
        current_dd = drawdowns.iloc[i-1]
        
        # Peak 업데이트
        if cum_returns.iloc[i-1] >= rolling_max.iloc[i-1]:
            peak_idx = i - 1
        
        time_since_peak = (i - 1) - peak_idx
        
        # Position size 계산
        position_size = strategy.calculate_position_size(
            current_returns,
            current_dd,
            time_since_peak
        )
        
        # 거래 비용
        turnover = abs(position_size - prev_position)
        cost = turnover * strategy.transaction_cost
        
        # i번째 수익률에 적용
        managed_return = returns.iloc[i] * position_size - cost
        
        managed_returns.append(managed_return)
        position_sizes.append(position_size)
        prev_position = position_size
    
    # 초기 기간
    initial_returns = returns.iloc[:strategy.lookback_days + 1] * strategy.base_leverage
    full_managed_returns = pd.concat([
        initial_returns,
        pd.Series(managed_returns, index=returns.index[strategy.lookback_days + 1:])
    ])
    
    return full_managed_returns, position_sizes


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
    print("ARES7 Enhanced AARM 백테스트 (MDD -10% 목표)")
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
    
    print(f"데이터: {len(ensemble_returns)} days, {ensemble_returns.index[0]} ~ {ensemble_returns.index[-1]}\n")
    
    # Train/Test 분할
    split_idx = int(len(ensemble_returns) * 0.7)
    train_returns = ensemble_returns.iloc[:split_idx]
    test_returns = ensemble_returns.iloc[split_idx:]
    
    print("="*100)
    print("Train/Test 분할")
    print("="*100)
    print(f"  Train: {len(train_returns)} days")
    print(f"  Test: {len(test_returns)} days\n")
    
    # 파라미터 그리드 서치 (Train)
    print("="*100)
    print("파라미터 최적화 (Train)")
    print("="*100)
    
    param_grid = [
        (1.0, 1.8, 0.001),  # (base, max, cost)
        (1.1, 2.0, 0.001),
        (1.2, 2.2, 0.001),
        (1.0, 2.0, 0.001),
        (1.1, 1.8, 0.001),
        (0.9, 1.8, 0.001),
    ]
    
    train_results = []
    
    for base_lev, max_lev, tx_cost in param_grid:
        strategy = EnhancedAARMStrategy(
            target_mdd=0.10,
            base_leverage=base_lev,
            max_leverage=max_lev,
            transaction_cost=tx_cost
        )
        
        managed_returns, _ = backtest_enhanced_aarm(train_returns, strategy)
        metrics = calculate_metrics(managed_returns)
        metrics['params'] = {'base': base_lev, 'max': max_lev, 'cost': tx_cost}
        train_results.append(metrics)
        
        print(f"  Base={base_lev:.1f}, Max={max_lev:.1f}: "
              f"Sharpe={metrics['sharpe_ratio']:.2f}, "
              f"Return={metrics['annualized_return']:.2%}, "
              f"MDD={metrics['max_drawdown']:.2%}")
    
    # 최적 파라미터 선정
    valid_results = [r for r in train_results if r['max_drawdown'] >= -0.10]
    
    if valid_results:
        best_result = max(valid_results, key=lambda x: x['sharpe_ratio'])
        print(f"\n✓ MDD -10% 달성! 최적 파라미터: Base={best_result['params']['base']:.1f}, Max={best_result['params']['max']:.1f}")
    else:
        best_result = max(train_results, key=lambda x: (x['max_drawdown'], x['sharpe_ratio']))
        print(f"\n⚠ MDD -10% 미달성, 최선의 결과 선택")
    
    # OOS 검증
    print("\n" + "="*100)
    print("OOS 검증")
    print("="*100)
    
    strategy_oos = EnhancedAARMStrategy(
        target_mdd=0.10,
        base_leverage=best_result['params']['base'],
        max_leverage=best_result['params']['max'],
        transaction_cost=best_result['params']['cost']
    )
    
    full_managed_returns, _ = backtest_enhanced_aarm(ensemble_returns, strategy_oos)
    test_managed_returns = full_managed_returns.loc[test_returns.index]
    
    metrics_oos = calculate_metrics(test_managed_returns)
    
    print(f"Train: Sharpe={best_result['sharpe_ratio']:.2f}, MDD={best_result['max_drawdown']:.2%}")
    print(f"OOS:   Sharpe={metrics_oos['sharpe_ratio']:.2f}, MDD={metrics_oos['max_drawdown']:.2%}")
    
    sharpe_diff = metrics_oos['sharpe_ratio'] - best_result['sharpe_ratio']
    print(f"{'✓ 과적합 없음' if sharpe_diff >= -0.5 else '⚠ 과적합 가능성'}: Sharpe 차이 {sharpe_diff:+.2f}\n")
    
    # 전체 기간 최종 성능
    print("="*100)
    print("최종 성능 (전체 기간)")
    print("="*100)
    
    metrics_final = calculate_metrics(full_managed_returns)
    metrics_before = calculate_metrics(ensemble_returns)
    
    print(f"  Sharpe Ratio: {metrics_final['sharpe_ratio']:.2f}")
    print(f"  Ann. Return: {metrics_final['annualized_return']:.2%}")
    print(f"  MDD: {metrics_final['max_drawdown']:.2%}")
    print(f"  CVaR (95%): {metrics_final['cvar_95']:.4f}\n")
    
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
        "performance_train": best_result,
        "performance_oos": metrics_oos,
        "performance_full": metrics_final
    }
    
    with open('results/enhanced_aarm_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    full_managed_returns.to_csv('results/ensemble_returns_enhanced_aarm.csv')
    
    print(f"\n결과 저장 완료!")


if __name__ == "__main__":
    main()
