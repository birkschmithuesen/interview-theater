"""Prompt-Texte mit Hot-Reload -- Verhalten aendern ohne Neustart.

Die Prompts (``system``, ``erkenner``, ``journal``, ``verdichter``, ``szene``
und die Negativliste ``theater-tells``, die ``szene.py`` an ``szene`` haengt)
liegen als Markdown unter ``theatersoap/prompts/``. Frueher wurden sie
einmal beim Import gelesen; jede Aenderung brauchte einen Neustart und damit
einen Eingriff am laufenden Prozess -- genau das, was am Workshoptag schief
geht (Doppelstart, 409 Conflict, Bot taub).

Jetzt wird die Datei bei **jedem Aufruf** auf ihren mtime geprueft und nur bei
Aenderung neu gelesen. Ein Stat-Aufruf je Modellaufruf ist gegen 1-5 s
Modell-Latenz nichts. Eine Aenderung an ``system.md`` wirkt damit beim
naechsten Gespraechszug.

**Zusatz-Datei fuer den Regie-Zettel.** Liegt neben der Datenbank ein
``zusatz.md`` (Pfad: ``<TS_DB-Verzeichnis>/zusatz.md``) oder ein
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


def hole(name: str) -> str:
    """Der Basis-Prompt ``name`` (system|erkenner|journal|verdichter|szene|
    theater-tells), heiss nachgeladen. Fehlt die Datei, ist das ein
    Programmierfehler."""
    text = _lies(_VERZEICHNIS / f"{name}.md", name)
    if text is None:
        raise FileNotFoundError(f"Prompt-Datei fehlt: {name}.md")
    return text


def zusatz_verzeichnis() -> Path | None:
    """Wo ``zusatz.md`` gesucht wird: neben der Datenbank (``TS_DB``)."""
    db = os.environ.get("TS_DB")
    if not db:
        return None
    return Path(db).expanduser().resolve().parent


def system(bot_name: str | None = None) -> str:
    """Systemanweisung des Gespraechs plus optionalem Regie-Zettel.

    Reihenfolge: Basis, dann ``zusatz.md`` (alle Bots), dann
    ``zusatz.<bot_name>.md`` (nur dieser Bot). Der Zusatz steht am Ende,
    weil das Ende des Prompts am schwersten wiegt (SPEC § 6.1) -- eine
    spontane Regieanweisung soll die Basis ueberstimmen koennen.
    """
    teile = [hole("system")]
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
