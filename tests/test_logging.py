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

_ORIGINAL_FIELDS = [
    "round_id", "session_id", "played_at", "corpus_version", "puzzle_id",
    "ticker", "session_date", "anchor_idx", "lookback_bars", "horizon_bars",
    "guess", "label", "correct", "raw_return", "sigma_lookback", "trend_r2",
    "minutes_from_open", "shown_at", "answered_at", "ms_to_answer",
]
# added later, always last, so older logs stay readable
_EXPECTED_FIELDS = _ORIGINAL_FIELDS + ["time_limit_s", "timed_out"]


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


def test_new_columns_come_last_and_match_what_stats_reads():
    """stats maps the added columns back by position on old-header logs,
    so their order in the row and in stats.ADDED_FIELDS must agree."""
    from intuition_trading import stats

    assert game._LOG_FIELDS[: len(_ORIGINAL_FIELDS)] == _ORIGINAL_FIELDS
    assert game._LOG_FIELDS[len(_ORIGINAL_FIELDS):] == list(stats.ADDED_FIELDS)


def test_appending_to_a_log_with_the_original_header(corpus, tmp_path):
    """A log started before the timer columns existed is appended to as is:
    its header is never rewritten, old rows read back without the new
    columns, and new rows read back with them."""
    from intuition_trading import stats

    path = tmp_path / "rounds.csv"
    old = _play_one(corpus, seed=1)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_ORIGINAL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(game._round_to_row(old))
    original_header = path.read_text(encoding="utf-8").splitlines()[0]

    new = game.play_round(
        corpus, random.Random(2), "session-1", key_getter=lambda fig, valid_keys: "timeout",
        advance_getter=lambda fig: None, time_limit=10, coin_flip=lambda: 1,
    )
    game.log_round(new, path=path)

    assert path.read_text(encoding="utf-8").splitlines()[0] == original_header
    old_row, new_row = stats._read_rounds(path)
    assert old_row["round_id"] == old.round_id
    assert "timed_out" not in old_row
    assert new_row["round_id"] == new.round_id
    assert new_row["time_limit_s"] == "10"
    assert new_row["timed_out"] == "True"


def test_a_timed_out_round_is_logged_with_its_random_guess(corpus, tmp_path):
    path = tmp_path / "rounds.csv"
    result = game.play_round(
        corpus, random.Random(SEED), "session-1",
        key_getter=lambda fig, valid_keys: "timeout", advance_getter=lambda fig: None,
        on_round=lambda r: game.log_round(r, path=path), time_limit=5, coin_flip=lambda: -1,
    )

    with open(path, newline="", encoding="utf-8") as f:
        [row] = list(csv.DictReader(f))
    assert row["guess"] == "-1"
    assert row["correct"] == str(result.label == -1)
    assert row["time_limit_s"] == "5"
    assert row["timed_out"] == "True"
