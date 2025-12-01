import numpy as np
import pandas as pd

class EnhancedAARM:
    def __init__(self,
                 initial_capital=100000,
                 kelly_fraction=0.1,  # Baseline Kelly fraction
                 max_leverage=2.0,      # Maximum leverage allowed
                 volatility_lookback=60, # Lookback for volatility calculation (days)
                 drawdown_threshold=0.05,  # Initial drawdown threshold (5%)
                 drawdown_reduction_factor=0.5, # Reduction factor for position size
                 volatility_threshold=0.1, # Threshold for high volatility regime
                 volatility_scale_factor=0.5, # Scale factor for leverage reduction
                 adaptive_drawdown_scale=2.0, # Scale factor for adaptive drawdown
                 transaction_cost=0.001):   # Transaction cost per trade (0.1%)

        self.capital = initial_capital
        self.position = 0  # Current position size
        self.kelly_fraction = kelly_fraction
        self.max_leverage = max_leverage
        self.volatility_lookback = volatility_lookback
        self.drawdown_threshold = drawdown_threshold
        self.drawdown_reduction_factor = drawdown_reduction_factor
        self.volatility_threshold = volatility_threshold
        self.volatility_scale_factor = volatility_scale_factor
        self.adaptive_drawdown_scale = adaptive_drawdown_scale
        self.transaction_cost = transaction_cost
        self.peak_equity = initial_capital
        self.equity_curve = [initial_capital]
        self.trades = [] # store trade information
        self.returns = []

    def calculate_kelly_leverage(self, edge, win_rate, volatility):
        """Calculates Kelly leverage, capped by volatility-adjusted maximum leverage."""
        kelly_leverage = (edge * win_rate - (1 - win_rate) * edge) / (edge**2) if edge!=0 else 0
        kelly_leverage = self.kelly_fraction * kelly_leverage
        # Volatility-Adjusted Leverage Cap
        volatility_adjustment = max(0, 1 - (volatility / self.volatility_threshold) * self.volatility_scale_factor)
        max_leverage = self.max_leverage * volatility_adjustment
        return np.clip(kelly_leverage, -max_leverage, max_leverage) # ensure leverage stays within -max_leverage and max_leverage

    def graduated_drawdown_response(self):
        """Reduces position size based on drawdown level."""
        drawdown = (self.peak_equity - self.capital) / self.peak_equity
        if drawdown > self.drawdown_threshold:
            # Adaptive Drawdown Threshold
            adaptive_threshold = self.drawdown_threshold + (drawdown - self.drawdown_threshold) * self.adaptive_drawdown_scale
            if drawdown > adaptive_threshold:
                reduction_factor = self.drawdown_reduction_factor * (drawdown / adaptive_threshold)  # Scale reduction with drawdown
                reduction_factor = min(reduction_factor, 1.0)
                self.position *= (1 - reduction_factor)
                print(f"Drawdown response triggered. Reducing position by {reduction_factor*100:.2f}%")


    def execute_trade(self, price, signal, edge, win_rate, returns, prices):
        """Executes a trade based on the signal and risk management rules."""
        # Calculate Volatility
        volatility = np.std(returns[-self.volatility_lookback:]) if len(returns) >= self.volatility_lookback else 0

        # Calculate Kelly Leverage
        kelly_leverage = self.calculate_kelly_leverage(edge, win_rate, volatility)

        # Graduated Drawdown Response
        self.graduated_drawdown_response()

        # Calculate target position size
        target_position = self.capital * kelly_leverage

        # Adjust position based on momentum overlay (assuming you have a momentum signal)
        # momentum_adjustment = self.get_momentum_adjustment(prices) # replace with your momentum signal
        # target_position *= (1 + momentum_adjustment)
        # target_position = np.clip(target_position, -self.capital * self.max_leverage, self.capital * self.max_leverage)

        # Calculate trade size
        trade_size = target_position - self.position
        trade_cost = abs(trade_size) * self.transaction_cost
        if self.capital - trade_cost < 0:
            trade_size = (self.capital / self.transaction_cost - 1) * np.sign(trade_size)
            trade_cost = abs(trade_size) * self.transaction_cost
            print("Trade size adjusted due to insufficient capital.")

        # Execute trade
        self.capital -= trade_cost
        self.position += trade_size
        self.trades.append({"price":price, "trade_size":trade_size, "trade_cost":trade_cost, "position":self.position})

    def process_signal(self, price, signal, edge, win_rate, returns, prices):
        """Processes a trading signal and updates the portfolio."""

        # Execute trade based on signal
        self.execute_trade(price, signal, edge, win_rate, returns, prices)

        # Calculate return
        current_return = (self.position * (price - self.trades[-1]["price"]) if len(self.trades)>0 else 0)
        self.capital += current_return
        self.returns.append(current_return)

        # Update equity curve and peak equity
        self.equity_curve.append(self.capital)
        self.peak_equity = max(self.peak_equity, self.capital)


# Example Usage (replace with your actual data and signals)
if __name__ == '__main__':
    # Generate some dummy data for demonstration
    np.random.seed(42)
    num_days = 200
    prices = np.cumsum(np.random.normal(0.001, 0.01, num_days)) + 100  # Simulating prices
    signals = np.random.choice([-1, 0, 1], num_days, p=[0.3, 0.4, 0.3])  # Simulating signals (-1: short, 0: neutral, 1: long)
    edges = np.random.uniform(0.01, 0.05, num_days) # Simulating edges
    win_rates = np.random.uniform(0.5, 0.6, num_days) # Simulating win rates
    returns = np.random.normal(0.0005, 0.005, num_days) # Simulating returns

    # Initialize AARM
    aarm = EnhancedAARM()

    # Simulate trading
    for i in range(1, num_days):
        aarm.process_signal(prices[i], signals[i], edges[i], win_rates[i], returns[:i], prices[:i])

    # Analyze results
    equity_curve = np.array(aarm.equity_curve)
    returns = np.diff(equity_curve) / equity_curve[:-1]
    annualized_return = np.mean(returns) * 252
    annualized_volatility = np.std(returns) * np.sqrt(252)
    sharpe_ratio = annualized_return / annualized_volatility if annualized_volatility > 0 else 0
    drawdown = (equity_curve.cummax() - equity_curve) / equity_curve.cummax()
    max_drawdown = np.max(drawdown)
    cvar_95 = -np.percentile(returns, 5)

    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Annualized Return: {annualized_return * 100:.2f}%")
    print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")
    print(f"Annualized Volatility: {annualized_volatility * 100:.2f}%")
    print(f"CVaR (95%): {cvar_95:.4f}")
