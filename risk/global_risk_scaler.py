#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARES7 Global Risk Scaler
=========================

Dynamic leverage and risk targeting module for ARES7-Best ensemble.

Features:
- Volatility targeting (e.g., 8%, 10%, 12%)
- Dynamic leverage adjustment (0.5x ~ 2.0x)
- Drawdown-based leverage reduction
- Kelly fraction support

Author: Manus AI
Date: 2025-11-28
Version: 2.0
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class GlobalRiskConfig:
    """Global Risk Management Configuration"""
    target_vol: float = 0.10      # Target annual volatility (10%)
    lookback_days: int = 63       # Lookback window for vol estimation (3 months)
    max_leverage: float = 2.0     # Maximum leverage multiplier
    min_leverage: float = 0.5     # Minimum leverage multiplier
    
    # Drawdown-based leverage reduction
    enable_dd_reduction: bool = True
    dd_threshold_1: float = -0.10  # -10% DD → reduce leverage
    dd_threshold_2: float = -0.15  # -15% DD → reduce more
    dd_reduction_1: float = 0.75   # Reduce to 75% of target leverage
    dd_reduction_2: float = 0.50   # Reduce to 50% of target leverage
    
    # Kelly fraction (optional)
    use_kelly: bool = False
    kelly_fraction: float = 0.5    # Half-Kelly (conservative)


class GlobalRiskScaler:
    """
    Global Risk Scaler for ARES7-Best
    
    Applies dynamic leverage based on:
    1. Volatility targeting
    2. Drawdown-based reduction
    3. Kelly fraction (optional)
    
    Example:
        >>> config = GlobalRiskConfig(target_vol=0.10, max_leverage=2.0)
        >>> scaler = GlobalRiskScaler(config)
        >>> 
        >>> # Compute leverage series
        >>> leverage = scaler.compute_leverage_series(portfolio_returns)
        >>> 
        >>> # Apply leverage to returns
        >>> scaled_returns = scaler.apply(portfolio_returns)
    """
    
    def __init__(self, cfg: GlobalRiskConfig):
        """
        Initialize Global Risk Scaler
        
        Args:
            cfg: GlobalRiskConfig dataclass
        """
        self.cfg = cfg
    
    def compute_realized_vol(self, returns: pd.Series) -> pd.Series:
        """
        Compute realized volatility (annualized)
        
        Args:
            returns: Daily returns series
        
        Returns:
            Series of annualized volatility
        """
        # Rolling std
        vol_daily = returns.rolling(
            window=self.cfg.lookback_days,
            min_periods=max(1, self.cfg.lookback_days // 2)
        ).std()
        
        # Annualize
        vol_annual = vol_daily * np.sqrt(252)
        
        return vol_annual
    
    def compute_vol_target_leverage(self, returns: pd.Series) -> pd.Series:
        """
        Compute leverage based on volatility targeting
        
        Args:
            returns: Daily returns series
        
        Returns:
            Series of leverage multipliers
        
        Formula:
            leverage = target_vol / realized_vol
            leverage = clip(leverage, min_leverage, max_leverage)
        """
        # Compute realized vol
        realized_vol = self.compute_realized_vol(returns)
        
        # Target leverage
        target_leverage = self.cfg.target_vol / realized_vol
        
        # Clip to range
        target_leverage = target_leverage.clip(
            lower=self.cfg.min_leverage,
            upper=self.cfg.max_leverage
        )
        
        # Fill NaN with 1.0 (neutral)
        target_leverage = target_leverage.fillna(1.0)
        
        return target_leverage
    
    def compute_drawdown(self, returns: pd.Series) -> pd.Series:
        """
        Compute running drawdown
        
        Args:
            returns: Daily returns series
        
        Returns:
            Series of drawdown values (negative, e.g., -0.15 for -15%)
        """
        # Cumulative returns
        cum_returns = (1 + returns).cumprod()
        
        # Running maximum
        running_max = cum_returns.expanding().max()
        
        # Drawdown
        drawdown = cum_returns / running_max - 1.0
        
        return drawdown
    
    def compute_dd_adjustment(self, returns: pd.Series) -> pd.Series:
        """
        Compute drawdown-based leverage adjustment
        
        Args:
            returns: Daily returns series
        
        Returns:
            Series of adjustment factors (e.g., 1.0, 0.75, 0.50)
        """
        if not self.cfg.enable_dd_reduction:
            return pd.Series(1.0, index=returns.index)
        
        # Compute drawdown
        dd = self.compute_drawdown(returns)
        
        # Adjustment factor
        adjustment = pd.Series(1.0, index=returns.index)
        
        # Apply thresholds
        adjustment[dd <= self.cfg.dd_threshold_2] = self.cfg.dd_reduction_2
        adjustment[(dd > self.cfg.dd_threshold_2) & (dd <= self.cfg.dd_threshold_1)] = self.cfg.dd_reduction_1
        
        return adjustment
    
    def compute_kelly_leverage(
        self,
        returns: pd.Series,
        lookback_days: Optional[int] = None,
    ) -> pd.Series:
        """
        Compute Kelly-based leverage
        
        Args:
            returns: Daily returns series
            lookback_days: Lookback window for Kelly calculation
                          (default: use cfg.lookback_days)
        
        Returns:
            Series of Kelly leverage multipliers
        
        Formula:
            kelly = (mean_return / variance) * kelly_fraction
            kelly = clip(kelly, min_leverage, max_leverage)
        """
        if lookback_days is None:
            lookback_days = self.cfg.lookback_days
        
        # Rolling mean and variance
        mean_ret = returns.rolling(lookback_days, min_periods=lookback_days//2).mean()
        var_ret = returns.rolling(lookback_days, min_periods=lookback_days//2).var()
        
        # Kelly fraction
        kelly = (mean_ret / var_ret) * self.cfg.kelly_fraction
        
        # Clip to range
        kelly = kelly.clip(
            lower=self.cfg.min_leverage,
            upper=self.cfg.max_leverage
        )
        
        # Fill NaN with 1.0
        kelly = kelly.fillna(1.0)
        
        return kelly
    
    def compute_leverage_series(self, returns: pd.Series) -> pd.Series:
        """
        Compute final leverage series combining all factors
        
        Args:
            returns: Daily returns series (unleveraged)
        
        Returns:
            Series of leverage multipliers
        
        Logic:
            1. Start with vol-targeting leverage
            2. Apply drawdown adjustment
            3. Optionally apply Kelly constraint
        """
        # 1. Vol-targeting leverage
        vol_lev = self.compute_vol_target_leverage(returns)
        
        # 2. Drawdown adjustment
        dd_adj = self.compute_dd_adjustment(returns)
        
        # 3. Combine
        leverage = vol_lev * dd_adj
        
        # 4. Kelly constraint (optional)
        if self.cfg.use_kelly:
            kelly_lev = self.compute_kelly_leverage(returns)
            # Take minimum of vol-target and Kelly
            leverage = pd.concat([leverage, kelly_lev], axis=1).min(axis=1)
        
        # 5. Final clip
        leverage = leverage.clip(
            lower=self.cfg.min_leverage,
            upper=self.cfg.max_leverage
        )
        
        # 6. Fill NaN
        leverage = leverage.fillna(1.0)
        
        leverage.name = "leverage"
        return leverage
    
    def apply(self, returns: pd.Series) -> pd.Series:
        """
        Apply leverage to returns
        
        Args:
            returns: Daily returns series (unleveraged)
        
        Returns:
            Series of leveraged returns
        
        Example:
            >>> unleveraged_returns = pd.Series([0.01, -0.005, 0.008])
            >>> leveraged_returns = scaler.apply(unleveraged_returns)
        """
        # Compute leverage
        leverage = self.compute_leverage_series(returns)
        
        # Align indices (leverage lags by 1 day for realistic application)
        leverage_aligned = leverage.shift(1).reindex(returns.index).fillna(1.0)
        
        # Apply leverage
        leveraged_returns = returns * leverage_aligned
        
        return leveraged_returns
    
    def get_statistics(self, returns: pd.Series) -> dict:
        """
        Get risk statistics for analysis
        
        Args:
            returns: Daily returns series
        
        Returns:
            Dictionary with risk statistics
        """
        leverage = self.compute_leverage_series(returns)
        realized_vol = self.compute_realized_vol(returns)
        drawdown = self.compute_drawdown(returns)
        dd_adj = self.compute_dd_adjustment(returns)
        
        stats = {
            'leverage_mean': leverage.mean(),
            'leverage_std': leverage.std(),
            'leverage_min': leverage.min(),
            'leverage_max': leverage.max(),
            'realized_vol_mean': realized_vol.mean(),
            'realized_vol_std': realized_vol.std(),
            'max_drawdown': drawdown.min(),
            'dd_adjustment_mean': dd_adj.mean(),
            'days_with_dd_reduction': (dd_adj < 1.0).sum(),
        }
        
        return stats


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("ARES7 Global Risk Scaler - Example Usage")
    print("=" * 80)
    
    # Generate sample returns (with some volatility clustering and drawdown)
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=1000, freq='D')
    
    # Simulate returns with regime changes
    returns_regime1 = np.random.normal(0.0005, 0.01, 500)  # Low vol regime
    returns_regime2 = np.random.normal(0.0003, 0.02, 300)  # High vol regime
    returns_regime3 = np.random.normal(0.0004, 0.015, 200) # Medium vol regime
    
    returns = pd.Series(
        np.concatenate([returns_regime1, returns_regime2, returns_regime3]),
        index=dates,
        name='returns'
    )
    
    print("\n1. Volatility Targeting (10%)")
    print("-" * 80)
    
    # Config: 10% vol target
    config = GlobalRiskConfig(
        target_vol=0.10,
        lookback_days=63,
        max_leverage=2.0,
        min_leverage=0.5,
        enable_dd_reduction=False,  # Disable DD reduction for now
    )
    
    scaler = GlobalRiskScaler(config)
    
    # Compute leverage
    leverage = scaler.compute_leverage_series(returns)
    
    # Apply leverage
    leveraged_returns = scaler.apply(returns)
    
    # Stats
    unleveraged_vol = returns.std() * np.sqrt(252)
    leveraged_vol = leveraged_returns.std() * np.sqrt(252)
    
    print(f"Unleveraged Vol: {unleveraged_vol*100:.2f}%")
    print(f"Leveraged Vol:   {leveraged_vol*100:.2f}%")
    print(f"Target Vol:      {config.target_vol*100:.2f}%")
    print(f"Average Leverage: {leverage.mean():.2f}x")
    print(f"Leverage Range:  {leverage.min():.2f}x - {leverage.max():.2f}x")
    
    print("\n2. Drawdown-Based Leverage Reduction")
    print("-" * 80)
    
    # Config: Enable DD reduction
    config_dd = GlobalRiskConfig(
        target_vol=0.10,
        lookback_days=63,
        max_leverage=2.0,
        min_leverage=0.5,
        enable_dd_reduction=True,
        dd_threshold_1=-0.10,
        dd_threshold_2=-0.15,
        dd_reduction_1=0.75,
        dd_reduction_2=0.50,
    )
    
    scaler_dd = GlobalRiskScaler(config_dd)
    
    # Get statistics
    stats = scaler_dd.get_statistics(returns)
    
    print(f"Max Drawdown: {stats['max_drawdown']*100:.2f}%")
    print(f"Days with DD Reduction: {stats['days_with_dd_reduction']} / {len(returns)}")
    print(f"DD Adjustment Mean: {stats['dd_adjustment_mean']:.3f}")
    print(f"Average Leverage: {stats['leverage_mean']:.2f}x")
    
    print("\n3. Performance Comparison")
    print("-" * 80)
    
    # Unleveraged
    unlev_sharpe = returns.mean() / returns.std() * np.sqrt(252)
    unlev_ret = returns.mean() * 252
    unlev_vol = returns.std() * np.sqrt(252)
    
    # Vol-targeted (no DD reduction)
    lev_returns = scaler.apply(returns)
    lev_sharpe = lev_returns.mean() / lev_returns.std() * np.sqrt(252)
    lev_ret = lev_returns.mean() * 252
    lev_vol = lev_returns.std() * np.sqrt(252)
    
    # Vol-targeted + DD reduction
    lev_dd_returns = scaler_dd.apply(returns)
    lev_dd_sharpe = lev_dd_returns.mean() / lev_dd_returns.std() * np.sqrt(252)
    lev_dd_ret = lev_dd_returns.mean() * 252
    lev_dd_vol = lev_dd_returns.std() * np.sqrt(252)
    
    print("Unleveraged:")
    print(f"  Sharpe: {unlev_sharpe:.3f}")
    print(f"  Return: {unlev_ret*100:.2f}%")
    print(f"  Vol:    {unlev_vol*100:.2f}%")
    
    print("\nVol-Targeted (10%):")
    print(f"  Sharpe: {lev_sharpe:.3f} ({(lev_sharpe/unlev_sharpe-1)*100:+.1f}%)")
    print(f"  Return: {lev_ret*100:.2f}%")
    print(f"  Vol:    {lev_vol*100:.2f}%")
    
    print("\nVol-Targeted + DD Reduction:")
    print(f"  Sharpe: {lev_dd_sharpe:.3f} ({(lev_dd_sharpe/unlev_sharpe-1)*100:+.1f}%)")
    print(f"  Return: {lev_dd_ret*100:.2f}%")
    print(f"  Vol:    {lev_dd_vol*100:.2f}%")
    
    print("\n4. Kelly Fraction (Optional)")
    print("-" * 80)
    
    # Config: Kelly
    config_kelly = GlobalRiskConfig(
        target_vol=0.10,
        lookback_days=63,
        max_leverage=2.0,
        min_leverage=0.5,
        enable_dd_reduction=True,
        use_kelly=True,
        kelly_fraction=0.5,  # Half-Kelly
    )
    
    scaler_kelly = GlobalRiskScaler(config_kelly)
    lev_kelly_returns = scaler_kelly.apply(returns)
    lev_kelly_sharpe = lev_kelly_returns.mean() / lev_kelly_returns.std() * np.sqrt(252)
    
    print(f"Vol-Targeted + DD + Kelly:")
    print(f"  Sharpe: {lev_kelly_sharpe:.3f} ({(lev_kelly_sharpe/unlev_sharpe-1)*100:+.1f}%)")
    
    print("\n" + "=" * 80)
    print("✅ Global Risk Scaler Ready for ARES7 Integration")
    print("=" * 80)
    print("\nRecommended Configs for ARES7-Best:")
    print("  1. Conservative: target_vol=0.08, max_leverage=1.5")
    print("  2. Moderate:     target_vol=0.10, max_leverage=2.0 (current)")
    print("  3. Aggressive:   target_vol=0.12, max_leverage=2.5")
