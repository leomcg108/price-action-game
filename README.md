# price-action-game

**Can you read a chart? This finds out, and it doesn't let you fool yourself.**

A local, single-player game that shows you an hour of anonymised intraday price
action and asks one question: over the next ten minutes, up or down?

Play twenty rounds and it tells you your hit rate and, in the same breath, how
often a coin flip does that well. That second number is the entire point of the
project.

```
Session:   12/20  (60.0%)
           A coin flip scores this well or better 25.2% of the time.

Lifetime:  96/180 (53.3%)
           95% CI [46.0, 60.5] — includes 50%.
```

---

## Why this exists

If you've spent years looking at charts, you probably believe you've absorbed
something from them. That belief is very hard to test in the wild, because real
trading mixes direction-calling with position sizing, stop placement, instrument
selection, and luck. A profitable month tells you nothing about which of
those was responsible.

This isolates one component: **can you predict short-term direction from price
action alone?**

It was built as a personal sanity check, and it is built to fail honestly. A
version of this that made you feel good about a lucky run would be worse than
useless, it would send you to a broker with unearned confidence. So every
design decision that could have gone toward "engaging" went toward "trustworthy"
instead.

There is no score that goes up. There are no streaks. There is no confetti.

---

## Quick start

```bash
git clone https://github.com/leomcg108/price-action-game.git
cd price-action-game
pip install -e .

# Build the corpus. Takes a few minutes — Yahoo rate-limits.
python -m intuition_trading.fetch

# Play
python -m intuition_trading.game
```

Arrow keys: **↑** predicts up, **↓** predicts down. **q** quits and prints your
results so far.

Python 3.11+. Dependencies are `yfinance`, `pandas`, `pyarrow`, `numpy`,
`matplotlib`, and `mplfinance` — nothing else.

---

## The data problem, and why you should run `fetch.py` today

Yahoo Finance serves 1-minute bars for roughly **the last 30 days only**, in
7-day chunks. That window rolls forward every day, and whatever you don't
collect is gone for good.

`fetch.py` is written to **append**, not overwrite. Run it on a schedule and the
30-day window becomes a permanent, growing archive:

```cron
0 6 * * 1  cd /path/to/price-action-game && python -m intuition_trading.fetch >> fetch.log 2>&1
```

Set that up before you write a line of anything else. A month from now you'll
have a month of minute bars. A year from now you'll have a year of data that
otherwise costs real money.

Your first session will draw from ~21 trading days across 22 tickers, which is
around 2,000 distinct non-overlapping windows. You will not run out.

### On Yahoo

`yfinance` is an unofficial client that scrapes Yahoo's endpoints. It breaks
occasionally and rate-limits under load, which is why the game never calls it at
runtime — `fetch.py` and `game.py` are entirely separate, and the game reads
only from local parquet. If you're planning anything beyond personal use, check
Yahoo's terms of service first.

---

## Universe

Twenty large caps plus two index ETFs, chosen for liquidity and clean minute
data:

```
AAPL  MSFT  NVDA  AMZN  GOOGL  META  TSLA  AVGO  JPM  V
UNH   XOM   JNJ   WMT   PG     HD    MA    COST  CVX  LLY
SPY   QQQ
```

Edit `UNIVERSE` in `config.py` to change it. Thinner names will have gappier
minute bars; the cleaning rules will drop more of their days.

---

## How it's kept honest

This is the part that matters, and it's why the game is more than a chart with
two buttons.

**The future never reaches the renderer.** Puzzle generation returns two
separate objects: a `PuzzleView` containing only the lookback bars, and a
`PuzzleAnswer` held by the game loop. The plotting function's signature accepts
`PuzzleView` only, so leakage is structurally impossible rather than a matter of
care. There's a test that asserts it.

**The y-axis is computed from visible bars only.** This is the classic way a
game like this gives itself away: if you let the plotting library autoscale over
an array that includes the hidden future, the axis limits encode the answer. The
padding is fixed and derived from the lookback range alone.

**Chart geometry doesn't change on reveal.** The x-axis spans lookback plus
horizon from the first frame, leaving the horizon's width as empty space. Nothing
about the layout shifts when the answer appears.

**Prices are normalised to percent from the anchor.** The anchor sits at exactly
0.0 and the axis reads in percent, so the absolute price level, a strong tell
about which stock you're looking at, is gone.

**No ticker, no date, no clock time.** The x-axis is labelled by bar index. By
default the identity is never shown, not even after the reveal. It's recorded in
the log for later analysis, but showing it during play invites retrospective
rationalisation ("of course, that was a Fed day"), which is exactly the reasoning
this is built to detect.

**Windows never span sessions.** Both the lookback and horizon fall inside a
single trading day. Cross a boundary and the overnight gap appears as a visible
discontinuity, a blatant tell, and the label ends up measuring overnight drift
instead of intraday movement.

**Candlesticks, not a line.** A line chart discards the high–low range and tests
a subtly different skill. If your experience is with candles, a line chart would
partly measure unfamiliarity rather than absence of edge.

---

## Reading your results

At the end of a session you get something like:

```
Session:   12/20  (60.0%)
           A coin flip scores this well or better 25.2% of the time.

Lifetime:  96/180 (53.3%)
           95% CI [46.0, 60.5] — includes 50%.
```

### The coin line

Twenty rounds is a small number and small numbers are wild. Here is exactly how
often chance alone produces each result over a 20-round session:

| Result | Hit rate | Probability from a coin |
|--------|----------|-------------------------|
| 12/20  | 60%      | 25.2% |
| 13/20  | 65%      | 13.2% |
| 14/20  | 70%      | 5.8%  |
| 15/20  | 75%      | 2.1%  |
| 16/20  | 80%      | 0.6%  |

Roughly one session in four ends at 60% or better with no skill whatsoever. Any
version of this game that printed "60%!" and stopped would be manufacturing
exactly the overconfidence it should be puncturing.

### The lifetime line

Your session result is entertainment. Your lifetime result is the measurement.

The standard error on a hit rate is about `0.5/√n`, which means detecting a real
edge takes far more rounds than feels reasonable:

| True edge | Rounds needed to distinguish it from a coin (2σ) |
|-----------|--------------------------------------------------|
| 52%       | ~2,500 |
| 53%       | ~1,100 |
| 55%       | ~400   |
| 60%       | ~100   |

Which is why the lifetime line reports a Wilson interval and states in words
whether it contains 50%. While it does, the honest reading is that no edge has
been demonstrated — not that you have none, but that this hasn't shown one.

### Why 53% isn't a business

Even a genuine edge has to clear costs. Breakeven hit rate is roughly:

```
p* = 0.5 + c / 2w
```

where `c` is round-trip cost and `w` the typical move size. Over ten minutes on
a liquid large cap, `w` is around 20bps. At 2bps round-trip you need about 55%;
at 4bps, about 60%.

And note what that implies about the horizon specifically: `w` grows with `√t`
while `c` stays fixed. Stretch the holding period to a full session and breakeven
drops to roughly 51%. Ten minutes isn't just noisy — it's the regime where costs
eat the largest share of the available move.

*(v1 doesn't compute P&L. It's in the roadmap. The formula is here because the
hit rate on its own makes the bar look lower than it is.)*

---

## What this does **not** test

Being clear about this is what makes a poor result meaningful rather than a
rigged morality play.

The game strips out almost everything a discretionary trader actually uses:

- **Volume** — no volume panel, no relative-volume context
- **Order book** — no level 2, no tape
- **Market context** — no index chart, no sector, no correlated names
- **Calendar and news** — no earnings, no Fed days, no headlines
- **Prior sessions** — you see one hour, not yesterday's range or the weekly trend
- **Instrument choice** — you don't pick what to trade, and you can't sit out

So a 50% result does not prove "you have no edge". It proves **no edge from bare
anonymised price action on a randomly sampled window** — a narrower claim, and a
defensible one.

Most importantly: **this measures prediction, not trading.** A trader hitting 45%
with a 3:1 payoff ratio is profitable. Position sizing, stop placement, and exit
discipline are where a great deal of real edge lives, and this game is entirely
silent on all of them.

The last of those omissions — no ability to sit out — is the one most worth
fixing, and a pass option is the headline feature of v2.

---

## Configuration

All in `config.py`:

| Setting | Default | Notes |
|---------|---------|-------|
| `LOOKBACK_BARS` | `60` | Visible history, one hour |
| `HORIZON_BARS` | `10` | Prediction horizon |
| `SESSION_ROUNDS` | `20` | Overridable per session via CLI |
| `MIN_BARS_PER_DAY` | `385` | Of 390; drops gappy days and half-days |
| `REVEAL_IDENTITY` | `False` | Show ticker and date after the reveal |
| `UNIVERSE` | 22 symbols | See above |

### `REVEAL_IDENTITY`

Off by default, and the default is a considered one. Turn it on for debugging or
deliberate review; leaving it on during normal play reintroduces exactly the
retrospective labelling the anonymisation exists to prevent. It's a config
constant rather than a CLI flag on purpose — flipping it should take a small
amount of effort.

---

## Your data

Everything stays on your machine. There is no server, no telemetry, no network
call at game time.

```
data/
├── bars/           # one parquet per ticker
├── manifest.json   # corpus version and coverage
└── rounds.csv      # your round-by-round history
```

`rounds.csv` is appended to after every answered round — written the moment you
answer, before the reveal is drawn, so sessions you quit halfway through are
still counted. That's deliberate: abandoning the sessions that are going badly
is a much more likely source of self-flattery than outright cheating.

### Log schema

```
round_id, session_id, played_at, corpus_version, puzzle_id,
ticker, session_date, anchor_idx, lookback_bars, horizon_bars,
guess, label, correct,
raw_return, sigma_lookback, trend_r2, minutes_from_open,
shown_at, answered_at, ms_to_answer
```

Three of these are computed at generation time and never shown to you, so you
can slice your history afterwards:

- `sigma_lookback` — realised volatility of the visible window
- `trend_r2` — how cleanly the visible window trends
- `raw_return` — the actual size of the move, not just its sign

That last one is the useful one. Because magnitude is logged even though the game
doesn't act on it, you can retroactively apply a dead-zone filter — "how do I do
if we ignore rounds where the move was under 0.1%?" — across sessions you played
months ago.

`ms_to_answer` is there for the same reason: no UI, no timer, just two timestamps
and a subtraction, so that later analysis has a history to work with.

### `.gitignore`

`data/` is excluded. The bars are large and regenerable; `rounds.csv` is yours.

---

## Project layout

```
price-action-game/
├── src/intuition_trading/
│   ├── config.py     # all tunable parameters, no logic
│   ├── fetch.py      # corpus builder — run on a schedule
│   ├── puzzles.py    # corpus loading, features, puzzle generation
│   ├── game.py       # session loop, chart, input, logging
│   └── stats.py      # binomial tail, Wilson interval, summary
├── tests/
│   ├── test_no_leakage.py
│   ├── test_game_loop.py
│   ├── test_logging.py
│   └── test_stats.py
└── data/             # local only, not tracked in git
```

`test_no_leakage.py` is the one test that matters. It generates several hundred
puzzles and asserts that no view contains a bar at or after its anchor. If you
fork this and change the generation logic, keep that test passing — without it,
every number the game produces is worthless.

---

## Roadmap

**v2 — web version.** Playable in a browser and shareable. Adds a pass option
(so you're not forced to trade the chop), confidence elicitation with Brier
scoring and a calibration curve, P&L net of costs, comparison against momentum
and mean-reversion baselines, and accumulation across sessions. No accounts, no
server-side storage of anything you do.

**v3 — human versus machine.** Score models on the identical puzzle set: a
logistic regression on window features, a CNN on the rendered charts, an LLM shown
the same images. Puzzle IDs are deterministic hashes of
`(corpus_version, ticker, session_date, anchor_idx)` precisely so that comparison
is exact rather than approximate.

The most interesting result available here is probably a placebo arm: mix
synthetic charts, geometric Brownian motion calibrated to the same realised
volatility, in among the real ones without telling the player. If you score the
same on both, your hit rate is noise, and you know it by experiment rather than
by inference.

---

## Contributing

Issues and PRs welcome. One request: the honesty constraints listed under **How
it's kept honest** are the project, not decoration. A PR that makes the game more
engaging at their expense will be declined, however good the code is.

Particularly: no streak counters, no score animations, no win rate displayed
without its reference line.

---

## Disclaimer

This is not financial advice, an endorsement of day trading, or a tool for
developing a trading strategy. It's a measurement instrument for a single narrow
question, and it was built partly because the honest answer to that question is
usually unwelcome.

If you use it and discover you have no measurable edge, that is the most
valuable result it can give you, and it cost you nothing to find out.

---

## Licence

MIT. See [LICENSE](LICENSE).
