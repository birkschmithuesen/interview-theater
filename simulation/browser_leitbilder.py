"""Leitbilder fuer Birks Deck (04.10.2026, 18:40): je Phase und Geraet
hoechstens fuenf Screenshots nach docs/guide/bilder/, nur im Schlusslauf.
Ein Waechter lehnt jedes Bild ab, auf dem das Gruppentoken, ein Link, ein
sichtbarer Fehler oder ein deutscher Rest steht. Kein PDF, keine
Bildbibliothek -- kleine PNGs ueber Playwrights scale="css"."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

MAX_BYTES = 400_000
_DEUTSCH = re.compile(r"[äöüß]|\b(und|nicht|der|die)\b")

UNTERSCHRIFTEN: dict[tuple[int, str], str] = {
    (1, "start"): "The app, freshly opened: nothing typed, nothing tapped yet.",
    (1, "eintritt"): "Phase 1 starts: the app explains what this phase is for.",
    (1, "kalibrierung"): "A short microphone check before the group starts talking.",
    (1, "zuhoeren"): "Listening: the phone lies in the middle while the group discusses.",
    (1, "cothinker"): "A second phone shows the term board growing in the CoThinker tab.",
    (1, "uebergang"): "Terms saved, the app offers the next phase.",
    (2, "eintritt"): "Phase 2 starts: the group writes its own questions first.",
    (2, "arbeit"): "Going through the questions one at a time with buttons.",
    (2, "ergebnis"): "Where we are: questions, opening and closing at a glance.",
    (2, "uebergang"): "Questions ready, the app offers the interview phase.",
}
_REIHENFOLGE = list(UNTERSCHRIFTEN)


def pruefe_bild(seitentext: str, token: str, fehler_sichtbar: bool) -> str | None:
    if token and token in seitentext:
        return "token"
    if "http" in seitentext:
        return "http"
    if fehler_sichtbar:
        return "fehler"
    if _DEUTSCH.search(seitentext):
        return "deutsch"
    return None


class Sammler:
    def __init__(self, *, token: str, geraet: str, ziel: Path):
        self.token, self.geraet, self.ziel = token, geraet, Path(ziel)
        self.eintraege: list[dict] = []
        self._genommen: set[tuple[int, str, str]] = set()

    def nimm(self, page, phase: int, station: str, geraet: str | None = None) -> dict | None:
        geraet = geraet or self.geraet
        schluessel = (phase, station, geraet)
        if schluessel in self._genommen or (phase, station) not in UNTERSCHRIFTEN:
            return None
        text = page.inner_text("body")
        fehler = page.locator("#fehler:visible").count() > 0
        grund = pruefe_bild(text, self.token, fehler)
        if grund:
            log.warning("Leitbild %s abgelehnt: %s", schluessel, grund)
            return None
        self.ziel.mkdir(parents=True, exist_ok=True)
        datei = f"phase-{phase}-{station}-{geraet}.png"
        page.screenshot(path=str(self.ziel / datei), scale="css")
        if (self.ziel / datei).stat().st_size > MAX_BYTES:
            (self.ziel / datei).unlink()
            log.warning("Leitbild %s zu gross", datei)
            return None
        eintrag = {"datei": datei, "phase": phase, "station": station,
                   "geraet": geraet, "unterschrift_en": UNTERSCHRIFTEN[(phase, station)]}
        self._genommen.add(schluessel)
        self.eintraege.append(eintrag)
        return eintrag

    def schreibe_index(self) -> Path:
        pfad = self.ziel / "index.json"
        alt = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else []
        alle = {e["datei"]: e for e in alt}
        alle.update({e["datei"]: e for e in self.eintraege})
        sortiert = sorted(alle.values(), key=lambda e: (
            e["phase"], _REIHENFOLGE.index((e["phase"], e["station"])), e["geraet"]))
        self.ziel.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(sortiert, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return pfad
