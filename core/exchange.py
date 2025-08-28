import os, ccxt

def make_exchange():
    ex = (os.getenv("EXCHANGE") or "MEXC").upper()
    if ex == "MEXC":
        return ccxt.mexc({
            "apiKey": os.getenv("MEXC_API_KEY"),
            "secret": os.getenv("MEXC_API_SECRET"),
            "options": {"defaultType": "swap"},   # jeśli futures na MEXC
            "enableRateLimit": True,
        })
    elif ex == "BINANCE":
        return ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "options": {"defaultType": "future"},
            "enableRateLimit": True,
        })
    else:
        raise ValueError(f"Unknown EXCHANGE={ex}")
