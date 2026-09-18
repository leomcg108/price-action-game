"""Start screen: option buttons pick rounds/horizon, Start returns them,
leaving without starting returns None."""

import threading
import time
import matplotlib

matplotlib.use("Agg")

import pytest
from matplotlib.backend_bases import KeyEvent

from intuition_trading import config, game, launcher


def _fire(button):
    """Simulate a click without a real mouse event."""
    button._observers.process("clicked", None)


def _in_background(fig, action):
    """Run `action` once `fig`'s blocking event loop is actually running --
    fired any earlier, entering the loop would reset its stop flag and the
    test would hang. Real GUI events are only ever delivered from inside it."""

    def run():
        deadline = time.monotonic() + 5
        while not getattr(fig.canvas, "_looping", False) and time.monotonic() < deadline:
            time.sleep(0.01)
        action()

    t = threading.Thread(target=run)
    t.start()
    return t


@pytest.fixture
def screen():
    return launcher.Launcher(game.new_figure())


def test_launcher_defaults_are_offered_options():
    assert config.LAUNCHER_ROUNDS in config.ROUND_OPTIONS
    assert config.LAUNCHER_HORIZON in config.HORIZON_OPTIONS


@pytest.mark.parametrize("word", ["INTUITION", "TRADING"])
def test_banner_rows_line_up(word):
    rows = launcher.banner(word).split("\n")
    assert len(rows) == 6
    assert len({len(r) for r in rows}) == 1


def test_one_button_per_option(screen):
    assert list(screen.round_buttons) == list(config.ROUND_OPTIONS)
    assert list(screen.horizon_buttons) == list(config.HORIZON_OPTIONS)


def test_start_straight_away_uses_the_defaults(screen):
    t = _in_background(screen.fig, lambda: _fire(screen.start_button))
    assert screen.wait() == (config.LAUNCHER_ROUNDS, config.LAUNCHER_HORIZON)
    t.join(timeout=5)


def test_selections_are_passed_through(screen):
    rounds, horizon = config.ROUND_OPTIONS[-1], config.HORIZON_OPTIONS[0]

    def pick_then_start():
        _fire(screen.round_buttons[rounds])
        _fire(screen.horizon_buttons[horizon])
        _fire(screen.start_button)

    t = _in_background(screen.fig, pick_then_start)
    assert screen.wait() == (rounds, horizon)
    t.join(timeout=5)


def test_only_the_chosen_option_is_highlighted(screen):
    choice = config.ROUND_OPTIONS[1]
    _fire(screen.round_buttons[choice])
    for value, button in screen.round_buttons.items():
        assert (button.color == launcher._SELECTED) == (value == choice)


def test_q_leaves_without_starting(screen):
    press_q = KeyEvent("key_press_event", screen.fig.canvas, "q")
    t = _in_background(screen.fig, lambda: screen.fig.canvas.callbacks.process("key_press_event", press_q))
    assert screen.wait() is None
    t.join(timeout=5)
