"""B1/B2 aus der Phase-4-Analyse: eine Menuezeile ist keine Geschichte.

Der gemessene Fall (§ 2.1): der Knopf ``geschichte_speichern`` trug in
seinem ``wert`` die vom Bot angebotene Auswahlzeile mit der **Formabfolge**
ueber drei Szenen. ``szenenfolge.zerlege_geschichte`` fand darin keine
Szenenzeilen, also wurde die ganze Menuezeile als Geschichte gespeichert:
``arbeitsstand.geschichte`` = 113 Zeichen Formabfolge statt der 665 Zeichen
langen, vierteiligen Handlung. Und ``szene.form`` blieb in allen 15 Zeilen
NULL -- die Formentscheidung existierte nur noch als Fliesstext.

Beide Haelften gehoeren zusammen: die Menuezeile abzuweisen, ohne die
Formwahl durchzuschreiben, waere ein neuer, zweiter Verlust.

Fixtures synthetisch.
"""

import pytest

from interview_theater import db, knoepfe, repo, szenenfolge
from tests.test_befehle import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_formen_sind_die_aus_szene():
    """``szenenfolge._FORMEN`` steht als Literal da (``szene`` zieht httpx
    nach). Laufen die beiden Listen auseinander, erkennt der Schutz eine
    Form nicht mehr."""
    from interview_theater import szene

    assert szenenfolge._FORMEN == szene.FORMEN


# --- Der Erkennungsteil ----------------------------------------------------


@pytest.mark.parametrize(
    "text, erwartet",
    [
        # Der Live-Fall: Formen je Szene, mit Nummern.
        (
            "Chor-Dialog-Rap — Szene 1 als Chor, Szene 2 als Dialog, "
            "Szene 3 als Rap",
            {1: "chor", 2: "dialog", 3: "rap"},
        ),
        # Dieselbe Wahl ohne Nummern: die Reihenfolge ist die Zuordnung.
        ("Chor - Dialog - Rap", {1: "chor", 2: "dialog", 3: "rap"}),
        ("Lied / Monolog", {1: "lied", 2: "monolog"}),
        # Gross-/Kleinschreibung egal.
        ("szene 1 dialog, szene 2 lied", {1: "dialog", 2: "lied"}),
    ],
)
def test_formabfolge_wird_erkannt(text, erwartet):
    assert szenenfolge.formabfolge(text) == erwartet


@pytest.mark.parametrize(
    "text",
    [
        # Eine echte Richtung: Bogen und Ende, keine Form.
        "Zwei Cliquen finden am Wasser zusammen\nEnde: offen",
        # Eine einzelne Form ist eine Angabe, keine Abfolge.
        "Die Szene wird ein Dialog am Kanal",
        # Zwei Formen, aber im Fliesstext einer Handlung -- das Stueck darf
        # singen, ohne dass daraus eine Formwahl wird.
        (
            "Sie singen ein Lied am Ufer, und als die anderen kommen, rappt "
            "einer dagegen, bis alle zusammen im Wasser stehen\n"
            "Ende: sie springen gemeinsam"
        ),
        "",
    ],
)
def test_keine_formabfolge(text):
    assert szenenfolge.formabfolge(text) is None


# --- Der Speicherweg -------------------------------------------------------


def _druecke(conn, tg, chat_id, wert):
    """Der Weg des Knopfs ``geschichte_speichern``: ``roh`` ist
    ``"<modus>|<Text der gewaehlten Zeile>"``. ``klm=None`` haelt den
    Szenenfolge-Lauf ab (``starte_geschichte_szenen`` steigt dann aus) --
    hier geht es um das, was gespeichert wird, nicht um den naechsten
    Schritt."""
    knoepfe._speichere_geschichte(conn, tg, None, None, chat_id, knoepfe.TRENNER + wert)


def test_menuezeile_landet_nicht_in_der_geschichte(conn, tg):
    _druecke(
        conn, tg, 1,
        "Chor-Dialog-Rap — Szene 1 als Chor, Szene 2 als Dialog, Szene 3 als Rap",
    )
    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand and stand["geschichte"])


def test_formwahl_wird_in_die_szenen_durchgeschrieben(conn, tg):
    for nummer in (1, 2, 3):
        repo.stelle_szene_sicher(conn, 1, nummer)
    _druecke(
        conn, tg, 1, "Szene 1 als Chor, Szene 2 als Dialog, Szene 3 als Rap",
    )
    formen = {s["nummer"]: s["form"] for s in repo.hole_szenen(conn, 1)}
    assert formen == {1: "chor", 2: "dialog", 3: "rap"}


def test_formwahl_ohne_szenen_wird_zur_festlegung(conn, tg):
    """Im Live-Fall kam die Formwahl **vor** der Szenenfolge -- es gab noch
    keine Zeile, in die sie haette geschrieben werden koennen. Genau dafuer
    gibt es die Auffangtabelle."""
    _druecke(
        conn, tg, 1, "Chor - Dialog - Rap",
    )
    zeilen = repo.festlegungen(conn, 1)
    assert [z["bereich"] for z in zeilen] == ["form"]
    assert "Szene 1: chor" in zeilen[0]["text"]
    assert "Szene 3: rap" in zeilen[0]["text"]


def test_die_gruppe_erfaehrt_dass_die_handlung_noch_fehlt(conn, tg):
    _druecke(
        conn, tg, 1, "Chor - Dialog - Rap",
    )
    assert knoepfe._TEXT_NUR_FORMWAHL in tg.gesendet[-1][1]


def test_eine_echte_richtung_wird_weiter_gespeichert(conn, tg):
    """Die Gegenprobe: der Regelweg darf sich nicht geaendert haben."""
    _druecke(
        conn, tg, 1, "Zwei Cliquen finden am Wasser zusammen\nEnde: offen",
    )
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["geschichte"].startswith("Zwei Cliquen finden am Wasser")
    assert repo.festlegungen(conn, 1) == []


def test_vorfall_haelt_den_abgewiesenen_fall_fest(conn, tg):
    _druecke(
        conn, tg, 1, "Chor - Dialog - Rap",
    )
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")]
    assert "geschichte_war_formwahl" in arten
