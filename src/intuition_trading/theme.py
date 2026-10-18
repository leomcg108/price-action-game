"""Light and dark colour palettes for every screen.

A theme only ever changes colours -- never sizes, positions or limits -- so
chart geometry is identical in both, and nothing about the question can
differ by theme.

The active theme travels with the figure (see game.apply_theme), because
the start screen can switch it after the window already exists.
"""

from __future__ import annotations

from dataclasses import dataclass

import mplfinance as mpf


@dataclass(frozen=True)
class Theme:
    name: str
    mpf_style: dict  # candle colours, plus rcParams mplfinance applies per new axes

    figure: str  # window background
    chart: str  # chart area background
    spine: str  # chart border
    text: str  # axis labels and tick labels
    muted: str  # round counter, reveal reference lines
    note: str  # the reveal's "Time's up" note
    countdown: str  # the timer bar

    good: str  # up arrow, tick
    bad: str  # down arrow, cross
    button: str
    button_hover: str
    button_edge: str
    nav_arrow: str  # the Next button's arrow

    banner: str  # start screen
    label: str  # start screen row labels, unselected option text
    selected: str  # chosen start-screen option
    selected_text: str

    panel: str  # results box background
    panel_text: str
    frame: str  # results box border
    end_button: str
    end_hover: str


# Exactly the colours the game always had, so light mode looks unchanged.
LIGHT = Theme(
    name="light",
    mpf_style=mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=""),
    figure="white",
    chart="#fafafa",
    spine="#f0f0f0",
    text="#101010",
    muted="#999999",
    note="#757575",
    countdown="#9e9e9e",
    good="#2e7d32",
    bad="#c62828",
    button="#eeeeee",
    button_hover="#e0e0e0",
    button_edge="#bbbbbb",
    nav_arrow="#616161",
    banner="#263238",
    label="#333333",
    selected="#455a64",
    selected_text="white",
    panel="white",
    panel_text="black",
    frame="black",
    end_button="#424242",
    end_hover="#616161",
)

_DARK_FIGURE = "#121212"
_DARK_CHART = "#1e1e1e"
_DARK_SPINE = "#3a3a3a"
_DARK_TEXT = "#e0e0e0"

DARK = Theme(
    name="dark",
    mpf_style=mpf.make_mpf_style(
        base_mpf_style="yahoo",
        gridstyle="",
        facecolor=_DARK_CHART,
        figcolor=_DARK_FIGURE,
        # yahoo's dark-grey wicks vanish on a dark chart
        marketcolors=mpf.make_marketcolors(base_mpf_style="yahoo", wick="#a0a0a0"),
        rc={
            "axes.labelcolor": _DARK_TEXT,
            "xtick.color": _DARK_TEXT,
            "ytick.color": _DARK_TEXT,
            "axes.edgecolor": _DARK_SPINE,
            "text.color": _DARK_TEXT,
        },
    ),
    figure=_DARK_FIGURE,
    chart=_DARK_CHART,
    spine=_DARK_SPINE,
    text=_DARK_TEXT,
    muted="#8a8a8a",
    note="#a8a8a8",
    countdown="#8a8a8a",
    good="#43a047",  # lighter than light mode's, to stand out on dark
    bad="#e53935",
    button="#2b2b2b",
    button_hover="#363636",
    button_edge="#4a4a4a",
    nav_arrow="#bdbdbd",
    banner="#eceff1",
    label="#cfcfcf",
    selected="#607d8b",
    selected_text="white",
    panel=_DARK_CHART,
    panel_text=_DARK_TEXT,
    frame=_DARK_TEXT,  # a black frame would vanish on a dark background
    end_button="#5f5f5f",
    end_hover="#757575",
)

THEMES = {t.name: t for t in (LIGHT, DARK)}
