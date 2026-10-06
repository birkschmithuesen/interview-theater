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


def zeile_ohne_kopf(zeile: str, begriffe: list[str]) -> tuple[str, str | None]:
    """(Frage ohne Begriffskopf, fremder Kopf oder ``None``) -- der
    zustandslose Teil von ``_cluster``s Kopf/Text-Trennung (ohne die
    Fortsetzungszeilen-/Zwischenueberschrift-Logik, die nur die GRUPPIERUNG
    betrifft, nicht den TEXT selbst). Oeffentlich fuer
    ``uebersetzung.segmente``: ein Hash je roher Zeile dort soll dieselbe
    Frage treffen, die das Dashboard am Ende zeigt. Der fremde Kopf kommt
    zweitens zurueck, wenn er KEIN Begriff der Gruppe ist (ein Ad-hoc-Thema
    der Fragengenerierung) -- er braucht dann selbst eine Uebersetzung."""
    from interview_theater.knoepfe.fragen import _teile_zeile

    begriff, frage = _teile_zeile(zeile, begriffe)
    if begriff is not None and frage:
        return frage, None
    fremd = _fremder_kopf(zeile)
    if fremd is not None and fremd[1]:
        return fremd[1], fremd[0]
    return zeile, None


def sortierung_offen(stand: Mapping | None) -> bool:
    """Die EINE Regel, ob die Gruppe gerade sortiert (Fix 05.10.2026): offen
    heisst ``fragen_entschieden IS NOT NULL`` (auch "" oder ",,") ODER
    ``fragen`` noch leer. ``_schliesse_fragen_ab`` setzt ``fragen`` und
    ``fragen_entschieden = NULL`` -- danach ist zu, bis eine neue Auswahl
    (oder ``scripts/padua_fragen_neu.py --apply``) ``fragen_entschieden``
    wieder auf einen leeren, aber nicht-NULL Wert setzt. Ohne Schemaaenderung.
    ``repo.setze_fragen_entscheidung`` prueft dieselbe Bedingung inline (die
    Ablage importiert keine Fachlogik)."""
    if stand is None:
        return True
    try:
        entschieden = stand["fragen_entschieden"]
    except (IndexError, KeyError):
        entschieden = None
    return entschieden is not None or not _feld(stand, "fragen").strip()


def _cluster(eintraege: list[dict], begriffe: list[str]) -> list[dict]:
    """Gruppiert ``eintraege`` (jeder mit einer rohen Zeile unter ``"text"``)
    nach Begriff -- Begriffe in ihrer Reihenfolge, danach Zeilen mit einem
    fremden Kopf (ein Begriff, den die Gruppe nicht oder nicht mehr hat) je
    Kopf, zuletzt die Zeilen ohne Kopf unter ``titel=""``. Leere Gruppen
    fallen weg. Erkennt einen Begriff, ersetzt ``"text"`` durch die reine
    Frage -- der genaue Abgleich aus ``knoepfe.fragen._teile_zeile``/
    ``_finde_begriff``, EINMAL, fuer jeden Aufrufer (``fragen_liste``,
    ``dashboard_fragen``)."""
    from interview_theater.knoepfe.fragen import _finde_begriff, _teile_zeile

    je_titel: dict[str, list[dict]] = {b: [] for b in begriffe}
    fremde: dict[str, list[dict]] = {}
    ohne: list[dict] = []
    aktuell: str | None = None  # Zwischenueberschrift (Zeile nur mit Begriff)
    for eintrag in eintraege:
        zeile = eintrag["text"]
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
    return gruppen


def fragen_liste(stand: Mapping | None) -> dict:
    """``{"gruppen": [{"titel", "eintraege": [{nummer, text, herkunft,
    zustand}]}], "zaehler": {ja, nein, schaerfen, offen}}``.

    Gruppen in der Reihenfolge der Begriffe; danach Zeilen mit einem
    fremden Kopf (ein Begriff, den die Gruppe nicht oder nicht mehr hat) je
    Kopf; zuletzt die Zeilen ohne Kopf unter ``titel=""``. Leere Gruppen
    fallen weg."""
    from interview_theater import begriffe as begriffe_modul
    from interview_theater import vorschlag

    zaehler = {"ja": 0, "nein": 0, "schaerfen": 0, "offen": 0}
    zeilen = vorschlag.zeilen(_feld(stand, "fragen_auswahl"))
    if not zeilen:
        return {"gruppen": [], "zaehler": zaehler}
    begriffe = begriffe_modul.zerlege(_feld(stand, "begriffe"))
    herkunft = _liste(_feld(stand, "fragen_herkunft"))
    entschieden = _liste(_feld(stand, "fragen_entschieden"))

    eintraege = []
    for nummer, zeile in enumerate(zeilen, start=1):
        zustand = entschieden[nummer - 1].strip() if nummer <= len(entschieden) else ""
        if zustand not in ZUSTAENDE:
            zustand = ""
        h = herkunft[nummer - 1].strip() if nummer <= len(herkunft) else ""
        zaehler[zustand or "offen"] += 1
        eintraege.append({"nummer": nummer, "text": zeile,
                           "herkunft": h if h in _HERKUENFTE else "", "zustand": zustand})

    return {"gruppen": _cluster(eintraege, begriffe), "zaehler": zaehler}


def dashboard_fragen(stand: Mapping | None) -> dict | None:
    """Fuers Regie-Dashboard (Fast-Track 06.10.2026): ALLE ausgewaehlten
    Fragen einer Gruppe, geclustert nach Begriff, numeriert wie im Chat, mit
    eigen/KI-Markierung -- ``None``, wenn es nichts zu zeigen gibt.

    ``{"offen": bool, "kept": int, "gruppen": [...]}`` -- ``gruppen`` wie
    ``fragen_liste`` (ohne ``zustand``, der ist hier immer "ja").

    Solange die Gruppe noch sortiert (``sortierung_offen``): die bereits
    behaltenen ("ja") Zeilen aus ``fragen_auswahl``, numeriert 1..k in
    genau der Reihenfolge, die die endgueltige Liste haben wird (dieselbe
    wie ``knoepfe.fragen._schliesse_fragen_ab``: die Reihenfolge der
    Auswahl selbst, nicht die der Begriffsgruppen). ``offen=True``.

    Danach: ``fragen`` selbst, 1..n, Herkunft aus ``fragen_herkunft_final``
    -- fehlt die (alte Runde vor dem A/B-Vergleich, oder ihre Laenge passt
    nicht mehr zu ``fragen``), wird je Zeile exakt gegen
    ``fragen_auswahl``/``fragen_herkunft`` abgeglichen. ``offen=False``."""
    from interview_theater import begriffe as begriffe_modul
    from interview_theater import vorschlag

    begriffe = begriffe_modul.zerlege(_feld(stand, "begriffe"))

    if sortierung_offen(stand):
        zeilen = vorschlag.zeilen(_feld(stand, "fragen_auswahl"))
        if not zeilen:
            return None
        herkunft = _liste(_feld(stand, "fragen_herkunft"))
        entschieden = _liste(_feld(stand, "fragen_entschieden"))
        eintraege = []
        for i, zeile in enumerate(zeilen):
            zustand = entschieden[i].strip() if i < len(entschieden) else ""
            if zustand != "ja":
                continue
            h = herkunft[i].strip() if i < len(herkunft) else ""
            eintraege.append({"text": zeile, "roh": zeile,
                               "herkunft": h if h in _HERKUENFTE else ""})
        for n, eintrag in enumerate(eintraege, start=1):
            eintrag["nummer"] = n
        if not eintraege and vorschlag.zeilen(_feld(stand, "fragen")):
            # Padua 06.10.2026 (Birk): eine Gruppe, die neu sortiert und noch
            # nichts behalten hat, zeigte im Regie-Dashboard GAR NICHTS --
            # bis zum ersten Haken steht die bisherige Liste da, markiert.
            vorher = _geschlossene_liste(stand, begriffe)
            if vorher:
                vorher.update({"offen": True, "kept": 0, "vorher": True})
                return vorher
        return {"offen": True, "kept": len(eintraege),
                "gruppen": _cluster(eintraege, begriffe)}

    return _geschlossene_liste(stand, begriffe)


def _geschlossene_liste(stand, begriffe) -> dict | None:
    """Die endgueltige Liste ``fragen``, 1..n, mit Herkunft (s. ``dashboard_fragen``)."""
    from interview_theater import vorschlag

    zeilen = vorschlag.zeilen(_feld(stand, "fragen"))
    if not zeilen:
        return None
    herkunft_final = _liste(_feld(stand, "fragen_herkunft_final"))
    if len(herkunft_final) != len(zeilen):
        auswahl_zeilen = vorschlag.zeilen(_feld(stand, "fragen_auswahl"))
        auswahl_herkunft = _liste(_feld(stand, "fragen_herkunft"))
        nachschlag = {
            z.strip(): (auswahl_herkunft[i].strip() if i < len(auswahl_herkunft) else "")
            for i, z in enumerate(auswahl_zeilen)
        }
        herkunft_final = [nachschlag.get(z.strip(), "") for z in zeilen]

    eintraege = []
    for n, zeile in enumerate(zeilen, start=1):
        h = herkunft_final[n - 1].strip() if n - 1 < len(herkunft_final) else ""
        eintraege.append({"nummer": n, "text": zeile, "roh": zeile,
                           "herkunft": h if h in _HERKUENFTE else ""})
    return {"offen": False, "kept": len(eintraege),
            "gruppen": _cluster(eintraege, begriffe)}
