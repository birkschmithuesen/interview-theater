"""Absichtserkenner (SPEC-kontext-architektur.md § 4.3, § 4.3a).

Schliesst die Luecke, die Teil A offen liess: ``kontext.py`` liest
``arbeitsstand``, ``figur`` und ``journal`` in den Prompt, aber vor Teil B
schrieb sie niemand. Diese Aufgabe baut NUR die Erkennung -- das Anwenden auf
die Datenbank kommt in einer spaeteren Aufgabe (``wende_an``), die Meldung an
die Gruppe danach.

Laeuft nachgelagert, nachdem die Bot-Antwort in der Gruppe steht. Niemand
wartet darauf (SPEC § 4.3): Modell ``google/gemma-4-31B-it``, erzwungenes
Schema, ``reasoning_effort: "none"`` (Vorgabe von ``LLM.schema``, hier nicht
extra gesetzt), ``temperature: 0.2``. Gemessen: 0 Falsch-Positive bei 25
Negativfaellen, 30/30 Treffer, 0,75 s -- Kimi (das Gespraechsmodell) verpasste
``interview_beenden`` in 3 von 3 Faellen, Nemotron-Nano fiel mit 6/27
Falsch-Positiven durch und darf deshalb nirgends als Vorgabewert auftauchen.

**Kontext:** aktueller Arbeitsstand + die neuen Nachrichten seit
``gruppe.letzte_extrahierte_message_id`` (``repo.unextrahierte``). Nicht das
Journal, nicht die Transkripte -- das Journal wird hier nur GESCHRIEBEN
(spaeter, in ``wende_an``), nie mitgelesen, und Transkripte gehoeren zum
Gespraechs-, nicht zum Erkenner-Kontext.

**Schema, bewusst flach** (global-constraints.md 'Schema'): ein Array aus
Objekten mit zwei Feldern, keine Verschachtelung tiefer als
``array > object > string``. Kein Objekt mit elf meist leeren Feldern --
strikte Modi kennen keine optionalen Felder, das Modell muesste jedes Mal
alle ausfuellen, und ein Feld, das befuellt werden *will*, ist ein
Halluzinationsanreiz. Die leere Liste ist die natuerliche Form von "nichts
gefunden". Kein ``maxItems`` im Schema (von strikten Modi oft nicht
unterstuetzt) -- die Fuenf-Obergrenze steht im Prompttext UND wird unten in
``erkenne()`` hart durchgesetzt.

**Fehlerhaltung** (global-constraints.md, SPEC § 4.3): Bei Erfolg rueckt das
Wasserzeichen vor, erkannte Aenderungen werden zurueckgegeben. Bei Fehlschlag
bleibt das Wasserzeichen STEHEN (kostenloser Wiederholungsversuch beim
naechsten Lauf), ein ``vorfall`` wird geschrieben, der Gruppe wird nichts
gemeldet, leere Liste zurueck. Ueber dem Token-Deckel FENSTER_DECKEL wird das
Wasserzeichen dagegen TROTZDEM vorgerueckt (sonst wuerde ein einmal zu
grosses Fenster den Erkenner dauerhaft lahmlegen) und ein ``vorfall``
``fenster_verworfen`` geschrieben.
"""

import logging
from pathlib import Path

from theatersoap import kontext, repo

log = logging.getLogger(__name__)

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: theatersoap/prompts/erkenner.md fuer die vollstaendige Anweisung samt
#: der fuenf Few-Shot-Beispiele).
PROMPT = (Path(__file__).parent / "prompts" / "erkenner.md").read_text(encoding="utf-8")

#: Alle erkennbaren Aenderungsarten, in derselben Reihenfolge wie im Prompt
#: aufgelistet (SPEC § 4.3, teil-b.md Aufgabe 2). Auch die Schema-Enum unten
#: verwendet diese Liste, damit beide Stellen nie auseinanderlaufen.
ARTEN = (
    "interview_starten",
    "interview_beenden",
    "interview_benennen",
    "begriffe_setzen",
    "kernthema_setzen",
    "hauptkonflikt_setzen",
    "figur_setzen",
    "wortlaut_an",
    "wortlaut_aus",
    "verworfen",
    "entschieden",
)

#: Obergrenze fuer Aenderungen je Lauf -- im Prompttext UND hier im Code
#: durchgesetzt (global-constraints.md 'Schema': kein maxItems im Schema
#: selbst, weil strikte Modi das oft nicht unterstuetzen).
MAX_AENDERUNGEN = 5

#: Sampling-Temperatur des Erkenneraufrufs (SPEC § 4.3, § 4.3a) -- niedrig,
#: gegen Formulierungsvarianz und (bei mehrsprachigen Modellen)
#: Sprachdrift. Bewusst ein eigener Wert, nicht die des Gespraechsaufrufs.
TEMPERATURE = 0.2

#: Ab dieser geschaetzten Tokenzahl (kontext.schaetze -- Zeichen // 3, kein
#: Tokenizer) wird das Fenster verworfen statt gesendet (SPEC § 4.3
#: 'Deckel'): das Wasserzeichen rueckt trotzdem vor, ein vorfall
#: 'fenster_verworfen' wird geschrieben. Verhindert, dass ein einmal
#: aussergewoehnlich grosses Fenster (z. B. ein sehr langer Gespraechsstau)
#: den Erkenner auf Dauer blockiert.
FENSTER_DECKEL = 4000

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md § 4). Absichtlich flach: array > object > string,
#: keine tiefere Verschachtelung (die bricht bei kleineren Modellen wie
#: gemma/Apertus).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["aenderungen"],
    "properties": {
        "aenderungen": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["art", "wert"],
                "properties": {
                    "art": {"type": "string", "enum": list(ARTEN)},
                    "wert": {"type": "string"},
                },
            },
        },
    },
}


def _arbeitsstand_text(conn, chat_id: int) -> str:
    """Formatiert den aktuellen Arbeitsstand (Begriffe, Kernthema,
    Hauptkonflikt, Figuren) fuer den Erkenner-Kontext -- eine eigene,
    schlanke Formatierung statt der privaten ``kontext._baue_arbeitsstand``,
    weil der Erkenner den Stand nur als Eingabe braucht, nicht in der vollen
    Anzeigeform des Gespraechs-Prompts (dort zusaetzlich mit
    Kernthema-Begruendung)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)

    zeilen = []
    if stand:
        if stand["begriffe"]:
            zeilen.append(f"Begriffe: {stand['begriffe']}")
        if stand["kernthema"]:
            zeilen.append(f"Kernthema: {stand['kernthema']}")
        if stand["hauptkonflikt"]:
            zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
    for figur in figuren:
        beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
        zeilen.append(f"Figur {figur['name']}{beschreibung}")

    if not zeilen:
        return ""
    return "Arbeitsstand:\n" + "\n".join(zeilen)


def _nachrichten_text(nachrichten) -> str:
    zeilen = [kontext.sprecherzeile(n) for n in nachrichten]
    return "Neue Nachrichten:\n" + "\n".join(zeilen)


def _baue_nutzertext(conn, chat_id: int, nachrichten) -> str:
    """Baut den Nutzertext des Erkenneraufrufs: aktueller Arbeitsstand plus
    die neuen Nachrichten seit dem Wasserzeichen -- nicht das Journal, nicht
    die Transkripte (SPEC § 4.3)."""
    bloecke = [b for b in (_arbeitsstand_text(conn, chat_id), _nachrichten_text(nachrichten)) if b]
    return "\n\n".join(bloecke)


def erkenne(klm, conn, e, chat_id: int) -> list[dict]:
    """Erkennt Aenderungsabsichten im Gespraech seit der letzten Erkennung.

    ``klm`` ist ein Objekt mit einer ``.schema(chat_id, system, nutzer,
    schema, art, modell=None, temperature=None) -> dict``-Methode (in
    Produktion ``theatersoap.llm.LLM``, in Tests eine Attrappe).

    Liefert eine Liste von ``{"art": ..., "wert": ...}``-Dicts, hoechstens
    ``MAX_AENDERUNGEN`` lang, nur mit bekannten ``art``-Werten. Wendet
    NICHTS auf die Datenbank an -- das ist eine spaetere Aufgabe
    (``wende_an``)."""
    neue = repo.unextrahierte(conn, chat_id)
    if not neue:
        # Kein Aufruf ins Leere: ohne neue Nachrichten gibt es nichts zu
        # erkennen, und ein Aufruf waere reine Latenz- und Kostenlast ohne
        # jeden Nutzen.
        return []

    letzte_message_id = max(n["message_id"] for n in neue)
    nutzer = _baue_nutzertext(conn, chat_id, neue)

    if kontext.schaetze(nutzer) > FENSTER_DECKEL:
        # Deckel (SPEC § 4.3): das Wasserzeichen rueckt TROTZDEM vor, sonst
        # bliebe der Erkenner an einem einmal zu grossen Fenster haengen und
        # wuerde bei jedem weiteren Lauf erneut daran scheitern.
        repo.setze_extrahiert_bis(conn, chat_id, letzte_message_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "fenster_verworfen",
            f"Absichtserkenner-Fenster ueber {FENSTER_DECKEL} geschaetzten Token "
            "verworfen, ohne Sprachmodell-Aufruf",
        )
        return []

    try:
        ergebnis = klm.schema(
            chat_id, PROMPT, nutzer, SCHEMA, "erkenner",
            modell=e.erkenner_modell, temperature=TEMPERATURE,
        )
    except Exception:
        # Fehlschlag: das Wasserzeichen bleibt STEHEN -- ein kostenloser
        # Wiederholungsversuch beim naechsten Lauf, ohne eigene
        # Retry-Logik hier (SPEC § 4.3). Der Gruppe wird nichts gemeldet,
        # sie kann den Fehler weder beheben noch wartet sie darauf
        # (global-constraints.md 'Fehlerhaltung').
        log.exception("Absichtserkennung fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "extraktor_fehler",
            "Absichtserkenner-Aufruf fehlgeschlagen",
        )
        return []

    aenderungen = []
    for eintrag in ergebnis.get("aenderungen", []):
        art = eintrag.get("art")
        if art not in ARTEN:
            # Unbekannte art wird verworfen statt zu krachen -- ein
            # strikt erzwungenes Schema garantiert zwar den Enum-Wert,
            # aber die Attrappe in Tests (und ein kuenftiger Anbieterwechsel)
            # koennen trotzdem einen unbekannten Wert liefern.
            continue
        aenderungen.append({"art": art, "wert": eintrag.get("wert", "")})
        if len(aenderungen) >= MAX_AENDERUNGEN:
            break

    repo.setze_extrahiert_bis(conn, chat_id, letzte_message_id)
    return aenderungen
