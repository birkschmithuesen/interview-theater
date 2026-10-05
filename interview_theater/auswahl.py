"""Die Sortierliste der Phase-2-Fragen (Padua, 05.10.2026): die Fragen der
laufenden Auswahl (``arbeitsstand.fragen_auswahl``) je Begriff, mit Herkunft
(eigen/KI) und Zustand (``fragen_entschieden``) -- dieselben Daten, die der
Chat Karte fuer Karte durchgeht, hier auf einmal, fuer den CoThinker und fuer
"show all" im Chat.

Rein, kein SQL, kein Modellaufruf. ``nummer`` ist 1-basiert und genau die
Zeile in ``vorschlag.zeilen(fragen_auswahl)`` -- dieselbe Zaehlung wie
``knoepfe.fragen._auswahlfragen`` und ``repo.setze_fragen_entscheidung``.
Eine Zeile wird deshalb nie geteilt oder zusammengelegt.

Der Begriffsabgleich ist der aus ``knoepfe.fragen._teile_zeile`` (laengster
Begriffskopf gewinnt, tolerant gegenueber Zierde und Anfuehrungszeichen);
``knoepfe`` ist Oberflaeche, deshalb ein lokaler Import in der Funktion
(AGENTS.md, Modulkarte).
"""

from collections.abc import Mapping

#: Die Werte einer Position in ``fragen_entschieden``; "" heisst offen.
ZUSTAENDE = ("ja", "nein", "schaerfen", "")

_HERKUENFTE = ("eigen", "ki")


def _feld(stand: Mapping | None, name: str) -> str:
    if stand is None:
        return ""
    try:
        return stand[name] or ""
    except (IndexError, KeyError):
        return ""


def _liste(roh: str) -> list[str]:
    return roh.split(",") if roh else []


def _fremder_kopf(zeile: str) -> tuple[str, str] | None:
    """("kopf", "frage") einer Zeile mit kurzem Kopf, der kein Begriff der
    Gruppe ist ("ricordi personali: ..."), sonst None -- dieselbe Grenze wie
    ``knoepfe.fragen._hat_fremden_kopf``."""
    from interview_theater.knoepfe.fragen import _hat_fremden_kopf

    if not _hat_fremden_kopf(zeile):
        return None
    kopf, _, rest = zeile.partition(":")
    return kopf.strip(" *_"), rest.lstrip(" *_").strip()


def fragen_liste(stand: Mapping | None) -> dict:
    """``{"gruppen": [{"titel", "eintraege": [{nummer, text, herkunft,
    zustand}]}], "zaehler": {ja, nein, schaerfen, offen}}``.

    Gruppen in der Reihenfolge der Begriffe; danach Zeilen mit einem
    fremden Kopf (ein Begriff, den die Gruppe nicht oder nicht mehr hat) je
    Kopf; zuletzt die Zeilen ohne Kopf unter ``titel=""``. Leere Gruppen
    fallen weg."""
    from interview_theater import begriffe as begriffe_modul
    from interview_theater import vorschlag
    from interview_theater.knoepfe.fragen import _finde_begriff, _teile_zeile

    zaehler = {"ja": 0, "nein": 0, "schaerfen": 0, "offen": 0}
    zeilen = vorschlag.zeilen(_feld(stand, "fragen_auswahl"))
    if not zeilen:
        return {"gruppen": [], "zaehler": zaehler}
    begriffe = begriffe_modul.zerlege(_feld(stand, "begriffe"))
    herkunft = _liste(_feld(stand, "fragen_herkunft"))
    entschieden = _liste(_feld(stand, "fragen_entschieden"))

    je_titel: dict[str, list[dict]] = {b: [] for b in begriffe}
    fremde: dict[str, list[dict]] = {}
    ohne: list[dict] = []
    aktuell: str | None = None  # Zwischenueberschrift (Zeile nur mit Begriff)
    for nummer, zeile in enumerate(zeilen, start=1):
        zustand = entschieden[nummer - 1].strip() if nummer <= len(entschieden) else ""
        if zustand not in ZUSTAENDE:
            zustand = ""
        h = herkunft[nummer - 1].strip() if nummer <= len(herkunft) else ""
        eintrag = {"nummer": nummer, "text": zeile,
                   "herkunft": h if h in _HERKUENFTE else "", "zustand": zustand}
        zaehler[zustand or "offen"] += 1

        begriff, frage = _teile_zeile(zeile, begriffe)
        if begriff is not None and frage:
            eintrag["text"] = frage
            je_titel[begriff].append(eintrag)
            aktuell = None
            continue
        kopfbegriff = _finde_begriff(zeile, begriffe)
        if kopfbegriff is not None:
            aktuell = kopfbegriff
            je_titel[kopfbegriff].append(eintrag)
            continue
        fremd = _fremder_kopf(zeile)
        if fremd is not None and fremd[1]:
            eintrag["text"] = fremd[1]
            fremde.setdefault(fremd[0], []).append(eintrag)
            aktuell = None
        elif aktuell is not None:
            je_titel[aktuell].append(eintrag)
        else:
            ohne.append(eintrag)

    gruppen = [{"titel": t, "eintraege": e} for t, e in je_titel.items() if e]
    gruppen += [{"titel": t, "eintraege": e} for t, e in fremde.items()]
    if ohne:
        gruppen.append({"titel": "", "eintraege": ohne})
    return {"gruppen": gruppen, "zaehler": zaehler}
