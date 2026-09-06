"""Das Workshop-Profil: alles, was an diesem Einsatzort individuell ist.

**Warum es das gibt** (Birk, 06.09.2026, nach der Analyse
``docs/workshop-profil-analyse-2026-09-06.md``). Das Repository ist an 1217
Stellen "Dortmund": Alter der Gruppe, Traegerverein, Auffuehrungsort,
Formenliste, Phasennamen, der Wortlaut der Einleitungen. Solange es nur
einen Einsatzort gibt, ist das kein Problem. Sobald ein zweiter dazukommt
(Padua, Italienisch, andere Altersgruppe), muesste man entweder das Repo
gabeln oder bei jedem Workshop dieselben sechs Dateien von Hand umschreiben
-- und beim naechsten ``git pull`` waere es wieder weg.

Deshalb: alles Individuelle liegt unter ``workshop/<name>/`` und wird ueber
die Umgebungsvariable ``IT_WORKSHOP`` **je Prozess** eingehaengt. Weil die
Env schon heute je Gruppe geladen wird (``betrieb/gruppeN.env``), koennen
zwei Workshops parallel auf einem Server laufen.

**Ohne Variable gilt das eingebaute Vorgabeprofil** (``VORGABE_WERTE``) --
und das traegt exakt die Werte, die vor dem Umbau im Code standen. Das ist
die Zusage, an der dieser Umbau gemessen wird: mit
``IT_WORKSHOP=dortmund-2026`` und ohne Variable entstehen dieselben Prompts
wie vorher. ``tests/test_profil_bitgleich.py`` prueft beides.

**Format TOML, nicht YAML** (06.09.2026). Die Analyse schlaegt ``profil.yaml``
vor; PyYAML ist aber keine Abhaengigkeit dieses Projekts, und eine neue
Abhaengigkeit fuer eine Konfigurationsdatei ist der falsche Preis.
``tomllib`` steht seit Python 3.11 in der Standardbibliothek, und dieses
Projekt verlangt ohnehin 3.11. TOML ist genauso ohne Python-Kenntnis
lesbar und aenderbar -- Zahlen, Listen und mehrzeilige Texte (``\"\"\"...\"\"\"``)
schreiben sich darin sogar geradliniger als in YAML-Blockskalaren.

**Kein Profil-Element ist Python.** Wer eine Altersgruppe, einen Ort oder
einen Formennamen aendern will, aendert ``profil.toml`` oder eine
Markdown-Datei daneben -- nie Code. Wenn eine Anpassung Code braucht, liegt
sie in der falschen Schicht.

**Fehlerbild am Workshoptag ist die teuerste Waehrung.** Ein fehlendes oder
kaputtes Profil bricht den Start mit einer klaren Meldung ab
(``ProfilFehler``) -- kein Halbstart, bei dem der Bot laeuft und die Gruppe
den falschen Rahmen bekommt. ``scripts/pruefe_profil.py`` prueft dasselbe
vorher, ohne einen Bot zu starten.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

#: Die eine Umgebungsvariable, die ein Profil auswaehlt. Je Prozess gesetzt
#: (``betrieb/gruppeN.env``), nie global.
VARIABLE = "IT_WORKSHOP"

#: Wo die Profile liegen. ``IT_WORKSHOP_BASIS`` verschiebt das Verzeichnis --
#: gebraucht wird das von Tests und von ``scripts/pruefe_profil.py``, wenn
#: ein Profil an einer anderen Stelle geprueft werden soll. Im Betrieb steht
#: die Variable nicht.
BASIS_VARIABLE = "IT_WORKSHOP_BASIS"

_PAKET = Path(__file__).resolve().parent

#: Der Dateiname des Profils im Profilverzeichnis.
DATEI = "profil.toml"

#: Die Felder, ohne die ein Profil nicht startet. Punkte trennen Ebenen.
#: Bewusst kurz: was fehlen darf, faellt auf den Wert des Vorgabeprofils
#: zurueck -- was hier steht, ist das, dessen Fehlen am Workshoptag als
#: falscher Inhalt und nicht als Fehlermeldung auffiele.
PFLICHTFELDER = (
    "beschreibung",
    "sprache.code",
    "sprache.anrede",
    "zielgruppe.beschreibung",
)


class ProfilFehler(RuntimeError):
    """Ein Profil fehlt, ist unlesbar oder unvollstaendig.

    Eigene Klasse, damit ``bot.main`` und ``scripts/pruefe_profil.py`` sie
    von einem gewoehnlichen Programmierfehler unterscheiden koennen: bei
    einem Profilfehler hilft ein Blick in ``workshop/<name>/profil.toml``,
    bei allem anderen nicht."""


#: Das eingebaute Vorgabeprofil -- **exakt die Werte, die vor dem Umbau im
#: Code standen** (Stand 06.09.2026, Zweig ``feat/workshop-profil``).
#:
#: Es ist nicht "irgendein sinnvoller Ausgangspunkt", sondern die
#: Beweisgrundlage: ``workshop/dortmund-2026/profil.toml`` traegt dieselben
#: Werte, und ein Test vergleicht beide Baeume Feld fuer Feld. Wer hier
#: etwas aendert, aendert das Verhalten ohne Profil -- also fuer jeden
#: Prozess, in dem ``IT_WORKSHOP`` nicht gesetzt ist.
VORGABE_WERTE: dict[str, Any] = {
    "beschreibung": (
        "Zweitaegiger Theaterworkshop mit einem Migrantinnenverein in "
        "Dortmund, 05./06.09.2026."
    ),
    "sprache": {
        # Prompt- und Chatsprache. Steuert spaeter auch die Whisper-Sprache.
        "code": "de",
        # Wie die Gruppe angesprochen wird. Deutsch "ihr", italienisch "voi".
        "anrede": "ihr",
    },
    "zielgruppe": {
        # Der Satz, der sechsmal wortgleich in den Prompts steht.
        "beschreibung": "junge Frauen zwischen 15 und 18 Jahren",
        # Der Traegerkontext in Klammern; leer = keine Klammer.
        "traeger": "Migrantinnenverein Dortmund",
    },
    "orte": {
        # Wie die Prompts die Spielorte beschreiben. Seit dem 06.09.2026
        # steht hier bewusst KEINE Beispielliste: die Orte nennt die Gruppe,
        # ein Beispiel im Prompt wird nachgeplappert.
        "beschreibung": (
            "altersgerechte, lebensnahe Orte aus der Welt der Gruppe -- welche,\n"
            "bestimmt die Gruppe selbst (keine Beispielorte aus dieser Anweisung)."
        ),
        # Was ausgeschlossen ist.
        "ausgeschlossen": ["Club", "Disko", "Alkohol", "Nachtleben", "Drogen"],
        # Wo das fertige Stueck gezeigt wird.
        "auffuehrung": "auf einem oeffentlichen Platz oder in einer grossen Halle",
    },
    "konflikt": {
        # Was an Stoff drin sein darf, und was nicht.
        "erlaubt": "Familie, Erwartungen, Zugehoerigkeit, Sprache, Zukunft",
        "ausgeschlossen": "Keine Gewaltverherrlichung",
    },
}


def _einfrieren(wert: Any) -> Any:
    """Macht aus dem geladenen TOML-Baum etwas Unveraenderliches.

    Ein Profil ist Konfiguration, keine Zustandsablage: wer es aus Versehen
    veraendert, aendert stillschweigend das Verhalten aller spaeteren
    Aufrufe im selben Prozess. Dicts werden zu ``MappingProxyType``, Listen
    zu Tupeln; alles andere bleibt, wie es ist."""
    if isinstance(wert, dict):
        return MappingProxyType({k: _einfrieren(v) for k, v in wert.items()})
    if isinstance(wert, list):
        return tuple(_einfrieren(v) for v in wert)
    return wert


def _vereinige(vorgabe: Any, eigen: Any) -> Any:
    """Legt ``eigen`` ueber ``vorgabe`` -- Ebene fuer Ebene, nicht als Ganzes.

    Ein Profil, das nur ``[zielgruppe] beschreibung = "..."`` setzt, soll den
    Traeger aus der Vorgabe behalten und nicht verlieren. Nur Dicts werden
    vereinigt; eine Liste ersetzt die Liste der Vorgabe vollstaendig (eine
    halb ueberschriebene Ortsliste waere schlimmer als eine falsche)."""
    if isinstance(vorgabe, dict) and isinstance(eigen, dict):
        zusammen = dict(vorgabe)
        for schluessel, wert in eigen.items():
            zusammen[schluessel] = _vereinige(vorgabe.get(schluessel), wert)
        return zusammen
    return eigen


@dataclass(frozen=True)
class Profil:
    """Ein geladenes Workshop-Profil -- eingefroren, ohne Zustand.

    ``name`` ist der Verzeichnisname (``dortmund-2026``) bzw. ``VORGABE_NAME``
    fuer das eingebaute Profil. ``verzeichnis`` ist ``None``, solange kein
    Profil eingehaengt ist -- dann gibt es auch keine Overlay-Dateien."""

    name: str
    verzeichnis: Path | None
    werte: Any

    def wert(self, pfad: str, vorgabe: Any = None) -> Any:
        """Ein Feld ueber seinen Punktpfad (``"zielgruppe.traeger"``).

        Liefert ``vorgabe``, wenn irgendein Schritt des Pfades fehlt -- ein
        Leser soll an einem nicht gesetzten Feld nicht abstuerzen, sondern
        das melden koennen, was er als Ersatz nimmt."""
        stelle: Any = self.werte
        for schritt in pfad.split("."):
            if not isinstance(stelle, (dict, MappingProxyType)):
                return vorgabe
            if schritt not in stelle:
                return vorgabe
            stelle = stelle[schritt]
        return stelle


#: Der Name des eingebauten Profils. Er steht in Logzeilen und in der
#: Ausgabe von ``scripts/pruefe_profil.py``; er ist kein Verzeichnis.
VORGABE_NAME = "(eingebaut)"

#: Das eingebaute Profil als fertiges Objekt -- einmal eingefroren, von
#: allen geteilt.
VORGABE = Profil(VORGABE_NAME, None, _einfrieren(VORGABE_WERTE))


def basis() -> Path:
    """Das Verzeichnis, unter dem die Profile liegen."""
    eigen = os.environ.get(BASIS_VARIABLE)
    if eigen:
        return Path(eigen).expanduser()
    return _PAKET.parent / "workshop"


def verzeichnis_fuer(name: str) -> Path:
    """Wo das Profil ``name`` liegt.

    Der Name kommt aus einer Umgebungsvariable, also aus der Hand eines
    Menschen -- die Pruefung auf Pfadtrenner steht deshalb hier und nicht
    im Vertrauen darauf, dass niemand ``IT_WORKSHOP=../../etc`` schreibt."""
    if not name or name != name.strip() or "/" in name or "\\" in name or name.startswith("."):
        raise ProfilFehler(
            f"{VARIABLE}={name!r} ist kein Profilname. Erlaubt ist der "
            f"Verzeichnisname unter {basis()}, z. B. 'dortmund-2026'."
        )
    return basis() / name


def lade(name: str) -> Profil:
    """Laedt das Profil ``name`` von der Platte.

    Wirft ``ProfilFehler`` mit einer Meldung, die sagt, was zu tun ist --
    fehlendes Verzeichnis, fehlende Datei, kaputtes TOML, fehlendes
    Pflichtfeld. Kein Halbstart: lieber gar kein Bot als einer mit dem
    falschen Rahmen."""
    verz = verzeichnis_fuer(name)
    datei = verz / DATEI
    if not verz.is_dir():
        raise ProfilFehler(
            f"Workshop-Profil {name!r} fehlt: {verz} gibt es nicht. "
            f"Entweder {VARIABLE} korrigieren oder das Verzeichnis anlegen "
            f"(Anleitung: docs/workshop-profil-umbau-2026-09-06.md)."
        )
    if not datei.is_file():
        raise ProfilFehler(
            f"Workshop-Profil {name!r} hat keine {DATEI}: {datei} fehlt."
        )
    try:
        roh = tomllib.loads(datei.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as fehler:
        raise ProfilFehler(f"{datei} ist kein gueltiges TOML: {fehler}") from fehler
    except OSError as fehler:
        raise ProfilFehler(f"{datei} ist nicht lesbar: {fehler}") from fehler

    werte = _vereinige(VORGABE_WERTE, roh)
    profil = Profil(name, verz, _einfrieren(werte))
    fehlend = [feld for feld in PFLICHTFELDER if not profil.wert(feld)]
    if fehlend:
        raise ProfilFehler(
            f"{datei}: Pflichtfeld(er) leer oder nicht gesetzt: "
            f"{', '.join(fehlend)}"
        )
    return profil


#: Geladene Profile je Name. Ein Profil wird einmal je Prozess von der Platte
#: gelesen -- anders als die Prompts ist es **kein** Hot-Reload-Kandidat: eine
#: halb gespeicherte ``profil.toml`` mitten im Workshop waere genau der
#: Halbstart, den dieses Modul verhindern soll.
_GELADEN: dict[str, Profil] = {}


def aktiv() -> Profil:
    """Das Profil dieses Prozesses -- aus ``IT_WORKSHOP``, sonst die Vorgabe.

    Die Variable wird bei **jedem** Aufruf gelesen und das Ergebnis je Name
    zwischengespeichert. Das kostet einen Dict-Zugriff und haelt die Zusage
    aus D.5 der Analyse: kein Profilzustand in einem Modul-Global, das ein
    zweites Profil im selben Prozess falsch beantworten wuerde."""
    name = (os.environ.get(VARIABLE) or "").strip()
    if not name:
        return VORGABE
    profil = _GELADEN.get(name)
    if profil is None:
        profil = lade(name)
        _GELADEN[name] = profil
    return profil


def name() -> str:
    """Der Name des aktiven Profils -- der Cache-Schluessel der Prompts."""
    return aktiv().name


def vergiss() -> None:
    """Leert den Profil-Zwischenspeicher. Nur fuer Tests und
    ``scripts/pruefe_profil.py`` -- im Betrieb wird ein Profil nie neu
    geladen (siehe ``_GELADEN``)."""
    _GELADEN.clear()
    _PLATZHALTER.clear()


#: Die Platzhalter je Profilname. Sie haengen nur an ``profil.toml``, und die
#: wird je Prozess einmal gelesen -- also einmal bauen, nicht je Prompt.
_PLATZHALTER: dict[str, dict[str, str]] = {}


def _liste(wert: Any, trenner: str = ", ") -> str:
    """Eine Liste aus dem Profil als Fliesstext. Ein einzelner String bleibt,
    wie er ist -- wer ``ausgeschlossen = "Club und Disko"`` schreibt, meint
    genau das."""
    if isinstance(wert, (tuple, list)):
        return trenner.join(str(teil) for teil in wert)
    return "" if wert is None else str(wert)


def platzhalter(profil: Profil | None = None) -> dict[str, str]:
    """Die Werte, die ``{{...}}`` in einem Prompt fuellen.

    Nur die **einzeiligen** Werte aus ``profil.toml``. Zusammenhaengende
    Prosa (der Rahmenblock, ein Formen-Regelblock) kommt nicht von hier,
    sondern als Markdown-Datei aus ``workshop/<name>/prompts/`` --
    ``anweisungen.platzhalter()`` legt beides zusammen. Der Grund steht in
    E.1 Frage 1 der Analyse: wer Prosa in eine Konfigurationsdatei presst,
    bekommt unlesbare Blockskalare; wer Zahlen in Markdown laesst, kann sie
    nicht pruefen.

    Ein Wert wird eingesetzt, **wie er dasteht** -- er wird nicht neu
    umbrochen. Ein Platzhalter gehoert deshalb an eine Stelle im Prompt, an
    der der Wert in eine Zeile passt; alles andere ist ein Baustein und
    keine Variable."""
    profil = profil or aktiv()
    fertig = _PLATZHALTER.get(profil.name)
    if fertig is not None:
        return fertig
    werte = {
        "beschreibung": _liste(profil.wert("beschreibung", "")),
        "sprache": _liste(profil.wert("sprache.code", "")),
        "anrede": _liste(profil.wert("sprache.anrede", "")),
        "zielgruppe": _liste(profil.wert("zielgruppe.beschreibung", "")),
        "zielgruppe_traeger": _liste(profil.wert("zielgruppe.traeger", "")),
        "orte": _liste(profil.wert("orte.beschreibung", "")),
        "orte_ausgeschlossen": _liste(profil.wert("orte.ausgeschlossen", ())),
        "auffuehrungsort": _liste(profil.wert("orte.auffuehrung", "")),
        "konflikt_erlaubt": _liste(profil.wert("konflikt.erlaubt", "")),
        "konflikt_ausgeschlossen": _liste(profil.wert("konflikt.ausgeschlossen", "")),
    }
    _PLATZHALTER[profil.name] = werte
    return werte
