"""Szenenweg auf Englisch, Einwilligung inhaltlich gleich (E9)."""

import pytest

from interview_theater import repo, sprache, szene, workshop


@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")
    sprache.vergiss()
    yield
    sprache.vergiss()


@pytest.mark.parametrize("deutsch, englisch_", [
    ("Anthropic", "Anthropic"), ("USA", "USA"), ("Schweiz", "Switzerland"),
    ("Keine\nAufnahmen", "No recordings"), ("keine Namen aus diesem Chat", "no names from this chat"),
    ("ja oder nein", "yes or no"),
])
def test_einwilligung_traegt_dieselben_kernaussagen(englisch, deutsch, englisch_):
    assert " ".join(deutsch.split()) in " ".join(szene._TEXT_ANGEBOT_USA.split())
    assert englisch_ in " ".join(szene.T._TEXT_ANGEBOT_USA.split())


def test_warnung_vor_jeder_szene_auf_englisch(englisch):
    for kern in ("Anthropic", "USA", "no audio recordings", "no names from this chat", "Switzerland"):
        assert kern in " ".join(szene.T._TEXT_WARNUNG_USA.split())


def test_nein_bleibt_ein_nein(conn):
    """AGENTS.md-Fallstrick: setze_szene_usa nimmt bool."""
    repo.setze_szene_usa(conn, 1, False)
    assert repo.szene_usa_stand(conn, 1) == "nein"


def test_chatblock_des_szenenlaufs_englisch(englisch):
    assert szene.T._SPRECHER_GRUPPE == "Group"
    assert szene.T._SPRECHER_DU == "You"


def test_kurzgeschichte_liest_die_englische_pflichtzeile(englisch):
    """Die englische Anweisung verlangt ``ZUSAMMENFASSUNG:`` in Versalien
    (Protokoll-Token, K6); der Parser liest es ohne Ruecksicht auf Gross-
    und Kleinschreibung -- dasselbe Ergebnis wie mit ``Zusammenfassung:``."""
    from interview_theater import kurzgeschichte

    assert "ZUSAMMENFASSUNG:" in kurzgeschichte.T.ANWEISUNG
    englisch_ = kurzgeschichte.zerlege("1. Arrival\nZUSAMMENFASSUNG: They meet.\n\nText.")
    deutsch = kurzgeschichte.zerlege("1. Arrival\nZusammenfassung: They meet.\n\nText.")
    assert englisch_ == deutsch == [("Arrival", "They meet.", "Text.")]


def test_pruefvermerk_ueberlebt_den_profilwechsel(conn, monkeypatch):
    """Rundreise-Marker: ein deutscher Pruef-Vermerk wird unter einem
    englischen Profil gefunden und zurueckgenommen (dieselbe Regel wie
    ``leitfaden._schon_gezeigt``: deutsche Konstante UND aktuelles T)."""
    from interview_theater import szenenfolge

    repo.schreibe_journal(
        conn, 1, "offen", szenenfolge.PRUEFVERMERK.format(nummer=3, geaendert=1),
        quelle="knopf",
    )
    monkeypatch.setattr(sprache, "code", lambda: "en")
    sprache.vergiss()
    try:
        assert szenenfolge.zu_pruefen(conn, 1, 3)
        szenenfolge.nimm_pruefvermerk(conn, 1, 3)
        assert not szenenfolge.zu_pruefen(conn, 1, 3)
        repo.schreibe_journal(
            conn, 1, "offen", szenenfolge.T.PRUEFVERMERK.format(nummer=4, geaendert=1),
            quelle="knopf",
        )
        assert szenenfolge.T.PRUEFVERMERK.startswith("Scene ")
        assert szenenfolge.zu_pruefen(conn, 1, 4)
    finally:
        sprache.vergiss()


def test_synopsenkette_wird_in_beiden_sprachen_gelesen(englisch):
    from interview_theater.dramaturgie import fanout

    deutsch = "Szene 1: A\nSie streiten sich.\nSzene 2: B\n(noch nichts geschrieben)"
    englisch_ = "Scene 1: A\nThey argue.\nScene 2: B\n(nothing written yet)"
    assert fanout.synopsen_fehlen(deutsch) == [2]
    assert fanout.synopsen_fehlen(englisch_) == [2]


def test_befundsaetze_der_mechanik_englisch(englisch):
    from interview_theater.dramaturgie import mechanik

    satz = mechanik.T._TEXT_SPRECHANTEIL.format(name="A", anzahl=34, gesamt=5800)
    assert satz.startswith("A speaks 34 of 5800 words")
    assert mechanik._TEXT_SPRECHANTEIL.startswith("{name} spricht im ganzen Stueck")


def test_der_kernpaket_kopf_nennt_das_kernthema_nicht_mehr(monkeypatch):
    """Karte P2-Fix, Restspannung 2 (02.10.2026).

    ``szene._kernpaket_text`` liefert die Schaerfungen DIESER Szene und ihrer
    Figuren (``szene.py:999-1013``) und faellt ohne sie auf die globale
    Auswahl zurueck (``szene.py:1020-1033``) -- ein Kopf fuer beide Zweige.
    "Am Kernthema gefiltert" war fuer keinen von beiden wahr, und das
    Kernthema ist seit dem 06.09.2026 keine Station mehr (c8, derselbe Grund
    wie bei ``kontext.KERNPAKET_KOPF``).

    Geprueft werden BEIDE Sprachen: die deutsche Konstante selbst und der
    englische Eintrag ueber ``T`` unter dem Padua-Profil."""
    from interview_theater import szene, workshop

    assert "Kernthema" not in szene.KERNPAKET_KOPF
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    try:
        assert "core theme" not in szene.T.KERNPAKET_KOPF
        assert szene.T.KERNPAKET_KOPF != szene.KERNPAKET_KOPF, "englisch"
    finally:
        workshop.vergiss()
