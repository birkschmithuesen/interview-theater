"""Karte t_4517d4ad, Aufgabe 5: begriffe_detail auf jedem Weg, der
``arbeitsstand.begriffe`` schreibt (D7)."""

import ast
import json
from pathlib import Path

import pytest

from interview_theater import begriffsboard, db, einstellungen, erkenner, repo, ruecknahme
from interview_theater.knoepfe import basis

CHAT = 1
WURZEL = Path(__file__).resolve().parent.parent / "interview_theater"
BOARD = [
    {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "Wo die Oma kocht.",
     "zitat": "wo meine Oma kocht", "doppelbedeutung": "Ort und Gefuehl", "status": "favorit"},
    {"begriff": "Grenze", "nennungen": 1, "zustimmung": 1, "begruendung": "Im Kopf.",
     "zitat": "", "doppelbedeutung": "", "status": "kandidat"},
]


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _board(conn):
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD), "sovereign", 1)


def _detail(conn):
    roh = repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"]
    return json.loads(roh) if roh else None


class _TG:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return 900 + len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)


# -- der Helfer ---------------------------------------------------------------

def test_schreibe_detail_mit_board(conn):
    _board(conn)
    begriffsboard.schreibe_detail(conn, CHAT, "heimat, Schule")
    assert _detail(conn) == [
        {"begriff": "heimat", "begruendung": "Wo die Oma kocht.", "zitat": "wo meine Oma kocht",
         "doppelbedeutung": "Ort und Gefuehl"},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
    ]


def test_schreibe_detail_findet_begruendung_aus_frueherer_boardzeile(conn):
    """AGG-2: ``schreibe_detail`` las bisher nur die JUENGSTE Boardzeile. Ein
    Begriff, den ein spaeterer Boardlauf nicht mehr nennt (z.B. weil er
    inzwischen verworfen ist und das Modell verworfene Begriffe nicht
    wiederholt), verlor so seine Begruendung -- obwohl die Gruppe ihn
    gespeichert hat. Birk: "der Chat muss immer alles wissen"."""
    _board(conn)  # Heimat/Grenze mit Begruendung, Zeile 1
    repo.lege_begriffsboard_an(
        conn, CHAT,
        json.dumps([{"begriff": "Schule", "nennungen": 1, "zustimmung": 0,
                     "begruendung": "", "zitat": "", "doppelbedeutung": "",
                     "status": "kandidat"}]),
        "sovereign", 2,
    )  # Zeile 2: Heimat kommt hier nicht mehr vor

    begriffsboard.schreibe_detail(conn, CHAT, "Heimat, Schule")

    assert _detail(conn) == [
        {"begriff": "Heimat", "begruendung": "Wo die Oma kocht.",
         "zitat": "wo meine Oma kocht", "doppelbedeutung": "Ort und Gefuehl"},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
    ]


def test_ohne_board_bleibt_die_spalte_unberuehrt(conn):
    """Dortmund hat nie ein Board -- dort entsteht kein begriffe_detail."""
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "A, B")
    begriffsboard.schreibe_detail(conn, CHAT, "A, B")
    assert repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"] is None


def test_leere_begriffe_leeren_das_detail(conn):
    _board(conn)
    begriffsboard.schreibe_detail(conn, CHAT, "Heimat")
    begriffsboard.schreibe_detail(conn, CHAT, None)
    assert repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"] is None


# -- die Wege -----------------------------------------------------------------

def test_erkenner_weg_schreibt_detail(conn, einst):
    _board(conn)
    erkenner.wende_an(conn, einst, CHAT, [{"art": "begriffe_setzen", "wert": "Heimat, Grenze"}])
    assert [d["begruendung"] for d in _detail(conn)] == ["Wo die Oma kocht.", "Im Kopf."]


def test_erkenner_entfernen_leert_detail(conn, einst):
    _board(conn)
    erkenner.wende_an(conn, einst, CHAT, [{"art": "begriffe_setzen", "wert": "Heimat"}])
    erkenner.entferne(conn, CHAT, "begriffe")
    stand = repo.hole_arbeitsstand(conn, CHAT)
    assert stand["begriffe"] is None and stand["begriffe_detail"] is None


def test_knopf_weg_schreibt_detail(conn, einst):
    _board(conn)
    basis._speichere(conn, _TG(), CHAT, "begriffe|Grenze, Heimat", e=einst)
    assert [d["begriff"] for d in _detail(conn)] == ["Grenze", "Heimat"]
    assert _detail(conn)[1]["doppelbedeutung"] == "Ort und Gefuehl"


# -- Ruecknahme ---------------------------------------------------------------

def test_ruecknahme_verfolgt_die_neue_spalte():
    assert "begriffe_detail" in ruecknahme.spalten("arbeitsstand")
    assert "begriffsboard" not in ruecknahme.VERFOLGT


# -- Struktur: kein neuer Schreibweg ohne Haken -------------------------------

#: Jede Stelle in ``interview_theater/``, die ``setze_arbeitsstand`` mit einem
#: NICHT-literalen Feldnamen ruft -- (Datei, innerste Funktion). Kommt eine
#: dazu, schlaegt der Test an: dann pruefen, ob sie ``begriffe`` schreiben
#: kann, und ggf. ``begriffsboard.schreibe_detail`` einhaengen.
VARIABLE_FELDER = {
    ("erkenner.py", "_wende_arbeitsstand_an"),     # Haken
    ("erkenner.py", "_entferne_arbeitsstandfeld"),  # Haken
    ("knoepfe/basis.py", "_schreibe"),             # Haken
    ("befehle.py", "_befehl_stueck"),              # nur rahmen/format
    ("web_schreiben.py", "handler"),               # nur rahmen/geschichte
    ("laengen.py", "setze_faktor"),                # nur laengen_faktor
}
MIT_HAKEN = {
    ("begriffsboard.py", "_schreibe"),
    ("erkenner.py", "_wende_arbeitsstand_an"),
    ("erkenner.py", "_entferne_arbeitsstandfeld"),
    ("knoepfe/basis.py", "_schreibe"),
}


def _aufrufe():
    literal, variabel = [], set()
    for pfad in WURZEL.rglob("*.py"):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        rel = str(pfad.relative_to(WURZEL))

        def besuche(knoten, funktion):
            for kind in ast.iter_child_nodes(knoten):
                name = kind.name if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)) else funktion
                if (isinstance(kind, ast.Call) and isinstance(kind.func, ast.Attribute)
                        and kind.func.attr == "setze_arbeitsstand" and len(kind.args) >= 3):
                    feld = kind.args[2]
                    if isinstance(feld, ast.Constant):
                        literal.append((rel, feld.value))
                    else:
                        variabel.add((rel, funktion))
                besuche(kind, name)

        besuche(baum, None)
    return literal, variabel


#: Literale Schreibwege fuer ``begriffe`` -- nur mit Haken. Seit 05.10.2026
#: (Birk, Auto-Speichern) einer: ``begriffsboard.speichere_automatisch``
#: schreibt die Top 5 des Boards, ``schreibe_detail`` direkt daneben
#: (``test_die_haken_stehen_an_den_drei_stellen`` prueft ``_schreibe``).
#: Seit 05.10.2026 mittags (Brief "p1-bleiben") ein zweiter:
#: ``knoepfe.basis._korrigiere_begriffe`` -- die Begriffs-Korrektur aus dem
#: Gespraechszug in Phase 1, ``schreibe_detail`` ebenfalls direkt daneben
#: (``test_korrektur_schreibt_detail`` unten). Seit Feedbackloop P1-2
#: (Befund S5) ein dritter: ``erkenner._entferne_einen_begriff`` nimmt einen
#: einzelnen Begriff aus der Liste statt das Feld zu leeren
#: (``test_einzelner_begriff_entfernen_schreibt_detail`` unten).
LITERAL_MIT_HAKEN = [
    ("begriffsboard.py", "begriffe"), ("erkenner.py", "begriffe"),
    ("knoepfe/basis.py", "begriffe"),
]


def test_kein_literaler_schreibweg_fuer_begriffe():
    literal, _ = _aufrufe()
    assert sorted(s for s in literal if s[1] == "begriffe") == LITERAL_MIT_HAKEN


def test_korrektur_schreibt_detail(conn, einst):
    _board(conn)
    basis._korrigiere_begriffe(conn, _TG(), CHAT, "Grenze, Heimat", "", e=einst)
    assert [d["begriff"] for d in _detail(conn)] == ["Grenze", "Heimat"]


def test_einzelner_begriff_entfernen_schreibt_detail(conn):
    _board(conn)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Grenze")
    erkenner.entferne(conn, CHAT, "BEGRIFFE Grenze")
    assert [d["begriff"] for d in _detail(conn)] == ["Heimat"]


def test_jeder_variable_schreibweg_ist_geprueft():
    _, variabel = _aufrufe()
    assert variabel == VARIABLE_FELDER


def test_die_haken_stehen_an_den_drei_stellen():
    for datei, funktion in MIT_HAKEN:
        quelle = (WURZEL / datei).read_text(encoding="utf-8")
        baum = ast.parse(quelle)
        treffer = [k for k in ast.walk(baum)
                   if isinstance(k, ast.FunctionDef) and k.name == funktion]
        assert treffer, (datei, funktion)
        assert "schreibe_detail" in ast.unparse(treffer[0]), (datei, funktion)
