"""Modellwahl-Karte (02.10.2026): Gespraech/Schaerfung/Szene/... ab Phase 4
mit Einwilligung ueber Claude, sonst (und immer fuer sensible Daten) Kimi.

Siehe docs/entscheidung-modellwahl-2026-10-02.md -- diese Tests pruefen
genau die darin festgehaltene Regel, nicht Implementierungsdetails."""

import ast
import dataclasses
import json
from pathlib import Path

import httpx
import pytest

from interview_theater import (
    erkenner, knoepfe, kontext, kosten, modellwahl, repo, szene, szene_claude,
    szenenfolge, vorschlagssperre, workshop,
)
from interview_theater.knoepfe.stationen import PHASE_BEGRIFFE

CHAT = 1


@pytest.fixture(autouse=True)
def _freie_szenenfolge_sperre():
    vorschlagssperre.vergiss(CHAT)
    yield
    vorschlagssperre.vergiss(CHAT)


@pytest.fixture
def opus_e(einst):
    """Dieselbe Einstellungen-Attrappe wie ueberall, nur mit erlaubtem
    Claude-Schalter (IT_SZENE_ANBIETER=claude)."""
    return dataclasses.replace(einst, szene_anbieter="claude")


@pytest.fixture
def padua(monkeypatch):
    """Wie ``test_erkenner_teil2.py::padua`` -- IT_WORKSHOP=padua-2026 per
    monkeypatch, Profil-Cache davor und danach vergessen."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


@pytest.fixture
def opus_e_padua(opus_e, padua):
    """``opus_e`` (Betreiber erlaubt Claude) UNTER dem Padua-Profil
    (``modellwahl.einwilligung = false``) -- die Einwilligungsfrage ist
    hier komplett abgeschaltet."""
    return opus_e


def _stimme_zu(conn, chat_id=CHAT, ja=True):
    repo.setze_szene_usa(conn, chat_id, ja)


# --------------------------------------------------------------------------
# Routing: Phase x Einwilligung x Schalter
# --------------------------------------------------------------------------


def test_phase_unter_4_bleibt_kimi_trotz_einwilligung_und_schalter(conn, opus_e):
    repo.setze_phase(conn, CHAT, 3)
    _stimme_zu(conn)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False


def test_phase_ab_4_mit_einwilligung_und_schalter_ist_claude(conn, opus_e):
    repo.setze_phase(conn, CHAT, 4)
    _stimme_zu(conn)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is True


def test_ohne_einwilligung_bleibt_kimi(conn, opus_e):
    repo.setze_phase(conn, CHAT, 5)
    # nicht zugestimmt (Stand 'offen')
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False


def test_nein_bleibt_kimi(conn, opus_e):
    repo.setze_phase(conn, CHAT, 5)
    _stimme_zu(conn, ja=False)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False


def test_ohne_betreiberschalter_bleibt_kimi(conn, einst):
    """``einst`` hat den Vorgabewert 'infomaniak' -- auch mit Einwilligung
    und hoher Phase passiert nichts, ohne dass der Betreiber es erlaubt."""
    repo.setze_phase(conn, CHAT, 6)
    _stimme_zu(conn)
    assert modellwahl.konversation_ueber_claude(einst, conn, CHAT) is False


def test_zurueck_zu_phase_3_interviews_ist_wieder_kimi(conn, opus_e):
    """Einmal in Phase 5 mit Einwilligung auf Claude, dann zurueck nach 3
    (Interviews) -- keine eigene Rueckschaltung noetig, die Phase IST die
    Bedingung. Phase 2 ist dagegen seit der Padua Phase 1+2 Karte
    (03.10.2026) selbst Opus-faehig -- nur der Sprung IN Phase 3 schaltet
    zurueck auf Kimi (vorher: jede Phase unter 4)."""
    repo.setze_phase(conn, CHAT, 5)
    _stimme_zu(conn)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is True
    repo.setze_phase(conn, CHAT, 3)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False
    repo.setze_phase(conn, CHAT, 2)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is True


@pytest.mark.parametrize("phase", [1, 2, 4, 5, 6, 7])
def test_jede_phase_ausser_interviews_ist_claude_faehig_mit_einwilligung(
    conn, opus_e, phase,
):
    """Seit der Padua Phase 1+2 Karte (03.10.2026) ist jede Phase ausser
    Phase 3 (Interviews) Opus-faehig, sobald Schalter und Einwilligung
    stehen -- auch Phase 1 (Diskussionsverdichtung) und Phase 2
    (Fragenformulierung/KI-Vorschlaege), die vorher wie jede Phase unter 4
    unbedingt bei Kimi blieben."""
    repo.setze_phase(conn, CHAT, phase)
    _stimme_zu(conn)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is True


def test_phase_3_interviews_bleibt_immer_kimi_mit_einwilligung(conn, opus_e):
    """Die einzige Ausnahme, unbedingt: Interview-Rohdaten gehen nie ueber
    Claude, auch mit Schalter und Einwilligung nicht."""
    repo.setze_phase(conn, CHAT, 3)
    _stimme_zu(conn)
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False


@pytest.mark.parametrize("phase", [1, 2, 3, 4, 5, 6, 7])
def test_ohne_einwilligung_bleibt_jede_phase_kimi(conn, opus_e, phase):
    repo.setze_phase(conn, CHAT, phase)
    # keine Zustimmung (Stand bleibt 'offen')
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False


@pytest.mark.parametrize("phase", [1, 2, 3, 4, 5, 6, 7])
def test_ohne_betreiberschalter_bleibt_jede_phase_kimi(conn, einst, phase):
    """``einst`` hat den Vorgabewert 'infomaniak' -- auch mit Einwilligung
    und jeder Phase passiert nichts, ohne dass der Betreiber es erlaubt."""
    repo.setze_phase(conn, CHAT, phase)
    _stimme_zu(conn)
    assert modellwahl.konversation_ueber_claude(einst, conn, CHAT) is False


def test_verdichter_ruft_modellwahl_und_szene_claude_nie_an():
    """Sensible Daten -- jede Interview-Verdichtung -- bleiben IMMER bei
    Kimi, auch waehrend eines Nachhol-Laufs in Phase 4+. Durchgesetzt wird
    das dadurch, dass das Modul die Frage nie stellt: ein struktureller
    Test (AST, kein Netz) haelt das am Quelltext fest, wie
    tests/test_knoepfe_struktur.py es fuer die Knopf-Zusagen tut."""
    quelle = Path("interview_theater/verdichter.py").read_text()
    baum = ast.parse(quelle)
    namen = {
        n.id for n in ast.walk(baum) if isinstance(n, ast.Name)
    } | {
        n.attr for n in ast.walk(baum) if isinstance(n, ast.Attribute)
    } | {
        alias.name for node in ast.walk(baum) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    } | {
        alias.asname or alias.name
        for node in ast.walk(baum) if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "modellwahl" not in namen
    assert "szene_claude" not in namen


# --------------------------------------------------------------------------
# Fallback auf Kimi bei einem Claude-Fehler
# --------------------------------------------------------------------------


class _KLM:
    def __init__(self):
        self.gesehen = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.gesehen.append(art)
        return {"antwort": "von Kimi"}


def test_fallback_bei_claude_fehler_nutzt_kimi_und_vermerkt_vorfall(
    conn, opus_e, monkeypatch,
):
    def kaputt(*a, **kw):
        raise szene_claude.ClaudeFehler("simulierter Ausfall")

    monkeypatch.setattr(szene_claude, "schema", kaputt)
    klm = _KLM()
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, opus_e, CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
        ueber_claude=True,
    )
    assert ergebnis == {"antwort": "von Kimi"}
    assert klm.gesehen == ["gespraech"]
    vorfall = conn.execute(
        "SELECT art FROM vorfall WHERE art = ?", (modellwahl.VORFALL_OPUS_FALLBACK,)
    ).fetchone()
    assert vorfall is not None


class _LLMAttrappe:
    def __init__(self):
        self.aufrufe = 0

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.aufrufe += 1
        return "VORSCHLAG SZENENFOLGE:\nSzene 1 -- Am Bahnhof"


class _TelegramAttrappeFolge:
    def __init__(self):
        self.gesendet = []
        self.naechste_message_id = 500

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)


def test_szenenfolge_laeuft_ab_phase_4_mit_einwilligung_ueber_claude(
    conn, opus_e, monkeypatch,
):
    """Szenenfolge fehlte in der ersten Fassung dieser Karte in der Liste
    der bereits ueber ``szene_claude.ist_aktiv`` geroutenen Module -- anders
    als Szene, Kurzgeschichte, Stueckpruefung und die Buehnenkarten rief sie
    ausschliesslich ``klm.prosa`` (Kimi), nie den Proxy."""
    repo.setze_phase(conn, CHAT, 4)
    _stimme_zu(conn)
    gesehen = {}

    def claude_prosa(conn_, e_, klient, chat_id, system, nutzer, art, timeout, bei_teil=None):
        gesehen["art"] = art
        return "VORSCHLAG SZENENFOLGE:\nSzene 1 -- Am Bahnhof"

    monkeypatch.setattr(szene_claude, "prosa", claude_prosa)
    klm = _LLMAttrappe()
    tg = _TelegramAttrappeFolge()
    thread = szenenfolge.starte(conn, tg, klm, opus_e, CHAT, anzahl=1)
    assert thread is not None
    thread.join(timeout=5)
    assert klm.aufrufe == 0
    assert gesehen.get("art") == szenenfolge.ART


def test_ohne_ueber_claude_laeuft_unveraendert_auf_kimi(conn, einst):
    klm = _KLM()
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, einst, CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
        ueber_claude=False,
    )
    assert ergebnis == {"antwort": "von Kimi"}
    assert klm.gesehen == ["gespraech"]


# --------------------------------------------------------------------------
# Prompt-Cache: cache_control auf dem System-Block
# --------------------------------------------------------------------------


def test_cache_control_steht_auf_dem_system_block(conn, opus_e):
    gesehen = {}

    def handler(anfrage):
        gesehen["body"] = json.loads(anfrage.content)
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "Text"}],
            "usage": {"input_tokens": 10, "output_tokens": 2},
            "stop_reason": "end_turn",
        })

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    szene_claude.prosa(conn, opus_e, klient, CHAT, "sys", "nutz", "szene", timeout=5)
    system = gesehen["body"]["system"]
    assert isinstance(system, list)
    assert system[0]["text"] == "sys"
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_schema_ueber_claude_entpackt_json_aus_freiem_text(conn, opus_e):
    def handler(anfrage):
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": '{"eintrag_nummern": [1]}'}],
            "usage": {"input_tokens": 10, "output_tokens": 2},
            "stop_reason": "end_turn",
        })

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    ergebnis = szene_claude.schema(
        conn, opus_e, klient, CHAT, "sys", "nutz", {"type": "object"},
        "schaerfung", timeout=5,
    )
    assert ergebnis == {"eintrag_nummern": [1]}


# --------------------------------------------------------------------------
# Kontextbudget: ein groesseres Fenster fuer Opus, Kimi unveraendert
# --------------------------------------------------------------------------


def test_opus_budget_ist_viel_groesser_als_kimi(monkeypatch):
    monkeypatch.delenv("IT_PROMPT_ZEICHEN", raising=False)
    monkeypatch.delenv("IT_PROMPT_ZEICHEN_GESAMT", raising=False)
    monkeypatch.delenv("IT_OPUS_PROMPT_ZEICHEN", raising=False)
    assert kontext.zeichengrenze(False) == kontext.ZEICHEN_GRENZE_VORGABE
    assert kontext.gesamtgrenze(False) == kontext.GESAMT_ZEICHEN_GRENZE_VORGABE
    assert kontext.zeichengrenze(True) == kontext.OPUS_ZEICHEN_GRENZE_VORGABE
    assert kontext.gesamtgrenze(True) > kontext.gesamtgrenze(False)


def test_opus_budget_liest_eigene_umgebungsvariable(monkeypatch):
    monkeypatch.setenv("IT_OPUS_PROMPT_ZEICHEN", "123000")
    monkeypatch.delenv("IT_PROMPT_ZEICHEN", raising=False)
    assert kontext.zeichengrenze(True) == 123_000
    assert kontext.gesamtgrenze(True) == 123_000
    # Die Kimi-Grenze liest eine ANDERE Variable -- unberuehrt.
    assert kontext.zeichengrenze(False) == kontext.ZEICHEN_GRENZE_VORGABE


# --------------------------------------------------------------------------
# Kostendeckel: Claude-ueber-Abo zaehlt nicht mit
# --------------------------------------------------------------------------


def test_ist_abo_modus():
    assert kosten.ist_abo_modus("C") is True
    assert kosten.ist_abo_modus("A") is False
    assert kosten.ist_abo_modus(None) is False


def test_claude_aufruf_sprengt_den_tagesdeckel_nicht(conn, opus_e):
    # Ein Aufruf mit riesigen Tokenzahlen, aber modus 'C' und kosten_chf=0
    # (wie szene_claude._buche es bucht) -- der Deckel darf das nicht sehen.
    repo.merke_aufruf(
        conn, CHAT, "gespraech", modus="C", geschaetzte_token=5_000_000,
        tatsaechliche_token=5_000_000, antwort_token=200_000, finish_reason="end_turn",
        dauer_ms=1000, erfolg=1, modell="claude-opus-5",
        kosten_chf=kosten.CLAUDE_CHF_JE_AUFRUF,
    )
    assert kosten.deckel_erreicht(conn, CHAT, opus_e) is False


# --------------------------------------------------------------------------
# Einwilligungsfrage beim Uebergang 3 -> 4
# --------------------------------------------------------------------------


class _TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self._id = 500

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        self.gesendet.append((chat_id, text))
        self.knoepfe.append((chat_id, text, list(knoepfe_)))
        self._id += 1
        return self._id


def _angebot_texte(tg):
    return [t for _, t in tg.gesendet
            if t == knoepfe.texte.T._TEXT_ANGEBOT_MODELLWAHL]


def test_konsensfrage_kommt_beim_uebergang_3_zu_4(conn, opus_e):
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, knoepfe.PHASE_SETTING)
    assert len(_angebot_texte(tg)) == 1
    assert len(tg.knoepfe) == 1
    assert repo.szene_usa_stand(conn, CHAT) == "offen"


def test_konsensfrage_kommt_nur_einmal(conn, opus_e):
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, knoepfe.PHASE_SETTING)
    # Zweiter Eintritt in dieselbe Phase (z. B. ein erneuter Klick, /phase 4
    # ein zweites Mal): keine zweite Frage.
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, knoepfe.PHASE_SETTING)
    assert len(_angebot_texte(tg)) == 1


def test_alte_einwilligung_gilt_weiter_keine_neue_frage(conn, opus_e):
    """Eine Gruppe, die (z. B. ueber den alten Szenen-Weg) schon geantwortet
    hat, bekommt beim Eintritt in Phase 4 keine zweite Frage."""
    _stimme_zu(conn, ja=True)
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, knoepfe.PHASE_SETTING)
    assert _angebot_texte(tg) == []
    assert repo.szene_usa_stand(conn, CHAT) == "ja"


def test_nein_wird_nie_wieder_gefragt(conn, opus_e):
    _stimme_zu(conn, ja=False)
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, knoepfe.PHASE_SETTING)
    assert _angebot_texte(tg) == []
    assert repo.szene_usa_stand(conn, CHAT) == "nein"
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False


def test_ohne_betreiberschalter_wird_nicht_gefragt(conn, einst):
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, einst, CHAT, knoepfe.PHASE_SETTING)
    assert _angebot_texte(tg) == []
    assert repo.szene_usa_stand(conn, CHAT) == "offen"


def test_phase_4_eintritt_blockiert_nicht_auf_die_antwort(conn, opus_e):
    """Entscheidend: der Eintritt selbst (Karte, Einleitung) findet trotz
    offener Frage statt -- nur das Gespraech bleibt bis zur Antwort auf
    Kimi (separat getestet in konversation_ueber_claude)."""
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, knoepfe.PHASE_SETTING)
    assert len(tg.gesendet) >= 2  # Karte/Einleitung + die Modellwahl-Frage
    assert modellwahl.konversation_ueber_claude(opus_e, conn, CHAT) is False


# --------------------------------------------------------------------------
# Einwilligungsfrage wandert auf den Eintritt in Phase 1 (03.10.2026, Padua
# Phase 1+2 Karte) -- dieselbe Spalte, derselbe Knopfweg, keine zweite Frage.
# --------------------------------------------------------------------------


def test_konsensfrage_kommt_jetzt_bei_phase_1(conn, opus_e):
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, PHASE_BEGRIFFE)
    assert len(_angebot_texte(tg)) == 1
    assert len(tg.knoepfe) == 1
    assert repo.szene_usa_stand(conn, CHAT) == "offen"


def test_phase_1_konsensfrage_nur_einmal_phase_4_fragt_nicht_erneut(conn, opus_e):
    """Nach der Frage beim Phase-1-Eintritt bleibt das alte Sicherheitsnetz
    in PHASE_SETTING ein No-Op -- genau wie der laengst bestehende
    PHASE_SZENEN-Zweig es schon ist."""
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, PHASE_BEGRIFFE)
    assert len(_angebot_texte(tg)) == 1
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, knoepfe.PHASE_SETTING)
    assert len(_angebot_texte(tg)) == 1


def test_phase_1_ohne_angebot_faellig_begriffe_kickoff_laeuft_trotzdem(conn, opus_e):
    """Schon beantwortet (hier: ueber den alten Weg) -- Phase 1 fragt nicht
    noch einmal, aber der deterministische Begriffe-Einstieg (ohne ``klm``,
    also ohne den modellgetriebenen Erstkontakt-Zug) laeuft unveraendert
    weiter."""
    _stimme_zu(conn, ja=True)
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, opus_e, CHAT, PHASE_BEGRIFFE)
    assert _angebot_texte(tg) == []
    assert any(
        knoepfe.texte.T._TEXT_PROAKTIV in text for _, text in tg.gesendet
    )


def test_phase_1_ohne_betreiberschalter_wird_nicht_gefragt(conn, einst):
    tg = _TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, einst, CHAT, PHASE_BEGRIFFE)
    assert _angebot_texte(tg) == []
    assert repo.szene_usa_stand(conn, CHAT) == "offen"


# --------------------------------------------------------------------------
# Padua Modellwahl-Nachtrag: Einwilligungsfrage komplett abschaltbar
# (``workshop.modellwahl_einwilligung_aktiv`` = False)
# --------------------------------------------------------------------------


def test_padua_ist_aktiv_ohne_einwilligung_und_ohne_repo_aufruf(conn, opus_e_padua):
    """Betreiber erlaubt Claude, Padua-Profil aktiv -- ``ist_aktiv`` ist
    True, OHNE dass ``repo.setze_szene_usa`` je aufgerufen wurde. Gilt auch
    ganz ohne conn/chat_id."""
    assert szene_claude.ist_aktiv(opus_e_padua, conn, CHAT) is True
    assert szene_claude.ist_aktiv(opus_e_padua) is True


@pytest.mark.parametrize("phase", [1, 4])
def test_padua_angebot_faellig_ist_immer_false(conn, opus_e_padua, phase):
    repo.setze_phase(conn, CHAT, phase)
    assert szene_claude.angebot_faellig(opus_e_padua, conn, CHAT) is False


def test_padua_wartet_auf_antwort_ist_false(conn, opus_e_padua):
    assert szene_claude.wartet_auf_antwort(opus_e_padua, conn, CHAT) is False


def test_padua_warnung_nicht_angebracht_obwohl_claude_aktiv(conn, opus_e_padua):
    """Claude laeuft (``ist_aktiv`` True), aber die Warnung vor der US-
    Datenuebermittlung waere eine Antwort auf eine nie gestellte Frage."""
    assert szene_claude.ist_aktiv(opus_e_padua, conn, CHAT) is True
    assert szene_claude.warnung_angebracht(opus_e_padua, conn, CHAT) is False


def test_dortmund_warnung_angebracht_wenn_zugestimmt(conn, opus_e):
    """Regression: unter Dortmund/Vorgabe bleibt die Warnung an die
    Einwilligung gekoppelt -- ohne Zustimmung keine Warnung, mit
    Zustimmung schon (weil ``ist_aktiv`` dort weiterhin True wird)."""
    assert szene_claude.warnung_angebracht(opus_e, conn, CHAT) is False
    _stimme_zu(conn)
    assert szene_claude.warnung_angebracht(opus_e, conn, CHAT) is True


def test_padua_szene_usa_nicht_im_schema(padua):
    assert "szene_usa" not in erkenner.arten_fuer_schema()


def test_dortmund_szene_usa_weiterhin_im_schema(einst):
    assert "szene_usa" in erkenner.arten_fuer_schema()


def test_dortmund_regression_ist_aktiv_haengt_weiterhin_an_der_einwilligung(
    conn, opus_e,
):
    """Zeigt, dass Task 2 den bestehenden Dortmund/Vorgabe-Pfad nicht
    gebrochen hat: ``ist_aktiv`` bleibt ohne Zustimmung False und wird erst
    nach ``repo.setze_szene_usa`` True."""
    assert szene_claude.ist_aktiv(opus_e, conn, CHAT) is False
    repo.setze_szene_usa(conn, CHAT, True)
    assert szene_claude.ist_aktiv(opus_e, conn, CHAT) is True


# --------------------------------------------------------------------------
# Padua Modellwahl, Zitate ab Phase 5: ``szene._kernpaket_text`` entfernt
# den woertlichen Zitattext fuer einen Claude-Zug, wenn der Profilschalter
# ``workshop.modellwahl_zitate_an_claude_aktiv`` aus ist -- Thema/Zuordnung
# bleiben, und der Schalter wirkt nur, wenn der Zug wirklich ueber Claude
# laeuft (Task 3 dieser Karte).
# --------------------------------------------------------------------------


def _verdichtung_mit_zitat(
    conn, chat_id=CHAT, message_id=90, thema="Arbeit ohne Anerkennung",
    zitat="Keiner hat gefragt",
):
    """Legt eine Aufnahme mit einer geprueften Verdichtung an und liefert
    ``(aufnahme_id, verdichtung_thema_id)`` -- die gemeinsame Grundlage fuer
    den Schaerfung- und den globalen Kernzitat-Zweig von
    ``szene._kernpaket_text``."""
    repo.merke_nachricht(
        conn, chat_id, message_id, "Ada", 0, "sprache", None,
        "2026-10-04T10:00:00+00:00",
    )
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "lang", "sprache", "/tmp/a.ogg", 300,
    )
    repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id, "Zusammenfassung des Interviews.",
        [{"thema": thema, "beleg_zitat": zitat, "zitat_geprueft": 1}],
    )
    thema_row = next(
        t for t in repo.gepruefte_themen(conn, chat_id) if t["thema"] == thema
    )
    return aufnahme_id, thema_row["id"]


def _schaerfung_mit_zitat(
    conn, chat_id=CHAT, message_id=90, zitat="Keiner hat gefragt",
    begruendung="genau der Einsatz",
):
    """Eine Szene mit genau einer Schaerfung -- der ``ziel``-Zweig von
    ``_kernpaket_text``. Liefert ``ziel`` als Dict mit ``id``, wie
    ``baue_nutzertext`` es uebergibt."""
    _aufnahme_id, thema_id = _verdichtung_mit_zitat(
        conn, chat_id, message_id=message_id, zitat=zitat,
    )
    szene_id = repo.lege_szene_an(conn, chat_id, 1, "Am Platz", None, None)
    repo.lege_schaerfung_an(conn, chat_id, [
        {"verdichtung_thema_id": thema_id, "szene_id": szene_id,
         "begruendung": begruendung},
    ])
    return {"id": szene_id}


def _kernzitat_global(
    conn, chat_id=CHAT, message_id=91, zitat="Keiner hat gefragt",
    begruendung="genau der Einsatz",
):
    """Der globale Fallback-Zweig (ohne ``ziel``): Kernthema + Kernzitat."""
    aufnahme_id, thema_id = _verdichtung_mit_zitat(
        conn, chat_id, message_id=message_id, zitat=zitat,
    )
    repo.markiere_themen_zum_kernthema(conn, chat_id, [thema_id])
    repo.ersetze_kernzitate(
        conn, chat_id,
        [{"verdichtung_thema_id": thema_id, "aufnahme_id": aufnahme_id,
          "zitat": zitat, "begruendung": begruendung}],
    )


def test_kernpaket_text_unveraendert_ohne_zitate_entfernen(conn):
    """Regression: ohne ``zitate_entfernen`` (Vorgabe False) steht der
    woertliche Zitattext weiterhin in Anfuehrungszeichen -- im
    Schaerfung-Zweig (mit ``ziel``) wie im globalen Fallback (ohne
    ``ziel``)."""
    ziel = _schaerfung_mit_zitat(conn, message_id=90)
    text_schaerfung = szene._kernpaket_text(conn, CHAT, ziel)
    assert '"Keiner hat gefragt"' in text_schaerfung
    assert "genau der Einsatz" in text_schaerfung

    _kernzitat_global(conn, message_id=91)
    text_global = szene._kernpaket_text(conn, CHAT, None)
    assert '"Keiner hat gefragt"' in text_global
    assert "genau der Einsatz" in text_global


def test_kernpaket_text_entfernt_zitate_in_beiden_zweigen(conn):
    """Mit ``zitate_entfernen=True`` steht das woertliche Zitat in keiner
    Zeile mehr -- Thema/Name/Zuordnung und ``begruendung`` bleiben."""
    ziel = _schaerfung_mit_zitat(conn, message_id=90)
    text_schaerfung = szene._kernpaket_text(
        conn, CHAT, ziel, zitate_entfernen=True,
    )
    assert "Keiner hat gefragt" not in text_schaerfung
    assert "Arbeit ohne Anerkennung" in text_schaerfung
    assert "genau der Einsatz" in text_schaerfung

    _kernzitat_global(conn, message_id=91)
    text_global = szene._kernpaket_text(conn, CHAT, None, zitate_entfernen=True)
    assert "Keiner hat gefragt" not in text_global
    assert "genau der Einsatz" in text_global


def test_baue_nutzertext_ueber_claude_entfernt_zitat_ohne_schalter(
    conn, opus_e, monkeypatch,
):
    """Integration: laeuft der Zug wirklich ueber Claude (``ist_aktiv`` ==
    True) und ist der Betreiberschalter aus, enthaelt der Volltext von
    ``baue_nutzertext`` das Zitat nicht mehr woertlich."""
    monkeypatch.setattr(
        workshop, "modellwahl_zitate_an_claude_aktiv", lambda *a, **k: False,
    )
    _stimme_zu(conn)
    _kernzitat_global(conn)
    assert szene_claude.ist_aktiv(opus_e, conn, CHAT) is True

    text = szene.baue_nutzertext(conn, CHAT, "Szene 1: der Platz", e=opus_e)

    assert "Keiner hat gefragt" not in text


def test_baue_nutzertext_kimi_zeigt_zitat_trotz_abgeschaltetem_schalter(
    conn, einst, monkeypatch,
):
    """Der Schalter wirkt NUR, wenn der Zug wirklich ueber Claude laeuft --
    bei Kimi (``ist_aktiv`` == False) steht das Zitat trotzdem da."""
    monkeypatch.setattr(
        workshop, "modellwahl_zitate_an_claude_aktiv", lambda *a, **k: False,
    )
    _kernzitat_global(conn)
    assert szene_claude.ist_aktiv(einst, conn, CHAT) is False

    text = szene.baue_nutzertext(conn, CHAT, "Szene 1: der Platz", e=einst)

    assert '"Keiner hat gefragt"' in text
