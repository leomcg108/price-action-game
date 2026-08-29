from pathlib import Path

LOOKBACK_BARS = 60  # visible history, one hour
HORIZON_OPTIONS = (10, 20, 30)  # minutes; selectable per session via --horizon
HORIZON_BARS = HORIZON_OPTIONS[0]  # default prediction horizon
SESSION_ROUNDS = 20  # overridable via CLI

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
