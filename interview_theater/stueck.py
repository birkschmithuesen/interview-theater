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


def _frage_bekannt(conn, chat_id: int, szene_id: int | None, text: str) -> int | None:
    """id einer Frage derselben Szene mit demselben (normalisierten) Text --
    egal welcher Status: eine beantwortete Frage wird nie wieder geoeffnet
    (Beleg 6, Kernkarte: 21 im Chat beantwortete Fragen blieben [OPEN])."""
    ziel = stueck_sicht.normalisiert(text)
    return next((f["id"] for f in repo.fragen_der_szene(conn, chat_id, szene_id)
                 if stueck_sicht.normalisiert(f["text"]) == ziel), None)


def karte_aendern(conn, chat_id: int, *, szene: int, worum: str | None = None,
                  typ: str | None = None, modus: str | None = None,
                  punkte: list[str] | None = None, punkte_hinzu: list[str] | None = None,
                  punkte_weg: list[str] | None = None, zitate: list[int] | None = None,
                  quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    from interview_theater import kartentreue, szenenkarte, szenenkern

    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    roh = szenenkarte.roh_karte_von(zeile)
    if roh is None:
        return _nein("keine_karte")
    neu = stueck_sicht.roh_ohne_struktur(roh)
    if typ is not None:
        if typ not in szenenkarte.TYPEN:
            return _nein("ungueltig")
        neu["typ"] = typ
    if modus is not None:
        if modus not in szenenkarte.MODI:
            return _nein("ungueltig")
        neu["modus"] = modus
    if neu.get("typ") != "moment":
        neu["modus"] = "none"
    if worum is not None:
        neu["worum"] = szenenkarte._kappe(worum)
    weg = set(punkte_weg or [])
    liste = list(neu.get("punkte") or []) if punkte is None else list(punkte)
    liste = [p for p in liste if p not in weg] + list(punkte_hinzu or [])
    fragen_neu: list[str] = []
    sauber: list[str] = []
    for p in liste:
        treffer = stueck_sicht.OFFEN_PUNKT.match(p or "")
        if treffer:
            fragen_neu.append(treffer.group(1))
        elif str(p).strip():
            sauber.append(szenenkarte._kappe(p))
    neu["punkte"] = sauber[:szenenkarte.PUNKTE_MAX]
    if zitate is not None:
        kandidaten = szenenkern._kandidaten(conn, chat_id, zeile)
        if any(not (1 <= int(n) <= len(kandidaten)) for n in zitate):
            return _nein("ungueltig")
        neu["zitate"] = [{"zitat": kandidaten[int(n) - 1][0], "interview": kandidaten[int(n) - 1][1]}
                         for n in zitate][:szenenkarte.ZITATE_MAX]
    alt_ansicht = karte(conn, zeile)
    karte_neu = neu != stueck_sicht.roh_ohne_struktur(roh)
    fragen_neu = [t for t in fragen_neu if not _frage_bekannt(conn, chat_id, zeile["id"], t)]
    if not karte_neu and not fragen_neu:
        return Ergebnis(ok=True)
    if karte_neu:
        repo.aktualisiere_szenenkarte(conn, chat_id, zeile["id"],
                                      json.dumps(neu, ensure_ascii=False),
                                      szenenkarte.AUSLOESER_AENDERUNG, None)
    for text in fragen_neu:
        repo.lege_offene_frage_an(conn, chat_id, zeile["id"], text, quelle, status="vertagt")
    neu_ansicht = karte(conn, repo.hole_szene(conn, zeile["id"]))
    diff = szenenkarte.diff_karten(alt_ansicht or {}, neu_ansicht or {})
    aid = _protokoll(conn, chat_id, "karte_aendern", {"szene": szene},
                     alt_ansicht, neu_ansicht, quelle)
    befunde: list[str] = []
    if _gesetzt(zeile["volltext"]):
        befunde = (kartentreue.widersprueche(neu_ansicht, zeile["volltext"])
                   + [T._BEFUND_FEHLT.format(stichwort=s)
                      for s in kartentreue.fehlende_stichworte(neu_ansicht, zeile["volltext"])])
    grund = T._GRUND_KARTE.format(felder=", ".join(d.split(":")[0] for d in diff) or "punkte")
    if befunde:
        grund += " -- " + "; ".join(befunde)
    v = _markiere_script(conn, chat_id, zeile, grund, aid) if quelle != QUELLE_SCRIPT else None
    return _ergebnis(aid, diff, [v], warnungen=befunde)


def szene_wieder_oeffnen(conn, chat_id: int, *, szene: int, ebene: str = "karte",
                         quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if ebene not in ("karte", "script"):
        return _nein("ungueltig")
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    if ebene == "karte":
        if not _gesetzt(zeile["karte_bestaetigt_am"]):
            return Ergebnis(ok=True)
        repo.setze_szenenkarte_offen(conn, zeile["id"])
    else:
        if not _gesetzt(zeile["fertig_am"]):
            return Ergebnis(ok=True)
        repo.setze_szene_fertig(conn, zeile["id"], False)
    aid = _protokoll(conn, chat_id, "szene_wieder_oeffnen", {"szene": szene, "ebene": ebene},
                     "abgenommen", "offen", quelle)
    return _ergebnis(aid, [f"{ebene}: abgenommen -> offen"])


def reihenfolge_aendern(conn, chat_id: int, *, folge: list[int],
                        quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    if _beschaeftigt(chat_id, quelle):
        return _nein("beschaeftigt", T._WARNUNG_BESCHAEFTIGT)
    szenen = sorted((s for s in repo.hole_szenen(conn, chat_id)
                     if s["nummer"] is not None and not s["entfernt_am"]),
                    key=lambda s: s["nummer"])
    je_nummer = {s["nummer"]: s for s in szenen}
    if sorted(folge) != sorted(je_nummer) or len(set(folge)) != len(folge):
        return _nein("ungueltig")
    if list(folge) == [s["nummer"] for s in szenen]:
        return Ergebnis(ok=True)
    repo.nummeriere_szenen(conn, chat_id, [je_nummer[n]["id"] for n in folge])
    aid = _protokoll(conn, chat_id, "reihenfolge_aendern", {"folge": list(folge)},
                     [s["nummer"] for s in szenen], list(folge), quelle)
    veraltet = []
    for neue_nummer, alte_nummer in enumerate(folge, start=1):
        if neue_nummer != alte_nummer:
            veraltet.append(_markiere_script(conn, chat_id, je_nummer[alte_nummer],
                                             T._GRUND_REIHENFOLGE.format(nummer=neue_nummer), aid))
    return _ergebnis(aid, [f"reihenfolge: {[s['nummer'] for s in szenen]} -> {list(folge)}"], veraltet)


def _frage_der_gruppe(conn, chat_id: int, frage_id: int):
    f = repo.hole_offene_frage(conn, frage_id)
    return f if f is not None and f["chat_id"] == chat_id else None


def _szene_nach_id(conn, szene_id: int | None):
    return repo.hole_szene(conn, szene_id) if szene_id is not None else None


def frage_stellen(conn, chat_id: int, *, frage: str, szene: int | None = None,
                  quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    text = " ".join((frage or "").split())
    if not text:
        return _nein("ungueltig")
    szene_id = None
    if szene is not None:
        zeile = _szene(conn, chat_id, szene)
        if zeile is None:
            return _nein("unbekannte_szene")
        szene_id = zeile["id"]
    bekannt = _frage_bekannt(conn, chat_id, szene_id, text)
    if bekannt is not None:
        f = repo.hole_offene_frage(conn, bekannt)
        warn = (T._WARNUNG_SCHON_BEANTWORTET,) if f["status"] in ("beantwortet", "uebersprungen") else ()
        return Ergebnis(ok=True, frage_id=bekannt, warnungen=warn)
    fid = repo.lege_offene_frage_an(conn, chat_id, szene_id, text, quelle)
    aid = _protokoll(conn, chat_id, "frage_stellen", {"szene": szene}, None, text, quelle)
    return _ergebnis(aid, [f"fragen: + {text}"], frage_id=fid)


def _schliesse(conn, chat_id: int, frage_id: int, status: str, antwort: str | None,
               art: str, quelle: str) -> Ergebnis:
    f = _frage_der_gruppe(conn, chat_id, frage_id)
    if f is None:
        return _nein("unbekannte_frage")
    if f["status"] == status and (antwort is None or f["antwort"] == antwort):
        return Ergebnis(ok=True, frage_id=frage_id)
    repo.setze_frage_status(conn, frage_id, status, antwort)
    aid = _protokoll(conn, chat_id, art, {"frage_id": frage_id}, f["status"], status, quelle)
    v = None
    if status == "beantwortet" and f["status"] in ("offen", "vertagt"):
        v = _markiere_script(conn, chat_id, _szene_nach_id(conn, f["szene_id"]),
                             T._GRUND_FRAGE.format(frage=f["text"]), aid)
    return _ergebnis(aid, [f"frage: {f['text']} -> {status}"], [v], frage_id=frage_id)


def frage_beantworten(conn, chat_id: int, *, frage_id: int, antwort: str,
                      quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    return _schliesse(conn, chat_id, frage_id, "beantwortet", (antwort or "").strip() or None,
                      "frage_beantworten", quelle)


def frage_zurueckstellen(conn, chat_id: int, *, frage_id: int,
                         quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    return _schliesse(conn, chat_id, frage_id, "vertagt", None, "frage_zurueckstellen", quelle)


def frage_verwerfen(conn, chat_id: int, *, frage_id: int,
                    quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    return _schliesse(conn, chat_id, frage_id, "uebersprungen", None, "frage_verwerfen", quelle)


def pruefe_szene(conn, chat_id: int, *, szene: int, quelle: str = QUELLE_GRUPPE) -> Ergebnis:
    from interview_theater import kartentreue

    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    k = karte(conn, zeile)
    if k is None or not _gesetzt(zeile["volltext"]):
        return Ergebnis(ok=True)
    befunde = (kartentreue.widersprueche(k, zeile["volltext"])
               + [T._BEFUND_FEHLT.format(stichwort=s)
                  for s in kartentreue.fehlende_stichworte(k, zeile["volltext"])])
    if not befunde:
        return Ergebnis(ok=True)
    aid = _protokoll(conn, chat_id, "pruefe_szene", {"szene": szene}, None, befunde, quelle)
    v = repo.merke_veraltet(conn, chat_id, zeile["id"], "script", "; ".join(befunde), aid)
    return _ergebnis(aid, veraltet=[v], warnungen=befunde)


def karte_aus_modell(conn, chat_id: int, *, szene: int, karte: dict, ausloeser: str,
                     notiz: str | None = None) -> Ergebnis:
    """Der EINE Weg, auf dem eine vom Modell gebaute Karte (``szenenkarte.
    erzeuge``) ins Stueckmodell kommt: Struktur an ihre Stellen, nur der Rest
    ins JSON. Das Modell darf Figuren hinzufuegen, nie still entfernen."""
    zeile = _szene(conn, chat_id, szene)
    if zeile is None:
        return _nein("unbekannte_szene")
    q = QUELLE_KARTE_MODELL
    if str(karte.get("ort") or "").strip():
        setze_ort(conn, chat_id, szene=szene, ort=karte["ort"], quelle=q)
    if str(karte.get("wer") or "").strip():
        eintraege, rest = stueck_sicht.ordne_besetzung(karte["wer"], _figuren_index(conn, chat_id))
        zeile = _szene(conn, chat_id, szene)
        bisher = [(b["figur_id"], b["rolle"]) for b in repo.besetzung(conn, zeile["id"])]
        rollen = dict(eintraege)
        zusammen = [(f, rollen.get(f) or r) for f, r in bisher] + [
            (f, r) for f, r in eintraege if f not in dict(bisher)]
        _schreibe_besetzung(conn, chat_id, zeile, zusammen, ", ".join(rest) or None,
                            "karte_aus_modell", {"szene": szene}, q,
                            T._GRUND_BESETZUNG.format(wer=karte["wer"]))
    zeile = _szene(conn, chat_id, szene)
    roh = stueck_sicht.roh_ohne_struktur(karte)
    punkte = []
    for p in roh.get("punkte") or []:
        treffer = stueck_sicht.OFFEN_PUNKT.match(p or "")
        if treffer:
            if not _frage_bekannt(conn, chat_id, zeile["id"], treffer.group(1)):
                repo.lege_offene_frage_an(conn, chat_id, zeile["id"], treffer.group(1), q,
                                          status="vertagt")
        else:
            punkte.append(p)
    roh["punkte"] = punkte
    for frage in karte.get("fragen") or []:
        frage_stellen(conn, chat_id, szene=szene, frage=frage, quelle=q)
    repo.setze_szenenkarte(conn, zeile["id"], json.dumps(roh, ensure_ascii=False))
    ansicht = karte_ansicht_von_id(conn, zeile["id"])
    repo.merke_karte_verlauf(conn, chat_id, zeile["id"],
                             json.dumps(ansicht, ensure_ascii=False), ausloeser, notiz)
    aid = _protokoll(conn, chat_id, "karte_aus_modell", {"szene": szene}, None, ansicht, q)
    return _ergebnis(aid)


def karte_ansicht_von_id(conn, szene_id: int) -> dict | None:
    """Lesehelfer, kein Werkzeug (nicht in ``WERKZEUGE``)."""
    zeile = repo.hole_szene(conn, szene_id)
    return karte(conn, zeile) if zeile is not None else None


# --- Texte -----------------------------------------------------------------

_WARNUNG_BESCHAEFTIGT = "Gerade wird noch geschrieben -- gleich nochmal."
_WARNUNG_UNBEKANNTE_FIGUR = "{name} ist noch keine Figur des Stücks."
_GRUND_RAHMEN = "neuer Rahmen"
_GRUND_ORT = "neuer Ort ({neu})"
_GRUND_BESETZUNG = "neue Besetzung ({wer})"
_GRUND_FIGUR_NEU = "neue Figur {name}"
_GRUND_FIGUR_WEG = "{name} spielt nicht mehr mit"
_GRUND_KARTE = "geänderte Karte ({felder})"
_GRUND_REIHENFOLGE = "neue Reihenfolge (jetzt Szene {nummer})"
_BEFUND_FEHLT = "Pflichtpunkt fehlt im Text: {stichwort}"
_WARNUNG_SCHON_BEANTWORTET = "Diese Frage ist schon geklärt."
_GRUND_FRAGE = "beantwortete Frage ({frage})"

from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)
