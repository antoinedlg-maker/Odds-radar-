"""Mise en forme des messages Discord (embeds)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from .analysis import best_prices
from .config import book_name, market_name
from .models import Event, Surebet, ValueBet

PARIS = ZoneInfo("Europe/Paris")
GREEN = 0x2ECC71
GOLD = 0xF1C40F
BLUE = 0x3498DB


def when(dt: datetime) -> str:
    return dt.astimezone(PARIS).strftime("%a %d/%m %H:%M")


def _outcome_label(ev: Event, outcome: str) -> str:
    if outcome == "Draw":
        return "Nul"
    if outcome == "Over":
        return "Plus"
    if outcome == "Under":
        return "Moins"
    return outcome


def surebet_embed(sb: Surebet) -> discord.Embed:
    ev = sb.event
    e = discord.Embed(
        title=f"🟢 Surebet +{sb.profit_pct:.2f} %",
        description=f"**{ev.name}**\n{ev.sport_title} · {when(ev.commence_time)}\n{market_name(sb.market, sb.point)}",
        color=GREEN,
    )
    lines = [
        f"**{_outcome_label(ev, l.outcome)}** @ {l.odds:.2f} chez **{book_name(l.bookmaker)}** → mise {l.stake:.2f} €"
        for l in sb.legs
    ]
    total = sum(l.stake for l in sb.legs)
    gain = sb.legs[0].stake * sb.legs[0].odds - total
    e.add_field(name=f"Répartition pour {total:.0f} €", value="\n".join(lines), inline=False)
    e.set_footer(text=f"Gain garanti ≈ {gain:.2f} € · vérifie les cotes avant de miser, elles bougent vite")
    return e


def value_embed(vb: ValueBet) -> discord.Embed:
    ev = vb.event
    e = discord.Embed(
        title=f"💎 Value bet +{vb.edge_pct:.1f} %",
        description=f"**{ev.name}**\n{ev.sport_title} · {when(ev.commence_time)}\n{market_name(vb.market, vb.point)}",
        color=GOLD,
    )
    e.add_field(name="Pari", value=f"**{_outcome_label(ev, vb.outcome)}**", inline=True)
    e.add_field(name="Cote", value=f"{vb.odds:.2f} ({book_name(vb.bookmaker)})", inline=True)
    e.add_field(name="Cote juste", value=f"{vb.fair_odds:.2f}", inline=True)
    e.set_footer(text="Cote juste estimée d'après Pinnacle sans marge. Avantage sur le long terme, pas une garantie.")
    return e


def event_embed(ev: Event, books: list[str]) -> discord.Embed:
    e = discord.Embed(title=ev.name, description=f"{ev.sport_title} · {when(ev.commence_time)}", color=BLUE)
    best = best_prices(ev, books)
    for (market, point), outcomes in sorted(best.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        rows = []
        for book in books:
            b = ev.bookmaker(book)
            if b is None:
                continue
            prices = [p for p in b.markets.get(market, []) if p.point == point]
            if not prices:
                continue
            cells = []
            for p in prices:
                star = "**" if outcomes.get(p.outcome, (0, ""))[1] == book else ""
                cells.append(f"{_outcome_label(ev, p.outcome)} {star}{p.odds:.2f}{star}")
            rows.append(f"`{book_name(book):<9}` " + " · ".join(cells))
        if rows:
            e.add_field(name=market_name(market, point), value="\n".join(rows)[:1024], inline=False)
    if not e.fields:
        e.add_field(name="Aucune cote", value="Aucun des bookmakers suivis ne propose ce match pour l'instant.")
    e.set_footer(text="En gras : meilleure cote pour chaque issue")
    return e
