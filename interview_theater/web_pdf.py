"""Das Stage Script als PDF (Birk, 07.10.2026 ~19:35, Nachtrag 3 Punkt 2a):
Knopf "PDF" im Script-Tab, damit die Gruppe das Skript am Handy oeffnet --
A4, Seitenumbruch je Szene/Moment, Interview quotes abgesetzt, Layout je
Gruppe (G2: Kopf mit Versuchsanordnung und Rollen vorn, G3: Orts-Partitur
vorn).

Kein zweiter Renderer: gedruckt wird **dieselbe Probenansicht**, die der
Script-Tab zeigt (``web.textbuch_html``) -- sie traegt seit dem 06.09.2026
ein Druck-CSS ("Der Ausdruck IST das PDF"). Dieses Modul legt nur ein paar
Druckregeln fuer A4 dazu und laesst das vorhandene Headless-Chromium drucken
(``--print-to-pdf``). Nur unter ``workshop.szenenkarten_aktiv`` (Padua);
ohne Schalter gibt es die Route nicht.

Kein Modellaufruf, kein Schreibzugriff: der Webserver liest read-only.
Immer nur ein Chromium gleichzeitig (``_SPERRE``)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from pathlib import Path

#: Die Headless-Shell aus dem Playwright-Cache: druckt in ~1 s. Das volle
#: Chromium (Birk) haengt auf herkules sowohl mit ``--headless=new`` als auch
#: mit ``--headless`` (gemessen 07.10.2026) -- es bleibt nur Rueckfall. Per
#: ``IT_CHROME`` umstellbar.
CHROME_VORGABE = ("/home/birk/.cache/ms-playwright/chromium_headless_shell-1228/"
                  "chrome-headless-shell-linux64/chrome-headless-shell")
CHROME_RUECKFALL = "/home/birk/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome"
ZEITLIMIT_S = 60
_SPERRE = threading.Lock()

#: Die Druckregeln obendrauf -- das abgenommene Design (Birk 08.10.2026
#: ~00:05, ``web_skript``): hell, A4, Raender 18/18/20 mm, jede Szene auf
#: eine neue Seite, Ueberschriften nie allein am Seitenende, Zitate,
#: Tabellen und Listenpunkte nicht zerrissen. Die Uebersicht vorn steht
#: nicht allein auf einer fast leeren Seite: die erste Szene schliesst an.
#: Steht als letztes ``<style>`` im Kopf und gewinnt deshalb gegen Seiten-
#: und Gestaltungs-CSS (dunkles Thema).
DRUCK_CSS = """
@page { size: A4; margin: 18mm 18mm 20mm; }
@media print {
  html, body { background: #fff !important; }
  body, body * { color: #1b1b1b !important; background: transparent !important;
                 box-shadow: none !important; text-shadow: none !important; }
  body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 11pt; line-height: 1.5; }
  h1 { font: 600 22pt/1.2 'DejaVu Sans', sans-serif; color: #9a5f12 !important; margin: 0 0 10pt; }
  .stueck { --sk-text: #1b1b1b; --sk-leise: #6b665c; --sk-akzent: #9a5f12; --sk-linie: #ddd6c8; --sk-zitat: #f6f1e7; font-size: 11pt; }
  .stueck .probe-szene, .stueck .probe-szene .text { max-width: none; }
  .stueck .probe-szene .text p, .stueck .probe-szene p, .stueck .probe-szene li { font-size: 11pt; line-height: 1.5; orphans: 3; widows: 3; }
  .stueck > .probe-szene { break-before: page; break-after: auto; page-break-after: auto; }
  .stueck > .probe-szene:first-child, .stueck > .uebersicht + .probe-szene { break-before: auto; }
  .stueck .probe-szene .szenenkopf { font-size: 15pt; border-top: none !important; padding-top: 0; margin-top: 0; }
  .stueck > .uebersicht + .probe-szene .szenenkopf { margin-top: 18pt; }
  h2, h3, h4, .zitat-kopf, .person, .meta, summary { break-after: avoid; page-break-after: avoid; }
  blockquote, table, tr, li, details { break-inside: avoid; page-break-inside: avoid; }
  .stueck h3, .stueck .zitat-kopf, .stueck details.rolle-mehr summary { color: #9a5f12 !important; }
  .stueck h4, .stueck .meta, .stueck .angaben, .stueck .besetzung, .stueck .sprache-kopf,
  .stueck .regie, .stueck .skript-tabelle th { color: #6b665c !important; }
  .stueck blockquote.interviewzitat { background: #f6f1e7 !important; border-left: 3px solid #9a5f12 !important; }
  .stueck .skript-tabelle th { border-bottom: 1px solid #9a5f12 !important; }
  .stueck .skript-tabelle td { border-bottom: 1px solid #ddd6c8 !important; }
  .stueck .skript-tabelle { font-size: 9.5pt; }
  .stueck .badge { background: #9a5f12 !important; color: #fff !important; }
  .stueck details.rolle-mehr summary { list-style: none; }
  .stueck details.rolle-mehr p { font-size: 10pt; }
  .wege, .leiste, .rollen, .hinweis-druck, details.fruehere, details.erstentwurf { display: none !important; }
}
"""


def chrome_pfad() -> str:
    if os.environ.get("IT_CHROME"):
        return os.environ["IT_CHROME"]
    return CHROME_VORGABE if Path(CHROME_VORGABE).exists() else CHROME_RUECKFALL


def mit_druck_css(html: str) -> str:
    """Haengt die A4-Druckregeln als letztes Stylesheet in den Kopf."""
    marke = "</head>"
    stil = f"<style>{DRUCK_CSS}</style>"
    # "what, never, when" je Person: am Handy zugeklappt, im PDF offen.
    html = html.replace('<details class="rolle-mehr">', '<details class="rolle-mehr" open>')
    return html.replace(marke, stil + marke, 1) if marke in html else stil + html


def pdf_aus_html(html: str, chrome: str | None = None) -> bytes:
    """Druckt ``html`` mit Headless-Chromium zu PDF-Bytes. Wirft
    ``RuntimeError``, wenn Chromium fehlt oder kein PDF liefert."""
    chrome = chrome or chrome_pfad()
    if not Path(chrome).exists():
        raise RuntimeError(f"Chromium fehlt: {chrome}")
    with _SPERRE, tempfile.TemporaryDirectory(prefix="it-pdf-") as ordner:
        quelle = Path(ordner) / "script.html"
        ziel = Path(ordner) / "script.pdf"
        quelle.write_text(mit_druck_css(html), encoding="utf-8")
        subprocess.run(
            [chrome, *(["--headless=new"] if "headless-shell" not in chrome else []),
             "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", "--hide-scrollbars",
             f"--user-data-dir={Path(ordner) / 'profil'}",
             f"--print-to-pdf={ziel}", quelle.as_uri()],
            check=False, capture_output=True, timeout=ZEITLIMIT_S,
        )
        if not ziel.exists() or not ziel.read_bytes().startswith(b"%PDF"):
            raise RuntimeError("Chromium hat kein PDF geschrieben")
        return ziel.read_bytes()


def sende(handler, daten: dict, token: str, praefix: str, lang: str = "en") -> None:
    """Die Antwort auf ``GET /g/<token>/textbuch.pdf?lang=en|it``: das PDF
    zum Ansehen im Browser (inline), nie zwischengespeichert -- das Skript
    aendert sich.

    Zwei getrennte PDFs statt einem gemischten (Morgen-Auftrag 3, 08.10.2026):
    ``lang`` waehlt EN oder IT, alles andere/Fehlendes faellt auf EN zurueck
    -- ``textbuch_html`` zeigt dann genau eine Fassung je Szene statt beider
    gestapelt."""
    from interview_theater import web

    lang = lang if lang in ("en", "it") else "en"
    try:
        roh = pdf_aus_html(web.textbuch_html(daten, token, praefix, lang))
    except Exception:
        handler._antworte(503, web.T._TEXT_PDF_FEHLER, "text/plain; charset=utf-8")
        return
    titel = (daten.get("titel") or "script").strip() or "script"
    datei = "".join(z if z.isalnum() or z in "-_" else "-" for z in titel)[:40] or "script"
    handler.send_response(200)
    handler.send_header("Content-Type", "application/pdf")
    handler.send_header("Content-Length", str(len(roh)))
    handler.send_header("Content-Disposition",
                        f'inline; filename="{datei}-stage-script-{lang}.pdf"')
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(roh)
