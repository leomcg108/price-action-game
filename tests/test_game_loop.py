"""Session-loop logic, exercised without a live GUI event loop.

`play_round`/`run_session` take `key_getter`/`advance_getter` so the real
blocking `_wait_for_key`/`_wait_for_any_key` (which need an interactive
matplotlib backend) can be swapped for fakes here.
"""

import random

import matplotlib

matplotlib.use("Agg")  # headless: no window, no real event loop

import pytest

from intuition_trading import game
from intuition_trading.puzzles import Corpus, load_corpus

SEED = 20260824


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


def _fixed_key(key: str):
    def getter(fig, valid_keys):
        assert key in valid_keys
        return key

    return getter


def _noop_advance(fig):
    pass


def test_play_round_scores_against_the_true_label(corpus: Corpus):
    rng = random.Random(SEED)
    result = game.play_round(
        corpus, rng, "session-1", key_getter=_fixed_key("up"), advance_getter=_noop_advance
    )
    assert result is not None
    assert result.guess == 1
    assert result.correct == (result.guess == result.label)


def test_play_round_quit_returns_none(corpus: Corpus):
    rng = random.Random(SEED)
    result = game.play_round(
        corpus, rng, "session-1", key_getter=_fixed_key("q"), advance_getter=_noop_advance
    )
    assert result is None


def test_run_session_plays_the_requested_number_of_rounds(corpus: Corpus):
    seen = []
    results = game.run_session(
        corpus, rounds=5, seed=SEED, on_round=seen.append,
        key_getter=_fixed_key("up"), advance_getter=_noop_advance,
    )
    assert len(results) == 5
    assert len(seen) == 5
    assert [r.round_id for r in results] == [r.round_id for r in seen]


def test_run_session_stops_early_on_quit(corpus: Corpus):
    calls = {"n": 0}

    def quits_on_third_round(fig, valid_keys):
        calls["n"] += 1
        return "q" if calls["n"] == 3 else "up"

    results = game.run_session(
        corpus, rounds=10, seed=SEED,
        key_getter=quits_on_third_round, advance_getter=_noop_advance,
    )

    assert len(results) == 2  # the quit round itself is not logged
    assert calls["n"] == 3


def test_on_round_fires_before_reveal(corpus: Corpus):
    order = []

    def recording_key(fig, valid_keys):
        return "up"

    def recording_advance(fig):
        order.append("advance")

    rng = random.Random(SEED)
    game.play_round(
        corpus,
        rng,
        "session-1",
        key_getter=recording_key,
        advance_getter=recording_advance,
        on_round=lambda r: order.append("logged"),
    )
    assert order == ["logged", "advance"]


def test_session_summary_never_prints_a_raw_score(corpus: Corpus, capsys):
    """Non-negotiable #3: stats.py doesn't exist yet (step 7), so step 5
    must not print anything score-shaped in the meantime."""
    game.run_session(
        corpus, rounds=3, seed=SEED, on_round=lambda r: None,
        key_getter=_fixed_key("up"), advance_getter=_noop_advance,
    )
    # play_round/run_session themselves must not print per-round or
    # session-level results; only the __main__ CLI prints a round count.
    captured = capsys.readouterr()
    assert captured.out == ""
