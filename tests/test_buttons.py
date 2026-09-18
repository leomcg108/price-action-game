"""Clickable Down/Up/Next square arrow buttons: an alternative to the
keyboard shortcuts, wired through the same fig._clicked_key path
_wait_for_key/_wait_for_any_key read from. No Quit button -- quitting stays
keyboard-only.
"""

import random
import threading
import time

import matplotlib

matplotlib.use("Agg")

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


def _fire(button):
    """Simulate a click without a real mouse event."""
    button._observers.process("clicked", None)


def test_three_square_buttons_created_down_up_next(corpus: Corpus):
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    fig, _ax = game.render(view)

    assert len(fig._buttons) == 3
    # no text labels -- just the arrow glyphs drawn on each button's axes
    assert all(b.label.get_text() == "" for b in fig._buttons)

    down_btn, up_btn, next_btn = fig._buttons
    bbox = down_btn.ax.get_position()
    fig_w, fig_h = fig.get_size_inches()
    # figure-fraction width/height aren't square themselves -- check the
    # actual physical (inch) dimensions the button renders at instead.
    assert bbox.width * fig_w == pytest.approx(bbox.height * fig_h, rel=0.01)


def test_button_click_sets_clicked_key(corpus: Corpus):
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    fig, _ax = game.render(view)
    down_btn, up_btn, next_btn = fig._buttons

    _fire(up_btn)
    assert fig._clicked_key == "up"

    _fire(down_btn)
    assert fig._clicked_key == "down"

    _fire(next_btn)
    assert fig._clicked_key == "next"


def test_stray_click_before_any_wait_does_not_raise(corpus: Corpus):
    """Clicking stops whatever event loop is active; with none running yet,
    that must be a no-op, not an error."""
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    fig, _ax = game.render(view)

    _fire(fig._buttons[0])  # should not raise
    assert fig._clicked_key == "down"


def test_wait_for_key_returns_the_clicked_button(corpus: Corpus):
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    fig, _ax = game.render(view)

    def click_up_soon():
        time.sleep(0.1)  # give _wait_for_key time to enter its event loop
        _fire(fig._buttons[1])  # Up

    t = threading.Thread(target=click_up_soon)
    t.start()
    key = game._wait_for_key(fig, ("up", "down", "q"))
    t.join(timeout=5)

    assert key == "up"


def test_wait_for_key_ignores_an_invalid_button_and_keeps_waiting(corpus: Corpus):
    """Next isn't a valid guess -- clicking it during the guess phase must
    be ignored (like a stray keypress), not returned as the answer."""
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    fig, _ax = game.render(view)
    down_btn, up_btn, next_btn = fig._buttons

    def click_next_then_down():
        time.sleep(0.1)
        _fire(next_btn)  # invalid for this phase -- must not end the wait
        time.sleep(0.1)
        _fire(down_btn)  # the real answer

    t = threading.Thread(target=click_next_then_down)
    t.start()
    key = game._wait_for_key(fig, ("up", "down", "q"))
    t.join(timeout=5)

    assert key == "down"


def test_wait_for_any_key_advances_on_the_next_button(corpus: Corpus):
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    fig, _ax = game.render(view)
    _down_btn, _up_btn, next_btn = fig._buttons

    def click_next_soon():
        time.sleep(0.1)  # give _wait_for_any_key time to enter its event loop
        _fire(next_btn)

    t = threading.Thread(target=click_next_soon)
    t.start()
    game._wait_for_any_key(fig)  # returns None either way; must not hang
    t.join(timeout=5)

    assert fig._clicked_key == "next"


def _real_click(fig, button):
    """A genuine press+release at the button's centre, routed through the
    canvas like a real mouse click (unlike _fire, which skips the widget's
    own mouse handling)."""
    from matplotlib.backend_bases import MouseButton, MouseEvent

    fig.canvas.draw()
    x, y = button.ax.transAxes.transform((0.5, 0.5))
    for name in ("button_press_event", "button_release_event"):
        MouseEvent(name, fig.canvas, x, y, button=MouseButton.LEFT)._process()


def test_clicking_after_rerender_hits_only_the_new_buttons(corpus: Corpus):
    """Rounds reuse one figure with the buttons in the same place. The old
    round's buttons must stop listening, or a click reaches them too and
    they fight the new ones for the mouse grab ("Another Axes already
    grabs mouse input")."""
    rng = random.Random(SEED)
    view1, _ = generate_puzzle(corpus, rng)
    fig, _ax = game.render(view1)
    old_buttons = fig._buttons

    view2, _ = generate_puzzle(corpus, rng)
    game.render(view2, fig=fig)

    old_hits = []
    for b in old_buttons:
        b.on_clicked(lambda _e: old_hits.append(1))

    _real_click(fig, fig._buttons[1])  # Up -- raised RuntimeError before the fix
    assert fig._clicked_key == "up"
    assert fig.canvas.mouse_grabber is None
    assert old_hits == []


def test_start_screen_buttons_stop_listening_once_the_game_starts(corpus: Corpus):
    from intuition_trading import launcher

    fig = game.new_figure()
    screen = launcher.Launcher(fig)
    rng = random.Random(SEED)
    view, _ = generate_puzzle(corpus, rng)
    game.render(view, fig=fig)

    _real_click(fig, screen.start_button)  # its old spot; must not start anything
    assert not screen.started
