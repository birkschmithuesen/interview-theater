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
#:
#: ``kurz`` ist am 05.09.2026 dazugekommen (N3/N6): dasselbe Ergebnis in
#: hoechstens acht Woertern. Es steht als eigenes Feld hier und nicht als
#: Laengenregel an ``thema``, weil beide Anzeigen, die davon leben -- die
#: Summary-Zeile je Interview auf der Gruppenseite und die eine Zeile je
#: Interview auf dem projizierten Dashboard --, eine verlaessliche Obergrenze
#: brauchen und nicht eine, die das Modell mal einhaelt und mal nicht.
#: Umgekehrt darf ``thema`` dadurch der ganze Satz bleiben, den N3 verlangt
#: ("was auf diese Frage geantwortet wurde, in einem Satz").
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
                "required": ["thema", "kurz", "beleg_zitat"],
                "properties": {
                    "thema": {"type": "string"},
                    "kurz": {"type": "string"},
                    "beleg_zitat": {"type": "string"},
                },
            },
        },
    },
}

#: Ueberschrift der Frageliste im Nutzertext. Der Verdichter kennt sonst
#: nichts vom Arbeitsstand -- die Fragen sind die eine Ausnahme (N3), weil
#: ein Interview an ihnen entlang gefuehrt wurde und die Gruppe zuerst
#: wissen will, was auf ihre Fragen geantwortet wurde.
_FRAGEN_KOPF = "Die Interviewfragen der Gruppe:"
_TRANSKRIPT_KOPF = "Das Transkript:"

#: Obergrenze der Kurzform in Woertern -- im Prompttext ("hoechstens acht
#: Woerter") UND hier, damit ``scripts/pruefe_prompts.py`` sie mechanisch
#: nachzaehlen kann. Nicht durchgesetzt: eine zu lange Kurzform ist eine
#: unschoene Zeile, kein Grund, ein belegtes Ergebnis wegzuwerfen.
KURZ_MAX_WOERTER = 8


def baue_nutzertext(transkript: str, fragen: str | None = None) -> str:
    """Baut den Nutzertext des Verdichteraufrufs.

    Ohne Frageliste ist er wortidentisch mit dem Transkript -- so wie vor
    N3, und so wie ihn die sechs aelteren Korpusfaelle erwarten. Mit
    Frageliste stehen die Fragen davor, mit einer Zeile, die sagt, was sie
    sind: der Prompt geht sie der Reihe nach durch."""
    if not (fragen or "").strip():
        return transkript
    return (
        f"{_FRAGEN_KOPF}\n{fragen.strip()}\n\n{_TRANSKRIPT_KOPF}\n{transkript}"
    )


#: Wird beim zweiten Versuch an den Prompt gehaengt, wenn Zitate des ersten
#: durchgefallen sind.
_NACHTRAG_WOERTLICH = (
    "\n\nWICHTIG, zweiter Anlauf: Im ersten Anlauf stimmten Belegzitate nicht "
    "Wort fuer Wort mit dem Transkript ueberein. Kopiere jedes Zitat ZEICHEN "
    "FUER ZEICHEN aus dem Transkript -- keine Glaettung, kein Komma versetzt, "
    "keine Fuellwoerter entfernt, keine Rechtschreibung korrigiert. Lieber "
    "ein kuerzeres Zitat, das exakt stimmt, als ein laengeres, das du "
    "nachgebessert hast."
)


def verdichte(klm, conn, e, aufnahme_id: int) -> int:
    """Verdichtet die Aufnahme ``aufnahme_id`` und speichert das Ergebnis.

    ``klm`` ist ein Objekt mit einer ``.schema(chat_id, system, nutzer,
    schema, art) -> dict``-Methode (in Produktion ``interview_theater.llm.LLM``, in
    Tests eine Attrappe). Liefert die id der neu angelegten Verdichtung.
    """
    aufnahme = repo.hole_aufnahme(conn, aufnahme_id)
    chat_id = aufnahme["chat_id"]
    transkript = aufnahme["transkript"]
    stand = repo.hole_arbeitsstand(conn, chat_id)
    fragen = stand["fragen"] if stand else None

    ergebnis = klm.schema(
        chat_id, prompt(), baue_nutzertext(transkript, fragen), SCHEMA, "verdichter"
    )
    # Ein zweiter Versuch, wenn Zitate durchfallen (05.09., Simulation
    # birk-6: 2 von 3 Ergebnissen 'ohne belegtes Zitat verworfen', im
    # Direkttest 6/6 bestanden -- das Modell glaettet gelegentlich). Nicht
    # mehr als einer: Kosten und Zeit, und ein Modell, das zweimal daneben
    # liegt, liegt auch beim dritten Mal daneben.
    if any(not (v.get("beleg_zitat") and zitat.pruefe(v["beleg_zitat"], transkript))
           for v in ergebnis.get("kernthemen", [])):
        zweiter = klm.schema(
            chat_id, prompt() + _NACHTRAG_WOERTLICH,
            baue_nutzertext(transkript, fragen), SCHEMA, "verdichter",
        )
        def _bestanden(r):
            return sum(1 for v in r.get("kernthemen", [])
                       if v.get("beleg_zitat") and zitat.pruefe(v["beleg_zitat"], transkript))
        if _bestanden(zweiter) > _bestanden(ergebnis):
            ergebnis = zweiter

    themen = []
    for vorschlag in ergebnis.get("kernthemen", []):
        thema = vorschlag["thema"]
        beleg_zitat = vorschlag["beleg_zitat"]
        if beleg_zitat and zitat.pruefe(beleg_zitat, transkript):
            themen.append({
                "thema": thema,
                # Ohne kurz faellt die Anzeige auf das Thema zurueck (N6):
                # eine lange Summary-Zeile ist unschoen, eine leere waere ein
                # verschwundenes Ergebnis.
                "kurz": (vorschlag.get("kurz") or "").strip() or thema,
                "beleg_zitat": beleg_zitat,
                "zitat_geprueft": 1,
            })
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
