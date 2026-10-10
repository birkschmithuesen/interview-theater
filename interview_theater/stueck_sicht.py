"""Die abgeleiteten Ansichten des Stueckmodells (Karte t_fd88600b, Birk
10.10.2026) -- reine Funktionen, kein Projektimport, kein SQL.

Jede Tatsache steht an genau einer Stelle (Ort: ``szene.ort``; wer:
``szene_figur`` + ``szene.wer_zusatz``; offene Fragen: ``offene_frage``).
Hier wird daraus die Karte, wie Script-Kopf, PDF, Werkbank und Prompt sie
zeigen. Bot (``stueck.karte``) und Webserver (``web_daten``) rufen DIESELBE
Funktion -- eine zweite Formatierung waere eine zweite Wahrheit."""

from __future__ import annotations

import re

#: Kartenschluessel, die in ``szene.karte`` NICHT mehr gelesen werden -- sie
#: haben ihre eine Stelle woanders.
STRUKTUR_SCHLUESSEL = ("ort", "wer", "fragen")

#: Ein Kartenpunkt, der in Wahrheit eine offene Frage ist.
OFFEN_PUNKT = re.compile(r"^\s*[\[(]\s*(?:OPEN|APERTO|OFFEN)\s*[\])]\s*:?\s*(.+?)\s*$", re.I)

_TRENNER = re.compile(r"\s*[;,]\s*|\s+(?:e|and|und)\s+", re.I)


def normalisiert(text) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def roh_ohne_struktur(karte: dict) -> dict:
    return {k: v for k, v in karte.items() if k not in STRUKTUR_SCHLUESSEL}


def teile_wer(text: str | None) -> list[str]:
    return [t.strip(" .") for t in _TRENNER.split(text or "") if t and t.strip(" .")]


def ordne_besetzung(text: str | None, figuren: dict[str, int]
                    ) -> tuple[list[tuple[int, str | None]], list[str]]:
    """``figuren``: normalisierter Name -> figur_id. Ein Stueck von ``text``,
    das mit einem bekannten Namen als ganzem Wort BEGINNT, wird diese Figur;
    der Rest des Stuecks ist ihre Rolle in der Szene. Alles andere bleibt
    woertlich als Zusatz -- nichts wird geraten, nichts geht verloren."""
    namen = sorted(figuren, key=len, reverse=True)
    eintraege: list[tuple[int, str | None]] = []
    rest: list[str] = []
    gesehen: set[int] = set()
    for stueck in teile_wer(text):
        klein = normalisiert(stueck)
        treffer = next((n for n in namen if klein == n or klein.startswith(n + " ")
                        or klein.startswith(n + "(")), None)
        if treffer is None:
            rest.append(stueck)
            continue
        figur_id = figuren[treffer]
        if figur_id in gesehen:
            continue
        gesehen.add(figur_id)
        rolle = stueck.strip()[len(treffer):].strip() or None
        eintraege.append((figur_id, rolle))
    return eintraege, rest


def wer_text(besetzung: list[tuple[str, str | None]], zusatz: str | None) -> str:
    teile = [f"{name} {rolle}".strip() if rolle else name for name, rolle in besetzung]
    if (zusatz or "").strip():
        teile.append(zusatz.strip())
    return ", ".join(teile)


def karte_ansicht(roh: dict | None, *, ort: str | None,
                  besetzung: list[tuple[str, str | None]], zusatz: str | None,
                  fragen_offen: list[str], fragen_vertagt: list[str],
                  punkt_offen: str = "[OPEN] {frage}") -> dict | None:
    if roh is None:
        return None
    karte = roh_ohne_struktur(roh)
    karte["ort"] = (ort or "").strip()
    karte["wer"] = wer_text(besetzung, zusatz)
    karte["punkte"] = [p for p in (karte.get("punkte") or [])
                       if not OFFEN_PUNKT.match(str(p))] + [
        punkt_offen.format(frage=f) for f in fragen_vertagt]
    karte["fragen"] = list(fragen_offen)
    return karte
