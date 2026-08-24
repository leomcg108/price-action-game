"""Binomial tail, Wilson interval, and summary formatting."""

import math
import random

import matplotlib

matplotlib.use("Agg")

from intuition_trading import game, stats

SEED = 20260824


def test_binomial_upper_tail_matches_spec_example():
    # spec's own worked example: a 20-round session at 12/20 (60%)
    assert round(stats.binomial_upper_tail(12, 20) * 100, 1) == 25.2


def test_binomial_upper_tail_edge_cases():
    assert stats.binomial_upper_tail(0, 0) == 1.0
    assert stats.binomial_upper_tail(1, 1) == 0.5
    assert stats.binomial_upper_tail(0, 1) == 1.0
    assert math.isclose(stats.binomial_upper_tail(10, 10), 0.5**10)


def test_binomial_upper_tail_is_the_survival_function():
    # P(X >= 0) is always 1; P(X >= n+1) would be 0, so P(X>=n) is the smallest mass
    n = 20
    total = sum(
        math.comb(n, i) * 0.5**n for i in range(n + 1)
    )
    assert math.isclose(total, 1.0)
    assert stats.binomial_upper_tail(0, n) == 1.0


def test_wilson_interval_matches_spec_example_within_rounding():
    lo, hi = stats.wilson_interval(96, 180)
    # spec's illustrative text says [46.0, 60.5]; the exact Wilson score
    # formula (verified against the standard closed-form reference) gives
    # 46.0518%, which rounds to 46.1 -- one tick above the spec's example.
    # Treating the formula (not the rounded example) as authoritative.
    assert round(lo * 100, 1) == 46.1
    assert round(hi * 100, 1) == 60.5


def test_wilson_interval_bounds_and_symmetry():
    lo, hi = stats.wilson_interval(90, 180)  # exactly 50%
    assert lo < 0.5 < hi
    assert math.isclose((lo + hi) / 2, 0.5, abs_tol=1e-9)

    lo, hi = stats.wilson_interval(0, 0)
    assert (lo, hi) == (0.0, 0.0)

    lo, hi = stats.wilson_interval(180, 180)
    assert 0.0 <= lo < hi <= 1.0


def test_format_summary_matches_spec_shape():
    text = stats.format_summary(session_k=12, session_n=20, lifetime_k=96, lifetime_n=180)
    lines = text.split("\n")

    assert lines[0] == "Session:   12/20  (60.0%)"
    assert lines[1] == "           A coin flip scores this well or better 25.2% of the time."
    assert lines[2] == ""
    assert lines[3] == "Lifetime:  96/180 (53.3%)"
    assert lines[4] == "           95% CI [46.1, 60.5] — includes 50%."


def test_format_summary_reports_excludes_50_when_interval_is_clear():
    text = stats.format_summary(session_k=18, session_n=20, lifetime_k=170, lifetime_n=180)
    assert text.endswith("does not include 50%.")


def test_format_summary_never_shows_a_bare_percentage_line():
    """Non-negotiable #3: every result line carries its reference on the
    very next line."""
    text = stats.format_summary(12, 20, 96, 180)
    lines = text.split("\n")
    assert "coin flip" in lines[1]
    assert "95% CI" in lines[4]


def _fixed_key(key: str):
    def getter(fig, valid_keys):
        return key

    return getter


def test_print_summary_reads_session_and_lifetime_from_csv(tmp_path, capsys):
    from intuition_trading.puzzles import load_corpus

    corpus = load_corpus()
    if not corpus.valid_sessions:
        import pytest

        pytest.skip("no data in data/bars/ -- run fetch.py first")

    path = tmp_path / "rounds.csv"

    # an earlier "lifetime" session, fully logged
    game.run_session(
        corpus, rounds=4, seed=1, session_id="old-session",
        on_round=lambda r: game.log_round(r, path=path),
        key_getter=_fixed_key("up"), advance_getter=lambda fig: None,
    )

    # the "current" session
    game.run_session(
        corpus, rounds=3, seed=2, session_id="current-session",
        on_round=lambda r: game.log_round(r, path=path),
        key_getter=_fixed_key("up"), advance_getter=lambda fig: None,
    )

    capsys.readouterr()  # discard anything printed so far
    stats.print_summary("current-session", path=path)
    out = capsys.readouterr().out

    lines = out.split("\n")
    assert lines[0].startswith("Session:")
    assert "/3 " in lines[0]  # current session only: 3 rounds
    assert lines[3].startswith("Lifetime:")
    assert "/7 " in lines[3]  # old (4) + current (3) = 7 rounds
