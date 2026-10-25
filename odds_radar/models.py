from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Price:
    """Une cote pour une issue (ex. "PSG" à 1.85, ou "Over" 2.5 à 1.90)."""

    outcome: str
    odds: float
    point: float | None = None


@dataclass
class BookmakerOdds:
    key: str
    title: str
    last_update: datetime | None
    # clé de marché ("h2h", "totals") -> liste des cotes
    markets: dict[str, list[Price]] = field(default_factory=dict)


@dataclass
class Event:
    id: str
    sport_key: str
    sport_title: str
    commence_time: datetime
    home_team: str
    away_team: str
    bookmakers: list[BookmakerOdds] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.home_team} – {self.away_team}"

    def bookmaker(self, key: str) -> BookmakerOdds | None:
        for b in self.bookmakers:
            if b.key == key:
                return b
        return None


@dataclass(frozen=True)
class Leg:
    outcome: str
    odds: float
    bookmaker: str
    stake: float  # mise conseillée pour une mise totale de référence


@dataclass(frozen=True)
class Surebet:
    event: Event
    market: str
    point: float | None
    legs: tuple[Leg, ...]
    profit_pct: float  # bénéfice garanti en %

    @property
    def key(self) -> str:
        sig = "|".join(f"{l.outcome}@{l.bookmaker}:{l.odds:.2f}" for l in self.legs)
        return f"sb:{self.event.id}:{self.market}:{self.point}:{sig}"


@dataclass(frozen=True)
class ValueBet:
    event: Event
    market: str
    point: float | None
    outcome: str
    bookmaker: str
    odds: float
    fair_odds: float  # cote "juste" sans marge, tirée du bookmaker de référence
    edge_pct: float  # avantage espéré en %

    @property
    def key(self) -> str:
        return (
            f"vb:{self.event.id}:{self.market}:{self.point}:"
            f"{self.outcome}:{self.bookmaker}:{self.odds:.2f}"
        )
