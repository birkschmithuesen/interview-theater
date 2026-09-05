"""Betriebsskript: uebernimmt Interviews aus anderen Gruppen in EINE Gruppe.

Der Anlass (Birk, 05.09.2026 abends): am Ende von Tag 2 arbeitet nur noch eine
Gruppe weiter, und die soll auf ALLES zugreifen koennen, was an beiden Tagen
aufgenommen wurde. Bisher ist jede Gruppe eine Insel -- jede Tabelle traegt
``chat_id`` (AGENTS.md, ``db.TABELLEN_MIT_CHAT_ID``), und kein Leser blickt
ueber die eigene Gruppe hinaus.

Was wandert: **nur Material.** Je Quellinterview der Kopf
(``klasse='lang'``, ``teil_von IS NULL``, ``entfernt_am IS NULL``) samt allen
Teilen, dazu Verdichtung und ``verdichtung_thema`` inklusive
``zitat_geprueft``, dazu die Audiodateien. Kein Modellaufruf, nirgends.

Was NICHT wandert: Arbeitsstand, Figuren, Szenen, Knoepfe, Nachrichten,
Journal, Kernzitate, Sprachprofile, Schaerfungen. Das ist die Arbeit der
Quellgruppe an ihrem Material, nicht das Material. ``zum_kernthema_am`` wird
beim Import auf NULL gesetzt -- welche Themen zur Kernfrage der ZIELgruppe
passen, entscheidet deren eigener Kernthema-Filter, nicht der der Quelle.

Die Quellen bleiben unangetastet. Es wird kopiert, nicht verschoben: die
Gruppe, die ein Interview gefuehrt hat, behaelt es.

Nummerierung: ``kontext.interviewbezeichnung`` zaehlt die Koepfe einer Gruppe
in ``id``-Reihenfolge (``repo.transkripte`` sortiert ``ORDER BY id ASC``).
Neue Zeilen bekommen hoehere ids als alle vorhandenen -- uebernommene
Interviews landen damit automatisch HINTER den eigenen, und ``empfangen_am``
darf unveraendert aus der Quelle mitkommen (es geht in keine Sortierung ein,
die Interviews betrifft). Ein eigenes Interview der Zielgruppe behaelt seine
Nummer.

``name`` wird beim Import auf ``Interview <neue Nummer>`` gesetzt und nie aus
der Quelle uebernommen: dort kann ein Klarname stehen (``lege_aufnahme_an``
vergibt zwar 'Interview n', ``/name`` und der Erkenner duerfen ihn aber
ueberschreiben), und ein Klarname gehoert weder in den Prompt der anderen
Gruppe noch auf deren Gruppenseite.

Idempotenz: jede uebernommene Zeile traegt ``uebernommen_von`` in der Form
``"<quell_chat_id>:<alte_aufnahme_id>"``. Ein zweiter Lauf ueberspringt, was
diesen Marker schon traegt. Alles laeuft in EINER Transaktion; bei einem
Fehler wird zurueckgerollt (die schon kopierten Audiodateien bleiben liegen --
sie sind ohne DB-Zeile wirkungslos und werden beim naechsten Lauf
ueberschrieben).

Aufruf (Env der ZIELgruppe laden -- ihr Bot schreibt die Zeile in den Chat):

    set -a; . ./betrieb/gruppe1.env; set +a
    python -m scripts.interviews_uebernehmen <ziel_chat_id> <quelle> [<quelle> ...]         # Trockenlauf
    python -m scripts.interviews_uebernehmen <ziel_chat_id> <quelle> [<quelle> ...] --ja    # wirklich

Ohne ``--ja`` wird nichts geschrieben, nichts kopiert und nichts gesendet --
nur gezaehlt.
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, einstellungen, repo  # noqa: E402
from interview_theater.telegram import Telegram  # noqa: E402

#: Der Name, den ein uebernommenes Interview in der Zielgruppe traegt. Die
#: Nummer haengt hinten dran und kommt aus der laufenden Zaehlung der
#: Zielgruppe, nicht aus der Quelle.
NAME_VORSATZ = "Interview"


def marker(quelle_chat_id: int, aufnahme_id: int) -> str:
    """Der Herkunftsstempel einer uebernommenen Zeile."""
    return f"{quelle_chat_id}:{aufnahme_id}"


def _jetzt() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Lesen (auch im Trockenlauf)
# --------------------------------------------------------------------------


def quellinterviews(conn, quelle_chat_id: int) -> list:
    """Die uebernehmbaren Interviews einer Quellgruppe: Koepfe, nicht
    entfernt, nicht selbst schon uebernommen.

    Ein schon uebernommenes Interview wandert bewusst nicht weiter -- sonst
    entstuende beim Ketten-Import (A -> B, danach B -> C) eine zweite Kopie
    desselben Materials mit falscher Herkunft."""
    return conn.execute(
        "SELECT * FROM aufnahme WHERE chat_id = ? AND klasse = 'lang' "
        "AND teil_von IS NULL AND entfernt_am IS NULL "
        "AND uebernommen_von IS NULL ORDER BY id ASC",
        (quelle_chat_id,),
    ).fetchall()


def schon_uebernommen(conn, ziel_chat_id: int) -> set[str]:
    """Die Herkunftsstempel, die in der Zielgruppe schon liegen."""
    return {
        z["uebernommen_von"]
        for z in conn.execute(
            "SELECT uebernommen_von FROM aufnahme WHERE chat_id = ? "
            "AND uebernommen_von IS NOT NULL",
            (ziel_chat_id,),
        )
    }


def laufende_aufnahme(conn, chat_id: int) -> bool:
    """True, wenn in dieser Gruppe gerade ein Interview laeuft oder der
    Interviewmodus an ist.

    Der Vorher-Check: waehrend eine Aufnahme laeuft, ist ein Interview noch
    nicht vollstaendig (Teile fehlen, das zusammengefuegte Transkript und die
    Verdichtung gibt es noch nicht). Eine halbe Kopie waere in der Zielgruppe
    nicht mehr zu heilen -- der Nachhol-Arbeiter der Quelle wuerde nur die
    Quelle fertigstellen."""
    if conn.execute(
        "SELECT 1 FROM aufnahme WHERE chat_id = ? AND status = 'laeuft' "
        "AND entfernt_am IS NULL LIMIT 1",
        (chat_id,),
    ).fetchone():
        return True
    zeile = conn.execute(
        "SELECT interviewmodus_seit FROM gruppe WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return bool(zeile and zeile["interviewmodus_seit"])


def _zaehle_material(conn, kopf_ids: list[int]) -> dict:
    """Teile, Verdichtungen, Themen, geprueferte Zitate und Audiodateien zu
    einer Menge von Interview-Koepfen."""
    zahlen = {"teile": 0, "verdichtungen": 0, "themen": 0, "zitate": 0, "audio": 0}
    for kopf_id in kopf_ids:
        teile = conn.execute(
            "SELECT * FROM aufnahme WHERE teil_von = ? ORDER BY id ASC", (kopf_id,)
        ).fetchall()
        zahlen["teile"] += len(teile)
        zahlen["audio"] += sum(1 for t in teile if t["audio_pfad"])
        for v in conn.execute(
            "SELECT id FROM verdichtung WHERE aufnahme_id = ? AND entfernt_am IS NULL",
            (kopf_id,),
        ).fetchall():
            zahlen["verdichtungen"] += 1
            for t in conn.execute(
                "SELECT zitat_geprueft FROM verdichtung_thema WHERE verdichtung_id = ?",
                (v["id"],),
            ):
                zahlen["themen"] += 1
                zahlen["zitate"] += 1 if t["zitat_geprueft"] else 0
    return zahlen


def plane(conn, ziel_chat_id: int, quellen: list[int]) -> dict:
    """Was ein Lauf tun wuerde -- die gemeinsame Grundlage von Trockenlauf und
    Ernstfall. Reine Leseabfrage."""
    bekannt = schon_uebernommen(conn, ziel_chat_id)
    vorhanden = repo.zaehle_interviews(conn, ziel_chat_id)
    naechste_nummer = vorhanden + 1
    posten = []
    for quelle in quellen:
        koepfe = quellinterviews(conn, quelle)
        neu = [k for k in koepfe if marker(quelle, k["id"]) not in bekannt]
        uebersprungen = len(koepfe) - len(neu)
        zahlen = _zaehle_material(conn, [k["id"] for k in neu])
        nummern = list(range(naechste_nummer, naechste_nummer + len(neu)))
        naechste_nummer += len(neu)
        posten.append(
            {
                "chat_id": quelle,
                "bot_name": _bot_name(conn, quelle),
                "koepfe": neu,
                "interviews": len(neu),
                "schon_da": uebersprungen,
                "nummern": nummern,
                **zahlen,
            }
        )
    return {
        "ziel": ziel_chat_id,
        "vorhanden": vorhanden,
        "posten": posten,
        "neu_gesamt": sum(p["interviews"] for p in posten),
        "nachher": naechste_nummer - 1,
    }


def _bot_name(conn, chat_id: int) -> str:
    zeile = conn.execute(
        "SELECT bot_name FROM gruppe WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return (zeile["bot_name"] if zeile and zeile["bot_name"] else str(chat_id))


# --------------------------------------------------------------------------
# Schreiben
# --------------------------------------------------------------------------

#: Die Spalten einer aufnahme-Zeile, die beim Import mitkommen. Bewusst als
#: Liste und nicht als "SELECT *": ``id``, ``chat_id``, ``name``, ``teil_von``
#: und die beiden uebernommen_*-Spalten werden neu gesetzt, und eine spaeter
#: hinzukommende Spalte soll nicht stillschweigend mitwandern.
_AUFNAHME_SPALTEN = (
    "message_id", "klasse", "quelle", "audio_pfad", "transkript",
    "dauer_sekunden", "status", "fehlertext", "versuche", "empfangen_am",
    "beendet_am",
)


def _kopiere_aufnahme(conn, zeile, ziel_chat_id, name, teil_von, stempel, zeit) -> int:
    werte = [zeile[s] for s in _AUFNAHME_SPALTEN]
    spalten = ", ".join(_AUFNAHME_SPALTEN)
    platzhalter = ", ".join("?" for _ in _AUFNAHME_SPALTEN)
    cur = conn.execute(
        f"INSERT INTO aufnahme (chat_id, name, teil_von, uebernommen_von, "
        f"uebernommen_am, {spalten}) VALUES (?, ?, ?, ?, ?, {platzhalter})",
        [ziel_chat_id, name, teil_von, stempel, zeit, *werte],
    )
    return cur.lastrowid


def audio_zieldatei(audio_verz: str, ziel_chat_id: int, stempel: str) -> Path:
    """Der Zielpfad einer uebernommenen Audiodatei.

    Nicht ``<message_id>.ogg`` wie im Regelbetrieb (``aufnahme.py``): zwei
    Gruppen koennen dieselbe ``message_id`` tragen, und die Datei der einen
    duerfte die der anderen nie ueberschreiben. Der Herkunftsstempel ist je
    Datei eindeutig und macht den Import ausserdem wiederholbar."""
    return Path(audio_verz) / str(ziel_chat_id) / f"uebernommen-{stempel.replace(':', '-')}.ogg"


def uebernimm(
    conn, ziel_chat_id: int, quellen: list[int], audio_verz: str,
    warnungen: list[str] | None = None,
) -> dict:
    """Fuehrt den Import aus -- alles in EINER Transaktion.

    Liefert denselben Bericht wie ``plane``, ergaenzt um die tatsaechlich
    kopierten Audiodateien. Bei einer Ausnahme wird zurueckgerollt."""
    warnungen = warnungen if warnungen is not None else []
    bericht = plane(conn, ziel_chat_id, quellen)
    zeit = _jetzt()
    nummer = bericht["vorhanden"]
    kopiert = 0
    try:
        conn.execute("BEGIN")
        for posten in bericht["posten"]:
            for kopf in posten["koepfe"]:
                nummer += 1
                stempel = marker(posten["chat_id"], kopf["id"])
                neuer_kopf = _kopiere_aufnahme(
                    conn, kopf, ziel_chat_id, f"{NAME_VORSATZ} {nummer}",
                    None, stempel, zeit,
                )
                kopiert += _kopiere_teile(
                    conn, kopf, posten["chat_id"], ziel_chat_id, neuer_kopf,
                    zeit, audio_verz, warnungen,
                )
                _kopiere_verdichtungen(
                    conn, kopf["id"], ziel_chat_id, neuer_kopf, zeit
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    bericht["kopierte_audio"] = kopiert
    return bericht


def _kopiere_teile(
    conn, kopf, quelle_chat_id, ziel_chat_id, neuer_kopf, zeit, audio_verz, warnungen
) -> int:
    kopiert = 0
    teile = conn.execute(
        "SELECT * FROM aufnahme WHERE teil_von = ? ORDER BY id ASC", (kopf["id"],)
    ).fetchall()
    for teil in teile:
        stempel = marker(quelle_chat_id, teil["id"])
        neuer_teil = _kopiere_aufnahme(
            conn, teil, ziel_chat_id, None, neuer_kopf, stempel, zeit
        )
        if not teil["audio_pfad"]:
            continue
        quelle_datei = Path(teil["audio_pfad"])
        ziel_datei = audio_zieldatei(audio_verz, ziel_chat_id, stempel)
        if not quelle_datei.exists():
            warnungen.append(f"Audiodatei fehlt: {quelle_datei} (Teil {teil['id']})")
            continue
        ziel_datei.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(quelle_datei, ziel_datei)
        conn.execute(
            "UPDATE aufnahme SET audio_pfad = ? WHERE id = ?",
            (str(ziel_datei), neuer_teil),
        )
        kopiert += 1
    return kopiert


def _kopiere_verdichtungen(conn, alter_kopf: int, ziel_chat_id: int, neuer_kopf: int, zeit) -> None:
    for v in conn.execute(
        "SELECT * FROM verdichtung WHERE aufnahme_id = ? AND entfernt_am IS NULL "
        "ORDER BY id ASC",
        (alter_kopf,),
    ).fetchall():
        cur = conn.execute(
            "INSERT INTO verdichtung (chat_id, aufnahme_id, zusammenfassung, erstellt_am) "
            "VALUES (?, ?, ?, ?)",
            (ziel_chat_id, neuer_kopf, v["zusammenfassung"], v["erstellt_am"]),
        )
        neue_v = cur.lastrowid
        for t in conn.execute(
            "SELECT * FROM verdichtung_thema WHERE verdichtung_id = ? ORDER BY id ASC",
            (v["id"],),
        ).fetchall():
            # zum_kernthema_am bleibt NULL: das ist eine Entscheidung der
            # Quellgruppe ueber ihre Kernfrage, nicht ueber die der Zielgruppe.
            conn.execute(
                "INSERT INTO verdichtung_thema (chat_id, verdichtung_id, thema, kurz, "
                "beleg_zitat, zitat_geprueft) VALUES (?, ?, ?, ?, ?, ?)",
                (ziel_chat_id, neue_v, t["thema"], t["kurz"], t["beleg_zitat"],
                 t["zitat_geprueft"]),
            )


# --------------------------------------------------------------------------
# Texte
# --------------------------------------------------------------------------


def _spanne(nummern: list[int]) -> str:
    if not nummern:
        return ""
    if len(nummern) == 1:
        return f"Interview {nummern[0]}"
    return f"Interview {nummern[0]}\u2013{nummern[-1]}"


def journaltext(bericht: dict) -> str:
    """Ein Eintrag je Lauf, nicht je Interview: was hier passiert ist, ist EIN
    Vorgang der Regie ('Interviews uebernommen'), und das Journal wird nur
    angehaengt (AGENTS.md)."""
    stuecke = [
        f"{p['interviews']} aus Gruppe {p['bot_name']} ({_spanne(p['nummern'])})"
        for p in bericht["posten"] if p["interviews"]
    ]
    return "Interviews uebernommen: " + ", ".join(stuecke)


def chattext(bericht: dict) -> str:
    """Die eine Zeile in den Zielchat. Nummern statt Namen -- die Gruppe
    sucht ihr Material ueber 'Interview N', so heisst es ueberall
    (kontext.interviewbezeichnung)."""
    nummern = [n for p in bericht["posten"] for n in p["nummern"]]
    if not nummern:
        return ""
    if len(nummern) == 1:
        was = f"Interview {nummern[0]}"
    else:
        was = f"Interview {nummern[0]} bis {nummern[-1]}"
    return (
        "Ab jetzt liegen hier auch die Interviews der anderen Gruppen: "
        f"{was}."
    )


def berichtstext(bericht: dict, trocken: bool) -> str:
    zeilen = []
    kopf = "Trockenlauf" if trocken else "Uebernommen"
    zeilen.append(f"{kopf} - Zielgruppe {bericht['ziel']}, hat bisher "
                  f"{bericht['vorhanden']} Interview(s).")
    for p in bericht["posten"]:
        zeilen.append(
            f"  Quelle {p['chat_id']} ({p['bot_name']}): {p['interviews']} Interview(s), "
            f"{p['teile']} Teil(e), {p['verdichtungen']} Verdichtung(en), "
            f"{p['themen']} Thema/Themen, {p['zitate']} geprueftes Zitat/Zitate, "
            f"{p['audio']} Audiodatei(en)"
            + (f" - {p['schon_da']} schon da" if p["schon_da"] else "")
        )
        if p["nummern"]:
            zeilen.append(f"    -> neue Nummern: {_spanne(p['nummern'])}")
    zeilen.append(
        f"  Danach hat die Zielgruppe {bericht['nachher']} Interview(s) "
        f"({bericht['neu_gesamt']} neu)."
    )
    return "\n".join(zeilen)


# --------------------------------------------------------------------------
# Einstieg
# --------------------------------------------------------------------------


def _backup(db_pfad: str) -> str | None:
    """Legt eine Kopie der Datenbank neben das Original. Vor einem Import, der
    mehrere Gruppen anfasst, ist das billiger als jede Ueberlegung, wie man
    ihn rueckgaengig macht."""
    quelle = Path(db_pfad)
    if not quelle.exists():
        return None
    ziel = quelle.with_name(
        quelle.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    shutil.copy2(quelle, ziel)
    return str(ziel)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ja = "--ja" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        print(
            "Aufruf: python -m scripts.interviews_uebernehmen "
            "<ziel_chat_id> <quelle_chat_id> [<quelle_chat_id> ...] [--ja]\n"
            "Ohne --ja: Trockenlauf, es wird nichts geschrieben."
        )
        return 1
    try:
        ziel_chat_id = int(args[0])
        quellen = [int(a) for a in args[1:]]
    except ValueError:
        print("chat_id muss eine Zahl sein.")
        return 1
    if ziel_chat_id in quellen:
        print("Die Zielgruppe kann nicht ihre eigene Quelle sein.")
        return 1

    e = einstellungen.laden()
    conn = db.verbinde(e.db_pfad)
    db.initialisiere(conn)

    # Wie loeschen.py/begruessen.py: die geladene Env muss die der ZIELgruppe
    # sein -- sonst kaeme die Chat-Zeile aus dem falschen Bot. Die QUELLEN
    # duerfen anderen Bots gehoeren, sie liegen ja in derselben Datenbank.
    zeile = conn.execute(
        "SELECT bot_name FROM gruppe WHERE chat_id = ?", (ziel_chat_id,)
    ).fetchone()
    if zeile is None:
        print(f"Zielgruppe {ziel_chat_id} ist unbekannt.")
        return 1
    if zeile["bot_name"] and zeile["bot_name"] != e.bot_name:
        print(
            f"Zielgruppe {ziel_chat_id} gehoert {zeile['bot_name']}, geladen ist "
            f"{e.bot_name} -- falsche Env."
        )
        return 1

    for chat_id in [ziel_chat_id, *quellen]:
        if laufende_aufnahme(conn, chat_id):
            print(
                f"Gruppe {chat_id}: es laeuft noch eine Aufnahme oder der "
                "Interviewmodus ist an. Erst beenden lassen, dann uebernehmen."
            )
            return 1

    warnungen: list[str] = []
    if not ja:
        bericht = plane(conn, ziel_chat_id, quellen)
        print(berichtstext(bericht, trocken=True))
        if bericht["neu_gesamt"]:
            print("\nJournal waere: " + journaltext(bericht))
            print("Chat-Zeile waere: " + chattext(bericht))
        print(
            f"\nNichts geschrieben. Mit --ja ausfuehren (das Skript legt dann "
            f"selbst ein Backup an: {e.db_pfad}.bak-<zeit>)."
        )
        conn.close()
        return 0

    sicherung = _backup(e.db_pfad)
    if sicherung:
        print(f"Backup: {sicherung}")

    bericht = uebernimm(conn, ziel_chat_id, quellen, e.audio_verz, warnungen)
    print(berichtstext(bericht, trocken=False))
    for w in warnungen:
        print(f"  WARNUNG: {w}")

    if bericht["neu_gesamt"]:
        repo.schreibe_journal(
            conn, ziel_chat_id, "entschieden", journaltext(bericht), "befehl"
        )
        text = chattext(bericht)
        try:
            import httpx

            with httpx.Client(timeout=30.0) as klient:
                message_id = Telegram(e.bot_token, klient).sende(ziel_chat_id, text)
            repo.merke_nachricht(
                conn, ziel_chat_id, message_id, "Bot", 1, "text", text,
                _jetzt(), 1,
            )
        except Exception as fehler:  # pragma: no cover - Netzweg
            print(f"  WARNUNG: Chat-Zeile nicht gesendet ({fehler!r}). Text war: {text}")
    else:
        print("  Nichts Neues - kein Journaleintrag, keine Chat-Zeile.")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
