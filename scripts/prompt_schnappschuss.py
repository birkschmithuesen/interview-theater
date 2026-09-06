"""Ein Schnappschuss von allem, was ein Workshop-Profil beeinflussen kann.

**Warum es das gibt** (06.09.2026, Umbau auf das einhaengbare Profil). Die
Abnahmebedingung des Umbaus lautet: **Dortmund bleibt bitgleich**, mit
``IT_WORKSHOP=dortmund-2026`` und ohne Variable. Beweisen laesst sich das nur
gegen etwas Festgeschriebenes.

``scripts/erzeuge_prompts.py`` und die 21 Dumps unter
``docs/prompt-audit/2026-09-06/`` waeren der naheliegende Massstab, taugen
dafuer aber nur zur Haelfte: sie brauchen eine **Kopie der Betriebsdatenbank**
(``IT_DB``), die in einem Arbeitsbaum nicht liegt und nicht liegen darf, und
ihr Nutzertext-Teil haengt an echten Interviews. Ihr SYSTEM-Teil dagegen ist
rein aus Dateien und Konstanten gebaut -- und genau dort, und nur dort, wirkt
ein Profil. (Gemessen am 06.09.2026: von den 21 Dumps stimmt der SYSTEM-Teil
von sechs noch mit dem heutigen Code ueberein, die uebrigen sind seit
``f908b68`` durch den Feinschliff-Umbau ueberholt. Was noch stimmt, prueft
``tests/test_profil_bitgleich.py`` mit.)

Dieses Skript sammelt deshalb **ohne Datenbank** alles ein, was ein Profil
verschieben koennte: jede Prompt-Datei, jede zusammengesetzte
Systemanweisung, die Formenliste, die Phasen, die Phasentexte, die
Leitfaden-Bausteine. Zwei Laeufe unter verschiedenen Profilen lassen sich
byteweise vergleichen.

Abgelegt wird nicht der Volltext (ueber ein Megabyte, weil jede Form mit
jedem Stil ihre eigene Systemanweisung hat), sondern je Abschnitt ein
SHA-256 mit Laenge. Fuer Gleichheit ist das genauso streng, und der
Abschnittsname sagt bei einem Unterschied sofort, wo er sitzt. Der Volltext
steht mit ``--voll`` zum Nachsehen bereit.

Aufruf::

    python -m scripts.prompt_schnappschuss                 # Fingerabdruck nach stdout
    python -m scripts.prompt_schnappschuss <datei>         # Fingerabdruck in eine Datei
    python -m scripts.prompt_schnappschuss --voll <datei>  # Volltext in eine Datei
"""

import hashlib
import re
import sys
from pathlib import Path

from interview_theater import (
    anweisungen, knoepfe, leitfaden, phasen, phasentexte, stile, szene,
    szenenfolge, web_schreiben, workshop,
)

#: Der Bot-Name, mit dem die Systemanweisung gebaut wird. Fest, damit der
#: Schnappschuss nicht von der Umgebung abhaengt.
BOT = "gruppe4"


def _prompt_namen() -> list[str]:
    """Alle Prompt-Namen unter ``interview_theater/prompts/``, sortiert."""
    verz = anweisungen._VERZEICHNIS
    return sorted(
        str(p.relative_to(verz).with_suffix("")).replace("\\", "/")
        for p in verz.rglob("*.md")
    )


def teile() -> list[tuple[str, str]]:
    """Der Schnappschuss als Liste ``(Abschnittsname, Text)``.

    Reine Leseoperation: keine Datenbank, kein Modell, kein Netz. Was hier
    nicht drinsteht, kann ein Profil auch nicht verschieben -- wer ein neues
    Profil-Feld einfuehrt, das einen Prompt aendert, ergaenzt hier eine
    Zeile, sonst prueft der Bitgleichheits-Test daran vorbei."""
    stuecke: list[tuple[str, str]] = []

    for name in _prompt_namen():
        stuecke.append((f"prompt {name}", anweisungen.hole(name)))

    # Die zusammengesetzte Systemanweisung des Gespraechs, je Phase. Ohne
    # Zusatz-Datei: ``IT_DB`` ist hier nicht gesetzt, der Regie-Zettel ist
    # Betrieb und kein Profil.
    for nummer in [None] + [n for n, _, _ in phasen.PHASEN]:
        stuecke.append((
            f"anweisungen.system(phase={nummer})",
            anweisungen.system(BOT, nummer),
        ))

    for form in (szene.PROSA,) + tuple(szene.FORMEN):
        stuecke.append(
            (f"szene.systemanweisung({form})", szene.systemanweisung(form)))
        for eintrag in stile.STILE:
            slug = eintrag["slug"]
            stuecke.append((
                f"szene.systemanweisung({form}, {slug})",
                szene.systemanweisung(form, slug)))

    for anzahl in szenenfolge.ANZAHL_MOEGLICH:
        stuecke.append((f"szenenfolge.systemanweisung({anzahl})",
                        szenenfolge.systemanweisung(anzahl)))
        stuecke.append((f"szenenfolge.systemanweisung_geschichte({anzahl})",
                        szenenfolge.systemanweisung_geschichte(anzahl)))
    stuecke.append(("szenenfolge.systemanweisung_geschichte_szenen",
                    szenenfolge.systemanweisung_geschichte_szenen()))
    stuecke.append(("szenenfolge.ANWEISUNG_FELDER", szenenfolge.ANWEISUNG_FELDER))

    stuecke.append(("szene.FORMEN", repr(tuple(szene.FORMEN))))
    stuecke.append(("szene.FORM_STICHWOERTER", repr(
        {k: tuple(v) for k, v in sorted(szene.FORM_STICHWOERTER.items())})))
    stuecke.append(("szene.PROSA", repr(szene.PROSA)))
    stuecke.append(("web_schreiben.FORMEN", repr(tuple(web_schreiben.FORMEN))))
    stuecke.append(("szenenfolge.FORM_VORGABE", repr(szenenfolge.FORM_VORGABE)))
    stuecke.append(("szenenfolge.ANZAHL_VORGABE", repr(szenenfolge.ANZAHL_VORGABE)))
    stuecke.append(("szenenfolge.ANZAHL_MOEGLICH",
                    repr(tuple(szenenfolge.ANZAHL_MOEGLICH))))

    stuecke.append(("phasen.PHASEN", repr(tuple(phasen.PHASEN))))
    stuecke.append(("phasen.STICHWOERTER", repr(
        {k: tuple(v) for k, v in sorted(phasen.STICHWOERTER.items())})))
    stuecke.append(("phasen.MEHRDEUTIG",
                    repr(dict(sorted(phasen.MEHRDEUTIG.items())))))
    stuecke.append(("phasen.MELDUNG", phasen.MELDUNG))
    stuecke.append(("phasen.ERSTE/LETZTE", f"{phasen.ERSTE} {phasen.LETZTE}"))
    for nummer, _, _ in phasen.PHASEN:
        stuecke.append(
            (f"phasen.bezeichnung({nummer})", phasen.bezeichnung(nummer)))

    for nummer in sorted(phasentexte.EINLEITUNGEN):
        stuecke.append((f"phasentexte.EINLEITUNGEN[{nummer}]",
                        phasentexte.EINLEITUNGEN[nummer]))
    stuecke.append(("phasentexte.EINLEITUNG_LETZTE_OFFEN",
                    phasentexte.EINLEITUNG_7_OFFEN))

    for feld in ("TEXT_KOPF", "UEBERSCHRIFT_EROEFFNUNG", "UEBERSCHRIFT_FRAGEN",
                 "UEBERSCHRIFT_ABSCHLUSS", "TEXT_LEER"):
        stuecke.append((f"leitfaden.{feld}", getattr(leitfaden, feld)))

    # Die Auftrags-Anweisungen der Knoepfe: Prompt-Text, der im Code steht
    # (ein Knopf schickt ihn ueber ablauf.starte_auftrag an das Modell).
    # ``fuelle`` wie am Aufrufort, sonst stuende hier der Platzhalter.
    for feld in sorted(f for f in dir(knoepfe) if f.startswith("ANWEISUNG_")):
        wert = getattr(knoepfe, feld)
        if isinstance(wert, str):
            stuecke.append((f"knoepfe.{feld}", anweisungen.fuelle(wert)))

    return stuecke


def fingerabdruck(stuecke: list[tuple[str, str]] | None = None) -> str:
    """Je Abschnitt eine Zeile ``sha256  laenge  name``.

    Der Profilname steht **nicht** darin: der Schnappschuss soll unter zwei
    Profilen gleich sein, wenn beide dieselben Texte erzeugen."""
    zeilen = []
    for name, text in (stuecke if stuecke is not None else teile()):
        pruef = hashlib.sha256(text.encode("utf-8")).hexdigest()
        zeilen.append(f"{pruef}  {len(text):7d}  {name}")
    return "\n".join(zeilen) + "\n"


def voll(stuecke: list[tuple[str, str]] | None = None) -> str:
    """Derselbe Schnappschuss als lesbarer Volltext -- zum Nachsehen, wenn
    der Fingerabdruck an einer Stelle abweicht."""
    return "".join(
        f"\n===== {name} =====\n{text}\n"
        for name, text in (stuecke if stuecke is not None else teile())
    )


#: Eine Zeile des Fingerabdrucks: Pruefsumme, Laenge (rechtsbuendig), Name.
_ZEILE = re.compile(r"^\S+\s+\d+\s+(.*)$")


def _name(zeile: str) -> str:
    treffer = _ZEILE.match(zeile)
    return treffer.group(1) if treffer else zeile


def ergaenze(datei: Path) -> list[str]:
    """Haengt **nur neue** Abschnitte an einen abgelegten Fingerabdruck an.

    Der Massstab wird nie neu geschrieben -- eine geaenderte Zeile bliebe
    sonst unbemerkt, und genau die soll der Bitgleichheits-Test finden. Wer
    einen Abschnitt neu in den Schnappschuss aufnimmt (weil eine weitere
    Stelle profilabhaengig geworden ist), ergaenzt ihn hiermit und weist
    getrennt nach, dass sein Wert sich nicht geaendert hat."""
    vorhanden = {
        _name(zeile) for zeile in datei.read_text(encoding="utf-8").splitlines()
    }
    neu = [zeile for zeile in fingerabdruck().splitlines()
           if _name(zeile) not in vorhanden]
    if neu:
        with datei.open("a", encoding="utf-8") as ziel:
            ziel.write("\n".join(neu) + "\n")
    return neu


def main() -> None:
    argumente = list(sys.argv[1:])
    volltext = "--voll" in argumente
    if volltext:
        argumente.remove("--voll")
    if "--ergaenze" in argumente:
        argumente.remove("--ergaenze")
        neu = ergaenze(Path(argumente[0]))
        print(f"{len(neu)} Abschnitt(e) ergaenzt:")
        print("\n".join(neu))
        return
    stuecke = teile()
    text = voll(stuecke) if volltext else fingerabdruck(stuecke)
    if argumente:
        Path(argumente[0]).write_text(text, encoding="utf-8")
        print(f"{len(text)} Zeichen nach {argumente[0]} "
              f"(Profil: {workshop.name()})")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
