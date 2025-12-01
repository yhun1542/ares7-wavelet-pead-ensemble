#!/bin/bash
# ARES7-Best Tuning Structure Setup
# 4축 튜닝을 위한 디렉토리 구조 생성

cd /home/ubuntu/ares7-ensemble

# 디렉토리 생성
mkdir -p risk
mkdir -p modules
mkdir -p config
mkdir -p tuning/axis1_transaction_cost
mkdir -p tuning/axis2_leverage_risk
mkdir -p tuning/axis3_quality_momentum
mkdir -p tuning/axis4_vix_guard
mkdir -p tuning/results
mkdir -p tuning/backtest

echo "✅ ARES7 Tuning Structure Created:"
echo "   - risk/                  # 리스크 관리 모듈"
echo "   - modules/               # 재사용 가능한 모듈"
echo "   - config/                # 설정 파일"
echo "   - tuning/axis1_*         # Axis 1: Transaction Cost"
echo "   - tuning/axis2_*         # Axis 2: Leverage/Risk"
echo "   - tuning/axis3_*         # Axis 3: Quality+Momentum"
echo "   - tuning/axis4_*         # Axis 4: VIX Guard"
echo "   - tuning/results/        # 백테스트 결과"
echo "   - tuning/backtest/       # 통합 백테스트 스크립트"

tree -L 2 -d
