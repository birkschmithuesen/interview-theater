"""Nachbesserung nach Aufgabe 10 (Code-Review-Befund 'Kritisch'): repo.py
serialisiert seit dieser Nachbesserung alle Zugriffe auf die geteilte
sqlite3.Connection ueber einen modulweiten ``threading.RLock``
(``repo._LOCK``/``repo._gesperrt``, siehe Moduldocstring in
``interview_theater/repo.py``).

Hintergrund: ``db.verbinde()`` oeffnet mit ``check_same_thread=False`` und
reicht EINE Connection an alle Threads eines Prozesses durch (Poll-Schleife,
8er-Pool, Nachhol-Thread, seit Aufgabe 10 auch jeder Gespraechszug). Ohne
Serialisierung fuehrt das unter echter Nebenlaeufigkeit sporadisch zu
``sqlite3.OperationalError: cannot commit - no transaction is active`` bzw.
``SystemError`` -- WAL und ``busy_timeout`` loesen nur die Dateisperre
ZWISCHEN Prozessen, nicht diese Racebedingung INNERHALB eines Prozesses.

Dieser Test belegt die Behebung unter mehreren Threads, die gleichzeitig
verschiedene Repo-Funktionen (lesend und schreibend) auf derselben
Verbindung aufrufen.
"""

import threading

import pytest

from interview_theater import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_gleichzeitige_repo_aufrufe_verschiedener_funktionen_sind_sicher(conn):
    """Sechs Threads (Schreiben von Nachrichten/Vorfaellen/Aufnahmen, Lesen
    von unbeantwortete()/letzte_nachrichten()) laufen gleichzeitig auf
    derselben Connection. Keine Ausnahme darf auftreten, jeder Thread muss
    innerhalb des Timeouts fertig werden, und am Ende muss die erwartete
    Zeilenzahl stimmen -- eine verlorene oder doppelt gezaehlte Zeile waere
    das Zeichen einer Race."""
    anzahl_je_art = 20
    ausnahmen = []
    ausnahmen_lock = threading.Lock()

    def _bewache(fn):
        try:
            fn()
        except Exception as fehler:  # sammeln statt den Test still zu verschlucken
            with ausnahmen_lock:
                ausnahmen.append(fehler)

    def schreibe_nachrichten(start_id):
        def _tun():
            for i in range(anzahl_je_art):
                repo.merke_nachricht(
                    conn, 1, start_id + i, "Ada", 0, "text", f"Text {i}", repo._jetzt(),
                )
        _bewache(_tun)

    def schreibe_vorfaelle():
        def _tun():
            for i in range(anzahl_je_art):
                repo.merke_vorfall(conn, 1, "gruppe1", "test", f"Vorfall {i}")
        _bewache(_tun)

    def schreibe_aufnahmen():
        def _tun():
            for i in range(anzahl_je_art):
                # lege_aufnahme_an ruft intern zaehle_aufnahmen auf (derselbe
                # Thread, derselbe Lock) -- genau der Fall, der RLock statt
                # Lock erzwingt.
                repo.lege_aufnahme_an(conn, 1, 3000 + i, "kurz", "sprache")
        _bewache(_tun)

    def lies_waehrenddessen():
        def _tun():
            for _ in range(anzahl_je_art):
                repo.unbeantwortete(conn, 1)
                repo.letzte_nachrichten(conn, 1)
        _bewache(_tun)

    threads = [
        threading.Thread(target=schreibe_nachrichten, args=(1000,)),
        threading.Thread(target=schreibe_nachrichten, args=(2000,)),
        threading.Thread(target=schreibe_vorfaelle),
        threading.Thread(target=schreibe_aufnahmen),
        threading.Thread(target=lies_waehrenddessen),
        threading.Thread(target=lies_waehrenddessen),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    for t in threads:
        assert not t.is_alive(), "Thread nicht innerhalb des Timeouts fertig geworden"

    assert ausnahmen == [], f"Repo-Aufrufe duerfen unter Nebenlaeufigkeit nie werfen: {ausnahmen!r}"

    nachrichten = conn.execute(
        "SELECT count(*) FROM nachricht WHERE chat_id = 1 AND message_id >= 1000"
    ).fetchone()[0]
    assert nachrichten == 2 * anzahl_je_art, "zwei Schreiber, keine Zeile verloren oder doppelt"

    vorfaelle = conn.execute(
        "SELECT count(*) FROM vorfall WHERE chat_id = 1 AND art = 'test'"
    ).fetchone()[0]
    assert vorfaelle == anzahl_je_art

    aufnahmen = conn.execute("SELECT count(*) FROM aufnahme WHERE chat_id = 1").fetchone()[0]
    assert aufnahmen == anzahl_je_art


def test_lock_ist_reentrant_lege_aufnahme_an_ruft_zaehle_aufnahmen_auf(conn):
    """Ohne RLock (ein einfacher threading.Lock) wuerde dieser Aufruf den
    Thread beim zweiten acquire() selbst blockieren: lege_aufnahme_an haelt
    den Lock schon, wenn es intern zaehle_aufnahmen aufruft. Dieser Test
    schlaegt bei einem Lock-Typ-Regress als Timeout fehl, nicht als
    Assertion -- deshalb der explizite join-Timeout."""
    fertig = threading.Event()

    def _tun():
        repo.lege_aufnahme_an(conn, 1, 4000, "kurz", "sprache")
        fertig.set()

    t = threading.Thread(target=_tun)
    t.start()
    t.join(timeout=5)
    assert not t.is_alive(), "Selbst-Deadlock: lege_aufnahme_an -> zaehle_aufnahmen braucht RLock"
    assert fertig.is_set()
