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
"""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_VERZEICHNIS = Path(__file__).parent / "prompts"

#: name -> (mtime_ns, text)
_CACHE: dict[str, tuple[int, str]] = {}

#: Trennt Basis und Regie-Zettel im Prompt.
UEBERSCHRIFT = "\n\nZusaetzliche Anweisung fuer diesen Workshop:\n\n"


def _lies(pfad: Path, schluessel: str) -> str | None:
    """Liest ``pfad`` nur, wenn er sich seit dem letzten Mal geaendert hat.
    Liefert None, wenn die Datei nicht existiert (Zusatz ist optional)."""
    try:
        mtime = pfad.stat().st_mtime_ns
    except FileNotFoundError:
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


def hole(name: str) -> str:
    """Der Basis-Prompt ``name`` (system|erkenner|journal|verdichter|szene|
    theater-tells|phasen/1..8), heiss nachgeladen. Fehlt die Datei, ist das
    ein Programmierfehler."""
    text = _lies(_pfad(name), name)
    if text is None:
        raise FileNotFoundError(f"Prompt-Datei fehlt: {name}.md")
    return text


def hole_optional(name: str) -> str | None:
    """Wie ``hole()``, liefert aber None statt zu krachen, wenn die Datei
    fehlt -- fuer Prompt-Teile, ohne die der Bot weiterarbeiten kann.

    Der Fall, um den es geht: eine Phasendatei (``prompts/phasen/N.md``)
    fehlt oder wurde am Workshoptag versehentlich geloescht. Dann laeuft das
    Gespraech mit der Basis-Anweisung weiter -- der Bot verliert seinen
    Phasenfokus, aber die Gruppe bekommt eine Antwort."""
    try:
        return _lies(_pfad(name), name)
    except ValueError:
        return None


def zusatz_verzeichnis() -> Path | None:
    """Wo ``zusatz.md`` gesucht wird: neben der Datenbank (``IT_DB``)."""
    db = os.environ.get("IT_DB")
    if not db:
        return None
    return Path(db).expanduser().resolve().parent


#: Trennt Basis und Phasenanweisung im Prompt.
PHASEN_UEBERSCHRIFT = "\n\n"


def system(bot_name: str | None = None, phase: int | None = None) -> str:
    """Systemanweisung des Gespraechs plus Phasenanweisung plus optionalem
    Regie-Zettel.

    Reihenfolge: Basis, dann ``phasen/<phase>.md`` (worauf der Bot in dieser
    Phase den Fokus legt), dann ``zusatz.md`` (alle Bots), dann
    ``zusatz.<bot_name>.md`` (nur dieser Bot). Der Regie-Zettel steht am
    Ende, weil das Ende des Prompts am schwersten wiegt (SPEC § 6.1) -- eine
    spontane Regieanweisung soll Basis UND Phase ueberstimmen koennen.

    Fehlt die Phasendatei, bleibt es bei der Basis: ein fehlender
    Phasenfokus ist kein Grund, das Gespraech scheitern zu lassen
    (``hole_optional``).
    """
    teile = [hole("system")]
    if phase is not None:
        phasentext = hole_optional(f"phasen/{int(phase)}")
        if phasentext and phasentext.strip():
            teile.append(PHASEN_UEBERSCHRIFT + phasentext.strip())
    verz = zusatz_verzeichnis()
    if verz is not None:
        namen = ["zusatz"]
        if bot_name:
            namen.append(f"zusatz.{bot_name}")
        for schluessel in namen:
            text = _lies(verz / f"{schluessel}.md", schluessel)
            if text and text.strip():
                teile.append(UEBERSCHRIFT + text.strip())
    return "".join(teile)
