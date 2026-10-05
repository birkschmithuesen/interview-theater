"""Eine echte Padua-Gruppe auf die Testinstanz spielen (Karte t_12a734ab).

Birk, 04.10.2026: "Wir werden ueber die Woche hinweg immer wieder 'ne
Testgruppe brauchen, wo wir wahlweise die Datenbank von einer Gruppe
draufspielen koennen."

Die Testinstanz ist eine eigene Datenbank (betrieb/padua-test.db), ein
eigener Webdienst (Port 8031, /padua-test) und ein eigener Bot (padua-test)
mit genau EINER Gruppe: ``TEST_CHAT_ID``. Dieses Skript kopiert den Stand
einer echten Gruppe dorthin. Die Quelle wird nur gelesen (mode=ro). Die ids
bleiben unveraendert -- Knoepfe tragen ids im Freitext (``knopf.wert``), eine
Neuvergabe braeche sie still --, umgeschrieben werden nur chat_id, bot_name,
Token, fluechtige Felder und Audiopfade.

Aufruf (aus dem Repo-Verzeichnis, Testbot VORHER stoppen):

    python -m scripts.test_uebernehmen <quell_chat_id>          # Trockenlauf
    python -m scripts.test_uebernehmen <quell_chat_id> --ja     # wirklich
    python -m scripts.test_uebernehmen --leer [--ja]            # frische Phase 1

Anleitung: docs/testgruppe-padua.md. Ausgegeben werden nur Zaehlungen, nie
Inhalte (Nachrichten, Transkripte, Titel, Namen).

ACHTUNG beim Erweitern: der Dateiname beginnt mit ``test_`` (Vorgabe der
Karte), pytest sammelt das Modul also ein. Keine Funktion und keine Klasse
darf mit ``test``/``Test`` anfangen -- sonst liefe sie als Test
(tests/test_testgruppe_uebernehmen.py haelt das fest).
"""

import argparse
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from interview_theater import db, repo
from interview_theater.web_daten import oeffne_lesend
from scripts.interviews_uebernehmen import laufende_aufnahme

#: Die eine Gruppe der Testinstanz. Fest, damit ein Lauf den vorigen ersetzt
#: und die Env des Testbots (IT_WEB_CHAT_ID) sich nie aendert.
TEST_CHAT_ID = 7_000_000_000_099
TEST_BOT_NAME = "padua-test"

VORGABE_QUELLE = "betrieb/padua.db"
VORGABE_ZIEL = "betrieb/padua-test.db"
VORGABE_AUDIO_QUELLE = "audio-padua"
VORGABE_AUDIO_ZIEL = "audio-padua-test"
VORGABE_URL = "https://lab.artesmobiles.art/padua-test"

#: Was nie Ziel sein darf: die Betriebsdatenbank und ihr Audio (E9).
GESCHUETZT_DB = (VORGABE_QUELLE,)
GESCHUETZT_AUDIO = (VORGABE_AUDIO_QUELLE,)

#: E4: Kostenbuchungen (sonst erbte die Testgruppe die heutigen Ausgaben der
#: Quelle gegen den Tagesdeckel, repo.kostensumme_seit) und fluechtige Stroeme
#: (sonst hinge im Browser ein "laeuft").
NICHT_UEBERNOMMEN = ("aufruf", "web_strom")
UEBERNOMMEN = tuple(t for t in db.TABELLEN_MIT_CHAT_ID if t not in NICHT_UEBERNOMMEN)

#: P2: bot-weite Vorfaelle (chat_id NULL) der Test-DB koennten dieselben ids
#: tragen. Auf vorfall.id zeigt keine Spalte -- also neue ids.
NEUE_IDS = ("vorfall",)

#: Die Spalten, die auf Dateien zeigen (Schema-grep: db.py:139, db.py:1124;
#: web_post.dateiname ist nur ein Anzeigename, web_post.bild ein Name unter
#: interview_theater/static/handys/). Ein Test haelt die Liste am Schema fest.
PFADSPALTEN = (("aufnahme", "audio_pfad"), ("web_post", "datei"))

TITEL_LEER = "Testgruppe"
TITEL_KOPIE = "Testgruppe (Kopie von {bot_name})"

TEXT_AUFNAHME_LAEUFT = (
    "In Gruppe {chat_id} laeuft gerade eine Aufnahme oder der Interviewmodus "
    "ist an. Erst beenden lassen, dann uebernehmen."
)

TEXT_DIENST_LAEUFT = (
    "Der Testbot laeuft (interview-theater@{bot}). Erst stoppen: "
    "systemctl --user stop interview-theater@{bot} -- sonst liefert ihm sein "
    "laufender Poll die uebernommene Historie als neuen Eingang (P1)."
)
TEXT_DANACH = (
    "\nJetzt den Testbot starten: systemctl --user start interview-theater@{bot}\n"
    "Link der Testgruppe: IT_DB={ziel} IT_WEB_URL={url} python scripts/web_links.py"
)
TEXT_NICHTS = "\nNichts geschrieben. Mit --ja ausfuehren (Testbot vorher stoppen)."
TEXT_AUFRUF = (
    "Aufruf: python -m scripts.test_uebernehmen <quell_chat_id> [--ja]\n"
    "    oder python -m scripts.test_uebernehmen --leer [--ja]"
)


class Verweigert(Exception):
    """Ein Grund, nichts zu tun. Der Text geht unveraendert an die Konsole --
    also nie Inhalte hineinschreiben (E10)."""


# --------------------------------------------------------------------------
# Pruefungen
# --------------------------------------------------------------------------


def _gleich(a: str, b: str) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def pruefe_ziel(ziel: str, audio_ziel: str) -> None:
    """Das Ziel ist nie die Betriebsdatenbank und nie das Betriebsaudio --
    weder als Pfad noch als gleichnamige Datei an anderem Ort."""
    for geschuetzt in GESCHUETZT_DB:
        if _gleich(ziel, geschuetzt) or Path(ziel).name == Path(geschuetzt).name:
            raise Verweigert(f"Ziel {ziel} ist die Betriebsdatenbank -- nie.")
    for geschuetzt in GESCHUETZT_AUDIO:
        if _gleich(audio_ziel, geschuetzt) or Path(audio_ziel).name == Path(geschuetzt).name:
            raise Verweigert(f"Audio-Ziel {audio_ziel} ist das Betriebsaudio -- nie.")


def pruefe_pfade(quelle: str, ziel: str, audio_quelle: str, audio_ziel: str) -> None:
    if _gleich(quelle, ziel):
        raise Verweigert("Quelle und Ziel sind dieselbe Datei.")
    if _gleich(audio_quelle, audio_ziel):
        raise Verweigert("Audio-Quelle und Audio-Ziel sind dasselbe Verzeichnis.")
    pruefe_ziel(ziel, audio_ziel)
    if not Path(quelle).exists():
        raise Verweigert(f"Quelle {quelle} gibt es nicht.")


# --------------------------------------------------------------------------
# Lesen (auch im Trockenlauf -- nur mode=ro)
# --------------------------------------------------------------------------


def tabellen(conn) -> set[str]:
    return {z[0] for z in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}


def zaehle(conn, chat_id: int) -> dict[str, int]:
    """Zeilen je uebernommener Tabelle fuer eine Gruppe -- nur Zahlen."""
    vorhanden = tabellen(conn)
    return {
        t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE chat_id = ?",
                        (chat_id,)).fetchone()[0]
        for t in UEBERNOMMEN if t in vorhanden
    }


def fremde_chat_ids(conn) -> dict[int, int]:
    """Jede chat_id ausser der Testgruppe, mit ihrer Zeilenzahl ueber alle
    Tabellen. ``chat_id IS NULL`` (bot-weite Vorfaelle) ist nicht fremd."""
    vorhanden = tabellen(conn)
    fremde: dict[int, int] = {}
    for t in db.TABELLEN_MIT_CHAT_ID:
        if t not in vorhanden:
            continue
        for chat_id, anzahl in conn.execute(
            f"SELECT chat_id, COUNT(*) FROM {t} WHERE chat_id IS NOT NULL "
            "AND chat_id != ? GROUP BY chat_id", (TEST_CHAT_ID,)
        ):
            fremde[int(chat_id)] = fremde.get(int(chat_id), 0) + int(anzahl)
    return fremde


def fremde_text(fremde: dict[int, int]) -> str:
    liste = ", ".join(f"{c} ({n} Zeilen)" for c, n in sorted(fremde.items()))
    return (
        f"Die Test-DB enthaelt fremde Gruppen: {liste}. Das Skript loescht sie "
        "nicht selbst (E1). Aufraeumen je Gruppe, mit der Env der Testinstanz: "
        "set -a; . ./betrieb/padua-test.env; set +a; "
        "python scripts/loeschen.py <chat_id>"
    )


def audio_bestand(verz: Path) -> tuple[int, int]:
    """(Anzahl Dateien, Bytes) unter einem Verzeichnis, 0/0 wenn es fehlt."""
    verz = Path(verz)
    if not verz.exists():
        return 0, 0
    dateien = [p for p in verz.rglob("*") if p.is_file()]
    return len(dateien), sum(p.stat().st_size for p in dateien)


def lies_ziel(ziel: str) -> dict:
    """Die Lage der Test-DB, read-only. Verweigert bei fremden Gruppen."""
    if not Path(ziel).exists():
        return {"existiert": False, "zeilen": {}, "token_vorhanden": False}
    conn = oeffne_lesend(ziel)
    try:
        fremde = fremde_chat_ids(conn)
        if fremde:
            raise Verweigert(fremde_text(fremde))
        zeilen = zaehle(conn, TEST_CHAT_ID)
        token = None
        if "gruppe" in tabellen(conn):
            zeile = conn.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                                 (TEST_CHAT_ID,)).fetchone()
            token = zeile["web_token"] if zeile else None
    finally:
        conn.close()
    return {"existiert": True, "zeilen": zeilen, "token_vorhanden": bool(token)}


def _pruefe_quellgruppe(conn, quell_chat_id: int) -> None:
    zeile = conn.execute("SELECT kanal FROM gruppe WHERE chat_id = ?",
                         (quell_chat_id,)).fetchone()
    if zeile is None:
        raise Verweigert(f"Gruppe {quell_chat_id} gibt es in der Quelle nicht.")
    if zeile["kanal"] != "web":
        raise Verweigert(f"Gruppe {quell_chat_id} ist keine Web-Gruppe (P6).")
    if laufende_aufnahme(conn, quell_chat_id):
        raise Verweigert(TEXT_AUFNAHME_LAEUFT.format(chat_id=quell_chat_id))


def plane(quell_chat_id: int, *, quelle: str, ziel: str, audio_quelle: str,
          audio_ziel: str) -> dict:
    """Was ein Lauf taete -- reine Leseabfrage, Grundlage von Trockenlauf und
    Ernstfall. Verweigert mit ``Verweigert``."""
    if quell_chat_id == TEST_CHAT_ID:
        raise Verweigert("Die Testgruppe kann nicht ihre eigene Quelle sein.")
    pruefe_pfade(quelle, ziel, audio_quelle, audio_ziel)
    src = oeffne_lesend(quelle)
    try:
        _pruefe_quellgruppe(src, quell_chat_id)
        zeilen = zaehle(src, quell_chat_id)
    finally:
        src.close()
    anzahl, groesse = audio_bestand(Path(audio_quelle) / str(quell_chat_id))
    return {
        "quell_chat_id": quell_chat_id,
        "ziel": ziel,
        "zeilen": zeilen,
        "audio_dateien": anzahl,
        "audio_bytes": groesse,
        "ziel_lage": lies_ziel(ziel),
    }


# --------------------------------------------------------------------------
# Schreiben
# --------------------------------------------------------------------------


def neues_token() -> str:
    """Derselbe Ausdruck wie repo.stelle_web_token_sicher (repo.py:146) --
    hier ohne dessen commit, weil es in der Transaktion entsteht (P4)."""
    return secrets.token_urlsafe(repo.WEB_TOKEN_BYTES)


def sichere_ziel(conn, ziel: str, jetzt: datetime) -> str:
    """Backup der Test-DB per VACUUM INTO (P5) -- NIE shutil.copy auf eine
    WAL-Datei: was noch im -wal steht, fehlte der Kopie."""
    pfad = Path(ziel)
    sicherung = pfad.with_name(f"{pfad.name}.bak-{jetzt:%Y%m%d-%H%M%S-%f}")
    conn.execute("VACUUM INTO ?", (str(sicherung),))
    return str(sicherung)


def _token_der_testgruppe(conn) -> str | None:
    zeile = conn.execute("SELECT web_token FROM gruppe WHERE chat_id = ?",
                         (TEST_CHAT_ID,)).fetchone()
    return zeile["web_token"] if zeile and zeile["web_token"] else None


def _schnappschuss(quelle: str, kopie: Path) -> None:
    """Die Quelle als Ganzes in eine Temp-DB -- aus einer mode=ro-Verbindung
    (E2). Die Quelle sieht dabei keinen einzigen Schreibzugriff."""
    src = oeffne_lesend(quelle)
    try:
        src.execute("VACUUM INTO ?", (str(kopie),))
    finally:
        src.close()


def setze_pfad_um(wert: str, quell_chat_id: int, audio_quelle: str,
                  audio_ziel: str) -> str | None:
    """``<audio_quelle>/<quell_chat_id>/REST`` -> ``<audio_ziel>/<TEST>/REST``.

    Relativ bleibt relativ (der Bot schreibt mit seinem relativen IT_AUDIO,
    aufnahme.py:515-518, web_kanal.py:476), absolut bleibt absolut und
    aufgeloest (der Webdienst schreibt so, web_chat.py:4412-4421). None, wenn
    der Pfad nicht unter dem Verzeichnis der Quellgruppe liegt -- dann bleibt
    er stehen und es gibt eine Warnung."""
    alt = Path(wert)
    try:
        rel = alt.resolve().relative_to(Path(audio_quelle).resolve())
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] != str(quell_chat_id):
        return None
    basis = Path(audio_ziel).resolve() if alt.is_absolute() else Path(audio_ziel)
    return str(basis / str(TEST_CHAT_ID) / Path(*rel.parts[1:]))


def kopiere_audio(audio_quelle: str, audio_ziel: str, quell_chat_id: int) -> Path:
    """Kopiert das Audioverzeichnis der Quellgruppe in ein Staging-Verzeichnis
    neben dem Ziel (P3). Die Quelle wird nur gelesen."""
    quelle = Path(audio_quelle) / str(quell_chat_id)
    staging = Path(audio_ziel) / f".neu-{TEST_CHAT_ID}"
    if staging.exists():
        shutil.rmtree(staging)
    if quelle.exists():
        shutil.copytree(quelle, staging)
    else:
        staging.mkdir(parents=True)
    return staging


def tausche_audio(staging: Path, audio_ziel: str) -> None:
    """Nach dem Commit: das alte Audio der Testgruppe weg, Staging an seinen
    Platz. Nur dieses eine Verzeichnis wird geleert (E6)."""
    ziel = Path(audio_ziel) / str(TEST_CHAT_ID)
    if ziel.exists():
        shutil.rmtree(ziel)
    staging.rename(ziel)


def _bereite_kopie_vor(kopie: Path, quell_chat_id: int, token: str, *,
                       audio_quelle: str, audio_ziel: str) -> list[str]:
    """Macht aus der Temp-DB genau die kuenftige Testgruppe: nur die
    Quellgruppe, chat_id umgeschrieben, Token der Testinstanz, fluechtige
    Felder leer, kein bot_zustand, Audiopfade aufs Testverzeichnis. Liefert
    Warnungen (nur Tabelle, Spalte, rowid, Pfad -- keine Inhalte)."""
    warnungen: list[str] = []
    k = db.verbinde(str(kopie))
    try:
        db.initialisiere(k)
        _pruefe_quellgruppe(k, quell_chat_id)  # P9: der Schnappschuss zaehlt
        quell_bot = k.execute("SELECT bot_name FROM gruppe WHERE chat_id = ?",
                              (quell_chat_id,)).fetchone()["bot_name"]
        for t in db.TABELLEN_MIT_CHAT_ID:
            if t in NICHT_UEBERNOMMEN:
                k.execute(f"DELETE FROM {t}")
                continue
            k.execute(f"DELETE FROM {t} WHERE chat_id IS NOT ?", (quell_chat_id,))
        for tabelle, spalte in PFADSPALTEN:
            for zeile in k.execute(
                f"SELECT rowid AS r, {spalte} AS p FROM {tabelle} "
                f"WHERE {spalte} IS NOT NULL"
            ).fetchall():
                if not Path(zeile["p"]).exists():
                    warnungen.append(f"{tabelle}.{spalte} rowid {zeile['r']}: "
                                     f"Datei fehlt ({zeile['p']})")
                neu = setze_pfad_um(zeile["p"], quell_chat_id, audio_quelle, audio_ziel)
                if neu is None:
                    warnungen.append(f"{tabelle}.{spalte} rowid {zeile['r']}: liegt "
                                     f"nicht unter {audio_quelle}/{quell_chat_id} "
                                     "-- unveraendert")
                    continue
                k.execute(f"UPDATE {tabelle} SET {spalte} = ? WHERE rowid = ?",
                          (neu, zeile["r"]))
        for t in UEBERNOMMEN:
            k.execute(f"UPDATE {t} SET chat_id = ? WHERE chat_id = ?",
                      (TEST_CHAT_ID, quell_chat_id))
        k.execute(
            "UPDATE gruppe SET bot_name = ?, titel = ?, web_token = ?, "
            "web_tippt_bis = NULL, kostenpause_gemeldet_am = NULL "
            "WHERE chat_id = ?",
            (TEST_BOT_NAME, TITEL_KOPIE.format(bot_name=quell_bot), token,
             TEST_CHAT_ID),
        )
        k.execute("UPDATE vorfall SET bot_name = ? WHERE bot_name IS NOT NULL",
                  (TEST_BOT_NAME,))
        k.execute("DELETE FROM bot_zustand")
        k.commit()
    finally:
        k.close()
    return warnungen


def _gemeinsame_spalten(conn, tabelle: str) -> list[str]:
    """Spalten, die Ziel UND Kopie kennen (E2), in der Reihenfolge des Ziels;
    bei NEUE_IDS ohne ``id`` (P2)."""
    im_ziel = [z[1] for z in conn.execute(f"PRAGMA main.table_info({tabelle})")]
    in_kopie = {z[1] for z in conn.execute(f"PRAGMA kopie.table_info({tabelle})")}
    return [s for s in im_ziel
            if s in in_kopie and not (tabelle in NEUE_IDS and s == "id")]


def _hebe_folgen(conn) -> None:
    """E1: sqlite_sequence je AUTOINCREMENT-Tabelle auf >= MAX(id). SQLite tut
    das beim Einfuegen mit expliziter id selbst -- hier steht es trotzdem,
    weil eine niedrigere Folge genau die Dortmund-Falle waere (neue
    message_ids unter der Historie)."""
    for (name,) in conn.execute(
        "SELECT name FROM main.sqlite_master WHERE type = 'table' "
        "AND sql LIKE '%AUTOINCREMENT%'"
    ).fetchall():
        hoechste = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM main.{name}").fetchone()[0]
        zeile = conn.execute("SELECT seq FROM main.sqlite_sequence WHERE name = ?",
                             (name,)).fetchone()
        if zeile is None:
            conn.execute("INSERT INTO main.sqlite_sequence (name, seq) VALUES (?, ?)",
                         (name, hoechste))
        elif zeile[0] < hoechste:
            conn.execute("UPDATE main.sqlite_sequence SET seq = ? WHERE name = ?",
                         (hoechste, name))


def _setze_offset(conn, jetzt: datetime) -> int:
    """E5: der Offset des Testbots auf die hoechste je vergebene web_post-id.

    bot.schleife liest ``hole_update_id + 1`` (bot.py:447) und der Web-Kanal
    liefert ``id >= offset`` (repo.py:4471-4483) -- nichts Uebernommenes kommt
    also noch einmal. Die naechste neue Zeile bekommt ``sqlite_sequence + 1``
    und liegt damit darueber. ``bot.baue_kanal`` setzt nur zurueck, wenn der
    Offset UEBER ``hoechste_web_post_id`` liegt (bot.py:540-548) -- er ist hier
    genau gleich. Upsert wie repo.setze_update_id (repo.py:464-473), aber ohne
    dessen commit (P4)."""
    offset = repo.hoechste_web_post_id(conn)
    jetzt_iso = jetzt.isoformat()
    conn.execute(
        "INSERT INTO main.bot_zustand (bot_name, letzte_update_id, gestartet_am, "
        "letzte_aktivitaet_am) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(bot_name) DO UPDATE SET "
        "letzte_update_id = excluded.letzte_update_id, "
        "letzte_aktivitaet_am = excluded.letzte_aktivitaet_am",
        (TEST_BOT_NAME, offset, jetzt_iso, jetzt_iso),
    )
    return offset


def _schreibe_in_ziel(conn, kopie: Path, jetzt: datetime) -> int:
    """E2: in EINER Transaktion die alte Testgruppe loeschen, die Kopie
    einfuegen, die Folge heben und den Offset setzen. Kein db.loesche_gruppe
    und kein repo.setze_update_id -- beide committen (db.py:1471,
    repo.py:474). Liefert den Offset."""
    conn.execute("ATTACH DATABASE ? AS kopie", (str(kopie),))
    try:
        spalten = {t: _gemeinsame_spalten(conn, t) for t in UEBERNOMMEN}
        conn.execute("BEGIN IMMEDIATE")
        try:
            for t in db.TABELLEN_MIT_CHAT_ID:
                conn.execute(f"DELETE FROM main.{t} WHERE chat_id = ?", (TEST_CHAT_ID,))
            for t, namen in spalten.items():
                liste = ", ".join(namen)
                conn.execute(f"INSERT INTO main.{t} ({liste}) SELECT {liste} FROM kopie.{t}")
            _hebe_folgen(conn)
            offset = _setze_offset(conn, jetzt)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.execute("DETACH DATABASE kopie")
    return offset


def uebernimm(quell_chat_id: int, *, quelle: str, ziel: str, audio_quelle: str,
              audio_ziel: str, jetzt: datetime | None = None) -> dict:
    """Der Ernstfall. Verweigert (``Verweigert``) VOR jedem Schreibzugriff.

    Reihenfolge: Schnappschuss -> Kopie vorbereiten (P9-Pruefung) -> Audio
    ins Staging -> Backup -> EINE Transaktion -> Audio tauschen (P3)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    bericht = plane(quell_chat_id, quelle=quelle, ziel=ziel,
                    audio_quelle=audio_quelle, audio_ziel=audio_ziel)
    existierte = Path(ziel).exists()
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    staging = None
    with tempfile.TemporaryDirectory(prefix=".testuebernahme-",
                                     dir=Path(ziel).resolve().parent) as tmp:
        kopie = Path(tmp) / "kopie.db"
        _schnappschuss(quelle, kopie)
        conn = db.verbinde(ziel)
        try:
            db.initialisiere(conn)
            token = _token_der_testgruppe(conn)
            bericht["warnungen"] = _bereite_kopie_vor(
                kopie, quell_chat_id, token or neues_token(),
                audio_quelle=audio_quelle, audio_ziel=audio_ziel)
            staging = kopiere_audio(audio_quelle, audio_ziel, quell_chat_id)
            bericht["backup"] = sichere_ziel(conn, ziel, jetzt) if existierte else None
            bericht["offset"] = _schreibe_in_ziel(conn, kopie, jetzt)
            tausche_audio(staging, audio_ziel)
            staging = None
            bericht["nachher"] = zaehle(conn, TEST_CHAT_ID)
            bericht["token_neu"] = token is None
        finally:
            conn.close()
            if staging is not None and staging.exists():
                shutil.rmtree(staging)
    return bericht


def plane_leer(*, ziel: str, audio_ziel: str) -> dict:
    """Was --leer taete -- reine Leseabfrage."""
    pruefe_ziel(ziel, audio_ziel)
    anzahl, groesse = audio_bestand(Path(audio_ziel) / str(TEST_CHAT_ID))
    return {"ziel": ziel, "ziel_lage": lies_ziel(ziel),
            "audio_dateien": anzahl, "audio_bytes": groesse}


def leere(*, ziel: str, audio_ziel: str, jetzt: datetime | None = None) -> dict:
    """E8: die Testgruppe auf eine frische Phase 1 -- dieselben Felder wie
    scripts/web_gruppe.py anlegen (web_gruppe.py:42-51), aber in EINER
    Transaktion mit fester chat_id und festem Token (P8). Phase 1 heisst:
    keine arbeitsstand-Zeile, phasen.aktuelle liefert dann die erste Phase
    (phasen.py:274-281)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    bericht = plane_leer(ziel=ziel, audio_ziel=audio_ziel)
    existierte = Path(ziel).exists()
    Path(ziel).parent.mkdir(parents=True, exist_ok=True)
    conn = db.verbinde(ziel)
    try:
        db.initialisiere(conn)
        token = _token_der_testgruppe(conn)
        bericht["backup"] = sichere_ziel(conn, ziel, jetzt) if existierte else None
        conn.execute("BEGIN IMMEDIATE")
        try:
            for t in db.TABELLEN_MIT_CHAT_ID:
                conn.execute(f"DELETE FROM main.{t} WHERE chat_id = ?", (TEST_CHAT_ID,))
            conn.execute(
                "INSERT INTO main.gruppe (chat_id, bot_name, titel, "
                "erste_nachricht_am, kanal, web_token) VALUES (?, ?, ?, ?, 'web', ?)",
                (TEST_CHAT_ID, TEST_BOT_NAME, TITEL_LEER, jetzt.isoformat(),
                 token or neues_token()),
            )
            bericht["offset"] = _setze_offset(conn, jetzt)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        bericht["token_neu"] = token is None
    finally:
        conn.close()
    verz = Path(audio_ziel) / str(TEST_CHAT_ID)
    if verz.exists():
        shutil.rmtree(verz)
    return bericht


# --------------------------------------------------------------------------
# Texte (nur Zahlen, E10)
# --------------------------------------------------------------------------


def berichtstext(bericht: dict, trocken: bool) -> str:
    kopf = "Trockenlauf" if trocken else "Uebernommen"
    z = [f"{kopf}: Gruppe {bericht['quell_chat_id']} -> Testgruppe "
         f"{TEST_CHAT_ID} ({bericht['ziel']})",
         "  Zeilen je Tabelle:"]
    z += [f"    {t}: {n}" for t, n in bericht["zeilen"].items() if n]
    z.append(f"  Nicht uebernommen: {', '.join(NICHT_UEBERNOMMEN)}")
    z.append(f"  Audio: {bericht['audio_dateien']} Datei(en), "
             f"{bericht['audio_bytes']} Bytes")
    lage = bericht["ziel_lage"]
    if lage["existiert"]:
        z.append(f"  Bisherige Testgruppe: {sum(lage['zeilen'].values())} "
                 "Zeile(n) -- wird ersetzt")
    else:
        z.append("  Test-DB gibt es noch nicht -- wird angelegt")
    z.append("  Link der Testgruppe: "
             + ("bleibt gleich" if lage["token_vorhanden"] else "wird neu erzeugt"))
    if not trocken:
        if bericht.get("backup"):
            z.append(f"  Backup: {bericht['backup']}")
        if "offset" in bericht:
            z.append(f"  Offset von {TEST_BOT_NAME}: {bericht['offset']}")
        for warnung in bericht.get("warnungen", []):
            z.append(f"  WARNUNG: {warnung}")
    return "\n".join(z)


def leer_berichtstext(bericht: dict, trocken: bool) -> str:
    kopf = "Trockenlauf --leer" if trocken else "Geleert"
    lage = bericht["ziel_lage"]
    z = [f"{kopf}: Testgruppe {TEST_CHAT_ID} ({bericht['ziel']}) -> frische Phase 1"]
    if lage["existiert"]:
        z.append("  Zeilen der Testgruppe, die wegfallen:")
        z += [f"    {t}: {n}" for t, n in lage["zeilen"].items() if n]
    else:
        z.append("  Test-DB gibt es noch nicht -- wird angelegt")
    z.append(f"  Audio der Testgruppe, das wegfaellt: {bericht['audio_dateien']} "
             f"Datei(en), {bericht['audio_bytes']} Bytes")
    z.append("  Link der Testgruppe: "
             + ("bleibt gleich" if lage["token_vorhanden"] else "wird neu erzeugt"))
    if not trocken:
        if bericht.get("backup"):
            z.append(f"  Backup: {bericht['backup']}")
        z.append(f"  Offset von {TEST_BOT_NAME}: {bericht['offset']}")
    return "\n".join(z)


# --------------------------------------------------------------------------
# Einstieg
# --------------------------------------------------------------------------


def dienst_laeuft(bot_name: str) -> bool:
    """Laeuft die Unit des Testbots? (P1) Ohne systemctl (Entwicklungsrechner)
    gilt sie als gestoppt."""
    try:
        ergebnis = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet",
             f"interview-theater@{bot_name}"],
            check=False, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return ergebnis.returncode == 0


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.test_uebernehmen",
        description="Spielt eine Padua-Gruppe auf die Testinstanz "
                    f"(chat_id {TEST_CHAT_ID}) oder setzt sie zurueck.",
    )
    zerleger.add_argument("quell_chat_id", nargs="?", type=int)
    zerleger.add_argument("--ja", action="store_true", help="wirklich schreiben")
    zerleger.add_argument("--leer", action="store_true", help="frische Phase 1")
    zerleger.add_argument("--quelle", default=VORGABE_QUELLE)
    zerleger.add_argument("--ziel", default=VORGABE_ZIEL)
    zerleger.add_argument("--audio-quelle", default=VORGABE_AUDIO_QUELLE)
    zerleger.add_argument("--audio-ziel", default=VORGABE_AUDIO_ZIEL)
    a = zerleger.parse_args(argv)
    if a.leer == (a.quell_chat_id is not None):
        print(TEXT_AUFRUF)
        return 1
    try:
        if a.ja and dienst_laeuft(TEST_BOT_NAME):
            raise Verweigert(TEXT_DIENST_LAEUFT.format(bot=TEST_BOT_NAME))
        if a.leer:
            if a.ja:
                bericht = leere(ziel=a.ziel, audio_ziel=a.audio_ziel)
            else:
                bericht = plane_leer(ziel=a.ziel, audio_ziel=a.audio_ziel)
            print(leer_berichtstext(bericht, trocken=not a.ja))
        else:
            pfade = {"quelle": a.quelle, "ziel": a.ziel,
                     "audio_quelle": a.audio_quelle, "audio_ziel": a.audio_ziel}
            if a.ja:
                bericht = uebernimm(a.quell_chat_id, **pfade)
            else:
                bericht = plane(a.quell_chat_id, **pfade)
            print(berichtstext(bericht, trocken=not a.ja))
    except Verweigert as fehler:
        print(f"Verweigert: {fehler}")
        return 1
    if a.ja:
        print(TEXT_DANACH.format(bot=TEST_BOT_NAME, ziel=a.ziel, url=VORGABE_URL))
    else:
        print(TEXT_NICHTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
