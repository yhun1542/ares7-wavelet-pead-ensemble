#!/usr/bin/env python3
"""
ARES-7 Alpha Engine
====================
Sharpe 2.0+ 달성을 위한 추가 알파 엔진

전략:
1. Sector Relative Strength - 섹터 상대 강도
2. Volatility-Weighted Momentum - 변동성 가중 모멘텀
3. Quality-Momentum Intersection - 품질+모멘텀 교집합

Author: Claude (Anthropic)
Date: 2025-11-25
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Tuple


class SectorRelativeStrengthEngine:
    """
    섹터 상대 강도 전략
    
    각 섹터 내에서 상대적으로 강한/약한 종목 선별
    - 섹터 중립 (각 섹터에서 동일 비중)
    - 섹터 내 상대 모멘텀 활용
    """
    
    def __init__(self,
                 lookback: int = 60,
                 n_per_sector: int = 2,
                 rebal_freq: int = 21):
        self.lookback = lookback
        self.n_per_sector = n_per_sector
        self.rebal_freq = rebal_freq
    
    def load_data(self, 
                  price_path: str, 
                  fund_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """데이터 로드"""
        # Price
        price_df = pd.read_csv(price_path)
        price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
        prices = price_df.pivot(index='timestamp', columns='symbol', values='close')
        returns = prices.pct_change()
        
        # Fundamentals with sector
        fund_df = pd.read_csv(fund_path)
        fund_df = fund_df.drop_duplicates('symbol', keep='last')
        
        sector_map = fund_df.set_index('symbol')['sector'].to_dict()
        
        return prices, returns, sector_map
    
    def calculate_sector_signals(self, 
                                  returns: pd.DataFrame,
                                  sector_map: Dict,
                                  date: pd.Timestamp) -> Dict[str, float]:
        """섹터 상대 강도 시그널 계산"""
        if date not in returns.index:
            return {}
        
        idx = returns.index.get_loc(date)
        if idx < self.lookback:
            return {}
        
        # 최근 lookback 기간 누적 수익률
        recent_returns = returns.iloc[idx-self.lookback:idx]
        cum_ret = (1 + recent_returns).prod() - 1
        
        # 섹터별 상대 강도 계산
        sector_stocks = {}
        for symbol in cum_ret.index:
            if symbol not in sector_map:
                continue
            sector = sector_map[symbol]
            if sector not in sector_stocks:
                sector_stocks[sector] = []
            sector_stocks[sector].append((symbol, cum_ret[symbol]))
        
        positions = {}
        
        for sector, stocks in sector_stocks.items():
            if len(stocks) < self.n_per_sector * 2:
                continue
            
            # 정렬
            stocks.sort(key=lambda x: x[1], reverse=True)
            
            # Long: 상위
            for symbol, _ in stocks[:self.n_per_sector]:
                positions[symbol] = 1.0
            
            # Short: 하위
            for symbol, _ in stocks[-self.n_per_sector:]:
                positions[symbol] = -1.0
        
        # 정규화 (총 노출 = 2.0)
        total_long = sum(w for w in positions.values() if w > 0)
        total_short = sum(abs(w) for w in positions.values() if w < 0)
        
        for sym in positions:
            if positions[sym] > 0:
                positions[sym] = positions[sym] / total_long if total_long > 0 else 0
            else:
                positions[sym] = positions[sym] / total_short if total_short > 0 else 0
        
        return positions
    
    def backtest(self, 
                 price_path: str = './data/price_full.csv',
                 fund_path: str = './data/fundamentals.csv') -> Dict:
        """백테스트"""
        print("=" * 60)
        print("ARES-7 Sector Relative Strength Engine")
        print("=" * 60)
        
        prices, returns, sector_map = self.load_data(price_path, fund_path)
        print(f"  Prices: {prices.shape}")
        print(f"  Sectors: {len(set(sector_map.values()))}")
        
        rebal_dates = prices.index[::self.rebal_freq]
        
        portfolio_returns = []
        current_positions = {}
        next_positions = {}
        
        for i, date in enumerate(prices.index):
            if next_positions:
                current_positions = next_positions.copy()
                next_positions = {}
            
            if date in rebal_dates and i >= self.lookback:
                prev_date = prices.index[i-1]
                next_positions = self.calculate_sector_signals(returns, sector_map, prev_date)
            
            if i == 0:
                portfolio_returns.append(0.0)
                continue
            
            daily_ret = 0.0
            for sym, weight in current_positions.items():
                if sym in returns.columns:
                    stock_ret = returns.loc[date, sym]
                    if not np.isnan(stock_ret):
                        daily_ret += weight * stock_ret
            
            portfolio_returns.append(daily_ret)
        
        # Stats
        ret_series = pd.Series(portfolio_returns, index=prices.index)
        ann_ret = ret_series.mean() * 252
        ann_vol = ret_series.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        
        cumret = (1 + ret_series).cumprod()
        mdd = ((cumret / cumret.expanding().max()) - 1).min()
        
        print(f"\nResults:")
        print(f"  Sharpe: {sharpe:.3f}")
        print(f"  Return: {ann_ret*100:.1f}%")
        print(f"  Vol: {ann_vol*100:.1f}%")
        print(f"  MDD: {mdd*100:.1f}%")
        
        return {
            'sharpe': float(sharpe),
            'annual_return': float(ann_ret),
            'annual_volatility': float(ann_vol),
            'max_drawdown': float(mdd),
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in ret_series.items()
            ]
        }


class VolWeightedMomentumEngine:
    """
    변동성 가중 모멘텀 전략
    
    낮은 변동성 + 높은 모멘텀 종목 선호
    - 변동성으로 정규화된 모멘텀
    - 극단적 변동성 종목 제외
    """
    
    def __init__(self,
                 mom_lookback: int = 60,
                 vol_lookback: int = 60,
                 n_long: int = 15,
                 n_short: int = 15,
                 rebal_freq: int = 21):
        self.mom_lookback = mom_lookback
        self.vol_lookback = vol_lookback
        self.n_long = n_long
        self.n_short = n_short
        self.rebal_freq = rebal_freq
    
    def load_data(self, price_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """데이터 로드"""
        price_df = pd.read_csv(price_path)
        price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
        prices = price_df.pivot(index='timestamp', columns='symbol', values='close')
        returns = prices.pct_change()
        return prices, returns
    
    def calculate_signals(self, 
                           prices: pd.DataFrame,
                           returns: pd.DataFrame,
                           date: pd.Timestamp) -> Dict[str, float]:
        """변동성 가중 모멘텀 시그널"""
        if date not in returns.index:
            return {}
        
        idx = returns.index.get_loc(date)
        if idx < max(self.mom_lookback, self.vol_lookback):
            return {}
        
        # 모멘텀
        momentum = (prices.iloc[idx] / prices.iloc[idx-self.mom_lookback] - 1)
        
        # 변동성
        recent_ret = returns.iloc[idx-self.vol_lookback:idx]
        volatility = recent_ret.std() * np.sqrt(252)
        
        # 변동성 가중 모멘텀 (Risk-adjusted momentum)
        vol_weighted_mom = momentum / (volatility + 1e-8)
        vol_weighted_mom = vol_weighted_mom.dropna()
        
        # 극단 변동성 제외 (10th ~ 90th percentile)
        vol_low = volatility.quantile(0.10)
        vol_high = volatility.quantile(0.90)
        valid_symbols = volatility[(volatility >= vol_low) & (volatility <= vol_high)].index
        vol_weighted_mom = vol_weighted_mom[vol_weighted_mom.index.isin(valid_symbols)]
        
        if len(vol_weighted_mom) < self.n_long + self.n_short:
            return {}
        
        sorted_signals = vol_weighted_mom.sort_values(ascending=False)
        
        positions = {}
        long_weight = 1.0 / self.n_long
        short_weight = -1.0 / self.n_short
        
        for sym in sorted_signals.head(self.n_long).index:
            positions[sym] = long_weight
        
        for sym in sorted_signals.tail(self.n_short).index:
            positions[sym] = short_weight
        
        return positions
    
    def backtest(self, price_path: str = './data/price_full.csv') -> Dict:
        """백테스트"""
        print("=" * 60)
        print("ARES-7 Vol-Weighted Momentum Engine")
        print("=" * 60)
        
        prices, returns = self.load_data(price_path)
        print(f"  Prices: {prices.shape}")
        
        rebal_dates = prices.index[::self.rebal_freq]
        
        portfolio_returns = []
        current_positions = {}
        next_positions = {}
        
        for i, date in enumerate(prices.index):
            if next_positions:
                current_positions = next_positions.copy()
                next_positions = {}
            
            if date in rebal_dates and i >= max(self.mom_lookback, self.vol_lookback):
                prev_date = prices.index[i-1]
                next_positions = self.calculate_signals(prices, returns, prev_date)
            
            if i == 0:
                portfolio_returns.append(0.0)
                continue
            
            daily_ret = 0.0
            for sym, weight in current_positions.items():
                if sym in returns.columns:
                    stock_ret = returns.loc[date, sym]
                    if not np.isnan(stock_ret):
                        daily_ret += weight * stock_ret
            
            portfolio_returns.append(daily_ret)
        
        # Stats
        ret_series = pd.Series(portfolio_returns, index=prices.index)
        ann_ret = ret_series.mean() * 252
        ann_vol = ret_series.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        
        cumret = (1 + ret_series).cumprod()
        mdd = ((cumret / cumret.expanding().max()) - 1).min()
        
        print(f"\nResults:")
        print(f"  Sharpe: {sharpe:.3f}")
        print(f"  Return: {ann_ret*100:.1f}%")
        print(f"  Vol: {ann_vol*100:.1f}%")
        print(f"  MDD: {mdd*100:.1f}%")
        
        return {
            'sharpe': float(sharpe),
            'annual_return': float(ann_ret),
            'annual_volatility': float(ann_vol),
            'max_drawdown': float(mdd),
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in ret_series.items()
            ]
        }


class QualityMomentumEngine:
    """
    품질+모멘텀 교집합 전략
    
    높은 품질(ROE, Margin) + 좋은 모멘텀 종목 선별
    품질과 모멘텀의 교집합 활용
    """
    
    def __init__(self,
                 mom_lookback: int = 60,
                 quality_percentile: float = 0.30,
                 n_long: int = 15,
                 n_short: int = 15,
                 rebal_freq: int = 21):
        self.mom_lookback = mom_lookback
        self.quality_percentile = quality_percentile
        self.n_long = n_long
        self.n_short = n_short
        self.rebal_freq = rebal_freq
    
    def load_data(self, 
                  price_path: str, 
                  fund_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """데이터 로드"""
        price_df = pd.read_csv(price_path)
        price_df['timestamp'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
        prices = price_df.pivot(index='timestamp', columns='symbol', values='close')
        returns = prices.pct_change()
        
        fund_df = pd.read_csv(fund_path)
        fund_df = fund_df.drop_duplicates('symbol', keep='last')
        
        # Quality score: ROE + Gross Margin - Debt/Equity
        quality = {}
        for _, row in fund_df.iterrows():
            symbol = row['symbol']
            roe = row.get('ROE', 0) or 0
            margin = row.get('gross_margin', 0) or 0
            debt = row.get('debt_to_equity', 0) or 0
            
            quality[symbol] = roe + margin - min(debt, 2.0)  # Cap debt penalty
        
        return prices, returns, quality
    
    def calculate_signals(self,
                           prices: pd.DataFrame,
                           returns: pd.DataFrame,
                           quality: Dict,
                           date: pd.Timestamp) -> Dict[str, float]:
        """품질+모멘텀 시그널"""
        if date not in returns.index:
            return {}
        
        idx = returns.index.get_loc(date)
        if idx < self.mom_lookback:
            return {}
        
        # 모멘텀
        momentum = (prices.iloc[idx] / prices.iloc[idx-self.mom_lookback] - 1)
        momentum = momentum.dropna()
        
        # 품질 점수 매핑
        quality_series = pd.Series({sym: quality.get(sym, np.nan) 
                                    for sym in momentum.index})
        quality_series = quality_series.dropna()
        
        # 공통 종목
        common = momentum.index.intersection(quality_series.index)
        if len(common) < self.n_long + self.n_short:
            return {}
        
        momentum = momentum[common]
        quality_series = quality_series[common]
        
        # 상위 품질 종목만 필터링
        quality_threshold = quality_series.quantile(1 - self.quality_percentile)
        high_quality = quality_series[quality_series >= quality_threshold].index
        
        # 품질 필터 적용된 모멘텀
        filtered_mom = momentum[momentum.index.isin(high_quality)]
        
        if len(filtered_mom) < self.n_long:
            return {}
        
        # Long: 상위 모멘텀 (품질 필터 적용)
        sorted_mom = filtered_mom.sort_values(ascending=False)
        
        positions = {}
        long_weight = 1.0 / self.n_long
        short_weight = -1.0 / self.n_short
        
        for sym in sorted_mom.head(self.n_long).index:
            positions[sym] = long_weight
        
        # Short: 전체에서 하위 모멘텀 (품질 무관)
        full_sorted = momentum.sort_values(ascending=True)
        for sym in full_sorted.head(self.n_short).index:
            positions[sym] = short_weight
        
        return positions
    
    def backtest(self, 
                 price_path: str = './data/price_full.csv',
                 fund_path: str = './data/fundamentals.csv') -> Dict:
        """백테스트"""
        print("=" * 60)
        print("ARES-7 Quality-Momentum Engine")
        print("=" * 60)
        
        prices, returns, quality = self.load_data(price_path, fund_path)
        print(f"  Prices: {prices.shape}")
        print(f"  Quality scores: {len(quality)}")
        
        rebal_dates = prices.index[::self.rebal_freq]
        
        portfolio_returns = []
        current_positions = {}
        next_positions = {}
        
        for i, date in enumerate(prices.index):
            if next_positions:
                current_positions = next_positions.copy()
                next_positions = {}
            
            if date in rebal_dates and i >= self.mom_lookback:
                prev_date = prices.index[i-1]
                next_positions = self.calculate_signals(prices, returns, quality, prev_date)
            
            if i == 0:
                portfolio_returns.append(0.0)
                continue
            
            daily_ret = 0.0
            for sym, weight in current_positions.items():
                if sym in returns.columns:
                    stock_ret = returns.loc[date, sym]
                    if not np.isnan(stock_ret):
                        daily_ret += weight * stock_ret
            
            portfolio_returns.append(daily_ret)
        
        # Stats
        ret_series = pd.Series(portfolio_returns, index=prices.index)
        ann_ret = ret_series.mean() * 252
        ann_vol = ret_series.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        
        cumret = (1 + ret_series).cumprod()
        mdd = ((cumret / cumret.expanding().max()) - 1).min()
        
        print(f"\nResults:")
        print(f"  Sharpe: {sharpe:.3f}")
        print(f"  Return: {ann_ret*100:.1f}%")
        print(f"  Vol: {ann_vol*100:.1f}%")
        print(f"  MDD: {mdd*100:.1f}%")
        
        return {
            'sharpe': float(sharpe),
            'annual_return': float(ann_ret),
            'annual_volatility': float(ann_vol),
            'max_drawdown': float(mdd),
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in ret_series.items()
            ]
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ARES-7 Alpha Engines')
    parser.add_argument('--engine', choices=['sector', 'volmom', 'qualmom', 'all'], default='all')
    parser.add_argument('--out_dir', default='./results')
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if args.engine in ['sector', 'all']:
        engine = SectorRelativeStrengthEngine()
        results = engine.backtest()
        with open(out_dir / 'engine_sector_rel_strength.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Saved to {out_dir}/engine_sector_rel_strength.json")
    
    if args.engine in ['volmom', 'all']:
        engine = VolWeightedMomentumEngine()
        results = engine.backtest()
        with open(out_dir / 'engine_vol_weighted_mom.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Saved to {out_dir}/engine_vol_weighted_mom.json")
    
    if args.engine in ['qualmom', 'all']:
        engine = QualityMomentumEngine()
        results = engine.backtest()
        with open(out_dir / 'engine_quality_momentum.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Saved to {out_dir}/engine_quality_momentum.json")


if __name__ == '__main__':
    main()
