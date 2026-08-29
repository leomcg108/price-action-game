"""One test that matters: the rendered view must never contain a bar from the
horizon. Two supporting checks ride along in the same file.

Parametrized over every selectable horizon (config.HORIZON_OPTIONS), not just
the default -- the horizon length is exactly the kind of change that could
quietly reintroduce leakage.
"""

import dataclasses
import random

import pytest

from intuition_trading.puzzles import Corpus, PuzzleView, generate_puzzle, load_corpus
from intuition_trading import config

N_PUZZLES = 200
SEED = 20260824


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_view_contains_no_future_bars(corpus: Corpus, horizon_bars: int):
    """The lookback view must contain no bar at or after the horizon start."""
    rng = random.Random(SEED)
    for _ in range(N_PUZZLES):
        view, answer = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)

        assert len(view.bars) == config.LOOKBACK_BARS
        assert len(answer.horizon_bars) == horizon_bars
        assert view.bars.index.max() < answer.horizon_bars.index.min()


@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_lookback_and_horizon_share_a_session(corpus: Corpus, horizon_bars: int):
    rng = random.Random(SEED)
    for _ in range(N_PUZZLES):
        view, answer = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)

        assert set(view.bars.index.date) == {answer.session_date}
        assert set(answer.horizon_bars.index.date) == {answer.session_date}


def test_puzzle_view_exposes_nothing_but_bars_id_and_horizon_width(corpus: Corpus):
    field_names = {f.name for f in dataclasses.fields(PuzzleView)}
    assert field_names == {"bars", "puzzle_id", "horizon_width"}

    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    # horizon_width is a bar count the player already chose, not price data;
    # everything else that could identify or reveal the outcome must be absent.
    for leaky_attr in ("ticker", "session_date", "horizon_bars", "label", "raw_return"):
        assert not hasattr(view, leaky_attr)
    assert isinstance(view.horizon_width, int)
