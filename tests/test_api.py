"""Tests for the ausport api client.

Uses respx to mock httpx responses against the Squiggle API.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from ausport.api import Game, SquiggleClient, SquiggleError, Team, compute_ladder

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------- teams ----------

def test_teams_afl_parses_correctly():
    with respx.mock(base_url="https://api.squiggle.com.au") as mock:
        mock.get("/").mock(return_value=httpx.Response(200, json=_load("afl_teams.json")))
        with SquiggleClient() as client:
            teams = client.teams("afl")
    assert len(teams) == 2
    assert teams[0].name == "Adelaide"
    assert teams[0].abbreviation == "ADEL"
    assert teams[0].competition == "afl"
    assert teams[1].name == "Brisbane Lions"


def test_teams_nrl_parses_correctly():
    with respx.mock(base_url="https://api.squiggle.com.au") as mock:
        mock.get("/").mock(return_value=httpx.Response(200, json=_load("nrl_teams.json")))
        with SquiggleClient() as client:
            teams = client.teams("nrl")
    assert len(teams) == 2
    assert teams[0].abbreviation == "BRI"
    assert teams[0].competition == "nrl"


# ---------- games ----------

def test_games_handles_missing_scores_as_none():
    raw = {
        "games": [
            {
                "id": 1,
                "round": 1,
                "year": 2025,
                "date": "2025-03-20 19:30:00",
                "hteam": "Carlton",
                "ateam": "Richmond",
                "hscore": 85,
                "ascore": 72,
                "venue": "MCG",
                "complete": 1,
            },
            {
                "id": 2,
                "round": 2,
                "year": 2025,
                "date": "2025-03-28 19:30:00",
                "hteam": "Essendon",
                "ateam": "Collingwood",
                "hscore": None,
                "ascore": None,
                "venue": "MCG",
                "complete": 0,
            },
        ]
    }
    with respx.mock(base_url="https://api.squiggle.com.au") as mock:
        mock.get("/").mock(return_value=httpx.Response(200, json=raw))
        with SquiggleClient() as client:
            games = client.games("afl", year=2025)
    assert len(games) == 2
    assert games[0].home_score == 85
    assert games[0].away_score == 72
    assert games[0].winner == "Carlton"
    assert games[1].home_score is None
    assert games[1].away_score is None
    assert games[1].winner is None


def test_games_filters_by_round():
    with respx.mock(base_url="https://api.squiggle.com.au") as mock:
        route = mock.get("/").mock(return_value=httpx.Response(200, json=_load("afl_games.json")))
        with SquiggleClient() as client:
            client.games("afl", year=2025, round=1)
    # Verify the client sent the round param
    assert route.calls.last.request.url.params["round"] == "1"


# ---------- error handling ----------

def test_500_raises_squiggle_error():
    with respx.mock(base_url="https://api.squiggle.com.au") as mock:
        mock.get("/").mock(return_value=httpx.Response(500, text="server down"))
        with SquiggleClient() as client:
            with pytest.raises(SquiggleError, match="HTTP 500"):
                client.teams("afl")


def test_api_error_in_payload_raises_squiggle_error():
    with respx.mock(base_url="https://api.squiggle.com.au") as mock:
        mock.get("/").mock(return_value=httpx.Response(200, json={"error": "bad query"}))
        with SquiggleClient() as client:
            with pytest.raises(SquiggleError, match="bad query"):
                client.teams("afl")


# ---------- ladder computation ----------

def test_compute_ladder_basic():
    games = [
        Game(
            id=1, round=1, year=2025, date="2025-03-20",
            home_team="A", away_team="B",
            home_score=80, away_score=70,
            venue="X", competition="afl", complete=True,
        ),
        Game(
            id=2, round=1, year=2025, date="2025-03-21",
            home_team="B", away_team="C",
            home_score=60, away_score=60,
            venue="X", competition="afl", complete=True,
        ),
        Game(
            id=3, round=1, year=2025, date="2025-03-22",
            home_team="C", away_team="A",
            home_score=50, away_score=90,
            venue="X", competition="afl", complete=True,
        ),
    ]
    ladder = compute_ladder(games)
    # A: 2W (beat B, beat C) -> 8 pts; PF=170, PA=120; pct=141.67
    # B: 0W, 1D (vs C), 1L (vs A) -> 2 pts; PF=130, PA=140; pct=92.86
    # C: 0W, 1D (vs B), 1L (vs A) -> 2 pts; PF=110, PA=150; pct=73.33
    # Tied B and C on points -> broken by percentage
    assert [r["team"] for r in ladder] == ["A", "B", "C"]
    assert ladder[0]["premiership_points"] == 8
    assert ladder[1]["premiership_points"] == 2
    assert ladder[1]["draws"] == 1
    assert ladder[1]["losses"] == 1
    assert ladder[2]["losses"] == 1
    assert ladder[1]["percentage"] > ladder[2]["percentage"]


def test_compute_ladder_skips_incomplete_games():
    games = [
        Game(
            id=1, round=1, year=2025, date="2025-03-20",
            home_team="A", away_team="B",
            home_score=80, away_score=70,
            venue="X", competition="afl", complete=True,
        ),
        Game(
            id=2, round=2, year=2025, date="2025-03-28",
            home_team="A", away_team="B",
            home_score=None, away_score=None,
            venue="X", competition="afl", complete=False,
        ),
    ]
    ladder = compute_ladder(games)
    # Only the completed game counts
    assert all(r["played"] == 1 for r in ladder)


# ---------- dataclass helpers ----------

def test_team_from_api_falls_back_to_abbrev_from_name():
    t = Team.from_api({"id": 99, "name": "GWS", "abbrev": ""}, "afl")
    # Falls back to first 3 chars uppercased if abbrev missing
    assert t.abbreviation == "GWS"
