"""Der Regie-Befehl ``/festlegung`` (06.09.2026).

**Kein Komfort, sondern die Rueckfallebene** (Analyse § 4.4 Risiko 4): der
Erkenner laeuft ueber ein Modell, das ausfallen kann -- am 06.09. ist es
mitten in Phase 4 mit HTTP 5xx ausgefallen. Faellt es aus, gibt es sonst
keinen Weg, eine Festlegung abzulegen.

Kein Netzzugriff, Telegram als Attrappe. Fixtures synthetisch.
"""

import pytest

from interview_theater import befehle, repo
from tests.test_befehle import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


def test_befehl_ist_bekannt():
    assert "/festlegung" in befehle._BEKANNTE_BEFEHLE


def test_befehl_wird_nicht_beworben():
    """Slash-Befehle werden nicht mehr beworben (docs/agents/entscheidungen.md) -- und dieser
    hier schon gar nicht: er ist der Notausgang des Workshop-Teams, nicht
    ein Weg fuer die Gruppe."""
    assert "/festlegung" not in befehle._TEXT_HILFE
    assert "festlegung" not in [b["command"] for b in befehle.BEFEHLE_LISTE]


def test_setzt_bereich_bezug_und_text(conn, einst, tg):
    befehle.behandle(
        conn, tg, einst, 1, "/festlegung figur/Sevda: 19, aus Bulgarien", "Ada"
    )
    zeile = repo.festlegungen(conn, 1)[0]
    assert (zeile["bereich"], zeile["bezug"], zeile["text"], zeile["quelle"]) == (
        "figur", "Sevda", "19, aus Bulgarien", "befehl"
    )
    assert "19, aus Bulgarien" in tg.gesendet[0][1]


def test_setzt_ohne_bezug(conn, einst, tg):
    befehle.behandle(
        conn, tg, einst, 1, "/festlegung struktur: nur eine Szene", "Ada"
    )
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "struktur"
    assert zeile["bezug"] is None


def test_ohne_bereich_landet_es_in_sonstiges(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/festlegung das Ende bleibt offen", "Ada")
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "sonstiges"
    assert zeile["text"] == "das Ende bleibt offen"


def test_dieselbe_zweimal_sagt_es_und_legt_nichts_an(conn, einst, tg):
    """Anders als der Erkenner (der still bleibt) antwortet ein getippter
    Befehl immer: Schweigen sieht aus wie ein kaputter Bot."""
    befehle.behandle(conn, tg, einst, 1, "/festlegung ort: der Skatepark", "Ada")
    befehle.behandle(conn, tg, einst, 1, "/festlegung ort: der Skatepark", "Ada")
    assert len(repo.festlegungen(conn, 1)) == 1
    assert tg.gesendet[1][1] == befehle._TEXT_FESTLEGUNG_SCHON_DA


def test_weg_nimmt_zurueck(conn, einst, tg):
    befehle.behandle(
        conn, tg, einst, 1, "/festlegung ort: Zweiter Ort ist die Schule", "Ada"
    )
    befehle.behandle(conn, tg, einst, 1, "/festlegung weg schule", "Ada")
    assert repo.festlegungen(conn, 1) == []
    # Wortgleich zum Journalweg ("Entfernt: Journal: ..."), damit beide
    # Ruecknahmen im Chat gleich aussehen.
    assert tg.gesendet[-1][1] == "Entfernt: Festlegung: Zweiter Ort ist die Schule."


def test_weg_ohne_treffer_sagt_es(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/festlegung weg bahnhof", "Ada")
    assert tg.gesendet[-1][1] == befehle._TEXT_FESTLEGUNG_UNBEKANNT


def test_weg_schreibt_eine_journalzeile(conn, einst, tg):
    """Der Weg bleibt sichtbar, auch wenn das Entfernte es nicht mehr ist --
    dieselbe Regel wie beim Journal (N3)."""
    befehle.behandle(conn, tg, einst, 1, "/festlegung ort: der Skatepark", "Ada")
    befehle.behandle(conn, tg, einst, 1, "/festlegung weg skatepark", "Ada")
    texte = [z["text"] for z in repo.journal(conn, 1)]
    assert any("Skatepark" in t for t in texte)


def test_ohne_argument_zeigt_die_liste(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/festlegung struktur: nur eine Szene", "Ada")
    befehle.behandle(conn, tg, einst, 1, "/festlegung", "Ada")
    text = tg.gesendet[-1][1]
    assert "[struktur] nur eine Szene" in text
    assert befehle._TEXT_FESTLEGUNG_HILFE in text


def test_ohne_argument_und_ohne_festlegungen(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/festlegung", "Ada")
    assert befehle._TEXT_FESTLEGUNG_LEER in tg.gesendet[-1][1]


def test_ruft_kein_modell(conn, einst, tg):
    """Wie jeder Slash-Befehl: er beantwortet sich allein aus der Datenbank
    -- deshalb steht er ueberhaupt als Rueckfallebene da."""
    behandelt = befehle.behandle(
        conn, tg, einst, 1, "/festlegung stil: kurze Szenen", "Ada", klm=None
    )
    assert behandelt is True
    assert repo.festlegungen(conn, 1)
