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


def _read_rounds(path: Path = config.ROUNDS_CSV) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _counts(rows: list[dict]) -> tuple[int, int]:
    """(correct, total) over a set of logged rounds."""
    n = len(rows)
    k = sum(1 for r in rows if r["correct"] == "True")
    return k, n


# --- Summary -------------------------------------------------------------

_LABEL_WIDTH = 11  # column the fraction starts at, for both labels
_FRACTION_WIDTH = 7  # column the "(pct%)" starts at, relative to the fraction


def format_summary(session_k: int, session_n: int, lifetime_k: int, lifetime_n: int) -> str:
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

    lines = [
        f"{'Session:':<{_LABEL_WIDTH}}{session_fraction:<{_FRACTION_WIDTH}}({session_pct:.1f}%)",
        f"{indent}A coin flip scores this well or better {tail_pct:.1f}% of the time.",
        "",
        f"{'Lifetime:':<{_LABEL_WIDTH}}{lifetime_fraction:<{_FRACTION_WIDTH}}({lifetime_pct:.1f}%)",
        f"{indent}95% CI [{lo_pct:.1f}, {hi_pct:.1f}] — {verdict}",
    ]
    return "\n".join(lines)


def print_summary(session_id: str, path: Path = config.ROUNDS_CSV) -> None:
    """Read the full CSV and print the session + lifetime summary.

    Neither line is ever shown without its chance reference (non-negotiable
    #3), and neither is softened, congratulated, or annotated.
    """
    rows = _read_rounds(path)
    session_rows = [r for r in rows if r["session_id"] == session_id]

    session_k, session_n = _counts(session_rows)
    lifetime_k, lifetime_n = _counts(rows)

    print(format_summary(session_k, session_n, lifetime_k, lifetime_n))
