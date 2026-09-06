"""Prueft ein Workshop-Profil, bevor ein Bot damit startet.

**Warum es das gibt** (E.1 Frage 9 der Analyse): *Fehlerbild am Workshoptag
ist die teuerste Waehrung.* Ein Profil mit einem Tippfehler im
Platzhalternamen faellt sonst erst auf, wenn die Gruppe im Chat
``{{zielgrupe}}`` liest -- oder gar nicht, weil niemand den Prompt zu sehen
bekommt. Dieses Skript sieht dieselben Dinge nach, die der Bot beim Start
braucht, aber ohne Bot, ohne Telegram und ohne Datenbank.

Aufruf::

    python -m scripts.pruefe_profil dortmund-2026
    python -m scripts.pruefe_profil --alle      # jedes Profil unter workshop/
    python -m scripts.pruefe_profil --vorgabe   # das eingebaute Profil

Rueckgabewert 0, wenn alles passt, sonst 1. ``scripts/betrieb-start.sh``
ruft es **vor** dem Bot-Start auf: ein kaputtes Profil soll keinen
Halbstart erzeugen.

Was geprueft wird:

1. Das Profil laedt ueberhaupt (``workshop.lade`` -- Pflichtfelder,
   gueltiges TOML, Formen- und Phasenkatalog in sich stimmig).
2. Zu jeder Form gibt es einen Regelblock, zu jeder Phase eine
   Phasenanweisung und eine Einleitung.
3. **Jeder Platzhalter loest sich auf** -- in jeder Prompt-Datei des Repos,
   in jeder des Profils und in den Prompt-Konstanten, die im Code stehen.
4. Das Zahlwort der Formen passt zu ihrer Anzahl (nur fuer deutschsprachige
   Profile pruefbar).
5. Der Rahmenblock nennt die Zielgruppe aus ``profil.toml``. Die kurzen
   Rahmenfassungen tragen den Wortlaut ausgeschrieben (dort faellt der
   Zeilenumbruch mitten in den Satz), und genau deshalb koennen sie von
   ``profil.toml`` abweichen, ohne dass es jemandem auffiele.
6. Bringt das Profil einen eigenen Korpus mit, gelten dort die
   Mindestzahlen aus ``tests/test_korpus.py``. Ohne eigenen Korpus wird
   nichts geprueft -- ein halbfertiges Profil soll den Betrieb des anderen
   nicht blockieren (E.1 Frage 8).
"""

import json
import os
import sys
from pathlib import Path

from interview_theater import anweisungen, knoepfe, szenenfolge, workshop

#: Die Zahlwoerter, mit denen ein deutscher Prompt eine Anzahl ausschreibt.
#: Nur fuer die Gegenprobe von ``formen.anzahl_wort``; ein Profil in einer
#: anderen Sprache traegt ein Wort, das hier nicht steht, und wird
#: uebersprungen statt falsch gemeldet.
ZAHLWOERTER = {
    "eine": 1, "zwei": 2, "drei": 3, "vier": 4, "fuenf": 5, "sechs": 6,
    "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwoelf": 12,
}

#: Mindestbesetzung eines eigenen Erkenner-Korpus -- dieselben Zahlen wie in
#: ``tests/test_korpus.py``. Hier noch einmal, weil ein Betriebsskript nicht
#: aus den Tests importiert.
KORPUS_MINDEST = {
    "erkenner": 70,
    "journal": 20,
    "verdichter": 6,
    "sprachprofil": 4,
}


class Bericht:
    """Sammelt Befunde. Ein Fehler laesst den Lauf scheitern, ein Hinweis
    nicht -- der Unterschied ist "der Bot startet falsch" gegen "das sollte
    sich jemand ansehen"."""

    def __init__(self) -> None:
        self.fehler: list[str] = []
        self.hinweise: list[str] = []

    def fehlt(self, text: str) -> None:
        self.fehler.append(text)

    def merke(self, text: str) -> None:
        self.hinweise.append(text)

    def ausgeben(self, name: str) -> int:
        for zeile in self.hinweise:
            print(f"  Hinweis: {zeile}")
        for zeile in self.fehler:
            print(f"  FEHLER:  {zeile}")
        if self.fehler:
            print(f"{name}: {len(self.fehler)} Fehler")
            return 1
        zusatz = f", {len(self.hinweise)} Hinweis(e)" if self.hinweise else ""
        print(f"{name}: in Ordnung{zusatz}")
        return 0


def _prompt_texte() -> dict[str, str]:
    """Jeder Text, in dem ein Platzhalter stehen kann: die Prompt-Dateien
    des Repos, die des Profils und die Prompt-Konstanten im Code."""
    texte: dict[str, str] = {}
    for wurzel, herkunft in ((anweisungen._VERZEICHNIS, "prompts"),
                             (anweisungen.profil_verzeichnis(), "profil")):
        if wurzel is None or not wurzel.is_dir():
            continue
        for pfad in sorted(wurzel.rglob("*.md")):
            texte[f"{herkunft}/{pfad.relative_to(wurzel)}"] = pfad.read_text(
                encoding="utf-8")
    for modul in (szenenfolge, knoepfe):
        for feld in sorted(dir(modul)):
            if not feld.startswith("ANWEISUNG_"):
                continue
            wert = getattr(modul, feld)
            if isinstance(wert, str):
                texte[f"{modul.__name__.split('.')[-1]}.{feld}"] = wert
    return texte


def pruefe(profil: workshop.Profil) -> Bericht:
    """Alles, was ohne Datenbank und ohne Netz pruefbar ist."""
    bericht = Bericht()

    # --- Formen: Katalog und Regelbloecke --------------------------------
    formen = workshop.formen(profil)
    for form in formen:
        if not (anweisungen.hole_optional(f"formen/{form}") or "").strip():
            bericht.fehlt(
                f"Form {form!r} hat keinen Regelblock. Erwartet: "
                f"workshop/{profil.name}/prompts/formen/{form}.md oder "
                f"interview_theater/prompts/formen/{form}.md"
            )
    wort = (profil.formen.get("anzahl_wort") or "").strip().lower()
    if wort in ZAHLWOERTER and ZAHLWOERTER[wort] != len(formen):
        bericht.fehlt(
            f"formen.toml: anzahl_wort={wort!r} passt nicht zu "
            f"{len(formen)} Formen. Der Prompt schriebe 'genau {wort}: "
            f"{', '.join(workshop.form_anzeige(profil))}'."
        )
    elif wort not in ZAHLWOERTER:
        bericht.merke(
            f"formen.toml: anzahl_wort={wort!r} ist kein deutsches Zahlwort "
            f"-- ob es zu {len(formen)} Formen passt, kann hier niemand "
            f"pruefen."
        )

    # --- Phasen: Anweisung und Einleitung je Station ---------------------
    einleitungen = workshop.phasentexte_einleitungen(profil)
    for nummer, name, _ in workshop.phasenliste(profil):
        if not (anweisungen.hole_optional(f"phasen/{nummer}") or "").strip():
            bericht.merke(
                f"Phase {nummer} ({name}) hat keine Phasenanweisung "
                f"(prompts/phasen/{nummer}.md). Das Gespraech laeuft ohne "
                f"Phasenfokus weiter, aber es fehlt etwas."
            )
        if not (einleitungen.get(nummer) or "").strip():
            bericht.fehlt(
                f"Phase {nummer} ({name}) hat keine Einleitung in "
                f"phasentexte.toml -- die Gruppe bekaeme beim Eintritt eine "
                f"leere Nachricht."
            )

    # --- Platzhalter -----------------------------------------------------
    bekannt = set(anweisungen.platzhalter())
    for herkunft, text in sorted(_prompt_texte().items()):
        offen = sorted(set(anweisungen.MUSTER.findall(text)) - bekannt)
        if offen:
            bericht.fehlt(
                f"{herkunft}: Platzhalter ohne Wert: "
                f"{', '.join('{{' + o + '}}' for o in offen)}"
            )

    # --- Zielgruppe und Rahmen zueinander --------------------------------
    zielgruppe = (profil.wert("zielgruppe.beschreibung") or "").strip()
    for name in ("rahmen", "rahmen-kurz", "rahmen-knapp"):
        text = anweisungen.hole_optional(name)
        if text is None:
            bericht.merke(f"Kein Rahmenblock {name}.md -- ist das Absicht?")
            continue
        if not _nennt(text, zielgruppe):
            bericht.merke(
                f"{name}.md nennt die Zielgruppe aus profil.toml nicht "
                f"({zielgruppe!r}). Die kurzen Fassungen tragen sie "
                f"ausgeschrieben, weil dort der Zeilenumbruch mitten in den "
                f"Satz faellt -- pruef, ob beide dasselbe sagen."
            )

    # --- Eigener Korpus --------------------------------------------------
    if profil.verzeichnis is not None:
        _pruefe_korpus(profil.verzeichnis / "korpus", bericht)

    return bericht


def _nennt(text: str, satz: str) -> bool:
    """Kommt ``satz`` in ``text`` vor -- auch dann, wenn ein Zeilenumbruch
    mitten hindurchgeht? Verglichen wird ohne Rueecksicht auf Leerraum."""
    if not satz:
        return True
    return " ".join(satz.split()) in " ".join(text.split())


def _pruefe_korpus(verzeichnis: Path, bericht: Bericht) -> None:
    """Mindestzahlen -- nur, wenn das Profil einen eigenen Korpus mitbringt.

    Ohne eigenen Korpus gilt der des Repos, und der ist von
    ``tests/test_korpus.py`` abgedeckt. Ein halbfertiges zweites Profil soll
    den Betrieb des ersten nicht blockieren (E.1 Frage 8)."""
    if not verzeichnis.is_dir():
        return
    for name, mindest in sorted(KORPUS_MINDEST.items()):
        datei = verzeichnis / f"{name}.jsonl"
        if not datei.is_file():
            bericht.fehlt(
                f"korpus/{name}.jsonl fehlt. Ein Profil mit eigenem Korpus "
                f"braucht alle vier -- sonst liefe die Haelfte der "
                f"Pruefungen gegen den Korpus des Repos, also gegen eine "
                f"andere Sprache."
            )
            continue
        anzahl = 0
        for nummer, zeile in enumerate(
                datei.read_text(encoding="utf-8").splitlines(), start=1):
            if not zeile.strip():
                continue
            try:
                json.loads(zeile)
            except json.JSONDecodeError as fehler:
                bericht.fehlt(f"korpus/{name}.jsonl Zeile {nummer}: {fehler}")
                continue
            anzahl += 1
        if anzahl < mindest:
            bericht.fehlt(
                f"korpus/{name}.jsonl hat {anzahl} Faelle, mindestens "
                f"{mindest} sind noetig."
            )


def pruefe_namen(name: str | None) -> int:
    """Ein Profil pruefen und den Befund ausgeben.

    Haengt das Profil dafuer kurz ein: die Prompt-Wege (``anweisungen``)
    lesen das aktive Profil und nicht ein durchgereichtes. Die Variable
    wird danach wieder auf ihren alten Stand gebracht -- sonst stuende nach
    einem ``--alle``-Lauf das zuletzt gepruefte Profil in der Umgebung."""
    anzeige = name or workshop.VORGABE_NAME
    print(f"Workshop-Profil {anzeige}")
    vorher = os.environ.get(workshop.VARIABLE)
    try:
        if name:
            os.environ[workshop.VARIABLE] = name
        else:
            os.environ.pop(workshop.VARIABLE, None)
        workshop.vergiss()
        anweisungen._CACHE.clear()
        try:
            profil = workshop.aktiv()
        except workshop.ProfilFehler as fehler:
            print(f"  FEHLER:  {fehler}")
            print(f"{anzeige}: 1 Fehler")
            return 1
        return pruefe(profil).ausgeben(anzeige)
    finally:
        if vorher is None:
            os.environ.pop(workshop.VARIABLE, None)
        else:
            os.environ[workshop.VARIABLE] = vorher
        workshop.vergiss()
        anweisungen._CACHE.clear()


def main() -> None:
    argumente = sys.argv[1:]
    if not argumente:
        print(__doc__.strip().splitlines()[0])
        print("Aufruf: python -m scripts.pruefe_profil <name>|--alle|--vorgabe")
        sys.exit(2)
    if argumente[0] == "--alle":
        namen = sorted(
            p.name for p in workshop.basis().iterdir()
            if (p / workshop.DATEI).is_file()
        )
        if not namen:
            print(f"Keine Profile unter {workshop.basis()}")
            sys.exit(1)
        schlecht = sum(pruefe_namen(n) for n in namen)
        sys.exit(1 if schlecht else 0)
    if argumente[0] == "--vorgabe":
        sys.exit(pruefe_namen(None))
    sys.exit(pruefe_namen(argumente[0]))


if __name__ == "__main__":
    main()
