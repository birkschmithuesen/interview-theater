"""Phase 7, Ort/Figuren-Nachzug (Padua, Birk 08.10.2026 ~12:50, Profilschalter
``[karten] p7_meta_nachziehen``).

In Phase 7 kann die Gruppe per "No, change" Ort oder Figuren einer Szene
aendern, auch neue Figuren einfuehren ("uno spettatore viene chiamato sul
palco"). Das Stage Script (``stagescript.py``) wird dafuer korrekt neu
geschrieben -- der Szenenkopf (Script-Tab/PDF/Partitur, ``szene.karte``)
kommt aber aus der Karte und blieb bisher alt, und Folgeszenen bekamen die
alte Karte weiter als "bindend" in den Prompt.

``ziehe_nach`` laeuft NACH jedem erfolgreich gespeicherten Skripttext
(``stagescript.schreibe``, eigener Hintergrund-Thread, bremst das Tempo der
Gruppe nicht): EIN kurzer Modellaufruf liest aus dem neuen EN-Text, wie Ort/
Figuren (ggf. Modus) jetzt sind. Nur wenn sich das normalisiert wirklich von
der Karte unterscheidet, wird die Karte aktualisiert (nur diese Felder, die
Abnahme bleibt stehen -- ``repo.aktualisiere_szenenkarte_meta``) und eine neue
Fassung an ``karte_verlauf`` gehaengt. Keine Aenderung -> nichts geschrieben.
Ein Fehler bleibt lokal (``log.exception``); die Karte bleibt, wie sie war.

Neue Figuren bekommen hier KEINE eigene Rolle/Rollenlink -- nur das
Kartenfeld ``wer``."""

from __future__ import annotations

import json
import logging

from interview_theater import anweisungen, modellwahl, repo, szenenkarte, workshop

log = logging.getLogger(__name__)

ART = "karten_nachzug"
CLAUDE_MODELL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "ort": {"type": "string",
                "description": "Where this scene happens now, short, like the card "
                               "field -- the SAME value as before if nothing changed."},
        "wer": {"type": "string",
                "description": "Who is in this scene now, short, including any new "
                               "people the text introduces -- the SAME value as "
                               "before if nothing changed."},
        "modus": {"type": "string", "enum": list(szenenkarte.MODI),
                  "description": "Only a value other than 'none' when the text "
                                 "clearly shows a different attention mode "
                                 "(microphone, one_to_one, collective); otherwise "
                                 "'none'."},
    },
    "required": ["ort", "wer", "modus"],
    "additionalProperties": False,
}

#: Notiz fuer ``karte_verlauf`` -- Prompt-Wortlaut (englisch), kein Chattext.
_NOTIZ = "Phase 7: place/people taken over from the newly written script."


def _normalisiert(wert) -> str:
    return " ".join(str(wert or "").split()).strip().lower()


def _system_fuer(chat_id: int) -> str:
    text = anweisungen.hole(ART)
    if chat_id in workshop.italienisch_ab_phase6_chats():
        text += "\n\n" + szenenkarte.T._AUFTRAG_AUSGABE_ITALIENISCH
    return text


def baue_nutzertext(karte: dict, text: str) -> str:
    kopf = [f"typ: {karte.get('typ') or ''}", f"ort: {karte.get('ort') or ''}",
            f"wer: {karte.get('wer') or ''}"]
    if karte.get("typ") == "moment":
        kopf.append(f"modus: {karte.get('modus') or 'none'}")
    return (
        "Previous card (style template, not necessarily still true):\n"
        + ", ".join(kopf)
        + "\n\nNewly written script text of this scene:\n" + text
    )


def ziehe_nach(conn, klm, e, chat_id: int, szene_id: int, text: str, *,
               ueber_claude: bool) -> None:
    """Der eine Modellaufruf plus deterministischer Vergleich. Nie wirft sie
    einen Fehler nach aussen -- der Aufrufer laeuft im Hintergrund-Thread."""
    try:
        szene = repo.hole_szene(conn, szene_id)
        if szene is None:
            return
        karte = szenenkarte.karte_von(szene)
        if karte is None or not (text or "").strip():
            return
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system=_system_fuer(chat_id),
            nutzer=baue_nutzertext(karte, text), schema=SCHEMA, art=ART,
            ueber_claude=ueber_claude, claude_modell=CLAUDE_MODELL, timeout=60.0,
        )
        neuer_ort = str(ergebnis.get("ort") or "").strip()
        neuer_wer = str(ergebnis.get("wer") or "").strip()
        neuer_modus = str(ergebnis.get("modus") or "").strip().lower()
        aenderungen: dict = {}
        if neuer_ort and _normalisiert(neuer_ort) != _normalisiert(karte.get("ort")):
            aenderungen["ort"] = neuer_ort
        if neuer_wer and _normalisiert(neuer_wer) != _normalisiert(karte.get("wer")):
            aenderungen["wer"] = neuer_wer
        if (karte.get("typ") == "moment" and neuer_modus in szenenkarte.MODI
                and neuer_modus != "none" and neuer_modus != karte.get("modus")):
            aenderungen["modus"] = neuer_modus
        if not aenderungen:
            return
        neue_karte = dict(karte)
        neue_karte.update(aenderungen)
        karte_json = json.dumps(neue_karte, ensure_ascii=False)
        repo.aktualisiere_szenenkarte_meta(conn, szene_id, karte_json)
        repo.merke_karte_verlauf(conn, chat_id, szene_id, karte_json,
                                 szenenkarte.AUSLOESER_AENDERUNG, _NOTIZ)
    except Exception:
        log.exception("P7-Meta-Nachzug fehlgeschlagen, chat_id=%s, szene_id=%s",
                      chat_id, szene_id)
