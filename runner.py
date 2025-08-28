from loguru import logger
from core.exchange import make_exchange
from core.llm_router import llm_complete

def main(symbol: str = "BTC/USDT", dry_run: bool = True):
    ex = make_exchange()
    ex.load_markets()
    if symbol not in ex.symbols:
        raise SystemExit(f"{symbol} not listed on {ex.id}")
    t = ex.fetch_ticker(symbol)
    last = t.get("last")
    logger.info(f"{ex.id} {symbol} last={last}")
    idea = llm_complete(f"Price={last}. Give a cautious scalp outline.")
    logger.info(f"LLM idea: {idea}")
    if not dry_run:
        logger.info("Here you would place orders…")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    main(symbol=args.symbol, dry_run=args.dry_run)
