"""Fuehrt eine Persona-Aktion auf der Seite aus und wartet, bis die
Bot-Antwort fertig ist (Padua-UX-Simulation, 2026-10-03)."""

from __future__ import annotations

import time

#: Wie lange hoechstens auf das Ende einer Bot-Antwort gewartet wird.
ANTWORT_GEDULD_S = 90.0

#: Ab wann eine Wartezeit ganz ohne sichtbare Aktivitaet (kein Tippen, keine
#: vorlaeufige Blase) als "nichts zu erwarten" gilt und der naechste Schritt
#: sofort weiterlaeuft -- die meisten Aktionen (Tab-Wechsel, Phasenklick)
#: loesen gar keinen Modellaufruf aus.
_ANLAUF_S = 3.0

#: Ab wann eine laufende Wartezeit ohne sichtbaren Hinweis als Befund zaehlt
#: (``ux_rubrik.md``-Checkliste, "Wartezeit > 20 s ohne sichtbaren Hinweis").
WARTEZEIT_OHNE_HINWEIS_S = 20.0


class UnbekannteAktion(Exception):
    pass


def fuehre_aus(page, aktion: dict) -> dict:
    """Fuehrt genau eine Aktion aus. Liefert ein Protokoll-Dict."""
    art = aktion.get("type")
    if art == "wait":
        page.wait_for_timeout(int(aktion.get("duration_ms") or 1000))
        return {"art": "wait"}
    if art == "click":
        el = _element(page, aktion)
        el.click(timeout=5000)
        return {"art": "click", "ziel": aktion.get("element_id")}
    if art == "type_send":
        page.fill("#eingabe", aktion.get("text", ""))
        page.click("#senden")
        return {"art": "type_send", "text": aktion.get("text", "")}
    if art == "tab":
        page.click(f'.tabs button[data-tab="{aktion["name"]}"]')
        return {"art": "tab", "ziel": aktion["name"]}
    if art == "phase":
        selektor = f'.phase-knopf[data-phase="{aktion["nummer"]}"]'
        # Die Roadmap ist auf der echten Seite per Vorgabe geschlossen
        # (``<details class="roadmap">`` ohne ``open`` --
        # ``web_vereint._leiste_html``); ihr Inhalt ist dann nicht sichtbar
        # und ein Klick darauf liefe in einen Timeout. Ein Phasenwechsel ist
        # eine eigene, bewusste Handlung -- sie oeffnet die Roadmap selbst,
        # statt vorher auf einen Klick auf ``summary`` zu warten.
        page.eval_on_selector(
            selektor, "el => { var d = el.closest('details'); "
            "if (d) { d.open = true; } }"
        )
        page.click(selektor)
        page.wait_for_timeout(300)
        # Nach vorn mit fehlender Voraussetzung bewaffnet der erste Klick
        # nur die Rueckfrage (data-sicher=1) -- ein zweiter Klick bestaetigt,
        # genau wie bei einer echten Gruppe (web_vereint._VEREINT_JS,
        # "bewaffne"/"springe").
        if page.locator(selektor).get_attribute("data-sicher") == "1":
            page.click(selektor)
        return {"art": "phase", "ziel": aktion["nummer"]}
    if art == "ptt":
        # Ton ist in dieser Kartenversion ausgespart (siehe Bericht,
        # "Real-Test Birk") -- die Aktion wird protokolliert, aber nicht
        # ausgefuehrt.
        return {"art": "ptt", "ausgefuehrt": False}
    if art == "done_phase":
        return {"art": "done_phase"}
    raise UnbekannteAktion(f"unbekannte Aktion: {art!r}")


def _element(page, aktion: dict):
    text = aktion.get("text")
    if text:
        return page.get_by_text(text, exact=True).first
    return page.locator(aktion.get("selektor") or "button, a, input").first


def laeuft_sichtbar(page) -> bool:
    """Laeuft der Bot gerade sichtbar (Tippanzeige oder vorlaeufige Blase)?"""
    return bool(page.evaluate(
        "() => { var t = document.getElementById('tippt'); "
        "var vl = document.querySelector('.blase.vorlaeufig'); "
        "return !!(t && t.textContent) || !!vl; }"
    ))


def warte_auf_antwort(page, geduld_s: float = ANTWORT_GEDULD_S,
                      anlauf_s: float = _ANLAUF_S) -> dict:
    """Wartet, bis der Bot sichtbar fertig ist.

    Zeigt sich binnen ``anlauf_s`` nichts, war die letzte Aktion vermutlich
    eine, die keinen Modellaufruf ausloest (Tab-/Phasenwechsel) -- sofort
    weiter. Zeigt sich etwas, wird gewartet, bis es wieder verschwindet,
    hoechstens ``geduld_s``."""
    start = time.monotonic()
    sah_aktivitaet = False
    while time.monotonic() - start < geduld_s:
        aktiv = laeuft_sichtbar(page)
        if aktiv:
            sah_aktivitaet = True
        elif sah_aktivitaet:
            dauer = time.monotonic() - start
            return {"fertig": True, "sekunden": dauer,
                    "ohne_hinweis": False}
        elif time.monotonic() - start > anlauf_s:
            dauer = time.monotonic() - start
            return {"fertig": True, "sekunden": dauer, "ohne_hinweis": False}
        page.wait_for_timeout(300)
    dauer = time.monotonic() - start
    # Das Budget ist abgelaufen -- ob der Bot *jetzt* noch sichtbar
    # arbeitet, entscheidet ``fertig``, nicht ob er es irgendwann im
    # Verlauf getan hat (``sah_aktivitaet``): sonst meldet ein Lauf, der
    # wegen Zeitablauf aufgibt, faelschlich "fertig".
    return {"fertig": not laeuft_sichtbar(page), "sekunden": dauer,
            "ohne_hinweis": dauer > WARTEZEIT_OHNE_HINWEIS_S and not sah_aktivitaet}
