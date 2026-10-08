"""Deterministische Sprachmessung: englischer Anteil in Bot-Texten
(P7-Audit-Karte, Klasse 5 -- Englisch an italienische Gruppen).

Stoppwortzaehlung, kein Modellaufruf, kein SQL. ``ist_englisch`` zaehlt
englische gegen italienische Funktionswoerter in einem Text; ``anteil_englisch``
den Anteil als-englisch erkannter Texte in einer Liste. Das Werkzeug fuer die
Messung gegen eine echte Datenbank ist ``scripts/miss_italienisch.py`` (nur
gegen eine Kopie, nie gegen die Live-Datenbank, AGENTS.md)."""

from __future__ import annotations

import re

_WORT_MUSTER = re.compile(r"[a-zA-Zàèéìòùá-ÿ']+")

#: Funktionswoerter, die in praktisch jedem laengeren Satz vorkommen -- kein
#: Vokabular, das auch als Eigenname oder in einem woertlichen Zitat auftaucht.
_ENGLISCHE_WOERTER = frozenset({
    "the", "and", "you", "your", "is", "are", "this", "that", "with", "for",
    "what", "will", "have", "has", "of", "to", "in", "on", "as", "be",
    "not", "when", "how", "works", "tap", "start", "stop", "send", "then",
    "after", "each", "one", "get", "tell", "me", "whether", "voice",
    "message", "stays", "true", "order", "places", "around", "table",
})
_ITALIENISCHE_WOERTER = frozenset({
    "il", "la", "lo", "gli", "le", "di", "che", "per", "con", "non", "una",
    "uno", "sono", "nella", "nel", "scena", "copione", "ecco", "questo",
    "questa", "cosa", "deve", "cambiare", "va", "bene", "così", "altrimenti",
    "dimmi", "sto", "riscrivendo", "già", "tutto", "come", "dove", "quando",
    "poi", "qui", "di", "lì",
})

#: Ab wie vielen eindeutig englischen Treffern UND klarem Uebergewicht
#: gegenueber italienischen Treffern gilt ein Text als englisch -- ein
#: einzelnes Fremdwort (ein Zitat, ein Knopfname wie "Yes, save") soll keinen
#: Treffer ausloesen.
_MINDESTTREFFER = 3


def ist_englisch(text: str) -> bool:
    """Grobe, deterministische Einordnung: ueberwiegend englische
    Funktionswoerter, ohne italienisches Gegengewicht."""
    woerter = [w.lower() for w in _WORT_MUSTER.findall(text or "")]
    englisch = sum(1 for w in woerter if w in _ENGLISCHE_WOERTER)
    italienisch = sum(1 for w in woerter if w in _ITALIENISCHE_WOERTER)
    return englisch >= _MINDESTTREFFER and englisch > italienisch


def anteil_englisch(texte: list[str]) -> float:
    """Anteil der als englisch erkannten Texte -- ``0.0`` ohne Texte."""
    if not texte:
        return 0.0
    return sum(1 for t in texte if ist_englisch(t)) / len(texte)
