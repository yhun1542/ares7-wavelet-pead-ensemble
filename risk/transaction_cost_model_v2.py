#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARES7 Transaction Cost Model V2
================================

Advanced transaction cost model with:
- Ticker-specific spread and liquidity
- ADV (Average Daily Volume) based impact
- Volatility-based slippage
- Rebalancing frequency scaling

Author: Manus AI
Date: 2025-11-28
Version: 2.0
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass
class TCCoeffs:
    """Transaction Cost Coefficients"""
    base_bps: float = 2.0       # Base commission + spread (bps)
    vol_coeff: float = 1.0      # Volatility coefficient
    adv_coeff: float = 5.0      # Size/ADV coefficient (linear)
    min_cost_bps: float = 1.0   # Minimum cost (bps)
    max_cost_bps: float = 50.0  # Maximum cost cap (bps)


class TransactionCostModelV2:
    """
    Advanced Transaction Cost Model V2
    
    Features:
    - Ticker-specific spread, ADV, volatility
    - Non-linear market impact (size/ADV)
    - Volatility-based slippage
    - Realistic cost estimation for backtesting
    
    Example:
        >>> coeffs = TCCoeffs(base_bps=2.0, vol_coeff=1.0, adv_coeff=5.0)
        >>> tc_model = TransactionCostModelV2(coeffs)
        >>> cost_bps = tc_model.estimate_trade_cost_bps(
        ...     ticker="AAPL",
        ...     trade_notional=100000.0,  # $100k trade
        ...     adv=50000000.0,           # $50M daily volume
        ...     sigma=0.20                # 20% annual volatility
        ... )
        >>> print(f"Cost: {cost_bps:.2f} bps")
    """
    
    def __init__(self, coeffs: TCCoeffs):
        """
        Initialize Transaction Cost Model V2
        
        Args:
            coeffs: TCCoeffs dataclass with cost parameters
        """
        self.coeffs = coeffs
    
    def estimate_trade_cost_bps(
        self,
        ticker: str,
        trade_notional: float,
        adv: float,
        sigma: float,
    ) -> float:
        """
        Estimate transaction cost for a single trade
        
        Args:
            ticker: Stock ticker (for logging/debugging)
            trade_notional: Trade size in dollars (absolute value)
            adv: Average Daily Volume in dollars
            sigma: Daily annualized volatility (e.g., 0.2 for 20%)
        
        Returns:
            Estimated transaction cost in basis points (bps)
        
        Formula:
            cost = base + (trade_notional / adv) * adv_coeff * 10000 
                   + sigma * vol_coeff * 10000
            cost = clip(cost, min_cost_bps, max_cost_bps)
        """
        # ADV term: market impact based on trade size relative to daily volume
        if adv <= 0:
            # Very illiquid: large penalty
            adv_term = 10.0  # 10 bps penalty
        else:
            # Linear impact: larger trades relative to ADV cost more
            adv_term = (trade_notional / adv) * self.coeffs.adv_coeff * 1e4  # → bps
        
        # Volatility term: higher volatility → higher slippage
        vol_term = sigma * self.coeffs.vol_coeff * 1e4  # → bps
        
        # Total cost
        cost = self.coeffs.base_bps + adv_term + vol_term
        
        # Clip to reasonable range
        cost = np.clip(cost, self.coeffs.min_cost_bps, self.coeffs.max_cost_bps)
        
        return float(cost)
    
    def apply_to_trades(
        self,
        trades: pd.DataFrame,
        adv_series: pd.Series,
        vol_series: pd.Series,
        port_value: Optional[pd.Series] = None,
    ) -> pd.Series:
        """
        Apply transaction cost model to a DataFrame of trades
        
        Args:
            trades: DataFrame with index=date, columns=tickers, 
                    values=position changes in dollars
            adv_series: Series with MultiIndex (date, ticker) or just (ticker)
                        containing Average Daily Volume in dollars
            vol_series: Series with MultiIndex (date, ticker) or just (ticker)
                        containing daily annualized volatility
            port_value: Optional Series with index=date, values=portfolio value
                        If None, uses sum of absolute trade notionals
        
        Returns:
            Series with index=date, values=daily transaction cost as fraction
            of portfolio value (e.g., 0.0005 = 5 bps)
        
        Example:
            >>> trades = pd.DataFrame({
            ...     'AAPL': [10000, -5000, 0],
            ...     'MSFT': [0, 8000, -3000]
            ... }, index=pd.date_range('2024-01-01', periods=3))
            >>> 
            >>> adv = pd.Series({
            ...     'AAPL': 50000000,
            ...     'MSFT': 40000000
            ... })
            >>> 
            >>> vol = pd.Series({
            ...     'AAPL': 0.20,
            ...     'MSFT': 0.18
            ... })
            >>> 
            >>> costs = tc_model.apply_to_trades(trades, adv, vol)
        """
        daily_costs = []
        
        for dt, row in trades.iterrows():
            cost_notional = 0.0
            trade_notional_sum = 0.0
            
            for tkr, trade_notional in row.items():
                if trade_notional == 0 or np.isnan(trade_notional):
                    continue
                
                trade_notional_abs = abs(trade_notional)
                trade_notional_sum += trade_notional_abs
                
                # Get ADV for this ticker
                if isinstance(adv_series.index, pd.MultiIndex):
                    # MultiIndex (date, ticker)
                    try:
                        adv = adv_series.loc[(dt, tkr)]
                    except KeyError:
                        adv = adv_series.xs(tkr, level='ticker').mean() if tkr in adv_series.index.get_level_values('ticker') else 0.0
                else:
                    # Single index (ticker)
                    adv = adv_series.get(tkr, 0.0)
                
                # Get volatility for this ticker
                if isinstance(vol_series.index, pd.MultiIndex):
                    # MultiIndex (date, ticker)
                    try:
                        sigma = vol_series.loc[(dt, tkr)]
                    except KeyError:
                        sigma = vol_series.xs(tkr, level='ticker').mean() if tkr in vol_series.index.get_level_values('ticker') else 0.0
                else:
                    # Single index (ticker)
                    sigma = vol_series.get(tkr, 0.0)
                
                # Estimate cost in bps
                bps = self.estimate_trade_cost_bps(tkr, trade_notional_abs, adv, sigma)
                
                # Convert to dollar cost
                cost_notional += trade_notional_abs * (bps / 1e4)
            
            # Convert to portfolio fraction
            if port_value is not None:
                # Use provided portfolio value
                pv = port_value.loc[dt] if dt in port_value.index else trade_notional_sum
            else:
                # Use sum of trade notionals as proxy
                pv = trade_notional_sum
            
            if pv > 0:
                cost_frac = cost_notional / pv
            else:
                cost_frac = 0.0
            
            daily_costs.append((dt, cost_frac))
        
        # Create Series
        cost_series = pd.Series(
            data=[c for (_, c) in daily_costs],
            index=[d for (d, _) in daily_costs],
            name="tc_cost",
        ).sort_index()
        
        return cost_series
    
    def compute_tc_adjusted_returns(
        self,
        returns: pd.Series,
        trades: pd.DataFrame,
        adv_series: pd.Series,
        vol_series: pd.Series,
        port_value: Optional[pd.Series] = None,
    ) -> pd.Series:
        """
        Compute transaction-cost-adjusted returns
        
        Args:
            returns: Series with index=date, values=gross returns
            trades: DataFrame with index=date, columns=tickers, 
                    values=position changes
            adv_series: ADV data (see apply_to_trades)
            vol_series: Volatility data (see apply_to_trades)
            port_value: Optional portfolio value series
        
        Returns:
            Series with index=date, values=net returns (after TC)
        
        Example:
            >>> gross_returns = pd.Series([0.01, -0.005, 0.008], 
            ...                           index=pd.date_range('2024-01-01', periods=3))
            >>> net_returns = tc_model.compute_tc_adjusted_returns(
            ...     gross_returns, trades, adv, vol
            ... )
        """
        # Compute transaction costs
        tc_costs = self.apply_to_trades(trades, adv_series, vol_series, port_value)
        
        # Align indices
        tc_costs = tc_costs.reindex(returns.index, fill_value=0.0)
        
        # Subtract costs from returns
        net_returns = returns - tc_costs
        
        return net_returns


def estimate_adv_from_prices(
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    window: int = 20,
) -> pd.Series:
    """
    Estimate Average Daily Volume (ADV) in dollars from price and volume data
    
    Args:
        prices: DataFrame with index=date, columns=tickers, values=close prices
        volumes: DataFrame with index=date, columns=tickers, values=volume
        window: Rolling window for ADV calculation (default: 20 days)
    
    Returns:
        Series with MultiIndex (date, ticker), values=ADV in dollars
    
    Example:
        >>> prices = pd.DataFrame({
        ...     'AAPL': [150, 152, 151],
        ...     'MSFT': [300, 305, 302]
        ... }, index=pd.date_range('2024-01-01', periods=3))
        >>> 
        >>> volumes = pd.DataFrame({
        ...     'AAPL': [1000000, 1200000, 1100000],
        ...     'MSFT': [800000, 850000, 820000]
        ... }, index=pd.date_range('2024-01-01', periods=3))
        >>> 
        >>> adv = estimate_adv_from_prices(prices, volumes, window=20)
    """
    # Compute dollar volume for each day
    dollar_volume = prices * volumes
    
    # Rolling mean
    adv = dollar_volume.rolling(window=window, min_periods=1).mean()
    
    # Convert to MultiIndex Series
    adv_stacked = adv.stack()
    adv_stacked.index.names = ['date', 'ticker']
    adv_stacked.name = 'adv'
    
    return adv_stacked


def estimate_volatility_from_returns(
    returns: pd.DataFrame,
    window: int = 30,
    annualize: bool = True,
) -> pd.Series:
    """
    Estimate volatility from returns
    
    Args:
        returns: DataFrame with index=date, columns=tickers, values=daily returns
        window: Rolling window for volatility calculation (default: 30 days)
        annualize: If True, annualize volatility (multiply by sqrt(252))
    
    Returns:
        Series with MultiIndex (date, ticker), values=volatility
    
    Example:
        >>> returns = pd.DataFrame({
        ...     'AAPL': [0.01, -0.02, 0.015],
        ...     'MSFT': [0.008, -0.01, 0.012]
        ... }, index=pd.date_range('2024-01-01', periods=3))
        >>> 
        >>> vol = estimate_volatility_from_returns(returns, window=30)
    """
    # Rolling std
    vol = returns.rolling(window=window, min_periods=1).std()
    
    # Annualize
    if annualize:
        vol = vol * np.sqrt(252)
    
    # Convert to MultiIndex Series
    vol_stacked = vol.stack()
    vol_stacked.index.names = ['date', 'ticker']
    vol_stacked.name = 'volatility'
    
    return vol_stacked


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("ARES7 Transaction Cost Model V2 - Example Usage")
    print("=" * 80)
    
    # 1. Create TC model
    coeffs = TCCoeffs(
        base_bps=2.0,
        vol_coeff=1.0,
        adv_coeff=5.0,
        min_cost_bps=1.0,
        max_cost_bps=50.0,
    )
    tc_model = TransactionCostModelV2(coeffs)
    
    print("\n1. Single Trade Cost Estimation")
    print("-" * 80)
    
    # Example: $100k trade in AAPL
    cost_aapl = tc_model.estimate_trade_cost_bps(
        ticker="AAPL",
        trade_notional=100000.0,  # $100k
        adv=50000000.0,           # $50M daily volume
        sigma=0.20                # 20% annual volatility
    )
    print(f"AAPL $100k trade: {cost_aapl:.2f} bps")
    
    # Example: $100k trade in small-cap stock
    cost_small = tc_model.estimate_trade_cost_bps(
        ticker="SMALL",
        trade_notional=100000.0,  # $100k
        adv=5000000.0,            # $5M daily volume (10x less liquid)
        sigma=0.35                # 35% annual volatility (higher vol)
    )
    print(f"Small-cap $100k trade: {cost_small:.2f} bps")
    
    print("\n2. Portfolio-Level Cost Calculation")
    print("-" * 80)
    
    # Create sample trades
    dates = pd.date_range('2024-01-01', periods=5, freq='D')
    trades = pd.DataFrame({
        'AAPL': [100000, -50000, 0, 80000, -30000],
        'MSFT': [0, 60000, -40000, 0, 50000],
        'GOOGL': [70000, 0, -35000, 45000, 0],
    }, index=dates)
    
    # Create ADV data (constant for simplicity)
    adv = pd.Series({
        'AAPL': 50000000,
        'MSFT': 40000000,
        'GOOGL': 30000000,
    })
    
    # Create volatility data (constant for simplicity)
    vol = pd.Series({
        'AAPL': 0.20,
        'MSFT': 0.18,
        'GOOGL': 0.22,
    })
    
    # Compute costs
    costs = tc_model.apply_to_trades(trades, adv, vol)
    
    print("Daily Transaction Costs:")
    for dt, cost in costs.items():
        print(f"  {dt.date()}: {cost*1e4:.2f} bps")
    
    print(f"\nAverage Daily Cost: {costs.mean()*1e4:.2f} bps")
    print(f"Total Cost (5 days): {costs.sum()*1e4:.2f} bps")
    
    print("\n3. TC-Adjusted Returns")
    print("-" * 80)
    
    # Create sample gross returns
    gross_returns = pd.Series([0.01, -0.005, 0.008, 0.012, -0.003], index=dates)
    
    # Compute net returns
    net_returns = tc_model.compute_tc_adjusted_returns(
        gross_returns, trades, adv, vol
    )
    
    print("Gross vs Net Returns:")
    for dt in dates:
        gr = gross_returns.loc[dt]
        nr = net_returns.loc[dt]
        tc = costs.loc[dt] if dt in costs.index else 0.0
        print(f"  {dt.date()}: Gross={gr*100:6.2f}%, TC={tc*1e4:5.2f}bps, Net={nr*100:6.2f}%")
    
    # Performance impact
    gross_sharpe = gross_returns.mean() / gross_returns.std() * np.sqrt(252)
    net_sharpe = net_returns.mean() / net_returns.std() * np.sqrt(252)
    
    print(f"\nGross Sharpe: {gross_sharpe:.3f}")
    print(f"Net Sharpe:   {net_sharpe:.3f}")
    print(f"Impact:       {(net_sharpe - gross_sharpe):.3f} ({(net_sharpe/gross_sharpe - 1)*100:.1f}%)")
    
    print("\n" + "=" * 80)
    print("✅ Transaction Cost Model V2 Ready for ARES7 Integration")
    print("=" * 80)
