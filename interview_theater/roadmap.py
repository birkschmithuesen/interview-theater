"""Die Roadmap zum Text: welche Aufgabe der sieben Phasen steht, welche fehlt
(30.09.2026, Karte W).

**Warum es das gibt** (Birk, 30.09.2026): "es soll eine uebersicht geben,
welche aufgaben der roadmap zur erstellung des textes schon erfuellt und noch
ausstehend sind." Im Chat sieht eine Gruppe die Checkliste einer Phase beim
Eintritt -- und danach nie wieder; auf der Gruppenseite steht, was gefuellt
ist, und daneben (seit dem 06.09.) was fehlt. Was keiner der beiden zeigt,
ist der **Weg**: sieben Stationen, wo stehen wir, was kommt noch.

**Keine zweite Wunschliste.** Welche Phase was setzt, steht in
``phasentexte.PARAMETER``; ``tests/test_roadmap.py`` nagelt Namen und
Reihenfolge daran fest. Eigen sind hier nur die **Pruefer** -- und das aus
einem harten Grund: die Leser in ``PARAMETER`` rufen ``repo``, und der
Webserver bekommt keinen ``repo``-Pfad (AGENTS.md, ``fehlstellen``). Die
Pruefer sind deshalb reine Funktionen ueber Dicts, und sie pruefen genau das,
woran ``phasen.voraussetzungen`` schon haengt.

**Ein Zusammenbau, zwei Aufrufer** -- dasselbe Muster wie
``leitfaden.aus_feldern`` und ``fehlstellen.aus_daten``: ``aus_daten`` ist
rein und kennt nur Dicts, ``register`` holt sie ueber ``repo`` (Bot),
``web_daten.roadmap`` ueber die read-only geoeffnete Verbindung (Web).

**Nichts hier setzt eine Phase.** Die Uebersicht zeigt den Datenstand; der
Datenstand schaltet nie (AGENTS.md, "Der automatische Phasensprung" --
Datenstand ist nicht Absicht). Umschalten tut allein die Gruppe, per Chat,
Befehl oder Klick (``befehle.wechsle_phase``).

**Kein Modellaufruf.**

**Eine Grenze, ausdruecklich:** 'laeuft' kann nur zeigen, was in der
Datenbank steht -- Interviewmodus, Tippanzeige (``gruppe.web_tippt_bis``) und
eine laufende Zeile in ``web_strom``. Ein Szenenlauf-Lock lebt im
Bot-Prozess und ist fuer den Webserver unsichtbar; laeuft ein Auftrag ohne
Strom (Schaerfung, Szenenfolge, Stueckpruefung), steht die Aufgabe hier
weiter auf 'offen'.
"""

from collections.abc import Callable
from typing import NamedTuple

from interview_theater import phasen, phasentexte


class Aufgabe(NamedTuple):
    """Eine Zeile der Uebersicht.

    ``parameter`` ist wortgleich der Name aus ``phasentexte.PARAMETER`` --
    daran haengt die Beschriftung (und damit die Uebersetzung) und der Test,
    der beide Listen zusammenhaelt."""

    kennung: str
    parameter: str
    erledigt: Callable[[dict], bool]
    ziel: dict


def _text(quelle, name: str) -> str:
    """Ein Feld als getrimmter String -- leer, wenn es fehlt oder NULL ist.
    Dieselbe Nachsicht wie in ``fehlstellen._text``: der Webserver sieht die
    Datenbank read-only und migriert nichts."""
    if quelle is None:
        return ""
    try:
        return (quelle[name] or "").strip()
    except (IndexError, KeyError, TypeError):
        return ""


def _gesetzt(quelle, name: str) -> bool:
    """Wie ``_text``, aber ein **leerer String zaehlt als gesetzt** -- der Fall
    der ``fragen_weich``/``frage_einleitungen``: "keine noetig" ist ein
    Ergebnis, kein fehlender Wert."""
    if quelle is None:
        return False
    try:
        return quelle[name] is not None
    except (IndexError, KeyError, TypeError):
        return False


def _szene_steht(szene) -> bool:
    """Wie ``phasen._prosa_oder_volltext``: Phase 6 schreibt die Geschichte,
    der Feinschliff den Theatertext -- beides ist "die Szene steht"."""
    return bool(_text(szene, "prosa") or _text(szene, "volltext"))


def _alle_szenen_stehen(lage: dict) -> bool:
    szenen = lage["szenen"]
    return bool(szenen) and all(_szene_steht(s) for s in szenen)


#: Je Phase, in der Reihenfolge der Arbeit: was sie setzt.
#: ``parameter`` **muss** wortgleich und in derselben Reihenfolge in
#: ``phasentexte.PARAMETER`` stehen (Test).
AUFGABEN: dict[int, tuple[Aufgabe, ...]] = {
    1: (
        Aufgabe("begriffe", "Begriffe",
                lambda l: bool(_text(l["stand"], "begriffe")),
                {"tab": "stand", "feld": "begriffe"}),
    ),
    2: (
        Aufgabe("fragen", "Fragen",
                lambda l: bool(_text(l["stand"], "fragen")),
                {"tab": "stand", "feld": "fragen"}),
        Aufgabe("einleitungen", "Einleitungen",
                lambda l: _gesetzt(l["stand"], "fragen_weich")
                or _gesetzt(l["stand"], "frage_einleitungen"),
                {"tab": "stand", "feld": "fragen"}),
        Aufgabe("eroeffnung", "Eroeffnung",
                lambda l: bool(_text(l["stand"], "interview_eroeffnung")),
                {"tab": "stand", "feld": "interview_eroeffnung"}),
        Aufgabe("abschluss", "Abschluss",
                lambda l: bool(_text(l["stand"], "interview_abschluss")),
                {"tab": "stand", "feld": "interview_abschluss"}),
    ),
    3: (
        Aufgabe("interviews", "Interviews",
                lambda l: bool(l["interviews"]),
                {"tab": "chat", "feld": None}),
        Aufgabe("auswertungen", "Auswertungen",
                lambda l: any(i.get("zusammenfassung") for i in l["interviews"]),
                {"tab": "stand", "feld": None}),
    ),
    4: (
        Aufgabe("setting", "Setting",
                lambda l: bool(_text(l["stand"], "rahmen")),
                {"tab": "stand", "feld": "rahmen"}),
        Aufgabe("figuren", "Figuren",
                lambda l: bool(l["figuren"]),
                {"tab": "stand", "feld": None}),
        Aufgabe("geschichte", "Geschichte",
                lambda l: bool(_text(l["stand"], "geschichte")),
                {"tab": "stand", "feld": "geschichte"}),
        Aufgabe("szenenfolge", "Szenenfolge",
                lambda l: bool(l["szenen"]),
                {"tab": "stand", "feld": None}),
    ),
    5: (
        Aufgabe("zuordnungen", "Zuordnungen",
                lambda l: l["zuordnungen"] > 0,
                {"tab": "stand", "feld": None}),
    ),
    6: (
        Aufgabe("szenentexte", "Szenentexte", _alle_szenen_stehen,
                {"tab": "textbuch", "feld": None}),
    ),
    7: (
        Aufgabe("stueckpruefung", "Stueckpruefung",
                lambda l: bool(l["pruefrunde"]),
                {"tab": "stand", "feld": None}),
    ),
}

#: Wann eine Aufgabe 'laeuft' statt 'offen' ist -- nur, wo der DATENSTAND es
#: zeigt. Siehe die Grenze im Moduldocstring.
_LAEUFT: dict[str, Callable[[dict], bool]] = {
    "interviews": lambda l: bool(l["interviewmodus"]),
    "auswertungen": lambda l: bool(l["interviewmodus"]),
    "szenentexte": lambda l: l["strom"] in ("szene", "prosa")
    or any(_szene_steht(s) for s in l["szenen"]),
}


def _zustand(aufgabe: Aufgabe, lage: dict) -> str:
    if aufgabe.erledigt(lage):
        return "erledigt"
    laeuft = _LAEUFT.get(aufgabe.kennung)
    return "laeuft" if laeuft is not None and laeuft(lage) else "offen"


def aus_daten(lage: dict) -> list[dict]:
    """Die sieben Phasen mit ihren Aufgaben -- rein, ohne Datenbank.

    ``lage`` traegt: ``stand`` (Arbeitsstand als Dict oder Row), ``figuren``,
    ``szenen``, ``interviews`` (je Dict mit ``zusammenfassung``),
    ``zuordnungen`` (Anzahl Schaerfungen), ``pruefrunde``, ``phase``,
    ``interviewmodus``, ``tippt`` und ``strom`` (die ``art`` einer laufenden
    ``web_strom``-Zeile oder ``None``)."""
    jetzige = lage["phase"]
    ergebnis = []
    for nummer, name, _satz in phasen.PHASEN:
        aufgaben = []
        for aufgabe in AUFGABEN.get(nummer, ()):
            zustand = _zustand(aufgabe, lage)
            aufgaben.append({
                "kennung": aufgabe.kennung,
                "text": phasentexte.beschriftung(aufgabe.parameter),
                "zustand": zustand,
                "ziel": dict(aufgabe.ziel),
            })
        ergebnis.append({
            "nummer": nummer,
            "name": name,
            "bezeichnung": phasen.bezeichnung(nummer),
            "aktiv": nummer == jetzige,
            "erledigt": sum(1 for a in aufgaben if a["zustand"] == "erledigt"),
            "gesamt": len(aufgaben),
            "aufgaben": aufgaben,
        })
    return ergebnis


def register(conn, chat_id: int) -> list[dict]:
    """Der Weg des Bots, ueber ``repo``. Kein Modellaufruf, kein
    Schreibvorgang."""
    from interview_theater import repo

    return aus_daten({
        "stand": repo.hole_arbeitsstand(conn, chat_id),
        "figuren": repo.figuren(conn, chat_id),
        "szenen": repo.hole_szenen(conn, chat_id),
        "interviews": [
            {"zusammenfassung": v["zusammenfassung"]}
            for v in repo.verdichtungen(conn, chat_id)
        ],
        "zuordnungen": len(repo.schaerfungen(conn, chat_id)),
        "pruefrunde": repo.letzte_pruefrunde(conn, chat_id),
        "phase": phasen.aktuelle(conn, chat_id),
        "interviewmodus": repo.ist_interviewmodus_an(conn, chat_id),
        "tippt": False,
        "strom": next(
            (z["art"] for z in repo.laufende_stroeme(conn, chat_id)), None),
    })
