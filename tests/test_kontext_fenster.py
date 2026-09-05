"""Das Kontextfenster (06.09.2026, Birk: "Kontextfenster ist kaputt").

Gemessen an der Testgruppe um 00:33: der Nutzertext eines Zuges hatte
**52 000 Zeichen**, der Gespraechsverlauf stand **rueckwaerts** darin
(neueste zuerst), reichte 700 Zeilen bis in den Vormittag der uebernommenen
Gruppe-1-Historie zurueck, und "Bin wieder da" stand doppelt.

Die Ursache ist eine Sortierannahme: ``repo.letzte_nachrichten`` ordnet nach
``message_id``, und eine uebernommene Historie traegt **negative, absteigend
vergebene** ids (in der Testgruppe 45 Stueck, von -256 abwaerts). Aufsteigend
sortiert steht die aelteste damit zuletzt.

Die Folge ist belegt (05.09.2026, 21:50): das Modell hielt den Vormittag fuer
die Gegenwart und bot in Phase 6 an, aus den Begriffen Interviewfragen zu
entwickeln -- "Das ist Tag 1 und wir stehen erst am Anfang."
"""

from datetime import datetime, timedelta

import pytest

from interview_theater import kontext, repo


def _lege_an(conn, message_id, ist_bot, text, minuten_vor_jetzt, absender="Birk"):
    zeit = (
        datetime.fromisoformat("2026-09-06T00:30:00+00:00")
        - timedelta(minutes=minuten_vor_jetzt)
    ).isoformat()
    repo.merke_nachricht(
        conn, 1, message_id, absender, 1 if ist_bot else 0, "text", text, zeit,
    )


@pytest.fixture
def gruppe(conn):
    repo.sichere_gruppe(conn, 1, "testbot", "Testgruppe")
    return conn


def test_fenster_steht_chronologisch(gruppe):
    """Aelteste oben, juengste direkt vor dem Ausloeser -- auch bei negativen,
    absteigend vergebenen message_ids aus einer uebernommenen Historie."""
    _lege_an(gruppe, -300, False, "ganz frueh am Vormittag", 20)
    _lege_an(gruppe, -310, False, "kurz danach am Vormittag", 15)
    _lege_an(gruppe, -320, False, "zuletzt am Vormittag", 5)

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, [])

    texte = "\n".join(eintraege)
    assert texte.index("ganz frueh") < texte.index("kurz danach") < texte.index("zuletzt")


def test_fenster_bleibt_bei_zwanzig_nachrichten(gruppe):
    """Kein Archiv: 700 Zeilen Vormittag gehoeren nicht in jeden Zug."""
    for i in range(40):
        _lege_an(gruppe, 100 + i, False, f"Nachricht {i}", 20 - i * 0.4)

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, [])

    nachrichtenzeilen = [z for z in eintraege if "Nachricht" in z]
    assert len(nachrichtenzeilen) == kontext.FENSTER_NACHRICHTEN
    assert "Nachricht 39" in "\n".join(eintraege)
    assert "Nachricht 0" not in "\n".join(eintraege)


def test_alles_aeltere_als_dreissig_minuten_faellt_weg(gruppe):
    """Der 21:50-Fall: der Vormittag ist nicht die Gegenwart."""
    _lege_an(gruppe, -300, False, "Vormittagszeug von damals", 600)
    _lege_an(gruppe, 200, False, "gerade eben gesagt", 3)

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, [])

    texte = "\n".join(eintraege)
    assert "gerade eben" in texte
    assert "Vormittagszeug" not in texte


def test_systemzeilen_stehen_nicht_im_fenster(gruppe):
    """Sie sind Ereignisse, keine Gespraechsbeitraege -- und "Bin wieder da"
    stand am Testabend doppelt im Fenster."""
    _lege_an(gruppe, 200, True, "Bin wieder da. Wir sind bei 4 · Setting & Figuren.", 10)
    _lege_an(gruppe, 201, True, "Notiert:\nRahmen: Schulhof", 9)
    _lege_an(gruppe, 202, True, "Ich schreibe die Szene aus, das dauert eine Minute.", 8)
    _lege_an(gruppe, 203, True, "Dann faengt Szene 1 am Kiosk an.", 7)
    _lege_an(gruppe, 204, False, "passt", 6)

    texte = "\n".join(kontext._baue_fenster_eintraege(gruppe, 1, []))

    assert "Bin wieder da" not in texte
    assert "Notiert:" not in texte
    assert "Ich schreibe die Szene aus" not in texte
    assert "Dann faengt Szene 1 am Kiosk an." in texte, "echte Beitraege bleiben"
    assert "passt" in texte


def test_eine_gruppennachricht_faellt_nie_dem_systemfilter_zum_opfer(gruppe):
    """Tippt die Gruppe selbst "Notiert:", sagt sie damit etwas."""
    _lege_an(gruppe, 200, False, "Notiert: wir wollen den Kiosk", 5)

    texte = "\n".join(kontext._baue_fenster_eintraege(gruppe, 1, []))

    assert "wir wollen den Kiosk" in texte


def test_der_ausloeser_ist_der_bezugspunkt_der_zeitgrenze(gruppe):
    """Nicht ``jetzt``: ein Nachlauf soll dieselbe Antwort bekommen wie der
    Livezug."""
    _lege_an(gruppe, 200, False, "zehn Minuten vor dem Ausloeser", 15)
    _lege_an(gruppe, 201, False, "zwei Stunden vor dem Ausloeser", 125)
    ausloeser = [dict(n) for n in repo.letzte_nachrichten(gruppe, 1) if n["message_id"] == 202]

    _lege_an(gruppe, 202, False, "der Ausloeser", 5)
    ausloeser = [
        dict(n) for n in repo.letzte_nachrichten(gruppe, 1)
        if n["message_id"] == 202
    ]

    texte = "\n".join(kontext._baue_fenster_eintraege(gruppe, 1, ausloeser))

    assert "zehn Minuten" in texte
    assert "zwei Stunden" not in texte
    assert "der Ausloeser" not in texte, "der Ausloeser steht im eigenen Block"
