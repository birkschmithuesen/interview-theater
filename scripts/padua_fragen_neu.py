"""Die Fragen-Sortierung einer Padua-Gruppe (Phase 2) neu oeffnen.

Birk, 05.10.2026 (docs/superpowers/plans/2026-10-05-auswahlliste-cothinker.md,
Task 4): eine Gruppe hat die Phase-2-Auswahl schon durchentschieden (jede
Frage ja/nein/schaerfen) -- morgens soll jemand ohne Python-Kenntnisse die
Liste neu aufmachen koennen, ohne die Fragen selbst zu verlieren.

Setzt ``arbeitsstand.fragen_entschieden``, ``fragen_aktuell`` und
``fragen_warte_auf`` auf ``NULL`` -- die Karten-/CoThinker-Sortierung
(``auswahl.fragen_liste``, ``knoepfe.fragen``) sieht danach wieder jede
Frage als offen. ``fragen_auswahl``/``fragen_herkunft`` (die Fragetexte
selbst) bleiben unveraendert, ausser ``--ki-neu`` ist gesetzt.

``--ki-neu``: erzeugt einen frischen isolierten KI-Fragen-Lauf auf den
AKTUELLEN Begriffen (dieselben Bausteine wie der Hintergrundlauf aus
``fragen_ki.starte``, hier synchron und ohne dessen Einmal-Sperre -- dieser
Lauf soll ausdruecklich neu erzeugen) und baut ``fragen_auswahl`` +
``fragen_herkunft`` aus den eigenen Fragen der Gruppe
(``fragen_eigene_vorschlag``) und den neuen KI-Fragen neu zusammen, in
derselben Reihenfolge und mit demselben Begriffsabgleich wie
``knoepfe.fragen.versuche_gegenueberstellung`` (ueber deren Helfer
``_ordne_zeilen`` -- keine zweite Begriffs-Erkennung).

**Kostet Geld nur mit ``--ki-neu`` UND ``--apply`` zusammen** -- der
Trockenlauf meldet mit ``--ki-neu`` nur, was er TAETE, ohne das Modell zu
rufen (E1, dasselbe Prinzip wie ``scripts/rauchtest.py`` & Co: ein
Modellaufruf steht nie stillschweigend in einem Trockenlauf).

Aufruf (aus dem Hauptcheckout):

    uv run --extra dev python -m scripts.padua_fragen_neu <chat_id>                      # Trockenlauf
    uv run --extra dev python -m scripts.padua_fragen_neu <chat_id> --apply              # wirklich
    uv run --extra dev python -m scripts.padua_fragen_neu <chat_id> --ki-neu --apply      # + neue KI-Fragen
    uv run --extra dev python -m scripts.padua_fragen_neu <chat_id> --db betrieb/anderebot.db

Sicherung: ``--apply`` schreibt zuerst per ``VACUUM INTO`` eine Kopie der
gesamten Datenbank nach ``<db-Verzeichnis>/backup/padua-<chat_id>-<Zeit>.db``
-- VOR jedem Schreibzugriff. ``VACUUM INTO`` statt ``shutil.copy``, weil die
Betriebsdatenbank im WAL-Modus laeuft (siehe ``scripts/test_uebernehmen.py``,
dieselbe Begruendung): eine blosse Dateikopie saehe nicht, was noch in der
``-wal``-Datei steht.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from interview_theater import anweisungen, db, fragen_ki, modellwahl, phasen, repo, roadmap, vorschlag
from interview_theater import auswahl as auswahl_modul
from interview_theater import begriffe as begriffe_modul
from interview_theater.knoepfe.fragen import _ordne_zeilen
from interview_theater.web_daten import oeffne_lesend

VORGABE_DB = "betrieb/padua.db"


class Verweigert(Exception):
    """Ein Grund, nichts zu tun. Der Text geht unveraendert an die Konsole
    -- also nie Inhalte hineinschreiben (Nachrichtentexte, Fragetexte)."""


# --------------------------------------------------------------------------
# Lesen (auch im Trockenlauf -- nur mode=ro)
# --------------------------------------------------------------------------


def zustand(conn, chat_id: int) -> dict:
    """Phase und Entscheidungs-Zaehler einer Gruppe -- reine Leseabfrage,
    funktioniert auch auf einer ``mode=ro``-Verbindung. Verweigert, wenn es
    die Gruppe in dieser Datenbank nicht gibt."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is None:
        raise Verweigert(f"Gruppe {chat_id} gibt es in dieser Datenbank nicht.")
    stand = repo.hole_arbeitsstand(conn, chat_id)
    liste = auswahl_modul.fragen_liste(stand)
    return {"chat_id": chat_id, "phase": phasen.aktuelle(conn, chat_id),
            "zaehler": liste["zaehler"]}


def _zaehler_text(z: dict) -> str:
    return f"ja={z['ja']} nein={z['nein']} schaerfen={z['schaerfen']} offen={z['offen']}"


def _anzahl(z: dict) -> int:
    return sum(z.values())


# --------------------------------------------------------------------------
# --ki-neu: der eine Modellaufruf, und die Neu-Zusammenstellung der Auswahl
# --------------------------------------------------------------------------


def ki_fragen_erzeugen(conn, chat_id: int, stand) -> str:
    """Der EINE Modellaufruf dieses Skripts -- dieselben Bausteine wie der
    Thread-Koerper von ``fragen_ki.starte`` (``_nutzertext``, ``SCHEMA``,
    ``ART``), hier synchron und ohne dessen Idempotenz-Sperre: ``--ki-neu``
    soll ausdruecklich neu erzeugen, auch wenn schon ein Vorschlag steht.
    Baut Einstellungen und Modell-Client selbst, also NICHT aufgerufen,
    bevor nicht feststeht, dass wirklich ``--ki-neu --apply`` beide gesetzt
    sind (``fuehre_aus``) -- der einzige Aufrufer."""
    import httpx

    from interview_theater import einstellungen, llm

    e = einstellungen.laden()
    klm = llm.LLM(e, httpx.Client(timeout=60.0), conn)

    begriffe_feld = stand["begriffe"] if stand is not None else ""
    diskussion_text = repo.diskussion_verdichtung_text(conn, chat_id)
    begriffe_detail = roadmap.begriffe_detail(stand)
    sprache_fragen = fragen_ki.interviewsprache(stand)
    nutzertext = fragen_ki._nutzertext(
        begriffe_feld or "", diskussion_text, begriffe_detail, sprache_fragen)
    ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id,
        system=anweisungen.hole(fragen_ki.ART),
        nutzer=nutzertext, schema=fragen_ki.SCHEMA, art=fragen_ki.ART,
        ueber_claude=ueber_claude,
    )
    return (ergebnis.get("antwort") or "").strip()


def baue_auswahl(begriffe_feld: str, eigene_roh: str, ki_roh: str) -> tuple[str, str]:
    """Baut ``fragen_auswahl``/``fragen_herkunft`` aus den eigenen Fragen der
    Gruppe und den (neuen) KI-Fragen -- dieselbe Zuordnung und Reihenfolge
    wie ``knoepfe.fragen.versuche_gegenueberstellung`` (je Begriff zuerst die
    eigene Frage, dann die KI-Frage; danach die Zeilen ohne erkennbaren
    Begriff, erst eigen dann KI), ueber deren Helfer ``_ordne_zeilen`` --
    keine zweite, eigene Begriffs-Erkennung."""
    begriffe = begriffe_modul.zerlege(begriffe_feld or "")
    eigene_je_begriff, eigene_rest = _ordne_zeilen(begriffe, vorschlag.zeilen(eigene_roh or ""))
    ki_je_begriff, ki_rest = _ordne_zeilen(begriffe, vorschlag.zeilen(ki_roh or ""))

    zeilen: list[str] = []
    herkunft: list[str] = []
    for begriff in begriffe:
        for zeile in eigene_je_begriff.get(begriff, []):
            zeilen.append(zeile)
            herkunft.append("eigen")
        for zeile in ki_je_begriff.get(begriff, []):
            zeilen.append(zeile)
            herkunft.append("ki")
    for zeile in eigene_rest:
        zeilen.append(zeile)
        herkunft.append("eigen")
    for zeile in ki_rest:
        zeilen.append(zeile)
        herkunft.append("ki")
    return "\n".join(zeilen), ",".join(herkunft)


# --------------------------------------------------------------------------
# --apply: Sicherung, optional neue KI-Fragen, dann zuruecksetzen
# --------------------------------------------------------------------------


def sicherungspfad(db_pfad: str, chat_id: int, jetzt: datetime) -> Path:
    ordner = Path(db_pfad).resolve().parent / "backup"
    return ordner / f"padua-{chat_id}-{jetzt:%Y%m%d-%H%M%S}.db"


def fuehre_aus(conn, db_pfad: str, chat_id: int, *, ki_neu: bool,
              jetzt: datetime | None = None) -> dict:
    """Der Ernstfall. Verweigert (``Verweigert``) VOR jedem Schreibzugriff.

    Reihenfolge: Sicherung -> (bei ``ki_neu``) neuer KI-Lauf und neu
    zusammengestellte Auswahl -> die drei Felder der laufenden Sortierung
    auf ``NULL``. ``fragen_auswahl``/``fragen_herkunft`` bleiben ohne
    ``ki_neu`` unangetastet."""
    jetzt = jetzt or datetime.now(timezone.utc)
    if repo.hole_gruppe(conn, chat_id) is None:
        raise Verweigert(f"Gruppe {chat_id} gibt es in dieser Datenbank nicht.")

    sicherung = sicherungspfad(db_pfad, chat_id, jetzt)
    sicherung.parent.mkdir(parents=True, exist_ok=True)
    conn.execute("VACUUM INTO ?", (str(sicherung),))

    ki_erzeugt = False
    if ki_neu:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        ki_antwort = ki_fragen_erzeugen(conn, chat_id, stand)
        begriffe_feld = stand["begriffe"] if stand is not None else ""
        eigene_roh = stand["fragen_eigene_vorschlag"] if stand is not None else ""
        auswahl_text, herkunft_text = baue_auswahl(begriffe_feld, eigene_roh, ki_antwort)
        repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", auswahl_text)
        repo.setze_arbeitsstand(conn, chat_id, "fragen_herkunft", herkunft_text)
        ki_erzeugt = True

    # Fix 05.10.2026: leer, aber nicht NULL ("," * (n-1)) -- so ist die
    # Sortierung wieder offen (``auswahl.sortierung_offen``), auch wenn
    # ``fragen`` aus der vorigen Runde schon steht.
    stand = repo.hole_arbeitsstand(conn, chat_id)
    anzahl = len(vorschlag.zeilen((stand["fragen_auswahl"] if stand else "") or ""))
    repo.setze_arbeitsstand(
        conn, chat_id, "fragen_entschieden", "," * max(anzahl - 1, 0),
    )
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)

    return {"backup": str(sicherung), "ki_erzeugt": ki_erzeugt,
            "nachher": zustand(conn, chat_id)}


# --------------------------------------------------------------------------
# Texte (nur Zahlen und Pfade, keine Fragetexte/Nachrichten -- E10)
# --------------------------------------------------------------------------


def berichtstext_trocken(vorher: dict, ki_neu: bool, db_pfad: str) -> str:
    anzahl = _anzahl(vorher["zaehler"])
    nachher_vorhersage = {"ja": 0, "nein": 0, "schaerfen": 0, "offen": anzahl}
    zeilen = [
        f"Trockenlauf: Gruppe {vorher['chat_id']} ({db_pfad})",
        f"  Phase: {vorher['phase']}",
        f"  Fragen aktuell: {anzahl}",
        f"  Entscheidungen jetzt: {_zaehler_text(vorher['zaehler'])}",
        f"  Entscheidungen nach --apply: {_zaehler_text(nachher_vorhersage)}",
    ]
    if ki_neu:
        zeilen.append(
            "  --ki-neu: wuerde die KI-Fragen neu erzeugen (ein Modellaufruf, "
            "kostet Geld) und fragen_auswahl/fragen_herkunft neu "
            "zusammenstellen -- im Trockenlauf kein Aufruf.")
    zeilen.append("  Nichts geschrieben. Mit --apply ausfuehren.")
    return "\n".join(zeilen)


def berichtstext_apply(vorher: dict, ergebnis: dict, db_pfad: str) -> str:
    nachher = ergebnis["nachher"]
    zeilen = [
        f"Ausgefuehrt: Gruppe {vorher['chat_id']} ({db_pfad})",
        f"  Sicherung: {ergebnis['backup']}",
        f"  Entscheidungen vorher: {_zaehler_text(vorher['zaehler'])}",
        f"  Entscheidungen nachher: {_zaehler_text(nachher['zaehler'])}",
    ]
    if ergebnis["ki_erzeugt"]:
        zeilen.append("  KI-Fragen neu erzeugt, Auswahl neu zusammengestellt.")
    else:
        zeilen.append("  Fragetexte unveraendert (ohne --ki-neu).")
    return "\n".join(zeilen)


# --------------------------------------------------------------------------
# Einstieg
# --------------------------------------------------------------------------


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.padua_fragen_neu",
        description="Oeffnet die Fragen-Sortierung einer Padua-Gruppe (Phase 2) "
                    "neu: Entscheidungen zuruecksetzen, optional KI-Fragen neu "
                    "erzeugen.",
    )
    zerleger.add_argument("chat_id", type=int)
    zerleger.add_argument("--db", default=VORGABE_DB, help="Vorgabe: betrieb/padua.db")
    zerleger.add_argument("--ki-neu", action="store_true",
                          help="KI-Fragen neu erzeugen (Modellaufruf, nur mit --apply)")
    zerleger.add_argument("--apply", action="store_true", help="wirklich schreiben")
    a = zerleger.parse_args(argv)

    try:
        if not Path(a.db).exists():
            raise Verweigert(f"Datenbank {a.db} gibt es nicht.")
        if not a.apply:
            conn = oeffne_lesend(a.db)
            try:
                vorher = zustand(conn, a.chat_id)
            finally:
                conn.close()
            print(berichtstext_trocken(vorher, a.ki_neu, a.db))
            return 0

        conn = db.verbinde(a.db)
        try:
            # Kein ``db.initialisiere`` hier: das ist ein Schreibzugriff
            # (Migration) VOR der Sicherung; die Betriebs-DB ist vom Bot
            # laengst initialisiert (Review 05.10.2026).
            vorher = zustand(conn, a.chat_id)
            ergebnis = fuehre_aus(conn, a.db, a.chat_id, ki_neu=a.ki_neu)
        finally:
            conn.close()
        print(berichtstext_apply(vorher, ergebnis, a.db))
        return 0
    except Verweigert as fehler:
        print(f"Verweigert: {fehler}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
