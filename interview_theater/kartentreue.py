"""Padua: Karte-Treue eines geschriebenen Buehnenscripts gegen die
abgenommene Szenenkarte (Phase 7, P7-Audit-Karte, Klassen 8b/9,
Birk 08.10.2026).

Zwei deterministische Pruefungen ueber den fertigen Text, kein Modellaufruf,
kein SQL -- der Aufrufer (``prueflauf.pruefe_szene``) liefert ``karte``
(``szenenkarte.karte_von``) und den geschriebenen Text:

* ``widersprueche`` (Klasse 8b, Live-Befund G2: Karte 3 verneinte
  ausdruecklich eine Angabe -- "senza dire che posto occupa nell'ordine di
  reclutamento" --, das gespeicherte Script nannte sie trotzdem woertlich).
  Ein Hakenpunkt, der mit einem Verneinungsmarker (``senza dire``,
  ``non dice``, ``without saying`` ...) etwas ausdruecklich ausschliesst,
  aber der ausgeschlossene Wortlaut steht trotzdem im Text.

* ``fehlende_stichworte`` (Klasse 9, Live-Befund G3: ein Kartenpunkt
  "OBBLIGATORIO (richiesta del gruppo): ... Millennium Bug ..." verlangte
  ausdruecklich ein Stichwort, das im gespeicherten Script fehlte). Jeder
  Punkt, der mit "OBBLIGATORIO" beginnt, nennt eine Liste von Stichworten
  (meist nach einem "--", sonst nach "su"/"about") -- wer davon fehlt im
  Text, kommt in die Rueckgabe.

Beide Pruefungen sind eine Teilmenge, kein Ersatz fuer den Richter (A10
Materialtreue): sie fangen nur den woertlichen, mechanisch pruefbaren Fall."""

from __future__ import annotations

import re


def _normalisiert(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def _kernform(wort: str) -> str:
    """Ohne Klammerzusatz ("Pietro Maso (Verona)" -> "Pietro Maso") -- die
    Karte haengt oft eine Ortsangabe an, die im Script fehlen darf, ohne dass
    das Stichwort selbst fehlt."""
    return re.sub(r"\s*\([^)]*\)\s*", " ", wort or "").strip()


# ---------------------------------------------------------------------------
# Klasse 8b: verneinte Hakenpunkte
# ---------------------------------------------------------------------------

_VERNEINUNG_MARKER = (
    r"senza\s+dire\s+che\s+", r"senza\s+dire\s+", r"non\s+dice\s+che\s+",
    r"non\s+dice\s+", r"without\s+saying\s+that\s+", r"without\s+saying\s+",
    r"doesn'?t\s+say\s+that\s+", r"doesn'?t\s+say\s+", r"does\s+not\s+say\s+",
)
_VERNEINUNG = re.compile(
    "(?:" + "|".join(_VERNEINUNG_MARKER) + r")(?P<inhalt>[^.;\n]+)",
    re.IGNORECASE,
)
#: Unter dieser Laenge ist ein "verneinter Inhalt" zu unspezifisch, um ihn
#: gegen den Text zu pruefen (z. B. ein blosses "das").
_MINDESTLAENGE = 4


def widersprueche(karte: dict, text: str) -> list[str]:
    """Verneinte Inhalte aus den Karten-Punkten, die trotzdem woertlich im
    Text stehen -- je ein Fund als lesbare Zeile (Punkt + Fundstelle)."""
    text_norm = _normalisiert(text)
    funde = []
    for punkt in (karte or {}).get("punkte") or []:
        for treffer in _VERNEINUNG.finditer(punkt or ""):
            inhalt = treffer.group("inhalt").strip(" .;,-")
            if len(inhalt) < _MINDESTLAENGE:
                continue
            if _normalisiert(inhalt) in text_norm:
                funde.append(f"{punkt.strip()} -- im Text trotzdem: „{inhalt}“")
    return funde


# ---------------------------------------------------------------------------
# Klasse 9: OBBLIGATORIO-Stichworte
# ---------------------------------------------------------------------------

_OBBLIGATORIO = re.compile(r"^\s*OBBLIGATORIO\b[^:]*:\s*(?P<rest>.+)$", re.IGNORECASE)
#: Fuellsaetze, die nur auf die beigefuegten Zitate der Karte verweisen
#: ("entrano anche le citazioni qui sotto su ...", "in questa scena entrano
#: TUTTE le citazioni qui sotto -- ..."), kein eigenes Stichwort.
_FUELLSATZ = re.compile(
    r"\b(tutte\s+)?le\s+citazioni\s+qui\s+sotto\b"
    r"|\bentrano\s+anche\b"
    r"|\bin\s+questa\s+scena\s+entrano\s+tutte\b",
    re.IGNORECASE,
)
_LISTENSTRICH = re.compile(r"\s(?:--|–|—)\s")
_TRENNER = re.compile(r",|\be\b|\band\b")


def _listensegment(rest: str) -> str:
    """Der Teil von ``rest``, der wirklich die Stichwortliste traegt -- nach
    dem letzten Listenstrich, sonst der ganze Rest ohne Fuellsatz und ohne
    ein fuehrendes "su"/"about"."""
    ohne_fuellsatz = _FUELLSATZ.sub(" ", rest)
    teile = _LISTENSTRICH.split(ohne_fuellsatz)
    segment = teile[-1] if len(teile) > 1 else ohne_fuellsatz
    return re.sub(r"^\s*(su|about)\s+", "", segment.strip(), flags=re.IGNORECASE)


def obbligatorio_stichworte(karte: dict) -> list[str]:
    """Alle Stichworte, die die OBBLIGATORIO-Punkte der Karte nennen --
    dedupliziert, in der Reihenfolge der Punkte."""
    gefunden: list[str] = []
    for punkt in (karte or {}).get("punkte") or []:
        treffer = _OBBLIGATORIO.match(punkt or "")
        if treffer is None:
            continue
        segment = _listensegment(treffer.group("rest"))
        for teil in _TRENNER.split(segment):
            wort = teil.strip(" .;-")
            if len(wort) >= 3 and wort not in gefunden:
                gefunden.append(wort)
    return gefunden


def fehlende_stichworte(karte: dict, text: str) -> list[str]:
    """Stichworte aus OBBLIGATORIO-Punkten, die im geschriebenen Text
    fehlen -- weder woertlich noch (ohne Klammerzusatz) in Kernform."""
    text_norm = _normalisiert(text)
    fehlend = []
    for wort in obbligatorio_stichworte(karte):
        if _normalisiert(wort) in text_norm:
            continue
        if _normalisiert(_kernform(wort)) in text_norm:
            continue
        fehlend.append(wort)
    return fehlend
