from datetime import datetime, timezone

from odds_radar.anomalies import find_odds_anomalies
from odds_radar.models import BookmakerOdds, Event, Price


def _event(odds_by_book):
    books = [
        BookmakerOdds(k, k, None, {"h2h": [Price("Home", h), Price("Away", a)]})
        for k, (h, a) in odds_by_book.items()
    ]
    return Event("e1", "soccer_x", "X", datetime(2030, 1, 1, tzinfo=timezone.utc), "Home", "Away", books)


def test_detecte_une_cote_aberrante():
    ev = _event({"a": (2.0, 2.0), "b": (2.1, 1.9), "c": (1.95, 2.05), "d": (3.5, 1.8)})
    found = find_odds_anomalies([ev], ["a", "b", "c", "d"], min_gap_pct=25)
    assert len(found) == 1
    assert found[0].bookmaker == "d" and found[0].outcome == "Home"
    assert found[0].gap_pct == 75.0


def test_pas_assez_de_bookmakers():
    ev = _event({"a": (2.0, 2.0), "d": (3.5, 1.8)})
    assert find_odds_anomalies([ev], ["a", "d"], min_gap_pct=25) == []


def test_cotes_normales():
    ev = _event({"a": (2.0, 2.0), "b": (2.1, 1.9), "c": (1.95, 2.05)})
    assert find_odds_anomalies([ev], ["a", "b", "c"], min_gap_pct=25) == []
