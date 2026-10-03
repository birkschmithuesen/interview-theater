"""Welches Sprachmodell wann (Birk, 02.10.2026, verbindlich --
``docs/entscheidung-modellwahl-2026-10-02.md``; erweitert 03.10.2026,
Padua Phase 1+2 Karte -- siehe den Nachtrag dort).

**Die Regel in einem Satz.** Sensible Daten -- Interview-Audio, Transkripte,
jede Verdichtung -- bleiben IMMER bei Kimi (Infomaniak, Schweiz), auch wenn
sie erst in Phase 4+ fertig wird oder vom Nachhol-Arbeiter nachgeholt wird:
``verdichter.py`` ruft dieses Modul nicht an, und das ist die ganze
Durchsetzung -- ein Modul, das nie fragt, kann nie umgeroutet werden.

Seit dem 03.10.2026 steht die Einwilligungsfrage schon beim EINTRITT IN
PHASE 1 (``knoepfe/stationen.py::eintritt_in_phase``), nicht erst beim
Uebergang 3->4 -- dieselbe Spalte (``gruppe.szene_usa_bestaetigt_am``),
derselbe Knopfweg (``ART_SZENE_USA``, ``biete_szene_usa``), keine zweite
Frage. Mit Zustimmung darf das Gespraech seitdem in JEDER Phase ausser
Phase 3 (Interviews) auf Claude Opus laufen, WENN der Betreiber es erlaubt
(``IT_SZENE_ANBIETER=claude``, dieselbe Umgebungsvariable wie beim
bestehenden Szenen-Schalter): Phase 1 (Diskussionsverdichtung), Phase 2
(Fragenformulierung/KI-Vorschlaege), Phase 4 (Setting/Figuren/Geschichte),
5 (Schaerfung), 6 (Szenen) und 7 (Feinschliff) sind damit Opus-faehig.
**Phase 3 (Interviews) bleibt UNBEDINGT Kimi** -- ohne Ausnahme und
unabhaengig von der Einwilligung: dort stecken die Rohdaten der
interviewten Personen, und diese eine Ausnahme ist nicht verhandelbar.

``szene_claude.ist_aktiv`` traegt genau diese zwei Bedingungen (Schalter +
Zustimmung) bereits -- fuer Szene, Kurzgeschichte, Szenenfolge,
Stueckpruefung und die Buehnenkarten (Brainstorming-Sparring) reicht das, sie
sind ohnehin erst ab ihrer eigenen Phase erreichbar. Nur das Gespraech selbst
laeuft durch alle sieben Phasen hindurch und braucht zusaetzlich die
Ausnahme fuer Phase 3 -- ``konversation_ueber_claude`` unten.

**Fallback.** Scheitert der Claude-Proxy nach seinen eigenen Wiederholungen
(``szene_claude.WARTEZEITEN``) oder liefert er kein JSON, das zu einem
Schema passt, laeuft GENAU DIESER Zug stattdessen auf Kimi -- die Gruppe
wartet, ein zweiter bezahlter Fehlversuch bringt nichts. Vermerkt wird das
als Vorfall ``opus_fallback``, einmal je gescheitertem Zug (kein Deckel noetig:
ein Proxy-Ausfall betrifft ohnehin jeden weiteren Zug und soll sichtbar
bleiben, nicht nach dem ersten Mal verschwinden)."""

from __future__ import annotations

import logging

from interview_theater import phasen, repo, szene_claude
from interview_theater.knoepfe.texte import PHASE_INTERVIEWS
from interview_theater.llm import LLMFehler

log = logging.getLogger(__name__)

VORFALL_OPUS_FALLBACK = "opus_fallback"


def konversation_ueber_claude(e, conn, chat_id: int) -> bool:
    """True, wenn DIESER Gespraechszug auf Claude laufen soll: Betreiber
    erlaubt es, die Gruppe hat zugestimmt (``szene_claude.ist_aktiv`` --
    Schalter + Einwilligung), UND die Gruppe steht NICHT in Phase 3
    (Interviews).

    Seit der Padua Phase 1+2 Karte (03.10.2026) ist das jede Phase ausser
    Phase 3 -- also auch Phase 1 und 2, die vorher wie jede Phase unter 4
    unbedingt bei Kimi blieben (``>= PHASE_SETTING``). Phase 3 bleibt die
    einzige, unbedingte Ausnahme: dort entstehen die sensiblen Rohdaten der
    interviewten Personen.

    Der Sprung IN Phase 3 schaltet automatisch zurueck auf Kimi, jede andere
    Phase automatisch wieder auf Claude -- es gibt keinen eigenen
    Merkposten dafuer, die Phase IST die Bedingung."""
    if not szene_claude.ist_aktiv(e, conn, chat_id):
        return False
    return phasen.aktuelle(conn, chat_id) != PHASE_INTERVIEWS


def aufruf_schema(conn, klm, e, chat_id: int | None, system: str, nutzer: str,
                  schema: dict, art: str, *, ueber_claude: bool,
                  bei_teil=None, teil_feld: str | None = None,
                  modell: str | None = None, timeout: float | None = None) -> dict:
    """Ein Schema-Aufruf (Modus A), der -- wenn ``ueber_claude`` -- zuerst den
    Claude-Proxy versucht und bei einem Fehler auf Kimi zurueckfaellt (dieser
    EINE Zug, kein Dauerschalter). Ohne ``ueber_claude`` unveraendert
    ``klm.schema`` (E1: kein Verhalten aendert sich, wenn die Bedingungen
    oben nicht zutreffen).

    ``teil_feld`` gilt nur fuer den Claude-Pfad (``szene_claude.schema``
    entpackt das Feld aus dem wachsenden JSON beim Streamen); der Kimi-Pfad
    bekommt es nicht, weil ``klm.schema`` es selbst aus seiner Signatur
    kennt und hier nicht gebraucht wird (einziger Aufrufer: das Gespraech,
    mit ``teil_feld="antwort"`` fest im eigenen Aufruf)."""
    if ueber_claude:
        import httpx

        klient = getattr(klm, "_klient", None) or httpx.Client(timeout=timeout or 60.0)
        try:
            return szene_claude.schema(
                conn, e, klient, chat_id, system, nutzer, schema, art,
                timeout=timeout or 60.0, bei_teil=bei_teil, teil_feld=teil_feld,
            )
        except (szene_claude.ClaudeFehler, LLMFehler) as fehler:
            _melde_fallback(conn, chat_id, e, art, fehler)
            if bei_teil is not None:
                neu = getattr(bei_teil, "neu", None)
                if callable(neu):
                    neu()
    # ``modell``/``bei_teil`` nur mitgeben, wenn wirklich gebraucht: beide
    # sind bei ``klm.schema`` optional, und ein Testdouble darf eine
    # schmalere Signatur haben als die echte ``LLM`` (gemessen:
    # ``KLMAttrappe.schema`` in tests/test_ablauf.py kennt kein ``modell``,
    # die Schaerfungs-Attrappe kein ``bei_teil``).
    zusatz = {}
    if modell is not None:
        zusatz["modell"] = modell
    if bei_teil is not None:
        zusatz["bei_teil"] = bei_teil
    return klm.schema(chat_id, system, nutzer, schema, art, **zusatz)


def _melde_fallback(conn, chat_id, e, art: str, fehler: Exception) -> None:
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), VORFALL_OPUS_FALLBACK,
            f"Claude-Proxy fuer {art} fehlgeschlagen ({type(fehler).__name__}) "
            "-- dieser Zug laeuft auf Kimi",
        )
    except Exception:  # noqa: BLE001 -- ein Vorfall darf den Fallback nie mitreissen
        log.exception("Vorfall opus_fallback nicht geschrieben, chat_id=%s", chat_id)
