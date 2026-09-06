"""Sprecherzeilen und Sprechanteile je Figur (06.09.2026).

**Warum es das gibt.** Der praktisch wichtigste Befund fuer eine Laiengruppe
stand nirgends: wie viel jede Figur eigentlich spricht. Eine Spielerin mit
vier Zeilen merkt das in der Probe, und dann ist der Text geschrieben. Diese
Zaehlung macht es sichtbar, bevor jemand ihn lernt.

**Reine Zaehlung, kein Modellaufruf.** Gezaehlt wird ueber ``szene.volltext``
-- den Theatertext, nicht die Prosafassung: eine Geschichte hat keine
Sprecherzeilen, und eine erfundene Zahl waere schlimmer als keine.

**Die Regel fuer eine Sprecherzeile**, bewusst schlank gehalten und wortgleich
zu der in ``web.sprecher_der_zeile`` aus ``feat/textbuch-ux``:

    Am Zeilenanfang steht ein Name, danach ein Doppelpunkt. Ein Name gilt,
    wenn er in der Figurenliste der Gruppe steht **oder** durchgehend
    grossgeschrieben ist.

**Die bekannte Grenze, ehrlich benannt:** Namen mit **Punkt** (``FRAU K.:``)
oder **Komma** (``MIRA, LEISE:``) werden **nicht** erkannt. Beides kommt in
Theatertexten vor -- eine Anrede mit Abkuerzung, eine Spielanweisung im
Sprecherkopf. Sie hier mitzunehmen hiesse, Doppelpunkte in normalen Saetzen
("Sie sagt: nein.") als Sprecherzeilen zu lesen; die Fehlerrichtung ist
bewusst gewaehlt: lieber eine Szene gar nicht zaehlen als sie falsch zaehlen.

**Erkennt eine Szene keine einzige Sprecherzeile, liefert sie gar nichts**
(``zaehle_szene`` gibt ``None``). Lied, Rap und Chor koennen ohne
Sprecherkopf geschrieben sein; eine Szene, die wie ein Gedicht aussieht,
darf keine Zahlen erzeugen, die niemand nachrechnen kann.

**Regieanweisungen zaehlen nicht.** Was in runden Klammern steht -- ob als
eigene Zeile oder mitten in einer Replik (``LEYLA:(dreht das Handy um)Gelesen.``)
-- ist keine gesprochene Sprache und faellt vor dem Zaehlen weg.
"""

import re

#: Ab diesem Anteil gilt eine Figur als "spricht mit". Darunter bekommt sie
#: eine eigene Hinweiszeile -- sachlich, ohne Wertung. Drei Prozent, weil das
#: bei vier bis sechs Figuren die Groessenordnung "eine Handvoll Zeilen" ist.
SCHWELLE_ANTEIL = 3.0

#: Der Kopf einer Sprecherzeile: alles bis zum ersten Doppelpunkt. Der Rest
#: der Pruefung steht in ``sprecher_der_zeile`` -- als Regex waere sie
#: unlesbar und die Grenze nicht mehr benennbar.
_KOPF = re.compile(r"^([^:]{1,40}):(.*)$")

#: Regieanweisungen in runden Klammern. Nicht verschachtelt: in
#: Theatertexten ist das der Normalfall, und ein Klammerzaehler waere mehr
#: Code als Nutzen.
_KLAMMER = re.compile(r"\([^()]*\)")

#: Was ein Wort ist: eine Folge aus Buchstaben, Ziffern und Apostrophen.
#: Satzzeichen und Gedankenstriche zaehlen nicht mit -- "Woher --" ist ein
#: Wort, nicht zwei.
_WORT = re.compile(r"[\w'’]+", re.UNICODE)


def _ist_grossgeschrieben(kopf: str) -> bool:
    """Steht der Kopf durchgehend in Grossbuchstaben?

    ``kopf.isupper()`` allein reicht nicht: eine Zeile ohne einen einzigen
    Buchstaben ("12:30") waere sonst nie und eine mit Ziffern immer
    grossgeschrieben."""
    return bool(re.search(r"[^\W\d_]", kopf)) and kopf == kopf.upper()


def sprecher_der_zeile(zeile: str, namen: set[str] | None = None) -> str | None:
    """Der Sprecher dieser Zeile, oder None.

    ``namen`` sind die Figurennamen der Gruppe (kleingeschrieben); eine Figur
    darf damit auch dann sprechen, wenn ihr Name im Text normal geschrieben
    ist ("Leyla: ..."). Ohne Liste bleibt es bei der Grossschreibung.

    Punkt und Komma im Kopf schliessen aus (siehe Modul-Docstring)."""
    treffer = _KOPF.match(zeile or "")
    if treffer is None:
        return None
    kopf = treffer.group(1).strip()
    if not kopf:
        return None
    if (namen or set()) and kopf.lower() in namen:
        return kopf
    if "." in kopf or "," in kopf:
        return None
    # Eine Ziffer im Kopf heisst: das ist keine Figur, das ist eine
    # Ueberschrift. Gemessen an den echten Opus-Texten unter
    # ``docs/prompt-audit/2026-09-06/opus-thinking-texte/``: dort steht
    # ``SZENE 1: EINUNDFUENFZIG STUNDEN ca. 10 min`` ueber dem Text und
    # zaehlte ohne diese Zeile als Sprecher mit rund 30 Woertern mit. Eine
    # Figur, die wirklich so heisst, steht in der Figurenliste und wird eine
    # Zeile weiter oben erkannt.
    if any(z.isdigit() for z in kopf):
        return None
    if not _ist_grossgeschrieben(kopf):
        return None
    return kopf


def _worte(text: str) -> int:
    """Die Zahl der gesprochenen Woerter -- ohne Regieanweisungen."""
    return len(_WORT.findall(_KLAMMER.sub(" ", text or "")))


def zerlege(volltext: str, namen: set[str] | None = None) -> list[tuple[str, str]]:
    """Der Szenentext als Liste ``(Sprecher, gesprochener Text)``.

    Zeilen ohne Sprecherkopf gehoeren zur laufenden Replik: in Liedern und
    Rap-Szenen steht der Name einmal und darunter mehrere Zeilen. Alles vor
    der ersten Sprecherzeile (Ortsangabe, Auftrittsbeschreibung) faellt weg.
    """
    repliken: list[tuple[str, list[str]]] = []
    for zeile in (volltext or "").splitlines():
        name = sprecher_der_zeile(zeile, namen)
        if name is not None:
            rest = _KOPF.match(zeile).group(2)
            repliken.append((name, [rest]))
            continue
        if repliken:
            repliken[-1][1].append(zeile)
    return [(name, "\n".join(teile)) for name, teile in repliken]


def zaehle_szene(volltext: str, namen: set[str] | None = None) -> dict | None:
    """Woerter und Repliken je Sprecher in EINER Szene -- oder ``None``.

    ``None`` heisst: in dieser Szene wurde keine einzige Sprecherzeile
    erkannt. Der Aufrufer laesst die Szene dann ganz weg, statt sie mit
    einer Null zu zaehlen -- ein Lied ohne Sprecherkoepfe ist kein Beleg
    dafuer, dass niemand darin spricht.

    Liefert ``{Sprecher: {"worte": n, "repliken": n}}``."""
    repliken = zerlege(volltext, namen)
    if not repliken:
        return None
    ergebnis: dict[str, dict[str, int]] = {}
    for name, text in repliken:
        eintrag = ergebnis.setdefault(name, {"worte": 0, "repliken": 0})
        eintrag["worte"] += _worte(text)
        eintrag["repliken"] += 1
    return ergebnis


def anteile(szenen: list, figuren: list) -> dict:
    """Die Sprechanteile ueber das ganze Stueck.

    ``szenen`` sind Dicts oder ``sqlite3.Row`` mit ``nummer`` und
    ``volltext``, ``figuren`` mit ``name`` -- damit laeuft dieselbe Funktion
    im Bot (ueber ``repo``) und auf der Weboberflaeche (read-only), ohne dass
    eine von beiden die andere Schicht anfassen muss.

    Liefert::

        {"szenen": <Zahl der gezaehlten Szenen>,
         "worte": <Gesamtzahl>,
         "figuren": [{"name", "anteil", "worte", "repliken", "szenen"}, …]}

    Die Liste ist nach Anteil absteigend sortiert und enthaelt **auch Figuren
    ohne eine einzige Replik** -- genau die sind der Grund fuer diese
    Zaehlung. Wurde keine Szene gezaehlt, ist ``szenen`` 0 und ``figuren``
    leer: dann gibt es nichts zu zeigen, und der Aufrufer zeigt nichts."""
    liste = [(_wert(f, "name") or "").strip() for f in figuren or []]
    liste = [n for n in liste if n]
    namen = {n.lower() for n in liste}
    schreibweise = {n.lower(): n for n in liste}

    gezaehlt = 0
    summe: dict[str, dict[str, int]] = {}
    for s in szenen or []:
        ergebnis = zaehle_szene(_wert(s, "volltext"), namen)
        if ergebnis is None:
            continue
        gezaehlt += 1
        for roh, zahlen in ergebnis.items():
            # Die Schreibweise der Figurenliste gewinnt: im Text steht
            # "LEYLA", auf der Seite soll "Leyla" stehen. Ein Sprecher, den
            # es als Figur nicht gibt, behaelt seine eigene.
            name = schreibweise.get(roh.lower(), roh)
            eintrag = summe.setdefault(
                name, {"worte": 0, "repliken": 0, "szenen": 0}
            )
            eintrag["worte"] += zahlen["worte"]
            eintrag["repliken"] += zahlen["repliken"]
            eintrag["szenen"] += 1

    if not gezaehlt:
        return {"szenen": 0, "worte": 0, "figuren": []}

    for name in liste:
        summe.setdefault(name, {"worte": 0, "repliken": 0, "szenen": 0})
    gesamt = sum(e["worte"] for e in summe.values())
    figurenliste = [
        {
            "name": name,
            "worte": e["worte"],
            "repliken": e["repliken"],
            "szenen": e["szenen"],
            "anteil": round(100 * e["worte"] / gesamt, 1) if gesamt else 0.0,
        }
        for name, e in summe.items()
    ]
    figurenliste.sort(key=lambda f: (-f["anteil"], f["name"]))
    return {"szenen": gezaehlt, "worte": gesamt, "figuren": figurenliste}


def _wert(quelle, name: str):
    """Ein Feld aus einem Dict oder einer ``sqlite3.Row``; None, wenn es die
    Spalte in einer alten Datenbank noch nicht gibt."""
    if quelle is None:
        return None
    try:
        return quelle[name]
    except (IndexError, KeyError, TypeError):
        return None


def hinweis(figur: dict, szenen_gesamt: int) -> str:
    """Die Hinweiszeile fuer eine Figur unter ``SCHWELLE_ANTEIL``.

    Sachlich formuliert, ohne Wertung: die Zahl steht da, die Entscheidung
    gehoert der Gruppe. ("Zeynep spricht in 1 von 4 Szenen, 2 % der Worte.")"""
    return (
        f"{figur['name']} spricht in {figur['szenen']} von {szenen_gesamt} "
        f"Szenen, {_prozent(figur['anteil'])} der Worte."
    )


def _prozent(wert: float) -> str:
    """"2 %" statt "2.0 %" -- und mit Komma, die Seite ist auf Deutsch."""
    text = f"{wert:.1f}".rstrip("0").rstrip(".")
    return f"{text.replace('.', ',') or '0'} %"


def zeile(figur: dict) -> str:
    """Eine Figurenzeile fuer den Chat: Name, Anteil, Repliken, Szenen."""
    return (
        f"{figur['name']}: {_prozent(figur['anteil'])}, "
        f"{figur['repliken']} Repliken, {figur['szenen']} Szenen"
    )


#: Der Kopf ueber der Liste -- wortgleich im Chat und im Web.
UEBERSCHRIFT = "Sprechanteile"

#: Was dasteht, solange keine Szene gezaehlt werden konnte. Nur im Chat: auf
#: der Gruppenseite bleibt der Abschnitt dann ganz weg.
TEXT_LEER = (
    "Sprechanteile kann ich noch nicht zaehlen - dafuer brauche ich "
    "Szenentexte mit Sprecherzeilen."
)


def text(daten: dict) -> str:
    """Die ganze Auswertung als Chattext (ASCII, wie jede Bot-Nachricht).

    Deterministisch aus ``anteile`` -- kein Modellaufruf, beliebig oft
    abrufbar."""
    if not daten.get("szenen"):
        return TEXT_LEER
    zeilen = [f"{UEBERSCHRIFT} ueber {daten['szenen']} Szenen:"]
    zeilen.extend(zeile(f) for f in daten["figuren"])
    leise = [f for f in daten["figuren"] if f["anteil"] < SCHWELLE_ANTEIL]
    if leise:
        zeilen.append("")
        zeilen.extend(hinweis(f, daten["szenen"]) for f in leise)
    return "\n".join(zeilen)
