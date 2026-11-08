"""Sichtbarkeit der Phasen-Summaries fuer die Regie (Karte t_1bc96848, Teil
3): die Werkbank (Padua, read-only) zeigt je Phase das in der Tabelle
``phasen_summary`` gespeicherte, bereits erzeugte Summary -- reine Anzeige,
kein neuer Modellaufruf. Ohne gespeichertes Summary bleibt der Abschnitt
ganz weg (derselbe Grundsatz wie Sprechanteile/Dramaturgie: eine leere Liste
heisst "kein Abschnitt", nicht "leerer Abschnitt").

Erscheint im Nutzerablauf: in der Werkbank (Arbeitsstand-Tab) der
Gruppenseite -- unter dem Journal und der Internet-Recherche, als letzter
zugeklappter Abschnitt. Sichtbar nur unter dem Padua-Profil
(``[web] workbench_bearbeitbar = false``), das dieselbe Funktion
(``werkbank_koerper`` statt ``gruppe_koerper``) ohnehin allein fuer Padua
waehlt. Wird NICHT durch einen Phasenwechsel oder eine neue Chatnachricht
verdeckt: die Seite laedt den Abschnitt bei jedem Aufruf neu aus der
Datenbank, er bleibt bestehen bis zum naechsten (additiven) Summary derselben
Phase."""

import pytest

from interview_theater import db, repo, sprache, web, web_daten, workshop
from tests.fixture_sprache import baue_englische_gruppe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _daten(tmp_path):
    pfad = str(tmp_path / "w.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()


def test_phasen_summary_steht_in_der_werkbank_wenn_gespeichert(tmp_path, padua):
    pfad = str(tmp_path / "w.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    repo.speichere_phasen_summary(conn, 1, 1, "The group agreed on home as the theme.")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()
    seite = web.gruppe_koerper(daten, None, token)
    assert '<details class="wb-phasen-summary">' in seite
    assert "The group agreed on home as the theme." in seite
    assert web.T._UEBERSCHRIFT_PHASEN_SUMMARY in seite


def test_phasen_summary_abschnitt_fehlt_ohne_gespeichertes_summary(tmp_path, padua):
    daten = _daten(tmp_path)
    seite = web.gruppe_koerper(daten, None, None)
    assert '<details class="wb-phasen-summary">' not in seite
    assert daten["phasen_summaries"] == []


def test_phasen_summary_nur_die_juengste_je_phase(tmp_path, padua):
    pfad = str(tmp_path / "w.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    repo.speichere_phasen_summary(conn, 1, 1, "erste Fassung")
    repo.speichere_phasen_summary(conn, 1, 1, "zweite, neuere Fassung")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()
    seite = web.gruppe_koerper(daten, None, token)
    assert "zweite, neuere Fassung" in seite
    assert "erste Fassung" not in seite


def test_phasen_summary_steht_unter_journal_und_recherche(tmp_path, padua):
    pfad = str(tmp_path / "w.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_englische_gruppe(conn)
    repo.setze_gruppe_kanal(conn, 1, "web")
    repo.speichere_phasen_summary(conn, 1, 2, "Questions settled.")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()
    seite = web.gruppe_koerper(daten, None, token)
    assert (seite.index('class="wb-journal"') < seite.index('class="wb-recherche"')
            < seite.index('class="wb-phasen-summary"'))


def test_minimales_daten_dict_ohne_phasen_summaries_stuerzt_nicht(padua):
    """``werkbank_koerper`` darf ohne den Schluessel ``phasen_summaries``
    nicht abstuerzen -- aeltere Aufrufer (Tests, Zwischenstand) kennen ihn
    noch nicht."""
    daten = {
        "titel": "Test group", "chat_id": 1, "web_token": None, "kanal": "web",
        "arbeitsstand": {}, "journal": [], "interviews": [],
        "figuren": [], "szenen": [], "festlegungen": [], "fragen_auswertung": None,
        "sprechanteile": None, "dramaturgie": None,
        "werkbank": {"phasen": [], "begriffe_detail": [], "szenen_anzahl": None},
    }
    seite = web.werkbank_koerper(daten)
    assert '<details class="wb-phasen-summary">' not in seite
