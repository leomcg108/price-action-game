"""CSV round logging: schema, append semantics, and immediacy.

Every test writes to a tmp_path CSV, never to the real data/rounds.csv.
"""

import csv
import random

import matplotlib

matplotlib.use("Agg")

import pytest

from intuition_trading import game
from intuition_trading.puzzles import Corpus, load_corpus

SEED = 20260824

_EXPECTED_FIELDS = [
    "round_id", "session_id", "played_at", "corpus_version", "puzzle_id",
    "ticker", "session_date", "anchor_idx", "lookback_bars", "horizon_bars",
    "guess", "label", "correct", "raw_return", "sigma_lookback", "trend_r2",
    "minutes_from_open", "shown_at", "answered_at", "ms_to_answer",
]


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    corpus = load_corpus()
    if not corpus.valid_sessions:
        pytest.skip("no data in data/bars/ -- run fetch.py first")
    return corpus


def _fixed_key(key: str):
    def getter(fig, valid_keys):
        return key

    return getter


def _play_one(corpus: Corpus, seed: int = SEED):
    rng = random.Random(seed)
    return game.play_round(
        corpus, rng, "session-1", key_getter=_fixed_key("up"), advance_getter=lambda fig: None
    )


def test_log_round_schema_matches_spec(corpus, tmp_path):
    result = _play_one(corpus)
    path = tmp_path / "rounds.csv"

    game.log_round(result, path=path)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == _EXPECTED_FIELDS
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["round_id"] == result.round_id
    assert row["guess"] == str(result.guess)
    assert row["correct"] == str(result.correct)
    # timestamps are ISO 8601 and tz-aware
    assert "T" in row["played_at"]
    assert row["played_at"].endswith("+00:00")


def test_log_round_creates_header_only_once(corpus, tmp_path):
    path = tmp_path / "rounds.csv"

    game.log_round(_play_one(corpus, seed=1), path=path)
    game.log_round(_play_one(corpus, seed=2), path=path)
    game.log_round(_play_one(corpus, seed=3), path=path)

    with open(path, newline="", encoding="utf-8") as f:
        lines = f.readlines()

    header_lines = [line for line in lines if line.startswith("round_id,")]
    assert len(header_lines) == 1
    assert len(lines) == 4  # 1 header + 3 rows


def test_log_round_appends_never_overwrites_existing_rows(corpus, tmp_path):
    path = tmp_path / "rounds.csv"

    first = _play_one(corpus, seed=1)
    game.log_round(first, path=path)

    second = _play_one(corpus, seed=2)
    game.log_round(second, path=path)

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert [r["round_id"] for r in rows] == [first.round_id, second.round_id]


def test_quit_round_is_not_logged(corpus, tmp_path):
    path = tmp_path / "rounds.csv"
    logged = []

    results = game.run_session(
        corpus, rounds=10, seed=SEED, on_round=lambda r: (logged.append(r), game.log_round(r, path=path)),
        key_getter=lambda fig, valid_keys: "q", advance_getter=lambda fig: None,
    )

    assert results == []
    assert logged == []
    assert not path.exists()


def test_session_survives_a_mid_session_quit_with_prior_rounds_logged(corpus, tmp_path):
    """Non-negotiable #2: abandoned sessions must still appear in the log --
    for every round that WAS answered before the quit."""
    path = tmp_path / "rounds.csv"
    calls = {"n": 0}

    def quits_on_third(fig, valid_keys):
        calls["n"] += 1
        return "q" if calls["n"] == 3 else "up"

    results = game.run_session(
        corpus, rounds=10, seed=SEED,
        on_round=lambda r: game.log_round(r, path=path),
        key_getter=quits_on_third, advance_getter=lambda fig: None,
    )

    assert len(results) == 2
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert [r["round_id"] for r in rows] == [r.round_id for r in results]
