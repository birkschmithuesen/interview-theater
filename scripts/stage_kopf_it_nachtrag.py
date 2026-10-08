"""Nachtrag: IT-Fassung fuer einen bereits gespeicherten Stage-Script-Kopf
(Birk, 08.10.2026 ~07:50, Auftrag 2 -- G2 "Setup & roles" fehlte als
italienische Fassung).

Ursache (siehe Bericht): ``stagescript.schreibe`` speichert
``arbeitsstand.stage_kopf`` VOR dem EN/IT-Spiegelpass und spiegelt nur den
Szenentext, nie den Kopf -- der Fix (``stagescript.py``, diese Nacht) gilt
nur fuer kuenftige Kopf-Laeufe. Gruppen, deren Kopf schon VOR dem Fix
geschrieben wurde, bleiben ohne ``stage_kopf_it`` stehen; dieses Skript holt
genau das nach, ueber denselben Mechanismus
(``skript_uebersetzung.spiegle_text``), **ohne** den bestehenden
(von der Gruppe schon gesehenen) ``stage_kopf`` (EN) zu veraendern -- nur die
neue Spalte ``stage_kopf_it`` wird gefuellt.

**Kostet Geld** (ein Schema-Aufruf, derselbe Spiegelpass wie im Szenenlauf)
und laeuft nie automatisch.

Aufruf (aus dem Hauptcheckout):

    uv run --extra dev python -m scripts.stage_kopf_it_nachtrag --db betrieb/padua-gruppe2.db --chat <chat_id>              # Trockenlauf
    uv run --extra dev python -m scripts.stage_kopf_it_nachtrag --db betrieb/padua-gruppe2.db --chat <chat_id> --ja          # wirklich

Sicherung: ``--ja`` schreibt zuerst per ``VACUUM INTO`` eine Kopie der
gesamten Datenbank nach ``<db-Verzeichnis>/backup/padua-<chat_id>-<Zeit>.db``
-- VOR jedem Schreibzugriff (dieselbe Begruendung wie
``scripts/padua_fragen_neu.py``: ``VACUUM INTO`` statt ``shutil.copy``, weil
die Betriebsdatenbank im WAL-Modus laeuft).

Journal: ein Eintrag Art ``entschieden``, Quelle ``regie`` (Birks Vorgabe --
ein Operator-Nachtrag, kein Erkenner- oder Befehlslauf)."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import db, einstellungen, llm, repo, skript_uebersetzung, szene_claude, workshop

TEXT_JOURNAL = "Stage-Script-Kopf: italienische Fassung nachgetragen (Robo, Auftrag 2)."


def sicherungspfad(db_pfad: str, chat_id: int, jetzt: datetime) -> Path:
    ordner = Path(db_pfad).resolve().parent / "backup"
    return ordner / f"padua-{chat_id}-stage-kopf-it-{jetzt:%Y%m%d-%H%M%S}.db"


def plane(conn, chat_id: int) -> dict:
    """Reine Leseabfrage, kein Modellaufruf, kein Schreibzugriff."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    kopf = (stand["stage_kopf"] if stand is not None else None) or ""
    kopf_it_vorhanden = bool((stand["stage_kopf_it"] if stand is not None else None) or "")
    return {
        "chat_id": chat_id,
        "hat_kopf": bool(kopf.strip()),
        "kopf_zeichen": len(kopf),
        "hat_bereits_it": kopf_it_vorhanden,
        "zweisprachig_aktiv": workshop.skript_zweisprachig_aktiv(),
    }


def berichtstext(plan: dict, trocken: bool) -> str:
    if not plan["hat_kopf"]:
        return f"Nichts zu tun: chat_id {plan['chat_id']} hat keinen stage_kopf."
    if not plan["zweisprachig_aktiv"]:
        return (f"Nichts zu tun: chat_id {plan['chat_id']} -- "
                f"[skript] zweisprachig ist im aktiven Profil nicht an.")
    kopf = "Trockenlauf" if trocken else "Nachgetragen"
    status = " (ersetzt vorhandenes stage_kopf_it)" if plan["hat_bereits_it"] else ""
    zeile = (f"{kopf}: chat_id {plan['chat_id']}, Kopf {plan['kopf_zeichen']} Zeichen{status}")
    if trocken:
        zeile += "\nNichts geschrieben. Mit --ja ausfuehren."
    return zeile


def fuehre_aus(conn, klm, e, chat_id: int) -> str:
    """Spiegelt den vorhandenen Kopf, schreibt NUR ``stage_kopf_it`` --
    ``stage_kopf`` (EN, von der Gruppe schon gesehen) bleibt unveraendert."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    kopf = (stand["stage_kopf"] if stand is not None else None) or ""
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    gespiegelt = skript_uebersetzung.spiegle_text(conn, klm, e, chat_id, kopf, ueber_claude=ueber_claude)
    if gespiegelt is None:
        raise RuntimeError("Spiegelpass fehlgeschlagen (siehe Log/Vorfall) -- nichts geschrieben.")
    _, kopf_it = gespiegelt
    repo.setze_arbeitsstand(conn, chat_id, "stage_kopf_it", kopf_it)
    repo.schreibe_journal(conn, chat_id, "entschieden", TEXT_JOURNAL, quelle="regie")
    return kopf_it


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.stage_kopf_it_nachtrag",
        description="Traegt stage_kopf_it (IT-Fassung des Stage-Script-Kopfs) nach (Auftrag 2).",
    )
    zerleger.add_argument("--db", required=True, dest="db_pfad")
    zerleger.add_argument("--chat", required=True, type=int, dest="chat_id")
    zerleger.add_argument("--ja", action="store_true", help="wirklich schreiben")
    a = zerleger.parse_args(argv)

    conn = db.verbinde(a.db_pfad)
    try:
        db.initialisiere(conn)
        plan = plane(conn, a.chat_id)
        print(berichtstext(plan, trocken=not a.ja))
        if not a.ja or not plan["hat_kopf"] or not plan["zweisprachig_aktiv"]:
            return 0

        jetzt = datetime.now(timezone.utc)
        sicherung = sicherungspfad(a.db_pfad, a.chat_id, jetzt)
        sicherung.parent.mkdir(parents=True, exist_ok=True)
        conn.execute("VACUUM INTO ?", (str(sicherung),))
        print(f"Backup: {sicherung}")

        einst = einstellungen.laden()
        with httpx.Client() as klient:
            klm = llm.LLM(einst, klient, conn)
            fuehre_aus(conn, klm, einst, a.chat_id)
            print(f"  geschrieben: chat_id {a.chat_id}, stage_kopf_it gesetzt.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
