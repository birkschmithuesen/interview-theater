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
