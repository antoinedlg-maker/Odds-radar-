from datetime import datetime, timedelta, timezone

from odds_radar.analysis import best_prices, fair_probabilities, find_surebets, find_value_bets
from odds_radar.models import BookmakerOdds, Event, Price
from odds_radar.provider import parse_events

BOOKS = ["winamax_fr", "unibet_fr", "pmu_fr", "betsson"]


def make_event(odds_by_book: dict[str, tuple[float, float, float]]) -> Event:
    books = [
        BookmakerOdds(
            key=k,
            title=k,
            last_update=None,
            markets={"h2h": [Price("PSG", h), Price("Draw", d), Price("OM", a)]},
        )
        for k, (h, d, a) in odds_by_book.items()
    ]
    return Event("e1", "soccer_france_ligue_one", "Ligue 1",
                 datetime.now(timezone.utc) + timedelta(days=1), "PSG", "OM", books)


def test_best_prices_picks_highest_per_outcome():
    ev = make_event({"winamax_fr": (1.80, 3.6, 4.5), "unibet_fr": (1.85, 3.5, 4.2)})
    best = best_prices(ev, BOOKS)[("h2h", None)]
    assert best["PSG"] == (1.85, "unibet_fr")
    assert best["Draw"] == (3.6, "winamax_fr")
    assert best["OM"] == (4.5, "winamax_fr")


def test_surebet_detected_with_stakes():
    ev = make_event({"winamax_fr": (2.20, 3.0, 5.0), "unibet_fr": (1.9, 3.9, 4.0), "pmu_fr": (2.0, 3.2, 5.5)})
    sbs = find_surebets([ev], BOOKS)
    assert len(sbs) == 1
    sb = sbs[0]
    inv = 1 / 2.2 + 1 / 3.9 + 1 / 5.5
    assert abs(sb.profit_pct - round((1 / inv - 1) * 100, 2)) < 1e-9
    assert abs(sum(l.stake for l in sb.legs) - 100) < 0.05
    # chaque issue rapporte le même montant
    payouts = [l.stake * l.odds for l in sb.legs]
    assert max(payouts) - min(payouts) < 0.1


def test_no_surebet_when_margin_positive():
    ev = make_event({"winamax_fr": (1.80, 3.4, 4.2), "unibet_fr": (1.85, 3.3, 4.0)})
    assert find_surebets([ev], BOOKS) == []


def test_surebet_needs_draw_on_three_way_market():
    ev = make_event({"winamax_fr": (2.5, 3.0, 2.5)})
    ev.bookmakers.append(BookmakerOdds("unibet_fr", "u", None, {"h2h": [Price("PSG", 3.0), Price("OM", 3.0)]}))
    # PSG 3.0 + OM 3.0 serait un "arbitrage" si on oubliait le nul
    sbs = find_surebets([ev], BOOKS)
    assert all(len(s.legs) == 3 for s in sbs)


def test_fair_probabilities_sum_to_one():
    probs = fair_probabilities([Price("A", 1.9), Price("B", 1.9)])
    assert abs(sum(probs.values()) - 1) < 1e-9
    assert abs(probs["A"] - 0.5) < 1e-9


def test_value_bet_against_pinnacle():
    ev = make_event({"pinnacle": (2.0, 3.6, 4.0), "winamax_fr": (2.25, 3.4, 3.8)})
    vbs = find_value_bets([ev], BOOKS, reference="pinnacle", min_edge_pct=3)
    assert [(v.outcome, v.bookmaker) for v in vbs] == [("PSG", "winamax_fr")]
    assert vbs[0].edge_pct > 3


def test_parse_events_from_api_payload():
    payload = [{
        "id": "abc", "sport_key": "soccer_epl", "sport_title": "EPL",
        "commence_time": "2026-11-01T15:00:00Z", "home_team": "Arsenal", "away_team": "Chelsea",
        "bookmakers": [{
            "key": "winamax_fr", "title": "Winamax (FR)", "last_update": "2026-10-25T03:00:00Z",
            "markets": [{"key": "h2h", "outcomes": [
                {"name": "Arsenal", "price": 1.9}, {"name": "Chelsea", "price": 4.1}, {"name": "Draw", "price": 3.5},
            ]}],
        }],
    }]
    (ev,) = parse_events(payload)
    assert ev.name == "Arsenal – Chelsea"
    assert ev.bookmaker("winamax_fr").markets["h2h"][0].odds == 1.9
