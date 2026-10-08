"""Tests fuer scripts/karten_verlauf_nachtrag.py (Birk 08.10.2026 ~10:48,
NACHTRAG Robo 10:48): Padua-Gruppen hatten ihre Karten schon vor
``karte_verlauf`` (b3ddefa) gebaut und ueberarbeitet -- der Chat ist die
einzige Quelle. Reine DB-Tests gegen eine frische Testdatenbank, nie gegen
eine Betriebsdatenbank."""

import json

import pytest

import scripts.karten_verlauf_nachtrag as skript
from interview_theater import db, repo, szenenkarte

from test_szenenkarte import padua  # noqa: F401

CHAT_ID = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT_ID, "gruppe1", "Testgruppe")
    return c


def _szene_mit_karte(conn, nummer: int, karte: dict) -> int:
    sid = repo.stelle_szene_sicher(conn, CHAT_ID, nummer)
    repo.setze_szenenfeld(conn, sid, "titel", f"Szene {nummer}")
    repo.setze_szenenkarte(conn, sid, json.dumps(karte, ensure_ascii=False))
    return sid


def _karte_anzeigen(conn, sid: int, karte: dict, *, status="") -> str:
    """Erzeugt denselben Text, den ``szenenkarte.zeige`` tatsaechlich in den
    Chat schreibt -- ueber die echte Rendering-Funktion, kein Hand-Fixture."""
    szene = repo.hole_szene(conn, sid)
    text = szenenkarte.karte_text(karte, szene)
    if status:
        text += "\n\n" + status
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text=text)
    return text


# ---------------------------------------------------------------------------
# _parse_karte_text: Rundreise durch die echte Rendering-Funktion
# ---------------------------------------------------------------------------


def test_parse_karte_text_liest_die_echte_anzeige_zurueck(conn, padua):
    karte = {"typ": "instructions", "worum": "Francesca sitzt allein.",
              "ort": "Tavolo vuoto di un bar", "wer": "Francesca",
              "punkte": ["Punkt eins", "Punkt zwei"],
              "zitate": [{"zitat": "Tendenzialmente si", "interview": "Interview 7"}],
              "fragen": ["Quanto dura l'attesa?"]}
    sid = _szene_mit_karte(conn, 1, karte)
    szene = repo.hole_szene(conn, sid)
    text = szenenkarte.karte_text(karte, szene)

    geparst = skript._parse_karte_text(text)

    assert geparst["typ"] == "instructions"
    assert geparst["worum"] == "Francesca sitzt allein."
    assert geparst["ort"] == "Tavolo vuoto di un bar"
    assert geparst["wer"] == "Francesca"
    assert geparst["punkte"] == ["Punkt eins", "Punkt zwei"]
    assert geparst["zitate"] == [{"zitat": "Tendenzialmente si", "interview": "Interview 7"}]
    assert geparst["fragen"] == ["Quanto dura l'attesa?"]


def test_parse_karte_text_englisch(conn, monkeypatch):
    from interview_theater import sprache

    karte = {"typ": "moment", "worum": "A quiet moment.", "ort": "the square",
              "wer": "Voce 1-5", "punkte": ["Something happens"], "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, karte)
    szene = repo.hole_szene(conn, sid)

    # EN-Fassung der Anzeige -- echte Funktion, nur mit erzwungener Sprache
    # (keine Italienisch-Pflicht fuer Phase 6/7 in diesem Test).
    monkeypatch.setattr(sprache, "code", lambda: "en")
    monkeypatch.setattr(szenenkarte.workshop, "p67_italienisch_aktiv", lambda: False)
    text = szenenkarte.karte_text(karte, szene)

    geparst = skript._parse_karte_text(text)
    assert geparst["ort"] == "the square"
    assert geparst["wer"] == "Voce 1-5"
    assert geparst["punkte"] == ["Something happens"]


def test_parse_karte_text_unbekannter_text_liefert_none(conn):
    assert skript._parse_karte_text("Nur ein normaler Chattext, keine Karte.") is None


# ---------------------------------------------------------------------------
# plane(): formale Notiz + Karte aus dem Chat rekonstruieren
# ---------------------------------------------------------------------------


def test_plane_rekonstruiert_notiz_und_karte_aus_formalem_dialog(conn, padua):
    alte_karte = {"typ": "instructions", "worum": "W", "ort": "O", "wer": "Francesca",
                  "punkte": ["p1"], "zitate": [], "fragen": []}
    neue_karte = {"typ": "instructions", "worum": "W", "ort": "O", "wer": "Francesca",
                  "punkte": ["p1 truccato"], "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, neue_karte)  # aktueller Endstand

    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Cosa deve cambiare nella scheda 1? Scrivilo in UN solo "
                               "messaggio -- ricostruisco subito la scheda e te la mostro qui.")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="Il barattolo è truccato")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Ok. Ricostruisco la scheda 1 con la vostra modifica -- "
                               "tra un attimo compare qui.")
    _karte_anzeigen(conn, sid, neue_karte,
                    status="Scheda 1 di 1, aggiornata. Va bene adesso?")

    plan = skript.plane(conn, CHAT_ID)

    assert len(plan) == 1
    eintrag = plan[0]
    assert eintrag["szene_id"] == sid
    assert eintrag["nummer"] == 1
    assert eintrag["notiz"] == "Il barattolo è truccato"
    assert eintrag["ausloeser"] == "aenderung"
    assert eintrag["karte"] == neue_karte


def test_plane_englischer_wortlaut_wird_auch_erkannt(conn):
    karte = {"typ": "moment", "worum": "W", "ort": "O", "wer": "Who", "punkte": ["p"],
             "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, karte)

    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="Make it darker")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Got it. I'm rebuilding card 1 with your change -- it "
                               "appears here in a moment.")
    _karte_anzeigen(conn, sid, karte, status="Card 1 of 1.")

    plan = skript.plane(conn, CHAT_ID)

    assert len(plan) == 1
    assert plan[0]["notiz"] == "Make it darker"


def test_plane_ohne_formalen_dialog_liefert_leeren_plan(conn, padua):
    """G1-Fall: reine CoThinker-Freitextkonversation ohne den formalen
    Notiz-Dialog -- nichts rekonstruierbar, kein falscher Treffer."""
    karte = {"typ": "spoken", "worum": "W", "ort": "O", "wer": "Wer", "punkte": ["p"],
             "zitate": [], "fragen": []}
    _szene_mit_karte(conn, 1, karte)
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                          text="Irgendein freier Wunsch zur Karte.")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="**Card 1 of 1.** Changes: something narrative, not the "
                               "formal rebuild ack.")

    plan = skript.plane(conn, CHAT_ID)

    assert plan == []


def test_plane_ueberspringt_szenen_mit_schon_vorhandenem_verlauf(conn, padua):
    """Idempotenz: ein zweiter Lauf (oder eine Szene, die ueber den neuen
    Code bereits einen Verlauf hat) wird nicht noch einmal angefasst."""
    karte = {"typ": "instructions", "worum": "W", "ort": "O", "wer": "Wer",
             "punkte": ["p"], "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, karte)
    repo.merke_karte_verlauf(conn, CHAT_ID, sid, json.dumps(karte), "erstentwurf", None)
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="X")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Ok. Ricostruisco la scheda 1 con la vostra modifica -- "
                               "tra un attimo compare qui.")
    _karte_anzeigen(conn, sid, karte)

    plan = skript.plane(conn, CHAT_ID)

    assert plan == []


def test_plane_ohne_passende_anzeige_faellt_auf_aktuelle_karte_zurueck(conn, padua):
    """Wenn die nachfolgende Kartenanzeige nicht geparst werden kann (oder
    fehlt), ist der aktuelle, gespeicherte Kartenstand die einzig sichere
    Grundlage -- besser ein etwas zu spaeter Stand als keiner."""
    karte = {"typ": "instructions", "worum": "W", "ort": "O", "wer": "Wer",
             "punkte": ["p"], "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, karte)
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="X")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Ok. Ricostruisco la scheda 1 con la vostra modifica -- "
                               "tra un attimo compare qui.")
    # keine Kartenanzeige danach

    plan = skript.plane(conn, CHAT_ID)

    assert len(plan) == 1
    assert plan[0]["karte"] == karte


# ---------------------------------------------------------------------------
# main(): Trockenlauf vs. --ja, Backup, Journal
# ---------------------------------------------------------------------------


def test_main_trockenlauf_schreibt_nichts(tmp_path, conn, capsys, padua):
    karte = {"typ": "instructions", "worum": "W", "ort": "O", "wer": "Wer",
             "punkte": ["p"], "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, karte)
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="X")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Ok. Ricostruisco la scheda 1 con la vostra modifica -- "
                               "tra un attimo compare qui.")
    _karte_anzeigen(conn, sid, karte)
    conn.close()

    rc = skript.main(["--db", str(tmp_path / "t.db")])

    assert rc == 0
    ausgabe = capsys.readouterr().out
    assert "1" in ausgabe
    nachlese = db.verbinde(str(tmp_path / "t.db"))
    assert repo.karte_verlauf(nachlese, CHAT_ID, sid) == []


def test_main_mit_ja_schreibt_verlauf_und_sichert_vorher(tmp_path, conn, padua):
    karte = {"typ": "instructions", "worum": "W", "ort": "O", "wer": "Wer",
             "punkte": ["p truccato"], "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, karte)
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="Il barattolo è truccato")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Ok. Ricostruisco la scheda 1 con la vostra modifica -- "
                               "tra un attimo compare qui.")
    _karte_anzeigen(conn, sid, karte)
    conn.close()

    rc = skript.main(["--db", str(tmp_path / "t.db"), "--ja"])

    assert rc == 0
    sicherungen = list((tmp_path / "backup").glob("*.db"))
    assert len(sicherungen) == 1
    nachlese = db.verbinde(str(tmp_path / "t.db"))
    zeilen = repo.karte_verlauf(nachlese, CHAT_ID, sid)
    assert len(zeilen) == 1
    assert zeilen[0]["ausloeser"] == "aenderung"
    assert zeilen[0]["notiz_text"] == "Il barattolo è truccato"
    assert json.loads(zeilen[0]["karte_json"]) == karte
    journal = repo.journal(nachlese, CHAT_ID)
    assert any("Karten-Verlauf nachgetragen" in z["text"] for z in journal)


def test_main_mit_ja_ist_wiederholbar_ohne_dubletten(tmp_path, conn, padua):
    karte = {"typ": "instructions", "worum": "W", "ort": "O", "wer": "Wer",
             "punkte": ["p"], "zitate": [], "fragen": []}
    sid = _szene_mit_karte(conn, 1, karte)
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="X")
    repo.lege_web_post_an(conn, CHAT_ID, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Ok. Ricostruisco la scheda 1 con la vostra modifica -- "
                               "tra un attimo compare qui.")
    _karte_anzeigen(conn, sid, karte)
    conn.close()

    rc1 = skript.main(["--db", str(tmp_path / "t.db"), "--ja"])
    rc2 = skript.main(["--db", str(tmp_path / "t.db"), "--ja"])

    assert rc1 == rc2 == 0
    nachlese = db.verbinde(str(tmp_path / "t.db"))
    assert len(repo.karte_verlauf(nachlese, CHAT_ID, sid)) == 1
