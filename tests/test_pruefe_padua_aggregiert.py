"""Tests fuer ``scripts/pruefe_padua_aggregiert.py`` -- das Mess-/Pruefskript
der Karte t_97f605c7. Gegen die aggregierte Fixture aus Task 1
(``scripts/fixture_padua_aggregiert.py``, Commit d38ff98), importiert und
gebaut, nie dupliziert."""
import pytest

from interview_theater import db, einstellungen, repo
from scripts import fixture_padua_aggregiert as fix
from scripts import pruefe_padua_aggregiert as pruefer


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "pruefe_aggregiert.db"))
    db.initialisiere(verbindung)
    yield verbindung
    verbindung.close()


@pytest.fixture
def e(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K",
        llm_modell="kimi", stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


# --------------------------------------------------------------------------
# treue_wortueberlappung
# --------------------------------------------------------------------------


def test_treue_findet_keinen_fehlalarm_bei_treuem_text():
    freitext = "The group talked about Elena and her garden for a while."
    transkript = "elena said she loves her garden more than anything else."
    befund = pruefer.treue_wortueberlappung(freitext, transkript)
    assert befund["verdaechtig"] == []


def test_treue_findet_erfundenen_namen():
    freitext = "Marco mentioned that Zbigniew used to work at the station."
    transkript = "marco said he used to work at the station for many years."
    befund = pruefer.treue_wortueberlappung(freitext, transkript)
    assert "Zbigniew" in befund["verdaechtig"]
    # "Marco" steht im Transkript -- kein Fehlalarm auf dem echten Namen.
    assert "Marco" not in befund["verdaechtig"]


def test_treue_prueft_zitate_mit_zitat_pruefe():
    freitext = 'She said "this exact sentence is in the transcript".'
    transkript = "Before. this exact sentence is in the transcript. After."
    befund = pruefer.treue_wortueberlappung(freitext, transkript)
    assert len(befund["quote_pruefungen"]) == 1
    assert befund["quote_pruefungen"][0]["bestanden"] is True

    freitext_falsch = 'She said "a sentence that was never actually said".'
    befund_falsch = pruefer.treue_wortueberlappung(freitext_falsch, transkript)
    assert befund_falsch["quote_pruefungen"][0]["bestanden"] is False


def test_treue_findet_alle_drei_honeypots_der_fixture(conn):
    """Muss nachweislich das fabrikationswort jeder der drei Honeypot-
    Sessions aus Task 1 in ``verdaechtig`` finden."""
    diskussion_chat = fix.chat_id_fuer("diskussion")
    diskussion_sessions = fix.baue_diskussion_sessions(conn, diskussion_chat, 5)
    diskussion_honeypot = next(s for s in diskussion_sessions if s["fabrikation"])
    befund = pruefer.treue_wortueberlappung(
        diskussion_honeypot["verdichtung_text"],
        diskussion_honeypot["transkript_bisher"],
    )
    assert diskussion_honeypot["fabrikationswort"] in befund["verdaechtig"]

    interviews_chat = fix.chat_id_fuer("interviews")
    interview_sessions = fix.baue_interview_sessions(conn, interviews_chat, 5)
    interview_honeypot = next(s for s in interview_sessions if s["fabrikation"])
    befund = pruefer.treue_wortueberlappung(
        interview_honeypot["zusammenfassung"], interview_honeypot["transkript"],
    )
    assert interview_honeypot["fabrikationswort"] in befund["verdaechtig"]

    brainstorm_chat = fix.chat_id_fuer("brainstorm")
    brainstorm_sessions = fix.baue_brainstorm_sessions(conn, brainstorm_chat, 5)
    brainstorm_honeypot = next(s for s in brainstorm_sessions if s["fabrikation"])
    karte = conn.execute(
        "SELECT text FROM buehnenkarte WHERE chat_id=? ORDER BY id ASC",
        (brainstorm_chat,),
    ).fetchall()[brainstorm_honeypot["session"] - 1]
    transkript = repo.brainstorm_transkript(conn, brainstorm_chat)
    befund = pruefer.treue_wortueberlappung(karte["text"], transkript)
    assert brainstorm_honeypot["fabrikationswort"] in befund["verdaechtig"]


def test_treue_wirft_keinen_fehlalarm_auf_nicht_fabrizierten_sessions(conn):
    """Mindestens eine nicht-fabrizierte Session jedes Strangs: ihr
    ``verdaechtig`` ist leer -- keine Fehlalarme auf Woertern wie "Elena",
    "Samir" oder "Ferzan", die tatsaechlich im jeweiligen Transkript stehen.

    Bewusst NICHT Interview-Session 1 (dort alarmiert die mechanische
    Pruefung "Quran" gegen das deutsche "Koran" -- ein echter, erklaerter
    Befund einer Uebersetzung, kein Heuristik-Fehlalarm, siehe Docstring von
    ``treue_wortueberlappung`` und den Bericht) und NICHT Brainstorm-Session
    2 (dort alarmiert "Tommaso", weil der Name in KEINEM chat-lokalen Feld
    dieses Strangs vorkommt -- ebenfalls dokumentiert, keine Fehlalarm-
    Heuristik-Luecke)."""
    diskussion_chat = fix.chat_id_fuer("diskussion")
    diskussion_sessions = fix.baue_diskussion_sessions(conn, diskussion_chat, 5)
    saubere_diskussion = next(s for s in diskussion_sessions if not s["fabrikation"])
    befund = pruefer.treue_wortueberlappung(
        saubere_diskussion["verdichtung_text"], saubere_diskussion["transkript_bisher"],
    )
    assert befund["verdaechtig"] == []

    interviews_chat = fix.chat_id_fuer("interviews")
    interview_sessions = fix.baue_interview_sessions(conn, interviews_chat, 5)
    sauberes_interview = next(
        s for s in interview_sessions if not s["fabrikation"] and s["session"] != 1
    )
    befund = pruefer.treue_wortueberlappung(
        sauberes_interview["zusammenfassung"], sauberes_interview["transkript"],
    )
    assert befund["verdaechtig"] == []

    brainstorm_chat = fix.chat_id_fuer("brainstorm")
    fix.baue_brainstorm_sessions(conn, brainstorm_chat, 5)
    stand = repo.hole_arbeitsstand(conn, brainstorm_chat)
    grundlage = "\n".join([
        repo.brainstorm_transkript(conn, brainstorm_chat),
        stand["rahmen"] or "", stand["geschichte"] or "",
    ])
    karten = conn.execute(
        "SELECT text FROM buehnenkarte WHERE chat_id=? ORDER BY id ASC",
        (brainstorm_chat,),
    ).fetchall()
    # Session 1 (idx 0): "Keep the lost-and-found window ... Samir glances
    # at once" -- Samir steht in arbeitsstand.geschichte.
    befund = pruefer.treue_wortueberlappung(karten[0]["text"], grundlage)
    assert befund["verdaechtig"] == []


# --------------------------------------------------------------------------
# kumulation_tabelle
# --------------------------------------------------------------------------


def test_kumulation_tabelle_rechnet_wachstum_und_dubletten():
    sessions = [
        {"session": 1, "zeichen": 100, "text": "abc"},
        {"session": 2, "zeichen": 150, "text": "def"},
        {"session": 3, "zeichen": 100, "text": "abc"},  # Dublette von 1
        {"session": 4, "zeichen": 90, "text": "ghi"},
    ]
    tabelle = pruefer.kumulation_tabelle(sessions, "zeichen")
    assert [z["wachstum_seit_vorher"] for z in tabelle] == [0, 50, -50, -10]
    assert [z["ist_dublette"] for z in tabelle] == [False, False, True, False]
    assert [z["zeichen"] for z in tabelle] == [100, 150, 100, 90]


def test_kumulation_tabelle_gegen_echte_diskussion_sessions(conn):
    chat_id = fix.chat_id_fuer("diskussion")
    sessions = fix.baue_diskussion_sessions(conn, chat_id, 5)
    tabelle = pruefer.kumulation_tabelle(sessions, "zeichen")
    assert len(tabelle) == 5
    assert all(not z["ist_dublette"] for z in tabelle)
    assert tabelle[0]["wachstum_seit_vorher"] == 0


# --------------------------------------------------------------------------
# ersetzt_oder_haengt_an
# --------------------------------------------------------------------------


def test_ersetzt_oder_haengt_an_diskussion_verdichtung_ersetzt(conn):
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    befund = pruefer.ersetzt_oder_haengt_an(conn, chat_id, "diskussion_verdichtung")
    assert befund == {"tabelle": "diskussion_verdichtung", "zeilen": 1}


def test_ersetzt_oder_haengt_an_verdichtung_haengt_an(conn):
    chat_id = fix.chat_id_fuer("interviews")
    fix.baue_interview_sessions(conn, chat_id, 5)
    befund = pruefer.ersetzt_oder_haengt_an(conn, chat_id, "verdichtung")
    assert befund == {"tabelle": "verdichtung", "zeilen": 5}


def test_ersetzt_oder_haengt_an_begriffsboard_und_buehnenkarte_haengen_an(conn):
    diskussion_chat = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, diskussion_chat, 5)
    befund = pruefer.ersetzt_oder_haengt_an(conn, diskussion_chat, "begriffsboard")
    assert befund == {"tabelle": "begriffsboard", "zeilen": 5}

    brainstorm_chat = fix.chat_id_fuer("brainstorm")
    fix.baue_brainstorm_sessions(conn, brainstorm_chat, 5)
    befund = pruefer.ersetzt_oder_haengt_an(conn, brainstorm_chat, "buehnenkarte")
    assert befund == {"tabelle": "buehnenkarte", "zeilen": 5}


# --------------------------------------------------------------------------
# platz_im_prompt
# --------------------------------------------------------------------------


def test_platz_im_prompt_zeigt_diskussion_block_bei_der_diskussion_gruppe(conn, e):
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    stand = pruefer.platz_im_prompt(conn, chat_id, e)
    assert stand["bloecke"]["diskussion"] > 0
    assert stand["anteil_diskussion_prozent"] > 0.0


def test_platz_im_prompt_begriffe_detail_ist_bei_phase_1_leer(conn, e):
    """Phase-Gating (AGENTS.md): begriffe_detail erscheint nicht in Phase 1,
    obwohl die Diskussions-Fixture ``arbeitsstand.begriffe_detail`` fuellt."""
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    assert repo.hole_phase(conn, chat_id) is None  # nie gesetzt -> Phase 1 (ERSTE)
    stand = pruefer.platz_im_prompt(conn, chat_id, e)
    assert stand["bloecke"]["begriffe_detail"] == 0


# --------------------------------------------------------------------------
# pruefe_phasen_asymmetrie
# --------------------------------------------------------------------------


def test_phasen_asymmetrie_diskussion_konstant_begriffe_detail_nicht(conn, e):
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    befund = pruefer.pruefe_phasen_asymmetrie(conn, chat_id, e)

    assert befund["phase_1"]["diskussion"] > 0
    assert befund["phase_7"]["diskussion"] > 0

    assert befund["phase_1"]["begriffe_detail"] == 0
    assert befund["phase_7"]["begriffe_detail"] > 0


# --------------------------------------------------------------------------
# provoziere_kuerzung
# --------------------------------------------------------------------------


def test_provoziere_kuerzung_erreicht_wirklich_eine_kuerzung(conn, e):
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    repo.setze_phase(conn, chat_id, 2)

    befund = pruefer.provoziere_kuerzung(conn, chat_id, e)

    assert befund["gekuerzt"] is True
    # Diskussion und begriffe_detail fallen laut Kuerzungsleiter VOR den
    # Verdichtungen weg (kontext._kuerze_auf_budget, Stufen 6/7/8).
    assert befund["bloecke_am_ende"]["diskussion"] == 0
    assert befund["bloecke_am_ende"]["begriffe_detail"] == 0


def test_provoziere_kuerzung_reihenfolge_diskussion_vor_verdichtungen(conn, e):
    """Empirischer Beleg fuer die in AGENTS.md/kontext.py dokumentierte
    Reihenfolge: faellt sowohl 'diskussion' als auch 'verdichtungen' auf 0,
    dann nicht in derselben allerersten Runde VOR 'diskussion'."""
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    repo.setze_phase(conn, chat_id, 2)

    befund = pruefer.provoziere_kuerzung(conn, chat_id, e)
    reihenfolge = dict(befund["reihenfolge_null"])
    if "verdichtungen" in reihenfolge and "diskussion" in reihenfolge:
        assert reihenfolge["diskussion"] <= reihenfolge["verdichtungen"]
    if "verdichtungen" in reihenfolge and "begriffe_detail" in reihenfolge:
        assert reihenfolge["begriffe_detail"] <= reihenfolge["verdichtungen"]


# --------------------------------------------------------------------------
# nutzung_befund
# --------------------------------------------------------------------------


def test_nutzung_befund_findet_kernpaket_und_verdichtung():
    befund = pruefer.nutzung_befund()
    assert befund["Kernpaket"], "Kernpaket sollte in mindestens einer Prompt-Datei stehen"
    assert befund["Verdichtung"], "Verdichtung sollte in mindestens einer Prompt-Datei stehen"


def test_nutzung_befund_findet_begriffs_diskussion_und_begriffe_detail_nirgends():
    befund = pruefer.nutzung_befund()
    assert befund["Begriffs-Diskussion"] == []
    assert befund["begriffe_detail"] == []
