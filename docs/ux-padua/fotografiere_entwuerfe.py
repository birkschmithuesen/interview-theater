#!/usr/bin/env python3
"""Handy- und Laptop-Screenshots der beiden Stil-Entwuerfe (Karte t_5ad6ac77).

Kein Test, laeuft nie automatisch, kostet nichts -- braucht aber Playwright
aus dem Wegwerf-venv (siehe ``tests/e2e/README.md``):

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python \
        docs/ux-padua/fotografiere_entwuerfe.py

Geoeffnet wird ueber ``file://`` -- die Entwuerfe sind selbststaendige
Dateien ohne Fremdquelle, es braucht keinen Server. Die Zustaende, die
fotografiert werden, stellt der Entwurf selbst ueber ``?halt=…`` ein
(``strom`` haelt den Textaufbau bei 55 %, ``aufnahme`` setzt den
Interviewknopf auf "laeuft"); so ist jedes Bild reproduzierbar und nicht
vom Zufall eines Zeitgebers abhaengig.
"""

import pathlib
import sys

from playwright.sync_api import sync_playwright

HIER = pathlib.Path(__file__).resolve().parent
HANDY = {"width": 390, "height": 844}
LAPTOP = {"width": 1366, "height": 900}

#: Name -> (Entwurf, Query, Viewport, Fragment, Wartezeit in ms)
BILDER = (
    ("entwurf-a-handy-chat.png", "a", "?halt=strom", HANDY, "", 900),
    ("entwurf-a-handy-aufnahme.png", "a", "?halt=aufnahme", HANDY, "", 1400),
    ("entwurf-a-handy-akte.png", "a", "?halt=belohnung", HANDY, "", 600),
    ("entwurf-a-handy-textbuch.png", "a", "", HANDY, "#textbuch", 600),
    ("entwurf-a-laptop-chat.png", "a", "?halt=strom", LAPTOP, "", 900),
    ("entwurf-b-handy-chat.png", "b", "?halt=strom", HANDY, "", 900),
    ("entwurf-b-handy-aufnahme.png", "b", "?halt=aufnahme", HANDY, "", 1400),
    ("entwurf-b-handy-akte.png", "b", "?halt=belohnung", HANDY, "", 600),
    ("entwurf-b-handy-textbuch.png", "b", "", HANDY, "#textbuch", 600),
    ("entwurf-b-laptop-chat.png", "b", "?halt=strom", LAPTOP, "", 900),
)

#: Bilder, bei denen die Aktleiste aufgeklappt sein soll (die Roadmap ist
#: zugeklappt EINE Zeile -- aufgeklappt will Birk sie trotzdem sehen).
AUFGEKLAPPT = {"entwurf-a-handy-akte.png", "entwurf-b-handy-akte.png"}


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, entwurf, query, viewport, fragment, warten in BILDER:
            datei = HIER / f"entwurf-{entwurf}.html"
            seite = browser.new_page(viewport=viewport)
            seite.goto(f"file://{datei}{query}{fragment}")
            if name in AUFGEKLAPPT:
                seite.eval_on_selector("#roadmap", "el => el.open = true")
            seite.wait_for_timeout(warten)
            seite.screenshot(path=str(HIER / name))
            print(name)
            seite.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
