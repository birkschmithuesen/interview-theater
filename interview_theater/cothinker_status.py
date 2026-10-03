"""Die CoThinker-Statuszeile (Phase 4, nur Web, 03.10.2026): aus
vorhandenen Fakten abgeleitet, kein Modellaufruf, keine Datenbank -- reine
Funktion wie fehlstellen.aus_daten/roadmap.aus_daten.

Zustaende, erster Treffer gewinnt: denkt > transkribiert > hoert > schweigt
> kein Status. Siehe Plan docs/superpowers/plans/2026-10-03-cothinker-
statuszeile.md fuer die Herleitung der Schwellenwerte."""

from datetime import datetime, timezone

DENKT_TIMEOUT_S = 180
HOERT_FRISCH_S = 60

ZUSTAND_DENKT = "denkt"
ZUSTAND_TRANSKRIBIERT = "transkribiert"
ZUSTAND_HOERT = "hoert"
ZUSTAND_SCHWEIGT = "schweigt"

#: Zustaende, deren Dauer im Browser sekuendlich tickt -- nur diese
#: bekommen spaeter (anderer Task) die ``data-tickt``-Markierung im HTML.
TICKT = frozenset({ZUSTAND_DENKT, ZUSTAND_TRANSKRIBIERT, ZUSTAND_HOERT})


def _sekunden_her(jetzt: datetime, zeitpunkt: str | None) -> float | None:
    if not zeitpunkt:
        return None
    try:
        wert = datetime.fromisoformat(zeitpunkt)
    except ValueError:
        return None
    if wert.tzinfo is None:
        wert = wert.replace(tzinfo=timezone.utc)
    return (jetzt - wert).total_seconds()


def leite_ab(
    *,
    jetzt: datetime,
    lauf_seit: str | None,
    segment_status: str | None,
    segment_schnittgrund: str | None,
    segment_empfangen_am: str | None,
    neueste_karte_schweigen: bool,
    neueste_karte_seit: str | None,
) -> tuple[str, str] | None:
    """Liefert ``(zustand, seit)`` oder ``None`` (kein Status -- die Zeile
    wird dann gar nicht gerendert). ``segment_*`` beschreibt die JUENGSTE
    nicht entfernte Brainstorm-``aufnahme``-Zeile dieser Gruppe (oder
    durchgehend ``None``, wenn es noch keine gibt)."""
    lauf_alter = _sekunden_her(jetzt, lauf_seit)
    if lauf_seit and lauf_alter is not None and lauf_alter < DENKT_TIMEOUT_S:
        return ZUSTAND_DENKT, lauf_seit

    if segment_status in ("empfangen", "laeuft"):
        return ZUSTAND_TRANSKRIBIERT, segment_empfangen_am

    segment_alter = _sekunden_her(jetzt, segment_empfangen_am)
    if (
        segment_status == "fertig"
        and segment_schnittgrund != "ende"
        and segment_alter is not None
        and segment_alter < HOERT_FRISCH_S
    ):
        return ZUSTAND_HOERT, segment_empfangen_am

    if neueste_karte_schweigen:
        return ZUSTAND_SCHWEIGT, neueste_karte_seit

    return None
