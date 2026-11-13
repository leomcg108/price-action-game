"""Replay: the lookback's last bars arrive one at a time before the guess.

The replay only ever handles PuzzleView bars, all of which are on screen
before the guess anyway, so it can't leak the horizon. What these tests pin
down is that it draws exactly the bars it should, that the y-scale fits only
the bars shown so far, and that once it's finished the question is exactly
what a non-replay round shows.
"""

import math
import random
import threading
import time

import matplotlib

matplotlib.use("Agg")

import pytest
from matplotlib.backend_bases import KeyEvent
from matplotlib.colors import same_color

from intuition_trading import config, game
from intuition_trading.puzzles import Corpus, generate_puzzle, load_corpus
from intuition_trading.theme import LIGHT

SEED = 20260824
FIRST_SHOWN = config.LOOKBACK_BARS - config.REPLAY_BARS


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


def _instant_replay(fig, replay, seconds_per_bar):
    """Stands in for _run_replay: every bar at once, no waiting."""
    while not replay.done:
        replay.step()
    return True


def _key(key):
    return lambda fig, valid_keys: key


def _no_wait(fig):
    pass


def _line_closes(ax) -> list[float]:
    """The closes a line chart actually draws, in order (NaN padding draws
    nothing; the reveal-free charts here only have price lines)."""
    lines = [ln for ln in ax.lines if same_color(ln.get_color(), LIGHT.line)]
    points = {}
    for line in lines:
        for x, y in zip(line.get_xdata(), line.get_ydata()):
            if not math.isnan(y):
                points[int(x)] = y
    return [points[x] for x in sorted(points)]


def test_replay_settings_are_sane():
    assert 0 < config.REPLAY_BARS < config.LOOKBACK_BARS  # something is on screen from the start
    assert 0 in config.REPLAY_OPTIONS  # "Off"
    assert all(s >= 0 for s in config.REPLAY_OPTIONS)


@pytest.mark.parametrize("chart", config.CHART_OPTIONS)
def test_a_partial_question_draws_and_fits_only_its_shown_bars(corpus: Corpus, chart: str, monkeypatch):
    view, _ = generate_puzzle(corpus, random.Random(SEED))
    plotted = []
    real_plot = game._plot_bars
    monkeypatch.setattr(game, "_plot_bars", lambda ax, frame, c: (plotted.append(frame), real_plot(ax, frame, c)))

    _fig, ax = game.render(view, chart=chart, shown_bars=FIRST_SHOWN)

    [frame] = plotted
    assert frame.notna().all(axis=1).sum() == FIRST_SHOWN
    assert frame.iloc[FIRST_SHOWN:].isna().all().all()
    assert ax.get_ylim() == pytest.approx(game._range_ylim(view.bars.iloc[:FIRST_SHOWN]))


@pytest.mark.parametrize("chart", config.CHART_OPTIONS)
@pytest.mark.parametrize("horizon_bars", config.HORIZON_OPTIONS)
def test_the_scale_fits_only_the_bars_shown_so_far(corpus: Corpus, chart: str, horizon_bars: int):
    """Every step: y-limits from the bars on screen, never the ones still to
    come -- so the empty space never hints where the replay is going."""
    rng = random.Random(SEED)
    for _ in range(5):
        view, _ = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)
        _fig, ax = game.render(view, chart=chart, shown_bars=FIRST_SHOWN)
        replay = game._Replay(ax, view, FIRST_SHOWN, chart)
        while not replay.done:
            replay.step()
            assert ax.get_ylim() == pytest.approx(game._range_ylim(view.bars.iloc[: replay.shown]))


@pytest.mark.parametrize("chart", config.CHART_OPTIONS)
def test_each_step_adds_exactly_the_next_bar(corpus: Corpus, chart: str, monkeypatch):
    view, _ = generate_puzzle(corpus, random.Random(SEED))
    _fig, ax = game.render(view, chart=chart, shown_bars=FIRST_SHOWN)
    replay = game._Replay(ax, view, FIRST_SHOWN, chart)

    plotted = []
    monkeypatch.setattr(game, "_plot_bars", lambda _ax, frame, _c: plotted.append(frame))
    while not replay.done:
        replay.step()

    assert len(plotted) == config.REPLAY_BARS
    for i, frame in zip(range(FIRST_SHOWN, config.LOOKBACK_BARS), plotted):
        drawn = frame.notna().all(axis=1)
        # the new bar, plus for a line the previous close it joins up from
        expected = {i - 1, i} if chart == "line" else {i}
        assert set(drawn[drawn].index.map(frame.index.get_loc)) == expected
        assert frame.iloc[config.LOOKBACK_BARS :].isna().all().all()  # never anything past the anchor


@pytest.mark.parametrize("chart", config.CHART_OPTIONS)
def test_a_finished_replay_is_the_ordinary_question(corpus: Corpus, chart: str):
    view, _ = generate_puzzle(corpus, random.Random(SEED))
    _fig, plain_ax = game.render(view, chart=chart)
    _fig, replay_ax = game.render(view, chart=chart, shown_bars=FIRST_SHOWN)
    _instant_replay(None, game._Replay(replay_ax, view, FIRST_SHOWN, chart), 0)

    assert replay_ax.get_ylim() == plain_ax.get_ylim()
    assert replay_ax.get_xlim() == plain_ax.get_xlim()
    if chart == "line":
        assert _line_closes(replay_ax) == pytest.approx(view.bars["close"].tolist())


def test_a_replay_round_is_logged_with_its_settings(corpus: Corpus):
    result = game.play_round(
        corpus, random.Random(SEED), "s", key_getter=_key("up"), advance_getter=_no_wait,
        replay_s=0.5, replay_runner=_instant_replay,
    )
    assert result.replay_s == 0.5
    assert result.replay_bars == config.REPLAY_BARS


def test_without_replay_nothing_is_replayed(corpus: Corpus):
    calls = []
    result = game.play_round(
        corpus, random.Random(SEED), "s", key_getter=_key("up"), advance_getter=_no_wait,
        replay_runner=lambda *args: calls.append(args) or True,
    )
    assert calls == []
    assert result.replay_s == 0 and result.replay_bars == 0


def test_the_clock_and_timer_start_once_the_replay_is_done(corpus: Corpus, monkeypatch):
    """ms_to_answer and the countdown measure the decision, not the replay."""
    events = []

    def slow_replay(fig, replay, seconds_per_bar):
        _instant_replay(fig, replay, seconds_per_bar)
        time.sleep(0.05)
        events.append(("replay done", time.monotonic()))
        return True

    real_countdown = game._Countdown

    class RecordingCountdown(real_countdown):
        def __init__(self, *args, **kwargs):
            events.append(("countdown", time.monotonic()))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(game, "_Countdown", RecordingCountdown)
    result = game.play_round(
        corpus, random.Random(SEED), "s", key_getter=_key("up"), advance_getter=_no_wait,
        replay_s=1, replay_runner=slow_replay, time_limit=5,
    )

    assert [name for name, _ in events] == ["replay done", "countdown"]
    assert result.ms_to_answer < 50  # the 50 ms spent replaying isn't counted


def test_quitting_mid_replay_ends_the_round_unlogged(corpus: Corpus):
    logged, asked = [], []
    result = game.play_round(
        corpus, random.Random(SEED), "s", key_getter=lambda fig, keys: asked.append(keys) or "up",
        advance_getter=_no_wait, on_round=logged.append,
        replay_s=1, replay_runner=lambda fig, replay, s: False,
    )
    assert result is None
    assert logged == [] and asked == []  # never got as far as the guess


def test_replay_doesnt_change_a_seeded_puzzle_sequence(corpus: Corpus):
    kwargs = dict(rounds=5, seed=SEED, key_getter=_key("up"), advance_getter=_no_wait)
    plain = game.run_session(corpus, **kwargs)
    replayed = game.run_session(corpus, replay_s=1, replay_runner=_instant_replay, **kwargs)
    assert [r.puzzle_id for r in plain] == [r.puzzle_id for r in replayed]


# --- the real runner, end to end, with a timer we can fire by hand ----------


class _FakeTimer:
    def __init__(self):
        self.callbacks = []
        self.running = False

    def add_callback(self, fn):
        self.callbacks.append(fn)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def fire(self):
        for fn in self.callbacks:
            fn()


def _setup_real_runner(corpus, monkeypatch):
    view, _ = generate_puzzle(corpus, random.Random(SEED))
    fig, ax = game.render(view, shown_bars=FIRST_SHOWN)
    timer = _FakeTimer()
    monkeypatch.setattr(fig.canvas, "new_timer", lambda interval: timer)
    return fig, game._Replay(ax, view, FIRST_SHOWN, "candle"), timer


def _once_waiting(fig, action):
    def run():
        deadline = time.monotonic() + 5
        while not getattr(fig.canvas, "_looping", False) and time.monotonic() < deadline:
            time.sleep(0.01)
        action()

    t = threading.Thread(target=run)
    t.start()
    return t


def test_real_runner_steps_until_every_bar_is_in(corpus: Corpus, monkeypatch):
    fig, replay, timer = _setup_real_runner(corpus, monkeypatch)

    def tick_until_done():
        while timer.running:
            timer.fire()

    t = _once_waiting(fig, tick_until_done)
    assert game._run_replay(fig, replay, 0.5) is True
    t.join(timeout=5)
    assert replay.done


def test_real_runner_ignores_guesses_but_honours_q(corpus: Corpus, monkeypatch):
    fig, replay, timer = _setup_real_runner(corpus, monkeypatch)

    def press(key):
        fig.canvas.callbacks.process("key_press_event", KeyEvent("key_press_event", fig.canvas, key))

    def guess_then_quit():
        timer.fire()
        press("up")  # ignored: guesses wait for the replay to finish
        time.sleep(0.05)
        press("q")

    t = _once_waiting(fig, guess_then_quit)
    assert game._run_replay(fig, replay, 0.5) is False
    t.join(timeout=5)
    assert replay.shown == FIRST_SHOWN + 1  # stopped where it was
    assert not timer.running
