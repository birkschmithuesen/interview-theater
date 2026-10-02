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
(Chat, Arbeitsstand, Textbuch, Bühne) -- ein Bild, das einen Tab zeigt, den
es auf der echten Seite nicht gibt, verwirrt mehr, als es hilft.

Aufruf: ``python scripts/handy_karten.py`` (braucht ``chromium`` im PATH).
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
    "Bühne": ("🎭", "#f472b6"),
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
      ("Bühne", "für alle sichtbar", "aufgestellt"),
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


def phone(tab: str, rolle: str, notiz: str) -> str:
    icon, farbe = TAB[tab]
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


def erzeuge() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_pfad = pathlib.Path(tmp)
        for nr, name, satz, phones in PHASEN:
            seite = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
            <div class="kopf">PHASE {nr} / 7 · SO LEGT IHR DIE HANDYS</div>
            <h1>{html.escape(name)}</h1>
            <div class="satz">{html.escape(satz)}</div>
            <div class="reihe">{''.join(phone(*p) for p in phones)}</div>
            </body></html>"""
            src = tmp_pfad / f"phase-{nr}.html"
            src.write_text(seite, encoding="utf-8")
            png = OUT / f"phase-{nr}.png"
            subprocess.run(
                ["chromium", "--headless", "--no-sandbox", "--disable-gpu",
                 "--hide-scrollbars", f"--window-size={W},{H}",
                 f"--screenshot={png}", src.as_uri()],
                check=True, capture_output=True, timeout=60,
            )
            print(png, png.stat().st_size)


if __name__ == "__main__":
    sys.exit(erzeuge())
