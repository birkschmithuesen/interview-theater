"""Telefon-Organisationskarten je Phase (UX-Knoepfe-Karte, Abschnitt 5).

Erzeugt sieben PNGs (1000x560, dunkel) -- je eine Karte, die zeigt, wie die
Gruppe ihre Telefone fuer diese Phase auslegt: welches Handy welchen Tab
zeigt, wer welche Rolle hat. Inhalt ist erfunden, keine echten Namen, keine
Daten aus einem Workshop.

HTML -> PNG ueber Headless-Chromium, wie ``scripts/prompt_schnappschuss`` und
``simulation/erzeuge_interviews.py`` andere einmalige Artefakte erzeugen: das
HTML selbst ist Wegwerf-Material (ein Temp-Verzeichnis), nur die PNGs werden
committet (``interview_theater/static/handys/``).

Die Tab-Namen hier MUESSEN mit ``web_vereint._TEXT_TAB`` uebereinstimmen
(Chat, Arbeitsstand, Textbuch, CoThinker) -- ein Bild, das einen Tab zeigt, den
es auf der echten Seite nicht gibt, verwirrt mehr, als es hilft.

Aufruf: ``python -m scripts.handy_karten`` (braucht Playwright mit Chromium).
Die englischen Karten (Padua) zeigen seit dem 05.10.2026 ECHTE Screenshots
der Seite je Phase (``scripts/handy_karten_bilder.py``, Wegwerf-DB mit
erfundenem Material); die deutschen Schema-Karten bleiben eingefroren und
entstehen nur noch mit ``--de``.
Aendern: die Tabelle ``PHASEN`` unten, dann neu laufen lassen -- das ist die
EINE Stelle, die der Betreiber anfasst.
"""

import html
import pathlib
import subprocess
import sys
import tempfile

OUT = pathlib.Path(__file__).resolve().parent.parent / "interview_theater" / "static" / "handys"
W, H = 1000, 560

#: Tab -> (Icon, Farbe). Die Namen sind ``web_vereint._TEXT_TAB`` (deutsch,
#: die Konstante selbst ist die deutsche Tabelle wie ueberall in diesem
#: Repo) -- nicht "Stand", das ist nur der interne Routenname.
TAB = {
    "Chat": ("💬", "#4ade80"),
    "Arbeitsstand": ("📋", "#60a5fa"),
    "CoThinker": ("🎭", "#f472b6"),
    "Textbuch": ("📖", "#fbbf24"),
}

#: (Nummer, Name, Satz, [(Tab, Rolle, Notiz), ...]) -- erfunden, keine PII.
PHASEN = [
    (1, "Begriffe",
     "Ein Handy reicht. Alle anderen reden – das Handy tippt mit.",
     [("Chat", "eine:r tippt", "")]),
    (2, "Fragen",
     "Eins entscheidet, eins zeigt die Liste. Ihr diskutiert jede Frage gemeinsam.",
     [("Chat", "entscheidet", "Annehmen · Verwerfen · Schärfen"),
      ("Arbeitsstand", "liest mit", "Fragenliste")]),
    (3, "Interviews",
     "Ein Interview nach dem anderen. Das Aufnahme-Handy liegt beim Gegenüber.",
     [("Chat", "🎙 nimmt auf", "liegt beim Gegenüber"),
      ("Arbeitsstand", "Leitfaden", "Interviewer:in liest die Fragen")]),
    (4, "Setting, Figuren & Geschichte",
     "Eins hört zu, eins steht aufgestellt für alle. Redet einfach.",
     [("Chat", "🎙 hört mit", "liegt in der Mitte"),
      ("CoThinker", "für alle sichtbar", "aufgestellt"),
      ("Arbeitsstand", "Stückkarte", "optional")]),
    (5, "Schärfung",
     "Eins arbeitet mit dem Bot, eins zeigt Figuren und Material.",
     [("Chat", "eine:r tippt", ""), ("Arbeitsstand", "Figuren & Material", "")]),
    (6, "Szenen als Geschichte",
     "Eins schreibt mit dem Bot, die anderen lesen die Geschichte mit.",
     [("Chat", "eine:r tippt", ""), ("Textbuch", "lesen mit", ""),
      ("Textbuch", "lesen mit", "")]),
    (7, "Feinschliff",
     "Jede:r öffnet die eigene Rolle per Rollenlink. Eins führt Regie im Chat.",
     [("Chat", "Regie", ""), ("Textbuch", "Rolle A", "Rollenlink"),
      ("Textbuch", "Rolle B", "Rollenlink"), ("Textbuch", "Rolle C", "Rollenlink")]),
]


#: Englische Tabelle (Padua, 02.10.2026: "Bilder zum Handy aufstellen sind auf
#: deutsch"). Dieselbe Struktur wie ``PHASEN``; Tab-Namen sind die englischen
#: Werte von ``web_vereint._TEXT_TAB`` (sprachen/en/texte.toml), Phasennamen
#: die aus ``phasen.PHASEN`` im Padua-Profil. Je Sprache: Tabelle, Kopfzeile,
#: Tabfarben-Zuordnung und Ausgabeordner.
TAB_EN = {
    "Chat": TAB["Chat"],
    "Workbench": TAB["Arbeitsstand"],
    "CoThinker": TAB["CoThinker"],
    "Script": TAB["Textbuch"],
}

PHASEN_EN = [
    # Phase 1 (Birk 05.10.2026, Nachtrag 8): ZWEI Handys -- A hoert in der
    # Mitte zu, B zeigt das Board. Vorher stand hier "One phone is enough".
    # Die Buchstaben A/B sind dieselben wie in der Begruessung
    # (``bot._TEXT_ERSTKONTAKT_DISKUSSION``) -- eine Begrifflichkeit.
    (1, "Terms",
     "Phone A lies in the middle and listens. Phone B shows the CoThinker – "
     "your terms appear there live.",
     [("Chat", "listens", "in the middle · Start listening"),
      ("CoThinker", "terms appear live", "")]),
    # Phase 2 (Birk 05.10.2026, Nachtrag 9): B ist der CoThinker, nicht die
    # Workbench -- er zeigt je Begriff die Fragen bzw. was noch fehlt.
    (2, "Questions",
     "Phone A decides in the chat. Phone B shows the CoThinker: the questions "
     "for each term.",
     [("Chat", "decides", ""),
      ("CoThinker", "questions per term", "")]),
    (3, "Interviews",
     "One interview after the other. The recording phone lies with the interviewee.",
     [("Chat", "🎙 records", "lies with the interviewee"),
      ("Workbench", "guide", "interviewer reads the questions")]),
    (4, "Setting, Characters & Story",
     "One phone listens, one stands up for everyone to see. Just talk.",
     [("Chat", "🎙 listens", "lies in the middle"),
      ("CoThinker", "visible to all", "propped up"),
      ("Workbench", "play card", "optional")]),
    (5, "Sharpening",
     "One phone works with the bot, one shows characters and material.",
     [("Chat", "one person types", ""), ("Workbench", "characters & material", "")]),
    (6, "Scenes as Story",
     "One phone writes with the bot, the others read the story along.",
     [("Chat", "one person types", ""), ("Script", "read along", ""),
      ("Script", "read along", "")]),
    (7, "Polish",
     "Everyone opens their own part via the role link. One directs in the chat.",
     [("Chat", "directs", ""), ("Script", "Part A", "role link"),
      ("Script", "Part B", "role link"), ("Script", "Part C", "role link")]),
]

#: Sprache -> (Tabelle, Tabfarben, Kopfzeile mit {nr}, Dateiname mit {nr}).
#: Alle Karten liegen flach in ``OUT`` -- die Static-Route nimmt nur
#: ``[a-z0-9-]+.png`` ohne Unterordner.
SPRACHEN = {
    "de": (PHASEN, TAB, "PHASE {nr} / 7 · SO LEGT IHR DIE HANDYS", "phase-{nr}.png"),
    "en": (PHASEN_EN, TAB_EN, "PHASE {nr} / 7 · HOW TO SET UP YOUR PHONES", "phase-{nr}-en.png"),
}


def phone(tab: str, rolle: str, notiz: str, tabs: dict = TAB) -> str:
    icon, farbe = tabs[tab]
    return f"""
    <div class="ph">
      <div class="body" style="border-color:{farbe}">
        <div class="notch"></div>
        <div class="screen" style="background:{farbe}22">
          <div class="ic">{icon}</div>
          <div class="tab" style="color:{farbe}">{html.escape(tab)}</div>
        </div>
      </div>
      <div class="rolle">{html.escape(rolle)}</div>
      <div class="notiz">{html.escape(notiz)}</div>
    </div>"""


CSS = f"""
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ width:{W}px; height:{H}px; background:#0d1117; color:#e6edf3;
       font-family:'DejaVu Sans',sans-serif; padding:34px 44px; overflow:hidden }}
.kopf {{ font-family:'DejaVu Sans Mono',monospace; color:#7d8590; font-size:20px; letter-spacing:2px }}
h1 {{ font-size:38px; margin:6px 0 10px }}
.satz {{ font-size:22px; color:#c9d1d9; line-height:1.35; max-width:900px }}
.reihe {{ display:flex; gap:44px; justify-content:center; align-items:flex-start; margin-top:34px }}
.ph {{ width:170px; text-align:center }}
.body {{ width:130px; height:230px; margin:0 auto; border:5px solid; border-radius:26px;
        background:#161b22; padding:22px 10px 14px; position:relative }}
.notch {{ position:absolute; top:8px; left:50%; width:36px; height:6px; margin-left:-18px;
         background:#30363d; border-radius:3px }}
.screen {{ height:100%; border-radius:12px; display:flex; flex-direction:column;
          align-items:center; justify-content:center; gap:10px }}
.ic {{ font-size:54px; font-family:'Noto Color Emoji' }}
.tab {{ font-size:22px; font-weight:bold }}
.rolle {{ margin-top:14px; font-size:20px; font-weight:bold }}
.notiz {{ margin-top:4px; font-size:16px; color:#8b949e; line-height:1.3 }}
"""


def satz_fuer(nr: int) -> str:
    """Der Alt-Text einer Karte -- derselbe Satz wie auf der Karte selbst
    (``web_karten.SAETZE`` liest ihn, kein zweiter Text)."""
    return next(satz for n, _name, satz, _p in PHASEN if n == nr)


def _erzeuge_schema(code: str) -> None:
    """Die alten Schema-Karten (Icon statt Bildschirm) -- nur noch fuer
    Deutsch, und nur auf ausdrueckliches ``--de``: Dortmund ist seit dem
    04.10.2026 eingefroren, ``phase-N.png`` wird nicht neu erzeugt."""
    tabelle, tabs, kopf, muster = SPRACHEN[code]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_pfad = pathlib.Path(tmp)
        for nr, name, satz, phones in tabelle:
            seite = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
            <div class="kopf">{html.escape(kopf.format(nr=nr))}</div>
            <h1>{html.escape(name)}</h1>
            <div class="satz">{html.escape(satz)}</div>
            <div class="reihe">{''.join(phone(*p, tabs=tabs) for p in phones)}</div>
            </body></html>"""
            src = tmp_pfad / f"phase-{nr}.html"
            src.write_text(seite, encoding="utf-8")
            png = OUT / muster.format(nr=nr)
            subprocess.run(
                ["chromium", "--headless", "--no-sandbox", "--disable-gpu",
                 "--hide-scrollbars", f"--window-size={W},{H}",
                 f"--screenshot={png}", src.as_uri()],
                check=True, capture_output=True, timeout=60,
            )
            print(png, png.stat().st_size)


def erzeuge(argv: list[str] | None = None) -> None:
    """Englisch (Padua) mit ECHTEN Screenshots (Birk 05.10.2026, Nachtrag 8:
    "Die echten Screenshots sind besser. Mache das gleich in allen Phasen.")
    -- siehe ``scripts/handy_karten_bilder.py``. ``--de`` erzeugt zusaetzlich
    die alten deutschen Schema-Karten (eingefroren, normalerweise nicht)."""
    argv = sys.argv[1:] if argv is None else argv
    OUT.mkdir(parents=True, exist_ok=True)
    from scripts import handy_karten_bilder

    handy_karten_bilder.erzeuge_en()
    if "--de" in argv:
        _erzeuge_schema("de")


if __name__ == "__main__":
    sys.exit(erzeuge())
