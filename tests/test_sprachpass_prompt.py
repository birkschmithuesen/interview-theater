"""Die englische Negativliste traegt die vier Muster des Sprachpasses
(30.09.2026, Karte R).

Der Prompt sagt es vorher, der Zaehler prueft es nachher -- beides, weil am
06.09.2026 das Vorhersagen allein nicht genuegte. Die deutsche Datei bleibt
unberuehrt: sie steht im Prompt-Schnappschuss, und Dortmund bleibt
zeichengleich.
"""

import hashlib
from pathlib import Path

import pytest

from interview_theater import anweisungen, sprachpass, workshop

WURZEL = Path(__file__).resolve().parent.parent
DEUTSCH = WURZEL / "interview_theater" / "prompts" / "theater-tells.md"
ENGLISCH = (WURZEL / "interview_theater" / "sprachen" / "en" / "prompts"
            / "theater-tells.md")

#: Selbst gemessen am 30.09.2026 auf ``d8deb6c``. Wer die deutsche Datei
#: anfasst, sieht es hier -- und im Bitgleichheits-Test.
DEUTSCH_SHA_D8DEB6C = (
    "ce75dd90397aca82440c77f0c9638cab6e69f168317a276b77f9483129904d6d")


def test_die_deutsche_liste_bleibt_unberuehrt():
    """Sie geht in ``szene.systemanweisung()`` UND in
    ``kurzgeschichte.systemanweisung()``, beide im Schnappschuss."""
    roh = DEUTSCH.read_bytes()
    assert hashlib.sha256(roh).hexdigest() == DEUTSCH_SHA_D8DEB6C


@pytest.mark.parametrize("marke", [
    "dash", "not X but Y", "three adjectives", "closing line",
])
def test_die_englische_liste_nennt_jedes_muster(marke):
    text = ENGLISCH.read_text(encoding="utf-8")
    assert marke.lower() in text.lower(), marke


def test_die_englische_liste_bleibt_in_der_form_der_datei():
    """Jeder Eintrag: fette Nummer, dann "Bad:" und "Better:". Wer die Form
    bricht, bricht das Muster, an dem das Modell die Liste liest."""
    text = ENGLISCH.read_text(encoding="utf-8")
    import re
    nummern = [int(n) for n in re.findall(r"(?m)^\*\*(\d+)\.", text)]
    assert nummern == list(range(1, len(nummern) + 1)), nummern
    assert text.count("- Bad:") == len(nummern)
    assert text.count("- Better:") == len(nummern)


def test_die_neuen_eintraege_stehen_am_ende():
    """Angehaengt, nicht eingeschoben: die bestehenden Nummern sind in
    Berichten und Notizen zitiert."""
    text = ENGLISCH.read_text(encoding="utf-8")
    import re
    nummern = [int(n) for n in re.findall(r"(?m)^\*\*(\d+)\.", text)]
    letzte_vier = text[text.index(f"**{nummern[-4]}."):]
    for marke in ("dash", "not ", "three", "closing"):
        assert marke.lower() in letzte_vier.lower(), marke


def test_die_beispiele_sind_englisch():
    from scripts import pruefe_sprache
    text = ENGLISCH.read_text(encoding="utf-8")
    assert pruefe_sprache.deutsche_treffer(str(ENGLISCH), text) == []


def test_jedes_beispiel_wuerde_vom_zaehler_gefunden():
    """Der Beweis, dass Prompt und Zaehler dasselbe meinen: jedes
    "Bad:"-Beispiel der vier neuen Eintraege loest seinen Zaehler aus.

    Ohne diesen Test koennten Negativliste und Zaehler zwei verschiedene
    Dinge verbieten -- und die Gruppe bekaeme einen Ueberarbeitungsauftrag fuer
    etwas, das im Prompt nie stand."""
    beispiele = {
        "gedankenstriche": "She waited—and waited—and waited.",
        "nicht_sondern": "It was not a home but a waiting room.",
        "adjektiv_dreier": "She was tired, angry, and alone.",
        "fazitsatz": "Maybe home is just where you stop explaining.",
    }
    for name, satz in beispiele.items():
        assert sprachpass.rohzahlen(satz, "en")[name] >= 1, name
        # Und der Satz steht wirklich in der Datei.
        assert satz in ENGLISCH.read_text(encoding="utf-8"), name


def test_die_englische_liste_kommt_im_prompt_an(monkeypatch):
    """Sie wird ueber die Sprachschicht geholt (A1 Aufgabe 4), nicht ueber
    einen eigenen Pfad."""
    from interview_theater import sprache
    monkeypatch.setattr(sprache, "code", lambda: "en")
    anweisungen._CACHE.clear()
    text = anweisungen.hole("theater-tells")
    assert "not a home but a waiting room" in text
    anweisungen._CACHE.clear()
