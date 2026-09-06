"""Betreiberskript: fuehrt Platzhalterfiguren mit ihren Nachbenennungen
zusammen -- fuer Bestandsdaten.

Der Anlass (docs/analyse-phase4-datenverlust-2026-09-06.md § 2.4): eine
Gruppe hatte 10 Figuren beschlossen, ``figur`` fuehrte **16 Zeilen**, keine
weich geloescht, darunter drei Paare mit wortgleicher Beschreibung -- je ein
Platzhalter ("Nebenfigur Outsider 1") und die spaeter nachbenannte Figur.

Der Schaden war nicht die Dublette, sondern ihre **Richtung**: die im Chat
erarbeiteten Sprachstile hingen an den Platzhaltern, die benannten Figuren
hatten ``sprachstil`` NULL, und ``szene_figur`` verwies gemischt auf beide
Seiten (eine Szene mit sechs Figuren fuehrte neun Zuordnungen). Der Bot
merkt das seit dem 06.09. beim Nachbenennen selbst
(``erkenner._schmelze_platzhalter_ein``) -- was vorher entstanden ist, holt
dieses Skript nach.

**Es laeuft nicht von selbst.** Kein Bot-Start ruft es, kein Timer: es
veraendert Arbeitsergebnisse einer Gruppe, und das ist eine Entscheidung,
kein Wartungsschritt. Erst ``--trocken`` lesen, dann ohne laufen lassen.

Zusammengefuehrt wird ueber ``repo.fuehre_figur_zusammen``, denselben Weg
wie im Chat: Sprachstil, Sprachprofil, Zitate, Interviewzuordnung und
Belegzitat wandern auf den Namen -- aber nur, wo der Name dort nichts hat --,
die Szenenbesetzungen haengen um, der Platzhalter bekommt ``entfernt_am``.
Weich, wie ueberall (N3): nichts wird geloescht.

Erkannt wird eng: ein Platzhaltername (``repo.ist_platzhaltername``) und
eine **wortgleiche, nicht leere** Beschreibung. Zwei benannte Figuren werden
nie verschmolzen, und ohne Beschreibung passiert nichts -- geraten wird hier
nicht, es geht um die Arbeit einer Gruppe.

Kein Modellaufruf. Ausgabe **ohne Inhalte**: je Gruppe nur Namen von
Figuren des Stuecks (erfundene Rollennamen) und Zahlen -- keine
Beschreibung, kein Sprachstil, kein Transkript.

Aufruf:  python scripts/figuren_aufraeumen.py [--trocken] [--chat-id N]
Umgebung: IT_DB (Pflicht)
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo


def _kern(beschreibung) -> str:
    return " ".join((beschreibung or "").split()).lower()


def finde_paare(conn, chat_id: int) -> list[tuple]:
    """Alle ``(Platzhalter, Nachbenennung)``-Paare einer Gruppe.

    Die **juengere** Zeile ist die Nachbenennung: der Platzhalter stand
    zuerst da, der Name kam dazu. Passen mehrere Nachbenennungen auf
    denselben Platzhalter, gewinnt die aelteste von ihnen -- ein Platzhalter
    wird nur einmal eingeschmolzen."""
    figuren = sorted(repo.figuren(conn, chat_id), key=lambda f: f["id"])
    vergeben: set[int] = set()
    paare = []
    for platzhalter in figuren:
        if not repo.ist_platzhaltername(platzhalter["name"]):
            continue
        kern = _kern(platzhalter["beschreibung"])
        if not kern:
            continue
        ziel = next(
            (
                f for f in figuren
                if f["id"] > platzhalter["id"]
                and f["id"] not in vergeben
                and not repo.ist_platzhaltername(f["name"])
                and _kern(f["beschreibung"]) == kern
            ),
            None,
        )
        if ziel is None:
            continue
        vergeben.add(ziel["id"])
        paare.append((platzhalter, ziel))
    return paare


def raeume_auf(conn, chat_id: int, trocken: bool = True) -> int:
    """Fuehrt alle Paare einer Gruppe zusammen. Liefert die Anzahl.

    Bei ``trocken`` wird nichts geschrieben -- nur gezaehlt. Idempotent: ein
    zweiter Lauf findet nichts mehr, weil der Platzhalter dann weich
    geloescht ist und ``repo.figuren`` ihn nicht mehr liefert."""
    paare = finde_paare(conn, chat_id)
    if trocken:
        return len(paare)
    getan = 0
    for platzhalter, ziel in paare:
        if repo.fuehre_figur_zusammen(conn, chat_id, platzhalter["id"], ziel["id"]):
            repo.schreibe_journal(
                conn, chat_id, "entschieden",
                f"Aus {platzhalter['name']} wurde {ziel['name']} -- Sprachstil "
                "und Szenenbesetzung sind mitgewandert.",
                quelle="befehl",
            )
            getan += 1
    return getan


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--chat-id", type=int, default=None,
                          help="nur diese Gruppe (Vorgabe: alle)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur zeigen, nichts schreiben")
    args = zerleger.parse_args(argv)

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        return 1

    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    gruppen = repo.alle_gruppen(conn)
    if args.chat_id is not None:
        gruppen = [g for g in gruppen if g["chat_id"] == args.chat_id]
    if not gruppen:
        print("Keine passende Gruppe in der Datenbank.")
        return 0
    for gruppe in gruppen:
        chat_id = gruppe["chat_id"]
        paare = finde_paare(conn, chat_id)
        for platzhalter, ziel in paare:
            print(f"  {platzhalter['name']} -> {ziel['name']}")
        anzahl = raeume_auf(conn, chat_id, trocken=args.trocken)
        print(
            f"Gruppe {chat_id} ({gruppe['bot_name']}): {anzahl} Paare"
            + (" (trocken, nichts geschrieben)" if args.trocken else " zusammengefuehrt")
        )
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
