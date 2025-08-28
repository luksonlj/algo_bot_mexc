# runner.py
import os
import time
import math
import pandas as pd
import numpy as np
from loguru import logger
import ccxt

# ======= KONFIG Z ENV =======
EXCHANGE   = os.getenv("EXCHANGE", "mexc")
SYMBOL     = os.getenv("SYMBOL", "BTCUSDT")
TIMEFRAME  = os.getenv("TIMEFRAME", "5m")
RISK_PCT   = float(os.getenv("RISK_PER_TRADE", "0.07"))   # agresywnie 7%
MAX_DD_DAY = float(os.getenv("MAX_DD_DAY", "0.20"))       # kill switch 20% dziennego DD
LEVERAGE   = int(os.getenv("MAX_LEVERAGE", "20"))
LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")
DRY_RUN    = os.getenv("DRY_RUN", "true").lower() == "true"

logger.remove()
logger.add(lambda msg: print(msg, end=""), level=LOG_LEVEL)
os.makedirs("logs", exist_ok=True)
logger.add("logs/bot.log", level=LOG_LEVEL, rotation="5 MB", enqueue=True)

def connect_mexc():
    api_key    = os.getenv("MEXC_API_KEY", "")
    api_secret = os.getenv("MEXC_API_SECRET", "")
    exchange = ccxt.mexc({
        "apiKey": api_key,
        "secret": api_secret,
        "options": {"defaultType": "swap"},  # MEXC futures USDT-M
    })
    exchange.set_sandbox_mode(False)  # brak oficjalnego testnetu przez ccxt dla swap
    return exchange

def fetch_klines(exchange, symbol, timeframe, limit=300):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(close, n=14):
    delta = close.diff()
    up, down = delta.clip(lower=0), -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/n, adjust=False).mean()
    ma_down = down.ewm(alpha=1/n, adjust=False).mean()
    rs = ma_up / (ma_down + 1e-9)
    return 100 - (100/(1+rs))

def atr(df, n=14):
    h,l,c = df["high"], df["low"], df["close"]
    tr = np.maximum(h-l, np.maximum((h-c.shift(1)).abs(), (l-c.shift(1)).abs()))
    return pd.Series(tr).rolling(n).mean()

def signal_breakout_retest(df):
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi"]   = rsi(df["close"])
    df["atr"]   = atr(df)

    last = df.iloc[-1]
    # prosta wersja „agresywnie”: momentum według ułożenia EMA + RSI
    if last["close"] > last["ema50"] and last["ema20"] > last["ema50"] and last["rsi"] > 55:
        return "LONG"
    if last["close"] < last["ema50"] and last["ema20"] < last["ema50"] and last["rsi"] < 45:
        return "SHORT"
    return "FLAT"

def position_size(balance_usdt, entry, sl, risk_pct=RISK_PCT, leverage=LEVERAGE):
    risk_usdt = max(balance_usdt * risk_pct, 1.0)
    stop_dist = abs(entry - sl)
    if stop_dist <= 0:
        return 0.0
    qty = (risk_usdt * leverage) / (stop_dist) / entry  # kontrakty kwotowane w USDT
    return max(round(qty, 4), 0.0)

def set_leverage(exchange, symbol, lev):
    try:
        exchange.set_leverage(lev, symbol, params={"marginMode": "cross"})
        logger.info(f"Leverage set to {lev}x for {symbol}\n")
    except Exception as e:
        logger.warning(f"Leverage set failed (non-fatal): {e}\n")

def get_balance_usdt(exchange):
    try:
        bal = exchange.fetch_balance()
        # dla swapów MEXC spotykane: 'USDT' w total/free, ale bywa inaczej; fallback na 40
        usdt = bal.get("USDT", {}).get("free") or 40.0
        return float(usdt)
    except Exception:
        return 40.0

def main():
    logger.info(f"Starting bot | EXCHANGE={EXCHANGE} SYMBOL={SYMBOL} TF={TIMEFRAME} DRY_RUN={DRY_RUN}\n")
    mexc = connect_mexc()
    set_leverage(mexc, SYMBOL, LEVERAGE)

    # pseudo-kill-switch – w tej wersji tylko licznik strat/zysków z sesji
    session_pnl = 0.0
    consec_losses = 0

    while True:
        df = fetch_klines(mexc, SYMBOL, TIMEFRAME, 300)
        price = float(df["close"].iloc[-1])
        sig = signal_breakout_retest(df)
        balance = get_balance_usdt(mexc)

        if sig in ("LONG", "SHORT"):
            atr_val = float(df["atr"].iloc[-1] or 5.0)
            if sig == "LONG":
                sl = price - max(5.0, atr_val*0.7)
            else:
                sl = price + max(5.0, atr_val*0.7)

            qty = position_size(balance, price, sl)
            logger.info(f"{sig} signal | price={price:.2f} sl={sl:.2f} qty={qty}\n")

            if qty > 0:
                if DRY_RUN:
                    logger.info(f"[DRY_RUN] Would place {sig} MARKET {qty} on {SYMBOL}\n")
                else:
                    side = "buy" if sig == "LONG" else "sell"
                    try:
                        order = mexc.create_order(SYMBOL, "market", side, qty)
                        logger.info(f"Live order placed: {order}\n")
                    except Exception as e:
                        logger.error(f"Order error: {e}\n")

        # prosty „oddech” – na 5m świecach nie ma sensu spamować częściej niż co ~15s
        time.sleep(15)

if __name__ == "__main__":
    main()
