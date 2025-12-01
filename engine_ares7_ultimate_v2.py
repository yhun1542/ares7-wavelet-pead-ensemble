#!/usr/bin/env python3
"""
ARES-7 Ultimate Engine v2
=========================
Sharpe 2.0+ 달성을 위한 종합 퀀트 트레이딩 시스템 (수정본)

수정사항:
1. 모멘텀 시그널 방향 수정 (Mean Reversion으로 변경)
2. 포지션 적용 타이밍 수정
3. Volatility Targeting 개선
4. 거래 비용 계산 수정

Author: Claude (Anthropic)
Date: 2025-11-25
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass 
class EngineConfig:
    """엔진 설정"""
    # Strategy parameters
    mom_lookback_fast: int = 5      # 단기 모멘텀
    mom_lookback_mid: int = 20      # 중기 모멘텀
    mom_lookback_slow: int = 60     # 장기 모멘텀
    
    # Position sizing
    n_long: int = 20
    n_short: int = 20
    gross_exposure: float = 1.6     # 160% 총 노출
    
    # Risk management
    vol_window: int = 60
    target_vol: float = 0.12        # 목표 변동성 12%
    max_leverage: float = 2.0
    min_leverage: float = 0.5
    
    # Transaction costs
    spread_bps: float = 5.0
    impact_bps: float = 10.0
    
    # Rebalancing
    rebal_freq: int = 7             # 주간 리밸런싱


class RobustMeanReversionEngine:
    """
    Robust Mean Reversion Engine
    
    단기 과매도/과매수 종목의 평균 회귀 활용
    - 단기(5일) 급락 종목 매수
    - 단기(5일) 급등 종목 매도
    - 중장기(20-60일) 추세 필터로 품질 확보
    """
    
    def __init__(self, config: EngineConfig):
        self.config = config
    
    def calculate_signals(self, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
        """평균 회귀 시그널 계산"""
        # 단기 모멘텀 (역방향 = 평균 회귀)
        short_mom = returns.rolling(self.config.mom_lookback_fast).sum()
        
        # 중기 추세 필터 (순방향)
        mid_trend = returns.rolling(self.config.mom_lookback_mid).sum()
        
        # 장기 추세 필터 (순방향)
        long_trend = returns.rolling(self.config.mom_lookback_slow).sum()
        
        # 변동성 조정
        rolling_vol = returns.rolling(self.config.vol_window).std() * np.sqrt(252)
        
        # Mean Reversion Signal:
        # - 단기 하락 + 중기 상승 추세 → 강력 매수
        # - 단기 상승 + 중기 하락 추세 → 강력 매도
        
        # 단기 역방향 (평균 회귀)
        mr_signal = -short_mom / (rolling_vol + 1e-8)
        
        # 중장기 순방향 필터 적용
        trend_filter = (0.6 * mid_trend + 0.4 * long_trend) / (rolling_vol + 1e-8)
        
        # 추세와 일치하는 평균 회귀만 채택
        # 즉, 하락 추세에서는 매수 시그널 제거, 상승 추세에서는 매도 시그널 제거
        combined_signal = mr_signal.copy()
        
        # 상승 추세에서 단기 하락 → 강력 매수 기회
        # 하락 추세에서 단기 상승 → 강력 매도 기회
        combined_signal = np.where(
            (mr_signal > 0) & (trend_filter > 0),  # 단기 하락 + 중장기 상승
            mr_signal * 1.5,  # 강화
            np.where(
                (mr_signal < 0) & (trend_filter < 0),  # 단기 상승 + 중장기 하락
                mr_signal * 1.5,  # 강화
                mr_signal * 0.5  # 추세와 반대되는 시그널 약화
            )
        )
        
        return pd.DataFrame(combined_signal, index=prices.index, columns=prices.columns)
    
    def select_positions(self, signals: pd.DataFrame, date: pd.Timestamp) -> Dict[str, float]:
        """포지션 선택"""
        if date not in signals.index:
            return {}
        
        signal_row = signals.loc[date].dropna()
        
        if len(signal_row) < self.config.n_long + self.config.n_short:
            return {}
        
        # Sort by signal
        sorted_signals = signal_row.sort_values(ascending=False)
        
        # Long: 상위 (단기 하락 + 중장기 상승)
        long_symbols = sorted_signals.head(self.config.n_long).index.tolist()
        
        # Short: 하위 (단기 상승 + 중장기 하락)
        short_symbols = sorted_signals.tail(self.config.n_short).index.tolist()
        
        positions = {}
        long_weight = (self.config.gross_exposure / 2.0) / self.config.n_long
        short_weight = -(self.config.gross_exposure / 2.0) / self.config.n_short
        
        for sym in long_symbols:
            positions[sym] = long_weight
        
        for sym in short_symbols:
            positions[sym] = short_weight
        
        return positions


class TrendFollowingEngine:
    """
    Trend Following Engine
    
    중장기 추세 추종 전략
    - 20-60일 모멘텀 기반
    - 변동성 조정
    """
    
    def __init__(self, config: EngineConfig):
        self.config = config
    
    def calculate_signals(self, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
        """추세 추종 시그널 계산"""
        # 다중 기간 모멘텀
        mom_20 = prices.pct_change(20)
        mom_40 = prices.pct_change(40)
        mom_60 = prices.pct_change(60)
        
        # 가중 평균
        combined = 0.4 * mom_20 + 0.35 * mom_40 + 0.25 * mom_60
        
        # 변동성 조정
        rolling_vol = returns.rolling(self.config.vol_window).std() * np.sqrt(252)
        vol_adjusted = combined / (rolling_vol + 1e-8)
        
        return vol_adjusted
    
    def select_positions(self, signals: pd.DataFrame, date: pd.Timestamp) -> Dict[str, float]:
        """포지션 선택"""
        if date not in signals.index:
            return {}
        
        signal_row = signals.loc[date].dropna()
        
        if len(signal_row) < self.config.n_long + self.config.n_short:
            return {}
        
        sorted_signals = signal_row.sort_values(ascending=False)
        
        long_symbols = sorted_signals.head(self.config.n_long).index.tolist()
        short_symbols = sorted_signals.tail(self.config.n_short).index.tolist()
        
        positions = {}
        long_weight = (self.config.gross_exposure / 2.0) / self.config.n_long
        short_weight = -(self.config.gross_exposure / 2.0) / self.config.n_short
        
        for sym in long_symbols:
            positions[sym] = long_weight
        
        for sym in short_symbols:
            positions[sym] = short_weight
        
        return positions


class ARES7UltimateV2:
    """
    ARES-7 Ultimate System v2
    
    Mean Reversion + Trend Following 앙상블
    """
    
    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        self.mr_engine = RobustMeanReversionEngine(self.config)
        self.tf_engine = TrendFollowingEngine(self.config)
    
    def load_data(self, data_dir: str = './data') -> Tuple[pd.DataFrame, pd.DataFrame]:
        """데이터 로드"""
        price_path = Path(data_dir) / 'price_full.csv'
        
        df = pd.read_csv(price_path)
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
        df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
        
        prices = df.pivot(index='timestamp', columns='symbol', values='close')
        returns = prices.pct_change()
        
        return prices, returns
    
    def calculate_vol_leverage(self, returns: pd.Series, idx: int) -> float:
        """목표 변동성 기반 레버리지 계산"""
        if idx < self.config.vol_window:
            return 1.0
        
        recent_returns = returns.iloc[max(0, idx-self.config.vol_window):idx]
        realized_vol = recent_returns.std() * np.sqrt(252)
        
        if realized_vol <= 0 or np.isnan(realized_vol):
            return 1.0
        
        leverage = self.config.target_vol / realized_vol
        leverage = np.clip(leverage, self.config.min_leverage, self.config.max_leverage)
        
        return leverage
    
    def blend_positions(self, 
                        mr_positions: Dict[str, float],
                        tf_positions: Dict[str, float],
                        mr_weight: float = 0.6,
                        tf_weight: float = 0.4) -> Dict[str, float]:
        """포지션 블렌딩"""
        all_symbols = set(mr_positions.keys()) | set(tf_positions.keys())
        
        blended = {}
        for sym in all_symbols:
            mr_w = mr_positions.get(sym, 0) * mr_weight
            tf_w = tf_positions.get(sym, 0) * tf_weight
            total_w = mr_w + tf_w
            
            if abs(total_w) > 0.001:  # 작은 포지션 필터링
                blended[sym] = total_w
        
        return blended
    
    def backtest(self, data_dir: str = './data') -> Dict:
        """백테스트 실행"""
        print("=" * 70)
        print("ARES-7 Ultimate Engine v2")
        print("=" * 70)
        
        # Load data
        print("\nLoading data...")
        prices, returns = self.load_data(data_dir)
        print(f"  Prices: {prices.shape}")
        print(f"  Period: {prices.index[0].date()} ~ {prices.index[-1].date()}")
        
        # Calculate signals
        print("\nCalculating signals...")
        mr_signals = self.mr_engine.calculate_signals(prices, returns)
        tf_signals = self.tf_engine.calculate_signals(prices, returns)
        
        # Rebalance dates
        rebal_dates = prices.index[::self.config.rebal_freq]
        print(f"\nBacktesting ({len(rebal_dates)} rebalance dates)...")
        
        # Backtest
        portfolio_returns = []
        current_positions = {}
        next_positions = {}
        
        for i, date in enumerate(prices.index):
            # Apply positions from previous rebalance
            if next_positions:
                current_positions = next_positions.copy()
                next_positions = {}
            
            # Rebalance
            if date in rebal_dates and i > self.config.mom_lookback_slow:
                # Use previous day's signal
                prev_date = prices.index[i-1]
                
                # Get positions from each engine
                mr_pos = self.mr_engine.select_positions(mr_signals, prev_date)
                tf_pos = self.tf_engine.select_positions(tf_signals, prev_date)
                
                # Blend positions
                blended = self.blend_positions(mr_pos, tf_pos)
                
                # Apply volatility targeting
                if len(portfolio_returns) > self.config.vol_window:
                    port_ret_series = pd.Series(portfolio_returns)
                    leverage = self.calculate_vol_leverage(port_ret_series, len(portfolio_returns))
                else:
                    leverage = 1.0
                
                # Scale positions
                next_positions = {sym: w * leverage for sym, w in blended.items()}
                
                if i % 50 == 0:
                    n_long = sum(1 for w in next_positions.values() if w > 0)
                    n_short = sum(1 for w in next_positions.values() if w < 0)
                    total_exp = sum(abs(w) for w in next_positions.values())
                    print(f"  {date.date()}: Long={n_long}, Short={n_short}, "
                          f"Leverage={leverage:.2f}, Exposure={total_exp:.2f}")
            
            # Calculate daily return
            if i == 0:
                portfolio_returns.append(0.0)
                continue
            
            daily_ret = 0.0
            for sym, weight in current_positions.items():
                if sym in returns.columns:
                    stock_ret = returns.loc[date, sym]
                    if not np.isnan(stock_ret):
                        daily_ret += weight * stock_ret
            
            # Transaction costs on rebalance days
            if date in rebal_dates and current_positions and next_positions:
                turnover = sum(
                    abs(next_positions.get(s, 0) - current_positions.get(s, 0))
                    for s in set(current_positions.keys()) | set(next_positions.keys())
                )
                cost = turnover * (self.config.spread_bps + self.config.impact_bps) / 10000
                daily_ret -= cost
            
            portfolio_returns.append(daily_ret)
        
        # Performance metrics
        returns_series = pd.Series(portfolio_returns, index=prices.index)
        
        annual_return = returns_series.mean() * 252
        annual_volatility = returns_series.std() * np.sqrt(252)
        sharpe = annual_return / annual_volatility if annual_volatility > 0 else 0
        
        # Max drawdown
        cumulative = (1 + returns_series).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Calmar ratio
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Sortino ratio
        downside_returns = returns_series[returns_series < 0]
        downside_std = downside_returns.std() * np.sqrt(252)
        sortino = annual_return / downside_std if downside_std > 0 else 0
        
        # Win rate
        win_rate = (returns_series > 0).mean()
        
        results = {
            'sharpe': float(sharpe),
            'annual_return': float(annual_return),
            'annual_volatility': float(annual_volatility),
            'max_drawdown': float(max_drawdown),
            'calmar': float(calmar),
            'sortino': float(sortino),
            'win_rate': float(win_rate),
            'total_return': float(cumulative.iloc[-1] - 1),
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in returns_series.items()
            ],
            'config': {
                'mr_lookback': self.config.mom_lookback_fast,
                'tf_lookback': self.config.mom_lookback_slow,
                'rebal_freq': self.config.rebal_freq,
                'target_vol': self.config.target_vol,
                'gross_exposure': self.config.gross_exposure
            }
        }
        
        # Print results
        print("\n" + "=" * 70)
        print("Results:")
        print("=" * 70)
        print(f"  Sharpe Ratio:      {sharpe:.3f}")
        print(f"  Annual Return:     {annual_return*100:.2f}%")
        print(f"  Annual Volatility: {annual_volatility*100:.2f}%")
        print(f"  Max Drawdown:      {max_drawdown*100:.2f}%")
        print(f"  Calmar Ratio:      {calmar:.3f}")
        print(f"  Sortino Ratio:     {sortino:.3f}")
        print(f"  Win Rate:          {win_rate*100:.1f}%")
        print(f"  Total Return:      {(cumulative.iloc[-1]-1)*100:.1f}%")
        print("=" * 70)
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ARES-7 Ultimate Engine v2')
    parser.add_argument('--data_dir', default='./data')
    parser.add_argument('--rebal_freq', type=int, default=7)
    parser.add_argument('--target_vol', type=float, default=0.12)
    parser.add_argument('--out', default='./results/ares7_ultimate_v2_results.json')
    args = parser.parse_args()
    
    config = EngineConfig(
        rebal_freq=args.rebal_freq,
        target_vol=args.target_vol
    )
    
    system = ARES7UltimateV2(config)
    results = system.backtest(args.data_dir)
    
    # Save results
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")


if __name__ == '__main__':
    main()
