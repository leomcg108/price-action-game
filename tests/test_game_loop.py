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
from intuition_trading.puzzles import Corpus, generate_puzzle, load_corpus

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


def test_run_session_reuses_one_window(corpus: Corpus):
    """Every round draws into the same figure, so the window stays put
    instead of a new one popping up each round."""
    figs = []

    def recording_key(fig, valid_keys):
        figs.append(fig)
        return "up"

    game.run_session(
        corpus, rounds=4, seed=SEED, key_getter=recording_key, advance_getter=_noop_advance,
    )
    assert len(figs) == 4
    assert all(f is figs[0] for f in figs)


def test_run_session_plays_in_a_given_window_and_leaves_it_open(corpus: Corpus):
    """The start screen's window is handed to the session; the session must
    play in it and leave closing it to the caller."""
    import matplotlib.pyplot as plt

    fig = game.new_figure()
    seen = []

    def recording_key(f, valid_keys):
        seen.append(f)
        return "up"

    game.run_session(
        corpus, rounds=2, seed=SEED, key_getter=recording_key, advance_getter=_noop_advance, fig=fig,
    )
    assert all(f is fig for f in seen)
    assert plt.fignum_exists(fig.number)
    plt.close(fig)


def test_rerender_clears_the_previous_reveal(corpus: Corpus):
    """Reusing the figure must not carry the last round's horizon candles,
    result mark or widened y-limits into the next question."""
    rng = random.Random(SEED)
    view1, answer1 = generate_puzzle(corpus, rng)
    fig, ax1 = game.render(view1)
    game.reveal(fig, ax1, view1, answer1, correct=True)

    view2, _ = generate_puzzle(corpus, rng)
    fig2, ax2 = game.render(view2, fig=fig)

    assert fig2 is fig
    assert ax1 not in fig.axes
    assert len(fig.axes) == 4  # chart + three buttons
    assert ax2.get_ylim() == pytest.approx(game._range_ylim(view2.bars))
    assert not ax2.lines  # no reveal-only reference lines or result mark


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
