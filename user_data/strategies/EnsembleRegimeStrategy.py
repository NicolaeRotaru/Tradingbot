# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
EnsembleRegimeStrategy — bot a commutazione di regime, 15m, SOL/USD:USD.

  REGIME  0  (laterale): MEAN-REVERSION
    Ingresso : close < bb_mid  +  RSI < 42  +  candela verde  +  RSI in recupero
    Uscita TP: prezzo raggiunge bb_up (linea VERDE)  O  RSI > 65  [i cerchi!]
    Stop     : −2% dall'ingresso (linea ROSSA tratteggiata)

  REGIME +1  (trend su): TREND-LONG
    Ingresso : regime == 1
    Uscita   : Chandelier trailing stop (linea ROSSA continua sul grafico)
    Stop rif.: max_close − 5×ATR

  Sul grafico:
    VERDE  bb_up        = dove il bot chiude in profitto i trade MR (take-profit)
    ROSSO  chan_stop     = dove scatta lo stop dei trade di trend (Chandelier)
    Grigio bb_low/bb_mid = zona di ingresso MR
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
    enable_shorts = False
    enable_mr = True

    # ===== parametri regime =====
    adx_trend = 15.0
    er_trend = 0.20

    # ===== modulo trend =====
    chandelier_long = 5.0    # stop = max_close - 5*ATR  (linea rossa sul grafico)
    chandelier_short = 3.5

    # ===== modulo mean-reversion =====
    mr_rsi_lo = 42.0         # RSI sotto questa soglia = dip → ingresso
    mr_rsi_hi = 65.0         # RSI sopra questa soglia = overbought → TP (i cerchi)
    mr_rsi_lo_exit = 35.0    # RSI per uscita short MR
    mr_stop = 0.02           # stop MR: −2%

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = True
    startup_candle_count = 700

    # custom_exit vende a bb_up se profit >= 1% (punta a 1.5-3%).
    # Fallback: dopo 2h (8 candele 15m) accetta qualsiasi +1%.
    minimal_roi = {"0": 100.0, "120": 0.01}
    stoploss = -0.05
    use_custom_stoploss = True
    trailing_stop = False

    order_types = {
        "entry": "limit", "exit": "limit",
        "stoploss": "market", "stoploss_on_exchange": False,
    }

    leverage_num = 1.0

    plot_config = {
        "main_plot": {
            "ema50":     {"color": "orange"},
            "ema200":    {"color": "#4477ff"},           # blu = EMA lenta (filtro trend)
            "bb_low":    {"color": "#666666"},           # grigio scuro = zona ingresso MR
            "bb_mid":    {"color": "#999999"},           # grigio = media BB
            "bb_up":     {"color": "#00dd55"},           # VERDE = linea take-profit MR ← i cerchi!
            "chan_stop":  {"color": "#ff3333"},           # ROSSO = trailing stop trend (Chandelier)
        },
        "subplots": {
            "ADX / ER": {
                "adx": {"color": "#dd2222"},
                "er":  {"color": "#22cc22"},
            },
            "Regime (+1 trend / 0 range / -1 down)": {
                "regime": {"color": "#bb44ff"},
            },
        },
    }

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return self.leverage_num

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 12},
            {"method": "MaxDrawdown", "lookback_period_candles": 672,
             "trade_limit": 6, "stop_duration_candles": 288, "max_allowed_drawdown": 0.25},
            {"method": "StoplossGuard", "lookback_period_candles": 192,
             "trade_limit": 3, "stop_duration_candles": 96, "only_per_pair": False},
        ]

    # ---------------- INDICATORI ----------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        d["ema50"]  = ta.EMA(d, timeperiod=50)
        d["ema200"] = ta.EMA(d, timeperiod=200)
        d["ema400"] = ta.EMA(d, timeperiod=400)
        d["rsi"]    = ta.RSI(d, timeperiod=14)
        d["atr"]    = ta.ATR(d, timeperiod=14)
        d["adx"]    = ta.ADX(d, timeperiod=14)

        # Bollinger 20,2
        mid = d["close"].rolling(20).mean()
        std = d["close"].rolling(20).std(ddof=0)
        d["bb_mid"] = mid
        d["bb_low"] = mid - 2.0 * std
        d["bb_up"]  = mid + 2.0 * std          # ← LINEA VERDE take-profit MR

        # Efficiency Ratio 96 barre = 24h su 15m
        change = (d["close"] - d["close"].shift(96)).abs()
        vol    = d["close"].diff().abs().rolling(96).sum()
        d["er"] = (change / vol.replace(0.0, np.nan)).fillna(0.0)

        # Chandelier trailing stop (LINEA ROSSA): max(high,14) − 5×ATR
        # Mostra dove il trade di trend verrebbe stoppato se il prezzo scende fin lì.
        d["chan_stop"] = d["high"].rolling(14).max() - self.chandelier_long * d["atr"]

        # Regime: +1 trend-su, −1 trend-giù, 0 laterale
        is_trend = (d["adx"] > self.adx_trend) & (d["er"] > self.er_trend)
        d["regime"] = 0
        d.loc[is_trend & (d["ema50"] > d["ema200"]) & (d["close"] > d["ema200"]), "regime"] =  1
        d.loc[is_trend & (d["ema50"] < d["ema200"]) & (d["close"] < d["ema200"]), "regime"] = -1
        return dataframe

    # ---------------- INGRESSI ----------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe

        # TREND LONG: regime rialzista
        d.loc[(d["regime"] == 1) & (d["volume"] > 0), ["enter_long", "enter_tag"]] = (1, "trend_long")

        # MEAN-REVERSION LONG: compra il dip quando il mercato è laterale (regime 0).
        #   regime == 0   → non in trend forte (nè su nè giù)
        #   close < bb_mid → metà bassa del canale = "compra basso"
        #   rsi < 42       → dip moderato (non serve ipervenduto estremo)
        #   close > open   → candela verde = rimbalzo già iniziato, non coltello che cade
        #   rsi > rsi[-2]  → RSI sta risalendo dal minimo (conferma della svolta)
        if self.enable_mr:
            d.loc[
                (d["regime"] == 0)
                & (d["close"] < d["bb_mid"])
                & (d["rsi"] < self.mr_rsi_lo)
                & (d["close"] > d["open"])
                & (d["rsi"] > d["rsi"].shift(2))
                & (d["volume"] > 0),
                ["enter_long", "enter_tag"],
            ] = (1, "mr_long")

        if self.enable_shorts:
            d.loc[
                (d["regime"] == -1) & (d["close"] < d["ema400"]) & (d["volume"] > 0),
                ["enter_short", "enter_tag"],
            ] = (1, "trend_short")
            if self.enable_mr:
                d.loc[
                    (d["regime"] == 0) & (d["close"] > d["bb_up"]) & (d["rsi"] > self.mr_rsi_hi)
                    & (d["close"] < d["ema200"]) & (d["volume"] > 0),
                    ["enter_short", "enter_tag"],
                ] = (1, "mr_short")
        return dataframe

    # ---------------- USCITE A SEGNALE ----------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe
        # Esce solo quando il regime diventa FORTEMENTE RIBASSISTA (-1).
        # Prima era "regime != 1" → scattava su quasi ogni candela (781 exit sul grafico!).
        # Ora è "regime == -1" → si attiva solo nei veri trend giù confermati.
        d.loc[(d["regime"] == -1) & (d["volume"] > 0), "exit_long"] = 1
        if self.enable_shorts:
            d.loc[(d["regime"] == 1) & (d["volume"] > 0), "exit_short"] = 1
        return dataframe

    # ---------------- TAKE-PROFIT MR (i cerchi!) ----------------
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if not str(trade.enter_tag or "").startswith("mr"):
            return None  # i trade di trend vengono gestiti da Chandelier

        # non uscire finché non siamo almeno a +1%: il target è bb_up, non un micro-gain
        if current_profit < 0.010:
            return None

        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        last = df.iloc[-1]

        if not trade.is_short:
            # TP LONG MR: prezzo raggiunge la banda VERDE superiore  ← I CERCHI
            #             OPPURE RSI diventa overbought (>65)
            if current_rate >= last["bb_up"] or last["rsi"] > self.mr_rsi_hi:
                return "mr_tp"
        else:
            # TP SHORT MR: prezzo scende alla banda inferiore o RSI < 35
            if current_rate <= last["bb_low"] or last["rsi"] < self.mr_rsi_lo_exit:
                return "mr_tp"
        return None

    # ---------------- STOP: Chandelier (trend) / −2% (MR) ----------------
    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, **kwargs):
        tag = str(trade.enter_tag or "")
        if tag.startswith("mr"):
            return -self.mr_stop  # stop fisso −2%

        # trend: Chandelier ATR trailing
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
