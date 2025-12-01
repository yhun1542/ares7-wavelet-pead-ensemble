#!/usr/bin/env python3
"""
ARES7 포괄적 그리드 서치 프레임워크
모든 파라미터를 체계적으로 탐색하여 최적의 조합 발굴
"""

import pandas as pd
import numpy as np
import json
import itertools
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from risk.adaptive_asymmetric_risk_manager import AdaptiveAsymmetricRiskManager


class ComprehensiveGridSearch:
    """ARES7 포괄적 그리드 서치"""
    
    def __init__(self, returns_data: pd.Series, transaction_cost: float = 0.001):
        self.returns_data = returns_data
        self.transaction_cost = transaction_cost
        
        # Train/Test 분할
        split_idx = int(len(returns_data) * 0.7)
        self.train_returns = returns_data.iloc[:split_idx]
        self.test_returns = returns_data.iloc[split_idx:]
        
        self.results = []
        
    def calculate_metrics(self, returns: pd.Series) -> Dict:
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
    
    def backtest_aarm(self, returns: pd.Series, params: Dict) -> pd.Series:
        """AARM 백테스트"""
        strategy = AdaptiveAsymmetricRiskManager(
            base_leverage=params.get('base_leverage', 1.0),
            max_leverage=params.get('max_leverage', 2.0),
            target_vol=params.get('target_volatility', 0.18),
            max_dd_threshold=params.get('mdd_threshold', -0.10)
        )
        
        cum_returns = (1 + returns).cumprod()
        rolling_max = cum_returns.expanding().max()
        drawdowns = (cum_returns - rolling_max) / rolling_max
        prices = cum_returns * 100
        
        managed_returns = []
        prev_position = strategy.base_leverage
        
        for i in range(strategy.lookback_days + 1, len(returns)):
            current_returns = returns.iloc[:i]
            current_prices = prices.iloc[:i]
            current_dd = drawdowns.iloc[i-1]
            
            position_info = strategy.calculate_adaptive_position_size(
                current_returns,
                current_prices,
                current_dd
            )
            
            position_size = position_info['position_size']
            
            # Circuit Breaker 적용
            if 'cb_trigger' in params and current_dd <= params['cb_trigger']:
                cb_factor = params.get('cb_reduction_factor', 0.5)
                position_size *= cb_factor
            
            # 거래 비용
            turnover = abs(position_size - prev_position)
            cost = turnover * self.transaction_cost
            
            managed_return = returns.iloc[i] * position_size - cost
            managed_returns.append(managed_return)
            prev_position = position_size
        
        initial_returns = returns.iloc[:strategy.lookback_days + 1] * strategy.base_leverage
        full_managed_returns = pd.concat([
            initial_returns,
            pd.Series(managed_returns, index=returns.index[strategy.lookback_days + 1:])
        ])
        
        return full_managed_returns
    
    def grid_search_aarm_parameters(self, n_samples: int = 50) -> List[Dict]:
        """AARM 파라미터 그리드 서치 (랜덤 샘플링)"""
        print("="*100)
        print("Phase 3: AARM 파라미터 최적화 (Random Search)")
        print("="*100)
        
        # 파라미터 그리드
        param_grid = {
            'base_leverage': [0.8, 0.9, 1.0, 1.1, 1.2],
            'max_leverage': [1.3, 1.5, 1.8, 2.0, 2.2],
            'target_volatility': [0.12, 0.15, 0.18, 0.20],
            'cb_trigger': [-0.07, -0.08, -0.09, -0.10, None],
            'cb_reduction_factor': [0.3, 0.4, 0.5, 0.6]
        }
        
        # 랜덤 샘플링
        np.random.seed(42)
        sampled_params = []
        
        for _ in range(n_samples):
            params = {
                'base_leverage': np.random.choice(param_grid['base_leverage']),
                'max_leverage': np.random.choice(param_grid['max_leverage']),
                'target_volatility': np.random.choice(param_grid['target_volatility']),
                'cb_trigger': np.random.choice(param_grid['cb_trigger']),
                'cb_reduction_factor': np.random.choice(param_grid['cb_reduction_factor']),
                'mdd_threshold': -0.10
            }
            
            # max_leverage >= base_leverage 제약
            if params['max_leverage'] < params['base_leverage']:
                continue
            
            sampled_params.append(params)
        
        results = []
        
        for idx, params in enumerate(sampled_params, 1):
            try:
                managed_returns = self.backtest_aarm(self.train_returns, params)
                metrics = self.calculate_metrics(managed_returns)
                
                result = {
                    'phase': 'aarm_optimization',
                    'params': params,
                    'metrics': metrics
                }
                results.append(result)
                
                if idx % 10 == 0:
                    print(f"  진행: {idx}/{len(sampled_params)} - "
                          f"Sharpe={metrics['sharpe_ratio']:.2f}, "
                          f"MDD={metrics['max_drawdown']:.2%}")
            
            except Exception as e:
                print(f"  ✗ 파라미터 조합 {idx} 실패: {e}")
                continue
        
        # 상위 10개 결과
        results_sorted = sorted(results, key=lambda x: x['metrics']['sharpe_ratio'], reverse=True)
        
        print(f"\n상위 10개 결과:")
        for i, r in enumerate(results_sorted[:10], 1):
            print(f"  {i}. Sharpe={r['metrics']['sharpe_ratio']:.2f}, "
                  f"Return={r['metrics']['annualized_return']:.2%}, "
                  f"MDD={r['metrics']['max_drawdown']:.2%}")
        
        return results_sorted
    
    def grid_search_circuit_breaker(self, base_params: Dict) -> List[Dict]:
        """Circuit Breaker 파라미터 그리드 서치"""
        print("\n" + "="*100)
        print("Phase 4: Circuit Breaker 최적화")
        print("="*100)
        
        param_grid = {
            'cb_trigger': [-0.07, -0.08, -0.09, -0.10],
            'cb_reduction_factor': [0.3, 0.4, 0.5, 0.6, 0.7],
            'cb_recovery_threshold': [-0.03, -0.04, -0.05]
        }
        
        results = []
        total_combinations = len(param_grid['cb_trigger']) * len(param_grid['cb_reduction_factor']) * len(param_grid['cb_recovery_threshold'])
        
        idx = 0
        for trigger, reduction, recovery in itertools.product(
            param_grid['cb_trigger'],
            param_grid['cb_reduction_factor'],
            param_grid['cb_recovery_threshold']
        ):
            idx += 1
            params = base_params.copy()
            params.update({
                'cb_trigger': trigger,
                'cb_reduction_factor': reduction,
                'cb_recovery_threshold': recovery
            })
            
            try:
                managed_returns = self.backtest_aarm(self.train_returns, params)
                metrics = self.calculate_metrics(managed_returns)
                
                result = {
                    'phase': 'circuit_breaker_optimization',
                    'params': params,
                    'metrics': metrics
                }
                results.append(result)
                
                if idx % 10 == 0:
                    print(f"  진행: {idx}/{total_combinations} - "
                          f"Sharpe={metrics['sharpe_ratio']:.2f}, "
                          f"MDD={metrics['max_drawdown']:.2%}")
            
            except Exception as e:
                print(f"  ✗ 조합 {idx} 실패: {e}")
                continue
        
        # 상위 10개 결과
        results_sorted = sorted(results, key=lambda x: x['metrics']['sharpe_ratio'], reverse=True)
        
        print(f"\n상위 10개 결과:")
        for i, r in enumerate(results_sorted[:10], 1):
            print(f"  {i}. Sharpe={r['metrics']['sharpe_ratio']:.2f}, "
                  f"Return={r['metrics']['annualized_return']:.2%}, "
                  f"MDD={r['metrics']['max_drawdown']:.2%}")
        
        return results_sorted
    
    def final_validation(self, best_params: Dict) -> Dict:
        """최종 검증 (OOS)"""
        print("\n" + "="*100)
        print("최종 검증 (OOS)")
        print("="*100)
        
        # Train 성능
        train_managed_returns = self.backtest_aarm(self.train_returns, best_params)
        train_metrics = self.calculate_metrics(train_managed_returns)
        
        # OOS 성능
        full_managed_returns = self.backtest_aarm(self.returns_data, best_params)
        test_managed_returns = full_managed_returns.loc[self.test_returns.index]
        test_metrics = self.calculate_metrics(test_managed_returns)
        
        # 전체 성능
        full_metrics = self.calculate_metrics(full_managed_returns)
        
        print(f"Train: Sharpe={train_metrics['sharpe_ratio']:.2f}, MDD={train_metrics['max_drawdown']:.2%}")
        print(f"OOS:   Sharpe={test_metrics['sharpe_ratio']:.2f}, MDD={test_metrics['max_drawdown']:.2%}")
        print(f"Full:  Sharpe={full_metrics['sharpe_ratio']:.2f}, MDD={full_metrics['max_drawdown']:.2%}")
        
        sharpe_diff = test_metrics['sharpe_ratio'] - train_metrics['sharpe_ratio']
        print(f"{'✓ 과적합 없음' if sharpe_diff >= -0.5 else '⚠ 과적합 가능성'}: Sharpe 차이 {sharpe_diff:+.2f}")
        
        return {
            'train': train_metrics,
            'test': test_metrics,
            'full': full_metrics,
            'returns': full_managed_returns
        }


def main():
    print("="*100)
    print("ARES7 포괄적 그리드 서치 시작")
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
    
    # 그리드 서치 초기화
    grid_search = ComprehensiveGridSearch(ensemble_returns)
    
    # Phase 3: AARM 파라미터 최적화
    aarm_results = grid_search.grid_search_aarm_parameters(n_samples=50)
    
    # 최상위 결과 선택
    best_aarm = aarm_results[0]
    print(f"\n최적 AARM 파라미터:")
    print(f"  {json.dumps(best_aarm['params'], indent=2)}")
    
    # Phase 4: Circuit Breaker 최적화
    cb_results = grid_search.grid_search_circuit_breaker(best_aarm['params'])
    
    # 최상위 결과 선택
    best_overall = cb_results[0]
    print(f"\n최종 최적 파라미터:")
    print(f"  {json.dumps(best_overall['params'], indent=2)}")
    
    # 최종 검증
    validation_results = grid_search.final_validation(best_overall['params'])
    
    # 결과 저장
    output = {
        'timestamp': datetime.now().isoformat(),
        'best_params': best_overall['params'],
        'performance': validation_results['full'],
        'oos_performance': validation_results['test']
    }
    
    with open('results/grid_search_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    validation_results['returns'].to_csv('results/ensemble_returns_grid_optimized.csv')
    
    print(f"\n결과 저장 완료!")
    print(f"  - results/grid_search_results.json")
    print(f"  - results/ensemble_returns_grid_optimized.csv")


if __name__ == "__main__":
    main()
