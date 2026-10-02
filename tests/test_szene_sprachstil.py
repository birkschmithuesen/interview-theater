"""Der in Phase 4 gewaehlte Sprachstil steht auch im Einzelszenen-Prompt
(Padua M1-Fix, 02.10.2026).

Vorher las ``szene._figuren_text`` nur ``beschreibung``, ``sprachprofil`` und
``zitate``; System- und Nutzertext waren mit und ohne Stil byte-identisch
(gemessen in ``docs/sprachstil-wirkung-2026-09-30.md``, Weg 2). Kein Netz,
kein Modell: geprueft wird der Prompt-Bau.
"""

import pytest

from interview_theater import repo, sprache, szene

#: Das Format, das ``knoepfe.wirkung._wirkung_figur_stil`` wirklich
#: speichert: "<Titel>: <Beispielsatz>".
STIL = "Kurz und abgehackt: Egal. Koffer bleibt zu. Weiter."
STIL_ZWEI = "Mit Fuellwoertern: Also, weisst du, der ist halt irgendwie."

#: Die Beschriftung ohne ihren Wert -- sprachunabhaengig aus der Konstante
#: abgeleitet, damit "steht keine Stilzeile da" ohne Literal pruefbar ist.
def _schild(konstante: str) -> str:
    return konstante.split("{stil}")[0]


def _figur(conn, name="Maria", beschreibung="Naeherin, kam 1998",
           profil="Kurze Saetze, bricht ab.", zitate=()):
    """Legt eine Figur an und liefert ihre id. ``zitate=()`` heisst: keine --
    dann bleibt ``mit_zitat`` falsch."""
    repo.setze_figur(conn, 1, name, beschreibung)
    figur_id = repo.hole_figur(conn, 1, name)["id"]
    repo.setze_sprachprofil(conn, figur_id, profil, list(zitate))
    return figur_id


def test_sprachstil_steht_im_szenen_prompt(conn, einst):
    """Der Kern des Fixes: der gewaehlte Stil kommt im Prompt an."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text


def test_sprachprofil_und_sprachstil_stehen_nebeneinander(conn, einst):
    """Beides, nicht eins statt des anderen: das Profil ist das Messergebnis
    aus einem Interview, der Stil die Wahl der Gruppe."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert "Kurze Saetze, bricht ab." in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text
    assert '"Ich hatte nur einen Koffer."' in text


def test_sprachstil_steht_nie_in_anfuehrungszeichen(conn, einst):
    """Ein Stil ist kein Belegzitat (Audit-Befund S4). Stuende er wie ein
    Zitat da, wuerde das Modell ihn als woertliche Interviewstelle lesen --
    und ``_figuren_mit_wenig_zitaten`` wuerde ihn als Zitat wegkuerzen."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert f'"{STIL}"' not in text
    assert f'  "{STIL}' not in text


def test_jede_figur_bekommt_ihren_eigenen_stil(conn, einst):
    eine = _figur(conn, "Maria", zitate=["Ich hatte nur einen Koffer."])
    andere = _figur(conn, "Elif", beschreibung="Nachbarin",
                    profil="Lange Saetze.", zitate=["Ich bin geblieben."])
    repo.setze_figur_sprachstil(conn, eine, STIL)
    repo.setze_figur_sprachstil(conn, andere, STIL_ZWEI)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL_ZWEI) in text


def test_leerer_sprachstil_erzeugt_keine_zeile(conn, einst):
    """Datengetrieben wie der ganze Prompt: ein Feld mit Leerzeichen ist
    kein Wert, und eine leere Beschriftung waere eine Einladung, etwas zu
    erfinden."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, "   ")

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert _schild(szene.ZEILE_SPRACHSTIL) not in text


def test_ohne_sprachstil_bleibt_der_prompt_wie_vorher(conn, einst):
    """Die Rueckwaertskompatibilitaet in einem Test: eine Gruppe, die nie
    einen Stil gewaehlt hat, bekommt keinen Zeichen mehr."""
    _figur(conn, zitate=["Ich hatte nur einen Koffer."])

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert _schild(szene.ZEILE_SPRACHSTIL) not in text
    assert szene.FIGUREN_KOPF in text


# ---------------------------------------------------------------------------
# Die Drei-Kopf-Regel: der Kopf verspricht nur, was darunter steht
# ---------------------------------------------------------------------------


def test_stil_allein_setzt_nicht_den_woertlich_kopf(conn, einst):
    """Audit-Befund S4, in die neue Lage uebertragen: nur **echte Zitate**
    rechtfertigen "aus ihrem Interview, woertlich". Ein Stil ist die Wahl der
    Gruppe -- stuende der woertlich-Kopf darueber, erfaende das Modell die
    Interviewstellen dazu, die es nicht sieht."""
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF not in text
    assert szene.FIGUREN_KOPF_MIT_STIL in text


def test_kopf_mit_stil_behauptet_nicht_mehr_fehlenden_beleg(conn, einst):
    """Widerspruch c9 aus ``docs/prompt-audit/2026-09-30-padua/BEFUND.md``:
    "Sprechweise ist noch nicht aus Interviews belegt" stand im Prompt,
    obwohl jede Figur einen von der Gruppe gewaehlten Stil hatte."""
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF_OHNE_STIMME not in text
    assert "noch nicht aus Interviews belegt" not in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text


def test_ein_zitat_schlaegt_den_stil_beim_kopf(conn, einst):
    """Reihenfolge der drei Koepfe: Zitat vor Stil. Wer ein Zitat hat, hat
    die staerkste Vorlage -- und der Stil steht trotzdem darunter."""
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF in text
    assert szene.FIGUREN_KOPF_MIT_STIL not in text
    assert szene.ZEILE_SPRACHSTIL.format(stil=STIL) in text


def test_ohne_stil_und_ohne_zitat_bleibt_der_alte_kopf_zeichengleich(conn, einst):
    """Die dritte Lage ist unveraendert -- und sie muss es sein, sonst
    aenderte sich der Prompt einer Gruppe, die nie einen Stil gewaehlt hat."""
    _figur(conn, zitate=())

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF_OHNE_STIMME in text
    assert szene.FIGUREN_KOPF_MIT_STIL not in text
    assert szene.FIGUREN_KOPF not in text


def test_ein_stil_unter_mehreren_figuren_reicht_fuer_den_kopf(conn, einst):
    """Der Kopf gilt fuer den ganzen Block: eine Figur mit Stil genuegt, und
    der Kopf sagt deshalb ausdruecklich, was fuer die uebrigen gilt."""
    mit = _figur(conn, "Maria", zitate=())
    _figur(conn, "Elif", beschreibung="Nachbarin", profil="Lange Saetze.",
           zitate=())
    repo.setze_figur_sprachstil(conn, mit, STIL)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF_MIT_STIL in text
    assert szene.FIGUREN_KOPF_OHNE_STIMME not in text


# ---------------------------------------------------------------------------
# Englisch (Padua): dieselbe Regel, die Woerter aus der Sprachschicht
# ---------------------------------------------------------------------------


@pytest.fixture
def englisch(monkeypatch):
    """Dasselbe Muster wie ``tests/test_szene_sprache.py``: nicht das Profil
    umschalten, sondern die eine Funktion, die die Sprache liefert -- der
    Cache wird davor und danach vergessen."""
    monkeypatch.setattr(sprache, "code", lambda: "en")
    sprache.vergiss()
    yield
    sprache.vergiss()


def test_englische_stilzeile_steht_im_prompt(conn, einst, englisch):
    figur_id = _figur(conn, zitate=["Ich hatte nur einen Koffer."])
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.ZEILE_SPRACHSTIL.format(stil=STIL) in text
    assert "Speech style (chosen by the group)" in text
    assert _schild(szene.ZEILE_SPRACHSTIL) not in text


def test_englischer_kopf_mit_stil_statt_woertlich(conn, einst, englisch):
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.FIGUREN_KOPF_MIT_STIL in text
    assert szene.T.FIGUREN_KOPF not in text


def test_englischer_kopf_sagt_nicht_mehr_unbelegt(conn, einst, englisch):
    """Widerspruch c9 am englischen Wortlaut (``texte.toml``, heute Zeile
    934): "Their way of speaking isn't backed by interviews yet"."""
    figur_id = _figur(conn, zitate=())
    repo.setze_figur_sprachstil(conn, figur_id, STIL)

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.FIGUREN_KOPF_OHNE_STIMME not in text
    assert "isn't backed by interviews yet" not in text


def test_englisch_ohne_stil_und_ohne_zitat_bleibt_der_alte_kopf(conn, einst, englisch):
    _figur(conn, zitate=())

    text = szene.baue_nutzertext(conn, 1, "Scene 1")

    assert szene.T.FIGUREN_KOPF_OHNE_STIMME in text
    assert szene.T.FIGUREN_KOPF_MIT_STIL not in text


def test_beide_fassungen_tragen_denselben_platzhalter():
    """Die Zusicherung aus ``tests/test_sprache_texte.py``, hier noch einmal
    als lesbarer Satz: wer den deutschen Wortlaut aendert und den englischen
    vergisst, merkt es an beiden Stellen."""
    assert "{stil}" in szene.ZEILE_SPRACHSTIL
    assert sprache.platzhalter(szene.ZEILE_SPRACHSTIL) == sprache.platzhalter(
        sprache.tabelle("en")["szene"]["ZEILE_SPRACHSTIL"])
    assert sprache.platzhalter(szene.FIGUREN_KOPF_MIT_STIL) == sprache.platzhalter(
        sprache.tabelle("en")["szene"]["FIGUREN_KOPF_MIT_STIL"])
