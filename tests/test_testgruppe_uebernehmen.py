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


# --------------------------------------------------------------------------
# Task 3: Uebernahme der Datenbank
# --------------------------------------------------------------------------


def test_uebernahme_ist_vollstaendig(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    src, ziel = lies(umgebung.quelle), lies(umgebung.ziel)
    for t in db.TABELLEN_MIT_CHAT_ID:
        im_ziel = ziel.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id = ?",
                               (TEST,)).fetchone()[0]
        if t in tu.NICHT_UEBERNOMMEN:
            assert im_ziel == 0, t
            continue
        in_quelle = src.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id = ?",
                                (QUELLE_CHAT,)).fetchone()[0]
        assert in_quelle >= 1, t
        assert im_ziel == in_quelle, t
        assert ziel.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id IN (?, ?)",
                            (QUELLE_CHAT, ANDERE_CHAT)).fetchone()[0] == 0, t
    src.close()
    ziel.close()


def test_ids_bleiben_unveraendert_ausser_bei_vorfall(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert {z[0] for z in ziel.execute(
        "SELECT id FROM web_post WHERE chat_id = ?", (TEST,))} == {101, 102, 103, 104}
    assert ziel.execute("SELECT id FROM aufnahme WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == 101
    assert ziel.execute("SELECT id FROM knopf WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == basis_id("knopf", 100)
    ziel.close()


def test_bot_weite_vorfaelle_im_ziel_bleiben_stehen(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert ziel.execute("SELECT COUNT(*) FROM vorfall WHERE chat_id IS NULL "
                        "AND art = 'bot_weit'").fetchone()[0] == 1
    assert ziel.execute("SELECT COUNT(*) FROM vorfall WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == 1
    ziel.close()


def test_quelle_bleibt_unveraendert(umgebung):
    db_vorher = fingerabdruck_db(umgebung.quelle)
    audio_vorher = fingerabdruck_baum(umgebung.audio_quelle)
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    assert fingerabdruck_db(umgebung.quelle) == db_vorher
    assert fingerabdruck_baum(umgebung.audio_quelle) == audio_vorher


def test_link_bleibt_gleich_und_ist_nie_der_quelllink(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    tokens = [z[0] for z in ziel.execute("SELECT web_token FROM gruppe")]
    ziel.close()
    assert tokens == ["fester-testtoken"]


def test_zweimal_uebernehmen_ist_idempotent(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    erste_verbindung = lies(umgebung.ziel)
    erstes = tu.zaehle(erste_verbindung, TEST)
    erste_verbindung.close()
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert tu.zaehle(ziel, TEST) == erstes
    assert ziel.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                        (TEST,)).fetchone()[0] == "fester-testtoken"
    ziel.close()


def test_ohne_bisherige_testgruppe_entsteht_ein_eigener_link(umgebung_ohne_ziel):
    tu.uebernimm(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    ziel = lies(umgebung_ohne_ziel.ziel)
    token = ziel.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                         (TEST,)).fetchone()[0]
    ziel.close()
    assert token and len(token) >= 32
    assert token != f"quelltoken-{QUELLE_CHAT}"


def test_gruppenfelder_der_testgruppe(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    g = ziel.execute("SELECT * FROM gruppe WHERE chat_id = ?", (TEST,)).fetchone()
    assert g["bot_name"] == tu.TEST_BOT_NAME
    assert g["kanal"] == "web"
    assert g["titel"] == "Testgruppe (Kopie von padua-gruppe1)"
    assert g["web_tippt_bis"] is None
    assert g["kostenpause_gemeldet_am"] is None
    assert g["letzte_beantwortete_message_id"] == 103
    assert g["letzte_extrahierte_message_id"] == 103
    assert g["letzte_journalisierte_message_id"] == 101
    assert [z[0] for z in ziel.execute(
        "SELECT bot_name FROM vorfall WHERE chat_id = ?", (TEST,))] == [tu.TEST_BOT_NAME]
    ziel.close()


def test_kein_bot_zustand_der_quelle_im_ziel(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    ziel = lies(umgebung.ziel)
    assert ziel.execute("SELECT COUNT(*) FROM bot_zustand WHERE bot_name = "
                        "'padua-gruppe1'").fetchone()[0] == 0
    ziel.close()


def test_folge_von_web_post_steht_nie_unter_der_hoechsten_id(umgebung_ohne_ziel):
    tu.uebernimm(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    ziel = lies(umgebung_ohne_ziel.ziel)
    seq = ziel.execute("SELECT seq FROM sqlite_sequence WHERE name = 'web_post'").fetchone()[0]
    hoechste = ziel.execute("SELECT MAX(id) FROM web_post").fetchone()[0]
    ziel.close()
    assert seq >= hoechste == 104


def test_backup_enthaelt_die_alte_testgruppe(umgebung):
    bericht = tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    assert bericht["backup"] and Path(bericht["backup"]).exists()
    alt = lies(bericht["backup"])
    assert alt.execute("SELECT COUNT(*) FROM nachricht WHERE chat_id = ? "
                       "AND message_id = 900", (TEST,)).fetchone()[0] == 1
    alt.close()


def test_kein_backup_wenn_es_noch_keine_test_db_gab(umgebung_ohne_ziel):
    bericht = tu.uebernimm(QUELLE_CHAT, **umgebung_ohne_ziel.pfade())
    assert bericht["backup"] is None


def test_keine_temp_kopie_bleibt_liegen(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    reste = [p.name for p in Path(umgebung.ziel).parent.iterdir()
             if p.name.startswith(".testuebernahme-")]
    assert reste == []


def test_verweigert_ohne_die_test_db_anzufassen(umgebung):
    conn = db.verbinde(umgebung.quelle)
    conn.execute("UPDATE aufnahme SET status = 'laeuft' WHERE chat_id = ?", (QUELLE_CHAT,))
    conn.commit()
    conn.close()
    vorher = fingerabdruck_db(umgebung.ziel)
    with pytest.raises(tu.Verweigert):
        tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    assert fingerabdruck_db(umgebung.ziel) == vorher


# --------------------------------------------------------------------------
# Task 4: Bot-Wasserzeichen (E5)
# --------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from interview_theater import bot  # noqa: E402
from interview_theater.web_kanal import WebKanal  # noqa: E402


def _offset(pfad) -> int:
    conn = db.verbinde(pfad)
    try:
        return repo.hole_update_id(conn, tu.TEST_BOT_NAME)
    finally:
        conn.close()


@pytest.mark.parametrize("mit_altem_ziel", [True, False])
def test_kein_uebernommener_eingang_wird_erneut_geliefert(request, mit_altem_ziel):
    u = request.getfixturevalue("umgebung" if mit_altem_ziel else "umgebung_ohne_ziel")
    bericht = tu.uebernimm(QUELLE_CHAT, **u.pfade())
    conn = db.verbinde(u.ziel)
    offset = repo.hole_update_id(conn, tu.TEST_BOT_NAME)
    assert offset == bericht["offset"] == repo.hoechste_web_post_id(conn)
    # mit altem Ziel liegt die Folge bei 900 (alte Testgruppe), sonst bei 104
    assert offset == (900 if mit_altem_ziel else 104)
    kanal = WebKanal(conn, TEST, u.audio_ziel)
    assert kanal.hole_updates(offset + 1, timeout=0) == []          # (a)
    neu = repo.lege_web_post_an(conn, TEST, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="hallo")
    assert neu == offset + 1
    assert [x["update_id"] for x in kanal.hole_updates(offset + 1, timeout=0)] == [neu]  # (b)
    conn.close()


def test_baue_kanal_setzt_den_offset_nicht_zurueck(umgebung):
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    vorher = _offset(umgebung.ziel)
    conn = db.verbinde(umgebung.ziel)
    e = SimpleNamespace(kanal="web", web_chat_id=TEST, bot_name=tu.TEST_BOT_NAME,
                        audio_verz=umgebung.audio_ziel, bot_token="")
    bot.baue_kanal(conn, e, None)
    assert repo.hole_update_id(conn, tu.TEST_BOT_NAME) == vorher
    conn.close()


def test_erkenner_und_journal_stehen_wie_in_der_quelle(umgebung):
    """(c): weder die Historie neu noch eine neue Nachricht uebersprungen --
    die Wasserzeichen sagen im Ziel dasselbe wie in der Quelle."""
    tu.uebernimm(QUELLE_CHAT, **umgebung.pfade())
    src = db.verbinde(umgebung.quelle)
    ziel = db.verbinde(umgebung.ziel)
    for funktion in (repo.unbeantwortete, repo.unextrahierte, repo.unjournalisierte):
        quell_ids = [z["message_id"] for z in funktion(src, QUELLE_CHAT)]
        ziel_ids = [z["message_id"] for z in funktion(ziel, TEST)]
        assert ziel_ids == quell_ids, funktion.__name__
    assert [z["message_id"] for z in repo.unbeantwortete(ziel, TEST)] == []
    neu = repo.lege_web_post_an(ziel, TEST, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="neu")
    repo.merke_nachricht(ziel, TEST, neu, "Gruppe", 0, "text", "neu", ZEIT)
    assert [z["message_id"] for z in repo.unbeantwortete(ziel, TEST)] == [neu]
    assert neu in [z["message_id"] for z in repo.unextrahierte(ziel, TEST)]
    src.close()
    ziel.close()
