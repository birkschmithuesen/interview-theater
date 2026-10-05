"""B4 aus der Phase-4-Analyse: ``arbeitsstand.figuren_anzahl`` befuellen --
und warum ``arbeitsstand.format`` NULL blieb.

Der gemessene Fall (§ 1.1 #1/#24): die Gruppe hat die Figurenzahl **zweimal**
festgelegt. Gelandet ist sie nur als ``journal``-Eintrag #27, art
``entschieden``, 77 Zeichen -- das Feld ``figuren_anzahl`` blieb NULL,
obwohl es existiert. Grund: gesetzt wurde es bis dahin ausschliesslich vom
Knopf (``knoepfe.uebernimm_figurenanzahl``); sagt die Gruppe die Zahl
einfach, gibt es keinen Weg ins Feld.

Der zweite Teil (``format``) ist ein Befund und keine Aenderung -- siehe den
Test unten und ``docs/analyse-phase4-datenverlust-2026-09-06.md``.

Fixtures synthetisch.
"""

import pytest

from interview_theater import db, erkenner, kontext, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


class Umgebung:
    bot_name = "gruppe1"


def _entschieden(conn, text):
    return erkenner.wende_an(
        conn, Umgebung(), 1, [{"art": "entschieden", "wert": text}]
    )


def _anzahl(conn):
    stand = repo.hole_arbeitsstand(conn, 1)
    return stand["figuren_anzahl"] if stand else None


@pytest.mark.parametrize(
    "text, erwartet",
    [
        ("Es sollen 10 bis 12 Figuren werden", "10 bis 12"),
        ("Wir nehmen 8 Figuren", "8"),
        ("Insgesamt zehn Figuren", "10"),
        ("acht bis zehn Figuren insgesamt", "8 bis 10"),
        ("Die Figurenanzahl ist 6", "6"),
    ],
)
def test_eine_gesagte_figurenzahl_landet_im_feld(conn, text, erwartet):
    _entschieden(conn, text)
    assert _anzahl(conn) == erwartet


@pytest.mark.parametrize(
    "text",
    [
        # Teilzahlen sind nicht die Gesamtzahl -- live wurden Haupt- und
        # Nebenfiguren getrennt gezaehlt.
        "Es gibt 2 bis 3 Hauptfiguren",
        "5 Nebenfiguren in der ersten Gruppe",
        # Andere Zahlen im Satz.
        "Wir treffen uns um 10 Uhr",
        "Das Stueck hat 3 Szenen",
        # Eine Zahl ohne Bezug auf Figuren.
        "Die Gruppe ist sich einig",
    ],
)
def test_andere_zahlen_lassen_das_feld_in_ruhe(conn, text):
    _entschieden(conn, text)
    assert _anzahl(conn) is None


def test_der_journaleintrag_bleibt_daneben_stehen(conn):
    """Das Journal ist die Chronik und bleibt es: dort steht, WANN die Gruppe
    sich entschieden hat. Das Feld traegt, WAS gilt."""
    _entschieden(conn, "Es sollen 10 bis 12 Figuren werden")
    assert [z["text"] for z in repo.journal(conn, 1)] == [
        "Es sollen 10 bis 12 Figuren werden"
    ]


def test_die_gruppe_erfaehrt_es(conn):
    """Ein ``entschieden`` bleibt still (SPEC § 4.3) -- eine Aenderung am
    Arbeitsstand nicht. Sonst stuende die Zahl in der Datenbank und die
    Gruppe wuesste nichts davon."""
    wirklich = _entschieden(conn, "Es sollen 10 bis 12 Figuren werden")
    assert erkenner.baue_meldung(wirklich) == "Notiert:\nAnzahl Figuren: 10 bis 12"


def test_dieselbe_zahl_zweimal_meldet_nur_einmal(conn):
    _entschieden(conn, "Es sollen 10 bis 12 Figuren werden")
    zweite = _entschieden(conn, "Bleiben wir bei 10 bis 12 Figuren")
    assert erkenner.baue_meldung(zweite) is None


def test_eine_neue_zahl_ueberschreibt(conn):
    _entschieden(conn, "Es sollen 10 bis 12 Figuren werden")
    _entschieden(conn, "Doch nur 6 Figuren")
    assert _anzahl(conn) == "6"


def test_der_knopfweg_bleibt_unangetastet(conn):
    """Die Gegenprobe: das Feld wird weiterhin auch vom Knopf gesetzt."""
    repo.setze_arbeitsstand(conn, 1, "figuren_anzahl", "4")
    assert _anzahl(conn) == "4"


# --- Warum ``format`` NULL blieb ------------------------------------------


def test_format_steht_nicht_mehr_im_prompt(conn):
    """**Der Befund zu ``arbeitsstand.format``** (B4, zweite Haelfte).

    Die Gruppe hat festgelegt: "nur eine Szene, erste Folge einer Serie".
    Das Feld blieb NULL, und selbst wenn es gesetzt worden waere, haette es
    nichts geaendert -- ``format`` ist seit dem 05.09.2026 abends **kein
    Prompt-Block mehr** (``kontext._baue_arbeitsstand``, docs/agents/entscheidungen.md: "``format``
    und ``hauptkonflikt`` bleiben als Spalten stehen und tragen keine
    Entscheidung mehr").

    Dazu kommt die Bedeutung: ``format_setzen`` meint laut
    ``prompts/erkenner.md`` die **Formen** des Stuecks ("Musical: Dialog,
    Lied, Rap"), nicht seine Struktur. Eine Szenen- oder Folgenzahl passt
    dort gar nicht hinein -- der Erkenner hat richtig nichts geschrieben, es
    fehlte das Fach. Das ist genau die Strukturluecke, und sie wird jetzt von
    der Auffangtabelle geschlossen (Bereich ``struktur``, Korpusfall fl02)."""
    repo.setze_arbeitsstand(conn, 1, "format", "nur eine Szene, erste Folge")
    block = kontext._baue_arbeitsstand(conn, 1)
    assert "erste Folge" not in block


def test_die_strukturfestlegung_kommt_dagegen_an(conn):
    repo.schreibe_festlegung(
        conn, 1, "struktur", "nur eine Szene, die erste Folge einer Serie"
    )
    assert "erste Folge einer Serie" in kontext._baue_festlegungen(conn, 1)
