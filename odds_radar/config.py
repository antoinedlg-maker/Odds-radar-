from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

BOOKMAKER_NAMES = {
    "winamax_fr": "Winamax",
    "unibet_fr": "Unibet",
    "pmu_fr": "PMU",
    "betsson": "Betsson",
    "betclic_fr": "Betclic",
    "netbet_fr": "NetBet",
    "pinnacle": "Pinnacle",
}

MARKET_NAMES = {"h2h": "1N2", "totals": "Plus/Moins"}


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _int(name: str, default: int | None) -> int | None:
    v = os.getenv(name, "").strip()
    return int(v) if v else default


def _float(name: str, default: float) -> float:
    v = os.getenv(name, "").strip()
    return float(v) if v else default


@dataclass
class Config:
    discord_token: str
    odds_api_key: str
    alert_channel_id: int | None
    guild_id: int | None
    sports: list[str]
    bookmakers: list[str]
    reference_bookmaker: str
    markets: list[str]
    scan_interval_minutes: int
    min_surebet_profit: float
    min_value_edge: float
    max_value_odds: float
    min_credits_reserve: int

    @property
    def fetched_bookmakers(self) -> list[str]:
        """Bookmakers suivis + la référence (Pinnacle) pour calculer la cote juste."""
        books = list(self.bookmakers)
        if self.reference_bookmaker and self.reference_bookmaker not in books:
            books.append(self.reference_bookmaker)
        return books

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN", "").strip()
        key = os.getenv("ODDS_API_KEY", "").strip()
        if not token or not key:
            raise SystemExit("DISCORD_TOKEN et ODDS_API_KEY sont obligatoires (voir .env.example).")
        return cls(
            discord_token=token,
            odds_api_key=key,
            alert_channel_id=_int("ALERT_CHANNEL_ID", None),
            guild_id=_int("GUILD_ID", None),
            sports=_list("SPORTS", "soccer_france_ligue_one,soccer_epl"),
            bookmakers=_list("BOOKMAKERS", "winamax_fr,unibet_fr,pmu_fr,betsson"),
            reference_bookmaker=os.getenv("REFERENCE_BOOKMAKER", "pinnacle").strip(),
            markets=_list("MARKETS", "h2h"),
            scan_interval_minutes=_int("SCAN_INTERVAL_MINUTES", 240) or 240,
            min_surebet_profit=_float("MIN_SUREBET_PROFIT", 0.5),
            min_value_edge=_float("MIN_VALUE_EDGE", 3.0),
            max_value_odds=_float("MAX_VALUE_ODDS", 10.0),
            min_credits_reserve=_int("MIN_CREDITS_RESERVE", 20) or 0,
        )


def book_name(key: str) -> str:
    return BOOKMAKER_NAMES.get(key, key)


def market_name(market: str, point: float | None = None) -> str:
    name = MARKET_NAMES.get(market, market)
    return f"{name} {point:g}" if point is not None else name
