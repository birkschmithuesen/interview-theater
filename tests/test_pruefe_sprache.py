"""Der Stoppwort-Pruefer (D10) -- Kern: Woerter, Ausnahmen, Dateien, Schluessel."""

from scripts import pruefe_sprache


def _woerter(text):
    return [t.wort for t in pruefe_sprache.deutsche_treffer("test", text)]


def test_deutsche_funktionswoerter_schlagen_an():
    assert "und" in _woerter("Figuren und Szenen")
    assert "euch" in _woerter("Ich zeige es euch.")


def test_ui_woerter_schlagen_an_auch_ohne_funktionswort():
    """W2: 'Ja, speichern' hat kein Funktionswort."""
    assert _woerter("Ja, speichern") == ["ja", "speichern"]
    assert "notiert" in _woerter("Notiert:\n- Begriffe")


def test_umlaut_ist_ein_eigenes_signal():
    assert "ä" in "".join(_woerter("Gespräch"))


def test_englisch_bleibt_still():
    assert _woerter("Yes, save. On to phase 3? Your terms are noted.") == []


def test_italienisch_bleibt_still():
    assert _woerter("Ciao, com'è andata l'intervista? Ci vediamo in piazza.") == []


def test_protokoll_token_sind_erlaubt():
    text = ('Append the block VORSCHLAG FRAGENAUSWAHL: and use '
            '{"art": "fragen_setzen"} with form "chor" or "lied". '
            'ZUSAMMENFASSUNG: one line. {{rahmen_kurz}} {name}')
    assert _woerter(text) == []


def test_slash_befehle_samt_argumentsyntax_sind_protokoll():
    """Annahme A4: die Befehlsnamen und ihre Argumentwoerter bleiben deutsch
    (``/hilfe`` darf sie nennen, K6). Ausgenommen ist nur die Befehlssyntax
    selbst -- der Satz drumherum wird weiter geprueft."""
    text = ("/stand - shows what I've kept so far\n"
            "/szene <number> ort|zeit|anlass|figuren <text> - place\n"
            "/figur <name> entfernen. /festlegung weg <search word>.\n"
            "/phase [number|name] - shows the phase")
    assert _woerter(text) == []
    assert _woerter("/stand zeigt euch den Stand") != []
    assert _woerter("Type /hilfe, und fertig.") == ["und", "fertig"]


def test_argumentwoerter_hinter_befehl_sind_eine_geschlossene_menge():
    """Nachbesserung Aufgabe 14: das fruehere Muster liess JEDES
    kleingeschriebene Wort hinter einem Befehl als Argument durchgehen und
    verschluckte damit ganze Saetze (0 Treffer statt "ihr"/"dir"). Nur
    Woerter aus ``ARGUMENTWOERTER`` (am Code von ``befehle.py`` ermittelt)
    bleiben als Befehlssyntax ungeprueft."""
    assert "ihr" in _woerter("Tippt /aufnahme und dann sprecht ihr los.")
    assert "euch" in _woerter("/hilfe zeigt euch alles")
    assert "dir" in _woerter("/hilfe zeigt dir alles, was geht")


def test_treffer_nennt_quelle_und_ausschnitt():
    treffer = pruefe_sprache.deutsche_treffer("prompt system", "Please write und so.")
    assert treffer[0].quelle == "prompt system"
    assert "write und so" in treffer[0].ausschnitt


def test_dateien_modus(tmp_path):
    gut = tmp_path / "gut.md"
    gut.write_text("Write in English, in short sentences.", encoding="utf-8")
    schlecht = tmp_path / "schlecht.md"
    schlecht.write_text("Schreibe auf Deutsch, bitte.", encoding="utf-8")
    assert pruefe_sprache.pruefe_dateien([gut]) == []
    assert pruefe_sprache.pruefe_dateien([schlecht])
    assert pruefe_sprache.main(["--dateien", str(gut)]) == 0
    assert pruefe_sprache.main(["--dateien", str(schlecht)]) == 1


# -- Aufgabe 30: der Render-Pruefer (Abnahme 3, D10) ------------------------

import pytest


@pytest.fixture(scope="module")
def padua_quellen():
    return pruefe_sprache.quellen("padua-2026")


@pytest.fixture(scope="module")
def dortmund_quellen():
    return pruefe_sprache.quellen("dortmund-2026")


def test_padua_ist_frei_von_deutsch(padua_quellen):
    treffer = [t for liste in padua_quellen.values() for q, text in liste
               for t in pruefe_sprache.deutsche_treffer(q, text)]
    assert [f"{t.quelle}: {t.wort} | {t.ausschnitt}" for t in treffer] == []


@pytest.mark.parametrize("quelle", ["prompts", "texte", "durchlauf", "modellprompts", "web"])
def test_dortmund_schlaegt_in_jeder_quelle_an(dortmund_quellen, quelle):
    """Positivkontrolle: jede Quelle liefert Text, und im Deutschen findet
    der Pruefer darin Deutsch -- sonst pruefte die Padua-Seite nichts."""
    assert dortmund_quellen[quelle], quelle
    assert any(pruefe_sprache.deutsche_treffer(q, t) for q, t in dortmund_quellen[quelle])


def test_padua_quellen_sind_nicht_leer(padua_quellen):
    for name, liste in padua_quellen.items():
        assert liste, name


def test_cli_exit_codes():
    assert pruefe_sprache.main(["padua-2026"]) == 0
    assert pruefe_sprache.main(["dortmund-2026", "--quelle", "texte"]) == 1


def test_cli_lehnt_unbekannte_quelle_ab():
    with pytest.raises(SystemExit):
        pruefe_sprache.main(["padua-2026", "--quelle", "gibtsnicht"])


def test_einzelne_deutsche_inhaltswoerter_ohne_stoppwort_schlagen_an():
    """Offener Punkt aus dem Review zu Aufgabe 17: diese drei rutschten
    durch (kein Stoppwort, kein Umlaut)."""
    assert "der" in _woerter("Der Weg dahin")
    assert "dahin" in _woerter("Der Weg dahin")
    assert _woerter("struktur") == ["struktur"]
    assert _woerter("sonstiges") == ["sonstiges"]


def test_deutsche_formanzeige_schlaegt_an_der_datenbankwert_nicht():
    """Gemessen im Padua-Durchlauf: Formknoepfe "Monolog", "Chor", "Lied".
    Der kleingeschriebene Datenbankwert bleibt Protokoll (ERLAUBT)."""
    assert _woerter("Monolog") == ["Monolog"]
    assert _woerter("Chor · Lied") == ["Chor", "Lied"]
    assert _woerter('with form "chor" or "lied"') == []
    assert _woerter("Chorus, Song, Monologue, Dialogue, Dialog, Rap") == []


def test_englisch_die_bleibt_still():
    """'die' ist auch ein englisches Wort -- es steht bewusst in keiner Liste."""
    assert "die" not in pruefe_sprache.STOPPWOERTER | pruefe_sprache.UI_WOERTER
    assert _woerter("The characters never die on stage.") == []


def test_feldnamen_in_backticks_aus_der_geschlossenen_menge_sind_protokoll():
    """Offener Punkt aus Aufgabe 21: ein englischer Judge-Prompt darf den
    Feldnamen woertlich nennen, den ein Programm liest -- aber nur in
    Backticks und nur aus dramaturgie.fanout.A10_FELDER | A11_FELDER."""
    from interview_theater.dramaturgie import fanout

    assert pruefe_sprache.FELDNAMEN_IN_BACKTICKS == (
        frozenset(fanout.A10_FELDER) | frozenset(fanout.A11_FELDER))
    assert _woerter("Allowed fields: `format`, `rahmen`, `figuren_anzahl`, `geschichte`.") == []
    assert "geschichte" in _woerter("Allowed fields: the geschichte of the play.")
    assert "geschichte" in _woerter("Write `neue geschichte` here.")
    # die Protokollform `<feld>: <Wert>`: der Name ist frei, der Wert nicht
    assert _woerter("Example: `geschichte: Nadia stays one more night`.") == []
    assert "und" in _woerter("Example: `geschichte: Tomas und Nadia`.")
    # ein Wort ausserhalb der Menge bleibt auch in Backticks ein Treffer
    assert "fertig" in _woerter("Then write `fertig`.")


def test_positivkontrolle_dortmund_loest_stoppwoerter_und_ui_woerter_aus(dortmund_quellen):
    """W2/Abnahme (3): gegen Dortmund muss der Pruefer anschlagen, und zwar
    ueber BEIDE Listen -- sonst waere eine davon tot. Auch der
    Probedurchlauf allein loest beide aus, nicht nur die Tabelle."""
    def woerter(listen):
        return {t.wort for liste in listen for q, text in liste
                for t in pruefe_sprache.deutsche_treffer(q, text)}

    alle = woerter(dortmund_quellen.values())
    assert alle & pruefe_sprache.STOPPWOERTER
    assert alle & pruefe_sprache.UI_WOERTER
    for quelle in ("durchlauf", "modellprompts"):
        gefunden = woerter([dortmund_quellen[quelle]])
        assert gefunden & pruefe_sprache.STOPPWOERTER, quelle
        assert gefunden & pruefe_sprache.UI_WOERTER, quelle


def test_fund_feldnamen_im_feldvorschlag_sind_englische_aliase():
    """Fund des Render-Pruefers: ANWEISUNG_FELDER nannte "figuren" im
    englischen Prompt. Die englischen Namen muessen zurueck auf das Feld
    fuehren -- das Modell schreibt sie in ``VORSCHLAG SZENE:`` zurueck."""
    from interview_theater import sprache, szene, szenenfolge

    assert set(szenenfolge.FELD_IM_PROMPT) == set(szene.PFLICHTFELDER)
    assert all(k == v for k, v in szenenfolge.FELD_IM_PROMPT.items())
    en = sprache.tabelle("en")["szenenfolge"]["FELD_IM_PROMPT"]
    assert set(en) == set(szene.PFLICHTFELDER)
    for feld, name in en.items():
        assert szene.feldname(name) == feld, name
        assert pruefe_sprache.deutsche_treffer("t", name) == []


def test_fund_journalart_im_nutzertext():
    """Fund des Render-Pruefers: "- [notiert] ..." im englischen Gespraechs-
    und Journal-Prompt. Dortmund bleibt zeichengleich."""
    from interview_theater import kontext

    eintrag = {"art": "notiert", "text": "Interview guide shown"}
    with pruefe_sprache._profil("dortmund-2026"):
        assert kontext.journalzeile(eintrag) == "- [notiert] Interview guide shown"
        assert kontext.journalzeile({"art": "neu", "text": "x"}) == "- [neu] x"
    with pruefe_sprache._profil("padua-2026"):
        assert kontext.journalzeile(eintrag) == "- [noted] Interview guide shown"


def test_modellprompts_enthalten_system_und_nutzer(padua_quellen):
    """W3: die Attrappe zeichnet JEDEN Prompt auf, System UND Nutzer -- und
    die Nutzertexte mit eigenen Koepfen (Gespraech, Erkenner, Journal,
    Verdichter, Szene) sind dabei."""
    namen = {q for q, _ in padua_quellen["modellprompts"]}
    for art in ("gespraech", "erkenner", "journal", "verdichter", "szene"):
        assert f"{art} system" in namen, art
        assert f"{art} nutzer" in namen, art
