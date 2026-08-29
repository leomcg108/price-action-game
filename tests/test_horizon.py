"""Selectable prediction horizon (10/20/30 minutes)."""

import random

import matplotlib

matplotlib.use("Agg")

import pytest

from intuition_trading import config, game
from intuition_trading.puzzles import Corpus, _puzzle_id, generate_puzzle, load_corpus

SEED = 20260824


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_generate_puzzle_honours_the_requested_horizon(corpus: Corpus, horizon_bars: int):
    rng = random.Random(SEED)
    view, answer = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)

    assert view.horizon_width == horizon_bars
    assert len(answer.horizon_bars) == horizon_bars
    # raw_return must be measured over the full requested horizon, not a
    # fixed default: it's the pct-from-anchor of the *last* horizon bar's
    # close, which is exactly what raw_return computes directly.
    assert answer.raw_return == pytest.approx(answer.horizon_bars["close"].iloc[-1], abs=1e-9)


def test_puzzle_id_changes_with_horizon():
    """Same anchor, different horizon -- a different puzzle, so it needs a
    different id (otherwise two genuinely different puzzles would collide
    in rounds.csv under the same puzzle_id)."""
    ids = {
        _puzzle_id("abc123", "AAPL", "2026-01-05", 200, horizon_bars)
        for horizon_bars in config.HORIZON_OPTIONS
    }
    assert len(ids) == len(config.HORIZON_OPTIONS)


def test_corpus_supports_the_longest_horizon(corpus: Corpus):
    """valid_sessions is built once, before any session's horizon choice is
    known, so it must already support the largest option."""
    rng = random.Random(SEED)
    for _ in range(50):
        view, answer = generate_puzzle(corpus, rng, horizon_bars=max(config.HORIZON_OPTIONS))
        assert len(answer.horizon_bars) == max(config.HORIZON_OPTIONS)


@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_render_reserves_the_correct_width(corpus: Corpus, horizon_bars: int):
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)
    fig, ax = game.render(view)
    total_bars = config.LOOKBACK_BARS + horizon_bars
    assert ax.get_xlim() == (-0.5, total_bars - 0.5)


def _fixed_key(key: str):
    def getter(fig, valid_keys):
        return key

    return getter


@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_session_logs_the_chosen_horizon(corpus: Corpus, horizon_bars: int, tmp_path):
    path = tmp_path / "rounds.csv"
    results = game.run_session(
        corpus, rounds=2, seed=SEED, horizon_bars=horizon_bars,
        on_round=lambda r: game.log_round(r, path=path),
        key_getter=_fixed_key("up"), advance_getter=lambda fig: None,
    )
    assert len(results) == 2
    assert all(r.horizon_bars == horizon_bars for r in results)
