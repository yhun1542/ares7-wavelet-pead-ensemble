import numpy as np
import pandas as pd

def calculate_historical_volatility(prices, window=20, asymmetry=0.5):
    """
    Calculates historical volatility with asymmetric weighting.

    Args:
        prices (pd.Series): Price data.
        window (int): Rolling window for volatility calculation.
        asymmetry (float): Weighting factor for downside volatility (0.0 to 1.0).
                           1.0 means only downside volatility is considered.
                           0.5 means equal weighting.  Values above 0.5 weight downside more.

    Returns:
        pd.Series: Historical volatility series.
    """
    returns = prices.pct_change().dropna()
    squared_returns = returns**2
    downside_filter = returns < 0  # Boolean mask for downside returns

    # Weighted squared returns
    weighted_squared_returns = squared_returns.copy()
    weighted_squared_returns[downside_filter] *= (1 + asymmetry)
    weighted_squared_returns[~downside_filter] *= (1 - asymmetry)

    # Rolling average of weighted squared returns
    rolling_variance = weighted_squared_returns.rolling(window).mean()
    rolling_volatility = np.sqrt(rolling_variance)

    return rolling_volatility


def calculate_moving_average(prices, window=50):
    """Calculates the moving average of a price series."""
    return prices.rolling(window).mean()

def backtest(prices, initial_capital=100000, volatility_target=0.20, drawdown_threshold=-0.10, ma_window=50, asymmetry=0.7, max_leverage=1.5):
    """
    Backtests a volatility-targeted strategy with dynamic leverage adjustment,
    asymmetric volatility weighting, and a moving average trend filter.

    Args:
        prices (pd.Series): Price data.
        initial_capital (float): Initial capital.
        volatility_target (float): Target annualized volatility.
        drawdown_threshold (float): Drawdown threshold for regime switching.
        ma_window (int): Window for moving average calculation.
        asymmetry (float): Asymmetry for volatility calculation (downside weighting).
        max_leverage (float): Maximum allowed leverage.

    Returns:
        pd.DataFrame: DataFrame containing backtest results (positions, capital, returns, etc.).
    """
    capital = initial_capital
    positions = []
    capital_values = []
    returns = []
    drawdowns = []
    peak = capital  # Initialize peak capital for drawdown calculation
    leverage_factors = []

    # Calculate historical volatility with asymmetry
    historical_volatility = calculate_historical_volatility(prices, asymmetry=asymmetry)

    # Calculate moving average
    moving_average = calculate_moving_average(prices, ma_window)

    for i in range(1, len(prices)):
        # Calculate position size based on volatility targeting
        volatility = historical_volatility.iloc[i-1]
        if np.isnan(volatility) or volatility == 0:
            position_size = 0  # No position if volatility is NaN or zero
        else:
            position_size = (volatility_target / volatility) * capital


        # Trend following filter: Increase leverage if price > moving average
        if prices.iloc[i] > moving_average.iloc[i-1]: #price higher than the moving average, assume upward trend
          trend_factor = 1.0  # Set leverage multiplier to 1 (or potentially higher, depending on the strength of the signal)
        else:
          trend_factor = 0.5 # reduce leverage when trend is unfavorable

        # Drawdown-based regime switch (example - adapt to your existing logic)
        current_drawdown = (capital - peak) / peak
        if current_drawdown < drawdown_threshold:  # Example drawdown regime
            position_size = 0
            trend_factor = 0 #reduce exposure even if trend looks favorable
        else:
            peak = max(peak, capital)

        # Dynamic Leverage Adjustment: Apply trend factor and limit by max_leverage
        leverage_factor = min(trend_factor, max_leverage / (position_size / capital))
        position_size *= leverage_factor
        leverage_factors.append(leverage_factor) #record for analysis


        # Calculate daily return
        price_change = prices.iloc[i] - prices.iloc[i-1]
        daily_return = (position_size / prices.iloc[i-1]) * price_change

        # Update capital
        capital *= (1 + daily_return)

        # Store results
        positions.append(position_size)
        capital_values.append(capital)
        returns.append(daily_return)
        drawdown = (capital - max(capital_values, default=capital)) / max(capital_values, default=capital)
        drawdowns.append(drawdown)



    results = pd.DataFrame({
        'Position': positions,
        'Capital': capital_values,
        'Return': returns,
        'Drawdown': drawdowns,
        'Leverage Factor': leverage_factors
    }, index=prices.index[1:])

    return results


# Example Usage
if __name__ == '__main__':
    # Generate sample price data (replace with your actual data)
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', '2024-01-01', freq='B')
    daily_returns = np.random.normal(0.0005, 0.01, len(dates)) # Simulate daily returns
    prices = (1 + pd.Series(daily_returns, index=dates)).cumprod() * 100  # Start at 100

    # Backtest parameters
    initial_capital = 100000
    volatility_target = 0.20
    drawdown_threshold = -0.10
    ma_window = 50
    asymmetry = 0.7  # Higher value means more weight to downside volatility
    max_leverage = 1.5  # Maximum allowable leverage

    # Run backtest
    results = backtest(prices, initial_capital, volatility_target, drawdown_threshold, ma_window, asymmetry, max_leverage)

    # Analyze results
    total_return = (results['Capital'].iloc[-1] - initial_capital) / initial_capital
    annualized_return = (1 + total_return)**(252/len(results)) - 1 # Assuming 252 trading days per year
    annualized_volatility = results['Return'].std() * np.sqrt(252)
    sharpe_ratio = annualized_return / annualized_volatility
    mdd = results['Drawdown'].min()


    print(f"Total Return: {total_return:.2%}")
    print(f"Annualized Return: {annualized_return:.2%}")
    print(f"Annualized Volatility: {annualized_volatility:.2%}")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Maximum Drawdown: {mdd:.2%}")

    # You can further analyze the 'results' DataFrame, e.g., plot the capital curve:
    import matplotlib.pyplot as plt
    plt.plot(results['Capital'])
    plt.title("Capital Over Time")
    plt.xlabel("Date")
    plt.ylabel("Capital")
    plt.show()