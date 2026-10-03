"""Der Vertrag des Effekt-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_gestalt_e2e.py``:
ob die Zustaende im echten Chromium wirklich umschalten. Hier steht, was
man am ausgelieferten Skript messen kann -- und das ist genug fuer die
Entscheidungen, die leicht verloren gehen.
"""

import re

import pytest

from interview_theater import web_gestalt


@pytest.fixture(params=web_gestalt.ENTWUERFE)
def js(request):
    return web_gestalt.skript(request.param)


# -- Der CSP-Vertrag im Skript ----------------------------------------------


def test_keine_platzhalter_bleiben_stehen(js):
    """Ein uebersehener ``__NAME__`` waere im Browser ein Syntaxfehler --
    und die ganze Gestaltung waere weg."""
    assert not re.search(r"__[A-Z_]+__", js)


def test_das_skript_setzt_werte_ueber_cssom(js):
    assert "setProperty(" in js
    assert "setAttribute('style'" not in js


def test_das_skript_haengt_keine_handler_ins_markup(js):
    """Alles ueber ``addEventListener``; ein ``el.onclick =`` waere zwar
    CSP-konform, aber wuerde einen fremden Handler ueberschreiben."""
    assert "addEventListener(" in js
    assert not re.search(r"\.on(click|input|change)\s*=", js)


def test_das_skript_schreibt_nie_in_den_interview_knopf(js):
    """Befund 2 an Karte A2: ``_CHAT_JS`` setzt dort ``textContent``.
    Zwei Schreiber auf einem Knoten sind ein Fehler, der erst im Workshop
    auffaellt -- die Gestaltung legt ihren Text daneben
    (``#ux-rec-zeile``)."""
    assert "ux-rec-zeile" in js
    for verboten in ("interview').textContent", 'interview").textContent',
                     "interviewKnopf.textContent"):
        assert verboten not in js


def test_das_skript_achtet_auf_reduzierte_bewegung(js):
    """Nicht nur im CSS: die Momente sind zeitgesteuert, und ein Timer
    laeuft auch dann, wenn die Animation aus ist."""
    assert "prefers-reduced-motion" in js
    assert "RUHIG" in js


# -- Chat --------------------------------------------------------------------


def test_der_denk_zustand_haengt_an_der_tippanzeige(js):
    """``#tippt`` kommt aus Karte A2 und traegt schon den Text. Die
    Gestaltung macht daraus eine Terminalzeile -- sie erfindet keine
    zweite Anzeige daneben."""
    assert "'tippt'" in js or '"tippt"' in js


def test_die_gestaltung_kennt_die_vorlaeufige_blase(js):
    """Sie gehoert Karte W; gestaltet wird sie, geschrieben nicht."""
    assert "vorlaeufig" in web_gestalt.css_chat("a")
    assert "vorlaeufig" in web_gestalt.css_chat("b")


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_das_chat_css_faerbt_beide_blasenarten(name):
    css = web_gestalt.css_chat(name)
    assert ".blase.bot" in css
    assert ".blase.gruppe" in css
    assert ".leiste button" in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_blasen_lesen_sich_gross_genug(name):
    """16 px ist die Untergrenze fuer Fliesstext am Telefon."""
    css = web_gestalt.css_chat(name)
    treffer = re.search(r"\.blase\s*\{[^}]*font-size:\s*([\d.]+)rem", css, flags=re.S)
    assert treffer, "die Blase setzt keine Schriftgroesse"
    assert float(treffer.group(1)) >= 1.0


def test_nur_entwurf_a_kennzeichnet_die_bot_blase():
    """Die Zeile ``bot ~ $`` ist Terminal; in B unterscheiden sich Bot und
    Gruppe wie Repliken -- durch Ausrichtung und Flaeche."""
    assert ".blase.bot::before" in web_gestalt.css_chat("a")
    assert ".blase.bot::before" not in web_gestalt.css_chat("b")


# -- Tabs und Panels ---------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_tableiste_ist_am_daumen_gross_genug(name):
    css = web_gestalt.css_rahmen(name)
    assert ".tabs button" in css
    assert "min-height: var(--tippflaeche)" in css or "--tabs-hoehe" in css


def test_a_legt_die_tabs_unten_und_b_oben():
    """Die eine Entscheidung, die Karte W offen gelassen hat
    (Uebergabe 1: "auf einem Telefon spricht viel fuer unten")."""
    def tabblock(name):
        return re.search(r"\.tabs\s*\{([^}]*)\}",
                         web_gestalt.css_rahmen(name), flags=re.S).group(1)

    assert "position: fixed" in tabblock("a") and "bottom: 0" in tabblock("a")
    assert "position: sticky" in tabblock("b") and "top: 0" in tabblock("b")
    # ``--tabs-hoehe`` ist der Platz, den der Fuss nach unten frei laesst:
    # in B liegt die Leiste oben, also null.
    assert web_gestalt.TOKENS["a"]["tabs-hoehe"] != "0rem"
    assert web_gestalt.TOKENS["b"]["tabs-hoehe"] == "0rem"


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_fuss_weicht_der_tableiste(name):
    """In A liegt die Leiste unter dem Fuss; in B ist ``--tabs-hoehe``
    null und dieselbe Regel kostet nichts."""
    assert "bottom: var(--tabs-hoehe)" in web_gestalt.css_rahmen(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_fuss_verschwindet_ausserhalb_des_chats(name):
    """Im Skript liest man, dort tippt niemand. W setzt
    ``body[data-tab]`` -- also braucht das kein JavaScript."""
    css = web_gestalt.css_rahmen(name)
    assert 'body:not([data-tab="chat"]) .fuss' in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_gewaehlte_tab_ist_nicht_nur_farbig_markiert(name):
    """Farbe allein traegt keinen Zustand (WCAG 1.4.1): der gewaehlte Tab
    bekommt zusaetzlich eine Kante."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(
        r'\.tabs button\[aria-selected="true"\]\s*\{([^}]*)\}', css, flags=re.S)
    assert block, "kein Stil fuer den gewaehlten Tab"
    assert "box-shadow" in block.group(1) or "border" in block.group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_arbeitsstand_setzt_seine_feldkarten(name):
    css = web_gestalt.css_stand(name)
    assert "[data-feld]" in css or ".feld" in css


# -- Die sieben Akte ---------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_aktleiste_hat_ihre_zustaende(name):
    css = web_gestalt.css_rahmen(name)
    for selektor in (".phase.aktiv", ".phase-knopf", ".aufgabe.erledigt",
                     ".aufgabe.laeuft"):
        assert selektor in css, selektor


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_bestaetigungszustand_sieht_anders_aus(name):
    """W schreibt beim ersten Druck die Rueckfrage in den Knopf
    (``data-sicher``). Sieht der Knopf dabei aus wie vorher, liest ihn
    niemand -- und der zweite Druck kommt aus Versehen."""
    assert '.phase-knopf[data-sicher="1"]' in web_gestalt.css_rahmen(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_eine_aufgabe_ist_gross_genug_zum_antippen(name):
    """Jede Aufgabe ist ein Sprungziel (``data-ziel-tab``)."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(r"\.aufgabe\s*\{([^}]*)\}", css, flags=re.S)
    assert block and "min-height: var(--tippflaeche)" in block.group(1)


def test_der_fortschritt_wird_aus_dem_dom_gerechnet(js):
    """Kein neuer Schluessel im Zustands-Poll: die Zahlen stehen schon
    da."""
    assert "aufgabe" in js
    assert "erledigt" in js
    assert "setProperty('--fortschritt'" in js


def test_der_fortschritt_haengt_nicht_an_einer_festen_sieben(js):
    """``phasen.PHASEN`` hat sich seit dem 04.09.2026 dreimal geaendert.
    Die Gestaltung zaehlt, was da ist."""
    assert "querySelectorAll" in js
    assert re.search(r"/\s*7\b", js) is None


# -- Die zwei Aufnahmeknoepfe ------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_aufnahmeknopf_ist_deutlich_groesser_als_eine_tippflaeche(name):
    """Dortmund Tag 1: 13 von 20 Aufnahmen leer, ein Knopf 14x in 93 s
    gedrueckt. Das ist das wichtigste Element dieser Oberflaeche."""
    tippflaeche = float(web_gestalt.TOKENS[name]["tippflaeche"].removesuffix("rem"))
    rec = float(web_gestalt.TOKENS[name]["rec-hoehe"].removesuffix("rem"))
    assert rec >= tippflaeche * 1.5, (rec, tippflaeche)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("zustand", ["startet", "laeuft", "laedt"])
def test_jeder_zustand_hat_seine_regel(name, zustand):
    """``ruht`` ist die Grundregel ``#interview { … }`` und braucht kein
    Attribut; die drei anderen sind Abweichungen davon."""
    assert f'#interview[data-ux-zustand="{zustand}"]' in web_gestalt.css_chat(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_laufende_zustand_ist_groesser_als_der_ruhende(name):
    """Nicht nur anders gefaerbt: wer im Augenwinkel hinsieht, soll den
    Unterschied sehen."""
    css = web_gestalt.css_chat(name)
    block = re.search(
        r'#interview\[data-ux-zustand="laeuft"\]\s*\{([^}]*)\}', css, flags=re.S)
    assert block, "kein Stil fuer den laufenden Zustand"
    assert "calc(var(--rec-hoehe)" in block.group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_es_gibt_eine_rueckmeldung_unter_hundert_millisekunden(name):
    """``:active`` ist CSS -- kein Netz, kein Promise, kein Warten."""
    assert "#interview:active" in web_gestalt.css_chat(name)
    takt = int(web_gestalt.TOKENS[name]["takt-schnell"].removesuffix("ms"))
    assert takt < 100, takt


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_zwei_mikrofone_unterscheiden_sich_in_der_form(name):
    """Form, Ort, Farbe, Verb -- vier Achsen. Die Form ist die, die man
    im Augenwinkel sieht."""
    css = web_gestalt.css_chat(name)
    rund = re.search(r"#ptt\s*\{[^}]*border-radius:\s*([^;]+);", css, flags=re.S)
    knopf = re.search(r"#interview\s*\{[^}]*border-radius:\s*([^;]+);", css, flags=re.S)
    assert rund and knopf
    assert rund.group(1).strip() != knopf.group(1).strip()


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_zwei_mikrofone_haben_verschiedene_farben(name):
    css = web_gestalt.css_chat(name)
    assert "var(--rec)" in re.search(r"#interview\s*\{([^}]*)\}", css, flags=re.S).group(1)
    assert "var(--signal)" in re.search(r"#ptt\s*\{([^}]*)\}", css, flags=re.S).group(1)


def test_das_skript_leitet_die_vier_zustaende_ab(js):
    for zustand in ("ruht", "startet", "laeuft", "laedt"):
        assert zustand in js, zustand
    assert "data-interview" in js or "dataset.interview" in js
    assert "warteschlange" in js


def test_das_skript_zeigt_busy_aber_sperrt_nicht(js):
    """Befund 1 an Karte A2 (Plan-Kopf): dort werden Drucke waehrend eines
    Uebergangs NICHT ignoriert. Das zu reparieren waere Logik. Die
    Gestaltung zeigt es -- und ein ``preventDefault``/``stopPropagation``
    hier waere genau die stille Reparatur, die der Plan verbietet."""
    assert "aria-busy" in js
    assert "stopPropagation" not in js
    assert "stopImmediatePropagation" not in js


def test_der_zustandstext_steht_neben_dem_knopf_nicht_darin(js):
    """Sonst schreiben zwei Stellen in denselben Knoten (Befund 2)."""
    assert "ux-rec-zeile" in js
    assert "createElement" in js


def test_die_zustandstexte_kommen_aus_den_mikrotexten(js):
    for schluessel in ("rec_ruht", "rec_startet", "rec_laeuft", "rec_laedt"):
        assert schluessel in js, schluessel


# -- Die Momente -------------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_akt_moment_ist_kurz(name):
    """Hoechstens ~600 ms: laenger ist keine Zutat mehr, sondern eine
    Wartezeit."""
    takt = int(web_gestalt.TOKENS[name]["takt-moment"].removesuffix("ms"))
    assert takt <= 600, takt


def test_a_glitcht_und_b_zieht_einen_vorhang():
    """**Abweichung vom Brief, begruendet:** ``_KEYFRAMES_CSS`` definiert
    seit Aufgabe 3 IMMER beide Keyframes (``ux-glitch`` UND ``ux-vorhang``)
    fuer jeden Entwurf -- ``test_jede_benutzte_animation_ist_auch_definiert``
    verlangt ``set(KEYFRAMES) == definiert`` je Entwurf, und das Element
    traegt in beiden Entwuerfen dieselbe ID ``#ux-vorhang`` (dasselbe JS,
    siehe ``_JS_MOMENT``). Die blosse Textsuche nach ``"ux-vorhang"`` waere
    also in JEDEM Entwurf wahr und koennte nie scheitern -- das ist kein
    Beweis fuer die Abweichung, nur fuer die (immer vorhandene)
    Keyframe-Definition und die geteilte ID. Geprueft wird deshalb, WELCHE
    Animation am Overlay haengt (``[data-an="1"] { animation: … }``), denn
    genau das ist der tatsaechliche Unterschied zwischen Glitch und
    Vorhang."""
    assert "animation: ux-glitch" in web_gestalt.css_rahmen("a")
    assert "animation: ux-vorhang" in web_gestalt.css_rahmen("b")
    assert "animation: ux-vorhang" not in web_gestalt.css_rahmen("a")
    assert "animation: ux-glitch" not in web_gestalt.css_rahmen("b")


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_moment_liegt_ueber_allem_und_faengt_nichts_ab(name):
    """Ein Overlay, durch das man nicht tippen kann, waere ein halber
    Ausfall, wenn das Skript haengt."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(r"#ux-vorhang\s*\{([^}]*)\}", css, flags=re.S).group(1)
    assert "pointer-events: none" in block


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_belohnung_ist_klein_und_verschwindet(name):
    css = web_gestalt.css_rahmen(name)
    assert "#ux-belohnung" in css
    assert "#ux-belohnung[hidden]" in css


def test_der_moment_haengt_am_bestaetigenden_druck(js):
    """Karte W schreibt beim ersten Druck die Rueckfrage in den Knopf
    (``data-sicher``); der Moment gehoert zum ZWEITEN."""
    assert "data-sicher" in js or "uxSicher" in js or "dataset.sicher" in js
    assert "phase-knopf" in js


def test_der_moment_faengt_den_klick_nicht_ab(js):
    """Karte W muss denselben Klick weiterhin sehen -- sonst wechselt die
    Phase gar nicht, und der Vorhang faellt vor eine leere Buehne."""
    assert "preventDefault" not in js or "ptt" in js  # nur PTT darf das
    assert "stopPropagation" not in js


def test_bei_reduzierter_bewegung_bleibt_nur_die_ansage(js):
    assert "RUHIG" in js
    assert "ux-ansage" in js


def test_die_belohnungen_kommen_ohne_neuen_serverschluessel_aus(js):
    """Die Karte erlaubt einen additiven read-only-Schluessel im Poll --
    gebraucht wird er nicht. Beide Belohnungen fallen aus dem DOM."""
    assert "ux-belohnung" in js
    assert "fetch(" not in js
    assert "EventSource" not in js


def test_die_belohnungstexte_kommen_aus_den_mikrotexten(js):
    for schluessel in ("belohnung_akt", "belohnung_aufnahme"):
        assert schluessel in js, schluessel


# -- Mikrotexte --------------------------------------------------------------


def test_jeder_schluessel_im_skript_hat_einen_text():
    """Ein ``TEXTE.foo``, das es nicht gibt, ist im Browser ``undefined``
    -- und in der Oberflaeche eine leere Zeile, die niemand erklaeren
    kann."""
    quelle = web_gestalt._GESTALT_JS + web_gestalt._BAUSTEINE
    benutzt = set(re.findall(r"TEXTE\.([a-z_]+)", quelle))
    benutzt |= set(re.findall(r"TEXTE\['([a-z_]+)'\]", quelle))
    vorhanden = set(web_gestalt._mikrotexte())
    assert not (benutzt - vorhanden), benutzt - vorhanden
    # Die vier rec_-Schluessel werden dynamisch zusammengesetzt
    # (TEXTE['rec_' + neu]) und stehen deshalb nicht im Regex.
    for zustand in ("ruht", "startet", "laeuft", "laedt"):
        assert f"rec_{zustand}" in vorhanden, zustand


def test_die_mikrotexte_kommen_aus_den_modulkonstanten():
    """Sonst laufen sie nicht ueber ``T`` (A1) und stehen in Padua
    deutsch da -- genau Befund 2 an Karte A2."""
    import inspect
    assert "T._TEXT_" in inspect.getsource(web_gestalt._mikrotexte)


def test_kein_vorname_in_den_mikrotexten():
    """E8 gilt ueberall, auch in einer Beschriftung."""
    zusammen = " ".join(web_gestalt._mikrotexte().values())
    for verboten in ("Meryem", "Erhan", "Leyla", "Birk", "Mira"):
        assert verboten not in zusammen, verboten


def test_die_platzhalter_stehen_in_geschweiften_klammern():
    """Das Skript ersetzt sie mit ``String.replace`` -- eine andere Form
    liefe ins Leere und stuende woertlich in der Oberflaeche."""
    texte = web_gestalt._mikrotexte()
    assert "{akt}" in texte["belohnung_akt_satz"]
    assert "{was}" in texte["naechstes"]
    assert "{bezeichnung}" in texte["naechste_phase"]
