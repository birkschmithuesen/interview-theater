"""Sprachnachricht ueber HINWEIS_AB_S OHNE laufenden Interviewmodus
(06.09.2026, Live-Fall Gruppe 1, 13:32-13:37).

Was an dem Tag schiefging und hier nie wieder passieren darf: die Gruppe
schickte 186 Sekunden Interview, ohne vorher "Interview starten" zu
druecken. Das Transkript ging als Gespraechsbeitrag in den Kontext, das
Gespraechsmodell antwortete mit einem Denkspur-Rest, der Absichtserkenner las
die Aufzaehlung der interviewten Person als Begriffsliste der Gruppe und
ueberschrieb ``arbeitsstand.begriffe``, und der Journal-Extraktor schrieb
einen Vorschlag aus dem Interviewinhalt.

Seitdem: kein Gespraechszug, kein Erkenner, kein Journal auf dieser Nachricht
-- stattdessen eine deterministische Frage mit zwei Knoepfen.

Kein Netzzugriff: Telegram und STT sind Attrappen wie in test_aufnahme.py.
"""

import json
from datetime import datetime, timezone

import httpx
import pytest

from interview_theater import aufnahme, db, einstellungen, knoepfe, phasen, repo


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self.mit_knoepfen = []
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

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))

    def tippt(self, chat_id):
        pass

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")


@pytest.fixture
def tg():
    return TelegramAttrappe()


class LLMAttrappe:
    """Zaehlt jeden Modellaufruf -- die Zusage 'kein Modellaufruf im
    Knopf-Handler' ist genau diese Zahl."""

    def __init__(self):
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art, **_kw):
        self.aufrufe += 1
        return {
            "zusammenfassung": "Eine Zusammenfassung des Gespraechs ueber frueher.",
            "kernthemen": [],
        }

    def antworte(self, *a, **kw):
        self.aufrufe += 1
        return "Antwort"


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


def sprachnachricht(dauer, message_id=10, chat_id=1) -> dict:
    return {
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
        "absender": "Ada",
        "typ": "sprache",
        "text": None,
        "file_id": "FILE1",
        "dauer": dauer,
        "gesendet_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "antwortet_auf_bot": False,
    }


LANG = (
    "Also ich bin hier aufgewachsen und wir sind immer raussgegangen, "
    "Familie war wichtig, Musik hoeren, mit Freunden abhaengen. Am Ende "
    "hat es sich angefuehlt wie ein zweites Zuhause. Meine Mutter hat in "
    "der Fabrik gearbeitet und mein Vater war Busfahrer, wir haben uns "
    "abends immer am Kuechentisch getroffen und ueber den Tag geredet, "
    "auch wenn alle muede waren."
)


def lange_aufnahme(conn, tg, einst, klm, message_id=220, dauer=186, text=LANG) -> int:
    """Der Live-Fall: eine lange Sprachnachricht, Interviewmodus AUS."""
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer, message_id))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(text), aid)
    return aid


def _knoepfe_der_frage(tg, teil: str):
    for _chat_id, text, leiste in tg.mit_knoepfen:
        if teil in text:
            return leiste
    return []


def _druecke(conn, tg, klm, einst, daten, chat_id=1, message_id=777):
    return knoepfe.behandle(conn, tg, klm, einst, {
        "callback_query_id": "q1",
        "data": daten,
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
    })


# --- (a) die Frage selbst -------------------------------------------------


def test_186s_ohne_modus_fragt_mit_zwei_knoepfen(conn, einst, tg, klm):
    """Punkt 4a: keine Gespraechsantwort, kein Erkenner-Aufruf, eine Frage
    mit genau zwei Knoepfen, Transkript versteckt."""
    aufgerufen = []

    def zug(conn, tg, klm, e, chat_id, hinweis=None):
        aufgerufen.append(chat_id)

    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(186, 220))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(LANG), aid, zug=zug)

    assert aufgerufen == [], "kein Gespraechszug -- und damit kein Erkenner, kein Journal"
    assert klm.aufrufe == 0, "kein Modellaufruf auf diesem Weg"

    leiste = _knoepfe_der_frage(tg, "klingt nach einem Interview")
    assert [b for b, _ in leiste] == ["Ja, als Interview", "Nein, war ein Beitrag"]
    assert "(3:06)" in [t for _, t in tg.gesendet if "Interview" in t][0]

    zeile = repo.hole_nachricht(conn, 1, 220)
    assert zeile["typ"] == repo.TYP_TRANSKRIPT, "versteckt, bis die Gruppe entscheidet"
    assert zeile["text"] == LANG, "gespeichert ist es trotzdem"


def test_offene_frage_wird_als_vorfall_vermerkt(conn, einst, tg, klm):
    """Punkt 1f: keine Antwort binnen zehn Minuten heisst NICHTS passiert --
    kein Auto-Ja. Fuers Dashboard bleibt ein Vorfall stehen."""
    lange_aufnahme(conn, tg, einst, klm)
    arten = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")
    ]
    assert "interview_ohne_knopf_offen" in arten
    # Ohne Knopfdruck: kein Interview, kein Modus.
    assert not repo.ist_interviewmodus_an(conn, 1)
    assert aufnahme.interviews(conn, 1) == []


def test_zwei_lange_nachrichten_nacheinander_nehmen_die_alte_leiste_ab(conn, einst, tg, klm):
    """Sonst traefe der Druck die vorletzte Aufnahme."""
    lange_aufnahme(conn, tg, einst, klm, message_id=220)
    lange_aufnahme(conn, tg, einst, klm, message_id=221)
    offen = repo.offene_knoepfe(conn, 1, knoepfe.ART_OHNE_KNOPF_JA)
    assert len(offen) == 1, "nur die juengste Leiste wirkt noch"


# --- (b) "Ja, als Interview" ---------------------------------------------


def test_ja_legt_kopf_an_mit_genau_dieser_aufnahme(conn, einst, tg, klm):
    """Punkt 4b: Kopf mit GENAU dieser Aufnahme als Teil, Phase 3,
    Folgefrage."""
    phasen.setze(conn, 1, 1, "test")
    aid = lange_aufnahme(conn, tg, einst, klm)
    ja = _knoepfe_der_frage(tg, "klingt nach einem Interview")[0][1]

    vorher = klm.aufrufe
    assert _druecke(conn, tg, klm, einst, ja)
    assert klm.aufrufe == vorher, "kein Modellaufruf im Knopf-Handler (Zusage 2)"

    koepfe = aufnahme.interviews(conn, 1)
    assert len(koepfe) == 1
    teile = [t["id"] for t in repo.hole_teile(conn, koepfe[0]["id"])]
    assert teile == [aid], "genau diese Aufnahme haengt am Kopf"
    assert repo.hole_aufnahme(conn, aid)["klasse"] == "teil"
    assert phasen.aktuelle(conn, 1) == 3, "Phase 3 gesichert"
    assert repo.ist_interviewmodus_an(conn, 1), "der Kopf bleibt offen"

    leiste = _knoepfe_der_frage(tg, "Ist das Interview fertig")
    assert [b for b, _ in leiste] == ["Fertig, auswerten", "Es kommt noch was"]


def test_ja_sammelt_auch_nach_langer_wartezeit_ein(conn, einst, tg, klm):
    """Die Gruppe steht im Raum: zwischen Aufnahme und Knopfdruck koennen mehr
    als ``NACHZUEGLER_FENSTER_S`` Sekunden liegen. ``ziehe_eine_in_interview``
    entscheidet dann, nicht das Zeitfenster."""
    aid = lange_aufnahme(conn, tg, einst, klm)
    conn.execute(
        "UPDATE aufnahme SET empfangen_am = '2020-01-01T00:00:00+00:00' WHERE id = ?",
        (aid,),
    )
    conn.commit()
    ja = _knoepfe_der_frage(tg, "klingt nach einem Interview")[0][1]
    _druecke(conn, tg, klm, einst, ja)

    kopf = aufnahme.interviews(conn, 1)[0]
    assert [t["id"] for t in repo.hole_teile(conn, kopf["id"])] == [aid]


def test_fertig_beendet_und_startet_den_abschluss(conn, einst, tg, klm):
    """Punkt 4b, zweite Haelfte: 'Fertig, auswerten' beendet das Interview und
    stoesst die Verdichtung an -- im Thread, nicht im Handler."""
    lange_aufnahme(conn, tg, einst, klm)
    ja = _knoepfe_der_frage(tg, "klingt nach einem Interview")[0][1]
    _druecke(conn, tg, klm, einst, ja)
    fertig = _knoepfe_der_frage(tg, "Ist das Interview fertig")[0][1]

    _druecke(conn, tg, klm, einst, fertig, message_id=778)

    assert not repo.ist_interviewmodus_an(conn, 1), "Modus aus"
    kopf = aufnahme.interviews(conn, 1)[0]
    assert kopf["beendet_am"] is not None, "als beendet gestempelt"
    # Der Abschluss laeuft im Thread; abwarten, bis er durch ist.
    for _ in range(50):
        if repo.verdichtungen(conn, 1):
            break
        import time
        time.sleep(0.05)
    assert repo.verdichtungen(conn, 1), "die Verdichtung ist entstanden"


def test_es_kommt_noch_was_laesst_alles_offen(conn, einst, tg, klm):
    lange_aufnahme(conn, tg, einst, klm)
    ja = _knoepfe_der_frage(tg, "klingt nach einem Interview")[0][1]
    _druecke(conn, tg, klm, einst, ja)
    weiter = _knoepfe_der_frage(tg, "Ist das Interview fertig")[1][1]

    _druecke(conn, tg, klm, einst, weiter, message_id=779)

    assert repo.ist_interviewmodus_an(conn, 1), "Modus bleibt an"
    assert repo.laufendes_interview(conn, 1) is not None, "Kopf bleibt offen"
    assert repo.verdichtungen(conn, 1) == [], "nichts verdichtet"


# --- (c) "Nein, war ein Beitrag" -----------------------------------------


def test_nein_macht_das_transkript_sichtbar_und_holt_den_zug_nach(conn, einst, tg, klm, monkeypatch):
    """Punkt 4c: Transkript sichtbar, Gespraechszug (mit Erkenner und Journal)
    genau EINMAL nachgeholt."""
    from interview_theater import bot

    nachgeholt = []
    monkeypatch.setattr(
        bot, "_zug_und_erkenner",
        lambda conn, tg, klm, e, chat_id, hinweis=None: nachgeholt.append(chat_id),
    )

    lange_aufnahme(conn, tg, einst, klm)
    nein = _knoepfe_der_frage(tg, "klingt nach einem Interview")[1][1]

    _druecke(conn, tg, klm, einst, nein)

    zeile = repo.hole_nachricht(conn, 1, 220)
    assert zeile["typ"] == "text", "jetzt sichtbar"
    assert zeile["unterdrueckt"] == 0

    texte = [(n["text"] or "") for n in repo.unextrahierte(conn, 1)]
    assert any(LANG in t for t in texte), "und im Erkenner-Fenster"

    for _ in range(50):
        if nachgeholt:
            break
        import time
        time.sleep(0.05)
    assert nachgeholt == [1], "genau einmal nachgeholt"
    assert aufnahme.interviews(conn, 1) == [], "kein Interview entstanden"
    assert not repo.ist_interviewmodus_an(conn, 1)


def test_zweiter_druck_wirkt_nicht(conn, einst, tg, klm):
    """Idempotenz (Zusage 3): der zweite Druck wird beantwortet, wirkt aber
    nicht -- sonst entstuenden zwei Interviews."""
    lange_aufnahme(conn, tg, einst, klm)
    ja = _knoepfe_der_frage(tg, "klingt nach einem Interview")[0][1]
    _druecke(conn, tg, klm, einst, ja)
    _druecke(conn, tg, klm, einst, ja)
    assert len(aufnahme.interviews(conn, 1)) == 1


def test_unbekannte_aufnahme_wird_freundlich_beantwortet(conn, einst, tg, klm):
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_OHNE_KNOPF_JA, "999999")
    _druecke(conn, tg, klm, einst, f"k:{knopf_id}")
    assert any("kenne ich nicht mehr" in t for _, t in tg.gesendet)
