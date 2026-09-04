import json
import time

import httpx
import pytest

from interview_theater import einstellungen, stt


def _klient(handler):
    """Baut einen httpx.Client mit MockTransport -- kein Netzzugriff (global-constraints.md)."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_zweistufiger_weg_liefert_text(einst, tmp_path, monkeypatch):
    """POST gibt batch_id, GET wird gepollt, data ist ein JSON-STRING."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    zustand = {"polls": 0}

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            assert b"testdaten" in request.read()
            return httpx.Response(200, json={"batch_id": "B1"})
        zustand["polls"] += 1
        if zustand["polls"] < 3:
            return httpx.Response(200, json={"status": "processing"})
        return httpx.Response(200, json={
            "status": "success",
            "data": json.dumps({"text": "Ich bin 1998 weggegangen."})})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS-testdaten")
    klient = _klient(handler)
    assert stt.transkribiere(einst, klient, datei, 30.0) == "Ich bin 1998 weggegangen."
    assert zustand["polls"] == 3


def test_url_liegt_unter_eins_nicht_unter_zwei(einst, tmp_path, monkeypatch):
    """Gemessen: /2/.../openai/v1/ antwortet 404. Der richtige Pfad liegt unter /1/."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    gesehen = {}

    def handler(request):
        gesehen["pfad"] = request.url.path
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": "x"})})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    stt.absenden(einst, _klient(handler), datei, 30.0)
    assert gesehen["pfad"] == "/1/ai/PRODUKT-ID/openai/audio/transcriptions"


def test_abbruchstatus_ist_ein_fehler(einst, tmp_path, monkeypatch):
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={"status": "failed"})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    with pytest.raises(stt.STTFehler):
        stt.transkribiere(einst, _klient(handler), datei, 30.0)


def test_unbekannter_status_wird_weiter_gepollt(einst, tmp_path, monkeypatch):
    """Zwischenzustaende sind nicht abschliessend bekannt: ein unbekannter
    Status ist kein Fehler, sondern heisst weiterwarten."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    zustand = {"polls": 0}

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        zustand["polls"] += 1
        if zustand["polls"] < 3:
            return httpx.Response(200, json={"status": "irgendwas_neues"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": "Text da."})})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    assert stt.transkribiere(einst, _klient(handler), datei, 30.0) == "Text da."
    assert zustand["polls"] == 3


def test_zeitbudget_bricht_ab(einst, tmp_path, monkeypatch):
    """Immer 'processing': das Zeitbudget begrenzt das Warten, nicht der Status."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={"status": "processing"})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    with pytest.raises(stt.STTFehler):
        stt.abholen(einst, _klient(handler), "B1", 0.05)


def test_zeitbudget_wird_nicht_um_ein_vielfaches_gerissen(einst, tmp_path, monkeypatch):
    """Ein Server, der nie antwortet: die Frist muss ueber ALLE Versuche und
    Wartezeiten zusammen gelten, nicht pro Versuch neu anlaufen. Ohne das
    reisst ein Anlauf bis zu vier volle Zeitbudgets plus Wartezeiten
    (~4 * budget_s), statt sich an die Zusage an den Aufrufer zu halten.

    time.sleep ist gepatcht (die Wartezeiten zwischen Versuchen sollen den
    Testlauf nicht ausbremsen), time.monotonic laeuft echt -- der Handler
    liest den tatsaechlich angefragten Timeout aus den Request-Extensions
    und "haengt" fuer genau diese Zeit (echtes Warten, ohne time.sleep zu
    benutzen), damit die Frist wirklich greifen muss."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)

    def handler(request):
        haenge_s = request.extensions["timeout"]["read"]
        ende = time.monotonic() + haenge_s
        while time.monotonic() < ende:
            pass
        raise httpx.ReadTimeout("simulierter haengender Server", request=request)

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")

    budget_s = 2.0
    start = time.monotonic()
    with pytest.raises(stt.STTFehler):
        stt.transkribiere(einst, _klient(handler), datei, budget_s)
    dauer = time.monotonic() - start

    assert dauer < budget_s * 2, (
        f"Budget um ein Vielfaches gerissen: {dauer:.2f}s bei budget_s={budget_s}s"
    )


def test_5xx_beim_pollen_wird_weiter_gewartet(einst, monkeypatch):
    """Ein voruebergehender 500er vom results-Endpunkt ist kein Abbruch --
    der Auftrag laeuft serverseitig weiter, also heisst es weiterwarten."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    zustand = {"polls": 0}

    def handler(request):
        zustand["polls"] += 1
        if zustand["polls"] < 3:
            return httpx.Response(503, json={"error": "kurz ueberlastet"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": "Text nach 5xx."})})

    text = stt.abholen(einst, _klient(handler), "B1", 30.0)
    assert text == "Text nach 5xx."
    assert zustand["polls"] == 3


def test_4xx_beim_pollen_ist_ein_sofortiger_fehler(einst, monkeypatch):
    """Ein 4xx (z.B. eine unbekannte batch_id) fuehrt nie zu einem Ergebnis --
    im Unterschied zu 5xx darf hier nicht weitergepollt werden."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    zustand = {"polls": 0}

    def handler(request):
        zustand["polls"] += 1
        return httpx.Response(404, json={"error": "unbekannte batch_id"})

    with pytest.raises(stt.STTFehler):
        stt.abholen(einst, _klient(handler), "B1", 30.0)
    assert zustand["polls"] == 1


def test_zu_grosse_datei_wird_abgelehnt(einst, tmp_path):
    """Die 25-MB-Grenze wird vor dem Upload geprueft -- kein HTTP-Aufruf."""
    aufgerufen = {"n": 0}

    def handler(request):
        aufgerufen["n"] += 1
        return httpx.Response(200, json={"batch_id": "B1"})

    datei = tmp_path / "gross.ogg"
    with open(datei, "wb") as f:
        f.truncate(stt.MAX_UPLOAD_BYTES + 1)

    with pytest.raises(stt.STTFehler):
        stt.absenden(einst, _klient(handler), datei, 30.0)
    assert aufgerufen["n"] == 0


def test_5xx_beim_absenden_wird_wiederholt(einst, tmp_path, monkeypatch):
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    versuche = {"n": 0}

    def handler(request):
        versuche["n"] += 1
        if versuche["n"] < 2:
            return httpx.Response(502, json={"error": "bad gateway"})
        return httpx.Response(200, json={"batch_id": "B1"})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    batch_id = stt.absenden(einst, _klient(handler), datei, 30.0)
    assert batch_id == "B1"
    assert versuche["n"] == 2


def test_leeres_transkript_ist_ein_fehler(einst, tmp_path, monkeypatch):
    """Stille ist kein gueltiges Transkript."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": "   "})})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    with pytest.raises(stt.STTFehler):
        stt.transkribiere(einst, _klient(handler), datei, 30.0)


def test_transkribiere_wiederholt_genau_einmal_mit_neuem_upload(einst, tmp_path, monkeypatch):
    """Der erste Anlauf scheitert komplett; der zweite ist ein neuer Upload
    (neue batch_id), nicht nur ein erneutes Pollen. Danach kein dritter Versuch."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    uploads = {"n": 0}

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            uploads["n"] += 1
            return httpx.Response(200, json={"batch_id": f"B{uploads['n']}"})
        if request.url.path.endswith("/results/B1"):
            return httpx.Response(200, json={"status": "failed"})
        if request.url.path.endswith("/results/B2"):
            return httpx.Response(200, json={
                "status": "success", "data": json.dumps({"text": "Zweiter Versuch."})})
        raise AssertionError(f"unerwarteter Pfad: {request.url.path}")

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    text = stt.transkribiere(einst, _klient(handler), datei, 30.0)
    assert text == "Zweiter Versuch."
    assert uploads["n"] == 2


def test_beide_versuche_scheitern_gibt_fehler_nach_genau_zwei_uploads(einst, tmp_path, monkeypatch):
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)
    uploads = {"n": 0}

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            uploads["n"] += 1
            return httpx.Response(200, json={"batch_id": f"B{uploads['n']}"})
        return httpx.Response(200, json={"status": "failed"})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    with pytest.raises(stt.STTFehler):
        stt.transkribiere(einst, _klient(handler), datei, 30.0)
    assert uploads["n"] == 2


def test_api_schluessel_landet_nicht_in_ausnahme(tmp_path, monkeypatch):
    """Der Schluessel steht nur im Authorization-Header und darf nach
    Ausschoepfen aller Wiederholungen nirgends in str(ausnahme) auftauchen."""
    monkeypatch.setattr(stt.time, "sleep", lambda s: None)

    geheim = "GEHEIMER_STT_SCHLUESSEL_999"
    e = einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key=geheim, llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )

    def handler(request):
        return httpx.Response(500, json={"error": "kaputt"})

    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"testdaten")
    with pytest.raises(stt.STTFehler) as ausnahme_info:
        stt.absenden(e, _klient(handler), datei, 30.0)

    meldung = str(ausnahme_info.value)
    assert geheim not in meldung


def test_mime_typ_aus_der_dateiendung():
    """Gemessen 04.09.2026: ein fest verdrahtetes audio/ogg fuer eine
    WAV-Datei wird mit einer batch_id quittiert, bleibt dann aber dauerhaft
    auf pending und laeuft in die Zeitfrist (89,7 s statt 2,0 s)."""
    from pathlib import Path as P
    assert stt.mime_typ(P("a.ogg")) == "audio/ogg"
    assert stt.mime_typ(P("a.oga")) == "audio/ogg"
    assert stt.mime_typ(P("a.wav")) == "audio/wav"
    assert stt.mime_typ(P("a.mp3")) == "audio/mpeg"
    assert stt.mime_typ(P("a.m4a")) == "audio/mp4"
    assert stt.mime_typ(P("a.unbekannt")) == "application/octet-stream"


def test_upload_sendet_den_passenden_mime_typ(einst, tmp_path):
    """Der Anbieter braucht den echten Typ; ogg fuer wav laesst den Auftrag
    stumm haengen statt ihn abzulehnen."""
    gesehen = {}

    def handler(request):
        gesehen["koerper"] = request.read()
        return httpx.Response(200, json={"batch_id": "B1"})

    klient = httpx.Client(transport=httpx.MockTransport(handler))

    wav = tmp_path / "f_kurz_7s.wav"
    wav.write_bytes(b"RIFFtestdaten")
    stt.absenden(einst, klient, wav, 10.0)
    assert b"audio/wav" in gesehen["koerper"]
    assert b"audio/ogg" not in gesehen["koerper"]

    ogg = tmp_path / "sprachnachricht.ogg"
    ogg.write_bytes(b"OggStestdaten")
    stt.absenden(einst, klient, ogg, 10.0)
    assert b"audio/ogg" in gesehen["koerper"]


def test_dauerhaft_pending_laeuft_in_die_frist(einst, monkeypatch):
    """Genau das Fehlerbild aus dem Rauchtest: batch_id kommt, Status bleibt
    pending. Das muss ein STTFehler werden, damit die Aufnahme auf
    status='empfangen' bleibt und der Nachhol-Arbeiter es erneut versucht."""
    monkeypatch.setattr(stt.time, "sleep", lambda _: None)
    klient = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"status": "pending"})
    ))
    with pytest.raises(stt.STTFehler):
        stt.abholen(einst, klient, "B1", 0.2)
