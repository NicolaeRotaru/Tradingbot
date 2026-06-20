# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
SolLongShortStrategy — strategia DEFINITIVA, focalizzata SOLO su SOL.

Trend-following su SOL (timeframe 1h), capace di LONG e SHORT (futures).
Leva 1x (nessuna amplificazione -> niente liquidazione). Size piena (sizing a
% del saldo nel config, cosi' i tuoi versamenti di 500 EUR/mese aumentano da soli
la dimensione delle operazioni).

⚠️  VERITA' DAI TUOI DATI (SOL 1h 2021-2026, anche fuori campione):
    lo SHORT su SOL PEGGIORA i risultati. Solo-long: +2182% (DD -68%).
    Long+short: peggio in OGNI periodo. SOL nel lungo periodo sale, quindi
    shortare ti fa travolgere dai rialzi.
    => Per il MASSIMO RENDIMENTO lascia `enable_shorts = False` (default).
       Lo short e' disponibile (enable_shorts = True) perche' l'avevi chiesto,
       con un filtro il piu' selettivo possibile, ma resta inferiore al solo-long.
       Il modo migliore di "guadagnare quando SOL scende" e' stare in CONTANTI
       durante i crolli: e' cio' che la strategia fa gia' uscendo dal long.

Niente promesse di "vincere sempre": il win rate del trend-following e' ~28%
(poche vincite grandi). Avvia SEMPRE in dry-run.
"""
from datetime import datetime

from pandas import DataFrame

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class SolLongShortStrategy(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = True

    # ===== INTERRUTTORE PRINCIPALE =====
    # False = solo long (MASSIMO RENDIMENTO sui dati di SOL) -> CONSIGLIATO.
    # True  = abilita anche gli short selettivi (come da tua richiesta).
    enable_shorts = False

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    startup_candle_count = 400

    # Take-profit disattivato: trend-following = lascia correre i profitti.
    minimal_roi = {"0": 10.0}
    # Rete di sicurezza ampia; il lavoro lo fanno uscita di trend + trailing.
    stoploss = -0.20
    trailing_stop = True
    trailing_stop_positive = 0.12
    trailing_stop_positive_offset = 0.18
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # Leva 1x: nessuna amplificazione (leva > 1 = rischio di LIQUIDAZIONE).
    leverage_num = 1.0

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        return self.leverage_num

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {"method": "MaxDrawdown", "lookback_period_candles": 168,
             "trade_limit": 6, "stop_duration_candles": 72, "max_allowed_drawdown": 0.35},
            {"method": "StoplossGuard", "lookback_period_candles": 48,
             "trade_limit": 3, "stop_duration_candles": 24, "only_per_pair": False},
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema400"] = ta.EMA(dataframe, timeperiod=400)   # filtro macro
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["mom24"] = dataframe["close"] - dataframe["close"].shift(24)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # LONG: trend rialzista confermato.
        dataframe.loc[
            (
                (dataframe["ema50"] > dataframe["ema200"])
                & (dataframe["close"] > dataframe["ema50"])
                & (dataframe["adx"] > 20)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        # SHORT: solo se abilitato e solo in downtrend MACRO confermato + momentum giu'.
        if self.enable_shorts:
            dataframe.loc[
                (
                    (dataframe["close"] < dataframe["ema200"])
                    & (dataframe["close"] < dataframe["ema400"])
                    & (dataframe["adx"] > 28)
                    & (dataframe["mom24"] < 0)
                    & (dataframe["volume"] > 0)
                ),
                "enter_short",
            ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Esci dal long quando il trend si rompe.
        dataframe.loc[
            (qtpylib.crossed_below(dataframe["close"], dataframe["ema200"]))
            & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        # Esci dallo short quando il prezzo torna sopra la media lenta.
        if self.enable_shorts:
            dataframe.loc[
                (qtpylib.crossed_above(dataframe["close"], dataframe["ema200"]))
                & (dataframe["volume"] > 0),
                "exit_short",
            ] = 1
        return dataframe
