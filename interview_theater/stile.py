"""Die Stil-Vorlagen (06.09.2026, Birk 12:50).

**Warum es das gibt.** Bis heute hing ein Stil am *Bot*: eine
Overlay-Datei je Gruppe (``zusatz.<botname>.md``), die niemand waehlen
konnte -- die Gruppe bekam den Stil, den der Betreiber ihrem Bot mitgegeben
hatte. Birk im Wortlaut: *"alle Gruppen sollen auf alle Stile zugreifen
koennen, als Auswahl, mit Nennung des Originalmaterials."*

Der Stil haengt deshalb jetzt an der **Szene** (``szene.stil``, ein Slug)
und wird im Feinschliff gewaehlt -- direkt nach der Form, weil beides
zusammen entscheidet, wie der Text klingt.

**Die Herkunft steht dabei** und nicht nur der Name. Ein Stil ist hier eine
*Meta-Anleitung*, die aus einem konkreten Stueck Material abgeleitet wurde
(ein Rap-Video, eine Ballade, eine eigene Produktion). Wer waehlt, soll
wissen, woher das Mass kommt -- das ist eine Frage der Redlichkeit
gegenueber dem Material und zugleich die Sicherung gegen die
naheliegendste Verwechslung: uebernommen wird die **Bauweise**, nie der
Inhalt.

**Wirkt nur bei ``form != prosa``.** Die Prosafassung aus Phase 6 ist eine
Geschichte, kein Buehnentext; ein Rap-Mass darauf waere eine Regel ueber
eine Textsorte, die es hier nicht gibt.
"""

from __future__ import annotations

import logging
import re

from interview_theater import anweisungen

log = logging.getLogger(__name__)

#: Der Slug, der "kein Stil" bedeutet -- die Gruppe kann sich ausdruecklich
#: dagegen entscheiden, und das ist eine Wahl und kein Schweigen. In der
#: Datenbank steht dann NULL.
OHNE = "ohne"
TEXT_OHNE = "Ohne Stilvorlage"

#: Die Stile in der Reihenfolge, in der sie im Menue stehen. Je Eintrag:
#: Slug, Titel, ein Satz, Herkunft. Die Prompt-Datei dazu ist
#: ``prompts/stile/<slug>.md`` und wird heiss nachgeladen -- wer den Stil
#: schaerft, aendert die Datei, kein Neustart.
#:
#: Die Herkunft steht HIER und nicht nur in der Prompt-Datei: sie gehoert in
#: den Chat, wo die Gruppe waehlt, und nicht nur in den Prompt, den nur das
#: Modell liest.
STILE: tuple[dict[str, str], ...] = (
    {
        "slug": "schlagabtausch",
        "titel": "Knapper Schlagabtausch",
        "satz": (
            "Kurze Zeilen, harte Schnitte, ein Hook, der wiederkommt - "
            "Ich-an-Du, viel Verneinung."
        ),
        "herkunft": "Schatten - Morpheuz x Monet192 (YouTube)",
    },
    {
        "slug": "litanei",
        "titel": "Litanei",
        "satz": (
            "Eine Satzschablone, immer wieder, mit einem Wort, das wechselt - "
            "die Steigerung liegt in der Haeufigkeit."
        ),
        "herkunft": "Lovesong - Adele (YouTube)",
    },
    {
        "slug": "herkules",
        "titel": "Herkules-Mass",
        "satz": (
            "Das gemessene Mass unserer eigenen Produktion: kurze Repliken, "
            "wenig Regie, keine weitere Stilverschiebung."
        ),
        "herkunft": "Herkules.exe - ArtesMobiles (eigene Produktion)",
    },
)

#: Welcher Stil zu welcher Form vorgeschlagen wird (Birk, 06.09.2026 12:50).
#: Ein **Vorschlag**, keine Vorentscheidung: gesetzt wird der Stil allein
#: durch die Auswahl der Gruppe -- dieselbe Regel wie beim Formvorschlag
#: (``form_vorschlag``, 06.09.2026 00:30).
VORSCHLAG: dict[str, str] = {
    "rap": "schlagabtausch",
    "lied": "litanei",
    "chor": "litanei",
    "dialog": "herkules",
    "monolog": "herkules",
}

#: Warum -- eine Zeile, die im Chat ueber dem Menue steht. Ohne Begruendung
#: waere der Vorschlag eine Ansage.
VORSCHLAG_GRUND: dict[str, str] = {
    "rap": "Zu einem Rap passt der knappe Schlagabtausch: kurze Zeilen, ein Hook.",
    "lied": "Zu einem Lied passt die Litanei: eine Zeile, die wiederkommt.",
    "chor": "Ein Chor lebt von der Wiederholung - dafuer ist die Litanei gebaut.",
    "dialog": "Fuer einen Dialog bleibt es beim Herkules-Mass, unserem eigenen.",
    "monolog": "Fuer einen Monolog bleibt es beim Herkules-Mass, unserem eigenen.",
}

_NACH_SLUG = {s["slug"]: s for s in STILE}


def alle() -> tuple[dict[str, str], ...]:
    """Alle Stile, fuer jede Gruppe dieselben."""
    return STILE


def hole(slug: str | None) -> dict[str, str] | None:
    """Der Stil zu einem Slug, oder None (unbekannt, leer oder ``ohne``)."""
    schluessel = (slug or "").strip().lower()
    if not schluessel or schluessel == OHNE:
        return None
    return _NACH_SLUG.get(schluessel)


def ist_bekannt(slug: str | None) -> bool:
    """Darf dieser Wert in ``szene.stil``? ``ohne``/leer zaehlt mit -- das
    ist die ausdrueckliche Abwahl."""
    schluessel = (slug or "").strip().lower()
    return not schluessel or schluessel == OHNE or schluessel in _NACH_SLUG


def vorschlag_fuer(form: str | None) -> tuple[str | None, str]:
    """``(Slug, Begruendung)`` fuer eine Form -- oder ``(None, "")``, wenn es
    zu dieser Form keinen Vorschlag gibt."""
    schluessel = (form or "").strip().lower()
    return VORSCHLAG.get(schluessel), VORSCHLAG_GRUND.get(schluessel, "")


def beschriftung(slug: str) -> str:
    """Der Titel eines Stils -- fuer Knopf und Dropdown."""
    eintrag = _NACH_SLUG.get(slug)
    return eintrag["titel"] if eintrag else slug


def herkunft(slug: str) -> str:
    """Woher das Mass kommt. Leer, wenn der Slug unbekannt ist."""
    eintrag = _NACH_SLUG.get(slug)
    return eintrag["herkunft"] if eintrag else ""


def menuetext(vorschlag: str | None = None, grund: str = "") -> str:
    """Die EINE Nachricht "Welcher Stil?" -- fetter Titel, ein Satz,
    Herkunft, je Stil.

    Ein Menue und keine sechs Nachrichten: die Gruppe soll die Stile
    nebeneinander lesen koennen, das ist der Sinn einer Auswahl. Der
    Vorschlag steht ZUERST und traegt "(Vorschlag)" -- sichtbar ein
    Vorschlag, keine Vorentscheidung."""
    reihenfolge = list(STILE)
    if vorschlag and vorschlag in _NACH_SLUG:
        eintrag = _NACH_SLUG[vorschlag]
        reihenfolge.remove(eintrag)
        reihenfolge.insert(0, eintrag)
    zeilen = ["Welcher Stil?"]
    if grund.strip():
        zeilen.append(grund.strip())
    for nummer, eintrag in enumerate(reihenfolge, start=1):
        marke = " (Vorschlag)" if eintrag["slug"] == vorschlag else ""
        zeilen.append(
            f"{nummer}. **{eintrag['titel']}**{marke}\n"
            f"{eintrag['satz']}\n"
            f"Vorlage: {eintrag['herkunft']}"
        )
    zeilen.append(
        f"{len(reihenfolge) + 1}. **{TEXT_OHNE}**\n"
        "Es bleibt bei den Regeln der Form."
    )
    return "\n\n".join(zeilen)


def reihenfolge_mit_vorschlag(vorschlag: str | None) -> list[dict[str, str]]:
    """Dieselbe Reihenfolge wie ``menuetext`` -- damit Knopf N und Punkt N
    dasselbe meinen. Getrennte Listen waeren genau der Fehler, den die
    Menue-Knopfregel (AGENTS.md, 06.09.2026 11:05) verhindert."""
    reihenfolge = list(STILE)
    if vorschlag and vorschlag in _NACH_SLUG:
        eintrag = _NACH_SLUG[vorschlag]
        reihenfolge.remove(eintrag)
        reihenfolge.insert(0, eintrag)
    return reihenfolge


#: Der Kommentarkopf der Prompt-Datei (``<!-- ... -->``) gehoert nicht in den
#: Prompt: er sagt dem Menschen, woher die Kopie stammt.
_KOPFKOMMENTAR = re.compile(r"<!--.*?-->", re.DOTALL)


def regelblock(slug: str | None) -> str:
    """Der Stil-Block fuer den Szenen-Prompt, heiss nachgeladen -- oder ``""``.

    Leer bei ``ohne``, bei unbekanntem Slug und wenn die Datei fehlt: ein
    fehlender Stil ist kein Grund, keine Szene zu schreiben (dieselbe Haltung
    wie ``anweisungen.hole_optional`` bei den Phasendateien)."""
    eintrag = hole(slug)
    if eintrag is None:
        return ""
    text = anweisungen.hole_optional(f"stile/{eintrag['slug']}")
    if not text or not text.strip():
        log.error("Stil-Datei fehlt: stile/%s.md", eintrag["slug"])
        return ""
    return _KOPFKOMMENTAR.sub("", text).strip()
