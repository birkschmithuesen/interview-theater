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

#: Playwrights eigenes ``is_visible()`` rechnet den Inhalt eines
#: geschlossenen ``<details>`` als unsichtbar (die Box hat dort eine
#: Ausdehnung von 0x0, gemessen) -- die Roadmap-Phasenknoepfe liegen aber
#: genau dort, bevor jemand auf die Zusammenfassung klickt. ``offsetParent``
#: unterscheidet das korrekt von einem expliziten ``hidden``-Attribut oder
#: einem ``display:none``-Vorfahren (beide liefern ``null``), ohne sich von
#: der Groesse der Box taeuschen zu lassen.
_SICHTBAR_JS = "e => e.offsetParent !== null"


def extrahiere(page) -> list[dict]:
    """Sichtbare Bedienelemente als Liste von Dicts.

    ``id`` ist die laufende Nummer innerhalb DIESES Aufrufs -- stabil genug,
    dass eine Persona-Antwort sie in derselben Antwort referenzieren kann,
    aber nicht ueber einen Schritt hinaus (bei jedem Schritt wird neu
    extrahiert, die DOM kann sich veraendert haben)."""
    elemente: list[dict] = []
    gesehen: set[int] = set()
    for art, selektor in _ARTEN:
        for handle in page.query_selector_all(selektor):
            if not handle.evaluate(_SICHTBAR_JS):
                continue
            schluessel = id(handle)
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
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
