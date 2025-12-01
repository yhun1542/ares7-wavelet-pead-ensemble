#!/usr/bin/env bash
################################################################################
# ARES8 PEAD Only 프로덕션 자동 실행 스크립트
################################################################################
#
# 용도:
#   - PEAD Only Overlay 전략을 프로덕션 환경에서 자동 실행
#   - R&D 모드(ENABLE_RD_MODE) 자동으로 OFF
#   - 실행 결과를 타임스탬프 기반 로그 파일에 기록
#   - cron 또는 수동 실행 모두 지원
#
# 실행 방법:
#   수동: ./run_pead_prod.sh
#   Cron: 0 9 * * * /home/ubuntu/ares7-ensemble/run_pead_prod.sh
#
# 안전장치:
#   - ENABLE_RD_MODE 자동 unset (R&D 모드 강제 OFF)
#   - 실행 전/후 모드 확인 메시지 출력
#   - 로그 파일 자동 생성 및 보관
#
# Author: ARES7/ARES8 Research Team
# Date: 2025-12-01
# Version: 1.0
################################################################################

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR="/home/ubuntu/ares7-ensemble"
LOG_DIR="${BASE_DIR}/logs"
SCRIPT_NAME="run_pead_buyback_ensemble_prod.py"

# ============================================================================
# Setup
# ============================================================================

# 로그 디렉토리 생성
mkdir -p "${LOG_DIR}"

# R&D 모드 강제로 OFF (CRITICAL)
unset ENABLE_RD_MODE 2>/dev/null || true
export ENABLE_RD_MODE=""

# 타임스탬프 기반 로그 파일 이름
TS="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_DIR}/pead_prod_${TS}.log"

# ============================================================================
# Pre-flight Check
# ============================================================================

echo "================================================================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARES8 PEAD PROD RUN START" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

echo "📍 Working Directory: ${BASE_DIR}" | tee -a "${LOG_FILE}"
echo "📝 Log File: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "🐍 Python: $(which python3)" | tee -a "${LOG_FILE}"
echo "🔒 MODE: PRODUCTION (ENABLE_RD_MODE unset)" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# 환경변수 확인
if [ -z "${ENABLE_RD_MODE:-}" ]; then
    echo "✅ ENABLE_RD_MODE: (unset) - PRODUCTION MODE" | tee -a "${LOG_FILE}"
else
    echo "❌ WARNING: ENABLE_RD_MODE='${ENABLE_RD_MODE}' - Forcing to unset" | tee -a "${LOG_FILE}"
    unset ENABLE_RD_MODE
    export ENABLE_RD_MODE=""
    echo "✅ ENABLE_RD_MODE: (forced unset) - PRODUCTION MODE" | tee -a "${LOG_FILE}"
fi

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# ============================================================================
# Execute Production Script
# ============================================================================

cd "${BASE_DIR}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing: python3 ${SCRIPT_NAME}" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# 실제 프로덕션 스크립트 실행
python3 "${SCRIPT_NAME}" >> "${LOG_FILE}" 2>&1

RET=$?

# ============================================================================
# Post-execution Summary
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARES8 PEAD PROD RUN END (exit=${RET})" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

if [ ${RET} -eq 0 ]; then
    echo "✅ Execution completed successfully" | tee -a "${LOG_FILE}"
else
    echo "❌ Execution failed with exit code ${RET}" | tee -a "${LOG_FILE}"
fi

echo "" | tee -a "${LOG_FILE}"
echo "📁 Full log: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# ============================================================================
# Extract Key Metrics
# ============================================================================

echo "================================================================================" | tee -a "${LOG_FILE}"
echo "📊 KEY METRICS SUMMARY" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# 모드 확인
echo "🔍 Mode Check:" | tee -a "${LOG_FILE}"
grep -E "PROD MODE|RD MODE" "${LOG_FILE}" | head -3 || echo "  (Mode info not found)" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# Alpha Buyback 확인
echo "🔒 Alpha Buyback:" | tee -a "${LOG_FILE}"
grep "Alpha Buyback" "${LOG_FILE}" | head -2 || echo "  (Alpha Buyback info not found)" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# Sharpe 확인
echo "📈 Sharpe Ratios:" | tee -a "${LOG_FILE}"
grep -E "Base Test Sharpe|Overlay Test Sharpe|Incremental Sharpe" "${LOG_FILE}" || echo "  (Sharpe info not found)" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

echo "================================================================================" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# ============================================================================
# Exit
# ============================================================================

exit ${RET}
