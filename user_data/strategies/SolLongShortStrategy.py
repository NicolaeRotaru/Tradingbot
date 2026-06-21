# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
SolLongShortStrategy — strategia DEFINITIVA, focalizzata SOLO su SOL.

Trend-following su SOL (timeframe 1h), SOLO-LONG di default (lo short su SOL perde
in ogni periodo testato). Uscita con CHANDELIER EXIT ad ATR (trailing su volatilita'),
che e' il miglior compromesso rendimento/rischio trovato sui dati reali.

⚠️  VERITA' DAI TUOI DATI (SOL 1h 2021-2026, in-sample E fuori campione):
    - Solo-long batte long+short ovunque. => enable_shorts = False (default).
    - L'obiettivo NON e' un rendimento mirabolante (quelli sono quasi sempre
      LOOKAHEAD/overfitting), ma il miglior CALMAR ROBUSTO + sopravvivenza al
      drawdown. Esempi reali (costi Kraken Futures inclusi, solo-long):
          Baseline trailing 12% : +2182% / DD -68% / Calmar 1.15 (OOS 2024-26: +5%)
          Chandelier 3xATR      : +1829% / DD -53% / Calmar 1.38 (OOS 2024-26: +11%)
    - Il grosso del rendimento storico viene dal 2021-2023 (lancio di SOL). Fuori
      campione la strategia rende molto meno: aspettative oneste, sempre dry-run.
    - Drawdown-obiettivo ~-50%: la Chandelier 3xATR a leva 1x ci si avvicina (-53%).
      Per scendere a -50% netto si puo' usare leverage_num = 0.9.

Niente promesse di "vincere sempre": il win rate del trend-following e' ~28%
(poche vincite grandi). Avvia SEMPRE in dry-run.
"""
from datetime import datetime

from pandas import DataFrame

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, stoploss_from_absolute


class SolLongShortStrategy(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = True

    # ===== INTERRUTTORE PRINCIPALE =====
    # False = solo long (DEFAULT): sui dati di SOL rende di piu' e con meno drawdown.
    # True  = long + short: lo short su SOL PEGGIORA in ogni periodo (resta nel codice,
    #         disattivato, per poterlo riattivare se lo si vuole testare).
    enable_shorts = False

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    startup_candle_count = 400

    # Take-profit disattivato: trend-following = lascia correre i profitti.
    minimal_roi = {"0": 10.0}

    # Rete di sicurezza ampia; il lavoro lo fa la Chandelier (custom_stoploss).
    stoploss = -0.20

    # USCITA = Chandelier Exit ad ATR (trailing su volatilita') via custom_stoploss.
    # Sostituisce il trailing a % fisso: sui dati reali da' DD -53% (vs -68%) e il
    # miglior Calmar (1.38). Niente trailing_stop fisso, niente conflitti.
    use_custom_stoploss = True
    trailing_stop = False
    chandelier_mult = 3.0   # stop = max_rate - 3 * ATR  (3xATR e' il valore validato)

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # Indicatori mostrati nella chart di FreqUI:
    #  - sul grafico del prezzo: le tre EMA (trend)
    #  - in pannelli separati sotto: ADX (forza del trend) e ATR (volatilita')
    plot_config = {
        "main_plot": {
            "ema50": {"color": "orange"},
            "ema200": {"color": "blue"},
            "ema400": {"color": "purple"},
        },
        "subplots": {
            "ADX (forza trend)": {
                "adx": {"color": "red"},
            },
            "ATR (volatilita')": {
                "atr": {"color": "grey"},
            },
        },
    }

    # Leva 1x: a -50% di drawdown-obiettivo NON serve piu' leva (oltre ~1.5x peggiora,
    # leverage decay). Per un -50% netto si puo' abbassare a 0.9.
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
        # Esci dal long quando il trend si rompe (la Chandelier ATR fa il trailing).
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

    def custom_stoploss(self, pair: str, trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float | None:
        """Chandelier Exit ad ATR: stop = (prezzo massimo dall'ingresso) - mult*ATR.

        Sui long, `trade.max_rate` e' il massimo visto dall'ingresso (per gli short e'
        `trade.min_rate` ma qui di default operiamo solo long). Restituendo None si
        mantiene lo stoploss corrente (rete di sicurezza -20%).
        """
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        atr = df["atr"].iat[-1]
        if atr is None or atr != atr or atr <= 0:   # NaN / non valido
            return None
        if trade.is_short:
            stop_price = trade.min_rate + self.chandelier_mult * atr
        else:
            stop_price = trade.max_rate - self.chandelier_mult * atr
        return stoploss_from_absolute(
            stop_price, current_rate, is_short=trade.is_short, leverage=trade.leverage)
