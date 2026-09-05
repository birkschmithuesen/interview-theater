"""Journal, Kontextaufbau und Zitatabfragen -- die zwei Hintergrundwege und
die eine Nutzerfrage, die entscheiden, **was der Bot weiss** (N4).

Ohne Netz. Der Kontext-Umriss (``kontext.umriss``) und die Journallage sind
reine Buchhaltung ueber Daten, die schon dastehen; ``erfundene_zitate``
vergleicht mit derselben Normalisierung, mit der im Betrieb ueber ein
Belegzitat entschieden wird.
"""

import pytest

from interview_theater import kontext, repo
from simulation import kennzahlen, richter, skript
from simulation.kennzahlen import Beitrag, Zug


# --- Kontextaufbau (N4b) --------------------------------------------------


def _ausloeser(conn, chat_id=1):
    repo.merke_nachricht(conn, chat_id, 10, "Dilan", 0, "text", "hallo",
                         repo._jetzt())
    return repo.unbeantwortete(conn, chat_id)


def test_baue_ohne_protokoll_verhaelt_sich_unveraendert(conn, einst):
    """Das Argument ist rein additiv: der Betrieb setzt es nie, und der Bot
    darf davon nichts merken."""
    ohne = kontext.baue(conn, 1, _ausloeser(conn), einst)
    mit = kontext.baue(conn, 1, repo.unbeantwortete(conn, 1), einst, protokoll=[])
    assert ohne == mit


def test_das_protokoll_nennt_jeden_block_auch_die_leeren(conn, einst):
    """Ein leerer Block ist die interessantere Zeile als ein voller: dass die
    Verdichtungen fehlten, ist der Befund."""
    protokoll = []
    kontext.baue(conn, 1, _ausloeser(conn), einst, protokoll=protokoll)
    assert len(protokoll) == 1
    umriss = protokoll[0]
    assert set(umriss["bloecke"]) == set(kontext._REIHENFOLGE)
    assert umriss["bloecke"]["verdichtungen"] == 0
    assert umriss["bloecke"]["ausloeser"] > 0
    assert umriss["gesamt"] > 0
    assert umriss["gekuerzt"] is False


def test_das_protokoll_vermerkt_eine_kuerzung(conn, einst, monkeypatch):
    monkeypatch.setattr(kontext, "ZIEL", 1)
    protokoll = []
    kontext.baue(conn, 1, _ausloeser(conn), einst, protokoll=protokoll)
    assert protokoll[0]["gekuerzt"] is True


def test_kontextlage_fasst_die_umrisse_zusammen():
    zuege = [
        Zug(schritt="a", kontext=[
            {"bloecke": {"verdichtungen": 0, "fenster": 100}, "gesamt": 100,
             "gekuerzt": False},
        ]),
        Zug(schritt="b", kontext=[
            {"bloecke": {"verdichtungen": 40, "fenster": 900}, "gesamt": 940,
             "gekuerzt": True},
        ]),
    ]
    lage = kennzahlen.kontextlage(zuege)
    assert lage["kontext_zuege"] == 2
    assert lage["kontext_gekuerzt"] == 1
    assert lage["kontext_bloecke"]["verdichtungen"]["leer"] == 1
    assert lage["kontext_bloecke"]["fenster"]["max"] == 900
    assert lage["kontext_gesamt_median"] == 520


def test_kontextlage_ohne_umrisse_liefert_nullen():
    assert kennzahlen.kontextlage([])["kontext_zuege"] == 0


def test_zuege_ueber_dem_ziel_werden_gezaehlt():
    zuege = [Zug(schritt="a", kontext=[
        {"bloecke": {}, "gesamt": kontext.ZIEL + 1, "gekuerzt": False},
        {"bloecke": {}, "gesamt": 10, "gekuerzt": False},
    ])]
    assert kennzahlen.kontextlage(zuege)["kontext_ueber_ziel"] == 1


def test_die_datenlage_haelt_den_augenblick_fest(conn):
    """Gegen den Endstand geprueft saehe der dritte Zug immer aus wie der
    letzte -- und die Frage, ob dem Bot damals etwas gefehlt hat, waere nicht
    zu beantworten."""
    leer = kennzahlen.datenlage(conn, 1)
    assert leer["verdichtungen"] == 0
    assert leer["arbeitsstand"] == []

    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    repo.setze_figur(conn, 1, "Meryem", "die Aeltere")
    voll = kennzahlen.datenlage(conn, 1)
    assert voll["figuren"] == 1
    assert "begriffe" in voll["arbeitsstand"]
    assert "Verdichtungen: 0" in kennzahlen.datenlage_text(voll)


def test_umriss_text_nennt_leere_bloecke_ausdruecklich():
    text = richter.umriss_text(
        {"bloecke": {"verdichtungen": 0, "fenster": 300}, "gesamt": 300,
         "gekuerzt": True}
    )
    assert "verdichtungen: 0 Token (leer)" in text
    assert "gekuerzt" in text


# --- Journal (N4a) --------------------------------------------------------


def test_journallage_zaehlt_je_art_und_quelle(conn):
    repo.schreibe_journal(conn, 1, "entschieden", "Kernthema: Ankommen",
                          quelle="erkenner")
    repo.schreibe_journal(conn, 1, "vorgeschlagen", "Eine Szene am Bahnhof",
                          quelle="extraktor")
    lage = kennzahlen.journallage(conn, 1)
    assert lage["journal_eintraege"] == 2
    assert lage["journal_je_art"] == {"entschieden": 1, "vorgeschlagen": 1}
    assert lage["journal_ausgeloest"] is True
    assert lage["journal_vorgeschlagen"] == ["Eine Szene am Bahnhof"]


def test_ohne_extraktoreintrag_gilt_das_journal_als_nicht_ausgeloest(conn):
    """Eine Null waere die Behauptung, der Extraktor habe nichts gefunden --
    er ist gar nicht gefragt worden (er laeuft nur bei Verdraengung)."""
    repo.schreibe_journal(conn, 1, "entschieden", "Phase 3", quelle="erkenner")
    assert kennzahlen.journallage(conn, 1)["journal_ausgeloest"] is False


def test_doppeleintraege_werden_gefunden(conn):
    repo.schreibe_journal(conn, 1, "vorgeschlagen",
                          "Szene am Bahnhof mit Koffer und Warten", quelle="extraktor")
    repo.schreibe_journal(conn, 1, "vorgeschlagen",
                          "Bahnhof Koffer Warten Szene", quelle="extraktor")
    dubletten = kennzahlen.journallage(conn, 1)["journal_dubletten"]
    assert len(dubletten) == 1


def test_verschiedene_eintraege_sind_keine_dublette(conn):
    repo.schreibe_journal(conn, 1, "vorgeschlagen", "Szene am Bahnhof mit Koffer",
                          quelle="extraktor")
    repo.schreibe_journal(conn, 1, "vorgeschlagen",
                          "Figur Meryem soll Hausmeisterin werden", quelle="extraktor")
    assert kennzahlen.journallage(conn, 1)["journal_dubletten"] == []


def test_ohne_eintraege_urteilt_der_richter_gar_nicht():
    """Kein Aufruf, kein Urteil -- und der Bericht schreibt 'nicht
    ausgeloest' statt einer Null."""
    class Sim:
        def json_objekt(self, *a, **k):
            raise AssertionError("darf nicht gefragt werden")

    urteil = richter.bewerte_journal(Sim(), "Chat", [])
    assert urteil["journal_wiedergefunden"] == []
    assert urteil["journal_fehler"] is None


def test_das_journalurteil_liest_die_drei_listen():
    class Sim:
        def json_objekt(self, system, nutzer, art="sim", max_tokens=None):
            assert "Das Journal:" in nutzer
            return {"wiedergefunden": ["A"], "nicht_wiedergefunden": [" B "],
                    "fehlt_im_journal": ["C", ""], "satz": " geht so "}

    urteil = richter.bewerte_journal(Sim(), "Chat", ["A", "B"])
    assert urteil["journal_wiedergefunden"] == ["A"]
    assert urteil["journal_nicht_wiedergefunden"] == ["B"]
    assert urteil["journal_fehlt"] == ["C"]
    assert urteil["journal_satz"] == "geht so"


# --- Zitatabfragen (N4c) --------------------------------------------------


def test_der_schritt_stellt_drei_verschieden_schwere_fragen():
    schritt = skript.schritt_fuer("zitate")
    assert schritt.art == "zitate"
    assert len(skript.ZITAT_ZIELE) == 3
    assert schritt.max_nachrichten == 3


TRANSKRIPT = (
    "Leyla: Was hattest du dabei?\n\n"
    "Meryem: Ein Koffer und eine Tuete mit Brot. Mehr nicht."
)


def _abfrage_zug(*bot_texte) -> Zug:
    return Zug(schritt="zitate", marke="zitatabfrage", bot=list(bot_texte))


def test_ein_echtes_zitat_zaehlt_nicht_als_erfunden():
    zug = _abfrage_zug('Sie sagt: "Ein Koffer und eine Tuete mit Brot."')
    assert kennzahlen.erfundene_zitate([zug], [TRANSKRIPT]) == []


def test_ein_erfundenes_zitat_wird_gefunden():
    zug = _abfrage_zug('Sie sagt: "Ein Koffer und ein Kopfkissen aus Wolle."')
    treffer = kennzahlen.erfundene_zitate([zug], [TRANSKRIPT])
    assert treffer == ["Ein Koffer und ein Kopfkissen aus Wolle."]


def test_kurze_anfuehrungen_zaehlen_nicht():
    """"fertig" oder "Kueche" in Anfuehrungszeichen ist eine Erwaehnung, keine
    Behauptung ueber das Transkript."""
    zug = _abfrage_zug('Sagt einfach "fertig", dann hoere ich auf.')
    assert kennzahlen.erfundene_zitate([zug], [TRANSKRIPT]) == []


def test_ausserhalb_der_abfragen_wird_nicht_gezaehlt():
    """Der Bot setzt auch eigene Vorschlaege in Anfuehrungszeichen -- ueber
    den ganzen Lauf gemessen waere die Zahl unbrauchbar."""
    zug = Zug(schritt="kernthema", marke="",
              bot=['Waere "Das Warten zwischen zwei Laendern" ein Kernthema fuer euch?'])
    assert kennzahlen.erfundene_zitate([zug], [TRANSKRIPT]) == []


def test_typografische_anfuehrungszeichen_werden_erkannt():
    zug = _abfrage_zug('Sie sagt: „Ein Koffer und ein Kopfkissen aus Wolle."')
    assert len(kennzahlen.erfundene_zitate([zug], [TRANSKRIPT])) == 1


# --- Latenz und Optionenlisten (N5.1, N5.2) -------------------------------


def test_latenzen_werden_nach_art_getrennt():
    zuege = [
        Zug(schritt="a", art="gespraech", latenz_s=2.0),
        Zug(schritt="a", art="gespraech", latenz_s=4.0),
        Zug(schritt="a", art="gespraech", latenz_s=20.0),
        Zug(schritt="b", art="szene", latenz_s=140.0),
        Zug(schritt="c", art="gespraech", latenz_s=None),
    ]
    lage = kennzahlen.latenzen(zuege)
    assert lage["gespraech"]["n"] == 3
    assert lage["gespraech"]["median"] == 4.0
    assert lage["gespraech"]["p90"] == 20.0
    assert lage["szene"]["median"] == 140.0
    assert lage["verdichtung"]["n"] == 0


def test_eine_optionenliste_am_ende_wird_gezaehlt():
    zug = Zug(schritt="a", bot=[
        "Ihr koenntet:\n- am Bahnhof\n- in der Kueche\n- im Zentrum",
        "Waere der Bahnhof was fuer euch?",
    ])
    assert len(kennzahlen.optionenlisten([zug])) == 1


def test_eine_aufzaehlung_mitten_im_text_ist_keine_optionenliste():
    """Eine Aufstellung ('das habt ihr bisher') ist keine Rueckgabe der
    Entscheidung an die Gruppe."""
    zug = Zug(schritt="a", bot=[
        "Bisher habt ihr:\n- Koffer\n- Bahnhof\n- Winter\n\nSoll ich weitermachen?"
    ])
    assert kennzahlen.optionenlisten([zug]) == []


def test_zwei_punkte_reichen_nicht():
    zug = Zug(schritt="a", bot=["Zwei Wege:\n- Bahnhof\n- Kueche"])
    assert kennzahlen.optionenlisten([zug]) == []


def test_perzentil_nimmt_den_naechsten_rang():
    """Nicht interpoliert: bei acht gemessenen Zuegen ist Interpolation eine
    Genauigkeit, die es nicht gibt. Der naechste Rang sagt 'so lange hat der
    zweitlangsamste Zug gedauert' -- das kann man nachzaehlen."""
    assert kennzahlen._perzentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9
    assert kennzahlen._perzentil([5.0], 0.9) == 5.0
    assert kennzahlen._perzentil([], 0.9) == 0.0


# --- Der Abschnitt im Bericht ---------------------------------------------


def test_mechanische_treffer_nennen_ihren_grund():
    zug = Zug(
        schritt="a",
        beitraege=[Beitrag("S1", "a", "Dilan", "dilan", "ja passt")],
        bot=["Das habe ich notiert."],
    )
    treffer = kennzahlen.mechanische_treffer([zug], ["Dilan"])
    assert "Das habe ich notiert." in treffer
    assert "Notiert-Zeile" in treffer["Das habe ich notiert."]


def test_eine_notiert_zeile_entlastet_den_zug():
    zug = Zug(
        schritt="a",
        bot=[f"{kennzahlen.NOTIERT}\nBegriffe: Koffer", "Das habe ich notiert."],
    )
    assert kennzahlen.mechanische_treffer([zug], []) == {}
