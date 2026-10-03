"""Die Auswertung eigene-vs-KI-Fragen (Aufgabe 14, 03.10.2026): wie viele der
final uebernommenen Interviewfragen stammen von der Gruppe selbst, wie viele
von der KI.

**Warum es das gibt.** Aufgabe 13 baut beim Abschluss von Phase 2
(``knoepfe.fragen._schliesse_fragen_ab``) zwei Felder im selben Durchgang:
``arbeitsstand.fragen`` (die final angenommenen Fragezeilen, eine je Zeile)
und ``arbeitsstand.fragen_herkunft_final`` (komma-getrennt ``eigen``/``ki``/
leer, index- und laengengleich zu ``fragen`` -- eine garantierte, getestete
Invariante aus Aufgabe 13). Dieses Modul liest die beiden Felder und zaehlt
nach, ohne selbst etwas zu schreiben oder ein Modell zu rufen.

**Reine Leseabfrage, kein Modellaufruf** -- dasselbe Muster wie
``fehlstellen.py`` und ``roadmap.py``: ``aus_daten`` ist rein und kennt nur
zwei Strings (oder ``None``), ``auswertung`` holt sie ueber ``repo`` (Bot).
``web_daten.py`` ruft ``aus_daten`` direkt mit den Feldern aus seiner
read-only gelesenen ``arbeitsstand``-Zeile -- der Webserver bekommt dadurch
keinen ``repo``-Pfad.

**Ohne A/B-Vergleich ist das Ergebnis deterministisch leer, nicht ein
Fehler.** Lief der A/B-Vergleich nie fuer diese Gruppe (``workshop.
fragen_ab_aktiv()`` aus -- heute jedes Profil ausser Padua -- oder eine
Padua-Gruppe, die den klassischen Weg nahm), ist ``fragen_herkunft_final``
entweder ``None``/leer oder eine Kette aus leeren Eintraegen. Beides zaehlt
als "der A/B-Vergleich lief fuer diese Frage nicht" -- eine Zeile wird dann
weder ``eigen`` noch ``ki`` zugerechnet, es gibt keine dritte Kategorie."""

from interview_theater import vorschlag


def aus_daten(fragen: str | None, fragen_herkunft_final: str | None) -> dict:
    """Zaehlt ``eigen``/``ki`` unter den final uebernommenen Fragen.

    ``fragen`` ist ``arbeitsstand.fragen`` (eine Frage je Zeile, wie sie
    ``_schliesse_fragen_ab`` ablegt), ``fragen_herkunft_final`` die
    komma-getrennte Herkunftskette derselben Laenge und Indexreihenfolge.

    Rueckgabe, immer in dieser Form (dokumentiert, weil sowohl der Chattext
    als auch das Dashboard und die Gruppenseite daraus lesen)::

        {
            "gesamt": {"eigen": <int>, "ki": <int>},
            "je_begriff": {
                "<Begriff>": {"eigen": <int>, "ki": <int>},
                ...
            },
        }

    Eine Zeile zaehlt mit, wenn ihr Herkunftseintrag ``eigen`` oder ``ki``
    ist. Ein leerer, fehlender oder ausserhalb der Kette liegender Eintrag
    zaehlt **nirgends** mit -- das ist der Fall "der A/B-Vergleich lief fuer
    diese Frage nicht", keine dritte Kategorie. Eine zaehlende Zeile ohne
    erkennbares ``Begriff:``-Praefix (dieselbe Pruefung wie in
    ``knoepfe.fragen.fragenliste``: ein nicht-leerer Begriff bis 30 Zeichen,
    ein nicht-leerer Rest) geht in ``gesamt``, aber in kein
    ``je_begriff``-Fach.

    Ohne Herkunftsdaten (``fragen_herkunft_final`` ``None``/leer -- der
    klassische Ablauf ohne A/B-Vergleich) ist das Ergebnis deterministisch
    ``{"gesamt": {"eigen": 0, "ki": 0}, "je_begriff": {}}``, nie eine
    Ausnahme."""
    zeilen = vorschlag.zeilen(fragen or "")
    herkunft = (fragen_herkunft_final or "").split(",") if fragen_herkunft_final else []

    gesamt = {"eigen": 0, "ki": 0}
    je_begriff: dict[str, dict[str, int]] = {}

    for i, zeile in enumerate(zeilen):
        wert = herkunft[i] if i < len(herkunft) else ""
        if wert not in ("eigen", "ki"):
            continue
        gesamt[wert] += 1
        begriff, trenner, rest = zeile.partition(":")
        if trenner and 0 < len(begriff.strip()) <= 30 and rest.strip():
            name = begriff.strip()
            eintrag = je_begriff.setdefault(name, {"eigen": 0, "ki": 0})
            eintrag[wert] += 1

    return {"gesamt": gesamt, "je_begriff": je_begriff}


def auswertung(conn, chat_id: int) -> dict:
    """Der Weg des Bots: holt ``fragen``/``fragen_herkunft_final`` ueber
    ``repo`` und zaehlt mit ``aus_daten``.

    Eine frische Gruppe ohne ``arbeitsstand``-Zeile (``repo.hole_arbeitsstand``
    liefert dann ``None``) ergibt dasselbe leere Ergebnis wie eine Gruppe ohne
    A/B-Vergleich -- kein Sonderfall, keine Ausnahme."""
    from interview_theater import repo

    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        fragen = stand["fragen"] if stand is not None else None
    except (IndexError, KeyError):
        fragen = None
    try:
        herkunft_final = stand["fragen_herkunft_final"] if stand is not None else None
    except (IndexError, KeyError):
        herkunft_final = None
    return aus_daten(fragen, herkunft_final)
