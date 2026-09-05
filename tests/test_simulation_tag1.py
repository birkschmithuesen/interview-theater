"""Die Stimmen-Sets aus dem echten Tag 1 -- vor allem: ist da PII drin?

Der harte Test ist ``test_keine_wortfolge_aus_einem_echten_transkript``: er
liest die Betriebsdatenbank **read-only** und prueft, dass keine Achtwortfolge
aus einem echten Transkript in den abgeleiteten Dateien steht. Fehlt die
Datenbank (Entwicklungsrechner, CI), wird uebersprungen -- ein Test, der ohne
sie durchfaellt, wuerde niemanden schuetzen und alle nerven.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from simulation import stimmen, tag1

#: Die Betriebsdatenbanken. Sie liegen ausserhalb des Repositories und
#: werden hier ausschliesslich ``mode=ro`` geoeffnet.
BETRIEB = Path(
    "/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb"
)

#: Die Dateien, die aus Tag 1 abgeleitet sind und deshalb geprueft werden.
ABGELEITET = [
    Path(tag1.__file__),
    *(stimmen.VERZEICHNIS / f"{b.schluessel}.md" for b in stimmen.TAG1),
]

#: Wie lang eine Wortfolge sein muss, damit ihr Auftauchen kein Zufall ist.
#: Acht: drei bis vier Woerter kommen in jedem deutschen Text vor ("und dann
#: hat sie"), acht sind ein Zitat.
FOLGE = 8

#: Namen, die stehen bleiben duerfen: der Autor selbst. Birk ist als
#: Workshopleiter auch in ``soap.db`` Absender, und in ``simulation/tag1.py``
#: steht sein Name als **Quellenangabe** ("aus Birks eigenen Nachrichten
#: abgeleitet, er ist ihr Autor"). Diese Zeile ist genau das Gegenteil eines
#: PII-Lecks: sie sagt, woher etwas kommt.
AUTOR = {"birk"}


def _folgen(text: str, laenge: int = FOLGE) -> set[str]:
    worte = text.lower().split()
    return {
        " ".join(worte[i:i + laenge])
        for i in range(max(0, len(worte) - laenge + 1))
    }


def _transkripte() -> list[str]:
    """Alle echten Transkripte, read-only gelesen. Leere Liste, wenn die
    Datenbanken fehlen."""
    texte = []
    for name in ("soap.db", "test.db"):
        pfad = BETRIEB / name
        if not pfad.is_file():
            continue
        conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        try:
            for (roh,) in conn.execute(
                "SELECT transkript FROM aufnahme WHERE transkript IS NOT NULL"
            ):
                if (roh or "").strip():
                    texte.append(roh)
        finally:
            conn.close()
    return texte


def test_alle_tag1_steckbriefe_sind_registriert_und_ladbar():
    for brief in stimmen.TAG1:
        text = stimmen.lade_profil(brief.schluessel)
        assert text.strip()
        assert "NICHT" in text, brief.schluessel


def test_jedes_set_hat_begriffe_fragen_und_ein_interviewset():
    for name in tag1.SETS:
        assert tag1.begriffe(name)
        assert tag1.fragen(name)
        assert tag1.interviewset(name) in (1, 2, 3)
        assert tag1.aggregat(name).nachrichten > 0


def test_referenz_traegt_nur_zahlen_und_stichworte():
    """Der Referenzblock geht in den Bericht -- dort darf kein Wortlaut
    stehen. Alles darin ist entweder eine Zahl, ein Begriff der Gruppe oder
    ein Themenstichwort von hoechstens vier Woertern."""
    for name in tag1.SETS:
        ref = tag1.referenz(name)
        for thema in ref["themen"]:
            assert len(thema.split()) <= 4, thema
        for begriff in ref["begriffe"]:
            assert len(begriff.split()) <= 2, begriff


def test_keine_wortfolge_aus_einem_echten_transkript():
    transkripte = _transkripte()
    if not transkripte:
        pytest.skip("keine Betriebsdatenbank -- nichts zu vergleichen")
    verboten: set[str] = set()
    for text in transkripte:
        verboten |= _folgen(text)
    assert verboten, "Transkripte da, aber keine Achtwortfolgen darin?"
    for datei in ABGELEITET:
        gefunden = _folgen(datei.read_text(encoding="utf-8")) & verboten
        assert not gefunden, f"{datei.name}: Wortlaut aus einem Transkript: {gefunden}"


def test_keine_teilnehmerinnennamen_in_den_abgeleiteten_dateien():
    """Kein Absendername aus einer echten Gruppe darf in den Steckbriefen
    stehen. Auch das nur, wenn die Datenbank da ist.

    ``betrieb/soap.db`` traegt die drei Gruppen; ``test.db`` ist Birks eigene
    Testgruppe und wird hier bewusst **nicht** geprueft -- er ist Autor
    seiner Nachrichten, und sein Name steht in ``simulation/tag1.py`` als
    Quellenangabe."""
    pfad = BETRIEB / "soap.db"
    if not pfad.is_file():
        pytest.skip("keine Betriebsdatenbank")
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    try:
        namen = {
            (n or "").strip()
            for (n,) in conn.execute(
                "SELECT DISTINCT absender FROM nachricht WHERE ist_bot = 0"
            )
            if (n or "").strip() and len(str(n).strip()) > 2
        }
    finally:
        conn.close()
    namen = {n for n in namen if n.lower() not in AUTOR}
    assert namen, "keine Namen zu pruefen -- der Test misst nichts"
    for datei in ABGELEITET:
        text = datei.read_text(encoding="utf-8").lower()
        for name in namen:
            assert name.lower() not in text, f"{datei.name}: Name {name!r}"
