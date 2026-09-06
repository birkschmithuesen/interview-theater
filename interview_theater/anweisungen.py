"""Prompt-Texte mit Hot-Reload -- Verhalten aendern ohne Neustart.

Die Prompts (``system``, ``erkenner``, ``journal``, ``verdichter``, ``szene``
und die Negativliste ``theater-tells``, die ``szene.py`` an ``szene`` haengt)
liegen als Markdown unter ``interview_theater/prompts/``. Frueher wurden sie
einmal beim Import gelesen; jede Aenderung brauchte einen Neustart und damit
einen Eingriff am laufenden Prozess -- genau das, was am Workshoptag schief
geht (Doppelstart, 409 Conflict, Bot taub).

Jetzt wird die Datei bei **jedem Aufruf** auf ihren mtime geprueft und nur bei
Aenderung neu gelesen. Ein Stat-Aufruf je Modellaufruf ist gegen 1-5 s
Modell-Latenz nichts. Eine Aenderung an ``system.md`` wirkt damit beim
naechsten Gespraechszug.

**Zusatz-Datei fuer den Regie-Zettel.** Liegt neben der Datenbank ein
``zusatz.md`` (Pfad: ``<IT_DB-Verzeichnis>/zusatz.md``) oder ein
``zusatz.<bot_name>.md``, wird deren Inhalt an die Systemanweisung des
Gespraechs angehaengt -- fuer alle Bots bzw. nur fuer einen. So laesst sich
"heute nur Figuren, keine Szenen" oder "weniger vorschlagen, mehr fragen"
eintragen, ohne die Basis-Anweisung anzufassen; loeschen der Datei nimmt es
wieder zurueck. Die Datei liegt ausserhalb des Pakets, damit sie nie ins
Repository geraet (``betrieb/`` ist gitignored).

Nur der Gespraechs-Prompt bekommt den Zusatz. Erkenner, Journal und
Verdichter sind gemessene Extraktionsaufgaben mit Few-Shots; ein freier
Zusatz wuerde dort die Trefferquote unkontrolliert veraendern. Wer die
aendern will, aendert ihre Datei -- die wird ebenso heiss nachgeladen. Der
Szenen-Prompt bleibt aus demselben Grund ohne Zusatz und hat sein eigenes
Ventil dafuer: ``theater-tells.md``, die Negativliste, die im Workshop
waechst.

**Der Einhaengepunkt des Workshop-Profils** (06.09.2026). Diese Datei ist
die einzige Stelle, an der Prompt-Text entsteht -- deshalb haengt das Profil
hier ein, und nur hier. Drei Dinge kommen dazu:

* **Platzhalter.** ``{{zielgruppe}}``, ``{{rahmen}}`` und so weiter werden
  aus dem aktiven Profil gefuellt (``platzhalter()``). Das ist der Normalfall
  (E.1 Frage 2 der Analyse): der generische Prompt bleibt im Repo und
  verbessert sich fuer alle Workshops weiter, nur die eingesetzten Stuecke
  sind workshop-eigen. Ein Text ohne ``{{`` wird nicht angefasst -- fuer
  jeden Prompt, der keinen Platzhalter traegt, kostet das nichts und aendert
  nichts.
* **Dateiersatz.** Liegt in ``workshop/<name>/prompts/`` eine Datei mit
  demselben Namen wie eine Repo-Prompt-Datei, gewinnt sie. Erlaubt, aber
  nicht der Normalfall: wer eine ganze Datei ersetzt, bekommt spaetere
  Verbesserungen am Repo-Prompt nicht mehr mit.
* **Profil-Anweisung.** ``workshop/<name>/prompts/anweisung.md`` haengt in
  ``system()`` zwischen Phasenanweisung und Regie-Zettel -- die Schicht aus
  B.3 der Analyse. Sie ist das, was fuer diesen Workshop immer gilt; der
  Regie-Zettel bleibt dahinter, damit eine spontane Regieanweisung weiter
  alles ueberstimmen kann.

**Der Zwischenspeicher traegt das Profil im Schluessel** (D.5 der Analyse).
Frueher war ``_CACHE`` nur nach Prompt-Name gekeyt. Solange ein Prozess ein
Profil hat (heute so: ein Prozess je Gruppe), faellt das nicht auf -- sobald
zwei Profile in **einem** Prozess vorkommen, liefert der Cache den Text des
falschen Workshops. Das ist kein hypothetischer Fall: der Web-Dienst laeuft
einmal fuer alle Gruppen. Der Schluessel ist deshalb
``(Profilname, Herkunft, Prompt-Name)``.
"""

import logging
import os
import re
from pathlib import Path

from interview_theater import workshop

log = logging.getLogger(__name__)

_VERZEICHNIS = Path(__file__).parent / "prompts"

#: Das Unterverzeichnis eines Profils, in dem Prompt-Dateien und
#: Prompt-Bausteine liegen.
PROFIL_PROMPTS = "prompts"

#: Der Name der Profil-Anweisung, die ``system()`` zwischen Phase und
#: Regie-Zettel haengt.
PROFIL_ANWEISUNG = "anweisung"

#: (profil, herkunft, name) -> (mtime_ns, text). Siehe Modul-Docstring, D.5.
_CACHE: dict[tuple[str, str, str], tuple[int, str]] = {}

#: Trennt Basis und Regie-Zettel im Prompt.
UEBERSCHRIFT = "\n\nZusaetzliche Anweisung fuer diesen Workshop:\n\n"

#: Ein Platzhalter: zwei geschweifte Klammern, kleingeschriebener Name.
#: Bewusst eng gefasst -- JSON-Beispiele in den Prompts enthalten geschweifte
#: Klammern, und ein weiter Ausdruck haette sie erwischt.
MUSTER = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")

#: Wie oft ``fuelle`` durchlaeuft. Ein Baustein aus dem Profil darf selbst
#: Platzhalter tragen (der Rahmenblock nennt die Zielgruppe), aber nicht
#: endlos tief -- drei Runden reichen fuer jede sinnvolle Schachtelung und
#: beenden auch einen Ring aus Versehen.
TIEFE = 3

#: Platzhalter, vor denen schon gewarnt wurde. Eine Warnung je Name und
#: Prozess: die Meldung soll auffallen und nicht das Log fluten.
_GEMELDET: set[str] = set()


def _lies(pfad: Path, schluessel: tuple[str, str, str]) -> str | None:
    """Liest ``pfad`` nur, wenn er sich seit dem letzten Mal geaendert hat.
    Liefert None, wenn die Datei nicht existiert (Zusatz ist optional)."""
    try:
        mtime = pfad.stat().st_mtime_ns
    except (FileNotFoundError, NotADirectoryError):
        if schluessel in _CACHE:
            del _CACHE[schluessel]
            log.info("Prompt %s entfernt", pfad.name)
        return None
    alt = _CACHE.get(schluessel)
    if alt is not None and alt[0] == mtime:
        return alt[1]
    text = pfad.read_text(encoding="utf-8")
    if alt is not None:
        log.info("Prompt %s neu geladen (%d Zeichen)", pfad.name, len(text))
    _CACHE[schluessel] = (mtime, text)
    return text


def _pfad(name: str) -> Path:
    """Der Dateipfad zu einem Prompt-Namen, auch mit Unterpfad
    (``"phasen/3"`` -> ``prompts/phasen/3.md``).

    Der Name kommt aus dem Code, nie aus einer Nachricht -- die Pruefung auf
    ``..`` und absolute Pfade steht trotzdem hier: sie kostet nichts und
    haelt die Zusage, dass ``hole()`` nur Dateien aus ``prompts/`` liest,
    auch dann, wenn jemand spaeter einen Namen von aussen durchreicht."""
    pfad = (_VERZEICHNIS / f"{name}.md").resolve()
    if not pfad.is_relative_to(_VERZEICHNIS.resolve()):
        raise ValueError(f"Prompt-Name zeigt aus prompts/ heraus: {name!r}")
    return pfad


def profil_verzeichnis() -> Path | None:
    """Das ``prompts/``-Verzeichnis des aktiven Profils, oder None."""
    profil = workshop.aktiv()
    if profil.verzeichnis is None:
        return None
    return profil.verzeichnis / PROFIL_PROMPTS


def _profil_pfad(name: str) -> Path | None:
    """Der Pfad einer Prompt-Datei im aktiven Profil -- None, wenn kein
    Profil eingehaengt ist. Dieselbe Pfadpruefung wie ``_pfad``."""
    wurzel = profil_verzeichnis()
    if wurzel is None:
        return None
    aufgeloest = wurzel.resolve()
    pfad = (wurzel / f"{name}.md").resolve()
    if not pfad.is_relative_to(aufgeloest):
        raise ValueError(f"Prompt-Name zeigt aus dem Profil heraus: {name!r}")
    return pfad


def bausteinschluessel(pfad: Path, wurzel: Path) -> str:
    """Der Platzhaltername einer Prompt-Datei: der Pfad unterhalb von
    ``wurzel``, ohne Endung, mit ``_`` statt ``/`` und ``-``.

    ``rahmen.md`` -> ``{{rahmen}}``, ``rahmen-kurz.md`` -> ``{{rahmen_kurz}}``,
    ``formen/dialog.md`` -> ``{{formen_dialog}}``. Der Bindestrich wandert
    mit, weil ein Platzhalter ein Bezeichner ist und die Dateinamen im
    Repo (``theater-tells.md``) Bindestriche tragen."""
    kurz = str(pfad.relative_to(wurzel).with_suffix(""))
    return kurz.replace("\\", "/").replace("/", "_").replace("-", "_")


def _bausteine() -> dict[str, str]:
    """Jede Prompt-Datei als Platzhalterwert -- erst die des Repos, dann
    die des Profils darueber.

    **Eine Regel, keine Sonderfaelle** (06.09.2026, Schritt 3): dieselbe
    Datei, die eine gleichnamige Repo-Datei ersetzen kann, ist zugleich der
    Wert ihres Platzhalters. Der Rahmenblock steht damit genau einmal --
    als ``prompts/rahmen.md`` -- und wird in ``system.md``, ``szene.md`` und
    den Phasendateien nur noch mit ``{{rahmen}}`` eingesetzt, statt sechsmal
    dupliziert dazustehen.

    Die Repo-Fassung ist die Vorgabe, damit ein Prozess **ohne**
    ``IT_WORKSHOP`` denselben Text bekommt wie einer mit
    ``IT_WORKSHOP=dortmund-2026``. Das Profil gewinnt, wo es eine Datei
    mitbringt.

    Gelesen wird ueber ``_lies``, also mit demselben Hot-Reload wie jeder
    andere Prompt: wer am Workshoptag ``rahmen.md`` aendert, sieht es beim
    naechsten Zug. Beide Verzeichnisse werden dabei jedes Mal durchgesehen
    -- es sind ein paar Dutzend Dateien, und eine neu angelegte soll ohne
    Neustart wirken. Der Aufwand faellt nur an, wenn ein Text ueberhaupt
    ein ``{{`` traegt (``fuelle``)."""
    profil = workshop.name()
    werte: dict[str, str] = {}
    for herkunft, wurzel in (("repo", _VERZEICHNIS), ("profil", profil_verzeichnis())):
        if wurzel is None or not wurzel.is_dir():
            continue
        for pfad in sorted(wurzel.rglob("*.md")):
            schluessel = bausteinschluessel(pfad, wurzel)
            text = _lies(pfad, (profil, f"baustein-{herkunft}", schluessel))
            if text is not None:
                werte[schluessel] = text.strip("\n")
    return werte


def platzhalter() -> dict[str, str]:
    """Alle Platzhalterwerte des aktiven Profils.

    Zwei Quellen, in dieser Reihenfolge: die einzeiligen Werte aus
    ``profil.toml`` (``workshop.platzhalter``) und die Markdown-Bausteine aus
    ``workshop/<name>/prompts/``. Ein Baustein gewinnt -- wer eine ganze
    Datei hinlegt, meint sie."""
    werte = dict(workshop.platzhalter())
    werte.update(_bausteine())
    return werte


def fuelle(text: str) -> str:
    """Setzt die Platzhalter des aktiven Profils in ``text`` ein.

    Ein Text ohne ``{{`` geht unveraendert zurueck -- das ist heute jeder
    Prompt im Repo, und deshalb kostet dieser Schritt dort nichts.

    Ein **unbekannter** Platzhalter bleibt stehen und wird geloggt, statt
    den Zug abzubrechen. Das ist Absicht: geprueft wird ein Profil vor dem
    Start (``scripts/pruefe_profil.py``, laeuft in
    ``scripts/betrieb-start.sh``), und wenn dort etwas durchgerutscht ist,
    ist ein Prompt mit einem sichtbaren ``{{tippfehler}}`` immer noch besser
    als eine Gruppe, die keine Antwort bekommt."""
    if "{{" not in text:
        return text
    werte = platzhalter()
    for _ in range(TIEFE):
        neu = MUSTER.sub(lambda t: werte.get(t.group(1), t.group(0)), text)
        if neu == text:
            break
        text = neu
    for offen in MUSTER.findall(text):
        if offen not in _GEMELDET:
            _GEMELDET.add(offen)
            log.warning(
                "Platzhalter {{%s}} hat im Profil %s keinen Wert",
                offen, workshop.name(),
            )
    return text


def _roh(name: str) -> str | None:
    """Der Prompt-Text ohne Platzhalter -- aus dem Profil, sonst aus dem
    Repo. Eine gleichnamige Datei im Profil ersetzt die Repo-Datei."""
    profil = workshop.name()
    eigen = _profil_pfad(name)
    if eigen is not None:
        text = _lies(eigen, (profil, "profil", name))
        if text is not None:
            return text
    return _lies(_pfad(name), (profil, "repo", name))


def hole(name: str) -> str:
    """Der Basis-Prompt ``name`` (system|erkenner|journal|verdichter|szene|
    theater-tells|phasen/1..7), heiss nachgeladen und mit gefuellten
    Platzhaltern. Fehlt die Datei, ist das ein Programmierfehler."""
    text = _roh(name)
    if text is None:
        raise FileNotFoundError(f"Prompt-Datei fehlt: {name}.md")
    return fuelle(text)


def hole_optional(name: str) -> str | None:
    """Wie ``hole()``, liefert aber None statt zu krachen, wenn die Datei
    fehlt -- fuer Prompt-Teile, ohne die der Bot weiterarbeiten kann.

    Der Fall, um den es geht: eine Phasendatei (``prompts/phasen/N.md``)
    fehlt oder wurde am Workshoptag versehentlich geloescht. Dann laeuft das
    Gespraech mit der Basis-Anweisung weiter -- der Bot verliert seinen
    Phasenfokus, aber die Gruppe bekommt eine Antwort."""
    try:
        text = _roh(name)
    except ValueError:
        return None
    return None if text is None else fuelle(text)


def zusatz_verzeichnis() -> Path | None:
    """Wo ``zusatz.md`` gesucht wird: neben der Datenbank (``IT_DB``)."""
    db = os.environ.get("IT_DB")
    if not db:
        return None
    return Path(db).expanduser().resolve().parent


#: Trennt Basis und Phasenanweisung im Prompt.
PHASEN_UEBERSCHRIFT = "\n\n"

#: Trennt Phasenanweisung und Profil-Anweisung. Dieselbe wie oben: die
#: Profil-Anweisung ist Teil dessen, was immer gilt, und kein Zuruf von
#: aussen -- ihre eigene Ueberschrift schreibt das Profil selbst hinein.
PROFIL_UEBERSCHRIFT = "\n\n"


def system(bot_name: str | None = None, phase: int | None = None) -> str:
    """Systemanweisung des Gespraechs plus Phasenanweisung plus optionaler
    Profil-Anweisung plus optionalem Regie-Zettel.

    Reihenfolge: Basis, dann ``phasen/<phase>.md`` (worauf der Bot in dieser
    Phase den Fokus legt), dann die Profil-Anweisung
    (``workshop/<name>/prompts/anweisung.md``), dann ``zusatz.md`` (alle
    Bots), dann ``zusatz.<bot_name>.md`` (nur dieser Bot). Der Regie-Zettel
    steht am Ende, weil das Ende des Prompts am schwersten wiegt (SPEC
    § 6.1) -- eine spontane Regieanweisung soll Basis, Phase UND Profil
    ueberstimmen koennen.

    Fehlt die Phasendatei, bleibt es bei der Basis: ein fehlender
    Phasenfokus ist kein Grund, das Gespraech scheitern zu lassen
    (``hole_optional``).
    """
    teile = [hole("system")]
    if phase is not None:
        phasentext = hole_optional(f"phasen/{int(phase)}")
        if phasentext and phasentext.strip():
            teile.append(PHASEN_UEBERSCHRIFT + phasentext.strip())
    profiltext = hole_optional(PROFIL_ANWEISUNG)
    if profiltext and profiltext.strip():
        teile.append(PROFIL_UEBERSCHRIFT + profiltext.strip())
    verz = zusatz_verzeichnis()
    if verz is not None:
        profil = workshop.name()
        namen = ["zusatz"]
        if bot_name:
            namen.append(f"zusatz.{bot_name}")
        for schluessel in namen:
            text = _lies(verz / f"{schluessel}.md", (profil, "zusatz", schluessel))
            if text and text.strip():
                teile.append(UEBERSCHRIFT + text.strip())
    return "".join(teile)
