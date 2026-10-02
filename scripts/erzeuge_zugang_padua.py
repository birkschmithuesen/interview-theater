"""Erzeugt je Gruppe ein druckbares A4-Blatt mit Token-Link + QR-Code
(Karte Padua A6).

Liest die Gruppen read-only aus der Datenbank (``IT_DB``), baut je Gruppe
eine HTML-Seite (QR als Inline-SVG, kein Pillow noetig) und druckt sie per
headless Chromium (Playwright) zu PDF -- eine Seite je Gruppe, A4.

Die Ausgabe liegt unter ``workshop/<profil>/zugang/`` (per ``.gitignore``
ausgeschlossen: das Token IST das Login, es darf nie in einen Commit).

Abhaengigkeiten (NICHT in pyproject.toml, bewusst getrennt vom Produktivcode):
    - ``qrcode`` (pure Python, erzeugt SVG ohne Pillow) -- lokal unter
      ``.padua-tools/`` installiert, siehe PYTHONPATH unten.
    - Playwright-venv unter ``/mnt/HC_Volume_106183673/venvs/it-webtest``
      (existiert bereits fuer tests/e2e, dasselbe Chromium wird hier
      wiederverwendet -- kein zweiter Download).

Aufruf::

    IT_DB=betrieb/padua.db IT_WEB_URL=https://lab.artesmobiles.art/padua \\
      PYTHONPATH=.padua-tools \\
      /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python \\
      -m scripts.erzeuge_zugang_padua --profil padua-2026
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo

CHAT_PFAD = "chat"


def _qr_svg_inline(daten: str) -> str:
    """Baut die blanke QR-Matrix als <svg>…</svg>-String (kein Dateianhang,
    direkt in die HTML-Seite eingebettet -- Chromium braucht dafuer keinen
    zweiten Request)."""
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(daten)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    zelle = 6
    groesse = n * zelle
    rechtecke = []
    for y, zeile in enumerate(matrix):
        for x, dunkel in enumerate(zeile):
            if dunkel:
                rechtecke.append(
                    f'<rect x="{x * zelle}" y="{y * zelle}" '
                    f'width="{zelle}" height="{zelle}" fill="#000"/>'
                )
    return (
        f'<svg viewBox="0 0 {groesse} {groesse}" width="260" height="260" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff">'
        f'<rect x="0" y="0" width="{groesse}" height="{groesse}" fill="#fff"/>'
        + "".join(rechtecke)
        + "</svg>"
    )


def _seite_html(titel: str, url: str) -> str:
    qr = _qr_svg_inline(url)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 0; }}
  body {{
    font-family: 'Helvetica Neue', Arial, sans-serif;
    width: 210mm; height: 297mm; margin: 0;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center;
  }}
  h1 {{ font-size: 36pt; margin: 0 0 10mm 0; }}
  .qr {{ margin: 10mm 0; }}
  .url {{ font-size: 13pt; word-break: break-all; max-width: 150mm;
          color: #333; margin-top: 6mm; }}
  .hinweis {{ font-size: 11pt; color: #666; margin-top: 14mm; max-width: 150mm; }}
</style></head>
<body>
  <h1>{titel}</h1>
  <div class="qr">{qr}</div>
  <div class="url">{url}</div>
  <div class="hinweis">
    Scan the QR code or open the link above in your phone's browser.
    No login needed &mdash; this link belongs to your group only.
  </div>
</body></html>"""


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser()
    zerleger.add_argument("--profil", default="padua-2026")
    zerleger.add_argument("--ausgabe", default=None)
    args = zerleger.parse_args(argv)

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        return 1
    basis = os.environ.get("IT_WEB_URL", "").rstrip("/")
    if not basis:
        print("Fehlende Umgebungsvariable: IT_WEB_URL", file=sys.stderr)
        return 1

    ziel_dir = Path(args.ausgabe or f"workshop/{args.profil}/zugang")
    ziel_dir.mkdir(parents=True, exist_ok=True)

    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    gruppen = repo.alle_gruppen(conn)
    conn.close()

    if not gruppen:
        print("Keine Gruppe in der Datenbank.", file=sys.stderr)
        return 1

    from playwright.sync_api import sync_playwright

    pfade = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for gruppe in gruppen:
            token = gruppe["web_token"]
            if not token:
                print(f"Gruppe {gruppe['chat_id']} hat kein Token -- uebersprungen.")
                continue
            titel = gruppe["titel"] or f"Group {gruppe['chat_id']}"
            url = f"{basis}/g/{token}/{CHAT_PFAD}"
            html = _seite_html(titel, url)
            htmlpfad = ziel_dir / f"{gruppe['bot_name']}.html"
            htmlpfad.write_text(html, encoding="utf-8")
            page.goto(f"file://{htmlpfad.resolve()}")
            pdfpfad = ziel_dir / f"{gruppe['bot_name']}.pdf"
            page.pdf(path=str(pdfpfad), format="A4", print_background=True)
            pfade.append(pdfpfad)
            print(f"{titel}: {pdfpfad}  ({url})")
        browser.close()

    print(f"\n{len(pfade)} Blatt/Blaetter unter {ziel_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
