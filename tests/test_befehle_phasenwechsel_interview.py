"""Abnahme P3-4 A3 (06.10.2026): ein verwaistes Interview sperrt
"Start listening"/#diskussion dauerhaft und phasenunabhaengig, weil
``interviewmodus_seit`` ein reiner Gruppenschalter ist, den bisher
ausschliesslich ``aufnahme.beende_interview()`` loeschte (siehe
/tmp/nacht/abn/b2-analyse.md). ``befehle.wechsle_phase`` beendet ein offenes
Interview deshalb jetzt selbst, bevor sie in Phase >= 4 wechselt -- derselbe
Pfad wie ``/fertig`` (``_befehl_fertig``): Interviews mit Teilen werden ganz
normal verdichtet (kein Audio-Verlust), ein Kopf ohne einen einzigen Teil
wird wie bisher weich verworfen.

Kein Netzzugriff: TelegramAttrappe/LLMAttrappe/stt_attrappe sind dieselbe
Bauart wie in tests/test_aufnahme.py (dort ausfuehrlicher begruendet).
"""

import json
import time
from datetime import datetime, timezone

import httpx
import pytest

from interview_theater import aufnahme, befehle, phasen, repo, workshop

CHAT = 1

#: Deutlich ueber aufnahme.MINDEST_WOERTER (N2), sonst wuerde ein
#: einteiliges Interview als "sehr kurz" abgelehnt statt verdichtet.
TEIL_A = (
    "Ich bin 1998 gekommen und hatte nur einen Koffer dabei, mehr nicht. Am "
    "Bahnhof war es grau, und ich habe gedacht, ich bleibe zwei Jahre und "
    "gehe dann wieder."
)
TEIL_B = (
    "Ich erinnere mich, wie wir als Kinder auf dem Hof Theater gespielt haben, "
    "mit Bettlaken als Vorhang, und meine Grossmutter hat immer zugeschaut."
)


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []  # Liste von (chat_id, text, system)

    def sende(self, chat_id, text, **kw):
        self.gesendet.append((chat_id, text, kw.get("system", False)))
        return 9001

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
        self.gesendet.append((chat_id, text, kw.get("system", False)))
        return 9001

    def tippt(self, chat_id):
        pass

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")


@pytest.fixture
def tg():
    return TelegramAttrappe()


class LLMAttrappe:
    """Liefert immer dieselbe gueltige Verdichtung; zaehlt NUR die
    Verdichter-Aufrufe (``art == "verdichter"``, siehe ``verdichter.
    verdichte``) -- Grundlage der Zusage "verdichtet wird genau einmal je
    Interview".

    Phase 4 (PHASE_SETTING) stoesst beim Eintritt unabhaengig von dieser
    Abnahme einen eigenen, deterministisch unabhaengigen Gespraechszug an
    (``knoepfe.stationen.eintritt_in_phase`` -> ``ablauf.auftragszug``,
    ``art == "gespraech"``, in einem eigenen Thread, Zusage 2). Ohne eine
    gueltige Antwort darauf wirft ``auftragszug`` ein (abgefangenes)
    ``LLMFehler`` und haette ohne eigenen Zweig hier zusaetzlich den
    Verdichter-Zaehler verfaelscht, weil derselbe ``klm`` von beiden
    Threads gerufen wird."""

    def __init__(self):
        self.aufrufe = 0
        self.nutzertexte = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
        if art == "verdichter":
            self.aufrufe += 1
            self.nutzertexte.append(nutzer)
            return {
                "zusammenfassung": "Eine Erinnerung an die Ankunft.",
                "kernthemen": [
                    {"thema": "Ankommen", "beleg_zitat": "Am Bahnhof war es grau"},
                ],
            }
        if art == "erkenner":
            return {"aenderungen": []}
        # "gespraech" (Phase-4-Eintrittsgruss) und alles sonst Unbeachtete:
        # eine gueltige, aber fuer diese Abnahme bedeutungslose Antwort.
        return {"antwort": "Weiter geht's."}


@pytest.fixture
def klm():
    return LLMAttrappe()


def stt_attrappe(text: str) -> httpx.Client:
    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


def sprachnachricht(message_id, chat_id=CHAT, file_id="FILE1") -> dict:
    return {
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
        "absender": "Ada",
        "typ": "sprache",
        "text": None,
        "file_id": file_id,
        "dauer": 60,
        "gesendet_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def interview_an(conn, chat_id=CHAT) -> int:
    """Schaltet den Interviewmodus an und legt den Kopf an -- derselbe Weg
    wie ``/interview``."""
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    return aufnahme.stelle_interview_sicher(conn, chat_id)


def interview_mit_teilen(conn, einst, tg, klm, texte, message_id=500) -> int:
    """Ein vollstaendig eingesprochenes, aber noch offenes Interview."""
    kopf_id = interview_an(conn)
    for i, text in enumerate(texte):
        aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(message_id + i))
        aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(text), aid)
    return kopf_id


def warte_bis(bedingung, timeout=5.0, schritt=0.02) -> bool:
    """Pollt, bis ``bedingung()`` wahr ist oder ``timeout`` erreicht ist --
    derselbe Grund, aus dem tests/test_aufnahme.py kurze ``time.sleep``-
    Schleifen statt eines Thread-Handles benutzt: der Abschluss laeuft in
    einem eigenen Thread (``aufnahme.starte_abschluss``), den
    ``befehle.wechsle_phase`` nicht nach aussen gibt."""
    ende = time.time() + timeout
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(schritt)
    return bedingung()


# -- (a) Phasenwechsel >= 4 beendet ein offenes Interview --------------------


def test_phasenwechsel_3_zu_4_beendet_offenes_interview_mit_teilen_und_verdichtet(
    conn, einst, tg, klm
):
    kopf_id = interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B])
    phasen.setze(conn, CHAT, 3, "befehl")
    assert repo.ist_interviewmodus_an(conn, CHAT) is True
    tg.gesendet.clear()

    befehle.wechsle_phase(conn, tg, klm, einst, CHAT, 4, quelle="befehl")

    # interviewmodus_seit wird SYNCHRON geloescht (aufnahme.beende_interview),
    # die Verdichtung selbst laeuft im Thread -- deshalb zwei Wartepunkte.
    assert repo.ist_interviewmodus_an(conn, CHAT) is False
    assert phasen.aktuelle(conn, CHAT) == 4

    assert warte_bis(lambda: repo.hole_aufnahme(conn, kopf_id)["status"] == "fertig")
    assert klm.aufrufe == 1, "genau ein Modellaufruf, kein Datenverlust"
    assert klm.nutzertexte == [f"{TEIL_A}\n\n{TEIL_B}"]
    assert len(repo.verdichtungen(conn, CHAT)) == 1

    # Ausserhalb des Padua-Fliesstexts (kein Web-Kanal) ist das eine
    # gewoehnliche Nachricht, keine Systemzeile -- system=True gehoert nur
    # zum Fliesstext-Pfad (siehe die Gegenprobe unten mit ``fliesstext``).
    treffer = [(t, s) for _, t, s in tg.gesendet if "Phasenwechsel" in t and "beendet" in t]
    assert treffer, tg.gesendet
    assert all(s is False for _t, s in treffer), treffer


def test_phasenwechsel_3_zu_4_unter_padua_fliesstext_meldet_mit_system_true(
    conn, einst, tg, klm, monkeypatch
):
    """Padua/Web: ``aufnahme.fliesstext_aktiv`` ist nur mit
    ``[interview] fliesstext`` UND Web-Kanal wahr (tests/
    test_interview_fliesstext.py) -- dort geht die Meldung als Systemzeile
    (``system=True``) in dieselbe Transkriptblase statt als eigene
    Chatnachricht."""
    monkeypatch.setattr(workshop, "interview_fliesstext", lambda profil=None: True)
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    kopf_id = interview_an(conn)
    phasen.setze(conn, CHAT, 3, "befehl")
    tg.gesendet.clear()

    befehle.wechsle_phase(conn, tg, klm, einst, CHAT, 4, quelle="befehl")

    assert repo.ist_interviewmodus_an(conn, CHAT) is False
    treffer = [(t, s) for _, t, s in tg.gesendet if "beendet" in t]
    assert treffer, tg.gesendet
    assert all(s is True for _t, s in treffer), treffer


def test_phasenwechsel_3_zu_4_mit_leerem_interview_wird_weich_verworfen(
    conn, einst, tg, klm
):
    """Ein Kopf ohne einen einzigen Teil (Handy weg, nie aufgenommen) wird
    wie am normalen ``/fertig``-Pfad weich verworfen -- kein Modellaufruf,
    keine Verdichtung von nichts."""
    kopf_id = interview_an(conn)
    phasen.setze(conn, CHAT, 3, "befehl")

    befehle.wechsle_phase(conn, tg, klm, einst, CHAT, 4, quelle="befehl")

    assert repo.ist_interviewmodus_an(conn, CHAT) is False
    assert phasen.aktuelle(conn, CHAT) == 4
    assert warte_bis(lambda: repo.hole_aufnahme(conn, kopf_id)["entfernt_am"] is not None)
    assert klm.aufrufe == 0, "keine Verdichtung von nichts (N5)"
    assert repo.verdichtungen(conn, CHAT) == []


def test_phasenwechsel_2_zu_3_laesst_offenes_interview_unberuehrt(conn, einst, tg, klm):
    """Phase 3 ist die eigentliche Interview-Mechanik -- ein Wechsel dorthin
    (oder jeder andere Sprung < 4) darf ein laufendes Interview nicht
    anfassen."""
    kopf_id = interview_mit_teilen(conn, einst, tg, klm, [TEIL_A])
    phasen.setze(conn, CHAT, 2, "befehl")
    tg.gesendet.clear()

    befehle.wechsle_phase(conn, tg, klm, einst, CHAT, 3, quelle="befehl")

    assert repo.ist_interviewmodus_an(conn, CHAT) is True
    assert repo.hole_aufnahme(conn, kopf_id)["status"] == "laeuft"
    assert phasen.aktuelle(conn, CHAT) == 3
    assert klm.aufrufe == 0
    assert not any("Interview" in t and "beendet" in t for _, t, _sys in tg.gesendet)


def test_phasenwechsel_ohne_offenes_interview_tut_nichts_zusaetzliches(conn, einst, tg, klm):
    """Gegenprobe: ohne laufendes Interview aendert der neue Codepfad
    nichts -- derselbe Chatverlauf wie vor dem Fix."""
    befehle.wechsle_phase(conn, tg, klm, einst, CHAT, 4, quelle="befehl")
    assert repo.ist_interviewmodus_an(conn, CHAT) is False
    assert klm.aufrufe == 0
    assert not any("beendet" in t for _, t, _sys in tg.gesendet)


def test_ein_fehlschlag_beim_interview_abschluss_blockiert_den_phasenwechsel_nicht(
    conn, einst, tg, klm, monkeypatch
):
    """Risiko aus b2-analyse.md: der neue Codepfad darf die Phase nie
    blockieren, selbst wenn er selbst eine Ausnahme wirft -- derselbe Rahmen
    wie ``knoepfe.eintritt_in_phase`` (``try/except`` + Logeintrag)."""
    def wirft(*_a, **_kw):
        raise RuntimeError("simulierter Fehler")

    monkeypatch.setattr(befehle, "_beende_interview_bei_phasenwechsel", wirft)
    interview_an(conn)
    phasen.setze(conn, CHAT, 3, "befehl")

    befehle.wechsle_phase(conn, tg, klm, einst, CHAT, 4, quelle="befehl")

    assert phasen.aktuelle(conn, CHAT) == 4, "die Phase wechselt trotzdem"
