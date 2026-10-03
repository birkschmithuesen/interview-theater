"""Die CoThinker-Tafel darf nie eine leere Ueberschrift/Label ausliefern,
nie "offen"/"open" zeigen, und bei mehreren Karten nie mehr als eine
sichtbar darstellen (Task 1, Padua CoThinker-Tab clean, 03.10.2026).

``_buehne_html(daten)`` nimmt dafuer einen reinen Dict -- keine Datenbank
noetig, das ist genau der Punkt dieser Tests (Brief, Abschnitt "Tests").
"""

import re
from datetime import datetime, timezone

from interview_theater import web

_JETZT = datetime.now(timezone.utc).isoformat()

# -- Die vier geforderten Zustaende -----------------------------------------

LEER: dict = {}

HOERT_ZU_SCHWEIGEN: dict = {
    # Der juengste (und einzige) Eintrag ist ein Schweigen -- keine echte
    # Karte, aber die Statuszeile greift (dieselbe Erkennung wie vor dem
    # Umbau, siehe web._buehne_status_text).
    "buehnenkarten": [
        {"id": 1, "text": "", "schweigen": 1, "erstellt_am": _JETZT},
    ],
}

EINE_KARTE: dict = {
    "buehnenkarten": [
        {"id": 5, "text": "Ein erster Gedanke.", "schweigen": 0, "erstellt_am": _JETZT},
    ],
}

# NEUESTE ZUERST, wie web_daten.buehnenkarten es liefert.
VIER_KARTEN: dict = {
    "buehnenkarten": [
        {"id": 9, "text": "Vierter Gedanke.", "schweigen": 0, "erstellt_am": _JETZT},
        {"id": 8, "text": "Dritter Gedanke.", "schweigen": 0, "erstellt_am": _JETZT},
        {"id": 7, "text": "Zweiter Gedanke.", "schweigen": 0, "erstellt_am": _JETZT},
        {"id": 6, "text": "Erster Gedanke.", "schweigen": 0, "erstellt_am": _JETZT},
    ],
}

ALLE_ZUSTAENDE = {
    "leer": LEER,
    "hoert_zu_schweigen": HOERT_ZU_SCHWEIGEN,
    "eine_karte": EINE_KARTE,
    "vier_karten": VIER_KARTEN,
}


# -- 1. Keine leere Ueberschrift/kein leeres Label ---------------------------
#
# ``_buehne_html`` traegt heute GAR KEINE <h1>-<h6>/<summary>-Tags -- der
# Test ist fuer alle vier Zustaende also vacuously erfuellt. Das ist richtig
# (der Brief sagt das ausdruecklich), aber damit der Check selbst nicht
# zahnlos ist, zeigt der Mutant unten, dass er eine wirklich leere
# Ueberschrift auch findet.

_TAG_RE = re.compile(r"<(h[1-6]|summary)\b[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)


def _leere_ueberschriften(ausgabe: str) -> list[str]:
    """Tags, deren Textinhalt (nach Entfernen verschachtelter Tags) leer
    ist -- nicht nur eine Zaehlung der Tags selbst."""
    treffer = []
    for m in _TAG_RE.finditer(ausgabe):
        inhalt = re.sub(r"<[^>]*>", "", m.group(2)).strip()
        if not inhalt:
            treffer.append(m.group(0))
    return treffer


def test_keine_leere_ueberschrift_in_keinem_zustand():
    for name, daten in ALLE_ZUSTAENDE.items():
        ausgabe = web._buehne_html(daten)
        assert _leere_ueberschriften(ausgabe) == [], (
            f"{name}: leere Ueberschrift in {ausgabe!r}"
        )
    # Kein <h1>-<h6>/<summary> ueberhaupt in diesem Panel -- die Pruefung
    # oben ist also vacuously erfuellt. Das haelt genau das fest, damit es
    # niemand als Luecke liest (Brief: "note it in the report").
    for daten in ALLE_ZUSTAENDE.values():
        assert not re.search(r"<(h[1-6]|summary)\b", web._buehne_html(daten))


def _mutierte_ausgabe_mit_leerer_ueberschrift(daten: dict) -> str:
    """Lokaler Mutant NUR fuer diesen Test (lebt nie in Produktionscode):
    haengt eine leere Ueberschrift an eine sonst gueltige Ausgabe, um zu
    zeigen, dass ``_leere_ueberschriften`` so etwas wirklich findet."""
    return web._buehne_html(daten) + "<h2></h2>"


def test_der_mutant_mit_leerer_ueberschrift_faellt_durch():
    kaputt = _mutierte_ausgabe_mit_leerer_ueberschrift(LEER)
    assert _leere_ueberschriften(kaputt) == ["<h2></h2>"]


# -- 2. Nie "offen"/"open" ----------------------------------------------------


def test_nie_offen_oder_open_in_keinem_zustand():
    for name, daten in ALLE_ZUSTAENDE.items():
        ausgabe = web._buehne_html(daten)
        assert "offen" not in ausgabe, name
        assert "open" not in ausgabe, name


# -- 3. Bei 4 Karten genau eine sichtbare Tafel ------------------------------


def test_vier_karten_zeigen_genau_eine_sichtbare_tafel():
    ausgabe = web._buehne_html(VIER_KARTEN)
    assert ausgabe.count('id="buehne-tafel"') == 1

    # Die drei AELTESTEN Karten sind keine zweite sichtbare Karte mehr --
    # sie duerfen nur noch im JSON-Verlaufsbaustein stehen.
    vor_dem_baustein = ausgabe.split('<script type="application/json"')[0]
    aelteste_drei = [k["text"] for k in VIER_KARTEN["buehnenkarten"][1:]]
    for text in aelteste_drei:
        assert text not in vor_dem_baustein
        # ... aber im Baustein selbst stehen sie, als Verlaufsdaten.
        assert text in ausgabe

    # Keine Karte steckt in einem eigenen sichtbaren <div class="karte...">
    # -- die alte Markup-Form ist komplett weg.
    assert '<div class="karte' not in ausgabe
