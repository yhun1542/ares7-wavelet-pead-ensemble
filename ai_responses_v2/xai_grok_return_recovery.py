import numpy as np
import pandas as pd

class EnhancedStrategy:
    def __init__(self, initial_capital=100000, target_volatility=0.1, mdd_threshold=-0.1):
        self.initial_capital = initial_capital
        self.target_volatility = target_volatility
        self.mdd_threshold = mdd_threshold
        self.equity_curve = [initial_capital]
        self.position_size = 1.0
        self.regime = 'normal'
        self.leverage = 1.0

    def run_strategy(self, returns, short_ma=50, long_ma=200):
        """
        Run the enhanced strategy with asymmetric position sizing, trend-following overlay,
        and dynamic leverage adjustment.
        
        Args:
        returns (pd.Series): Daily returns of the strategy
        short_ma (int): Short-term moving average window
        long_ma (int): Long-term moving average window
        
        Returns:
        pd.DataFrame: Results including equity curve, position size, regime, and leverage
        """
        results = pd.DataFrame(index=returns.index, columns=['equity', 'position_size', 'regime', 'leverage'])
        
        for i in range(len(returns)):
            if i == 0:
                results.iloc[i] = [self.initial_capital, self.position_size, self.regime, self.leverage]
                continue
            
            # Calculate daily return
            daily_return = returns.iloc[i]
            
            # Calculate MDD
            mdd = self.calculate_mdd(results['equity'].iloc[:i+1])
            
            # Asymmetric Position Sizing
            if mdd < self.mdd_threshold:
                self.position_size = 1.0  # Maintain full exposure on upside
            else:
                self.position_size = 0.5  # Reduce exposure on downside
            
            # Trend-Following Overlay
            short_ma_value = results['equity'].iloc[:i+1].rolling(window=short_ma).mean().iloc[-1]
            long_ma_value = results['equity'].iloc[:i+1].rolling(window=long_ma).mean().iloc[-1]
            
            if short_ma_value > long_ma_value:
                self.regime = 'bull'
            else:
                self.regime = 'bear'
            
            # Dynamic Leverage Adjustment
            recent_volatility = returns.iloc[max(0, i-20):i+1].std() * np.sqrt(252)
            if self.regime == 'bull' and recent_volatility < self.target_volatility:
                self.leverage = min(2.0, self.target_volatility / recent_volatility)  # Up to 2x leverage
            else:
                self.leverage = 1.0
            
            # Calculate new equity
            new_equity = results['equity'].iloc[i-1] * (1 + daily_return * self.position_size * self.leverage)
            
            results.iloc[i] = [new_equity, self.position_size, self.regime, self.leverage]
        
        return results

    def calculate_mdd(self, equity_curve):
        """
        Calculate Maximum Drawdown (MDD) from an equity curve.
        
        Args:
        equity_curve (pd.Series): Equity curve
        
        Returns:
        float: Maximum Drawdown
        """
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        return drawdown.min()

    def calculate_performance(self, results):
        """
        Calculate performance metrics from strategy results.
        
        Args:
        results (pd.DataFrame): Strategy results
        
        Returns:
        dict: Performance metrics
        """
        equity = results['equity']
        returns = equity.pct_change().dropna()
        
        annualized_return = (equity.iloc[-1] / equity.iloc[0]) ** (252/len(returns)) - 1
        annualized_volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = annualized_return / annualized_volatility
        mdd = self.calculate_mdd(equity)
        cvar = returns.quantile(0.05)
        
        return {
            'Annualized Return': annualized_return,
            'Annualized Volatility': annualized_volatility,
            'Sharpe Ratio': sharpe_ratio,
            'MDD': mdd,
            'CVaR (95%)': cvar
        }

# Example usage
if __name__ == "__main__":
    # Generate sample returns (replace with actual strategy returns)
    np.random.seed(42)
    sample_returns = pd.Series(np.random.normal(0.001, 0.02, 252))
    
    strategy = EnhancedStrategy()
    results = strategy.run_strategy(sample_returns)
    performance = strategy.calculate_performance(results)
    
    print("Performance Metrics:")
    for key, value in performance.items():
        print(f"{key}: {value:.4f}")
    
    print("\nStrategy Results:")
    print(results.tail())