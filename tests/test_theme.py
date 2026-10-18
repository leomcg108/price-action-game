"""Light and dark themes: colours change, nothing else does.

The geometry test is the one that matters for non-negotiable #1: a theme
must never change what the question shows -- limits, positions, sizes.
"""

import random

import matplotlib

matplotlib.use("Agg")

import pytest
from matplotlib.colors import same_color

from intuition_trading import game, results, stats
from intuition_trading.puzzles import Corpus, generate_puzzle, load_corpus
from intuition_trading.theme import DARK, LIGHT

SEED = 20260824


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


def _geometry(fig, ax):
    return (
        ax.get_position().bounds, ax.get_xlim(), ax.get_ylim(),
        [b.ax.get_position().bounds for b in fig._buttons],
        fig.get_size_inches().tolist(),
    )


def test_themes_draw_identical_geometry(corpus: Corpus):
    for seed in range(10):
        view, answer = generate_puzzle(corpus, random.Random(seed))
        light_fig, light_ax = game.render(view, fig=game.new_figure(LIGHT))
        dark_fig, dark_ax = game.render(view, fig=game.new_figure(DARK))
        assert _geometry(light_fig, light_ax) == _geometry(dark_fig, dark_ax)

        game.reveal(light_fig, light_ax, view, answer, correct=True)
        game.reveal(dark_fig, dark_ax, view, answer, correct=True)
        assert _geometry(light_fig, light_ax) == _geometry(dark_fig, dark_ax)


def test_light_theme_keeps_the_original_colours(corpus: Corpus):
    view, _ = generate_puzzle(corpus, random.Random(SEED))
    fig, ax = game.render(view, fig=game.new_figure(LIGHT))
    assert same_color(fig.get_facecolor(), "white")
    assert same_color(ax.get_facecolor(), "#fafafa")
    assert same_color(fig._buttons[0].ax.get_facecolor(), "#eeeeee")


def test_dark_theme_colours_every_part_of_a_round(corpus: Corpus):
    view, answer = generate_puzzle(corpus, random.Random(SEED))
    fig, ax = game.render(view, 3, 10, fig=game.new_figure(DARK))
    fig.canvas.draw()

    assert same_color(fig.get_facecolor(), DARK.figure)
    assert same_color(ax.get_facecolor(), DARK.chart)
    assert all(same_color(t.get_color(), DARK.text) for t in ax.get_xticklabels())
    assert same_color(ax.xaxis.label.get_color(), DARK.text)
    assert all(same_color(b.ax.get_facecolor(), DARK.button) for b in fig._buttons)
    [counter] = ax.texts
    assert same_color(counter.get_color(), DARK.muted)

    game.reveal(fig, ax, view, answer, correct=False, timed_out=True, guess=1)
    reference_lines = [ln for ln in ax.lines if ln.get_linestyle() == ":"]
    assert reference_lines and all(same_color(ln.get_color(), DARK.muted) for ln in reference_lines)
    assert any(same_color(ln.get_color(), DARK.bad) for ln in ax.lines)  # the cross
    note = next(t for t in ax.texts if "random" in t.get_text())
    assert same_color(note.get_color(), DARK.note)


def test_dark_countdown_and_results(corpus: Corpus):
    fig = game.new_figure(DARK)
    countdown = game._Countdown(fig, 5)
    assert same_color(countdown.bar.get_facecolor(), DARK.countdown)
    countdown.stop()

    end = results.draw_results(fig, stats.format_summary(7, 10, 138, 296, session_up=6, lifetime_up=161))
    [text] = fig.texts
    frame = text.get_bbox_patch()
    assert same_color(text.get_color(), DARK.panel_text)
    assert same_color(frame.get_facecolor(), DARK.panel)
    assert same_color(frame.get_edgecolor(), DARK.frame)
    assert same_color(end.ax.get_facecolor(), DARK.end_button)


def test_new_figure_accepts_a_theme_name():
    assert game.theme_of(game.new_figure("dark")) is DARK
    assert game.theme_of(game.new_figure("light")) is LIGHT
