"""QUICKFIX Birk, 07.10.2026 (Testgruppe Padua, chat_id 7000000000099, 07:16
UTC): ein Klick in der Phasenleiste auf eine schon besuchte Phase riss den
Anker im Chat IMMER zum (neuesten) ``▶️ Phase ...``-Eintrag, unabhaengig
davon, ob dieses Geraet die Phase zum ersten Mal sieht. Bei mehreren
schnellen Phasenwechseln (Ping-Pong 3<->4, siehe
``tests/test_erkenner_phase_rennen.py`` und
``tests/test_phasensprung_wiederherstellen.py`` fuer die serverseitigen
Gegenstuecke) sprang der Anker bei JEDEM Poll erneut, zuletzt direkt vor die
letzten zwei Zeilen -- fuer Birk sah das aus wie ein geloeschter Chatverlauf,
obwohl alle Nachrichten in der DB standen.

Regel jetzt: der Live-Sprung zum Phasenanfang (``nimmZustand``, Zweig
``phasenwechsel``) gilt nur, wenn dieses GERAET diese Phase zum ersten Mal
sieht (``ersteOeffnungInPhase``, dieselbe Pruefung wie beim Oeffnen der
Seite, ``scrolleBeimOeffnen``). Eine WIEDERHOLTE Phase verhaelt sich wie ein
gewoehnlicher neuer Zug: nur scrollen, wenn die Gruppe ohnehin schon unten
war."""

from interview_theater import web_chat


def _nimm_zustand_rumpf() -> str:
    js = web_chat._CHAT_JS
    return js[js.index("function nimmZustand"):js.index("function zeigeAntworten")]


def test_der_live_sprung_gilt_nur_beim_allerersten_sehen_dieser_phase():
    nimm = _nimm_zustand_rumpf()
    block = nimm[nimm.index("if (neu.length) {"):nimm.index("} else if ")]
    assert (
        "if (phasenwechsel && ersteOeffnungInPhase(kalSpeicher(), "
        "kalGruppeAus(location.pathname), phaseNeu)) { "
        "scrolleZuPhasenanfang(); erzwingeNachUnten = false; }"
    ) in block


def test_eine_wiederholte_phase_erzwingt_keinen_sprung():
    """Gegenprobe zum Namen: der alte, unbedingte Sprung-Aufruf darf nicht
    mehr vorkommen -- sonst waere die Bedingung oben nur Deko."""
    nimm = _nimm_zustand_rumpf()
    block = nimm[nimm.index("if (neu.length) {"):nimm.index("} else if ")]
    assert "if (phasenwechsel) { scrolleZuPhasenanfang();" not in block
