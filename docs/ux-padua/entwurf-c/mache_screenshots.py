#!/usr/bin/env python3
"""Vergleichs-Screenshots Entwurf b (Vorgabe) vs. c (dunkel-violett/Salbei),
Karte t_1599392a (05.10.2026).

Kein Test, laeuft nie automatisch, aendert keine Betriebsdaten: eine
Wegwerf-Datenbank unter ``/tmp``, ein echter Webserver **im selben
Prozess** (``interview_theater.web.baue_server``, Port 0), damit
``IT_UX_ENTWURF`` zwischen den beiden Bildserien ohne Neustart umschaltet
(``web_gestalt.entwurf()`` liest die Umgebungsvariable bei jedem Aufruf neu).

Alle Inhalte (Begriffe, Chatzeilen) sind frei erfunden -- keine echten
Namen, keine Sitzungsdaten, kein Token/keine URL im Bild (Viewport-
Screenshot, keine Adressleiste).

Aufruf (Playwright aus dem Wegwerf-venv, siehe ``tests/e2e/README.md``)::

    python3.11 docs/ux-padua/entwurf-c/mache_screenshots.py
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
WURZEL = HIER.parent.parent.parent
sys.path.insert(0, str(WURZEL))

DB_PFAD = "/tmp/it-entwurf-c-screenshots.db"
CHAT_P1 = 7_000_000_000_911
CHAT_P2 = 7_000_000_000_912

HANDY = {"width": 390, "height": 844}
LAPTOP = {"width": 1366, "height": 900}

os.environ.setdefault("IT_WORKSHOP", "padua-2026")
os.environ.setdefault("IT_DB", DB_PFAD)

from interview_theater import db, repo, web, web_gestalt  # noqa: E402

BEGRIFFE = [
    {"begriff": "Ankommen", "status": "aktiv", "zustimmung": 1, "nennungen": 3},
    {"begriff": "Nachtschicht", "status": "aktiv", "zustimmung": 1, "nennungen": 2},
    {"begriff": "Koffer", "status": "aktiv", "zustimmung": 0, "nennungen": 1},
    {"begriff": "Warten", "status": "aktiv", "zustimmung": 1, "nennungen": 2,
     "vorgaenger": ["Stillstand"]},
    {"begriff": "Heimweh", "status": "aktiv", "zustimmung": 0, "nennungen": 1},
    {"begriff": "Laerm", "status": "verworfen", "zustimmung": 0, "nennungen": 1},
]


def _baue_datenbank() -> tuple[str, str]:
    for endung in ("", "-wal", "-shm"):
        Path(DB_PFAD + endung).unlink(missing_ok=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)

    repo.sichere_gruppe(conn, CHAT_P1, "demobot", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT_P1, "web")
    repo.setze_phase(conn, CHAT_P1, 1)
    repo.merke_nachricht(
        conn, CHAT_P1, 1, "demobot", 1, "text",
        "Willkommen! Sammelt erstmal frei Begriffe zu eurem Thema -- "
        "ich hoere im Hintergrund mit und baue daraus ein Begriffsboard.",
        repo._jetzt(),
    )
    repo.merke_nachricht(
        conn, CHAT_P1, 2, "Rosa", 0, "text",
        "Ankommen in einer neuen Stadt, mitten in der Nacht.",
        repo._jetzt(),
    )
    repo.merke_nachricht(
        conn, CHAT_P1, 3, "Jonas", 0, "text",
        "Und dieses Gefuehl, den Koffer nicht wiederzufinden.",
        repo._jetzt(),
    )
    repo.lege_begriffsboard_an(conn, CHAT_P1, json.dumps(BEGRIFFE), "demo", 0)
    token_p1 = repo.stelle_web_token_sicher(conn, CHAT_P1)

    repo.sichere_gruppe(conn, CHAT_P2, "demobot", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT_P2, "web")
    repo.setze_arbeitsstand(conn, CHAT_P2, "begriffe", "Ankommen, Nachtschicht, Koffer, Warten")
    repo.setze_phase(conn, CHAT_P2, 2)
    repo.merke_nachricht(
        conn, CHAT_P2, 1, "demobot", 1, "text",
        "Aus euren Begriffen moegliche Fragen fuer das Interview -- "
        "waehlt drei davon aus, die euch am meisten interessieren.",
        repo._jetzt(),
    )
    repo.merke_nachricht(
        conn, CHAT_P2, 2, "Rosa", 0, "text",
        "Mir gefaellt die Frage nach dem ersten Moment in der neuen Stadt.",
        repo._jetzt(),
    )
    token_p2 = repo.stelle_web_token_sicher(conn, CHAT_P2)

    conn.commit()
    conn.close()
    return token_p1, token_p2


def main() -> int:
    from playwright.sync_api import sync_playwright

    token_p1, token_p2 = _baue_datenbank()

    server = web.baue_server(DB_PFAD, bind="127.0.0.1:0", praefix="")
    faden = threading.Thread(target=server.serve_forever, daemon=True)
    faden.start()
    basis = f"http://127.0.0.1:{server.server_address[1]}"

    ZIELE = (
        ("phase1-chat", f"{basis}/g/{token_p1}#chat", "#tab-chat:not([hidden])"),
        ("phase1-cothinker", f"{basis}/g/{token_p1}#buehne", "#tab-buehne:not([hidden])"),
        ("phase2-chat", f"{basis}/g/{token_p2}#chat", "#tab-chat:not([hidden])"),
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for entwurf in ("b", "c"):
                    os.environ["IT_UX_ENTWURF"] = entwurf
                    assert web_gestalt.entwurf() == entwurf
                    for geraet, viewport in (("handy", HANDY), ("laptop", LAPTOP)):
                        kontext = browser.new_context(
                            viewport=viewport, is_mobile=(geraet == "handy"),
                        )
                        for name, url, warte_auf in ZIELE:
                            seite = kontext.new_page()
                            seite.set_default_timeout(8000)
                            seite.goto(url)
                            seite.wait_for_selector(warte_auf)
                            seite.wait_for_timeout(400)
                            ziel = HIER / f"{name}-{geraet}-{entwurf}.png"
                            seite.screenshot(path=str(ziel))
                            print(ziel.name)
                            seite.close()
                        kontext.close()
            finally:
                browser.close()
    finally:
        os.environ.pop("IT_UX_ENTWURF", None)
        server.shutdown()
        faden.join(timeout=5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
