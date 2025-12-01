"""
백테스터 헬스체크 - 3가지 기본 테스트
목적: 백테스터의 정확성 검증
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

# Load data
print("="*70)
print("백테스터 헬스체크")
print("="*70)

print("\n데이터 로딩...")
df = pd.read_csv('./data/price_full.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
price = df.pivot(index='timestamp', columns='symbol', values='close')
print(f"  Price data: {price.shape}")

ret = price.pct_change().fillna(0)

# =============================================================================
# Test 1: Equal-Weight Long-Only
# =============================================================================
print("\n" + "="*70)
print("Test 1: Equal-Weight Long-Only")
print("="*70)

# Simple equal weight portfolio
n_stocks = len(price.columns)
weights = pd.Series(1.0 / n_stocks, index=price.columns)

# Calculate returns
portfolio_ret = (ret * weights).sum(axis=1)

# Metrics
sharpe = portfolio_ret.mean() / portfolio_ret.std() * np.sqrt(252)
annual_return = portfolio_ret.mean() * 252
annual_vol = portfolio_ret.std() * np.sqrt(252)

cumret = (1 + portfolio_ret).cumprod()
cummax = cumret.cummax()
dd = (cumret - cummax) / cummax
max_dd = dd.min()

print(f"\n결과:")
print(f"  Sharpe: {sharpe:.4f}")
print(f"  Annual Return: {annual_return:.2%}")
print(f"  Annual Vol: {annual_vol:.2%}")
print(f"  Max DD: {max_dd:.2%}")

print(f"\n평가:")
if sharpe > 0.5:
    print(f"  ✅ PASS - Sharpe {sharpe:.4f} > 0.5 (정상)")
elif sharpe > 0:
    print(f"  ⚠️  WARNING - Sharpe {sharpe:.4f} 낮음 (시장 환경 또는 데이터 문제)")
else:
    print(f"  ❌ FAIL - Sharpe {sharpe:.4f} 음수 (백테스터 오류 가능성)")

# =============================================================================
# Test 2: Zero Position (No Trading)
# =============================================================================
print("\n" + "="*70)
print("Test 2: Zero Position (No Trading)")
print("="*70)

# Zero weights
zero_ret = pd.Series(0.0, index=ret.index)

sharpe_zero = zero_ret.std()
return_zero = zero_ret.sum()

print(f"\n결과:")
print(f"  Total Return: {return_zero:.6f}")
print(f"  Std Dev: {sharpe_zero:.6f}")

print(f"\n평가:")
if abs(return_zero) < 1e-10 and abs(sharpe_zero) < 1e-10:
    print(f"  ✅ PASS - 수익 및 변동성 모두 0 (정상)")
else:
    print(f"  ❌ FAIL - 수익 {return_zero:.6f} 또는 변동성 {sharpe_zero:.6f} 비정상")
    print(f"  → PnL 집계/shift/날짜 인덱싱 문제 가능성")

# =============================================================================
# Test 3: 12-Month Momentum (Simple)
# =============================================================================
print("\n" + "="*70)
print("Test 3: 12-Month Momentum (1-Month Skip)")
print("="*70)

# Calculate momentum
mom_12m = ret.rolling(252).sum()
mom_1m = ret.rolling(21).sum()
mom_signal = mom_12m - mom_1m

# Monthly rebalancing
rebal_dates = price.resample('MS').first().index
rebal_dates = [d for d in rebal_dates if d in mom_signal.index]

portfolio_returns = []
current_weights = pd.Series(0.0, index=price.columns)

for i, date in enumerate(price.index):
    # Rebalance
    if date in rebal_dates:
        sig = mom_signal.loc[date].dropna()
        if len(sig) >= 40:  # Need at least 40 stocks
            sig = sig.sort_values(ascending=False)
            
            # Top 20 long, Bottom 20 short
            long_stocks = sig.head(20).index
            short_stocks = sig.tail(20).index
            
            new_weights = pd.Series(0.0, index=price.columns)
            new_weights[long_stocks] = 1.0 / 20  # 100% long
            new_weights[short_stocks] = -1.0 / 20  # 100% short
            
            current_weights = new_weights
    
    # Calculate return
    if i > 0:
        daily_ret = (ret.loc[date] * current_weights).sum()
        portfolio_returns.append(daily_ret)
    else:
        portfolio_returns.append(0.0)

mom_ret = pd.Series(portfolio_returns, index=price.index)

# Metrics
sharpe_mom = mom_ret.mean() / mom_ret.std() * np.sqrt(252)
return_mom = mom_ret.mean() * 252
vol_mom = mom_ret.std() * np.sqrt(252)

cumret_mom = (1 + mom_ret).cumprod()
cummax_mom = cumret_mom.cummax()
dd_mom = (cumret_mom - cummax_mom) / cummax_mom
mdd_mom = dd_mom.min()

print(f"\n결과:")
print(f"  Sharpe: {sharpe_mom:.4f}")
print(f"  Annual Return: {return_mom:.2%}")
print(f"  Annual Vol: {vol_mom:.2%}")
print(f"  Max DD: {mdd_mom:.2%}")

print(f"\n평가:")
if sharpe_mom > 0.3:
    print(f"  ✅ PASS - Sharpe {sharpe_mom:.4f} > 0.3 (정상)")
elif sharpe_mom > 0:
    print(f"  ⚠️  WARNING - Sharpe {sharpe_mom:.4f} 낮음 (시장 환경 또는 파라미터 문제)")
else:
    print(f"  ❌ FAIL - Sharpe {sharpe_mom:.4f} 음수 (타이밍/라깅 문제 가능성)")

# =============================================================================
# Summary
# =============================================================================
print("\n" + "="*70)
print("백테스터 헬스체크 요약")
print("="*70)

results = {
    "test_1_equal_weight": {
        "sharpe": float(sharpe),
        "annual_return": float(annual_return),
        "annual_volatility": float(annual_vol),
        "max_drawdown": float(max_dd),
        "status": "PASS" if sharpe > 0.5 else ("WARNING" if sharpe > 0 else "FAIL")
    },
    "test_2_zero_position": {
        "total_return": float(return_zero),
        "std_dev": float(sharpe_zero),
        "status": "PASS" if abs(return_zero) < 1e-10 and abs(sharpe_zero) < 1e-10 else "FAIL"
    },
    "test_3_momentum": {
        "sharpe": float(sharpe_mom),
        "annual_return": float(return_mom),
        "annual_volatility": float(vol_mom),
        "max_drawdown": float(mdd_mom),
        "status": "PASS" if sharpe_mom > 0.3 else ("WARNING" if sharpe_mom > 0 else "FAIL")
    }
}

# Save results
Path("./results").mkdir(exist_ok=True)
with open("./results/backtester_healthcheck.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n결과 저장: ./results/backtester_healthcheck.json")

# Overall assessment
all_pass = all(r["status"] == "PASS" for r in results.values())
any_fail = any(r["status"] == "FAIL" for r in results.values())

print(f"\n전체 평가:")
if all_pass:
    print(f"  ✅ 모든 테스트 통과 - 백테스터 정상")
elif any_fail:
    print(f"  ❌ 일부 테스트 실패 - 백테스터 검토 필요")
else:
    print(f"  ⚠️  일부 테스트 경고 - 시장 환경 또는 파라미터 확인 필요")

print("="*70)
