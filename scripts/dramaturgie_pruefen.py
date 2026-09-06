"""Die Dramaturgie-Pruefung ausserhalb des Chats gegen eine Kopie-Datenbank.

**Kein Test, laeuft nie automatisch, kostet Geld** -- wie
``scripts/pruefe_prompts.py`` und ``scripts/rauchtest.py``. Die Testsuite
prueft den Code drumherum (Parser, Belegschleife, Aggregation) mit Attrappen;
dieses Skript ist das Gegenstueck: es schickt die Fragen an das echte
Richtermodell.

**Wozu.** Ein Prompt unter ``prompts/dramaturgie/`` wird heiss nachgeladen und
also am Workshoptag geaendert. Ohne einen Weg, ihn danach gegen ein echtes
Stueck laufen zu lassen, ist jede solche Aenderung ein Blindflug. Ausserdem
kann man so einer Gruppe eine Pruefung anbieten, ohne im Chat einen Lauf
auszuloesen, und die Befunde in Ruhe lesen.

Aufruf::

    set -a; . ./betrieb/gruppe1.env; set +a
    PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)
    cp betrieb/soap.db /tmp/kopie.db
    IT_JUDGE_MODELL=claude-opus-5 $PY -m scripts.dramaturgie_pruefen /tmp/kopie.db <chat_id>
    $PY -m scripts.dramaturgie_pruefen /tmp/kopie.db <chat_id> --nur-mechanik
    $PY -m scripts.dramaturgie_pruefen /tmp/kopie.db <chat_id> --bericht
    $PY -m scripts.dramaturgie_pruefen /tmp/kopie.db <chat_id> --schleife --bericht

**Gegen eine KOPIE.** Das Skript schreibt Befunde, ``aufruf``- und
``vorfall``-Zeilen in die Datenbank, die es bekommt -- und verweigert deshalb
den Dienst, wenn der Pfad derselbe ist wie ``IT_DB``. Die Betriebsdatenbank
wird von diesem Skript nie geschrieben; Kopieren ist ein Handgriff, ein
verlorener Workshoptag nicht.

**Kein Telegram.** Es wird nichts in einen Chat geschickt. Der Bericht landet
unter ``docs/dramaturgie-berichte/`` (gitignored -- er enthaelt Belegzitate
aus Szenentexten).

``--nur-mechanik`` laeuft ohne jeden Modellaufruf und kostet nichts: die
Schicht 1 allein, fuer den schnellen Blick auf Namensdrift, Geisterfiguren
und Sprechanteile.

``--schleife`` fuehrt die Ueberarbeitungsauftraege auch aus und misst, ob es
geholfen hat (``dramaturgie.schleife``). **Das ist der teuerste Schalter
dieses Repos** -- bis zu drei volle Pruefungen und je Auftrag ein
Szenenlauf -- und er schreibt Szenentexte in die Kopie-Datenbank. Genau
deshalb steht er hier und nicht an einem Knopf im Chat: die Schleife
schlaegt vor, die Gruppe bestaetigt. Was in der Kopie entsteht, ist ein
Vorschlag, den ein Mensch liest, bevor irgendetwas davon in die Live-Daten
kommt.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import db, einstellungen, llm, repo
from interview_theater.dramaturgie import fanout, mechanik, schleife

#: Wohin ``--bericht`` ohne Pfadangabe schreibt. Gitignored: die Berichte
#: enthalten Belegzitate aus den Szenentexten der Gruppe.
BERICHTE = Path(__file__).resolve().parent.parent / "docs" / "dramaturgie-berichte"


class Stumm:
    """Telegram, das nichts verschickt -- die Zusage "kein Telegram" aus dem
    Modulkopf, als Objekt.

    ``szene.schreibe`` schickt den fertigen Text in den Chat; hier gibt es
    keinen. Statt die Zusage in jedem Aufrufer zu wiederholen, steht sie
    einmal hier: **jede** Methode ist ein Nichtstun, das eine
    ``message_id`` zurueckgibt. Der Fangarm ueber ``__getattr__`` ist
    Absicht -- kaeme in ``telegram.py`` eine Methode dazu, waere das Ergebnis
    sonst ein Fehlschlag im Skript statt einer nicht verschickten Nachricht,
    und das waere die falsche Fehlerrichtung fuer ein Werkzeug, dessen
    einzige Aufgabe das Schweigen ist."""

    def __init__(self):
        self.message_id = 0

    def _nichts(self, *args, **kwargs) -> int:
        self.message_id += 1
        return self.message_id

    def __getattr__(self, name):
        return self._nichts


def _pruefe_pfad(pfad: str) -> None:
    """Verweigert den Dienst auf der Betriebsdatenbank."""
    betrieb = os.environ.get("IT_DB")
    if betrieb and Path(betrieb).resolve() == Path(pfad).resolve():
        raise SystemExit(
            f"Das ist die Betriebsdatenbank ({betrieb}). Kopiert sie erst:\n"
            f"  cp {betrieb} /tmp/kopie.db"
        )
    if not Path(pfad).exists():
        raise SystemExit(f"Datenbank nicht gefunden: {pfad}")


def _zeile(befund) -> str:
    schwere = fanout._feld(befund, "schwere") or "?"
    pruefung = fanout._feld(befund, "pruefung") or "?"
    return f"- [{schwere}] {pruefung}: {fanout.befundzeile(befund)}"


def _bilanzteil(lauf) -> list[str]:
    """Der Abschnitt zur Rueckkopplung: je Runde eine Zeile, dazu die Bilanz
    und der Grund, warum Schluss war.

    Er steht **vor** den Befunden: wer eine Schleife gefahren hat, will
    zuerst wissen, ob sie geholfen hat."""
    if lauf is None:
        return []
    teile = ["## Rueckkopplung", ""]
    for runde in lauf.runden:
        teile.append(
            f"- Runde {runde.nummer}: {len(runde.ergebnis.befunde)} Befunde, "
            f"{len(runde.ergebnis.bewertungen)} Bewertungen, "
            f"{len(runde.auftraege)} Auftraege, "
            f"{len(runde.ueberarbeitet)} Szenen ueberarbeitet"
        )
        if runde.bilanz is not None:
            teile += [""] + [f"  {z}" for z in runde.bilanz.zeilen()] + [""]
    teile += ["", f"**Schluss:** {lauf.meldung}", ""]
    if lauf.geschadet:
        teile += [
            "> Eine Ueberarbeitung hat einen Score gesenkt. Die betroffene "
            "Fassung steht in der Kopie-Datenbank und geht **nicht** an die "
            "Gruppe, bevor ein Mensch sie gelesen hat.",
            "",
        ]
    return teile


def bericht(chat_id: int, ergebnis, auftraege, dauer_s: float, lauf=None) -> str:
    """Der Markdown-Bericht eines Laufs -- Kennzahlen, Befunde, Auftraege,
    und bei ``--schleife`` die Bilanz zwischen den Runden.

    Mit Belegzitat: der Bericht ist fuer die Person, die den Prompt
    nachschaerft, und genau dort will man sehen, WORAUF sich ein Befund
    stuetzt. Deshalb ist das Verzeichnis gitignored."""
    jetzt = datetime.now().strftime("%Y-%m-%d %H:%M")
    richter = ergebnis.richter
    teile = [
        f"# Dramaturgie-Pruefung Gruppe {chat_id}, Runde {ergebnis.runde}",
        "",
        f"- Datum: {jetzt}",
        f"- Richter: {richter.modell} ueber {richter.weg}"
        if richter else "- Richter: keiner (nur Mechanik)",
        f"- Modellaufrufe: {ergebnis.aufrufe}",
        f"- Dauer: {dauer_s:.0f} s",
        f"- Befunde: {len(ergebnis.befunde)}",
        f"- Ueberarbeitungsauftraege: {len(auftraege)}",
        "",
        "## Prompt-Versionen",
        "",
    ]
    for schluessel in fanout.PROMPTS:
        teile.append(f"- {schluessel}: {fanout.version(schluessel)}")
    teile += [""] + _bilanzteil(lauf)
    teile += ["", "## Befunde der letzten Runde", ""]
    for befund in ergebnis.befunde:
        teile.append(_zeile(befund))
        beleg = fanout._feld(befund, "beleg")
        if beleg:
            geprueft = "geprueft" if fanout._feld(befund, "beleg_geprueft") else "UNGEPRUEFT"
            teile.append(f"  - Beleg ({geprueft}): {beleg}")
    teile += ["", "## Ueberarbeitungsauftraege", ""]
    if not auftraege:
        teile.append("(keine)")
    for auftrag in auftraege:
        teile.append(
            f"- Szene {auftrag['szene']} [{auftrag['schwere']}] "
            f"{auftrag['pruefung']}: {auftrag['anweisung']}"
        )
    return "\n".join(teile) + "\n"


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument("datenbank", help="Pfad zu einer KOPIE der Datenbank")
    zerleger.add_argument("chat_id", type=int)
    zerleger.add_argument(
        "--nur-mechanik", action="store_true",
        help="Schicht 1 allein, ohne jeden Modellaufruf -- kostet nichts",
    )
    zerleger.add_argument(
        "--schleife", action="store_true",
        help=(
            "Die Auftraege auch ausfuehren und messen, ob es geholfen hat -- "
            f"hoechstens {schleife.RUNDEN_MAX} Ueberarbeitungsrunden. Teuer, "
            "und schreibt Szenentexte in die KOPIE"
        ),
    )
    zerleger.add_argument(
        "--bericht", nargs="?", const="", metavar="PFAD",
        help=f"Markdown-Bericht schreiben (ohne Pfad nach {BERICHTE})",
    )
    args = zerleger.parse_args(argv)
    if args.schleife and args.nur_mechanik:
        # Die Schleife braucht Judge-Scores; die Mechanik gibt keine. Lieber
        # eine Zeile als ein Lauf, der stillschweigend nur die Haelfte tut.
        print("--schleife und --nur-mechanik schliessen sich aus.", file=sys.stderr)
        return 2

    _pruefe_pfad(args.datenbank)
    conn = db.verbinde(args.datenbank)
    db.initialisiere(conn)

    dauer = 0.0
    lauf = None
    if args.nur_mechanik:
        befunde = [b.als_dict() for b in mechanik.pruefe_alles(conn, args.chat_id)]
        ergebnis = fanout.Ergebnis(runde=0, befunde=befunde)
        auftraege = fanout.auftraege(befunde)
    else:
        e = einstellungen.laden()
        start = time.monotonic()
        with httpx.Client(timeout=fanout.TIMEOUT_S) as klient:
            klm = llm.LLM(e, klient, conn)
            try:
                if args.schleife:
                    lauf = schleife.schliesse(
                        conn, Stumm(), klm, e, args.chat_id
                    )
                    ergebnis = lauf.runden[-1].ergebnis
                else:
                    ergebnis = fanout.pruefe(conn, e, klm, args.chat_id)
            except (fanout.RichterFehler, fanout.DramaturgieFehler) as fehler:
                print(str(fehler), file=sys.stderr)
                return 1
        dauer = time.monotonic() - start
        auftraege = fanout.auftraege(
            repo.dramaturgie_befunde(conn, args.chat_id, runde=ergebnis.runde),
            [f["name"] for f in repo.figuren(conn, args.chat_id)],
        )

    for befund in ergebnis.befunde:
        print(_zeile(befund))
    print(
        f"\n{len(ergebnis.befunde)} Befunde, {ergebnis.aufrufe} Modellaufrufe, "
        f"{len(auftraege)} Auftraege, {dauer:.0f} s."
    )
    if lauf is not None:
        print()
        print(lauf.als_text())

    if args.bericht is not None:
        ziel = Path(args.bericht) if args.bericht else (
            BERICHTE / f"{datetime.now():%Y-%m-%d-%H%M}-gruppe{args.chat_id}.md"
        )
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(
            bericht(args.chat_id, ergebnis, auftraege, dauer, lauf),
            encoding="utf-8",
        )
        print(f"Bericht: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
