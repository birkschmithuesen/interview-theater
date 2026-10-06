"""Parser zweisprachig (D5): Englisch wird erkannt, Deutsch bleibt, wie es war.

Die deutschen Sollwerte sind am 30.09.2026 auf d8deb6c gemessen (Plan A1,
Aufgaben 22-24) -- sie aendern sich durch A1 nicht.
"""

import pytest

from interview_theater import (ablauf, begriffe, erkenner, kuerzung, kurzgeschichte, sprache,
                               stueckpruefung, szenenfolge, vorspann, web)
from interview_theater import szene as szene_modul
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


# --- Modellausgabe in beiden Sprachen (Aufgabe 23, D5 Art A) -------------
# Ausgabeparser probieren beide Sprachen, deutsch zuerst -- unabhaengig vom
# Profil, weil ein englisches Modell manchmal deutsch labelt und umgekehrt.
# Die deutschen Sollwerte sind gegen a739997 (vor Aufgabe 23) nachgemessen.

DE_SZENE = ("TITEL: Nacht\nKURZ: Zwei streiten.\nZUSAMMENFASSUNG: Sie streiten.\n"
            "ANDERS GEMACHT: nichts\n\nNADIA: Hallo")
EN_SZENE = ("TITLE: Night\nSHORT: Two argue.\nSUMMARY: They argue.\n"
            "DONE DIFFERENTLY: nothing\n\nNADIA: Hi")


class _Tg:
    def sende(self, *a, **k):
        return None


def test_szenenkopf_deutsch_wie_vorher():
    assert szene_modul.zerlege(DE_SZENE) == (
        "Nacht", "Zwei streiten.", "Sie streiten.", None, "NADIA: Hallo")


def test_szenenkopf_englisch_auch_unter_deutschem_profil():
    assert szene_modul.zerlege(EN_SZENE) == ("Night", "Two argue.", "They argue.", None, "NADIA: Hi")


def test_anders_gemacht_nothing_ist_keine_abweichung():
    """Offener Punkt (c): der englische Szenenprompt verlangt
    ``ANDERS GEMACHT: nothing``."""
    assert szene_modul.zerlege("ANDERS GEMACHT: nothing\n\nNADIA: Hi")[3] is None
    assert szene_modul.zerlege("ANDERS GEMACHT: nichts\n\nNADIA: Hi")[3] is None
    assert szene_modul.zerlege("ANDERS GEMACHT: Mira geht frueher\n\nNADIA: Hi")[3] == (
        "Mira geht frueher")


@pytest.mark.parametrize("text, soll", [("Schreib Szene 2", 2), ("write scene 2", 2),
                                        ("scene no. 4 please", 4)])
def test_szenennummer_beide(text, soll):
    assert szene_modul.nummer_aus_auftrag(text) == soll


@pytest.mark.parametrize("wort, soll", [("ort", "ort"), ("was passiert", "was_passiert"),
                                        ("place", "ort"), ("what happens", "was_passiert"),
                                        ("tone", "ton"), ("summary", "kurzbeschreibung")])
def test_feldname_beide(wort, soll):
    assert szene_modul.feldname(wort) == soll


@pytest.mark.parametrize("wert, soll", [
    ("Szene 2 | ort: Kanal", (2, {"ort": "Kanal"})),
    ("Scene 2 | place: canal", (2, {"ort": "canal"})),
    ("scene no. 3 | tone: quiet", (3, {"ton": "quiet"})),
])
def test_planung_beide(wert, soll):
    assert szene_modul.zerlege_planung(wert) == soll


@pytest.mark.parametrize("rahmen, soll", [
    ("Ort: Kanal, Zeit: Nacht", {"ort": "Kanal", "zeit": "Nacht"}),
    ("Ein Kanal bei Nacht", {"ort": "Ein Kanal bei Nacht"}),
    ("Place: canal, Time: night, Occasion: a farewell",
     {"ort": "canal", "zeit": "night", "anlass": "a farewell"}),
])
def test_rahmenfelder_beide(rahmen, soll):
    assert szene_modul.rahmenfelder(rahmen) == soll


@pytest.mark.parametrize("wert, soll", [("Szene 3", 3), ("3", 3), ("Scene 3", 3),
                                        ("Szene drei", None)])
def test_kuerzung_nummer_beide(wert, soll):
    assert kuerzung.nummer_aus_wert(wert) == soll


def test_kurzgeschichte_englische_zusammenfassung():
    text = ("## 1. Arrival\nText one.\nSummary: She arrives.\n\n"
            "## 2. Fight\nText two.\nSummary: It explodes.")
    assert kurzgeschichte.zerlege(text) == [("Arrival", "She arrives.", "Text one."),
                                           ("Fight", "It explodes.", "Text two.")]


def test_kurzgeschichte_englische_abschnittsueberschrift():
    text = "SECTION 1: Arrival\nText one.\nSummary: She arrives.\n\nPART 2: Fight\nText two."
    assert [t for t, _, _ in kurzgeschichte.zerlege(text)] == ["Arrival", "Fight"]


def test_kurzgeschichte_deutsch_wie_vorher():
    text = ("## 1. Ankunft\nText eins.\nZusammenfassung: Sie kommt an.\n\n"
            "## 2. Streit\nText zwei.\nZusammenfassung: Es kracht.")
    assert kurzgeschichte.zerlege(text) == [("Ankunft", "Sie kommt an.", "Text eins."),
                                           ("Streit", "Es kracht.", "Text zwei.")]


@pytest.mark.parametrize("text, soll", [
    ("Szene 1: Dialog, Szene 2: Monolog, Szene 3: Chor", {1: "dialog", 2: "monolog", 3: "chor"}),
    ("Chor-Dialog-Rap", {1: "chor", 2: "dialog", 3: "rap"}),
    ("Szene 1: Dialog, Szene 2: Song", None),
    ("Scene 1: Dialogue, Scene 2: Monologue, Scene 3: Chorus",
     {1: "dialog", 2: "monolog", 3: "chor"}),
    ("Choir-Dialogue-Song", {1: "chor", 2: "dialog", 3: "lied"}),
    ("They sing a song and then rap about it.", None),
])
def test_formabfolge_beide(text, soll):
    assert szenenfolge.formabfolge(text) == soll


def test_szenen_in_zeile_beide():
    assert szenenfolge.szenen_in_zeile(
        "Nacht am Kanal. Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis.") == [
        (1, "Ankunft am Steg", ""), (2, "Das Gestaendnis", "")]
    assert szenenfolge.szenen_in_zeile(
        "Night by the canal. Scene 1: Arrival at the pier. Scene 2: The confession.") == [
        (1, "Arrival at the pier", ""), (2, "The confession", "")]


def test_szenen_der_richtung_englisch_mit_form():
    assert szenenfolge.szenen_der_richtung(
        "Night. Scene 1: Arrival at the pier (Dialogue). Scene 2: The confession (Song).") == [
        (1, "Arrival at the pier", "dialog"), (2, "The confession", "lied")]
    # Ein Titel, der mit einem Formwort beginnt, ist eine Formwahl.
    assert szenenfolge.szenen_der_richtung(
        "Scene 1: Chorus with dance. Scene 2: Dialogue with interruptions.") == []


def test_szenenfolge_zeile_mit_englischem_praefix():
    assert szenenfolge.zerlege("Scene 1: Arrival - She arrives")[0][:2] == (
        "Arrival", "She arrives")
    assert szenenfolge.zerlege("Szene 1: Ankunft - Sie kommt an")[0][:2] == (
        "Ankunft", "Sie kommt an")


def test_ende_zeile_deutsch_wie_vorher():
    assert szenenfolge.zerlege_geschichte("Sie treffen sich.\nEnde: Sie gehen.") == (
        "Sie treffen sich.\nEnde: Sie gehen.", [])


@pytest.mark.parametrize("wort", ["End", "Ending"])
def test_ende_zeile_englisch(wort):
    """Abweichung vom Brief-Sollwert ("...\\nEnd: They leave."): die Ende-Zeile
    wird wie im Deutschen ueber ``T._GESCHICHTE_MIT_ENDE`` neu gesetzt -- unter
    dem deutschen Profil also "Ende:". Das Soll des Briefs ("gehoert zur
    Geschichte, keine Szene") gilt."""
    eingabe = "They meet.\n" + wort + ": They leave."
    assert szenenfolge.zerlege_geschichte(eingabe) == ("They meet.\nEnde: They leave.", [])


def test_ende_zeile_englisch_unter_englischem_profil(englisch):
    """Offener Punkt (b): in Englisch legt ``zerlege_geschichte`` "Ending:" ab,
    und genau das muss beim naechsten Lesen wieder erkannt werden."""
    assert szenenfolge.zerlege_geschichte("They meet.\nEnd: They leave.") == (
        "They meet.\nEnding: They leave.", [])
    assert szenenfolge.ist_ende_zeile("Ending: They leave.")
    assert szenenfolge.ist_ende_zeile("Ende: Sie gehen.")
    assert not szenenfolge.ist_ende_zeile("Endless night by the canal.")
    assert erkenner._ist_geschichte("They meet. Ending: They leave.")


@pytest.mark.parametrize("zeile, soll", [
    ("SZENE 1: Der Anfang", None), ("NADIA: Hallo", "NADIA"),
    ("SCENE 1: The beginning", None), ("TITLE: Night", None),
    ("DONE DIFFERENTLY: nothing", None),
])
def test_sprecher_der_zeile_beide(zeile, soll):
    assert web.sprecher_der_zeile(zeile) == soll


@pytest.mark.parametrize("wert, soll", [
    ("Sie streiten. Ende: Versoehnung.", True), ("Ein Kanal bei Nacht", False),
    ("They fight. End: reconciliation.", True),
    ("In the end they make up, then they leave, then it rains.", True),
    ("A canal at night", False),
])
def test_ist_geschichte_beide(wert, soll):
    assert erkenner._ist_geschichte(wert) is soll


@pytest.mark.parametrize("text, soll", [
    ("Wir wollen drei Figuren", "3"), ("vier bis fuenf Figuren", "4 bis 5"),
    ("2 bis 3 Hauptfiguren", None),
    ("We want three characters", "3"), ("four to five characters", "4 bis 5"),
    ("The number of characters is 6", "6"),
    ("2 main characters", None), ("5 side characters", None),
])
def test_figurenzahl_aus_beide(text, soll):
    assert erkenner.figurenzahl_aus(text) == soll


@pytest.mark.parametrize("wert, soll", [
    ("Figur Peter", ("figur", "Peter")), ("Kernthema", ("kernthema", "")),
    ("character Peter", ("figur", "Peter")), ("core theme", ("kernthema", "")),
    ("Scene 2", ("szene", "2")), ("recording of Meryem", ("aufnahme", "of Meryem")),
    ("storyline", None),
])
def test_entfernen_ziele_beide(wert, soll):
    assert erkenner._zerlege_entfernen(wert) == soll


@pytest.mark.parametrize("name, soll", [
    ("Figur 2", True), ("Nebenfigur 1", True), ("Character 2", True),
    ("Side character 1", True), ("Placeholder", True), ("Nadia", False),
    ("Charlotte", False),
])
def test_platzhaltername_beide(name, soll):
    from interview_theater import repo

    assert repo.ist_platzhaltername(name) is soll


def test_vorspann_schneidet_englische_formeln():
    assert vorspann.erster_satz(
        "Nadia fights with herself provides the background for her refusal") == (
        "Nadia fights with herself")
    assert vorspann.erster_satz(
        "Mira kaempft mit sich selbst liefert den Hintergrund fuer ihre Ablehnung") == (
        "Mira kaempft mit sich selbst")
    # Die Untergrenze schuetzt wie im Deutschen.
    assert vorspann.erster_satz("Mira shows grit.") == "Mira shows grit."


@pytest.mark.parametrize("text, soll", [
    ("Spannungsbogen", "Spannungsbogen"), ("Anfang und Ende", "Anfang und Ende"),
    ("Figurenzeichnung", "Figuren"),
    # Offener Punkt (d): die sechs Namen aus sprachen/en/prompts/stueckpruefung.md.
    ("Tension arc", "Spannungsbogen"), ("Characters", "Figuren"),
    ("Suspense", "Spannung"), ("Plausibility", "Nachvollziehbarkeit"),
    ("Beginning and end", "Anfang und Ende"), ("Language and speakability", "Sprechbarkeit"),
    ("Research", None),
])
def test_frage_fuer_beide(text, soll):
    assert stueckpruefung.frage_fuer(text) == soll


def test_die_sechs_englischen_fragenamen_treffen_die_sechs_fragen():
    """Offener Punkt (d), gegen den Prompt selbst statt gegen eine Abschrift."""
    import pathlib
    import re

    prompt = (pathlib.Path(stueckpruefung.__file__).parent
              / "sprachen/en/prompts/stueckpruefung.md").read_text(encoding="utf-8")
    namen = re.findall(r"^\d\. (.+?) --", prompt, re.MULTILINE)
    assert len(namen) == 6
    assert [stueckpruefung.frage_fuer(n) for n in namen] == [
        name for name, _ in stueckpruefung.FRAGEN]


def test_denkspur_beide():
    assert ablauf.ist_denkspur("I should: help the group. The group wants more. The rule says no markdown.")
    assert ablauf.ist_denkspur("Ich soll: der Gruppe helfen. Die Gruppe will mehr.")
    # Eine echte englische Antwort mit Ratschlag ist keine Denkspur.
    assert not ablauf.ist_denkspur(
        "You should ask her about her childhood. I should add: take your time.")


@pytest.mark.parametrize("text", [
    # Nachbesserung (Review Commit fbc47e9, Befund 1): vier am Interpreter
    # gemessene Faelle, in denen normale Antworten als Denkspur verworfen
    # wurden -- siehe task-23-report.md Nachbesserung.
    "Perfect. That is a strong ending. I suggest a title: The Pier.",
    "Good idea. I should mention that scene 2 still has no place. "
    "I suggest a park at night.",
    "Nice. The group wants a sad ending, so I suggest a final image at the station.",
    "Your turn is next: tell me who the third character is.",
])
def test_denkspur_englisch_keine_falsch_positiven(text):
    assert not ablauf.ist_denkspur(text), text


def test_denkspur_kern_englisch(englisch):
    text = ("I should: keep it short. The group wants a scene.\n\n"
            "Your scene is ready to go - tell me which moment you want to start with, "
            "and I will write it.")
    assert ablauf._denkspur_kern(text).startswith("Your scene is ready")


def test_denkspur_kern_bleibt_deutsch_fuer_dortmund():
    """Nachbesserung (Review-Befund 2): ohne aktives Profil (code() == "de")
    rettet _denkspur_kern nur einen deutsch beginnenden Absatz -- ein
    englisch beginnender Absatz bleibt unverwertet, genau wie vor Karte A1."""
    text = ("I should: keep it short. The group wants a scene.\n\n"
            "Your scene is ready to go - tell me which moment you want to start with, "
            "and I will write it.")
    assert ablauf._denkspur_kern(text) is None


def test_tschechow_ist_im_englischen_aus(englisch):
    from interview_theater.dramaturgie import mechanik

    assert mechanik._motive("The Suitcase stands in the Kitchen again and again.", ()) == set()


def test_tschechow_bleibt_im_deutschen():
    from interview_theater.dramaturgie import mechanik

    assert "Reisekoffer" in mechanik._motive("Dann steht der Reisekoffer wieder da.", ())


def test_tschechow_kandidaten_im_englischen_leer(englisch):
    from interview_theater.dramaturgie import mechanik

    lage = mechanik.Szenenlage(nummern=[1], texte={1: (
        "NADIA: The Suitcase is here. The Suitcase is heavy. The Suitcase stays.")})
    assert mechanik.tschechow_kandidaten(lage) == []


def test_kollektive_englisch():
    """Offener Punkt (c): ``BOTH:`` und ``HOOK (ALL)`` aus den englischen
    Formen sind Kollektive, keine Geisterfiguren."""
    from interview_theater.dramaturgie import mechanik

    repliken = mechanik.repliken("BOTH: We stay.\n\nHOOK (ALL)\nLine")
    assert [r.label for r in repliken]
    assert {mechanik._schluessel(r.label) for r in repliken} <= mechanik.KOLLEKTIV_EN
    assert all(mechanik._schluessel(r.label) in mechanik.KOLLEKTIVE for r in repliken)
    lage = mechanik.Szenenlage(nummern=[1], figuren=["Nadia"], texte={1: ""},
                               repliken={1: repliken})
    assert [b for b in mechanik.geisterfiguren(lage) if b.pruefung == "geisterfigur"] == []


def test_englische_strukturzeilen_sind_keine_sprecher():
    from interview_theater.dramaturgie import mechanik

    labels = [r.label for r in mechanik.repliken(
        "SCENE 1: The pier\nTITLE: Night\nNADIA: Hi.\n\nVERSE (NADIA)\nI stay")]
    assert labels == ["NADIA", "NADIA"]


def test_erste_form_englisch_mit_beschriftung(englisch):
    """Offener Punkt (g): ``_TEXT_ERSTE_FORM`` nennt in Englisch die
    Anzeigebeschriftung ("monologue"), nicht den rohen DB-Wert."""
    from interview_theater.dramaturgie import mechanik

    lage = mechanik.Szenenlage(nummern=[1, 2], formen={1: "monolog", 2: "dialog"})
    texte = [b.text for b in mechanik.formverteilung(lage, phase=mechanik.FORM_AB_PHASE)]
    assert any(t.startswith("Scene 1 is a monologue.") for t in texte)


def test_erste_form_deutsch_wie_vorher():
    from interview_theater.dramaturgie import mechanik

    lage = mechanik.Szenenlage(nummern=[1, 2], formen={1: "monolog", 2: "dialog"})
    texte = [b.text for b in mechanik.formverteilung(lage, phase=mechanik.FORM_AB_PHASE)]
    assert any(t.startswith("Szene 1 ist ein monolog.") for t in texte)


@pytest.mark.parametrize("wert, soll", [
    ("hoch", "hoch"), ("blocker", "blocker"), ("niedrig", "niedrig"), ("", "mittel"),
    ("high", "hoch"), ("Medium", "mittel"), ("low", "niedrig"),
    ("below average", "mittel"),
])
def test_schwere_beide(wert, soll):
    """Offener Punkt (e)."""
    from interview_theater.dramaturgie import fanout

    assert fanout._schwere(wert) == soll


@pytest.mark.parametrize("wert", [
    "Hallo, wir sind vom Theaterprojekt.\nAbschluss: Danke fuer deine Zeit.",
    "Opening: Hallo, wir sind vom Theaterprojekt.\nClosing: Danke fuer deine Zeit.",
    "Hallo, wir sind vom Theaterprojekt.\nClosing: Danke fuer deine Zeit.",
])
def test_eroeffnung_abschluss_beide(conn, wert):
    """Offener Punkt (f): "Opening:"/"Closing:" zusaetzlich zu den deutschen
    Koepfen."""
    from interview_theater import repo

    repo.sichere_gruppe(conn, 1, "test", "Gruppe")
    fragen._speichere_eroeffnung(conn, _Tg(), 1, wert)
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["interview_eroeffnung"] == "Hallo, wir sind vom Theaterprojekt."
    assert stand["interview_abschluss"] == "Danke fuer deine Zeit."


# --- Interne Auftragszeilen (offener Punkt a) ----------------------------

def test_auftragszeilen_deutsch_wie_vorher():
    from interview_theater.dramaturgie import fanout

    assert szene_modul.T.TEXT_AUFTRAG_SCHREIBEN.format(nummer=2) == "Schreib Szene 2."
    assert szene_modul.T.TEXT_AUFTRAG_NEU.format(nummer=2, notiz="Kuerzer.") == (
        "Schreib Szene 2 neu. Kuerzer.")
    # Nachbesserung (Review-Befund 3): fanout.T.TEXT_SZENENAUFTRAG gibt es
    # nicht mehr -- fanout.szenenauftrag delegiert an szene.T.TEXT_AUFTRAG_NEU.
    assert fanout.szenenauftrag({"szene": 3, "text": "X"}) == "Schreib Szene 3 neu. X"


def test_auftragszeilen_englisch_und_lesbar(englisch):
    from interview_theater.dramaturgie import fanout

    schreiben = szene_modul.T.TEXT_AUFTRAG_SCHREIBEN.format(nummer=2)
    neu = szene_modul.T.TEXT_AUFTRAG_NEU.format(
        nummer=4, notiz="Shorter. " + szene_modul.BISHER_MARKER)
    pruefung = fanout.szenenauftrag({"szene": 3, "text": "More conflict."})
    assert (schreiben, neu.split(".")[0], pruefung) == (
        "Write scene 2.", "Rewrite scene 4", "Rewrite scene 3. More conflict.")
    # Der Parser liest die Nummer, der Marker bleibt Protokoll.
    assert [szene_modul.nummer_aus_auftrag(t) for t in (schreiben, neu, pruefung)] == [2, 4, 3]
    assert szene_modul.BISHER_MARKER in neu


def test_kuerzungsauftrag_englisch(conn, englisch, monkeypatch):
    """Der Kuerzungsauftrag geht in Englisch als "Rewrite scene N." an
    ``szene.starte`` -- die Nummer bleibt lesbar, der Marker bleibt."""
    from interview_theater.knoepfe import szenen as knoepfe_szenen

    gerufen = []
    monkeypatch.setattr(szene_modul, "starte",
                        lambda conn, tg, klm, e, chat_id, auftrag: gerufen.append(auftrag) or object())
    monkeypatch.setattr(kuerzung, "_hat_text", lambda conn, chat_id, nummer: True)
    monkeypatch.setattr(knoepfe_szenen, "_melde_spaetere", lambda *a: None)
    kuerzung.starte(conn, _Tg(), None, None, 1, 2)
    assert gerufen and gerufen[0].startswith("Rewrite scene 2. ")
    assert szene_modul.nummer_aus_auftrag(gerufen[0]) == 2
    assert szene_modul.BISHER_MARKER in gerufen[0]


# --- Systemzeilen und Rundreisen (Aufgabe 24) ------------------------------

from interview_theater import kontext  # noqa: E402
from interview_theater import repo  # noqa: E402


def test_jeder_englische_systemanfang_steht_in_der_tabelle():
    """Rundreise: der Anfang muss zu einem englischen Text passen, sonst
    erkennt der Code seine eigene Zeile nicht wieder."""
    sprache.vergiss()
    werte = []
    for eintraege in sprache.tabelle("en").values():
        for wert in eintraege.values():
            if isinstance(wert, str):
                werte.append(wert.lstrip())
    for anfang in kontext._SYSTEMANFAENGE_EN:
        assert any(w.startswith(anfang) for w in werte), anfang


def test_deutsche_systemanfaenge_wie_vorher():
    assert kontext._SYSTEMANFAENGE == (
        "Bin wieder da.", "Notiert:", "Aufnahme laeuft.", "Aufnahme beendet.",
        "Bereit -", "Hinweis: Den Szenentext", "Ich schreibe die Szene aus",
        "Ich schreibe gerade noch", "Ich werte die offenen Interviews aus",
        "Entfernt:",
    )


def test_englische_notiert_zeile_faellt_aus_dem_fenster():
    assert kontext._ist_systemzeile({"ist_bot": 1, "text": "Noted:\n- Terms: love"})
    assert kontext._ist_systemzeile({"ist_bot": 1, "text": "Notiert:\n- Begriffe: Liebe"})
    assert not kontext._ist_systemzeile({"ist_bot": 0, "text": "Noted: we agree"})


@pytest.mark.parametrize("text", [
    "Removed: character Peter.", "Withdrawn: the ending at the pier",
    "I'm back. We're at Terms.", "Recording stopped.",
    "Ready - send your voice messages.", "I'm writing out the scene, that takes a minute.",
    "I'm still writing a scene, one moment.", "I'm analysing the open interviews.",
    "Note: the scene text is written by a model from Anthropic (USA).",
])
def test_englische_systemzeilen_fallen_aus_dem_fenster(text):
    assert kontext._ist_systemzeile({"ist_bot": 1, "text": text})


@pytest.mark.parametrize("text", [
    "I'm glad you like the ending.", "Noted, but what about scene 2?",
    "Ready when you are: who is the third character?",
    "Recording is a good idea for the second interview.",
])
def test_normale_englische_bot_antwort_ist_keine_systemzeile(text):
    assert not kontext._ist_systemzeile({"ist_bot": 1, "text": text})


@pytest.mark.parametrize("text", [
    "I'm writing out the scene, that takes a minute.",
    "I'm writing out the scene now.",
    "I'm writing the scene now.",
    "Starting now. The story is coming.",
    "Great. Starting now!",
    "Your data goes to a US server for the scene text.",
    "Should I use the US model?",
    "Recordings stay in Switzerland, only the scene details go to the US.",
])
def test_erfundene_englische_systemzeile(text):
    assert ablauf.ist_erfundene_systemzeile(text), text


def test_erfundene_deutsche_systemzeile_wie_vorher():
    assert ablauf.ist_erfundene_systemzeile("Ich schreibe die Szene jetzt aus.")
    assert ablauf.ist_erfundene_systemzeile("Start frei!")
    assert ablauf.ist_erfundene_systemzeile("Das geht an einen US-Server.")
    assert not ablauf.ist_erfundene_systemzeile("Mir gefaellt, wie die Szene endet.")


@pytest.mark.parametrize("text", [
    "I like how the scene ends.",
    "Tell us what happens next.",
    "Let us think about Switzerland as a setting.",
    "We could try starting now with the second scene.",
    "Show us model answers for the first question?",
    "Are you writing the scene yourselves, or should the button do it?",
    "Once you have the story, the button writes it out.",
])
def test_normale_englische_antwort_ist_keine_erfundene_systemzeile(text):
    assert not ablauf.ist_erfundene_systemzeile(text), text


def test_regienotizen_finden_beide_sprachen(conn, englisch):
    repo.schreibe_journal(conn, 1, "entschieden", "Szene 2: ohne den Bruder", quelle="test")
    repo.schreibe_journal(conn, 1, "entschieden", "Scene 2: at night", quelle="test")
    repo.schreibe_journal(conn, 1, "entschieden", "Scene 4: elsewhere", quelle="test")
    notizen = szene_modul._regienotizen(conn, 1, 2)
    assert notizen == ["- Szene 2: ohne den Bruder", "- Scene 2: at night"]


@pytest.mark.parametrize("text, soll", [
    # P57 Lauf 2 A2: die Nummer des Lesewunschs, nicht die erste im Satz.
    ("Scene 1 is good now. Please show scene 2", 2),
    ("Scene 1 is good now. Please show scene 2.", 2),
    ("show scene 2", 2),
    ("Please read scene 3, scene 1 is fine", 3),
    ("scene 2 - show me the text", 2),
    ("in scene 2 he leaves", None),
])
def test_szenentext_englisch_nimmt_die_nummer_des_lesewunschs(englisch, text, soll):
    assert ablauf.szenentext_gewuenscht(text) == soll


@pytest.mark.parametrize("text, soll", [
    ("Szene 1 ist gut. Zeig bitte Szene 2", 2),
    ("Szene 1 gefaellt uns, lies uns jetzt Szene 3 vor", 3),
    ("zeig mal Szene 2", 2),
    ("in Szene 2 soll er gehen", None),
])
def test_szenentext_deutsch_nimmt_die_nummer_des_lesewunschs(text, soll):
    assert ablauf.szenentext_gewuenscht(text) == soll
