"""Die EINE Sperre, die Schaerfung und Szenenfolge voneinander trennt.

**Warum es dieses Modul gibt** (30.09.2026, Massnahme C7 aus
``docs/analyse-phase5-chaos-2026-09-06.md``). Am 06.09. lagen in Gruppe 1
zwei Vorschlagsstraenge uebereinander: 13:53:42 startete die Schaerfung aus
dem Phaseneintritt, 13:54:10 wurde der Szenenfolge-Lauf fertig, 13:54:20 kam
die naechste Schaerfung, 13:54:37 wurde die Folge gespeichert. Die Gruppe
bekam zwei unabhaengige Fragen in dasselbe Chatfenster und wusste nicht, auf
welche sie antwortet -- die eigentliche Wall of Text. Grund: ``szenenfolge``
hatte eine eigene Sperre (``_sperre_fuer``), ``schaerfung.starte`` gar keine.

**Was diese Sperre NICHT ist.** Sie koppelt ausschliesslich die
Vorschlagslaeufe: ``schaerfung`` und die vier ``starte*`` in
``szenenfolge.py``. Gespraechszug (``ablauf``), Szenenlauf (``szene``),
Prosalauf (``kurzgeschichte``) und Sprachstil behalten ihre eigenen Register
-- eine gemeinsame Sperre wuerde den Gespraechszug am Szenenlauf haengen
lassen (AGENTS.md, "Ein Sperren-Register je Nebenlaeufigkeit").

**Nichts geht verloren.** Wer die Sperre nicht bekommt, legt seinen Auftrag
auf einen Merkplatz (einen je ``(chat_id, art)``); ``gib_frei`` gibt zuerst
die Sperre zurueck und startet danach, was gemerkt wurde. Ein Platz je art
und nicht eine Warteschlange: zwei nachgeholte Schaerfungslaeufe wuerden
zweimal dasselbe Geld fuer dasselbe Ergebnis kosten.

**Bekannte Grenze:** der Merkplatz liegt im Prozess, nicht in der Datenbank.
Ein Neustart zwischen Ankuendigung und Nachholen verliert den gemerkten
Auftrag -- wie bei jeder anderen Thread-Sperre im Repo
(``szenenfolge._regienotiz_erwartet``, ``szene._usa_erinnerungen``). Die
harmlose Fehlerrichtung: die Gruppe fragt noch einmal, und der Knopf steht
weiter da.

Keine Importe aus dem Projekt: dieses Modul kennt weder Datenbank noch
Telegram noch Modell. Damit ist es von beiden Aufrufern aus importierbar,
ohne einen Zyklus zu bauen.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)

#: Eine Sperre je chat_id. Lebt fuer die Laufzeit des Prozesses; ein paar
#: Bytes je jemals gesehener Gruppe sind kein Problem (wie ``ablauf._sperren``).
_sperren: dict[int, threading.Lock] = {}

#: Ein Merkplatz je chat_id, darin einer je Auftragsart.
_gemerkt: dict[int, dict[str, Callable[[], None]]] = {}

#: Schuetzt die beiden Register -- nicht die Laeufe.
_schutz = threading.Lock()


def sperre_fuer(chat_id: int) -> threading.Lock:
    """Die (ggf. neu angelegte) Sperre dieser Gruppe.

    Oeffentlich, weil Tests darauf warten: ``acquire(timeout=10)`` auf
    dasselbe Objekt ist die Art, auf das Ende eines Laufs zu warten, ohne zu
    schlafen (``tests/test_szenenfolge.py``)."""
    with _schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def nimm(chat_id: int) -> bool:
    """Versucht, die Sperre zu nehmen, ohne zu warten. True heisst: du hast
    sie, und du gibst sie mit ``gib_frei`` zurueck."""
    return sperre_fuer(chat_id).acquire(blocking=False)


def laeuft(chat_id: int) -> bool:
    """Haelt gerade jemand die Sperre dieser Gruppe?"""
    return sperre_fuer(chat_id).locked()


def merke(chat_id: int, art: str, auftrag: Callable[[], None]) -> bool:
    """Legt einen Auftrag auf den Merkplatz dieser Art. Liefert True.

    Ein zweiter Auftrag derselben art ersetzt den ersten: was gerade gefragt
    wurde, ist aktueller als das, was vor zwei Minuten gefragt wurde."""
    with _schutz:
        _gemerkt.setdefault(chat_id, {})[art] = auftrag
    return True


def gemerkte_arten(chat_id: int) -> list[str]:
    """Welche Arten warten? Fuer Tests und fuer das Log."""
    with _schutz:
        return list(_gemerkt.get(chat_id, {}))


def gib_frei(chat_id: int) -> None:
    """Gibt die Sperre zurueck und holt nach, was gemerkt wurde.

    **Erst freigeben, dann nachholen** -- der gemerkte Auftrag nimmt die
    Sperre selbst wieder (er laeuft ueber dieselbe ``starte``-Funktion wie
    beim ersten Versuch). In der anderen Reihenfolge bekaeme er nur die
    Wartemeldung, die er gerade abarbeitet.

    Robust gegen den Fall, dass niemand genommen hat: ``finally``-Zweige
    geben in JEDEM Fall frei (wie ``szenenfolge._lauf``), und ein
    ``RuntimeError`` dort duerfte einen Lauf nicht nachtraeglich als
    gescheitert dastehen lassen."""
    with _schutz:
        sperre = _sperren.get(chat_id)
        nachzuholen = list(_gemerkt.pop(chat_id, {}).items())
    if sperre is not None and sperre.locked():
        try:
            sperre.release()
        except RuntimeError:  # pragma: no cover -- Verteidigung, kein Weg
            log.exception("Vorschlagssperre war schon frei, chat_id=%s", chat_id)
    for art, auftrag in nachzuholen:
        log.info("Gemerkten Vorschlagslauf nachgeholt, chat_id=%s, art=%s",
                 chat_id, art)
        try:
            auftrag()
        except Exception:
            log.exception(
                "Gemerkter Vorschlagslauf fehlgeschlagen, chat_id=%s, art=%s",
                chat_id, art,
            )


def vergiss(chat_id: int) -> None:
    """Raeumt Sperre und Merkplatz dieser Gruppe ab -- fuer Tests.

    Im Betrieb gibt es keinen Anlass: ein Prozess je Gruppe, und die Sperre
    lebt so lange wie er."""
    with _schutz:
        _sperren.pop(chat_id, None)
        _gemerkt.pop(chat_id, None)
