"""Die vereinte Gruppenseite: drei Tabs, eine Phasenuebersicht, ein Strom
(30.09.2026, Karte W).

**Warum es dieses Modul gibt.** ``web.py`` traegt schon Dashboard,
Gruppenseite, Probenansicht und Leitfaden; ``web_chat.py`` (Karte A2) den
Chat. Was hier dazukommt -- die Klammer um alle drei, die Phasenleiste und
der SSE-Kanal -- gehoert in keins von beiden, und beide sind Hotspots
mehrerer Karten. Also ein eigenes Modul, das von ``web.py`` nur ueber
Routing-Zeilen erreicht wird.

**Der Strom ist die einzige Ausnahme von A2s "kein SSE".** Fuer alles andere
bleibt der Poll aus ``web_chat``; hier geht es um Teiltexte im
Zehntelsekunden-Takt, und dafuer ist ein Poll je Delta das falsche Werkzeug.
Faellt ``EventSource`` aus, zeigt der Poll die fertige Nachricht wie heute --
Streaming ist eine Zutat, keine Bedingung.

Kein Modellaufruf, kein ``repo``: read-only ueber ``web_daten``, wie der
Rest der Leseseite.
"""

import json
import time
import urllib.parse

from interview_theater import web_daten

#: Der Unterpfad unter ``/g/<token>/chat/``.
STROM_PFAD = "strom"

#: Wie oft der Server nach neuem Text sieht -- derselbe Takt, in dem der Bot
#: schreibt (``strom.INTERVALL_S``). Schneller zu pollen faende nichts,
#: langsamer machte den Strom ruckelig.
STROM_TAKT_S = 0.15

#: Eine Kommentarzeile alle 15 s haelt die Verbindung durch Proxys am Leben,
#: die stille Verbindungen nach 30-60 s schliessen.
STROM_KEEPALIVE_S = 15.0

#: Nach fuenf Minuten wird die Verbindung geschlossen, auch wenn noch etwas
#: laeuft. ``ThreadingHTTPServer`` bindet je Verbindung einen Thread; der
#: Browser verbindet sich von selbst neu (das ist EventSource eingebaut), und
#: ein Reconnect auf eine fertige Zeile liefert sofort das Ende.
STROM_MAX_S = 300.0

#: Der Zustand einer Zeile, solange der Bot an ihr schreibt
#: (= ``repo.STROM_LAEUFT``; ``repo`` wird hier bewusst nicht importiert).
_LAEUFT = "laeuft"


def _kopf(handler) -> None:
    """Die Kopfzeilen eines Ereignisstroms.

    ``protocol_version`` ist ``HTTP/1.1`` (``web._Basishandler``), und dieser
    Antwort fehlt die ``Content-Length``: ohne ``Connection: close`` wartete
    der Browser auf einen weiteren Request auf derselben Verbindung.
    ``X-Accel-Buffering: no`` ist fuer nginx -- ohne das puffert der
    Reverse-Proxy den ganzen Strom zu einem Block (ANNAHME 6)."""
    handler.close_connection = True
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    handler.send_header("Connection", "close")
    handler.end_headers()


def _schicke(handler, daten: dict) -> bool:
    """Ein Ereignis. ``False``, wenn der Browser weg ist -- dann endet der
    Strom still (kein Vorfall: ein zugeklappter Tab ist kein Fehler)."""
    try:
        handler.wfile.write(
            f"data: {json.dumps(daten, ensure_ascii=False)}\n\n".encode("utf-8")
        )
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def _lebt(handler) -> bool:
    try:
        handler.wfile.write(b": ping\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def _nach(query: str) -> int:
    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return 0
    roh = (werte.get("nach") or ["0"])[0]
    return int(roh) if roh.isdigit() else 0


def _lies(db_pfad: str, funktion, *argumente):
    """Eine Abfrage auf einer frischen read-only Verbindung: eine ueber
    Minuten offen gehaltene Leseverbindung saehe wegen der WAL-Momentaufnahme
    den Fortschritt des Bots gar nicht."""
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        return funktion(conn, *argumente)
    finally:
        conn.close()


def sende_strom(handler, db_pfad: str, token: str, query: str) -> None:
    """``GET /g/<token>/chat/strom`` -- die Teiltexte der laufenden Aufrufe.

    Pro Gruppe koennen **mehrere** Zeilen zugleich laufen (ein Prosalauf und
    ein Gespraechszug, Befund aus Aufgabe 7). Deshalb liefert der Strom
    Ereignisse **je Zeile** -- jedes traegt seine ``id`` -- fuer alle Zeilen ab
    ``web_daten.web_stromanfang``, und er endet erst, wenn keine davon mehr
    laeuft (oder der Browser weg ist, oder nach ``STROM_MAX_S``). Eine Zeile,
    die waehrend der Verbindung beginnt, kommt mit.

    Ein Ereignis geht raus, wenn sich Text, Zustand oder ``post_id`` einer
    Zeile geaendert haben; das Ende einer Zeile kommt genau einmal."""
    from interview_theater import web

    chat_id = _lies(db_pfad, web_daten.web_chat_id_nach_token, token)
    if chat_id is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return

    _kopf(handler)
    anfang = _lies(db_pfad, web_daten.web_stromanfang, chat_id, _nach(query))
    if anfang is None:
        return
    gesendet: dict[int, tuple] = {}
    letztes_lebenszeichen = time.monotonic()
    ende = time.monotonic() + STROM_MAX_S
    while time.monotonic() < ende:
        zeilen = _lies(db_pfad, web_daten.web_stromzeilen, chat_id, anfang)
        for zeile in zeilen:
            stand = (zeile["text"], zeile["zustand"], zeile["post_id"])
            if gesendet.get(zeile["id"]) == stand:
                continue
            if not _schicke(handler, zeile):
                return
            gesendet[zeile["id"]] = stand
            letztes_lebenszeichen = time.monotonic()
        if not any(zeile["zustand"] == _LAEUFT for zeile in zeilen):
            return
        if time.monotonic() - letztes_lebenszeichen >= STROM_KEEPALIVE_S:
            if not _lebt(handler):
                return
            letztes_lebenszeichen = time.monotonic()
        time.sleep(STROM_TAKT_S)
