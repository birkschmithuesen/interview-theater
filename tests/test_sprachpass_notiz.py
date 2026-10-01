"""Grenzwerte, Notiz und Zitatschutz (30.09.2026, Karte R).

Der Zitatschutz ist die wichtigste einzelne Massnahme dieses Pfades: ein
Ueberarbeitungslauf, der einen woertlichen Interviewsatz glattzieht, nimmt der
Gruppe genau das, was sie selbst gesammelt hat (theater-tells Nr. 21, 25, 28).
Geprueft wird mit ``zitat.pruefe`` -- der EINEN Normalisierung des Repos, ohne
eine zweite daneben.
"""

import pytest

from interview_theater import repo, sprachpass, workshop, zitat


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Grenzwerte und Ueberschreitungen ------------------------------------


def test_die_grenzwerte_kommen_aus_dem_profil(padua):
    grenzen = sprachpass.grenzwerte()
    assert set(grenzen) == set(sprachpass.NAMEN)
    assert grenzen["gedankenstriche"] == 6.0
    assert grenzen["fazitsatz"] == 1


def test_unter_der_grenze_gibt_es_nichts_zu_tun():
    zahlen = {"gedankenstriche": 5.9, "nicht_sondern": 1.0,
              "adjektiv_dreier": 0.0, "fazitsatz": 0}
    grenzen = {"gedankenstriche": 6.0, "nicht_sondern": 2.0,
               "adjektiv_dreier": 2.0, "fazitsatz": 1}
    assert sprachpass.ueberschreitungen(zahlen, grenzen) == []


def test_ab_der_grenze_wird_gemeldet():
    grenzen = {"gedankenstriche": 6.0, "nicht_sondern": 2.0,
               "adjektiv_dreier": 2.0, "fazitsatz": 1}
    zahlen = {"gedankenstriche": 6.0, "nicht_sondern": 0.0,
              "adjektiv_dreier": 0.0, "fazitsatz": 1}
    assert sprachpass.ueberschreitungen(zahlen, grenzen) == [
        "gedankenstriche", "fazitsatz"]


def test_die_reihenfolge_ist_die_von_NAMEN():
    """Eine Notiz mit wechselnder Reihenfolge waere zwei Notizen fuer
    denselben Befund -- und im Prompt zwei verschiedene Auftraege."""
    # Abweichung vom Plan: Grenzwert 1 statt 0 -- ein Grenzwert 0 schaltet
    # den Zaehler AB (sonst meldete er jeden Text und kostete je Szene einen
    # Lauf), siehe ``test_ein_grenzwert_null_schaltet_den_zaehler_ab``.
    grenzen = {n: 1 for n in sprachpass.NAMEN}
    zahlen = {n: 1 for n in sprachpass.NAMEN}
    assert sprachpass.ueberschreitungen(zahlen, grenzen) == list(sprachpass.NAMEN)


def test_ein_grenzwert_null_schaltet_den_zaehler_ab():
    grenzen = {n: 0 for n in sprachpass.NAMEN}
    zahlen = {n: 5 for n in sprachpass.NAMEN}
    assert sprachpass.ueberschreitungen(zahlen, grenzen) == []


# --- Die Notiz -----------------------------------------------------------


def test_ohne_ueberschreitung_gibt_es_keine_notiz():
    assert sprachpass.notiz([]) == ""


def test_die_notiz_nennt_jedes_muster_einmal():
    text = sprachpass.notiz(["gedankenstriche", "fazitsatz"])
    assert sprachpass.NOTIZ_KOPF in text
    assert sprachpass.NOTIZ["gedankenstriche"] in text
    assert sprachpass.NOTIZ["fazitsatz"] in text
    assert sprachpass.NOTIZ["nicht_sondern"] not in text


def test_die_notiz_verbietet_das_umschreiben_von_zitaten():
    """Der Auftrag muss es SAGEN und der Code muss es PRUEFEN. Beides -- der
    Satz allein ist eine Bitte, die Pruefung allein eine Ueberraschung."""
    text = sprachpass.notiz(["gedankenstriche"])
    assert sprachpass.NOTIZ_ZITATE in text


def test_die_notiz_ist_eine_regie_notiz_und_kein_neuschrieb():
    """Derselbe Weg wie "Passt, aber anders": derselbe Text, ueberarbeitet.
    Ein Wort wie "neu" darin wuerde einen Neuschrieb ausloesen."""
    text = sprachpass.notiz(list(sprachpass.NAMEN))
    for verboten in ("Schreib eine andere", "ganz neu", "[NEU]"):
        assert verboten not in text


def test_die_texte_laufen_ueber_T():
    assert sprachpass.T.NOTIZ_KOPF == sprachpass.NOTIZ_KOPF
    assert sprachpass.T.NOTIZ["fazitsatz"] == sprachpass.NOTIZ["fazitsatz"]


# --- Die geprueften Zitate -----------------------------------------------


@pytest.fixture
def mit_zitaten(conn):
    """Ein geprueftes Verdichtungsthema und zwei Sprachprofil-Zitate.

    Abweichung vom Plan (der die Signaturen aus der Erinnerung schrieb):
    ``lege_aufnahme_an(conn, chat_id, message_id, klasse, quelle)`` wie in
    ``tests/test_kontext.py``, und die Figurenzitate kommen ueber
    ``repo.setze_sprachprofil`` -- ``setze_figur_feld`` kennt nur Name und
    Beschreibung. Dort werden sie mit ``repo.ZITAT_TRENNER`` verbunden."""
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 500, "lang", "sprache")
    repo.setze_transkript(conn, aufnahme_id,
                          "also ich, ja, ich weiss nicht, das war halt so")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Sie erzaehlt vom Warten.",
        [{"thema": "Warten", "kurz": "Warten",
          "beleg_zitat": "das war halt so", "zitat_geprueft": 1},
         {"thema": "Erfunden", "kurz": "Erfunden",
          "beleg_zitat": "nie gesagt", "zitat_geprueft": 0}],
    )
    repo.setze_figur(conn, 1, "Mira", "wartet")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    repo.setze_sprachprofil(conn, figur_id, "kurze Saetze",
                            ["Seit drei Jahren und vier Monaten.", "Weiss nicht."])
    return conn


def test_figurenzitate_werden_am_zitat_trenner_getrennt(mit_zitaten):
    """``figur.zitate`` ist EIN Feld mit ``repo.ZITAT_TRENNER`` dazwischen.
    Als ein Zitat gelesen stuende es nie woertlich in einer Szene -- der
    Schutz griffe ins Leere."""
    zitate = sprachpass.gepruefte_zitate(mit_zitaten, 1)
    assert "Weiss nicht." in zitate
    assert not any(repo.ZITAT_TRENNER in z for z in zitate)
    assert "nie gesagt" not in zitate          # zitat_geprueft = 0


def test_die_zitate_kommen_aus_beiden_quellen(mit_zitaten):
    zitate = sprachpass.gepruefte_zitate(mit_zitaten, 1)
    assert "das war halt so" in zitate
    assert "Seit drei Jahren und vier Monaten." in zitate


def test_ungepruefte_zitate_zaehlen_nicht(conn):
    """``repo.gepruefte_themen`` filtert ``zitat_geprueft = 1``. Ein
    unbelegtes Zitat zu schuetzen hiesse, eine Erfindung festzuschreiben."""
    assert sprachpass.gepruefte_zitate(conn, 1) == []


def test_enthaltene_findet_nur_was_dasteht():
    text = "MIRA: das war halt so. / PAL: Und dann?"
    assert sprachpass.enthaltene(text, ["das war halt so", "nie gesagt"]) == \
        ["das war halt so"]


def test_enthaltene_normalisiert_wie_zitat_pruefe():
    """Keine zweite Normalisierung: Zeilenumbrueche und typografische
    Anfuehrungszeichen behandelt ``zitat.pruefe``, und nur es."""
    text = "MIRA: das war\n   halt so."
    assert sprachpass.enthaltene(text, ["das war halt so"]) == ["das war halt so"]
    assert zitat.pruefe("das war halt so", text) is True


def test_verlorene_meldet_nur_was_vorher_dastand():
    alt = "MIRA: das war halt so."
    neu = "MIRA: So war das eben."
    assert sprachpass.verlorene(alt, neu, ["das war halt so"]) == ["das war halt so"]
    # Was vorher schon nicht dastand, kann nicht verlorengehen.
    assert sprachpass.verlorene(alt, neu, ["nie gesagt"]) == []


def test_ein_unveraendertes_zitat_faellt_nicht_auf():
    alt = "MIRA: das war halt so. Und dann ging sie."
    neu = "MIRA: das war halt so.\n(Sie geht.)"
    assert sprachpass.verlorene(alt, neu, ["das war halt so"]) == []


def test_ein_veraendertes_zitat_faellt_auf():
    """Der Kern: ein glattgezogener Interviewsatz ist ein verlorenes Zitat.
    Aus "also ich, ja, ich weiss nicht" wird "Es war eine schwierige Zeit" --
    theater-tells Nr. 21."""
    alt = "MIRA: also ich, ja, ich weiss nicht, das war halt so."
    neu = "MIRA: Es war eine schwierige Zeit fuer mich."
    assert sprachpass.verlorene(
        alt, neu, ["also ich, ja, ich weiss nicht"]) == \
        ["also ich, ja, ich weiss nicht"]


def test_die_vorgabe_im_modul_und_im_profil_sagen_dasselbe():
    """Zwei Orte fuer eine Zahl sind erlaubt, solange ein Test sie
    aneinanderhaelt -- der Leser des Moduls soll die Zahl sehen, ohne die
    TOML zu oeffnen."""
    for name, wert in sprachpass.GRENZEN_VORGABE.items():
        schluessel = sprachpass.SCHLUESSEL[name]
        assert workshop.VORGABE.wert(f"sprachpass.{schluessel}") == wert, name
