from pathlib import Path

LOOKBACK_BARS = 60  # visible history, one hour
HORIZON_OPTIONS = (5, 10, 20, 30)  # minutes; selectable per session via --horizon
HORIZON_BARS = 10  # default prediction horizon when using the CLI flags; one of HORIZON_OPTIONS
SESSION_ROUNDS = 20  # overridable via CLI

# Seconds allowed per guess; 0 = no timer. When time runs out, the round is
# guessed at random, so every round stays a fair 50/50 for the statistics.
TIMER_OPTIONS = (0, 2, 5, 10)  # selectable per session via --timer
TIMER_SECONDS = 0  # default when using the CLI flags

# Start screen (shown when the game is launched without --rounds/--horizon/--timer)
ROUND_OPTIONS = (10, 20, 30, 50)  # session lengths offered as buttons
LAUNCHER_ROUNDS = 10  # preselected, so pressing Start straight away uses these
LAUNCHER_HORIZON = 30  # one of HORIZON_OPTIONS
LAUNCHER_TIMER = 0  # one of TIMER_OPTIONS

THEME = "light"  # "light" or "dark"; switchable on the start screen or via --theme

MIN_BARS_PER_DAY = 385  # of 390; drops gappy days and half-days

REVEAL_IDENTITY = False  # see spec: debugging only, do not add a mid-session flip

# Default/backup universe. Used as-is if the S&P 500 csv (below) is missing,
# and always unioned into it otherwise -- this is also what keeps SPY/QQQ in
# the universe, since index ETFs aren't S&P 500 constituents themselves.
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "TSLA", "AVGO", "JPM", "V",
    "UNH", "XOM", "JNJ", "WMT", "PG",
    "HD", "MA", "COST", "CVX", "LLY",
    "SPY", "QQQ",
]

MARKET_TZ = "America/New_York"

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BARS_DIR = DATA_DIR / "bars"
MANIFEST_PATH = DATA_DIR / "manifest.json"
ROUNDS_CSV = DATA_DIR / "rounds.csv"

# S&P 500 constituents (Wikipedia export format, "Symbol" column), used by
# fetch.py to expand UNIVERSE.
SP500_CSV = Path(__file__).resolve().parents[2] / "docs" / "sp500.csv"
