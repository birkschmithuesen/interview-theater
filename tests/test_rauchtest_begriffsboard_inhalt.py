"""Karte t_2b9d2cbe: das Messskript offline -- keine Netz-, keine Live-DB-Zugriffe."""

import sqlite3

import pytest

from interview_theater import sprache, workshop
from scripts import begriffsboard_inhalt_zaehler as zaehler
from scripts import rauchtest_begriffsboard_inhalt as skript


@pytest.fixture
def padua(monkeypatch):
    """Muster aus tests/test_chat_sprache.py: Profil-Cache vor UND nach dem
    Test leeren, sonst erbt der naechste Test padua-2026."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_live_mit_opus_wird_verweigert():
    with pytest.raises(SystemExit):
        skript.pruefe_auswahl(["ansage_en", "live"], "opus")


def test_opus_mit_erfundenen_ist_erlaubt():
    skript.pruefe_auswahl(list(zaehler.ERFUNDEN), "opus")


def test_live_fall_traegt_kein_transkript():
    assert skript.LIVE.segmente == ()
    assert skript.LIVE.soll  # Soll-Liste steht im Skript


def test_live_rohantworten_werden_nie_geschrieben():
    assert skript.roh_pfad("live", "nachher", "kimi", 0, 1) is None
    assert skript.roh_pfad("ansage_en", "nachher", "kimi", 0, 1).parent == skript.ROH_VERZ


def test_live_db_wird_nur_lesend_geoeffnet(tmp_path, monkeypatch):
    gesehen = []
    echt = sqlite3.connect

    def merke(ziel, *a, **kw):
        gesehen.append((ziel, kw.get("uri")))
        return echt(ziel, *a, **kw)

    monkeypatch.setattr(skript.sqlite3, "connect", merke)
    with pytest.raises(sqlite3.OperationalError):
        skript.lies_live_segmente(str(tmp_path / "gibtsnicht.db"), skript.LIVE_CHAT_ID)
    assert gesehen and gesehen[0][0].endswith("?mode=ro") and gesehen[0][1] is True
    assert not (tmp_path / "gibtsnicht.db").exists()


def test_vorher_stand_kommt_aus_git():
    stand = skript.stand_vorher()
    assert stand.name == "vorher"
    assert stand.schema["required"] == ["board"]
    assert callable(stand.validiere) and callable(stand.nutzertext)
    assert "term board" in stand.system  # der EN-Prompt


def test_ein_lauf_mit_attrappe_zaehlt_beide_stufen(padua):
    fall = zaehler.lade_erfundene()[1]  # deutsch_stt
    antworten = iter([
        [{"begriff": "Heimat", "nennungen": 1, "zustimmung": 1,
          "begruendung": "Wird als Begriff gesammelt.", "zitat": "der erste Gepäck ist Heimat",
          "doppelbedeutung": "", "status": "kandidat"}],
        [{"begriff": "Heimat", "nennungen": 2, "zustimmung": 1,
          "begruendung": "Wird als Begriff gesammelt.", "zitat": "der erste Gepäck ist Heimat",
          "doppelbedeutung": "", "status": "kandidat"},
         {"begriff": "Test", "nennungen": 2, "zustimmung": 0, "begruendung": "",
          "zitat": "", "doppelbedeutung": "", "status": "kandidat"}],
    ])
    nutzertexte = []

    def rufe(stand, nutzer):
        nutzertexte.append(nutzer)
        return next(antworten)

    zahlen, roh, validiert = skript.ein_lauf(rufe, skript.stand_nachher(), fall, "en")
    assert len(nutzertexte) == 2                     # Haelfte, dann ganz
    assert set(zahlen) == {"roh", "validiert"}
    assert zahlen["roh"]["meta_begriffe"] == 1       # "Test"
    assert zahlen["roh"]["fuell_begruendungen"] == 1
    assert len(roh) == 2
