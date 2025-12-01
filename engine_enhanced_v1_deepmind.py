import pandas as pd
import numpy as np
import riskfolio as rp
from pykalman import KalmanFilter
from sklearn.preprocessing import QuantileTransformer
import nolds
import warnings
import matplotlib.pyplot as plt

# Configuration (ARES-X v2.0 Parameters)
TARGET_VOLATILITY = 0.12  # 12% Annualized Volatility Target
MAX_LEVERAGE = 2.0
TRANSACTION_COST_BPS = 3  # 3 basis points (0.03%) realistic cost assumption
REBALANCE_FREQ = 'W-FRI'  # Weekly rebalancing on Friday
DRAWDOWN_THRESHOLD = 0.10 # 10% drawdown threshold for de-risking

warnings.filterwarnings('ignore')

# ==================================================================
# 1. ADVANCED DATA PROCESSING MODULE
# ==================================================================

class DataProcessor:
    """Handles data cleaning, transformation, and advanced feature engineering."""
    
    def __init__(self, prices):
        self.prices = prices
        # Ensure index is datetime
        if not isinstance(self.prices.index, pd.DatetimeIndex):
            self.prices.index = pd.to_datetime(self.prices.index)
        self.returns = prices.pct_change().dropna()
        
    def apply_kalman_filter(self, series):
        """Insight #1: Dynamic Kalman Filtering for True Price Discovery."""
        try:
            # Dynamic parameters based on observed volatility
            observation_covariance = series.rolling(window=60).std().mean() * 5
            if pd.isna(observation_covariance) or observation_covariance == 0:
                observation_covariance = 1.0
                
            transition_covariance = 0.05

            kf = KalmanFilter(transition_matrices=[1], observation_matrices=[1], initial_state_mean=series.iloc[0],
                              initial_state_covariance=1, observation_covariance=observation_covariance, 
                              transition_covariance=transition_covariance)
            state_means, _ = kf.filter(series.values)
            return pd.Series(state_means.flatten(), index=series.index)
        except Exception as e:
            # Fallback to Exponential Moving Average if Kalman fails
            return series.ewm(span=10, adjust=False).mean()

    def calculate_hurst_exponent(self, series, window=126):
        """Insight #2: Hurst Exponent Regime Filtering."""
        def hurst_fn(x):
            if len(x) < window: return np.nan
            try:
                # Use nolds for robust Hurst exponent calculation
                return nolds.hurst_rs(x)
            except:
                return 0.5 # Default to random walk if calculation fails
        return series.rolling(window=window).apply(hurst_fn)

    def quantile_transform(self, df):
        """Insight #4: Optimal Feature Transformation."""
        # Apply transformation cross-sectionally (per day)
        if df.empty:
            return df
        try:
            # Determine n_quantiles dynamically based on the number of assets
            n_quantiles = min(len(df.columns), 1000)
            if n_quantiles < 2:
                return df.rank(axis=1, pct=True) - 0.5
                
            qt = QuantileTransformer(output_distribution='normal', random_state=42, n_quantiles=n_quantiles)
            transformed = pd.DataFrame(qt.fit_transform(df.T).T, index=df.index, columns=df.columns)
            return transformed
        except Exception as e:
            # Fallback to ranking if QuantileTransformer fails
            return df.rank(axis=1, pct=True) - 0.5

    def process(self):
        print("ARES-X: Starting data processing...")
        # Apply Kalman filter to all price series
        self.k_prices = self.prices.apply(self.apply_kalman_filter)
        self.k_returns = self.k_prices.pct_change().dropna()
        
        # Calculate Hurst exponent
        self.hurst = self.prices.apply(lambda x: self.calculate_hurst_exponent(x))
        print("ARES-X: Data processing complete.")

# ==================================================================
# 2. SIGNAL GENERATION MODULE
# ==================================================================

class SignalGenerator:
    """Generates diversified alpha signals robust to timing lags."""
    
    def __init__(self, data_processor):
        self.data = data_processor

    def signal_residual_momentum(self, lookback=120, skip=5):
        """Insight #8: Residual Momentum (Adaptive)."""
        # Calculate returns over the lookback period, skipping recent days
        returns = self.data.returns.rolling(window=lookback, min_periods=int(lookback*0.8)).apply(lambda x: (1 + x).prod() - 1)
        returns = returns.shift(skip)

        # Simplified residualization: neutralizing against the cross-sectional mean (market proxy)
        market_momentum = returns.mean(axis=1)
        residual_momentum = returns.sub(market_momentum, axis=0)
        
        # Adaptive overlay: emphasize momentum in trending regimes (Hurst > 0.55)
        trending_mask = (self.data.hurst > 0.55).astype(float)
        adaptive_momentum = residual_momentum * trending_mask

        # CRITICAL: Lag by 1 day to prevent look-ahead bias
        return adaptive_momentum.shift(1)

    def signal_advanced_mean_reversion(self, lookback=20):
        """Insight #9: Advanced Mean Reversion (Adaptive)."""
        # Use Kalman filtered prices for cleaner signal
        prices = self.data.k_prices
        mean = prices.rolling(lookback).mean()
        std = prices.rolling(lookback).std()
        # Handle division by zero
        std = std.replace(0, 1e-6)
        z_score = (prices - mean) / std
        
        # Signal is negative Z-score
        reversion_signal = -z_score
        
        # Adaptive overlay: emphasize reversion in reverting regimes (Hurst < 0.45)
        reverting_mask = (self.data.hurst < 0.45).astype(float)
        adaptive_reversion = reversion_signal * reverting_mask

        # CRITICAL: Lag by 1 day
        return adaptive_reversion.shift(1)

    def signal_skewness_preference(self, lookback=60):
        """Insight #10: Cross-Sectional Skewness Preference (CSSP)."""
        skewness = self.data.returns.rolling(window=lookback).skew()
        # Signal is negative skewness (short lottery tickets)
        # CRITICAL: Lag by 1 day
        return (-skewness).shift(1)

    def generate_all_signals(self):
        print("ARES-X: Generating alpha signals...")
        signals = {
            'ResidualMomentum': self.signal_residual_momentum(),
            'MeanReversion': self.signal_advanced_mean_reversion(),
            'SkewnessPreference': self.signal_skewness_preference(),
        }
        # Combine signals into a multi-index dataframe (Date, Symbols)
        # Handling potential multi-level column indices if they exist
        self.all_signals = pd.concat(signals, axis=1)
        # Ensure the structure is (Date x (Strategy, Symbol))
        if isinstance(self.all_signals.columns, pd.MultiIndex):
             self.all_signals = self.all_signals.stack(level=1)
        else:
             self.all_signals.columns.name = 'Strategy'
             self.all_signals = self.all_signals.stack()
             self.all_signals = self.all_signals.unstack(level=1)

        return self.all_signals

# ==================================================================
# 3. PORTFOLIO OPTIMIZATION MODULE
# ==================================================================

class PortfolioConstructor:
    """Combines signals and optimizes portfolio weights using HRP."""
    
    def __init__(self, returns, data_processor):
        self.returns = returns
        self.data_processor = data_processor

    def combine_signals(self, signals_df):
        """Combines alpha signals using robust normalization."""
        # Apply Quantile Transformation (Insight #4) cross-sectionally
        # signals_df structure assumed: Index=Date, Columns=Symbols, Values=Signal Scores
        
        # If input is multi-strategy, we need to handle it. Assuming input is already combined or single strategy for transformation.
        # For simplicity here, we average the strategies first if needed.
        if isinstance(signals_df.columns, pd.MultiIndex):
             # Average across strategies
             combined_raw = signals_df.groupby(level=1, axis=1).mean()
        else:
             combined_raw = signals_df

        normalized_signals = self.data_processor.quantile_transform(combined_raw)
        
        # Ensure dollar neutrality
        combined_alpha = normalized_signals.sub(normalized_signals.mean(axis=1), axis=0)
        return combined_alpha

    def hrp_optimization(self, date, lookback=252):
        """Insight #15: Hierarchical Risk Parity (HRP) Optimization."""
        # Use data up to the specified date for optimization
        historical_returns = self.returns.loc[:date].tail(lookback)
        
        if historical_returns.shape[0] < 50 or historical_returns.isnull().values.any().sum() > historical_returns.size * 0.1:
            # Fallback if data is insufficient
            return self._inverse_volatility_weights(historical_returns)

        try:
            # Initialize HRP portfolio object using riskfolio-lib
            port = rp.HCPortfolio(returns=historical_returns)
            
            # Estimate optimal portfolio weights using HRP with Ledoit-Wolf shrinkage (Insight 16)
            weights = port.optimization(model='HRP', codependence='pearson', covariance='ledoit', 
                                        rm='MV', rf=0, linkage='ward', max_k=10, leaf_order=True)
            return weights.T.iloc[0]
        except Exception as e:
            # Fallback to Inverse Volatility if HRP fails
            return self._inverse_volatility_weights(historical_returns)

    def _inverse_volatility_weights(self, returns):
        """Helper for robust allocation fallback."""
        vols = returns.std()
        inv_vols = 1 / vols.replace(0, 1e-6)
        if inv_vols.sum() == 0 or np.isinf(inv_vols.sum()):
             return pd.Series(1/len(returns.columns), index=returns.columns)
        weights = inv_vols / inv_vols.sum()
        return weights

    def construct_portfolio(self, combined_alpha, hrp_weights):
        """Blends alpha signals with HRP base weights."""
        # Align indices
        aligned_alpha = combined_alpha.reindex(hrp_weights.index).fillna(0)
        
        # Apply alpha signal direction to HRP weights
        # HRP provides the risk structure; alpha dictates the direction (long/short)
        final_weights = hrp_weights * np.sign(aligned_alpha)
        
        # Enhance magnitude based on signal strength (use tanh for bounded scaling)
        # This tilts the portfolio towards stronger signals while respecting the HRP risk structure
        tilt_factor = 1 + np.tanh(abs(aligned_alpha) * 2) # Scaling factor
        final_weights *= tilt_factor

        # Renormalize to maintain Long/Short balance (Dollar Neutral)
        final_weights -= final_weights.mean()
        
        # Normalize gross exposure to 1 (before leverage)
        gross_exposure = final_weights.abs().sum()
        if gross_exposure > 0:
            final_weights /= gross_exposure
            
        return final_weights

# ==================================================================
# 4. BACKTESTING AND EXECUTION MODULE
# ==================================================================

class Backtester:
    """Simulates the strategy with realistic execution and risk management."""
    
    def __init__(self, data_processor, signal_generator, portfolio_constructor):
        self.data = data_processor
        self.signal_gen = signal_generator
        self.constructor = portfolio_constructor
        # Determine rebalance dates based on frequency
        self.rebal_dates = pd.date_range(start=self.data.returns.index.min(), end=self.data.returns.index.max(), freq=REBALANCE_FREQ)

    def run_backtest(self):
        print("ARES-X: Starting backtest simulation...")
        signals = self.signal_gen.generate_all_signals()
        portfolio_returns = []
        weights_history = {}
        
        # Filter rebalance dates to align with available trading days
        valid_rebal_dates = self.rebal_dates[self.rebal_dates.isin(self.data.returns.index)]
        
        for i, date in enumerate(valid_rebal_dates):
            # Ensure sufficient lookback history (e.g., 1 year)
            if self.data.returns.index.get_loc(date) < 252: continue

            # 1. Get signals available at this date (Signals are already lagged T-1 in SignalGenerator)
            current_signals = signals.loc[date]
            if current_signals.isnull().all().all(): continue

            # 2. Combine Alphas
            # Input structure for combine_signals needs (Date x Symbol) DataFrame
            combined_alpha_series = self.constructor.combine_signals(current_signals.to_frame().T)
            combined_alpha = combined_alpha_series.iloc[0]
            
            # 3. Optimize Weights (HRP base)
            # Use data up to the previous day (T-1) for optimization
            current_date_loc = self.data.returns.index.get_loc(date)
            prev_day = self.data.returns.index[current_date_loc - 1]
            hrp_weights = self.constructor.hrp_optimization(prev_day)
            
            # 4. Construct Final Portfolio
            final_weights = self.constructor.construct_portfolio(combined_alpha, hrp_weights)
            weights_history[date] = final_weights
            
            # 5. Execute Trades and Calculate Returns
            # Weights apply from the close of 'date' until the close of the next rebalance date
            if i + 1 < len(valid_rebal_dates):
                next_date = valid_rebal_dates[i+1]
            else:
                next_date = self.data.returns.index[-1]
                
            # Returns realized starting the day AFTER rebalance (T+1)
            period_returns = self.data.returns.loc[date:next_date].iloc[1:] 
            
            daily_ret = period_returns.dot(final_weights)
            
            # 6. Apply Transaction Costs (Insight #22)
            if i > 0 and valid_rebal_dates[i-1] in weights_history:
                prev_weights = weights_history[valid_rebal_dates[i-1]]
                # Align indices before calculating turnover
                aligned_prev_weights = prev_weights.reindex(final_weights.index).fillna(0)
                turnover = (final_weights - aligned_prev_weights).abs().sum()
                cost = turnover * TRANSACTION_COST_BPS / 10000
                
                # Deduct cost from the first day's return of the period
                if not daily_ret.empty:
                    daily_ret.iloc[0] -= cost
            
            portfolio_returns.append(daily_ret)

        self.portfolio_returns = pd.concat(portfolio_returns)
        
        # 7. Apply Dynamic Risk Management
        self.apply_dynamic_risk_scaling()
        
        print("ARES-X: Backtest complete.")
        return self.portfolio_returns

    def apply_dynamic_risk_scaling(self):
        """Combines Volatility Targeting (Insight 17) and Drawdown Control (Insight 18)."""
        # Calculate realized volatility (60-day lookback)
        realized_vol = self.portfolio_returns.rolling(60).std() * np.sqrt(252)
        
        # Calculate base leverage
        leverage = TARGET_VOLATILITY / realized_vol
        # Apply leverage based on yesterday's vol (T-1)
        leverage = leverage.shift(1) 
        
        # Drawdown Control Mechanism
        cumulative_returns = (1 + self.portfolio_returns).cumprod()
        running_max = cumulative_returns.cummax()
        drawdown = (running_max - cumulative_returns) / running_max
        
        # Reduce leverage if drawdown exceeds threshold
        # If drawdown > 10%, reduce exposure by 50%
        drawdown_multiplier = np.where(drawdown.shift(1) > DRAWDOWN_THRESHOLD, 0.5, 1.0)
        leverage *= drawdown_multiplier

        # Cap leverage and fill initial values
        leverage = leverage.clip(upper=MAX_LEVERAGE).fillna(1.0) 
        
        self.portfolio_returns = self.portfolio_returns * leverage

    def calculate_performance_metrics(self):
        """Calculates key performance indicators."""
        returns = self.portfolio_returns
        if returns.empty:
            return {"Net Sharpe Ratio": 0}

        annual_ret = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)
        sharpe_ratio = annual_ret / annual_vol if annual_vol != 0 else 0
        
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.cummax()
        drawdown = (running_max - cumulative_returns) / running_max
        max_drawdown = drawdown.max()
        
        return {
            "Net Sharpe Ratio": sharpe_ratio,
            "Annualized Return": annual_ret,
            "Annualized Volatility": annual_vol,
            "Max Drawdown": max_drawdown,
            "Transaction Cost (BPS)": TRANSACTION_COST_BPS
        }

# ==================================================================
# 5. SIMULATION ENVIRONMENT (Main Execution)
# ==================================================================

if __name__ == '__main__':
    # This section is for demonstration and validation.
    # CRITICAL: Replace the synthetic data generation with your actual US 100 stock price data (2015-2025).
    
    print("ARES-X: Initializing Simulation Environment...")
    
    # Generate synthetic data (for demonstration only)
    START_DATE = '2015-01-01'
    END_DATE = '2025-11-25'
    N_ASSETS = 50 # Reduced number for faster simulation
    N_DAYS = 252 * 10 + 11*25 # Approximate days
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq='B')
    N_DAYS = len(dates)

    # Create prices with drift, noise, and some correlation
    returns = pd.DataFrame(np.random.normal(0.0001, 0.015, (N_DAYS, N_ASSETS)), index=dates)
    market_factor = np.random.normal(0.0002, 0.01, N_DAYS)
    returns = returns.add(market_factor, axis=0)
    
    prices = (1 + returns).cumprod()
    prices.columns = pd.Index([f'Asset_{i}' for i in range(N_ASSETS)], name='Symbols')
    
    # Initialize Modules
    # Ensure required libraries (pykalman, nolds, riskfolio-lib) are installed
    try:
        data_processor = DataProcessor(prices)
        data_processor.process()
        
        signal_generator = SignalGenerator(data_processor)
        portfolio_constructor = PortfolioConstructor(data_processor.returns, data_processor)
        
        # Run Backtest
        backtester = Backtester(data_processor, signal_generator, portfolio_constructor)
        strategy_returns = backtester.run_backtest()
        
        # Calculate Performance
        metrics = backtester.calculate_performance_metrics()
        
        print("\n--- ARES-X v2.0 Performance Metrics (Simulated Data) ---")
        for key, value in metrics.items():
            if key in ["Net Sharpe Ratio"]:
                print(f"{key}: {value:.3f}")
            else:
                if isinstance(value, float):
                    print(f"{key}: {value:.2%}")
                else:
                    print(f"{key}: {value}")
        
        # Plot Equity Curve
        plt.figure(figsize=(12, 6))
        (1 + strategy_returns).cumprod().plot(title="ARES-X v2.0 Equity Curve (Target Sharpe 2.0+)")
        plt.ylabel("Cumulative Returns")
        plt.grid(True)
        plt.show()

    except ImportError as e:
        print(f"\nERROR: Missing required libraries. Please install pykalman, nolds, and riskfolio-lib.")
        print(f"Import Error Details: {e}")
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")
        import traceback
        traceback.print_exc()

# =============================================================================
# Main Execution
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description='ARES-7 Enhanced Engine v1 (DeepMind)')
    parser.add_argument('--price', type=str, default='./data/price_full.csv',
                        help='Path to price CSV file')
    parser.add_argument('--output', type=str, default='./results/engine_enhanced_v1_deepmind.json',
                        help='Output JSON file path')
    
    args = parser.parse_args()
    
    print("="*70)
    print("ARES-7 Enhanced Engine v1 (DeepMind Integration)")
    print("="*70)
    
    # Load data
    print("\nLoading price data...")
    df = pd.read_csv(args.price)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    prices = df.pivot(index='timestamp', columns='symbol', values='close')
    print(f"  Loaded: {prices.shape}")
    
    # Run engine
    print("\nInitializing engine...")
    engine = EnhancedEngine(prices, CONFIG)
    
    print("\nRunning backtest...")
    returns = engine.run_backtest()
    
    # Calculate metrics
    print("\nCalculating performance metrics...")
    metrics = engine.calculate_metrics(returns)
    
    # Save results
    print(f"\nSaving results to {args.output}...")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    output_data = {
        'sharpe': float(metrics['sharpe']),
        'annual_return': float(metrics['annual_return']),
        'annual_volatility': float(metrics['annual_volatility']),
        'max_drawdown': float(metrics['max_drawdown']),
        'daily_returns': [{'date': d.strftime('%Y-%m-%d'), 'ret': float(r)} 
                          for d, r in returns.items()],
        'config': CONFIG
    }
    
    with open(args.output, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print("\n" + "="*70)
    print("Results:")
    print("="*70)
    print(f"  Sharpe Ratio: {metrics['sharpe']:.4f}")
    print(f"  Annual Return: {metrics['annual_return']:.2%}")
    print(f"  Annual Volatility: {metrics['annual_volatility']:.2%}")
    print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
    print("="*70)


if __name__ == '__main__':
    main()
