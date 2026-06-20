# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
StarterStrategy — strategia baseline semplice, robusta e anti-overfitting.

Filosofia (vedi docs/analisi-completa.md, potenziamento-v2.md, mentalita-esperti.md):
- Poche regole chiare = pochi gradi di liberta' = meno overfitting.
- Solo LONG su spot, NESSUNA leva (sopravvivenza prima del rendimento).
- Una sola idea: "compra il ribasso dentro un trend rialzista".
- Il rischio e' gestito da stoploss + ROI + trailing + le `protections` in config.

NON e' una macchina da soldi: e' una base onesta da validare in backtest e dry-run.
Tara i parametri con cautela (l'over-ottimizzazione uccide le strategie).
"""

from datetime import datetime
from pandas import DataFrame

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class StarterStrategy(IStrategy):

    INTERFACE_VERSION = 3

    # --- Impostazioni base -------------------------------------------------
    timeframe = "1h"
    can_short = False  # solo long, niente leva

    # Lavora solo alla chiusura di una nuova candela (meno rumore, meno costi).
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False

    # Servono 200 candele di "riscaldamento" per la EMA200.
    startup_candle_count = 200

    # --- Protezioni (circuit breaker dai documenti) ------------------------
    # Nelle versioni recenti di Freqtrade le protezioni si definiscono qui,
    # nella strategia (non piu' nel config.json).
    @property
    def protections(self):
        return [
            # Pausa breve dopo ogni trade chiuso (evita di rientrare sul rumore).
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2
            },
            # Troppi stoploss in poco tempo -> sospendi il trading.
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 2,
                "stop_duration_candles": 12,
                "only_per_pair": False
            },
            # Drawdown oltre il 15% -> stop temporaneo (Leva 2: controllo del DD).
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 48,
                "trade_limit": 5,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.15
            },
            # Coppie costantemente in perdita -> mettile in pausa.
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 360,
                "trade_limit": 2,
                "stop_duration_candles": 60,
                "required_profit": 0.0
            }
        ]

    # --- Uscite gestite dal rischio ----------------------------------------
    # ROI decrescente nel tempo (chiavi = minuti): prendi profitto e non
    # restare innamorato del trade. Valori di partenza, da validare in backtest.
    minimal_roi = {
        "0": 0.10,
        "360": 0.06,
        "720": 0.03,
        "1440": 0.0
    }

    # Stoploss "hard" per trade: la rete di sicurezza piu' importante.
    stoploss = -0.10

    # Trailing stop: blocca i profitti quando il trade va bene.
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # Ordini limit (maker-leaning) per ridurre i costi (Leva 1 dei documenti).
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # --- Indicatori --------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Filtro di regime: trend di fondo.
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        # Oscillatore per il timing del "ribasso".
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        # Volatilita' (usata in futuro per sizing/stop dinamici).
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        return dataframe

    # --- Regola di ENTRATA (una sola idea) ---------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1) Regime rialzista: prezzo sopra la media lenta.
                (dataframe["close"] > dataframe["ema200"]) &
                # 2) Pullback che rientra: RSI risale sopra 35 dall'ipervenduto.
                (qtpylib.crossed_above(dataframe["rsi"], 35)) &
                # 3) Mercato attivo.
                (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    # --- Regola di USCITA (oltre a ROI/stop/trailing) ----------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Ipercomprato: prendi i profitti.
                (qtpylib.crossed_above(dataframe["rsi"], 75)) &
                (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
