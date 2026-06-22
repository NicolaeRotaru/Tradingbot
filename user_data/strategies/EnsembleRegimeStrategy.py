# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
EnsembleRegimeStrategy — il bot "potenziato" a COMMUTAZIONE DI REGIME.

Realizza l'obiettivo nel modo serio (non con promesse da backtest overfittato):
  - SALE con forza  -> modulo TREND-LONG: cavalca e tiene fino in fondo (Chandelier ATR)
  - SCENDE con forza -> modulo TREND-SHORT (opzionale, off di default: su SOL peggiora)
  - PIATTO/laterale  -> modulo MEAN-REVERSION long/short: compra basso, vende alto

Un classificatore di regime (ADX + Efficiency Ratio + EMA50/200) decide quale modulo
e' attivo. Sizing e rischio sono nel motore di Freqtrade (stake + protezioni) e nella
Chandelier; il vol-targeting/Kelly del backtest qui si traducono in stake prudente +
leva 1x. Mantiene live ≈ backtest: stessa logica, stessi indicatori della ricerca in
research/ (validata walk-forward out-of-sample su SOL/BTC/ETH 1h).

⚠️ Avvia SEMPRE in dry-run. Il win-rate del trend-following e' basso (~25-30%): poche
vincite grandi. Nessuna strategia "vince sempre"; questa massimizza il Calmar robusto.
"""
from datetime import datetime

import numpy as np
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.strategy import IStrategy, stoploss_from_absolute


class EnsembleRegimeStrategy(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # ===== INTERRUTTORI =====
    enable_shorts = False   # short di trend: su SOL peggiora (vedi ricerca). Attivabile su asset bidirezionali.
    enable_mr = True        # mean-reversion nelle fasi laterali (compra basso / vende alto)

    # ===== parametri regime =====
    adx_trend = 22.0
    er_trend = 0.30
    # ===== modulo trend =====
    chandelier_long = 5.0   # stop = max_rate - 5*ATR
    chandelier_short = 3.5  # stop = min_rate + 3.5*ATR (gli short rimbalzano: piu' stretto)
    # ===== modulo mean-reversion =====
    mr_rsi_lo = 32.0
    mr_rsi_hi = 68.0
    mr_exit_lo = 45.0
    mr_exit_hi = 55.0
    mr_stop = 0.02          # hard stop dei trade mean-reversion (2% su 15m: 1:1 R:R col target)

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = True   # non uscire in perdita per segnale: aspetta ROI 1% o stop
    startup_candle_count = 700   # EMA400 + buffer protections su 15m

    minimal_roi = {"0": 0.01}     # chiudi a +1% di profitto su qualsiasi trade
    stoploss = -0.05              # rete di sicurezza: max -5% se tutto il resto fallisce
    use_custom_stoploss = True
    trailing_stop = False

    order_types = {
        "entry": "limit", "exit": "limit",
        "stoploss": "market", "stoploss_on_exchange": False,
    }

    leverage_num = 1.0

    plot_config = {
        "main_plot": {
            "ema50": {"color": "orange"}, "ema200": {"color": "blue"},
            "bb_low": {"color": "grey"}, "bb_up": {"color": "grey"},
        },
        "subplots": {
            "ADX": {"adx": {"color": "red"}},
            "Efficiency Ratio": {"er": {"color": "green"}},
            "Regime": {"regime": {"color": "purple"}},
        },
    }

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return self.leverage_num

    @property
    def protections(self):
        # periodi scalati per 15m: 1h*4 = 4 candele da 15m per ogni ora
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 12},   # 3h
            {"method": "MaxDrawdown", "lookback_period_candles": 672,
             "trade_limit": 6, "stop_duration_candles": 288, "max_allowed_drawdown": 0.25},
            {"method": "StoplossGuard", "lookback_period_candles": 192,
             "trade_limit": 3, "stop_duration_candles": 96, "only_per_pair": False},
        ]

    # ---------------- INDICATORI ----------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        d["ema50"] = ta.EMA(d, timeperiod=50)
        d["ema200"] = ta.EMA(d, timeperiod=200)
        d["ema400"] = ta.EMA(d, timeperiod=400)
        d["rsi"] = ta.RSI(d, timeperiod=14)
        d["atr"] = ta.ATR(d, timeperiod=14)
        d["adx"] = ta.ADX(d, timeperiod=14)
        # Bollinger 20,2
        mid = d["close"].rolling(20).mean()
        std = d["close"].rolling(20).std(ddof=0)
        d["bb_mid"] = mid
        d["bb_low"] = mid - 2.0 * std
        d["bb_up"] = mid + 2.0 * std
        # Efficiency Ratio (Kaufman) su 96 barre (= 24h su 15m): "trendiness" 0..1
        change = (d["close"] - d["close"].shift(96)).abs()
        vol = d["close"].diff().abs().rolling(96).sum()
        d["er"] = (change / vol.replace(0.0, np.nan)).fillna(0.0)
        # Regime: +1 trend-up, -1 trend-down, 0 range
        is_trend = (d["adx"] > self.adx_trend) & (d["er"] > self.er_trend)
        d["regime"] = 0
        d.loc[is_trend & (d["ema50"] > d["ema200"]) & (d["close"] > d["ema200"]), "regime"] = 1
        d.loc[is_trend & (d["ema50"] < d["ema200"]) & (d["close"] < d["ema200"]), "regime"] = -1
        return dataframe

    # ---------------- INGRESSI ----------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        # TREND LONG: regime rialzista
        d.loc[(d["regime"] == 1) & (d["volume"] > 0), ["enter_long", "enter_tag"]] = (1, "trend_long")

        # MEAN-REVERSION LONG: range + ipervenduto + sopra EMA200 (compra il ribasso in uptrend)
        if self.enable_mr:
            d.loc[
                (d["regime"] == 0) & (d["close"] < d["bb_low"]) & (d["rsi"] < self.mr_rsi_lo)
                & (d["close"] > d["ema200"]) & (d["volume"] > 0),
                ["enter_long", "enter_tag"],
            ] = (1, "mr_long")

        if self.enable_shorts:
            # TREND SHORT: regime ribassista MACRO confermato
            d.loc[
                (d["regime"] == -1) & (d["close"] < d["ema400"]) & (d["volume"] > 0),
                ["enter_short", "enter_tag"],
            ] = (1, "trend_short")
            if self.enable_mr:
                # MEAN-REVERSION SHORT: range + ipercomprato + sotto EMA200 (vende il rialzo in downtrend)
                d.loc[
                    (d["regime"] == 0) & (d["close"] > d["bb_up"]) & (d["rsi"] > self.mr_rsi_hi)
                    & (d["close"] < d["ema200"]) & (d["volume"] > 0),
                    ["enter_short", "enter_tag"],
                ] = (1, "mr_short")
        return dataframe

    # ---------------- USCITE A SEGNALE (la Chandelier la fa custom_stoploss) ----------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        # trend long: esce quando il prezzo perde la EMA200
        d.loc[(d["regime"] != 1) & (d["close"] < d["ema200"]) & (d["volume"] > 0), "exit_long"] = 1
        if self.enable_shorts:
            d.loc[(d["regime"] != -1) & (d["close"] > d["ema200"]) & (d["volume"] > 0), "exit_short"] = 1
        return dataframe

    # ---------------- USCITA MEAN-REVERSION (ritorno alla media) ----------------
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if not str(trade.enter_tag or "").startswith("mr"):
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        last = df.iloc[-1]
        if trade.is_short:
            if current_rate <= last["bb_mid"] or last["rsi"] < self.mr_exit_lo:
                return "mr_target"
        else:
            if current_rate >= last["bb_mid"] or last["rsi"] > self.mr_exit_hi:
                return "mr_target"
        return None

    # ---------------- STOP: Chandelier (trend) / hard stop (mean-reversion) ----------------
    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, **kwargs):
        tag = str(trade.enter_tag or "")
        if tag.startswith("mr"):
            # mean-reversion: stop fisso (frazione), gestito come stoploss relativo
            return -self.mr_stop if not trade.is_short else -self.mr_stop
        # trend: Chandelier ATR
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        atr = df["atr"].iat[-1]
        if atr is None or atr != atr or atr <= 0:
            return None
        if trade.is_short:
            stop_price = trade.min_rate + self.chandelier_short * atr
        else:
            stop_price = trade.max_rate - self.chandelier_long * atr
        return stoploss_from_absolute(
            stop_price, current_rate, is_short=trade.is_short, leverage=trade.leverage)
