"""scripts/test_uebernehmen.py -- eine echte Gruppe auf die Testinstanz spielen.

Alles gegen Wegwerf-DBs in tmp_path (monkeypatch.chdir), ohne Netz, ohne
systemctl. Die Quelle wird mit einer schreibenden Verbindung GEFUELLT und
danach geschlossen; das Skript selbst liest sie nur mode=ro.

Die Pfade sind die Vorgaben des Skripts (betrieb/padua.db, audio-padua, ...),
relativ zu tmp_path -- so wird nebenbei die Vorgabe selbst geprueft.
"""

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from interview_theater import db, repo
from scripts import test_uebernehmen as tu

QUELLE_CHAT = 7_000_000_000_001
ANDERE_CHAT = 7_000_000_000_002
TEST = tu.TEST_CHAT_ID
#: Steht in jedem Textfeld der Quelle -- darf in keiner Ausgabe auftauchen (E10).
GEHEIM = "GEHEIM-INHALT-7c1f"
ZEIT = "2026-10-04T10:00:00+00:00"
#: Diese Tabellen fuellt baue_gruppe von Hand (zusammenhaengende ids, Dateien).
VON_HAND = ("gruppe", "nachricht", "aufnahme", "web_post")


@dataclass
class Umgebung:
    quelle: str = "betrieb/padua.db"
    ziel: str = "betrieb/padua-test.db"
    audio_quelle: str = "audio-padua"
    audio_ziel: str = "audio-padua-test"

    def pfade(self) -> dict:
        return {"quelle": self.quelle, "ziel": self.ziel,
                "audio_quelle": self.audio_quelle, "audio_ziel": self.audio_ziel}


def basis_id(tabelle: str, basis: int) -> int:
    """Die id der generisch gefuellten Zeile einer Tabelle (basis+10 ...)."""
    return basis + 10 + db.TABELLEN_MIT_CHAT_ID.index(tabelle)


def fuelle_zeile(conn, tabelle: str, chat_id, nummer: int, **fest) -> None:
    """Eine Zeile mit allen Pflichtspalten -- aus PRAGMA table_info, damit
    eine spaeter hinzukommende Pflichtspalte den Test nicht bricht."""
    werte = {}
    for s in conn.execute(f"PRAGMA table_info({tabelle})").fetchall():
        name, typ = s["name"], (s["type"] or "").upper()
        if name == "chat_id":
            werte[name] = chat_id
        elif s["pk"] or (s["notnull"] and s["dflt_value"] is None):
            werte[name] = nummer if ("INT" in typ or "REAL" in typ) else f"x{nummer}"
    werte.update(fest)
    namen = ", ".join(werte)
    fragen = ", ".join("?" for _ in werte)
    conn.execute(f"INSERT INTO {tabelle} ({namen}) VALUES ({fragen})",
                 list(werte.values()))


def schreibe_datei(pfad: Path, inhalt: bytes) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(inhalt)


def baue_gruppe(conn, chat_id: int, basis: int, bot_name: str, audio: str) -> None:
    """Je Tabelle aus db.TABELLEN_MIT_CHAT_ID mindestens eine Zeile; dazu
    drei Nachrichten, vier web_post-Zeilen (Eingang Text, Eingang Sprache mit
    ABSOLUTEM Pfad wie der Webdienst, Ausgang Text, Ausgang Datei mit
    RELATIVEM Pfad wie der Bot) und eine Aufnahme mit relativem Pfad."""
    for tabelle in db.TABELLEN_MIT_CHAT_ID:
        if tabelle not in VON_HAND:
            fuelle_zeile(conn, tabelle, chat_id, basis_id(tabelle, basis))
    conn.execute("UPDATE vorfall SET bot_name = ? WHERE chat_id = ?", (bot_name, chat_id))
    fuelle_zeile(
        conn, "gruppe", chat_id, basis, bot_name=bot_name, kanal="web",
        titel=GEHEIM, web_token=f"quelltoken-{chat_id}", erste_nachricht_am=ZEIT,
        letzte_beantwortete_message_id=basis + 3,
        letzte_extrahierte_message_id=basis + 3,
        letzte_journalisierte_message_id=basis + 1,
        web_tippt_bis=ZEIT, kostenpause_gemeldet_am=ZEIT,
    )
    for nr, ist_bot, typ, unterdrueckt in (
        (basis + 1, 0, "text", 0),
        (basis + 2, 0, "sprache", 1),
        (basis + 3, 1, "text", 0),
    ):
        fuelle_zeile(conn, "nachricht", chat_id, nr, message_id=nr, ist_bot=ist_bot,
                     typ=typ, text=GEHEIM, gesendet_am=ZEIT,
                     unterdrueckt=unterdrueckt, absender="Gruppe")
    eingang = (Path(audio) / str(chat_id) / "web-eingang" / f"{basis + 2}.webm").resolve()
    ausgang = Path(audio) / str(chat_id) / "web-ausgang" / f"{basis + 4}-textbuch.md"
    aufnahme = Path(audio) / str(chat_id) / f"{basis + 2}.webm"
    schreibe_datei(eingang, b"webm-" + str(chat_id).encode())
    schreibe_datei(ausgang, GEHEIM.encode())
    schreibe_datei(aufnahme, b"aufnahme-" + str(chat_id).encode())
    fuelle_zeile(conn, "web_post", chat_id, basis + 1, richtung="ein", typ="text",
                 text=GEHEIM, erstellt_am=ZEIT)
    fuelle_zeile(conn, "web_post", chat_id, basis + 2, richtung="ein", typ="sprache",
                 datei=str(eingang), mime="audio/webm", erstellt_am=ZEIT)
    fuelle_zeile(conn, "web_post", chat_id, basis + 3, richtung="aus", typ="text",
                 text=GEHEIM, erstellt_am=ZEIT)
    fuelle_zeile(conn, "web_post", chat_id, basis + 4, richtung="aus", typ="datei",
                 datei=str(ausgang), dateiname="textbuch.md", erstellt_am=ZEIT)
    fuelle_zeile(conn, "aufnahme", chat_id, basis + 1, message_id=basis + 2,
                 klasse="kurz", quelle="sprache", audio_pfad=str(aufnahme),
                 transkript=GEHEIM, status="fertig", empfangen_am=ZEIT)


def baue_quelle(u: Umgebung) -> None:
    Path(u.quelle).parent.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(u.quelle)
    db.initialisiere(conn)
    baue_gruppe(conn, QUELLE_CHAT, 100, "padua-gruppe1", u.audio_quelle)
    baue_gruppe(conn, ANDERE_CHAT, 500, "padua-gruppe2", u.audio_quelle)
    conn.commit()
    repo.setze_update_id(conn, "padua-gruppe1", 103)
    conn.close()


def baue_ziel(u: Umgebung) -> None:
    """Eine Test-DB mit einer ALTEN Testgruppe (festes Token, web_post-id 900
    -- hoeher als alles in der Quelle) und einem bot-weiten Vorfall ohne
    chat_id, dessen id mit einem Quellvorfall kollidiert (P2)."""
    Path(u.ziel).parent.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(u.ziel)
    db.initialisiere(conn)
    fuelle_zeile(conn, "gruppe", TEST, 900, bot_name=tu.TEST_BOT_NAME, kanal="web",
                 web_token="fester-testtoken", titel=GEHEIM)
    fuelle_zeile(conn, "nachricht", TEST, 900, message_id=900, typ="text",
                 text=GEHEIM, gesendet_am=ZEIT)
    fuelle_zeile(conn, "web_post", TEST, 900, richtung="ein", typ="text",
                 text=GEHEIM, erstellt_am=ZEIT)
    fuelle_zeile(conn, "vorfall", None, basis_id("vorfall", 100), art="bot_weit",
                 erstellt_am=ZEIT)
    conn.commit()
    repo.setze_update_id(conn, tu.TEST_BOT_NAME, 900)
    conn.close()
    schreibe_datei(Path(u.audio_ziel) / str(TEST) / "alt.webm", b"alt")


def fingerabdruck_db(pfad) -> tuple:
    """Hauptdatei und -wal (fehlend == leer). -shm bewusst nicht: auch Leser
    schreiben dort ihre Lesemarken (ANNAHME 2 im Plan)."""
    def h(p: Path) -> str:
        return hashlib.sha256(p.read_bytes() if p.exists() else b"").hexdigest()
    return h(Path(pfad)), h(Path(f"{pfad}-wal"))


def fingerabdruck_baum(verz) -> dict:
    verz = Path(verz)
    return {str(p.relative_to(verz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(verz.rglob("*")) if p.is_file()}


def lies(pfad) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture(autouse=True)
def kein_echter_dienst(monkeypatch):
    """Auf dem Server laeuft womoeglich die echte Unit -- kein Test darf
    davon abhaengen (Task 7 fuehrt dienst_laeuft ein)."""
    monkeypatch.setattr(tu, "dienst_laeuft", lambda bot_name: False, raising=False)


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    u = Umgebung()
    baue_quelle(u)
    baue_ziel(u)
    return u


@pytest.fixture
def umgebung_ohne_ziel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    u = Umgebung()
    baue_quelle(u)
    return u


# --------------------------------------------------------------------------
# Task 2: Pruefungen und Trockenlauf
# --------------------------------------------------------------------------


def test_skript_hat_keine_funktion_die_pytest_als_test_saehe():
    """scripts/test_uebernehmen.py heisst test_*, pytest sammelt es ein."""
    namen = [n for n, o in vars(tu).items()
             if callable(o) and (n.startswith("test") or n.startswith("Test"))]
    assert namen == []


def test_trockenlauf_zaehlt_und_veraendert_nichts(umgebung):
    q_vorher = fingerabdruck_db(umgebung.quelle)
    z_vorher = fingerabdruck_db(umgebung.ziel)
    bericht = tu.plane(QUELLE_CHAT, **umgebung.pfade())
    assert bericht["zeilen"]["nachricht"] == 3
    assert bericht["zeilen"]["web_post"] == 4
    assert bericht["zeilen"]["gruppe"] == 1
    assert "aufruf" not in bericht["zeilen"]
    assert bericht["audio_dateien"] == 3
    assert bericht["ziel_lage"]["existiert"] is True
    assert bericht["ziel_lage"]["token_vorhanden"] is True
    assert fingerabdruck_db(umgebung.quelle) == q_vorher
    assert fingerabdruck_db(umgebung.ziel) == z_vorher


def test_bericht_zeigt_zahlen_und_keine_inhalte(umgebung):
    text = tu.berichtstext(tu.plane(QUELLE_CHAT, **umgebung.pfade()), trocken=True)
    assert "nachricht: 3" in text
    assert GEHEIM not in text
    assert "quelltoken" not in text
    assert "fester-testtoken" not in text


def test_trockenlauf_ohne_test_db_sagt_es_wird_angelegt(umgebung_ohne_ziel):
    bericht = tu.plane(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    assert bericht["ziel_lage"] == {"existiert": False, "zeilen": {}, "token_vorhanden": False}
    assert not Path(umgebung_ohne_ziel.ziel).exists()


def test_verweigert_quelle_gleich_ziel(umgebung):
    pfade = umgebung.pfade() | {"ziel": umgebung.quelle}
    with pytest.raises(tu.Verweigert, match="dieselbe"):
        tu.plane(QUELLE_CHAT, **pfade)


def test_verweigert_die_betriebsdatenbank_als_ziel(umgebung, tmp_path):
    pfade = umgebung.pfade() | {"quelle": umgebung.ziel, "ziel": "betrieb/padua.db"}
    with pytest.raises(tu.Verweigert, match="Betrieb"):
        tu.plane(QUELLE_CHAT, **pfade)


def test_verweigert_das_betriebsaudio_als_ziel(umgebung):
    pfade = umgebung.pfade() | {"audio_ziel": "audio-padua"}
    with pytest.raises(tu.Verweigert, match="Audio"):
        tu.plane(QUELLE_CHAT, **pfade)


def test_verweigert_die_testgruppe_als_quelle(umgebung):
    with pytest.raises(tu.Verweigert):
        tu.plane(TEST, **umgebung.pfade())


def test_verweigert_unbekannte_quellgruppe(umgebung):
    with pytest.raises(tu.Verweigert, match="gibt es"):
        tu.plane(7_000_000_000_077, **umgebung.pfade())


def test_verweigert_eine_telegram_gruppe_als_quelle(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE gruppe SET kanal = 'telegram' WHERE chat_id = ?", (QUELLE_CHAT,))
    conn.commit()
    conn.close()
    with pytest.raises(tu.Verweigert, match="Web"):
        tu.plane(QUELLE_CHAT, **umgebung.pfade())


def test_verweigert_bei_laufender_aufnahme(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE aufnahme SET status = 'laeuft' WHERE chat_id = ?", (QUELLE_CHAT,))
    conn.commit()
    conn.close()
    with pytest.raises(tu.Verweigert, match="Aufnahme"):
        tu.plane(QUELLE_CHAT, **umgebung.pfade())


def test_verweigert_bei_interviewmodus(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE gruppe SET interviewmodus_seit = ? WHERE chat_id = ?",
                 (ZEIT, QUELLE_CHAT))
    conn.commit()
    conn.close()
    with pytest.raises(tu.Verweigert, match="Aufnahme"):
        tu.plane(QUELLE_CHAT, **umgebung.pfade())


def test_verweigert_fremde_gruppen_im_ziel_mit_liste_ohne_inhalt(umgebung):
    conn = db.verbinde(umgebung.ziel)
    fuelle_zeile(conn, "gruppe", ANDERE_CHAT, 1, bot_name="alt", titel=GEHEIM)
    fuelle_zeile(conn, "nachricht", ANDERE_CHAT, 1, message_id=1, text=GEHEIM)
    conn.commit()
    conn.close()
    vorher = fingerabdruck_db(umgebung.ziel)
    with pytest.raises(tu.Verweigert) as fehler:
        tu.plane(QUELLE_CHAT, **umgebung.pfade())
    meldung = str(fehler.value)
    assert f"{ANDERE_CHAT} (2 Zeilen)" in meldung
    assert "scripts/loeschen.py" in meldung
    assert GEHEIM not in meldung
    assert fingerabdruck_db(umgebung.ziel) == vorher


def test_bot_weite_vorfaelle_ohne_chat_id_sind_nicht_fremd(umgebung):
    conn = lies(umgebung.ziel)
    assert tu.fremde_chat_ids(conn) == {}
    conn.close()
