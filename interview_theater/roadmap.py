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
Webserver bekommt keinen ``repo``-Pfad (docs/agents/was-bewusst-fehlt.md, ``fehlstellen``). Die
Pruefer sind deshalb reine Funktionen ueber Dicts, und sie pruefen genau das,
woran ``phasen.voraussetzungen`` schon haengt.

**Ein Zusammenbau, zwei Aufrufer** -- dasselbe Muster wie
``leitfaden.aus_feldern`` und ``fehlstellen.aus_daten``: ``aus_daten`` ist
rein und kennt nur Dicts, ``register`` holt sie ueber ``repo`` (Bot),
``web_daten.roadmap`` ueber die read-only geoeffnete Verbindung (Web).

**Nichts hier setzt eine Phase.** Die Uebersicht zeigt den Datenstand; der
Datenstand schaltet nie (docs/agents/was-bewusst-fehlt.md, "Der automatische Phasensprung" --
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

import json
from collections.abc import Callable
from typing import NamedTuple

from interview_theater import phasen, phasentexte


def _weich_aktiv() -> bool:
    from interview_theater import workshop
    return workshop.fragen_weich_aktiv()


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


# --- Padua-Phasenumbau: Szenenkarten (Phase 6) und Stage Script (Phase 7) --
#
# Workbench-Checkliste P6/P7 passt nicht zum neuen Ablauf (Birk 08.10.2026):
# unter ``workshop.szenenkarten_aktiv`` baut Phase 6 keine Prosa mehr,
# sondern EINE Karte je Szene (``szenenkarte.py``), Phase 7 das Stage
# Script aus den Karten (``stagescript.py``) -- die alten Punkte
# ("Szenentexte", "Feedback on the whole text", "Scene N: revised",
# "Dramaturgy check" in Phase 6; Formen/Sprechweisen in Phase 7) gehoeren
# zum frueheren Prosa-Weg und passen nicht mehr. Die folgenden Pruefer sind
# reine Funktionen ueber ``lage`` wie der Rest der Datei; Dortmund (ohne den
# Schalter) bleibt bei ``AUFGABEN``/``_details`` unveraendert.


def _karten_relevante_szenen(lage: dict) -> list:
    """Dieselbe Filterung wie ``szenenkarte._szenen``, rein ueber ``lage``:
    ``repo.hole_szenen`` liefert schon ohne ``entfernt_am``, nur die
    Nummer-Pruefung bleibt (eine Szene ohne Nummer ist kein Schritt der
    Gruppe)."""
    return [s for s in lage["szenen"] if _roh(s, "nummer") is not None]


def _karte_dict(szene) -> dict | None:
    """Die Karte als Dict, gleich ob ``lage['szenen']`` vom Bot kommt
    (``repo.hole_szenen``, rohes JSON in ``szene.karte``) oder vom Webserver
    (``web_daten._szenen`` parst ``karte`` fuer ``[karten] aktiv`` schon zu
    einem Dict). Wie ``szenenkarte.karte_von``, nur ohne ``repo``."""
    try:
        karte = szene["karte"]
    except (IndexError, KeyError, TypeError):
        return None
    if isinstance(karte, dict):
        return karte
    if not isinstance(karte, str) or not karte.strip():
        return None
    try:
        geparst = json.loads(karte)
    except ValueError:
        return None
    return geparst if isinstance(geparst, dict) else None


def _karte_erledigt(szene) -> bool:
    """``szene['karte_bestaetigt']`` (``web_daten._szenen``, schon ein
    ``bool``) oder, vom Bot, der rohe Zeitstempel ``karte_bestaetigt_am``
    (``szenenkarte.bestaetige``)."""
    try:
        return bool(szene["karte_bestaetigt"])
    except (IndexError, KeyError, TypeError):
        return bool(_text(szene, "karte_bestaetigt_am"))


def _karte_zustand(szene) -> str:
    """'erledigt', sobald die Karte gespeichert ist, 'laeuft', sobald sie
    gebaut, aber noch nicht gespeichert ist, sonst 'offen'."""
    if _karte_erledigt(szene):
        return "erledigt"
    if _karte_dict(szene) is not None:
        return "laeuft"
    return "offen"


def _script_zustand(szene) -> str:
    """'erledigt', sobald das Stage Script dieser Szene steht
    (``szene.volltext``, ``stagescript.schreibe``), sonst 'offen'."""
    return "erledigt" if _text(szene, "volltext") else "offen"


def _braucht_skriptkopf(szenen: list) -> bool:
    """Dieselbe Formel wie ``stagescript.braucht_kopf``, rein ueber die
    schon geladenen Karten: ueberwiegend Handlungsanweisungen (G2)."""
    typen = [(_karte_dict(s) or {}).get("typ") for s in szenen]
    return bool(typen) and sum(t == "instructions" for t in typen) * 2 > len(typen)


def _karten_zeilen(lage: dict) -> list[dict]:
    """Phase 6 unter ``[karten] aktiv``: EIN Punkt je Szenenkarte statt der
    Prosa-Aufgabe ``AUFGABEN[6]``."""
    return [
        {
            "kennung": f"karte_{s['nummer']}",
            "text": phasentexte.karte_aufgabe_text(s["nummer"], _text(s, "titel")),
            "zustand": _karte_zustand(s),
            "ziel": {"tab": "stand", "feld": None},
        }
        for s in _karten_relevante_szenen(lage)
    ]


def _stagescript_zeilen(lage: dict) -> list[dict]:
    """Phase 7 unter ``[karten] aktiv``: EIN Punkt je Stage Script statt
    der Prosa-Aufgabe ``AUFGABEN[7]``, dazu der Skriptkopf (G2), nur wenn
    das Skript einen braucht."""
    szenen = _karten_relevante_szenen(lage)
    zeilen = [
        {
            "kennung": f"script_{s['nummer']}",
            "text": phasentexte.stagescript_aufgabe_text(s["nummer"], _text(s, "titel")),
            "zustand": _script_zustand(s),
            "ziel": {"tab": "stand", "feld": None},
        }
        for s in szenen
    ]
    if _braucht_skriptkopf(szenen):
        zeilen.append({
            "kennung": "skriptkopf",
            "text": phasentexte.stagekopf_aufgabe_text(),
            "zustand": "erledigt" if _text(lage["stand"], "stage_kopf") else "offen",
            "ziel": {"tab": "stand", "feld": None},
        })
    return zeilen


def _alle_karten_bestaetigt(lage: dict) -> bool:
    """Dieselbe Schwelle wie ``phasen.voraussetzungen[7]``
    (``phasen._karte_abgenommen``) unter ``[karten] aktiv``: jede Szene mit
    einer GESPEICHERTEN Karte, nicht nur geschriebenem Text."""
    szenen = _karten_relevante_szenen(lage)
    return bool(szenen) and all(_karte_erledigt(s) for s in szenen)


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
#:
#: Feedbackloop P1-2, P2-H4 (05.10.2026): "Fragen" zeigte "offen" ohne jeden
#: Vermerk, solange noch keine Frage angenommen war -- obwohl die Gruppe
#: laengst eigene Fragen sammelt oder ein Vorschlag auf dem Tisch liegt.
#: "Laeuft", sobald eine der beiden laufenden Ablagen etwas traegt.
_LAEUFT: dict[str, Callable[[dict], bool]] = {
    "fragen": lambda l: bool(_text(l["stand"], "fragen_eigene_vorschlag")
                              or _text(l["stand"], "fragen_auswahl")),
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


def _aufgaben_fuer(nummer: int) -> tuple[Aufgabe, ...]:
    """``AUFGABEN[nummer]`` ohne "Einleitungen", wenn das Profil die weiche
    Fassung sensibler Fragen abschaltet (Padua: ``[fragen_weich] aktiv =
    false``) -- derselbe Filter fuer die Phasen-Checkliste (``aus_daten``)
    UND die Werkbank (``werkbank``).

    Feedbackloop P1-2, P2-H4 (05.10.2026): die Werkbank zeigte
    "Einleitungen" weiterhin an, obwohl das Profil-Prompt die weiche Fassung
    nie liefert -- der Zaehler ("2 · Questions 0 of 4") wurde dadurch nie
    voll. ``aus_daten`` filterte das schon vor dieser Karte, ``werkbank``
    noch nicht; jetzt teilen sich beide denselben Filter statt ihn zweimal
    zu pflegen."""
    return tuple(
        a for a in AUFGABEN.get(nummer, ())
        if not (a.kennung == "einleitungen" and not _weich_aktiv())
    )


#: Die Voraussetzung je Phase -- dieselbe Quelle wie ``phasen.voraussetzungen``
#: (UX-Knoepfe-Karte, Abschnitt 4: der Phasensprung in der Web-Leiste braucht
#: denselben Pruefer, ohne ``repo``), hier als reine Funktionen ueber ``lage``
#: wie ``AUFGABEN``. Jedes Wort steht in ``phasentexte.PARAMETER_BESCHRIFTUNG``
#: (dieselben Woerter wie Checkliste und Abschluss, keine zweite
#: Uebersetzung); Phase 1 hat keinen Eintrag -- dorthin kommt man immer
#: zurueck. Bewusst EIGENE Pruefer statt ``AUFGABEN``-Wiederverwendung: die
#: Aufgaben zeigen, was in EINER Phase ansteht (``AUFGABEN[4]["figuren"]``
#: prueft nur "gibt es welche"), die Voraussetzung der NAECHSTEN Phase ist an
#: zwei Stellen strenger (Figurenliste abgenommen, keine offene Auswertung
#: mehr) -- ``phasen.voraussetzungen`` traegt genau diese Strenge.
_GATE: dict[int, tuple[tuple[str, Callable[[dict], bool]], ...]] = {
    2: (
        ("Begriffe", lambda l: bool(_text(l["stand"], "begriffe"))),
    ),
    3: (
        ("Fragen", lambda l: bool(_text(l["stand"], "fragen"))),
        ("Einleitungen", lambda l: not _weich_aktiv()
         or _gesetzt(l["stand"], "fragen_weich")
         or _gesetzt(l["stand"], "frage_einleitungen")),
        ("Eroeffnung", lambda l: bool(_text(l["stand"], "interview_eroeffnung"))),
        ("Abschluss", lambda l: bool(_text(l["stand"], "interview_abschluss"))),
    ),
    4: (
        ("Auswertungen", lambda l: bool(l.get("hat_verdichtung"))),
        ("Offene Auswertungen", lambda l: not l.get("offene_interviews")),
    ),
    5: (
        ("Setting", lambda l: bool(_text(l["stand"], "rahmen"))),
        ("Figuren", lambda l: bool(l["figuren"])
         and bool(_text(l["stand"], "figuren_fixiert_am"))),
        ("Geschichte", lambda l: bool(_text(l["stand"], "geschichte"))),
        ("Szenenfolge", lambda l: bool(l["szenen"])),
    ),
    6: (
        ("Geschichte", lambda l: bool(_text(l["stand"], "geschichte"))),
        ("Szenenfolge", lambda l: bool(l["szenen"])),
    ),
    7: (
        ("Szenentexte", _alle_szenen_stehen),
    ),
}


def _gate_fuer(nummer: int) -> tuple[tuple[str, Callable[[dict], bool]], ...]:
    """``_GATE[nummer]``, ausser Phase 7 unter ``[karten] aktiv``: dort
    verlangt der Eintritt alle GESPEICHERTEN Karten statt aller
    geschriebenen Szenentexte -- dieselbe Schwelle wie
    ``phasen.voraussetzungen[7]`` (Workbench-Checkliste P6/P7, Birk
    08.10.2026)."""
    from interview_theater import workshop

    if nummer == 7 and workshop.szenenkarten_aktiv():
        return (("Szenenkarten", _alle_karten_bestaetigt),)
    return _GATE.get(nummer, ())


def bereit(nummer: int, lage: dict) -> bool:
    """Darf die Gruppe ohne Hinweis nach Phase ``nummer`` springen?

    Reine Pruefung ueber ``lage`` wie ``AUFGABEN`` -- Phase 1 hat keine
    Voraussetzung, dorthin kommt man immer zurueck."""
    return all(check(lage) for _, check in _gate_fuer(nummer))


def fehlt(nummer: int, lage: dict) -> list[str]:
    """Die kurzen Namen dessen, was fuer Phase ``nummer`` noch fehlt -- leere
    Liste, wenn ``bereit`` wahr ist. Dieselben Woerter wie die Checkliste
    (``phasentexte.beschriftung``), damit niemand zwei Namen fuer dasselbe
    Feld lernen muss."""
    return [
        phasentexte.beschriftung(label)
        for label, check in _gate_fuer(nummer)
        if not check(lage)
    ]


def _karten_aufgaben_fuer(nummer: int, lage: dict) -> list[dict] | None:
    """Die Checkliste von Phase 6/7 unter ``[karten] aktiv`` -- ``None``,
    wenn die Phase oder das Profil nicht betroffen ist (dann gelten
    ``AUFGABEN``/``_aufgaben_fuer`` wie bisher, Dortmund unveraendert).
    Dieselbe Form wie eine ``AUFGABEN``-Zeile (``kennung``, ``text``,
    ``zustand``, ``ziel``) -- ``aus_daten`` und ``werkbank`` lesen sie
    gleich."""
    from interview_theater import workshop

    if not workshop.szenenkarten_aktiv():
        return None
    if nummer == 6:
        return _karten_zeilen(lage)
    if nummer == 7:
        return _stagescript_zeilen(lage)
    return None


def aus_daten(lage: dict) -> list[dict]:
    """Die sieben Phasen mit ihren Aufgaben -- rein, ohne Datenbank.

    ``lage`` traegt: ``stand`` (Arbeitsstand als Dict oder Row), ``figuren``,
    ``szenen``, ``interviews`` (je Dict mit ``zusammenfassung``),
    ``hat_verdichtung`` (mindestens eine Verdichtung -- dasselbe Mass wie
    ``phasen.voraussetzungen[4]``, unabhaengig davon, was ``interviews``
    traegt), ``offene_interviews`` (beendete Interviews ohne Verdichtung,
    ``bool``), ``zuordnungen`` (Anzahl Schaerfungen), ``pruefrunde``,
    ``phase``, ``interviewmodus``, ``tippt`` und ``strom`` (die ``art`` einer
    laufenden ``web_strom``-Zeile oder ``None``). ``hat_verdichtung`` und
    ``offene_interviews`` fehlen durfen: ``bereit``/``fehlt`` lesen sie ueber
    ``.get`` und werten eine fehlende Angabe als "nicht erfuellt"."""
    jetzige = lage["phase"]
    ergebnis = []
    for nummer, name, satz in phasen.PHASEN:
        karten_zeilen = _karten_aufgaben_fuer(nummer, lage)
        if karten_zeilen is not None:
            aufgaben = karten_zeilen
        else:
            aufgaben = []
            for aufgabe in _aufgaben_fuer(nummer):
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
            "satz": satz,
            "bezeichnung": phasen.bezeichnung(nummer),
            "aktiv": nummer == jetzige,
            "erledigt": sum(1 for a in aufgaben if a["zustand"] == "erledigt"),
            "gesamt": len(aufgaben),
            "aufgaben": aufgaben,
            # UX-Knoepfe-Karte, Abschnitt 4: darf die Phasenleiste ohne
            # Hinweis dorthin springen, und wenn nicht, was fehlt.
            "bereit": bereit(nummer, lage),
            "fehlt": fehlt(nummer, lage),
        })
    return ergebnis


# --- Die Werkbank (Padua, 03.10.2026) ---------------------------------------
#
# Der Arbeitsstand-Tab in Padua ist eine reine Statusansicht: je Phase ihre
# Attribute mit einem von drei Zustaenden. Dieselbe ``lage`` wie
# ``aus_daten``, dieselben ``AUFGABEN`` -- dazu Detailzeilen, die nur lesen,
# was in ``lage`` steht. Die Beschriftung der Details macht ``web.py``; hier
# stehen nur Kennungen. Auch das Stepper-Bottom-Sheet (Karte t_cc4306db)
# liest diese Funktion.

ERLEDIGT = "erledigt"
OFFEN = "offen"
SPAETER = "spaeter"


def status(erledigt: bool, nummer: int, aktuelle_phase: int) -> str:
    """Erledigt, sonst offen bis zur aktuellen Phase, danach spaeter.

    Eine noch nicht erreichte Phase hat nichts "Offenes" -- dort steht
    niemand im Verzug (Birk: dezent, aber klar)."""
    if erledigt:
        return ERLEDIGT
    return OFFEN if nummer <= aktuelle_phase else SPAETER


def _roh(quelle, name: str):
    """Ein Feld als Rohwert -- ``None``, wenn es fehlt (Dict, Row, ``None``)."""
    if quelle is None:
        return None
    try:
        return quelle[name]
    except (IndexError, KeyError, TypeError):
        return None


def _szenenzeilen(kennung: str, szenen, feld: str) -> list[tuple]:
    return [
        (kennung, bool(_text(s, feld)), _roh(s, "nummer"), _text(s, "titel") or None)
        for s in szenen
    ]


def _details(nummer: int, lage: dict) -> list[tuple]:
    """Die Detailzeilen einer Phase als ``(kennung, erledigt, bezug, titel)``."""
    stand = lage["stand"]
    # Phase 1 hat keine Detailzeile mehr: "Discussion summarised" ist kein
    # Schritt der Gruppe, die Verdichtung laeuft still im Hintergrund und
    # geht in den Phase-2-Prompt (Birk, 05.10.2026).
    if nummer == 3:
        return [
            ("interview", bool(_roh(i, "zusammenfassung")), _roh(i, "bezeichnung"), None)
            for i in lage["interviews"]
        ]
    if nummer == 5:
        return _szenenzeilen("prosa", lage["szenen"], "prosa")
    if nummer == 6:
        return (
            [("gesamttext", bool(_text(stand, "gesamttext_fixiert_am")), None, None)]
            + _szenenzeilen("ueberarbeitet", lage["szenen"], "ueberarbeitung_bestaetigt_am")
        )
    if nummer == 7:
        return _szenenzeilen("form", lage["szenen"], "form") + [
            ("sprechweise", bool(_text(f, "sprachstil")), _text(f, "name") or None, None)
            for f in lage["figuren"]
        ]
    return []


def werkbank(lage: dict, aktuelle_phase: int) -> list[dict]:
    """Die sieben Phasen mit ihren Attributen und je einem Zustand -- rein.

    Rueckgabeform siehe ``docs/superpowers/plans/2026-10-03-padua-workbench-
    readonly.md`` (Kopf): je Phase ``nummer``, ``name``, ``bezeichnung``,
    ``aktiv``, ``erledigt``, ``gesamt``, ``fertig`` und ``zeilen``; je Zeile
    ``kennung``, ``art`` ("aufgabe"/"detail"), ``text``, ``bezug``, ``titel``,
    ``status`` und ``laeuft``. 'laeuft' ist ein Vermerk an einer offenen
    Aufgabe, kein vierter Zustand."""
    ergebnis = []
    for nummer, name, _satz in phasen.PHASEN:
        zeilen = []
        karten_zeilen = _karten_aufgaben_fuer(nummer, lage)
        if karten_zeilen is not None:
            for a in karten_zeilen:
                stand = status(a["zustand"] == "erledigt", nummer, aktuelle_phase)
                zeilen.append({
                    "kennung": a["kennung"], "art": "aufgabe",
                    "text": a["text"], "bezug": None, "titel": None,
                    "status": stand,
                    "laeuft": stand != ERLEDIGT and a["zustand"] == "laeuft",
                })
        else:
            for aufgabe in _aufgaben_fuer(nummer):
                stand = status(aufgabe.erledigt(lage), nummer, aktuelle_phase)
                zeilen.append({
                    "kennung": aufgabe.kennung, "art": "aufgabe",
                    "text": phasentexte.beschriftung(aufgabe.parameter),
                    "bezug": None, "titel": None, "status": stand,
                    "laeuft": stand != ERLEDIGT and _zustand(aufgabe, lage) == "laeuft",
                })
            for kennung, erledigt, bezug, titel in _details(nummer, lage):
                zeilen.append({
                    "kennung": kennung, "art": "detail", "text": None,
                    "bezug": bezug, "titel": titel,
                    "status": status(erledigt, nummer, aktuelle_phase), "laeuft": False,
                })
        erledigt = sum(1 for z in zeilen if z["status"] == ERLEDIGT)
        ergebnis.append({
            "nummer": nummer,
            "name": name,
            "bezeichnung": phasen.bezeichnung(nummer),
            "aktiv": nummer == aktuelle_phase,
            "erledigt": erledigt,
            "gesamt": len(zeilen),
            "fertig": bool(zeilen) and erledigt == len(zeilen),
            "zeilen": zeilen,
        })
    return ergebnis


def begriffe_detail(stand) -> list[dict]:
    """Der Haken fuer ``arbeitsstand.begriffe_detail`` (Karte t_4517d4ad):
    eine JSON-Liste ``[{begriff, begruendung, zitat, doppelbedeutung}]``.

    Defensiv: fehlt die Spalte, ist sie leer oder kaputt, kommt eine leere
    Liste -- nie ein Fehler (der Webserver migriert nichts). Das ``zitat``
    geht bewusst NICHT mit: es hat keine ``zitat_geprueft``-Pruefung, und auf
    der Seite steht kein ungeprueftes Zitat (docs/agents/weboberflaeche.md, "Drei Grenzen")."""
    roh = _text(stand, "begriffe_detail")
    if not roh:
        return []
    try:
        eintraege = json.loads(roh)
    except (ValueError, TypeError):
        return []
    if not isinstance(eintraege, list):
        return []
    ergebnis = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        begriff = str(eintrag.get("begriff") or "").strip()
        if not begriff:
            continue
        ergebnis.append({
            "begriff": begriff,
            "begruendung": str(eintrag.get("begruendung") or "").strip(),
            "doppelbedeutung": str(eintrag.get("doppelbedeutung") or "").strip(),
        })
    return ergebnis


def _fragenzeilen(roh: str) -> list[str]:
    """Die Zeilen eines Fragenfelds ohne Aufzaehlungszeichen -- dieselbe
    Saeuberung wie ``vorschlag.zeilen``, hier nachgebaut, weil der Webserver
    dieses Modul ohne Bot-Abhaengigkeiten liest."""
    import re

    ergebnis = []
    for zeile in (roh or "").splitlines():
        sauber = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", zeile).strip()
        if sauber:
            ergebnis.append(sauber)
    return ergebnis


def _einzelfragen(text: str) -> list[str]:
    """Mehrere Fragen in einer Zeile ("Q1? Q2? Q3?", live G1 05.10.2026 in
    ``fragen``) als einzelne Fragen -- getrennt nach einem "?" vor einem
    Grossbuchstaben. Ein kurzes Anhaengsel ("Perché?", "E in che modo?")
    bleibt an der Frage davor. Nur fuer die Anzeige; gespeichert wird nichts
    anders."""
    import re

    if not text:
        return []
    teile: list[str] = []
    for stueck in re.split(r"(?<=\?)\s+(?=[A-ZÀ-ÖØ-Þ¿¡])", text):
        if teile and len(stueck.split()) < 4:
            teile[-1] = f"{teile[-1]} {stueck}"
        else:
            teile.append(stueck)
    return teile


def fragenuebersicht(stand) -> list[dict]:
    """Der CoThinker in Phase 2 (Birk, 05.10.2026): je Begriff der Gruppe die
    Fragen, die bisher dazu stehen -- ``[{begriff, fragen: [text]}]`` in der
    Reihenfolge der Begriffe. **Keine Soll-Zahl**: wie viele Fragen ein
    Begriff bekommt, entscheidet die Gruppe; ein Begriff ohne Frage hat eine
    leere Liste, mehr nicht.

    Quelle sind die bestaetigten Fragen (``fragen``) und die laufende eigene
    Liste (``fragen_eigene_vorschlag``), Dubletten einmal. Steht die
    Entscheidung Frage fuer Frage schon (``fragen_herkunft_final`` ist nicht
    NULL), gilt nur noch ``fragen`` -- eine verworfene eigene Frage soll dann
    nicht mehr dastehen. Zeilen ohne passenden Begriff stehen unveraendert
    in einer letzten Gruppe mit ``begriff == ""`` (nur, wenn es sie gibt):
    kein Begriff wird erfunden, aber auch keine Frage verloren. Rein, kein
    SQL.

    Der Begriffsabgleich ist derselbe wie im A/B-Vergleich
    (``knoepfe.fragen._ordne_zeilen``, P2-H2, Feedbackloop P1-2): tolerant
    gegenueber Markdown-Zierde, Anfuehrungszeichen, Artikel, Plural-s und
    Gedankenstrich statt Doppelpunkt -- vorher verlangte diese Funktion den
    exakten Praefix "<Begriff>: " und liess echte Modellausgabe (fett,
    Artikel vorweg) genauso stumm aus der Uebersicht fallen wie damals aus
    dem Vergleich. ``roadmap`` ist Fachlogik, ``knoepfe`` Oberflaeche --
    deshalb ein lokaler Import hier statt am Modulkopf (AGENTS.md,
    Modulkarte: Aufrufe nach oben stehen als lokaler Import in der
    Funktion, die sie braucht)."""
    from interview_theater import begriffe as begriffe_modul
    from interview_theater.knoepfe.fragen import _ordne_zeilen

    begriffe = begriffe_modul.zerlege(_text(stand, "begriffe"))
    if not begriffe:
        return []
    zeilen = _fragenzeilen(_text(stand, "fragen"))
    if _roh(stand, "fragen_herkunft_final") is None:
        zeilen += _fragenzeilen(_text(stand, "fragen_eigene_vorschlag"))
    # ``rest`` (Zeilen ohne erkennbaren Begriff): bis zum Abschlussreview
    # (robo-fbl) fiel eine solche Zeile heraus -- eine angenommene Frage
    # verschwand aus der Uebersicht. Jetzt steht sie unveraendert in einer
    # letzten Gruppe mit leerem Begriff (kein Begriff erfunden, wie in der
    # Gegenueberstellung, ``knoepfe.fragen.versuche_gegenueberstellung``).
    je_begriff, rest = _ordne_zeilen(begriffe, zeilen)
    gesehen: set[tuple[str, str]] = set()
    ergebnis = []
    for begriff in begriffe:
        fragen = []
        for zeile in je_begriff.get(begriff, []):
            # ``_ordne_zeilen`` schreibt "<Begriff>: <Frage>" -- der Begriff
            # kann selbst einen Doppelpunkt tragen (G3, 05.10.2026: "EVENTO:
            # dall'esterno all'interno"), also den Begriff abschneiden, nicht
            # am ersten Doppelpunkt teilen.
            frage = zeile[len(begriff) + 1:] if zeile.startswith(begriff + ":") else ""
            for teil in _einzelfragen(" ".join(frage.split())):
                schluessel = (begriff, teil.casefold())
                if schluessel in gesehen:
                    continue
                gesehen.add(schluessel)
                fragen.append(teil)
        ergebnis.append({"begriff": begriff, "fragen": fragen})
    ohne_begriff = []
    for zeile in rest:
        zeile = " ".join(zeile.split())
        schluessel = ("", zeile.casefold())
        if not zeile or schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        ohne_begriff.append(zeile)
    if ohne_begriff:
        ergebnis.append({"begriff": "", "fragen": ohne_begriff})
    return ergebnis


# --- Internet-Recherche (Karte t_c5117c91) ---------------------------------
#
# Ein eigener Abschnitt, unabhaengig von den sieben Phasen: eine Recherche
# gehoert zu keiner Phase und gate't keinen Phasensprung (anders als
# AUFGABEN/_GATE oben) -- sie ist Material von aussen, das die Werkbank
# klar als solches zeigt ("Research - from the internet (not interview
# material)", siehe web.py). Reine Funktion ueber Dicts wie ``aus_daten``/
# ``werkbank``: ``recherchen`` kommt vom Bot ueber ``repo.hole_recherchen``
# oder vom Webserver ueber die read-only Leseseite, beide liefern dieselbe
# Form (``frage``, ``ergebnis_text``, ``quellen``).


def recherche_abschnitt(recherchen: list[dict]) -> list[dict]:
    """Die Recherchekarten fuer die Werkbank, in der Reihenfolge von
    ``recherchen`` (neueste zuerst, wie ``repo.hole_recherchen``). Eine
    Quelle ohne Titel zeigt ihre URL -- nie eine erfundene Bezeichnung."""
    ergebnis = []
    for r in recherchen:
        quellen = [
            (q.get("titel") or "").strip() or q.get("url") or ""
            for q in (r.get("quellen") or [])
        ]
        ergebnis.append({
            "frage": r.get("frage") or "",
            "ergebnis_text": r.get("ergebnis_text") or "",
            "quellen": [q for q in quellen if q],
        })
    return ergebnis


def register(conn, chat_id: int) -> list[dict]:
    """Der Weg des Bots, ueber ``repo``. Kein Modellaufruf, kein
    Schreibvorgang."""
    from interview_theater import aufnahme, repo

    verdichtungen = repo.verdichtungen(conn, chat_id)
    return aus_daten({
        "stand": repo.hole_arbeitsstand(conn, chat_id),
        "figuren": repo.figuren(conn, chat_id),
        "szenen": repo.hole_szenen(conn, chat_id),
        "interviews": [
            {"zusammenfassung": v["zusammenfassung"]} for v in verdichtungen
        ],
        "hat_verdichtung": bool(verdichtungen),
        "offene_interviews": bool(aufnahme.unausgewertete_interviews(conn, chat_id)),
        "zuordnungen": _zuordnungen_anzahl(conn, chat_id),
        "pruefrunde": repo.letzte_pruefrunde(conn, chat_id),
        "phase": phasen.aktuelle(conn, chat_id),
        "interviewmodus": repo.ist_interviewmodus_an(conn, chat_id),
        "tippt": False,
        "strom": next(
            (z["art"] for z in repo.laufende_stroeme(conn, chat_id)), None),
    })


def _zuordnungen_anzahl(conn, chat_id: int) -> int:
    """Mit CoThinker-Liste (Padua, ``diskussion_aktiv``) die feste, sichtbare
    Auswahl (Birk 07.10.2026 ~19:25, ``web_daten.auswahl_anzahl``), sonst wie
    bisher alle Zuordnungen."""
    from interview_theater import repo, web_daten, workshop

    if workshop.diskussion_aktiv():
        return web_daten.auswahl_anzahl(conn, chat_id)
    return len(repo.schaerfungen(conn, chat_id))
