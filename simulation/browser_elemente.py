"""Was die Persona auf einem Bildschirm sieht (Padua-Browser-UX-Simulation,
2026-10-03): ein Screenshot plus eine strukturierte Liste der sichtbaren
Bedienelemente -- ueber Rolle, Text und ``data-*`` identifiziert, nicht
ueber Gestaltungsklassen. Ein spaeteres Redesign darf die CSS-Klassen
tauschen, ohne dass die Persona blind wird (AGENTS.md-Auftrag der Karte:
"Elemente ueber Rolle/Text/data-* finden").
"""

from __future__ import annotations

#: Je Elementart ein Selektor -- eine Allowlist bekannter Stellen, wie
#: ``browser_zaehler.VERDRAHTETE_SELEKTOREN``. Ein neues UI-Stueck wird hier
#: eingetragen, nicht erraten.
_ARTEN = (
    ("chip", ".leiste button"),
    ("tab", ".tabs button"),
    ("roadmap_oeffnen", ".roadmap summary"),
    ("phase", ".phase-knopf"),
    ("phase_abbrechen", ".phase-abbrechen"),
    ("aufgabe", ".roadmap li.aufgabe"),
    ("senden", "#senden"),
    ("eingabe", "#eingabe"),
    ("interview", "#interview"),
    ("interview_pause", "#interview-pause"),
    ("interview_beenden", "#interview-beenden"),
    ("brainstorm", "#brainstorm"),
    ("brainstorm_pause", "#brainstorm-pause"),
    ("brainstorm_beenden", "#brainstorm-beenden"),
    ("ptt", "#ptt"),
    ("nachreichen", "#nachreichen"),
    ("verwerfen", "#verwerfen"),
    ("link", "a[href]"),
)

_DATEN_JS = (
    "e => ({tab: e.dataset.tab, phase: e.dataset.phase, "
    "message: e.dataset.message, daten: e.dataset.daten, "
    "zielTab: e.dataset.zielTab, zielFeld: e.dataset.zielFeld, "
    "sicher: e.dataset.sicher, bereit: e.dataset.bereit, "
    "fehlt: e.dataset.fehlt, placeholder: e.placeholder || null, "
    "value: (e.value !== undefined ? e.value : null), "
    "haelt: e.dataset.haelt})"
)

def extrahiere(page) -> list[dict]:
    """Sichtbare Bedienelemente als Liste von Dicts.

    Sichtbarkeit prueft Playwrights eigenes ``ElementHandle.is_visible()`` --
    es liefert ``False`` fuer den Inhalt eines geschlossenen ``<details>``
    (genau da liegen die Roadmap-Phasenknoepfe, bis jemand auf die
    ``<summary>`` klickt -- die selbst, per Spezifikation, nie darunter
    faellt und immer sichtbar bleibt) und ebenso fuer ``hidden``,
    ``display:none`` und ``visibility:hidden``. Ein eigener
    ``offsetParent !== null``-Test saehe denselben geschlossenen
    ``<details>``-Inhalt faelschlich als sichtbar an (die Box hat dort kein
    Layout, aber ``offsetParent`` fragt danach nicht) und liesse
    ``visibility:hidden`` ebenfalls durch -- deshalb ``is_visible()``, nicht
    eine eigene Heuristik.

    ``id`` ist die laufende Nummer innerhalb DIESES Aufrufs -- stabil genug,
    dass eine Persona-Antwort sie in derselben Antwort referenzieren kann,
    aber nicht ueber einen Schritt hinaus (bei jedem Schritt wird neu
    extrahiert, die DOM kann sich veraendert haben).

    Keine Dopplungs-Pruefung: kein Selektor in ``_ARTEN`` ueberschneidet sich
    mit einem anderen, also trifft niemals derselbe DOM-Knoten auf zwei
    Eintraege."""
    elemente: list[dict] = []
    for art, selektor in _ARTEN:
        for handle in page.query_selector_all(selektor):
            if not handle.is_visible():
                continue
            eintrag = {
                "id": len(elemente),
                "art": art,
                "text": (handle.text_content() or "").strip(),
            }
            daten = handle.evaluate(_DATEN_JS)
            eintrag.update({k: v for k, v in daten.items() if v not in (None, "")})
            elemente.append(eintrag)
    return elemente


def bildschirmfoto(page) -> bytes:
    return page.screenshot()
