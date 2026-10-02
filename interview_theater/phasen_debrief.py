"""Der Phasen-Debrief: ein kurzer, automatischer Rueckblick je verlassener
Arbeitsphase -- Geschmack, Ton, Arbeitsweise, NIE Inhalt (Karte
phasen-debrief).

**Warum es das gibt.** Was eine Gruppe in Phase 4 ueber sich selbst zeigt --
mag sie es duester, entscheidet sie schnell oder ringt sie lange, zieht ein
Bild mehr als ein Argument -- geht heute mit dem Ende der Phase verloren: der
Arbeitsstand haelt Ergebnisse fest, nicht die Art, wie die Gruppe zu ihnen
gekommen ist. Der Debrief ist das Gegenstueck zur Verdichtung eines
Interviews, nur ueber das Gespraech der Gruppe MIT dem Bot statt ueber ein
Interview MIT einer dritten Person.

**Ausgeloest wird er an genau einer Stelle: ``phasen.setze``.** Jede der
fuenf Code-Stellen, an denen eine Phase tatsaechlich wechselt, ruft
``phasen.setze`` -- die Dispatch-Zeile steht deshalb dort und nirgends sonst
(Karte phasen-debrief, Schritt 7). Dieses Modul kennt die Phase nur als
Zahl, nie als laufenden Zustand.

**Ein Hintergrundjob wie ``kernzitate``/``sprachprofil``**: ``starte`` prueft
schnell (Umschalter, Mindestnachrichten) und liefert sofort, der eigentliche
Modellaufruf laeuft in einem eigenen Thread. Kein ``tg``, keine
Chatnachricht -- der Debrief ist Material fuer spaetere Phasen und den
Szenenlauf (Folgekarten), keine Meldung an die Gruppe.

**Die Modellwahl folgt der VERLASSENEN Phase, nicht der aktuellen.** Ab
Phase 4 darf -- wie das Gespraech selbst -- Claude laufen, wenn der Betreiber
es erlaubt und die Gruppe einmal zugestimmt hat. Anders als
``modellwahl.konversation_ueber_claude`` (das die *aktuelle* Phase der
Gruppe liest) gilt hier die Phase, die gerade verlassen wird -- ein Debrief
urteilt rueckblickend, und bis der Thread laeuft, kann die Gruppe
laengst weiter sein.

**Kein Zitat, keine Zeile.** Der Prompt (``prompts/phasen_debrief.md``)
verlangt zu jeder Aussage ein woertliches Kurzzitat; eine Zeile ohne Zitat
oder mit einem erfundenen Zitat wird herausgefiltert (``zitat.pruefe``,
dieselbe Pruefung wie beim Verdichter, bei Kernzitaten, Schaerfung und
Dramaturgie). Antwortet das Modell ``NICHTS`` (die Phase gibt nichts her),
wird nichts gespeichert.

**Verlaesst die Gruppe dieselbe Phase ein zweites Mal** (zurueck und wieder
vor), ersetzt der neue Debrief den alten (``repo.merke_phasen_debrief``,
Upsert ueber ``chat_id, phase``) -- der alte galt fuer einen Stand, den es
nicht mehr gibt."""

from __future__ import annotations

import logging
import os
import re
import threading

from interview_theater import anweisungen, modellwahl, phasen, repo, szene_claude, zitat
from interview_theater.knoepfe.texte import PHASE_SETTING

log = logging.getLogger(__name__)

#: Abschalten fuer den ganzen Workshop (Betreiber). Alles ausser den drei
#: Werten "0"/"aus"/"off" (gross-/kleingeschrieben) gilt als an -- dieselbe
#: Schreibweise wie bei anderen Umschaltern in diesem Repo.
_ENV_AN = "IT_PHASEN_DEBRIEF"
_ENV_MINDEST = "IT_DEBRIEF_MIN_NACHRICHTEN"
#: Unter dieser Zahl an GRUPPEN-Nachrichten (Bot-Zeilen zaehlen nicht mit)
#: lohnt kein Aufruf -- eine Phase, die in drei Saetzen durchlief, hat keinen
#: Geschmack zu zeigen.
_MINDEST_VORGABE = 6


def _aktiv() -> bool:
    """Hot-read wie ``kontext._aus_umgebung`` -- keine Caching-Schicht, eine
    geaenderte Env-Variable wirkt beim naechsten Phasenwechsel."""
    wert = (os.environ.get(_ENV_AN) or "").strip().lower()
    return wert not in ("0", "aus", "off")


def _mindest_nachrichten() -> int:
    roh = os.environ.get(_ENV_MINDEST)
    try:
        n = int(roh) if roh else _MINDEST_VORGABE
    except ValueError:
        n = _MINDEST_VORGABE
    return max(n, 0)


#: Das Schema des einen Modellaufrufs: ein Fliesstext, kein Objekt -- der
#: Prompt verlangt vier moegliche Abschnitte, aber die Gliederung ist Sache
#: des Modells, nicht ein Pflichtfeld je Abschnitt (manche duerfen fehlen).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["antwort"],
    "properties": {"antwort": {"type": "string"}},
}

#: Art dieses Aufrufs in der Tabelle ``aufruf``.
ART = "phasen_debrief"


# --- Das Phasenfenster -------------------------------------------------------


#: Journalzeilen eines Phasenwechsels beginnen immer so (``phasen.setze``:
#: ``f"Phase {bezeichnung(nummer)}"``) -- ``bezeichnung`` haengt Kurzname und
#: ggf. einen Klammerzusatz an, das Muster greift trotzdem, weil es nur den
#: Kopf der Zeile braucht.
_PHASE_MUSTER = re.compile(r"^Phase (\d+)\b")


def _phasenfenster(conn, chat_id: int, phase: int) -> tuple[str, str]:
    """(von, bis) fuer die zuletzt VERLASSENE Phase ``phase``. ``bis`` ist
    jetzt -- der Debrief liest alles bis zu diesem Aufruf, nicht nur bis zum
    Wechsel (der Thread startet erst, nachdem ``phasen.setze`` schon
    geschrieben hat, aber in der Sekunde dazwischen ist nichts Neues
    entstanden).

    ``von`` ist der juengste Eintritt in GENAU diese Phase laut Journal --
    "juengster Treffer gewinnt" deckt den Fall, dass die Gruppe schon einmal
    dort war, zurueckging und wieder kam. Ohne einen einzigen Journaleintrag
    (die allererste Phase der Gruppe) gilt die allererste Nachricht."""
    bis = repo._jetzt()
    von = None
    for eintrag in repo.journal(conn, chat_id):
        treffer = _PHASE_MUSTER.match(eintrag["text"] or "")
        if treffer and int(treffer.group(1)) == phase:
            von = eintrag["erstellt_am"]
    if von is None:
        von = repo.erste_nachricht_am(conn, chat_id) or bis
    return von, bis


def _gruppennachrichten_anzahl(zeilen) -> int:
    return sum(1 for z in zeilen if not z["ist_bot"])


def _korpus(zeilen) -> str:
    """Der Rohtext aller Zeilen -- Grundlage des Zitat-Checks. Transkript-
    Echos stehen hier nie: ``repo.nachrichten_zwischen`` schliesst
    ``typ='transkript'`` schon aus (wie jedes andere Fenster, SPEC § 10.6)."""
    return "\n".join((z["text"] or "") for z in zeilen)


def _nachrichtentext(zeilen) -> str:
    """Der Verlauf fuer den Prompt: 'Absender: Text' je Zeile."""
    return "\n".join(
        f"{z['absender'] or ('Bot' if z['ist_bot'] else 'Gruppe')}: {z['text'] or ''}"
        for z in zeilen
    )


def _bereits_gespeichert(conn, chat_id: int) -> str:
    """Was die Gruppe fuer diese Phase schon festgelegt hat, als Text --
    dieselbe Darstellung wie im Gespraechs-Prompt (keine zweite Wahrheit):
    Arbeitsstand plus die Auffangtabelle der Festlegungen. Lokaler Import
    wie ueberall im Repo, wo ein Modul sonst zyklisch importieren muesste
    (``kernzitate._eintraege`` macht es mit ``kontext`` genauso)."""
    from interview_theater import kontext

    bloecke = [
        block
        for block in (
            kontext._baue_arbeitsstand(conn, chat_id),
            kontext._baue_festlegungen(conn, chat_id),
        )
        if block
    ]
    return "\n\n".join(bloecke)


_ZEILE_SCHON_GESPEICHERT = "Schon gespeichert (nicht wiederholen):\n"


def _nutzertext(conn, chat_id: int, zeilen) -> str:
    teile = []
    bereits = _bereits_gespeichert(conn, chat_id)
    if bereits:
        teile.append(_ZEILE_SCHON_GESPEICHERT + bereits)
    teile.append(_nachrichtentext(zeilen))
    return "\n\n".join(teile)


# --- Modellwahl ---------------------------------------------------------------


def _ueber_claude(e, conn, chat_id: int, phase: int) -> bool:
    """True, wenn DIESER Debrief auf Claude laufen soll.

    Absichtlich NICHT ``modellwahl.konversation_ueber_claude`` wiederverwendet:
    das liest die AKTUELLE Phase der Gruppe, hier zaehlt die Phase, die
    gerade verlassen wird -- bis der Thread laeuft, kann die Gruppe laengst
    in einer anderen Phase stehen."""
    return phase >= PHASE_SETTING and szene_claude.ist_aktiv(e, conn, chat_id)


def _rufe_modell(conn, klm, e, chat_id: int, phase: int, phasenname: str,
                  nutzertext: str) -> str | None:
    system = (
        anweisungen.hole("phasen_debrief")
        .replace("{nummer}", str(phase))
        .replace("{phasenname}", phasenname)
    )
    try:
        antwort = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system, nutzertext, SCHEMA, ART,
            ueber_claude=_ueber_claude(e, conn, chat_id, phase),
        )
    except Exception:
        log.exception(
            "Phasen-Debrief: Modellaufruf fehlgeschlagen, chat_id=%s, phase=%s",
            chat_id, phase,
        )
        return None
    return (antwort or {}).get("antwort")


# --- Der Zitat-Filter ----------------------------------------------------------


#: Dieselben Anfuehrungszeichen, die ``zitat.normalisiere`` auf gerade
#: abbildet (``zitat._ERSETZUNGEN``) -- auf die DOPPELTEN beschraenkt, weil
#: der Prompt nach einem woertlichen SATZ fragt, keinem einzelnen Wort in
#: einfachen Anfuehrungszeichen. Bewusst dupliziert statt importiert: die
#: beiden Module sollen unabhaengig voneinander lesbar bleiben, und eine
#: Aenderung an ``zitat._ERSETZUNGEN`` ist selten genug, dass ein Test hier
#: reicht, um eine Drift aufzufangen (siehe ``test_zitat.py``).
_ANFUEHRUNG = str.maketrans({"„": '"', "“": '"', "”": '"', "»": '"', "«": '"'})
_ZITAT_MUSTER = re.compile(r'"([^"\n]+)"')

#: Der Leerfall: das Modell sagt selbst, dass diese Phase nichts hergibt.
_NICHTS = "nichts"


def _zitate_in_zeile(zeile: str) -> list[str]:
    return _ZITAT_MUSTER.findall(zeile.translate(_ANFUEHRUNG))


def _gefiltert(antwort: str, korpus: str) -> str:
    """Zeile fuer Zeile: keine Aussage ohne belegtes Zitat.

    Eine Zeile OHNE jedes Zitat faellt weg (der Prompt verlangt zu jeder
    Aussage eines), eine Zeile MIT Zitat(en) bleibt nur, wenn JEDES ihrer
    Zitate gegen den rohen Nachrichtentext dieser Phase besteht
    (``zitat.pruefe`` normalisiert selbst). Leere Zeilen (Absatztrenner)
    bleiben erhalten, damit die Gliederung des Modells ueberlebt."""
    if not antwort or antwort.strip().strip(".").lower() == _NICHTS:
        return ""
    behalten: list[str] = []
    for zeile in antwort.splitlines():
        if not zeile.strip():
            behalten.append(zeile)
            continue
        zitate = _zitate_in_zeile(zeile)
        if not zitate:
            continue
        if all(zitat.pruefe(z, korpus) for z in zitate):
            behalten.append(zeile)
    return "\n".join(behalten).strip()


# --- Der Job selbst -------------------------------------------------------


def starte(conn, klm, e, chat_id: int, phase: int) -> threading.Thread | None:
    """Stoesst den Debrief fuer die verlassene Phase ``phase`` an, wenn der
    Betreiber es nicht abgeschaltet hat und genug gesprochen wurde. Liefert
    sofort (kein Modellaufruf in diesem Aufruf), wie ``kernzitate.starte``."""
    if klm is None or not _aktiv():
        return None
    von, bis = _phasenfenster(conn, chat_id, phase)
    zeilen = repo.nachrichten_zwischen(conn, chat_id, von, bis)
    if _gruppennachrichten_anzahl(zeilen) < _mindest_nachrichten():
        return None
    thread = threading.Thread(
        target=_lauf, args=(conn, klm, e, chat_id, phase, zeilen), daemon=True,
    )
    thread.start()
    return thread


def _lauf(conn, klm, e, chat_id: int, phase: int, zeilen) -> None:
    """Der Thread-Rumpf: fragen, pruefen, speichern. Ein Fehlschlag bleibt
    fuer die Gruppe unsichtbar (SPEC § 11.1) -- niemand wartet auf einen
    Debrief, er ist Material fuer spaeter."""
    try:
        phasenname = phasen.bezeichnung(phase)
        nutzertext = _nutzertext(conn, chat_id, zeilen)
        antwort = _rufe_modell(conn, klm, e, chat_id, phase, phasenname, nutzertext)
        if not antwort:
            return
        text = _gefiltert(antwort, _korpus(zeilen))
        if not text:
            return
        # Bestenfalls geschaetztes Label: faellt der Claude-Pfad zur Laufzeit
        # auf das souveraene Modell zurueck (``modellwahl.aufruf_schema``),
        # weiss diese Funktion das nicht mehr -- ``_ueber_claude`` prueft nur
        # noch einmal dieselben Bedingungen (Phase, Einwilligung). Fuer die
        # Dashboardzeile reicht das; etwas, das eine Entscheidung TRAEGT,
        # ist es nicht (vgl. ``kosten.py``s genaue Buchung).
        modell = "claude" if _ueber_claude(e, conn, chat_id, phase) else "sovereign"
        repo.merke_phasen_debrief(conn, chat_id, phase, text, modell)
    except Exception:
        log.exception(
            "Phasen-Debrief fehlgeschlagen, chat_id=%s, phase=%s", chat_id, phase,
        )
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), "phasen_debrief_fehler",
                f"Phasen-Debrief fuer Phase {phase} fehlgeschlagen",
            )
        except Exception:
            log.exception(
                "Vorfall phasen_debrief_fehler nicht geschrieben, chat_id=%s", chat_id,
            )
