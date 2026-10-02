"""Der Vertrag des Strom-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_vereint_e2e.py``:
dass die Blase im echten Chromium waechst. Hier steht, was man am
ausgelieferten Skript messen kann -- und das ist genug, um die vier
Entscheidungen festzuhalten, die leicht verloren gehen.
"""

import re

from interview_theater import web_vereint

from tests.test_web_vereint import _hole, aufbau, aufbau_telegram  # noqa: F401


def test_der_strom_haengt_an_eventsource():
    assert "EventSource" in web_vereint._STROM_JS


def test_der_strom_zeigt_auf_die_route_die_es_gibt():
    assert f"chat/{web_vereint.STROM_PFAD}" in web_vereint._strom_js("t/")


def test_eine_abgebrochene_antwort_verschwindet_ersatzlos():
    """Entscheidung E: kein halber Text bleibt stehen."""
    assert "abgebrochen" in web_vereint._STROM_JS


def test_die_fertige_nachricht_ersetzt_die_blase_ueber_die_post_id():
    """Sonst stuende der Text zweimal da: einmal vorlaeufig, einmal echt."""
    assert "post_id" in web_vereint._STROM_JS


def test_ohne_eventsource_passiert_nichts():
    """Faellt EventSource aus, liefert der Poll die fertige Nachricht wie
    heute -- Streaming ist eine Zutat, keine Bedingung."""
    assert "window.EventSource" in web_vereint._STROM_JS


def test_reduzierte_bewegung_hat_ihre_regel():
    """Der Text erscheint trotzdem stueckweise -- das ist Information, keine
    Animation. Nur der Cursor blinkt nicht mehr."""
    assert "prefers-reduced-motion" in web_vereint._CSS_VEREINT


def test_die_blase_traegt_ihre_eigene_klasse():
    assert "vorlaeufig" in web_vereint._STROM_JS
    assert "vorlaeufig" in web_vereint._CSS_VEREINT


# -- Ueber den Brief hinaus: die Entscheidungen aus den Reviews ------------


def test_der_stromtext_geht_nie_durch_innerhtml():
    """Der Teiltext ist roher Modelltext -- gefiltert wird erst die fertige
    Nachricht (``web_chat.sichere_html``)."""
    assert "innerHTML" not in web_vereint._STROM_JS
    assert "textContent" in web_vereint._STROM_JS


def test_eine_blase_je_stromzeile():
    """Mehrere Zeilen koennen zugleich laufen (Gespraechszug + Szenenlauf):
    die Blasen haengen an der id der Zeile, nicht an einer globalen
    Variablen."""
    js = web_vereint._STROM_JS
    assert "blasen[" in js
    assert "daten.id" in js
    assert "dataset.strom" in js


def test_ein_beendetes_ende_erzeugt_keine_blase_mehr():
    """``nach=`` kann fertige Zeilen erneut liefern -- ein zweites Ende darf
    keine Blase neu anlegen."""
    js = web_vereint._STROM_JS
    assert "erledigt[daten.id]" in js


def test_der_strom_wird_geschlossen_statt_ewig_neu_verbunden():
    """Der Server schliesst, sobald nichts mehr laeuft; EventSource verbaende
    sich sonst alle ~3 s neu, fuer immer."""
    js = web_vereint._STROM_JS
    assert ".close()" in js
    assert "onerror" in js


def test_platzhalter_sind_alle_ersetzt():
    js = web_vereint._strom_js("abc/")
    assert "__" not in js
    assert "'abc/'" in js
    assert str(web_vereint.STROM_OEFFNEN_MIN_MS) in js
    assert str(web_vereint.STROM_NACHSEHEN_MS) in js


def test_web_gruppe_bekommt_den_strom_auf_der_seite(aufbau):  # noqa: F811
    basis, token, _pfad = aufbau
    status, text, _ = _hole(f"{basis}/g/{token}")
    assert status == 200
    assert "new EventSource" in text
    assert f"'{token}/'" in text
    assert re.search(r"\.blase\.vorlaeufig", text)


def test_telegram_gruppe_oeffnet_keinen_strom(aufbau_telegram):  # noqa: F811
    """Fuer eine Gruppe ohne Web-Kanal ist ``/chat/*`` 404 -- ein EventSource
    dorthin liefe ins Leere (und verbaende sich ewig neu)."""
    basis, token, _pfad = aufbau_telegram
    status, text, _ = _hole(f"{basis}/g/{token}")
    assert status == 200
    assert "EventSource" not in text
