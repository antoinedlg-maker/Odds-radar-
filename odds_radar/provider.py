"""Client pour The Odds API (https://the-odds-api.com)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from .models import BookmakerOdds, Event, Price

log = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"


class OddsApiError(RuntimeError):
    pass


@dataclass
class Usage:
    remaining: int | None = None
    used: int | None = None
    last_cost: int | None = None


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_events(payload: list[dict[str, Any]]) -> list[Event]:
    events: list[Event] = []
    for raw in payload:
        books = []
        for b in raw.get("bookmakers", []):
            markets = {
                m["key"]: [
                    Price(outcome=o["name"], odds=float(o["price"]), point=o.get("point"))
                    for o in m.get("outcomes", [])
                ]
                for m in b.get("markets", [])
            }
            books.append(BookmakerOdds(b["key"], b.get("title", b["key"]), _dt(b.get("last_update")), markets))
        events.append(
            Event(
                id=raw["id"],
                sport_key=raw["sport_key"],
                sport_title=raw.get("sport_title", raw["sport_key"]),
                commence_time=_dt(raw["commence_time"]),
                home_team=raw.get("home_team") or "?",
                away_team=raw.get("away_team") or "?",
                bookmakers=books,
            )
        )
    return events


class OddsApiClient:
    def __init__(self, api_key: str, session: aiohttp.ClientSession | None = None):
        self.api_key = api_key
        self._session = session
        self.usage = Usage()

    async def _get(self, path: str, **params: Any) -> Any:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        params["apiKey"] = self.api_key
        async with self._session.get(f"{BASE_URL}{path}", params=params) as resp:
            h = resp.headers
            if "x-requests-remaining" in h:
                self.usage = Usage(
                    remaining=int(float(h["x-requests-remaining"])),
                    used=int(float(h.get("x-requests-used", 0))),
                    last_cost=int(float(h.get("x-requests-last", 0))),
                )
            if resp.status != 200:
                text = await resp.text()
                raise OddsApiError(f"HTTP {resp.status} sur {path} : {text[:200]}")
            return await resp.json()

    async def sports(self) -> list[dict[str, Any]]:
        """Liste des sports en cours (gratuit, ne consomme pas de crédit)."""
        return await self._get("/sports")

    async def odds(self, sport: str, bookmakers: list[str], markets: list[str]) -> list[Event]:
        """Cotes d'un sport. Coût : 1 crédit par marché et par groupe de 10 bookmakers."""
        data = await self._get(
            f"/sports/{sport}/odds",
            bookmakers=",".join(bookmakers),
            markets=",".join(markets),
            oddsFormat="decimal",
            dateFormat="iso",
        )
        events = parse_events(data)
        log.info("%s : %d matchs, crédits restants %s", sport, len(events), self.usage.remaining)
        return events

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
