#!/usr/bin/env bash
# run_daily_wavelet_pead_prod.sh
#
# ============================================================================
# ARES7 + Wavelet + PEAD Daily Production Automation
# ============================================================================
#
# 역할:
#   1) Wavelet overlay 생성 (Wavelet 엔진 실행)
#   2) PEAD overlay 생성 (PEAD 엔진 실행)
#   3) Wavelet + PEAD 합성 (최종 overlay 생성)
#
# 실행:
#   ./run_daily_wavelet_pead_prod.sh
#
# Cron 설정 예:
#   0 9 * * * /home/ubuntu/ares7-ensemble/run_daily_wavelet_pead_prod.sh >> /home/ubuntu/ares7-ensemble/logs/cron_daily.log 2>&1
#
# ============================================================================

set -euo pipefail

BASE_DIR="/home/ubuntu/ares7-ensemble"
LOG_DIR="${BASE_DIR}/logs"

mkdir -p "${LOG_DIR}"

# Timestamp
TS="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_DIR}/daily_wavelet_pead_${TS}.log"

cd "${BASE_DIR}"

echo "================================================================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARES7 + Wavelet + PEAD Daily Production Run START" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "Working Directory: ${BASE_DIR}" | tee -a "${LOG_FILE}"
echo "Log File: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

# ============================================================================
# Step 1: Generate Wavelet Overlay
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 1: Generating Wavelet Overlay..." | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

# TODO: Replace with actual Wavelet overlay generation script
# Example: python3 run_wavelet_overlay_prod.py >> "${LOG_FILE}" 2>&1

# For testing, use sample data
if [ ! -f "${BASE_DIR}/ensemble_outputs/wavelet_overlay_latest.csv" ]; then
    echo "[WARNING] wavelet_overlay_latest.csv not found, generating sample data..." | tee -a "${LOG_FILE}"
    python3 generate_sample_overlays.py >> "${LOG_FILE}" 2>&1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Wavelet overlay ready" | tee -a "${LOG_FILE}"

# ============================================================================
# Step 2: Generate PEAD Overlay
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 2: Generating PEAD Overlay..." | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

# TODO: Modify run_pead_buyback_ensemble_prod.py to output pead_overlay_latest.csv
# Example: python3 run_pead_buyback_ensemble_prod.py >> "${LOG_FILE}" 2>&1

# For testing, sample data is already generated in Step 1
if [ ! -f "${BASE_DIR}/ensemble_outputs/pead_overlay_latest.csv" ]; then
    echo "[WARNING] pead_overlay_latest.csv not found" | tee -a "${LOG_FILE}"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] PEAD overlay ready" | tee -a "${LOG_FILE}"

# ============================================================================
# Step 3: Combine Wavelet + PEAD Overlays
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 3: Combining Wavelet + PEAD Overlays..." | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

python3 run_wavelet_pead_overlay_prod.py >> "${LOG_FILE}" 2>&1

RET=$?

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARES7 + Wavelet + PEAD Daily Production Run END (exit=${RET})" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

if [ ${RET} -eq 0 ]; then
    echo "✅ Daily production run completed successfully" | tee -a "${LOG_FILE}"
else
    echo "❌ Daily production run failed with exit code ${RET}" | tee -a "${LOG_FILE}"
    exit ${RET}
fi

# ============================================================================
# Summary
# ============================================================================

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "SUMMARY" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

# Check output file
TODAY=$(date '+%Y%m%d')
FINAL_OVERLAY="${BASE_DIR}/ensemble_outputs/wavelet_pead_overlay_prod_${TODAY}.csv"

if [ -f "${FINAL_OVERLAY}" ]; then
    SYMBOL_COUNT=$(tail -n +2 "${FINAL_OVERLAY}" | wc -l)
    echo "✅ Final overlay file: ${FINAL_OVERLAY}" | tee -a "${LOG_FILE}"
    echo "   Symbols: ${SYMBOL_COUNT}" | tee -a "${LOG_FILE}"
    
    # Sample output
    echo "" | tee -a "${LOG_FILE}"
    echo "Sample output (first 5 rows):" | tee -a "${LOG_FILE}"
    head -6 "${FINAL_OVERLAY}" | tee -a "${LOG_FILE}"
else
    echo "❌ Final overlay file not found: ${FINAL_OVERLAY}" | tee -a "${LOG_FILE}"
    exit 1
fi

echo "" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"
echo "Full log: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "================================================================================" | tee -a "${LOG_FILE}"

exit 0
