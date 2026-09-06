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
    absteigend vergebenen message_ids aus einer uebernommenen Historie.

    **Erweitert am 06.09.2026** (Birk, vor dem Merge von Auftrag 1+2): der
    Fensterumbau hat die Auswahlregel angefasst, und die Falle, gegen die
    dieser Test steht, ist genau die, die schon einmal einen Nachmittag
    gekostet hat (AGENTS.md: Fenster nach ``gesendet_am``, **nicht** nach
    ``message_id``). Geprueft wird deshalb die ganze Kette: alle Beitraege
    tragen negative, absteigend vergebene ids, die zeitlich juengste steht
    unten, und die letzte Zeile vor dem Ausloeser ist die zeitlich
    juengste."""
    for i in range(kontext.FENSTER_MIN_NACHRICHTEN + 3):
        # id sinkt, Zeit steigt -- id und Zeit laufen gegeneinander.
        _lege_an(gruppe, -300 - i * 10, False, f"Beitrag {i}", 25 - i)
    _lege_an(gruppe, -900, False, "der Ausloeser", 1)
    ausloeser = [
        dict(n) for n in repo.letzte_nachrichten(gruppe, 1)
        if n["message_id"] == -900
    ]

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, ausloeser)

    texte = "\n".join(eintraege)
    letzter = kontext.FENSTER_MIN_NACHRICHTEN + 2
    for i in range(letzter):
        assert texte.index(f"Beitrag {i}") < texte.index(f"Beitrag {i + 1}"), (
            f"Beitrag {i} steht nach Beitrag {i + 1} -- nach message_id sortiert?"
        )
    assert eintraege[-1].endswith(f"Beitrag {letzter}"), (
        "die zeitlich juengste Nachricht steht direkt vor dem Ausloeser"
    )
    assert "der Ausloeser" not in texte


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
    """Der 21:50-Fall: der Vormittag ist nicht die Gegenwart.

    Seit dem 06.09.2026 (Auftrag 2) ist die Zeitgrenze **weich**: sie
    schneidet erst, wenn ohnehin mehr als ``FENSTER_MIN_NACHRICHTEN``
    juengere Nachrichten dastehen. Deshalb stehen hier genug frische
    Beitraege -- sonst zeigt der Test nicht die Zeitgrenze, sondern die
    Untergrenze."""
    _lege_an(gruppe, -300, False, "Vormittagszeug von damals", 600)
    for i in range(kontext.FENSTER_MIN_NACHRICHTEN + 2):
        _lege_an(gruppe, 200 + i, False, f"gerade eben gesagt {i}", 10 - i * 0.5)

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, [])

    texte = "\n".join(eintraege)
    assert "gerade eben" in texte
    assert "Vormittagszeug" not in texte


def test_nach_langer_pause_bleiben_die_letzten_nachrichten_im_fenster(gruppe):
    """**Befund C.2 des Audits vom 06.09.2026** -- das Fenster war nach jeder
    Pause ueber 30 Minuten vollstaendig leer.

    Gemessen an der Test-DB: der Ausloeser lag um 23:56, die zwanzig
    Kandidaten zwischen 21:53 und 22:32 -- die 30-Minuten-Grenze schnitt alle
    zwanzig weg, und der Bot antwortete mit Arbeitsstand, Kernpaket und
    Journal, aber **ohne einen einzigen Satz Gespraechsverlauf**.

    Hier als 18-Stunden-Pause (Nacht zwischen zwei Workshoptagen): mindestens
    ``FENSTER_MIN_NACHRICHTEN`` Nachrichten bleiben, und die Pausenzeile aus
    § 6.2 kann ueberhaupt erst erscheinen -- sie konnte es vorher nie, weil
    das, was vor der Pause lag, schon weggefiltert war."""
    for i in range(10):
        _lege_an(gruppe, 300 + i, False, f"gestern Abend gesagt {i}", 18 * 60 + 30 - i)
    _lege_an(gruppe, 400, False, "guten Morgen, weiter gehts", 2)
    ausloeser = [
        dict(n) for n in repo.letzte_nachrichten(gruppe, 1)
        if n["message_id"] == 400
    ]

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, ausloeser)

    nachrichtenzeilen = [z for z in eintraege if not z.startswith("[Pause")]
    assert len(nachrichtenzeilen) >= kontext.FENSTER_MIN_NACHRICHTEN, (
        "das Fenster darf nach einer Pause nie leer sein (Befund C.2)"
    )
    assert any(z.startswith("[Pause: 18 Stunden]") for z in eintraege), (
        f"die Pausenzeile aus § 6.2 fehlt: {eintraege}"
    )
    # Chronologisch: gestern oben, die Pause als letzte Zeile (der naechste
    # Beitrag ist der Ausloeser, und der steht in seinem eigenen Block).
    assert eintraege[-1] == "[Pause: 18 Stunden]"
    texte = "\n".join(eintraege)
    assert texte.index("gestern Abend") < texte.index("[Pause: 18 Stunden]")


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


def test_untergrenze_holt_keine_systemzeilen_und_keine_interview_echos(gruppe):
    """**Birk, 06.09.2026, vor dem Merge**: die neue Untergrenze
    (``FENSTER_MIN_NACHRICHTEN``) greift auf aeltere Nachrichten zurueck --
    sie darf dabei nicht am Systemfilter vorbeigreifen.

    Der Filter sitzt VOR der Auswahl (``_baue_fenster_eintraege`` filtert,
    dann waehlt ``waehle_fenster``), und genau das wird hier zugesichert:
    steht im Rueckgriffsbereich fast nur Systemtext, kommt lieber ein
    kuerzeres Fenster heraus als eines mit Notiert-Zeilen. Zwei Quellen:
    ``_ist_systemzeile`` (Bot-Meldungen) und ``repo.letzte_nachrichten``
    (Interview-Echos, ``typ='transkript'`` -- sonst laese der Bot
    Interviewinhalt als Gruppenabsicht, SPEC § 10.6)."""
    # Alt genug, dass die Zeitgrenze sie alle wegschnitte -- die Untergrenze
    # holt sie zurueck.
    for i, text in enumerate((
        "Bin wieder da. Wir sind bei 4 · Setting & Figuren.",
        "Notiert:\nRahmen: Schulhof",
        "Aufnahme laeuft.",
        "Aufnahme beendet.",
        "Ich schreibe die Szene aus, das dauert eine Minute.",
        "Entfernt: Figur Mira",
    )):
        _lege_an(gruppe, 700 + i, True, text, 300 - i)
    repo.merke_nachricht(
        gruppe, 1, 800, "Birk", 0, repo.TYP_TRANSKRIPT,
        "im Interview gesagt: mir wurde das Kopftuch abgezogen",
        (datetime.fromisoformat("2026-09-06T00:30:00+00:00")
         - timedelta(minutes=290)).isoformat(),
    )
    _lege_an(gruppe, 810, False, "echter Beitrag von damals", 280)
    _lege_an(gruppe, 900, False, "und jetzt weiter", 2)

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, [])
    texte = "\n".join(eintraege)

    for verboten in ("Bin wieder da", "Notiert:", "Aufnahme laeuft",
                     "Aufnahme beendet", "Ich schreibe die Szene aus",
                     "Entfernt:", "Kopftuch abgezogen"):
        assert verboten not in texte, f"{verboten!r} steht im Fenster"
    assert "echter Beitrag von damals" in texte
    assert "und jetzt weiter" in texte


def test_der_ausloeser_ist_der_bezugspunkt_der_zeitgrenze(gruppe):
    """Nicht ``jetzt``: ein Test und ein Nachlauf sollen dieselbe Antwort
    bekommen wie der Livezug.

    Mit genug frischen Beitraegen, damit die **weiche** Zeitgrenze (seit dem
    06.09.2026, Untergrenze ``FENSTER_MIN_NACHRICHTEN``) ueberhaupt
    schneidet."""
    _lege_an(gruppe, 201, False, "zwei Stunden vor dem Ausloeser", 125)
    for i in range(kontext.FENSTER_MIN_NACHRICHTEN + 2):
        _lege_an(gruppe, 210 + i, False, f"zehn Minuten vor dem Ausloeser {i}", 15 - i * 0.5)
    _lege_an(gruppe, 202, False, "der Ausloeser", 5)
    ausloeser = [
        dict(n) for n in repo.letzte_nachrichten(gruppe, 1)
        if n["message_id"] == 202
    ]

    texte = "\n".join(kontext._baue_fenster_eintraege(gruppe, 1, ausloeser))

    assert "zehn Minuten" in texte
    assert "zwei Stunden" not in texte
    assert "der Ausloeser" not in texte, "der Ausloeser steht im eigenen Block"


def test_fenster_ist_in_zeichen_bemessen(gruppe):
    """**SPEC § 6.2 Block 7**, wiederhergestellt am 06.09.2026 (Auftrag 2):
    *"in Token statt Nachrichten bemessen -- im Gruppenchat koennen 'N
    Nachrichten' vier Redebeitraege oder vierzig Sekunden Geplaenkel sein"*.

    Zwanzig sehr lange Beitraege duerfen nicht zwanzigmal in den Prompt: das
    primaere Mass ist ``FENSTER_ZEICHEN``, ``FENSTER_NACHRICHTEN`` ist nur
    noch die Obergrenze darueber."""
    for i in range(kontext.FENSTER_NACHRICHTEN):
        _lege_an(gruppe, 500 + i, False, f"{i} " + "wortreich " * 200, 20 - i * 0.5)

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, [])

    assert len("\n".join(eintraege)) <= kontext.FENSTER_ZEICHEN
    assert len(eintraege) < kontext.FENSTER_NACHRICHTEN, (
        "die Nachrichtenzahl allein haette alle zwanzig durchgelassen"
    )
    assert len(eintraege) >= 1, "ein Fenster ist nie leer"


def test_fenster_ist_nie_leer_auch_wenn_eine_nachricht_das_budget_sprengt(gruppe):
    """Die juengste Nachricht gehoert immer dazu, auch wenn sie allein
    groesser als ``FENSTER_ZEICHEN`` ist -- sonst haette der Bot bei einem
    langen Beitrag gar keinen Verlauf."""
    _lege_an(gruppe, 600, False, "x" * (kontext.FENSTER_ZEICHEN + 5000), 3)

    eintraege = kontext._baue_fenster_eintraege(gruppe, 1, [])

    assert len(eintraege) == 1
