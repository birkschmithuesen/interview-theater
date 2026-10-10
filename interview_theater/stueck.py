"""Das Stueckmodell: die EINE Mutations-Schnittstelle (Karte t_fd88600b,
Birk 10.10.2026, Kernkarte t_5a439d0d).

Jede Tatsache ueber ein Stueck steht an genau einer Stelle; Karte,
Script-Kopf, PDF, Werkbank und Prompt sind Ansichten
(``stueck_sicht.karte_ansicht``). Geaendert wird NUR hier:

* in jeder Phase -- Phasen bestimmen Fokus und Vorschlag, nie ein Verbot;
* Strukturfelder ziehen deterministisch nach (es gibt nur eine Stelle);
* Prosa (Stage Script, Kopf) wird NIE still umgeschrieben -- sie wird als
  ``veraltet`` vermerkt, und die Gruppe bekommt "Szene N passt nicht mehr
  zu ... -- neu schreiben? Ja/Nein" (``knoepfe.szenen.biete_veraltete``);
* die deterministischen Pruefungen (Busy-Gate, Kartentreue, [OPEN]-
  Reinigung, Zitat nur aus geprueftem Bestand, Diff) laufen HIER.

**Werkzeug-Zuschnitt** (B-vs-C bleibt offen, Folie 7): jede oeffentliche
Funktion nimmt ``(conn, chat_id, *, <JSON-Werte>)`` und gibt ``Ergebnis``
zurueck -- kein ``tg``/``klm``/``e``, kein Senden, kein Modellaufruf. Damit
ist sie 1:1 als Werkzeug eines spaeteren Agenten aufrufbar
(``tests/test_stueck_schnittstelle.py``)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from interview_theater import repo, stueck_sicht

QUELLE_GRUPPE = "gruppe"
QUELLE_SCRIPT = "script"
QUELLE_KARTE_MODELL = "karte_modell"
QUELLE_PLANUNG = "planung"
QUELLE_AGENT = "agent"
#: Der Schreiber selbst -- fuer ihn gilt das Busy-Gate nicht.
INTERNE_QUELLEN = frozenset({QUELLE_SCRIPT, QUELLE_KARTE_MODELL, QUELLE_PLANUNG})

#: Die oeffentlichen Werkzeuge (Reihenfolge = Tool-Liste eines spaeteren Agenten).
WERKZEUGE = (
    "setze_rahmen", "setze_ort", "setze_besetzung", "figur_hinzu", "figur_aus_szene",
    "karte_aendern", "szene_wieder_oeffnen", "reihenfolge_aendern",
    "frage_stellen", "frage_beantworten", "frage_zurueckstellen", "frage_verwerfen",
    "pruefe_szene",
)

_MIN_ERWAEHNUNG = 4


@dataclass(frozen=True)
class Ergebnis:
    ok: bool
    aenderung_id: int | None = None
    diff: tuple[str, ...] = ()
    warnungen: tuple[str, ...] = ()
    veraltet: tuple[int, ...] = ()
    fehler: str | None = None
    frage_id: int | None = None

    def als_dict(self) -> dict:
        return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}


def _nein(fehler: str, *warnungen: str) -> Ergebnis:
    return Ergebnis(ok=False, fehler=fehler, warnungen=tuple(warnungen))


def _beschaeftigt(chat_id: int, quelle: str) -> bool:
    if quelle in INTERNE_QUELLEN:
        return False
    from interview_theater import ueberarbeitung

    return ueberarbeitung.laeuft(chat_id)


def _szene(conn, chat_id: int, nummer: int):
    return next((s for s in repo.hole_szenen(conn, chat_id)
                 if s["nummer"] == nummer and not s["entfernt_am"]), None)


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def _erwaehnt(text, wert) -> bool:
    w = stueck_sicht.normalisiert(wert)
    return len(w) >= _MIN_ERWAEHNUNG and w in stueck_sicht.normalisiert(text)


def _punkt_offen(chat_id: int) -> str:
    from interview_theater import szenenkarte

    return szenenkarte._T(chat_id)._PUNKT_OFFEN


def karte(conn, szene) -> dict | None:
    """Die Karte, wie JEDE Ansicht sie zeigt -- aus den einen Stellen
    abgeleitet. ``szene`` ist eine ``szene``-Zeile."""
    from interview_theater import szenenkarte

    roh = szenenkarte.roh_karte_von(szene)
    if roh is None:
        return None
    fragen = repo.offene_fragen(conn, szene["chat_id"], szene["id"])
    return stueck_sicht.karte_ansicht(
        roh, ort=szene["ort"],
        besetzung=[(b["name"], b["rolle"]) for b in repo.besetzung(conn, szene["id"])],
        zusatz=szene["wer_zusatz"] if "wer_zusatz" in szene.keys() else None,
        fragen_offen=[f["text"] for f in fragen if f["status"] == "offen"],
        fragen_vertagt=[f["text"] for f in fragen if f["status"] == "vertagt"],
        punkt_offen=_punkt_offen(szene["chat_id"]),
    )


def _protokoll(conn, chat_id: int, art: str, ziel: dict, vorher, nachher, quelle: str) -> int:
    return repo.merke_stueck_aenderung(conn, chat_id, art, ziel, vorher, nachher, quelle)


def _markiere_script(conn, chat_id: int, szene, grund: str, aenderung_id: int) -> int | None:
    if szene is None or not _gesetzt(szene["volltext"]):
        return None
    return repo.merke_veraltet(conn, chat_id, szene["id"], "script", grund, aenderung_id)


def _markiere_kopf(conn, chat_id: int, grund: str, aenderung_id: int,
                   nur_wenn_erwaehnt: str | None = None) -> int | None:
    stand = repo.hole_arbeitsstand(conn, chat_id)
    kopf = (stand["stage_kopf"] if stand is not None else None) or ""
    if not kopf.strip():
        return None
    if nur_wenn_erwaehnt is not None and not _erwaehnt(kopf, nur_wenn_erwaehnt):
        return None
    return repo.merke_veraltet(conn, chat_id, None, "kopf", grund, aenderung_id)


def _ergebnis(aenderung_id, diff=(), veraltet=(), warnungen=(), frage_id=None) -> Ergebnis:
    return Ergebnis(ok=True, aenderung_id=aenderung_id, diff=tuple(diff),
                    veraltet=tuple(v for v in veraltet if v is not None),
                    warnungen=tuple(warnungen), frage_id=frage_id)


def setze_rahmen(conn, chat_id: int, *, rahmen: str, quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    stand = repo.hole_arbeitsstand(conn, chat_id)
    alt = (stand["rahmen"] if stand is not None else None) or ""
    neu = " ".join((rahmen or "").split())
    if stueck_sicht.normalisiert(alt) == stueck_sicht.normalisiert(neu):
        return Ergebnis(ok=True)
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", neu or None)
    aid = _protokoll(conn, chat_id, "setze_rahmen", {}, alt, neu, quelle)
    v = _markiere_kopf(conn, chat_id, T._GRUND_RAHMEN, aid)
    return _ergebnis(aid, [f"rahmen: {alt or '(none)'} -> {neu or '(none)'}"], [v])


def setze_ort(conn, chat_id: int, *, szene: int, ort: str | None,
              quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    alt = zeile["ort"] or ""
    neu = " ".join((ort or "").split())
    if stueck_sicht.normalisiert(alt) == stueck_sicht.normalisiert(neu):
        return Ergebnis(ok=True)
    repo.setze_szenenort(conn, zeile["id"], neu or None)
    aid = _protokoll(conn, chat_id, "setze_ort", {"szene": szene}, alt, neu, quelle)
    grund = T._GRUND_ORT.format(neu=neu or "—")
    veraltet = []
    for s in repo.hole_szenen(conn, chat_id):
        if s["entfernt_am"] or s["nummer"] is None:
            continue
        if s["id"] == zeile["id"]:
            if quelle != QUELLE_SCRIPT:
                veraltet.append(_markiere_script(conn, chat_id, s, grund, aid))
        elif alt and _erwaehnt(s["volltext"], alt):
            veraltet.append(_markiere_script(conn, chat_id, s, grund, aid))
    if alt:
        veraltet.append(_markiere_kopf(conn, chat_id, grund, aid, nur_wenn_erwaehnt=alt))
    return _ergebnis(aid, [f"ort: {alt or '(none)'} -> {neu or '(none)'}"], veraltet)


def _figuren_index(conn, chat_id: int) -> dict[str, int]:
    return {stueck_sicht.normalisiert(f["name"]): f["id"] for f in repo.figuren(conn, chat_id)}


def _schreibe_besetzung(conn, chat_id: int, zeile, eintraege, zusatz, art: str,
                        ziel: dict, quelle: str, grund: str,
                        kopf_auch: bool = False) -> Ergebnis:
    alt = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
    alt_zusatz = zeile["wer_zusatz"]
    if alt == list(eintraege) and (alt_zusatz or None) == (zusatz or None):
        return Ergebnis(ok=True)
    alt_text = stueck_sicht.wer_text(
        [(b["name"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])], alt_zusatz)
    repo.setze_besetzung(conn, chat_id, zeile["id"], list(eintraege), zusatz or None)
    neu_text = stueck_sicht.wer_text(
        [(b["name"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])], zusatz)
    aid = _protokoll(conn, chat_id, art, ziel, alt_text, neu_text, quelle)
    veraltet = []
    if quelle != QUELLE_SCRIPT:
        veraltet.append(_markiere_script(conn, chat_id, zeile, grund, aid))
    if kopf_auch:
        veraltet.append(_markiere_kopf(conn, chat_id, grund, aid))
    return _ergebnis(aid, [f"wer: {alt_text or '(none)'} -> {neu_text or '(none)'}"], veraltet)


def setze_besetzung(conn, chat_id: int, *, szene: int, namen: list[str],
                    zusatz: str | None = None, quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    index = _figuren_index(conn, chat_id)
    rollen = {b["figur_id"]: b["rolle"] for b in repo.besetzung(conn, zeile["id"])}
    eintraege = []
    for name in namen:
        figur_id = index.get(stueck_sicht.normalisiert(name))
        if figur_id is None:
            return _nein("unbekannte_figur", T._WARNUNG_UNBEKANNTE_FIGUR.format(name=name))
        if figur_id not in dict(eintraege):
            eintraege.append((figur_id, rollen.get(figur_id)))
    return _schreibe_besetzung(conn, chat_id, zeile, eintraege, zusatz, "setze_besetzung",
                               {"szene": szene}, quelle,
                               T._GRUND_BESETZUNG.format(wer=", ".join(namen)))


def figur_hinzu(conn, chat_id: int, *, name: str, szene: int | None = None,
                rolle: str | None = None, beschreibung: str | None = None,
                quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    name = " ".join((name or "").split())
    if not name:
        return _nein("ungueltig")
    zeile = None
    if szene is not None:
        zeile = _szene(conn, chat_id, szene)
        if zeile is None:
            return _nein("unbekannte_szene")
    figur = repo.hole_figur(conn, chat_id, name)
    neu_angelegt = figur is None
    if neu_angelegt:
        repo.setze_figur(conn, chat_id, name, beschreibung or "")
        figur = repo.hole_figur(conn, chat_id, name)
    elif beschreibung and not _gesetzt(figur["beschreibung"]):
        repo.setze_figur_feld(conn, figur["id"], "beschreibung", beschreibung)
    grund = T._GRUND_FIGUR_NEU.format(name=figur["name"])
    if zeile is None:
        if not neu_angelegt:
            return Ergebnis(ok=True)
        aid = _protokoll(conn, chat_id, "figur_hinzu", {"name": name}, None, figur["name"], quelle)
        return _ergebnis(aid, [f"figur: + {figur['name']}"], [_markiere_kopf(conn, chat_id, grund, aid)])
    eintraege = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
    vorhanden = dict(eintraege)
    if figur["id"] in vorhanden:
        if rolle is None or vorhanden[figur["id"]] == rolle:
            return Ergebnis(ok=True)
        eintraege = [(f, rolle if f == figur["id"] else r) for f, r in eintraege]
    else:
        eintraege.append((figur["id"], rolle))
    return _schreibe_besetzung(conn, chat_id, zeile, eintraege, zeile["wer_zusatz"],
                               "figur_hinzu", {"name": name, "szene": szene}, quelle, grund,
                               kopf_auch=neu_angelegt)


def figur_aus_szene(conn, chat_id: int, *, name: str, szene: int,
                    quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    figur = repo.hole_figur(conn, chat_id, name)
    if figur is None:
        return _nein("unbekannte_figur", T._WARNUNG_UNBEKANNTE_FIGUR.format(name=name))
    eintraege = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
    if figur["id"] not in dict(eintraege):
        return Ergebnis(ok=True)
    eintraege = [(f, r) for f, r in eintraege if f != figur["id"]]
    return _schreibe_besetzung(conn, chat_id, zeile, eintraege, zeile["wer_zusatz"],
                               "figur_aus_szene", {"name": name, "szene": szene}, quelle,
                               T._GRUND_FIGUR_WEG.format(name=figur["name"]))


# --- Texte -----------------------------------------------------------------

_WARNUNG_BESCHAEFTIGT = "Gerade wird noch geschrieben -- gleich nochmal."
_WARNUNG_UNBEKANNTE_FIGUR = "{name} ist noch keine Figur des Stücks."
_GRUND_RAHMEN = "neuer Rahmen"
_GRUND_ORT = "neuer Ort ({neu})"
_GRUND_BESETZUNG = "neue Besetzung ({wer})"
_GRUND_FIGUR_NEU = "neue Figur {name}"
_GRUND_FIGUR_WEG = "{name} spielt nicht mehr mit"

from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)
