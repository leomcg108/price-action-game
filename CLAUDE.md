# Price-action game

Full spec: @docs/v1-spec.md — read it before implementing.

## Non-negotiables
- No lookahead leakage. `PuzzleView` must never carry horizon data,
  and y-limits are computed from the lookback only.
- Rounds are logged the moment they're answered, not at session end.
- Never print a win rate without its coin-flip reference line.
- v1 scope is fixed. Do not add pass, confidence, indicators, or P&L.
