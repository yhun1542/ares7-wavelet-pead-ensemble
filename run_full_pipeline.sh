#!/usr/bin/env bash
# run_full_pipeline.sh
#
# ============================================================================
# ARES7 + Wavelet + PEAD 완전 자동화 파이프라인
# ============================================================================
#
# 역할:
#   1) Wavelet + PEAD Overlay 생성
#   2) ARES7 Base weights + Overlay 통합
#   3) 최종 weights CSV 생성
#
# 실행:
#   ./run_full_pipeline.sh
#
# Cron 설정 예:
#   0 9 * * * /home/ubuntu/ares7-ensemble/run_full_pipeline.sh >> /home/ubuntu/ares7-ensemble/logs/cron_full_pipeline.log 2>&1
#
# ============================================================================

set -euo pipefail

BASE_DIR="/home/ubuntu/ares7-ensemble"
LOG_DIR="${BASE_DIR}/logs"

mkdir -p "${LOG_DIR}"

# Timestamp
TS="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_DIR}/full_pipeline_${TS}.log"

cd "${BASE_DIR}"

echo "================================================================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARES7 + Wavelet + PEAD Full Pipeline START" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "Working Directory: ${BASE_DIR}" | tee -a "${LOG_FILE}"
echo "Log File: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

# ============================================================================
# Step 1: Wavelet + PEAD Overlay 생성
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 1: Generating Wavelet + PEAD Overlay..." | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

./run_daily_wavelet_pead_prod.sh >> "${LOG_FILE}" 2>&1

RET1=$?

if [ ${RET1} -ne 0 ]; then
    echo "[ERROR] Wavelet + PEAD overlay generation failed (exit=${RET1})" | tee -a "${LOG_FILE}"
    exit ${RET1}
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Wavelet + PEAD overlay generation complete" | tee -a "${LOG_FILE}"

# ============================================================================
# Step 2: ARES7 통합
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 2: Integrating with ARES7 Base Weights..." | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

python3 ares7_integrate_overlay.py >> "${LOG_FILE}" 2>&1

RET2=$?

if [ ${RET2} -ne 0 ]; then
    echo "[ERROR] ARES7 integration failed (exit=${RET2})" | tee -a "${LOG_FILE}"
    exit ${RET2}
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARES7 integration complete" | tee -a "${LOG_FILE}"

# ============================================================================
# Summary
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARES7 + Wavelet + PEAD Full Pipeline END" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "✅ Full pipeline completed successfully" | tee -a "${LOG_FILE}"

# Check output files
TODAY=$(date '+%Y%m%d')
OVERLAY_FILE="${BASE_DIR}/ensemble_outputs/wavelet_pead_overlay_prod_${TODAY}.csv"
FINAL_WEIGHTS_FILE="${BASE_DIR}/ensemble_outputs/ares7_final_weights_${TODAY}.csv"

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "OUTPUT FILES" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

if [ -f "${OVERLAY_FILE}" ]; then
    OVERLAY_COUNT=$(tail -n +2 "${OVERLAY_FILE}" | wc -l)
    echo "✅ Overlay file: ${OVERLAY_FILE}" | tee -a "${LOG_FILE}"
    echo "   Symbols: ${OVERLAY_COUNT}" | tee -a "${LOG_FILE}"
else
    echo "❌ Overlay file not found: ${OVERLAY_FILE}" | tee -a "${LOG_FILE}"
fi

if [ -f "${FINAL_WEIGHTS_FILE}" ]; then
    WEIGHTS_COUNT=$(tail -n +2 "${FINAL_WEIGHTS_FILE}" | wc -l)
    echo "✅ Final weights file: ${FINAL_WEIGHTS_FILE}" | tee -a "${LOG_FILE}"
    echo "   Symbols: ${WEIGHTS_COUNT}" | tee -a "${LOG_FILE}"
    
    # Sample output
    echo "" | tee -a "${LOG_FILE}"
    echo "Sample final weights (first 5 rows):" | tee -a "${LOG_FILE}"
    head -6 "${FINAL_WEIGHTS_FILE}" | tee -a "${LOG_FILE}"
else
    echo "❌ Final weights file not found: ${FINAL_WEIGHTS_FILE}" | tee -a "${LOG_FILE}"
    exit 1
fi

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "Full log: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

exit 0
