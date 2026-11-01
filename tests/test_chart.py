"""Candles or line: a session setting that changes how the bars are drawn,
and nothing else about the round.

Parametrized over every horizon where it matters: the line chart gets the
same no-leakage guarantees as candles -- no horizon data before the guess,
and y-limits from the lookback alone.
"""

import math
import random

import matplotlib

matplotlib.use("Agg")

import pytest
from matplotlib.colors import same_color

from intuition_trading import config, game
from intuition_trading.puzzles import Corpus, generate_puzzle, load_corpus
from intuition_trading.theme import LIGHT

SEED = 20260824


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


def _price_lines(ax):
    return [ln for ln in ax.lines if same_color(ln.get_color(), LIGHT.line)]


def _points(line) -> list[tuple[float, float]]:
    """The (x, y) points actually drawn; NaN padding draws nothing."""
    return [(x, y) for x, y in zip(line.get_xdata(), line.get_ydata()) if not math.isnan(y)]


def _geometry(ax):
    return ax.get_position().bounds, ax.get_xlim(), ax.get_ylim(), list(ax.get_xticks())


def test_candles_are_the_default():
    assert config.CHART_TYPE == "candle"
    assert config.CHART_TYPE in config.CHART_OPTIONS


@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_line_question_draws_only_the_lookback_closes(corpus: Corpus, horizon_bars: int):
    """Non-negotiable #1 for line charts: before the guess, the line holds
    the visible closes and nothing past the anchor."""
    rng = random.Random(SEED)
    for _ in range(20):
        view, _answer = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)
        _fig, ax = game.render(view, chart="line")

        [line] = _price_lines(ax)
        points = _points(line)
        assert [x for x, _y in points] == list(range(config.LOOKBACK_BARS))
        assert [y for _x, y in points] == pytest.approx(view.bars["close"].tolist())
        assert not ax.collections  # no candle bodies or wicks


@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_line_y_limits_come_from_the_lookback_alone(corpus: Corpus, horizon_bars: int):
    rng = random.Random(SEED)
    for _ in range(20):
        view, _answer = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)
        _fig, ax = game.render(view, chart="line")
        assert ax.get_ylim() == pytest.approx(game._range_ylim(view.bars))


def test_chart_type_doesnt_change_the_geometry(corpus: Corpus):
    """Same puzzle, same axes and limits either way, question and reveal."""
    for seed in range(10):
        view, answer = generate_puzzle(corpus, random.Random(seed))
        candle_fig, candle_ax = game.render(view, chart="candle")
        line_fig, line_ax = game.render(view, chart="line")
        assert _geometry(candle_ax) == _geometry(line_ax)

        game.reveal(candle_fig, candle_ax, view, answer, correct=True, chart="candle")
        game.reveal(line_fig, line_ax, view, answer, correct=True, chart="line")
        assert _geometry(candle_ax) == _geometry(line_ax)


def test_line_reveal_carries_on_from_the_anchor(corpus: Corpus):
    view, answer = generate_puzzle(corpus, random.Random(SEED))
    fig, ax = game.render(view, chart="line")
    game.reveal(fig, ax, view, answer, correct=True, chart="line")

    _lookback, horizon = _price_lines(ax)
    points = _points(horizon)
    anchor = config.LOOKBACK_BARS - 1

    assert points[0] == (anchor, pytest.approx(view.bars["close"].iloc[-1]))
    assert [x for x, _y in points[1:]] == list(range(anchor + 1, anchor + 1 + len(answer.horizon_bars)))
    assert [y for _x, y in points[1:]] == pytest.approx(answer.horizon_bars["close"].tolist())


def test_candle_reveal_doesnt_redraw_the_anchor_bar(corpus: Corpus, monkeypatch):
    """Only the line joins up to the anchor: what a candle reveal plots has
    the lookback blank, so it adds just the new bars."""
    view, answer = generate_puzzle(corpus, random.Random(SEED))
    fig, ax = game.render(view, chart="candle")

    plotted = []
    monkeypatch.setattr(game, "_plot_bars", lambda _ax, frame, _chart: plotted.append(frame))
    game.reveal(fig, ax, view, answer, correct=True, chart="candle")

    [frame] = plotted
    assert frame.iloc[: config.LOOKBACK_BARS].isna().all().all()


def test_session_setting_reaches_every_round_and_the_log(corpus: Corpus, tmp_path):
    path = tmp_path / "rounds.csv"
    results = game.run_session(
        corpus, rounds=3, seed=SEED, chart="line", on_round=lambda r: game.log_round(r, path=path),
        key_getter=lambda fig, valid_keys: "up", advance_getter=lambda fig: None,
    )
    assert [r.chart for r in results] == ["line"] * 3

    from intuition_trading import stats

    assert [r["chart"] for r in stats._read_rounds(path)] == ["line"] * 3


def test_line_rounds_look_up_the_same_puzzles_as_candles(corpus: Corpus):
    """With a seed, the chart type changes the drawing, not the sequence."""
    kwargs = dict(
        rounds=5, seed=SEED, key_getter=lambda fig, valid_keys: "up", advance_getter=lambda fig: None,
    )
    candles = game.run_session(corpus, chart="candle", **kwargs)
    lines = game.run_session(corpus, chart="line", **kwargs)
    assert [r.puzzle_id for r in candles] == [r.puzzle_id for r in lines]
