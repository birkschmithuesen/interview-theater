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
