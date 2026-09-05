"""Der Richter: Claude Opus bewertet den Lauf abschnittsweise nach fester
Metrik.

Ein Aufruf je Skript-Schritt, plus einer fuer den Szenentext. Modell:
``simulation/claude.py`` -- Opus am lokalen Proxy, nicht das Erkennermodell
des Bots. Der Richter gehoert zur Simulationsseite, nicht zum Prueflung; er
soll lesen koennen, ob eine Antwort auf das eingeht, was zwei Nachrichten
frueher gesagt wurde, und das ist keine Klassifikationsaufgabe.

**Kein erzwungenes Schema.** Der Proxy kennt keinen Schema-Modus. Der Richter
bekommt die Felderliste stattdessen im Nutzertext und die Anweisung, reines
JSON zu liefern (``anforderung``); gelesen wird mit ``claude.lies_json``, das
genau einen Reparaturversuch macht (```json-Zaun entfernen).

**Warum ueberhaupt ein Modell.** Die harten Fehler zaehlt
``kennzahlen.py`` ohne Modell -- Echo, behauptete Schreibvorgaenge,
Namensanrede, Laenge. Was sich so nicht zaehlen laesst, ist die Frage, ob der
Bot auf das eingeht, was gerade gesagt wurde, oder ob er einen Text liefert,
der auf jede Nachricht gepasst haette. Genau dafuer, und nur dafuer, ist der
Richter da.

**Ein Fehlschlag ist kein Abbruch.** Faellt ein Abschnitt aus (Modellfehler,
kaputtes JSON), bekommt er die Note ``None`` und einen Satz darueber; die
mechanischen Kennzahlen und der Rest des Berichts bleiben vollstaendig. Ein
Lauf, der Geld gekostet hat, soll nicht an der Bewertung sterben.
"""

from __future__ import annotations

import logging

from interview_theater import anweisungen

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Statistik des Simulationsklienten.
ART = "richter"

#: Ausgabebudget eines Richterurteils. Grosszuegig: das Urteil enthaelt die
#: schlechteste Bot-Antwort im Wortlaut, und die kann lang sein.
MAX_TOKENS = 4000

#: Die vier Noten, die jeder Abschnitt bekommt.
KRITERIEN = (
    "geht_auf_gesagtes_ein",
    "bietet_an_statt_vorzuschreiben",
    "phase_transparent",
    "korrektur_angenommen",
)

#: Die drei Noten, die nur ein Szenentext bekommt. ``form_eingehalten`` kam
#: mit ``--set birk`` dazu: dort werden drei Szenen in drei Formen verlangt
#: (Dialog, Lied, Rap), und ob der Bot eine Formvorgabe durchhaelt, die nicht
#: Dialog heisst, ist genau das Experiment. Ohne Formvorgabe vergibt der
#: Richter laut Metrik eine 2 -- ein Bot wird nicht dafuer bestraft, dass eine
#: Situation nicht vorkam.
SZENEN_KRITERIEN = ("szene_stimmt_zur_planung", "stimmen_unterscheidbar",
                    "form_eingehalten")

BESTNOTE = 2


def _note() -> dict:
    """Ein Notenfeld. Kein ``enum`` und kein ``minimum``: strikte Modi
    unterstuetzen beides nicht zuverlaessig (AGENTS.md 'Die Fallen'), und
    ausserhalb von 0-2 wird ohnehin geklemmt (``_klemme``)."""
    return {"type": "integer"}


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [*KRITERIEN, "satz", "zustimmungen", "schlechteste_antwort",
                 "begruendung"],
    "properties": {
        **{k: _note() for k in KRITERIEN},
        "satz": {"type": "string"},
        "zustimmungen": {"type": "array", "items": {"type": "string"}},
        "schlechteste_antwort": {"type": "string"},
        "begruendung": {"type": "string"},
    },
}

SZENEN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [*SZENEN_KRITERIEN, "satz"],
    "properties": {
        **{k: _note() for k in SZENEN_KRITERIEN},
        "satz": {"type": "string"},
    },
}


#: Wie ein Feldtyp im Anforderungstext heisst -- deutsch, weil der ganze
#: Prompt deutsch ist und "integer" darin wie ein Stolperstein laege.
_TYPNAMEN = {
    "integer": "eine ganze Zahl 0, 1 oder 2",
    "string": "ein Text",
    "array": "eine Liste von Texten",
}


def anforderung(schema: dict) -> str:
    """Die Anweisung, reines JSON in genau dieser Form zu liefern -- aus dem
    Schema erzeugt, nicht danebengeschrieben.

    Der Proxy kennt keinen erzwungenen Schema-Modus (``claude.py``), also
    muss die Form in den Nutzertext. Sie hier aus ``SCHEMA`` abzuleiten statt
    sie ein zweites Mal hinzuschreiben ist kein Schoenheitsdienst: eine
    Metrik, die im Schema ein Kriterium mehr hat als im Prompttext, liefert
    lautlos ``None`` fuer dieses Kriterium, und im Bericht steht dann ein
    Strich, den niemand erklaeren kann."""
    zeilen = ["Antworte mit einem einzigen JSON-Objekt, ohne Text davor oder "
              "danach, ohne Code-Zaun. Genau diese Felder:"]
    for name in schema["required"]:
        typ = schema["properties"][name].get("type", "string")
        zeilen.append(f'- "{name}": {_TYPNAMEN.get(typ, typ)}')
    return "\n".join(zeilen)


def prompt() -> str:
    """Die Metrik, heiss nachgeladen (``interview_theater/prompts/richter.md``).

    Sie liegt bei den uebrigen Prompts und nicht neben diesem Modul, aus
    demselben Grund wie ``erkenner.md``: der Betreiber zieht sie nach, wenn
    der Bericht Noten liefert, die er nicht teilt -- und dann soll sie dort
    liegen, wo er alle anderen Prompts auch sucht."""
    return anweisungen.hole("richter")


def _klemme(wert) -> int:
    """Eine Note auf 0-2 begrenzen. Ein Modell, das 5 liefert, meint 'gut';
    ein Modell, das -1 liefert, meint 'schlecht'. Beides ist eine Note, kein
    Fehler, und einen ganzen Abschnitt daran scheitern zu lassen waere teurer
    als die Ungenauigkeit."""
    try:
        return max(0, min(BESTNOTE, int(wert)))
    except (TypeError, ValueError):
        return 0


def baue_nutzertext(titel: str, ziel: str, abschnitt: str) -> str:
    """Der Nutzertext eines Abschnitts: worum es dem Schritt ging, dann der
    Wortlaut. Das Ziel steht **vor** dem Abschnitt, weil der Richter sonst
    nicht beurteilen kann, ob der Bot am Thema vorbeigeantwortet hat."""
    return "\n".join([
        f"Abschnitt: {titel}",
        f"Was die Gruppe in diesem Abschnitt wollte: {ziel.strip()}",
        "",
        "Der Wortlaut:",
        abschnitt.strip() or "(keine Nachrichten in diesem Abschnitt)",
        "",
        anforderung(SCHEMA),
    ])


def baue_szenen_nutzertext(planung: str, szene: str, form: str = "") -> str:
    return "\n".join([
        "Die Gruppe hat diese Szene geplant:",
        planung.strip() or "(keine Planung im Wortlaut)",
        "",
        (f"Verlangte Form: {form.strip()}." if form.strip()
         else "Es war keine besondere Form verlangt."),
        "",
        "Das ist der Szenentext, den der Bot daraus geschrieben hat:",
        szene.strip(),
        "",
        anforderung(SZENEN_SCHEMA),
    ])


def _leeres_urteil(fehler: str) -> dict:
    return {
        **{k: None for k in KRITERIEN},
        "satz": f"Nicht bewertet: {fehler}",
        "zustimmungen": [],
        "schlechteste_antwort": "",
        "begruendung": "",
        "fehler": fehler,
    }


def bewerte_abschnitt(sim, titel: str, ziel: str, abschnitt: str) -> dict:
    """Bewertet einen Abschnitt. Liefert immer ein Dict -- bei einem
    Fehlschlag eines mit Noten ``None`` und dem Fehler im Satz."""
    try:
        ergebnis = sim.json_objekt(
            prompt(), baue_nutzertext(titel, ziel, abschnitt), ART,
            max_tokens=MAX_TOKENS,
        )
    except Exception as fehler:  # noqa: BLE001 -- ein Abschnitt reisst den Lauf nie mit
        log.exception("Richter-Aufruf fehlgeschlagen: %s", titel)
        return _leeres_urteil(f"{type(fehler).__name__}: {fehler}")

    urteil = {k: _klemme(ergebnis.get(k)) for k in KRITERIEN}
    urteil["satz"] = (ergebnis.get("satz") or "").strip()
    urteil["zustimmungen"] = [
        str(k).strip() for k in (ergebnis.get("zustimmungen") or []) if str(k).strip()
    ]
    urteil["schlechteste_antwort"] = (ergebnis.get("schlechteste_antwort") or "").strip()
    urteil["begruendung"] = (ergebnis.get("begruendung") or "").strip()
    urteil["fehler"] = None
    return urteil


def bewerte_szene(sim, planung: str, szene: str, form: str = "") -> dict:
    """Die drei Noten, die nur ein Szenentext bekommt. Leeres Dict, wenn keine
    Szene geschrieben wurde -- ``--ohne-szene`` ist ein zulaessiger Lauf, kein
    Mangel."""
    if not (szene or "").strip():
        return {}
    try:
        ergebnis = sim.json_objekt(
            prompt(), baue_szenen_nutzertext(planung, szene, form), ART,
            max_tokens=MAX_TOKENS,
        )
    except Exception as fehler:  # noqa: BLE001
        log.exception("Richter-Aufruf zur Szene fehlgeschlagen")
        return {
            **{k: None for k in SZENEN_KRITERIEN},
            "satz": f"Nicht bewertet: {type(fehler).__name__}: {fehler}",
            "fehler": str(fehler),
        }
    return {
        **{k: _klemme(ergebnis.get(k)) for k in SZENEN_KRITERIEN},
        "satz": (ergebnis.get("satz") or "").strip(),
        "fehler": None,
    }


def summe(urteil: dict, kriterien=KRITERIEN) -> int | None:
    """Die Notensumme eines Abschnitts, oder None, wenn er nicht bewertet
    wurde. Grundlage der Rangfolge im Bericht: die schlechtesten Abschnitte
    stehen dort mit ihrer schlechtesten Antwort."""
    noten = [urteil.get(k) for k in kriterien]
    if any(n is None for n in noten):
        return None
    return sum(noten)


def markierte_zustimmungen(urteile: dict) -> set[str]:
    """Alle Kennungen, die der Richter ueber alle Abschnitte hinweg als
    Zustimmung markiert hat -- die Eingabe fuer
    ``kennzahlen.zustimmungen``."""
    return {
        kennung
        for urteil in urteile.values()
        for kennung in urteil.get("zustimmungen", [])
    }
