"""Padua Phase 2, Live-Test-Fixes (Birk, 05.10.2026, Gruppe 2).

K: zwei nacheinander bestaetigte Fragen -- im Feld ``fragen`` stand nur die
zweite. L: die Diskussionsverdichtung lief, gespeichert wurde nichts. M: kein
CoThinker in Phase 2, stattdessen "Still missing: term (x/3)" nach jeder
Bestaetigung im Chat.

Kein Netz, kein Modell: Telegram ist eine Attrappe, Modellaufrufe liefern
vorbereitete Antworten. Erfundenes Material."""

import json
import re
import sqlite3

import pytest

from interview_theater import (
    diskussion, erkenner, kontext, knoepfe, phasen, repo, roadmap, sprache,
    web, web_daten, web_vereint, workshop,
)

from test_knoepfe import _druck
from test_undo_knopf import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


class _ErkennerAttrappe:
    def __init__(self, aenderungen):
        self.aenderungen = aenderungen

    def schema(self, *a, **k):
        return {"aenderungen": self.aenderungen}


def _bestaetige(conn, tg, einst, message_id, wert):
    repo.merke_nachricht(
        conn, 1, message_id, "Ada", 0, "text", "yes, take that one", repo._jetzt(),
    )
    erkenner.laufe(_ErkennerAttrappe([{"art": "fragen_setzen", "wert": wert}]),
                   tg, conn, einst, 1)


ERSTE = "Living on mars: Would you like to live on Mars?"
ZWEITE = "robots: Would you like to have a robot that serves you?"


# --- K: Fragen sammeln statt ueberschreiben ---------------------------------


def test_k_zwei_bestaetigungen_nacheinander_stehen_beide_in_fragen(conn, tg, einst, padua):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Living on mars, robots")
    phasen.setze(conn, 1, 2, "test")

    _bestaetige(conn, tg, einst, 41, ERSTE)
    _bestaetige(conn, tg, einst, 42, ZWEITE)

    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == f"{ERSTE}\n{ZWEITE}"
    # Die 📌-Zeile nennt nur die eine neue Frage, nicht die ganze Liste.
    letzte = tg.knoepfe[-1][1]
    assert ZWEITE in letzte and ERSTE not in letzte


def test_k_dublette_wird_nicht_zweimal_angehaengt(conn, tg, einst, padua):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Living on mars, robots")
    phasen.setze(conn, 1, 2, "test")

    _bestaetige(conn, tg, einst, 41, ERSTE)
    _bestaetige(conn, tg, einst, 42, "  " + ERSTE.upper() + "\n" + ZWEITE)

    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == f"{ERSTE}\n{ZWEITE}"


def test_k_undo_nimmt_genau_die_letzte_frage_zurueck(conn, tg, einst, padua):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Living on mars, robots")
    phasen.setze(conn, 1, 2, "test")
    _bestaetige(conn, tg, einst, 41, ERSTE)
    _bestaetige(conn, tg, einst, 42, ZWEITE)

    undo = next(d for b, d in tg.knoepfe[-1][2] if b == "Undo")
    assert knoepfe.behandle(conn, tg, None, einst, _druck(undo)) is True

    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == ERSTE


def test_k_ohne_padua_ueberschreibt_der_erkenner_wie_bisher(conn, tg, einst):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Living on mars, robots")
    phasen.setze(conn, 1, 2, "test")

    _bestaetige(conn, tg, einst, 41, ERSTE)
    _bestaetige(conn, tg, einst, 42, ZWEITE)

    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == ZWEITE


# --- L: Diskussionsverdichtung still erzeugen, in Phase 2 einspeisen --------


class _VerdichterKLM:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        return {"antwort": self.antwort}


def _diskussionssegment(conn, transkript):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 9, "kurz", "sprache", diskussion=True)
    conn.execute(
        "UPDATE aufnahme SET transkript = ?, status = 'fertig' WHERE id = ?",
        (transkript, aufnahme_id),
    )
    conn.commit()


def _warte_auf_lauf():
    import time

    ende = time.monotonic() + 5
    while time.monotonic() < ende:
        if diskussion.versuche_start(1):
            diskussion.beende(1)
            return
        time.sleep(0.01)
    raise AssertionError("Verdichtungslauf nie fertig")


TRANSKRIPT = (
    "we said robots could do the boring jobs but then who pays us. "
    "and mars is cold, nobody wants to live there really"
)


def test_l_ein_verhoertes_zitat_wirft_die_verdichtung_nicht_mehr_weg(conn, einst, monkeypatch):
    """Live: ein Absatz = eine Zeile; ein einziges unbestaetigtes Zitat warf
    bis 05.10.2026 die ganze Verdichtung weg (0 Zeilen gespeichert). Jetzt
    faellt nur das Zitat, die Aussage bleibt."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    _diskussionssegment(conn, TRANSKRIPT)
    klm = _VerdichterKLM(
        'The discussion asked who earns money once robots work '
        '("who pays us") and doubted life on Mars '
        '("nobody would ever move to Mars").'
    )

    diskussion.starte(conn, None, klm, einst, 1)
    _warte_auf_lauf()

    text = repo.diskussion_verdichtung_text(conn, 1)
    assert text is not None
    assert '"who pays us"' in text
    assert "nobody would ever move" not in text
    assert "doubted life on Mars" in text
    assert conn.execute(
        "SELECT COUNT(*) FROM vorfall WHERE art = 'diskussion_verdichtung_leer'"
    ).fetchone()[0] == 0


def test_l_bleibt_nichts_uebrig_steht_ein_vorfall_ohne_inhalt(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    _diskussionssegment(conn, TRANSKRIPT)
    klm = _VerdichterKLM('"completely invented sentence here"')

    diskussion.starte(conn, None, klm, einst, 1)
    _warte_auf_lauf()

    assert repo.diskussion_verdichtung_text(conn, 1) is None
    vorfall = conn.execute(
        "SELECT text FROM vorfall WHERE art = 'diskussion_verdichtung_leer'"
    ).fetchone()
    assert vorfall is not None
    # Nur Zahlen, nie Inhalt der Gruppe.
    assert "invented" not in vorfall[0] and "robots" not in vorfall[0]


def test_l_typografische_anfuehrungszeichen_werden_auch_geprueft():
    text, zahlen = diskussion._filtere(
        "They said “who pays us” and “a sentence nobody said” in the end.",
        TRANSKRIPT,
    )
    assert "“who pays us”" in text
    assert "nobody said" not in text
    assert zahlen["zitate"] == 2 and zahlen["zitate_verworfen"] == 1


def test_l_phase2_prompt_enthaelt_verdichtung_und_begriffs_begruendung(
    conn, tg, einst, padua,
):
    """Sobald eine Verdichtung existiert, steht sie im Gespraechsprompt der
    Phase 2; und Begriffe, die gespeichert werden, bringen ihre Begruendung
    vom Board mit (``begriffe_detail``)."""
    repo.lege_begriffsboard_an(conn, 1, json.dumps([
        {"begriff": "robots", "nennungen": 3, "zustimmung": 2,
         "begruendung": "who does the boring jobs", "zitat": "", "doppelbedeutung": "",
         "status": "favorit"},
    ]), "sovereign", 0)
    phasen.setze(conn, 1, 2, "test")
    repo.merke_nachricht(conn, 1, 40, "Ada", 0, "text", "our terms: robots", repo._jetzt())
    erkenner.laufe(
        _ErkennerAttrappe([{"art": "begriffe_setzen", "wert": "robots"}]), tg, conn, einst, 1,
    )
    detail = repo.hole_arbeitsstand(conn, 1)["begriffe_detail"] or ""
    assert "who does the boring jobs" in detail
    repo.merke_diskussion_verdichtung(conn, 1, "The group doubted life on Mars.", "claude")

    repo.merke_nachricht(conn, 1, 41, "Ada", 0, "text", "let's write questions", repo._jetzt())
    prompt = kontext.baue(conn, 1, [repo.hole_nachricht(conn, 1, 41)], einst)

    assert kontext.T.DISKUSSION_KOPF in prompt
    assert "The group doubted life on Mars." in prompt
    assert kontext.T.BEGRIFFE_DETAIL_KOPF in prompt
    assert "who does the boring jobs" in prompt


def test_l_werkbank_zeigt_keine_diskussionszeile(tmp_path, monkeypatch):
    from interview_theater import db

    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad = str(tmp_path / "w.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    repo.setze_phase(c, 1, 1)
    repo.merke_diskussion_verdichtung(c, 1, "Etwas.", "claude")
    c.commit()
    ro = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row

    eins = web_daten.werkbank(ro, 1)["phasen"][0]
    assert [z["kennung"] for z in eins["zeilen"]] == ["begriffe"]


# --- M: CoThinker in Phase 2 ------------------------------------------------


def test_m_fragenuebersicht_je_begriff_ohne_soll_zahl():
    stand = {
        "begriffe": "Living on mars, robots, Family",
        "fragen": ERSTE,
        "fragen_eigene_vorschlag": (
            f"{ERSTE}\nrobots: Who repairs the robot?\nCats: Do you like cats?"
        ),
        "fragen_herkunft_final": None,
    }
    uebersicht = roadmap.fragenuebersicht(stand)

    assert uebersicht == [
        {"begriff": "Living on mars", "fragen": ["Would you like to live on Mars?"]},
        {"begriff": "robots", "fragen": ["Who repairs the robot?"]},
        {"begriff": "Family", "fragen": []},
    ]


def test_m_nach_der_entscheidung_zaehlt_nur_noch_fragen():
    stand = {
        "begriffe": "robots",
        "fragen": "robots: Kept question?",
        "fragen_eigene_vorschlag": "robots: Discarded question?",
        "fragen_herkunft_final": "eigen",
    }
    assert roadmap.fragenuebersicht(stand) == [
        {"begriff": "robots", "fragen": ["Kept question?"]},
    ]


def test_m_buehne_zeigt_in_phase_2_die_uebersicht_und_markiert_offene_begriffe(padua):
    html_ = web._buehne_html({
        "fragenuebersicht_zeigen": True,
        "fragenuebersicht": [
            {"begriff": "robots", "fragen": ["Who repairs <the> robot?"]},
            {"begriff": "Family", "fragen": []},
        ],
    })
    assert 'data-ansicht="fragen"' in html_
    assert re.search(r'<li data-begriff="robots">', html_)
    assert re.search(r'<li data-begriff="Family" data-offen="1">', html_)
    assert "Who repairs &lt;the&gt; robot?" in html_
    assert "no question yet" in html_
    assert re.search(r"\d+\s*/\s*3", html_) is None
    assert "style=" not in html_ and re.search(r"\son\w+=", html_) is None


def test_m_gruppe_nach_token_liefert_die_uebersicht_nur_in_phase_2(tmp_path, monkeypatch):
    from interview_theater import db

    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad = str(tmp_path / "m.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    repo.setze_arbeitsstand(c, 1, "begriffe", "robots, Family")
    repo.setze_arbeitsstand(c, 1, "fragen", ZWEITE)
    token = repo.stelle_web_token_sicher(c, 1)
    repo.setze_phase(c, 1, 2)
    c.commit()
    ro = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row

    daten = web_daten.gruppe_nach_token(ro, token)
    assert daten["fragenuebersicht_zeigen"] is True
    assert daten["fragenuebersicht"][1] == {"begriff": "Family", "fragen": []}

    repo.setze_phase(c, 1, 3)
    c.commit()
    assert web_daten.gruppe_nach_token(ro, token)["fragenuebersicht_zeigen"] is False


def test_m_cothinker_tab_ist_in_phase_2_sichtbar(tmp_path, monkeypatch):
    import threading

    from interview_theater import db
    from test_begriffsboard_web import _hole

    gruppe = 7_000_000_000_001
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad = str(tmp_path / "t.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, gruppe, "gruppe2", "Gruppe 2")
    repo.setze_gruppe_kanal(c, gruppe, "web")
    repo.setze_arbeitsstand(c, gruppe, "begriffe", "robots, Family")
    repo.setze_arbeitsstand(c, gruppe, "fragen", ZWEITE)
    repo.setze_phase(c, gruppe, 2)
    token = repo.stelle_web_token_sicher(c, gruppe)
    c.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        basis = f"http://127.0.0.1:{dienst.server_address[1]}"
        _status, seite, _kopf = _hole(f"{basis}/g/{token}")
        assert re.search(r'<button[^>]*data-tab="buehne"(?![^>]*hidden)', seite)
        _status, teil, _kopf = _hole(f"{basis}/g/{token}/teil/buehne")
        assert 'data-begriff="robots"' in teil
        assert re.search(r'data-begriff="Family" data-offen="1"', teil)
    finally:
        dienst.shutdown()


def test_m_js_laesst_den_cothinker_in_phase_2_zu():
    js = web_vereint._VEREINT_JS
    assert "(p === '1' || p === '2') && rm.dataset.begriffsboard === '1'" in js


def test_m_kein_still_missing_mehr_im_chat(conn, tg, padua, monkeypatch):
    from interview_theater.knoepfe import fragen

    monkeypatch.setattr(fragen, "versuche_gegenueberstellung", lambda *a, **k: None)
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Living on mars, robots")
    phasen.setze(conn, 1, 2, "test")

    for _ in range(2):
        knoepfe.sende_mit_speicherleiste(
            conn, tg, 1,
            "Nice one, I've put it down.\n\nVORSCHLAG EIGENE FRAGEN:\n" + ZWEITE,
        )

    texte = tg.texte
    assert texte == ["Nice one, I've put it down."] * 2
    assert not any("Still missing" in t for t in texte)
    assert not any(re.search(r"\(\d+/\d+\)", t) for t in texte)


def test_m_padua_prompt_nennt_keine_soll_zahl_je_begriff(padua):
    from interview_theater import anweisungen

    anweisungen._CACHE.clear()
    text = " ".join(anweisungen.hole("phasen/2").split())
    anweisungen._CACHE.clear()
    assert "keep only the best or most recent three" not in text
    assert "before every term has three questions" not in text
    assert "reaches three per term" not in text
    assert "Own questions done." in text
