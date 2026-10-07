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

#: Die Druckregeln obendrauf. Steht als letztes ``<style>`` im Kopf und
#: gewinnt deshalb gegen Seiten- und Gestaltungs-CSS (dunkles Thema) --
#: gedruckt wird schwarz auf weiss.
DRUCK_CSS = """
@page { size: A4; margin: 18mm 17mm 20mm; }
@media print {
  html, body { background: #fff !important; }
  body, body * { color: #111 !important; background: transparent !important;
                 box-shadow: none !important; text-shadow: none !important; }
  body { font-family: Georgia, "Times New Roman", serif; font-size: 11.5pt; line-height: 1.5; }
  h1 { font-size: 18pt; margin: 0 0 10pt; }
  .szenenkopf { font-size: 15pt; border-bottom: .6pt solid #888 !important; margin: 0 0 6pt; }
  .angaben, .besetzung, .sprache-kopf, .karte-typ, .worum-kopf { font-size: 8.5pt; color: #444 !important; }
  .sprache-kopf { margin-top: 14pt; letter-spacing: .12em; text-transform: uppercase; }
  .text { max-width: none; }
  .text p { margin: 0 0 7pt; orphans: 3; widows: 3; }
  blockquote.interviewzitat, .karte-zitat {
      margin: 7pt 0 9pt; padding: 2pt 0 2pt 10pt; border-left: 2pt solid #777 !important;
      font-style: italic; break-inside: avoid; page-break-inside: avoid; }
  .stage-kopf, .probe-szene.partitur { break-after: page; page-break-after: always; }
  table.partitur { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
  table.partitur th { border-bottom: .8pt solid #555 !important; text-align: left; }
  table.partitur td { border-bottom: .4pt solid #bbb !important; vertical-align: top; padding: 4pt; }
  table.partitur td.an { background: #eee !important; }
  .wege, .leiste, .rollen, details, .hinweis-druck { display: none !important; }
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


def sende(handler, daten: dict, token: str, praefix: str) -> None:
    """Die Antwort auf ``GET /g/<token>/textbuch.pdf``: das PDF zum Ansehen
    im Browser (inline), nie zwischengespeichert -- das Skript aendert sich."""
    from interview_theater import web

    try:
        roh = pdf_aus_html(web.textbuch_html(daten, token, praefix))
    except Exception:
        handler._antworte(503, web.T._TEXT_PDF_FEHLER, "text/plain; charset=utf-8")
        return
    titel = (daten.get("titel") or "script").strip() or "script"
    datei = "".join(z if z.isalnum() or z in "-_" else "-" for z in titel)[:40] or "script"
    handler.send_response(200)
    handler.send_header("Content-Type", "application/pdf")
    handler.send_header("Content-Length", str(len(roh)))
    handler.send_header("Content-Disposition", f'inline; filename="{datei}-stage-script.pdf"')
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(roh)
