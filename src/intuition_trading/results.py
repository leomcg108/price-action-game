"""Results screen: the end-of-session summary in the game window, framed,
with an End button that closes the window.

Shows exactly stats.summary()'s text -- both result lines with their chance
references (non-negotiable #3), nothing added, nothing softened.
"""

from __future__ import annotations

from matplotlib.widgets import Button

from intuition_trading.game import clear_figure


def draw_results(fig, summary: str) -> Button:
    """Replace whatever `fig` shows with the summary and an End button;
    returns the button."""
    clear_figure(fig)
    fig.text(
        0.5, 0.60, summary,
        ha="center", va="center", multialignment="left",  # keep the text's own column alignment
        # as large as the longest line (~70 chars) allows while the frame
        # keeps a margin inside the window
        family="monospace", fontsize=12, linespacing=1.6, color="black",
        bbox=dict(boxstyle="square,pad=1.0", facecolor="white", edgecolor="black", linewidth=2),
    )

    bax = fig.add_axes([0.38, 0.08, 0.24, 0.13])
    end = Button(bax, "END", color="#424242", hovercolor="#616161")
    end.label.set_fontsize(20)
    end.label.set_fontweight("bold")
    end.label.set_color("white")
    fig._widgets = [end]  # so clear_figure can disconnect it
    fig.canvas.draw_idle()
    return end


def wait_for_end(fig, end: Button) -> None:
    """Block until End is clicked, Enter or q is pressed, or the window is
    closed."""
    canvas = fig.canvas  # held on to: closing the window replaces fig.canvas
    done = False

    def finish(_event=None):
        nonlocal done
        done = True
        canvas.stop_event_loop()

    def on_key(event):
        if event.key in ("enter", "q"):
            finish()

    end.on_clicked(finish)
    cids = [canvas.mpl_connect("key_press_event", on_key), canvas.mpl_connect("close_event", finish)]
    while not done:
        canvas.start_event_loop(timeout=-1)
    for cid in cids:
        canvas.mpl_disconnect(cid)


def show_results(fig, summary: str) -> None:
    """Show the results screen in `fig` until the player ends it. The caller
    closes the window afterwards."""
    wait_for_end(fig, draw_results(fig, summary))
