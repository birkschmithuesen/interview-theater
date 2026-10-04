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

from pathlib import Path

from interview_theater import db
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

TITEL_LEER = "Testgruppe"
TITEL_KOPIE = "Testgruppe (Kopie von {bot_name})"

TEXT_AUFNAHME_LAEUFT = (
    "In Gruppe {chat_id} laeuft gerade eine Aufnahme oder der Interviewmodus "
    "ist an. Erst beenden lassen, dann uebernehmen."
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
