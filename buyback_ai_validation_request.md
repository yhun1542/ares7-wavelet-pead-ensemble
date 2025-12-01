# Buyback Event Research - AI Validation Request

## 📋 Executive Summary

We conducted a buyback event research on SP100 stocks (10 tickers test) and need validation + improvement suggestions from AI models.

## 🎯 Research Objective

Validate whether **buyback announcements** (8-K filings) generate **positive excess returns** and can be used as an **alpha signal** for overlay strategies.

## 📊 Current Results

### Data
- **Events**: 260 total, 196 bb_top (top 10% by amount)
- **Valid Returns**: 175 events (128 bb_top)
- **Tickers**: 9 (AAPL, MSFT, GOOGL, JPM, CVX, JNJ, XOM, BAC, PFE)
  - Note: BAC, PFE missing in price data
- **Horizons**: 10d, 20d, 40d forward returns

### Event-Level Performance

| Split | Horizon | N Events | Mean Excess Ret | Sharpe | t-stat | Win Rate | p-value |
|-------|---------|----------|-----------------|--------|--------|----------|---------|
| **Train** | 10d | 44 | +0.0061 | +0.154 | 1.02 | 50.0% | 0.265 |
| **Train** | 20d | 44 | +0.0024 | +0.058 | 0.39 | 54.5% | 0.275 |
| **Train** | 40d | 44 | +0.0081 | **+0.175** | 1.16 | 54.5% | **0.140** |
| **Val** | 10d | 17 | +0.0100 | +0.228 | 0.94 | 41.2% | 0.610 |
| **Val** | 20d | 17 | -0.0077 | -0.180 | -0.74 | 41.2% | 0.620 |
| **Val** | 40d | 17 | +0.0056 | +0.125 | 0.51 | 47.1% | 0.560 |
| **Test** | 10d | 67 | +0.0021 | +0.045 | 0.37 | 53.7% | **0.905** |
| **Test** | 20d | 67 | +0.0030 | +0.063 | 0.52 | 56.7% | 0.725 |
| **Test** | 40d | 67 | +0.0058 | +0.058 | 0.47 | 52.2% | **0.935** |

### Key Findings

✅ **Positive**:
- Train 40d shows strongest alpha (Sharpe +0.175, p-value 0.140)
- All Train horizons show positive Sharpe
- Val 10d shows strong Sharpe (+0.228)

⚠️ **Negative**:
- **Test p-values very high (0.73-0.94)** → likely random
- Val 20d shows negative Sharpe
- Overall statistical significance is weak
- Much weaker than PEAD (Test Sharpe +2.726 vs +0.046)

## 🔧 Implementation Details

### Event Builder
```python
def build_buyback_events(raw_bb_df, price_index, split_cfg, use_mc_ratio=False):
    # 1. Date normalization
    df['event_date'] = pd.to_datetime(df['filing_date']).dt.normalize()
    
    # 2. Filter: event_date in price_index
    df = df[df['event_date'].isin(price_index)]
    
    # 3. Signal strength (absolute amount)
    df['signal_strength'] = df['amount_usd']
    
    # 4. Cross-sectional rank (within each event_date)
    df['signal_rank'] = df.groupby('event_date')['signal_strength'].rank(pct=True)
    
    # 5. Bucket assignment (top 10% = bb_top)
    df['bucket'] = df['signal_rank'].apply(lambda r: 'bb_top' if r >= 0.9 else 'neutral')
```

### Forward Return Calculation
- Cumulative returns over horizon (t+1 to t+h)
- Excess return = stock return - benchmark return
- Benchmark = equal-weight average of all stocks (ffill to handle NaN)

### Label Shuffle Test
- 200 iterations
- Shuffle signal_rank within each event_date
- Calculate p-value: P(shuffled >= observed)

## 🤔 Questions for AI Models

### 1. **Result Validation**
- Are the results statistically valid?
- Is the Test p-value (0.73-0.94) a red flag?
- Should we proceed with this signal?

### 2. **Methodology Issues**
- Is the event definition correct (8-K filings)?
- Should we use amount/marketcap ratio instead of absolute amount?
- Is the benchmark (equal-weight) appropriate?
- Is the label shuffle test correctly implemented?

### 3. **Improvement Suggestions**
- How to improve Test performance?
- Should we filter events by other criteria (e.g., minimum amount, sector)?
- Should we use different horizons?
- Should we combine with other signals (PEAD)?

### 4. **Next Steps**
- Should we expand to full SP100 (93 more tickers)?
- Should we implement PEAD+Buyback ensemble immediately?
- What weight should Buyback have in ensemble (current: 40%)?

## 📁 Attached Files

1. `buyback_research_event_stats.csv` - Event-level summary
2. `buyback_research_label_shuffle.csv` - Label shuffle p-values
3. `data/buyback_events.csv` - Full event table
4. `research/pead/run_buyback_research.py` - Research script

## 🎯 Expected Output from AI Models

Please provide:
1. **Validation**: Is the methodology sound? Are results trustworthy?
2. **Red Flags**: Any critical issues we missed?
3. **Improvements**: Top 3 actionable suggestions
4. **Decision**: Proceed with ensemble or abandon Buyback signal?
5. **Rationale**: Detailed reasoning for your recommendation

---

**Note**: This is a follow-up to our PEAD research which achieved:
- PEAD Test Sharpe: +2.726 (very strong)
- PEAD Combined Sharpe: 0.958 (target achieved)

We're exploring whether Buyback can **complement** PEAD or should be **abandoned**.
