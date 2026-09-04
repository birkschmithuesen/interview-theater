"""Belegzitat-Pruefung (SPEC-kontext-architektur.md § 5, global-constraints.md).

Eine Regel: Kommt das Zitat nach Normalisierung woertlich im Transkript vor,
ja oder nein. Normalisieren heisst Whitespace-Folgen zu einem Leerzeichen und
typografische Anfuehrungszeichen auf gerade, sonst nichts -- danach ein
einfacher Teilstring-Vergleich.

Bewusst **kein** Zerlegen an ``[...]``, **keine** Reihenfolge- oder
Abstandspruefung, **kein** Retry. Eine fruehere Fassung hatte all das und
schuetzte damit gegen ein einziges Vorkommnis in neun Messlaeufen -- und
konnte selbst faelschlich ablehnen, was am Workshoptag genauso schlecht ist
wie ein zusammengeklebtes Zitat. Siehe § 5 fuer die ausfuehrliche Begruendung.
"""

import re
import unicodedata

_ERSETZUNGEN = str.maketrans({"„": '"', "“": '"', "”": '"', "»": '"', "«": '"',
                              "‚": "'", "‘": "'", "’": "'", " ": " "})


def normalisiere(text: str) -> str:
    """Whitespace-Folgen zu einem Leerzeichen, typografische Anfuehrungszeichen
    auf gerade. Sonst nichts (§ 5)."""
    text = unicodedata.normalize("NFC", text or "").translate(_ERSETZUNGEN)
    return re.sub(r"\s+", " ", text).strip()


def pruefe(zitat: str, transkript: str) -> bool:
    """Teilstring-Vergleich nach beidseitiger Normalisierung. Umschliessende
    Anfuehrungszeichen im Zitat werden zusaetzlich entfernt, weil das Modell
    sie oft mitliefert, obwohl sie im Transkript selbst nicht stehen."""
    z, t = normalisiere(zitat).strip('"\''), normalisiere(transkript)
    return bool(z) and bool(t) and z in t
