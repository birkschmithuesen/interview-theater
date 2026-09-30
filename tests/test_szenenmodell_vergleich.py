"""Tests fuer ``scripts/szenenmodell_vergleich.py`` (Padua M2).

Kein Netz: jeder HTTP-Aufruf laeuft ueber ``httpx.MockTransport``. Die
Wartezeiten zwischen Retries werden auf leer gepatcht, damit ein Test mit
429/5xx nicht Sekunden braucht."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts import szenenmodell_vergleich as smv
from interview_theater import szene_claude


@pytest.fixture(autouse=True)
def _keine_wartezeit(monkeypatch):
    """Kein Test soll echte Sekunden schlafen -- WARTEZEITEN auf einen
    kurzen, aber nicht-leeren Wert patchen (ein Retry bleibt moeglich)."""
    monkeypatch.setattr(szene_claude, "WARTEZEITEN", (0.0, 0.0))


def _antwort(text: str = "TITEL: X\n\nMIRA: Hallo.", stop_reason: str = "end_turn",
             eingabe: int = 100, ausgabe: int = 20) -> httpx.Response:
    return httpx.Response(200, json={
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "usage": {"input_tokens": eingabe, "output_tokens": ausgabe},
    })


def _klient_fabrik(handler):
    """Ersetzt ``httpx.Client`` im Modul durch einen MockTransport-Klienten,
    unabhaengig von den Konstruktor-Kwargs (z.B. ``timeout=``).

    Die echte Klasse wird VOR dem Patchen eingefangen -- ``smv.httpx`` ist
    das globale ``httpx``-Modul, ``monkeypatch.setattr(smv.httpx, "Client",
    fabrik)`` ersetzt also ``httpx.Client`` ueberall. Ein Aufruf von
    ``httpx.Client(...)`` INNERHALB von ``fabrik`` liefe sonst gegen sich
    selbst (RecursionError)."""
    echter_client = httpx.Client

    def fabrik(*args, **kwargs):
        return echter_client(transport=httpx.MockTransport(handler))
    return fabrik


# ---------------------------------------------------------------------------
# pfad (kein Netz)
# ---------------------------------------------------------------------------


def test_pfad_schreibt_prompt_mit_meryem_und_prosavorlage(tmp_path):
    rc = smv.main(["pfad", "--ausgabe", str(tmp_path)])
    assert rc == 0
    text = (tmp_path / "prompt.txt").read_text()
    assert "Meryem" in text
    from scripts import sprachstil_wirkung as sw
    assert sw.PROSA[1] in text


def test_pfad_druckt_profilnamen_und_sha(tmp_path, capsys):
    rc = smv.main(["pfad", "--ausgabe", str(tmp_path)])
    assert rc == 0
    ausgabe = capsys.readouterr().out
    assert "(eingebaut)" in ausgabe  # workshop.VORGABE_NAME, ohne IT_WORKSHOP


def test_pfad_bricht_ab_wenn_it_workshop_gesetzt_ist(tmp_path, monkeypatch):
    monkeypatch.setenv("IT_WORKSHOP", "irgendwas")
    rc = smv.main(["pfad", "--ausgabe", str(tmp_path)])
    assert rc == 1
    assert not (tmp_path / "prompt.txt").exists()


# ---------------------------------------------------------------------------
# lauf (Netz ueber MockTransport abgefangen)
# ---------------------------------------------------------------------------


def test_beide_modelle_bekommen_identisches_system_und_messages(tmp_path, monkeypatch):
    koerper: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in {k.lower() for k in request.headers}
        assert request.headers["anthropic-version"] == szene_claude.API_VERSION
        koerper.append(json.loads(request.content))
        return _antwort()

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "1", "--ausgabe", str(tmp_path)])
    assert rc == 0
    assert len(koerper) == 2
    a, b = koerper
    assert a["model"] != b["model"]
    assert {a["model"], b["model"]} == set(smv.MODELLE)
    assert a["system"] == b["system"]
    assert a["messages"] == b["messages"]
    assert a["max_tokens"] == szene_claude.MAX_TOKENS
    assert b["max_tokens"] == szene_claude.MAX_TOKENS

    for modell in smv.MODELLE:
        satz = json.loads((tmp_path / "laeufe" / f"{modell}-1.json").read_text())
        assert satz["status"] == "ok"
        assert satz["modell"] == modell
        assert satz["prompt_sha256"] == json.loads(
            (tmp_path / "laeufe" / f"{smv.MODELLE[0]}-1.json").read_text())["prompt_sha256"]


def test_reihenfolge_ist_je_lauf_verschraenkt(tmp_path, monkeypatch):
    reihenfolge: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        reihenfolge.append(json.loads(request.content)["model"])
        return _antwort()

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "2", "--ausgabe", str(tmp_path)])
    assert rc == 0
    # Lauf 1 beide Modelle, dann Lauf 2 beide Modelle -- nicht Modell 1 beide
    # Laeufe, dann Modell 2 beide Laeufe.
    assert reihenfolge == [smv.MODELLE[0], smv.MODELLE[1], smv.MODELLE[0], smv.MODELLE[1]]


def test_stop_reason_max_tokens_bleibt_ok_mit_text(tmp_path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(text="TITEL: X\n\nMIRA: Halber Sa", stop_reason="max_tokens")

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "1", "--modell", smv.MODELLE[0], "--ausgabe", str(tmp_path)])
    assert rc == 0
    satz = json.loads((tmp_path / "laeufe" / f"{smv.MODELLE[0]}-1.json").read_text())
    assert satz["status"] == "ok"
    assert satz["stop_reason"] == "max_tokens"
    assert satz["text"].startswith("TITEL: X")
    assert satz["zeichen"] == len(satz["text"])


def test_http_400_ergibt_fehler_ohne_wurf(tmp_path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "1", "--modell", smv.MODELLE[0], "--ausgabe", str(tmp_path)])
    assert rc == 1
    satz = json.loads((tmp_path / "laeufe" / f"{smv.MODELLE[0]}-1.json").read_text())
    assert satz["status"] == "fehler"
    assert "400" in satz["fehler"]
    assert satz["text"] == ""


def test_429_dann_erfolg_wird_gespeichert(tmp_path, monkeypatch):
    aufrufe = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        aufrufe["n"] += 1
        if aufrufe["n"] == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return _antwort()

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "1", "--modell", smv.MODELLE[0], "--ausgabe", str(tmp_path)])
    assert rc == 0
    assert aufrufe["n"] == 2
    satz = json.loads((tmp_path / "laeufe" / f"{smv.MODELLE[0]}-1.json").read_text())
    assert satz["status"] == "ok"
    assert satz["versuche"] == 2


def test_vorhandener_erfolgreicher_lauf_wird_uebersprungen(tmp_path, monkeypatch):
    laeufe = tmp_path / "laeufe"
    laeufe.mkdir(parents=True)
    system, nutzer = smv.baue_prompt()
    sha = smv._sha(system, nutzer)
    vorhanden = {
        "modell": smv.MODELLE[0], "lauf": 1, "status": "ok", "text": "schon da",
        "zeichen": 8, "dauer_s": 1.0, "prompt_sha256": sha, "versuche": 1,
    }
    (laeufe / f"{smv.MODELLE[0]}-1.json").write_text(json.dumps(vorhanden))

    aufgerufen = []

    def handler(request: httpx.Request) -> httpx.Response:
        aufgerufen.append(json.loads(request.content)["model"])
        return _antwort()

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "1", "--ausgabe", str(tmp_path)])
    assert rc == 0
    # das erste Modell war schon "ok" -- nur das zweite wird wirklich gerufen.
    assert aufgerufen == [smv.MODELLE[1]]


def test_abbruch_bei_abweichendem_prompt_sha(tmp_path, monkeypatch):
    laeufe = tmp_path / "laeufe"
    laeufe.mkdir(parents=True)
    (laeufe / f"{smv.MODELLE[0]}-1.json").write_text(json.dumps({
        "modell": smv.MODELLE[0], "lauf": 1, "status": "fehler",
        "prompt_sha256": "nicht-der-echte-hash",
    }))

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("es haette kein Aufruf stattfinden duerfen")

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "1", "--ausgabe", str(tmp_path)])
    assert rc == 1


def test_lauf_bricht_ab_wenn_it_workshop_gesetzt_ist(tmp_path, monkeypatch):
    monkeypatch.setenv("IT_WORKSHOP", "irgendwas")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("es haette kein Aufruf stattfinden duerfen")

    monkeypatch.setattr(smv.httpx, "Client", _klient_fabrik(handler))
    rc = smv.main(["lauf", "--n", "1", "--ausgabe", str(tmp_path)])
    assert rc == 1


# ---------------------------------------------------------------------------
# tabelle (kein Netz)
# ---------------------------------------------------------------------------


def _schreibe_lauf(ausgabe, modell, lauf, text, **rest):
    laeufe = ausgabe / "laeufe"
    laeufe.mkdir(parents=True, exist_ok=True)
    satz = {
        "modell": modell, "lauf": lauf, "status": "ok", "text": text,
        "zeichen": len(text), "dauer_s": 1.2, "stop_reason": "end_turn",
        "eingabe_token": 1000, "ausgabe_token": 200,
    }
    satz.update(rest)
    (laeufe / f"{modell}-{lauf}.json").write_text(json.dumps(satz, ensure_ascii=False))
    return satz


def test_tabelle_rechnet_zeichen_und_mechanik_richtig(tmp_path, capsys):
    text_1 = (
        "TITEL: Der Koffer\nKURZ: eine Kueche\nZUSAMMENFASSUNG: sie schweigen\n"
        "ANDERS GEMACHT: mehr Stille\n\n"
        "SZENE 1\nMERYEM: Ich bleibe.\nFERZAN: Nein.\n"
    )
    text_2 = "SZENE 1\nMERYEM: Ich bleibe.\n"  # keine Pflichtzeilen
    _schreibe_lauf(tmp_path, smv.MODELLE[0], 1, text_1)
    _schreibe_lauf(tmp_path, smv.MODELLE[1], 1, text_2)

    rc = smv.main(["tabelle", "--ausgabe", str(tmp_path)])
    assert rc == 0
    ausgabe = capsys.readouterr().out
    assert str(len(text_1)) in ausgabe
    assert str(len(text_2)) in ausgabe

    daten = json.loads((tmp_path / "auswertung.json").read_text())
    zeilen = {z["modell"]: z for z in daten["laeufe"]}
    assert zeilen[smv.MODELLE[0]]["zeichen"] == len(text_1)
    assert zeilen[smv.MODELLE[0]]["zusammenfassung_vorhanden"] is True
    assert zeilen[smv.MODELLE[0]]["anders_gemacht_vorhanden"] is True
    assert zeilen[smv.MODELLE[0]]["sprecherzeilen"] == 2  # MERYEM:, FERZAN:
    assert zeilen[smv.MODELLE[1]]["zeichen"] == len(text_2)
    assert zeilen[smv.MODELLE[1]]["zusammenfassung_vorhanden"] is False
    assert zeilen[smv.MODELLE[1]]["anders_gemacht_vorhanden"] is False
    assert zeilen[smv.MODELLE[1]]["sprecherzeilen"] == 1

    for modell in smv.MODELLE:
        stat = daten["je_modell"][modell]
        assert stat["n"] == 1


def test_tabelle_zaehlt_auch_fehlgeschlagene_laeufe_ohne_absturz(tmp_path):
    """Ein fehlgeschlagener Lauf (leerer Text) hat ein JSON und gehoert damit
    zur Tabelle -- ``_mechanik`` auf leerem Text darf nicht abstuerzen, und
    die Zeile zaehlt in der Statistik mit (zeichen=0)."""
    _schreibe_lauf(tmp_path, smv.MODELLE[0], 1, "ein Text", status="ok")
    _schreibe_lauf(tmp_path, smv.MODELLE[0], 2, "", status="fehler", fehler="HTTP 400")
    rc = smv.main(["tabelle", "--ausgabe", str(tmp_path)])
    assert rc == 0
    daten = json.loads((tmp_path / "auswertung.json").read_text())
    assert len(daten["laeufe"]) == 2
    stat = daten["je_modell"][smv.MODELLE[0]]
    assert stat["n"] == 2
    assert stat["zeichen"]["min"] == 0
