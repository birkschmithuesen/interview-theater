"""Tests fuer die mechanischen Masse aus ``scripts/sprachstil_masse.py``
(Padua M1, 30.09.2026).

Reine Funktionen, keine DB, kein Netz -- kleine erfundene Texte, jede
Funktion mindestens ein Fall. Die drei Grenzfaelle aus dem Plan bekommen
je einen eigenen Test: ein Zitat ohne zuordenbaren Namen, ein Mehrwortmarker
und eine Regieklammer, die aus einer Sprecherzeile verschwinden muss.
"""

from scripts import sprachstil_masse as m


# --- direkte_rede (Prosa) ---------------------------------------------------


NAMEN = {"Meryem", "Ferzan", "Aynur"}


def test_direkte_rede_name_nach_dem_zitat():
    text = '„Egal“, sagt Meryem. Sie dreht sich weg.'
    ergebnis = m.direkte_rede(text, NAMEN)

    assert ergebnis["Meryem"] == ["Egal"]


def test_direkte_rede_name_vor_dem_zitat():
    text = 'Ferzan sagt: „Ich komme spaeter nach.“'
    ergebnis = m.direkte_rede(text, NAMEN)

    assert ergebnis["Ferzan"] == ["Ich komme spaeter nach."]


def test_direkte_rede_naechster_name_gewinnt():
    text = 'Aynur steht auf. Ferzan schweigt. „Weiter“, sagt Ferzan.'
    ergebnis = m.direkte_rede(text, NAMEN)

    assert ergebnis["Ferzan"] == ["Weiter"]
    assert "Aynur" not in ergebnis


def test_direkte_rede_zitat_ohne_namen_wird_none():
    """Kein Name im selben Absatz -- die Rede bleibt unter dem Schluessel
    ``None`` stehen, statt still zu verschwinden."""
    text = '„Wer weiss das schon.“ Stille im Raum.'
    ergebnis = m.direkte_rede(text, NAMEN)

    assert ergebnis[None] == ["Wer weiss das schon."]


def test_direkte_rede_genitiv_name_wird_zugeordnet():
    """Ein Name in Genitivform ("Meryems") zaehlt noch als Namensfund --
    der Wortgrenzenvergleich darf das angehaengte "s" nicht ablehnen."""
    text = 'Meryems Stimme klingt hart. „Wir gehen jetzt.“'
    ergebnis = m.direkte_rede(text, NAMEN)

    assert ergebnis["Meryem"] == ["Wir gehen jetzt."]


def test_direkte_rede_gemischte_anfuehrungszeichen_werden_erfasst():
    """Ein oeffnendes „ darf mit “, ” oder dem ASCII " geschlossen werden --
    sonst faellt das Zitat aus allen vier Erfassungsbloecken heraus und
    verschwindet still, statt der Figur zugeordnet zu werden."""
    text = 'Meryem sagt: „Ich gehe jetzt." Sie dreht sich um.'
    ergebnis = m.direkte_rede(text, NAMEN)

    assert ergebnis["Meryem"] == ["Ich gehe jetzt."]


def test_direkte_rede_erkennt_alle_vier_anfuehrungsstile():
    text = (
        '„Eins“, sagt Meryem. '
        '"Zwei", sagt Ferzan. '
        '»Drei«, sagt Aynur. '
        '«Vier», sagt Meryem.'
    )
    ergebnis = m.direkte_rede(text, NAMEN)

    alle_reden = [r for reden in ergebnis.values() for r in reden]
    assert sorted(alle_reden) == ["Drei", "Eins", "Vier", "Zwei"]


# --- sprecherzeilen (Theatertext) -------------------------------------------


def test_sprecherzeilen_entfernt_regieklammer():
    text = "MERYEM:(dreht sich weg) Egal.\nFERZAN: Ich komme spaeter nach."
    ergebnis = m.sprecherzeilen(text, {"meryem", "ferzan"})

    assert ergebnis["MERYEM"] == ["Egal."]
    assert ergebnis["FERZAN"] == ["Ich komme spaeter nach."]


def test_sprecherzeilen_ohne_sprecher_liefert_leeres_dict():
    ergebnis = m.sprecherzeilen("Nur ein Erzaehltext ohne Doppelpunkt.", {"meryem"})

    assert ergebnis == {}


# --- saetze / mittlere_satzlaenge -------------------------------------------


def test_saetze_trennt_an_satzzeichen():
    ergebnis = m.saetze(["Egal. Weiter."])

    assert ergebnis == ["Egal.", "Weiter."]


def test_mittlere_satzlaenge_knappe_saetze():
    """Zwei Ein-Wort-Saetze -- die mittlere Satzlaenge ist 1."""
    ergebnis = m.mittlere_satzlaenge(["Egal. Weiter."])

    assert ergebnis == 1.0


def test_mittlere_satzlaenge_ohne_reden_ist_null():
    assert m.mittlere_satzlaenge([]) == 0.0


def test_mittlere_satzlaenge_laengerer_satz():
    ergebnis = m.mittlere_satzlaenge(["Das ist ein Satz mit sieben Woertern hier."])

    assert ergebnis == 8.0


# --- wortschatz / jaccard ---------------------------------------------------


def test_wortschatz_ist_kleingeschrieben_ohne_satzzeichen():
    ergebnis = m.wortschatz(["Egal. Weiter, dann."])

    assert ergebnis == {"egal", "weiter", "dann"}


def test_jaccard_identische_mengen_ist_eins():
    assert m.jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjunkte_mengen_ist_null():
    assert m.jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_teilweise_ueberschneidung():
    ergebnis = m.jaccard({"a", "b", "c"}, {"b", "c", "d"})

    assert ergebnis == 2 / 4


def test_jaccard_zwei_leere_mengen_ist_null():
    assert m.jaccard(set(), set()) == 0.0


# --- marker_anteil -----------------------------------------------------------


def test_marker_anteil_einfacher_treffer():
    reden = ["Das ist halt so."]
    ergebnis = m.marker_anteil(reden, ["halt"])

    # 1 Treffer auf 4 Woerter -> 25 je 100 Woerter.
    assert ergebnis == 25.0


def test_marker_anteil_mehrwortmarker():
    """"weisst du" ist ein Marker aus zwei Woertern -- er zaehlt als EIN
    Treffer, nicht als zwei einzelne Wortfunde."""
    reden = ["Das ist, weisst du, gar nicht so einfach."]
    ergebnis = m.marker_anteil(reden, ["weisst du"])

    woerter = len(reden[0].split())
    assert ergebnis == 100 / woerter


def test_marker_anteil_case_insensitiv_und_wortgrenzen():
    """"Also" (Satzanfang) und "ALSO" (Grossschreibung) zaehlen, das
    zusammengesetzte "Alsobald" nicht -- da endet das Wort nicht an der
    Wortgrenze, die der Marker "also" braucht."""
    reden = ["Also gut. Alsobald reicht das nicht. ALSO gut."]
    ergebnis = m.marker_anteil(reden, ["also"])

    woerter = len(reden[0].split())
    assert ergebnis == 100 * 2 / woerter


def test_marker_anteil_ohne_woerter_ist_null():
    assert m.marker_anteil([], ["halt"]) == 0.0


# --- MARKER ------------------------------------------------------------------


def test_marker_hat_die_drei_stile():
    assert set(m.MARKER) == {"KNAPP", "SCHACHTEL", "FUELL"}
    for liste in m.MARKER.values():
        assert liste


def test_marker_schachtel_enthaelt_die_genannten_woerter():
    for wort in ("wobei", "insofern", "gewissermassen", "prinzipiell"):
        assert wort in [w.lower() for w in m.MARKER["SCHACHTEL"]]


def test_marker_fuell_enthaelt_die_genannten_woerter():
    for wort in ("halt", "irgendwie", "sozusagen", "also"):
        assert wort in [w.lower() for w in m.MARKER["FUELL"]]
