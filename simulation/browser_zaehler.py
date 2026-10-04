"""Mechanische UX-Zaehler fuer den Browserlauf (Padua-UX-Simulation,
2026-10-03): reine Funktionen ueber eine Playwright-``Page`` (oder, wo es
reicht, ueber reinen Text) -- kein Modellaufruf, kein Netz. Sie ergaenzen
den Opus-Richter (``browser_judge.py``): was sich zaehlen laesst, zaehlt
der Code; was Urteil braucht, liest der Richter.
"""

from __future__ import annotations

#: Telefon-Tastatur: unter diesem Wert gilt ein Eingabefeld als Zoom-Falle
#: (iOS zoomt beim Fokussieren eines Feldes mit kleinerer Schrift) --
#: dieselbe Zahl wie in ``participatory-bot-ux`` Abschnitt 7 ("inputs >=16px").
MIN_SCHRIFT_PX = 16.0

#: WCAG-Tastenmass: unter diesem Wert in Pixel gilt ein Tippziel als zu klein.
MIN_TAPZIEL_PX = 44.0

#: Bekannte, mit einem Klick-Handler verdrahtete Stellen -- ueber ID/Rolle/
#: data-* identifiziert, NICHT ueber eine Gestaltungsklasse. Diese Liste
#: darf wachsen, wenn ein neues UI-Stueck dazukommt.
VERDRAHTETE_SELEKTOREN = (
    "#senden", "#interview", "#interview-pause", "#interview-beenden",
    "#brainstorm", "#brainstorm-pause", "#brainstorm-beenden", "#ptt",
    "#nachreichen", "#verwerfen", "#diskussion", "#diskussion-pause",
    "#diskussion-beenden", "#kalibrierung-start", "#kalibrierung-sprechen",
    "#kalibrierung-ja", "#kalibrierung-nein", "#kalibrierung-versuch",
    "#kalibrierung-weiter-trotzdem", "#kalibrierung-nochmal-hoeren",
    "#kalibrierung-skip", ".leiste button", ".tabs button",
    ".phase-knopf", ".phase-abbrechen", ".roadmap li.aufgabe", "a[href]",
)


def seitliches_rutschen(page) -> bool:
    """Liegt der Inhalt breiter als der Viewport (horizontales Scrollen)?"""
    return bool(page.evaluate(
        "document.documentElement.scrollWidth > window.innerWidth + 1"
    ))


def tap_ziele_zu_klein(page, selektor: str = (
        ".leiste button, .tabs button, .phase-knopf, #senden, #interview, "
        "#ptt, #brainstorm")) -> list[dict]:
    """Sichtbare Tippziele unter ``MIN_TAPZIEL_PX``."""
    treffer = []
    for el in page.query_selector_all(selektor):
        if not el.is_visible():
            continue
        box = el.bounding_box()
        if box is None:
            continue
        if box["width"] < MIN_TAPZIEL_PX or box["height"] < MIN_TAPZIEL_PX:
            treffer.append({
                "text": (el.text_content() or "").strip(),
                "breite": box["width"], "hoehe": box["height"],
            })
    return treffer


def eingabefeld_schrift_zu_klein(page, selektor: str = "#eingabe, input, textarea") -> list[dict]:
    treffer = []
    for el in page.query_selector_all(selektor):
        if not el.is_visible():
            continue
        px = el.evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
        if px and px < MIN_SCHRIFT_PX:
            treffer.append({"schrift_px": px})
    return treffer


def mehrere_fragen_pro_nachricht(page, selektor: str = ".blase.bot") -> list[dict]:
    """Mehr als ein Fragezeichen in einer Bot-Nachricht."""
    treffer = []
    for el in page.query_selector_all(selektor):
        text = el.text_content() or ""
        anzahl = text.count("?")
        if anzahl > 1:
            treffer.append({"text": text.strip()[:200], "fragen": anzahl})
    return treffer


def knoepfe_ohne_wirkung(page, selektor: str = "button") -> list[dict]:
    """Ein sichtbarer, aktiver Knopf, der weder einen ``fetch``-Aufruf noch
    eine DOM-Aenderung ausloest -- ``installiere_messung`` muss vorher auf
    dem ``context`` gelaufen sein, sonst bleibt ``window.__fetchZaehler``
    undefiniert und der fetch-Teil des Vergleichs greift nicht."""
    treffer = []
    for el in page.query_selector_all(selektor):
        if not el.is_visible() or el.is_disabled():
            continue
        vorher_fetch = page.evaluate("window.__fetchZaehler || 0")
        vorher_html = page.evaluate("document.body.innerHTML.length")
        try:
            el.click(timeout=1000)
        except Exception:
            continue
        page.wait_for_timeout(300)
        nachher_fetch = page.evaluate("window.__fetchZaehler || 0")
        nachher_html = page.evaluate("document.body.innerHTML.length")
        if nachher_fetch == vorher_fetch and nachher_html == vorher_html:
            treffer.append({"text": (el.text_content() or "").strip()})
    return treffer


def installiere_messung(context) -> None:
    """Zaehlt ``fetch``-Aufrufe in ``window.__fetchZaehler`` -- fuer
    ``knoepfe_ohne_wirkung``. Muss auf dem ``context`` laufen, BEVOR eine
    Seite geladen wird (``context.add_init_script``), damit es auf jedem
    neuen Dokument steht."""
    context.add_init_script(
        "window.__fetchZaehler = 0; var __echtesFetch = window.fetch;"
        "window.fetch = function () { window.__fetchZaehler++; "
        "return __echtesFetch.apply(this, arguments); };"
    )


def alle(page) -> dict:
    """Alle Zaehler in einem Durchlauf -- fuer den Mitschnitt je Schritt."""
    return {
        "seitliches_rutschen": seitliches_rutschen(page),
        "tap_ziele_zu_klein": tap_ziele_zu_klein(page),
        "eingabefeld_schrift_zu_klein": eingabefeld_schrift_zu_klein(page),
        "mehrere_fragen_pro_nachricht": mehrere_fragen_pro_nachricht(page),
    }


# -- reine Funktionen ohne Browser -------------------------------------------


def bot_text_waehrend_zuhoermodus(modus: str, neue_bot_nachrichten: list[str]) -> bool:
    """Schreibt der Bot im Brainstorm-/Zuhoermodus trotzdem in den Chat?
    (``ux_rubrik.md`` Abschnitt 4: "the bot writes NOTHING in the chat")."""
    return modus == "brainstorm" and any(t.strip() for t in neue_bot_nachrichten)
