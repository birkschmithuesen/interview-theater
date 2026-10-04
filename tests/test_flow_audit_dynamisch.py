"""Flow-Audit Schicht 2 (dynamischer Persona-Lauf, Padua, 04.10.2026) --
Tests fuer ``simulation/flow_audit_dynamisch.py``.

Laeuft vollstaendig offline: eine echte SQLite-Verbindung
(``tests/conftest.py``-Fixtures ``conn``/``einst``), eine
``TelegramAttrappe`` statt Netz, ein ``SkriptLLM`` statt eines echten
Sprachmodells. Kein ``betrieb/``-Zugriff, keine Kosten.

**Die Mutationsprobe** (``test_mutation_*``) ist das Abnahmekriterium dieser
Karte: ohne ``erkenner.ARTEN`` auf eine mutierte Menge zu stellen, bliebe
unklar, ob diese Schicht wirklich den ECHTEN Code misst oder nur eine
Attrappe bestaetigt, die sich selbst zustimmt."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from interview_theater import anweisungen, erkenner, phasen, repo, workshop
from simulation import flow_audit_dynamisch as fad
from simulation.attrappe import TelegramAttrappe


@pytest.fixture(autouse=True)
def padua_profil(monkeypatch):
    """Alle Tests dieser Datei laufen gegen das Padua-Profil (Englisch, die
    A/B-Fragenrunde, kein ``fragen_weich``) -- derselbe Umschaltweg wie
    ``tests/profile/test_dortmund.py`` und
    ``tests/test_web_dashboard_en.py`` (``monkeypatch.setenv`` reicht,
    ``workshop.aktiv()`` liest ``IT_WORKSHOP`` bei jedem Aufruf frisch; die
    beiden ``vergiss``/``_CACHE.clear``-Aufrufe sind reine Vorsicht gegen
    profilgebundene Caches in anderen Modulen)."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def klm():
    return fad.SkriptLLM()


CHAT_ID = 1  # dieselbe Testgruppe, die tests/conftest.py::conn anlegt


# ---------------------------------------------------------------------------
# Die Mutationsprobe -- DAS Abnahmekriterium dieser Karte.
# ---------------------------------------------------------------------------


def test_mutation_probe_begriffe_setzen_schreibt_normal(conn, einst, tg, klm):
    """Gegenprobe zuerst: ohne Mutation schreibt Station 3 wirklich --
    sonst waere ein spaeteres ``wirkungslos`` kein Befund, sondern der
    Normalzustand."""
    s = fad.station_03_korrektur_via_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert s.wirkungslos is False
    assert s.behauptet_nicht_getan is False


def test_mutation_probe_begriffe_setzen_ohne_intent_ist_wirkungslos(
    conn, einst, tg, klm, monkeypatch,
):
    """Die Probe selbst: ``erkenner.ARTEN`` ohne ``begriffe_setzen`` --
    SkriptLLM prueft ``erkenner.ARTEN`` LEBEND bei jedem Aufruf (siehe
    ``SkriptLLM._antwort_erkenner``), nicht einmal beim Bau. Ohne das wuerde
    dieser Test nichts beweisen: er pruefte dann nur, dass eine Attrappe tut,
    was man ihr sagt -- nicht, dass der echte Code auf eine fehlende
    Modell-Faehigkeit reagiert."""
    gepatcht = tuple(a for a in erkenner.ARTEN if a != "begriffe_setzen")
    assert "begriffe_setzen" not in gepatcht  # die Mutation griff wirklich
    monkeypatch.setattr(erkenner, "ARTEN", gepatcht)

    s = fad.station_03_korrektur_via_chat(conn, tg, klm, einst, CHAT_ID)

    assert s.schreibvorgang is False
    assert s.wirkungslos is True
    # "Got it -- swapping that in." klingt nach erledigt, obwohl nichts
    # geschrieben wurde -- genau das Muster, das diese Schicht jagt.
    assert s.behauptet_nicht_getan is True


def test_mutation_probe_erholt_sich_nach_dem_monkeypatch(conn, einst, tg, klm):
    """``monkeypatch`` revertiert automatisch nach dem vorigen Test --
    dieser eigenstaendige Test (frische Fixtures, kein geteilter Zustand)
    zeigt, dass ``erkenner.ARTEN`` wieder vollstaendig ist und Station 3
    wieder normal schreibt."""
    assert "begriffe_setzen" in erkenner.ARTEN
    s = fad.station_03_korrektur_via_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert s.wirkungslos is False


def test_skript_llm_antwort_erkenner_filtert_direkt_gegen_erkenner_arten(
    klm, monkeypatch,
):
    """Isoliert ``SkriptLLM._antwort_erkenner`` selbst -- OHNE den Umweg
    ueber eine Station, ``bot._zug_und_erkenner`` oder ``erkenner.erkenne``.

    Die drei ``test_mutation_probe_*``-Tests oben beweisen eine
    End-zu-Ende-Eigenschaft (Station 3 schreibt/schreibt nicht), aber eine
    kaputte oder rueckdatierte ``_antwort_erkenner`` wuerde dort NICHT
    auffallen: ``erkenner.erkenne`` hat selbst ein redundantes
    ``if art not in ARTEN: continue`` und wuerde eine aus ``ARTEN``
    entfernte Absicht ohnehin herausfiltern, auch wenn die Attrappe sie
    faelschlich zurueckgeben wuerde. Dieser Test ruft die Attrappen-Methode
    direkt auf und prueft NUR ihre eigene Lebend-Pruefung."""
    stufe = "unit_direkt_erkenner"
    klm.erkenner(stufe, [{"art": "begriffe_setzen", "wert": "x"}])

    assert "begriffe_setzen" in erkenner.ARTEN
    mit_intent = klm._antwort_erkenner(stufe)
    assert mit_intent == {
        "aenderungen": [{"art": "begriffe_setzen", "wert": "x"}],
    }

    gepatcht = tuple(a for a in erkenner.ARTEN if a != "begriffe_setzen")
    assert "begriffe_setzen" not in gepatcht
    monkeypatch.setattr(erkenner, "ARTEN", gepatcht)

    ohne_intent = klm._antwort_erkenner(stufe)
    assert ohne_intent == {"aenderungen": []}


# ---------------------------------------------------------------------------
# Phase 1, einzeln.
# ---------------------------------------------------------------------------


def test_station_01_eintritt_ohne_jargon_mit_cothinker_hinweis(conn, einst, tg, klm):
    s = fad.station_01_eintritt(conn, tg, klm, einst, CHAT_ID)
    assert fad.jargon_treffer(s.bot_antwort) == []
    assert fad.erwaehnt_zweites_handy(s.bot_antwort) is True


def test_station_02_begriffe_vorschlag_hat_hoechstens_eine_ruckfrage(
    conn, einst, tg, klm,
):
    s = fad.station_02_begriffe_vorschlag(conn, tg, klm, einst, CHAT_ID)
    assert s.rueckfragen_vor_aktion <= 1
    assert "Yes, save" in s.hinweis
    assert "True" in s.hinweis  # der Speicher-Knopf stand da


def test_station_03_korrektur_schreibt_ueber_den_erkenner(conn, einst, tg, klm):
    s = fad.station_03_korrektur_via_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert "Neighbours" in (fad._begriff_feld(conn, CHAT_ID) or "")


def test_station_04_begriffsboard_korrektur_schreibt_begriffe_und_detail(
    conn, einst, tg, klm,
):
    s = fad.station_04_begriffsboard_korrektur(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert "begriffe_detail geaendert: True" in s.hinweis
    assert "'Take these'-Knopf stand vorher da: True" in s.hinweis
    detail = fad._begriffe_detail_feld(conn, CHAT_ID)
    assert detail and "Departure" in detail


def test_station_05_echo_wird_erkannt_und_neu_angefordert(conn, einst, tg, klm):
    s = fad.station_05_echo_kontrolle(conn, tg, klm, einst, CHAT_ID)
    assert s.echo_erkannt is True
    assert klm.anzahl_aufrufe("p5_echo", "gespraech") == 2
    assert s.nachricht.lower() not in s.bot_antwort.lower()


def test_station_14_priya_begriffe_korrektur_schreibt_ueber_den_erkenner(
    conn, einst, tg, klm,
):
    """Review-Nachtrag: Priya muss auch in Phase 1 auftreten (mindestens
    einmal), nicht nur in Phase 2 -- siehe Docstring der Station."""
    s = fad.station_14_priya_begriffe_korrektur(conn, tg, klm, einst, CHAT_ID)
    assert s.phase == 1
    assert s.persona == fad.PRIYA.name
    assert s.schreibvorgang is True
    assert "Outsiders" in (fad._begriff_feld(conn, CHAT_ID) or "")
    assert len(s.fragen_der_persona) >= 1


# ---------------------------------------------------------------------------
# Phase 2, einzeln.
# ---------------------------------------------------------------------------


def test_station_06_eintritt_phase2_ohne_jargon(conn, einst, tg, klm):
    s = fad.station_06_eintritt_phase2(conn, tg, klm, einst, CHAT_ID)
    assert fad.jargon_treffer(s.bot_antwort) == []


def test_station_07_priya_eigene_frage_wird_gespeichert(conn, einst, tg, klm):
    s = fad.station_07_priya_eigene_frage(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert len(s.fragen_der_persona) >= 1


def test_station_08_giulia_aendert_frage_per_chat(conn, einst, tg, klm):
    s = fad.station_08_giulia_aendert_frage(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True


def test_station_09_fruehzeitig_fertig_loest_gegenueberstellung_aus(
    conn, einst, tg, klm,
):
    s = fad.station_09_fruehzeitig_fertig(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    stand = repo.hole_arbeitsstand(conn, CHAT_ID)
    assert stand["fragen_auswahl"]


def test_station_10_priya_akzeptiert_per_chat_ist_wirkungslos(conn, einst, tg, klm):
    """Dokumentiert den gefundenen toten Weg: ein getipptes 'yes' entscheidet
    die Frage nicht (siehe Docstring der Station)."""
    s = fad.station_10_priya_akzeptiert_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.wirkungslos is True
    assert s.behauptet_nicht_getan is True
    assert len(s.fragen_der_persona) >= 1


def test_station_11_klickzwang_chat_wirkungslos_knopf_wirkt(conn, einst, tg, klm):
    s = fad.station_11_klickzwang(conn, tg, klm, einst, CHAT_ID)
    assert s.klickzwang is True
    assert s.schreibvorgang is True


def test_station_12_phasenwechsel_per_chat_greift(conn, einst, tg, klm):
    assert phasen.aktuelle(conn, CHAT_ID) != 3
    s = fad.station_12_phasenwechsel_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert phasen.aktuelle(conn, CHAT_ID) == 3


def test_station_13_wartezustand_zeigt_tippanzeige(conn, einst, tg, klm):
    """Kostet echte ~4,2 Sekunden Testlaufzeit -- siehe Docstring der
    Station fuer die Begruendung (sonst ein Scheinbefund aus Schnelligkeit)."""
    s = fad.station_13_wartezustand(conn, tg, klm, einst, CHAT_ID)
    treffer = re.search(r"aufgerufen: (\d+) Mal", s.hinweis)
    assert treffer is not None
    assert int(treffer.group(1)) >= 1


# ---------------------------------------------------------------------------
# Phase 3, einzeln (Task B, t_92f99911).
# ---------------------------------------------------------------------------


def test_station_15_interview_starten_per_chat_schaltet_nichts_ein(conn, einst, tg, klm):
    """Der Kernfund dieser Station: ein per Chat erkannter
    'interview_starten'-Intent schaltet den Modus NICHT ein, er bietet nur
    den Start-Knopf an -- erst dessen Druck startet wirklich."""
    s = fad.station_15_interview_starten_ist_knopf_bzw_befehl_only(
        conn, tg, klm, einst, CHAT_ID,
    )
    assert s.schreibvorgang is True
    assert s.wirkungslos is False
    assert "Start-Knopf wurde angeboten: True" in s.hinweis
    assert "nach dem Knopfdruck wirklich gestartet: True" in s.hinweis


def test_station_16_interview_verwerfen_laufend_entfernt_den_laufenden_kopf(
    conn, einst, tg, klm,
):
    s = fad.station_16_interview_verwerfen_laufend(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert s.wirkungslos is False
    assert "entfernt_am danach gesetzt: True" in s.hinweis
    assert "Interviewmodus danach noch an: True" in s.hinweis


def test_station_17_transkript_korrektur_als_text_waehrend_interview_greift(
    conn, einst, tg, klm,
):
    s = fad.station_17_transkript_korrektur_waehrend_interview(
        conn, tg, klm, einst, CHAT_ID,
    )
    assert s.schreibvorgang is True
    assert "gepogt" in s.hinweis
    assert "gepoekt market" not in s.hinweis.split("nachher=")[-1]


def test_station_18_normales_interview_wird_echt_verdichtet(conn, einst, tg, klm):
    s = fad.station_18_normales_interview_wird_echt_verdichtet(
        conn, tg, klm, einst, CHAT_ID,
    )
    assert s.schreibvorgang is True
    assert "Verdichtung angelegt: True" in s.hinweis
    assert "Phase 4 moeglich: True" in s.hinweis


def test_station_19_kurzes_interview_blockiert_phase4_nicht(conn, einst, tg, klm):
    """Padua Phasen TEIL 2, Befund 4a -- ein zu-kurz uebersprungenes
    Interview darf die Phase-4-Sperre nicht auf unbestimmte Zeit offen
    halten."""
    s = fad.station_19_kurzes_interview_blockiert_phase4_nicht(
        conn, tg, klm, einst, CHAT_ID,
    )
    assert s.schreibvorgang is True
    assert s.wirkungslos is False
    assert "zu_kurz_uebersprungen: True" in s.hinweis
    assert "Phase 4 moeglich: True" in s.hinweis


def test_station_20_offenes_interview_blockiert_phase4(conn, einst, tg, klm):
    """Das Gegenstueck zu Station 19: ein ausreichend langes, aber nie
    verdichtetes Interview MUSS die Sperre auf Phase 4 auslösen."""
    s = fad.station_20_offenes_interview_blockiert_phase4(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert s.wirkungslos is False
    assert "Phase 4 vor dem offenen Interview: True" in s.hinweis
    assert "Phase 4 danach: False" in s.hinweis


def test_station_21_phasenhinweis_kommt_genau_einmal(conn, einst, tg, klm):
    """Der heute wirkende Mechanismus (``kontext._baue_phasenhinweis``,
    NICHT das tote ``aufnahme._phasenfrage``) bietet Phase 4 genau einmal
    an."""
    s = fad.station_21_phasenhinweis_genau_einmal(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert s.wirkungslos is False
    assert "1. Aufruf: 4" in s.hinweis
    assert "2. Aufruf: None" in s.hinweis


# ---------------------------------------------------------------------------
# Phase 4, einzeln (Task B, t_92f99911).
# ---------------------------------------------------------------------------


def test_station_22_eintritt_phase4_ohne_jargon_und_ohne_schlag_vor_knopf(
    conn, einst, tg, klm,
):
    s = fad.station_22_eintritt_phase4_offene_frage_ohne_knoepfe(
        conn, tg, klm, einst, CHAT_ID,
    )
    assert fad.jargon_treffer(s.bot_antwort) == []
    assert "'Schlag du vor'-Knopf beim Eintritt angeboten: False" in s.hinweis
    assert "'wir zuerst'-Knopf angeboten: False" in s.hinweis


def test_station_23_setting_per_chat_schreibt_rahmen(conn, einst, tg, klm):
    s = fad.station_23_setting_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    from interview_theater import repo

    stand = repo.hole_arbeitsstand(conn, CHAT_ID)
    assert "laundromat" in (stand["rahmen"] or "")


def test_station_24_figuren_per_chat_legt_eine_figur_an(conn, einst, tg, klm):
    s = fad.station_24_figuren_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert len(s.fragen_der_persona) >= 1


def test_station_25_geschichte_per_chat_schreibt_geschichte(conn, einst, tg, klm):
    s = fad.station_25_geschichte_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True


def test_station_26_us_einwilligung_per_chat_setzt_den_stand_auf_ja(
    conn, einst, tg, klm,
):
    s = fad.station_26_us_einwilligung_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    from interview_theater import repo

    assert repo.szene_usa_stand(conn, CHAT_ID) == "ja"


def test_station_27_phasenwechsel_4_zu_5_per_chat_greift(conn, einst, tg, klm):
    from interview_theater import phasen

    assert phasen.aktuelle(conn, CHAT_ID) != 5
    s = fad.station_27_phasenwechsel_4_zu_5_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert phasen.aktuelle(conn, CHAT_ID) == 5


# ---------------------------------------------------------------------------
# Die Mutationsprobe dieser Karte (Phase 4) -- das Abnahmekriterium von
# t_92f99911: einen Intent aus der Phasenfreigabe entfernen -> Schicht 1 UND
# Schicht 2 melden den Befund; zuruecksetzen -> gruen. Der Schicht-1-Teil
# steht in tests/test_flow_abdeckung.py
# (test_mutationsprobe_phase4_rahmen_setzen_wird_als_toter_weg_gemeldet);
# dies hier ist der Schicht-2-Teil, am selben Intent (rahmen_setzen).
# ---------------------------------------------------------------------------


def test_mutationsprobe_rahmen_setzen_macht_station_23_wirkungslos(
    conn, einst, tg, klm, monkeypatch,
):
    """Gegenprobe zuerst: ohne Mutation schreibt Station 23 wirklich."""
    s_vorher = fad.station_23_setting_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s_vorher.schreibvorgang is True
    assert s_vorher.wirkungslos is False


def test_mutationsprobe_rahmen_setzen_entfernt_erzeugt_wirkungslos(
    conn, einst, tg, klm, monkeypatch,
):
    """Die Probe selbst: ``erkenner.ARTEN`` ohne ``rahmen_setzen`` -- Station
    23 muss ``wirkungslos``/``behauptet_nicht_getan`` werden, wie
    ``test_mutation_probe_begriffe_setzen_ohne_intent_ist_wirkungslos`` fuer
    Phase 1 es schon tut."""
    from interview_theater import erkenner

    gepatcht = tuple(a for a in erkenner.ARTEN if a != "rahmen_setzen")
    assert "rahmen_setzen" not in gepatcht
    monkeypatch.setattr(erkenner, "ARTEN", gepatcht)

    s = fad.station_23_setting_per_chat(conn, tg, klm, einst, CHAT_ID)

    assert s.schreibvorgang is False
    assert s.wirkungslos is True
    assert s.behauptet_nicht_getan is True


def test_mutationsprobe_rahmen_setzen_erholt_sich_nach_dem_monkeypatch(
    conn, einst, tg, klm,
):
    """``monkeypatch`` revertiert automatisch nach dem vorigen Test -- dieser
    eigenstaendige Test (frische Fixtures) zeigt, dass ``erkenner.ARTEN``
    wieder vollstaendig ist und Station 23 wieder normal schreibt
    ('Zuruecksetzen -> gruen' aus der Abnahme)."""
    from interview_theater import erkenner

    assert "rahmen_setzen" in erkenner.ARTEN
    s = fad.station_23_setting_per_chat(conn, tg, klm, einst, CHAT_ID)
    assert s.schreibvorgang is True
    assert s.wirkungslos is False


# ---------------------------------------------------------------------------
# Der ganze Lauf, in Reihenfolge.
# ---------------------------------------------------------------------------


def test_fuehre_alle_aus_liefert_27_sondierungen_ohne_ausnahme(conn, einst, tg, klm):
    ergebnisse = fad.fuehre_alle_aus(conn, tg, klm, einst, CHAT_ID)
    assert len(ergebnisse) == len(fad.ALLE_STATIONEN) == 27
    fehlgeschlagen = [s for s in ergebnisse if s.phase == 0]
    assert fehlgeschlagen == [], (
        "Eine oder mehrere Stationen sind mit einer Ausnahme abgebrochen: "
        + "; ".join(f"{s.station}: {s.hinweis}" for s in fehlgeschlagen)
    )
    personen = {s.persona for s in ergebnisse}
    phase1_personen = {s.persona for s in ergebnisse if s.phase == 1}
    phase2_personen = {s.persona for s in ergebnisse if s.phase == 2}
    phase3_personen = {s.persona for s in ergebnisse if s.phase == 3}
    phase4_personen = {s.persona for s in ergebnisse if s.phase == 4}
    assert fad.PRIYA.name in personen
    assert fad.PRIYA.name in phase1_personen, (
        "Priya muss mindestens einmal in Phase 1 auftreten (Review-Fund "
        "04.10.2026, Station 14)"
    )
    assert fad.PRIYA.name in phase2_personen
    assert fad.PRIYA.name in phase3_personen and fad.GIULIA.name in phase3_personen, (
        "Beide Personas muessen in Phase 3 auftreten (Task B, t_92f99911)"
    )
    assert fad.PRIYA.name in phase4_personen and fad.GIULIA.name in phase4_personen, (
        "Beide Personas muessen in Phase 4 auftreten (Task B, t_92f99911)"
    )
    # Der einzige bekannte rote Befund im vollen Sitzungslauf ist der schon
    # dokumentierte Phase-2-Fund (Station 10, 'Priya akzeptiert eine Frage
    # per Chat') -- kein neuer, unbekannter roter Befund darf hier
    # auftauchen, ohne dass jemand ihn bemerkt.
    rote = [s for s in ergebnisse if s.wirkungslos]
    unbekannt = [s for s in rote if "GEFUNDENER TOTER WEG" not in s.hinweis]
    assert unbekannt == [], (
        "Unbekannter roter Befund im vollen Sitzungslauf: "
        + "; ".join(f"{s.station}: {s.hinweis}" for s in unbekannt)
    )


# ---------------------------------------------------------------------------
# Klasse-A-Fix (04.10.2026): ein echtes ``klm`` darf nicht crashen.
#
# Der echte, kostenpflichtige Lauf von ``scripts/flow_audit_lauf.py`` gegen
# ``interview_theater.llm.LLM`` liess vor diesem Fix ALLE 14 Stationen mit
# ``AttributeError: 'LLM' object has no attribute 'stelle'`` abstuerzen --
# kein einziger Test in dieser Datei hatte das je geprueft, weil die
# ``klm``-Fixture oben immer ``fad.SkriptLLM`` baut. Diese Attrappe hat
# bewusst NUR ``.schema()`` -- die oeffentliche Schnittstelle von
# ``interview_theater.llm.LLM``, die jede Station tatsaechlich braucht --
# und ausdruecklich KEINE der SkriptLLM-spezifischen Konfigurationsmethoden
# (``.stelle()``, ``.antwort()``, ``.erkenner()``, ``.verzoegere()``,
# ``.anzahl_aufrufe()``). Direkter Regressionstest fuer genau den
# Produktionsabsturz.
# ---------------------------------------------------------------------------


class _NurSchemaLLM:
    """Minimale Fake-``klm`` fuer den Regressionstest: nur ``.schema()``,
    mit derselben Signatur wie ``interview_theater.llm.LLM.schema`` (siehe
    dort), sonst nichts. Liefert eine feste, plausible Antwort unabhaengig
    vom Inhalt -- genug, um zu beweisen, dass eine Station selbst nichts
    aufruft, das dieser Fake nicht hat."""

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort") -> dict:
        if art == "erkenner":
            return {"aenderungen": []}
        return {
            "antwort": "A plausible, fixed reply -- this fake implements "
                       "only .schema(), nothing SkriptLLM-specific.",
        }


def test_echtes_klm_ohne_attrappenmethoden_crasht_nicht_bei_gespraech_kette(
    conn, einst, tg,
):
    """Call-Form 1: die Kettensyntax ``klm.stelle(stufe).gespraech(...)``
    (hier: ueber ``_konfiguriere_falls_attrappe``) -- Station 1 ist die
    erste Station jeder Sitzung und nutzt sie beim Phaseneintritt. Vor dem
    Fix: ``AttributeError: 'LLM' object has no attribute 'stelle'``, noch
    bevor ein Modellaufruf stattfand."""
    klm = _NurSchemaLLM()
    s = fad.station_01_eintritt(conn, tg, klm, einst, CHAT_ID)
    assert isinstance(s, fad.Sondierung)


def test_echtes_klm_ohne_attrappenmethoden_crasht_nicht_bei_standalone_erkenner(
    conn, einst, tg,
):
    """Call-Form 2: der NICHT gekettete, eigenstaendige Aufruf
    ``klm.erkenner(stufe, [...])`` (Station 3, die Mutationsprobe-Station).
    Ob am Ende wirklich etwas geschrieben wurde, ist hier nicht der Punkt
    (die Fake-``klm.schema`` liefert fuer ``art='erkenner'`` eine leere
    Liste -- ein plausibles, aber leeres Ergebnis) -- entscheidend ist
    allein, dass die Station durchlaeuft, ohne an einer fehlenden
    SkriptLLM-Methode zu krachen."""
    klm = _NurSchemaLLM()
    s = fad.station_03_korrektur_via_chat(conn, tg, klm, einst, CHAT_ID)
    assert isinstance(s, fad.Sondierung)
    assert s.schreibvorgang in (True, False)


def test_echtes_klm_ohne_attrappenmethoden_station_05_skippt_messung_ehrlich(
    conn, einst, tg,
):
    """Call-Form 3: die Messung-statt-Konfiguration-Stationen (Aufgabenbrief
    Punkt 2). Station 5 braucht ``klm.anzahl_aufrufe()`` -- eine reine
    SkriptLLM-Messgroesse ohne Gegenstueck bei einem echten Modell (ein
    echtes Sprachmodell spiegelt eine Nutzernachricht so gut wie nie
    woertlich). Gegen ein ``klm`` ohne diese Methode darf die Station nicht
    crashen UND darf keinen erfundenen Befund vortaeuschen -- sie muss die
    Messung ueberspringen und das im Hinweis sagen."""
    klm = _NurSchemaLLM()
    s = fad.station_05_echo_kontrolle(conn, tg, klm, einst, CHAT_ID)
    assert isinstance(s, fad.Sondierung)
    assert s.echo_erkannt is None
    assert "uebersprungen" in s.hinweis


def test_echtes_klm_ohne_attrappenmethoden_station_13_skippt_verzoegerung(
    conn, einst, tg,
):
    """Dieselbe Call-Form wie Station 5, am anderen Pflichtfall
    (Aufgabenbrief Punkt 2): Station 13 braucht ``klm.verzoegere()``. Gegen
    ein echtes ``klm`` entfaellt die kuenstliche Verzoegerung, aber die
    Zaehlung von ``tg.getippt`` bleibt sinnvoll und laeuft unveraendert
    weiter (was am echten Modell messbar bleibt, bleibt gemessen)."""
    klm = _NurSchemaLLM()
    s = fad.station_13_wartezustand(conn, tg, klm, einst, CHAT_ID)
    assert isinstance(s, fad.Sondierung)
    assert "keine kuenstliche Verzoegerung" in s.hinweis
    treffer = re.search(r"aufgerufen: (\d+) Mal", s.hinweis)
    assert treffer is not None


def test_fuehre_alle_aus_markiert_eine_abgebrochene_station_als_befund(
    conn, einst, tg, klm, monkeypatch,
):
    """Der zweite Klasse-A-Fund: eine werfende Station sah im Bericht vor
    dem Fix wie Station 2 aus (``schreibvorgang=None`` -> ``wirkungslos``
    FALSE -- 'nichts zu schreiben erwartet, wie vorgesehen'). Der echte,
    kostenpflichtige Lauf stand deshalb trotz 14/14 Abstuerzen mit 'Keine --
    alle Sondierungen haben gewirkt' im Bericht, denn
    ``scripts/flow_audit_lauf.py::schreibe_bericht`` gruppiert die
    Befunde-Sektion ausschliesslich ueber ``Sondierung.wirkungslos``.

    Monkeypatcht ``ALLE_STATIONEN`` auf eine einzelne, absichtlich werfende
    Funktion -- isoliert, ohne auf einen echten Bot-Fehlerpfad angewiesen
    zu sein, der eine Ausnahme eventuell selbst schon abfaengt."""
    def _werfende_station(conn, tg, klm, e, chat_id):
        raise RuntimeError("absichtlich fuer diesen Test")

    monkeypatch.setattr(fad, "ALLE_STATIONEN", (_werfende_station,))

    ergebnisse = fad.fuehre_alle_aus(conn, tg, klm, einst, CHAT_ID)

    assert len(ergebnisse) == 1
    s = ergebnisse[0]
    assert s.phase == 0
    assert s.schreibvorgang is False
    assert s.wirkungslos is True
    assert "RuntimeError" in s.hinweis
    assert "absichtlich fuer diesen Test" in s.hinweis


# ---------------------------------------------------------------------------
# Onboarding-Pflichtpruefpunkt 5 (Verstaendlichkeit der Fehlermeldungen) --
# EIN rein statischer Test, kein Modellaufruf, keine Sondierung. Phase 3
# (aufnahme.py, web_chat.py) ist fuer DIESE Karte nicht der Pruefgegenstand
# (Audio/STT/Segmente bleiben aussen vor) -- dieser Test liest den
# Phase-3-Code nur als Nachweis fuer den Onboarding-Pflichtpruefpunkt
# "verstaendliche Fehlerfaelle" und bewertet Phase 3 selbst nicht.
# ---------------------------------------------------------------------------

_ROT_FLAGGEN = re.compile(
    r"\b(?:400|401|403|404|405|408|409|413|415|429|500|502|503)\b"
    r"|Exception|Traceback|\bError\b",
)


def _text_konstanten(pfad: Path) -> list[str]:
    """Alle String-Literale, die einer ``_TEXT_*``/``TEXT_*``-Konstante
    zugewiesen werden -- per ``ast``, nicht per Regex, weil mehrzeilige
    Dreifach-Anfuehrungszeichen und f-Strings sonst falsch geschnitten
    wuerden."""
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    werte: list[str] = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Assign):
            continue
        namen = [t.id for t in knoten.targets if isinstance(t, ast.Name)]
        if not any(n.startswith("_TEXT_") or n.startswith("TEXT_") for n in namen):
            continue
        for teil in ast.walk(knoten.value):
            if isinstance(teil, ast.Constant) and isinstance(teil.value, str):
                werte.append(teil.value)
    return werte


def test_phase3_fehlermeldungen_enthalten_keine_rohen_codes():
    """Nachweis fuer Onboarding-Pflichtpruefpunkt 5 ('Understandable error
    cases: mic denied, upload failed, empty transcript'). Diese zwei Module
    (``aufnahme.py``, ``web_chat.py``) sind Phase-3-Mechanik und liegen
    ausserhalb des dynamischen Geltungsbereichs dieser Karte (nur Phase 1+2) --
    gelesen wird hier rein als Text, kein Modellaufruf, keine Bewertung von
    Phase 3 selbst."""
    wurzel = Path(__file__).resolve().parent.parent / "interview_theater"
    treffer: list[tuple[str, str]] = []
    for datei in ("aufnahme.py", "web_chat.py"):
        for text in _text_konstanten(wurzel / datei):
            if _ROT_FLAGGEN.search(text):
                treffer.append((datei, text))
    assert treffer == [], (
        "Nutzertext-Konstante mit rohem HTTP-Code oder Exception-Namen "
        f"gefunden: {treffer}"
    )
