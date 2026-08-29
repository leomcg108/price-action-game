"""Standalone corpus builder. Run on a schedule (weekly is ample) to accumulate
a permanent archive from Yahoo's rolling 30-day window of 1-minute bars.

This is the only time-critical component in the project: Yahoo serves 1-minute
bars for roughly the last 30 days only, so data not collected here is
permanently lost.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from intuition_trading import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

WINDOW_DAYS = 7
N_WINDOWS = 4
MAX_RETRIES = 3
# No proactive rate-limiting between requests -- back-to-back requests for
# 500+ tickers have been reliable in practice. MAX_RETRIES/backoff below is
# the reactive safety net if Yahoo ever does return a 429.


def _fetch_window(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Fetch one <=7-day window of 1-minute bars, retrying with backoff."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = yf.download(
                ticker,
                start=start,
                end=end,
                interval="1m",
                prepost=False,
                auto_adjust=True,
                progress=False,
            )
            return df
        except Exception as exc:  # yfinance raises a variety of things, including on HTTP 429
            last_exc = exc
            backoff = 2**attempt
            logger.warning(
                "fetch failed for %s [%s, %s], attempt %d/%d: %s. retrying in %ds",
                ticker, start.date(), end.date(), attempt + 1, MAX_RETRIES, exc, backoff,
            )
            time.sleep(backoff)
    raise RuntimeError(f"exhausted retries for {ticker} [{start}, {end}]") from last_exc


def _fetch_raw(ticker: str) -> pd.DataFrame | None:
    """Pull the last ~30 days of 1-minute bars in four consecutive 7-day windows."""
    now = datetime.now(timezone.utc)
    chunks = []
    for i in range(N_WINDOWS):
        end = now - timedelta(days=i * WINDOW_DAYS)
        start = end - timedelta(days=WINDOW_DAYS)
        try:
            df = _fetch_window(ticker, start, end)
        except RuntimeError as exc:
            logger.error("giving up on one window for %s: %s", ticker, exc)
            continue
        if df is not None and not df.empty:
            chunks.append(df)
    if not chunks:
        return None
    return pd.concat(chunks)


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    return df[keep]


def _to_market_tz(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df = df.copy()
    df.index = idx.tz_convert(config.MARKET_TZ)
    df.index.name = "timestamp"
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any session with fewer than MIN_BARS_PER_DAY bars. No interpolation."""
    if df.empty:
        return df
    session_dates = pd.Index(df.index.date)
    counts = session_dates.value_counts()
    valid_dates = counts[counts >= config.MIN_BARS_PER_DAY].index
    return df.loc[session_dates.isin(valid_dates)]


def _load_existing(path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_parquet(path)
    return None


def _merge(existing: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing, new]) if existing is not None and not existing.empty else new
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined.sort_index()


def fetch_ticker(ticker: str) -> pd.DataFrame | None:
    logger.info("fetching %s", ticker)
    raw = _fetch_raw(ticker)
    if raw is None or raw.empty:
        logger.error("no data fetched for %s", ticker)
        return None

    raw = _flatten_columns(raw)
    raw = _to_market_tz(raw)
    raw = _standardize(raw)
    cleaned = _clean(raw)
    if cleaned.empty:
        logger.warning("no sessions survived cleaning for %s", ticker)
        return None

    path = config.BARS_DIR / f"{ticker}.parquet"
    merged = _merge(_load_existing(path), cleaned)

    config.BARS_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(path)
    logger.info("wrote %s: %d rows, %d sessions", ticker, len(merged), pd.Index(merged.index.date).nunique())
    return merged


def _corpus_version(tickers_data: dict[str, pd.DataFrame]) -> str:
    tuples = []
    for ticker, df in tickers_data.items():
        counts = pd.Index(df.index.date).value_counts()
        for session_date, count in counts.items():
            tuples.append((ticker, str(session_date), int(count)))
    tuples.sort()
    payload = json.dumps(tuples, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def write_manifest(universe: list[str]) -> dict:
    tickers_data: dict[str, pd.DataFrame] = {}
    tickers_info: dict[str, dict] = {}

    for ticker in universe:
        path = config.BARS_DIR / f"{ticker}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if df.empty:
            continue
        tickers_data[ticker] = df
        tickers_info[ticker] = {
            "rows": int(len(df)),
            "sessions": int(pd.Index(df.index.date).nunique()),
            "first": df.index.min().isoformat(),
            "last": df.index.max().isoformat(),
        }

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_version": _corpus_version(tickers_data),
        "tickers": tickers_info,
    }

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def _load_sp500_tickers(path: Path = config.SP500_CSV) -> list[str]:
    """Read the "Symbol" column of the S&P 500 constituents csv.

    Yahoo uses a dash where the index listing uses a dot (BRK.B -> BRK-B).
    """
    if not path.exists():
        logger.warning("sp500 csv not found at %s; universe falls back to UNIVERSE only", path)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row["Symbol"].strip().replace(".", "-") for row in reader if row.get("Symbol")]


def build_universe() -> list[str]:
    """config.UNIVERSE unioned with the S&P 500 constituents.

    UNIVERSE is kept as the default/backup set: it's what you get if the csv
    is missing, and it's always included even when the csv is present (this
    is also what keeps index ETFs like SPY/QQQ in scope, since they aren't
    S&P 500 constituents themselves).
    """
    sp500 = _load_sp500_tickers()
    return sorted(set(config.UNIVERSE) | set(sp500))


def main(tickers: list[str] | None = None) -> None:
    universe = tickers or build_universe()
    logger.info("fetching %d tickers", len(universe))
    config.BARS_DIR.mkdir(parents=True, exist_ok=True)

    failures = []
    for ticker in universe:
        try:
            fetch_ticker(ticker)
        except Exception:
            logger.exception("failed to fetch %s", ticker)
            failures.append(ticker)

    manifest = write_manifest(universe)
    logger.info(
        "manifest written: corpus_version=%s tickers=%d",
        manifest["corpus_version"], len(manifest["tickers"]),
    )
    if failures:
        logger.warning("failed tickers: %s", ", ".join(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        help="comma-separated ticker override for a partial/test run (default: full UNIVERSE)",
    )
    args = parser.parse_args()
    override = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    main(override)
