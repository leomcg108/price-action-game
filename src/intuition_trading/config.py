from pathlib import Path

LOOKBACK_BARS = 60  # visible history, one hour
HORIZON_BARS = 10  # prediction horizon
SESSION_ROUNDS = 20  # overridable via CLI

MIN_BARS_PER_DAY = 385  # of 390; drops gappy days and half-days

REVEAL_IDENTITY = False  # see spec: debugging only, do not add a mid-session flip

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
