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
der Karte unterscheidet, schreibt der Nachzug -- und zwar ausschliesslich ueber
die Mutations-Schnittstelle ``stueck`` (Quelle ``script``). Seit dem
Stueckmodell (Karte t_fd88600b) schreibt dieses Modul nichts selbst; es gibt
keine zweite Fassung von Ort/Besetzung mehr, die nachzuziehen waere. Ein
Fehler bleibt lokal (``log.exception``).

Unbekannte Namen werden NICHT zur Figur (``stueck.figur_hinzu`` legt hier nur
eine schon bekannte Figur in die Besetzung; Namensabgleich ueber
``stueck_sicht.ordne_besetzung``).

**Figuren aus dem Text, zusaetzlich zum Modell** (Nachtrag Birk 08.10.2026,
Live-Befund G2: ``wer`` nannte nur einen Teil der sprechenden Figuren, obwohl
weitere als Abschnittskopf -- "ANNA (Arlecchino)", "PIETRO, FRANCESCO,
SILVIO" -- oder als Sprecherzeile "NAME: ..." im Skript standen; die
Werkbank blieb unvollstaendig). ``_figuren_aus_text`` liest deterministisch
per Regex gegen die ``figur``-Tabelle nach -- Sprecherzeilen wie
``sprecher.sprecher_der_zeile``, Abschnittskoepfe als eigene Pruefung
(eine Zeile aus Grossbuchstaben-Namen, Komma-Liste, optionaler
Klammerzusatz). Die Treffer werden mit dem Modellergebnis VEREINT, nicht
ersetzt."""

from __future__ import annotations

import logging
import re

from interview_theater import (
    anweisungen, modellwahl, repo, stueck, stueck_sicht, szenenkarte, workshop,
)

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

#: Ein Abschnittskopf ohne Doppelpunkt: eine oder mehrere Grossbuchstaben-
#: Namen, mit Komma getrennt, optional ein Klammerzusatz ("ANNA
#: (Arlecchino)", "PIETRO, FRANCESCO, SILVIO"). Gleiche Fehlerrichtung wie
#: ``sprecher.sprecher_der_zeile``: lieber eine Kopfzeile nicht erkennen als
#: einen normalen Satz dafuer halten -- jedes Zeichen der Zeile muss in den
#: erlaubten Satz passen (volle Zeile, kein Teiltreffer).
_KLAMMERZUSATZ = re.compile(r"\s*\([^)]*\)\s*$")
_KOPFZEILE = re.compile(
    r"^[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ0-9 .'’-]{0,40}"
    r"(?:,\s*[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ0-9 .'’-]{0,40})*$"
)


def _figuren_aus_text(conn, chat_id: int, text: str) -> list[int]:
    """Figur-ids, die im Skripttext als Sprecherzeile ("NAME: ...") oder
    Abschnittskopf ("ANNA (Arlecchino)", "PIETRO, FRANCESCO, SILVIO")
    stehen -- deterministisch per Regex gegen die ``figur``-Tabelle, **nur**
    schon vorhandene Figuren (wie ``erkenner._figuren_aus_namen``). Ergaenzt
    das Modellergebnis in ``ziehe_nach``, ersetzt es nicht."""
    from interview_theater import sprecher

    schreibweise = {f["name"].strip().lower(): f["id"] for f in repo.figuren(conn, chat_id)}
    if not schreibweise:
        return []
    namen = set(schreibweise)
    gefunden: set[int] = set()
    for zeile in (text or "").splitlines():
        kopf = zeile.strip()
        sprecher_name = sprecher.sprecher_der_zeile(zeile, namen)
        if sprecher_name is not None:
            figur_id = schreibweise.get(sprecher_name.strip().lower())
            if figur_id is not None:
                gefunden.add(figur_id)
            continue
        ohne_klammer = _KLAMMERZUSATZ.sub("", kopf)
        if not ohne_klammer or _KOPFZEILE.match(ohne_klammer) is None:
            continue
        for teil in ohne_klammer.split(","):
            figur_id = schreibweise.get(teil.strip().lower())
            if figur_id is not None:
                gefunden.add(figur_id)
    return sorted(gefunden)


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
    """EIN Modellaufruf liest Ort/Figuren/Modus aus dem neuen Skripttext;
    geschrieben wird NUR ueber die Mutations-Schnittstelle (``stueck``,
    Quelle ``script``: der Text ist hier die Quelle, die eigene Szene wird
    nicht als veraltet markiert). Ein aelterer Text als der gespeicherte
    schreibt nichts (gleiche Regel wie die IT-Spiegelung). Nie wirft sie
    einen Fehler nach aussen -- der Aufrufer laeuft im Hintergrund-Thread."""
    try:
        szene = repo.hole_szene(conn, szene_id)
        if szene is None or (szene["volltext"] or "").strip() != (text or "").strip():
            return
        karte = stueck.karte(conn, szene)
        if karte is None or not (text or "").strip():
            return
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system=_system_fuer(chat_id),
            nutzer=baue_nutzertext(karte, text), schema=SCHEMA, art=ART,
            ueber_claude=ueber_claude, claude_modell=CLAUDE_MODELL, timeout=60.0,
        )
        nummer = szene["nummer"]
        q = stueck.QUELLE_SCRIPT
        neuer_ort = str(ergebnis.get("ort") or "").strip()
        if neuer_ort:
            stueck.setze_ort(conn, chat_id, szene=nummer, ort=neuer_ort, quelle=q)
        figuren = repo.figuren(conn, chat_id)
        index = {stueck_sicht.normalisiert(f["name"]): f["id"] for f in figuren}
        namen = {f["id"]: f["name"] for f in figuren}
        aus_modell, _unbekannt = stueck_sicht.ordne_besetzung(
            str(ergebnis.get("wer") or ""), index)
        ids = [f for f, _rolle in aus_modell]
        ids += [f for f in _figuren_aus_text(conn, chat_id, text) if f not in ids]
        for figur_id in ids:
            stueck.figur_hinzu(conn, chat_id, name=namen[figur_id], szene=nummer, quelle=q)
        neuer_modus = str(ergebnis.get("modus") or "").strip().lower()
        if (karte.get("typ") == "moment" and neuer_modus in szenenkarte.MODI
                and neuer_modus not in ("none", karte.get("modus"))):
            stueck.karte_aendern(conn, chat_id, szene=nummer, modus=neuer_modus, quelle=q)
    except Exception:
        log.exception("P7-Meta-Nachzug fehlgeschlagen, chat_id=%s, szene_id=%s",
                      chat_id, szene_id)
