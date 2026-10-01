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
4. Das Zahlwort der Formen passt zu ihrer Anzahl (fuer deutsche und
   englische Zahlwoerter).
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
import re
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
    # Englisch seit Karte A1 (Padua): "exactly five: ..."
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
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
                # Ueber den Sprachzugriff (Karte A1), wo das Modul schon
                # einen hat: unter einem englischen Profil wird der
                # englische Auftrag auf Platzhalter geprueft.
                wert = getattr(getattr(modul, "T", modul), feld)
                texte[f"{modul.__name__.split('.')[-1]}.{feld}"] = wert
    return texte


def pruefe(profil: workshop.Profil) -> Bericht:
    """Alles, was ohne Datenbank und ohne Netz pruefbar ist."""
    bericht = Bericht()

    # --- Geruest: angefangen, nicht startbereit --------------------------
    if profil.geruest():
        fehlend = profil.fehlende_pflichtfelder()
        bericht.fehlt(
            "Das Profil ist ein Geruest (geruest = true in profil.toml) und "
            "damit nicht startbereit."
            + (f" Leere Pflichtfelder: {', '.join(fehlend)}." if fehlend else "")
            + " Wer es fertig macht, fuellt die Felder und streicht die Zeile."
        )

    # --- Sprache (Karte A1) ----------------------------------------------
    code = (profil.wert("sprache.code") or "").strip()
    if code not in workshop.SPRACHEN:
        bericht.fehlt(
            f"sprache.code={code!r} ist nicht gebaut. Moeglich: "
            f"{', '.join(workshop.SPRACHEN)}."
        )
    whisper = (profil.wert("sprache.whisper") or "").strip()
    if not re.fullmatch(r"auto|[a-z]{2}", whisper):
        bericht.fehlt(
            f"sprache.whisper={whisper!r} ist weder 'auto' noch ein "
            f"zweistelliger Sprachcode in Kleinbuchstaben (ISO 639-1, z. B. 'it')."
        )

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

    # --- Laengen-Rhythmus (30.09.2026, Karte R) ---------------------------
    # Steht der Schalter aus, wird keine dieser Zahlen gelesen; dann sind
    # auch Fehler darin harmlos und werden nur gemerkt. Steht er an, ist eine
    # kaputte Zahl ein Startfehler -- Fehlerbild am Workshoptag ist die
    # teuerste Waehrung.
    laengen_an = bool(profil.wert("laengen.aktiv", False))
    melde = bericht.fehlt if laengen_an else bericht.merke
    stufen = ("schlag", "kurz", "mittel", "lang")
    gewicht = {"schlag": 0.0, "kurz": 0.2, "mittel": 0.5, "lang": 1.0}

    faktor = profil.wert("laengen.kurz_faktor", 0.25)
    if not isinstance(faktor, (int, float)) or not 0 < float(faktor) <= 1:
        melde(f"laengen.kurz_faktor muss zwischen 0 und 1 liegen, ist {faktor!r}")
    schwelle = profil.wert("laengen.nachzaehl_schwelle", 1.3)
    if not isinstance(schwelle, (int, float)) or float(schwelle) < 1.0:
        melde(
            "laengen.nachzaehl_schwelle muss >= 1.0 sein (1.3 = ab 130 % des "
            f"Budgets), ist {schwelle!r}"
        )
    unten = profil.wert("laengen.vorgabe_min", 0)
    oben = profil.wert("laengen.vorgabe_max", 0)
    if not (isinstance(unten, int) and isinstance(oben, int) and 0 < unten < oben):
        melde(f"laengen.vorgabe_min/max muss 0 < min < max sein, ist {unten!r}/{oben!r}")

    for eintrag in profil.wert("laengen.muster", ()) or ():
        unbekannt = [s for s in eintrag if s not in stufen]
        if unbekannt:
            melde(
                f"laengen.muster {list(eintrag)}: unbekannte Stufe(n) "
                f"{unbekannt} -- erlaubt sind {list(stufen)}"
            )
            continue
        if len(set(eintrag)) < 2:
            melde(f"laengen.muster {list(eintrag)} ist flach -- mindestens "
                  "zwei verschiedene Stufen")
        else:
            werte = [gewicht[s] for s in eintrag]
            if min(werte) > 0.2 or max(werte) < 1.0:
                melde(
                    f"laengen.muster {list(eintrag)} spreizt nicht: es braucht "
                    "eine Stufe 'kurz' oder 'schlag' UND eine Stufe 'lang'"
                )

    formnamen = {f["name"] for f in (profil.formen or {}).get("form", ())}
    rahmen = profil.wert("laengen.rahmen", {}) or {}
    for name, paar in rahmen.items():
        if name not in formnamen:
            melde(
                f"laengen.rahmen: '{name}' ist keine Form dieses Profils "
                f"(formen.toml kennt {sorted(formnamen)}) -- der Rahmen "
                "wuerde nie gelesen"
            )
        if len(paar) != 2 or not (0 < paar[0] < paar[1]):
            melde(f"laengen.rahmen['{name}'] muss [min, max] mit 0 < min < max "
                  f"sein, ist {list(paar)}")
    if laengen_an:
        for name in sorted(formnamen - set(rahmen)):
            bericht.merke(
                f"Form '{name}' hat keinen eigenen Laengenrahmen -- sie nimmt "
                f"laengen.vorgabe_min/max ({unten}-{oben} Woerter)"
            )

    # --- Sprachpass -------------------------------------------------------
    pass_an = bool(profil.wert("sprachpass.aktiv", False))
    melde_pass = bericht.fehlt if pass_an else bericht.merke
    for schluessel in ("gedankenstriche_je_1000", "nicht_sondern_je_1000",
                       "adjektiv_dreier_je_1000", "fazitsatz_je_text"):
        wert = profil.wert(f"sprachpass.{schluessel}")
        if not isinstance(wert, (int, float)) or float(wert) < 0:
            melde_pass(f"sprachpass.{schluessel} muss eine Zahl >= 0 sein, "
                       f"ist {wert!r}")

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
