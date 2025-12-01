# ARES-7 Ensemble Trading System

**High-Performance Quantitative Trading System achieving Sharpe Ratio 1.36**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## 🎯 Overview

ARES-7 is a sophisticated quantitative trading ensemble system that combines multiple uncorrelated strategies to achieve superior risk-adjusted returns.

**Key Performance Metrics (4-Way Ensemble with Vol Target 12%):**
- **Sharpe Ratio**: 1.3588
- **Annual Return**: 16.36%
- **Annual Volatility**: 12.04%
- **Maximum Drawdown**: -13.46%

---

## 📊 System Architecture

### 4-Way Ensemble Composition

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

**Key Insight**: Low correlation between engines (especially C1 and Factor) enables strong diversification benefits.

---

## 🚀 Quick Start

### Prerequisites

```bash
Python 3.11+
pandas
numpy
statsmodels
sklearn
```

### Installation

```bash
git clone https://github.com/yhun1542/ares7-ensemble.git
cd ares7-ensemble
pip install -r requirements.txt
```

### Running 4-Way Ensemble

```bash
# With Vol Targeting (12%)
python3.11 ensemble_4way_vol_target.py
```

---

## 📈 Performance Analysis

**Diversification Effect**: +68.4%
- Individual engines: Sharpe 0.55-0.95
- 4-Way Ensemble: Sharpe 1.36
- Improvement: 43-147% over individual engines

**Risk Reduction**:
- Individual MDD: -27% to -33%
- Ensemble MDD: -13.46%
- Improvement: 50-59% reduction

---

## 📚 Documentation

See `docs/` directory for detailed documentation.

---

## 📝 License

MIT License

---

## 📧 Contact

**Author**: Jason (yhun1542)  
**GitHub**: [@yhun1542](https://github.com/yhun1542)

---

**Last Updated**: 2025-11-26  
**Version**: 1.0.0  
**Status**: ✅ Production Ready
