"""Karte t_cb2c4678, Aufgabe 2: Schaerfung eines Begriffs -- der Code prueft
``vorheriger_begriff`` gegen das bisherige Board und fuehrt ``vorgaenger``
(D1). Nur erfundenes Material."""

import json

import pytest

from interview_theater import begriffsboard

TRANSKRIPT = (
    "Wir wollen einen Roboter. Nein, einen KI-Roboter, der redet. "
    "Einen sozialen KI-Roboter eigentlich. Und Heimat, Heimat ist wichtig."
)


def _z(begriff, vorher="", **kw):
    zeile = {"begriff": begriff, "nennungen": 1, "zustimmung": 0, "begruendung": "",
             "zitat": "", "doppelbedeutung": "", "status": "kandidat",
             "vorheriger_begriff": vorher}
    zeile.update(kw)
    return zeile


def _bisher(*zeilen):
    """Ein bisheriges Board, wie ``aktuelles`` es liefert (ueber ``lies``)."""
    return begriffsboard.lies(json.dumps(list(zeilen)))


def _ketten(ergebnis):
    return {e["begriff"]: e.get("vorgaenger") for e in ergebnis}


# -- Pruefung des Links (D1) ---------------------------------------------------

def test_gueltiger_link_wird_zur_kette():
    neu = begriffsboard.validiere([_z("KI-Roboter", "Roboter")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": ["Roboter"]}


def test_erfundener_link_wird_verworfen():
    neu = begriffsboard.validiere([_z("KI-Roboter", "Maschine")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": None}


def test_link_auf_einen_noch_stehenden_begriff_wird_verworfen():
    neu = begriffsboard.validiere(
        [_z("KI-Roboter", "Heimat"), _z("Heimat")], TRANSKRIPT,
        bisher=_bisher(_z("Roboter"), _z("Heimat")),
    )
    assert _ketten(neu) == {"KI-Roboter": None, "Heimat": None}


def test_link_auf_sich_selbst_wird_verworfen():
    neu = begriffsboard.validiere([_z("Roboter", "roboter")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"Roboter": None}


@pytest.mark.parametrize("link", [None, 5, ["Roboter"], {"x": 1}, "", "   "])
def test_kaputter_link_ist_kein_link_und_kein_absturz(link):
    neu = begriffsboard.validiere([_z("KI-Roboter", link)], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": None}


def test_ohne_feld_und_ohne_bisher_wie_bisher():
    """Abwaertskompatibel: alte Aufrufer und alte Modellantworten."""
    zeile = _z("Heimat")
    del zeile["vorheriger_begriff"]
    assert begriffsboard.validiere([zeile], TRANSKRIPT) == [
        {"begriff": "Heimat", "nennungen": 1, "zustimmung": 0, "begruendung": "",
         "zitat": "", "doppelbedeutung": "", "status": "kandidat"},
    ]


# -- Kette ueber mehrere Laeufe ----------------------------------------------

def test_kette_ueber_zwei_laeufe_aelteste_zuerst():
    lauf1 = begriffsboard.validiere([_z("Roboter")], TRANSKRIPT)
    lauf2 = begriffsboard.validiere([_z("KI-Roboter", "Roboter")], TRANSKRIPT, bisher=lauf1)
    lauf3 = begriffsboard.validiere([_z("sozialen KI-Roboter", "KI-Roboter")], TRANSKRIPT,
                                    bisher=lauf2)
    assert _ketten(lauf3) == {"sozialen KI-Roboter": ["Roboter", "KI-Roboter"]}


def test_gleicher_schluessel_erbt_die_kette_ohne_dass_das_modell_sie_wiederholt():
    bisher = _bisher(_z("KI-Roboter", vorgaenger=["Roboter"]))
    neu = begriffsboard.validiere([_z("ki-roboter")], TRANSKRIPT, bisher=bisher)
    assert _ketten(neu) == {"ki-roboter": ["Roboter"]}


def test_zusammenfuehren_zweier_alter_zeilen_haengt_die_aufgenommene_an():
    bisher = _bisher(_z("KI-Roboter", vorgaenger=["Roboter"]), _z("Heimat"))
    neu = begriffsboard.validiere([_z("KI-Roboter", "Heimat")], TRANSKRIPT, bisher=bisher)
    assert _ketten(neu) == {"KI-Roboter": ["Roboter", "Heimat"]}


def test_kein_strich_ueber_etwas_das_wieder_als_eigene_zeile_steht():
    """Praezisierung 3 im Plankopf: ein Vorgaenger, der als eigene Zeile
    zurueckkommt, faellt aus jeder Kette -- sonst stuende er zweimal da."""
    bisher = _bisher(_z("KI-Roboter", vorgaenger=["Roboter"]))
    neu = begriffsboard.validiere([_z("KI-Roboter"), _z("Roboter")], TRANSKRIPT, bisher=bisher)
    assert _ketten(neu) == {"KI-Roboter": None, "Roboter": None}


# -- Konstruktion: eine Kette traegt nie mehr als einen Begriff ----------------

def test_kette_traegt_den_wortlaut_des_bisherigen_boards_nicht_den_des_modells():
    neu = begriffsboard.validiere([_z("KI-Roboter", "  ROBOTER ")], TRANSKRIPT,
                                  bisher=_bisher(_z("Roboter")))
    assert _ketten(neu) == {"KI-Roboter": ["Roboter"]}


def test_ein_zitat_als_link_kommt_nie_in_die_kette():
    neu = begriffsboard.validiere(
        [_z("KI-Roboter", "Roboter, und dann sagte sie: ich will nach Hause")],
        TRANSKRIPT, bisher=_bisher(_z("Roboter")),
    )
    assert _ketten(neu) == {"KI-Roboter": None}


def test_eine_vom_modell_mitgeschickte_kette_wird_ignoriert():
    """``vorgaenger`` steht nicht im Schema; kommt es trotzdem (anderer
    Anbieterweg), schreibt die Kette allein der Code."""
    neu = begriffsboard.validiere([_z("Heimat", vorgaenger=["Erfunden", "Auch erfunden"])],
                                  TRANSKRIPT)
    assert _ketten(neu) == {"Heimat": None}


def test_jedes_kettenelement_ist_ein_frueherer_begriff_des_boards():
    """Die Zusage als Eigenschaft: nach beliebig vielen Laeufen ist jedes
    Kettenelement wortgleich ein ``begriff``, der in einem frueheren Lauf
    auf dem Board stand -- nie ein Modelltext."""
    gesehen = set()
    board = []
    laeufe = [
        [_z("Roboter"), _z("Heimat")],
        [_z("KI-Roboter", "Roboter"), _z("Heimat", "Roboter, und mehr")],
        [_z("sozialen KI-Roboter", "KI-Roboter"), _z("Heimat", "Heimat")],
    ]
    for roh in laeufe:
        board = begriffsboard.validiere(roh, TRANSKRIPT, bisher=board)
        for eintrag in board:
            for v in eintrag.get("vorgaenger", []):
                assert v in gesehen, v
                assert begriffsboard._ein_begriff(v) == v
        gesehen |= {e["begriff"] for e in board}


# -- Defensives Lesen (lies / _eintrag) ----------------------------------------

def test_lies_eines_alten_boards_ohne_feld():
    assert begriffsboard.lies('[{"begriff": "Mut"}]') == [
        {"begriff": "Mut", "nennungen": 0, "zustimmung": 0, "begruendung": "",
         "zitat": "", "doppelbedeutung": "", "status": "kandidat"},
    ]


@pytest.mark.parametrize("roh, erwartet", [
    ('"Roboter"', None),                              # keine Liste
    ('null', None),
    ('[5, null, {"a": 1}, "Roboter"]', ["Roboter"]),  # nur Zeichenketten
    ('["Heimat, Grenze", "Roboter"]', ["Roboter"]),   # Listentrenner fliegt
    ('["Roboter", "roboter", "KI-Roboter"]', ["Roboter", "KI-Roboter"]),  # doppelt
    ('["Mut", "Roboter"]', ["Roboter"]),              # der eigene Begriff fliegt
    ('["  Roboter  "]', ["Roboter"]),                 # Whitespace zusammengezogen
])
def test_lies_liest_vorgaenger_defensiv(roh, erwartet):
    eintrag = begriffsboard.lies(f'[{{"begriff": "Mut", "vorgaenger": {roh}}}]')[0]
    assert eintrag.get("vorgaenger") == erwartet


# -- Aufgabe 3: Schema, Nutzertext, Lauf, Prompt -------------------------------

from pathlib import Path  # noqa: E402

from interview_theater import db, einstellungen, repo, workshop  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent
CHAT = 1


def test_schema_verlangt_vorheriger_begriff_als_string():
    zeile = begriffsboard.SCHEMA["properties"]["board"]["items"]
    assert "vorheriger_begriff" in zeile["required"]
    assert zeile["properties"]["vorheriger_begriff"] == {"type": "string"}
    assert "vorgaenger" not in zeile["properties"]


def test_nutzertext_zeigt_dem_modell_die_kette():
    """Sofort gruen (der Dump traegt alle Felder) -- ein Waechter: ohne die
    Kette im Nutzertext spaltete das Modell "Roboter" im naechsten Lauf
    wieder ab, weil das Wort weiter im Transkript steht."""
    board = begriffsboard.lies(json.dumps([_z("KI-Roboter", vorgaenger=["Roboter"])]))
    text = begriffsboard._nutzertext("Roboter. KI-Roboter.", board)
    assert '"vorgaenger": ["Roboter"]' in text
    assert "vorheriger_begriff" not in text


class _KLM:
    def __init__(self):
        self.boards = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        return {"board": self.boards.pop(0)}


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Testgruppe")
    aid = repo.lege_aufnahme_an(conn, CHAT, 10, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund="pause")
    repo.setze_transkript(conn, aid, TRANSKRIPT)
    repo.setze_status(conn, aid, "fertig")
    einst = einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )
    return conn, einst, aid


def test_lauf_fuehrt_die_kette_ueber_drei_laeufe(lauf):
    conn, einst, aid = lauf
    klm = _KLM()
    klm.boards = [
        [_z("Roboter")],
        [_z("KI-Roboter", "Roboter")],
        [_z("sozialen KI-Roboter", "KI-Roboter")],
    ]
    for _ in range(3):
        begriffsboard._lauf_einmal(conn, klm, einst, CHAT, aid)
    assert _ketten(begriffsboard.aktuelles(conn, CHAT)) == {
        "sozialen KI-Roboter": ["Roboter", "KI-Roboter"],
    }


@pytest.mark.parametrize("pfad", [
    "interview_theater/prompts/begriffsboard.md",
    "interview_theater/sprachen/en/prompts/begriffsboard.md",
])
def test_prompt_nennt_feld_und_kettenregel(pfad):
    text = (WURZEL / pfad).read_text(encoding="utf-8")
    assert "vorheriger_begriff" in text
    assert "``vorgaenger``" in text
