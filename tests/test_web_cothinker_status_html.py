"""Die CoThinker-Statuszeile ueber dem Buehne-Panel (Task 4, 03.10.2026).

Gemessen wird reine Darstellung, ohne HTTP und ohne Datenbank:
``web._cothinker_status_html`` baut aus dem Dict, das ``web_daten.
cothinker_status`` (Task 3) liefert, genau die Markup-Zeile, die
``web_vereint._VEREINT_JS`` danach per ``data-seit``/``data-tickt``
sekuendlich weiterrechnet.

Die harte Regel der Karte: die tickende Dauer selbst steht NIE im
servergerenderten HTML (nur ``data-seit`` als Rohwert) -- sonst taeuschte
sich ``web_vereint.py``s ``ladeBuehne()`` bei jedem Poll eine echte
Aenderung vor und tauschte das ganze Panel unnoetig aus.

Alle Daten sind erfunden."""

import re

from interview_theater import db, repo, web, web_chat, web_daten, web_vereint


def test_ohne_status_leerer_string():
    assert web._cothinker_status_html(None) == ""


def test_denkt_traegt_attribute_text_und_tickt():
    html = web._cothinker_status_html(
        {"zustand": "denkt", "seit": "2026-10-03T12:00:00+00:00"}
    )
    assert 'id="cothinker-status"' in html
    assert 'class="co-status co-denkt"' in html
    assert 'data-zustand="denkt"' in html
    assert 'data-seit="2026-10-03T12:00:00+00:00"' in html
    assert "denkt nach" in html
    assert 'data-tickt="1"' in html


def test_schweigt_traegt_keinen_tickt_marker():
    html = web._cothinker_status_html(
        {"zustand": "schweigt", "seit": "2026-10-03T12:00:00+00:00"}
    )
    assert 'class="co-status co-schweigt"' in html
    assert "zugehört" in html
    assert 'data-tickt="1"' not in html


def test_die_tickende_zahl_steht_nie_im_html():
    """Die harte Regel der Karte: keine vorgerechnete Sekundenzahl im
    servergerenderten Markup, nur der rohe ISO-Zeitstempel als Attribut --
    sonst aenderte sich der HTML-String bei jedem Poll und ``ladeBuehne()``
    tauschte das Panel jede Sekunde unnoetig aus."""
    html = web._cothinker_status_html(
        {"zustand": "hoert", "seit": "2026-10-03T12:00:00+00:00"}
    )
    assert '<span class="co-dauer" data-tickt="1"></span>' in html


def test_buehne_html_zeigt_den_status_vor_dem_panel():
    daten = {
        "cothinker_status": {
            "zustand": "transkribiert", "seit": "2026-10-03T12:00:00+00:00",
        },
        "buehnenkarten": [],
        "stueckkarte_felder": [],
        "festlegungen": [],
    }
    html = web._buehne_html(daten)
    assert "cothinker-status" in html
    assert "buehne-panel" in html
    assert html.index("cothinker-status") < html.index("buehne-panel")


def test_buehne_html_ohne_cothinker_status_zeigt_nichts_neues():
    """Regressionstest: eine Gruppe ohne diesen Zustand (alter Stand,
    ausserhalb Phase 4, oder einfach ``None``) sieht am Panel nichts
    Neues."""
    daten = {
        "cothinker_status": None,
        "buehnenkarten": [],
        "stueckkarte_felder": [],
        "festlegungen": [],
    }
    html = web._buehne_html(daten)
    assert "cothinker-status" not in html


def test_buehne_html_ohne_den_schluessel_zeigt_nichts_neues():
    daten = {
        "buehnenkarten": [],
        "stueckkarte_felder": [],
        "festlegungen": [],
    }
    html = web._buehne_html(daten)
    assert "cothinker-status" not in html


# -- die harten CSS-Regeln der Karte -----------------------------------------
#
# ``web_vereint.scope_css()`` versteht ``@media``, aber nicht ``@keyframes``:
# ihre Regex haette den Rumpf eines ``@keyframes``-Blocks (``50% { ... }``)
# faelschlich als verschachtelten Selektor gelesen (siehe docs/agents/weboberflaeche.md
# "``@keyframes`` und ``@media`` nur in ``css_rahmen()``", derselbe Fehler
# wie in ``web_gestalt.py``). Deshalb: kein ``@keyframes`` in ``_CSS_BUEHNE``
# (die gescopt wird), und die eigene Konstante bleibt unangetastet, wenn sie
# -- wie in ``web_vereint.seite()`` -- roh statt durch ``scope_css()`` geht.


def test_css_buehne_enthaelt_kein_keyframes():
    # Eine Erwaehnung in einem Kommentar ist erlaubt (siehe oben in
    # ``web._CSS_BUEHNE`` selbst) -- verboten ist eine echte Regel.
    assert not re.search(r"@keyframes\s+[\w-]+\s*\{", web._CSS_BUEHNE)


def test_keyframes_konstante_traegt_beide_animationen_und_die_ruhigstellung():
    css = web.CSS_COTHINKER_KEYFRAMES
    assert "@keyframes co-atmen" in css
    assert "@keyframes co-punkte" in css
    block = re.search(
        r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}", css, flags=re.S,
    )
    assert block, "kein reduced-motion-Block"
    assert "animation: none !important" in block.group(1)
    assert ".co-icon" in block.group(1)


def test_scope_css_wuerde_die_keyframes_verunstalten_deshalb_bleiben_sie_roh():
    """Die Gegenprobe zum obigen Test: wer ``CSS_COTHINKER_KEYFRAMES``
    versehentlich doch durch ``scope_css()`` schickt, bekommt genau die
    kaputte Ausgabe, vor der die Karte warnt -- dieser Test dokumentiert den
    Fehler, den die Implementierung vermeiden muss."""
    verunstaltet = web_vereint.scope_css(web.CSS_COTHINKER_KEYFRAMES, ".panel-buehne")
    assert re.search(r"\.panel-buehne \d+%", verunstaltet)


def _baue_seite(tmp_path, chat_id: int) -> str:
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, chat_id, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, chat_id, "web")
    token = repo.stelle_web_token_sicher(conn, chat_id)
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
        chatdaten = web_daten.web_chatzustand(lesend, token)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    for nachricht in chatdaten["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    return web_vereint.seite(
        daten, chatdaten, roadmapdaten, web.nonce(b"k" * 32, token), token,
        "/theatersoap", web_chat._segment_ms(), chat_vorhanden=True,
    )


def test_die_ausgelieferte_seite_traegt_die_keyframes_unverunstaltet(tmp_path):
    """Der eigentliche Beweis am Integrationspunkt
    (``web_vereint.seite()``): die rohe Konstante kommt unveraendert im
    ausgelieferten ``<style>`` an, kein ``.panel-buehne 50%``-Fragment."""
    html = _baue_seite(tmp_path, 7_000_000_099_001)
    treffer = re.search(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
    assert treffer is not None, "kein <style> in der Seite"
    css = treffer.group(1)
    assert "@keyframes co-atmen" in css
    assert "@keyframes co-punkte" in css
    assert not re.search(r"\.panel-buehne \d+%", css)
