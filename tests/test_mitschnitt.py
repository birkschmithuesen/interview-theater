"""Das mitschreibende Double: Signaturtreue und Patchwirkung."""
import httpx
import pytest

from interview_theater import einstellungen, llm, szene_claude
from scripts import mitschnitt as ms


def _e():
    return einstellungen.Einstellungen(
        bot_token="x", bot_name="padua1", db_pfad=":memory:", audio_verz="audio",
        llm_url="http://127.0.0.1:1/chat/completions", llm_key="k",
        llm_modell="moonshotai/Kimi-K2.6", stt_basis="http://127.0.0.1:1",
        stt_produkt="p", erkenner_modell="google/gemma-4-31B-it",
        szene_anbieter="claude", szene_modell="claude-opus-5",
    )


def test_minimale_antwort_fuellt_jedes_pflichtfeld():
    schema = {
        "type": "object", "required": ["antwort", "liste", "zahl", "ja"],
        "properties": {
            "antwort": {"type": "string"},
            "liste": {"type": "array", "items": {"type": "string"}},
            "zahl": {"type": "integer"},
            "ja": {"type": "boolean"},
        },
    }
    assert ms.minimale_antwort(schema) == {
        "antwort": ms.PROSA_MARKE, "liste": [], "zahl": 0, "ja": False,
    }


def test_schema_zeichnet_auf_und_liefert_eine_gueltige_antwort():
    schnitt = ms.Mitschnitt(_e())
    schema = {"type": "object", "required": ["antwort"],
              "properties": {"antwort": {"type": "string"}}}
    ergebnis = schnitt.schema(1, "SYS", "NUTZ", schema, "gespraech")
    assert ergebnis["antwort"] == ms.PROSA_MARKE
    letzter = schnitt.letzter("gespraech")
    assert (letzter.system, letzter.nutzer) == ("SYS", "NUTZ")
    assert letzter.weg == "infomaniak"
    assert letzter.modell == "moonshotai/Kimi-K2.6"


def test_schema_mit_modell_zeichnet_das_gemma_modell_auf():
    schnitt = ms.Mitschnitt(_e())
    schnitt.schema(1, "S", "N", {"type": "object", "properties": {}}, "erkenner",
                   modell="google/gemma-4-31B-it")
    assert schnitt.letzter("erkenner").modell == "google/gemma-4-31B-it"


def test_prosa_zeichnet_auf():
    schnitt = ms.Mitschnitt(_e())
    assert schnitt.prosa(1, "S", "N", "szene") == ms.PROSA_MARKE
    assert schnitt.letzter("szene").weg == "infomaniak"


def test_fange_alles_leitet_den_claude_weg_um():
    schnitt = ms.Mitschnitt(_e())
    with ms.fange_alles(schnitt):
        szene_claude.prosa(None, _e(), None, 1, "S", "N", "szene", timeout=1.0)
        szene_claude.schema(
            None, _e(), None, 1, "S2", "N2",
            {"type": "object", "properties": {"antwort": {"type": "string"}}},
            "gespraech", timeout=1.0,
        )
    arten = [a.art for a in schnitt.aufrufe]
    assert arten == ["szene", "gespraech"]
    assert all(a.weg == "claude" for a in schnitt.aufrufe)
    assert all(a.modell == "claude-opus-5" for a in schnitt.aufrufe)


def test_fange_alles_ersetzt_auch_die_LLM_klasse_und_stellt_sie_zurueck():
    """``fanout.Richter.frage`` baut sich fuer den Richter selbst ein ``LLM``."""
    echt = llm.LLM
    schnitt = ms.Mitschnitt(_e())
    with ms.fange_alles(schnitt):
        assert llm.LLM is not echt
        gebaut = llm.LLM(_e(), httpx.Client(), None)
        gebaut.prosa(1, "S", "N", "dramaturgie_b1")
    assert llm.LLM is echt
    assert schnitt.letzter("dramaturgie_b1").weg == "infomaniak"


def test_double_hat_einen_klienten_platzhalter():
    """Sonst baut ``modellwahl.aufruf_schema`` je Aufruf einen echten Klienten."""
    assert ms.Mitschnitt(_e())._klient is not None
