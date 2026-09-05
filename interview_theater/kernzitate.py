"""Der Filter am Kernthema: welche Stellen tragen die Kernfrage?

**Warum es das gibt** (Birk, 05.09.2026 abends, nach dem Regie-Test): in
Phase 4 kamen die Figuren aus den Interviews und nicht aus dem Kernthema. Der
Figuren-Prompt bekam alle Verdichtungen und alle Transkripte, und
``prompts/phasen/4.md`` verlangte Figuren, "die sich auf Interviewstellen
stuetzen" -- die Gruppe konnte den Weg Kernthema -> Figuren nicht mehr
nachvollziehen, weil es ihn so nicht gab.

Der Weg jetzt, in einem Satz: **Kernthema schaerfen (Kernfrage), dann am
Kernthema filtern, dann Figuren und Szenen NUR aus dem gefilterten Paket.**
Dieses Modul ist der Filter. Er laeuft **einmal**, automatisch, gleich nachdem
die Kernfrage gespeichert ist -- ohne eigenen Knopf und ohne Liste im Chat:
in die Gruppe geht eine einzige Zeile ("Ich habe 7 Stellen aus Interview 3, 5
und 8 als Grundlage fuer die Figuren ausgewaehlt."), danach direkt die Frage
nach der Figurenanzahl. Aendern kann die Gruppe die Auswahl im Gespraech
("nimm auch Interview 2 dazu") -- dafuer braucht es keinen zweiten Pfad,
nur den Hinweis im Phasen-Prompt.

**Zwei Ergebnisse, ein Aufruf:**

* **Kernzitate** (Tabelle ``kernzitat``): 5-10 gepruefte Belegzitate, die zur
  Kernfrage passen, je mit Interview-Nummer und einem Halbsatz, warum.
* **Gefilterte Verdichtungen** (``verdichtung_thema.zum_kernthema_am``): die
  Themen samt Zusammenfassung, die zur Kernfrage passen. Die Verdichtungen
  fliegen also **nicht** raus -- sie werden am Kernthema gefiltert, genau wie
  die Zitate (Birk, Korrektur am selben Abend).

**Die Eingabe ist geschlossen.** Das Modell sieht ausschliesslich die schon
geprueften Verdichtungsthemen (``repo.gepruefte_themen``): Interview-Nummer,
Thema, Zusammenfassung, Zitat -- **keine Transkripte**. Es waehlt daraus per
Nummer aus; erfinden kann es nichts, weil nichts Erfundenes eine Nummer hat.
Nennt es zusaetzlich einen Wortlaut, wird dieser gegen das Original-Zitat
geprueft (``zitat.pruefe``) und der Eintrag sonst verworfen -- dieselbe Regel
wie beim Verdichter und beim Sprachprofil (N2, T3).

**Reasoning aus, gemma, eigener Thread** -- wie ``sprachprofil.py``: die
Aufgabe ist Auswahl, kein Abwaegen, und niemand wartet im Chat darauf.
"""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, repo, zitat

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf``.
ART = "kernzitate"

#: Wie viele Zitate die Auswahl umfassen soll. Fuenf ist die Untergrenze, ab
#: der ein Kernthema mehr als eine Stimme hat; zehn die Obergrenze, ab der das
#: Kernpaket wieder zu einem Materialberg wuerde -- und genau davon kommen wir
#: gerade weg.
MIN_ZITATE = 5
MAX_ZITATE = 10

#: Flach wie ueberall (global-constraints.md 'Schema'): drei Listen, keine
#: Verschachtelung tiefer als ``array > string|integer``. Die Zuordnung
#: laeuft ueber die Nummern der Eingabeliste -- deshalb braucht es kein
#: verschachteltes Objekt je Zitat.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["zitat_nummern", "zitate", "begruendungen", "verdichtung_nummern"],
    "properties": {
        "zitat_nummern": {"type": "array", "items": {"type": "integer"}},
        "zitate": {"type": "array", "items": {"type": "string"}},
        "begruendungen": {"type": "array", "items": {"type": "string"}},
        "verdichtung_nummern": {"type": "array", "items": {"type": "integer"}},
    },
}

#: Die eine Zeile, die in den Chat geht. Keine Liste, keine Knoepfe: die
#: Auswahl ist Arbeitsmaterial fuer den naechsten Schritt, keine Entscheidung,
#: die die Gruppe abnicken muss (Birk, 05.09.2026 abends).
MELDUNG = (
    "Ich habe {anzahl} Stellen aus {interviews} als Grundlage fuer die Figuren "
    "ausgewaehlt."
)
#: Der Leerfall: es gibt Verdichtungen, aber keine passt. Auch das ist ein
#: Ergebnis -- die Figuren kommen dann allein aus dem Kernthema, und die
#: Gruppe soll wissen, warum gleich keine Interviewstelle mehr auftaucht.
MELDUNG_LEER = (
    "Kein Zitat passt zum Kernthema - die Figuren kommen dann allein aus dem "
    "Kernthema."
)


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("kernzitate")


def baue_nutzertext(kernthema: str, kernfrage: str, eintraege: list[dict]) -> str:
    """Kernthema, Kernfrage und die nummerierte Materialliste.

    Oeffentlich wie ``verdichter.baue_nutzertext``, damit ein Pruefskript
    denselben Text bauen kann wie der Betrieb. Jede Zeile traegt ihre Nummer
    vorn -- sie ist der einzige Weg, auf einen Eintrag zu zeigen."""
    zeilen = [f"Kernthema: {(kernthema or '').strip()}"]
    if (kernfrage or "").strip():
        zeilen.append("Kernfrage:\n" + kernfrage.strip())
    zeilen.append("")
    zeilen.append("Material (nur hieraus waehlen, nach Nummer):")
    for eintrag in eintraege:
        zeilen.append(
            f"[{eintrag['nummer']}] {eintrag['interview']} | "
            f"Thema: {eintrag['thema']} | "
            f"Zusammenfassung: {eintrag['zusammenfassung']} | "
            f'Zitat: "{eintrag["zitat"]}"'
        )
    return "\n".join(zeilen)


def _eintraege(conn, chat_id: int) -> list[dict]:
    """Die Materialliste: je geprueftem Thema eine Zeile mit Nummer."""
    from interview_theater import kontext

    eintraege = []
    for nummer, zeile in enumerate(repo.gepruefte_themen(conn, chat_id), start=1):
        eintraege.append(
            {
                "nummer": nummer,
                "thema_id": zeile["id"],
                "aufnahme_id": zeile["aufnahme_id"],
                "interview": kontext.interviewbezeichnung(
                    conn, chat_id, zeile["aufnahme_id"]
                ) or f"Interview {zeile['aufnahme_id']}",
                "thema": zeile["thema"] or "",
                "zusammenfassung": zeile["zusammenfassung"] or "",
                "zitat": zeile["beleg_zitat"] or "",
            }
        )
    return eintraege


def _interviewliste(namen: list[str]) -> str:
    """'Interview 3, 5 und 8' -- die Nummern, nicht die Namen (die sind oft
    Klarnamen und gehoeren nicht in den Chat, kontext.interviewbezeichnung)."""
    nummern = []
    for name in namen:
        kurz = name.replace("Interview", "").strip()
        if kurz and kurz not in nummern:
            nummern.append(kurz)
    if not nummern:
        return "den Interviews"
    if len(nummern) == 1:
        return f"Interview {nummern[0]}"
    return "Interview " + ", ".join(nummern[:-1]) + f" und {nummern[-1]}"


def waehle(klm, conn, e, chat_id: int) -> str:
    """Der eigentliche Lauf: Material holen, Modell fragen, pruefen,
    speichern. Liefert die eine Zeile fuer die Gruppe.

    Ohne Material (noch keine geprueften Themen) gibt es keinen Aufruf --
    ein Modell, das aus nichts auswaehlen soll, erfindet."""
    eintraege = _eintraege(conn, chat_id)
    if not eintraege:
        repo.ersetze_kernzitate(conn, chat_id, [])
        repo.markiere_themen_zum_kernthema(conn, chat_id, [])
        return MELDUNG_LEER

    stand = repo.hole_arbeitsstand(conn, chat_id)
    kernthema = (stand["kernthema"] if stand else "") or ""
    kernfrage = (stand["kernfrage"] if stand else "") or ""

    ergebnis = klm.schema(
        chat_id, prompt(), baue_nutzertext(kernthema, kernfrage, eintraege),
        SCHEMA, ART, modell=e.erkenner_modell,
    )

    nach_nummer = {eintrag["nummer"]: eintrag for eintrag in eintraege}
    begruendungen = [str(b or "").strip() for b in ergebnis.get("begruendungen", [])]
    wortlaute = [str(z or "").strip() for z in ergebnis.get("zitate", [])]

    gewaehlt: list[dict] = []
    interviews: list[str] = []
    for lauf, roh in enumerate(ergebnis.get("zitat_nummern", [])):
        try:
            nummer = int(roh)
        except (TypeError, ValueError):
            continue
        eintrag = nach_nummer.get(nummer)
        if eintrag is None or any(
            g["verdichtung_thema_id"] == eintrag["thema_id"] for g in gewaehlt
        ):
            # Eine Nummer, die es nicht gibt, ist genau der Fall, gegen den
            # die Nummerierung schuetzt: sie wird verworfen, nicht geraten.
            continue
        # Gespeichert wird IMMER das Original aus der Datenbank -- es ist
        # beim Verdichten schon gegen das Transkript geprueft worden (N2).
        # Der vom Modell mitgeschriebene Wortlaut wird zusaetzlich dagegen
        # gehalten: schreibt es etwas anderes hin als das Zitat, auf dessen
        # Nummer es zeigt, ist die Auswahl nicht die, die es meint -- der
        # Eintrag faellt weg statt stillschweigend zu passen.
        wortlaut = wortlaute[lauf] if lauf < len(wortlaute) else ""
        if wortlaut and not zitat.pruefe(wortlaut, eintrag["zitat"]):
            log.info(
                "Kernzitat verworfen: Wortlaut passt nicht zur Nummer %s", nummer
            )
            continue
        gewaehlt.append(
            {
                "verdichtung_thema_id": eintrag["thema_id"],
                "aufnahme_id": eintrag["aufnahme_id"],
                "zitat": eintrag["zitat"],
                "begruendung": begruendungen[lauf] if lauf < len(begruendungen) else None,
            }
        )
        interviews.append(eintrag["interview"])
        if len(gewaehlt) >= MAX_ZITATE:
            break

    # Die gefilterten Verdichtungen: was das Modell als passend nennt, plus
    # die Themen der gewaehlten Zitate -- ein Zitat ohne seine Verdichtung
    # waere eine Stelle ohne Zusammenhang.
    thema_ids: list[int] = [g["verdichtung_thema_id"] for g in gewaehlt]
    for roh in ergebnis.get("verdichtung_nummern", []):
        try:
            eintrag = nach_nummer.get(int(roh))
        except (TypeError, ValueError):
            continue
        if eintrag is not None and eintrag["thema_id"] not in thema_ids:
            thema_ids.append(eintrag["thema_id"])

    repo.ersetze_kernzitate(conn, chat_id, gewaehlt)
    repo.markiere_themen_zum_kernthema(conn, chat_id, thema_ids)

    if not gewaehlt:
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            "Kernzitate: keine Stelle passt zum Kernthema", quelle="kernzitate",
        )
        return MELDUNG_LEER

    liste = _interviewliste(interviews)
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        f"Kernzitate: {len(gewaehlt)} ausgewaehlt aus {liste}",
        quelle="kernzitate",
    )
    return MELDUNG.format(anzahl=len(gewaehlt), interviews=liste)


def _lauf(conn, tg, klm, e, chat_id: int, nachbereitung=None) -> None:
    """Der Thread-Rumpf: auswaehlen, die eine Zeile schicken, weitergehen.

    Ein Fehlschlag bleibt fuer die Gruppe **nicht** still: sie wartet gerade
    auf den naechsten Schritt (SPEC § 11.1). Deshalb geht die Nachbereitung
    (die Frage nach der Figurenanzahl) in jedem Fall los -- der Weg durch die
    Phase darf an einem Auswahl-Lauf nicht haengenbleiben."""
    try:
        meldung = waehle(klm, conn, e, chat_id)
    except Exception:
        log.exception("Kernzitat-Auswahl fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "kernzitate_fehlgeschlagen", "Kernzitat-Auswahl fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall zur Kernzitat-Auswahl nicht schreibbar")
        meldung = None
    if meldung:
        try:
            message_id = tg.sende(chat_id, meldung)
            repo.merke_nachricht(
                conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
                meldung, repo._jetzt(),
            )
        except Exception:
            log.exception("Kernzitat-Meldung fehlgeschlagen, chat_id=%s", chat_id)
    if nachbereitung is not None:
        try:
            nachbereitung()
        except Exception:
            log.exception("Nachbereitung der Kernzitate gescheitert, chat_id=%s", chat_id)


def starte(conn, tg, klm, e, chat_id: int, nachbereitung=None):
    """Gibt die Auswahl an einen eigenen Thread ab -- dasselbe Muster wie
    ``sprachprofil.starte``: ein Knopf-Handler ruft nie selbst ein Modell
    (AGENTS.md, Zusage 2).

    Liefert den Thread (fuer Tests) oder None, wenn es nichts anzustossen
    gab."""
    if klm is None:
        log.error("Kernzitat-Auswahl ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, nachbereitung), daemon=True,
    )
    thread.start()
    return thread
