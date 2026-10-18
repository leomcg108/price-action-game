"""Start screen: pick the session's settings with buttons instead of CLI
arguments, then press Start.

Drawn into the same figure the session then plays in, so the start screen
and the game share one window. Only session settings live here -- never
REVEAL_IDENTITY, which stays a config constant on purpose (see spec).
"""

from __future__ import annotations

from matplotlib.widgets import Button

from intuition_trading import config
from intuition_trading.game import apply_theme, clear_figure, theme_of
from intuition_trading.theme import THEMES, Theme

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


def _paint(button: Button, selected: bool, theme: Theme) -> None:
    color = theme.selected if selected else theme.button
    button.color = color  # Button restores this colour when the mouse leaves
    button.hovercolor = color if selected else theme.button_hover
    button.ax.set_facecolor(color)
    button.ax.patch.set_edgecolor(theme.button_edge)
    button.label.set_color(theme.selected_text if selected else theme.label)
    _paint_border(button, theme)


def _paint_border(button: Button, theme: Theme) -> None:
    # spines take their colour from the theme active when the button was
    # made, so switching theme on screen has to redo them
    for spine in button.ax.spines.values():
        spine.set_edgecolor(theme.spine)


class Launcher:
    """The start screen's state and widgets. `wait()` blocks until the
    player starts a session or backs out."""

    def __init__(
        self, fig,
        rounds: int = config.LAUNCHER_ROUNDS,
        horizon: int = config.LAUNCHER_HORIZON,
        timer: int = config.LAUNCHER_TIMER,
    ):
        self.fig = fig
        # held on to: closing the window replaces fig.canvas, and the loop
        # must be stopped on the canvas it's actually blocking on
        self.canvas = fig.canvas
        self.rounds = rounds
        self.horizon = horizon
        self.timer = timer
        self.theme = theme_of(fig).name
        self.started = False
        self.closed = False

        clear_figure(fig)
        self._texts = self._draw_banner()
        self.round_buttons = self._option_row(0.53, "Rounds", config.ROUND_OPTIONS, str, "rounds")
        self.horizon_buttons = self._option_row(
            0.435, "Horizon", config.HORIZON_OPTIONS, lambda v: f"{v} min", "horizon"
        )
        self.timer_buttons = self._option_row(
            0.34, "Timer", config.TIMER_OPTIONS, lambda v: f"{v} s" if v else "Off", "timer"
        )
        self.theme_buttons = self._option_row(0.245, "Theme", tuple(THEMES), str.capitalize, "theme")
        self.start_button = self._start_button()
        # so the session's first clear_figure disconnects them
        fig._widgets = [
            *self.round_buttons.values(), *self.horizon_buttons.values(),
            *self.timer_buttons.values(), *self.theme_buttons.values(), self.start_button,
        ]
        self._refresh()

    def _draw_banner(self) -> list:
        text = dict(ha="center", va="top", family="monospace", fontsize=9, linespacing=1.0)
        return [
            self.fig.text(0.5, 0.95, banner("INTUITION"), **text),
            self.fig.text(0.5, 0.77, banner("TRADING"), **text),
        ]

    def _option_row(self, y: float, name: str, options, fmt, attr: str) -> dict:
        width, height, gap = 0.12, 0.07, 0.02
        left0 = 0.30
        self._texts.append(self.fig.text(left0 - 0.03, y + height / 2, name, ha="right", va="center", fontsize=12))

        buttons = {}
        for i, value in enumerate(options):
            bax = self.fig.add_axes([left0 + i * (width + gap), y, width, height])
            button = Button(bax, fmt(value))
            button.label.set_fontsize(12)

            def select(_event, value=value):
                setattr(self, attr, value)
                self._refresh()

            button.on_clicked(select)
            buttons[value] = button
        return buttons

    def _start_button(self) -> Button:
        bax = self.fig.add_axes([0.30, 0.04, 0.40, 0.14])
        button = Button(bax, "START", color="#2e7d32", hovercolor="#388e3c")
        button.label.set_fontsize(24)
        button.label.set_fontweight("bold")
        button.label.set_color("white")
        button.on_clicked(lambda _event: self.start())
        return button

    def _refresh(self) -> None:
        """Re-colour everything for the chosen options and theme -- choosing
        a theme switches the whole screen (and the session after it)."""
        apply_theme(self.fig, self.theme)
        theme = theme_of(self.fig)
        banner_texts, label_texts = self._texts[:2], self._texts[2:]
        for text in banner_texts:
            text.set_color(theme.banner)
        for text in label_texts:
            text.set_color(theme.label)
        for buttons, chosen in (
            (self.round_buttons, self.rounds), (self.horizon_buttons, self.horizon),
            (self.timer_buttons, self.timer), (self.theme_buttons, self.theme),
        ):
            for value, button in buttons.items():
                _paint(button, value == chosen, theme)
        _paint_border(self.start_button, theme)
        self.fig.canvas.draw_idle()

    def start(self) -> None:
        self.started = True
        self.canvas.stop_event_loop()

    def wait(self) -> tuple[int, int, int] | None:
        """Block until Start (button or Enter) -> (rounds, horizon, timer),
        or until the window is closed or q is pressed -> None."""

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

        return (self.rounds, self.horizon, self.timer) if self.started else None


def choose_settings(fig) -> tuple[int, int, int] | None:
    """Show the start screen in `fig`; returns (rounds, horizon, timer) once
    the player presses Start, or None if they leave without starting."""
    return Launcher(fig).wait()
