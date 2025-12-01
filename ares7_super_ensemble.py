#!/usr/bin/env python3
"""
ARES-7 Super Ensemble
======================
검증된 전략들의 최적화된 앙상블 시스템

핵심 개선사항:
1. 기존 검증된 전략들 활용 (E1, C1, LV, F)
2. Volatility Targeting (목표 변동성 유지)
3. Adaptive Weighting (Rolling Sharpe 기반)
4. Correlation-Based Risk Management
5. Transaction Cost 반영

목표: Sharpe 2.0+ (거래비용 반영 후)

Author: Claude (Anthropic)
Date: 2025-11-25
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class EnsembleConfig:
    """앙상블 설정"""
    # Volatility targeting
    target_vol: float = 0.10          # 목표 변동성 10%
    vol_lookback: int = 60            # 변동성 계산 기간
    max_leverage: float = 2.0         # 최대 레버리지
    min_leverage: float = 0.3         # 최소 레버리지
    
    # Adaptive weighting
    sharpe_lookback: int = 63         # Rolling Sharpe 기간 (3개월)
    temperature: float = 0.5          # Softmax temperature
    min_weight: float = 0.05          # 최소 전략 비중
    
    # Correlation management
    corr_lookback: int = 63           # 상관관계 계산 기간
    corr_penalty_threshold: float = 0.6  # 상관 패널티 임계값
    
    # Transaction costs
    spread_bps: float = 5.0           # 스프레드 비용 (bps)
    turnover_cost: float = 0.0010     # 터노버 비용 (0.1%)


class VolatilityTargeting:
    """변동성 목표 관리"""
    
    def __init__(self, 
                 target_vol: float,
                 lookback: int,
                 max_leverage: float,
                 min_leverage: float):
        self.target_vol = target_vol
        self.lookback = lookback
        self.max_leverage = max_leverage
        self.min_leverage = min_leverage
    
    def get_leverage(self, returns: pd.Series) -> float:
        """현재 레버리지 계산"""
        if len(returns) < self.lookback:
            return 1.0
        
        recent_vol = returns.iloc[-self.lookback:].std() * np.sqrt(252)
        
        if recent_vol <= 0 or np.isnan(recent_vol):
            return 1.0
        
        leverage = self.target_vol / recent_vol
        leverage = np.clip(leverage, self.min_leverage, self.max_leverage)
        
        return leverage


class AdaptiveWeighting:
    """적응형 가중치 시스템"""
    
    def __init__(self,
                 lookback: int,
                 temperature: float,
                 min_weight: float):
        self.lookback = lookback
        self.temperature = temperature
        self.min_weight = min_weight
    
    def calculate_weights(self, 
                          strategy_returns: pd.DataFrame,
                          correlations: pd.DataFrame = None) -> Dict[str, float]:
        """적응형 가중치 계산"""
        n_strategies = len(strategy_returns.columns)
        
        if len(strategy_returns) < self.lookback:
            # 동일 가중치
            return {col: 1.0/n_strategies for col in strategy_returns.columns}
        
        recent = strategy_returns.iloc[-self.lookback:]
        
        # Rolling Sharpe ratios
        sharpes = {}
        for col in recent.columns:
            mean_ret = recent[col].mean() * 252
            std_ret = recent[col].std() * np.sqrt(252)
            sharpes[col] = mean_ret / std_ret if std_ret > 0 else 0
        
        # 음수 Sharpe 처리
        min_sharpe = min(sharpes.values())
        if min_sharpe < 0:
            sharpes = {k: v - min_sharpe + 0.1 for k, v in sharpes.items()}
        
        # Softmax weighting
        sharpe_values = np.array(list(sharpes.values()))
        exp_values = np.exp(sharpe_values / self.temperature)
        softmax_weights = exp_values / exp_values.sum()
        
        # 최소 비중 보장
        weights = {}
        for i, col in enumerate(sharpes.keys()):
            w = max(softmax_weights[i], self.min_weight)
            weights[col] = w
        
        # 정규화
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        
        return weights


class ARES7SuperEnsemble:
    """ARES-7 Super Ensemble 시스템"""
    
    def __init__(self, config: EnsembleConfig = None):
        self.config = config or EnsembleConfig()
        
        self.vol_targeting = VolatilityTargeting(
            target_vol=self.config.target_vol,
            lookback=self.config.vol_lookback,
            max_leverage=self.config.max_leverage,
            min_leverage=self.config.min_leverage
        )
        
        self.adaptive_weighting = AdaptiveWeighting(
            lookback=self.config.sharpe_lookback,
            temperature=self.config.temperature,
            min_weight=self.config.min_weight
        )
    
    def load_engine_returns(self, path: str, name: str) -> Tuple[pd.Series, Dict]:
        """개별 엔진 수익률 로드"""
        with open(path, 'r') as f:
            data = json.load(f)
        
        # daily_returns 추출
        if 'daily_returns' in data:
            if isinstance(data['daily_returns'][0], dict):
                returns = pd.Series({
                    pd.Timestamp(d['date']): d['ret']
                    for d in data['daily_returns']
                })
            else:
                returns = pd.Series(data['daily_returns'])
        else:
            raise ValueError(f"No daily_returns found in {path}")
        
        stats = {
            'sharpe': data.get('sharpe', np.nan),
            'annual_return': data.get('annual_return', np.nan),
            'annual_volatility': data.get('annual_volatility', np.nan),
            'max_drawdown': data.get('max_drawdown', np.nan)
        }
        
        print(f"  {name}: {len(returns)} days, Sharpe {stats['sharpe']:.3f}")
        
        return returns, stats
    
    def calculate_stats(self, returns: pd.Series) -> Dict:
        """성과 지표 계산"""
        annual_return = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0
        
        cumret = (1 + returns).cumprod()
        cummax = cumret.expanding().max()
        dd = (cumret - cummax) / cummax
        max_dd = dd.min()
        
        # Sortino
        downside = returns[returns < 0]
        downside_std = downside.std() * np.sqrt(252)
        sortino = annual_return / downside_std if downside_std > 0 else 0
        
        # Calmar
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0
        
        return {
            'sharpe': float(sharpe),
            'annual_return': float(annual_return),
            'annual_volatility': float(annual_vol),
            'max_drawdown': float(max_dd),
            'sortino': float(sortino),
            'calmar': float(calmar),
            'win_rate': float((returns > 0).mean()),
            'total_return': float(cumret.iloc[-1] - 1)
        }
    
    def run(self, 
            engine_paths: Dict[str, str],
            rebal_freq: int = 21,  # 월간 리밸런싱
            out_path: str = None) -> Dict:
        """앙상블 실행"""
        print("=" * 70)
        print("ARES-7 Super Ensemble")
        print("=" * 70)
        
        # Load all engine returns
        print("\nLoading engine returns...")
        all_returns = {}
        all_stats = {}
        
        for name, path in engine_paths.items():
            if Path(path).exists():
                returns, stats = self.load_engine_returns(path, name)
                all_returns[name] = returns
                all_stats[name] = stats
            else:
                print(f"  WARNING: {name} file not found: {path}")
        
        if len(all_returns) < 2:
            raise ValueError("Need at least 2 engines for ensemble")
        
        # Combine into DataFrame
        df = pd.DataFrame(all_returns)
        df = df.dropna()
        
        print(f"\nCommon dates: {len(df)}")
        print(f"Period: {df.index[0].date()} ~ {df.index[-1].date()}")
        
        # Correlation matrix
        print("\nCorrelation matrix:")
        corr = df.corr()
        print(corr.to_string())
        
        # Run ensemble with adaptive weighting
        print(f"\nRunning ensemble (rebal every {rebal_freq} days)...")
        
        rebal_dates = df.index[::rebal_freq]
        
        ensemble_returns = []
        current_weights = {col: 1.0/len(df.columns) for col in df.columns}
        leverage = 1.0
        
        for i, date in enumerate(df.index):
            # Rebalance
            if date in rebal_dates and i >= self.config.sharpe_lookback:
                # Calculate adaptive weights
                past_returns = df.iloc[:i]
                new_weights = self.adaptive_weighting.calculate_weights(past_returns)
                
                # Calculate turnover cost
                turnover = sum(abs(new_weights.get(s, 0) - current_weights.get(s, 0)) 
                              for s in set(new_weights.keys()) | set(current_weights.keys()))
                turnover_cost = turnover * self.config.turnover_cost
                
                current_weights = new_weights
                
                # Update leverage based on volatility targeting
                if len(ensemble_returns) > self.config.vol_lookback:
                    ens_series = pd.Series(ensemble_returns)
                    leverage = self.vol_targeting.get_leverage(ens_series)
            else:
                turnover_cost = 0
            
            # Calculate ensemble return
            daily_ret = sum(current_weights.get(col, 0) * df.loc[date, col] 
                           for col in df.columns)
            
            # Apply leverage
            daily_ret *= leverage
            
            # Subtract turnover cost
            daily_ret -= turnover_cost
            
            ensemble_returns.append(daily_ret)
            
            if i % 100 == 0 and i > 0:
                print(f"  {date.date()}: Weights={dict(zip(current_weights.keys(), [f'{v:.2f}' for v in current_weights.values()]))}, "
                      f"Leverage={leverage:.2f}")
        
        # Convert to Series
        ensemble_series = pd.Series(ensemble_returns, index=df.index)
        
        # Calculate final stats
        print("\n" + "=" * 70)
        print("Ensemble Results:")
        print("=" * 70)
        
        stats = self.calculate_stats(ensemble_series)
        
        print(f"  Sharpe Ratio:      {stats['sharpe']:.3f}")
        print(f"  Annual Return:     {stats['annual_return']*100:.2f}%")
        print(f"  Annual Volatility: {stats['annual_volatility']*100:.2f}%")
        print(f"  Max Drawdown:      {stats['max_drawdown']*100:.2f}%")
        print(f"  Sortino Ratio:     {stats['sortino']:.3f}")
        print(f"  Calmar Ratio:      {stats['calmar']:.3f}")
        print(f"  Win Rate:          {stats['win_rate']*100:.1f}%")
        print(f"  Total Return:      {stats['total_return']*100:.1f}%")
        print("=" * 70)
        
        # Compare with individual engines
        print("\nComparison with individual engines:")
        print("-" * 50)
        for name, eng_stats in all_stats.items():
            print(f"  {name}: Sharpe {eng_stats['sharpe']:.3f}, Return {eng_stats['annual_return']*100:.1f}%")
        print(f"  ENSEMBLE: Sharpe {stats['sharpe']:.3f}, Return {stats['annual_return']*100:.1f}%")
        print("-" * 50)
        
        # Prepare output
        results = {
            'ensemble_stats': stats,
            'individual_stats': all_stats,
            'correlation': corr.to_dict(),
            'config': {
                'target_vol': self.config.target_vol,
                'rebal_freq': rebal_freq,
                'sharpe_lookback': self.config.sharpe_lookback
            },
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in ensemble_series.items()
            ]
        }
        
        # Save if path provided
        if out_path:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n✅ Results saved to {out_path}")
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ARES-7 Super Ensemble')
    parser.add_argument('--results_dir', default='./results')
    parser.add_argument('--rebal_freq', type=int, default=21)
    parser.add_argument('--target_vol', type=float, default=0.10)
    parser.add_argument('--out', default='./results/ares7_super_ensemble_results.json')
    args = parser.parse_args()
    
    # Engine paths
    engine_paths = {
        'E1_LS': f'{args.results_dir}/engine_ls_enhanced_results.json',
        'C1_MR': f'{args.results_dir}/C1_final_v5.json',
        'LV2': f'{args.results_dir}/engine_c_lowvol_v2_final_results.json',
        'Factor': f'{args.results_dir}/engine_factor_final_results.json',
        'LV_Enhanced': f'{args.results_dir}/engine_lowvol_enhanced_results.json'
    }
    
    config = EnsembleConfig(
        target_vol=args.target_vol
    )
    
    ensemble = ARES7SuperEnsemble(config)
    results = ensemble.run(engine_paths, args.rebal_freq, args.out)


if __name__ == '__main__':
    main()
