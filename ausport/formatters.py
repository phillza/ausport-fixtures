"""Output formatters for ausport commands.

Three formats: table (default, via rich), json, csv. Each is a function that
takes a list of dataclass instances and returns a string ready to print.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, is_dataclass
from typing import Iterable, Sequence

from rich.console import Console
from rich.table import Table


def _to_dicts(items: Iterable) -> list[dict]:
    """Convert an iterable of dataclasses to list of dicts (for json/csv)."""
    out = []
    for it in items:
        if is_dataclass(it):
            out.append(asdict(it))
        elif isinstance(it, dict):
            out.append(it)
        else:
            raise TypeError(f"Cannot format {type(it).__name__}")
    return out


def format_table(items: Sequence, title: str | None = None) -> str:
    """Render a list of dataclasses as a rich Table and return the string."""
    if not items:
        return "(no data)\n"
    rows = _to_dicts(items)
    keys = list(rows[0].keys())
    table = Table(title=title, show_header=True, header_style="bold")
    for k in keys:
        table.add_column(k)
    for r in rows:
        table.add_row(*[str(r.get(k, "")) for k in keys])
    buf = io.StringIO()
    Console(file=buf, force_terminal=False, width=120).print(table)
    return buf.getvalue()


def format_json(items: Sequence, indent: int = 2) -> str:
    """Render a list of dataclasses as JSON."""
    return json.dumps(_to_dicts(items), indent=indent, default=str)


def format_csv(items: Sequence) -> str:
    """Render a list of dataclasses as CSV."""
    if not items:
        return ""
    rows = _to_dicts(items)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def format_output(items: Sequence, fmt: str, title: str | None = None) -> str:
    """Dispatch to the right formatter by name."""
    fmt = fmt.lower()
    if fmt == "json":
        return format_json(items)
    if fmt == "csv":
        return format_csv(items)
    if fmt in ("table", "txt", "text"):
        return format_table(items, title=title)
    raise ValueError(f"Unknown format: {fmt!r} (use table|json|csv)")
