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
    assert config.LAUNCHER_TIMER in config.TIMER_OPTIONS


def test_cli_defaults_are_offered_options():
    """The --horizon/--timer defaults must be values those flags accept."""
    assert config.HORIZON_BARS in config.HORIZON_OPTIONS
    assert config.TIMER_SECONDS in config.TIMER_OPTIONS


@pytest.mark.parametrize("word", ["INTUITION", "TRADING"])
def test_banner_rows_line_up(word):
    rows = launcher.banner(word).split("\n")
    assert len(rows) == 6
    assert len({len(r) for r in rows}) == 1


def test_one_button_per_option(screen):
    assert list(screen.round_buttons) == list(config.ROUND_OPTIONS)
    assert list(screen.horizon_buttons) == list(config.HORIZON_OPTIONS)
    assert list(screen.timer_buttons) == list(config.TIMER_OPTIONS)


def test_timer_buttons_read_off_then_seconds(screen):
    labels = [b.label.get_text() for b in screen.timer_buttons.values()]
    assert labels == ["Off"] + [f"{s} s" for s in config.TIMER_OPTIONS if s]


def test_start_straight_away_uses_the_defaults(screen):
    t = _in_background(screen.fig, lambda: _fire(screen.start_button))
    assert screen.wait() == (config.LAUNCHER_ROUNDS, config.LAUNCHER_HORIZON, config.LAUNCHER_TIMER)
    t.join(timeout=5)


def test_selections_are_passed_through(screen):
    rounds, horizon, timer = config.ROUND_OPTIONS[-1], config.HORIZON_OPTIONS[0], config.TIMER_OPTIONS[-1]

    def pick_then_start():
        _fire(screen.round_buttons[rounds])
        _fire(screen.horizon_buttons[horizon])
        _fire(screen.timer_buttons[timer])
        _fire(screen.start_button)

    t = _in_background(screen.fig, pick_then_start)
    assert screen.wait() == (rounds, horizon, timer)
    t.join(timeout=5)


def test_only_the_chosen_option_is_highlighted(screen):
    choice = config.ROUND_OPTIONS[1]
    _fire(screen.round_buttons[choice])
    for value, button in screen.round_buttons.items():
        assert (button.color == game.theme_of(screen.fig).selected) == (value == choice)


def test_q_leaves_without_starting(screen):
    press_q = KeyEvent("key_press_event", screen.fig.canvas, "q")
    t = _in_background(screen.fig, lambda: screen.fig.canvas.callbacks.process("key_press_event", press_q))
    assert screen.wait() is None
    t.join(timeout=5)


def test_theme_row_offers_light_and_dark(screen):
    assert list(screen.theme_buttons) == ["light", "dark"]
    assert [b.label.get_text() for b in screen.theme_buttons.values()] == ["Light", "Dark"]


def test_choosing_dark_switches_the_whole_screen(screen):
    from matplotlib.colors import same_color

    from intuition_trading.theme import DARK

    _fire(screen.theme_buttons["dark"])
    assert game.theme_of(screen.fig) is DARK
    assert same_color(screen.fig.get_facecolor(), DARK.figure)
    assert all(same_color(t.get_color(), DARK.banner) for t in screen._texts[:2])
    assert same_color(screen.round_buttons[config.LAUNCHER_ROUNDS].ax.get_facecolor(), DARK.selected)
    assert same_color(screen.round_buttons[config.ROUND_OPTIONS[-1]].ax.get_facecolor(), DARK.button)
    # borders too: made under the light theme, they'd otherwise stay near-white
    for button in (*screen.round_buttons.values(), screen.start_button):
        assert all(same_color(s.get_edgecolor(), DARK.spine) for s in button.ax.spines.values())


def test_the_session_after_the_start_screen_keeps_its_theme():
    """The theme is chosen on the start screen but used by every round
    drawn into the same window afterwards."""
    import random

    from matplotlib.colors import same_color

    from intuition_trading.puzzles import generate_puzzle, load_corpus
    from intuition_trading.theme import DARK

    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")

    fig = game.new_figure("light")
    screen = launcher.Launcher(fig)
    _fire(screen.theme_buttons["dark"])

    view, _ = generate_puzzle(corpus, random.Random(1))
    _, ax = game.render(view, fig=fig)
    assert same_color(ax.get_facecolor(), DARK.chart)
    assert same_color(fig.get_facecolor(), DARK.figure)


def test_theme_defaults_are_real_themes():
    from intuition_trading.theme import THEMES

    assert config.THEME in THEMES
