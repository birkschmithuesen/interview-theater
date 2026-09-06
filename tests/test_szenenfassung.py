"""Die Tabelle ``szenenfassung`` (07.09.2026): eine Zeile je Fassung.

Gemessen wird, was der Auftrag zusagt: nur-anhaengend, je Szene fortlaufende
Nummer, idempotent, rueckwaertskompatibel -- eine Datenbank aus der Zeit davor
laeuft durch ``db.initialisiere`` und bekommt die Tabelle, ohne dass eine
bestehende Szene etwas verliert.

Alle Texte sind erfunden.
"""

import sqlite3

import pytest

from interview_theater import db, repo, szenenfolge


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Die Ankommenden")
    return c


def _szene(conn, nummer=1):
    return repo.stelle_szene_sicher(conn, 1, nummer)


# --- Schema ----------------------------------------------------------------


def test_die_tabelle_wird_angelegt(conn):
    tabellen = {
        z["name"]
        for z in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }

    assert "szenenfassung" in tabellen


def test_initialisieren_ist_idempotent(conn):
    szene_id = _szene(conn)
    repo.lege_szenenfassung_an(conn, 1, szene_id, "MIRA: Da bist du.", "Dialog")

    db.initialisiere(conn)

    assert len(repo.szenenfassungen(conn, szene_id)) == 1


def test_alte_datenbank_ohne_die_tabelle_wird_nachgeruestet(tmp_path):
    """Rueckwaertskompatibel: eine Datei aus der Zeit davor bekommt die
    Tabelle beim naechsten Start, die bestehende Szene bleibt stehen."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    db.initialisiere(alt)
    repo.sichere_gruppe(alt, 1, "gruppe1", "Alt")
    szene_id = repo.stelle_szene_sicher(alt, 1, 1)
    repo.aktualisiere_szene(alt, szene_id, "Am Steg", None, "Alter Text", None)
    alt.execute("DROP TABLE szenenfassung")
    alt.commit()
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)

    assert repo.szenenfassungen(neu, szene_id) == []
    assert repo.hole_szenen(neu, 1)[0]["volltext"] == "Alter Text"


def test_die_tabelle_haengt_an_der_loeschzusage(conn):
    assert "szenenfassung" in db.TABELLEN_MIT_CHAT_ID

    szene_id = _szene(conn)
    repo.lege_szenenfassung_an(conn, 1, szene_id, "MIRA: Da bist du.")

    db.loesche_gruppe(conn, 1)

    assert repo.szenenfassungen(conn, szene_id) == []


# --- Anhaengen -------------------------------------------------------------


def test_nummern_laufen_je_szene_fortlaufend(conn):
    eins = _szene(conn, 1)
    zwei = _szene(conn, 2)

    assert repo.lege_szenenfassung_an(conn, 1, eins, "erste") == 1
    assert repo.lege_szenenfassung_an(conn, 1, eins, "zweite") == 2
    # Die zweite Szene faengt wieder bei 1 an.
    assert repo.lege_szenenfassung_an(conn, 1, zwei, "erste dort") == 1
    assert repo.lege_szenenfassung_an(conn, 1, eins, "dritte") == 3


def test_derselbe_text_zweimal_legt_keine_zweite_fassung_an(conn):
    szene_id = _szene(conn)

    assert repo.lege_szenenfassung_an(conn, 1, szene_id, "MIRA: Da bist du.") == 1
    assert repo.lege_szenenfassung_an(conn, 1, szene_id, "MIRA: Da bist du. ") == 1

    assert len(repo.szenenfassungen(conn, szene_id)) == 1


def test_leerer_text_legt_nichts_an(conn):
    szene_id = _szene(conn)

    assert repo.lege_szenenfassung_an(conn, 1, szene_id, "   ") == 0
    assert repo.lege_szenenfassung_an(conn, 1, szene_id, None) == 0
    assert repo.szenenfassungen(conn, szene_id) == []


def test_beschriftung_und_reihenfolge(conn):
    szene_id = _szene(conn)
    repo.lege_szenenfassung_an(conn, 1, szene_id, "erste", "Dialog")
    repo.lege_szenenfassung_an(conn, 1, szene_id, "zweite", "Rap · Schlagabtausch")

    zeilen = repo.szenenfassungen(conn, szene_id)

    assert [z["nummer"] for z in zeilen] == [1, 2]
    assert [z["beschriftung"] for z in zeilen] == ["Dialog", "Rap · Schlagabtausch"]
    assert [z["volltext"] for z in zeilen] == ["erste", "zweite"]
    assert all(z["erstellt_am"] for z in zeilen)


def test_es_gibt_keinen_aenderungs_oder_loeschweg():
    """Nur-anhaengend, wie das Journal: kein aktualisiere_szenenfassung, kein
    DELETE FROM szenenfassung."""
    from pathlib import Path

    quelltext = Path(repo.__file__).read_text(encoding="utf-8")

    assert "aktualisiere_szenenfassung" not in quelltext
    assert "DELETE FROM szenenfassung" not in quelltext
    assert "UPDATE szenenfassung" not in quelltext


# --- Der Weg dahin ---------------------------------------------------------


def test_hebe_fassung_auf_sichert_auch_eine_alte_szene(conn):
    """Eine Szene, deren Volltext vor dieser Aenderung entstanden ist, hat
    noch keine Zeile -- 'Neu schreiben' legt sie nach."""
    szene_id = _szene(conn)
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", None, "Erste Fassung", None)
    conn.execute("DELETE FROM szenenfassung")
    conn.commit()

    repo.hebe_fassung_auf(conn, szene_id)

    zeilen = repo.szenenfassungen(conn, szene_id)
    assert [z["volltext"] for z in zeilen] == ["Erste Fassung"]
    # Das alte Feld bleibt daneben stehen.
    assert "Erste Fassung" in repo.hole_szenen(conn, 1)[0]["fruehere_fassungen"]


def test_hebe_fassung_auf_verdoppelt_eine_vorhandene_zeile_nicht(conn):
    szene_id = _szene(conn)
    repo.lege_szenenfassung_an(conn, 1, szene_id, "Erste Fassung", "Dialog")
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", None, "Erste Fassung", None)

    repo.hebe_fassung_auf(conn, szene_id)

    assert len(repo.szenenfassungen(conn, szene_id)) == 1


class _LLMAttrappe:
    def __init__(self, volltext):
        self._volltext = volltext

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        return (
            "TITEL: Am Bahnhof\n"
            "KURZ: Maria kommt an.\n"
            "ZUSAMMENFASSUNG: Maria wartet, Elif kommt dazu.\n"
            "ANDERS GEMACHT: nichts\n"
            f"\n{self._volltext}"
        )


class _TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self._naechste = 9000

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._naechste += 1
        return self._naechste


def _bereit(conn):
    """Eine Szene, die die Sperre aus ``szene.PFLICHTFELDER`` passieren
    laesst -- wie in ``tests/test_szene.py``."""
    from interview_theater import phasen, szene as szene_modul

    szene_modul._sperren.clear()
    phasen.setze(conn, 1, 7, "befehl")
    repo.setze_figur(conn, 1, "Mira", "Naeherin")
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    repo.setze_sprachprofil(conn, figur_id, "Kurze Saetze.", ["Nur ein Koffer."])
    repo.setze_arbeitsstand(conn, 1, "format", "Sprechtheater: Dialog")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Bahnhof, ein Abend")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Bahnhof")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Mira kommt an")
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    return szene_id


def test_jeder_szenenlauf_haengt_eine_fassung_an(conn, einst):
    from interview_theater import szene as szene_modul

    szene_id = _bereit(conn)
    tg = _TelegramAttrappe()

    szene_modul.schreibe(conn, tg, _LLMAttrappe("MIRA: Da."), einst, 1, "Szene 1")
    szene_modul.schreibe(conn, tg, _LLMAttrappe("MIRA: Immer noch da."), einst, 1, "Szene 1")

    zeilen = repo.szenenfassungen(conn, szene_id)
    assert [z["nummer"] for z in zeilen] == [1, 2]
    assert [z["volltext"] for z in zeilen] == ["MIRA: Da.", "MIRA: Immer noch da."]
    # Die Beschriftung sagt, was die Fassung von der naechsten unterscheidet.
    assert zeilen[0]["beschriftung"] == "Dialog"
    # Und der aktuelle Volltext ist die letzte Fassung.
    assert repo.hole_szene(conn, szene_id)["volltext"] == "MIRA: Immer noch da."


def test_der_prosalauf_legt_keine_fassung_an(conn, einst):
    """Phase 6 schreibt eine Geschichte nach ``szene.prosa``, keinen
    Theatertext -- die Fassungen zaehlen den Buehnentext."""
    from interview_theater import phasen, szene as szene_modul

    szene_id = _bereit(conn)
    phasen.setze(conn, 1, 5, "befehl")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Sie bleibt, er geht.")
    szene_modul._sperren.clear()

    szene_modul.schreibe(conn, _TelegramAttrappe(), _LLMAttrappe("Sie stand da."),
                         einst, 1, "Szene 1")

    assert repo.szenenfassungen(conn, szene_id) == []
    assert repo.hole_szene(conn, szene_id)["prosa"] == "Sie stand da."


def test_beschriftung_aus_form_und_stil():
    assert szenenfolge.fassungsbeschriftung("Dialog", "herkules") == "Dialog · herkules"
    assert szenenfolge.fassungsbeschriftung("Dialog", None) == "Dialog"
    assert szenenfolge.fassungsbeschriftung(None, "  ") == ""
