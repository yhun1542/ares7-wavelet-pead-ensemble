#!/usr/bin/env python3
"""
GPT Backtester v4 - Clean and Simple Framework
NO LOOK-AHEAD BIAS by design

Key principle: weights.shift(1) * returns
- Weights computed on day T are used to trade on day T+1
- Returns on day T+1 are realized from positions entered at T's close
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
import json


class GPTBacktester:
    """
    Clean backtesting framework with proper timing
    
    Usage:
        backtester = GPTBacktester(price_df, fundamentals_df)
        results = backtester.run(compute_signals_func)
    """
    
    def __init__(self, price_df: pd.DataFrame, fundamentals_df: pd.DataFrame = None):
        """
        Initialize backtester
        
        Args:
            price_df: DataFrame with columns [timestamp, symbol, close, ret1]
            fundamentals_df: Optional DataFrame with fundamental data
        """
        self.price_df = price_df.copy()
        self.fundamentals_df = fundamentals_df.copy() if fundamentals_df is not None else None
        
        # Pivot returns for easy access
        self.returns = price_df.pivot(index='timestamp', columns='symbol', values='ret1')
        self.prices = price_df.pivot(index='timestamp', columns='symbol', values='close')
        
        print(f"Backtester initialized:")
        print(f"  Dates: {self.returns.index[0]} to {self.returns.index[-1]}")
        print(f"  Symbols: {len(self.returns.columns)}")
        print(f"  Days: {len(self.returns)}")
    
    def run(self, compute_signals_func, **kwargs) -> Dict:
        """
        Run backtest with proper timing
        
        Args:
            compute_signals_func: Function that computes weights for each day
                Signature: func(date, prices, returns, fundamentals, **kwargs) -> pd.Series
                Returns: Series of weights (sum to 1.0 for long-only, can be negative for L/S)
            **kwargs: Additional arguments passed to compute_signals_func
        
        Returns:
            Dictionary with backtest results
        """
        print("\nRunning backtest...")
        
        # Store weights for each day
        weights_list = []
        dates = self.returns.index
        
        for i, date in enumerate(dates):
            if i % 500 == 0:
                print(f"  Processing {i}/{len(dates)}: {date.date()}")
            
            # Compute signals using data UP TO (and including) current date
            # These weights will be used to trade NEXT day
            weights = compute_signals_func(
                date=date,
                prices=self.prices.loc[:date],
                returns=self.returns.loc[:date],
                fundamentals=self.fundamentals_df,
                **kwargs
            )
            
            # Store weights with date
            if weights is not None:
                weights_list.append({
                    'date': date,
                    'weights': weights
                })
        
        # Convert to DataFrame
        weights_df = pd.DataFrame([
            {'date': w['date'], **w['weights'].to_dict()}
            for w in weights_list
        ]).set_index('date')
        
        # Align with returns
        weights_df = weights_df.reindex(self.returns.index, fill_value=0.0)
        
        # CRITICAL: Shift weights by 1 day to avoid look-ahead bias
        # Weights computed on day T are used for returns on day T+1
        weights_shifted = weights_df.shift(1)
        
        # Calculate portfolio returns
        portfolio_returns = (weights_shifted * self.returns).sum(axis=1)
        
        # Remove NaN from beginning
        portfolio_returns = portfolio_returns.dropna()
        
        print(f"\nBacktest complete: {len(portfolio_returns)} days")
        
        # Calculate statistics
        stats = self._calculate_stats(portfolio_returns)
        
        # Calculate turnover
        turnover = self._calculate_turnover(weights_shifted, self.returns)
        stats['avg_turnover'] = turnover
        
        return {
            'stats': stats,
            'daily_returns': portfolio_returns,
            'weights': weights_shifted
        }
    
    def _calculate_stats(self, returns: pd.Series) -> Dict:
        """Calculate performance statistics"""
        returns = returns.dropna()
        
        if len(returns) == 0:
            return {
                'sharpe': 0.0,
                'annual_return': 0.0,
                'annual_volatility': 0.0,
                'max_drawdown': 0.0
            }
        
        # Annualized metrics
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        annual_return = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)
        
        # Drawdown
        cumret = (1 + returns).cumprod()
        cummax = cumret.expanding().max()
        dd = (cumret - cummax) / cummax
        max_dd = dd.min()
        
        return {
            'sharpe': float(sharpe),
            'annual_return': float(annual_return),
            'annual_volatility': float(annual_vol),
            'max_drawdown': float(max_dd)
        }
    
    def _calculate_turnover(self, weights: pd.DataFrame, returns: pd.DataFrame) -> float:
        """Calculate average daily turnover"""
        # Align weights and returns
        weights = weights.reindex(returns.index).fillna(0)
        returns = returns.reindex(weights.index).fillna(0)
        
        # Calculate position changes
        # Position after returns: w[t] * (1 + r[t])
        positions = weights.copy()
        
        turnover_list = []
        for i in range(1, len(positions)):
            # Previous positions after returns
            prev_pos = positions.iloc[i-1] * (1 + returns.iloc[i])
            prev_pos = prev_pos / prev_pos.abs().sum() if prev_pos.abs().sum() > 0 else prev_pos
            
            # New target positions
            new_pos = positions.iloc[i]
            
            # Turnover = sum of absolute changes
            turnover = (new_pos - prev_pos).abs().sum()
            turnover_list.append(turnover)
        
        return float(np.mean(turnover_list)) if turnover_list else 0.0
    
    def save_results(self, results: Dict, output_path: str):
        """Save results to JSON"""
        output = {
            **results['stats'],
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in results['daily_returns'].items()
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n✅ Results saved to {output_path}")
        print(f"   Sharpe: {results['stats']['sharpe']:.3f}")
        print(f"   Annual Return: {results['stats']['annual_return']:.2%}")
        print(f"   Annual Vol: {results['stats']['annual_volatility']:.2%}")
        print(f"   Max DD: {results['stats']['max_drawdown']:.2%}")
        print(f"   Avg Turnover: {results['stats']['avg_turnover']:.3f}")


def load_data(price_csv: str, fundamentals_csv: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load price and fundamental data"""
    print("Loading data...")
    
    # Load price data
    price_df = pd.read_csv(price_csv)
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])
    price_df = price_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Calculate returns if not present
    if 'ret1' not in price_df.columns:
        price_df['ret1'] = price_df.groupby('symbol')['close'].pct_change()
    
    print(f"  Price data: {len(price_df):,} rows, {price_df['symbol'].nunique()} symbols")
    
    # Load fundamental data if provided
    fundamentals_df = None
    if fundamentals_csv:
        fundamentals_df = pd.read_csv(fundamentals_csv)
        fundamentals_df['report_date'] = pd.to_datetime(fundamentals_df['report_date'])
        print(f"  Fundamental data: {len(fundamentals_df):,} rows")
    
    return price_df, fundamentals_df


if __name__ == '__main__':
    print("GPT Backtester v4 - Framework only")
    print("Import this module and use GPTBacktester class")
