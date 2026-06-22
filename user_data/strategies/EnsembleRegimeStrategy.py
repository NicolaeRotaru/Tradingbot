# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
EnsembleRegimeStrategy — bot a commutazione di regime, 15m, SOL/USD:USD.

  USCITA — ADATTIVA per regime:
    BULL (+1)  TRAILING  : linea VERDE che RATCHETTA — highest_high(22) − 2.5×ATR, sale
                           coi massimi e NON scende mai nel pump. Esce quando il prezzo
                           scende a toccarla (profit ≥1%). Cavalca tutto il trend bull.
    RANGE >EMA50 (0)    : linea VERDE a bb_up (mean reversion piena).
    RANGE <EMA50 (0)    : linea VERDE a bb_mid (rimbalzi più corti → target compresso).
    BEAR (-1)  SEGNALE  : esce su segnale regime; nessun nuovo ingresso in bear.

  INGRESSO — "V-BOUNCE":
    A) DIP & RIMBALZO : dip recente (RSI<40 o low<bb_low) + prima candela verde
                        + bb_mid stabile + volatilità non estrema (veto ATR%)
    B) PULLBACK UP    : in regime +1, storno leggero (RSI<50) che rimbalza

  Filtri anti-coltello che cadono:
    bb_not_falling : bb_mid non è scesa >0.5% in 5 candele (blocca discese prolungate)
    atr_veto       : ATR% nel top 20% degli ultimi 200 bar → volatilità da crash → skip

  Sul grafico:
    VERDE trailing : in BULL sale con le candele (segue i massimi → "tocca" ogni candela)
    VERDE fisso    : in RANGE mostra il target (bb_up o bb_mid per contesto EMA50)
    ROSSO          : Chandelier 3×ATR sotto il prezzo (sale col trade)
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
    bull_trail_atr = 2.5     # BULL: la VERDE esce solo se il prezzo ritraccia 2.5×ATR dal max → lascia correre il trend

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

    # custom_exit gestisce TUTTE le uscite in profitto (target range + trailing bull).
    # ROI temporale DISATTIVATO: il vecchio {"120": 0.005} chiudeva i trade bull a +0.5%
    # dopo 2h, troncando proprio i trend che vogliamo cavalcare. Ora il bull corre fino
    # al trailing stop (2.5×ATR) o al cambio di regime; il range esce al target/stop.
    minimal_roi = {"0": 100.0}
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

        # +DI / -DI — l'altra metà dell'ADX che non usavamo.
        # ADX = forza del trend. +DI = forza dei compratori. -DI = forza dei venditori.
        # Quando -DI > +DI: i venditori dominano → siamo in un bear anche se ADX è basso.
        # I trader professionisti usano sempre ADX + DI insieme (mai ADX da solo).
        d["plus_di"]  = ta.PLUS_DI(d, timeperiod=14)
        d["minus_di"] = ta.MINUS_DI(d, timeperiod=14)

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

        # ===== ATR VETO: blocca entrate in volatilità da crash =====
        # atr_pct = ATR come % del prezzo. Se è nel top 20% degli ultimi 200 bar
        # = mercato in crollo o spike → knife-catching → non entrare.
        atr_pct = d["atr"] / d["close"]
        d["atr_veto"] = atr_pct > atr_pct.rolling(200, min_periods=100).quantile(0.80)

        # ===== LINEA VERDE — adattiva per regime =====
        # BULL : trailing tipo Chandelier che RATCHETTA — highest_high(22) − bull_trail_atr×ATR,
        #        poi cummax dentro ogni tratto consecutivo di bull. La verde SALE coi massimi
        #        e NON scende mai durante il pump (prima crollava: usava max(high,3)−×ATR e
        #        quando l'ATR esplodeva la riga si abbassava). Riparte solo a fine bull.
        # RANGE >EMA50 : bb_up (target pieno: mean reversion classica).
        # RANGE <EMA50 : bb_mid (rimbalzi più corti in contesto ribassista → target compresso).
        chand      = d["high"].rolling(22).max() - self.bull_trail_atr * d["atr"]
        is_bull    = d["regime"] == 1
        bull_grp   = (is_bull != is_bull.shift()).cumsum()     # id di ogni tratto consecutivo
        trail_bull = chand.groupby(bull_grp).cummax()          # ratchet: solo verso l'alto nel bull
        range_tp   = np.where(d["close"] > d["ema50"], d["bb_up"], d["bb_mid"])
        d["take_profit"] = np.where(is_bull, trail_bull, range_tp)
        d["stop_loss"]   = d["close"] - self.chandelier_long * d["atr"]
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

        # Il mercato NON sta scendendo a breve termine: bb_mid (la media) non è caduta
        # più dello 0.5% rispetto a 5 candele fa (~1h15). Blocca "compra il rimbalzo
        # dentro una discesa che continua" (regime -1 si accende tardi, bb_mid no).
        # Tolleranza 0.5%: una V buona abbassa bb_mid di ~0.1-0.3% (passa), una vera
        # discesa la fa scendere di oltre 0.5% (blocca). Soglia da tarare col backtest.
        bb_not_falling = d["bb_mid"] >= d["bb_mid"].shift(5) * 0.995

        # NB: NON usiamo +DI > -DI come filtro d'ingresso. Al fondo di un dip il
        # prezzo è appena sceso, quindi -DI domina sempre +DI (il DMI è lento). Per
        # un dip-buyer quel filtro blocca OGNI entrata. Contro la discesa prolungata
        # usiamo bb_not_falling e atr_veto, che reagiscono subito senza il ritardo del DMI.

        # Veto volatilità estrema: se ATR% è nel top 20% degli ultimi 200 bar = crash/spike.
        # Il prezzo continua a scendere anche con RSI basso → no entrata.
        atr_safe = ~d["atr_veto"]

        # STRADA A — DIP & RIMBALZO (range o V netta). Prima singola candela verde.
        dip_bounce = (
            (d["regime"] != -1)
            & just_had_dip
            & enough_room
            & bb_not_falling
            & atr_safe
            & turning_up
        )

        # STRADA B — PULLBACK IN UPTREND. Close sotto bb_mid + RSI leggero.
        trend_pullback = (
            (d["regime"] == 1)
            & (d["close"] < d["bb_mid"])
            & (d["rsi"] < self.trend_pull_rsi)
            & (d["rsi"] > self.mr_rsi_lo_exit)
            & enough_room
            & atr_safe
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

    # ---------------- TAKE-PROFIT ADATTIVO ----------------
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if current_profit < 0.003:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        last = df.iloc[-1]

        if not trade.is_short:
            if last["regime"] == 1:
                # BULL — esce quando il prezzo scende a TOCCARE la verde (trailing che
                # ratchetta in populate_indicators: sale coi massimi, non scende mai nel
                # bull). Così cattura tutto il pump ed esce solo sul ritracciamento vero,
                # dopo almeno +1%. Niente cap RSI: in un bull forte l'RSI resta >78 a lungo.
                if current_profit >= 0.010 and current_rate <= last["take_profit"]:
                    return "trail_bull"
            else:
                # RANGE / BEAR — target adattivo (pre-calcolato in populate_indicators):
                #   close > EMA50 → bb_up (rimbalzo pieno)
                #   close < EMA50 → bb_mid (rimbalzo compresso, contesto ribassista)
                if current_rate >= last["take_profit"] or last["rsi"] > self.mr_rsi_hi:
                    return "take_profit"
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
