#!/usr/bin/env python3
"""
ARES-7 Ultimate Engine
======================
Sharpe 2.0+ 달성을 위한 종합 퀀트 트레이딩 시스템

핵심 개선사항:
1. Volatility Targeting (목표 10%)
2. Transaction Cost Modeling (현실적 비용)
3. Robust Multi-Period Momentum (20-60일)
4. Cross-Asset Signals (SPY-TLT)
5. VIX Regime Switching
6. Adaptive Ensemble Weighting
7. Correlation-Based Risk Management

Author: Claude (Anthropic)
Date: 2025-11-25
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')


class MarketRegime(Enum):
    """시장 레짐 분류"""
    LOW_VOL = "low_vol"      # VIX < 15
    NORMAL = "normal"        # 15 <= VIX < 25
    HIGH_VOL = "high_vol"    # VIX >= 25
    CRISIS = "crisis"        # VIX >= 35


@dataclass
class TradeConfig:
    """거래 설정"""
    target_volatility: float = 0.10      # 목표 변동성 10%
    spread_cost_bps: float = 5.0         # 스프레드 비용 (bps)
    market_impact_coef: float = 10.0     # 시장 충격 계수
    max_position_size: float = 0.10      # 개별 종목 최대 비중 10%
    max_leverage: float = 2.0            # 최대 레버리지
    min_trade_threshold: float = 0.01    # 최소 거래 임계값 (1%)
    vol_lookback: int = 60               # 변동성 계산 기간


class DataLoader:
    """데이터 로더"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
    
    def load_prices(self) -> pd.DataFrame:
        """가격 데이터 로드"""
        df = pd.read_csv(self.data_dir / "price_full.csv")
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
        df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
        return df.pivot(index='timestamp', columns='symbol', values='close')
    
    def load_fundamentals(self) -> pd.DataFrame:
        """펀더멘탈 데이터 로드"""
        df = pd.read_csv(self.data_dir / "fundamentals.csv")
        df['report_date'] = pd.to_datetime(df['report_date'])
        return df
    
    def load_vix(self) -> pd.DataFrame:
        """VIX 데이터 로드"""
        try:
            df = pd.read_csv(self.data_dir / "vix_futures.csv")
            df['date'] = pd.to_datetime(df['date']).dt.normalize()
            df = df.set_index('date')
            return df
        except:
            return None
    
    def load_spy_tlt(self) -> pd.DataFrame:
        """SPY-TLT 데이터 로드"""
        try:
            df = pd.read_csv(self.data_dir / "spy_tlt_price.csv")
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
            return df.pivot(index='timestamp', columns='symbol', values='close')
        except:
            return None


class RobustMomentumEngine:
    """
    Robust Multi-Period Momentum Engine
    
    다중 기간 모멘텀 조합으로 안정적인 시그널 생성
    - 20일 (단기 트렌드)
    - 40일 (중기 트렌드)  
    - 60일 (장기 트렌드)
    
    변동성 조정으로 리스크 당 수익률 극대화
    """
    
    def __init__(self, 
                 lookbacks: List[int] = [20, 40, 60],
                 weights: List[float] = [0.3, 0.4, 0.3],
                 vol_window: int = 20,
                 n_long: int = 15,
                 n_short: int = 15,
                 gross_exposure: float = 1.5):
        self.lookbacks = lookbacks
        self.weights = weights
        self.vol_window = vol_window
        self.n_long = n_long
        self.n_short = n_short
        self.gross_exposure = gross_exposure
    
    def calculate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """다중 기간 모멘텀 시그널 계산"""
        returns = prices.pct_change()
        
        # 각 기간별 모멘텀 계산
        mom_signals = []
        for lb in self.lookbacks:
            # 가격 기반 모멘텀 (not return-based for stability)
            mom = (prices / prices.shift(lb) - 1)
            mom_signals.append(mom)
        
        # 가중 평균
        combined = sum(w * m for w, m in zip(self.weights, mom_signals))
        
        # 변동성 조정 (vol-adjusted momentum)
        rolling_vol = returns.rolling(self.vol_window).std() * np.sqrt(252)
        vol_adjusted = combined / (rolling_vol + 1e-8)
        
        return vol_adjusted
    
    def generate_positions(self, signals: pd.Series, date: pd.Timestamp) -> Dict[str, float]:
        """시그널 기반 포지션 생성"""
        if date not in signals.index:
            return {}
        
        signal_row = signals.loc[date].dropna()
        
        if len(signal_row) < self.n_long + self.n_short:
            return {}
        
        sorted_signals = signal_row.sort_values(ascending=False)
        
        # Long: 상위 n_long
        long_symbols = sorted_signals.head(self.n_long).index.tolist()
        # Short: 하위 n_short
        short_symbols = sorted_signals.tail(self.n_short).index.tolist()
        
        positions = {}
        long_weight = (self.gross_exposure / 2.0) / self.n_long
        short_weight = -(self.gross_exposure / 2.0) / self.n_short
        
        for sym in long_symbols:
            positions[sym] = long_weight
        for sym in short_symbols:
            positions[sym] = short_weight
        
        return positions


class CrossAssetEngine:
    """
    Cross-Asset Signal Engine
    
    SPY-TLT 상관관계 기반 시그널
    - 채권-주식 상관관계 변화 감지
    - Risk-on/Risk-off 레짐 판단
    """
    
    def __init__(self, 
                 corr_window: int = 60,
                 momentum_window: int = 20):
        self.corr_window = corr_window
        self.momentum_window = momentum_window
    
    def calculate_regime_signal(self, spy_tlt: pd.DataFrame) -> pd.Series:
        """
        SPY-TLT 상관관계 기반 레짐 시그널
        
        양의 상관관계 → Risk-off (방어적)
        음의 상관관계 → Risk-on (공격적)
        """
        if spy_tlt is None or 'SPY' not in spy_tlt.columns or 'TLT' not in spy_tlt.columns:
            return None
        
        spy_ret = spy_tlt['SPY'].pct_change()
        tlt_ret = spy_tlt['TLT'].pct_change()
        
        # Rolling correlation
        rolling_corr = spy_ret.rolling(self.corr_window).corr(tlt_ret)
        
        # Momentum signal for SPY
        spy_mom = spy_tlt['SPY'].pct_change(self.momentum_window)
        
        # Combined signal: 낮은 상관관계 + 양의 SPY 모멘텀 → Risk-on
        signal = -rolling_corr * 0.5 + spy_mom * 0.5
        
        return signal
    
    def get_allocation_adjustment(self, signal: pd.Series, date: pd.Timestamp) -> float:
        """
        레짐 시그널 기반 할당 조정
        
        Returns: 1.0 (기본), 0.5 (방어적), 1.5 (공격적)
        """
        if signal is None or date not in signal.index:
            return 1.0
        
        sig_val = signal.loc[date]
        if np.isnan(sig_val):
            return 1.0
        
        # Signal을 0.5 ~ 1.5 범위로 매핑
        adjustment = 1.0 + np.clip(sig_val, -0.5, 0.5)
        
        return adjustment


class VIXRegimeEngine:
    """
    VIX Regime Switching Engine
    
    VIX 레벨 기반 시장 레짐 판단
    - Low Vol (VIX < 15): 모멘텀 전략 강화
    - Normal (15-25): 균형 포트폴리오
    - High Vol (VIX >= 25): 저변동성 전략 강화
    - Crisis (VIX >= 35): 현금 비중 확대
    """
    
    def __init__(self, 
                 low_vol_threshold: float = 15,
                 high_vol_threshold: float = 25,
                 crisis_threshold: float = 35):
        self.low_vol_threshold = low_vol_threshold
        self.high_vol_threshold = high_vol_threshold
        self.crisis_threshold = crisis_threshold
    
    def get_regime(self, vix_data: pd.DataFrame, date: pd.Timestamp) -> MarketRegime:
        """현재 시장 레짐 판단"""
        if vix_data is None or date not in vix_data.index:
            return MarketRegime.NORMAL
        
        vix_level = vix_data.loc[date, 'VIX']
        
        if np.isnan(vix_level):
            return MarketRegime.NORMAL
        
        if vix_level >= self.crisis_threshold:
            return MarketRegime.CRISIS
        elif vix_level >= self.high_vol_threshold:
            return MarketRegime.HIGH_VOL
        elif vix_level < self.low_vol_threshold:
            return MarketRegime.LOW_VOL
        else:
            return MarketRegime.NORMAL
    
    def get_strategy_weights(self, regime: MarketRegime) -> Dict[str, float]:
        """레짐별 전략 가중치"""
        weights = {
            MarketRegime.LOW_VOL: {
                'momentum': 0.40,
                'low_vol': 0.20,
                'factor': 0.30,
                'mean_rev': 0.10
            },
            MarketRegime.NORMAL: {
                'momentum': 0.30,
                'low_vol': 0.30,
                'factor': 0.25,
                'mean_rev': 0.15
            },
            MarketRegime.HIGH_VOL: {
                'momentum': 0.15,
                'low_vol': 0.50,
                'factor': 0.20,
                'mean_rev': 0.15
            },
            MarketRegime.CRISIS: {
                'momentum': 0.05,
                'low_vol': 0.60,
                'factor': 0.15,
                'mean_rev': 0.20
            }
        }
        return weights.get(regime, weights[MarketRegime.NORMAL])


class VolatilityTargeting:
    """
    Volatility Targeting Module
    
    목표 변동성 유지를 위한 레버리지 조정
    - 변동성 낮을 때: 레버리지 증가
    - 변동성 높을 때: 레버리지 감소
    """
    
    def __init__(self, 
                 target_vol: float = 0.10,
                 lookback: int = 60,
                 max_leverage: float = 2.0,
                 min_leverage: float = 0.3):
        self.target_vol = target_vol
        self.lookback = lookback
        self.max_leverage = max_leverage
        self.min_leverage = min_leverage
    
    def calculate_leverage(self, returns: pd.Series, date: pd.Timestamp) -> float:
        """목표 변동성 기반 레버리지 계산"""
        if date not in returns.index:
            return 1.0
        
        idx = returns.index.get_loc(date)
        if idx < self.lookback:
            return 1.0
        
        recent_returns = returns.iloc[idx-self.lookback:idx]
        realized_vol = recent_returns.std() * np.sqrt(252)
        
        if realized_vol <= 0 or np.isnan(realized_vol):
            return 1.0
        
        leverage = self.target_vol / realized_vol
        leverage = np.clip(leverage, self.min_leverage, self.max_leverage)
        
        return leverage


class TransactionCostModel:
    """
    Transaction Cost Model
    
    현실적인 거래 비용 모델링
    - Spread cost: 고정 스프레드 비용
    - Market impact: 거래량 기반 시장 충격
    """
    
    def __init__(self, 
                 spread_bps: float = 5.0,
                 impact_coef: float = 10.0):
        self.spread_bps = spread_bps
        self.impact_coef = impact_coef
    
    def calculate_cost(self, 
                       old_positions: Dict[str, float], 
                       new_positions: Dict[str, float]) -> float:
        """거래 비용 계산 (총 자산 대비 비율)"""
        all_symbols = set(old_positions.keys()) | set(new_positions.keys())
        
        total_turnover = 0
        for sym in all_symbols:
            old_w = old_positions.get(sym, 0)
            new_w = new_positions.get(sym, 0)
            total_turnover += abs(new_w - old_w)
        
        # Spread cost (one-way)
        spread_cost = (self.spread_bps / 10000) * total_turnover
        
        # Market impact (simplistic model)
        impact_cost = (self.impact_coef / 10000) * np.sqrt(total_turnover)
        
        total_cost = spread_cost + impact_cost
        
        return total_cost
    
    def should_trade(self, 
                     old_positions: Dict[str, float], 
                     new_positions: Dict[str, float],
                     expected_return: float) -> bool:
        """거래 실행 여부 판단"""
        cost = self.calculate_cost(old_positions, new_positions)
        
        # 기대 수익이 비용의 2배 이상일 때만 거래
        return expected_return > 2 * cost


class AdaptiveEnsemble:
    """
    Adaptive Ensemble Weighting
    
    Rolling Sharpe 기반 동적 가중치 조정
    - 성과 좋은 전략에 더 높은 비중
    - 상관관계 고려한 분산 효과
    """
    
    def __init__(self, 
                 lookback: int = 63,  # 3개월
                 temperature: float = 1.0):
        self.lookback = lookback
        self.temperature = temperature
    
    def calculate_weights(self, 
                          strategy_returns: pd.DataFrame,
                          date: pd.Timestamp) -> Dict[str, float]:
        """적응형 가중치 계산"""
        if date not in strategy_returns.index:
            # 동일 가중치
            n = len(strategy_returns.columns)
            return {col: 1.0/n for col in strategy_returns.columns}
        
        idx = strategy_returns.index.get_loc(date)
        if idx < self.lookback:
            n = len(strategy_returns.columns)
            return {col: 1.0/n for col in strategy_returns.columns}
        
        recent = strategy_returns.iloc[idx-self.lookback:idx]
        
        # Rolling Sharpe ratios
        sharpes = {}
        for col in recent.columns:
            ret_mean = recent[col].mean() * 252
            ret_std = recent[col].std() * np.sqrt(252)
            sharpes[col] = ret_mean / ret_std if ret_std > 0 else 0
        
        # Softmax weighting
        sharpe_values = np.array(list(sharpes.values()))
        exp_values = np.exp(sharpe_values / self.temperature)
        softmax_weights = exp_values / exp_values.sum()
        
        weights = {col: w for col, w in zip(sharpes.keys(), softmax_weights)}
        
        return weights


class ARES7Ultimate:
    """
    ARES-7 Ultimate System
    
    모든 컴포넌트를 통합한 최종 시스템
    """
    
    def __init__(self, 
                 data_dir: str = "./data",
                 config: TradeConfig = None):
        self.data_loader = DataLoader(data_dir)
        self.config = config or TradeConfig()
        
        # Sub-engines
        self.momentum_engine = RobustMomentumEngine()
        self.cross_asset_engine = CrossAssetEngine()
        self.vix_engine = VIXRegimeEngine()
        self.vol_targeting = VolatilityTargeting(
            target_vol=self.config.target_volatility,
            max_leverage=self.config.max_leverage
        )
        self.cost_model = TransactionCostModel(
            spread_bps=self.config.spread_cost_bps,
            impact_coef=self.config.market_impact_coef
        )
        self.ensemble = AdaptiveEnsemble()
    
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """모든 데이터 로드"""
        print("Loading data...")
        prices = self.data_loader.load_prices()
        fundamentals = self.data_loader.load_fundamentals()
        vix = self.data_loader.load_vix()
        spy_tlt = self.data_loader.load_spy_tlt()
        
        print(f"  Prices: {prices.shape}")
        print(f"  Fundamentals: {len(fundamentals)} rows")
        print(f"  VIX: {len(vix) if vix is not None else 0} rows")
        print(f"  SPY-TLT: {len(spy_tlt) if spy_tlt is not None else 0} rows")
        
        return prices, fundamentals, vix, spy_tlt
    
    def backtest(self, 
                 rebal_freq: int = 5,  # 5일 = 주간
                 start_date: str = None,
                 end_date: str = None) -> Dict:
        """
        백테스트 실행
        
        Parameters:
        -----------
        rebal_freq: 리밸런싱 주기 (일)
        start_date: 시작 날짜
        end_date: 종료 날짜
        
        Returns:
        --------
        Dict containing performance metrics and daily returns
        """
        # Load data
        prices, fundamentals, vix, spy_tlt = self.load_data()
        returns = prices.pct_change()
        
        # Filter date range
        if start_date:
            prices = prices.loc[start_date:]
            returns = returns.loc[start_date:]
        if end_date:
            prices = prices.loc[:end_date]
            returns = returns.loc[:end_date]
        
        print(f"\nBacktest period: {prices.index[0].date()} to {prices.index[-1].date()}")
        print(f"Rebalance frequency: {rebal_freq} days")
        
        # Calculate signals
        print("\nCalculating signals...")
        momentum_signals = self.momentum_engine.calculate_signals(prices)
        cross_asset_signal = self.cross_asset_engine.calculate_regime_signal(spy_tlt)
        
        # Rebalance dates
        rebal_dates = prices.index[::rebal_freq]
        
        # Backtest loop
        print(f"\nRunning backtest ({len(rebal_dates)} rebalance dates)...")
        
        portfolio_returns = []
        current_positions = {}
        next_positions = {}
        
        for i, date in enumerate(prices.index):
            # Apply positions from previous rebalance
            if next_positions:
                current_positions = next_positions.copy()
                next_positions = {}
            
            # Rebalance
            if date in rebal_dates and i > 0:
                prev_date = prices.index[i-1]
                
                # Get regime
                regime = self.vix_engine.get_regime(vix, prev_date)
                strategy_weights = self.vix_engine.get_strategy_weights(regime)
                
                # Generate momentum positions
                mom_positions = self.momentum_engine.generate_positions(
                    momentum_signals, prev_date
                )
                
                # Cross-asset adjustment
                if cross_asset_signal is not None:
                    adjustment = self.cross_asset_engine.get_allocation_adjustment(
                        cross_asset_signal, prev_date
                    )
                else:
                    adjustment = 1.0
                
                # Calculate portfolio-level volatility for targeting
                if len(portfolio_returns) > self.config.vol_lookback:
                    port_ret_series = pd.Series(portfolio_returns)
                    leverage = self.vol_targeting.calculate_leverage(
                        port_ret_series, 
                        pd.Timestamp(date)
                    )
                else:
                    leverage = 1.0
                
                # Combine positions with regime and leverage
                next_positions = {}
                for sym, weight in mom_positions.items():
                    adjusted_weight = weight * adjustment * leverage
                    adjusted_weight = np.clip(
                        adjusted_weight, 
                        -self.config.max_position_size, 
                        self.config.max_position_size
                    )
                    next_positions[sym] = adjusted_weight
                
                if i % 50 == 0:
                    n_long = sum(1 for w in next_positions.values() if w > 0)
                    n_short = sum(1 for w in next_positions.values() if w < 0)
                    print(f"  {date.date()}: Regime={regime.value}, Leverage={leverage:.2f}, "
                          f"Long={n_long}, Short={n_short}")
            
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
            
            # Subtract transaction costs (on rebalance days)
            if date in rebal_dates and current_positions and next_positions:
                cost = self.cost_model.calculate_cost(current_positions, next_positions)
                daily_ret -= cost
            
            portfolio_returns.append(daily_ret)
        
        # Calculate performance metrics
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
            'n_trades': len(rebal_dates),
            'daily_returns': [
                {'date': d.strftime('%Y-%m-%d'), 'ret': float(r)}
                for d, r in returns_series.items()
            ],
            'config': {
                'rebal_freq': rebal_freq,
                'target_vol': self.config.target_volatility,
                'spread_bps': self.config.spread_cost_bps,
                'max_leverage': self.config.max_leverage
            }
        }
        
        return results
    
    def print_results(self, results: Dict):
        """결과 출력"""
        print("\n" + "=" * 70)
        print("ARES-7 Ultimate Engine Results")
        print("=" * 70)
        print(f"  Sharpe Ratio:      {results['sharpe']:.3f}")
        print(f"  Annual Return:     {results['annual_return']*100:.2f}%")
        print(f"  Annual Volatility: {results['annual_volatility']*100:.2f}%")
        print(f"  Max Drawdown:      {results['max_drawdown']*100:.2f}%")
        print(f"  Calmar Ratio:      {results['calmar']:.3f}")
        print(f"  Sortino Ratio:     {results['sortino']:.3f}")
        print(f"  Win Rate:          {results['win_rate']*100:.1f}%")
        print(f"  Total Return:      {results['total_return']*100:.1f}%")
        print("=" * 70)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ARES-7 Ultimate Engine')
    parser.add_argument('--data_dir', default='./data')
    parser.add_argument('--rebal_freq', type=int, default=5)
    parser.add_argument('--target_vol', type=float, default=0.10)
    parser.add_argument('--out', default='./results/ares7_ultimate_results.json')
    args = parser.parse_args()
    
    # Configuration
    config = TradeConfig(
        target_volatility=args.target_vol
    )
    
    # Initialize system
    system = ARES7Ultimate(data_dir=args.data_dir, config=config)
    
    # Run backtest
    results = system.backtest(rebal_freq=args.rebal_freq)
    
    # Print results
    system.print_results(results)
    
    # Save results
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.out}")


if __name__ == '__main__':
    main()
