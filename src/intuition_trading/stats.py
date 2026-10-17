"""Binomial tail, Wilson interval, and the session/lifetime summary.

No scipy: both statistics are closed-form and implemented directly with
math.comb / math.sqrt.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from intuition_trading import config

_Z_95 = 1.959963984540054  # two-sided 95% normal quantile


def binomial_upper_tail(k: int, n: int, p: float = 0.5) -> float:
    """Exact P(X >= k) for X ~ Binomial(n, p)."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def wilson_interval(k: int, n: int, z: float = _Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion, at the confidence
    level implied by `z` (default: 95%, two-sided)."""
    if n == 0:
        return 0.0, 0.0
    phat = k / n
    denom = 1 + z**2 / n
    center = phat + z**2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    return (center - margin) / denom, (center + margin) / denom


# --- Reading the log ---------------------------------------------------


# Columns added after the original schema, in order. They're always written
# last, so a log whose header predates them stays valid without being
# rewritten (the log is never rewritten): newer rows simply carry them as
# trailing fields the old header doesn't name, mapped back here by position.
# Rows older than a column don't have it at all.
ADDED_FIELDS = ("time_limit_s", "timed_out")

_UNNAMED = "_unnamed"


def _read_rounds(path: Path = config.ROUNDS_CSV) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, restkey=_UNNAMED)
        rows = list(reader)
    unnamed = [name for name in ADDED_FIELDS if name not in (reader.fieldnames or [])]
    for row in rows:
        row.update(zip(unnamed, row.pop(_UNNAMED, [])))
    return rows


def _counts(rows: list[dict]) -> tuple[int, int]:
    """(correct, total) over a set of logged rounds."""
    n = len(rows)
    k = sum(1 for r in rows if r["correct"] == "True")
    return k, n


def _timed_out(row: dict) -> bool:
    return row.get("timed_out") == "True"  # absent on rows logged before the timer existed


def _timeouts(rows: list[dict]) -> int:
    """How many of the rounds ran out of time and were guessed at random."""
    return sum(1 for r in rows if _timed_out(r))


def _ups(rows: list[dict]) -> int:
    """How many of the player's own guesses were up -- random guesses made
    on a timeout aren't the player's, so they're left out."""
    return sum(1 for r in rows if r["guess"] == "1" and not _timed_out(r))


# --- Summary -------------------------------------------------------------

_LABEL_WIDTH = 11  # column the fraction starts at, for both labels
_FRACTION_WIDTH = 7  # minimum column the "(pct%)" starts at, relative to the fraction


def format_summary(
    session_k: int, session_n: int, lifetime_k: int, lifetime_n: int,
    session_up: int = 0, lifetime_up: int = 0,
    session_timeouts: int = 0, lifetime_timeouts: int = 0,
) -> str:
    """`*_up` count the player's own up guesses; `*_timeouts` count rounds
    guessed at random when the clock ran out. Timed-out rounds are scored
    like any other (a random guess keeps them a fair 50/50), but they're
    not the player's choice, so the guess split leaves them out."""
    session_pct = 100 * session_k / session_n if session_n else 0.0
    tail_pct = binomial_upper_tail(session_k, session_n) * 100

    lifetime_pct = 100 * lifetime_k / lifetime_n if lifetime_n else 0.0
    lo, hi = wilson_interval(lifetime_k, lifetime_n)
    lo_pct, hi_pct = lo * 100, hi * 100
    includes_50 = lo_pct <= 50.0 <= hi_pct
    verdict = "includes 50%." if includes_50 else "does not include 50%."

    indent = " " * _LABEL_WIDTH
    session_fraction = f"{session_k}/{session_n}"
    lifetime_fraction = f"{lifetime_k}/{lifetime_n}"
    # widen past the minimum when a fraction needs it (e.g. "138/296"), so
    # there's always a space before "(" and both percentages stay aligned
    fraction_width = max(_FRACTION_WIDTH, len(session_fraction) + 1, len(lifetime_fraction) + 1)

    # which way the guesses went, so a one-sided habit ("I always pick up")
    # is visible -- over the session, and over the whole log, where a habit
    # shows far more clearly. Not a result: no reference line needed, and
    # none implied.
    def guess_split(up: int, n: int) -> str:
        down = n - up
        up_pct = 100 * up / n if n else 0.0
        down_pct = 100 * down / n if n else 0.0
        return f"Guesses: {up_pct:.0f}% ({up}/{n}) up, {down_pct:.0f}% ({down}/{n}) down."

    # only when it happened: untimed play never shows the line
    def timeout_lines(timeouts: int, n: int) -> list[str]:
        return [f"{indent}Timed out: {timeouts}/{n}, guessed at random."] if timeouts else []

    lines = [
        f"{'Session:':<{_LABEL_WIDTH}}{session_fraction:<{fraction_width}}({session_pct:.1f}%)",
        f"{indent}A coin flip scores this well or better {tail_pct:.1f}% of the time.",
        f"{indent}{guess_split(session_up, session_n - session_timeouts)}",
        *timeout_lines(session_timeouts, session_n),
        "",
        f"{'Lifetime:':<{_LABEL_WIDTH}}{lifetime_fraction:<{fraction_width}}({lifetime_pct:.1f}%)",
        f"{indent}95% CI [{lo_pct:.1f}, {hi_pct:.1f}] — {verdict}",
        f"{indent}{guess_split(lifetime_up, lifetime_n - lifetime_timeouts)}",
        *timeout_lines(lifetime_timeouts, lifetime_n),
    ]
    return "\n".join(lines)


def summary(session_id: str, path: Path = config.ROUNDS_CSV) -> str:
    """Read the full CSV and build the session + lifetime summary.

    Neither line is ever shown without its chance reference (non-negotiable
    #3), and neither is softened, congratulated, or annotated. The terminal
    and the results screen both show exactly this text.
    """
    rows = _read_rounds(path)
    session_rows = [r for r in rows if r["session_id"] == session_id]

    session_k, session_n = _counts(session_rows)
    lifetime_k, lifetime_n = _counts(rows)

    return format_summary(
        session_k, session_n, lifetime_k, lifetime_n,
        _ups(session_rows), _ups(rows), _timeouts(session_rows), _timeouts(rows),
    )


def print_summary(session_id: str, path: Path = config.ROUNDS_CSV) -> None:
    print(summary(session_id, path))
