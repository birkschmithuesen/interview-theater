"""Der Markdown-Bericht und der Kontaktbogen (Padua-UX-Simulation,
2026-10-03). Kein Pillow: der Kontaktbogen ist ein Playwright-Screenshot
einer kleinen HTML-Bildergalerie -- derselbe Werkzeugkasten wie der Rest
dieses Browserlaufs."""

from __future__ import annotations

import base64
from pathlib import Path


def baue_markdown(lauf_titel: str, geraet: str, modelle: dict,
                  phasen_ergebnisse: list[dict],
                  top_befunde: list[dict]) -> str:
    zeilen = [f"# {lauf_titel} ({geraet})", "", "## Overall", ""]
    if top_befunde:
        for befund in top_befunde[:5]:
            zeilen.append(
                f"- **{befund.get('schwere', '?')}** "
                f"(Phase {befund.get('phase', '?')}): {befund['text']}"
            )
    else:
        zeilen.append("(no findings)")
    zeilen += ["", "## Models used"]
    for art, name in sorted(modelle.items()):
        zeilen.append(f"- {art}: {name}")
    zeilen.append("")
    for phase in phasen_ergebnisse:
        note = phase.get("note")
        zeilen.append(
            f"## Phase {phase['nummer']} · {phase['name']} — "
            f"note {note if note is not None else '?'}/5"
        )
        zeilen.append("")
        if phase.get("fallback_benutzt"):
            zeilen += [
                "**Operator fallback used** — the persona got stuck and the "
                "phase was advanced via the harness's phase-click path (the "
                "same endpoint a group's own click on the phase bar uses).",
                "",
            ]
        for befund in phase.get("befunde", []):
            zeilen.append(f"- ({befund.get('schwere', '?')}) {befund['text']}")
        if phase.get("befunde"):
            zeilen.append("")
        zeilen += ["| counter | value |", "|---|---|"]
        for schluessel, wert in (phase.get("zaehler_summe") or {}).items():
            zeilen.append(f"| {schluessel} | {wert} |")
        zeilen.append("")
        for bild in phase.get("screenshots_fuer_bericht") or []:
            zeilen.append(f"![{bild}]({bild})")
        zeilen.append("")
    return "\n".join(zeilen)


def kontaktbogen(context, bild_pfade: list[Path], ausgabe: Path,
                 spalten: int = 4) -> None:
    """Alle Screenshots einer Phase verkleinert auf einem Blatt -- ein
    Playwright-Screenshot einer Rasterseite, kein Pillow.

    Die Bilder gehen als ``data:``-URI ein, nicht als ``file://``-Pfad:
    realer Betriebsbefund (Padua-Abnahme, 03.10.2026) -- eine Seite aus
    ``set_content`` hat keinen Ursprung (``about:blank``), und Chromium
    verweigert ihr den Dateizugriff ohne eine sichtbare Fehlermeldung. Das
    Ergebnis war ein leerer Kontaktbogen mit nur den Dateinamen als
    Bildunterschrift -- kein Absturz, also auch keine Warnung."""
    kacheln = "".join(
        f'<figure><img src="data:image/png;base64,'
        f'{base64.b64encode(Path(p).read_bytes()).decode()}">'
        f"<figcaption>{Path(p).name}</figcaption></figure>"
        for p in bild_pfade
    )
    html = (
        "<style>body{margin:0;background:#222;font-family:sans-serif} "
        f"figure{{display:inline-block;width:{100 // spalten}%;margin:0;"
        "box-sizing:border-box;vertical-align:top}} "
        "img{width:100%;display:block} "
        "figcaption{color:#fff;font:11px monospace;padding:2px}</style>"
        f"<body>{kacheln}</body>"
    )
    seite = context.new_page()
    try:
        seite.set_content(html)
        seite.wait_for_timeout(200)
        # Lieber ein lauter Fehler als ein stiller, leerer Kontaktbogen: mit
        # der alten file://-URI schlug das Laden ohne jede Fehlermeldung
        # fehl und niemand hat es bemerkt, bis jemand die PNG von Hand
        # ansah. ``naturalWidth`` ist 0, solange ein Bild nicht decodiert
        # werden konnte.
        kaputt = seite.evaluate(
            "Array.from(document.images).filter(i => i.naturalWidth === 0).length"
        )
        if kaputt:
            raise RuntimeError(
                f"Kontaktbogen: {kaputt} von {len(bild_pfade)} Bildern "
                f"liessen sich nicht laden ({ausgabe})"
            )
        seite.screenshot(path=str(ausgabe), full_page=True)
    finally:
        seite.close()
