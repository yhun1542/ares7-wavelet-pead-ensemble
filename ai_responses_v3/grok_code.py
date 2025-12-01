import numpy as np
import pandas as pd

class EnhancedAARM:
    def __init__(self, initial_capital, risk_free_rate=0.02, transaction_cost=0.001):
        self.capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.transaction_cost = transaction_cost
        self.position = 0
        self.stop_loss = 0
        self.leverage = 1.0

    def calculate_kelly_leverage(self, win_prob, win_ratio, loss_ratio):
        # Modified Kelly Criterion with volatility adjustment
        volatility_factor = self.get_volatility_factor()
        kelly_fraction = (win_prob * win_ratio - (1 - win_prob) * loss_ratio) / loss_ratio
        return max(0, min(2.0, kelly_fraction * volatility_factor))

    def get_volatility_factor(self):
        # Placeholder for volatility calculation
        # In practice, this would use historical data
        return 1 / (1 + np.random.normal(0, 0.1))  # Example: inverse of volatility

    def update_stop_loss(self, current_price, atr):
        # Dynamic stop-loss based on ATR (Average True Range)
        self.stop_loss = current_price * (1 - 2 * atr)

    def execute_trade(self, signal, current_price, atr):
        # Calculate potential new position
        win_prob = 0.6  # Example win probability
        win_ratio = 1.5  # Example win/loss ratio
        loss_ratio = 1.0  # Example loss ratio

        self.leverage = self.calculate_kelly_leverage(win_prob, win_ratio, loss_ratio)
        new_position = self.capital * self.leverage * signal

        # Check if stop-loss is hit
        if self.position > 0 and current_price <= self.stop_loss:
            new_position = 0  # Close position if stop-loss is hit

        # Calculate transaction cost
        transaction_cost = abs(new_position - self.position) * self.transaction_cost

        # Update position and capital
        self.position = new_position
        self.capital -= transaction_cost

        # Update stop-loss
        self.update_stop_loss(current_price, atr)

        return self.position, self.capital

    def run_strategy(self, data):
        results = []
        for _, row in data.iterrows():
            signal = row['signal']
            current_price = row['price']
            atr = row['atr']  # Assuming ATR is provided in the data

            position, capital = self.execute_trade(signal, current_price, atr)
            returns = (position * current_price / self.capital) - 1 if self.capital > 0 else 0

            results.append({
                'date': row['date'],
                'position': position,
                'capital': capital,
                'returns': returns
            })

        return pd.DataFrame(results)

# Example usage
data = pd.DataFrame({
    'date': pd.date_range(start='2020-01-01', periods=1000),
    'signal': np.random.choice([-1, 0, 1], 1000),
    'price': np.cumprod(1 + np.random.normal(0.0005, 0.01, 1000)),
    'atr': np.random.uniform(0.01, 0.03, 1000)
})

strategy = EnhancedAARM(initial_capital=1000000)
results = strategy.run_strategy(data)

# Calculate performance metrics
daily_returns = results['returns']
sharpe_ratio = np.sqrt(252) * daily_returns.mean() / daily_returns.std()
annualized_return = (1 + daily_returns).prod() ** (252/len(daily_returns)) - 1
cumulative_returns = (1 + daily_returns).cumprod()
max_drawdown = ((cumulative_returns / cumulative_returns.cummax()) - 1).min()

print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
print(f"Annualized Return: {annualized_return:.2f}")
print(f"Maximum Drawdown: {max_drawdown:.2f}")