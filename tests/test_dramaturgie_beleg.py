"""Schicht 2: die Belegverifikation -- scharf geprueft.

Die vier Faelle aus dem Auftrag: veraendertes Zitat, halluziniertes Zitat,
Zitat mit typografischen Anfuehrungszeichen, Zitat ueber einen Zeilenumbruch.
Dazu die Regel, an der alles haengt: **ein** Retry, danach ``unsicher`` und
Score verworfen.
"""

from interview_theater.dramaturgie import beleg

SZENE = """MIRA:(sieht nicht auf)Der Koffer steht seit gestern hier.
JONAS: Und niemand holt ihn ab,
weil niemand ihn vermisst.
MIRA: Lass den Koffer stehen.
"""


class Judge:
    """Eine Attrappe, die eine feste Folge von Antworten liefert und
    mitschreibt, mit welchem Hinweis sie gefragt wurde."""

    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.hinweise = []

    def __call__(self, hinweis):
        self.hinweise.append(hinweis)
        return self.antworten.pop(0) if self.antworten else {}


def _antwort(zitat_text, score=0):
    return {"score": score, "befund": "Die Szene dreht nichts.",
            "beleg": zitat_text, "schwere": "hoch",
            "vorschlag": "Szene 1: Lass Mira den Koffer oeffnen."}


# --- pruefe() -------------------------------------------------------------


def test_woertliches_zitat_besteht():
    assert beleg.pruefe("Der Koffer steht seit gestern hier.", SZENE)


def test_typografische_anfuehrungszeichen_stoeren_nicht():
    """``zitat.normalisiere`` zieht „ “ » « auf gerade Anfuehrungszeichen --
    ein Modell, das seine eigenen Zitate typografisch setzt, wird deshalb
    nicht faelschlich abgelehnt."""
    assert beleg.pruefe("„Lass den Koffer stehen.“", SZENE)
    assert beleg.pruefe("»Lass den Koffer stehen.«", SZENE)


def test_zitat_ueber_einen_zeilenumbruch_besteht():
    """Im Text steht der Satz ueber zwei Zeilen; das Modell zitiert ihn in
    einer. Whitespace-Folgen werden auf ein Leerzeichen normalisiert, also
    ist das dasselbe Zitat."""
    assert beleg.pruefe(
        "Und niemand holt ihn ab, weil niemand ihn vermisst.", SZENE
    )
    assert beleg.pruefe(
        "Und niemand holt ihn ab,\n   weil niemand ihn vermisst.", SZENE
    )


def test_veraendertes_zitat_faellt_durch():
    """Ein Wort ausgetauscht -- und es ist kein Beleg mehr. Genau das ist der
    Punkt: ein Judge, der das Zitat "sinngemaess" wiedergibt, hat es nicht
    gelesen."""
    assert not beleg.pruefe("Der Koffer steht seit heute hier.", SZENE)


def test_halluziniertes_zitat_faellt_durch():
    assert not beleg.pruefe("MIRA: Ich habe dich nie geliebt.", SZENE)


def test_zusammengeklebtes_zitat_faellt_durch():
    """Zwei echte Stellen, aneinandergehaengt -- im Text steht das so nicht."""
    assert not beleg.pruefe(
        "Der Koffer steht seit gestern hier. Lass den Koffer stehen.", SZENE
    )


def test_zu_kurzes_zitat_faellt_durch():
    """"Und" steht im Text und belegt nichts."""
    assert "Und" in SZENE
    assert not beleg.pruefe("Und", SZENE)
    assert not beleg.pruefe("Koffer", SZENE)


def test_leerer_beleg_faellt_durch():
    assert not beleg.pruefe(None, SZENE)
    assert not beleg.pruefe("   ", SZENE)


# --- hole_mit_beleg(): der eine Retry -------------------------------------


def test_treffer_im_ersten_anlauf_fragt_nicht_nach():
    judge = Judge(_antwort("Der Koffer steht seit gestern hier."))

    antwort, stand = beleg.hole_mit_beleg(judge, SZENE, "b1 Szene 1")

    assert judge.hinweise == [None]
    assert stand.geprueft and not stand.unsicher and stand.versuche == 1
    assert antwort["score"] == 0


def test_ein_retry_mit_dem_hinweis_und_dann_ist_schluss():
    judge = Judge(
        _antwort("MIRA: Das habe ich erfunden."),
        _antwort("Lass den Koffer stehen."),
    )

    antwort, stand = beleg.hole_mit_beleg(judge, SZENE)

    assert judge.hinweise == [None, beleg.HINWEIS]
    assert stand.geprueft and stand.versuche == 2
    assert antwort["score"] == 0


def test_nach_dem_retry_wird_der_score_verworfen():
    """Nicht abgewertet -- **verworfen**. Eine Note ohne Beleg ist keine
    schlechtere Note, sie ist keine."""
    judge = Judge(
        _antwort("MIRA: Erfunden."),
        _antwort("JONAS: Auch erfunden."),
    )

    antwort, stand = beleg.hole_mit_beleg(judge, SZENE)

    assert len(judge.hinweise) == 2      # genau ein Retry, kein dritter Versuch
    assert not stand.geprueft and stand.unsicher
    assert antwort["score"] is None
    assert antwort["unsicher"] is True
    assert stand.grund == beleg.GRUND_NICHT_GEFUNDEN


def test_fehlender_beleg_zaehlt_wie_ein_falscher():
    judge = Judge(_antwort(None), _antwort(None))

    _, stand = beleg.hole_mit_beleg(judge, SZENE)

    assert len(judge.hinweise) == 2
    assert stand.unsicher and stand.grund == beleg.GRUND_FEHLT


def test_der_hinweis_verraet_die_erwartete_antwort_nicht():
    """Er sagt, was falsch war, nicht was dastehen soll -- sonst schreibt das
    Modell den Hinweis ab."""
    assert "nicht woertlich vor" in beleg.HINWEIS
    assert "score" not in beleg.HINWEIS.lower()


# --- Die Faustregel aus Recherche § 4 -------------------------------------


def _befund(**anders):
    grund = {
        "beleg_geprueft": True, "unsicher": False, "szene": 3,
        "vorschlag": "Szene 3: Lass Mira den Koffer oeffnen.",
    }
    grund.update(anders)
    return grund


def test_ungeprueftes_zitat_geht_nicht_an_den_schreiber():
    assert not beleg.darf_an_den_schreiber(_befund(beleg_geprueft=False))


def test_unsicherer_befund_geht_nicht_an_den_schreiber():
    assert not beleg.darf_an_den_schreiber(_befund(unsicher=True))


def test_vorschlag_ohne_szene_geht_nicht_an_den_schreiber():
    assert not beleg.darf_an_den_schreiber(_befund(szene=None))
    assert not beleg.darf_an_den_schreiber(_befund(vorschlag=" "))


def test_mit_figurenliste_braucht_der_vorschlag_einen_namen():
    assert beleg.darf_an_den_schreiber(_befund(), ["Mira", "Jonas"])
    assert not beleg.darf_an_den_schreiber(
        _befund(vorschlag="Szene 3: mehr Spannung erzeugen."), ["Mira", "Jonas"]
    )


def test_vollstaendiger_befund_darf_durch():
    assert beleg.darf_an_den_schreiber(_befund())
