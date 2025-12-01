#!/usr/bin/env python3
"""
Event-book 기반 Pure Tilt Overlay 구현

핵심 아이디어:
- 이벤트 발생 시에만 포지션 변경
- Horizon 동안 포지션 고정
- 만기 시 자동 청산
- Base weight 내에서 재분배 (net exposure 유지)
"""

import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Dict, List, Tuple


class EventBook:
    """
    이벤트 기반 포지션 관리
    
    각 이벤트는 (symbol, open_date, close_date, tilt_amount) 튜플로 저장
    """
    
    def __init__(self):
        self.active_events = []  # List of (symbol, open_date, close_date, tilt_amount)
        self.event_history = []  # 분석용 히스토리
    
    def add_event(self, symbol: str, open_date, horizon_days: int, tilt_amount: float):
        """
        새로운 이벤트 추가
        
        Args:
            symbol: 종목 코드
            open_date: 이벤트 오픈 날짜
            horizon_days: 보유 기간 (영업일)
            tilt_amount: Tilt 크기 (절대값, 예: 0.005 = 0.5%p)
        """
        close_date = open_date + pd.Timedelta(days=horizon_days)
        event = (symbol, open_date, close_date, tilt_amount)
        self.active_events.append(event)
        self.event_history.append({
            'symbol': symbol,
            'open_date': open_date,
            'close_date': close_date,
            'tilt_amount': tilt_amount,
            'status': 'opened'
        })
    
    def get_active_tilts(self, current_date) -> Dict[str, float]:
        """
        현재 날짜에 활성화된 tilts 반환
        
        Args:
            current_date: 현재 날짜
        
        Returns:
            {symbol: total_tilt_amount} 딕셔너리
        """
        tilts = {}
        for symbol, open_date, close_date, amount in self.active_events:
            if open_date <= current_date < close_date:
                tilts[symbol] = tilts.get(symbol, 0.0) + amount
        return tilts
    
    def close_expired_events(self, current_date):
        """
        만료된 이벤트 제거
        
        Args:
            current_date: 현재 날짜
        """
        # 만료된 이벤트 히스토리에 기록
        for event in self.active_events:
            symbol, open_date, close_date, amount = event
            if close_date <= current_date:
                self.event_history.append({
                    'symbol': symbol,
                    'open_date': open_date,
                    'close_date': close_date,
                    'tilt_amount': amount,
                    'status': 'closed',
                    'close_actual_date': current_date
                })
        
        # 활성 이벤트에서 제거
        self.active_events = [
            event for event in self.active_events
            if event[2] > current_date
        ]
    
    def get_event_count(self, current_date) -> int:
        """현재 활성 이벤트 수"""
        return len([e for e in self.active_events if e[1] <= current_date < e[2]])
    
    def get_total_tilt(self, current_date) -> float:
        """현재 총 tilt 크기"""
        return sum(self.get_active_tilts(current_date).values())
    
    def get_event_history_df(self) -> pd.DataFrame:
        """이벤트 히스토리를 DataFrame으로 반환"""
        return pd.DataFrame(self.event_history)


def apply_pure_tilt_overlay(
    w_base: pd.Series,
    signal: pd.Series,
    event_book: EventBook,
    current_date,
    horizon_days: int,
    tilt_per_event: float,
    funding_method: str = 'proportional'
) -> pd.Series:
    """
    Pure Tilt 방식으로 Overlay 적용
    
    Args:
        w_base: Base weights (Series, index=symbols)
        signal: Event signal (Series, 1 for pos_top, 0 otherwise)
        event_book: EventBook instance
        current_date: 현재 날짜
        horizon_days: 보유 기간
        tilt_per_event: 이벤트당 tilt 크기 (예: 0.005 = 0.5%p)
        funding_method: 'proportional' (base weight 비례) or 'equal' (균등)
    
    Returns:
        w_overlay: Overlay 적용된 weights (Series)
    """
    # 1. 새로운 이벤트 추가
    new_events = signal[signal == 1].index.tolist()
    for symbol in new_events:
        event_book.add_event(symbol, current_date, horizon_days, tilt_per_event)
    
    # 2. 현재 활성 tilts 가져오기
    active_tilts = event_book.get_active_tilts(current_date)
    
    # 3. Overlay weight 초기화
    w_overlay = w_base.copy()
    
    # 4. Tilt up event stocks
    total_tilt = 0.0
    for symbol, tilt in active_tilts.items():
        if symbol in w_overlay.index:
            w_overlay[symbol] += tilt
            total_tilt += tilt
    
    # 5. Funding from no-event stocks
    event_symbols = set(active_tilts.keys())
    no_event_symbols = [s for s in w_base.index if s not in event_symbols]
    
    if len(no_event_symbols) > 0 and total_tilt > 0:
        if funding_method == 'proportional':
            # Base weight에 비례하여 funding
            no_event_base_sum = w_base[no_event_symbols].sum()
            if no_event_base_sum > 0:
                for symbol in no_event_symbols:
                    funding_amount = total_tilt * (w_base[symbol] / no_event_base_sum)
                    w_overlay[symbol] -= funding_amount
        else:  # equal
            # 균등하게 funding
            funding_per_stock = total_tilt / len(no_event_symbols)
            for symbol in no_event_symbols:
                w_overlay[symbol] -= funding_per_stock
    
    # 6. Normalize (음수 방지 및 합=1 보장)
    w_overlay = w_overlay.clip(lower=0)
    w_overlay = w_overlay / w_overlay.sum()
    
    # 7. 만료된 이벤트 정리
    event_book.close_expired_events(current_date)
    
    return w_overlay


def backtest_pure_tilt(
    w_base: pd.DataFrame,
    signal: pd.DataFrame,
    px: pd.DataFrame,
    horizon_days: int,
    tilt_per_event: float,
    fee_rate: float = 0.001,
    funding_method: str = 'proportional'
) -> Tuple[pd.Series, pd.Series, pd.Series, EventBook]:
    """
    Pure Tilt Overlay 백테스트
    
    Args:
        w_base: Base weights (DataFrame, index=dates, columns=symbols)
        signal: Event signals (DataFrame, 1 for pos_top, 0 otherwise)
        px: Prices (DataFrame, index=dates, columns=symbols)
        horizon_days: 보유 기간
        tilt_per_event: 이벤트당 tilt 크기
        fee_rate: 거래 비용 (편도)
        funding_method: Funding 방식
    
    Returns:
        base_ret: Base 수익률 (Series)
        overlay_ret: Overlay 수익률 (Series)
        incr_ret: Incremental 수익률 (Series)
        event_book: EventBook instance (분석용)
    """
    event_book = EventBook()
    w_overlay_history = []
    
    dates = px.index
    
    for date in dates:
        if date not in w_base.index or date not in signal.index:
            continue
        
        # Apply Pure Tilt
        w_overlay = apply_pure_tilt_overlay(
            w_base.loc[date],
            signal.loc[date],
            event_book,
            date,
            horizon_days,
            tilt_per_event,
            funding_method
        )
        
        w_overlay_history.append(w_overlay)
    
    # Convert to DataFrame
    w_overlay_df = pd.DataFrame(w_overlay_history, index=dates[:len(w_overlay_history)])
    
    # Compute returns
    from research.pead.overlay_engine import compute_portfolio_returns
    
    base_ret = compute_portfolio_returns(w_base, px, fee_rate)
    overlay_ret = compute_portfolio_returns(w_overlay_df, px, fee_rate)
    incr_ret = overlay_ret - base_ret
    
    return base_ret, overlay_ret, incr_ret, event_book


if __name__ == "__main__":
    # 간단한 테스트
    print("Event-book Pure Tilt Overlay 모듈")
    print("사용법:")
    print("  from event_book import EventBook, apply_pure_tilt_overlay, backtest_pure_tilt")
