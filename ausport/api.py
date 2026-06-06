"""HTTP client for the Squiggle public sports API.

Data source: https://api.squiggle.com.au/
- Free, no auth, JSON
- Covers AFL, NRL, and a few other Australian competitions
- Returns team lists, fixtures, and results
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

# Squiggle is a community-built public API. We use it because:
# - No auth required
# - Returns clean JSON
# - Covers AFL and NRL
# - Stable for years
DEFAULT_BASE_URL = "https://api.squiggle.com.au"

Competition = Literal["afl", "nrl"]


class SquiggleError(RuntimeError):
    """Raised when the Squiggle API returns an error or unreachable data."""


@dataclass(frozen=True)
class Team:
    """A team in an Australian sports competition."""

    id: int
    name: str
    abbreviation: str
    competition: Competition

    @classmethod
    def from_api(cls, row: dict, competition: Competition) -> "Team":
        abbrev = (row.get("abbrev") or "").strip()
        if not abbrev:
            abbrev = row["name"][:3].upper()
        return cls(
            id=int(row["id"]),
            name=row["name"],
            abbreviation=abbrev,
            competition=competition,
        )


@dataclass(frozen=True)
class Game:
    """A single game (fixture or result)."""

    id: int
    round: int
    year: int
    date: str  # ISO date string, or empty string if unplayed
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    venue: str
    competition: Competition
    complete: bool

    @classmethod
    def from_api(cls, row: dict, competition: Competition) -> "Game":
        # Squiggle returns scores as int or string; normalise to int | None
        def _to_int(v) -> int | None:
            if v in (None, "", "None"):
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        return cls(
            id=int(row["id"]),
            round=int(row.get("round", 0)),
            year=int(row.get("year", 0)),
            date=str(row.get("date", "") or ""),
            home_team=str(row.get("hteam", "")),
            away_team=str(row.get("ateam", "")),
            home_score=_to_int(row.get("hscore")),
            away_score=_to_int(row.get("ascore")),
            venue=str(row.get("venue", "") or ""),
            competition=competition,
            complete=bool(int(row.get("complete", 0) or 0)),
        )

    @property
    def winner(self) -> str | None:
        """Return the winning team name, or None if unplayed/tied."""
        if not self.complete or self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return self.home_team
        if self.away_score > self.home_score:
            return self.away_team
        return None  # tie


class SquiggleClient:
    """Thin wrapper around the Squiggle API.

    Usage:
        client = SquiggleClient()
        teams = client.teams("afl")
        games = client.games("afl", year=2025)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Allow tests to inject a mock client
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "SquiggleClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, params: dict) -> dict:
        """GET /? with the given params. Returns the parsed JSON body."""
        try:
            resp = self._client.get(f"{self.base_url}/", params=params)
        except httpx.HTTPError as e:
            raise SquiggleError(f"Network error contacting Squiggle: {e}") from e
        if resp.status_code != 200:
            raise SquiggleError(
                f"Squiggle returned HTTP {resp.status_code}: {resp.text[:200]}"
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise SquiggleError(f"Squiggle returned non-JSON: {resp.text[:200]}") from e
        if "error" in data and data["error"]:
            raise SquiggleError(f"Squiggle API error: {data['error']}")
        return data

    def teams(self, competition: Competition) -> list[Team]:
        """List all teams in a competition."""
        data = self._get({"q": "teams", "sport": competition_to_sport(competition)})
        rows = data.get("teams", [])
        return [Team.from_api(r, competition) for r in rows]

    def games(
        self,
        competition: Competition,
        *,
        year: int | None = None,
        round: int | None = None,
        complete: bool | None = None,
    ) -> list[Game]:
        """List games, optionally filtered by year/round/complete status."""
        params: dict = {"q": "games", "sport": competition_to_sport(competition)}
        if year is not None:
            params["year"] = year
        if round is not None:
            params["round"] = round
        if complete is not None:
            params["complete"] = 1 if complete else 0
        data = self._get(params)
        rows = data.get("games", [])
        return [Game.from_api(r, competition) for r in rows]


def competition_to_sport(c: Competition) -> str:
    """Map our short competition code to Squiggle's sport name."""
    return {"afl": "AFL", "nrl": "NRL"}[c]


def compute_ladder(games: list[Game], teams: list[Team] | None = None) -> list[dict]:
    """Compute a competition ladder from completed games.

    Returns a list of dicts sorted by premiership points (descending), then by
    percentage (descending), with columns: team, played, wins, draws, losses,
    points_for, points_against, percentage, premiership_points.

    Ladder points: 4 for a win, 2 for a draw, 0 for a loss (standard AFL).
    """
    ladder: dict[str, dict] = {}

    def _row(team: str) -> dict:
        if team not in ladder:
            ladder[team] = {
                "team": team,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points_for": 0,
                "points_against": 0,
                "percentage": 0.0,
                "premiership_points": 0,
            }
        return ladder[team]

    for g in games:
        if not g.complete or g.home_score is None or g.away_score is None:
            continue
        h = _row(g.home_team)
        a = _row(g.away_team)
        h["played"] += 1
        a["played"] += 1
        h["points_for"] += g.home_score
        h["points_against"] += g.away_score
        a["points_for"] += g.away_score
        a["points_against"] += g.home_score
        if g.home_score > g.away_score:
            h["wins"] += 1
            a["losses"] += 1
            h["premiership_points"] += 4
        elif g.away_score > g.home_score:
            a["wins"] += 1
            h["losses"] += 1
            a["premiership_points"] += 4
        else:
            h["draws"] += 1
            a["draws"] += 1
            h["premiership_points"] += 2
            a["premiership_points"] += 2

    # Percentage = points_for / points_against * 100 (0.0 if PA = 0)
    for r in ladder.values():
        pa = r["points_against"]
        r["percentage"] = round((r["points_for"] / pa * 100) if pa else 0.0, 2)

    return sorted(
        ladder.values(),
        key=lambda r: (r["premiership_points"], r["percentage"]),
        reverse=True,
    )
