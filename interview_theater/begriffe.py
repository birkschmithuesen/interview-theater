"""Zuordnung Verdichtung <-> Kernbegriffe der Gruppe (06.09.2026).

Die Gruppe legt in Phase 1 ihre Kernbegriffe fest; sie stehen als Freitext in
``arbeitsstand.begriffe`` (\"Rassismus, Liebe, Spass, Streit\"). Jedes
ausgewertete Interview (eine ``verdichtung``) soll den Begriffen zugeordnet
werden, zu denen es etwas beitraegt -- **n:m**: ein Interview traegt mehrere
Begriffe, ein Begriff sammelt mehrere Interviews.

**Deterministisch, kein Modellaufruf.** Der Weg ist ein Begriffsabgleich
gegen die Zusammenfassung und die Kernthemen der Verdichtung -- also gegen
Text, den der Verdichter schon erzeugt und dessen Zitate schon geprueft sind
(``zitat.pruefe``). Gruende, in der Reihenfolge ihres Gewichts:

1. **Kein zusaetzlicher Aufruf am Workshoptag.** Die Zuordnung faellt beim
   Verdichten ab, ohne Wartezeit, ohne Kosten und ohne einen weiteren Weg,
   auf dem ein Modell etwas ueber einen interviewten Menschen behaupten kann.
2. **Nachvollziehbar und stabil.** Dieselbe Verdichtung ergibt immer dieselben
   Tags; ein Tag ist erklaerbar (\"das Wort steht in der Zusammenfassung\").
   Ein Modell wuerde je Lauf leicht andere Zuordnungen liefern -- auf einer
   Seite, die die Gruppe waehrend des Workshops mehrfach neu laedt, ist das
   Rauschen.
3. **Kein Prompt-Risiko.** Ein neuer Prompt haette einen Korpuslauf gegen das
   echte Modell verlangt (AGENTS.md, \"Prompt geaendert? -> Korpus laufen
   lassen\"), der waehrend des laufenden Workshops nicht zu fahren ist.

Der Preis ist bekannt: ein Interview, das ueber \"Zuhause\" spricht, ohne das
Wort zu sagen, bekommt den Tag nicht. Das ist die richtige Richtung des
Fehlers -- ein fehlender Tag ist eine Luecke, ein erfundener Tag eine
Behauptung.

Die Zuordnung ist **abgeleitete Anzeige, keine Entscheidung der Gruppe**: sie
wird bei jedem Lauf neu berechnet und ersetzt (``repo.setze_verdichtung_begriffe``),
und sie ruehrt die Verdichtung selbst nicht an (AGENTS.md: Verdichtungen
werden nie nachtraeglich geaendert).
"""

import re
import unicodedata

#: Woran eine Begriffsliste zerlegt wird. Der Freitext kommt aus dem Chat --
#: mal \"Heimat, Arbeit, Angst\", mal eine Zeile je Begriff, mal mit
#: Aufzaehlungsstrichen.
_TRENNER = re.compile(r"[,;\n/]|(?:\s+·\s+)|(?:\s+•\s+)")

#: Fuehrende Aufzaehlungszeichen und Nummerierungen einer Zeile.
_AUFZAEHLUNG = re.compile(r"^\s*(?:[-–—*•]+|\d+[.)])\s*")

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

#: Ab dieser Laenge (nach Normalisierung) darf ein Begriff ueberhaupt
#: matchen. Kuerzere Woerter (\"Ich\", \"Wir\", \"EU\") erzeugen im Deutschen zu
#: leicht Zufallstreffer in einem Fliesstext.
MINDESTLAENGE = 4

#: Endungen, die vom Wortende genommen werden, bevor verglichen wird -- eine
#: bewusst dumme, kurze Liste statt eines Stemmers (keine neuen
#: Abhaengigkeiten). \"Liebe\" trifft damit \"Lieben\", \"Sorge\" trifft
#: \"Sorgen\". Abgeschnitten wird nur, solange der Rest noch
#: ``MINDESTLAENGE`` Zeichen hat.
_ENDUNGEN = ("ungen", "enden", "ende", "keit", "heit", "en", "er", "es", "em", "e", "n", "s")


def normalisiere(text: str) -> str:
    """Kleinschreibung, Umlaute ausgeschrieben, Whitespace zu einem
    Leerzeichen. Wie ``zitat.normalisiere`` bewusst arm an Regeln."""
    text = unicodedata.normalize("NFC", text or "").lower().translate(_UMLAUTE)
    return re.sub(r"\s+", " ", text).strip()


def stamm(wort: str) -> str:
    """Der Vergleichsstamm eines Wortes: normalisiert und um genau eine
    Flexionsendung gekuerzt, solange ``MINDESTLAENGE`` gewahrt bleibt."""
    wort = re.sub(r"[^a-z0-9 ]+", "", normalisiere(wort))
    for endung in _ENDUNGEN:
        if wort.endswith(endung) and len(wort) - len(endung) >= MINDESTLAENGE:
            return wort[: -len(endung)]
    return wort


def zerlege(freitext: str | None) -> list[str]:
    """Zerlegt ``arbeitsstand.begriffe`` in einzelne Begriffe.

    Reihenfolge bleibt die der Gruppe, Dubletten (auch solche, die sich nur
    in Gross-/Kleinschreibung unterscheiden) fallen weg. Der Wortlaut bleibt
    unangetastet -- auf der Seite steht der Begriff so, wie die Gruppe ihn
    aufgeschrieben hat."""
    gesehen: set[str] = set()
    ergebnis: list[str] = []
    for stueck in _TRENNER.split(freitext or ""):
        begriff = _AUFZAEHLUNG.sub("", stueck or "").strip(" \t\"'„“()")
        if not begriff:
            continue
        schluessel = normalisiere(begriff)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        ergebnis.append(begriff)
    return ergebnis


def passt(begriff: str, text: str) -> bool:
    """Kommt ``begriff`` in ``text`` vor?

    Mehrwortige Begriffe (\"Ankommen in Deutschland\") werden als
    normalisierter Teilstring gesucht. Einwortige ueber ihren Stamm am
    Wortanfang: \"Liebe\" trifft \"Lieben\" und \"Liebesgeschichte\", aber nicht
    \"Belieben\" -- Komposita im Deutschen haengen hinten an, nicht vorn."""
    grund = stamm(begriff)
    if len(grund) < MINDESTLAENGE:
        return False
    heu = normalisiere(text)
    if " " in normalisiere(begriff):
        return normalisiere(begriff) in heu
    return re.search(r"(?<![a-z0-9])" + re.escape(grund) + r"[a-z0-9]*", heu) is not None


def ordne_zu(begriffe: list[str], texte) -> list[str]:
    """Welche der ``begriffe`` in irgendeinem der ``texte`` vorkommen --
    in der Reihenfolge der Begriffsliste der Gruppe."""
    heu = " \n ".join(t for t in texte if t)
    return [b for b in begriffe if passt(b, heu)]


def texte_der_verdichtung(zusammenfassung: str | None, themen) -> list[str]:
    """Die Textgrundlage einer Verdichtung fuer den Abgleich: Zusammenfassung,
    Kernthemen und deren Kurzformen.

    **Ohne Belegzitate und ohne Transkript.** Beides ist der Wortlaut eines
    interviewten Menschen; ein Tag daraus abzuleiten hiesse, ein einzelnes
    hingesagtes Wort zur Aussage des Interviews zu machen. Die Zusammenfassung
    und die Kernthemen sind das Ergebnis der Auswertung -- das ist die Ebene,
    auf der die Begriffe der Gruppe liegen."""
    texte: list[str | None] = [zusammenfassung]
    for thema in themen or []:
        if isinstance(thema, dict):
            texte.append(thema.get("thema"))
            texte.append(thema.get("kurz"))
        else:
            texte.append(thema["thema"])
            try:
                texte.append(thema["kurz"])
            except (IndexError, KeyError):
                pass
    return [t for t in texte if t]
