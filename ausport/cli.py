"""Click CLI for ausport-fixtures.

Run `ausport --help` for the command list. Each subcommand supports
`--format=table|json|csv` and a quiet mode.
"""

from __future__ import annotations

import sys
from datetime import date

import click

from . import __version__
from .api import SquiggleClient, SquiggleError, compute_ladder
from .formatters import format_output

VALID_COMPETITIONS = ("afl", "nrl")
VALID_FORMATS = ("table", "json", "csv")


@click.group()
@click.version_option(__version__, prog_name="ausport")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(VALID_FORMATS, case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.option("-q", "--quiet", is_flag=True, help="Suppress headers and decorations.")
@click.pass_context
def main(ctx: click.Context, fmt: str, quiet: bool) -> None:
    """Australian sports fixtures, results, and ladders from public data."""
    # Stash options for subcommands
    ctx.ensure_object(dict)
    ctx.obj["fmt"] = fmt
    ctx.obj["quiet"] = quiet


@main.command()
@click.argument("competition", type=click.Choice(VALID_COMPETITIONS))
@click.pass_context
def teams(ctx: click.Context, competition: str) -> None:
    """List all teams in a competition."""
    try:
        with SquiggleClient() as client:
            data = client.teams(competition)
    except SquiggleError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    click.echo(format_output(data, ctx.obj["fmt"], title=f"{competition.upper()} teams"))


@main.command()
@click.argument("competition", type=click.Choice(VALID_COMPETITIONS))
@click.option("--year", type=int, default=None, help="Season year (default: current).")
@click.option("--round", "round_num", type=int, default=None, help="Specific round number.")
@click.option(
    "--complete/--all",
    default=None,
    help="Show only completed games (--complete) or all including upcoming (--all). Default: all.",
)
@click.pass_context
def fixtures(ctx: click.Context, competition: str, year: int | None, round_num: int | None, complete: bool | None) -> None:
    """Show fixtures for a competition."""
    if year is None:
        year = date.today().year
    try:
        with SquiggleClient() as client:
            data = client.games(competition, year=year, round=round_num, complete=complete)
    except SquiggleError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    title = f"{competition.upper()} {year} games"
    if round_num is not None:
        title = f"{competition.upper()} {year} round {round_num}"
    click.echo(format_output(data, ctx.obj["fmt"], title=title))


@main.command()
@click.argument("competition", type=click.Choice(VALID_COMPETITIONS))
@click.option("--year", type=int, default=None, help="Season year (default: current).")
@click.option("--since", type=str, default=None, help="Only show games from this date (YYYY-MM-DD).")
@click.pass_context
def results(ctx: click.Context, competition: str, year: int | None, since: str | None) -> None:
    """Show completed results (winners, scores)."""
    if year is None:
        year = date.today().year
    try:
        with SquiggleClient() as client:
            data = client.games(competition, year=year, complete=True)
    except SquiggleError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    if since:
        data = [g for g in data if g.date and g.date[:10] >= since]
    data.sort(key=lambda g: g.date, reverse=True)
    click.echo(format_output(data, ctx.obj["fmt"], title=f"{competition.upper()} {year} results"))


@main.command()
@click.argument("competition", type=click.Choice(VALID_COMPETITIONS))
@click.option("--year", type=int, default=None, help="Season year (default: current).")
@click.pass_context
def ladder(ctx: click.Context, competition: str, year: int | None) -> None:
    """Show the current ladder (ranked by premiership points and percentage)."""
    if year is None:
        year = date.today().year
    try:
        with SquiggleClient() as client:
            games = client.games(competition, year=year, complete=True)
    except SquiggleError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    rows = compute_ladder(games)
    click.echo(format_output(rows, ctx.obj["fmt"], title=f"{competition.upper()} {year} ladder"))


if __name__ == "__main__":
    main(obj={})
