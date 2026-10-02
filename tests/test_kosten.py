"""Die Kostenrechnung: Preise, Tagesgrenze, unbekanntes Modell.

Der Ausgangspunkt ist ein Befund, kein Wunsch: die Tabelle ``aufruf`` trug
bis zum 30.09.2026 weder Modell noch Kosten (db.py:705-717), und Whisper
buchte gar nicht. Eine Kostenrechnung im Nachhinein war deshalb unmoeglich --
aus ``art`` folgt das Modell nicht, ``LLM.schema`` waehlt es je Aufruf.
"""

import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from interview_theater import db, kosten, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Die Ankommenden")
    yield verbindung
    verbindung.close()


# -- Die Preistabelle -----------------------------------------------------


def test_die_preise_stehen_im_paket_und_im_skript_gleich():
    """Zwei Tabellen waeren zwei Wahrheiten: der Bericht rechnete mit
    anderen Preisen als der Deckel."""
    from scripts import pruefe_prompts

    assert pruefe_prompts.PREISE_CHF_JE_MIO_TOKEN is kosten.PREISE_CHF_JE_MIO_TOKEN


def test_kosten_eines_bekannten_modells():
    # gemma: 0.20 Eingabe, 0.40 Ausgabe je Million.
    assert kosten.kosten_chf("google/gemma-4-31B-it", 1_000_000, 0) == pytest.approx(0.20)
    assert kosten.kosten_chf("google/gemma-4-31B-it", 0, 1_000_000) == pytest.approx(0.40)
    assert kosten.kosten_chf("google/gemma-4-31B-it", 0, 0) == 0.0


def test_unbekanntes_modell_gibt_none():
    """Unveraendert gegenueber scripts/pruefe_prompts -- fuer einen BERICHT
    ist 'lieber keine Zahl als eine erfundene' richtig."""
    assert kosten.kosten_chf("gibtsnicht/modell-9", 1000, 1000) is None


def test_teuerster_preis_ist_das_maximum_je_richtung():
    eingabe, ausgabe = kosten.teuerster_preis()
    assert eingabe == max(p[0] for p in kosten.PREISE_CHF_JE_MIO_TOKEN.values())
    assert ausgabe == max(p[1] for p in kosten.PREISE_CHF_JE_MIO_TOKEN.values())


def test_unbekanntes_modell_wird_teuerst_gerechnet_und_vermerkt(conn):
    """Fuer einen DECKEL ist None/0 die falsche Richtung: dann umgeht ein
    Modellwechsel die Grenze, ohne dass es jemand merkt."""
    eingabe, ausgabe = kosten.teuerster_preis()
    wert = kosten.kosten_oder_teuerster(
        conn, CHAT, "gruppe1", "gibtsnicht/modell-9", 1_000_000, 1_000_000
    )
    assert wert == pytest.approx(eingabe + ausgabe)
    zeilen = conn.execute(
        "SELECT art, detail FROM vorfall WHERE chat_id = ?", (CHAT,)
    ).fetchall()
    assert [z["art"] for z in zeilen] == ["kosten_modell_unbekannt"]
    assert "gibtsnicht/modell-9" in zeilen[0]["detail"]


def test_unbekanntes_modell_vermerkt_nur_einmal_am_tag_bucht_aber_jedes_mal(conn):
    """Ein Vorfall je Gruppe und Tag, wie beim Deckel: sonst schriebe jeder
    Gespraechszug mit dem neuen Modell eine Zeile und faerbte das Dashboard
    rot, ohne mehr zu sagen als die erste."""
    eingabe, ausgabe = kosten.teuerster_preis()
    for _ in range(3):
        wert = kosten.kosten_oder_teuerster(
            conn, CHAT, "gruppe1", "gibtsnicht/modell-9", 1_000_000, 1_000_000
        )
        assert wert == pytest.approx(eingabe + ausgabe)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ? "
        "AND art = 'kosten_modell_unbekannt'", (CHAT,)
    ).fetchone()["n"] == 1


def test_bekanntes_modell_erzeugt_keinen_vorfall(conn):
    kosten.kosten_oder_teuerster(conn, CHAT, "gruppe1", "google/gemma-4-31B-it", 10, 10)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ?", (CHAT,)
    ).fetchone()["n"] == 0


def test_whisper_kostet_je_minute():
    assert kosten.stt_kosten_chf(60) == pytest.approx(kosten.WHISPER_CHF_JE_MINUTE)
    assert kosten.stt_kosten_chf(90) == pytest.approx(kosten.WHISPER_CHF_JE_MINUTE * 1.5)
    assert kosten.stt_kosten_chf(0) == 0.0
    assert kosten.stt_kosten_chf(None) == 0.0


def test_claude_steht_an_einer_stelle():
    """Aus dem Abo kann eine Abrechnung werden -- dann ist das eine Zeile
    und keine Suche."""
    assert kosten.CLAUDE_CHF_JE_AUFRUF == 0.0


# -- Die Spalten ----------------------------------------------------------


def test_aufruf_hat_modell_und_kosten(conn):
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(aufruf)")}
    assert "modell" in spalten and "kosten_chf" in spalten


def test_alte_zeilen_bleiben_null_und_zaehlen_als_null(conn):
    """Additive Migration: eine Datenbank von gestern hat NULL in den neuen
    Spalten, und NULL ist keine Kostenangabe, sondern 'wissen wir nicht'."""
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, erstellt_am) VALUES (?, ?, ?)",
        (CHAT, "gespraech", repo._jetzt()),
    )
    conn.commit()
    assert repo.kostensumme_seit(conn, CHAT, "1970-01-01T00:00:00+00:00") == 0.0


def test_merke_aufruf_schreibt_modell_und_kosten(conn):
    repo.merke_aufruf(conn, CHAT, "gespraech", "A", 100, 120, 30, "stop", 900, 1,
                      modell="moonshotai/Kimi-K2.6", kosten_chf=0.25)
    zeile = conn.execute("SELECT * FROM aufruf WHERE chat_id = ?", (CHAT,)).fetchone()
    assert zeile["modell"] == "moonshotai/Kimi-K2.6"
    assert zeile["kosten_chf"] == pytest.approx(0.25)


def test_merke_aufruf_ohne_die_neuen_werte_geht_weiter(conn):
    """Die zwei Parameter sind additiv und stehen am Ende -- jeder
    bestehende Aufruf funktioniert unveraendert."""
    repo.merke_aufruf(conn, CHAT, "extraktor", "A", 10, 12, 3, "stop", 80, 1)
    zeile = conn.execute("SELECT * FROM aufruf WHERE chat_id = ?", (CHAT,)).fetchone()
    assert zeile["modell"] is None and zeile["kosten_chf"] is None


def test_kostensumme_zaehlt_nur_die_eigene_gruppe(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Die Zweiten")
    repo.merke_aufruf(conn, CHAT, "gespraech", "A", kosten_chf=1.0)
    repo.merke_aufruf(conn, 2, "gespraech", "A", kosten_chf=99.0)
    assert repo.kostensumme_seit(conn, CHAT, "1970-01-01T00:00:00+00:00") == pytest.approx(1.0)


def test_kostensumme_zaehlt_auch_gescheiterte_aufrufe(conn):
    """Ein 5xx nach dem Senden ist bezahlt -- llm._anfrage bucht im finally
    (llm.py:316), und der Deckel muss dasselbe sehen."""
    repo.merke_aufruf(conn, CHAT, "gespraech", "A", erfolg=0, kosten_chf=0.4)
    assert repo.kostensumme_seit(conn, CHAT, "1970-01-01T00:00:00+00:00") == pytest.approx(0.4)


def test_kostensumme_ignoriert_was_vor_dem_stichtag_liegt(conn):
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, kosten_chf, erstellt_am) VALUES (?, ?, ?, ?)",
        (CHAT, "gespraech", 3.0, "2026-09-29T21:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, kosten_chf, erstellt_am) VALUES (?, ?, ?, ?)",
        (CHAT, "gespraech", 2.0, "2026-09-30T08:00:00+00:00"),
    )
    conn.commit()
    summe = repo.kostensumme_seit(conn, CHAT, "2026-09-29T22:00:00+00:00")
    assert summe == pytest.approx(2.0)
