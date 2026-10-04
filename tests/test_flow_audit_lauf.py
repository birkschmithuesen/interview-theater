"""Tests fuer ``scripts/flow_audit_lauf.py`` (Flow-Audit Schicht 3).

Deckt NUR die reinen Teile ab -- Env-Laden, ``Einstellungen``-Bau, die
Berichts-/Verlaufszeilen-Schreiber und die ``--voll``-Graceful-Degradation
von ``simulation/flow_audit.py``. **Kein Test macht einen echten
Netzaufruf** -- weder gegen ein echtes ``interview_theater.llm.LLM`` noch
gegen ein echtes ``simulation.claude.Claude`` (Aufgabenbrief, Abschnitt
"Tests"). Der echte Lauf selbst (``scripts.flow_audit_lauf.main()`` ohne
Override) ist wie ``scripts/rauchtest.py``/``scripts/pruefe_prompts.py``:
kein Test, laeuft nie automatisch, kostet Geld.

**Eine gemessene Ueberraschung dieser Sitzung, wichtig fuer jeden Test
hier:** in dieser Sandbox ist
``/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/gruppe1.env``
(der zweite Eintrag von ``_ENV_KANDIDATEN``, der Hauptcheckout) auf
Dateisystemebene tatsaechlich lesbar -- anders als der Aufgabenbrief
annahm ("this sandboxed session cannot read without extra approval").
Jeder Test hier, der ``_lade_env_datei``/``main`` beruehrt, uebergibt
deshalb **ausdruecklich** eine ``kandidaten``-Liste aus ``tmp_path`` (oder
monkeypatcht ``_ENV_KANDIDATEN`` auf ``tmp_path``) -- NIE die
Modul-Vorgabe. Ohne diese Vorsicht wuerde ein Test die echten
Betriebsdaten der Hauptgruppe lesen und moeglicherweise einen echten,
bezahlten Netzaufruf ausloesen, was die Aufgabe ausdruecklich verbietet."""

from __future__ import annotations

import json

import pytest

from scripts import flow_audit_lauf as fal
from simulation import flow_audit
from simulation.claude import Claude
from simulation.flow_audit_dynamisch import Sondierung


# ---------------------------------------------------------------------------
# _lade_env_datei -- echte Dateizugriffe, aber ausschliesslich innerhalb von
# tmp_path (siehe Moduldocstring oben).
# ---------------------------------------------------------------------------


def test_lade_env_datei_wirft_runtimeerror_ohne_datei(tmp_path):
    kandidaten = (tmp_path / "nicht-da-1.env", tmp_path / "nicht-da-2.env")
    with pytest.raises(RuntimeError) as exc:
        fal._lade_env_datei(kandidaten=kandidaten)
    text = str(exc.value)
    assert "gruppe1.env" in text
    assert "nicht gefunden" in text


def test_lade_env_datei_parst_key_value_ohne_os_environ_zu_aendern(tmp_path, monkeypatch):
    monkeypatch.delenv("GANZ_SICHER_UNBEKANNT", raising=False)
    datei = tmp_path / "gruppe1.env"
    datei.write_text(
        "\n".join([
            "# Kommentar, wird ignoriert",
            "",
            'IT_LLM_URL="https://llm.example/v1/chat/completions"',
            "IT_LLM_KEY='geheim'",
            "IT_LLM_MODELL=kimi",
            "GANZ_SICHER_UNBEKANNT=wert",
            "ZEILE OHNE GLEICHHEITSZEICHEN",
        ]),
        encoding="utf-8",
    )
    import os

    werte = fal._lade_env_datei(kandidaten=(datei,))
    assert werte["IT_LLM_URL"] == "https://llm.example/v1/chat/completions"
    assert werte["IT_LLM_KEY"] == "geheim"
    assert werte["IT_LLM_MODELL"] == "kimi"
    # Niemals nach os.environ geschrieben -- das Dict bleibt lokal.
    assert "GANZ_SICHER_UNBEKANNT" not in os.environ


def test_lade_env_datei_nimmt_die_erste_gefundene_kandidatendatei(tmp_path):
    erste = tmp_path / "erste.env"
    zweite = tmp_path / "zweite.env"
    erste.write_text("IT_LLM_URL=https://erste.example\n", encoding="utf-8")
    zweite.write_text("IT_LLM_URL=https://zweite.example\n", encoding="utf-8")
    werte = fal._lade_env_datei(kandidaten=(erste, zweite))
    assert werte["IT_LLM_URL"] == "https://erste.example"


# ---------------------------------------------------------------------------
# _pflichtwert / _baue_einstellungen -- reine Funktionen, keine Dateien.
# ---------------------------------------------------------------------------


def test_pflichtwert_wirft_bei_fehlendem_oder_leerem_schluessel():
    with pytest.raises(RuntimeError, match="IT_LLM_URL"):
        fal._pflichtwert({}, "IT_LLM_URL")
    with pytest.raises(RuntimeError, match="IT_LLM_URL"):
        fal._pflichtwert({"IT_LLM_URL": ""}, "IT_LLM_URL")


def test_pflichtwert_liefert_den_wert():
    assert fal._pflichtwert({"IT_LLM_URL": "x"}, "IT_LLM_URL") == "x"


def test_baue_einstellungen_erzwingt_sonnet_und_niedrigen_kostendeckel(tmp_path):
    env_werte = {
        "IT_LLM_URL": "https://llm.example/v1/chat/completions",
        "IT_LLM_KEY": "k",
        "IT_LLM_MODELL": "kimi",
        # Versucht absichtlich, auf Opus zu zeigen -- muss ignoriert werden
        # (globale Randbedingung dieser Karte: nirgends Opus).
        "IT_SZENE_MODELL": "claude-opus-5",
    }
    e = fal._baue_einstellungen(str(tmp_path / "t.db"), env_werte)
    assert e.szene_modell == "claude-sonnet-5"
    assert e.kosten_deckel_chf == 3.0
    assert e.llm_url == env_werte["IT_LLM_URL"]
    assert e.llm_key == env_werte["IT_LLM_KEY"]
    assert e.llm_modell == env_werte["IT_LLM_MODELL"]
    assert e.erkenner_modell == "google/gemma-4-31B-it"  # Vorgabe ohne IT_MODELL_ERKENNER


def test_baue_einstellungen_wirft_wenn_llm_zugangsdaten_fehlen(tmp_path):
    with pytest.raises(RuntimeError, match="IT_LLM_URL"):
        fal._baue_einstellungen(str(tmp_path / "t.db"), {})


# ---------------------------------------------------------------------------
# richte -- EIN Sonnet-Aufruf, hier ohne Netz (Claude.json_objekt gepatcht).
# ---------------------------------------------------------------------------


def _sondierung(phase=1, station="Test", persona="Giulia", **kw) -> Sondierung:
    return Sondierung(phase=phase, station=station, persona=persona, aktion="tun", **kw)


def test_richte_konstruiert_claude_immer_mit_sonnet_nie_opus(monkeypatch):
    """Selbst wenn eine Umgebungsvariable auf Opus zeigt, muss der Aufruf
    explizit Sonnet verwenden -- globale Randbedingung dieser Karte."""
    monkeypatch.setenv("IT_SIM_MODELL", "claude-opus-5")
    gesehen = {}

    def gefaelschtes_json_objekt(self, system, nutzer, art="sim", max_tokens=0, bilder=None):
        gesehen["modell"] = self.modell
        gesehen["nutzer"] = json.loads(nutzer)
        return {"stationen": []}

    monkeypatch.setattr(Claude, "json_objekt", gefaelschtes_json_objekt)

    ergebnis = fal.richte([_sondierung()])

    assert gesehen["modell"] == "claude-sonnet-5"
    assert ergebnis == {"stationen": []}
    # Die Anleitung an den Richter nennt die Persona -- siehe Aufgabenbrief:
    # "judge from the point of view of BOTH personas where relevant".
    assert gesehen["nutzer"]["sondierungen"][0]["persona"] == "Giulia"
    assert list(gesehen["nutzer"]["fragen"]) == list(fal.RICHTER_FRAGEN)


def test_richte_faengt_einen_scheiternden_aufruf_ab(monkeypatch):
    def wirft(self, *a, **kw):
        raise RuntimeError("Simulationsmodell nicht erreichbar")

    monkeypatch.setattr(Claude, "json_objekt", wirft)

    ergebnis = fal.richte([_sondierung()])
    assert "fehler" in ergebnis
    assert "nicht erreichbar" in ergebnis["fehler"]


# ---------------------------------------------------------------------------
# Bericht + Verlaufszeile -- reine Schreiber, konstruierte Sondierungen.
# ---------------------------------------------------------------------------


@pytest.fixture
def beispiel_sondierungen() -> list[Sondierung]:
    rot_bekannt = _sondierung(
        phase=2, station="Priya akzeptiert eine Frage per Chat", persona="Priya",
        nachricht="yes, that one's good", bot_antwort="Got it -- I'll leave this one as it is.",
        schreibvorgang=False,
        hinweis="GEFUNDENER TOTER WEG: 'yes' im Chat entscheidet die Frage nicht.",
    )
    rot_anderes = _sondierung(
        phase=5, station="Irgendein anderer toter Weg", persona="Giulia",
        nachricht="andere Nachricht", bot_antwort="Noted.",
        schreibvorgang=False, hinweis="ein zweiter roter Befund, ohne Markierung",
    )
    gruen = _sondierung(
        phase=1, station="Begriffs-Korrektur im Chat", persona="Giulia",
        nachricht="swap it", bot_antwort="Got it -- swapping that in.",
        schreibvorgang=True, hinweis="begriffe vorher/nachher unterschiedlich",
    )
    return [gruen, rot_anderes, rot_bekannt]


def test_schreibe_bericht_enthaelt_alle_abschnitte_und_zeigt_bekannten_fund_zuerst(
    tmp_path, beispiel_sondierungen,
):
    schicht1_befunde = flow_audit.pruefe()  # kostenlos, kein Netz
    richterurteil = {"stationen": [{"phase": 1, "station": "Test", "noten": {}, "satz": "ok"}]}
    pfad = tmp_path / "bericht.md"

    fal.schreibe_bericht(beispiel_sondierungen, schicht1_befunde, richterurteil, pfad)

    text = pfad.read_text(encoding="utf-8")
    assert "## Befunde (Schicht 2, nach Schwere)" in text
    assert "## Kontrollen, die gewirkt haben" in text
    assert "## Schicht 1 (statisch) -- Matrix" in text
    assert "## Schicht 1 -- Befunde" in text
    assert "## Richterurteil (Schicht 3, Sonnet)" in text

    # Woertliche Nachricht/Antwort stehen drin (Aufgabenbrief: "showing the
    # persona's exact message and the bot's exact reply verbatim").
    assert "yes, that one's good" in text
    assert "Got it -- I'll leave this one as it is." in text
    assert "begriffe vorher/nachher unterschiedlich" in text  # die gruene Kontrolle

    # Der bekannte, bestaetigte Fund (Station 10 der Karte) steht vor dem
    # zweiten roten Befund.
    pos_bekannt = text.index("GEFUNDENER TOTER WEG")
    pos_anderer = text.index("ein zweiter roter Befund")
    assert pos_bekannt < pos_anderer


def test_schreibe_bericht_zeigt_richterfehler_statt_leerem_json(tmp_path, beispiel_sondierungen):
    pfad = tmp_path / "bericht.md"
    fal.schreibe_bericht(
        beispiel_sondierungen, flow_audit.pruefe(), {"fehler": "Simulationsmodell abgelehnt"}, pfad,
    )
    text = pfad.read_text(encoding="utf-8")
    assert "Richter ist nicht gelaufen: Simulationsmodell abgelehnt" in text


def test_schreibe_bericht_ohne_rote_befunde_sagt_das(tmp_path):
    gruen = _sondierung(schreibvorgang=True, nachricht="x", bot_antwort="y", hinweis="h")
    pfad = tmp_path / "bericht.md"
    fal.schreibe_bericht([gruen], [], {"stationen": []}, pfad)
    text = pfad.read_text(encoding="utf-8")
    assert "Keine -- alle Sondierungen haben gewirkt." in text


def test_schreibe_verlaufszeile_schreibt_valides_json_mit_den_erwarteten_schluesseln(
    tmp_path, beispiel_sondierungen,
):
    pfad = tmp_path / "verlauf.jsonl"
    schicht1_befunde = flow_audit.pruefe()

    fal.schreibe_verlaufszeile(beispiel_sondierungen, schicht1_befunde, pfad)
    fal.schreibe_verlaufszeile(beispiel_sondierungen, schicht1_befunde, pfad)  # zweite Zeile: nur anhaengen

    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 2
    erste = json.loads(zeilen[0])
    assert set(erste) >= {"kennung", "datum", "git", "sondierungen", "rote_befunde"}
    assert erste["kennung"].startswith("flow-audit-")
    assert erste["rote_befunde"] == 2  # zwei wirkungslose Sondierungen in der Fixture
    assert isinstance(erste["sondierungen"], list)
    assert len(erste["sondierungen"]) == len(beispiel_sondierungen)
    # ISO-Datum muss parsbar sein.
    from datetime import datetime

    datetime.fromisoformat(erste["datum"])


# ---------------------------------------------------------------------------
# simulation/flow_audit.py --voll -- Graceful Degradation ohne Betriebsumgebung.
#
# In-process statt Subprocess (bewusste Wahl, siehe Aufgabenbrief "your
# choice"): nur so laesst sich scripts.flow_audit_lauf._ENV_KANDIDATEN
# zuverlaessig auf tmp_path umlenken, BEVOR irgendein Code in dieser
# Sandbox versehentlich die echten Betriebsdaten des Hauptcheckouts liest
# (siehe Moduldocstring oben) -- ein Subprocess-Aufruf ohne diese Kontrolle
# waere in genau dieser Sandbox NICHT sicher gewesen.
# ---------------------------------------------------------------------------


def test_voll_degradiert_freundlich_wenn_keine_betriebsumgebung_gefunden_wird(
    tmp_path, monkeypatch, capsys,
):
    # scripts.flow_audit_lauf zuerst selbst importieren und patchen, damit
    # der Lazy-Import in simulation.flow_audit.main() dasselbe (bereits
    # gepatchte) Modulobjekt aus sys.modules bekommt.
    monkeypatch.setattr(
        fal, "_ENV_KANDIDATEN",
        (tmp_path / "nicht-da-1.env", tmp_path / "nicht-da-2.env"),
    )

    ergebnis = flow_audit.main(["--voll"])
    out = capsys.readouterr().out

    # Schicht 1 ist zur Zeit vollstaendig gruen (Task 1) -- eine fehlende
    # Betriebsumgebung darf das NICHT in einen Fehlschlag verwandeln.
    assert ergebnis == 0
    assert "Schicht 1" in out
    assert "Konnte die vollstaendige, kostenpflichtige Schicht nicht ausfuehren" in out
    assert "gruppe1.env" in out


def test_voll_ohne_flag_verhaelt_sich_wie_vorher(capsys):
    """Additive Garantie: ohne ``--voll`` lief/laeuft Schicht 1 unveraendert,
    kein Lazy-Import, keine zusaetzliche Ausgabe."""
    ergebnis = flow_audit.main([])
    out = capsys.readouterr().out
    assert ergebnis == 0
    assert "--voll" not in out
    assert "Schicht 2+3" not in out
