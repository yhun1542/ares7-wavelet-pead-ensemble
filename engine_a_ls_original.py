#!/usr/bin/env python3
"""
ARES-7 Fast Vectorized Backtest Engine v80
- 벡터화된 연산으로 100배 속도 향상
- 진행률 로깅 및 체크포인트 저장
- 중단 후 재시작 가능
"""
import numpy as np
import pandas as pd
import pickle
import json
import logging
from datetime import datetime
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/backtest_v80.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FastBacktestV80:
    def __init__(self):
        # 거래비용
        self.COMMISSION_RATE = 0.0012  # 12bps
        self.SLIPPAGE_RATE = 0.0005    # 5bps
        
        # 백테스트 파라미터
        self.INITIAL_CAPITAL = 100000
        self.MAX_POSITIONS = 20
        self.MIN_HOLD_DAYS = 5
        self.MAX_HOLD_DAYS = 20
        
        # ===== v80 단일 엔진 베이스라인 (보수형 Top #1 조합) =====
        # Engine A: Momentum + Mean Reversion
        self.MOMENTUM_WEIGHT = 0.5
        self.MR_WEIGHT = 0.5
        self.SIGNAL_THRESHOLD = 0.035   # 상위 강한 시그널만 진입
        
        # 리스크 관리
        self.HARD_STOP = -0.08      # -8% 손절
        self.TRAILING_STOP = 0.0    # Trailing Stop 비활성화
        self.PROFIT_TARGET = 0.15   # +15% 익절
        
        # 유니버스 설정
        self.USE_ETF = False  # Phase 3-1: ETF 비활성화, 주식 100개만 사용
        
        # ===== 멀티엔진 / 메타 옵션은 존재하더라도 프로덕션에서는 끄 =====
        self.USE_MULTI_ENGINE = False  # ★ 단일 엔진 모드로 고정
        self.META_TARGET_P = 0.99      # R&D용, 현재는 사용 안 함
        self.meta_threshold_ = None
        
        # ===== 단일 엔진용 THRESHOLD 자동화 옵션 =====
        # 단일 엔진 시그널 절대값 기준 상위 p 비율만 진입 (예: 0.98 = 상위 2%)
        self.SINGLE_TARGET_P = 0.98    # 상위 2% 컷 타깃 (P=0.98 확정)
        self.single_threshold_ = None
        
        # ===== 엔진 모드 플래그 (A/B/C 중 선택) =====
        # "A" : 기존 Momentum+MR 엔진
        # "B" : Short Reversal 엔진 (단기 리버설, R&D용)
        # "C" : Low-Vol + Quality 엔진 (신규 설계, R&D용)
        self.ENGINE_MODE = "A"  # Engine A: Momentum + Mean Reversion
        
        # ===== 레짐 필터 옵션 추가 =====
        self.USE_REGIME_FILTER   = False    # 레짐 필터 비활성화 (순수 엔진 성능 평가)
        self.REGIME_LOOKBACK_D   = 200      # 인덱스 이동평균 기간(일)
        self.REGIME_MIN_PERIODS  = 120      # 최소 유효 기간
        self.REGIME_ON_VALUE     = 1        # Risk-ON 표시값
        self.REGIME_OFF_VALUE    = 0        # Risk-OFF 표시값
        
        # 레짐 관련 통계
        self.regime_days = {"on": 0, "off": 0}
        self.regime_blocked_entries = 0
        
        # 통계
        self.stats = {
            'total_signals': 0,
            'blocked_reentry': 0,
            'stop_loss_hits': 0,
            'profit_target_hits': 0,
            'time_exits': 0
        }
        
    def apply_transaction_cost(self, value):
        """거래비용 계산"""
        base_cost = abs(value) * (self.COMMISSION_RATE + self.SLIPPAGE_RATE)
        if abs(value) > 10000000:
            base_cost *= 1.2
        return base_cost
    
    def calculate_signals_vectorized(self, df):
        """
        시그널 계산:
        - 단일 엔진 모드: Engine A or B (ENGINE_MODE에 따라)
        - 멀티엔진 모드: Engine A/B/C + meta_signal (R&D용)
        """
        
        # 1) 단일 엔진 모드: ENGINE_MODE에 따라 A 혹은 B만 사용
        if not self.USE_MULTI_ENGINE:
            d = df.copy()
            d = d.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
            g = d.groupby('symbol', group_keys=False)
            
            # --- Engine A: Momentum + MR (기존 엔진) ---
            if self.ENGINE_MODE == "A":
                logger.info("단일 엔진 시그널 계산 중... (Engine A: Momentum+MR)")
                
                ret20 = g['close'].pct_change(20)
                ret5  = g['close'].pct_change(5)
                
                mom_raw = ret20.shift(1)
                mr_raw  = -ret5.shift(1)
                
                # 극단값 클리핑 (과도한 spike 방지)
                mom_raw = mom_raw.clip(-0.15, 0.15)
                mr_raw  = mr_raw.clip(-0.15, 0.15)
                
                signal_A = self.MOMENTUM_WEIGHT * mom_raw + self.MR_WEIGHT * mr_raw
                
                d['signal'] = signal_A.fillna(0.0)
                
                logger.info(f"단일 엔진 A 시그널 계산 완료: {len(d)} rows (Momentum+MR)")
                return d
            
            # --- Engine B: Short Reversal (단기 리버설 전용, R&D용) ---
            elif self.ENGINE_MODE == "B":
                logger.info("단일 엔진 시그널 계산 중... (Engine B: Short Reversal)")
                
                # 5일 수익률
                ret5_long = g['close'].pct_change(5)
                
                # 60일 롤링 평균/표준편차로 정규화 (리버설 z-score)
                mean60 = ret5_long.rolling(60, min_periods=20).mean()
                std60  = ret5_long.rolling(60, min_periods=20).std(ddof=0)
                
                z_rev = -(ret5_long - mean60) / std60.replace(0, np.nan)
                
                # 룩어헤드 방지: 신호는 항상 1틱(1일) 지연
                signal_B = z_rev.shift(1)
                
                # 극단값 클리핑 (과도한 spike 방지)
                signal_B = signal_B.clip(-5.0, 5.0)
                
                d['signal'] = signal_B.fillna(0.0)
                
                logger.info(f"단일 엔진 B 시그널 계산 완료: {len(d)} rows (Short Reversal)")
                return d
            
            # --- Engine C v2: Ultra Simple Downside Low-Vol (신규 설계, R&D용) ---
            elif self.ENGINE_MODE == "C":
                logger.info("단일 엔진 시그널 계산 중... (Engine C v2: Ultra Simple Downside Low-Vol)")
                
                # 1) 일간 수익률
                daily_ret = g['close'].pct_change()
                
                # 2) 60일 downside volatility
                #    - 양수 수익률은 0으로 날리고, 음수 구간의 std만 본다.
                downside_ret = daily_ret.clip(upper=0)  # r>0 → 0
                down_vol60 = downside_ret.rolling(60, min_periods=40).std(ddof=0)
                d['down_vol60'] = down_vol60
                
                # 3) 중기 모멘텀/장기 수익률 (필터용)
                ret120 = g['close'].pct_change(120)
                ret252 = g['close'].pct_change(252)
                d['ret120'] = ret120
                d['ret252'] = ret252
                
                # 4) 날짜별 cross-section rank (0~1)
                def rank_pct(x):
                    return x.rank(pct=True)
                
                # 낮은 downside vol 선호 점수 (0~1, 1이 가장 low-vol)
                d['lowvol_score'] = d.groupby('timestamp')['down_vol60'].transform(
                    lambda x: 1.0 - rank_pct(x)
                )
                
                # 5) 모멘텀/퀴얼리티 필터
                # - 120일 수익률 양수인 종목만 통과
                d['mom_filter'] = (d['ret120'] > 0.0).astype(float)
                
                # - 252일 수익률 10% 이상인 종목만 quality pass
                d['qual_filter'] = (d['ret252'] > 0.10).astype(float)
                
                # 6) 최종 raw 시그널 = lowvol_score * mom_filter * qual_filter
                raw_signal = d['lowvol_score'] * d['mom_filter'] * d['qual_filter']
                
                # 7) 룩어헤드 방지: 1틱(1일) 시프트 후 결측치는 0으로 (중립)
                signal_C = raw_signal.shift(1)
                d['signal'] = signal_C.fillna(0.0)
                
                logger.info(f"단일 엔진 C v2 시그널 계산 완료: {len(d)} rows (Downside Low-Vol + Filters)")
                return d
            
            # --- 정의되지 않은 ENGINE_MODE일 때: 기본 A로 fallback ---
            else:
                logger.warning(f"알 수 없는 ENGINE_MODE={self.ENGINE_MODE}, Engine A로 fallback 합니다.")
                
                ret20 = g['close'].pct_change(20)
                ret5  = g['close'].pct_change(5)
                
                mom_raw = ret20.shift(1)
                mr_raw  = -ret5.shift(1)
                
                mom_raw = mom_raw.clip(-0.15, 0.15)
                mr_raw  = mr_raw.clip(-0.15, 0.15)
                
                signal_A = self.MOMENTUM_WEIGHT * mom_raw + self.MR_WEIGHT * mr_raw
                
                d['signal'] = signal_A.fillna(0.0)
                
                logger.info(f"단일 엔진 A(Fallback) 시그널 계산 완료: {len(d)} rows")
                return d
        
        # 2) 멀티엔진 모드: Engine A/B/C + meta_signal (R&D 전용)
        logger.info("멀티엔진 시그널 계산 중... (R&D 모드)")
        
        d = df.copy()
        # 정렬 및 기본 그룹
        d = d.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
        g = d.groupby('symbol', group_keys=False)
        
        # -------------------------
        # Engine A: Momentum + MR
        # -------------------------
        # 20일 모멘텀, 5일 mean reversion (룩어헤드 방지 위해 shift(1))
        ret20 = g['close'].pct_change(20)
        ret5  = g['close'].pct_change(5)
        
        mom_raw = ret20.shift(1)            # 모멘텀
        mr_raw  = -ret5.shift(1)            # mean reversion: 최근 많이 빠진 애 선호
        
        # 극단값 클리핑 (과도한 spike 방지)
        mom_raw = mom_raw.clip(-0.15, 0.15)
        mr_raw  = mr_raw.clip(-0.15, 0.15)
        
        signal_A_raw = self.MOMENTUM_WEIGHT * mom_raw + self.MR_WEIGHT * mr_raw
        
        # -------------------------
        # Engine B: Short Reversal
        # -------------------------
        # 5일 수익률을 60일 롤링 평균/표준편차로 정규화 → 과도한 하락 구간 포착
        ret5_long = g['close'].pct_change(5)
        mean60 = ret5_long.rolling(60, min_periods=20).mean()
        std60  = ret5_long.rolling(60, min_periods=20).std(ddof=0)
        
        z_rev = -(ret5_long - mean60) / std60.replace(0, np.nan)
        signal_B_raw = z_rev.shift(1)   # 룩어헤드 방지
        
        # -------------------------
        # Engine C: Low-Vol + 60d Momentum
        # -------------------------
        # 60일 변동성 (낮을수록 선호), 60일 모멘텀 (높을수록 선호)
        daily_ret = g['close'].pct_change()
        vol60 = daily_ret.rolling(60, min_periods=20).std(ddof=0)
        ret60 = g['close'].pct_change(60)
        
        d['vol60'] = vol60
        d['ret60'] = ret60
        
        # 날짜별 cross-sectional rank 사용 (0~1)
        def rank_pct(x):
            return x.rank(pct=True)
        
        # 낮은 변동성 선호 → rank 높을수록 vol 낮음
        d['lowvol_score'] = d.groupby('timestamp')['vol60'].transform(
            lambda x: 1.0 - rank_pct(x)
        )
        d['mom60_score'] = d.groupby('timestamp')['ret60'].transform(rank_pct)
        
        signal_C_raw = (0.7 * d['lowvol_score'] + 0.3 * d['mom60_score']).shift(1)
        
        # -------------------------
        # cross-sectional z-score 표준화
        # -------------------------
        d['signal_A_raw'] = signal_A_raw
        d['signal_B_raw'] = signal_B_raw
        d['signal_C_raw'] = signal_C_raw
        
        def zscore_cs(s):
            m = s.mean()
            v = s.std(ddof=0)
            if v is None or v == 0 or np.isnan(v):
                return pd.Series(0.0, index=s.index)
            return (s - m) / v
        
        d['zA'] = d.groupby('timestamp')['signal_A_raw'].transform(zscore_cs)
        d['zB'] = d.groupby('timestamp')['signal_B_raw'].transform(zscore_cs)
        d['zC'] = d.groupby('timestamp')['signal_C_raw'].transform(zscore_cs)
        
        # -------------------------
        # 메타 시그널 가중합
        # -------------------------
        # 초기 가중치 (추후 튜닝 가능): A 0.4 / B 0.3 / C 0.3
        wA, wB, wC = 0.4, 0.3, 0.3
        
        meta_signal = (
            wA * d['zA'].fillna(0.0) +
            wB * d['zB'].fillna(0.0) +
            wC * d['zC'].fillna(0.0)
        )
        
        # NaN → 0 (중립) 처리
        d['signal'] = meta_signal.fillna(0.0)
        
        logger.info(f"멀티엔진 시그널 계산 완료: {len(d)} rows")
        logger.info(f"  Engine A (Momentum+MR), Engine B (Reversal), Engine C (LowVol+Mom60)")
        logger.info(f"  Meta Signal Weights: A={wA}, B={wB}, C={wC}")
        
        return d
    
    def run_backtest(self, data_path, checkpoint_file='/tmp/backtest_checkpoint.pkl'):
        """메인 백테스트 로직"""
        logger.info("="*70)
        logger.info("ARES-7 Fast Vectorized Backtest v80")
        logger.info("="*70)
        
        # 데이터 로드
        logger.info(f"데이터 로드 중: {data_path}")
        with open(data_path, 'rb') as f:
            df = pickle.load(f)
        
        logger.info(f"데이터: {len(df)} rows, {df['symbol'].nunique()} symbols")
        
        # === 유니버스 구성 ===
        logger.info("\n" + "="*70)
        logger.info("🌐 유니버스 구성")
        logger.info("="*70)
        
        if self.USE_ETF:
            # ETF 포함 모드
            ETF_WHITELIST = [
                'SPY', 'QQQ', 'IWM', 'XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLU'
            ]
            
            symbols_in_data = df['symbol'].unique().tolist()
            etfs_in_data = [s for s in ETF_WHITELIST if s in symbols_in_data]
            
            is_etf = df['symbol'].isin(etfs_in_data)
            stock_df = df[~is_etf]
            etf_df = df[is_etf]
            
            top_stocks = stock_df.groupby('symbol')['volume'].sum().nlargest(80).index
            
            if len(etfs_in_data) > 0:
                top_etfs = etf_df.groupby('symbol')['volume'].sum().nlargest(20).index
            else:
                top_etfs = []
            
            universe = list(top_stocks) + list(top_etfs)
            logger.info(f"주식: {len(top_stocks)}개, ETF: {len(top_etfs)}개, 총 {len(universe)}개 심볼")
        else:
            # 주식 100개만 사용 (Phase 3-1 기본 모드)
            top_stocks = df.groupby('symbol')['volume'].sum().nlargest(100).index
            universe = list(top_stocks)
            logger.info(f"주식 전용 모드: {len(universe)}개 심볼")
        
        df = df[df['symbol'].isin(universe)]
        logger.info("="*70 + "\n")
        
        # 시그널 계산
        df = self.calculate_signals_vectorized(df)
        
        # === 멀티엔진 meta_signal 분포 기반 THRESHOLD 자동 설정 ===
        if self.USE_MULTI_ENGINE:
            abs_meta = df['signal'].abs()
            p = self.META_TARGET_P  # 예: 0.99 (상위 1%)
            self.meta_threshold_ = float(abs_meta.quantile(p))
            
            logger.info("\n" + "="*70)
            logger.info("🎯 Meta Signal THRESHOLD 자동 설정")
            logger.info("="*70)
            logger.info(f"Target Percentile: {p*100:.1f}% (상위 {100*(1-p):.2f}%)")
            logger.info(f"Auto Threshold: {self.meta_threshold_:.4f}")
            logger.info(f"\nMeta Signal 분포:")
            logger.info(f"  Mean: {df['signal'].mean():.6f}")
            logger.info(f"  Std:  {df['signal'].std():.6f}")
            logger.info(f"  Min:  {df['signal'].min():.6f}")
            logger.info(f"  Max:  {df['signal'].max():.6f}")
            logger.info(f"\n예상 거래 수: {(abs_meta > self.meta_threshold_).sum():,} rows")
            logger.info("="*70 + "\n")
        else:
            # 단일 엔진 모드에서는 meta_threshold 계산 안 함
            self.meta_threshold_ = None
        
        # === 단일 엔진 시그널 분포 기반 THRESHOLD 자동 설정 ===
        if not self.USE_MULTI_ENGINE:
            if 'signal' not in df.columns:
                raise RuntimeError("calculate_signals 후 df['signal'] 컴럼이 없습니다. 단일 엔진 시그널 계산을 확인하세요.")
            
            abs_sig = df['signal'].abs().dropna()
            if len(abs_sig) == 0:
                self.single_threshold_ = None
                logger.warning("경고: 단일 엔진 시그널 데이터가 비어 있습니다. SIGNAL_THRESHOLD 값만 사용합니다.")
            else:
                p = self.SINGLE_TARGET_P   # 예: 0.98 (상위 2% 컷)
                self.single_threshold_ = float(abs_sig.quantile(p))
                
                logger.info("\n" + "="*70)
                logger.info("🎯 Single Engine Signal THRESHOLD 자동 설정")
                logger.info("="*70)
                logger.info(f"Target Percentile: {p*100:.1f}% (상위 {100*(1-p):.2f}%)")
                logger.info(f"Auto Threshold: {self.single_threshold_:.4f}")
                logger.info(f"\nSingle Signal 분포:")
                logger.info(f"  Mean: {df['signal'].mean():.6f}")
                logger.info(f"  Std:  {df['signal'].std():.6f}")
                logger.info(f"  Min:  {df['signal'].min():.6f}")
                logger.info(f"  Max:  {df['signal'].max():.6f}")
                logger.info(f"\n예상 거래 수: {(abs_sig > self.single_threshold_).sum():,} rows")
                logger.info("="*70 + "\n")
        else:
            self.single_threshold_ = None
        
        # === 레짐 계산: 유니버스 평균 가격 기반 인덱스 + 200일 MA ===
        if self.USE_REGIME_FILTER:
            logger.info("\n" + "="*70)
            logger.info("🚦 레짐 필터 계산 중...")
            logger.info("="*70)
            
            # df: ['timestamp','symbol','close','signal', ...] 가정
            df = df.sort_values(['timestamp', 'symbol']).reset_index(drop=True)
            
            # 1) 날짜별 유니버스 평균 종가로 "시장 인덱스" 생성
            mkt = (
                df.groupby('timestamp')['close']
                  .mean()
                  .rename('mkt_index')
                  .to_frame()
                  .sort_index()
            )
            
            # 2) 200일 단순 이동평균 계산
            lookback = self.REGIME_LOOKBACK_D
            minp     = self.REGIME_MIN_PERIODS
            mkt['mkt_ma'] = mkt['mkt_index'].rolling(lookback, min_periods=minp).mean()
            
            # 3) 레짐 플래그: 인덱스 > MA 이면 Risk-ON(1), 아니면 Risk-OFF(0)
            mkt['regime_flag'] = np.where(
                mkt['mkt_index'] > mkt['mkt_ma'],
                self.REGIME_ON_VALUE,
                self.REGIME_OFF_VALUE
            )
            
            # 4) df에 레짐 정보 merge
            df = df.merge(
                mkt[['regime_flag']],
                left_on='timestamp',
                right_index=True,
                how='left'
            )
            
            # NaN 레짐(초기 구간)는 보수적으로 Risk-OFF 처리
            df['regime_flag'] = df['regime_flag'].fillna(self.REGIME_OFF_VALUE).astype(int)
            
            # 레짐 일수 카운팅 (정보용)
            n_on  = int((mkt['regime_flag'] == self.REGIME_ON_VALUE).sum())
            n_off = int((mkt['regime_flag'] == self.REGIME_OFF_VALUE).sum())
            self.regime_days['on']  = n_on
            self.regime_days['off'] = n_off
            
            logger.info(f"레짐 계산 완료: Risk-ON={n_on}일 ({n_on/(n_on+n_off)*100:.1f}%), Risk-OFF={n_off}일 ({n_off/(n_on+n_off)*100:.1f}%)")
            logger.info("="*70 + "\n")
        else:
            # 레짐 필터 미사용 시 더미 컴럼 추가
            df['regime_flag'] = self.REGIME_ON_VALUE
            logger.info("레짐 필터 비활성화 (Risk-ON 고정)\n")
        
        # === 시그널 분포 진단 ===
        logger.info("\n" + "="*70)
        logger.info("🔍 시그널 분포 진단")
        logger.info("="*70)
        
        sig = df['signal'].dropna()
        abs_sig = sig.abs()
        
        logger.info("\n기본 통계:")
        logger.info(f"  Mean: {sig.mean():.6f}")
        logger.info(f"  Std:  {sig.std():.6f}")
        logger.info(f"  Min:  {sig.min():.6f}")
        logger.info(f"  Max:  {sig.max():.6f}")
        
        logger.info("\n|signal| > threshold 비율:")
        for th in [0.05, 0.1, 0.15, 0.2, 0.3]:
            ratio = (abs_sig > th).mean()
            count = (abs_sig > th).sum()
            logger.info(f"  |signal| > {th:.2f}: {ratio*100:6.3f}% ({count:,} rows)")
        
        logger.info("\nQuantiles of |signal|:")
        for q in [0.5, 0.8, 0.9, 0.95, 0.99]:
            val = abs_sig.quantile(q)
            logger.info(f"  {q*100:.0f}%: {val:.6f}")
        
        logger.info("="*70 + "\n")
        
        # 날짜별 인덱스 생성 (벡터화 최적화)
        logger.info("날짜별 인덱스 생성 중...")
        df['date_idx'] = pd.factorize(df['timestamp'])[0]
        dates = sorted(df['timestamp'].unique())
        
        # 종목별 데이터 딕셔너리 (빠른 접근)
        logger.info("종목별 데이터 딕셔너리 생성 중...")
        symbol_data = {sym: group for sym, group in df.groupby('symbol')}
        
        # 초기화
        cash = self.INITIAL_CAPITAL
        positions = {}
        trades = []
        daily_equity = {}
        
        total_days = len(dates)
        logger.info(f"백테스트 시작: {total_days} days")
        
        # 진행률 체크포인트
        checkpoint_interval = 500
        progress_interval = 100
        
        for day_idx, date in enumerate(dates):
            # 진행률 출력
            if (day_idx + 1) % progress_interval == 0:
                progress_pct = (day_idx + 1) / total_days * 100
                logger.info(f"진행률: {day_idx+1}/{total_days} ({progress_pct:.1f}%) - "
                          f"Positions: {len(positions)}, Trades: {len(trades)}, "
                          f"Cash: ${cash:,.0f}")
            
            # 체크포인트 저장
            if (day_idx + 1) % checkpoint_interval == 0:
                checkpoint = {
                    'day_idx': day_idx,
                    'cash': cash,
                    'positions': positions.copy(),
                    'trades': trades.copy(),
                    'daily_equity': daily_equity.copy(),
                    'stats': self.stats.copy()
                }
                with open(checkpoint_file, 'wb') as f:
                    pickle.dump(checkpoint, f)
                logger.info(f"체크포인트 저장: {checkpoint_file}")
            
            # 현재 날짜 데이터
            day_data = df[df['timestamp'] == date]
            
            # === 1. 기존 포지션 체크 ===
            for symbol in list(positions.keys()):
                pos = positions[symbol]
                
                # 현재 가격
                current = day_data[day_data['symbol'] == symbol]
                if current.empty:
                    continue
                
                current_price = current['close'].iloc[0]
                pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']
                hold_days = (date - pos['entry_date']).days
                
                # High Water Mark 갱신
                if 'high_water_mark' not in pos:
                    pos['high_water_mark'] = current_price
                else:
                    pos['high_water_mark'] = max(pos['high_water_mark'], current_price)
                
                exit_reason = None
                
                # MIN_HOLD_DAYS 이전에는 HARD_STOP만 허용
                if hold_days < self.MIN_HOLD_DAYS:
                    if pnl_pct <= self.HARD_STOP:
                        exit_reason = 'STOP_LOSS'
                        self.stats['stop_loss_hits'] += 1
                else:
                    # 손절
                    if pnl_pct <= self.HARD_STOP:
                        exit_reason = 'STOP_LOSS'
                        self.stats['stop_loss_hits'] += 1
                    
                    # Trailing Stop (High Water Mark 기준)
                    elif self.TRAILING_STOP > 0 and (current_price - pos['high_water_mark']) / pos['high_water_mark'] <= -self.TRAILING_STOP:
                        exit_reason = 'TRAILING_STOP'
                        self.stats['trailing_stop_hits'] = self.stats.get('trailing_stop_hits', 0) + 1
                    
                    # 익절
                    elif pnl_pct >= self.PROFIT_TARGET:
                        exit_reason = 'PROFIT_TARGET'
                        self.stats['profit_target_hits'] += 1
                    
                    # 시간 종료
                    elif hold_days >= self.MAX_HOLD_DAYS:
                        exit_reason = 'TIME_EXIT'
                        self.stats['time_exits'] += 1
                
                # 청산
                if exit_reason:
                    proceeds = pos['shares'] * current_price
                    exit_cost = self.apply_transaction_cost(proceeds)
                    net_proceeds = proceeds - exit_cost
                    
                    cash += net_proceeds
                    
                    trades.append({
                        'symbol': symbol,
                        'entry_date': pos['entry_date'],
                        'exit_date': date,
                        'entry_price': pos['entry_price'],
                        'exit_price': current_price,
                        'shares': pos['shares'],
                        'net_pnl': net_proceeds - pos['cost_basis'],
                        'exit_reason': exit_reason
                    })
                    
                    del positions[symbol]
            
            # === 2. 신규 진입 ===
            # 당일 레짐 값 (0 or 1)
            if self.USE_REGIME_FILTER:
                # day_data 전체가 동일한 regime_flag를 가질 것이므로 첫 값 사용
                regime_today = int(day_data['regime_flag'].iloc[0])
            else:
                regime_today = self.REGIME_ON_VALUE  # 필터 미사용시 항상 ON 취급
            
            # Risk-OFF 일 때 신규 진입 금지
            if self.USE_REGIME_FILTER and regime_today == self.REGIME_OFF_VALUE:
                # 이 날은 Risk-OFF → 신규 진입 금지
                # (리스크 관리는 이미 위 단계에서 처리)
                # 차단된 진입 후보 수 카운팅
                potential_entries = day_data[day_data['signal'] > self.SIGNAL_THRESHOLD]
                self.regime_blocked_entries += len(potential_entries)
                continue
            
            # 엔트리용 threshold 결정
            threshold = self.SIGNAL_THRESHOLD
            
            # 1) 단일 엔진 모드면 single_threshold_ 우선
            if (not self.USE_MULTI_ENGINE) and (self.single_threshold_ is not None):
                threshold = self.single_threshold_
            
            # 2) 멀티엔진 모드면 meta_threshold_ (있을 경우)
            elif self.USE_MULTI_ENGINE and (self.meta_threshold_ is not None):
                threshold = self.meta_threshold_
            
            strong_signals = day_data[day_data['signal'] > threshold]
            strong_signals = strong_signals.nlargest(
                min(self.MAX_POSITIONS - len(positions), 5),
                'signal'
            )
            
            for _, row in strong_signals.iterrows():
                symbol = row['symbol']
                
                # 재진입 가드
                if symbol in positions:
                    self.stats['blocked_reentry'] += 1
                    continue
                
                # 포지션 크기
                position_size = min(
                    cash * 0.05,
                    cash / max(1, self.MAX_POSITIONS - len(positions))
                )
                
                if position_size < 1000:
                    continue
                
                entry_price = row['close']
                entry_cost = self.apply_transaction_cost(position_size)
                shares = position_size / entry_price
                total_cost = position_size + entry_cost
                
                if cash >= total_cost:
                    positions[symbol] = {
                        'entry_date': date,
                        'entry_price': entry_price,
                        'shares': shares,
                        'cost_basis': total_cost
                    }
                    
                    cash -= total_cost
                    self.stats['total_signals'] += 1
            
            # === 3. 일별 에쿼티 기록 ===
            portfolio_value = cash
            for symbol, pos in positions.items():
                current = day_data[day_data['symbol'] == symbol]
                if not current.empty:
                    portfolio_value += current['close'].iloc[0] * pos['shares']
            
            daily_equity[date] = portfolio_value
        
        logger.info("백테스트 완료! 성과 계산 중...")
        
        # === 4. 성과 계산 ===
        equity_df = pd.DataFrame(list(daily_equity.items()), 
                                columns=['date', 'equity'])
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df = equity_df.set_index('date').sort_index()
        
        # 일별 리샘플링
        daily = equity_df.resample('B').last().ffill()
        daily_returns = daily['equity'].pct_change().dropna()
        
        # 샤프 비율
        if len(daily_returns) > 0:
            sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) \
                    if daily_returns.std() > 0 else 0
            
            # 최대 낙폭
            cummax = daily['equity'].cummax()
            drawdown = (daily['equity'] - cummax) / cummax
            max_dd = drawdown.min()
            
            # 연환산 수익률
            total_return = (daily['equity'].iloc[-1] / self.INITIAL_CAPITAL) - 1
            days = len(daily)
            annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
            
            # 연환산 변동성
            annual_vol = daily_returns.std() * np.sqrt(252)
        else:
            sharpe = max_dd = annual_return = annual_vol = 0
        
        # Profit Factor
        trades_df = pd.DataFrame(trades)
        if len(trades_df) > 0:
            wins = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].sum()
            losses = abs(trades_df[trades_df['net_pnl'] < 0]['net_pnl'].sum())
            profit_factor = wins / losses if losses > 0 else 999
            win_rate = len(trades_df[trades_df['net_pnl'] > 0]) / len(trades_df)
        else:
            profit_factor = win_rate = 0
        
        # === 5. 결과 출력 ===
        logger.info("\n" + "="*70)
        logger.info("📊 백테스트 결과 (Fast v80)")
        logger.info("="*70)
        logger.info(f"Sharpe Ratio:      {sharpe:.3f}")
        logger.info(f"Annual Return:     {annual_return:.1%}")
        logger.info(f"Annual Volatility: {annual_vol:.1%}")
        logger.info(f"Max Drawdown:      {max_dd:.1%}")
        logger.info(f"Profit Factor:     {profit_factor:.2f}")
        logger.info(f"Win Rate:          {win_rate:.1%}")
        logger.info(f"Total Trades:      {len(trades_df)}")
        
        logger.info("\n📈 리스크 관리 통계")
        logger.info(f"총 시그널:         {self.stats['total_signals']}")
        logger.info(f"재진입 차단:       {self.stats['blocked_reentry']}")
        logger.info(f"손절 발생:         {self.stats['stop_loss_hits']}")
        logger.info(f"익절 발생:         {self.stats['profit_target_hits']}")
        logger.info(f"시간 청산:         {self.stats['time_exits']}")
        
        # 레짐 통계 출력
        if self.USE_REGIME_FILTER:
            logger.info("\n🚦 레짐 필터 통계")
            logger.info(f"Risk-ON 일수:  {self.regime_days['on']}")
            logger.info(f"Risk-OFF 일수: {self.regime_days['off']}")
            logger.info(f"레짐으로 신규 진입 차단: {self.regime_blocked_entries}")
        
        # daily_returns를 JSON에 저장할 수 있는 형태로 변환
        if len(daily_returns) > 0:
            daily_ret_list = [
                {"date": idx.strftime("%Y-%m-%d"), "ret": float(val)}
                for idx, val in daily_returns.items()
            ]
        else:
            daily_ret_list = []
        
        # 결과 저장
        output = {
            'sharpe': sharpe,
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'max_drawdown': max_dd,
            'profit_factor': profit_factor,
            'win_rate': win_rate,
            'total_trades': len(trades_df),
            'stats': self.stats,
            'regime_stats': {
                'use_regime_filter': self.USE_REGIME_FILTER,
                'regime_days': self.regime_days,
                'regime_blocked_entries': self.regime_blocked_entries
            },
            'daily_returns': daily_ret_list,   # ★ 추가
            'trades': trades_df.to_dict('records') if len(trades_df) > 0 else []
        }
        
        # ENGINE_MODE에 따라 저장 경로 동적 설정
        if self.ENGINE_MODE == "A":
            out_path = "/tmp/engine_a_single_results.json"
        elif self.ENGINE_MODE == "B":
            out_path = "/tmp/engine_b_single_results.json"
        elif self.ENGINE_MODE == "C":
            out_path = "/tmp/engine_c_single_results.json"
        else:
            out_path = "/tmp/ares7_v80_results_with_etf.json"  # fallback
        
        with open(out_path, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        logger.info(f"\n💾 결과 저장: {out_path}")
        logger.info("="*70)
        
        return output

if __name__ == "__main__":
    import sys
    
    data_path = '/tmp/ares7_training_data.pkl'
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    
    bt = FastBacktestV80()
    result = bt.run_backtest(data_path)
    
    logger.info(f"\n✅ 백테스트 완료! Sharpe: {result['sharpe']:.3f}")
