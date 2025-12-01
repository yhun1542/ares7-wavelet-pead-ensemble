# engines/low_volatility_v2.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class LowVolConfig:
    top_quantile: float = 0.3       # 저위험 상위 비율 (0.3 → 상위 30% 롱)
    long_gross: float = 1.0         # 롱 총합
    use_inverse_vol: bool = True    # inverse vol weighting 사용 여부
    vol_lookback: int = 63          # 변동성 lookback (일수)
    beta_lookback: int = 252        # 베타 lookback
    use_beta: bool = True           # 베타를 risk_score에 포함할지 여부
    downside_weight: float = 0.5    # 다운사이드 변동성 가중치
    beta_weight: float = 0.5        # |beta| 가중치


class LowVolEnhancedEngine:
    """
    저변동/Defensive 엔진 v2.
    - 가격 + SPX 기준으로 변동성/다운사이드/베타 팩터를 계산하고
      risk_score가 낮은 종목(안전한 종목)을 롱한다.
    """

    def __init__(self, cfg: Optional[LowVolConfig] = None):
        self.cfg = cfg or LowVolConfig()

    def _calc_factors(
        self,
        prices: pd.DataFrame,
        spx_close: pd.Series,
    ) -> pd.DataFrame:
        # 정렬 및 align
        prices = prices.sort_index()
        spx_close = spx_close.sort_index()
        spx_close = spx_close.reindex(prices.index, method="ffill")

        ret = prices.pct_change()
        spx_ret = spx_close.pct_change()

        vol_63d = ret.rolling(self.cfg.vol_lookback).std()

        down_ret = ret.copy()
        down_ret[down_ret > 0] = 0.0
        down_vol_63d = down_ret.rolling(self.cfg.vol_lookback).std()

        if self.cfg.use_beta:
            cov = ret.rolling(self.cfg.beta_lookback).cov(spx_ret)
            var_spx = spx_ret.rolling(self.cfg.beta_lookback).var()
            var_spx_df = pd.DataFrame(
                {col: var_spx for col in ret.columns},
                index=ret.index,
            )
            beta = cov / var_spx_df
        else:
            beta = pd.DataFrame(0.0, index=ret.index, columns=ret.columns)

        df = pd.DataFrame(
            index=pd.MultiIndex.from_product(
                [prices.index, prices.columns],
                names=["date", "ticker"],
            )
        )
        df["vol_63d"] = vol_63d.stack()
        df["down_vol_63d"] = down_vol_63d.stack()
        df["beta"] = beta.stack()
        return df

    @staticmethod
    def _xsec_zscore(s: pd.Series) -> pd.Series:
        def _z(x: pd.Series) -> pd.Series:
            x = x.replace([np.inf, -np.inf], np.nan)
            if x.isna().all():
                return pd.Series(0.0, index=x.index)
            std = x.std(ddof=0)
            if std == 0 or np.isnan(std):
                return pd.Series(0.0, index=x.index)
            return (x - x.mean()) / std

        out = s.groupby(level="date").transform(_z)
        return out.fillna(0.0)

    def build_signals(
        self,
        prices: pd.DataFrame,
        spx_close: pd.Series,
    ) -> pd.Series:
        """
        risk_score (낮을수록 안전)를 반환.
        index: (date, ticker)
        """
        f = self._calc_factors(prices, spx_close)

        z_vol = self._xsec_zscore(f["vol_63d"])
        z_down = self._xsec_zscore(f["down_vol_63d"])
        z_beta = self._xsec_zscore(f["beta"].abs()) if self.cfg.use_beta else 0.0

        risk_raw = (
            z_vol +
            self.cfg.downside_weight * z_down +
            self.cfg.beta_weight * z_beta
        )
        risk_score = self._xsec_zscore(risk_raw)
        return risk_score.rename("risk_score")

    def build_portfolio(
        self,
        prices: pd.DataFrame,
        spx_close: pd.Series,
        rebalance_dates: List[pd.Timestamp],
    ) -> Dict[pd.Timestamp, pd.Series]:
        """
        prices: index=date, columns=tickers
        spx_close: S&P 500 or SPY close, index=date
        rebalance_dates: 리밸 날짜 리스트

        반환: {date: weight Series(ticker → weight)}
        """
        risk_score = self.build_signals(prices, spx_close)
        returns = prices.pct_change()
        vol = returns.rolling(self.cfg.vol_lookback).std()

        weights_by_date: Dict[pd.Timestamp, pd.Series] = {}

        for d in rebalance_dates:
            if d not in risk_score.index.get_level_values("date"):
                continue
            if d not in vol.index:
                continue

            cs = risk_score.loc[d].dropna()
            if cs.empty:
                continue

            n = len(cs)
            n_long = max(int(n * self.cfg.top_quantile), 1)

            cs_sorted = cs.sort_values(ascending=True)  # 낮을수록 안전
            long_names = cs_sorted.head(n_long).index

            if self.cfg.use_inverse_vol:
                vols_long = vol.loc[d, long_names]
                inv_long = 1.0 / vols_long
                inv_long = inv_long.replace([np.inf, -np.inf], np.nan).dropna()
                if inv_long.empty:
                    continue
                w_raw = inv_long
            else:
                w_raw = pd.Series(1.0, index=long_names)

            w_long = w_raw / w_raw.sum() * self.cfg.long_gross
            weights_by_date[d] = w_long

        return weights_by_date
