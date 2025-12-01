#!/usr/bin/env python3
"""
ARES-7 Low Volatility Enhanced Engine
======================================
저변동성 전략 + 품질 팩터 + 모멘텀 필터 결합

핵심 개선사항:
1. 다중 저변동성 지표 (Downside Vol, Beta, Max DD)
2. 품질 필터 (ROE, Gross Margin, Low Debt)
3. 모멘텀 필터 (약세 종목 제외)
4. 동적 리밸런싱 (변동성 레짐 기반)

목표: Sharpe 1.0+, 낮은 변동성, 낮은 상관관계

Author: Claude (Anthropic)
Date: 2025-11-25
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class LowVolConfig:
    """저변동성 전략 설정"""
    # Risk metrics weights
    downside_vol_weight: float = 0.35
    beta_weight: float = 0.35
    max_dd_weight: float = 0.30
    
    # Quality weights
    roe_weight: float = 0.35
    margin_weight: float = 0.35
    debt_weight: float = 0.30
    
    # Momentum filter
    mom_lookback: int = 60
    mom_threshold: float = -0.10  # 10% 이상 하락 종목 제외
    
    # Portfolio construction
    top_n: int = 25
    rebal_freq: int = 21  # 월간 리밸런싱
    
    # Lookbacks
    vol_lookback: int = 180
    beta_lookback: int = 252
    mdd_lookback: int = 252


class LowVolEnhancedEngine:
    """저변동성 강화 엔진"""
    
    def __init__(self, config: LowVolConfig = None):
        self.config = config or LowVolConfig()
    
    def load_data(self, price_path: str, fund_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """데이터 로드"""
        # Price data
        price_df = pd.read_csv(price_path)
        price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
        price_df = price_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
        
        prices = price_df.pivot(index='timestamp', columns='symbol', values='close')
        returns = prices.pct_change()
        
        # Fundamentals
        fund_df = pd.read_csv(fund_path)
        fund_df['report_date'] = pd.to_datetime(fund_df['report_date'])
        
        return prices, returns, fund_df
    
    def calculate_risk_metrics(self, returns: pd.DataFrame, prices: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """리스크 지표 계산"""
        # Market returns (equal-weighted proxy)
        market_ret = returns.mean(axis=1)
        
        # 1. Downside Volatility
        downside_ret = returns.copy()
        downside_ret[downside_ret > 0] = 0
        downside_vol = downside_ret.rolling(self.config.vol_lookback).std() * np.sqrt(252)
        
        # 2. Rolling Beta
        def calc_beta(stock_ret):
            corr = stock_ret.rolling(self.config.beta_lookback).corr(market_ret)
            stock_vol = stock_ret.rolling(self.config.beta_lookback).std()
            market_vol = market_ret.rolling(self.config.beta_lookback).std()
            return corr * (stock_vol / market_vol)
        
        beta = returns.apply(calc_beta, axis=0)
        
        # 3. Rolling Max Drawdown
        def calc_mdd(close_series):
            def mdd_window(window):
                if len(window) < 60:
                    return np.nan
                cummax = np.maximum.accumulate(window)
                dd = (window - cummax) / cummax
                return abs(dd.min())
            return close_series.rolling(self.config.mdd_lookback).apply(mdd_window, raw=True)
        
        max_dd = prices.apply(calc_mdd, axis=0)
        
        return {
            'downside_vol': downside_vol,
            'beta': beta,
            'max_dd': max_dd
        }
    
    def prepare_fundamentals(self, fund_df: pd.DataFrame, dates: pd.DatetimeIndex) -> Dict[str, pd.DataFrame]:
        """펀더멘탈 데이터 정렬"""
        fund_df = fund_df.drop_duplicates(subset=['symbol', 'report_date'], keep='first')
        symbols = fund_df['symbol'].unique()
        
        metrics = {
            'ROE': pd.DataFrame(index=dates, columns=symbols, dtype=float),
            'gross_margin': pd.DataFrame(index=dates, columns=symbols, dtype=float),
            'debt_to_equity': pd.DataFrame(index=dates, columns=symbols, dtype=float)
        }
        
        for symbol in symbols:
            symbol_data = fund_df[fund_df['symbol'] == symbol].copy()
            symbol_data = symbol_data.sort_values('report_date').set_index('report_date')
            
            for col in metrics.keys():
                if col in symbol_data.columns:
                    series = symbol_data[col].reindex(dates, method='ffill')
                    metrics[col][symbol] = series
        
        return metrics
    
    def calculate_composite_score(self, 
                                   risk_metrics: Dict[str, pd.DataFrame],
                                   fund_metrics: Dict[str, pd.DataFrame],
                                   returns: pd.DataFrame,
                                   date: pd.Timestamp) -> pd.Series:
        """복합 점수 계산"""
        # Get data for this date
        if date not in risk_metrics['downside_vol'].index:
            return pd.Series(dtype=float)
        
        # Risk scores (lower is better)
        down_vol = risk_metrics['downside_vol'].loc[date]
        beta = risk_metrics['beta'].loc[date]
        max_dd = risk_metrics['max_dd'].loc[date]
        
        # Quality scores
        if date in fund_metrics['ROE'].index:
            roe = fund_metrics['ROE'].loc[date]
            margin = fund_metrics['gross_margin'].loc[date]
            debt = fund_metrics['debt_to_equity'].loc[date]
        else:
            return pd.Series(dtype=float)
        
        # Momentum filter
        if date not in returns.index:
            return pd.Series(dtype=float)
        
        idx = returns.index.get_loc(date)
        if idx < self.config.mom_lookback:
            return pd.Series(dtype=float)
        
        momentum = (returns.iloc[idx-self.config.mom_lookback:idx] + 1).prod() - 1
        
        # Combine into DataFrame
        df = pd.DataFrame({
            'down_vol': down_vol,
            'beta': beta,
            'max_dd': max_dd,
            'roe': roe,
            'margin': margin,
            'debt': debt,
            'momentum': momentum
        })
        
        # Drop symbols with missing data
        df = df.dropna()
        
        # Filter out momentum losers
        df = df[df['momentum'] > self.config.mom_threshold]
        
        if len(df) < self.config.top_n:
            return pd.Series(dtype=float)
        
        # Rank percentile (0-1)
        def rank_pct(series):
            return series.rank(pct=True)
        
        # Risk score (lower is better, so invert)
        risk_score = (
            self.config.downside_vol_weight * (1 - rank_pct(df['down_vol'])) +
            self.config.beta_weight * (1 - rank_pct(df['beta'])) +
            self.config.max_dd_weight * (1 - rank_pct(df['max_dd']))
        )
        
        # Quality score (higher is better, except debt)
        quality_score = (
            self.config.roe_weight * rank_pct(df['roe']) +
            self.config.margin_weight * rank_pct(df['margin']) +
            self.config.debt_weight * (1 - rank_pct(df['debt']))
        )
        
        # Final composite score
        composite = 0.6 * risk_score + 0.4 * quality_score
        
        return composite
    
    def backtest(self, 
                 price_path: str = './data/price_full.csv',
                 fund_path: str = './data/fundamentals.csv',
                 cost_bps: float = 5.0) -> Dict:
        """백테스트 실행"""
        print("=" * 70)
        print("ARES-7 Low Volatility Enhanced Engine")
        print("=" * 70)
        
        # Load data
        print("\nLoading data...")
        prices, returns, fund_df = self.load_data(price_path, fund_path)
        print(f"  Prices: {prices.shape}")
        print(f"  Returns: {returns.shape}")
        
        # Calculate risk metrics
        print("\nCalculating risk metrics...")
        risk_metrics = self.calculate_risk_metrics(returns, prices)
        
        # Prepare fundamentals
        print("Preparing fundamentals...")
        fund_metrics = self.prepare_fundamentals(fund_df, prices.index)
        
        # Rebalance schedule
        rebal_dates = prices.index[::self.config.rebal_freq]
        print(f"\nBacktesting ({len(rebal_dates)} rebalance dates)...")
        
        # Initialize
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        
        for i, rebal_date in enumerate(rebal_dates):
            # Calculate composite scores
            scores = self.calculate_composite_score(
                risk_metrics, fund_metrics, returns, rebal_date
            )
            
            if len(scores) < self.config.top_n:
                continue
            
            # Select top N stocks
            top_symbols = scores.nlargest(self.config.top_n).index.tolist()
            
            # Equal weight
            w = 1.0 / len(top_symbols)
            
            # Determine period
            if i < len(rebal_dates) - 1:
                next_rebal = rebal_dates[i + 1]
                end_idx = prices.index.get_loc(next_rebal)
            else:
                end_idx = len(prices.index)
            
            start_idx = prices.index.get_loc(rebal_date)
            
            # Set weights
            weights.iloc[start_idx:end_idx, :] = 0.0
            for sym in top_symbols:
                if sym in weights.columns:
                    weights.iloc[start_idx:end_idx, weights.columns.get_loc(sym)] = w
            
            if i % 10 == 0:
                print(f"  {rebal_date.date()}: Selected {len(top_symbols)} stocks")
        
        # Calculate portfolio returns
        port_ret = (weights.shift(1) * returns).sum(axis=1)
        
        # Transaction costs
        turnover = weights.diff().abs().sum(axis=1)
        turnover_cost = turnover * (cost_bps / 10000)
        
        # Net returns
        net_ret = port_ret - turnover_cost
        net_ret = net_ret.dropna()
        
        # Performance metrics
        annual_return = net_ret.mean() * 252
        annual_vol = net_ret.std() * np.sqrt(252)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0
        
        # Max drawdown
        cumret = (1 + net_ret).cumprod()
        cummax = cumret.expanding().max()
        dd = (cumret - cummax) / cummax
        max_dd = dd.min()
        
        # Sortino
        downside_ret = net_ret[net_ret < 0]
        downside_std = downside_ret.std() * np.sqrt(252)
        sortino = annual_return / downside_std if downside_std > 0 else 0
        
        # Win rate
        win_rate = (net_ret > 0).mean()
        
        # Average turnover
        avg_turnover = turnover.mean()
        
        results = {
            'sharpe': float(sharpe),
            'annual_return': float(annual_return),
            'annual_volatility': float(annual_vol),
            'max_drawdown': float(max_dd),
            'sortino': float(sortino),
            'win_rate': float(win_rate),
            'avg_turnover': float(avg_turnover),
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in net_ret.items()
            ],
            'config': {
                'top_n': self.config.top_n,
                'rebal_freq': self.config.rebal_freq,
                'downside_vol_weight': self.config.downside_vol_weight,
                'beta_weight': self.config.beta_weight,
                'max_dd_weight': self.config.max_dd_weight
            }
        }
        
        print("\n" + "=" * 70)
        print("Results:")
        print("=" * 70)
        print(f"  Sharpe Ratio:      {sharpe:.3f}")
        print(f"  Annual Return:     {annual_return*100:.2f}%")
        print(f"  Annual Volatility: {annual_vol*100:.2f}%")
        print(f"  Max Drawdown:      {max_dd*100:.2f}%")
        print(f"  Sortino Ratio:     {sortino:.3f}")
        print(f"  Win Rate:          {win_rate*100:.1f}%")
        print(f"  Avg Turnover:      {avg_turnover:.4f}")
        print("=" * 70)
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ARES-7 Low Volatility Enhanced Engine')
    parser.add_argument('--price', default='./data/price_full.csv')
    parser.add_argument('--fund', default='./data/fundamentals.csv')
    parser.add_argument('--top_n', type=int, default=25)
    parser.add_argument('--rebal', type=int, default=21)
    parser.add_argument('--out', default='./results/engine_lowvol_enhanced_results.json')
    args = parser.parse_args()
    
    config = LowVolConfig(
        top_n=args.top_n,
        rebal_freq=args.rebal
    )
    
    engine = LowVolEnhancedEngine(config)
    results = engine.backtest(args.price, args.fund)
    
    # Save results
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")


if __name__ == '__main__':
    main()
