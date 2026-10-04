"""Leitbilder fuer Birks Deck (04.10.2026, 18:40): je Phase und Geraet
hoechstens fuenf Screenshots nach docs/guide/bilder/, nur im Schlusslauf.
Ein Waechter lehnt jedes Bild ab, auf dem das Gruppentoken, ein Link, ein
sichtbarer Fehler oder ein deutscher Rest steht. Kein PDF, keine
Bildbibliothek -- kleine PNGs ueber Playwrights scale="css"."""

from __future__ import annotations

import hashlib
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


def _aktive_phase_nummer(page) -> int | None:
    """Liest ``#roadmap``s ``data-aktive-phase`` -- lokal dupliziert statt
    aus ``browser_lauf`` importiert (das importiert bereits dieses Modul,
    ein Rueckimport waere ein Zyklus). Abnahme P1-2, Fortsetzung
    (Robo-Befund, visuelle Pruefung der Leitbilder): zwei Handy-Bilder, die
    als "Phase 1" beschriftet waren, zeigten tatsaechlich Phase-2-Inhalt --
    der Screenshot wurde genommen, nachdem die Seite schon weitergesprungen
    war."""
    wert = page.get_attribute("#roadmap", "data-aktive-phase")
    if wert is None:
        return None
    try:
        return int(wert)
    except ValueError:
        return None


class Sammler:
    def __init__(self, *, token: str, geraet: str, ziel: Path):
        self.token, self.geraet, self.ziel = token, geraet, Path(ziel)
        self.eintraege: list[dict] = []
        self._genommen: set[tuple[int, str, str]] = set()
        #: SHA-256 der bereits akzeptierten Bilder DIESES Sammlers -- Robo-
        #: Befund: drei Handy-Bilder waren pixelgleich (dieselbe md5), weil
        #: sich die Oberflaeche zwischen zwei Aufnahmepunkten nicht sichtbar
        #: veraendert hatte. Ein zweites, identisches Bild bringt dem Deck
        #: nichts und wird jetzt abgelehnt statt still mitgenommen.
        self._hashes: set[str] = set()

    def nimm(self, page, phase: int, station: str, geraet: str | None = None) -> dict | None:
        geraet = geraet or self.geraet
        schluessel = (phase, station, geraet)
        if schluessel in self._genommen or (phase, station) not in UNTERSCHRIFTEN:
            return None
        aktiv = _aktive_phase_nummer(page)
        if aktiv is not None and aktiv != phase:
            log.warning("Leitbild %s abgelehnt: Kopfzeile zeigt Phase %s, nicht %s",
                       schluessel, aktiv, phase)
            return None
        text = page.inner_text("body")
        fehler = page.locator("#fehler:visible").count() > 0
        grund = pruefe_bild(text, self.token, fehler)
        if grund:
            log.warning("Leitbild %s abgelehnt: %s", schluessel, grund)
            return None
        bild = page.screenshot(scale="css")
        if len(bild) > MAX_BYTES:
            log.warning("Leitbild %s zu gross", schluessel)
            return None
        hash_ = hashlib.sha256(bild).hexdigest()
        if hash_ in self._hashes:
            log.warning("Leitbild %s abgelehnt: pixelgleich mit einem bereits "
                       "gesammelten Bild", schluessel)
            return None
        self.ziel.mkdir(parents=True, exist_ok=True)
        datei = f"phase-{phase}-{station}-{geraet}.png"
        (self.ziel / datei).write_bytes(bild)
        self._hashes.add(hash_)
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
