# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
TrendFollowStrategy — versione MIGLIORATA, orientata alle performance.

Differenza chiave rispetto a StarterStrategy: invece di "scalpare" piccoli
ribassi ed uscire dopo poche ore (uscita rapida = poca partecipazione ai trend),
questa strategia FA TREND-FOLLOWING: entra quando il trend e' rialzista e
RESTA dentro finche' il trend regge, lasciando correre i profitti.

Perche' migliora (vedi docs/potenziamento-v2.md, Leva 5 "alpha robusto"):
- partecipa ai grandi trend invece di stare quasi sempre in contanti;
- niente take-profit anticipato (minimal_roi disattivato): si lascia correre;
- esce quando il trend si rompe (close < EMA200) o con un trailing ampio.

Nel backtest su Solana (daily, 2021-2024) questo approccio ha reso molto piu'
della StarterStrategy e ha battuto anche il "compra e tieni", con un drawdown
inferiore. MA ATTENZIONE (vedi docs/miglioramento-performance.md):
- e' un test su UN solo asset, UN periodo, dati giornalieri -> forte rischio di
  overfitting: NON e' una promessa di rendimento futuro;
- il drawdown resta GRANDE (~ -60/70%): va validato su piu' asset (BTC, ETH) e
  fuori campione, e usato con size piccola;
- il trend-following guadagna nei trend e SOFFRE (whipsaw) nei mercati laterali.
Parti sempre in dry-run.
"""
from datetime import datetime

from pandas import DataFrame

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class TrendFollowStrategy(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False  # solo long, niente leva (versione prudente)

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    startup_candle_count = 200

    # Take-profit DISATTIVATO: il trend-following vive del "lascia correre".
    # 10.0 = 1000% = di fatto mai (l'uscita la decide il trend / il trailing).
    minimal_roi = {"0": 10.0}

    # Rete di sicurezza ampia: e' l'uscita di trend a fare il lavoro, non lo stop.
    stoploss = -0.35

    # Trailing AMPIO: lascia respirare il trend, poi protegge i guadagni.
    trailing_stop = True
    trailing_stop_positive = 0.15
    trailing_stop_positive_offset = 0.20
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "MaxDrawdown", "lookback_period_candles": 96,
             "trade_limit": 5, "stop_duration_candles": 48, "max_allowed_drawdown": 0.30},
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entra quando il trend e' confermato rialzista (EMA50 > EMA200) e il
        # prezzo e' sopra la media veloce. Si resta dentro finche' regge.
        dataframe.loc[
            (
                (dataframe["ema50"] > dataframe["ema200"])
                & (dataframe["close"] > dataframe["ema50"])
                & (dataframe["adx"] > 20)        # trend con un minimo di forza
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Esci quando il trend si rompe: prezzo sotto la media lenta.
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["close"], dataframe["ema200"]))
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
