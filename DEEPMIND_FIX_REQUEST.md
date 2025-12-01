# DeepMind Enhanced v1 수정 요청

## 현재 상황

DeepMind Enhanced v1 엔진 실행 중 다음 오류 발생:

### 오류 1: DataFrame.to_frame() 오류
```
AttributeError: 'DataFrame' object has no attribute 'to_frame'
```

**위치**: `engine_enhanced_v1_deepmind.py`, line 282
```python
combined_alpha_series = self.constructor.combine_signals(current_signals.to_frame().T)
```

**문제**: `current_signals`가 이미 DataFrame인데 `.to_frame()`을 호출

**수정 필요**: 
- `current_signals`가 Series인지 DataFrame인지 확인
- Series일 경우만 `.to_frame()` 호출
- 또는 `.to_frame()` 제거

### 오류 2: argparse import 누락
```
NameError: name 'argparse' is not defined
```

**위치**: `engine_enhanced_v1_deepmind.py`, line 448
```python
parser = argparse.ArgumentParser(description='ARES-7 Enhanced Engine v1 (DeepMind)')
```

**문제**: `import argparse` 누락

**수정 필요**: 파일 상단에 `import argparse` 추가

---

## 요청 사항

**완전히 수정된 `engine_enhanced_v1_deepmind.py` 전체 코드 제공**

### 요구사항:
1. ✅ 위 2개 오류 수정
2. ✅ Look-ahead bias 제거 확인
3. ✅ 다음 인자로 실행 가능:
   ```bash
   python3.11 engine_enhanced_v1_deepmind.py \
     --price data/price_full.csv \
     --output results/engine_enhanced_v1_deepmind.json
   ```
4. ✅ JSON 출력 형식:
   ```json
   {
     "sharpe": 0.0,
     "annual_return": 0.0,
     "annual_volatility": 0.0,
     "max_drawdown": 0.0,
     "daily_returns": [...]
   }
   ```

### 데이터 형식:
- `data/price_full.csv`: timestamp, symbol, close (100 종목, 2512일)
- timestamp: 2015-01-05 ~ 2024-12-31

### 목표 성능:
- Sharpe: 0.8-1.2
- 기존 4개 엔진과 낮은 상관관계 (< 0.3)

---

## 원본 코드 위치

`/home/ubuntu/ares7_ensemble/engine_enhanced_v1_deepmind.py`

---

## 참고: 기존 엔진 성능

| 엔진 | Sharpe | Return | Vol | MDD |
|:---|---:|---:|---:|---:|
| A+LS Enhanced | 0.909 | 14.96% | 16.46% | -27.62% |
| C1 Final v5 | 0.677 | 8.96% | 13.24% | -32.80% |
| Low-Vol v2 | 0.809 | 11.75% | 14.53% | -27.31% |
| Factor (Value) | 0.555 | 8.33% | 15.02% | -33.24% |

**4-Way Ensemble**: Sharpe 1.36, Return 16.36%, Vol 12.04%, MDD -13.46%

---

## 기대 결과

DeepMind Enhanced v1이 5번째 엔진으로 추가되어:
- **5-Way Ensemble**: Sharpe 1.5-1.6 달성
- **상관관계**: 기존 엔진들과 < 0.3

---

**작성자**: Jason (with Manus AI)  
**날짜**: 2025-11-26  
**우선순위**: 🔥 긴급
