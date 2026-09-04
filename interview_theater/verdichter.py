"""Verdichtet ein Interviewtranskript zu Zusammenfassung und Kernthemen
(SPEC-kontext-architektur.md § 4.2).

Laeuft genau einmal je Interview, auf dem frischen Transkript, ohne den
Chatverlauf zu kennen. Erzwungenes JSON-Schema, ``reasoning_effort: "none"``
(Modus A, siehe ``interview_theater.llm.LLM.schema``).

Jedes Kernthema traegt ein woertliches Belegzitat, das die Gruppe
ueberzeugen soll: ein Konfliktvorschlag mit Beleg ist Dramaturgie, einer ohne
ist ein Automat. Das Zitat durchlaeuft zusaetzlich die Pruefung aus
``interview_theater.zitat`` (§ 5) -- ein einfacher, bewusst dummer
Teilstring-Vergleich, **kein** Retry.

**Faellt die Pruefung durch, faellt das ganze Thema weg** (Nachtrag N2,
05.09.2026). Bis dahin blieb der Themenvorschlag stehen und nur das Zitat
wurde entfernt (``zitat_geprueft = 0``); der Probelauf vom 04.09. abends hat
gezeigt, wohin das fuehrt: aus einer vier Sekunden langen Sprachnachricht
("Zeigt mir die Verdichtungen von den Interviews an.") entstand ein
vollstaendig erfundenes Interview mit den Themen "Heimweh",
"Mutter-Tochter-Beziehung" und "Abschied und Verlust" -- alle drei ohne
Zitat, alle drei standen trotzdem im Chat und im Prompt. Ein Thema ohne
Beleg ist kein halbes Ergebnis, sondern eine Behauptung ueber einen
Menschen, den die Gruppe interviewt hat. Bleibt kein Thema uebrig, wird die
Verdichtung mit leerer Themenliste gespeichert -- die Zusammenfassung bleibt,
und ``aufnahme._verdichtungstext`` sagt der Gruppe, dass nichts belegbar war.
"""


from interview_theater import repo, zitat

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: interview_theater/prompts/verdichter.md fuer die vollstaendige Anweisung).
from interview_theater import anweisungen


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("verdichter")

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md § 4).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["zusammenfassung", "kernthemen"],
    "properties": {
        "zusammenfassung": {"type": "string"},
        "kernthemen": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["thema", "beleg_zitat"],
                "properties": {
                    "thema": {"type": "string"},
                    "beleg_zitat": {"type": "string"},
                },
            },
        },
    },
}


def verdichte(klm, conn, e, aufnahme_id: int) -> int:
    """Verdichtet die Aufnahme ``aufnahme_id`` und speichert das Ergebnis.

    ``klm`` ist ein Objekt mit einer ``.schema(chat_id, system, nutzer,
    schema, art) -> dict``-Methode (in Produktion ``interview_theater.llm.LLM``, in
    Tests eine Attrappe). Liefert die id der neu angelegten Verdichtung.
    """
    aufnahme = repo.hole_aufnahme(conn, aufnahme_id)
    chat_id = aufnahme["chat_id"]
    transkript = aufnahme["transkript"]

    ergebnis = klm.schema(chat_id, prompt(), transkript, SCHEMA, "verdichter")

    themen = []
    for vorschlag in ergebnis.get("kernthemen", []):
        thema = vorschlag["thema"]
        beleg_zitat = vorschlag["beleg_zitat"]
        if beleg_zitat and zitat.pruefe(beleg_zitat, transkript):
            themen.append({"thema": thema, "beleg_zitat": beleg_zitat, "zitat_geprueft": 1})
        else:
            # Kein Retry, keine Segmentzerlegung (§ 5) -- und seit N2 auch kein
            # Behalten: ohne Beleg wird das Thema gar nicht erst gespeichert.
            # Der Gruppe wird nichts gemeldet, sie kann es nicht beheben und
            # wartet nicht darauf; der Vorfall haelt es fuers Dashboard fest.
            repo.merke_vorfall(
                conn,
                chat_id,
                getattr(e, "bot_name", None),
                "zitat_ungeprueft",
                f"Thema ohne belegtes Zitat verworfen (thema={thema!r})",
            )

    return repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id, ergebnis["zusammenfassung"], themen
    )
