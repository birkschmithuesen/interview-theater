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


from interview_theater import begriffe, repo, zitat

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
        f"{T._FRAGEN_KOPF}\n{fragen.strip()}\n\n{T._TRANSKRIPT_KOPF}\n{transkript}"
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

#: Unterhalb dieser Wortzahl ist ein Zitat ausserhalb seiner Interviewfrage
#: nicht mehr zu verstehen -- gemessen an einer Stichprobe aus
#: ``betrieb/padua.db`` (3 Gruppen, 09.10.2026): ALLE Zitate mit 2-3 Woertern
#: waren blosse Fragmente ("In Romania.", "Il sale", "I femminicidi"), ab 4
#: Woertern ueberwog das Gegenteil ("io avevo tre mesi", "Il profumo del
#: sugo."). Anlass: Padua-Abschlussfeedback 09.10.2026 Abschnitt 05, "worst
#: sentence of the interviews that had no meaning".
MIN_ZITAT_WOERTER = 4

#: Zusaetzlich an den Prompt gehaengt, wenn ein woertlich korrektes Zitat zu
#: kurz ist, um fuer sich zu stehen.
_NACHTRAG_SELBSTAENDIG = (
    "\n\nWICHTIG, zweiter Anlauf: Mindestens ein Belegzitat im ersten Anlauf "
    "war zu kurz, um ausserhalb seiner Interviewfrage verstanden zu werden "
    "(ein, zwei Woerter wie eine blosse Ja/Nein-Antwort). Waehle, wo das "
    "Transkript es zulaesst, eine laengere, zusammenhaengende Passage, die "
    "auch ohne die Frage nebenan verstaendlich ist -- weiterhin woertlich "
    "und ohne Auslassungen."
)


def _ist_fragment(zitat_text: str) -> bool:
    """Weniger als ``MIN_ZITAT_WOERTER`` Woerter: ein Fragment, das nur mit
    der (hier nicht gespeicherten) Interviewfrage daneben einen Sinn ergibt."""
    return len((zitat_text or "").split()) < MIN_ZITAT_WOERTER


def _bewertung(ergebnis: dict, transkript: str) -> tuple[int, int]:
    """``(Anzahl belegter Themen, davon Anzahl zu kurzer Fragmente)`` -- die
    Kennzahl, an der ``verdichte`` den ersten gegen den zweiten Anlauf
    misst."""
    bestanden = 0
    fragmente = 0
    for v in ergebnis.get("kernthemen", []):
        z = v.get("beleg_zitat")
        if z and zitat.pruefe(z, transkript):
            bestanden += 1
            if _ist_fragment(z):
                fragmente += 1
    return bestanden, fragmente


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
    # Direkttest 6/6 bestanden -- das Modell glaettet gelegentlich) ODER
    # wenn ein woertlich korrektes Zitat ein blosses Fragment ist
    # (``_ist_fragment``, Padua-Feedback "worst sentence ... had no
    # meaning"). Nicht mehr als einer: Kosten und Zeit, und ein Modell, das
    # zweimal daneben liegt, liegt auch beim dritten Mal daneben.
    gesamt = len(ergebnis.get("kernthemen", []))
    bestanden, fragmente = _bewertung(ergebnis, transkript)
    if bestanden < gesamt or fragmente:
        zusatz = T._NACHTRAG_WOERTLICH if bestanden < gesamt else ""
        if fragmente:
            zusatz += T._NACHTRAG_SELBSTAENDIG
        zweiter = klm.schema(
            chat_id, prompt() + zusatz,
            baue_nutzertext(transkript, fragen), SCHEMA, "verdichter",
        )
        bestanden2, fragmente2 = _bewertung(zweiter, transkript)
        if (bestanden2, -fragmente2) > (bestanden, -fragmente):
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

    verdichtung_id = repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id, ergebnis["zusammenfassung"], themen
    )
    ordne_begriffe_zu(conn, chat_id, verdichtung_id, aufnahme_id,
                      ergebnis["zusammenfassung"], themen, stand)
    return verdichtung_id


def ordne_begriffe_zu(
    conn, chat_id: int, verdichtung_id: int, aufnahme_id: int | None,
    zusammenfassung: str | None, themen, stand=None,
) -> list[str]:
    """Ordnet die frische Verdichtung den Kernbegriffen der Gruppe zu
    (06.09.2026, ``interview_theater.begriffe``).

    **Deterministisch, kein zweiter Modellaufruf** -- der Abgleich laeuft
    gegen Zusammenfassung und Kernthemen, die gerade entstanden sind; die
    Begruendung steht im Modulkopf von ``begriffe.py``. Leere Begriffsliste
    (die Gruppe ist noch in Phase 1) heisst schlicht: keine Tags.

    Ein Fehler hier darf die Verdichtung nicht kosten: sie ist gespeichert,
    die Zuordnung ist Beiwerk, und die Gruppe wartet auf den Text im Chat.
    Deshalb faengt der Aufrufpfad in ``verdichte`` nichts ab -- die Funktion
    selbst gibt bei fehlendem Arbeitsstand einfach eine leere Liste
    zurueck."""
    if stand is None:
        stand = repo.hole_arbeitsstand(conn, chat_id)
    liste = begriffe.zerlege(stand["begriffe"] if stand else None)
    if not liste:
        return []
    treffer = begriffe.ordne_zu(
        liste, begriffe.texte_der_verdichtung(zusammenfassung, themen)
    )
    repo.setze_verdichtung_begriffe(
        conn, chat_id, verdichtung_id, treffer, aufnahme_id=aufnahme_id
    )
    return treffer


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)
