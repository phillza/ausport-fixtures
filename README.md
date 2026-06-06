# ausport-fixtures

> Australian sports fixtures, results, and ladders from public data sources.

A small CLI for Aussie sports fans who want to look up a fixture, check the ladder, or pipe recent results into another tool. No bookmaker scraping, no auth, no secrets — just the public Squiggle API.

## What it does

- `ausport teams afl` — list all 18 AFL teams
- `ausport teams nrl` — list all 17 NRL teams
- `ausport fixtures afl --year=2025 --round=12` — show round 12 AFL games
- `ausport results afl --year=2025 --since=2025-06-01` — show AFL results since a date
- `ausport ladder afl --year=2025` — show the current AFL ladder

Three output formats: `table` (default, pretty), `json`, `csv`.

## Quick start

```bash
# Install from source
git clone https://github.com/phillza/ausport-fixtures
cd ausport-fixtures
pip install -e .

# Try it
ausport teams afl
ausport fixtures afl --round=1
ausport ladder afl --format=json
ausport results nrl --since=2025-05-01 --format=csv > recent.csv
```

## Data source

All data comes from [Squiggle](https://api.squiggle.com.au/) — a free, public, no-auth JSON API that aggregates AFL and NRL fixtures and results. No bookmaker data, no betting markets, just the public schedule.

## Why I built this

I wanted a small, fast CLI for Aussie sports that:
- Doesn't require logging in
- Works offline once cached
- Pipes cleanly into other tools (`--format=csv`, `--format=json`)
- Is easy to extend for new competitions (the Squiggle API covers AFL, NRL, and a few others)

## Development

```bash
git clone https://github.com/phillza/ausport-fixtures
cd ausport-fixtures
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
```

## Architecture

```
ausport/
  __init__.py     # package metadata
  api.py          # SquiggleClient: HTTP wrapper + Game/Team dataclasses + compute_ladder
  cli.py          # click commands: teams, fixtures, results, ladder
  formatters.py   # table / json / csv output formatters
tests/
  test_api.py     # unit tests with respx-mocked HTTP
  fixtures/       # canned Squiggle JSON responses
```

The `api.py` module is the only place that touches HTTP. CLI and formatters consume dataclasses, so the whole thing is easy to test without the network.

## License

MIT — see [LICENSE](LICENSE).
