"""Start screen: pick the session's settings with buttons instead of CLI
arguments, then press Start.

Drawn into the same figure the session then plays in, so the start screen
and the game share one window. Only session settings live here -- never
REVEAL_IDENTITY, which stays a config constant on purpose (see spec).
"""

from __future__ import annotations

from matplotlib.widgets import Button

from intuition_trading import config
from intuition_trading.game import clear_figure

# "ANSI Shadow" block letters, six rows each, every row of a glyph the same width
_GLYPHS = {
    "I": [
        "██╗",
        "██║",
        "██║",
        "██║",
        "██║",
        "╚═╝",
    ],
    "N": [
        "███╗   ██╗",
        "████╗  ██║",
        "██╔██╗ ██║",
        "██║╚██╗██║",
        "██║ ╚████║",
        "╚═╝  ╚═══╝",
    ],
    "T": [
        "████████╗",
        "╚══██╔══╝",
        "   ██║   ",
        "   ██║   ",
        "   ██║   ",
        "   ╚═╝   ",
    ],
    "U": [
        "██╗   ██╗",
        "██║   ██║",
        "██║   ██║",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ],
    "O": [
        " ██████╗ ",
        "██╔═══██╗",
        "██║   ██║",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ],
    "R": [
        "██████╗ ",
        "██╔══██╗",
        "██████╔╝",
        "██╔══██╗",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ],
    "A": [
        " █████╗ ",
        "██╔══██╗",
        "███████║",
        "██╔══██║",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ],
    "D": [
        "██████╗ ",
        "██╔══██╗",
        "██║  ██║",
        "██║  ██║",
        "██████╔╝",
        "╚═════╝ ",
    ],
    "G": [
        " ██████╗ ",
        "██╔════╝ ",
        "██║  ███╗",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ],
}


def banner(word: str) -> str:
    """`word` in block letters, one glyph column apart."""
    glyphs = [_GLYPHS[c] for c in word]
    return "\n".join(" ".join(g[row] for g in glyphs) for row in range(6))


_SELECTED = "#455a64"
_UNSELECTED = "#eeeeee"
_UNSELECTED_HOVER = "#e0e0e0"


def _paint(button: Button, selected: bool) -> None:
    color = _SELECTED if selected else _UNSELECTED
    button.color = color  # Button restores this colour when the mouse leaves
    button.hovercolor = color if selected else _UNSELECTED_HOVER
    button.ax.set_facecolor(color)
    button.label.set_color("white" if selected else "#333333")


class Launcher:
    """The start screen's state and widgets. `wait()` blocks until the
    player starts a session or backs out."""

    def __init__(self, fig, rounds: int = config.LAUNCHER_ROUNDS, horizon: int = config.LAUNCHER_HORIZON):
        self.fig = fig
        # held on to: closing the window replaces fig.canvas, and the loop
        # must be stopped on the canvas it's actually blocking on
        self.canvas = fig.canvas
        self.rounds = rounds
        self.horizon = horizon
        self.started = False
        self.closed = False

        clear_figure(fig)
        self._draw_banner()
        self.round_buttons = self._option_row(0.44, "Rounds", config.ROUND_OPTIONS, str, "rounds")
        self.horizon_buttons = self._option_row(
            0.31, "Horizon", config.HORIZON_OPTIONS, lambda v: f"{v} min", "horizon"
        )
        self.start_button = self._start_button()
        # so the session's first clear_figure disconnects them
        fig._widgets = [*self.round_buttons.values(), *self.horizon_buttons.values(), self.start_button]
        self._refresh()

    def _draw_banner(self) -> None:
        text = dict(ha="center", va="top", family="monospace", fontsize=9, linespacing=1.0, color="#263238")
        self.fig.text(0.5, 0.95, banner("INTUITION"), **text)
        self.fig.text(0.5, 0.77, banner("TRADING"), **text)

    def _option_row(self, y: float, name: str, options, fmt, attr: str) -> dict[int, Button]:
        width, height, gap = 0.12, 0.08, 0.02
        left0 = 0.30
        self.fig.text(left0 - 0.03, y + height / 2, name, ha="right", va="center", fontsize=12, color="#333333")

        buttons = {}
        for i, value in enumerate(options):
            bax = self.fig.add_axes([left0 + i * (width + gap), y, width, height])
            button = Button(bax, fmt(value))
            button.label.set_fontsize(12)
            bax.patch.set_edgecolor("#bbbbbb")

            def select(_event, value=value):
                setattr(self, attr, value)
                self._refresh()

            button.on_clicked(select)
            buttons[value] = button
        return buttons

    def _start_button(self) -> Button:
        bax = self.fig.add_axes([0.30, 0.06, 0.40, 0.16])
        button = Button(bax, "START", color="#2e7d32", hovercolor="#388e3c")
        button.label.set_fontsize(24)
        button.label.set_fontweight("bold")
        button.label.set_color("white")
        button.on_clicked(lambda _event: self.start())
        return button

    def _refresh(self) -> None:
        for value, button in self.round_buttons.items():
            _paint(button, value == self.rounds)
        for value, button in self.horizon_buttons.items():
            _paint(button, value == self.horizon)
        self.fig.canvas.draw_idle()

    def start(self) -> None:
        self.started = True
        self.canvas.stop_event_loop()

    def wait(self) -> tuple[int, int] | None:
        """Block until Start (button or Enter) -> (rounds, horizon), or
        until the window is closed or q is pressed -> None."""

        def on_key(event):
            if event.key == "enter":
                self.start()
            elif event.key == "q":
                self.closed = True
                self.canvas.stop_event_loop()

        def on_close(_event):
            self.closed = True
            self.canvas.stop_event_loop()

        canvas = self.canvas
        cids = [canvas.mpl_connect("key_press_event", on_key), canvas.mpl_connect("close_event", on_close)]
        while not (self.started or self.closed):
            canvas.start_event_loop(timeout=-1)
        for cid in cids:
            canvas.mpl_disconnect(cid)

        return (self.rounds, self.horizon) if self.started else None


def choose_settings(fig) -> tuple[int, int] | None:
    """Show the start screen in `fig`; returns (rounds, horizon) once the
    player presses Start, or None if they leave without starting."""
    return Launcher(fig).wait()
