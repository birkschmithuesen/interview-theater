"""Der EN/IT-Spiegelpass fuer die Szenenprosa (Birk, Live-Workshop
07.10.2026 ~17:20): "Das Skript soll immer zweisprachig kommen, Englisch /
Italienisch. Aber nicht gemischt, so wie es gerade ist."

Padua laeuft auf Englisch (``[sprache] code = "en"``), die Interviews aber
auf Italienisch (``[sprache] whisper = "auto"``) -- ein Szenentext, der
woertliche Interviewzitate traegt, ist damit ein Mischtext. Dieser Pass
laeuft NUR unter dem Profilschalter ``[skript] zweisprachig``
(``workshop.skript_zweisprachig_aktiv``) und nur nach einem fertigen
Szenentext (``szene.schreibe``, Phase 5 Prosa). Er nimmt die gerade
geschriebene ``prosa`` und laesst sie vom selben Modellweg (Kimi, mit
Opus-Fallback wie jeder andere Schema-Aufruf -- ``modellwahl.aufruf_schema``)
in zwei saubere Fassungen spiegeln:

* ``prosa_en`` ersetzt ``szene.prosa`` -- komplett Englisch, Interviewzitate
  ins Englische uebertragen. Jeder Prompt und jede Pruefung danach liest
  weiterhin ``prosa``, also EN, ohne etwas zu aendern.
* ``prosa_it`` geht nach der neuen Spalte ``szene.prosa_it`` -- komplett
  Italienisch, Interviewzitate im italienischen Original-Wortlaut.

**Darf den Szenenlauf nie kaputt machen**: ``spiegel()`` faengt jeden
Fehler selbst (Modellfehler, kein JSON, leere Antwort) und loggt ihn als
Vorfall -- der einzige Aufrufer (``szene.schreibe``) ruft sie ohnehin unter
einem eigenen ``try/except``, diese zweite Sicherung gilt fuer Aufrufer, die
das vergessen."""

from __future__ import annotations

import logging

from interview_theater import anweisungen, modellwahl, repo, workshop

log = logging.getLogger(__name__)

#: Erkenner-art in der Tabelle ``aufruf`` -- eigene Zeile, damit sich die
#: Kosten des Spiegelpasses von denen des Szenenlaufs trennen lassen.
ART = "skript_spiegel"

#: Modus A (Schema): zwei vollstaendige Fassungen, kein Drittfeld. ``strict``
#: verlangt beide Schluessel in jeder Antwort.
SCHEMA = {
    "type": "object",
    "properties": {
        "prosa_en": {
            "type": "string",
            "description": (
                "The whole scene text, entirely in English. Any quoted "
                "interview lines are translated into English; keep an "
                "interview number if one is present in the source text."
            ),
        },
        "prosa_it": {
            "type": "string",
            "description": (
                "The whole scene text, entirely in Italian. Any quoted "
                "interview lines stay in their original Italian wording, "
                "unchanged."
            ),
        },
    },
    "required": ["prosa_en", "prosa_it"],
    "additionalProperties": False,
}


#: Eine Uebertragung ist ungefaehr so lang wie die Quelle. Tester 08.10.2026
#: 12:12: Opus brach zweimal ab, der Kimi-Fallback lieferte einen fremden
#: 1 100-Zeichen-Text statt der 5 500-Zeichen-Szene -- und der Nachholpass
#: ueberschrieb damit EN UND IT. Ausserhalb dieses Bandes wird verworfen.
LAENGE_MIN, LAENGE_MAX = 0.6, 1.7


#: Mit Zitat-Uebersetzung (unten) kann die EN-Fassung bis gut doppelt so
#: lang werden -- eine Szene, die fast nur aus Zitaten besteht (G3 S2).
LAENGE_MAX_MIT_UEBERSETZUNG = 2.6

#: Birk 08.10.2026 ~14:25 (G3 S2: in der EN-Ansicht blieb fast alles
#: italienisch, weil die Szene nur aus Interviewzitaten besteht): in der
#: EN-Fassung steht unter jedem Zitat in anderer Sprache die englische
#: Uebersetzung. Gespielt wird das Original; die IT-Fassung bleibt ohne.
ZUSATZ_ZITAT_UEBERSETZUNG = (
    "\n\nAdditionally, ONLY in prosa_en: directly below every line or passage that is "
    "not in English (interview quotes in their original wording), add one line with "
    "its English translation, in italics and in parentheses, like this:\n"
    "VOCE 4: Mi pare che fossi sul divano dopo pranzo.\n"
    "*(I think I was on the sofa after lunch.)*\n"
    "The original line stays exactly as it is and is what is performed. Do not add "
    "translations to prosa_it."
)


def plausibel(quelle: str, uebertragung: str, max_faktor: float | None = None) -> bool:
    q = len((quelle or "").strip())
    if q < 200:
        return True
    hoch = LAENGE_MAX if max_faktor is None else max_faktor
    return LAENGE_MIN * q <= len((uebertragung or "").strip()) <= hoch * q


def spiegle_text(conn, klm, e, chat_id: int, text: str, *,
                 ueber_claude: bool) -> tuple[str, str] | None:
    """Derselbe Spiegelpass fuer einen beliebigen Szenentext (Stage Script,
    Padua-Phasenumbau 07.10.2026 ~18:12): ``(en, it)`` oder ``None`` bei
    jedem Fehler (geloggt). Speichert nichts -- das tut der Aufrufer."""
    if not (text or "").strip():
        return None
    try:
        mit_uebersetzung = workshop.zitat_uebersetzung_en_aktiv()
        system = anweisungen.hole(ART) + (ZUSATZ_ZITAT_UEBERSETZUNG if mit_uebersetzung else "")
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system=system, nutzer=text,
            schema=SCHEMA, art=ART, ueber_claude=ueber_claude,
        )
        en = (ergebnis.get("prosa_en") or "").strip()
        it = (ergebnis.get("prosa_it") or "").strip()
        if not en or not it:
            raise ValueError("Spiegelpass ohne beide Fassungen zurueckgekommen")
        en_ok = plausibel(text, en, max_faktor=LAENGE_MAX_MIT_UEBERSETZUNG if mit_uebersetzung else LAENGE_MAX)
        if not en_ok or not plausibel(text, it):
            raise ValueError(
                f"Spiegelpass unplausibel (Quelle {len(text)}, EN {len(en)}, IT {len(it)} Zeichen)")
        return en, it
    except Exception:
        log.exception("Skript-Spiegelpass (Text) fehlgeschlagen, chat_id=%s", chat_id)
        return None


def spiegel(conn, klm, e, chat_id: int, szene_id: int, prosa_roh: str,
           *, ueber_claude: bool) -> bool:
    """Der eine Modellaufruf: ``prosa_roh`` (die gerade geschriebene Prosa,
    vermutlich mit italienischen Zitaten durchsetzt) wird in eine saubere
    EN- und eine saubere IT-Fassung gespiegelt und gespeichert.

    Liefert ``True`` bei Erfolg, ``False`` bei jedem Fehler (geloggt, nie
    geworfen) -- die Szene bleibt dann bei ihrer englischen Rohfassung
    stehen, ``prosa_it`` bleibt leer."""
    if not (prosa_roh or "").strip():
        return False
    try:
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id,
            system=anweisungen.hole(ART),
            nutzer=prosa_roh,
            schema=SCHEMA, art=ART, ueber_claude=ueber_claude,
        )
        prosa_en = (ergebnis.get("prosa_en") or "").strip()
        prosa_it = (ergebnis.get("prosa_it") or "").strip()
        if not prosa_en or not prosa_it:
            raise ValueError("Spiegelpass ohne beide Fassungen zurueckgekommen")
    except Exception:
        log.exception("Skript-Spiegelpass fehlgeschlagen, chat_id=%s, szene_id=%s",
                      chat_id, szene_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), "skript_spiegel_fehler",
                f"Szene {szene_id}: EN/IT-Spiegelpass fehlgeschlagen -- Szene bleibt EN-only",
            )
        except Exception:
            log.exception("Vorfall skript_spiegel_fehler nicht geschrieben")
        return False
    repo.setze_szene_uebersetzung(conn, szene_id, prosa_en, prosa_it)
    return True
