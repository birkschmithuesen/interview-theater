"""Padua Phasen TEIL 2, Task 5 -- Phase-4-Sperre bei zu kurzem Interview
(Befund 4a/4b/4c).

Vor diesem Fix blieb ein zu kurzes Interview (``aufnahme._zu_kurz_gemeldet``,
N2), das nie verdichtet wird, in ``aufnahme.unausgewertete_interviews()``
stehen -- es hatte ``status='fertig'``, aber keine Verdichtung, und sah damit
fuer die Phase-4-Sperre genauso aus wie ein normales, noch nicht
ausgewertetes Interview. Die Gruppe kam nie nach Phase 4 (genau der Fall der
echten Padua-Gruppe aus dem Kartentext). Die neue Spalte
``aufnahme.zu_kurz_uebersprungen`` (Task 1) unterscheidet beide Faelle.

Kein Netzzugriff: Telegram und Sprachmodell sind Attrappen (wie
tests/test_aufnahme.py).
"""

import pytest

from interview_theater import ablauf, aufnahme, knoepfe, phasen, repo

#: Deutlich unter aufnahme.MINDEST_WOERTER (40) -- der zu-kurz-Fall.
TRANSKRIPT_KURZ = "Kurzer Satz ueber die Probe heute Abend."

#: Deutlich ueber aufnahme.MINDEST_WOERTER (40 Woerter) -- ein normales,
#: verdichtbares Interview.
TRANSKRIPT_LANG = (
    "Wir haben lange ueber das Ensemble gesprochen und darueber, wie die "
    "Proben ablaufen sollen. Ich erinnere mich an die erste Vorstellung, bei "
    "der alle sehr nervoes waren, aber am Ende hat alles gut geklappt und "
    "wir haben zusammen gefeiert, bis es spaet in der Nacht wurde."
)


class TelegramAttrappe:
    """Dieselbe Schnittstelle wie ``telegram.Telegram``: Aufnahme-Download
    (wie in test_aufnahme.py) UND Knopf-Wege (wie in test_szenenfolge.py),
    weil dieser Test sowohl ein Interview durchlaufen laesst als auch
    wirklich auf "Interviews fertig" drueckt."""

    def __init__(self):
        self.gesendet = []       # Liste von (chat_id, text)
        self.mit_knoepfen = []   # Liste von (chat_id, text, [(beschriftung, daten), ...])
        self.beantwortet = []
        self.entfernt = []
        self._letzte_message_id = 9000

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._letzte_message_id += 1
        return self._letzte_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        message_id = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return message_id

    def tippt(self, chat_id):
        pass

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))


class LLMAttrappe:
    """Liefert immer eine gueltige, belegte Verdichtung -- wie in
    tests/test_aufnahme.py. Das Belegzitat steht woertlich in
    TRANSKRIPT_LANG, sonst faellt das Thema wegen N2 (Zitatpflicht) weg."""

    def __init__(self):
        self.aufrufe = 0
        self.nutzertexte = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
        if art == "erkenner":
            return {"aenderungen": []}
        self.aufrufe += 1
        self.nutzertexte.append(nutzer)
        return {
            "zusammenfassung": "Ein Ensemble erinnert sich an die erste Vorstellung.",
            "kernthemen": [
                {"thema": "Ensemble", "beleg_zitat": "haben lange ueber das Ensemble gesprochen"},
            ],
        }


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def klm():
    return LLMAttrappe()


def sprachnachricht(dauer, message_id, chat_id=1, file_id="FILE1") -> dict:
    """Ein normalisiertes Nachrichten-Dictionary wie telegram.lies_nachricht()
    es fuer eine Sprachnachricht liefern wuerde (wie in test_aufnahme.py)."""
    from datetime import datetime, timezone

    return {
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
        "absender": "Ada",
        "typ": "sprache",
        "text": None,
        "file_id": file_id,
        "dauer": dauer,
        "gesendet_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _stt_attrappe(text: str):
    import json

    import httpx

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


def _interview(conn, einst, tg, klm, text, message_id, chat_id=1, abschliessen=True):
    """Baut ein vollstaendig eingesprochenes, beendetes Interview mit genau
    einer Sprachnachricht. Mit ``abschliessen=True`` (Vorgabe) laeuft
    ``schliesse_ab`` mit -- das ist der Live-Pfad (``/fertig``) und der
    einzige Weg, auf dem ``_zu_kurz_gemeldet`` ueberhaupt greift. Mit
    ``abschliessen=False`` bleibt das Interview beendet, aber NICHT
    verdichtet -- der normale "noch nicht ausgewertet"-Fall."""
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    kopf_id = aufnahme.stelle_interview_sicher(conn, chat_id)
    aid = aufnahme.empfange(
        conn, tg, einst, sprachnachricht(dauer=60, message_id=message_id, chat_id=chat_id)
    )
    aufnahme.verarbeite(conn, tg, klm, einst, _stt_attrappe(text), aid)
    aufnahme.beende_interview(conn, chat_id)
    if abschliessen:
        aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)
    return kopf_id


# ---------------------------------------------------------------------------
# 1. Zu kurz blockiert nicht mehr
# ---------------------------------------------------------------------------


def test_zu_kurz_blockiert_phase_4_nicht_mehr(conn, einst, tg, klm):
    phasen.setze(conn, 1, 3, "befehl")
    kurz_id = _interview(conn, einst, tg, klm, TRANSKRIPT_KURZ, message_id=100)
    assert repo.hole_aufnahme(conn, kurz_id)["zu_kurz_uebersprungen"] == 1
    assert repo.hole_aufnahme(conn, kurz_id)["status"] == "fertig"
    assert repo.verdichtung_zu_aufnahme(conn, kurz_id) is None

    # Ohne ein zweites, normal verdichtetes Interview wuerde
    # phasen.voraussetzungen()[4] trivial an "keine Verdichtung ueberhaupt"
    # scheitern -- das zweite Interview macht die Pruefung aussagekraeftig.
    _interview(conn, einst, tg, klm, TRANSKRIPT_LANG, message_id=200)

    offen = aufnahme.unausgewertete_interviews(conn, 1)
    assert offen == [], "das zu-kurz uebersprungene Interview sperrt nicht mehr"
    assert phasen.voraussetzungen(conn, 1)[4] is True


# ---------------------------------------------------------------------------
# 2. Normales offenes Interview blockiert weiterhin (Regressionsschutz)
# ---------------------------------------------------------------------------


def test_normales_offenes_interview_blockiert_weiterhin(conn, einst, tg, klm):
    phasen.setze(conn, 1, 3, "befehl")
    # Ein verdichtetes Interview, damit repo.verdichtungen() nicht ohnehin
    # leer ist -- sonst wuerde phasen.voraussetzungen()[4] unabhaengig vom
    # hier getesteten Verhalten False liefern.
    _interview(conn, einst, tg, klm, TRANSKRIPT_LANG, message_id=300)

    offen_id = _interview(
        conn, einst, tg, klm, TRANSKRIPT_LANG, message_id=400, abschliessen=False
    )
    zeile = repo.hole_aufnahme(conn, offen_id)
    assert zeile["zu_kurz_uebersprungen"] == 0
    assert repo.verdichtung_zu_aufnahme(conn, offen_id) is None

    offen = [k["id"] for k in aufnahme.unausgewertete_interviews(conn, 1)]
    assert offen_id in offen, "ein normal offenes Interview sperrt weiterhin"
    assert phasen.voraussetzungen(conn, 1)[4] is False


# ---------------------------------------------------------------------------
# 3. /auswerten entfernt ein zu-kurz-Interview trotzdem aus der Liste
# ---------------------------------------------------------------------------


def test_auswerten_entfernt_zu_kurz_interview_trotzdem(conn, einst, tg, klm):
    phasen.setze(conn, 1, 3, "befehl")
    kurz_id = _interview(conn, einst, tg, klm, TRANSKRIPT_KURZ, message_id=500)
    assert repo.hole_aufnahme(conn, kurz_id)["zu_kurz_uebersprungen"] == 1
    assert kurz_id not in [k["id"] for k in aufnahme.unausgewertete_interviews(conn, 1)], (
        "das Flag allein haelt es schon draussen -- die eigentliche "
        "Zusicherung dieses Tests folgt unten: /auswerten funktioniert "
        "WEITERHIN, auch mit gesetztem Flag"
    )

    aufnahme._interview_abschliessen(
        conn, tg, klm, einst, repo.hole_aufnahme(conn, kurz_id), erzwungen=True,
    )

    assert repo.verdichtung_zu_aufnahme(conn, kurz_id) is not None, (
        "/auswerten (erzwungen=True) verdichtet auch ein zu-kurz-Interview"
    )
    offen = [k["id"] for k in aufnahme.unausgewertete_interviews(conn, 1)]
    assert kurz_id not in offen, (
        "nach der erzwungenen Verdichtung ist es ueber verdichtung_zu_aufnahme "
        "draussen -- unabhaengig vom (weiterhin gesetzten) Flag"
    )
    # Das Flag selbst wird dabei NICHT zurueckgesetzt (laut Spezifikation
    # nicht noetig) -- hier explizit festgehalten, damit ein spaeterer Umbau
    # nicht versehentlich davon ausgeht, es wuerde geleert.
    assert repo.hole_aufnahme(conn, kurz_id)["zu_kurz_uebersprungen"] == 1


# ---------------------------------------------------------------------------
# 4. Keine Dopplung mehr beim Knopf "Interviews fertig"
# ---------------------------------------------------------------------------


def _druecke_interviews_fertig(conn, tg, klm, einst, chat_id=1):
    knopf_id = repo.lege_knopf_an(conn, chat_id, knoepfe.ART_INTERVIEWS_FERTIG, None)
    druck = {
        "callback_query_id": "q1",
        "data": knoepfe._daten(knopf_id),
        "chat_id": chat_id,
        "message_id": 777,
    }
    assert knoepfe.behandle(conn, tg, klm, einst, druck) is True
    return druck


def test_keine_dopplung_beim_knopf_interviews_fertig(conn, einst, tg, klm):
    phasen.setze(conn, 1, 3, "befehl")
    offen_id = _interview(
        conn, einst, tg, klm, TRANSKRIPT_LANG, message_id=600, abschliessen=False
    )
    assert offen_id in [k["id"] for k in aufnahme.unausgewertete_interviews(conn, 1)]
    tg.gesendet.clear()
    tg.beantwortet.clear()

    _druecke_interviews_fertig(conn, tg, klm, einst)

    # Praezise Pruefung an der Attrappe statt nur am Rueckgabewert: der Text
    # kommt NUR noch als Knopf-Quittung (answerCallbackQuery), nie als
    # zusaetzliches d.tg.sende(). knoepfe.T liest dynamisch aus dem aktiven
    # Sprachprofil -- ohne IT_WORKSHOP ist das wortgleich die deutsche
    # Konstante in knoepfe/texte.py.
    erwarteter_text = knoepfe.T._TEXT_INTERVIEWS_NOCH_OFFEN.format(anzahl=1)
    anzahl_sende_treffer = sum(1 for _, t in tg.gesendet if t == erwarteter_text)
    assert anzahl_sende_treffer == 0, (
        "der Text darf NICHT ueber d.tg.sende() rausgehen -- nur als "
        "Knopf-Quittung (Rueckgabewert von _wirke/behandle)"
    )
    assert tg.beantwortet == [("q1", erwarteter_text)], (
        "die Quittung selbst muss trotzdem ankommen"
    )


# ---------------------------------------------------------------------------
# 5. Automatischer Weitergang (Befund 4c)
# ---------------------------------------------------------------------------


def test_automatischer_weitergang_nach_letzter_verdichtung(conn, einst, tg, klm, monkeypatch):
    # Phase 4 (Setting) stoesst beim Eintritt selbst einen Gespraechszug im
    # Thread an (``knoepfe.stationen.eintritt_in_phase``, Padua-Brainstorming-
    # Umbau) -- Zusage 2, kein Modellaufruf im Knopf-/Auto-Uebergang-Pfad
    # selbst. Aufgezeichnet statt ausgefuehrt (derselbe Fang wie in
    # tests/test_phasenangebot_nach_eroeffnung.py), weil dieser Test nur den
    # PHASENWECHSEL selbst beweisen soll, nicht den Einstiegstext von Phase 4.
    monkeypatch.setattr(ablauf, "starte_auftrag", lambda *a, **kw: object())

    phasen.setze(conn, 1, 3, "befehl")
    offen_id = _interview(
        conn, einst, tg, klm, TRANSKRIPT_LANG, message_id=700, abschliessen=False
    )
    assert offen_id in [k["id"] for k in aufnahme.unausgewertete_interviews(conn, 1)]

    _druecke_interviews_fertig(conn, tg, klm, einst)
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["interviews_fertig_wunsch_seit"] is not None, (
        "Vorbedingung: der Wunsch wurde gemerkt, weil noch etwas offen war"
    )

    # Jetzt wird genau dieses (normale, NICHT zu-kurze) Interview verdichtet
    # -- ohne dass die Gruppe nochmal etwas tut. Dasselbe, was
    # ``aufnahme._schliesse_ab`` vor einem Verdichtungsversuch tut: das
    # zusammengefuegte Transkript steht am Kopf (``_zu_kurz_gemeldet`` liest
    # NUR ``row["transkript"]``, nicht den Teile-Fallback).
    repo.setze_transkript(conn, offen_id, TRANSKRIPT_LANG)
    repo.setze_status(conn, offen_id, "transkribiert")
    aufnahme._interview_abschliessen(
        conn, tg, klm, einst, repo.hole_aufnahme(conn, offen_id), erzwungen=False,
    )

    assert repo.verdichtung_zu_aufnahme(conn, offen_id) is not None
    assert aufnahme.unausgewertete_interviews(conn, 1) == []

    stand_danach = repo.hole_arbeitsstand(conn, 1)
    assert stand_danach["interviews_fertig_wunsch_seit"] is None, (
        "schliesse_interviews_ab wurde ausgeloest und hat den Merkposten "
        "geleert -- die sichtbare Wirkung des automatischen Weitergangs"
    )
    assert phasen.aktuelle(conn, 1) == 4, "der Phasenwechsel ist tatsaechlich vollzogen"
