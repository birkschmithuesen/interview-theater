"""Die Abnahme: ein Workshopanfang ohne Telegram, nur ueber HTTP.

Gefahren wird DERSELBE Codepfad wie im Betrieb -- ``bot.schleife`` in einem
Thread, mit ``WebKanal`` statt ``Telegram``, dazu ein echter Webserver auf
Port 0. Attrappen gibt es nur an den zwei Stellen, an denen Geld fliessen
wuerde: Sprachmodell und Whisper.

Was die Gruppe tut, tut sie per HTTP. Es gibt in diesem Test keinen einzigen
``repo``-Schreibaufruf als Abkuerzung -- sonst prueft er nicht den Weg, den
eine Gruppe im Browser geht. (Der Vorlauf in der Fixture ist genau der von
``scripts/web_gruppe.py`` und gehoert nicht zum Weg der Gruppe.)

**Gewaehlter Weg:** die volle Phasenkette 1 -> 2 -> 3 ueber Knoepfe
(Begriffe, Fragen, weiche Fassungen, Eroeffnung/Abschluss, "Weiter zu ..."),
NICHT der Text-Import-Rueckfallweg aus ANNAHME 5 des Plans -- die Kette traegt.
"""

import json
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from interview_theater import bot, db, einstellungen, phasen, repo, web, web_kanal
from interview_theater.knoepfe.texte import _TEXT_SPEICHERN_KNOPF

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32
GEDULD_S = 30.0
SCHRITT_S = 0.1

_INTERVIEWDATEI = (
    Path(__file__).resolve().parent.parent
    / "simulation" / "interviews" / "set1" / "1-meryem-koffer.md"
)


def _interviewtext() -> str:
    """Erfundenes Material aus ``simulation/interviews/`` -- kein Wort davon
    kommt aus betrieb/. Genommen wird die erste Antwort der befragten Person,
    OHNE den Sprechernamen davor (E8: kein Vorname in Web-Nachrichten, und das
    Transkript-Echo steht im Chat)."""
    for zeile in _INTERVIEWDATEI.read_text(encoding="utf-8").splitlines():
        if zeile.startswith("Meryem:"):
            return zeile.split(":", 1)[1].strip()
    raise AssertionError("Interviewdatei ohne Antwortzeile")


INTERVIEWTEXT = _interviewtext()
#: Steht woertlich im Interviewtext -- der Verdichter belegt damit sein Thema,
#: und ``zitat.pruefe`` muss es im Transkript wiederfinden.
BELEG = "Der Koffer war braun, so ein Braun wie Milchkaffee."

BEGRIFFE = (
    "Gut, ich habe eure drei Begriffe.\n\n"
    "VORSCHLAG BEGRIFFE:\nAnkommen\nArbeit\nNacht"
)
FRAGEN = (
    "Drei Fragen, die dazu passen:\n\n"
    "VORSCHLAG FRAGEN:\n"
    "Was war in deinem Koffer?\n"
    "Wer hat auf dich gewartet?\n"
    "Wann ist eine Stadt deine geworden?"
)
FRAGEN_WEICH = (
    "Eine Frage habe ich weicher formuliert.\n\n"
    "VORSCHLAG FRAGEN WEICH:\n"
    "2 — Du musst nichts sagen, was zu nah ist. Ich frage trotzdem: "
    "war jemand da, als du angekommen bist?"
)
EROEFFNUNG = (
    "So koenntet ihr anfangen und aufhoeren.\n\n"
    "VORSCHLAG EROEFFNUNG:\n"
    "Hallo, wir machen ein Theaterstueck und sammeln dafuer Geschichten. "
    "Was du erzaehlst, bleibt anonym, und du kannst jederzeit aufhoeren. "
    "Darf ich mitschneiden?\n"
    "Abschluss: Danke, dass du dir Zeit genommen hast. Wir spielen das im "
    "Fruehjahr, und du bist eingeladen."
)


class LLMAttrappe:
    """Antwortet nach Teilstrings im Nutzertext -- die erste passende Regel
    gewinnt.

    Keine Warteschlange: der Bot laeuft in mehreren Threads (Gespraechszug,
    Erkenner, Auftragszuege), und eine Warteschlange hinge von der
    Reihenfolge ab, die dabei nicht festgelegt ist. Die ersten zwei
    Teilstrings sind die Anweisungstexte aus ``knoepfe/texte.py``, woertlich."""

    REGELN = (
        # Die Auftragszuege der Fragenkette (knoepfe/texte.ANWEISUNG_*).
        ("Sieh dir diese Interviewfragen der Gruppe an", FRAGEN_WEICH),
        ("womit das Interview anfaengt und aufhoert", EROEFFNUNG),
        # Die Beitraege der Gruppe.
        ("Unsere Begriffe", BEGRIFFE),
        ("drei Fragen", FRAGEN),
    )

    def __init__(self):
        self.nutzertexte = []
        self.verdichtet = 0
        self._sperre = threading.Lock()

    def _gespraech(self, nutzer: str) -> str:
        # Die Anweisungen der Auftragszuege gewinnen immer. Danach entscheidet
        # der JUENGSTE Treffer im Nutzertext: im Gespraechs-Prompt steht der
        # ganze Verlauf, und "Unsere Begriffe" stuende sonst auch dann noch
        # darin, wenn die Gruppe laengst nach Fragen fragt.
        for merkmal, antwort in self.REGELN[:2]:
            if merkmal in nutzer:
                return antwort
        bester, stelle = "Erzaehlt weiter.", -1
        for merkmal, antwort in self.REGELN[2:]:
            pos = nutzer.rfind(merkmal)
            if pos > stelle:
                bester, stelle = antwort, pos
        return bester

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        """Jeder Modellaufruf des Bots laeuft ueber ``schema`` -- der
        Gespraechszug mit ``art='gespraech'`` und ``{"antwort": ...}``
        (``ablauf.SCHEMA``), der Rest mit eigenem Schema."""
        if art == "erkenner":
            # Der Erkenner schreibt in diesem Lauf nichts: alles Speichern
            # laeuft ueber Knoepfe, und ein Erkenner, der daneben etwas
            # setzt, machte den Test von einem Modell abhaengig.
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        if art == "verdichter":
            with self._sperre:
                self.verdichtet += 1
            return {
                "zusammenfassung": "Eine Ankunft mit einem einzigen Koffer.",
                "kernthemen": [{
                    "thema": "Ein Koffer als ganzes Gepaeck",
                    "kurz": "Koffer",
                    "beleg_zitat": BELEG,
                }],
            }
        with self._sperre:
            self.nutzertexte.append(nutzer)
        return {"antwort": self._gespraech(nutzer)}


def stt_attrappe(text: str) -> httpx.Client:
    """Wie ``tests/test_aufnahme.stt_attrappe``: Upload liefert eine
    batch_id, die erste Abfrage ist fertig. Das Feld ``data`` ist ein
    JSON-STRING (Falle 2) -- genau wie beim echten Anbieter."""

    def handler(anfrage):
        if "audio/transcriptions" in anfrage.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


class _Halt(Exception):
    """Beendet ``bot.schleife`` von aussen. Die Schleife faengt um
    ``hole_updates`` nur ``TelegramFehler`` -- alles andere laesst sie aus
    dem ``while True`` heraus, und genau das braucht ein sauberes Testende."""


class _HaltbarerKanal(web_kanal.WebKanal):
    """``WebKanal`` mit Ausschalter. Der Long-Poll wartet hier hoechstens
    eine halbe Sekunde je Runde statt 25 s, damit das Testende nicht auf
    einen laufenden Poll wartet -- am Weg der Updates aendert das nichts."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.halt = threading.Event()

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        if self.halt.is_set():
            raise _Halt()
        return super().hole_updates(offset, timeout=min(timeout, 0.5))


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    """Webserver und Bot-Schleife, beide im Thread, auf einer Wegwerf-DB."""
    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"
    monkeypatch.setenv("IT_AUDIO", str(audio))
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", "1000")

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    # Genau wie scripts/web_gruppe.py -- der einzige Vorlauf, den eine echte
    # Web-Gruppe auch braucht.
    repo.sichere_gruppe(aufbau, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    web_faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    web_faden.start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=pfad, audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
        web_url="", kanal=einstellungen.KANAL_WEB, web_chat_id=CHAT,
    )
    klm = LLMAttrappe()
    kanal = _HaltbarerKanal(bot_conn, CHAT, str(audio), schritt_s=0.05)
    pool = ThreadPoolExecutor(max_workers=bot.POOL_GROESSE)
    stt = stt_attrappe(INTERVIEWTEXT)
    def fahre():
        try:
            bot.schleife(bot_conn, e, kanal, klm, stt, pool)
        except _Halt:
            pass

    bot_faden = threading.Thread(target=fahre, daemon=True)
    bot_faden.start()

    yield basis, token, pfad, klm

    kanal.halt.set()
    bot_faden.join(timeout=GEDULD_S)
    pool.shutdown(wait=True, cancel_futures=True)
    dienst.shutdown()
    dienst.server_close()
    web_faden.join(timeout=GEDULD_S)
    stt.close()
    bot_conn.close()
    assert not bot_faden.is_alive(), "bot.schleife ist nicht beendet"


# -- Hilfsmittel: nur HTTP ------------------------------------------------


def _zustand(basis, token, nach=0):
    """Der Poll -- und mit ihm der aktuelle Nonce, wie im Browser."""
    with urllib.request.urlopen(
        f"{basis}/g/{token}/chat/zustand?nach={nach}", timeout=5
    ) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def _nonce(basis, token):
    return _zustand(basis, token)["nonce"]


def _post(basis, token, weg, koerper):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/{weg}",
        data=json.dumps({"nonce": _nonce(basis, token), **koerper}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        assert antwort.status == 202
        return json.loads(antwort.read().decode("utf-8"))


def _warte_auf_knopf(basis, token, teil: str, nach: int = 0) -> tuple[int, str]:
    """Wartet, bis im Chat (ab Nachricht ``nach``, exklusiv) ein Knopf steht,
    dessen Beschriftung ``teil`` enthaelt -- und liefert ``(message_id, data)``.

    Immer den JUENGSTEN: was zuletzt im Chat stand, ist das, was eine Gruppe
    auf dem Handy sieht (dieselbe Regel wie
    ``simulation.attrappe.offene_knoepfe``)."""
    frist = time.monotonic() + GEDULD_S
    gesehen = set()
    while time.monotonic() < frist:
        for n in reversed(_zustand(basis, token, nach)["nachrichten"]):
            for beschriftung, daten in n["knoepfe"]:
                gesehen.add(beschriftung)
                if teil.lower() in beschriftung.lower():
                    return n["id"], daten
        time.sleep(SCHRITT_S)
    raise AssertionError(f"Knopf {teil!r} kam nicht. Gesehen: {sorted(gesehen)}")


def _letzte_id(basis, token) -> int:
    nachrichten = _zustand(basis, token)["nachrichten"]
    return nachrichten[-1]["id"] if nachrichten else 0


def _druecke(basis, token, teil: str, nach: int = 0) -> int:
    """Drueckt den juengsten passenden Knopf und liefert die id der
    Nachricht, an der er hing -- der naechste Schritt sucht danach."""
    message_id, daten = _warte_auf_knopf(basis, token, teil, nach)
    _post(basis, token, "knopf", {"message_id": message_id, "data": daten})
    return message_id


def _warte_auf(pfad: str, pruefung, was: str):
    """Wartet, bis eine Bedingung in der Datenbank gilt. Gelesen wird ueber
    eine eigene Verbindung -- der Bot-Thread hat seine."""
    frist = time.monotonic() + GEDULD_S
    conn = db.verbinde(pfad)
    try:
        while time.monotonic() < frist:
            ergebnis = pruefung(conn)
            if ergebnis:
                return ergebnis
            time.sleep(SCHRITT_S)
    finally:
        conn.close()
    raise AssertionError(f"{was} trat nicht ein")


def _feld(name):
    def pruefung(conn):
        stand = repo.hole_arbeitsstand(conn, CHAT)
        return (stand[name] or "").strip() if stand is not None else ""
    return pruefung


def _phase(nummer):
    return lambda conn: phasen.aktuelle(conn, CHAT) == nummer


def _lade_segment(basis, token, nummer: int) -> None:
    """Ein WebM-Segment, wie MediaRecorder es liefert (EBML-Kopf + Rest).
    Roher Koerper, Nonce und Dauer in der Query -- wie im Browser-JS."""
    koerper = b"\x1a\x45\xdf\xa3" + bytes([nummer]) * 512
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/audio?nonce={_nonce(basis, token)}&dauer=30",
        data=koerper, headers={"Content-Type": "audio/webm;codecs=opus"},
        method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=15) as antwort:
        assert antwort.status == 202


def _teile(conn):
    return conn.execute(
        "SELECT a.id, a.transkript FROM aufnahme a "
        "JOIN aufnahme k ON k.id = a.teil_von "
        "WHERE a.chat_id = ? ORDER BY a.id", (CHAT,),
    ).fetchall()


# -- die Abnahme ----------------------------------------------------------


def test_von_phase_eins_bis_zum_ersten_interview_nur_ueber_http(lauf):
    basis, token, pfad, klm = lauf
    speichern = _TEXT_SPEICHERN_KNOPF

    # (1) Phase 1: Begriffe
    _post(basis, token, "senden", {"text": "Unsere Begriffe: Ankommen, Arbeit, Nacht"})
    hing = _druecke(basis, token, speichern)
    assert "Ankommen" in _warte_auf(pfad, _feld("begriffe"), "begriffe gesetzt")

    # (2) Phase 2: Fragen, weiche Fassungen, Eroeffnung -- drei Stufen,
    # jede mit derselben Grundleiste (knoepfe.offene_art).
    hing = _druecke(basis, token, "Weiter zu", nach=hing)
    _warte_auf(pfad, _phase(2), "Phase 2")

    _post(basis, token, "senden", {"text": "Macht uns drei Fragen dazu."})
    hing = _druecke(basis, token, speichern, nach=hing)
    _warte_auf(pfad, _feld("fragen"), "fragen gesetzt")

    # Die Sensibilitaetspruefung laeuft von selbst an (im Thread).
    hing = _druecke(basis, token, speichern, nach=hing)
    _warte_auf(pfad, _feld("fragen_weich"), "fragen_weich gesetzt")

    # Eroeffnung und Abschluss: EIN Block, ZWEI Felder
    # (knoepfe/fragen._speichere_eroeffnung).
    hing = _druecke(basis, token, speichern, nach=hing)
    _warte_auf(pfad, _feld("interview_eroeffnung"), "Eroeffnung gesetzt")
    _warte_auf(pfad, _feld("interview_abschluss"), "Abschluss gesetzt")

    # (3) Phase 3: Interviews
    _druecke(basis, token, "Weiter zu", nach=hing)
    _warte_auf(pfad, _phase(3), "Phase 3")

    # (4) Interview an -- ueber /interview, nicht ueber eine zweite
    # Moduslogik (aufnahme.klasse_fuer haengt allein am Modus).
    _post(basis, token, "interview", {"an": True})
    _warte_auf(pfad, lambda c: repo.ist_interviewmodus_an(c, CHAT), "Modus an")

    # (5) Zwei Segmente -- und beide transkribiert, BEVOR der Modus endet:
    # ein offener Teil haelt den Abschluss auf (AGENTS.md, § 10.6), und der
    # Test soll den Normalfall pruefen, nicht das Nachholen.
    for nummer in (1, 2):
        _lade_segment(basis, token, nummer)
    _warte_auf(
        pfad,
        lambda c: len([t for t in _teile(c) if (t["transkript"] or "").strip()]) >= 2,
        "zwei transkribierte Interview-Teile",
    )

    # (6) Interview aus
    _post(basis, token, "interview", {"an": False})
    _warte_auf(pfad, lambda c: not repo.ist_interviewmodus_an(c, CHAT), "Modus aus")
    _warte_auf(pfad, lambda c: klm.verdichtet >= 1, "Verdichtung")

    # GENAU EIN Interview mit mindestens zwei Teilen.
    conn = db.verbinde(pfad)
    try:
        koepfe = conn.execute(
            "SELECT DISTINCT teil_von FROM aufnahme "
            "WHERE chat_id = ? AND teil_von IS NOT NULL", (CHAT,),
        ).fetchall()
        assert len(koepfe) == 1
        kopf = koepfe[0][0]
        teile = conn.execute(
            "SELECT COUNT(*) FROM aufnahme WHERE teil_von = ?", (kopf,)
        ).fetchone()[0]
        assert teile >= 2
        # Nach aussen ist ein Interview eine Einheit (repo.transkripte zaehlt
        # ohne Teile): genau eine Zeile, und sie ist der Kopf.
        einheiten = repo.transkripte(conn, CHAT)
        assert [z["id"] for z in einheiten] == [kopf]

        # Die Transkripte tragen den erfundenen Text -- der Weg durch
        # WebKanal.lade_datei, stt.mime_typ und Whisper hat gehalten.
        assert all("Koffer" in (t["transkript"] or "") for t in _teile(conn))
        # Die abgelegten Dateien sind .webm (Aufgabe 3) -- sonst raete
        # stt.mime_typ daneben (Falle 3).
        dateien = [z[0] for z in conn.execute(
            "SELECT datei FROM web_post WHERE chat_id = ? AND typ = ?",
            (CHAT, repo.WEB_TYP_SPRACHE),
        )]
        assert len(dateien) == 2
        assert all(re.search(r"\.webm$", d or "") for d in dateien), dateien
    finally:
        conn.close()
    # Verdichtet wird EINMAL je Interview, nicht je Teil (§ 10.6).
    assert klm.verdichtet == 1


def test_kein_telegram_im_ganzen_lauf(lauf):
    """E1 von der anderen Seite: dieser Lauf hat keinen Bot-Token und keine
    Netzverbindung zu Telegram -- und funktioniert trotzdem."""
    basis, token, _pfad, _klm = lauf
    _post(basis, token, "senden", {"text": "Unsere Begriffe: Ankommen"})
    # Der Bot antwortet -- mehr braucht dieser Test nicht.
    frist = time.monotonic() + GEDULD_S
    while time.monotonic() < frist:
        if any(n["von"] == "bot" for n in _zustand(basis, token)["nachrichten"]):
            return
        time.sleep(SCHRITT_S)
    raise AssertionError("der Bot hat nicht geantwortet")


def test_kein_absendername_im_verlauf(lauf):
    """E8: nie Vornamen. Die Blase der Gruppe traegt keinen Namen, und im
    Gespraechs-Prompt steht das Rollenwort ``Gruppe``."""
    basis, token, _pfad, klm = lauf
    _post(basis, token, "senden", {"text": "Unsere Begriffe: Ankommen"})
    frist = time.monotonic() + GEDULD_S
    while time.monotonic() < frist and not klm.nutzertexte:
        time.sleep(SCHRITT_S)
    assert klm.nutzertexte, "das Modell wurde nicht gerufen"
    assert f"{web_kanal.ABSENDER}:" in klm.nutzertexte[0]
    assert "None:" not in klm.nutzertexte[0]
    gruppe = [n for n in _zustand(basis, token)["nachrichten"] if n["von"] == "gruppe"]
    assert gruppe and all("name" not in n for n in gruppe)
