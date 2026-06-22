# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
EnsembleRegimeStrategy — bot a commutazione di regime, 15m, SOL/USD:USD.

  USCITA — sistema a DUE LINEE, IDENTICO per OGNI trade long:
    TAKE-PROFIT : il prezzo tocca la linea VERDE (bb_up) con almeno +1% → chiude in GUADAGNO
    STOP-LOSS   : il prezzo scende alla linea ROSSA (Chandelier 3×ATR)   → chiude in PERDITA

  INGRESSO — UNICO, "compra il dip che rimbalza" (tranne nei downtrend forti):
    regime != -1  +  close<bb_mid  +  RSI<42  +  candela verde  +  RSI in recupero
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

        # INGRESSO UNICO — "compra il DIP che rimbalza", tranne nei downtrend forti.
        # Elimina il muro di triangoli: in un trend SENZA storni NON entra (RSI resta alto),
        # entra solo quando il prezzo storna e poi rimbalza = UN ingresso per ogni ribasso.
        #   regime != -1   → non in trend giù confermato (lì si sta fuori dal mercato)
        #   close < bb_mid → metà bassa del canale = "compra basso"
        #   rsi < 42       → c'è stato un dip (in trend forte senza pullback aspetta)
        #   close > open   → candela verde = rimbalzo già iniziato, non coltello che cade
        #   rsi > rsi[-2]  → RSI sta risalendo dal minimo (conferma della svolta)
        long_dip = (
            (d["regime"] != -1)
            & (d["close"] < d["bb_mid"])
            & (d["rsi"] < self.mr_rsi_lo)
            & (d["close"] > d["open"])
            & (d["rsi"] > d["rsi"].shift(2))
            & (d["volume"] > 0)
        )
        d.loc[long_dip, ["enter_long", "enter_tag"]] = (1, "dip_long")

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
        # Chiude in PROFITTO quando il prezzo raggiunge la linea VERDE (bb_up),
        # ma solo se il guadagno è almeno +1% (niente micro-uscite flat).
        # IMPORTANTE: vale per TUTTI i long (trend E mean-reversion) — prima i trend
        # NON usavano questa uscita e restavano aperti (= "entry senza puntino giallo").
        if current_profit < 0.010:
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
