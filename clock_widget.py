#!/usr/bin/env python3
"""Clock widget — full-width, single vertical module.

Mostra: orologio digitale, percentuale della giornata, stato batteria.
Usage: python clock_widget.py
"""

import datetime
import sys
import time

try:
    from rich.align import Align
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    sys.exit("Dipendenza mancante: pip install rich")

try:
    import psutil as _psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

# Cifre digitali su 3 righe, ognuna larga 3 caratteri
_SEGS: dict[str, list[str]] = {
    "0": ["┌─┐", "│ │", "└─┘"],
    "1": [" ╷ ", " │ ", " ╵ "],
    "2": ["╶─┐", "┌─┘", "└─╴"],
    "3": ["╶─┐", "╶─┤", "╶─┘"],
    "4": ["╷ ╷", "└─┤", "  ╵"],
    "5": ["┌─╴", "└─┐", "╶─┘"],
    "6": ["┌─╴", "├─┐", "└─┘"],
    "7": ["╶─┐", "  │", "  ╵"],
    "8": ["┌─┐", "├─┤", "└─┘"],
    "9": ["┌─┐", "└─┤", "╶─┘"],
    ":": ["   ", " ∶ ", "   "],
}


def _clock_art(s: str) -> list[str]:
    rows = ["", "", ""]
    for ch in s:
        seg = _SEGS.get(ch, ["   ", "   ", "   "])
        for i in range(3):
            rows[i] += seg[i] + "  "
    return rows


def _bar(pct: float, width: int = 44, fill: str = "█", empty: str = "░") -> str:
    n = max(0, min(width, round(width * pct / 100)))
    return fill * n + empty * (width - n)


def _battery() -> tuple[float | None, bool | None]:
    if not _HAS_PSUTIL:
        return None, None
    b = _psutil.sensors_battery()
    if b is None:
        return None, None
    return b.percent, b.power_plugged


def _widget() -> Panel:
    now = datetime.datetime.now()

    elapsed = now.hour * 3600 + now.minute * 60 + now.second
    day_pct = elapsed / 86400 * 100

    batt_pct, plugged = _battery()

    grid = Table.grid(expand=True)
    grid.add_column(justify="center")

    # ── Orologio digitale ──────────────────────────────────────────────
    grid.add_row("")
    for row in _clock_art(now.strftime("%H:%M:%S")):
        grid.add_row(Align.center(Text(row, style="bold bright_cyan")))

    # ── Data ───────────────────────────────────────────────────────────
    grid.add_row("")
    grid.add_row(Align.center(Text(
        now.strftime("%A, %d %B %Y").capitalize(),
        style="dim white",
    )))
    grid.add_row("")

    # ── Percentuale giornata ───────────────────────────────────────────
    day_label = Text()
    day_label.append("☀  Giorno  ", style="yellow")
    day_label.append(f"{day_pct:5.1f}%", style="bold yellow")
    grid.add_row(Align.center(day_label))
    grid.add_row(Align.center(Text(_bar(day_pct), style="yellow")))
    grid.add_row("")

    # ── Batteria ───────────────────────────────────────────────────────
    if batt_pct is not None:
        icon = "⚡" if plugged else "🔋"
        clr = "green" if batt_pct > 50 else ("yellow" if batt_pct > 20 else "red")
        batt_label = Text()
        batt_label.append(f"{icon}  Batteria  ", style=clr)
        batt_label.append(f"{batt_pct:5.1f}%", style=f"bold {clr}")
        if plugged:
            batt_label.append("  in carica", style="dim green")
        grid.add_row(Align.center(batt_label))
        grid.add_row(Align.center(Text(_bar(batt_pct), style=clr)))
    else:
        grid.add_row(Align.center(Text("🔋  Batteria non disponibile", style="dim")))

    grid.add_row("")

    return Panel(
        grid,
        title="[bold bright_blue] Clock [/bold bright_blue]",
        border_style="bright_blue",
        expand=True,
    )


def main() -> None:
    console = Console()
    with Live(_widget(), console=console, refresh_per_second=2) as live:
        try:
            while True:
                time.sleep(0.5)
                live.update(_widget())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
