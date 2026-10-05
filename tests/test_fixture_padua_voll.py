"""Die Padua-Fixture: sieben Gruppen mit realistischem Volumen.

Die Zahlen hier sind keine Wuensche, sondern die Bedingung dafuer, dass der
Prompt-Dump ueberhaupt etwas messen kann (Birk, 05.10.2026 00:40): gegen eine
frische Datenbank zeigt sich keiner der Befunde, die am 06.09.2026 gemessen
wurden.
"""
import json

import pytest

from interview_theater import db, kontext, repo
from scripts import fixture_padua_voll as fix


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "fixture.db"))
    db.initialisiere(verbindung)
    fix.baue_alle(verbindung)
    yield verbindung
    verbindung.close()


def _alle_nachrichten(conn, chat_id):
    """Rueckfall ohne neue Repo-Funktion (``repo.alle_nachrichten`` existiert
    nicht -- siehe AGENTS.md-Fallenkatalog und Schritt 3 des Plans): direktes
    SQL nur hier im Test, nie in ``repo.py``."""
    return conn.execute(
        "SELECT * FROM nachricht WHERE chat_id=? ORDER BY gesendet_am",
        (chat_id,),
    ).fetchall()


def test_jede_phase_hat_eine_gruppe_mit_genug_verlauf(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        nachrichten = _alle_nachrichten(conn, chat_id)
        assert len(nachrichten) >= 34, (phase, len(nachrichten))


def test_jede_gruppe_traegt_systemzeilen_und_ein_transkript_echo(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        texte = [n["text"] for n in _alle_nachrichten(conn, chat_id)]
        assert any(t.startswith("📌 Agreed:") for t in texte), phase
        assert any(t.startswith("Noted:") for t in texte), phase
        assert any(t == "Changed since." for t in texte), phase
        echos = conn.execute(
            "SELECT COUNT(*) FROM nachricht WHERE chat_id=? AND typ=?",
            (chat_id, repo.TYP_TRANSKRIPT),
        ).fetchone()[0]
        assert echos >= 1, phase


def test_mehrere_sprecher_je_gruppe(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        absender = {
            n["absender"] for n in _alle_nachrichten(conn, chat_id)
            if not n["ist_bot"]
        }
        assert len(absender) >= 3, (phase, absender)


def test_arbeitsstand_journal_und_festlegungen_sind_gefuellt(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        stand = repo.hole_arbeitsstand(conn, chat_id)
        assert stand["begriffe"], phase
        if phase >= 2:
            assert stand["fragen"], phase
        if phase >= 4:
            assert stand["rahmen"] and stand["geschichte"], phase
        assert repo.journal(conn, chat_id), phase
        assert repo.festlegungen(conn, chat_id), phase


def test_phase1_hat_diskussionssegmente_und_ein_begriffsboard(conn):
    chat_id = fix.chat_id_fuer(1)
    segmente = conn.execute(
        "SELECT COUNT(*) FROM aufnahme WHERE chat_id=? AND diskussion=1",
        (chat_id,),
    ).fetchone()[0]
    assert segmente >= 2
    board = conn.execute(
        "SELECT COUNT(*) FROM begriffsboard WHERE chat_id=?", (chat_id,)
    ).fetchone()[0]
    assert board >= 1


def test_jede_phase_hat_diskussion_board_und_begriffe_detail(conn):
    """a6/Board-Rundenbefund (Runde 1): eine echte Gruppe, die Phase 1
    durchlaufen hat, traegt Diskussion, Board und ``begriffe_detail`` auch in
    Phase 2+ weiter -- ``kontext._baue_board``/``_baue_begriffe_detail`` lesen
    datengetrieben in JEDER Phase. Bisher legte die Fixture das nur fuer
    Phase 1 an, wodurch der Pruefer in Phase 2 faelschlich "Board-Block
    fehlt" meldete (lesung.json, 05.10.2026)."""
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        segmente = conn.execute(
            "SELECT COUNT(*) FROM aufnahme WHERE chat_id=? AND diskussion=1",
            (chat_id,),
        ).fetchone()[0]
        assert segmente >= 2, phase
        board = conn.execute(
            "SELECT COUNT(*) FROM begriffsboard WHERE chat_id=?", (chat_id,)
        ).fetchone()[0]
        assert board >= 1, phase
        stand = repo.hole_arbeitsstand(conn, chat_id)
        assert stand["begriffe_detail"], phase


def test_ab_phase3_gibt_es_ein_verdichtetes_interview(conn):
    for phase in (3, 4, 5, 6, 7):
        chat_id = fix.chat_id_fuer(phase)
        assert repo.verdichtungen(conn, chat_id), phase


def test_das_fenster_schneidet_messbar_und_nicht_nur_nach_anzahl(conn):
    """Die Grenzen werden GEMESSEN, nicht angenommen (Birk 00:40).

    Mindestens eine Gruppe muss am Zeichenbudget schneiden und mindestens
    eine an der weichen Minutengrenze -- sonst ist die Fixture zu brav und
    der BEFUND kann zu den Fenstergrenzen nichts sagen."""
    gruende = set()
    for phase in fix.PHASEN:
        befund = fix.fensterbefund(conn, fix.chat_id_fuer(phase))
        assert befund["im_fenster"] < befund["nachrichten_gesamt"], phase
        assert befund["zeichen_im_fenster"] <= kontext.FENSTER_ZEICHEN
        gruende.add(befund["grund"])
    assert "zeichen" in gruende, gruende
    assert "minuten" in gruende, gruende


def test_fixture_nennt_kein_betriebsverzeichnis():
    """Die Fixture darf keine Betriebsdatei kennen -- auch nicht lesend."""
    import inspect

    quelle = inspect.getsource(fix)
    for wort in ("betrieb/", "soap.db", "IT_DB"):
        assert wort not in quelle, wort


# --- P1-L7: Fixture-Artefakte, die der Prompt-Pruefer faelschlich als ------
# Produktbefund liest (docs/prompt-audit/2026-10-05-padua-p12/lesung.json) ---

#: Woertlich die Zeilen, die am 05.10. als "reines Rauschen" am Fensteranfang
#: gelesen wurden -- nach dem Fix muss keine davon mehr das erste Fensterglied
#: sein (``_GRUNDVERLAUF`` legt das abgeschnittene Rauschen jetzt nach vorn).
_ORPHAN_UND_RAUSCHEN = (
    "In the work status tab. Everything saved is there.",
    "is anyone writing this down",
    "my phone went to sleep",
    "mine too, annoying",
)


def test_fenster_beginnt_nicht_mit_verwaistem_rauschen(conn):
    """P1-L7: der Pruefer fand das Fenster beginnend mit einer Bot-Antwort
    ohne die Frage davor ("In the work status tab...", Frage abgeschnitten),
    gefolgt von acht Zuegen reinem Rauschen (Handy schlaeft ein, "is anyone
    writing this down"). Reines Rauschen soll immer vorn in ``_GRUNDVERLAUF``
    liegen -- dort, wo das Fenster ohnehin abschneidet."""
    for phase in fix.PHASEN:
        befund = fix.fensterbefund(conn, fix.chat_id_fuer(phase))
        erste = befund["erste_zeile_text"]
        for satz in _ORPHAN_UND_RAUSCHEN:
            assert satz not in erste, (phase, erste)


def test_board_begruendung_ist_keine_blosse_erwaehnung(conn):
    """P1-L7: die Board-Beispielzeile "the group returns to it twice" verstoesst
    gegen die eigene Regel im Schema-Prompt ("No begruendung that only says
    the term was named, collected or suggested") -- ein Beispiel, das die
    Regel bricht, lehrt dem Modell, sie zu brechen."""
    chat_id = fix.chat_id_fuer(1)
    zeile = conn.execute(
        "SELECT json FROM begriffsboard WHERE chat_id=? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    board = json.loads(zeile["json"])
    eintrag = next(e for e in board if e["begriff"] == "waiting")
    begruendung = eintrag["begruendung"].lower()
    assert begruendung
    for verboten in ("returns to it", "mentioned", "named", "collected", "suggested"):
        assert verboten not in begruendung, eintrag["begruendung"]


#: Journal-Saetze, die nur Sinn ergeben, wenn Geschichte/Szenen schon stehen
#: (Phase 4+) -- in Phase 1 widersprechen sie dem Arbeitsstand und stehen mit
#: mehr Gewicht als die Begriffsliste im Prompt (lesung.json Zeile 524).
_SPAETPHASEN_JOURNAL_WOERTER = ("story as short story", "fourth scene", "platform")


def test_journal_in_phase1_nennt_keine_spaetphaseninhalte(conn):
    chat_id = fix.chat_id_fuer(1)
    texte = [z["text"] for z in repo.journal(conn, chat_id)]
    assert texte
    for text in texte:
        tief = text.lower()
        for wort in _SPAETPHASEN_JOURNAL_WOERTER:
            assert wort not in tief, (text, wort)


def test_changed_since_zeile_ist_der_echte_wortlaut_und_wird_gefiltert(conn):
    """a6 (Runde 1, lesung.json): die Fixture schrieb einen erfundenen
    Wortlaut ("Changed since - please fix it in the work status"), der NICHT
    von ``kontext._ist_systemzeile`` erkannt wird und deshalb faelschlich als
    Produktbefund im Prompt-Dump auftaucht. Der echte Wortlaut ist
    ``T._ANTWORT_UNDO_GEAENDERT`` = "Changed since." (``sprachen/en/texte.toml``)
    und wird gefiltert."""
    chat_id = fix.chat_id_fuer(1)
    zeilen = [
        dict(n) for n in conn.execute(
            "SELECT * FROM nachricht WHERE chat_id=? AND typ='text'",
            (chat_id,),
        )
    ]
    treffer = [n for n in zeilen if n["text"] == "Changed since."]
    assert treffer, "die Fixture muss den echten Wortlaut tragen"
    for n in treffer:
        assert kontext._ist_systemzeile(n)


def test_spaetphasenjournal_kommt_erst_wenn_die_geschichte_da_ist(conn):
    """Dieselben Saetze duerfen weiterhin stehen, sobald die Phase dazu passt
    -- die Fixture soll das Material nicht verlieren, nur phasengerecht
    einordnen."""
    frueh = [z["text"].lower() for z in repo.journal(conn, fix.chat_id_fuer(1))]
    spaet = [z["text"].lower() for z in repo.journal(conn, fix.chat_id_fuer(6))]
    assert not any("story as short story" in t for t in frueh)
    assert any("story as short story" in t for t in spaet)


def test_phase2_verlauf_endet_nicht_mit_einem_bot_zug(conn):
    """P2-Fixture-Artefakt (Runde 1, lesung.json): ``repo.letzte_nachrichten``
    (die Grundlage des Ausloesers, den ``erzeuge_prompts_padua_voll._gespraech``
    an ``ablauf.antworte`` gibt) liefert die Nachricht mit der hoechsten
    ``message_id`` -- bisher die letzte Zeile aus ``_JE_PHASE[2]``, eine
    Bot-Antwort. Im Dump erschien sie unter "## Now" als "You: ...", als
    waere der Bot selbst der Ausloeser -- eine echte Gruppe loest ihren
    naechsten Zug immer mit einer eigenen Nachricht aus."""
    chat_id = fix.chat_id_fuer(2)
    letzte = repo.letzte_nachrichten(conn, chat_id, anzahl=1)
    assert letzte, "chat_id 2 muss Nachrichten tragen"
    assert not letzte[-1]["ist_bot"], dict(letzte[-1])
