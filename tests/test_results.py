"""Results screen: shows stats' summary text verbatim in a framed box, and
blocks until End (button, Enter or q) or the window closes."""

import threading
import time

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.backend_bases import KeyEvent

from intuition_trading import game, results, stats

SUMMARY = stats.format_summary(7, 10, 138, 296)


def _fire(button):
    """Simulate a click without a real mouse event."""
    button._observers.process("clicked", None)


def _in_background(fig, action):
    """Run `action` once `fig`'s blocking event loop is actually running."""

    def run():
        deadline = time.monotonic() + 5
        while not getattr(fig.canvas, "_looping", False) and time.monotonic() < deadline:
            time.sleep(0.01)
        action()

    t = threading.Thread(target=run)
    t.start()
    return t


def test_shows_the_summary_verbatim_in_a_black_frame():
    """Non-negotiable #3: the screen must carry both chance references --
    guaranteed by showing stats' text unchanged."""
    fig = game.new_figure()
    results.draw_results(fig, SUMMARY)

    [text] = fig.texts
    assert text.get_text() == SUMMARY
    frame = text.get_bbox_patch()
    assert matplotlib.colors.same_color(frame.get_edgecolor(), "black")


def test_frame_fits_inside_the_window():
    fig = game.new_figure()
    results.draw_results(fig, SUMMARY)
    fig.canvas.draw()
    box = fig.texts[0].get_bbox_patch().get_window_extent(fig.canvas.get_renderer())
    assert fig.bbox.x0 < box.x0 and box.x1 < fig.bbox.x1
    assert fig.bbox.y0 < box.y0 and box.y1 < fig.bbox.y1


def test_replaces_the_previous_screen():
    """Drawn into the session's window: the last chart and its buttons go."""
    fig = game.new_figure()
    game.clear_figure(fig)
    fig.add_axes([0.1, 0.1, 0.8, 0.8])
    end = results.draw_results(fig, SUMMARY)
    assert fig.axes == [end.ax]


def test_end_button_finishes():
    fig = game.new_figure()
    end = results.draw_results(fig, SUMMARY)
    t = _in_background(fig, lambda: _fire(end))
    results.wait_for_end(fig, end)  # returns rather than hanging
    t.join(timeout=5)


def test_q_finishes_without_closing_the_window_first():
    """q is the game's key, not matplotlib's close-window shortcut: the
    window must still be open for the caller to close."""
    fig = game.new_figure()
    end = results.draw_results(fig, SUMMARY)
    press_q = KeyEvent("key_press_event", fig.canvas, "q")
    t = _in_background(fig, lambda: fig.canvas.callbacks.process("key_press_event", press_q))
    results.wait_for_end(fig, end)
    t.join(timeout=5)
    assert plt.fignum_exists(fig.number)
    plt.close(fig)
