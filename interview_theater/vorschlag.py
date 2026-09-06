"""Deterministische Vorschlagsbloecke in der Bot-Antwort (05.09.2026).

**Warum es das gibt.** Begriffe (Phase 1), Fragen (Phase 2) und Kernthema
bzw. Figuren (Phase 4) sind die drei Stellen, an denen am Workshoptag das
Ablegen scheiterte: der Bot schlug etwas vor, die Gruppe stimmte zu -- und
der Absichtserkenner sah live nur ein Fenster von ein bis drei Nachrichten
und schrieb ``entschieden`` (Journalnotiz) statt ``begriffe_setzen``
(Arbeitsstand). Die Zustimmung war da, der Wert nicht.

Ein Knopf traegt den Wert selbst (``knoepfe.py``) -- dafuer muss der Wert
aber **eindeutig aus dem Antworttext** herauszuholen sein. Raten ist hier
ausdruecklich verboten: lieber keine Leiste als eine, die den falschen Text
speichert. Deshalb ein **fester Marker**, den der Gespraechs-Prompt
(``prompts/system.md``, ``prompts/phasen/1.md``, ``2.md``, ``4.md``)
anweist:

.. code-block:: text

    VORSCHLAG BEGRIFFE:
    Heimat, Arbeit, Angst, Ankommen

Eine Markerzeile, danach die Zeilen bis zur ersten Leerzeile (oder bis zum
naechsten Marker). Fehlt der Marker, gibt es keine Leiste -- kein Raten.
Die Gruppe sieht den Text **ohne** Markerzeile (``ohne_marker``); der Marker
ist Technik, kein Inhalt.
"""

import re

#: Die Arten, die ueber einen Vorschlagsblock deterministisch verarbeitet
#: werden koennen. Der Name ist zugleich das Arbeitsstand-Feld (begriffe,
#: fragen, kernthema, rahmen) bzw. der Name einer Auswahl-Liste.
#:
#: Seit dem 05.09.2026 abends sind vier Auswahl-Marker dazugekommen, die
#: **nichts** direkt speichern, sondern je Zeile einen Knopf ergeben
#: (``knoepfe.sende_mit_speicherleiste``):
#:
#: * ``richtungen`` -- Stufe 1 der zweistufigen Kernthema-Wahl (grobe
#:   Richtungen, aus denen die Gruppe eine antippt; danach kommen mit
#:   ``kernthema`` die Formulierungen dazu).
#: * ``namen``   -- Namensvorschlaege fuer EINE Figur (Ebene 1).
#: * ``duktus``  -- alternative Sprachduktus-Beschreibungen fuer EINE Figur
#:   (Ebene 2).
#: * ``rahmen``  -- Ort/Zeit/Anlass-Vorschlaege (Phase 5).
#:
#: Dazu am selben Tag die beiden Marker der Phase 6 (``szenenfolge.py``):
#: ``szenenfolge`` -- die Szenenfolge als eine Zeile je Szene -- und
#: ``szene`` -- die fehlenden Felder EINER Szene als ``feld: Wert`` je Zeile.
#: Sie stehen bewusst in derselben Liste und nutzen denselben
#: Marker-Mechanismus: es gibt einen Weg, einen Vorschlag deterministisch zu
#: verarbeiten, nicht zwei.
ARTEN = (
    "begriffe", "fragen", "kernthema", "kernfrage", "figuren",
    "richtungen", "namen", "duktus", "rahmen",
    "szenenfolge", "szene",
    # Phase 5 seit dem Umbau vom 05.09.2026 nachts: der Bogen in Zeile 1,
    # das Ende in Zeile 2, danach je Szene eine Zeile. Ein Marker fuer
    # beides, weil es EINE Entscheidung ist -- die Geschichte und ihre
    # Szenenfolge trennt die Gruppe nicht.
    "geschichte",
    # Die Verfeinerungsebene der Fragen (Phase 2, 06.09.2026, Birk): NACH dem
    # Festlegen der Frageliste prueft der Bot sie auf sensible Themen und
    # schlaegt je heikler Frage eine Einleitung vor (``einleitungen``),
    # danach den Eroeffnungs- und Abschlusstext (``eroeffnung``). Beide
    # laufen ueber die Grundleiste wie jeder andere Vorschlag -- es gibt
    # einen Weg, einen Vorschlag abzunehmen, nicht drei.
    "einleitungen", "eroeffnung",
    # Die weichen Fragefassungen (06.09.2026, 10:18, Birk): eine sensible
    # Frage wird zu EINEM Gespraechsstueck umformuliert, statt eine
    # Einleitung davorzuhaengen. Marker ``VORSCHLAG FRAGEN WEICH:``, je
    # Zeile ``<Nummer> — <weiche Fassung>``; die Art heisst intern
    # ``fragen_weich`` wie die Spalte.
    "fragen_weich",
    # Die Mehrfachauswahl der Phase 2 (06.09.2026, Birk): zehn Fragen zur
    # Wahl, aus denen die Gruppe genau drei antippt. Eigener Marker und
    # nicht ``fragen``, weil ein FRAGENAUSWAHL-Block nichts speichert --
    # er wird zu zehn Knoepfen (``knoepfe.biete_fragenauswahl``).
    "fragenauswahl",
)

#: Die Markerzeile. Grossbuchstaben, weil sie im Fliesstext nicht vorkommt
#: und ein Modell sie zuverlaessig wiederholt; der Doppelpunkt macht sie
#: auch fuer eine mitlesende Gruppe als Technik erkennbar.
MARKER = "VORSCHLAG {art}:"

_ZEILE = re.compile(
    r"^\s*VORSCHLAG\s+"
    # ``FRAGEN WEICH`` steht VOR ``FRAGEN``: eine Alternation nimmt die
    # erste passende, und ``FRAGEN`` allein wuerde die weichen Fassungen als
    # neue Frageliste verbuchen.
    r"(BEGRIFFE|FRAGENAUSWAHL|FRAGEN\s+WEICH|FRAGEN|KERNTHEMA|KERNFRAGE"
    r"|FIGUREN|RICHTUNGEN"
    r"|NAMEN|DUKTUS|RAHMEN"
    r"|SZENENFOLGE|GESCHICHTE|SZENE|EINLEITUNGEN|EROEFFNUNG)"
    r"\s*:\s*(.*)$",
    re.IGNORECASE,
)


def marker(art: str) -> str:
    """Die Markerzeile fuer eine Art -- eine Stelle statt vier Zeichenketten
    im Prompt und im Test."""
    # ``fragen_weich`` heisst im Text ``FRAGEN WEICH`` -- ein Marker ist
    # etwas, das ein Modell zuverlaessig abschreibt, und ein Unterstrich
    # gehoert nicht dazu.
    return MARKER.format(art=art.upper().replace("_", " "))


def _zerlege(text: str) -> dict[str, str]:
    """Alle Vorschlagsbloecke eines Textes: art -> Wert (mehrzeilig, getrimmt).

    Ein Block endet an der ersten Leerzeile oder am naechsten Marker. Kommt
    dieselbe Art zweimal vor, gewinnt die letzte -- das ist die, die der Bot
    zuletzt gemeint hat.
    """
    gefunden: dict[str, str] = {}
    zeilen = (text or "").splitlines()
    i = 0
    while i < len(zeilen):
        treffer = _ZEILE.match(zeilen[i])
        if treffer is None:
            i += 1
            continue
        art = treffer.group(1).lower()
        # ``FRAGEN WEICH`` -> ``fragen_weich``: im Text zwei Woerter, im Code
        # eine Art (und derselbe Name wie die Spalte).
        art = re.sub(r"\s+", "_", art)
        teile = [treffer.group(2).strip()] if treffer.group(2).strip() else []
        i += 1
        while i < len(zeilen):
            zeile = zeilen[i]
            if not zeile.strip() or _ZEILE.match(zeile):
                break
            teile.append(zeile.strip())
            i += 1
        wert = "\n".join(t for t in teile if t).strip()
        if wert:
            gefunden[art] = wert
    return gefunden


def lies(text: str, art: str) -> str | None:
    """Der Wert des Vorschlagsblocks dieser Art, oder None.

    None heisst: **keine Leiste**. Der Aufrufer raet nicht nach, sondern
    schickt die Antwort ohne Knoepfe -- die naechste Bot-Antwort bekommt die
    Leiste wieder, weil der Wert weiterhin leer ist.
    """
    return _zerlege(text).get(art)


def alle(text: str) -> dict[str, str]:
    """Alle Vorschlagsbloecke eines Textes auf einmal -- fuer den Aufrufer,
    der entscheiden muss, WELCHE Leiste unter die Nachricht gehoert
    (``knoepfe.sende_mit_speicherleiste``). Eine Nachricht traegt im
    Normalfall genau einen Block; kommen zwei, entscheidet die Reihenfolge
    dort, nicht hier."""
    return _zerlege(text)


def zeilen(wert: str) -> list[str]:
    """Die Zeilen eines mehrzeiligen Vorschlagsblocks, ohne fuehrende
    Aufzaehlungszeichen und ohne Leerzeilen -- eine Zeile, ein Knopf.

    Dieselbe Saeuberung wie in ``figuren()``: Modelle schreiben mal ``1) ``,
    mal ``- ``, und die Ziffer gehoert nicht in die Knopfbeschriftung."""
    ergebnis = []
    for zeile in (wert or "").splitlines():
        roh = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", zeile).strip()
        if roh:
            ergebnis.append(roh)
    return ergebnis


def _normal(zeile: str) -> str:
    return re.sub(r"\s+", " ", (zeile or "")).strip().lower()


def ohne_marker(text: str) -> str:
    """Der Antworttext, wie die Gruppe ihn sehen soll: ohne die
    Markerzeilen, mit dem Inhalt darunter.

    Nur die Markerzeile faellt weg, nie der Vorschlag selbst -- er ist ja
    genau das, worueber die Gruppe entscheidet. Doppelte Leerzeilen, die
    dabei entstehen koennen, werden eingedampft.

    **Keine Doppelung** (06.09.2026 12:50, Gruppe 1): das Modell schrieb die
    Eroeffnung einmal im Fliesstext UND einmal im Block ``VORSCHLAG
    EROEFFNUNG:`` -- die Gruppe las 600 Zeichen zweimal untereinander. Eine
    Fliesstextzeile, die wortgleich (nach Whitespace/Kleinschreibung) auch im
    Blockinhalt steht, wird deshalb aus dem Fliesstext gestrichen; der Block
    behaelt sie, denn er ist die Fassung, ueber die die Gruppe entscheidet."""
    roh = (text or "").splitlines()
    im_block: set[str] = set()
    aktiv = False
    for z in roh:
        if _ZEILE.match(z) is not None:
            aktiv = True
            continue
        if aktiv:
            if not z.strip():
                aktiv = False
            elif len(_normal(z)) >= 40:
                im_block.add(_normal(z))
    zeilen: list[str] = []
    aktiv = False
    for z in roh:
        if _ZEILE.match(z) is not None:
            aktiv = True
            continue
        if aktiv and not z.strip():
            aktiv = False
        if not aktiv and _normal(z) in im_block:
            continue
        zeilen.append(z)
    zusammen = "\n".join(zeilen)
    return re.sub(r"\n{3,}", "\n\n", zusammen).strip()


def ohne_block(text: str, art: str) -> str:
    """Der Antworttext ohne den Block dieser Art -- Markerzeile UND Inhalt.

    Der Gegensatz zu ``ohne_marker``, und er hat genau einen Anlass
    (06.09.2026): ``VORSCHLAG FRAGENAUSWAHL:`` wird zu zehn Knoepfen, und die
    Fragen stehen dann auf den Knoepfen. Blieben sie zusaetzlich im Text,
    laese die Gruppe dieselben zehn Zeilen zweimal untereinander -- auf einem
    Telefon ist das eine halbe Bildschirmseite Doppelung.

    Ueberall sonst gilt weiter ``ohne_marker``: der Vorschlag ist das,
    worueber die Gruppe entscheidet, und er muss lesbar dastehen.
    """
    zeilen = (text or "").splitlines()
    ergebnis: list[str] = []
    i = 0
    while i < len(zeilen):
        treffer = _ZEILE.match(zeilen[i])
        if treffer is not None and treffer.group(1).lower() == art.lower():
            i += 1
            while i < len(zeilen):
                if not zeilen[i].strip() or _ZEILE.match(zeilen[i]):
                    break
                i += 1
            continue
        ergebnis.append(zeilen[i])
        i += 1
    zusammen = "\n".join(z for z in ergebnis if _ZEILE.match(z) is None)
    return re.sub(r"\n{3,}", "\n\n", zusammen).strip()


#: Trennzeichen in einer Figurenzeile: "Name — ein Satz — Interview 2".
#: Gedankenstrich (das, worum der Prompt bittet) und der einfache
#: Bindestrich mit Leerzeichen drumherum, weil Modelle beides liefern.
_FIGUR_TRENNER = re.compile(r"\s+[—–]\s+|\s+-\s+")


def figuren(wert: str) -> list[tuple[str, str]]:
    """Zerlegt den Figuren-Vorschlagsblock in ``(Name, Beschreibung)``.

    Eine Zeile je Figur, Form ``Name — ein Satz — Interview N``. Die dritte
    Spalte (das Interview) wird hier bewusst nicht ausgewertet: die
    Zuordnung Figur -> Interview entsteht im Gespraech
    (``erkenner.figur_quelle_setzen``, ``kontext._baue_figurenhinweis``) und
    braucht ein Belegzitat -- sie aus einem Vorschlagstext zu raten waere
    genau der Fehler, den dieses Modul vermeidet.

    Fuehrende Aufzaehlungszeichen ("- ", "1. ") fallen weg. Zeilen ohne
    Namen fallen raus."""
    ergebnis: list[tuple[str, str]] = []
    for zeile in (wert or "").splitlines():
        roh = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", zeile).strip()
        if not roh:
            continue
        teile = [t.strip() for t in _FIGUR_TRENNER.split(roh)]
        name = teile[0].strip(" .;:")
        if not name:
            continue
        beschreibung = teile[1].strip() if len(teile) > 1 else ""
        ergebnis.append((name, beschreibung))
    return ergebnis


def enthaelt_block(text: str | None) -> bool:
    """Steht irgendein ``VORSCHLAG <ART>:``-Marker in diesem Text?

    Gebraucht vom Wiederholungsfilter (ablauf.antworte, 06.09.2026): eine
    Antwort mit Vorschlagsblock traegt einen Wert und wird nie als
    Wiederholung verworfen -- auch wenn sie dem vorigen Vorschlag aehnelt
    (eine Ueberarbeitung tut das immer)."""
    return any(_ZEILE.match(z) is not None for z in (text or "").splitlines())
