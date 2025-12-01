#!/bin/bash
# ARES7-Best Tuning Backtest Runner
# ==================================
# 
# 사용법:
#   ./run_tuning_backtest.sh [conservative|moderate|aggressive|all]
#
# 예시:
#   ./run_tuning_backtest.sh conservative
#   ./run_tuning_backtest.sh all

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONFIG_DIR="${SCRIPT_DIR}/config"
RESULTS_DIR="${SCRIPT_DIR}/tuning/results"
BACKTEST_SCRIPT="${SCRIPT_DIR}/tuning/backtest/ares7_tuning_backtest_v1.py"

# Create results directory if not exists
mkdir -p "${RESULTS_DIR}"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to run backtest for a specific config
run_backtest() {
    local config_name=$1
    local config_file="${CONFIG_DIR}/tuning_config_${config_name}.yaml"
    local output_file="${RESULTS_DIR}/backtest_${config_name}_$(date +%Y%m%d_%H%M%S).txt"
    
    print_info "Running ${config_name} backtest..."
    print_info "Config: ${config_file}"
    print_info "Output: ${output_file}"
    
    if [ ! -f "${config_file}" ]; then
        print_error "Config file not found: ${config_file}"
        return 1
    fi
    
    if [ ! -f "${BACKTEST_SCRIPT}" ]; then
        print_error "Backtest script not found: ${BACKTEST_SCRIPT}"
        return 1
    fi
    
    # Run backtest
    python3 "${BACKTEST_SCRIPT}" --config "${config_file}" | tee "${output_file}"
    
    if [ $? -eq 0 ]; then
        print_success "${config_name} backtest completed!"
        print_info "Results saved to: ${output_file}"
    else
        print_error "${config_name} backtest failed!"
        return 1
    fi
}

# Main execution
main() {
    local mode=${1:-"moderate"}  # Default to moderate
    
    echo "=========================================="
    echo "  ARES7-Best Tuning Backtest Runner"
    echo "=========================================="
    echo ""
    print_info "Mode: ${mode}"
    echo ""
    
    case "${mode}" in
        conservative)
            run_backtest "conservative"
            ;;
        moderate)
            run_backtest "moderate"
            ;;
        aggressive)
            run_backtest "aggressive"
            ;;
        all)
            print_info "Running all configurations..."
            echo ""
            
            run_backtest "conservative"
            echo ""
            echo "----------------------------------------"
            echo ""
            
            run_backtest "moderate"
            echo ""
            echo "----------------------------------------"
            echo ""
            
            run_backtest "aggressive"
            echo ""
            
            print_success "All backtests completed!"
            ;;
        *)
            print_error "Invalid mode: ${mode}"
            echo ""
            echo "Usage: $0 [conservative|moderate|aggressive|all]"
            echo ""
            echo "Modes:"
            echo "  conservative - Safe tuning (Sharpe 2.15 target)"
            echo "  moderate     - Balanced tuning (Sharpe 2.30 target)"
            echo "  aggressive   - Max tuning (Sharpe 2.45 target)"
            echo "  all          - Run all three configs"
            exit 1
            ;;
    esac
    
    echo ""
    echo "=========================================="
    print_success "Backtest run complete!"
    echo "=========================================="
    echo ""
    print_info "Results directory: ${RESULTS_DIR}"
    echo ""
}

# Run main
main "$@"
