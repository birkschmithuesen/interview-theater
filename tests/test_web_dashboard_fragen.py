"""Regie-Dashboard: ALLE ausgewaehlten Fragen einer Gruppe, geclustert nach
Begriff, numeriert wie im Chat, mit eigen/KI-Markierung (Fast-Track
06.10.2026, Birk: "soll alle Fragen darstellen, nicht nur die ersten ...
geclustert nach Begriffen" + "mit der Markierung, ob sie eigen oder
KI-generiert waren").

Reine Funktion zuerst (``auswahl.dashboard_fragen``), dann die HTML-Seite
(``web.dashboard_html``) -- Dortmund bleibt unberuehrt, weil der neue Pfad
nur hinter ``web.dashboard_gestaltet`` (Padua) steht.
"""

import copy
import re

import pytest

from interview_theater import auswahl, sprache, web, workshop
from test_web_dashboard_en import DATEN, _profil


@pytest.fixture(autouse=True)
def _frisch():
    yield
    workshop.vergiss()
    sprache.vergiss()


def _stand(**felder) -> dict:
    basis = {
        "begriffe": None, "fragen": None, "fragen_auswahl": None,
        "fragen_herkunft": None, "fragen_entschieden": None,
        "fragen_herkunft_final": None,
    }
    basis.update(felder)
    return basis


def _geschlossen_stand() -> dict:
    """Sieben Fragen, drei Begriffe, die endgueltige Liste wie im Chat."""
    return _stand(
        begriffe="Home, Work, Family",
        fragen=(
            "Home: Q1\nWork: Q2\nHome: Q3\nFamily: Q4\n"
            "Work: Q5\nHome: Q6\nFamily: Q7"
        ),
        fragen_herkunft_final="eigen,ki,eigen,ki,eigen,ki,eigen",
    )


# --- auswahl.dashboard_fragen: geschlossene Liste ----------------------------


def test_geschlossen_alle_sieben_vorhanden_numeriert_1_bis_7():
    erg = auswahl.dashboard_fragen(_geschlossen_stand())
    assert erg["offen"] is False
    assert erg["kept"] == 7
    nummern = sorted(e["nummer"] for g in erg["gruppen"] for e in g["eintraege"])
    assert nummern == list(range(1, 8))


def test_geschlossen_drei_ueberschriften_in_begriffsreihenfolge():
    erg = auswahl.dashboard_fragen(_geschlossen_stand())
    assert [g["titel"] for g in erg["gruppen"]] == ["Home", "Work", "Family"]


def test_geschlossen_jede_gruppe_behaelt_ihre_urspruengliche_nummer():
    """Numerierung bleibt die des Chats (1..7), NICHT neu 1..n je Gruppe --
    sonst zeigte die Karte eine andere Zaehlung als "Fragen uebernommen"."""
    erg = auswahl.dashboard_fragen(_geschlossen_stand())
    je_titel = {g["titel"]: [e["nummer"] for e in g["eintraege"]] for g in erg["gruppen"]}
    assert je_titel == {"Home": [1, 3, 6], "Work": [2, 5], "Family": [4, 7]}


def test_geschlossen_kein_begriff_praefix_mehr_im_text():
    erg = auswahl.dashboard_fragen(_geschlossen_stand())
    texte = [e["text"] for g in erg["gruppen"] for e in g["eintraege"]]
    assert texte == ["Q1", "Q3", "Q6", "Q2", "Q5", "Q4", "Q7"]


def test_geschlossen_herkunft_je_nummer_aus_herkunft_final():
    erg = auswahl.dashboard_fragen(_geschlossen_stand())
    je_nummer = {e["nummer"]: e["herkunft"] for g in erg["gruppen"] for e in g["eintraege"]}
    assert je_nummer == {1: "eigen", 2: "ki", 3: "eigen", 4: "ki",
                          5: "eigen", 6: "ki", 7: "eigen"}


def test_geschlossen_herkunft_final_null_wird_aus_auswahl_nachgeschlagen():
    """Alte Runden (vor dem A/B-Vergleich) kennen ``fragen_herkunft_final``
    nicht -- die Herkunft kommt dann per Textabgleich aus
    ``fragen_auswahl``/``fragen_herkunft``."""
    stand = _geschlossen_stand()
    stand["fragen_herkunft_final"] = None
    stand["fragen_auswahl"] = stand["fragen"]
    stand["fragen_herkunft"] = "eigen,ki,eigen,ki,eigen,ki,eigen"
    erg = auswahl.dashboard_fragen(stand)
    je_nummer = {e["nummer"]: e["herkunft"] for g in erg["gruppen"] for e in g["eintraege"]}
    assert je_nummer[1] == "eigen"
    assert je_nummer[2] == "ki"


def test_geschlossen_herkunft_final_falscher_laenge_wird_nachgeschlagen():
    """Passt die Laenge von ``fragen_herkunft_final`` nicht mehr zu
    ``fragen`` (verwaister Stand), gilt sie wie fehlend."""
    stand = _geschlossen_stand()
    stand["fragen_herkunft_final"] = "eigen"  # zu kurz fuer sieben Fragen
    stand["fragen_auswahl"] = stand["fragen"]
    stand["fragen_herkunft"] = "ki,ki,ki,ki,ki,ki,ki"
    erg = auswahl.dashboard_fragen(stand)
    je_nummer = {e["nummer"]: e["herkunft"] for g in erg["gruppen"] for e in g["eintraege"]}
    assert je_nummer[1] == "ki"


# --- auswahl.dashboard_fragen: offene Sortierung -----------------------------


def test_offen_nur_ja_zeilen_numeriert_1_bis_k():
    """Mutationswaechter: faellt der ``zustand != 'ja'``-Filter weg, zeigt
    das Dashboard verworfene/offene Fragen als "schon behalten" -- dieser
    Test schlaegt dann fehl (``kept`` waere 4 statt 2)."""
    stand = _stand(
        begriffe="Home, Work",
        fragen_auswahl="Home: Q1\nWork: Q2\nHome: Q3\nWork: Q4",
        fragen_herkunft="eigen,ki,eigen,ki",
        fragen_entschieden="ja,nein,ja,",  # Q2 weg, Q4 noch offen
    )
    erg = auswahl.dashboard_fragen(stand)
    assert erg["offen"] is True
    assert erg["kept"] == 2
    texte = {e["nummer"]: e["text"] for g in erg["gruppen"] for e in g["eintraege"]}
    assert texte == {1: "Q1", 2: "Q3"}
    herkunft = {e["nummer"]: e["herkunft"] for g in erg["gruppen"] for e in g["eintraege"]}
    assert herkunft == {1: "eigen", 2: "eigen"}


def test_offen_ohne_ja_aber_mit_bisheriger_liste_zeigt_die_bisherige():
    """Padua 06.10. (Birk: 'Auflistung nur bei Gruppe 3'): G1/G2 sortierten neu,
    noch kein Haken -> Dashboard war leer. Mutant: Rueckfall entfernt -> rot."""
    stand = _stand(begriffe="Home, Work", fragen="Home: A\nWork: B\nHome: C",
                   fragen_herkunft_final="eigen,ki,eigen",
                   fragen_auswahl="Home: A\nWork: B\nHome: C\nWork: D",
                   fragen_herkunft="eigen,ki,eigen,ki", fragen_entschieden=",,,")
    fd = auswahl.dashboard_fragen(stand)
    assert fd["offen"] is True and fd["kept"] == 0 and fd.get("vorher") is True
    nummern = [e["nummer"] for g in fd["gruppen"] for e in g["eintraege"]]
    assert sorted(nummern) == [1, 2, 3]


def test_html_offen_ohne_ja_zeigt_bisherige_liste_mit_hinweis(monkeypatch):
    karte = _karte_mit(
        monkeypatch, begriffe="Home, Work", fragen="Home: A\nWork: B",
        fragen_herkunft_final="eigen,ki", fragen_auswahl="Home: A\nWork: B\nHome: C",
        fragen_herkunft="eigen,ki,eigen", fragen_entschieden="nein,,",
    )
    assert karte.count("<li value=") == 2
    assert "previous list" in karte or "bisherige Liste" in karte


def test_offen_ohne_eine_einzige_ja_zeile_ist_leer_aber_kein_none():
    stand = _stand(begriffe="Home", fragen_auswahl="Home: Q1", fragen_entschieden="nein")
    assert auswahl.dashboard_fragen(stand) == {"offen": True, "kept": 0, "gruppen": []}


def test_ohne_jede_frage_ist_none():
    assert auswahl.dashboard_fragen(_stand()) is None


# --- HTML: die Karte im gestalteten (Padua) Dashboard ------------------------


def _karte_mit(monkeypatch, **arbeitsstand_felder) -> str:
    _profil(monkeypatch, "padua-2026")
    daten = copy.deepcopy(DATEN)
    daten["gruppen"][0]["arbeitsstand"].update(arbeitsstand_felder)
    html = web.dashboard_html(daten)
    treffer = re.findall(r'<section class="karte[^"]*">.*?</section>', html, flags=re.S)
    return treffer[0]


def test_html_geschlossene_liste_zeigt_alle_sieben_geclustert(monkeypatch):
    karte = _karte_mit(
        monkeypatch,
        begriffe="Home, Work, Family",
        fragen=(
            "Home: Q1\nWork: Q2\nHome: Q3\nFamily: Q4\n"
            "Work: Q5\nHome: Q6\nFamily: Q7"
        ),
        fragen_herkunft_final="eigen,ki,eigen,ki,eigen,ki,eigen",
    )
    assert karte.count('<h4 class="fragen-begriff">') == 3
    assert karte.count("<li value=") == 7
    for n in range(1, 8):
        assert f'<li value="{n}">' in karte
    assert "Home: Q1" not in karte  # kein Begriffs-Praefix mehr im Eintrag


def test_html_eigen_und_ki_markierung_steht_an_der_frage(monkeypatch):
    karte = _karte_mit(
        monkeypatch,
        begriffe="Home",
        fragen="Home: Q1\nHome: Q2",
        fragen_herkunft_final="eigen,ki",
    )
    assert '<span class="herkunft eigen">own</span>' in karte
    assert '<span class="herkunft ki">AI</span>' in karte


def test_html_offene_sortierung_zeigt_fortschrittszeile(monkeypatch):
    karte = _karte_mit(
        monkeypatch,
        begriffe="Home, Work",
        fragen=None,
        fragen_auswahl="Home: Q1\nWork: Q2\nHome: Q3\nWork: Q4",
        fragen_herkunft="eigen,ki,eigen,ki",
        fragen_entschieden="ja,nein,ja,",
    )
    assert '<li value="1">' in karte
    assert '<li value="2">' in karte
    assert karte.count("<li value=") == 2
    assert "kept so far" in karte or "schon behalten" in karte


def test_html_ohne_fragen_bleibt_feld_weg(monkeypatch):
    karte = _karte_mit(monkeypatch, begriffe=None, fragen=None)
    assert "fragen-begriff" not in karte
    assert "fragen-voll" not in karte


def test_html_volle_liste_traegt_keine_zeilenkappung(monkeypatch):
    """Mutationswaechter: haengt die Vollliste wieder an ``dd.kurz`` (statt
    ``dd.fragen-voll``), kappt das CSS sie wieder auf drei Zeilen -- dieser
    Test schlaegt dann fehl."""
    karte = _karte_mit(
        monkeypatch,
        begriffe="Home, Work, Family",
        fragen=(
            "Home: Q1\nWork: Q2\nHome: Q3\nFamily: Q4\n"
            "Work: Q5\nHome: Q6\nFamily: Q7"
        ),
        fragen_herkunft_final="eigen,ki,eigen,ki,eigen,ki,eigen",
    )
    kopf = "<dt>Questions</dt>"
    assert kopf in karte
    rest = karte.split(kopf, 1)[1]
    assert rest.startswith('<dd class="fragen-voll">')


# --- Dortmund bleibt unberuehrt ----------------------------------------------


def test_dortmund_zeigt_weiterhin_die_alte_fragenliste(monkeypatch):
    _profil(monkeypatch, "dortmund-2026")
    daten = copy.deepcopy(DATEN)
    daten["gruppen"][0]["arbeitsstand"].update(
        begriffe="Home, Work, Family",
        fragen=(
            "Home: Q1\nWork: Q2\nHome: Q3\nFamily: Q4\n"
            "Work: Q5\nHome: Q6\nFamily: Q7"
        ),
        fragen_herkunft_final="eigen,ki,eigen,ki,eigen,ki,eigen",
    )
    html = web.dashboard_html(daten)
    assert "fragen-begriff" not in html
    assert "fragen-voll" not in html
    assert '<ul class="fragen">' in html
