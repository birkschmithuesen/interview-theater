"""Die zwei offenen Flow-Fixes der Nacht-Simulation vom 06.09.2026.

Punkt 6 und 7 aus ``simulation/laeufe/2026-09-06-sammel.md`` (Top-8). Beide
haengen an einer Stelle, die in einem der Laeufe gemessen wurde -- kein Test
hier ist geraten.
"""

from __future__ import annotations

import pytest

from interview_theater import (
    ablauf, anweisungen, befehle, db, erkenner, knoepfe, phasen, repo,
)

from tests.test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


# --- Punkt 6a: eine Bitte erneuert das Angebot -----------------------------


def _mach_phase_2_moeglich(conn):
    """Begriffe gespeichert -> Phase 2 ist moeglich."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe, Streit")


def test_bitte_um_weiter_holt_das_phasenangebot_zurueck(conn, tg):
    """Gemessen: das Angebot fiel einmal, danach sagte die Gruppe "weiter"
    und bekam nichts mehr -- sie brauchte den versteckten ``/phase``."""
    _mach_phase_2_moeglich(conn)
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False

    # Der Erkenner liest "weiter" als phase_setzen -- ohne Nummer, die
    # ``nummer_fuer`` zuordnen koennte, oder mit der aktuellen Phase.
    erneuert = erkenner._erneuere_angebot_auf_bitte(
        conn, 1, [{"art": "phase_setzen", "wert": "weiter"}]
    )

    assert erneuert is True
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True
    _, text, leiste = tg.knoepfe[-1]
    assert [b for b, _ in leiste][0] == f"Weiter zu {phasen.knopfbezeichnung(2)}"


def test_bitte_ohne_moegliche_hoehere_phase_erneuert_nichts(conn, tg):
    """Kein Angebot ins Leere: steht die Voraussetzung nicht, bleibt es
    still, egal wie oft die Gruppe "weiter" sagt."""
    assert erkenner._erneuere_angebot_auf_bitte(
        conn, 1, [{"art": "phase_setzen", "wert": "weiter"}]
    ) is False
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False


def test_ein_echter_phasenwechsel_ist_keine_bitte(conn, tg):
    """"Wir gehen zu den Fragen" nennt eine HOEHERE Phase -- das ist ein
    Wechsel, kein Erneuern; dafuer gibt es ``_eintritt_nach_phasenwechsel``."""
    _mach_phase_2_moeglich(conn)
    knoepfe.biete_phase_proaktiv(conn, tg, 1)

    assert erkenner._erneuere_angebot_auf_bitte(
        conn, 1, [{"art": "phase_setzen", "wert": "2"}]
    ) is False


# --- Punkt 6b: /stand traegt den Knopf -------------------------------------


def test_stand_haengt_den_phasenknopf_darunter(conn, tg, einst):
    """Wer ``/stand`` tippt, sucht Orientierung -- dann soll der naechste
    Schritt ein Druck sein und nicht der versteckte ``/phase``."""
    _mach_phase_2_moeglich(conn)

    befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")

    _, text, leiste = tg.knoepfe[-1]
    assert text.startswith("Stand:")
    assert [b for b, _ in leiste] == [f"Weiter zu {phasen.knopfbezeichnung(2)}"]


def test_stand_ohne_moegliche_phase_bleibt_eine_reine_nachricht(conn, tg, einst):
    befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")

    assert tg.knoepfe == []
    assert tg.gesendet[-1][1].startswith("Stand:")


def test_stand_ruft_kein_modell(conn, tg, einst):
    """Die Zusage aus befehle.py gilt weiter -- auch mit dem neuen Knopf."""
    _mach_phase_2_moeglich(conn)
    befehle.behandle(conn, tg, einst, 1, "/stand", "Ada", klm=None)
    assert tg.knoepfe


# --- Punkt 6c: "Noch etwas aendern" und der naechste Parameter -------------


def _druecke_noch_etwas_aendern(conn, tg, einst):
    knoepfe.biete_phase_proaktiv(conn, tg, 1)
    _, _, leiste = tg.knoepfe[-1]
    daten = leiste[1][1]
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))


def test_noch_etwas_aendern_schweigt_zunaechst_weiter(conn, tg, einst):
    """Kein Draengeln: der Druck allein holt das Angebot nicht zurueck."""
    _mach_phase_2_moeglich(conn)
    _druecke_noch_etwas_aendern(conn, tg, einst)

    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False


def test_nach_noch_etwas_aendern_kommt_das_angebot_beim_naechsten_parameter(
    conn, tg, einst
):
    """Genau der Fall aus der Simulation: die Gruppe drueckt "Noch etwas
    aendern", aendert wirklich etwas -- und das Angebot kommt einmal wieder."""
    _mach_phase_2_moeglich(conn)
    _druecke_noch_etwas_aendern(conn, tg, einst)

    # Eine wirkliche Aenderung (Journal-/Arbeitsstandeintrag).
    assert phasen.erneuere_nach_aenderung(conn, 1) is True

    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True


def test_das_erneuerte_angebot_kommt_nur_einmal(conn, tg, einst):
    """Einmal je Aenderung, nicht bei jeder Nachricht."""
    _mach_phase_2_moeglich(conn)
    _druecke_noch_etwas_aendern(conn, tg, einst)
    phasen.erneuere_nach_aenderung(conn, 1)
    knoepfe.biete_phase_proaktiv(conn, tg, 1)

    assert phasen.erneuere_nach_aenderung(conn, 1) is False
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False


# --- Punkt 7: der Bot erfindet keine Szenentexte ---------------------------


@pytest.mark.parametrize(
    "text",
    [
        "lies uns Szene 2 vor",
        "zeig mal den Text von Szene 2",
        "Szene 2 ansehen",
        "was steht nochmal in szene 2?",
        "wortlaut szene 2 bitte",
    ],
)
def test_bitte_um_einen_szenentext_wird_erkannt(text):
    assert ablauf.szenentext_gewuenscht(text) == 2


@pytest.mark.parametrize(
    "text",
    [
        "in Szene 2 soll er einfach gehen",
        "Szene 2 gefaellt uns nicht",
        "zeig uns mal was du kannst",
        "wir haben drei Szenen",
        "",
    ],
)
def test_andere_saetze_bleiben_ein_gespraechszug(text):
    assert ablauf.szenentext_gewuenscht(text) is None


def _lege_szene_an(conn, nummer: int, volltext: str | None):
    return repo.lege_szene_an(
        conn, 1, nummer=nummer, titel="Am Kiosk", kurzbeschreibung=None,
        volltext=volltext,
    )


def test_die_bitte_liefert_den_echten_volltext(conn, tg):
    """Statt einer erfundenen Zusammenfassung: der Text aus der Datenbank,
    derselbe Weg wie hinter dem Knopf "Szene 2 ansehen"."""
    _lege_szene_an(conn, 2, "ANNA: Ich geh jetzt.\nBEN: Bleib.")

    knoepfe.zeige_szenentext(conn, tg, 1, 2)

    text = tg.gesendet[-1][1]
    assert "ANNA: Ich geh jetzt." in text
    assert text.startswith("Szene 2: Am Kiosk")


def test_ungeschriebene_szene_wird_als_solche_gemeldet(conn, tg):
    _lege_szene_an(conn, 2, None)

    knoepfe.zeige_szenentext(conn, tg, 1, 2)

    assert "noch nicht geschrieben" in tg.gesendet[-1][1]


def test_unbekannte_szene_wird_nicht_erfunden(conn, tg):
    knoepfe.zeige_szenentext(conn, tg, 1, 9)

    assert tg.gesendet[-1][1] == knoepfe._TEXT_SZENE_UNBEKANNT


def test_der_prompt_sagt_dass_der_volltext_fehlt(tmp_path, monkeypatch):
    """system.md und die Phasen 6/7 tragen den Satz -- der Modellweg fuer
    alles, was der Musterabgleich nicht faengt."""
    monkeypatch.setenv("IT_DB", str(tmp_path / "t.db"))
    anweisungen._CACHE.clear()

    system = anweisungen.hole("system")
    assert "Szenentexte nicht vor dir" in system
    assert "Szene N ansehen" in system

    for nummer in (6, 7):
        text = anweisungen.hole(f"phasen/{nummer}")
        assert "Szenentexte nicht vor dir" in text
        assert "erfinde keinen Text" in text


# --- Punkt 7, der Zug: kein Modellaufruf, echter Text ----------------------


class _KLM:
    def __init__(self):
        self.aufrufe = 0

    def schema(self, *a, **k):
        self.aufrufe += 1
        return {"antwort": "In Szene 2 geht es darum, dass Anna sich traut."}


class _TG:
    def __init__(self):
        self.gesendet = []
        self.naechste_message_id = 800

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


class _E:
    bot_name = "testbot"
    web_url = ""
    erkenner_modell = "m"


def test_die_bitte_um_szene_2_ruft_kein_modell(conn):
    """Der gemessene Fall: der Bot antwortete inhaltlich, obwohl der Text
    nicht in seinem Kontext lag. Jetzt kommt der echte Text, ohne Modell."""
    _lege_szene_an(conn, 2, "ANNA: Ich geh jetzt.")
    repo.merke_nachricht(
        conn, 1, 30, "Ada", 0, "text", "lies uns Szene 2 vor", repo._jetzt()
    )
    tg, klm = _TG(), _KLM()
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg, klm, _E(), 1, offen)

    assert klm.aufrufe == 0
    assert "ANNA: Ich geh jetzt." in tg.gesendet[-1][1]
    assert repo.unbeantwortete(conn, 1) == []


def test_eine_andere_szenennachricht_bleibt_ein_gespraechszug(conn):
    """Gegenprobe: nicht erkannt -> unveraendert ins Gespraech."""
    _lege_szene_an(conn, 2, "ANNA: Ich geh jetzt.")
    repo.merke_nachricht(
        conn, 1, 30, "Ada", 0, "text",
        "In Szene 2 soll Anna am Ende doch bleiben.", repo._jetzt(),
    )
    tg, klm = _TG(), _KLM()
    offen = [dict(n) for n in repo.unbeantwortete(conn, 1)]

    ablauf.antworte(conn, tg, klm, _E(), 1, offen)

    assert klm.aufrufe == 1
