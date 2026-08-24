"""Corpus loading, features, and puzzle generation for the price-action game."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from intuition_trading import config


@dataclass(frozen=True)
class Corpus:
    """The full in-memory archive plus an index of sessions usable for puzzles."""

    bars: dict[str, pd.DataFrame]  # ticker -> full bar history, timestamp-indexed
    valid_sessions: list[tuple[str, date]]  # (ticker, session_date) with enough bars to play
    corpus_version: str


def _min_session_bars() -> int:
    """A session needs enough bars for an anchor to sit with a full lookback
    behind it and a full horizon ahead of it, both within the same session."""
    return config.LOOKBACK_BARS + config.HORIZON_BARS


def _load_corpus_version() -> str:
    if not config.MANIFEST_PATH.exists():
        return ""
    with open(config.MANIFEST_PATH) as f:
        manifest = json.load(f)
    return manifest.get("corpus_version", "")


def load_corpus() -> Corpus:
    """Load every parquet in data/bars/ and index sessions long enough to play.

    The whole corpus at this size is comfortably in-memory, so this loads
    everything up front rather than building a query layer.
    """
    bars: dict[str, pd.DataFrame] = {}
    valid_sessions: list[tuple[str, date]] = []
    min_bars = _min_session_bars()

    for path in sorted(config.BARS_DIR.glob("*.parquet")):
        ticker = path.stem
        df = pd.read_parquet(path)
        if df.empty:
            continue
        bars[ticker] = df

        counts = pd.Index(df.index.date).value_counts()
        for session_date, count in counts.items():
            if count >= min_bars:
                valid_sessions.append((ticker, session_date))

    valid_sessions.sort()
    return Corpus(bars=bars, valid_sessions=valid_sessions, corpus_version=_load_corpus_version())


def session_bars(corpus: Corpus, ticker: str, session_date: date) -> pd.DataFrame:
    """Bars for one (ticker, session_date), in timestamp order."""
    df = corpus.bars[ticker]
    return df.loc[pd.Index(df.index.date) == session_date]


# --- Puzzle generation ------------------------------------------------------
#
# The anchor bar is the *last* bar of the lookback window, not the first bar
# of the horizon. This is forced by the sampling bounds below: the minimum
# anchor_idx (LOOKBACK_BARS - 1) is only reachable if LOOKBACK_BARS bars
# *including* the anchor exist before it. Its close is therefore both the
# lookback's normalisation reference (it sits at 0.0) and the "now" price
# that raw_return measures forward from.


@dataclass(frozen=True)
class PuzzleView:
    """Everything the renderer is allowed to see."""

    bars: pd.DataFrame  # lookback bars only, normalised
    puzzle_id: str


@dataclass(frozen=True)
class PuzzleAnswer:
    """Held by the game loop. Never passed to the renderer."""

    puzzle_id: str
    label: int  # +1 up, -1 down
    horizon_bars: pd.DataFrame
    ticker: str
    session_date: date
    anchor_idx: int
    raw_return: float
    sigma_lookback: float
    trend_r2: float
    minutes_from_open: int


def _puzzle_id(corpus_version: str, ticker: str, session_date: date, anchor_idx: int) -> str:
    payload = f"{corpus_version}|{ticker}|{session_date}|{anchor_idx}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _sigma_lookback(close: pd.Series) -> float:
    """Standard deviation of 1-minute log returns over the visible window."""
    log_returns = np.log(close / close.shift(1)).dropna()
    return float(log_returns.std(ddof=1))


def _trend_r2(close: pd.Series) -> float:
    """R^2 of an OLS fit of close against bar index over the visible window."""
    y = close.to_numpy(dtype=float)
    if len(y) < 2 or np.all(y == y[0]):
        return 0.0
    x = np.arange(len(y), dtype=float)
    corr = np.corrcoef(x, y)[0, 1]
    return float(corr**2)


def _normalize(df: pd.DataFrame, anchor_close: float) -> pd.DataFrame:
    """Percent deviation from the anchor close: value = (price / anchor - 1) * 100."""
    cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
    return (df[cols] / anchor_close - 1.0) * 100.0


def generate_puzzle(corpus: Corpus, rng: random.Random) -> tuple[PuzzleView, PuzzleAnswer]:
    """Sample one puzzle from the corpus.

    `rng` controls determinism: pass a `random.Random(seed)` shared across a
    session's rounds for a reproducible sequence, or a fresh unseeded
    `random.Random()` (the default for normal play) for one that isn't.
    """
    if not corpus.valid_sessions:
        raise ValueError("corpus has no sessions long enough to generate a puzzle")

    while True:
        ticker, session_date = rng.choice(corpus.valid_sessions)
        session = session_bars(corpus, ticker, session_date)
        n = len(session)

        anchor_idx = rng.randint(config.LOOKBACK_BARS - 1, n - config.HORIZON_BARS - 1)

        lookback = session.iloc[anchor_idx - config.LOOKBACK_BARS + 1 : anchor_idx + 1]
        horizon = session.iloc[anchor_idx + 1 : anchor_idx + 1 + config.HORIZON_BARS]

        anchor_close = float(session["close"].iloc[anchor_idx])
        horizon_close = float(session["close"].iloc[anchor_idx + config.HORIZON_BARS])

        if horizon_close == anchor_close:
            continue  # exact tie: rare enough not to warrant a dedicated path

        puzzle_id = _puzzle_id(corpus.corpus_version, ticker, session_date, anchor_idx)

        view = PuzzleView(bars=_normalize(lookback, anchor_close), puzzle_id=puzzle_id)

        answer = PuzzleAnswer(
            puzzle_id=puzzle_id,
            label=1 if horizon_close > anchor_close else -1,
            horizon_bars=_normalize(horizon, anchor_close),
            ticker=ticker,
            session_date=session_date,
            anchor_idx=anchor_idx,
            raw_return=(horizon_close / anchor_close - 1.0) * 100.0,
            sigma_lookback=_sigma_lookback(lookback["close"]),
            trend_r2=_trend_r2(lookback["close"]),
            minutes_from_open=anchor_idx,
        )

        return view, answer
