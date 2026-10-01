"""Der letzte Sprachpass: vier mechanisch gezaehlte Muster (30.09.2026, Karte R).

Kein Modell, kein Netz. Je Muster mindestens drei Positiv- und drei
Negativfaelle, und die Negativfaelle sind die eigentliche Arbeit: eine
Requisitenliste in einer Regieanweisung, ein Bindestrich-Kompositum, ein
Sprecherkopf und ein "but" als gewoehnliche Konjunktion duerfen nicht feuern.
Ein falscher Befund kostet einen bezahlten Lauf und Vertrauen; ein fehlender
kostet eine Gelegenheit.

Das Material ist erfunden.
"""

import pytest

from interview_theater import sprachpass


# --- entkleide ------------------------------------------------------------


def test_entkleide_nimmt_sprecherkoepfe_und_regie():
    text = "MIRA: (steht auf, sehr langsam) Nein.\nPAL: Doch."
    ohne = sprachpass.entkleide(text)
    assert "MIRA:" not in ohne
    assert "steht auf" not in ohne
    assert "Nein." in ohne and "Doch." in ohne


def test_entkleide_laesst_prosa_stehen():
    """Phase 6 ist Prosa ohne Sprecherkoepfe -- dort darf nichts wegfallen."""
    text = "Sie steht am Fenster und wartet. Der Kanal liegt still."
    assert sprachpass.entkleide(text) == text


def test_entkleide_nimmt_auch_die_kopfzeilen_des_szenenformats():
    """``TITEL:``, ``ZUSAMMENFASSUNG:`` und ``ANDERS GEMACHT:`` sind
    Protokoll und kein Text der Szene -- sie duerfen nicht mitgezaehlt
    werden."""
    ohne = sprachpass.entkleide("ZUSAMMENFASSUNG: Sie gehen.\n\nMIRA: Ja.")
    assert "ZUSAMMENFASSUNG" not in ohne


# --- 1. Gedankenstriche ---------------------------------------------------


@pytest.mark.parametrize("text", [
    "She waited—and waited—and waited.",
    "Das war es – jedenfalls fast – gewesen.",
    "Sie kam spaet -- wie immer.",
])
def test_gedankenstriche_positiv(text):
    assert sprachpass.rohzahlen(text)["gedankenstriche"] >= 1, text


@pytest.mark.parametrize("text", [
    # Bindestrich-Kompositum: ein Bindestrich ohne Leerzeichen ist kein
    # Gedankenstrich.
    "a well-known face in the neighbourhood",
    "die Sechzehn-Stunden-Schicht",
    # Listenstrich am Zeilenanfang -- davor steht kein Wortzeichen.
    "- Milch\n- Brot\n- Zucker",
])
def test_gedankenstriche_negativ(text):
    assert sprachpass.rohzahlen(text)["gedankenstriche"] == 0, text


def test_gedankenstriche_werden_je_tausend_woerter_gerechnet():
    """Ein Strich in 2.230 Woertern (Dortmund v2, gemessen) sind 0,45 je
    1.000 -- weit unter dem Grenzwert 6,0. Die Einheit macht den
    Unterschied zwischen "ein Strich" und "Inflation"."""
    text = ("wort " * 999) + "eins—zwei"
    zahl = sprachpass.zaehle(text)["gedankenstriche"]
    assert 0.9 <= zahl <= 1.1, zahl


# --- 2. not X but Y / nicht X, sondern Y ---------------------------------


@pytest.mark.parametrize("text", [
    "It was not a home but a waiting room.",
    "She was not only tired but also angry.",
    "It was not loud, but heavy.",
])
def test_nicht_sondern_positiv_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["nicht_sondern"] >= 1, text


@pytest.mark.parametrize("text", [
    # "but" als gewoehnliche Konjunktion nach einer Verneinung.
    "She was not ready but I tried anyway.",
    "He could not hear her. But she stayed.",
    # "nothing but" ist kein Muster.
    "There was nothing but water.",
])
def test_nicht_sondern_negativ_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["nicht_sondern"] == 0, text


@pytest.mark.parametrize("text, soll", [
    ("Es war nicht Heimat, sondern Warteraum.", 1),
    ("Sie war nicht muede, sondern wuetend.", 1),
    ("Sie konnte nicht schlafen. Sondern? Nichts.", 0),
])
def test_nicht_sondern_deutsch(text, soll):
    assert sprachpass.rohzahlen(text, "de")["nicht_sondern"] == soll, text


# --- 3. Adjektiv-Dreierketten -------------------------------------------


@pytest.mark.parametrize("text", [
    "She was tired, angry, and alone.",
    "It felt cold, wet, empty.",
    "The room seemed smaller, darker, colder.",
])
def test_dreier_positiv_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["adjektiv_dreier"] >= 1, text


@pytest.mark.parametrize("text", [
    # Namensliste -- grossgeschrieben.
    "There was John, Mary, and Sue.",
    # Requisitenliste mit Artikel.
    "On the table was a cup, a plate, and a knife.",
    # Aufzaehlung in einer Regieanweisung -- ``entkleide`` raeumt sie weg.
    "MIRA: Ja.\n(Auf dem Tisch: a cup, a plate, and a knife.)",
    # Nur zwei.
    "She was tired and angry.",
])
def test_dreier_negativ_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["adjektiv_dreier"] == 0, text


@pytest.mark.parametrize("text, soll", [
    ("Sie war muede, wuetend und allein.", 1),
    ("Es war kalt, nass, leer.", 1),
    ("Da waren Mira, Pal und Nadia.", 0),
])
def test_dreier_deutsch(text, soll):
    assert sprachpass.rohzahlen(text, "de")["adjektiv_dreier"] == soll, text


# --- 4. Fazitsatz -------------------------------------------------------


@pytest.mark.parametrize("text", [
    "She closed the door. Maybe home is just where you stop explaining.",
    "He left. We all should listen more.",
    "Nobody moved. That's just how it is.",
])
def test_fazitsatz_positiv_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["fazitsatz"] >= 1, text


@pytest.mark.parametrize("text", [
    # Dieselben Worte MITTEN im Text: dort ist es kein Fazit.
    "Maybe home is just where you stop explaining. "
    "She opened the window. Rain came in. He said nothing. She waited.",
    # "Maybe" ohne den Fazit-Bau.
    "Maybe she is late again.",
    # Ein Satz ueber jemanden, der zuhoert -- keine Moral.
    "He listened to everyone in the room.",
])
def test_fazitsatz_negativ_englisch(text):
    assert sprachpass.rohzahlen(text, "en")["fazitsatz"] == 0, text


def test_der_fazitsatz_wird_nur_am_schluss_gezaehlt():
    """Das ist der ganze Unterschied zwischen einer Floskel und einer Moral:
    die Stelle. Gezaehlt wird in den letzten ``FAZIT_FENSTER_SAETZE`` Saetzen."""
    schluss = "Maybe home is just where you stop explaining."
    fuellung = " ".join(["She waited."] * 5)
    assert sprachpass.rohzahlen(fuellung + " " + schluss, "en")["fazitsatz"] == 1
    assert sprachpass.rohzahlen(schluss + " " + fuellung, "en")["fazitsatz"] == 0


@pytest.mark.parametrize("text, soll", [
    ("Sie ging. Vielleicht ist Heimat einfach da, wo man nichts erklaert.", 1),
    ("Er schwieg. Wir alle sollten mehr zuhoeren.", 1),
    ("Sie ging. Es regnete.", 0),
])
def test_fazitsatz_deutsch(text, soll):
    assert sprachpass.rohzahlen(text, "de")["fazitsatz"] == soll, text


# --- Die Zaehlung als Ganzes --------------------------------------------


def test_alle_namen_kommen_in_der_zaehlung_vor():
    zahlen = sprachpass.zaehle("Ein kurzer Text.", "de")
    assert set(zahlen) == set(sprachpass.NAMEN)


def test_ein_leerer_text_zaehlt_nichts():
    for text in ("", None):
        assert all(v == 0 for v in sprachpass.zaehle(text, "de").values())


def test_die_sprache_kommt_aus_dem_profil(monkeypatch):
    """``sprache.je_sprache`` waehlt die Musterliste; ``code`` ist nur der
    Ueberschreibweg fuer Tests und den Befund."""
    monkeypatch.setattr(sprachpass.sprache, "code", lambda: "en")
    assert sprachpass.rohzahlen("It was not a home but a room.")["nicht_sondern"] >= 1
