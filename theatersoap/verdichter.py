"""Verdichtet ein Interviewtranskript zu Zusammenfassung und Kernthemen
(SPEC-kontext-architektur.md § 4.2).

Laeuft genau einmal je Interview, auf dem frischen Transkript, ohne den
Chatverlauf zu kennen. Erzwungenes JSON-Schema, ``reasoning_effort: "none"``
(Modus A, siehe ``theatersoap.llm.LLM.schema``).

Jedes Kernthema traegt ein woertliches Belegzitat, das die Gruppe
ueberzeugen soll: ein Konfliktvorschlag mit Beleg ist Dramaturgie, einer ohne
ist ein Automat. Das Zitat durchlaeuft zusaetzlich die Pruefung aus
``theatersoap.zitat`` (§ 5) -- ein einfacher, bewusst dummer
Teilstring-Vergleich, **kein** Retry. Faellt die Pruefung durch, wird nicht
der ganze Themenvorschlag verworfen, sondern nur das Zitat entfernt: das
Thema selbst bleibt (SPEC § 5, global-constraints.md 'Belegzitate').
"""

from pathlib import Path

from theatersoap import repo, zitat

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: theatersoap/prompts/verdichter.md fuer die vollstaendige Anweisung).
PROMPT = (Path(__file__).parent / "prompts" / "verdichter.md").read_text(encoding="utf-8")

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
    schema, art) -> dict``-Methode (in Produktion ``theatersoap.llm.LLM``, in
    Tests eine Attrappe). Liefert die id der neu angelegten Verdichtung.
    """
    aufnahme = repo.hole_aufnahme(conn, aufnahme_id)
    chat_id = aufnahme["chat_id"]
    transkript = aufnahme["transkript"]

    ergebnis = klm.schema(chat_id, PROMPT, transkript, SCHEMA, "verdichter")

    themen = []
    for vorschlag in ergebnis.get("kernthemen", []):
        thema = vorschlag["thema"]
        beleg_zitat = vorschlag["beleg_zitat"]
        if zitat.pruefe(beleg_zitat, transkript):
            themen.append({"thema": thema, "beleg_zitat": beleg_zitat, "zitat_geprueft": 1})
        else:
            # Kein Retry, keine Segmentzerlegung (§ 5): der Vorschlag bleibt
            # erhalten, nur das Zitat faellt weg. Der Gruppe wird nichts
            # gemeldet -- sie kann es nicht beheben und wartet nicht darauf.
            themen.append({"thema": thema, "beleg_zitat": None, "zitat_geprueft": 0})
            repo.merke_vorfall(
                conn,
                chat_id,
                getattr(e, "bot_name", None),
                "zitat_ungeprueft",
                f"Belegzitat nicht im Transkript gefunden (thema={thema!r})",
            )

    return repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id, ergebnis["zusammenfassung"], themen
    )
