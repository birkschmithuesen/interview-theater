"""Aufgabe 12 (Padua Phase 1+2 Umbau, 03.10.2026): die isolierten KI-Fragen
fuer den A/B-Vergleich eigene-vs-KI-Fragen in Phase 2.

Birk: "wie man das hinbekommt, dass die KI eigene Fragen entwickelt, ohne
dass die Fragen von den Studierenden uebernommen werden. Also es soll
wirklich ein sauberer A-B-Vergleich sein. [...] dass die Fragen von der KI
im Hintergrund schon entwickelt werden, bevor die Fragen von den Usern
eingesprochen werden, weil sonst weiss die KI ja die Fragen der User."
(AB-AENDERUNG-PHASE2.md).

**Beim Eintritt in Phase 2, nicht danach.** ``starte`` laeuft aus
``knoepfe/stationen.py::eintritt_in_phase`` an -- noch bevor die Gruppe eine
einzige eigene Frage geschrieben hat. Gespeichert wird sofort mit
Zeitstempel (``fragen_ki_erzeugt_am``), aber fuer die Gruppe versteckt, bis
die Gegenueberstellung so weit ist (Aufgabe 13).

**Kontext-Isolation per Code, nicht per Prompt** (AB-AENDERUNG-PHASE2.md
Punkt 2): ``_nutzertext`` nimmt NUR ``begriffe``/``diskussion_text`` als
Klartext entgegen -- keine ``conn``, keine ``chat_id`` in der Signatur.
Dieser Aufruf kann strukturell nichts anderes sehen als die Begriffe und,
falls vorhanden, die Verdichtung der Phase-1-Hintergrunddiskussion -- kein
``kontext.baue``, kein Phase-2-Chatfenster, keine eigene Frage der Gruppe.

**Kein Nachbessern** (Punkt 3): einmal erzeugt, bleibt
``fragen_ki_vorschlag`` stehen. Faellt der Hintergrundlauf aus, bleibt das
Feld leer, und ein spaeterer Aufruf von ``starte`` (z.B. ein erneuter
Phase-2-Eintritt) ist damit automatisch ein zulaessiger Retry -- derselbe
isolierte Nutzertext, keine zusaetzliche Wiederholungslogik noetig.

Nach einem erfolgreichen, nicht-leeren Lauf wird
``knoepfe.fragen.versuche_gegenueberstellung`` angestossen (Aufgabe 13, noch
nicht gebaut): sie prueft, ob BEIDE Seiten -- KI und Gruppe -- fertig sind,
und zeigt dann die Gegenueberstellung. Ein gescheiterter oder leerer Lauf
ruft sie nicht auf, weil die Gegenueberstellung ohne echten KI-Inhalt
nichts zu vergleichen haette.

**Dasselbe Sperrenmuster wie ``diskussion.py``** (``versuche_start``/
``beende``), hier bewusst noch einmal geschrieben statt importiert: eine
gemeinsame Sperre wuerde die Hintergrund-Diskussion (Phase 1) und die
KI-Fragen (Phase 2) aneinanderketten, obwohl die beiden nie gleichzeitig
eine Gruppe betreffen (AGENTS.md: "Gleicher Code, verschiedene Sperren")."""

import logging
import threading

from interview_theater import anweisungen, modellwahl, repo, workshop
from interview_theater import begriffe as begriffe_modul

log = logging.getLogger(__name__)

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["antwort"],
    "properties": {
        "antwort": {"type": "string"},
    },
}

ART = "fragen_ki_vorschlag"


def _nutzertext(begriffe: str, diskussion_text: str | None) -> str:
    """Der isolierte Nutzertext -- NUR die Begriffe und, falls vorhanden, die
    Verdichtung einer vorangegangenen Diskussion. Kein ``conn``, keine
    ``chat_id`` in der Signatur: dieser Aufruf kann strukturell nichts
    anderes sehen, insbesondere keine eigene Frage der Gruppe."""
    liste = begriffe_modul.zerlege(begriffe)
    text = "Die Begriffe der Gruppe:\n" + "\n".join(f"- {b}" for b in liste)
    if diskussion_text and diskussion_text.strip():
        text += (
            "\n\nVerdichtung einer vorangegangenen Diskussion der Gruppe "
            "(nur Hintergrund, kein Diktat):\n" + diskussion_text.strip()
        )
    return text


#: Ein Sperren-Register je Nebenlaeufigkeit (AGENTS.md: "Gleicher Code,
#: verschiedene Sperren"), in Form kopiert aus ``diskussion.py``: nie mehr
#: als ein KI-Fragen-Lauf je Gruppe gleichzeitig.
_LAEUFT_LOCK = threading.Lock()
_LAEUFT: set[int] = set()


def versuche_start(chat_id: int) -> bool:
    """True und merkt sich den Lauf, wenn fuer diese Gruppe gerade KEIN
    KI-Fragen-Lauf laeuft -- sonst False, ohne etwas zu veraendern."""
    with _LAEUFT_LOCK:
        if chat_id in _LAEUFT:
            return False
        _LAEUFT.add(chat_id)
        return True


def beende(chat_id: int) -> None:
    """Gibt die Sperre wieder frei -- immer in einem ``finally``, auch nach
    einem Fehlschlag oder einem fruehen Abbruch vor dem Thread-Start."""
    with _LAEUFT_LOCK:
        _LAEUFT.discard(chat_id)


def starte(conn, tg, klm, e, chat_id: int) -> None:
    """Stoesst den EINEN isolierten KI-Fragen-Lauf dieser Gruppe an.

    Kein Modellaufruf hier selbst (Zusage 2): der eigentliche Aufruf laeuft
    in einem eigenen Thread. Diese Funktion prueft nur, ob ueberhaupt etwas
    zu tun ist, und gibt die Sperre selbst zurueck, wenn sie es doch nicht
    ist -- sonst gaebe niemand sie je wieder frei.

    Idempotent (kein Nachbessern): ist ``fragen_ki_vorschlag`` schon
    gesetzt, passiert nichts -- weder ein zweiter Modellaufruf noch eine
    Aenderung des gespeicherten Werts."""
    if klm is None:
        return
    if not workshop.fragen_ab_aktiv():
        return

    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is not None and stand["fragen_ki_vorschlag"]:
        return

    if not versuche_start(chat_id):
        return

    begriffe_feld = stand["begriffe"] if stand is not None else None
    diskussion_text = repo.diskussion_verdichtung_text(conn, chat_id)

    def _lauf() -> None:
        try:
            nutzertext = _nutzertext(begriffe_feld or "", diskussion_text)
            ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
            ergebnis = modellwahl.aufruf_schema(
                conn, klm, e, chat_id,
                system=anweisungen.hole("fragen_ki_vorschlag"),
                nutzer=nutzertext, schema=SCHEMA, art=ART,
                ueber_claude=ueber_claude,
            )
            antwort = (ergebnis.get("antwort") or "").strip()
            if not antwort:
                return
            repo.setze_arbeitsstand(conn, chat_id, "fragen_ki_vorschlag", antwort)
            repo.setze_arbeitsstand(
                conn, chat_id, "fragen_ki_erzeugt_am", repo._jetzt(),
            )

            from interview_theater.knoepfe import fragen as fragen_modul

            fragen_modul.versuche_gegenueberstellung(conn, tg, chat_id)
        except Exception:
            log.exception("KI-Fragen-Lauf fehlgeschlagen, chat_id=%s", chat_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "fragen_ki_fehler",
                    f"KI-Fragen-Lauf fehlgeschlagen fuer chat_id={chat_id}",
                )
            except Exception:
                log.exception(
                    "Vorfall fragen_ki_fehler nicht geschrieben, chat_id=%s",
                    chat_id,
                )
        finally:
            beende(chat_id)

    threading.Thread(target=_lauf, daemon=True).start()
