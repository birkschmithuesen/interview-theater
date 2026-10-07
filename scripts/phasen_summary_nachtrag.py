"""Nachtrag: Phasen-Summary fuer bereits abgeschlossene Phasen (Karte
t_1bc96848, Teil 2 -- Aufgabe 3).

Der Mechanismus (``interview_theater.phasen_summary``) laeuft seit seiner
Einfuehrung nur bei einem Phasenwechsel. Gruppen, die eine Phase schon
VORHER abgeschlossen hatten, haben also kein Summary -- dieses Skript holt
es nach, ueber **denselben** Mechanismus (``phasen_summary.erzeuge`` /
``phasen_summary.baue_text`` / ``repo.speichere_phasen_summary``), hier nur
synchron statt im Hintergrund-Thread und ohne einen Fehlschlag zu
verschlucken: ein Skriptlauf soll einen Fehler auf der Konsole zeigen, nicht
nur als Vorfall in der Datenbank.

**Kostet Geld** (ein Schema-Aufruf je nachgetragener Phase) und laeuft nie
automatisch.

Aufruf:
    python -m scripts.phasen_summary_nachtrag --db <pfad> --chat <chat_id> [--phase N] [--ja]

Ohne ``--ja``: Trockenlauf, zeigt nur an, was erzeugt wuerde (welche Phase,
geschaetzte Zeichenzahl der Quelle), schreibt NICHTS.

Ohne ``--phase``: alle abgeschlossenen Phasen (kleiner als die aktuelle
Phase der Gruppe) ohne vorhandenes Summary -- ein wiederholter Lauf erzeugt
dadurch keine Dubletten. Mit ``--phase``: genau diese eine Phase, auch wenn
schon ein Summary existiert (ein bewusster Nachtrag/Ersatz).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import db, einstellungen, llm, phasen, phasen_summary, repo, workshop


def _abgeschlossene_phasen_ohne_summary(conn, chat_id: int) -> list[int]:
    """Alle Phasen VOR der aktuellen, fuer die noch kein Summary gespeichert
    ist -- dieselbe Grenze wie ``phasen_summary.bloecke_bis``."""
    aktuelle = phasen.aktuelle(conn, chat_id)
    return [
        nummer for nummer, _, _ in workshop.phasenliste()
        if nummer < aktuelle and repo.hole_phasen_summary(conn, chat_id, nummer) is None
    ]


def plane(conn, chat_id: int, phase: int | None) -> list[dict]:
    """Was ein Lauf taete -- reine Leseabfrage, kein Modellaufruf, kein
    Schreibzugriff. Grundlage von Trockenlauf UND Ernstfall."""
    phasen_liste = [phase] if phase is not None else (
        _abgeschlossene_phasen_ohne_summary(conn, chat_id)
    )
    plan = []
    for nummer in phasen_liste:
        quelle = phasen_summary.baue_nutzertext(conn, chat_id, nummer)
        plan.append({
            "chat_id": chat_id,
            "phase": nummer,
            "bezeichnung": phasen.bezeichnung(nummer),
            "quelle_zeichen": len(quelle),
            "hat_bereits_summary": repo.hole_phasen_summary(conn, chat_id, nummer) is not None,
        })
    return plan


def fuehre_aus(conn, klm, e, chat_id: int, phase: int) -> str:
    """Erzeugt und speichert das Summary einer Phase -- derselbe Mechanismus
    wie ``phasen_summary._lauf``, hier synchron: ein Fehler geht als
    Ausnahme an den Aufrufer, statt im Hintergrund-Thread stillzubleiben."""
    ergebnis = phasen_summary.erzeuge(klm, conn, e, chat_id, phase)
    text = phasen_summary.baue_text(ergebnis, phase)
    repo.speichere_phasen_summary(conn, chat_id, phase, text)
    return text


def berichtstext(plan: list[dict], trocken: bool) -> str:
    if not plan:
        return "Nichts zu tun: keine passende Phase gefunden."
    kopf = "Trockenlauf" if trocken else "Nachgetragen"
    zeilen = [f"{kopf}:"]
    for eintrag in plan:
        status = " (ersetzt vorhandenes Summary)" if eintrag["hat_bereits_summary"] else ""
        zeilen.append(
            f"  chat_id {eintrag['chat_id']}, Phase {eintrag['bezeichnung']}: "
            f"Quelle {eintrag['quelle_zeichen']} Zeichen{status}"
        )
    if trocken:
        zeilen.append("Nichts geschrieben. Mit --ja ausfuehren.")
    return "\n".join(zeilen)


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.phasen_summary_nachtrag",
        description="Traegt ein Phasen-Summary fuer bereits abgeschlossene "
                    "Phasen nach (Karte t_1bc96848).",
    )
    zerleger.add_argument("--db", required=True, dest="db_pfad")
    zerleger.add_argument("--chat", required=True, type=int, dest="chat_id")
    zerleger.add_argument("--phase", type=int, default=None)
    zerleger.add_argument("--ja", action="store_true", help="wirklich schreiben")
    a = zerleger.parse_args(argv)

    conn = db.verbinde(a.db_pfad)
    try:
        db.initialisiere(conn)
        plan = plane(conn, a.chat_id, a.phase)
        print(berichtstext(plan, trocken=not a.ja))
        if not a.ja or not plan:
            return 0

        einst = einstellungen.laden()
        with httpx.Client() as klient:
            klm = llm.LLM(einst, klient, conn)
            for eintrag in plan:
                fuehre_aus(conn, klm, einst, eintrag["chat_id"], eintrag["phase"])
                print(f"  geschrieben: chat_id {eintrag['chat_id']}, "
                      f"Phase {eintrag['bezeichnung']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
