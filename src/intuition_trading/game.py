"""Session loop, chart rendering, input handling, logging, and summary for the
price-action game.
"""

from __future__ import annotations

import csv
import os
import random
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from matplotlib.ticker import FuncFormatter
from matplotlib.widgets import Button

from intuition_trading import config
from intuition_trading.puzzles import Corpus, PuzzleAnswer, PuzzleView, generate_puzzle

_STYLE = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle="")


# --- Chart -------------------------------------------------------------


def _to_mpf_frame(bars: pd.DataFrame, total_bars: int) -> pd.DataFrame:
    """Lay `bars` onto a synthetic, contiguous 1-minute timeline and pad it
    out to `total_bars` (LOOKBACK_BARS + the session's chosen horizon) rows
    with NaN OHLC.

    mplfinance plots at sequential integer positions regardless of the actual
    calendar spacing of a DatetimeIndex, so this both avoids gaps in the
    rendered candles and, via the trailing NaN rows -- which mplfinance
    simply leaves blank -- reserves the horizon's width as empty space
    without ever handing mplfinance real horizon data.
    """
    synthetic_index = pd.date_range("2000-01-01", periods=total_bars, freq="1min")
    frame = pd.DataFrame(index=synthetic_index, columns=["Open", "High", "Low", "Close"], dtype=float)
    frame.iloc[: len(bars)] = bars[["open", "high", "low", "close"]].to_numpy()
    return frame


def _horizon_frame(horizon_bars: pd.DataFrame, total_bars: int) -> pd.DataFrame:
    """Horizon bars laid onto the same synthetic timeline, at the offset
    right after the lookback, with everything before left NaN so replotting
    onto the existing axes only adds the new candles."""
    synthetic_index = pd.date_range("2000-01-01", periods=total_bars, freq="1min")
    frame = pd.DataFrame(index=synthetic_index, columns=["Open", "High", "Low", "Close"], dtype=float)
    frame.iloc[config.LOOKBACK_BARS :] = horizon_bars[["open", "high", "low", "close"]].to_numpy()
    return frame


def _range_ylim(bars: pd.DataFrame) -> tuple[float, float]:
    """Y-limits spanning `bars`, padded 10% of their range each side."""
    lo = float(bars[["open", "high", "low", "close"]].min().min())
    hi = float(bars[["open", "high", "low", "close"]].max().max())
    span = hi - lo
    pad = span * 0.10 if span > 0 else 1.0
    return lo - pad, hi + pad


def _expand_ylim(
    current: tuple[float, float], lookback: pd.DataFrame, horizon: pd.DataFrame
) -> tuple[float, float]:
    """The reveal is permitted to see the future; the question is not. Widen
    the question's y-limits to fit the horizon too, but never shrink them."""
    lo, hi = _range_ylim(pd.concat([lookback, horizon]))
    return min(current[0], lo), max(current[1], hi)


def _style_axes(ax, ylim: tuple[float, float], total_bars: int) -> None:
    ax.set_xlim(-0.5, total_bars - 0.5)
    ax.set_ylim(*ylim)

    ticks = list(range(0, total_bars, 10))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_xlabel("bar index")
    ax.set_ylabel("% from anchor")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:.2f}"))
    ax.set_title("")
    ax.grid(False)


def _draw_round_counter(ax, round_num: int, total_rounds: int) -> None:
    """Small, muted "n/total" in the top-right corner. Round progress only --
    not a score, not a tally of correct/incorrect, so it doesn't run into the
    "no running score" rule: it can't be read as a performance number."""
    ax.text(
        0.97, 0.94, f"{round_num}/{total_rounds}",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=9, color="#999999",
    )


_CHART_BOTTOM = 0.27  # figure-fraction y where the chart's own axes start


def _reserve_button_space(fig, ax) -> None:
    """Shrink the main chart axes (and mplfinance's hidden twin, which
    shares its position exactly) to leave room at the bottom for tick
    labels and the buttons.

    fig.subplots_adjust() has no effect here: mplfinance positions its axes
    directly via set_position()/add_axes(), bypassing the subplot grid that
    subplots_adjust controls.
    """
    old_bounds = ax.get_position().bounds
    x0, y0, width, height = old_bounds
    top = y0 + height
    new_pos = [x0, _CHART_BOTTOM, width, top - _CHART_BOTTOM]
    for a in fig.axes:
        if a.get_position().bounds == old_bounds:
            a.set_position(new_pos)


def _draw_arrow(bax, direction: str, color: str) -> None:
    """A thick, colour-coordinated arrow -- the button's only marking, drawn
    on the button's own axes rather than relying on font glyphs/weight."""
    bax.set_xlim(0, 1)
    bax.set_ylim(0, 1)
    # no axis('off') here -- that hides the button's own background patch
    # (fill + border) along with the ticks; Button already starts tickless.
    endpoints = {
        "down": ((0.5, 0.75), (0.5, 0.25)),
        "up": ((0.5, 0.25), (0.5, 0.75)),
        "right": ((0.25, 0.5), (0.75, 0.5)),
    }
    xytext, xy = endpoints[direction]
    bax.annotate(
        "", xy=xy, xytext=xytext,
        arrowprops=dict(arrowstyle="-|>", color=color, lw=4, mutation_scale=28),
    )


def _install_buttons(fig) -> None:
    """Square Down/Up/Next buttons at the bottom of the figure -- an
    optional mouse path alongside the keyboard shortcuts, not a replacement
    for them. No quit button: quitting stays a deliberate keyboard action.

    Clicking one writes the matching key name into fig._clicked_key and
    stops whatever event loop is currently blocking, exactly like pressing
    the key would; _wait_for_key/_wait_for_any_key read from that same
    attribute, so both input paths are handled by one code path there.
    _wait_for_key additionally filters out clicks that aren't valid for the
    current phase (e.g. Next during guessing), the same as it already does
    for stray keypresses.
    """
    fig._clicked_key = None

    def make_handler(key: str):
        def handler(_event):
            fig._clicked_key = key
            fig.canvas.stop_event_loop()

        return handler

    # figure-fraction units aren't square pixels -- scale height by the
    # figure's aspect ratio so the buttons render as actual squares.
    fig_w, fig_h = fig.get_size_inches()
    width = 0.09
    height = width * (fig_w / fig_h)
    gap = 0.03
    y = 0.06
    left0 = 0.5 - (3 * width + 2 * gap) / 2

    specs = [("down", "#c62828"), ("up", "#2e7d32"), ("right", "#616161")]
    buttons = []
    for i, (direction, color) in enumerate(specs):
        left = left0 + i * (width + gap)
        bax = fig.add_axes([left, y, width, height])
        button = Button(bax, "", color="#eeeeee", hovercolor="#e0e0e0")
        bax.patch.set_edgecolor("#bbbbbb")
        bax.patch.set_linewidth(1)
        _draw_arrow(bax, direction, color)
        key = "next" if direction == "right" else direction
        button.on_clicked(make_handler(key))
        buttons.append(button)

    fig._buttons = buttons  # keep references alive -- matplotlib drops unreferenced widgets


def render(view: PuzzleView, round_num: int = 1, total_rounds: int = 1):
    """Render the question: lookback candles only, with the horizon's width
    reserved as empty space to the right.

    The signature accepts PuzzleView plus two plain session-progress ints --
    never PuzzleAnswer or anything derived from it. That's what structurally
    enforces non-negotiable #1; round_num/total_rounds can't carry price or
    outcome data no matter what.
    """
    total_bars = config.LOOKBACK_BARS + view.horizon_width
    frame = _to_mpf_frame(view.bars, total_bars)

    fig, axlist = mpf.plot(
        frame,
        type="candle",
        style=_STYLE,
        returnfig=True,
        volume=False,
        datetime_format=" ",
        xrotation=0,
        tight_layout=True,
    )
    ax = axlist[0]
    _style_axes(ax, _range_ylim(view.bars), total_bars)
    _draw_round_counter(ax, round_num, total_rounds)

    _reserve_button_space(fig, ax)
    _install_buttons(fig)

    return fig, ax


def _draw_result_mark(ax, correct: bool) -> None:
    """Green tick or red cross. Nothing else."""
    color = "#2e7d32" if correct else "#c62828"
    x, y = 0.05, 0.90  # axes-fraction coordinates, top-left corner
    kwargs = dict(transform=ax.transAxes, color=color, linewidth=4, solid_capstyle="round")
    if correct:
        ax.plot([x, x + 0.02, x + 0.06], [y - 0.03, y - 0.07, y + 0.05], **kwargs)
    else:
        ax.plot([x, x + 0.06], [y - 0.06, y + 0.06], **kwargs)
        ax.plot([x, x + 0.06], [y + 0.06, y - 0.06], **kwargs)


def reveal(fig, ax, view: PuzzleView, answer: PuzzleAnswer, correct: bool) -> None:
    """Draw the horizon into the reserved space, expand y-limits if needed,
    and mark the result. The reveal is permitted to see the future."""
    total_bars = config.LOOKBACK_BARS + view.horizon_width
    frame = _horizon_frame(answer.horizon_bars, total_bars)
    mpf.plot(frame, type="candle", style=_STYLE, ax=ax, volume=False, datetime_format=" ", xrotation=0)

    ylim = _expand_ylim(_range_ylim(view.bars), view.bars, answer.horizon_bars)
    _style_axes(ax, ylim, total_bars)
    # marks the lookback/horizon boundary -- only ever drawn here, on reveal
    ax.axvline(config.LOOKBACK_BARS - 0.5, linestyle=":", color="#999999", linewidth=1)
    # anchor close (always 0.0, by normalisation) and the final horizon
    # close, so the size of the move is visible at a glance -- also reveal-only
    ax.axhline(0.0, linestyle=":", color="#999999", linewidth=1)
    ax.axhline(answer.horizon_bars["close"].iloc[-1], linestyle=":", color="#999999", linewidth=1)
    _draw_result_mark(ax, correct)

    if config.REVEAL_IDENTITY:
        print(f"{answer.ticker}  {answer.session_date}")

    fig.canvas.draw_idle()


# --- Input ---------------------------------------------------------------


def _wait_for_key(fig, valid_keys: tuple[str, ...]) -> str:
    """Block until one of `valid_keys` is pressed or clicked. All other
    input is ignored and waiting resumes.

    Button clicks (see _install_buttons) always stop the event loop -- they
    aren't phase-aware, unlike the keyboard handler below, which only stops
    it for a valid_keys match. So a click on a button whose key isn't valid
    right now (e.g. Next during guessing) would otherwise end the wait
    early with an invalid result; looping here re-blocks instead, exactly
    as if that click, like a stray keypress, had been ignored.
    """

    def on_key(event):
        if event.key in valid_keys:
            fig._clicked_key = event.key
            fig.canvas.stop_event_loop()

    cid = fig.canvas.mpl_connect("key_press_event", on_key)
    while True:
        fig._clicked_key = None
        fig.canvas.start_event_loop(timeout=-1)
        if fig._clicked_key in valid_keys:
            break
    fig.canvas.mpl_disconnect(cid)
    return fig._clicked_key


def _wait_for_any_key(fig) -> None:
    """Block until any key is pressed or a button is clicked."""
    fig._clicked_key = None

    def on_key(event):
        fig._clicked_key = event.key
        fig.canvas.stop_event_loop()

    cid = fig.canvas.mpl_connect("key_press_event", on_key)
    fig.canvas.start_event_loop(timeout=-1)
    fig.canvas.mpl_disconnect(cid)


_KEY_TO_GUESS = {"up": 1, "down": -1}


# --- Session loop ----------------------------------------------------------


@dataclass(frozen=True)
class RoundResult:
    """One answered round, matching the data/rounds.csv schema exactly.
    Step 7 summarises these. Abandoned (quit) rounds don't produce one."""

    round_id: str
    session_id: str
    played_at: datetime
    corpus_version: str
    puzzle_id: str
    ticker: str
    session_date: date
    anchor_idx: int
    lookback_bars: int
    horizon_bars: int
    guess: int
    label: int
    correct: bool
    raw_return: float
    sigma_lookback: float
    trend_r2: float
    minutes_from_open: int
    shown_at: datetime
    answered_at: datetime
    ms_to_answer: int


# --- Logging ---------------------------------------------------------------

_LOG_FIELDS = [f.name for f in fields(RoundResult)]


def _round_to_row(result: RoundResult) -> dict:
    row = asdict(result)
    row["played_at"] = result.played_at.isoformat()
    row["shown_at"] = result.shown_at.isoformat()
    row["answered_at"] = result.answered_at.isoformat()
    row["session_date"] = result.session_date.isoformat()
    return row


def log_round(result: RoundResult, path: Path = config.ROUNDS_CSV) -> None:
    """Append one row for an answered round.

    Written immediately -- not buffered -- at the moment the answer is
    committed, before the reveal is drawn. Creates the file with a header if
    absent. Never rewrites or rotates it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(_round_to_row(result))
        f.flush()
        os.fsync(f.fileno())


def play_round(
    corpus: Corpus,
    rng: random.Random,
    session_id: str,
    round_num: int = 1,
    total_rounds: int = 1,
    horizon_bars: int = config.HORIZON_BARS,
    key_getter=_wait_for_key,
    advance_getter=_wait_for_any_key,
    on_round=lambda result: None,
) -> RoundResult | None:
    """Play one round: render, wait for a guess, reveal. Returns None if the
    player quit instead of answering.

    `round_num`/`total_rounds` are only used for the on-chart "n/total"
    progress indicator -- purely a position in the session, not a score.

    `key_getter`/`advance_getter` default to the real blocking waiters on a
    matplotlib figure; tests inject fakes so the loop logic can be exercised
    without a live GUI event loop.
    """
    view, answer = generate_puzzle(corpus, rng, horizon_bars=horizon_bars)

    fig, ax = render(view, round_num, total_rounds)
    fig.show()
    shown_at = datetime.now(timezone.utc)

    key = key_getter(fig, ("up", "down", "q"))
    answered_at = datetime.now(timezone.utc)

    if key not in _KEY_TO_GUESS:
        plt.close(fig)
        return None

    guess = _KEY_TO_GUESS[key]
    correct = guess == answer.label
    ms_to_answer = int((answered_at - shown_at).total_seconds() * 1000)

    result = RoundResult(
        round_id=str(uuid.uuid4()),
        session_id=session_id,
        played_at=answered_at,
        corpus_version=corpus.corpus_version,
        puzzle_id=answer.puzzle_id,
        ticker=answer.ticker,
        session_date=answer.session_date,
        anchor_idx=answer.anchor_idx,
        lookback_bars=len(view.bars),
        horizon_bars=len(answer.horizon_bars),
        guess=guess,
        label=answer.label,
        correct=correct,
        raw_return=answer.raw_return,
        sigma_lookback=answer.sigma_lookback,
        trend_r2=answer.trend_r2,
        minutes_from_open=answer.minutes_from_open,
        shown_at=shown_at,
        answered_at=answered_at,
        ms_to_answer=ms_to_answer,
    )
    on_round(result)  # logged here, before the reveal is drawn (non-negotiable #2)

    reveal(fig, ax, view, answer, correct)
    advance_getter(fig)
    plt.close(fig)

    return result


def run_session(
    corpus: Corpus,
    rounds: int = config.SESSION_ROUNDS,
    seed: int | None = None,
    session_id: str | None = None,
    horizon_bars: int = config.HORIZON_BARS,
    on_round=lambda result: None,
    key_getter=_wait_for_key,
    advance_getter=_wait_for_any_key,
) -> list[RoundResult]:
    """Play a fixed-length session. Stops early if the player quits.

    `horizon_bars` (one of config.HORIZON_OPTIONS) applies to every round in
    the session -- it's a session setting, not a per-round one.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    session_id = session_id or str(uuid.uuid4())

    results = []
    for round_num in range(1, rounds + 1):
        result = play_round(
            corpus, rng, session_id, round_num=round_num, total_rounds=rounds, horizon_bars=horizon_bars,
            key_getter=key_getter, advance_getter=advance_getter, on_round=on_round,
        )
        if result is None:
            break
        results.append(result)

    return results


if __name__ == "__main__":
    import argparse

    from intuition_trading import stats
    from intuition_trading.puzzles import load_corpus

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=config.SESSION_ROUNDS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--horizon", type=int, choices=config.HORIZON_OPTIONS, default=config.HORIZON_BARS,
        help="prediction horizon in minutes",
    )
    args = parser.parse_args()

    corpus = load_corpus()
    session_id = str(uuid.uuid4())
    run_session(
        corpus, rounds=args.rounds, seed=args.seed, session_id=session_id,
        horizon_bars=args.horizon, on_round=log_round,
    )

    print()
    stats.print_summary(session_id)
