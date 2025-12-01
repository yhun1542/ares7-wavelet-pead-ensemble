#!/usr/bin/env python3
"""
ARES-7 Optimized Ensemble
==========================
상관관계와 Sharpe 최적화된 앙상블

핵심 원칙:
1. 낮은 상관관계 전략만 선택
2. Risk Parity 가중치
3. 적절한 Volatility Targeting
4. 최소 회전율 유지

Author: Claude (Anthropic)
Date: 2025-11-25
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Tuple
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')


class OptimizedEnsemble:
    """최적화된 앙상블 시스템"""
    
    def __init__(self, 
                 target_vol: float = 0.10,
                 max_leverage: float = 1.5,
                 risk_parity: bool = True):
        self.target_vol = target_vol
        self.max_leverage = max_leverage
        self.risk_parity = risk_parity
    
    def load_engine_returns(self, path: str, name: str) -> pd.Series:
        """엔진 수익률 로드"""
        with open(path, 'r') as f:
            data = json.load(f)
        
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
        
        sharpe = data.get('sharpe', 0)
        print(f"  {name}: {len(returns)} days, Sharpe {sharpe:.3f}")
        
        return returns
    
    def calculate_risk_parity_weights(self, cov_matrix: pd.DataFrame) -> Dict[str, float]:
        """Risk Parity 가중치 계산"""
        n = len(cov_matrix)
        
        def risk_budget_objective(weights, cov):
            portfolio_vol = np.sqrt(weights @ cov @ weights)
            if portfolio_vol == 0:
                return 1e10
            
            marginal_contrib = cov @ weights
            risk_contrib = weights * marginal_contrib / portfolio_vol
            
            # 모든 자산이 동일한 리스크 기여
            target_risk = portfolio_vol / n
            return sum((rc - target_risk) ** 2 for rc in risk_contrib)
        
        # Initial guess
        x0 = np.ones(n) / n
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: sum(x) - 1},  # Sum to 1
        ]
        
        bounds = [(0.05, 0.5) for _ in range(n)]  # 5%~50% per strategy
        
        result = minimize(
            risk_budget_objective,
            x0,
            args=(cov_matrix.values,),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        weights = dict(zip(cov_matrix.columns, result.x / result.x.sum()))
        return weights
    
    def calculate_sharpe_weighted(self, returns_df: pd.DataFrame, lookback: int = 126) -> Dict[str, float]:
        """Sharpe 기반 가중치"""
        if len(returns_df) < lookback:
            n = len(returns_df.columns)
            return {col: 1.0/n for col in returns_df.columns}
        
        recent = returns_df.iloc[-lookback:]
        
        sharpes = {}
        for col in recent.columns:
            mean_ret = recent[col].mean() * 252
            std_ret = recent[col].std() * np.sqrt(252)
            sharpes[col] = max(mean_ret / std_ret, 0.01) if std_ret > 0 else 0.01
        
        # Sharpe 비례 가중치
        total = sum(sharpes.values())
        weights = {k: v/total for k, v in sharpes.items()}
        
        return weights
    
    def run(self, 
            engine_paths: Dict[str, str],
            method: str = 'risk_parity',
            rebal_freq: int = 21) -> Dict:
        """앙상블 실행"""
        print("=" * 70)
        print("ARES-7 Optimized Ensemble")
        print("=" * 70)
        print(f"Method: {method}")
        print(f"Target Vol: {self.target_vol*100:.0f}%")
        print()
        
        # Load returns
        print("Loading engine returns...")
        all_returns = {}
        for name, path in engine_paths.items():
            if Path(path).exists():
                all_returns[name] = self.load_engine_returns(path, name)
        
        # Combine
        df = pd.DataFrame(all_returns).dropna()
        print(f"\nCommon dates: {len(df)}")
        
        # Correlation
        print("\nCorrelation matrix:")
        corr = df.corr()
        print(corr.round(3).to_string())
        
        # Calculate covariance for Risk Parity
        cov = df.cov() * 252  # Annualized
        
        # Weights
        if method == 'risk_parity':
            weights = self.calculate_risk_parity_weights(cov)
        elif method == 'sharpe':
            weights = self.calculate_sharpe_weighted(df)
        else:
            # Equal weight
            n = len(df.columns)
            weights = {col: 1.0/n for col in df.columns}
        
        print(f"\nOptimized Weights:")
        for name, w in weights.items():
            print(f"  {name}: {w*100:.1f}%")
        
        # Calculate ensemble returns
        print(f"\nRunning ensemble...")
        
        ensemble_returns = []
        for i, date in enumerate(df.index):
            daily_ret = sum(weights[col] * df.loc[date, col] for col in df.columns)
            ensemble_returns.append(daily_ret)
        
        ensemble_series = pd.Series(ensemble_returns, index=df.index)
        
        # Apply volatility targeting
        print("\nApplying volatility targeting...")
        
        vol_lookback = 60
        targeted_returns = []
        
        for i, date in enumerate(df.index):
            if i < vol_lookback:
                targeted_returns.append(ensemble_series.iloc[i])
                continue
            
            recent_vol = ensemble_series.iloc[i-vol_lookback:i].std() * np.sqrt(252)
            
            if recent_vol > 0:
                leverage = min(self.target_vol / recent_vol, self.max_leverage)
            else:
                leverage = 1.0
            
            targeted_returns.append(ensemble_series.iloc[i] * leverage)
        
        targeted_series = pd.Series(targeted_returns, index=df.index)
        
        # Final stats
        print("\n" + "=" * 70)
        print("Results:")
        print("=" * 70)
        
        for name, series in [('Raw Ensemble', ensemble_series), 
                            ('Vol-Targeted', targeted_series)]:
            ann_ret = series.mean() * 252
            ann_vol = series.std() * np.sqrt(252)
            sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
            
            cumret = (1 + series).cumprod()
            cummax = cumret.expanding().max()
            dd = (cumret - cummax) / cummax
            max_dd = dd.min()
            
            print(f"\n{name}:")
            print(f"  Sharpe Ratio:      {sharpe:.3f}")
            print(f"  Annual Return:     {ann_ret*100:.2f}%")
            print(f"  Annual Volatility: {ann_vol*100:.2f}%")
            print(f"  Max Drawdown:      {max_dd*100:.2f}%")
            print(f"  Total Return:      {(cumret.iloc[-1]-1)*100:.1f}%")
        
        print("=" * 70)
        
        # Prepare output
        final_series = targeted_series
        
        stats = {
            'sharpe': float(final_series.mean() * 252 / (final_series.std() * np.sqrt(252))),
            'annual_return': float(final_series.mean() * 252),
            'annual_volatility': float(final_series.std() * np.sqrt(252)),
            'max_drawdown': float(((1 + final_series).cumprod() / 
                                   (1 + final_series).cumprod().expanding().max() - 1).min()),
            'win_rate': float((final_series > 0).mean()),
            'total_return': float((1 + final_series).cumprod().iloc[-1] - 1)
        }
        
        results = {
            'ensemble_stats': stats,
            'weights': weights,
            'method': method,
            'correlation': corr.to_dict(),
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in final_series.items()
            ]
        }
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ARES-7 Optimized Ensemble')
    parser.add_argument('--results_dir', default='./results')
    parser.add_argument('--method', choices=['risk_parity', 'sharpe', 'equal'], default='risk_parity')
    parser.add_argument('--target_vol', type=float, default=0.10)
    parser.add_argument('--out', default='./results/ares7_optimized_ensemble_results.json')
    args = parser.parse_args()
    
    # 낮은 상관관계 전략만 선택
    # E1_LS와 C1_MR의 상관: 0.007 (매우 낮음)
    # C1_MR과 Factor의 상관: 0.017 (매우 낮음)
    # E1_LS와 Factor의 상관: 0.082 (낮음)
    
    engine_paths = {
        'E1_LS': f'{args.results_dir}/engine_ls_enhanced_results.json',
        'C1_MR': f'{args.results_dir}/C1_final_v5.json',
        'Factor': f'{args.results_dir}/engine_factor_final_results.json',
        # LV2는 E1_LS와 높은 상관(0.815)으로 제외
    }
    
    ensemble = OptimizedEnsemble(target_vol=args.target_vol)
    results = ensemble.run(engine_paths, method=args.method)
    
    # Save
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")


if __name__ == '__main__':
    main()
