#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARES7-Best Tuning Backtest V1
==============================

Integrated backtest script for testing 4-axis tuning improvements:
1. Transaction Cost Model V2
2. Global Risk Scaler (Leverage/Vol Targeting)
3. Quality+Momentum Overlay
4. VIX Global Guard

Target: Sharpe 1.85 → 2.15~2.35 (Min Sharpe 1.626 → 2.0+)

Author: Manus AI
Date: 2025-11-28
Version: 1.0
"""

import sys
import os

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Import tuning modules
from risk.transaction_cost_model_v2 import TransactionCostModelV2, TCCoeffs
from risk.global_risk_scaler import GlobalRiskScaler, GlobalRiskConfig
from modules.overlay_quality_mom_v1 import QualityMomentumOverlayV1, OverlayConfig
from modules.vix_global_guard import VIXGlobalGuard, VIXGuardConfig


@dataclass
class TuningConfig:
    """Overall tuning configuration"""
    # Enable/disable each axis
    enable_tc_model: bool = True
    enable_risk_scaler: bool = True
    enable_qm_overlay: bool = True
    enable_vix_guard: bool = True
    
    # Axis 1: Transaction Cost
    tc_coeffs: TCCoeffs = None
    
    # Axis 2: Risk Scaler
    risk_config: GlobalRiskConfig = None
    
    # Axis 3: Quality+Momentum Overlay
    overlay_config: OverlayConfig = None
    
    # Axis 4: VIX Guard
    vix_config: VIXGuardConfig = None
    
    def __post_init__(self):
        # Default configs
        if self.tc_coeffs is None:
            self.tc_coeffs = TCCoeffs(
                base_bps=2.0,
                vol_coeff=1.0,
                adv_coeff=5.0,
            )
        
        if self.risk_config is None:
            self.risk_config = GlobalRiskConfig(
                target_vol=0.10,
                max_leverage=2.0,
                enable_dd_reduction=True,
            )
        
        if self.overlay_config is None:
            self.overlay_config = OverlayConfig(
                top_frac=0.1,
                bottom_frac=0.1,
                overlay_strength=0.2,
            )
        
        if self.vix_config is None:
            self.vix_config = VIXGuardConfig(
                level_reduce_1=25.0,
                level_reduce_2=30.0,
                reduce_factor_1=0.75,
                reduce_factor_2=0.50,
            )


class ARES7TuningBacktest:
    """
    ARES7-Best Tuning Backtest Engine
    
    Applies 4-axis tuning to ARES7-Best baseline and measures performance improvement.
    
    Example:
        >>> config = TuningConfig(
        ...     enable_tc_model=True,
        ...     enable_risk_scaler=True,
        ...     enable_qm_overlay=True,
        ...     enable_vix_guard=True
        ... )
        >>> 
        >>> backtest = ARES7TuningBacktest(config)
        >>> results = backtest.run(
        ...     base_returns=ares7_returns,
        ...     base_weights=ares7_weights,
        ...     stock_returns=stock_returns,
        ...     quality_data=quality_data,
        ...     momentum_data=prices,
        ...     vix_data=vix_series
        ... )
        >>> 
        >>> backtest.print_results(results)
    """
    
    def __init__(self, cfg: TuningConfig):
        """
        Initialize ARES7 Tuning Backtest
        
        Args:
            cfg: TuningConfig dataclass
        """
        self.cfg = cfg
        
        # Initialize modules
        if self.cfg.enable_tc_model:
            self.tc_model = TransactionCostModelV2(self.cfg.tc_coeffs)
        
        if self.cfg.enable_risk_scaler:
            self.risk_scaler = GlobalRiskScaler(self.cfg.risk_config)
        
        if self.cfg.enable_qm_overlay:
            self.qm_overlay = QualityMomentumOverlayV1(self.cfg.overlay_config)
        
        if self.cfg.enable_vix_guard:
            self.vix_guard = VIXGlobalGuard(self.cfg.vix_config)
    
    def run(
        self,
        base_returns: pd.Series,
        base_weights: Optional[pd.DataFrame] = None,
        stock_returns: Optional[pd.DataFrame] = None,
        trades: Optional[pd.DataFrame] = None,
        adv_series: Optional[pd.Series] = None,
        vol_series: Optional[pd.Series] = None,
        quality_data: Optional[Dict[str, pd.Series]] = None,
        momentum_data: Optional[pd.DataFrame] = None,
        vix_data: Optional[pd.Series] = None,
    ) -> Dict:
        """
        Run tuning backtest
        
        Args:
            base_returns: Baseline ARES7-Best returns (Series)
            base_weights: Baseline portfolio weights (DataFrame, optional for overlay)
            stock_returns: Individual stock returns (DataFrame, optional for overlay)
            trades: Position changes (DataFrame, optional for TC model)
            adv_series: Average Daily Volume (Series, optional for TC model)
            vol_series: Volatility (Series, optional for TC model)
            quality_data: Quality factors (Dict, optional for overlay)
            momentum_data: Price data (DataFrame, optional for overlay)
            vix_data: VIX data (Series, optional for VIX guard)
        
        Returns:
            Dictionary with results for each configuration
        """
        results = {}
        
        # Baseline (no tuning)
        results['baseline'] = self._compute_metrics(base_returns, "Baseline (ARES7-Best)")
        
        # Axis 1: Transaction Cost
        if self.cfg.enable_tc_model and trades is not None:
            tc_returns = self._apply_tc_model(
                base_returns, trades, adv_series, vol_series
            )
            results['axis1_tc'] = self._compute_metrics(tc_returns, "Axis 1: TC Model")
        
        # Axis 2: Risk Scaler
        if self.cfg.enable_risk_scaler:
            risk_returns = self._apply_risk_scaler(base_returns)
            results['axis2_risk'] = self._compute_metrics(risk_returns, "Axis 2: Risk Scaler")
        
        # Axis 3: Quality+Momentum Overlay
        if self.cfg.enable_qm_overlay and base_weights is not None:
            overlay_returns = self._apply_qm_overlay(
                base_returns, base_weights, stock_returns, quality_data, momentum_data
            )
            results['axis3_overlay'] = self._compute_metrics(overlay_returns, "Axis 3: QM Overlay")
        
        # Axis 4: VIX Guard
        if self.cfg.enable_vix_guard and vix_data is not None:
            self.vix_guard.initialize(vix_data)
            vix_returns = self._apply_vix_guard(base_returns)
            results['axis4_vix'] = self._compute_metrics(vix_returns, "Axis 4: VIX Guard")
        
        # Combined: All axes
        combined_returns = base_returns.copy()
        
        # Apply in sequence
        if self.cfg.enable_tc_model and trades is not None:
            combined_returns = self._apply_tc_model(
                combined_returns, trades, adv_series, vol_series
            )
        
        if self.cfg.enable_qm_overlay and base_weights is not None:
            combined_returns = self._apply_qm_overlay(
                combined_returns, base_weights, stock_returns, quality_data, momentum_data
            )
        
        if self.cfg.enable_risk_scaler:
            combined_returns = self._apply_risk_scaler(combined_returns)
        
        if self.cfg.enable_vix_guard and vix_data is not None:
            combined_returns = self._apply_vix_guard(combined_returns)
        
        results['combined'] = self._compute_metrics(combined_returns, "Combined (All Axes)")
        
        return results
    
    def _apply_tc_model(
        self,
        returns: pd.Series,
        trades: pd.DataFrame,
        adv_series: pd.Series,
        vol_series: pd.Series,
    ) -> pd.Series:
        """Apply transaction cost model"""
        tc_adjusted_returns = self.tc_model.compute_tc_adjusted_returns(
            returns, trades, adv_series, vol_series
        )
        return tc_adjusted_returns
    
    def _apply_risk_scaler(self, returns: pd.Series) -> pd.Series:
        """Apply global risk scaler"""
        scaled_returns = self.risk_scaler.apply(returns)
        return scaled_returns
    
    def _apply_qm_overlay(
        self,
        returns: pd.Series,
        base_weights: pd.DataFrame,
        stock_returns: pd.DataFrame,
        quality_data: Dict[str, pd.Series],
        momentum_data: pd.DataFrame,
    ) -> pd.Series:
        """Apply quality+momentum overlay"""
        # Compute scores
        qm_score = self.qm_overlay.compute_scores(quality_data, momentum_data)
        
        # Build overlay weights
        overlay_weights = self.qm_overlay.build_overlay_weights(
            qm_score, returns.index
        )
        
        # Apply overlay
        overlay_returns = self.qm_overlay.backtest_overlay(
            returns, base_weights, overlay_weights, stock_returns
        )
        
        return overlay_returns
    
    def _apply_vix_guard(self, returns: pd.Series) -> pd.Series:
        """Apply VIX global guard"""
        guarded_returns = self.vix_guard.apply(returns)
        return guarded_returns
    
    def _compute_metrics(self, returns: pd.Series, name: str) -> Dict:
        """Compute performance metrics"""
        sharpe = returns.mean() / returns.std() * np.sqrt(252)
        ann_ret = returns.mean() * 252
        ann_vol = returns.std() * np.sqrt(252)
        
        cum_returns = (1 + returns).cumprod()
        running_max = cum_returns.expanding().max()
        drawdown = cum_returns / running_max - 1.0
        max_dd = drawdown.min()
        
        calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0.0
        
        return {
            'name': name,
            'sharpe': sharpe,
            'ann_return': ann_ret,
            'ann_vol': ann_vol,
            'max_dd': max_dd,
            'calmar': calmar,
            'returns': returns,
        }
    
    def print_results(self, results: Dict):
        """Print backtest results"""
        print("=" * 100)
        print("ARES7-Best Tuning Backtest Results")
        print("=" * 100)
        
        # Table header
        print(f"\n{'Configuration':<30} {'Sharpe':>10} {'Ann Ret':>10} {'Ann Vol':>10} {'Max DD':>10} {'Calmar':>10}")
        print("-" * 100)
        
        # Baseline
        baseline = results['baseline']
        print(f"{baseline['name']:<30} {baseline['sharpe']:>10.3f} {baseline['ann_return']*100:>9.2f}% "
              f"{baseline['ann_vol']*100:>9.2f}% {baseline['max_dd']*100:>9.2f}% {baseline['calmar']:>10.3f}")
        
        # Individual axes
        for key in ['axis1_tc', 'axis2_risk', 'axis3_overlay', 'axis4_vix']:
            if key in results:
                res = results[key]
                sharpe_delta = res['sharpe'] - baseline['sharpe']
                print(f"{res['name']:<30} {res['sharpe']:>10.3f} {res['ann_return']*100:>9.2f}% "
                      f"{res['ann_vol']*100:>9.2f}% {res['max_dd']*100:>9.2f}% {res['calmar']:>10.3f} "
                      f"(Δ Sharpe: {sharpe_delta:+.3f})")
        
        # Combined
        if 'combined' in results:
            combined = results['combined']
            sharpe_delta = combined['sharpe'] - baseline['sharpe']
            print("-" * 100)
            print(f"{combined['name']:<30} {combined['sharpe']:>10.3f} {combined['ann_return']*100:>9.2f}% "
                  f"{combined['ann_vol']*100:>9.2f}% {combined['max_dd']*100:>9.2f}% {combined['calmar']:>10.3f} "
                  f"(Δ Sharpe: {sharpe_delta:+.3f})")
        
        print("=" * 100)
        
        # Target achievement
        if 'combined' in results:
            target_sharpe = 2.0
            current_sharpe = combined['sharpe']
            achievement = (current_sharpe / target_sharpe) * 100
            
            print(f"\n🎯 Target Achievement:")
            print(f"   Baseline Sharpe:  {baseline['sharpe']:.3f}")
            print(f"   Combined Sharpe:  {current_sharpe:.3f}")
            print(f"   Target Sharpe:    {target_sharpe:.3f}")
            print(f"   Achievement:      {achievement:.1f}%")
            
            if current_sharpe >= target_sharpe:
                print(f"   ✅ TARGET ACHIEVED! (+{(current_sharpe - target_sharpe):.3f})")
            else:
                gap = target_sharpe - current_sharpe
                print(f"   ⏳ Gap to target: {gap:.3f} ({gap/target_sharpe*100:.1f}%)")


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 100)
    print("ARES7-Best Tuning Backtest - Example Usage")
    print("=" * 100)
    
    # Generate sample data
    print("\n1. Generating Sample Data...")
    print("-" * 100)
    
    np.random.seed(42)
    dates = pd.date_range('2018-01-01', '2024-12-31', freq='D')
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'JPM', 'BAC', 'WMT', 'PG', 'JNJ']
    
    # Baseline ARES7-Best returns (Sharpe ~1.85)
    base_returns = pd.Series(
        np.random.normal(0.0007, 0.01, len(dates)),  # ~18% return, ~16% vol
        index=dates,
        name='ares7_returns'
    )
    
    # Stock returns
    stock_returns = pd.DataFrame(
        np.random.normal(0.0005, 0.015, (len(dates), len(tickers))),
        index=dates,
        columns=tickers
    )
    
    # Base weights (equal-weighted)
    base_weights = pd.DataFrame(
        1.0 / len(tickers),
        index=dates,
        columns=tickers
    )
    
    # Trades (rebalancing)
    trades = base_weights.diff().fillna(0.0) * 1000000  # $1M portfolio
    
    # ADV and volatility
    adv = pd.Series({t: np.random.uniform(10e6, 100e6) for t in tickers})
    vol = pd.Series({t: np.random.uniform(0.15, 0.30) for t in tickers})
    
    # Quality data (dummy)
    quality_data = {
        'roe': pd.Series(np.random.uniform(0.1, 0.3, len(dates) * len(tickers))),
        'ebitda_margin': pd.Series(np.random.uniform(0.15, 0.40, len(dates) * len(tickers))),
        'debt_equity': pd.Series(np.random.uniform(0.3, 1.5, len(dates) * len(tickers))),
    }
    
    # Momentum data (prices)
    prices = stock_returns.cumsum().apply(np.exp) * 100
    
    # VIX data (dummy)
    vix_data = pd.Series(
        np.random.uniform(12, 35, len(dates)),
        index=dates,
        name='vix'
    )
    
    print(f"✅ Sample data generated:")
    print(f"   Dates: {len(dates)} days ({dates[0].date()} to {dates[-1].date()})")
    print(f"   Tickers: {len(tickers)}")
    print(f"   Base Sharpe (target): ~1.85")
    
    # 2. Create tuning config
    print("\n2. Creating Tuning Configuration...")
    print("-" * 100)
    
    config = TuningConfig(
        enable_tc_model=True,
        enable_risk_scaler=True,
        enable_qm_overlay=False,  # Disable for simplicity (needs proper quality data)
        enable_vix_guard=True,
    )
    
    print("✅ Tuning config created:")
    print(f"   Axis 1 (TC Model):     {'Enabled' if config.enable_tc_model else 'Disabled'}")
    print(f"   Axis 2 (Risk Scaler):  {'Enabled' if config.enable_risk_scaler else 'Disabled'}")
    print(f"   Axis 3 (QM Overlay):   {'Enabled' if config.enable_qm_overlay else 'Disabled'}")
    print(f"   Axis 4 (VIX Guard):    {'Enabled' if config.enable_vix_guard else 'Disabled'}")
    
    # 3. Run backtest
    print("\n3. Running Tuning Backtest...")
    print("-" * 100)
    
    backtest = ARES7TuningBacktest(config)
    
    results = backtest.run(
        base_returns=base_returns,
        base_weights=base_weights,
        stock_returns=stock_returns,
        trades=trades,
        adv_series=adv,
        vol_series=vol,
        vix_data=vix_data,
    )
    
    # 4. Print results
    print("\n4. Results")
    print("-" * 100)
    
    backtest.print_results(results)
    
    print("\n" + "=" * 100)
    print("✅ ARES7-Best Tuning Backtest Complete")
    print("=" * 100)
    print("\nNext Steps:")
    print("  1. Replace sample data with actual ARES7-Best data")
    print("  2. Enable all 4 axes with proper data")
    print("  3. Run full backtest on 2015-2024 period")
    print("  4. Analyze results and tune parameters")
    print("  5. Deploy best configuration to production")
