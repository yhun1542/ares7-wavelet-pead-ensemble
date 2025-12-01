import numpy as np
import pandas as pd

def calculate_volatility_target(returns, target_vol=0.15, lookback=21):
    # Calculate realized volatility
    realized_vol = returns.rolling(lookback).std() * np.sqrt(252)
    # Calculate position size based on target volatility
    position_size = target_vol / realized_vol
    position_size = position_size.clip(upper=1.0)  # Restrict max position size to 1.0
    return position_size

def calculate_trend_signal(returns, lookback=50):
    # Simple moving average crossover as a trend signal
    short_ma = returns.rolling(lookback // 2).mean()
    long_ma = returns.rolling(lookback).mean()
    trend_signal = (short_ma > long_ma).astype(int)
    return trend_signal

def apply_dynamic_leverage(returns, position_size, trend_signal, max_leverage=2.0):
    # Dynamically adjust leverage based on trend signal
    dynamic_exposure = position_size * (1 + trend_signal * (max_leverage - 1))
    return returns * dynamic_exposure.shift(1)

def optimize_strategy(returns):
    # Calculate position size based on volatility targeting
    position_size = calculate_volatility_target(returns)
    # Calculate trend signal
    trend_signal = calculate_trend_signal(returns)
    # Apply dynamic leverage
    optimized_returns = apply_dynamic_leverage(returns, position_size, trend_signal)
    return optimized_returns

# Assuming `returns` is your historical returns data as a pandas Series
optimized_returns = optimize_strategy(returns)

# Evaluate performance
annualized_return = optimized_returns.mean() * 252
annualized_volatility = optimized_returns.std() * np.sqrt(252)
mdd = (optimized_returns.cumsum().cummax() - optimized_returns.cumsum()).max()
sharpe_ratio = annualized_return / annualized_volatility
cvar_95 = optimized_returns[optimized_returns < optimized_returns.quantile(0.05)].mean()

print(f"Annualized Return: {annualized_return:.2%}")
print(f"Annualized Volatility: {annualized_volatility:.2%}")
print(f"Max Drawdown: {mdd:.2%}")
print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
print(f"CVaR (95%): {cvar_95:.4f}")