"""Der Vorspann vor dem Text: wo, worum, welche Form, welche Szenen, wer
vorkommt (07.09.2026).

**Warum es das gibt.** Phase 6 lieferte die Kurzgeschichte ohne Vorspann. Die
Gruppe -- und jeder, der den Text spaeter liest -- hat dreizehn Figuren vor
sich, ohne zu wissen, wer wer ist. Der Vorspann ist ausdruecklich **nicht Teil
der Geschichte**, sondern steht davor: eine Besetzungsliste mit dem Rahmen
darueber.

**Deterministisch, ohne Modellaufruf.** Alles kommt aus ``figur.name``,
``figur.beschreibung``, ``szene.titel``, ``szene.form`` und ``arbeitsstand.*``.
Das ist Absicht und keine Sparmassnahme: der Vorspann darf nichts erfinden, und
er soll bei jedem Abruf identisch sein -- im Chat, auf der Gruppenseite und im
Textbuch-Export. Ein Modell dazwischen haette drei verschiedene Fassungen
derselben Liste erzeugt.

**Datengetrieben wie ``kontext.baue``**: jeder Block faellt weg, solange die
zugrundeliegenden Daten leer sind. Eine Gruppe ohne Setting bekommt keine
leere Ueberschrift "Wo und wann".

Drei Stellen lesen dasselbe: ``daten()`` liefert die reinen Werte (Dicts rein,
Dict raus -- keine Datenbank), ``als_markdown()`` den Export, ``als_chattext()``
die Telegram-Fassung ohne Rauten. ``aus_datenbank()`` ist die Abkuerzung fuer
alle, die eine ``repo``-Verbindung haben; die Weboberflaeche geht ueber
``daten()``, weil sie read-only und ohne ``repo`` liest (siehe
``web_daten.py``).
"""

from __future__ import annotations

import re

#: Die Schaerfungsformeln aus Phase 5. Am echten Material gemessen
#: (06.09.2026): ``figur.beschreibung`` traegt die Schaerfungsnotiz oft **ohne
#: Trennzeichen angeklebt** ("kaempft mit sich selbst liefert den Hintergrund
#: fuer ihre Ablehnung", 371 Zeichen). Es gibt dort kein Satzende, an dem sich
#: schneiden liesse -- also wird an der Formel geschnitten, mit der die Notiz
#: beginnt.
#:
#: Beide Schreibweisen, mit und ohne Umlaut: die Notizen kommen aus einem
#: Sprachmodell, das mal "begruendet" und mal "begründet" schreibt, und eine
#: Liste, die nur eine Haelfte kennt, schneidet die andere nicht.
SCHAERFUNGSFORMELN = (
    "macht deutlich",
    "liefert",
    "zeigt",
    "begruendet",
    "begründet",
    "erklaert",
    "erklärt",
    "verstaerkt",
    "verstärkt",
    "unterstreicht",
)

_FORMEL = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in SCHAERFUNGSFORMELN) + r")\b",
    re.IGNORECASE,
)

#: Ein Satzende: Punkt, Ausrufe- oder Fragezeichen, gefolgt von Leerraum oder
#: Textende. Das Lookahead haelt Abkuerzungen und Zahlen zusammen ("z. B." hat
#: hinter dem ersten Punkt ein Leerzeichen -- deshalb steht die Formel-Regel
#: davor und gewinnt, wenn sie frueher greift).
_SATZENDE = re.compile(r"[.!?](?=\s|$)")

#: Wie viel Text mindestens vor einer Formel stehen muss, damit an ihr
#: geschnitten wird. Ohne diese Untergrenze wuerde "Mira zeigt Haerte." zu
#: "Mira" -- die Formeln sind Notiz-Anfaenge, keine verbotenen Woerter, und am
#: gemessenen Fall stehen 23 Zeichen davor. Darunter gilt das Satzende.
MINDEST_ZEICHEN = 20

#: Obergrenze fuer einen "ersten Satz". Ein Absatz ohne einen einzigen Punkt
#: und ohne Formel bliebe sonst in voller Laenge stehen und machte aus der
#: Besetzungsliste wieder Fliesstext.
GRENZE = 200

_ABSCHLUSS = " ,;:—–- \t"


def erster_satz(text: str | None, grenze: int = GRENZE) -> str:
    """Der erste Satz einer Figurenbeschreibung -- ohne die Schaerfungsnotiz.

    Geschnitten wird am **frueheren** der beiden Punkte: am Beginn einer
    Schaerfungsformel (``SCHAERFUNGSFORMELN``, nur wenn ``MINDEST_ZEICHEN``
    davor stehen) oder am ersten Satzende. Bleibt beides aus, greift
    ``grenze``.

    Rein und ohne Datenbank, damit die Regel an einem String testbar ist."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    schnitt = len(text)
    treffer = _FORMEL.search(text)
    if treffer is not None and treffer.start() >= MINDEST_ZEICHEN:
        schnitt = treffer.start()
    satz = _SATZENDE.search(text)
    if satz is not None and satz.end() < schnitt:
        # Das Satzzeichen bleibt stehen: der Vorspann zitiert die
        # Beschreibung, er formuliert sie nicht um.
        schnitt = satz.end()
    kurz = text[:schnitt].strip(_ABSCHLUSS)
    if not kurz:
        kurz = text
    if len(kurz) > grenze:
        kurz = kurz[:grenze].rsplit(" ", 1)[0].strip(_ABSCHLUSS) + " …"
    return kurz


def _wert(zeile, feld: str) -> str:
    """Ein Feld aus einer ``sqlite3.Row`` oder einem Dict, immer als getrimmter
    String. Fehlt die Spalte (alte Datenbank), ist das Ergebnis leer statt ein
    Fehler."""
    if zeile is None:
        return ""
    try:
        wert = zeile[feld]
    except (IndexError, KeyError):
        return ""
    return "" if wert is None else str(wert).strip()


def _zahl(zeile, feld: str) -> int | None:
    """Dasselbe fuer eine Nummer: fehlt sie oder steht dort etwas, das keine
    Zahl ist, gilt sie als nicht gesetzt."""
    roh = _wert(zeile, feld)
    try:
        return int(roh)
    except (TypeError, ValueError):
        return None


def daten(
    rahmen: str | None,
    hauptkonflikt: str | None,
    format_: str | None,
    szenen,
    figuren,
) -> dict:
    """Die Werte des Vorspanns, aus schon gelesenen Zeilen.

    ``szenen`` und ``figuren`` sind Folgen von Zeilen (``sqlite3.Row`` oder
    Dict). **Weich geloeschte Figuren gehoeren nicht hinein** -- sie werden
    hier noch einmal ausgefiltert, obwohl ``repo.figuren`` und
    ``web_daten._figuren`` das schon tun: der Vorspann ist die eine Liste, die
    ein Aussenstehender liest, und eine entfernte Figur darin waere ein Fehler,
    der niemandem auffiele.

    Figuren ohne Namen fallen weg (ein Gedankenstrich ohne Namen ist keine
    Besetzung), Szenen behalten ihre Nummer auch dann, wenn sie keinen Titel
    haben."""
    szenen_zeilen = []
    for s in szenen or ():
        if _wert(s, "entfernt_am"):
            continue
        szenen_zeilen.append(
            {
                "nummer": _zahl(s, "nummer"),
                "titel": _wert(s, "titel"),
                # Nur die BESTAETIGTE Form (``szene.form``), nie der Vorschlag:
                # der Vorspann sagt, was gilt, und ein Vorschlag gilt nicht.
                "form": _wert(s, "form"),
            }
        )
    figuren_zeilen = []
    for f in figuren or ():
        if _wert(f, "entfernt_am"):
            continue
        name = _wert(f, "name")
        if not name:
            continue
        figuren_zeilen.append(
            {"name": name, "beschreibung": erster_satz(_wert(f, "beschreibung"))}
        )
    return {
        "rahmen": (rahmen or "").strip(),
        "hauptkonflikt": (hauptkonflikt or "").strip(),
        "format": (format_ or "").strip(),
        "szenen": szenen_zeilen,
        "figuren": figuren_zeilen,
    }


def aus_datenbank(conn, chat_id: int) -> dict:
    """``daten()`` fuer alle, die eine schreibende Verbindung und ``repo``
    haben (Chat, Textbuch-Export). Kein Modellaufruf, nur Leseabfragen."""
    from interview_theater import repo

    stand = repo.hole_arbeitsstand(conn, chat_id)
    return daten(
        _wert(stand, "rahmen"),
        _wert(stand, "hauptkonflikt"),
        _wert(stand, "format"),
        repo.hole_szenen(conn, chat_id),
        repo.figuren(conn, chat_id),
    )


def ist_leer(d: dict) -> bool:
    """Gibt es ueberhaupt etwas zu zeigen? Ein Vorspann aus lauter leeren
    Ueberschriften ist schlechter als keiner."""
    return not (
        d["rahmen"] or d["hauptkonflikt"] or d["format"] or d["szenen"] or d["figuren"]
    )


#: Die Ueberschriften der Bloecke -- dieselben in Chat, Web und Textbuch.
#: Singular und Plural der Szenenzahl als ganze Ueberschriften.
_UEBERSCHRIFT_WO_UND_WANN = "Wo und wann"
_UEBERSCHRIFT_WORUM = "Worum es geht"
_UEBERSCHRIFT_FORM = "Form"
_UEBERSCHRIFT_EINE_SZENE = "{anzahl} Szene"
_UEBERSCHRIFT_SZENEN = "{anzahl} Szenen"
_UEBERSCHRIFT_FIGUREN = "Wer vorkommt"


def _szenenzeile(s: dict) -> str:
    nummer = "—" if s["nummer"] is None else str(s["nummer"])
    zeile = f"{nummer}. {s['titel']}" if s["titel"] else f"{nummer}."
    if s["form"]:
        zeile += f" ({s['form']})"
    return zeile


def _bloecke(d: dict, fett: bool) -> list[tuple[str, str]]:
    """Die Bloecke als ``(Ueberschrift, Text)`` -- die eine Stelle, an der
    steht, was der Vorspann enthaelt. Markdown und Chattext unterscheiden sich
    danach nur noch in den Rauten und den Sternchen."""
    bloecke: list[tuple[str, str]] = []
    if d["rahmen"]:
        bloecke.append((T._UEBERSCHRIFT_WO_UND_WANN, d["rahmen"]))
    if d["hauptkonflikt"]:
        bloecke.append((T._UEBERSCHRIFT_WORUM, d["hauptkonflikt"]))
    if d["format"]:
        bloecke.append((T._UEBERSCHRIFT_FORM, d["format"]))
    if d["szenen"]:
        anzahl = len(d["szenen"])
        kopf = T._UEBERSCHRIFT_EINE_SZENE if anzahl == 1 else T._UEBERSCHRIFT_SZENEN
        bloecke.append(
            (
                kopf.format(anzahl=anzahl),
                "\n".join(_szenenzeile(s) for s in d["szenen"]),
            )
        )
    if d["figuren"]:
        zeilen = []
        for f in d["figuren"]:
            name = f"**{f['name']}**" if fett else f["name"]
            zeilen.append(f"{name} — {f['beschreibung']}" if f["beschreibung"] else name)
        bloecke.append((T._UEBERSCHRIFT_FIGUREN, "\n".join(zeilen)))
    return bloecke


def als_markdown(d: dict) -> str:
    """Der Vorspann als Markdown -- fuer den Textbuch-Export und die Datei,
    die die Gruppe mitnimmt."""
    bloecke = _bloecke(d, fett=True)
    if not bloecke:
        return ""
    return "\n\n".join(f"## {kopf}\n{text}" for kopf, text in bloecke)


def als_chattext(d: dict) -> str:
    """Derselbe Inhalt fuer Telegram. Ohne Rauten und Sternchen: ``tg.sende``
    schickt reinen Text (kein ``parse_mode``), und ein woertliches "## Wo und
    wann" im Chat sieht nach kaputtem Bot aus."""
    bloecke = _bloecke(d, fett=False)
    if not bloecke:
        return ""
    return "\n\n".join(f"{kopf}\n{text}" for kopf, text in bloecke)


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)
