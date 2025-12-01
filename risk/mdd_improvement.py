# risk/mdd_improvement.py
"""
MDD 개선 모듈: Volatility Targeting + Drawdown-Based Regime Switch
4개 AI 모델(OpenAI GPT-4, Anthropic Claude, xAI Grok, Google Gemini) 제안 통합
"""

import pandas as pd
import numpy as np
from typing import Tuple


def calculate_mdd(returns: pd.Series) -> float:
    """
    Maximum Drawdown (MDD) 계산
    
    Args:
        returns: 일간 수익률 Series
        
    Returns:
        MDD (음수 값, 예: -0.2362 for -23.62%)
    """
    cumulative_returns = (1 + returns).cumprod()
    peak = cumulative_returns.expanding(min_periods=1).max()
    drawdown = (cumulative_returns - peak) / peak
    return drawdown.min()


def apply_volatility_targeting(
    returns: pd.Series,
    target_volatility: float = 0.12,
    vol_window: int = 21,
    max_leverage: float = 1.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Volatility Targeting: 변동성 기반 동적 포지션 사이징
    
    변동성이 높을 때 포지션을 줄이고, 낮을 때 늘려서
    일정한 리스크 수준을 유지합니다.
    
    Args:
        returns: 일간 수익률 Series
        target_volatility: 목표 연율화 변동성 (예: 0.12 = 12%)
        vol_window: Rolling volatility 계산 윈도우 (일수)
        max_leverage: 최대 레버리지 (1.0 = 100% exposure)
        
    Returns:
        (scaled_returns, position_sizes): 조정된 수익률과 포지션 크기
    """
    # Rolling historical volatility (annualized)
    annualization_factor = np.sqrt(252)
    historical_vol = returns.rolling(window=vol_window).std() * annualization_factor
    
    # Avoid division by zero and handle initial NaN values
    historical_vol = historical_vol.replace(0, np.nan).fillna(method='bfill').fillna(target_volatility)
    
    # Calculate volatility-targeted position size
    # Position Size = Target Volatility / Historical Volatility
    position_size = target_volatility / historical_vol
    
    # Cap position size at max_leverage
    position_size = position_size.clip(upper=max_leverage)
    
    # Apply position size to returns (shift to avoid look-ahead bias)
    scaled_returns = returns * position_size.shift(1).fillna(1.0)
    
    return scaled_returns, position_size


def apply_drawdown_regime_switch(
    returns: pd.Series,
    mdd_threshold: float = -0.08,
    recovery_threshold: float = -0.02,
    defensive_exposure: float = 0.3,
    normal_exposure: float = 1.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Drawdown-Based Regime Switch: 드로다운 기반 방어 모드 전환
    
    MDD threshold를 초과하면 defensive regime으로 전환하여
    추가 손실을 방지합니다.
    
    Args:
        returns: 일간 수익률 Series
        mdd_threshold: Defensive regime 진입 임계값 (예: -0.08 = -8%)
        recovery_threshold: Normal regime 복귀 임계값 (예: -0.02 = -2%)
        defensive_exposure: Defensive regime exposure (예: 0.3 = 30%)
        normal_exposure: Normal regime exposure (예: 1.0 = 100%)
        
    Returns:
        (adjusted_returns, exposure): 조정된 수익률과 exposure 레벨
    """
    # Calculate cumulative returns and drawdown
    cumulative_returns = (1 + returns).cumprod()
    peak = cumulative_returns.expanding(min_periods=1).max()
    current_drawdown = (cumulative_returns - peak) / peak
    
    # Shift drawdown by one day to avoid look-ahead bias
    drawdown_signal = current_drawdown.shift(1).fillna(0.0)
    
    # Initialize exposure series
    exposure = pd.Series(normal_exposure, index=returns.index)
    in_defensive = False
    
    # Iterate through drawdown to implement regime switching with hysteresis
    for i in range(1, len(returns)):
        dd = drawdown_signal.iloc[i]
        
        if not in_defensive and dd < mdd_threshold:
            # Enter defensive regime
            exposure.iloc[i:] = defensive_exposure
            in_defensive = True
        elif in_defensive and dd > recovery_threshold:
            # Exit defensive regime (recovery)
            exposure.iloc[i:] = normal_exposure
            in_defensive = False
    
    # Apply exposure to returns
    adjusted_returns = returns * exposure
    
    return adjusted_returns, exposure


def apply_mdd_improvement(
    daily_returns: pd.Series,
    target_volatility: float = 0.12,
    vol_window: int = 21,
    mdd_threshold: float = -0.08,
    recovery_threshold: float = -0.02,
    defensive_exposure: float = 0.3
) -> pd.Series:
    """
    MDD 개선 통합 함수: Volatility Targeting + Drawdown-Based Regime Switch
    
    두 가지 기법을 순차적으로 적용하여 MDD를 개선합니다:
    1. Volatility Targeting: 변동성 기반 포지션 조정
    2. Drawdown-Based Regime Switch: 드로다운 기반 방어 모드
    
    Args:
        daily_returns: 일간 수익률 Series
        target_volatility: 목표 연율화 변동성 (기본: 12%)
        vol_window: Volatility rolling window (기본: 21일)
        mdd_threshold: Defensive regime 진입 임계값 (기본: -8%)
        recovery_threshold: Normal regime 복귀 임계값 (기본: -2%)
        defensive_exposure: Defensive regime exposure (기본: 30%)
        
    Returns:
        MDD 개선된 일간 수익률 Series
    """
    # Step 1: Apply Volatility Targeting
    vol_targeted_returns, _ = apply_volatility_targeting(
        daily_returns,
        target_volatility=target_volatility,
        vol_window=vol_window
    )
    
    # Step 2: Apply Drawdown-Based Regime Switch
    final_returns, _ = apply_drawdown_regime_switch(
        vol_targeted_returns,
        mdd_threshold=mdd_threshold,
        recovery_threshold=recovery_threshold,
        defensive_exposure=defensive_exposure
    )
    
    return final_returns


# --- Example Usage ---
if __name__ == '__main__':
    # Create synthetic returns for testing
    np.random.seed(42)
    
    # Simulate ARES7-like returns (Sharpe ~2.83, Vol ~20.72%)
    annual_return = 0.5859
    annual_vol = 0.2072
    daily_mean = annual_return / 252
    daily_std = annual_vol / np.sqrt(252)
    
    returns_data = np.random.normal(daily_mean, daily_std, 1000)
    
    # Inject a large drawdown event
    drawdown_start = 300
    drawdown_end = 350
    returns_data[drawdown_start:drawdown_end] = np.random.normal(-0.01, daily_std, 50)
    
    base_returns = pd.Series(returns_data, name="Base Strategy Returns")
    
    # Calculate initial performance
    initial_mdd = calculate_mdd(base_returns)
    initial_ann_ret = base_returns.mean() * 252
    initial_ann_vol = base_returns.std() * np.sqrt(252)
    initial_sharpe = initial_ann_ret / initial_ann_vol
    
    print("="*80)
    print("Initial Performance (Before MDD Improvement)")
    print("="*80)
    print(f"Annualized Return: {initial_ann_ret:.2%}")
    print(f"Annualized Volatility: {initial_ann_vol:.2%}")
    print(f"Sharpe Ratio: {initial_sharpe:.2f}")
    print(f"MDD: {initial_mdd:.2%}")
    
    # Apply MDD improvement
    improved_returns = apply_mdd_improvement(
        base_returns,
        target_volatility=0.12,
        mdd_threshold=-0.08,
        defensive_exposure=0.3
    )
    
    # Calculate improved performance
    improved_mdd = calculate_mdd(improved_returns)
    improved_ann_ret = improved_returns.mean() * 252
    improved_ann_vol = improved_returns.std() * np.sqrt(252)
    improved_sharpe = improved_ann_ret / improved_ann_vol
    
    print("\n" + "="*80)
    print("Improved Performance (After MDD Improvement)")
    print("="*80)
    print(f"Annualized Return: {improved_ann_ret:.2%}")
    print(f"Annualized Volatility: {improved_ann_vol:.2%}")
    print(f"Sharpe Ratio: {improved_sharpe:.2f}")
    print(f"MDD: {improved_mdd:.2%}")
    
    print("\n" + "="*80)
    print("Improvement Summary")
    print("="*80)
    print(f"Sharpe Change: {initial_sharpe:.2f} → {improved_sharpe:.2f} ({improved_sharpe - initial_sharpe:+.2f})")
    print(f"MDD Change: {initial_mdd:.2%} → {improved_mdd:.2%} ({improved_mdd - initial_mdd:+.2%})")
