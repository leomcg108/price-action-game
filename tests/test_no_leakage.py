"""One test that matters: the rendered view must never contain a bar from the
horizon. Two supporting checks ride along in the same file.
"""

import dataclasses
import random

import pytest

from intuition_trading.puzzles import Corpus, PuzzleView, generate_puzzle, load_corpus
from intuition_trading import config

N_PUZZLES = 500
SEED = 20260824


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


def test_view_contains_no_future_bars(corpus: Corpus):
    """The lookback view must contain no bar at or after the horizon start."""
    rng = random.Random(SEED)
    for _ in range(N_PUZZLES):
        view, answer = generate_puzzle(corpus, rng)

        assert len(view.bars) == config.LOOKBACK_BARS
        assert view.bars.index.max() < answer.horizon_bars.index.min()


def test_lookback_and_horizon_share_a_session(corpus: Corpus):
    rng = random.Random(SEED)
    for _ in range(N_PUZZLES):
        view, answer = generate_puzzle(corpus, rng)

        assert set(view.bars.index.date) == {answer.session_date}
        assert set(answer.horizon_bars.index.date) == {answer.session_date}


def test_puzzle_view_exposes_nothing_but_bars_and_id(corpus: Corpus):
    field_names = {f.name for f in dataclasses.fields(PuzzleView)}
    assert field_names == {"bars", "puzzle_id"}

    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    for leaky_attr in ("ticker", "session_date", "horizon_bars", "label", "raw_return"):
        assert not hasattr(view, leaky_attr)
