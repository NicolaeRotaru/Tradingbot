# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
EnsembleRegimeStrategy — bot a commutazione di regime, 15m, SOL/USD:USD.

  USCITA — sistema a DUE LINEE, IDENTICO per OGNI trade long:
    TAKE-PROFIT : il prezzo tocca la linea VERDE (bb_up) con almeno +0.3% → chiude in GUADAGNO
    STOP-LOSS   : il prezzo scende alla linea ROSSA (close - 3×ATR)       → chiude in PERDITA

  INGRESSO — "V-BOUNCE": compra la PRIMA candela verde dopo un dip. Due strade:
    A) DIP & RIMBALZO  : c'è stato un dip negli ultimi 3 (minimo sul fondo o RSI
                         ipervenduto) e ORA gira su → prende anche le V veloci.
    B) PULLBACK in UP  : in uptrend confermato, storno leggero (RSI<50) che rimbalza.
    In un trend senza storni NON entra (niente muro di ingressi): uno per ogni ribasso.

  Sul grafico:
    VERDE  bb_up         = linea di TAKE-PROFIT (dove chiude in PROFITTO)
    ROSSO  chan_stop     = linea di STOP-LOSS   (dove chiude in PERDITA)
    Grigio bb_low/bb_mid = zona di ingresso del dip
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
    enable_shorts = False    # short disattivati: su SOL peggiorano (vedi ricerca)

    # ===== parametri regime =====
    adx_trend = 15.0
    er_trend = 0.20

    # ===== stop-loss (linea ROSSA, uguale per tutti i trade) =====
    chandelier_long = 3.0    # stop = max_close - 3*ATR (linea rossa). Stretto = rischio ~1-2% per scalp 1%
    chandelier_short = 3.0

    # ===== soglie RSI =====
    mr_rsi_lo = 42.0         # RSI sotto questa soglia = dip → ingresso
    mr_rsi_hi = 65.0         # RSI sopra questa soglia = overbought → take-profit (i cerchi)
    mr_rsi_lo_exit = 35.0    # RSI per uscita short

    # ===== V-Bounce: catturare PIÙ "V" (le entrate che azzeccano) =====
    dip_lookback = 3         # candele indietro in cui cercare il dip (per le V veloci)
    dip_rsi = 40.0           # RSI ipervenduto nel lookback = "c'è stato un vero dip"
    trend_pull_rsi = 50.0    # in uptrend i pullback sono leggeri: RSI più alto consentito

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = True
    startup_candle_count = 700

    # custom_exit vende a bb_up se profit >= 0.3% (copre fees, punta a 1.5-3%).
    # Fallback: dopo 2h (8 candele 15m) accetta qualsiasi +0.5%.
    minimal_roi = {"0": 100.0, "120": 0.005}
    stoploss = -0.05
    use_custom_stoploss = True
    trailing_stop = False

    order_types = {
        "entry": "limit", "exit": "limit",
        "stoploss": "market", "stoploss_on_exchange": False,
    }

    leverage_num = 1.0

    # Sul grafico SOLO due linee: verde = take-profit, rossa = stop-loss.
    plot_config = {
        "main_plot": {
            "take_profit": {"color": "#00dd55"},   # 🟢 VERDE = chiude in PROFITTO
            "stop_loss":   {"color": "#ff3333"},   # 🔴 ROSSO = chiude in PERDITA
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

        # Chandelier trailing stop: max(high,14) − 3×ATR (usato da custom_stoploss).
        d["chan_stop"] = d["high"].rolling(14).max() - self.chandelier_long * d["atr"]

        # Regime: +1 trend-su, −1 trend-giù, 0 laterale
        is_trend = (d["adx"] > self.adx_trend) & (d["er"] > self.er_trend)
        d["regime"] = 0
        d.loc[is_trend & (d["ema50"] > d["ema200"]) & (d["close"] > d["ema200"]), "regime"] =  1
        d.loc[is_trend & (d["ema50"] < d["ema200"]) & (d["close"] < d["ema200"]), "regime"] = -1

        # ===== LE UNICHE DUE LINEE MOSTRATE SUL GRAFICO =====
        d["take_profit"] = d["bb_up"]                                    # VERDE: dove il bot chiude in PROFITTO
        d["stop_loss"]   = d["close"] - self.chandelier_long * d["atr"]  # ROSSO: sempre sotto il prezzo attuale
        return dataframe

    # ---------------- INGRESSI ----------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        d = dataframe

        # ===== V-BOUNCE: compra la prima candela verde dopo un dip =====
        turning_up = (
            (d["close"] > d["open"])              # candela verde
            & (d["rsi"] > d["rsi"].shift(1))      # RSI risale dalla candela precedente
            & (d["volume"] > 0)
        )

        # Solo la candela IMMEDIATAMENTE dopo il dip (shift 1, non rolling 3).
        # Con rolling(3) entrava 3 volte di fila per lo stesso dip = muro di triangoli.
        just_had_dip = (
            (d["rsi"].shift(1) < self.dip_rsi)       # RSI era ipervenduto sulla candela prima
            | (d["low"].shift(1) < d["bb_low"])      # oppure il minimo ha toccato il fondo
        )

        # Deve esserci abbastanza spazio fino alla linea verde (take-profit).
        # Se siamo già vicini a bb_up, non c'è margine → non entrare.
        enough_room = (d["bb_up"] - d["close"]) / d["close"] > 0.008

        # STRADA A — DIP & RIMBALZO (range o V netta). Prima singola candela verde.
        dip_bounce = (
            (d["regime"] != -1)
            & just_had_dip
            & enough_room
            & turning_up
        )

        # STRADA B — PULLBACK IN UPTREND. Close sotto bb_mid + RSI leggero.
        trend_pullback = (
            (d["regime"] == 1)
            & (d["close"] < d["bb_mid"])
            & (d["rsi"] < self.trend_pull_rsi)
            & (d["rsi"] > self.mr_rsi_lo_exit)
            & enough_room
            & turning_up
        )

        d.loc[dip_bounce | trend_pullback, ["enter_long", "enter_tag"]] = (1, "v_bounce")

        if self.enable_shorts:
            short_pop = (
                (d["regime"] != 1)
                & (d["close"] > d["bb_mid"])
                & (d["rsi"] > self.mr_rsi_hi)
                & (d["close"] < d["open"])
                & (d["rsi"] < d["rsi"].shift(2))
                & (d["volume"] > 0)
            )
            d.loc[short_pop, ["enter_short", "enter_tag"]] = (1, "dip_short")
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

    # ---------------- TAKE-PROFIT: linea VERDE (bb_up) per OGNI trade long ----------------
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        # Chiude in PROFITTO quando il prezzo raggiunge la linea VERDE (bb_up).
        # Soglia minima 0.3%: copre le fees senza bloccare uscite valide.
        if current_profit < 0.003:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        last = df.iloc[-1]
        if not trade.is_short:
            if current_rate >= last["bb_up"] or last["rsi"] > self.mr_rsi_hi:
                return "take_profit"      # ← punto di uscita VERDE (profitto)
        else:
            if current_rate <= last["bb_low"] or last["rsi"] < self.mr_rsi_lo_exit:
                return "take_profit"
        return None

    # ---------------- STOP-LOSS: linea ROSSA (Chandelier) per OGNI trade long ----------------
    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, **kwargs):
        # Chiude in PERDITA quando il prezzo scende alla linea ROSSA (Chandelier 3×ATR).
        # Trailing: lo stop sale insieme al massimo del trade. Uguale per tutti i long.
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
