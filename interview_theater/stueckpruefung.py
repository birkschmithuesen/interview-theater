"""Die Pruefung des GANZEN Stuecks -- Phase 7, der Stueck-Judge.

**Warum es das gibt** (Birk, 06.09.2026, 09:20): *"Das ganze Stueck -- ohne
sonstige Informationen -- wird als kompletter Szenentext an ein Judge-LLM
gegeben und im Durchlauf mit neuen Fragen bewertet, die
Verbesserungsmoeglichkeiten aufzeigen: Hat das Stueck einen guten
Spannungsbogen? Sind die Figuren alle gut dargestellt? Ist es inhaltlich
spannend? Ist alles nachvollziehbar?"*

**Die Eingabe ist geschlossen -- und zwar in die andere Richtung als
ueberall sonst.** Der Szenen-Prompt bekommt Arbeitsstand, Figuren,
Schaerfungen und Chat-Notizen, damit die Szene zur Gruppe passt. Dieser
Prompt bekommt **nichts davon**: nur das Textbuch, alle Szenen im Volltext
in ihrer Reihenfolge, je Szene Nummer, Titel und Form. Kein Arbeitsstand,
keine Interviews, keine Zitate, kein Chat, kein Journal. Der Grund ist der
Zweck: der Richter soll lesen wie ein Zuschauer im Saal. Wer weiss, was
gemeint war, sieht nicht mehr, was dasteht.

**Sechs feste Fragen** (``FRAGEN``, im Prompt und hier gleich benannt):
Spannungsbogen, Figuren, Spannung, Nachvollziehbarkeit, Anfang und Ende,
Sprache und Sprechbarkeit. Je Frage kommen Bewertung (1-5), zwei Saetze
Begruendung und EIN Vorschlag mit Szenennummer zurueck -- als Marker-Bloecke
wie die VORSCHLAG-Bloecke des Gespraechs, nicht als JSON-Schema: die
Szenen-Anbieter liefern Prosa (``llm.prosa`` / ``szene_claude.prosa``), und
ein zweiter Anbieterweg nur fuer diese Pruefung waere ein zweiter Ort fuer
dieselbe Entscheidung.

**Anbieter wie der Szenenlauf**: ``IT_SZENE_ANBIETER=claude`` schickt auch
diese Pruefung ueber den Proxy (eigene ``art='stueckpruefung'`` in der
Tabelle ``aufruf``, damit Dashboard und Kosten den Weg getrennt sehen),
sonst Infomaniak. Dieselbe Bedingung wie bei der Szene: der Betreiber muss
es erlauben UND die Gruppe zugestimmt haben.

**Volltexte werden nie gekuerzt** (Birk, 06.09.2026: "Nichts darf
stillschweigend abgeschnitten werden"). Passt das Textbuch nicht ins
Budget, gibt es eine klare Fehlermeldung und keinen Lauf -- ein Urteil
ueber ein halbes Stueck waere schlimmer als keins.

**Eigener Thread, kein Modellaufruf im Knopf-Handler** (Zusage 2).
"""

from __future__ import annotations

import logging
import re
import threading

import httpx

from interview_theater import anweisungen, repo, szene_claude

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf`` -- getrennt von ``szene``,
#: obwohl derselbe Anbieter antwortet: es ist ein anderer Zweck mit einer
#: anderen Groessenordnung, und eine Kostenzeile, die beides zusammenwirft,
#: sagt nichts.
ART = "stueckpruefung"

#: Timeout und Ausgabedeckel wie beim Szenenlauf: dieselbe Groessenordnung
#: Eingabe, deutlich weniger Ausgabe (sechs Bloecke), aber ein knapper
#: Deckel ist der teurere Fehler.
TIMEOUT_S = 600.0
MAX_TOKENS = 16_000

#: Die sechs Fragen, in der Reihenfolge des Prompts. Der Schluessel ist der
#: Name, unter dem der Befund gespeichert und im Chat angesagt wird; die
#: Stichwoerter erkennen ihn in der Antwort wieder, auch wenn das Modell die
#: Ueberschrift anders schreibt ("Spannungsbogen des Stuecks").
#:
#: **Erweiterbar** (Birk): eine siebte Frage braucht eine Zeile hier und
#: einen Absatz im Prompt, sonst nichts -- Speicherung, Chat und
#: Weboberflaeche lesen aus dieser Liste.
FRAGEN: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Spannungsbogen", ("spannungsbogen", "bogen")),
    ("Figuren", ("figuren", "figur")),
    ("Spannung", ("spannung", "spannend")),
    ("Nachvollziehbarkeit", ("nachvollziehbar", "logik", "motivation")),
    ("Anfang und Ende", ("anfang", "ende", "exposition", "schluss")),
    ("Sprechbarkeit", ("sprechbarkeit", "sprache", "sprechen")),
)

#: Die Markerzeilen des Antwortformats.
_MARKER_BEFUND = "BEFUND:"
_MARKER_BEWERTUNG = "BEWERTUNG:"
_MARKER_BEGRUENDUNG = "BEGRUENDUNG:"
_MARKER_VORSCHLAG = "VORSCHLAG:"
_MARKER_SZENE = "SZENE:"

#: Was in den Chat geht, wenn die Pruefung nicht laufen konnte.
MELDUNG_OHNE_SZENEN = (
    "Ich kann das Stueck noch nicht als Ganzes lesen - es ist noch keine "
    "Szene geschrieben."
)
MELDUNG_ZU_LANG = (
    "Euer Textbuch ist laenger, als ich am Stueck lesen kann ({zeichen} "
    "Zeichen). Ich kuerze nichts davon - sagt mir Bescheid, dann sehen wir "
    "uns die Szenen einzeln an."
)
MELDUNG_FEHLGESCHLAGEN = (
    "Die Pruefung hat nicht geklappt. Ihr koennt es gleich noch einmal "
    "versuchen."
)
MELDUNG_LEER = (
    "Ich habe das Stueck gelesen, bekomme aber keinen brauchbaren Befund "
    "zurueck. Versucht es noch einmal."
)
MELDUNG_KOPF = "Ich habe euer Stueck als Ganzes gelesen - Runde {runde}:"


def prompt() -> str:
    """Heiss nachgeladen (``interview_theater.anweisungen``)."""
    return anweisungen.hole("stueckpruefung")


# ---------------------------------------------------------------------------
# Die Eingabe: NUR das Textbuch
# ---------------------------------------------------------------------------


def baue_nutzertext(conn, chat_id: int) -> str:
    """Das komplette Textbuch und **nichts sonst**.

    Je Szene: Nummer, Titel, Form und der volle Text, in der Reihenfolge der
    Szenen. Szenen ohne Volltext fallen heraus -- die Phase setzt voraus,
    dass alle geschrieben sind (``phasen.voraussetzungen[7]``), und ein
    "(noch nicht geschrieben)" im Prompt waere fuer einen Richter, der wie
    ein Zuschauer liest, eine Behauptung ueber etwas, das er nicht sieht.

    Oeffentlich wie ``verdichter.baue_nutzertext``, damit ein Pruefskript
    denselben Text bauen kann wie der Betrieb -- und damit der Negativtest
    ("keine Zitate, kein Arbeitsstand") auf genau diesen String zeigt."""
    teile: list[str] = []
    for s in repo.hole_szenen(conn, chat_id):
        volltext = (s["volltext"] or "").strip()
        if not volltext:
            continue
        kopf = f"Szene {s['nummer']}" if s["nummer"] is not None else "Szene"
        if (s["titel"] or "").strip():
            kopf += f": {s['titel'].strip()}"
        if (s["form"] or "").strip():
            kopf += f" ({s['form'].strip()})"
        teile.append(f"{kopf}\n{volltext}")
    return "\n\n".join(teile)


# ---------------------------------------------------------------------------
# Die Antwort: Marker-Bloecke
# ---------------------------------------------------------------------------


def _wert(zeile: str, marker: str) -> str:
    return zeile.split(marker, 1)[1].strip() if marker in zeile else ""


def frage_fuer(text: str) -> str | None:
    """Ordnet eine Befund-Ueberschrift einer der ``FRAGEN`` zu.

    Ueber Stichwoerter und nicht ueber Gleichheit: das Modell schreibt
    "Spannungsbogen des Stuecks" oder "Figurenzeichnung", und ein Befund,
    der nur an der Schreibweise scheitert, waere weg."""
    gefaltet = (text or "").strip().lower()
    if not gefaltet:
        return None
    for name, stichwoerter in FRAGEN:
        if name.lower() in gefaltet:
            return name
    for name, stichwoerter in FRAGEN:
        if any(s in gefaltet for s in stichwoerter):
            return name
    return None


def _zahl(text: str) -> int | None:
    """Die erste Zahl 1-5 aus einer Bewertungszeile ("3/5", "3 von 5")."""
    treffer = re.search(r"[1-5]", text or "")
    return int(treffer.group()) if treffer else None


def _szenennummer(text: str) -> int | None:
    """Die Szenennummer aus der SZENE-Zeile; None bei "-" oder Unsinn."""
    treffer = re.search(r"\d+", text or "")
    return int(treffer.group()) if treffer else None


def zerlege(antwort: str) -> list[dict]:
    """Zerlegt die Modellantwort in Befunde.

    Je ``BEFUND:``-Zeile ein Block, die folgenden Markerzeilen gehoeren
    dazu. Ein Block ohne zuordenbare Frage faellt weg (dieselbe Haltung wie
    in ``schaerfung.mappe``: verworfen, nicht geraten), ebenso ein zweiter
    Block zu einer Frage, die schon dasteht -- gefragt war einmal."""
    befunde: list[dict] = []
    aktuell: dict | None = None
    for roh in (antwort or "").splitlines():
        zeile = roh.strip().lstrip("*# ").strip()
        if zeile.startswith(_MARKER_BEFUND):
            name = frage_fuer(_wert(zeile, _MARKER_BEFUND))
            aktuell = {"frage": name} if name else None
            if aktuell is not None:
                befunde.append(aktuell)
            continue
        if aktuell is None:
            continue
        if zeile.startswith(_MARKER_BEWERTUNG):
            aktuell["bewertung"] = _zahl(_wert(zeile, _MARKER_BEWERTUNG))
        elif zeile.startswith(_MARKER_BEGRUENDUNG):
            aktuell["begruendung"] = _wert(zeile, _MARKER_BEGRUENDUNG) or None
        elif zeile.startswith(_MARKER_VORSCHLAG):
            aktuell["vorschlag"] = _wert(zeile, _MARKER_VORSCHLAG) or None
        elif zeile.startswith(_MARKER_SZENE):
            aktuell["szene_nummer"] = _szenennummer(_wert(zeile, _MARKER_SZENE))
    gesehen: set[str] = set()
    eindeutig = []
    for befund in befunde:
        if befund["frage"] in gesehen:
            continue
        gesehen.add(befund["frage"])
        eindeutig.append(befund)
    return eindeutig


def durchschnitt(zeilen) -> float | None:
    """Der Schnitt der Bewertungen einer Runde, oder None ohne Bewertung."""
    werte = [z["bewertung"] for z in zeilen if z["bewertung"] is not None]
    return sum(werte) / len(werte) if werte else None


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


class PruefungFehler(Exception):
    """Die Pruefung konnte nicht laufen -- mit einem Text fuer die Gruppe."""


def pruefe(klm, conn, e, chat_id: int) -> tuple[int, int]:
    """Der eigentliche Lauf: Textbuch bauen, Modell fragen, zerlegen,
    speichern. Liefert ``(Anzahl Befunde, Runde)``.

    Fehler fliegen als ``PruefungFehler`` mit einem Satz heraus, den der
    Aufrufer der Gruppe zeigen kann -- sie wartet gerade darauf
    (SPEC § 11.1)."""
    from interview_theater import szene as szene_modul

    nutzer = baue_nutzertext(conn, chat_id)
    if not nutzer.strip():
        raise PruefungFehler(MELDUNG_OHNE_SZENEN)

    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    budget = szene_modul.token_budget(ueber_claude)
    geschaetzt = szene_modul.schaetze_token(nutzer)
    if geschaetzt > budget:
        # **Kein Kuerzen.** Der Volltext ist der ganze Punkt dieses Aufrufs;
        # ein gekuerztes Textbuch beantwortet die Fragen nach Bogen und Ende
        # nachweislich falsch.
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "stueckpruefung_zu_lang",
                f"{len(nutzer)} Zeichen, {geschaetzt} von {budget} Token",
            )
        except Exception:
            log.exception("Vorfall stueckpruefung_zu_lang nicht geschrieben")
        raise PruefungFehler(MELDUNG_ZU_LANG.format(zeichen=len(nutzer)))

    runde = repo.letzte_pruefrunde(conn, chat_id) + 1
    system = prompt()
    if ueber_claude:
        antwort = szene_claude.prosa(
            conn, e, getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S),
            chat_id, system, nutzer, ART, timeout=TIMEOUT_S,
        )
    else:
        antwort = klm.prosa(
            chat_id, system, nutzer, ART, max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
        )

    befunde = zerlege(antwort)
    if not befunde:
        raise PruefungFehler(MELDUNG_LEER)
    anzahl = repo.lege_stueckpruefung_an(conn, chat_id, befunde, runde=runde)
    if anzahl:
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            f"Stueckpruefung Runde {runde}: {anzahl} Befunde",
            quelle="stueckpruefung",
        )
    return anzahl, runde


def _lauf(conn, tg, klm, e, chat_id: int, nachbereitung=None) -> None:
    """Der Thread-Rumpf: pruefen, die Befunde in den Chat legen, weitergehen.

    Ein Fehlschlag bleibt fuer die Gruppe **nicht** still (SPEC § 11.1). Die
    Nachbereitung laeuft in jedem Fall."""
    from interview_theater import knoepfe

    runde = 0
    from interview_theater import arbeitszeilen

    zeilen = arbeitszeilen.sichtbar(tg, chat_id, "stueckpruefung")
    try:
        _, runde = pruefe(klm, conn, e, chat_id)
    except PruefungFehler as fehler:
        zeilen.stoppe()
        _sende(conn, tg, e, chat_id, str(fehler))
    except Exception:
        log.exception("Stueckpruefung fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "stueckpruefung_fehlgeschlagen", "Stueckpruefung fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall zur Stueckpruefung nicht schreibbar")
        zeilen.stoppe()
        _sende(conn, tg, e, chat_id, MELDUNG_FEHLGESCHLAGEN)
    else:
        zeilen.stoppe()
        try:
            knoepfe.zeige_stueckpruefung(conn, tg, chat_id, runde)
        except Exception:
            log.exception("Befunde nicht zustellbar, chat_id=%s", chat_id)
    if nachbereitung is not None:
        try:
            nachbereitung()
        except Exception:
            log.exception("Nachbereitung der Stueckpruefung gescheitert, chat_id=%s", chat_id)


def _sende(conn, tg, e, chat_id: int, text: str) -> None:
    try:
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
            text, repo._jetzt(),
        )
    except Exception:
        log.exception("Meldung der Stueckpruefung fehlgeschlagen, chat_id=%s", chat_id)


def starte(conn, tg, klm, e, chat_id: int, nachbereitung=None):
    """Gibt die Pruefung an einen eigenen Thread ab -- dasselbe Muster wie
    ``schaerfung.starte`` (Zusage 2: kein Modellaufruf in einem
    Knopf-Handler).

    Liefert den Thread (fuer Tests) oder None."""
    if klm is None:
        log.error("Stueckpruefung ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, nachbereitung), daemon=True,
    )
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Was im Chat steht
# ---------------------------------------------------------------------------

#: Eine Nachricht je Frage: "Spannungsbogen 3/5 - <Begruendung>. Vorschlag:
#: Szene 2 ...". Deterministisch aus der Datenbank, kein Modellaufruf.
TEXT_BEFUND = "{frage} {bewertung}/5 - {begruendung}"
TEXT_BEFUND_OHNE_NOTE = "{frage} - {begruendung}"
TEXT_VORSCHLAG = "Vorschlag: {vorschlag}"
TEXT_VORSCHLAG_SZENE = "Vorschlag: Szene {nummer} - {vorschlag}"


def befundtext(zeile) -> str:
    """Der Text EINER Befund-Nachricht."""
    begruendung = (zeile["begruendung"] or "").strip() or "keine Begruendung."
    if zeile["bewertung"] is not None:
        kopf = TEXT_BEFUND.format(
            frage=zeile["frage"], bewertung=zeile["bewertung"],
            begruendung=begruendung,
        )
    else:
        kopf = TEXT_BEFUND_OHNE_NOTE.format(
            frage=zeile["frage"], begruendung=begruendung,
        )
    vorschlag = (zeile["vorschlag"] or "").strip()
    if not vorschlag:
        return kopf
    if zeile["szene_nummer"] is not None:
        return f"{kopf}\n{TEXT_VORSCHLAG_SZENE.format(nummer=zeile['szene_nummer'], vorschlag=vorschlag)}"
    return f"{kopf}\n{TEXT_VORSCHLAG.format(vorschlag=vorschlag)}"


def regienotiz(zeile) -> str:
    """Was als Regie-Notiz in den Szenenauftrag geht, wenn die Gruppe
    "Szene N ueberarbeiten" drueckt: der Vorschlag des Richters, mit der
    Frage davor, damit im Auftrag steht, WORAUF er zielt."""
    vorschlag = (zeile["vorschlag"] or "").strip()
    return f"{zeile['frage']}: {vorschlag}" if vorschlag else str(zeile["frage"])
