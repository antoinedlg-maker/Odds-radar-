"""Calculs : meilleures cotes, surebets (arbitrages) et value bets."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import Event, Leg, Price, Surebet, ValueBet

Line = tuple[str, float | None]  # (marché, ligne) — la ligne vaut None pour le 1N2


def _lines(event: Event, books: Iterable[str]) -> dict[Line, dict[str, dict[str, float]]]:
    """Regroupe les cotes par (marché, ligne) -> issue -> bookmaker -> cote."""
    out: dict[Line, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    wanted = set(books)
    for b in event.bookmakers:
        if b.key not in wanted:
            continue
        for market, prices in b.markets.items():
            for p in prices:
                if p.odds > 1.0:
                    out[(market, p.point)][p.outcome][b.key] = p.odds
    return out


def _complete_outcomes(event: Event, market: str, point: float | None, books: Iterable[str]) -> set[str]:
    """Issues attendues pour une ligne : le plus grand ensemble proposé par un seul bookmaker.

    Évite de prendre un "surebet" 2 issues sur un marché qui en a 3 (oubli du nul).
    """
    best: set[str] = set()
    for b in event.bookmakers:
        if b.key not in books:
            continue
        outs = {p.outcome for p in b.markets.get(market, []) if p.point == point}
        if len(outs) > len(best):
            best = outs
    return best


def best_prices(event: Event, books: Iterable[str]) -> dict[Line, dict[str, tuple[float, str]]]:
    """Meilleure cote par issue : (marché, ligne) -> issue -> (cote, bookmaker)."""
    books = list(books)
    result: dict[Line, dict[str, tuple[float, str]]] = {}
    for line, outcomes in _lines(event, books).items():
        result[line] = {
            outcome: max(((o, bk) for bk, o in by_book.items()), key=lambda t: t[0])
            for outcome, by_book in outcomes.items()
        }
    return result


def find_surebets(
    events: Iterable[Event],
    books: Iterable[str],
    min_profit_pct: float = 0.0,
    total_stake: float = 100.0,
) -> list[Surebet]:
    books = list(books)
    found: list[Surebet] = []
    for ev in events:
        for (market, point), best in best_prices(ev, books).items():
            expected = _complete_outcomes(ev, market, point, books)
            if len(expected) < 2 or not expected.issubset(best):
                continue
            legs_raw = [(o, *best[o]) for o in sorted(expected)]
            # Un arbitrage sur un seul bookmaker n'existe pas en pratique : c'est une erreur de données.
            if len({bk for _, _, bk in legs_raw}) < 2:
                continue
            inv = sum(1.0 / odds for _, odds, _ in legs_raw)
            if inv >= 1.0:
                continue
            profit = (1.0 / inv - 1.0) * 100.0
            if profit < min_profit_pct:
                continue
            legs = tuple(
                Leg(outcome=o, odds=odds, bookmaker=bk, stake=round(total_stake * (1.0 / odds) / inv, 2))
                for o, odds, bk in legs_raw
            )
            found.append(Surebet(ev, market, point, legs, round(profit, 2)))
    found.sort(key=lambda s: s.profit_pct, reverse=True)
    return found


def fair_probabilities(prices: Iterable[Price]) -> dict[str, float]:
    """Probabilités sans marge (normalisation proportionnelle des 1/cote)."""
    prices = [p for p in prices if p.odds > 1.0]
    implied = {p.outcome: 1.0 / p.odds for p in prices}
    total = sum(implied.values())
    if total <= 0:
        return {}
    return {o: v / total for o, v in implied.items()}


def find_value_bets(
    events: Iterable[Event],
    books: Iterable[str],
    reference: str = "pinnacle",
    min_edge_pct: float = 3.0,
    max_odds: float = 10.0,
) -> list[ValueBet]:
    books = [b for b in books if b != reference]
    found: list[ValueBet] = []
    for ev in events:
        ref = ev.bookmaker(reference)
        if ref is None:
            continue
        for market, ref_prices in ref.markets.items():
            by_point: dict[float | None, list[Price]] = defaultdict(list)
            for p in ref_prices:
                by_point[p.point].append(p)
            for point, line_prices in by_point.items():
                if len(line_prices) < 2:
                    continue
                fair = fair_probabilities(line_prices)
                for b in ev.bookmakers:
                    if b.key not in books:
                        continue
                    for p in b.markets.get(market, []):
                        if p.point != point or p.outcome not in fair or p.odds > max_odds:
                            continue
                        prob = fair[p.outcome]
                        edge = (p.odds * prob - 1.0) * 100.0
                        if edge >= min_edge_pct:
                            found.append(
                                ValueBet(
                                    event=ev,
                                    market=market,
                                    point=point,
                                    outcome=p.outcome,
                                    bookmaker=b.key,
                                    odds=p.odds,
                                    fair_odds=round(1.0 / prob, 2),
                                    edge_pct=round(edge, 2),
                                )
                            )
    found.sort(key=lambda v: v.edge_pct, reverse=True)
    return found
