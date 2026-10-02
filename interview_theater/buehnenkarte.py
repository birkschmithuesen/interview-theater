"""Die Buehnenkarte des Brainstorm-Modus (Phase 4, nur Web, 02.10.2026).

Ein Aufruf, ein Text (oder NICHTS). Reuses ``szene_claude.prosa`` fuer den
Claude-Pfad (mit Einwilligung, dasselbe ``szene_claude.ist_aktiv``) und
``llm.LLM.prosa`` (Infomaniak, Modus B) ohne -- derselbe Verzweigungscode wie
in ``szene.py``, Kostenbuchung und Reasoning bleiben also in diesen beiden
Funktionen. Dieses Modul fuegt nur den Prompt, das eigene Transkript-Budget
und die Stueckkarte als Kontext hinzu.

Kein Modellaufruf in einem Knopf-Handler (Zusage 2) -- das gilt hier
unveraendert: ``erzeuge()`` wird aus ``brainstorm.py``s Trigger-Verdrahtung
in einem eigenen Thread gerufen, nie inline in einer Anfrage."""

import logging
import os

import httpx

from interview_theater import anweisungen, repo, szene_claude

log = logging.getLogger(__name__)

#: Die Sentinel-Antwort, mit der das Modell sagt "keine Karte jetzt" --
#: bewusst das deutsche Wort, auch in der englischen Prompt-Fassung
#: (sprachen/en/prompts/buehnenkarte.md): es ist ein interner Code-Vergleich,
#: kein Text, den die Gruppe je sieht.
NICHTS = "NICHTS"

#: Grosszuegig, aber endlich -- eine Karte ist eine Zugabe, kein Szenenlauf
#: mit Reasoning. Kein eigener Thread-Timeout noetig wie bei szene.py, weil
#: der Aufrufer (brainstorm.py) ohnehin schon in einem eigenen Thread laeuft.
TIMEOUT_S = 120.0
MAX_TOKENS = 4000

VORGABE_TRANSKRIPT_ZEICHEN = 200_000


def transkript_zeichen_grenze() -> int:
    """``IT_BRAINSTORM_TRANSKRIPT_ZEICHEN`` -- eigenes, viel groesseres
    Budget als das normale Gespraechsfenster (``kontext.ZEICHEN_GRENZE_VORGABE``
    = 24.000): eine Buehnenkarte soll den ganzen bisherigen Bogen sehen, der
    Prompt-Prefix soll dabei cache-stabil bleiben (nur anhaengen, nie
    umschreiben)."""
    roh = (os.environ.get("IT_BRAINSTORM_TRANSKRIPT_ZEICHEN") or "").strip()
    if roh.isdigit() and int(roh) > 0:
        return int(roh)
    return VORGABE_TRANSKRIPT_ZEICHEN


def _kontext_phasen_1_bis_3(conn, chat_id: int) -> str:
    """Begriffe und die (vom Modell formulierten) Interviewfragen -- NIE
    Interviewmaterial, Phase 4 ist absichtlich interview-frei."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return ""
    zeilen = []
    if stand["begriffe"]:
        zeilen.append(f"Begriffe: {stand['begriffe']}")
    if stand["fragen"]:
        zeilen.append(f"Fragen: {stand['fragen']}")
    return "\n".join(zeilen)


def _stueckkarte_text(conn, chat_id: int) -> str:
    zeilen = []
    for name, wert in repo.stueckkarte_felder(conn, chat_id):
        zeilen.append(f"{name}: {wert}" if wert else f"{name}: (noch offen)")
    for zeile in repo.festlegungen(conn, chat_id):
        zeilen.append(
            repo.festlegungszeile(zeile["bereich"], zeile["bezug"], zeile["text"])
        )
    return "\n".join(zeilen)


def _nutzertext(conn, chat_id: int) -> str:
    transkript = repo.brainstorm_transkript(conn, chat_id)
    grenze = transkript_zeichen_grenze()
    if len(transkript) > grenze:
        vorher = len(transkript)
        # Aelteste zuerst weg -- derselbe Grundsatz wie beim normalen
        # Gespraechsfenster (kontext.py): das Jetzt wiegt mehr als der Anfang.
        transkript = transkript[-grenze:]
        try:
            repo.merke_vorfall(
                conn, chat_id, None, "brainstorm_transkript_gekuerzt",
                f"Brainstorm-Transkript von {vorher} auf {len(transkript)} "
                f"Zeichen gekuerzt (Grenze {grenze})",
            )
        except Exception:
            log.exception("Vorfall brainstorm_transkript_gekuerzt nicht geschrieben")

    teile = []
    kontext_1_3 = _kontext_phasen_1_bis_3(conn, chat_id)
    if kontext_1_3:
        teile.append(f"Begriffe und Fragen (Phase 1-3):\n{kontext_1_3}")
    stueckkarte = _stueckkarte_text(conn, chat_id)
    if stueckkarte:
        teile.append(f"Stueckkarte:\n{stueckkarte}")
    teile.append(f"Mitschnitt des Brainstormings bisher:\n{transkript}")
    return "\n\n".join(teile)


def erzeuge(conn, e, klm, chat_id: int) -> tuple[str | None, str]:
    """Erzeugt eine Buehnenkarte. Liefert ``(text, modell)``, oder
    ``(None, modell)``, wenn das Modell ``NICHTS`` antwortete oder der
    Aufruf scheiterte.

    Ein Scheitern bleibt fuer die Gruppe unsichtbar (wie ein gescheiterter
    Nachpass, AGENTS.md § 11.1): Phase 4 ist eine Zugabe, niemand wartet auf
    eine Karte und niemand muss auf einen Fehler reagieren -- dafuer ein
    Vorfall fuers Dashboard."""
    system = anweisungen.hole("buehnenkarte")
    nutzer = _nutzertext(conn, chat_id)
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    modell = "claude" if ueber_claude else "infomaniak"
    try:
        if ueber_claude:
            klient = getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S)
            antwort = szene_claude.prosa(
                conn, e, klient, chat_id, system, nutzer, "brainstorm_karte",
                timeout=TIMEOUT_S,
            )
        else:
            antwort = klm.prosa(
                chat_id, system, nutzer, "brainstorm_karte",
                max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
            )
    except Exception:
        log.exception("Buehnenkarte fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "buehnenkarte_fehlgeschlagen", f"modell={modell}",
            )
        except Exception:
            log.exception("Vorfall buehnenkarte_fehlgeschlagen nicht geschrieben")
        return None, modell

    text = (antwort or "").strip()
    if not text or text.upper() == NICHTS:
        return None, modell
    return text, modell
