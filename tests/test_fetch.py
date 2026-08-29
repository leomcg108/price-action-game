"""Ticker universe construction: config.UNIVERSE unioned with the S&P 500
constituents csv, with UNIVERSE as the default/backup set."""

import csv

import pytest

from intuition_trading import config, fetch


def test_load_sp500_tickers_from_real_csv():
    tickers = fetch._load_sp500_tickers()
    if not tickers:
        pytest.skip("docs/sp500.csv not present locally")

    assert len(tickers) > 400
    assert len(tickers) == len(set(tickers))  # no duplicates
    assert "AAPL" in tickers
    # Yahoo uses a dash where the index listing uses a dot
    assert "BRK.B" not in tickers
    assert "BRK-B" in tickers


def test_load_sp500_tickers_missing_file_returns_empty(tmp_path):
    tickers = fetch._load_sp500_tickers(path=tmp_path / "does-not-exist.csv")
    assert tickers == []


def test_load_sp500_tickers_converts_dots_to_dashes(tmp_path):
    path = tmp_path / "sp500.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol", "Security"])
        writer.writerow(["BRK.B", "Berkshire Hathaway"])
        writer.writerow(["AAPL", "Apple"])

    tickers = fetch._load_sp500_tickers(path=path)
    assert tickers == ["BRK-B", "AAPL"]


def test_build_universe_is_a_superset_of_the_backup_list():
    universe = fetch.build_universe()
    assert set(config.UNIVERSE) <= set(universe)


def test_build_universe_falls_back_to_backup_list_when_csv_missing(monkeypatch):
    monkeypatch.setattr(fetch, "_load_sp500_tickers", lambda: [])
    universe = fetch.build_universe()
    assert universe == sorted(set(config.UNIVERSE))


def test_build_universe_has_no_duplicates():
    universe = fetch.build_universe()
    assert len(universe) == len(set(universe))
