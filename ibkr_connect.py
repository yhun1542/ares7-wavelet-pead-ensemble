#!/usr/bin/env python3
"""
ibkr_connect.py

================================================================================
IBKR API Connection Script
================================================================================

역할:
  - IBKR API를 통해 계정 접속
  - 포지션, 잔고, 주문 기능 제공
  - ib_insync 라이브러리 사용

실행:
  python3 ibkr_connect.py

요구사항:
  - IB Gateway 또는 TWS 실행 중이어야 함
  - API 설정에서 포트 활성화 필요 (기본: 7497 for TWS, 4001 for Gateway)

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
Version: 1.0
================================================================================
"""

from ib_insync import *
import pandas as pd
from datetime import datetime

# ============================================================================
# Configuration
# ============================================================================

# IBKR Gateway/TWS connection
IB_HOST = '127.0.0.1'
IB_PORT = 4001  # Gateway paper trading port (4001), live port (4002)
                # TWS paper trading port (7497), live port (7496)
CLIENT_ID = 1

# ============================================================================
# IBKR Connection Class
# ============================================================================

class IBKRConnection:
    def __init__(self, host=IB_HOST, port=IB_PORT, client_id=CLIENT_ID):
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
    
    def connect(self):
        """Connect to IBKR"""
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            print(f"✅ Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from IBKR"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            print("✅ Disconnected from IBKR")
    
    def get_account_summary(self):
        """Get account summary"""
        if not self.connected:
            print("❌ Not connected")
            return None
        
        try:
            account_values = self.ib.accountSummary()
            
            summary = {}
            for item in account_values:
                summary[item.tag] = item.value
            
            return summary
        except Exception as e:
            print(f"❌ Failed to get account summary: {e}")
            return None
    
    def get_positions(self):
        """Get current positions"""
        if not self.connected:
            print("❌ Not connected")
            return None
        
        try:
            positions = self.ib.positions()
            
            if not positions:
                print("No positions")
                return []
            
            pos_list = []
            for pos in positions:
                pos_list.append({
                    'symbol': pos.contract.symbol,
                    'position': pos.position,
                    'avg_cost': pos.avgCost,
                    'market_value': pos.position * pos.avgCost,
                })
            
            return pos_list
        except Exception as e:
            print(f"❌ Failed to get positions: {e}")
            return None
    
    def get_portfolio(self):
        """Get portfolio items"""
        if not self.connected:
            print("❌ Not connected")
            return None
        
        try:
            portfolio = self.ib.portfolio()
            
            if not portfolio:
                print("No portfolio items")
                return []
            
            port_list = []
            for item in portfolio:
                port_list.append({
                    'symbol': item.contract.symbol,
                    'position': item.position,
                    'market_price': item.marketPrice,
                    'market_value': item.marketValue,
                    'avg_cost': item.averageCost,
                    'unrealized_pnl': item.unrealizedPNL,
                    'realized_pnl': item.realizedPNL,
                })
            
            return port_list
        except Exception as e:
            print(f"❌ Failed to get portfolio: {e}")
            return None
    
    def place_order(self, symbol, quantity, action='BUY', order_type='MKT', limit_price=None):
        """Place an order"""
        if not self.connected:
            print("❌ Not connected")
            return None
        
        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Create order
            if order_type == 'MKT':
                order = MarketOrder(action, quantity)
            elif order_type == 'LMT':
                if limit_price is None:
                    print("❌ Limit price required for LMT order")
                    return None
                order = LimitOrder(action, quantity, limit_price)
            else:
                print(f"❌ Unsupported order type: {order_type}")
                return None
            
            # Place order
            trade = self.ib.placeOrder(contract, order)
            
            print(f"✅ Order placed: {action} {quantity} {symbol} @ {order_type}")
            
            return trade
        except Exception as e:
            print(f"❌ Failed to place order: {e}")
            return None


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 80)
    print("IBKR API Connection Test")
    print("=" * 80)
    
    # Create connection
    ibkr = IBKRConnection()
    
    # Connect
    if not ibkr.connect():
        print("\n❌ Connection failed!")
        print("\nTroubleshooting:")
        print("1. Make sure IB Gateway or TWS is running")
        print("2. Enable API connections in settings")
        print("3. Check port number (4001 for Gateway paper, 7497 for TWS paper)")
        print("4. Allow connections from localhost (127.0.0.1)")
        return
    
    print("\n" + "=" * 80)
    print("Account Summary")
    print("=" * 80)
    
    # Get account summary
    summary = ibkr.get_account_summary()
    if summary:
        for key, value in summary.items():
            print(f"{key}: {value}")
    
    print("\n" + "=" * 80)
    print("Current Positions")
    print("=" * 80)
    
    # Get positions
    positions = ibkr.get_positions()
    if positions:
        df_pos = pd.DataFrame(positions)
        print(df_pos.to_string(index=False))
    
    print("\n" + "=" * 80)
    print("Portfolio")
    print("=" * 80)
    
    # Get portfolio
    portfolio = ibkr.get_portfolio()
    if portfolio:
        df_port = pd.DataFrame(portfolio)
        print(df_port.to_string(index=False))
    
    # Disconnect
    print("\n" + "=" * 80)
    ibkr.disconnect()
    print("=" * 80)


if __name__ == '__main__':
    main()
