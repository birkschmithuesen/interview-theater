"""ElevenLabs als zweiter STT-Weg (Nacht 07.10.2026, Padua-Ausfall Infomaniak
Whisper ab 10:48). Ohne ``stt_ersatz_schluessel`` bleibt der Weg bitgleich --
das deckt schon tests/test_stt.py mit der ``einst``-Fixture (kein Schluessel).
"""

import dataclasses
import json

import httpx
import pytest

from interview_theater import stt


def _klient(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _mit_ersatz(einst, **kw):
    return dataclasses.replace(einst, stt_ersatz_schluessel="EL_TESTSCHLUESSEL", **kw)


def test_fallback_bei_infomaniak_timeout(einst, tmp_path, monkeypatch):
    """Infomaniak haengt (bleibt 'processing'); nach dem Primaerbudget
    uebernimmt ElevenLabs mit dem Resttext."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    e = _mit_ersatz(einst, stt_infomaniak_budget_s=0.05)
    gesehen = {"elevenlabs": False}

    def handler(request):
        if "elevenlabs.io" in str(request.url):
            assert request.headers["xi-api-key"] == "EL_TESTSCHLUESSEL"
            gesehen["elevenlabs"] = True
            return httpx.Response(200, json={"text": "Vom Ersatzweg transkribiert."})
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={"status": "processing"})  # haengt dauerhaft

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS-testdaten")
    text = stt.transkribiere(e, _klient(handler), datei, 2.0)
    assert text == "Vom Ersatzweg transkribiert."
    assert gesehen["elevenlabs"] is True
    assert stt.letzter_anbieter() == "elevenlabs"


def test_ohne_schluessel_bitgleich_kein_elevenlabs_aufruf(einst, tmp_path, monkeypatch):
    """Ohne ``stt_ersatz_schluessel`` wird ElevenLabs nie angefragt -- auch
    nicht bei einem Infomaniak-Fehlschlag (bitgleicher Weg wie bisher)."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    aufrufe = {"elevenlabs": 0}

    def handler(request):
        if "elevenlabs.io" in str(request.url):
            aufrufe["elevenlabs"] += 1
            return httpx.Response(200, json={"text": "sollte nie passieren"})
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={"status": "failed"})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS-testdaten")
    with pytest.raises(stt.AuftragAbgebrochen):
        stt.transkribiere(einst, _klient(handler), datei, 2.0)
    assert aufrufe["elevenlabs"] == 0
    assert stt.letzter_anbieter() == "infomaniak"


def test_leeres_transkript_loest_keinen_fallback_aus(einst, tmp_path, monkeypatch):
    """Ein erfolgreicher Infomaniak-Auftrag mit leerem Text ist Stille, kein
    Dienstausfall -- ElevenLabs darf dafuer nicht anlaufen."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    e = _mit_ersatz(einst)
    aufrufe = {"elevenlabs": 0}

    def handler(request):
        if "elevenlabs.io" in str(request.url):
            aufrufe["elevenlabs"] += 1
            return httpx.Response(200, json={"text": "sollte nie passieren"})
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": "   "})})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS-testdaten")
    with pytest.raises(stt.LeeresTranskript):
        stt.transkribiere(e, _klient(handler), datei, 2.0)
    assert aufrufe["elevenlabs"] == 0


def test_it_stt_nur_ersatz_ueberspringt_infomaniak(einst, tmp_path, monkeypatch):
    """IT_STT_NUR_ERSATZ (stt_nur_ersatz=True): Infomaniak wird gar nicht
    erst angefragt -- Schalter fuer einen Totalausfall."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    e = _mit_ersatz(einst, stt_nur_ersatz=True)
    aufrufe = {"infomaniak": 0}

    def handler(request):
        if "elevenlabs.io" in str(request.url):
            return httpx.Response(200, json={"text": "Direkt von ElevenLabs."})
        aufrufe["infomaniak"] += 1
        return httpx.Response(200, json={"status": "success"})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS-testdaten")
    text = stt.transkribiere(e, _klient(handler), datei, 2.0)
    assert text == "Direkt von ElevenLabs."
    assert aufrufe["infomaniak"] == 0
    assert stt.letzter_anbieter() == "elevenlabs"


def test_transkribiere_elevenlabs_sendet_erwartete_felder(tmp_path):
    gesehen = {}

    def handler(request):
        gesehen["koerper"] = request.read()
        gesehen["header"] = dict(request.headers)
        return httpx.Response(200, json={"text": "Ciao a tutti."})

    datei = tmp_path / "a.m4a"
    datei.write_bytes(b"testdaten")
    text = stt.transkribiere_elevenlabs(
        _klient(handler), datei, 10.0, sprache="it", schluessel="K")
    assert text == "Ciao a tutti."
    assert gesehen["header"]["xi-api-key"] == "K"
    assert b'name="model_id"\r\n\r\nscribe_v2' in gesehen["koerper"]
    assert b'name="language_code"\r\n\r\nit' in gesehen["koerper"]


def test_transkribiere_elevenlabs_auto_ohne_language_code(tmp_path):
    gesehen = {}

    def handler(request):
        gesehen["koerper"] = request.read()
        return httpx.Response(200, json={"text": "x"})

    datei = tmp_path / "a.m4a"
    datei.write_bytes(b"testdaten")
    stt.transkribiere_elevenlabs(
        _klient(handler), datei, 10.0, sprache=stt.AUTO, schluessel="K")
    assert b"language_code" not in gesehen["koerper"]


def test_transkribiere_elevenlabs_leerer_text_ist_leeres_transkript(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"text": "   "})

    datei = tmp_path / "a.m4a"
    datei.write_bytes(b"testdaten")
    with pytest.raises(stt.LeeresTranskript):
        stt.transkribiere_elevenlabs(_klient(handler), datei, 10.0, sprache="de", schluessel="K")


def test_transkribiere_elevenlabs_http_fehler_wird_sttfehler(tmp_path):
    def handler(request):
        return httpx.Response(401, json={"detail": "ungueltiger Schluessel"})

    datei = tmp_path / "a.m4a"
    datei.write_bytes(b"testdaten")
    with pytest.raises(stt.STTFehler):
        stt.transkribiere_elevenlabs(_klient(handler), datei, 10.0, sprache="de", schluessel="K")
