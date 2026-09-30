"""Parser zweisprachig (D5): Englisch wird erkannt, Deutsch bleibt, wie es war.

Die deutschen Sollwerte sind am 30.09.2026 auf d8deb6c gemessen (Plan A1,
Aufgaben 22-24) -- sie aendern sich durch A1 nicht.
"""

import pytest

from interview_theater import ablauf, begriffe, sprache
from interview_theater.knoepfe import figuren, fragen


@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")


# --- Gruppentext je Sprache (Aufgabe 22) ---------------------------------

@pytest.mark.parametrize("text, soll", [
    ("schreib die szene", True), ("neu schreiben", True),
    ("interview starten", True), ("write the scene", False),
])
def test_auftrag_deutsch_wie_vorher(text, soll):
    assert ablauf.ist_auftrag(text) is soll


@pytest.mark.parametrize("text, soll", [
    ("write the scene", True), ("rewrite", True), ("start the interview", True),
    ("let's do an interview", True), ("interview done", True),
    ("I think the interview was good but long", False),
    # Nachbesserung (Review Commit 15d70a8, Befund 2/3): "go" traf
    # "How did the interview go?" ueber interview\b.{0,20}\b(start|begin|go)\b,
    # und "re-?write" war unverankert und traf "I would rewrite the ending"
    # mitten im Satz -- beides gemessen mit dem Interpreter, siehe
    # task-22-report.md Nachbesserung.
    ("How did the interview go?", False), ("The interview will go well", False),
    ("I would rewrite the ending", False),
])
def test_auftrag_englisch(englisch, text, soll):
    assert ablauf.ist_auftrag(text) is soll


@pytest.mark.parametrize("text, soll", [
    ("zeig mal szene 2", 2), ("lies uns Szene 3 vor", 3), ("show us scene 2", None),
])
def test_szenentext_deutsch_wie_vorher(text, soll):
    assert ablauf.szenentext_gewuenscht(text) == soll


@pytest.mark.parametrize("text, soll", [
    ("show us scene 2", 2), ("read scene 3", 3), ("in scene 2 he should leave", None),
    # Nachbesserung (Review Commit 15d70a8, Befund 1): ohne Wortgrenzen traf
    # "read" den Substring in "already" und "what does" jede Frage --
    # gemessen: "Scene 2 is already finished" -> 2, "what does she want in
    # scene 3" -> 3. Siehe task-22-report.md Nachbesserung.
    ("Scene 2 is already finished", None),
    ("what does she want in scene 3", None),
])
def test_szenentext_englisch(englisch, text, soll):
    assert ablauf.szenentext_gewuenscht(text) == soll


@pytest.mark.parametrize("text, soll", [
    ("die erste und die dritte", [1, 3]), ("1, 4 und 7", [1, 4, 7]),
    ("the first and the third", []),
])
def test_fragennummern_deutsch_wie_vorher(text, soll):
    assert fragen.lies_fragennummern(text) == soll


@pytest.mark.parametrize("text, soll", [
    ("the first and the third", [1, 3]), ("2, 5 and 8", [2, 5, 8]),
])
def test_fragennummern_englisch(englisch, text, soll):
    assert fragen.lies_fragennummern(text) == soll


@pytest.mark.parametrize("text, soll", [("drei", 3), ("fuenf Figuren", 5), ("three", None), ("4", 4)])
def test_figurenzahl_deutsch_wie_vorher(text, soll):
    assert figuren._zahl_aus(text) == soll


@pytest.mark.parametrize("text, soll", [("three", 3), ("five characters", 5), ("4", 4)])
def test_figurenzahl_englisch(englisch, text, soll):
    assert figuren._zahl_aus(text) == soll


def test_begriffe_deutsch_wie_vorher():
    assert begriffe.passt("Freundschaft", "Sie reden ueber Freundschaften.") is True
    assert begriffe.passt("Freundschaft", "They talk about friendships.") is False


def test_begriffe_englisch(englisch):
    assert begriffe.passt("friendship", "They talk about friendships.") is True


def test_begriffe_stamm_deutsch_wie_vorher():
    # Umlautfaltung und deutsche Endungen, gemessen vor der Aenderung.
    assert begriffe.stamm("Übungen") == "uebung"
    assert begriffe.stamm("Sorgen") == "sorg"
    assert begriffe.stamm("meetings") == "meeting"
    assert begriffe.stamm("Mädchen") == "maedch"


def test_begriffe_stamm_englisch(englisch):
    assert begriffe.stamm("meetings") == "meet"
    assert begriffe.stamm("stories") == "stor"
    assert begriffe.passt("meeting", "They describe many meetings at school.") is True


# --- Befehle: Argumentwoerter je Sprache ----------------------------------

def _befehl(conn, einst, text):
    from interview_theater import befehle
    from simulation.attrappe import TelegramAttrappe

    tg = TelegramAttrappe()
    befehle.behandle(conn, tg, einst, 1, text, None)
    return tg


def test_befehl_entfernen_englisch(conn, einst, englisch):
    from interview_theater import befehle, repo
    from simulation.attrappe import TelegramAttrappe

    repo.setze_figur(conn, 1, "Nadia", "sister")
    befehle.behandle(conn, TelegramAttrappe(), einst, 1, "/figur Nadia remove", None)
    assert all(f["name"] != "Nadia" for f in repo.figuren(conn, 1))


def test_befehl_entfernen_deutsch_wie_vorher(conn, einst):
    from interview_theater import repo

    repo.setze_figur(conn, 1, "Nadia", "Schwester")
    repo.setze_figur(conn, 1, "Emre", "Bruder")
    _befehl(conn, einst, "/figur Nadia remove")
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Nadia", "Emre"]
    _befehl(conn, einst, "/figur Nadia entfernen")
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Emre"]


def test_befehl_entfernen_englisch_nimmt_auch_das_deutsche_argument(conn, einst, englisch):
    # Annahme A4: die Argumentwoerter bleiben deutsch, und die englische
    # Hilfe nennt "/figur <name> entfernen" -- das muss weiter wirken.
    from interview_theater import repo

    repo.setze_figur(conn, 1, "Nadia", "sister")
    _befehl(conn, einst, "/figur Nadia entfernen")
    assert repo.figuren(conn, 1) == []


def test_szene_entfernen_englisch(conn, einst, englisch):
    from interview_theater import repo

    repo.stelle_szene_sicher(conn, 1, 2)
    _befehl(conn, einst, "/szene scene 2 delete")
    assert repo.hole_szenen(conn, 1) == []


def test_szene_entfernen_deutsch_wie_vorher(conn, einst):
    from interview_theater import repo

    repo.stelle_szene_sicher(conn, 1, 2)
    _befehl(conn, einst, "/szene szene 2 entfernen")
    assert repo.hole_szenen(conn, 1) == []


def test_kernthema_off_englisch(conn, einst, englisch):
    from interview_theater import repo

    repo.setze_arbeitsstand(conn, 1, "kernthema", "Arriving")
    _befehl(conn, einst, "/kernthema off")
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] is None


def test_kernthema_aus_deutsch_wie_vorher(conn, einst):
    from interview_theater import repo

    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    _befehl(conn, einst, "/kernthema off")
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "off"
    _befehl(conn, einst, "/kernthema aus")
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] is None


def test_wortlaut_off_englisch(conn, einst, englisch):
    from interview_theater import repo

    repo.setze_wortlaut_modus(conn, 1, "*")
    _befehl(conn, einst, "/wortlaut off")
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_wortlaut_aus_deutsch_wie_vorher(conn, einst):
    from interview_theater import repo

    repo.setze_wortlaut_modus(conn, 1, "*")
    _befehl(conn, einst, "/wortlaut aus")
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_stueck_setting_englisch(conn, einst, englisch):
    from interview_theater import repo

    _befehl(conn, einst, "/stueck setting A harbour at night")
    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] == "A harbour at night"
    _befehl(conn, einst, "/stueck setting off")
    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] is None


def test_stueck_rahmen_deutsch_wie_vorher(conn, einst):
    from interview_theater import repo

    tg = _befehl(conn, einst, "/stueck setting Ein Hafen")
    assert tg.texte() == ["Das kenne ich nicht. Es gibt /stueck rahmen <text>."]
    _befehl(conn, einst, "/stueck rahmen Ein Hafen bei Nacht")
    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] == "Ein Hafen bei Nacht"


def test_festlegung_remove_englisch(conn, einst, englisch):
    from interview_theater import repo

    repo.schreibe_festlegung(conn, 1, "struktur", "only one scene")
    _befehl(conn, einst, "/festlegung remove one scene")
    assert repo.festlegungen(conn, 1) == []


def test_festlegung_weg_deutsch_wie_vorher(conn, einst):
    from interview_theater import repo

    repo.schreibe_festlegung(conn, 1, "struktur", "nur eine Szene")
    _befehl(conn, einst, "/festlegung weg eine Szene")
    assert repo.festlegungen(conn, 1) == []


def test_szene_form_leer_englisch(conn, einst, englisch, monkeypatch):
    from interview_theater import knoepfe

    gerufen = []
    monkeypatch.setattr(knoepfe, "biete_szenenform",
                        lambda conn, tg, chat_id, nummer: gerufen.append(nummer))
    _befehl(conn, einst, "/szene scene 3 form")
    assert gerufen == [3]


def test_szene_form_leer_deutsch_wie_vorher(conn, einst, monkeypatch):
    from interview_theater import knoepfe

    gerufen = []
    monkeypatch.setattr(knoepfe, "biete_szenenform",
                        lambda conn, tg, chat_id, nummer: gerufen.append(nummer))
    _befehl(conn, einst, "/szene szene 3 form")
    assert gerufen == [3]


def test_szene_feld_englisch(conn, einst, englisch):
    from interview_theater import repo

    _befehl(conn, einst, "/szene scene 2 ort Harbour")
    szene = repo.hole_szenen(conn, 1)[0]
    assert (szene["nummer"], szene["ort"]) == (2, "Harbour")


def test_szene_feld_deutsch_wie_vorher(conn, einst):
    from interview_theater import repo

    _befehl(conn, einst, "/szene szene 2 ort Hafen")
    szene = repo.hole_szenen(conn, 1)[0]
    assert (szene["nummer"], szene["ort"]) == (2, "Hafen")


# --- Nachbesserung (Review Commit 15d70a8, Befund 4) ---------------------
#
# ``_SZENE_ENTFERNEN_EN``/``_SZENE_FELD_EN`` kannten als Praefix nur
# ``scene`` -- der Slash-Befehl selbst heisst aber weiterhin ``/szene``
# (Annahme A4), und eine englischsprachige Gruppe, die diesen Namen beim
# Tippen wiederholt ("/szene szene 2 remove"), fiel bis zum Schreibauftrag
# durch: weder Entfernung noch Feld griffen, das Modell haette "szene 2
# remove" als Szenentext-Auftrag bekommen. Gemessen mit dem Interpreter
# (``_SZENE_ENTFERNEN_EN.match("szene 2 remove")`` -> ``None``, mit
# ``scene`` statt ``szene`` -> Treffer). Fix: Praefix akzeptiert jetzt
# ``szene`` ODER ``scene`` (``(?:s(?:z|c)ene\s*)?``).

def test_szene_entfernen_englisch_mit_szene_praefix(conn, einst, englisch):
    from interview_theater import repo

    repo.lege_szene_an(conn, 1, 2, "Farewell", "Peter leaves", "PETER: Gone.")

    _befehl(conn, einst, "/szene szene 2 remove")

    assert repo.hole_szenen(conn, 1) == []


def test_szene_feld_englisch_mit_szene_praefix(conn, einst, englisch):
    from interview_theater import repo

    _befehl(conn, einst, "/szene szene 2 ort Harbour")
    szene = repo.hole_szenen(conn, 1)[0]
    assert (szene["nummer"], szene["ort"]) == (2, "Harbour")


def test_szene_form_leer_englisch_mit_szene_praefix(conn, einst, englisch, monkeypatch):
    """Derselbe Praefix-Fund wie oben, hier fuer den dritten Ort mit
    identischem Muster (``_SZENE_FORM_LEER_EN``) -- am Code entdeckt, nicht
    im Befund benannt, aber derselbe Fehler."""
    from interview_theater import knoepfe

    gerufen = []
    monkeypatch.setattr(knoepfe, "biete_szenenform",
                        lambda conn, tg, chat_id, nummer: gerufen.append(nummer))
    _befehl(conn, einst, "/szene szene 3 form")
    assert gerufen == [3]
