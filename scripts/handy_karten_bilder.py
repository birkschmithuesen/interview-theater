"""Die englischen Handy-Karten mit ECHTEN Screenshots (Birk 05.10.2026,
Nachtrag 8: "Die echten Screenshots sind besser. Mache das gleich in allen
Phasen.").

Je Phase: eine Wegwerf-Datenbank mit erfundenem Material (keine echten
Namen, keine Workshop-Daten), ein Wegwerf-Webserver im selben Prozess
(``web.baue_server``, Port 0, Profil ``padua-2026``), und je Handy der
Karte ein Screenshot des Tabs, den die Tabelle ``handy_karten.PHASEN_EN``
diesem Handy gibt -- 390x844 wie ein Telefon. Die Karte setzt die
Screenshots in Handy-Rahmen nebeneinander, beschriftet mit "A · Chat",
"B · CoThinker" ..., darunter Rolle und Notiz aus derselben Tabelle. Kein
Token und keine URL steht im Bild: die Seite zeigt keins, und die Karte
selbst ist reines HTML aus der Tabelle.

Vorbild: der Phase-1-Versuch ``zwei_handys.py``/``dom_map_server.py``
(Birks Scratch, 05.10.2026).

**Phase 2, Handy B:** der CoThinker zeigt in Phase 2 die Fragen je Begriff (seit Merge robo/p2-livefix echt, AUS_PHASE leer).
erst nach dem Merge von ``robo/p2-livefix`` (Punkt M). Bis dahin ist
``AUS_PHASE`` gesetzt: der Screenshot von B entsteht als CoThinker der
Phase 1 (das Begriffsboard) -- ein Platzhalter. Nach dem Merge den Eintrag
in ``AUS_PHASE`` loeschen und neu laufen lassen.

Aufruf: ``python -m scripts.handy_karten`` (ruft ``erzeuge_en``). Kein Test,
braucht Playwright mit Chromium, kostet nichts (kein Modell, kein Netz).
"""

from __future__ import annotations

import base64
import html
import json
import os
import pathlib
import tempfile
import threading
import time

from scripts.handy_karten import OUT, PHASEN_EN, SPRACHEN

CHAT = 7_000_000_000_801

#: Tab der Karte -> Hash der vereinten Seite (``web_vereint.TABS``, plus der
#: CoThinker-Tab ``buehne``).
HASH = {"Chat": "chat", "Workbench": "stand", "CoThinker": "buehne", "Script": "textbuch"}

#: (Phase, Handy-Index) -> Phase, deren Daten fuer diesen Screenshot gelten.
#: Nur fuer den Platzhalter Phase 2 / Handy B (siehe Modulkopf).
AUS_PHASE: dict = {}

#: Phase 7: die Rollen der drei Script-Handys (Rollenlink ``#textbuch&figur=``).
ROLLEN_7 = ("LENA", "MALIK", "SOFIA")

VIEWPORT = {"width": 390, "height": 844}
ORANGE = "#F0B163"

BOARD = [
    ("home", "favorit", 2, 6, "Home is where someone waits for you."),
    ("border", "favorit", 2, 4, "Every family here crossed one."),
    ("waiting", "favorit", 2, 4, "We all know the waiting rooms."),
    ("language", "kandidat", 1, 3, ""),
    ("night shift", "kandidat", 1, 2, ""),
    ("noise", "kandidat", 0, 2, ""),
    ("party", "verworfen", -1, 1, ""),
]
BEGRIFFE = "home, border, waiting, language, night shift"
FRAGEN = (
    "1. Where did you feel at home for the first time?\n"
    "2. Which border do you still carry with you?\n"
    "3. What were you waiting for, back then?"
)
FIGUREN = [
    ("Lena", "a night-shift nurse who never misses a call from home"),
    ("Malik", "her younger brother, studies law, translates for everyone"),
    ("Sofia", "the neighbour who has waited eleven years for a letter"),
]
SZENEN = [
    ("The Waiting Room", "Dialogue",
     "Lena sits in the corridor of the clinic. The vending machine hums. "
     "Malik arrives late, still in his coat, and does not sit down.",
     "LENA: (without looking up) You're late.\n"
     "MALIK: The bus didn't come.\n"
     "LENA: It never comes when Mum calls.\n"
     "SOFIA: (from the door) Is this the line for the forms?\n"
     "MALIK: There is no line. Only us."),
    ("Night Shift", "Monologue",
     "Three in the morning. Lena counts the beds and the hours until the "
     "phone will ring again.",
     "LENA: Twelve beds. Nine sleeping. One asking for her mother in a "
     "language nobody here speaks. I speak it. I say: soon.\n"
     "SOFIA: (off) Soon is a long word."),
    ("The Letter", "Dialogue",
     "Sofia finally holds the envelope. She asks Malik to read it out loud.",
     "SOFIA: Read it. Slowly.\n"
     "MALIK: \"Dear Mrs ...\" It's your name. They spelled it right.\n"
     "SOFIA: Eleven years, and they spelled it right.\n"
     "LENA: Go on. Read the rest."),
]


def _bot(conn, text):
    from interview_theater import repo
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text=text)


def _gruppe(conn, text):
    from interview_theater import repo
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text=text)


def _board(conn):
    from interview_theater import repo
    eintraege = [
        {"begriff": b, "nennungen": n, "zustimmung": z, "begruendung": g, "zitat": "",
         "doppelbedeutung": "", "status": st}
        for b, st, z, n, g in BOARD
    ]
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(eintraege), "sovereign", 0)


def _saeen(conn, phase: int) -> None:
    """Erfundenes Material bis einschliesslich ``phase`` -- jede Phase sieht
    so aus, als haette die Gruppe die Phasen davor durchlaufen."""
    from interview_theater import bot, repo

    repo.setze_phase(conn, CHAT, phase)
    if phase == 1:
        _board(conn)
        _bot(conn, bot.T._TEXT_ERSTKONTAKT_DISKUSSION)
        return
    _board(conn)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", BEGRIFFE)
    if phase == 2:
        # CoThinker Phase 2 zeigt Fragen je Begriff ("Begriff: Frage");
        # zwei Begriffe bewusst noch ohne Frage (leise markiert).
        repo.setze_arbeitsstand(conn, CHAT, "fragen", (
            "home: Where did you feel at home for the first time?\n"
            "home: What would you take with you if you had to leave tonight?\n"
            "border: Which border do you still carry with you?\n"
            "waiting: What were you waiting for, back then?"
        ))
        _bot(conn, "These are your five terms – saved. Now: which question would you "
                   "ask a stranger about \"home\"?")
        _gruppe(conn, "Where did you feel at home for the first time?")
        _bot(conn, "Good, that one opens people up. Keep it as it is, or sharpen it?")
        return
    repo.setze_arbeitsstand(conn, CHAT, "fragen", FRAGEN)
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung",
                            "Hi, we are drama students. Can we ask you three questions "
                            "about home? It takes ten minutes, and we use no names.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss",
                            "Thank you. Is there anything you would like to add?")
    if phase == 3:
        _bot(conn, "Your interview guide is ready – it's in the Workbench. When you "
                   "sit down with someone, tap Start interview.")
        return
    kopf = repo.lege_aufnahme_an(conn, CHAT, 900, "lang", "sprache", status="fertig")
    repo.speichere_verdichtung(
        conn, CHAT, kopf,
        "A bus driver talks about the night he stopped counting the years since "
        "he left; home is the route he drives, not the city he came from.",
        [{"thema": "Home as a route", "kurz": "home as a route",
          "beleg_zitat": "my home is the 47, the whole night", "zitat_geprueft": 1}],
    )
    if phase == 4:
        repo.lege_buehnenkarte_an(
            conn, CHAT, "What if the whole play happens in one waiting room – and "
            "nobody is ever called?", "sovereign")
        repo.lege_buehnenkarte_an(
            conn, CHAT, "A brother and a sister, one translates, one stays silent. "
            "Who speaks for whom?", "sovereign")
        _bot(conn, "I'm listening along. Your ideas appear as cards in the CoThinker.")
        return
    repo.setze_arbeitsstand(conn, CHAT, "rahmen",
                            "A hospital corridor in a port city, one long night")
    repo.setze_arbeitsstand(conn, CHAT, "geschichte",
                            "Lena, Malik and Sofia wait through one night for news "
                            "that has taken years; at dawn a letter arrives.")
    repo.setze_arbeitsstand(conn, CHAT, "figuren_fixiert_am", repo._jetzt())
    for name, beschreibung in FIGUREN:
        repo.setze_figur(conn, CHAT, name, beschreibung)
    for nr, (titel, form, prosa, volltext) in enumerate(SZENEN, 1):
        sid = repo.lege_szene_an(conn, CHAT, nr, titel, None, None)
        if phase >= 6:
            repo.aktualisiere_szene(conn, sid, titel, None,
                                    volltext if phase >= 7 else None, prosa=prosa)
        if phase >= 7:
            repo.setze_szenenfeld(conn, sid, "form", form)
    if phase == 5:
        _bot(conn, "Sharpening: the bus driver's line \"my home is the 47\" fits Malik "
                   "in scene 1. Shall we give it to him?")
    elif phase == 6:
        _bot(conn, "The story is written – read it in the Script tab. Which scene "
                   "should we look at first?")
    else:
        _bot(conn, "Scene 3 is a dialogue now. Everyone: open your part with the "
                   "role link in the Script tab.")


def _starte_server(pfad: str):
    from interview_theater import web
    dienst = web.baue_server(pfad, "127.0.0.1:0", "", schluessel=b"handykarten-schluessel")
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    return dienst


def _bildschirm(browser, url: str, phase: int, index: int, tab: str) -> bytes:
    """Ein Screenshot wie auf dem Telefon: 390x844, der Tab der Karte."""
    kontext = browser.new_context(viewport=VIEWPORT, device_scale_factor=2,
                                  permissions=["microphone"])
    seite = kontext.new_page()
    ziel = HASH[tab]
    if tab == "Script" and phase == 7 and index >= 1:
        ziel = f"textbuch&figur={ROLLEN_7[(index - 1) % len(ROLLEN_7)]}"
    seite.goto(f"{url}#{ziel}")
    seite.wait_for_timeout(2500)
    if phase == 1 and tab == "Chat":
        # Handy A hoert zu: "Start listening" gedrueckt (Mikrofon ist die
        # Chromium-Attrappe, Kalibrierung per Umgebung aus).
        knopf = seite.locator("#diskussion")
        if knopf.count() and knopf.is_visible():
            knopf.click()
            seite.wait_for_timeout(1800)
    if phase == 3 and tab == "Workbench":
        # "guide": der Leitfaden steht in der Workbench unter Phase 2 --
        # aufklappen und hinscrollen, wie es die Interviewerin tut.
        seite.evaluate("""() => {
          for (const d of document.querySelectorAll('details')) {
            if (d.querySelector('pre.leitfaden')) { d.open = true;
              d.querySelector('pre.leitfaden').scrollIntoView({block: 'center'}); }
          }
        }""")
        seite.wait_for_timeout(500)
    bild = seite.screenshot()
    kontext.close()
    return bild


CSS = """
* { box-sizing:border-box; margin:0; padding:0 }
body { width:1000px; background:#0d1117; color:#e6edf3;
       font-family:'DejaVu Sans',system-ui,sans-serif; padding:34px 40px 30px }
.kopf { font-family:'DejaVu Sans Mono',monospace; color:#7d8590; font-size:20px; letter-spacing:2px }
h1 { font-size:38px; margin:6px 0 10px }
.satz { font-size:22px; color:#c9d1d9; line-height:1.35; max-width:920px }
.reihe { display:flex; gap:28px; justify-content:center; align-items:flex-start; margin-top:28px }
.ph { text-align:center }
.ph img { display:block; border:8px solid #222; border-radius:30px; background:#000 }
.mark { color:%s; font-weight:700; font-size:24px; margin-top:12px }
.rolle { margin-top:4px; font-size:19px; font-weight:bold }
.notiz { margin-top:3px; font-size:16px; color:#8b949e; line-height:1.3 }
""" % ORANGE


def _karte(nr: int, name: str, satz: str, phones: list, bilder: list[bytes]) -> str:
    kopf = SPRACHEN["en"][2].format(nr=nr)
    breite = min(300, (920 - 28 * (len(phones) - 1)) // len(phones))
    zellen = []
    for i, ((tab, rolle, notiz), bild) in enumerate(zip(phones, bilder)):
        daten = base64.b64encode(bild).decode()
        zellen.append(
            f'<div class="ph"><img src="data:image/png;base64,{daten}" '
            f'style="width:{breite}px"/>'
            f'<div class="mark">{chr(65 + i)} · {html.escape(tab)}</div>'
            f'<div class="rolle">{html.escape(rolle)}</div>'
            f'<div class="notiz">{html.escape(notiz)}</div></div>'
        )
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style>'
            f'</head><body><div class="kopf">{html.escape(kopf)}</div>'
            f'<h1>{html.escape(name)}</h1><div class="satz">{html.escape(satz)}</div>'
            f'<div class="reihe">{"".join(zellen)}</div></body></html>')


def erzeuge_en() -> list[pathlib.Path]:
    """Erzeugt ``phase-N-en.png`` fuer alle Phasen aus ``PHASEN_EN`` und
    liefert die Pfade."""
    os.environ["IT_WORKSHOP"] = "padua-2026"
    os.environ["IT_WEB_VAD_KALIBRIERUNG"] = "0"
    from playwright.sync_api import sync_playwright

    from interview_theater import db, repo, sprache, workshop

    workshop.vergiss()
    sprache.vergiss()
    erzeugt = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        os.environ["IT_AUDIO"] = str(pathlib.Path(tmp) / "audio")
        browser = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
        server = {}

        def url_fuer(phase: int) -> str:
            if phase not in server:
                pfad = str(pathlib.Path(tmp) / f"phase-{phase}.db")
                conn = db.verbinde(pfad)
                db.initialisiere(conn)
                repo.sichere_gruppe(conn, CHAT, "handykarte", "Group 1")
                repo.setze_gruppe_kanal(conn, CHAT, "web")
                _saeen(conn, phase)
                token = repo.stelle_web_token_sicher(conn, CHAT)
                conn.close()
                dienst = _starte_server(pfad)
                server[phase] = (dienst, f"http://127.0.0.1:{dienst.server_address[1]}/g/{token}")
            return server[phase][1]

        for nr, name, satz, phones in PHASEN_EN:
            bilder = []
            for i, (tab, _rolle, _notiz) in enumerate(phones):
                quelle = AUS_PHASE.get((nr, i), nr)
                bilder.append(_bildschirm(browser, url_fuer(quelle), quelle, i, tab))
            seite = browser.new_page(viewport={"width": 1000, "height": 600})
            seite.set_content(_karte(nr, name, satz, phones, bilder))
            seite.wait_for_timeout(400)
            ziel = OUT / SPRACHEN["en"][3].format(nr=nr)
            seite.screenshot(path=str(ziel), full_page=True)
            seite.close()
            erzeugt.append(ziel)
            print(ziel, ziel.stat().st_size, flush=True)
        browser.close()
        for dienst, _ in server.values():
            dienst.shutdown()
        time.sleep(0.2)
    return erzeugt
