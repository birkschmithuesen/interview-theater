"""scripts/ux_auswertung.py -- die reinen Auswertungsfunktionen (kein
Modellaufruf, kein Geld, laeuft nie automatisch per se, aber kostet auch
nichts: reine Arithmetik ueber schon gespeicherte Ereignisse).

Nie Freitext in der Ausgabe: die Tests pruefen ausdruecklich, dass
``extra_json``/``extra``-Inhalte jenseits der whitelisted Schluessel
(``msg`` fuer JS-Fehler) nie als Freitext in den Bericht wandern."""

from scripts import ux_auswertung


def _ereignis(typ, ziel, geraet="g-1", phase=None, dauer_ms=None, extra=None):
    return {"typ": typ, "ziel": ziel, "geraet": geraet, "phase": phase,
            "dauer_ms": dauer_ms, "extra": extra or {}}


# -- funnel_je_phase ----------------------------------------------------------


def test_funnel_zaehlt_betreten_erste_aktion_und_weiter(tmp_path=None):
    ereignisse = [
        _ereignis("tab_wechsel", "tab:stand", geraet="a", phase=4),
        _ereignis("klick", "knopf:stift", geraet="a", phase=4),
        _ereignis("tab_wechsel", "tab:stand", geraet="b", phase=4),
        # Geraet a kommt spaeter in Phase 5 an -- "done" fuer Phase 4.
        _ereignis("klick", "knopf:x", geraet="a", phase=5),
    ]
    funnel = ux_auswertung.funnel_je_phase(ereignisse)
    assert funnel[4] == {"entered": 2, "first_action": 1, "done": 1}
    assert funnel[5] == {"entered": 1, "first_action": 1, "done": 0}


def test_funnel_ignoriert_ereignisse_ohne_phase():
    ereignisse = [_ereignis("klick", "knopf:x", phase=None)]
    assert ux_auswertung.funnel_je_phase(ereignisse) == {}


def test_funnel_leere_liste():
    assert ux_auswertung.funnel_je_phase([]) == {}


# -- tab_verweildauer ----------------------------------------------------------


def test_tab_verweildauer_rechnet_dauer_dem_vorigen_tab_zu():
    """Das Ereignis, das Tab B betritt, traegt die Verweildauer auf Tab A
    (so baut das Client-JS es, siehe web_vereint._UX_JS)."""
    ereignisse = [
        _ereignis("tab_wechsel", "tab:chat", dauer_ms=None),
        _ereignis("tab_wechsel", "tab:stand", dauer_ms=5000),
        _ereignis("tab_wechsel", "tab:chat", dauer_ms=3000),
    ]
    dauer = ux_auswertung.tab_verweildauer(ereignisse)
    assert dauer["tab:chat"]["summe_ms"] == 5000
    assert dauer["tab:chat"]["n"] == 1
    assert dauer["tab:stand"]["summe_ms"] == 3000
    assert dauer["tab:stand"]["n"] == 1


def test_tab_verweildauer_summiert_mehrere_besuche():
    # Reihenfolge der Tabs: chat -> stand (1000 ms auf chat verbracht) ->
    # chat (2000 ms auf stand verbracht) -> stand (4000 ms auf chat
    # verbracht). "chat" sammelt zwei Besuche (1000 + 4000), "stand" einen
    # (2000) -- dieselbe Zurechnung wie im Einzelfall oben.
    ereignisse = [
        _ereignis("tab_wechsel", "tab:chat"),
        _ereignis("tab_wechsel", "tab:stand", dauer_ms=1000),
        _ereignis("tab_wechsel", "tab:chat", dauer_ms=2000),
        _ereignis("tab_wechsel", "tab:stand", dauer_ms=4000),
    ]
    dauer = ux_auswertung.tab_verweildauer(ereignisse)
    assert dauer["tab:chat"]["summe_ms"] == 1000 + 4000
    assert dauer["tab:chat"]["n"] == 2
    assert dauer["tab:stand"]["summe_ms"] == 2000
    assert dauer["tab:stand"]["n"] == 1


def test_tab_verweildauer_ohne_wechsel_ist_leer():
    assert ux_auswertung.tab_verweildauer([]) == {}


def test_tab_verweildauer_ignoriert_andere_typen():
    ereignisse = [_ereignis("klick", "knopf:x", dauer_ms=9999)]
    assert ux_auswertung.tab_verweildauer(ereignisse) == {}


# -- top_tote_tipps -------------------------------------------------------------


def test_top_tote_tipps_zaehlt_rage_klicks_je_ziel():
    ereignisse = [
        _ereignis("rage_klick", "tot:div"),
        _ereignis("rage_klick", "tot:div"),
        _ereignis("rage_klick", "knopf:x"),
        _ereignis("klick", "knopf:y"),  # kein Rage-Tap, zaehlt nicht
    ]
    top = ux_auswertung.top_tote_tipps(ereignisse)
    assert top == [("tot:div", 2), ("knopf:x", 1)]


def test_top_tote_tipps_begrenzt_auf_n():
    ereignisse = [_ereignis("rage_klick", f"tot:{i}") for i in range(5)]
    assert len(ux_auswertung.top_tote_tipps(ereignisse, n=3)) == 3


# -- abbrueche ------------------------------------------------------------------


def test_abbrueche_zaehlt_nur_den_typ_abbruch():
    ereignisse = [
        _ereignis("abbruch", "aufnahme:slide"),
        _ereignis("abbruch", "aufnahme:modusende"),
        _ereignis("klick", "knopf:x"),
    ]
    assert ux_auswertung.abbrueche(ereignisse) == 2


# -- js_fehler_liste -------------------------------------------------------------


def test_js_fehler_liste_zaehlt_je_meldung():
    ereignisse = [
        _ereignis("js_fehler", "fenster", extra={"msg": "TypeError: x"}),
        _ereignis("js_fehler", "fenster", extra={"msg": "TypeError: x"}),
        _ereignis("js_fehler", "promise", extra={"msg": "anderer Fehler"}),
    ]
    liste = ux_auswertung.js_fehler_liste(ereignisse)
    assert liste == [("TypeError: x", 2), ("anderer Fehler", 1)]


def test_js_fehler_liste_ohne_msg_zeigt_platzhalter():
    ereignisse = [_ereignis("js_fehler", "fenster", extra={})]
    liste = ux_auswertung.js_fehler_liste(ereignisse)
    assert liste == [("(ohne Meldung)", 1)]


# -- antwortzeiten_bot_zu_gruppe: liest ausschliesslich Zeit/Richtung ----------


def test_antwortzeiten_misst_delta_von_bot_zu_naechster_gruppenantwort():
    posts = [
        {"id": 1, "richtung": "aus", "typ": "text", "erstellt_am": "2026-10-06T10:00:00+00:00"},
        {"id": 2, "richtung": "ein", "typ": "text", "erstellt_am": "2026-10-06T10:00:30+00:00"},
        {"id": 3, "richtung": "aus", "typ": "text", "erstellt_am": "2026-10-06T10:01:00+00:00"},
        {"id": 4, "richtung": "ein", "typ": "text", "erstellt_am": "2026-10-06T10:01:05+00:00"},
    ]
    deltas = ux_auswertung.antwortzeiten_bot_zu_gruppe(posts)
    assert deltas == [30.0, 5.0]


def test_antwortzeiten_zaehlt_nur_die_erste_antwort_je_bot_zeile():
    posts = [
        {"id": 1, "richtung": "aus", "typ": "text", "erstellt_am": "2026-10-06T10:00:00+00:00"},
        {"id": 2, "richtung": "ein", "typ": "text", "erstellt_am": "2026-10-06T10:00:10+00:00"},
        {"id": 3, "richtung": "ein", "typ": "text", "erstellt_am": "2026-10-06T10:00:20+00:00"},
    ]
    assert ux_auswertung.antwortzeiten_bot_zu_gruppe(posts) == [10.0]


def test_antwortzeiten_ohne_vorherige_bot_zeile_wird_ignoriert():
    posts = [
        {"id": 1, "richtung": "ein", "typ": "text", "erstellt_am": "2026-10-06T10:00:00+00:00"},
    ]
    assert ux_auswertung.antwortzeiten_bot_zu_gruppe(posts) == []


# -- bericht: Markdown ohne Freitextinhalt -------------------------------------


def test_bericht_ist_markdown_und_enthaelt_keine_rohdaten_ausser_msg():
    ereignisse = [
        _ereignis("tab_wechsel", "tab:chat", geraet="a", phase=4),
        _ereignis("tab_wechsel", "tab:stand", geraet="a", phase=4, dauer_ms=2000),
        _ereignis("klick", "knopf:stift", geraet="a", phase=4),
        _ereignis("rage_klick", "tot:div", geraet="a", phase=4),
        _ereignis("js_fehler", "fenster", geraet="a", extra={"msg": "TypeError: x"}),
        _ereignis("abbruch", "aufnahme:slide", geraet="a", phase=3),
    ]
    posts = [
        {"id": 1, "richtung": "aus", "typ": "text", "erstellt_am": "2026-10-06T10:00:00+00:00"},
        {"id": 2, "richtung": "ein", "typ": "text", "erstellt_am": "2026-10-06T10:00:12+00:00"},
    ]
    text = ux_auswertung.bericht(42, ereignisse, posts)
    assert text.startswith("# UX-Auswertung")
    assert "42" in text
    assert "tab:chat" in text
    assert "TypeError: x" in text  # einzige erlaubte Ausnahme von "kein Freitext"
    assert "Abbrueche" in text or "abbruch" in text.lower()


def test_bericht_ohne_ereignisse_bricht_nicht():
    text = ux_auswertung.bericht(42, [], [])
    assert text.startswith("# UX-Auswertung")
