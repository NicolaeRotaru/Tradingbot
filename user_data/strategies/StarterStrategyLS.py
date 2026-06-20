# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
StarterStrategyLS — versione LONG + SHORT della StarterStrategy.

Oltre a COMPRARE in trend rialzista (long), VENDE allo scoperto in trend
ribassista (short) per provare a guadagnare anche quando il prezzo scende.

⚠️  IMPORTANTE — LO SHORT RICHIEDE I FUTURES (margine):
    - usare con  trading_mode: "futures"  (vedi user_data/config-futures.json);
    - sullo SPOT lo short NON e' possibile;
    - lo short e' molto piu' rischioso del long: con leva > 1 rischi anche la
      LIQUIDAZIONE (perdere tutto). Qui la leva e' impostata a 1x (nessuna
      amplificazione): alzala solo se sai esattamente cosa stai facendo.
    - parti SEMPRE in dry-run.
"""
from datetime import datetime

from pandas import DataFrame

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class StarterStrategyLS(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = True  # <-- abilita lo SHORT (solo in modalita' futures)

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    startup_candle_count = 200

    minimal_roi = {"0": 0.10, "360": 0.06, "720": 0.03, "1440": 0.0}
    stoploss = -0.10

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # Leva conservativa: 1x = nessuna amplificazione. Cambiala con prudenza.
    leverage_num = 1.0

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        return self.leverage_num

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "StoplossGuard", "lookback_period_candles": 24,
             "trade_limit": 2, "stop_duration_candles": 12, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 48,
             "trade_limit": 5, "stop_duration_candles": 24, "max_allowed_drawdown": 0.15},
            {"method": "LowProfitPairs", "lookback_period_candles": 360,
             "trade_limit": 2, "stop_duration_candles": 60, "required_profit": 0.0},
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # LONG: compra il ribasso DENTRO un trend rialzista.
        dataframe.loc[
            (
                (dataframe["close"] > dataframe["ema200"])
                & (qtpylib.crossed_above(dataframe["rsi"], 35))
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        # SHORT: vendi il rimbalzo DENTRO un trend ribassista.
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["ema200"])
                & (qtpylib.crossed_below(dataframe["rsi"], 65))
                & (dataframe["volume"] > 0)
            ),
            "enter_short",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Chiudi il long in ipercomprato.
        dataframe.loc[
            (qtpylib.crossed_above(dataframe["rsi"], 75)) & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        # Chiudi lo short in ipervenduto.
        dataframe.loc[
            (qtpylib.crossed_below(dataframe["rsi"], 25)) & (dataframe["volume"] > 0),
            "exit_short",
        ] = 1
        return dataframe
