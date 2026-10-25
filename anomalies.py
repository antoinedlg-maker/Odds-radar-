"""Détection d'erreurs de cotes : une cote très au-dessus de la médiane des autres bookmakers."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

import discord

from .analysis import _lines
from .config import book_name, market_name
from .formatting import _outcome_label, when
from .models import Event

ORANGE = 0xE67E22


@dataclass(frozen=True)
class OddsAnomaly:
    event: Event
    market: str
    point: float | None
    outcome: str
    bookmaker: str
    odds: float
    median_odds: float  # médiane des cotes des autres bookmakers
    gap_pct: float  # écart au-dessus de la médiane, en %

    @property
    def key(self) -> str:
        return (
            f"oe:{self.event.id}:{self.market}:{self.point}:"
            f"{self.outcome}:{self.bookmaker}:{self.odds:.2f}"
        )


def find_odds_anomalies(
    events: Iterable[Event],
    books: Iterable[str],
    min_gap_pct: float = 25.0,
    min_books: int = 3,
) -> list[OddsAnomaly]:
    """Cotes qui dépassent de `min_gap_pct` % la médiane des autres bookmakers.

    Il faut au moins `min_books` bookmakers sur l'issue pour que la médiane ait un sens.
    """
    books = list(books)
    found: list[OddsAnomaly] = []
    for ev in events:
        for (market, point), outcomes in _lines(ev, books).items():
            for outcome, by_book in outcomes.items():
                if len(by_book) < min_books:
                    continue
                for bk, odds in by_book.items():
                    others = [o for b, o in by_book.items() if b != bk]
                    ref = median(others)
                    gap = (odds / ref - 1.0) * 100.0
                    if gap >= min_gap_pct:
                        found.append(
                            OddsAnomaly(ev, market, point, outcome, bk, odds, round(ref, 2), round(gap, 1))
                        )
    found.sort(key=lambda a: a.gap_pct, reverse=True)
    return found


def anomaly_embed(a: OddsAnomaly) -> discord.Embed:
    ev = a.event
    e = discord.Embed(
        title=f"⚠️ Erreur de cote possible +{a.gap_pct:.0f} %",
        description=f"**{ev.name}**\n{ev.sport_title} · {when(ev.commence_time)}\n{market_name(a.market, a.point)}",
        color=ORANGE,
    )
    e.add_field(name="Pari", value=f"**{_outcome_label(ev, a.outcome)}**", inline=True)
    e.add_field(name="Cote", value=f"{a.odds:.2f} ({book_name(a.bookmaker)})", inline=True)
    e.add_field(name="Médiane des autres", value=f"{a.median_odds:.2f}", inline=True)
    e.set_footer(
        text="Vraie erreur ou cote périmée : vérifie sur le site. Un pari pris sur une erreur peut être annulé."
    )
    return e
