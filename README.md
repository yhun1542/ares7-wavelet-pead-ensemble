# ARES7 Wavelet+PEAD Ensemble Trading System

**EC2 Production Deployment - High-Performance Quantitative Trading**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## 🎯 Project Overview

ARES7 is an advanced quantitative trading system that combines **Wavelet** and **PEAD (Post-Earnings Announcement Drift)** strategies using an optimized ensemble approach.

### Latest Performance (Wavelet+PEAD)

- ✅ **Overlay Test Sharpe: 0.775** (Target: 0.7~0.8)
- ✅ **Base+Overlay Test Sharpe: 0.990** (+0.382 improvement)
- ✅ **Optimal Weights**: Wavelet 54% + PEAD 46%
- ✅ **λ=1.0 (100% Overlay)** - Full overlay from the start
- ✅ **Risk Guards**: ±2% tilt cap per symbol

### Legacy Performance (4-Way Ensemble)

- **Sharpe Ratio**: 1.3588
- **Annual Return**: 16.36%
- **Annual Volatility**: 12.04%
- **Maximum Drawdown**: -13.46%

---

## 📊 Wavelet+PEAD Performance

| Split | Wavelet | PEAD | **Overlay** | Base | **Base+Overlay** |
|-------|---------|------|-------------|------|------------------|
| Train | 1.549 | 1.345 | **1.767** | 1.233 | **2.073** |
| Val | 1.668 | 1.255 | **1.758** | 1.651 | **2.333** |
| **Test** | 0.571 | 0.795 | **0.775** | 0.608 | **0.990** |

**Key Metrics**:
- Incremental Sharpe: +0.382
- Wavelet Weight: 0.54 (54%)
- PEAD Weight: 0.46 (46%)

---

## 🏗️ System Architecture

### Core Components

1. **Wavelet Strategy** - Momentum-based signal generation
2. **PEAD Strategy** - Earnings surprise overlay
3. **Ensemble Optimizer** - Optimal weight calculation (Σ^-1 μ method)
4. **Risk Manager** - Tilt capping and exposure control
5. **Dashboard** - Real-time monitoring (Flask + HTML)
6. **IBKR Integration** - Automated trading via IB Gateway

### Directory Structure

```
ares7-ensemble/
├── data/                           # Market data (prices, events)
├── research/pead/                  # PEAD research modules
├── risk/                           # Risk management
├── ensemble_outputs/               # Generated overlays and weights
├── logs/                           # Execution logs
├── templates/                      # Dashboard HTML
├── run_*.py                        # Main execution scripts
├── run_*.sh                        # Automation scripts
└── *.md                            # Documentation
```

---

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up data directory
mkdir -p data ensemble_outputs logs
```

### 2. Generate Overlay (Wavelet+PEAD)

```bash
# Run full pipeline (Wavelet + PEAD → Final Weights)
./run_full_pipeline.sh
```

### 3. View Dashboard

```bash
# Start dashboard API
python3 dashboard_api.py

# Access at http://localhost:5000
```

### 4. Legacy 4-Way Ensemble

```bash
# With Vol Targeting (12%)
python3.11 ensemble_4way_vol_target.py
```

---

## 📁 Key Files

### Wavelet+PEAD Scripts

| Script | Purpose |
|--------|---------|
| `run_full_pipeline.sh` | **Main**: Wavelet + PEAD → Final weights |
| `run_wavelet_pead_optimizer.py` | Find optimal weights (R&D) |
| `run_wavelet_pead_overlay_prod.py` | Combine Wavelet + PEAD overlays |
| `ares7_integrate_overlay.py` | Base + Overlay → Final weights |
| `run_pead_prod.sh` | PEAD Only (legacy) |

### Documentation

| Document | Description |
|----------|-------------|
| `ARES7_FINAL_INTEGRATION.md` | λ=1.0 integration guide |
| `WAVELET_PEAD_INTEGRATION_GUIDE.md` | Wavelet+PEAD setup |
| `AUTOMATION_GUIDE.md` | Cron automation |
| `EC2_DEPLOYMENT_RUNBOOK.md` | EC2 deployment guide |
| `IB_KEY_AUTO_LOGIN_GUIDE.md` | IBKR auto-login setup |

---

## ⚙️ Configuration

### Optimal Weights (LOCKED)

```python
WEIGHT_WAVELET = 0.54  # 54%
WEIGHT_PEAD = 0.46     # 46%
LAMBDA_OVERLAY = 1.0   # 100% overlay
MAX_TILT = 0.02        # ±2% cap per symbol
```

### Automation (Cron)

```bash
# Daily execution at US market open (UTC 14:30)
30 14 * * 1-5 /home/ubuntu/ares7-ensemble/run_full_pipeline.sh >> /home/ubuntu/ares7-ensemble/logs/cron_full_pipeline.log 2>&1
```

---

## 🔒 Security

**⚠️ Important**: This repository contains **code only**. Sensitive data is excluded:

- ❌ API keys / credentials
- ❌ PEM keys
- ❌ Log files
- ❌ Actual market data (sample data only)

---

## 📊 Dashboard

**Real-time monitoring dashboard** (Flask + HTML):

- Portfolio stats (leverage, exposure, regime)
- Top 5 positions (final weight, base, tilt)
- All 50 symbols with weights
- Kill switch control

**Access**: `http://EC2_IP:5000`

---

## 🤖 IBKR Integration

### Auto-Login (IBC + IB Key)

```bash
# Start IB Gateway with auto-login
./start_ibc_simple.sh
```

### API Connection

```python
# Test IBKR API connection
python3 ibkr_connect.py
```

**Port**: 4001 (Paper Trading)

---

## 🛠️ Development

### R&D Tools

```bash
# Optimize weights (Train+Val)
python3 run_wavelet_pead_optimizer.py

# Evaluate performance
python3 run_wavelet_pead_prod.py

# Backtest PEAD only
python3 run_pead_prod.sh
```

### Testing

```bash
# Generate sample data
python3 generate_sample_pnl.py
python3 generate_sample_overlays.py
python3 generate_sample_base_weights.py

# Test overlay combiner
python3 run_wavelet_pead_overlay_prod.py

# Test integration
python3 ares7_integrate_overlay.py
```

---

## 📈 Legacy 4-Way Ensemble

### Composition

| Engine | Sharpe | Return | Vol | MDD | Weight | Type |
|:---|---:|---:|---:|---:|---:|:---|
| **A+LS Enhanced** | 0.947 | 14.96% | 16.46% | -27.62% | 30% | Trend Following |
| **C1 Final v5** | 0.715 | 8.96% | 13.24% | -32.80% | 20% | Mean Reversion |
| **Low-Vol v2** | 0.809 | 11.75% | 14.53% | -27.31% | 20% | Defensive |
| **Factor (Value)** | 0.555 | 8.33% | 15.02% | -33.24% | 30% | Long-Short |

### Correlation Matrix

```
              A+LS    C1     LV2   Factor
A+LS         1.000  0.007  0.815   0.082
C1           0.007  1.000  0.033   0.017
LV2          0.815  0.033  1.000  -0.082
Factor       0.082  0.017 -0.082   1.000
```

---

## 🎓 Key Insights

1. **Structure > Parameters**: Pure Tilt structure is 34x more effective than parameter tuning
2. **PEAD Only Sufficient**: Buyback adds minimal improvement (+0.006)
3. **Wavelet+PEAD Synergy**: 54/46 split achieves Test Sharpe 0.775
4. **100% Overlay Works**: λ=1.0 from start with risk guards (±2% cap)
5. **Train Negative OK**: Val/Test strong indicates good generalization

---

## 🏆 Project Milestones

- ✅ **Phase 1**: 4-Way Ensemble (Sharpe 1.36)
- ✅ **Phase 2**: PEAD Only (Test Sharpe 0.504)
- ✅ **Phase 3**: Wavelet+PEAD Optimizer (Test Sharpe 0.775)
- ✅ **Phase 4**: λ=1.0 Integration (Base+Overlay 0.990)
- ✅ **Phase 5**: EC2 Deployment + Automation
- ✅ **Phase 6**: Dashboard + IBKR Integration
- ✅ **Phase 7**: GitHub Backup ✨

---

## 📞 Support

- **GitHub Issues**: https://github.com/yhun1542/ares7-wavelet-pead-ensemble/issues
- **Documentation**: See `*.md` files in repository

---

## 📝 License

MIT License

---

## 📧 Contact

**Author**: Jason (yhun1542)  
**GitHub**: [@yhun1542](https://github.com/yhun1542)

---

**Last Updated**: 2025-12-01  
**EC2 Deployment**: 3.35.141.47  
**Repository**: https://github.com/yhun1542/ares7-wavelet-pead-ensemble  
**Version**: 2.0.0 (Wavelet+PEAD)  
**Status**: ✅ Production Ready
