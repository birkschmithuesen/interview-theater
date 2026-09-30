"""E8: in Padua sieht kein Prompt einen Vornamen oder Aufnahmenamen (D6)."""

import pytest

from interview_theater import aufnahme, erkenner, journal, kontext, repo, sprache, workshop
from tests.fixture_sprache import ABSENDER, AUFNAHMENAME, baue_englische_gruppe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _ohne_namen(text: str) -> list[str]:
    return [n for n in (*ABSENDER, AUFNAHMENAME) if n in text]


def test_gespraechsprompt_ohne_namen(conn, einst, padua):
    baue_englische_gruppe(conn)
    ausloeser = repo.letzte_nachrichten(conn, 1)[-2:]
    text = kontext.baue(conn, 1, ausloeser, einst)
    assert _ohne_namen(text) == []
    assert "Member 1:" in text


def test_pseudonyme_sind_stabil_nach_erstem_auftreten(conn, padua):
    baue_englische_gruppe(conn)
    assert kontext.pseudonyme(conn, 1) == {
        "Giulia": "Member 1", "Tomasz": "Member 2", "Amara": "Member 3"}


def test_erkenner_und_journal_ohne_namen(conn, padua):
    baue_englische_gruppe(conn)
    zeilen = repo.unextrahierte(conn, 1)
    assert _ohne_namen(erkenner._baue_nutzertext(conn, 1, zeilen)) == []
    namen = kontext.pseudonyme(conn, 1)
    assert _ohne_namen(journal._ausschnitt_text(zeilen, namen)) == []


def test_wortlaut_zeigt_interviewnummer_statt_aufnahmename(conn, einst, padua):
    baue_englische_gruppe(conn)
    # Material (Verdichtungen, Volltranskripte) steht nur vor den erfindenden
    # Phasen im Prompt (kontext.material_erlaubt) -- in Phase 6 der Fixture
    # waere der Block leer und der Test sagte nichts.
    repo.setze_phase(conn, 1, 3)
    repo.setze_wortlaut_modus(conn, 1, "*")
    text = kontext.baue(conn, 1, repo.letzte_nachrichten(conn, 1)[-1:], einst)
    assert AUFNAHMENAME not in text
    assert "Interview 1" in text


def test_aufnahme_texte_nennen_die_nummer(conn, padua):
    baue_englische_gruppe(conn)
    zeile = [a for a in repo.transkripte(conn, 1) if a["klasse"] == "lang"][0]
    assert aufnahme.anzeigename(conn, zeile, "The interview") == "Interview 1"


class _Tg:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return 9001


def test_wortlaut_nimmt_die_gezeigte_nummer_an(conn, einst, padua):
    """Was der Bot zeigt ("Interview 1"), muss die Gruppe tippen koennen --
    und die Antwort nennt den Aufnahmenamen nicht (sie kommt als Bot-Zeile
    zurueck ins Fenster)."""
    from interview_theater import befehle

    baue_englische_gruppe(conn)
    tg = _Tg()
    befehle.behandle(conn, tg, einst, 1, "/wortlaut Peter", "Giulia")
    assert AUFNAHMENAME not in tg.gesendet[-1] and "Interview 1" in tg.gesendet[-1]
    befehle.behandle(conn, tg, einst, 1, "/wortlaut interview 1", "Giulia")
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == AUFNAHMENAME
    assert AUFNAHMENAME not in tg.gesendet[-1]


def test_dortmund_behaelt_die_vornamen(conn, einst):
    """Bitgleich: ohne Pseudonym-Schalter bleibt der Verlauf, wie er war."""
    baue_englische_gruppe(conn)
    text = kontext.baue(conn, 1, repo.letzte_nachrichten(conn, 1)[-2:], einst)
    assert "Giulia:" in text
    assert kontext.pseudonyme(conn, 1) is None
    zeile = [a for a in repo.transkripte(conn, 1) if a["klasse"] == "lang"][0]
    assert aufnahme.anzeigename(conn, zeile, "Das Interview") == AUFNAHMENAME


# --- Nachbesserung Aufgabe 25 ------------------------------------------------


def test_figur_quelle_nennt_die_nummer_in_der_notiert_zeile(conn, padua):
    """Die Notiert-Zeile ist eine Bot-Nachricht und kommt als Zeile in die
    Fenster des Erkenners und des Journal-Extraktors zurueck."""
    baue_englische_gruppe(conn)
    angewendet = erkenner._wende_eine_an(conn, 1, "figur_quelle_setzen", "Nadia: Interview 1")
    assert angewendet["wert"] == "Nadia: Interview 1"
    meldung = erkenner.baue_meldung([angewendet]) or ""
    assert AUFNAHMENAME not in meldung


def test_figur_quelle_dortmund_wie_vorher(conn):
    baue_englische_gruppe(conn)
    angewendet = erkenner._wende_eine_an(conn, 1, "figur_quelle_setzen", "Nadia: " + AUFNAHMENAME)
    assert angewendet["wert"] == "Nadia: " + AUFNAHMENAME


def _journaltexte(conn):
    return [z[0] for z in conn.execute("SELECT text FROM journal WHERE chat_id = 1")]


def test_entferntes_interview_ohne_aufnahmenamen_im_journal(conn, padua):
    baue_englische_gruppe(conn)
    angewendet = erkenner._wende_eine_an(conn, 1, "entfernen", "interview 1")
    assert angewendet["wert"] == "Interview 1"
    texte = _journaltexte(conn)
    assert "Removed: Interview 1" in texte
    assert not [t for t in texte if AUFNAHMENAME in t]


def test_entferntes_interview_dortmund_wie_vorher(conn):
    baue_englische_gruppe(conn)
    angewendet = erkenner._wende_eine_an(conn, 1, "entfernen", "interview " + AUFNAHMENAME)
    assert angewendet["wert"] == AUFNAHMENAME
    assert "Entfernt: " + AUFNAHMENAME in _journaltexte(conn)


def _lange_aufnahme(conn, sekunden, name):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, sekunden, "lang", "sprache", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "A story about the harbour, " + name)
    repo.setze_aufnahme_name(conn, aufnahme_id, name)
    return aufnahme_id


def test_wortlaut_trifft_nur_die_gezeigte_nummer(conn, einst, padua):
    """Nach einem entfernten Interview heisst eine Aufnahme gespeichert
    "Interview 3", gezeigt aber "Interview 2". "/wortlaut Interview 3" meint
    das, was der Bot als "Interview 3" zeigt -- nicht den gespeicherten Namen
    einer anderen Aufnahme, sonst liest der Prompt das falsche Material mit."""
    from interview_theater import befehle

    baue_englische_gruppe(conn)
    weg = _lange_aufnahme(conn, 20, "Interview 2")
    _lange_aufnahme(conn, 30, "Interview 3")
    gemeint = _lange_aufnahme(conn, 40, "Interview 4")
    repo.entferne_aufnahme(conn, 1, weg)
    assert aufnahme.anzeigename(conn, repo.hole_aufnahme(conn, gemeint), "") == "Interview 3"
    befehle.behandle(conn, _Tg(), einst, 1, "/wortlaut Interview 3", "Giulia")
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "Interview 4"


def test_journal_nutzertext_ohne_vornamen(conn, padua):
    baue_englische_gruppe(conn)
    zeilen = repo.unjournalisierte(conn, 1)
    assert zeilen
    text = journal._baue_nutzertext(conn, 1, zeilen)
    assert _ohne_namen(text) == []
    assert "Member 1:" in text
