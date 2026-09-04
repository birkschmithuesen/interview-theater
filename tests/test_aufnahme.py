"""Aufgabe 8: Aufnahme-Pipeline, Nachhol-Arbeiter, Whisper-Ausfall
(SPEC-kontext-architektur.md § 10).

Attrappen statt Netzzugriff: TelegramAttrappe ersetzt interview_theater.telegram.Telegram,
LLMAttrappe ersetzt interview_theater.llm.LLM (wie in test_verdichter.py), stt_attrappe/
stt_kaputt bauen einen httpx.Client mit MockTransport, der genau wie ein echter
Whisper-Endpunkt antwortet (wie in test_stt.py) -- so laeuft der echte
interview_theater.stt.transkribiere() in den Tests, nur ohne Netz.
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from interview_theater import aufnahme, db, einstellungen, phasen, repo

#: Ueber MINDEST_WOERTER Woerter lang (N2), sonst wuerde jedes einteilige
#: Interview in diesen Tests als "sehr kurz" abgelehnt statt verdichtet -- die
#: Wortzahl ist seit N2 Teil der Vorbedingung, nicht mehr nur Beiwerk.
TRANSKRIPT = (
    "Wir haben letzte Woche ueber das Buehnenbild gesprochen. Ich erinnere mich, "
    "wie wir als Kinder auf dem Hof Theater gespielt haben, mit Bettlaken als "
    "Vorhang. Meine Grossmutter hat immer zugeschaut und geklatscht. Danach gab "
    "es Kuchen im Garten, und mein Onkel hat auf der Trompete gespielt, bis die "
    "Nachbarin sich beschwert hat."
)

#: Zwei Teile eines Interviews, zusammen deutlich ueber MINDEST_WOERTER --
#: dieselbe Ueberlegung wie bei TRANSKRIPT. Das Zitat der LLMAttrappe steht
#: woertlich in TEIL_B.
TEIL_A = (
    "Ich bin 1998 gekommen und hatte nur einen Koffer dabei, mehr nicht. Am "
    "Bahnhof war es grau, und ich habe gedacht, ich bleibe zwei Jahre und "
    "gehe dann wieder."
)
TEIL_B = (
    "Ich erinnere mich, wie wir als Kinder auf dem Hof Theater gespielt haben, "
    "mit Bettlaken als Vorhang, und meine Grossmutter hat immer zugeschaut."
)


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
    """Ersetzt interview_theater.telegram.Telegram: kein Netzzugriff, zeichnet auf."""

    def __init__(self):
        self.gesendet = []       # Liste von (chat_id, text)
        self.getippt = []        # Liste von chat_id
        self.heruntergeladen = []  # Liste von (file_id, ziel)
        self._letzte_message_id = 9000

    def sende(self, chat_id, text):
        self.gesendet.append((chat_id, text))
        self._letzte_message_id += 1
        return self._letzte_message_id

    def tippt(self, chat_id):
        self.getippt.append(chat_id)

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")
        self.heruntergeladen.append((file_id, ziel))


class TelegramKaputterDownload(TelegramAttrappe):
    """lade_datei schlaegt IMMER fehl -- fuer den Kritisch-1-Test: ein
    Telegram-Download, der nie klappt, darf die Aufnahme nicht spurlos
    verschlucken."""

    def lade_datei(self, file_id, ziel):
        raise RuntimeError("Telegram nicht erreichbar (simuliert)")


@pytest.fixture
def tg():
    return TelegramAttrappe()


class LLMAttrappe:
    """Ersetzt interview_theater.llm.LLM: liefert immer dieselbe gueltige Antwort.

    ``nutzertexte`` haelt fest, womit verdichtet wurde -- Grundlage der
    Zusage, dass ``verdichte`` genau einmal je Interview und mit dem
    ZUSAMMENGEFUEGTEN Transkript laeuft (§ 10.6). ``aufrufe`` zaehlt deshalb
    weiterhin nur die Verdichteraufrufe.

    Seit N1 laeuft ausserdem der Absichtserkenner ueber jedes Teil-Transkript
    (``art='erkenner'``). ``erkenner_antwort`` darf eine feste Antwort oder
    eine Funktion des Nutzertexts sein -- so kann ein Test den fuenften Teil
    "fertig" sagen lassen und die vier davor nicht."""

    def __init__(self, antwort=None, erkenner_antwort=None):
        self._antwort = antwort or {
            "zusammenfassung": "Eine Erinnerung an Theaterspiele im Kindesalter.",
            "kernthemen": [
                {"thema": "Kindheit", "beleg_zitat": "wie wir als Kinder auf dem Hof Theater gespielt haben"},
            ],
        }
        self._erkenner_antwort = erkenner_antwort or {"aenderungen": []}
        self.aufrufe = 0
        self.nutzertexte = []
        self.erkenner_aufrufe = 0
        self.erkenner_texte = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
        if art == "erkenner":
            self.erkenner_aufrufe += 1
            self.erkenner_texte.append(nutzer)
            if callable(self._erkenner_antwort):
                return self._erkenner_antwort(nutzer)
            return self._erkenner_antwort
        self.aufrufe += 1
        self.nutzertexte.append(nutzer)
        return self._antwort


@pytest.fixture
def klm():
    return LLMAttrappe()


def _stt_klient(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def stt_attrappe(text: str) -> httpx.Client:
    """Ein STT-Klient, der wie ein funktionierender Whisper-Endpunkt antwortet:
    Upload liefert eine batch_id, die erste Ergebnisabfrage ist schon fertig."""

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return _stt_klient(handler)


def stt_kaputt() -> httpx.Client:
    """Ein STT-Klient, der jeden Upload sofort ablehnt (HTTP 400 -- kein
    Serverfehler, also kein Wiederholungsversuch in stt.absenden). Zwei
    Versuche (interview_theater.stt.transkribiere wiederholt genau einmal) scheitern
    beide sofort, ganz ohne time.sleep -- die Tests bleiben schnell."""

    def handler(request):
        return httpx.Response(400, json={"error": "kaputt"})

    return _stt_klient(handler)


def sprachnachricht(dauer, message_id=10, chat_id=1, file_id="FILE1", absender="Ada",
                     gesendet_am=None) -> dict:
    """Baut ein normalisiertes Nachrichten-Dictionary wie telegram.lies_nachricht()
    es fuer eine Sprachnachricht liefern wuerde."""
    return {
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
        "absender": absender,
        "typ": "sprache",
        "text": None,
        "file_id": file_id,
        "dauer": dauer,
        "gesendet_am": gesendet_am or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "antwortet_auf_bot": False,
    }


def interview_an(conn, tg=None, einst=None, chat_id=1) -> int:
    """Schaltet den Interviewmodus an und legt das Interview an -- derselbe
    Weg wie /interview und die Erkenner-art interview_starten (§ 10.6).
    Liefert die aufnahme_id des Kopfes."""
    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    return aufnahme.stelle_interview_sicher(conn, chat_id)


# ---------------------------------------------------------------------------
# Die neun wichtigsten Tests aus dem Auftrag
# ---------------------------------------------------------------------------

def test_klasse_fuer_modus_an_ergibt_teil_unabhaengig_von_der_dauer(conn):
    """Aufgabe 5 (teil-b.md, § 10.1): die Dauer spielt keine Rolle mehr --
    nur der Modus. Selbst sieben Sekunden zaehlen bei aktivem Modus als
    Material -- seit § 10.6 als *Teil* eines Interviews, nicht als eigene
    lange Aufnahme."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    assert aufnahme.klasse_fuer(conn, 1) == "teil"


def test_klasse_fuer_modus_aus_ergibt_kurz_unabhaengig_von_der_dauer(conn):
    """Spiegelbildlich: bei ausgeschaltetem Modus bleibt es *kurz*, selbst
    wenn die (hier gar nicht mehr uebergebene) Dauer 300 Sekunden waere."""
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None
    assert aufnahme.klasse_fuer(conn, 1) == "kurz"


def test_datei_ist_gespeichert_bevor_whisper_gefragt_wird(conn, einst, tg):
    """Die eigentliche Absicherung (SPEC 10.2)."""
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=120))
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "empfangen"
    from pathlib import Path
    assert Path(zeile["audio_pfad"]).exists()
    # empfange() hat Whisper nie angefasst - es gibt keinen STT-Klienten im Aufruf


def test_empfang_bestaetigt_nichts_mehr(conn, einst, tg):
    """§ 10.6: 'Ich hoere durch' ist ersatzlos weg -- in keiner Klasse. Im
    Probelauf kam die Zeile fuenfmal und danach nichts; seitdem ist das
    Transkript selbst die Bestaetigung (_teil_abschliessen)."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    assert tg.gesendet == [], "der Empfang bestaetigt sich nicht mehr selbst"

    repo.setze_interviewmodus(conn, 1, None)
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=11))
    assert tg.gesendet == [], "bei ausgeschaltetem Modus erst recht nicht"


def test_kurz_landet_als_nachricht_im_verlauf(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("Mach mal lauter"), aid)
    zeile = conn.execute("SELECT * FROM nachricht WHERE typ='text' AND ist_bot=0 "
                         "ORDER BY message_id DESC").fetchone()
    assert zeile["text"] == "Mach mal lauter"
    assert repo.hole_aufnahme(conn, aid)["status"] == "fertig"
    assert repo.verdichtungen(conn, 1) == [], "kurz wird nicht verdichtet"


def test_ein_interview_wird_am_ende_einmal_verdichtet(conn, einst, tg, klm):
    """§ 10.6: verdichtet wird bei "fertig", ueber das ganze Interview."""
    interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(TRANSKRIPT), aid)
    assert repo.verdichtungen(conn, 1) == [], "vor 'fertig' wird nichts verdichtet"

    kopf_id = aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)
    assert len(repo.verdichtungen(conn, 1)) == 1


def test_fuenf_sprachnachrichten_im_modus_ergeben_ein_interview_mit_fuenf_teilen(
    conn, einst, tg, klm
):
    """Der Auftragstest zum Nachtrag (§ 10.6, Probelauf 04.09. abends): ein
    Interview aus fuenf Sprachnachrichten ist EIN Interview mit fuenf Teilen
    -- nicht fuenf Aufnahmen 'Interview 6' bis 'Interview 10' mit fuenf
    Verdichtungen, zwei davon leer.

    Jeder Teil bekommt sein Transkript sofort und woertlich in den Chat, in
    der Reihenfolge, in der er eintraf; verdichtet wird bis "fertig" nichts."""
    kopf_id = interview_an(conn, tg, einst)
    for i in range(5):
        n = sprachnachricht(dauer=7, message_id=200 + i)
        aid = aufnahme.empfange(conn, tg, einst, n)
        zeile = repo.hole_aufnahme(conn, aid)
        assert zeile["klasse"] == "teil"
        assert zeile["teil_von"] == kopf_id
        aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(f"Stueck {i + 1}"), aid)

    assert len(repo.transkripte(conn, 1)) == 1, "nach aussen ist das ein Interview"
    assert len(repo.hole_teile(conn, kopf_id)) == 5
    assert repo.verdichtungen(conn, 1) == [], "keine Verdichtung bis 'fertig'"
    assert klm.aufrufe == 0, "kein Modellaufruf im Live-Pfad"

    echos = [t for _, t in tg.gesendet if t.startswith("Interview 1, Teil")]
    assert echos == [
        f"Interview 1, Teil {i + 1}:\nStueck {i + 1}" for i in range(5)
    ]


def test_modus_ueberlebt_eine_neue_verbindung(tmp_path):
    """Aufgabe 5, Auftragstest: der Modus steht in der Datenbank
    (gruppe.interviewmodus_seit), nicht in einem Prozessspeicher -- ein
    Neustart darf ihn nicht vergessen."""
    pfad = str(tmp_path / "modus.db")
    erste_verbindung = db.verbinde(pfad)
    db.initialisiere(erste_verbindung)
    repo.sichere_gruppe(erste_verbindung, 1, "gruppe1", "Testgruppe")
    repo.setze_interviewmodus(erste_verbindung, 1, repo._jetzt())

    zweite_verbindung = db.verbinde(pfad)
    assert aufnahme.klasse_fuer(zweite_verbindung, 1) == "teil"


def test_aktiver_modus_loest_bei_sprachnachricht_keinen_gespraechszug_aus(conn, einst, tg, klm):
    """Aufgabe 5, Auftragstest: waehrend des Interviewmodus ist eine
    Sprachnachricht Material, kein Gespraechsbeitrag -- sie darf keinen Zug
    ausloesen. Seit § 10.6 bekommt die Gruppe stattdessen das Transkript, und
    zwar ohne jeden Modellaufruf."""
    interview_an(conn, tg, einst)
    aufgerufen = []

    def zug(conn, tg, klm, e, chat_id, hinweis=None):
        aufgerufen.append(chat_id)

    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=210))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(TRANSKRIPT), aid, zug=zug)

    assert aufgerufen == [], "Material darf keinen Gespraechszug ausloesen"
    assert klm.aufrufe == 0, "und keinen Modellaufruf"
    assert any(TRANSKRIPT in t for _, t in tg.gesendet), "das Transkript geht in den Chat"


def test_hinweis_bei_langer_aufnahme_ausserhalb_des_modus(conn, einst, tg, klm):
    """Aufgabe 5, § 10.1: ueber HINWEIS_AB_S Sekunden UND Modus aus haengt der
    Zug einen beilaeufigen Hinweis an -- keine eigene Nachricht, keine
    Rueckfrage, nur ein zusaetzliches Argument fuer die ohnehin faellige
    Antwort."""
    gesehen = {}

    def zug(conn, tg, klm, e, chat_id, hinweis=None):
        gesehen["hinweis"] = hinweis

    aid = aufnahme.empfange(
        conn, tg, einst, sprachnachricht(dauer=aufnahme.HINWEIS_AB_S + 1, message_id=220)
    )
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("eine lange Erzaehlung"), aid, zug=zug)

    assert gesehen["hinweis"] is not None
    assert "Material" in gesehen["hinweis"]


def test_kein_hinweis_unter_der_schwelle_oder_bei_aktivem_modus(conn, einst, tg, klm):
    gesehen = {}

    def zug(conn, tg, klm, e, chat_id, hinweis=None):
        gesehen["hinweis"] = hinweis

    aid = aufnahme.empfange(
        conn, tg, einst, sprachnachricht(dauer=aufnahme.HINWEIS_AB_S, message_id=230)
    )
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("kurz genug"), aid, zug=zug)
    assert gesehen["hinweis"] is None


def test_zeitbudget_ueberschritten_meldet_der_gruppe(conn, einst, tg, klm):
    interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    assert repo.hole_aufnahme(conn, aid)["status"] in ("empfangen", "fehlgeschlagen")
    assert any("nochmal" in t for _, t in tg.gesendet)


def test_whisper_ausfall_wird_genau_einmal_gemeldet(conn, einst, tg, klm):
    for i in range(3):
        aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=20 + i))
        aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    meldungen = [t for _, t in tg.gesendet if "nicht hoeren" in t]
    assert len(meldungen) == 1, "nicht bei jeder Nachricht wiederholen"


def test_rueckkehr_wird_gemeldet(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    aid2 = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=30))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("da"), aid2)
    assert any("wieder hoeren" in t for _, t in tg.gesendet)
    assert repo.hole_gruppe(conn, 1)["whisper_stumm_seit"] is None


def test_nachholen_greift_empfangene_auf_und_loest_keine_antwort_aus(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    aufnahme.nachholen(conn, tg, klm, einst, stt_attrappe("nachgeholt"))
    zeile = conn.execute("SELECT * FROM nachricht WHERE text='nachgeholt'").fetchone()
    assert zeile["unterdrueckt"] == 1, "Nachgeholtes loest nie eine Antwort aus"


def test_textimport_erzeugt_material_wie_eine_aufnahme(conn, einst, tg, klm):
    """Wie im urspruenglichen Auftragstest, aber ueber aufnahme.verarbeite()
    statt eines direkten verdichter.verdichte()-Aufrufs (Nachbesserung
    'Kritisch 2'): der Verdichtungsschritt laeuft ausschliesslich ueber
    verarbeite(), das nach Erfolg auch den Status auf 'fertig' setzt --
    direktes verdichter.verdichte() wuerde die Aufnahme bei 'transkribiert'
    stehen lassen und den Nachhol-Arbeiter zu einer zweiten, bezahlten
    Verdichtung derselben Aufnahme verleiten (siehe naechster Test)."""
    aid = aufnahme.importiere_text(conn, einst, 1, 40, TRANSKRIPT, name="Recherche")
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["quelle"] == "text" and zeile["status"] == "transkribiert"

    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)

    assert repo.hole_aufnahme(conn, aid)["status"] == "fertig"
    assert len(repo.verdichtungen(conn, 1)) == 1


def test_textimport_dann_nachholen_verdichtet_nur_einmal(conn, einst, tg, klm):
    """Kritisch 2, der eigentliche Regressionstest: importiere_text() laesst
    die Aufnahme bei 'transkribiert'. Ein anschliessender Nachhol-Lauf darf
    sie genau einmal verdichten und muss danach status='fertig' erreichen,
    damit ein zweiter Nachhol-Lauf sie nicht noch einmal aufgreift."""
    aid = aufnahme.importiere_text(conn, einst, 1, 41, TRANSKRIPT, name="Recherche 2")

    aufnahme.nachholen(conn, tg, klm, einst, stt_kaputt())
    assert len(repo.verdichtungen(conn, 1)) == 1
    assert repo.hole_aufnahme(conn, aid)["status"] == "fertig"

    # ein zweiter Nachhol-Lauf darf keine weitere Verdichtung mehr erzeugen
    aufnahme.nachholen(conn, tg, klm, einst, stt_kaputt())
    assert len(repo.verdichtungen(conn, 1)) == 1


# ---------------------------------------------------------------------------
# Ein Interview ist eine Einheit (§ 10.6, Nachtrag 05.09.2026)
# ---------------------------------------------------------------------------

def _interview_mit_teilen(conn, einst, tg, klm, texte, message_id=300):
    """Ein vollstaendig eingesprochenes Interview: Modus an, je
    Sprachnachricht ein Teil samt Transkript. Liefert die aufnahme_id des
    Kopfes."""
    kopf_id = interview_an(conn, tg, einst)
    for i, text in enumerate(texte):
        aid = aufnahme.empfange(
            conn, tg, einst, sprachnachricht(dauer=60, message_id=message_id + i)
        )
        aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(text), aid)
    return kopf_id


def test_fertig_verdichtet_einmal_ueber_das_ganze_interview(conn, einst, tg, klm):
    """§ 10.6, der zweite Auftragstest: "fertig" loest genau EINEN
    verdichte-Aufruf aus, und zwar mit dem zusammengefuegten Text -- und die
    Gruppe bekommt endlich zu hoeren, was in ihrem Interview steckt."""
    kopf_id = _interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B])
    tg.gesendet.clear()

    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)

    assert klm.aufrufe == 1, "genau ein Modellaufruf je Interview"
    assert klm.nutzertexte == [f"{TEIL_A}\n\n{TEIL_B}"]
    assert repo.hole_aufnahme(conn, kopf_id)["status"] == "fertig"

    meldungen = [t for _, t in tg.gesendet if "ist durch" in t]
    assert len(meldungen) == 1
    text = meldungen[0]
    assert text.startswith("Interview 1 ist durch. Was ich darin hoere:")
    assert "Eine Erinnerung an Theaterspiele im Kindesalter." in text
    assert "Kernthemen:" in text
    assert '- Kindheit: "wie wir als Kinder auf dem Hof Theater gespielt haben"' in text
    assert text.endswith("Stimmt das so? Sonst sagt es mir.")


def test_die_erste_verdichtung_fragt_nach_der_naechsten_phase(conn, einst, tg, klm):
    """Brief 3 (C): der Datenstand erlaubt jetzt Phase 4, aber er entscheidet
    sie nicht -- eine fertige Verdichtung sagt nicht, ob noch drei Interviews
    kommen. Also haengt an der Verdichtung eine Frage, keine Ankuendigung.

    Sie steht genau hier und nicht erst im naechsten Gespraechszug: hier ist
    der Moment, in dem sie aufkommt."""
    phasen.setze(conn, 1, 3, "befehl")
    kopf_id = _interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B], message_id=340)
    tg.gesendet.clear()

    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)

    text = next(t for _, t in tg.gesendet if "ist durch" in t)
    assert text.endswith("Kommen noch Interviews, oder gehen wir ans Kernthema?")
    assert repo.hole_phase(conn, 1) == 3, "gefragt, nicht geschaltet"
    assert repo.hole_phase_angeboten(conn, 1) == 4


def test_die_phasenfrage_kommt_nur_einmal(conn, einst, tg, klm):
    """Bei fuenf Interviews wuerde sie sonst fuenfmal dastehen. Der Merkposten
    ist derselbe wie fuer den Gespraechs-Prompt (arbeitsstand.phase_angeboten)
    -- eine Frage, egal auf welchem Weg sie herauskommt."""
    phasen.setze(conn, 1, 3, "befehl")
    erster = _interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B], message_id=350)
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, erster)

    zweiter = _interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B], message_id=360)
    tg.gesendet.clear()
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, zweiter)

    text = next(t for _, t in tg.gesendet if "ist durch" in t)
    assert "Kommen noch Interviews" not in text


def test_ausserhalb_von_phase_drei_keine_phasenfrage(conn, einst, tg, klm):
    """Ist die Gruppe schon beim Kernthema, ist die Frage beantwortet -- und
    der Merkposten bleibt unangetastet, damit der Gespraechs-Prompt seine
    eigene Frage noch stellen kann."""
    phasen.setze(conn, 1, 4, "befehl")
    kopf_id = _interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B], message_id=370)
    tg.gesendet.clear()

    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)

    text = next(t for _, t in tg.gesendet if "ist durch" in t)
    assert text.endswith("Stimmt das so? Sonst sagt es mir.")
    assert repo.hole_phase_angeboten(conn, 1) is None


def test_thema_ohne_belegtes_zitat_faellt_ganz_weg(conn, einst, tg):
    """N2: ein Thema, dessen Zitat nicht im Transkript steht, wird gar nicht
    erst gespeichert -- frueher blieb es mit ``zitat_geprueft=0`` stehen und
    stand damit im Chat, im Prompt und auf der Gruppenseite."""
    klm = LLMAttrappe(antwort={
        "zusammenfassung": "Zwei Themen.",
        "kernthemen": [
            {"thema": "Kindheit", "beleg_zitat": "auf dem Hof Theater gespielt"},
            {"thema": "Arbeit", "beleg_zitat": "so hat das niemand gesagt"},
        ],
    })
    kopf_id = _interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B], message_id=310)
    tg.gesendet.clear()

    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)

    themen = repo.themen_zu(conn, repo.verdichtungen(conn, 1)[0]["id"])
    assert [t["thema"] for t in themen] == ["Kindheit"]

    text = next(t for _, t in tg.gesendet if "ist durch" in t)
    assert '- Kindheit: "auf dem Hof Theater gespielt"' in text
    assert "Arbeit" not in text
    assert "so hat das niemand gesagt" not in text


def test_keine_belegte_these_meldet_die_leerstelle(conn, einst, tg):
    """N2: bleibt kein einziges Thema uebrig, wird die Verdichtung mit leerer
    Themenliste gespeichert und der Bot sagt es -- statt eine
    Kernthemen-Ueberschrift ueber nichts zu setzen."""
    klm = LLMAttrappe(antwort={
        "zusammenfassung": "Ich habe eine Zusammenfassung, aber keinen Beleg.",
        "kernthemen": [{"thema": "Heimweh", "beleg_zitat": "das hat niemand gesagt"}],
    })
    kopf_id = _interview_mit_teilen(conn, einst, tg, klm, [TEIL_A, TEIL_B], message_id=320)
    tg.gesendet.clear()

    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)

    verdichtung = repo.verdichtungen(conn, 1)[0]
    assert repo.themen_zu(conn, verdichtung["id"]) == []

    text = next(t for _, t in tg.gesendet if "ist durch" in t)
    assert "Ich habe eine Zusammenfassung, aber keinen Beleg." in text
    assert "Ich konnte kein Thema mit einem woertlichen Zitat belegen." in text
    assert "Kernthemen:" not in text
    assert "Heimweh" not in text


def test_sehr_kurzes_interview_wird_nicht_verdichtet(conn, einst, tg, klm):
    """N2, der Fall aus dem Probelauf: aus einer vier Sekunden langen
    Sprachnachricht ("Zeigt mir die Verdichtungen von den Interviews an.")
    erfand das Modell ein komplettes Interview. Unter MINDEST_WOERTER wird
    deshalb gar nicht erst gefragt -- die Gruppe erfaehrt, warum."""
    kopf_id = interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=4, message_id=330))
    aufnahme.verarbeite(
        conn, tg, klm, einst,
        stt_attrappe("Zeigt mir die Verdichtungen von den Interviews an."), aid,
    )
    tg.gesendet.clear()

    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)

    assert klm.aufrufe == 0, "kein Modellaufruf unter der Mindestlaenge"
    assert repo.verdichtungen(conn, 1) == []
    assert repo.hole_aufnahme(conn, kopf_id)["status"] == "fertig"
    assert [t for _, t in tg.gesendet] == [
        "Interview 1 ist sehr kurz (4 s, 8 Woerter). Ich werte es nicht aus - "
        "sagt Bescheid, wenn ich es trotzdem soll."
    ]


def test_auswerten_verdichtet_ein_zu_kurzes_interview_doch(conn, einst, tg, klm):
    """N2: die Gruppe kennt ihr Material besser als eine Wortzahl.
    ``aufnahme.starte_auswertung`` (hinter ``/auswerten``) uebergeht die
    Mindestlaenge und verdichtet trotzdem."""
    kopf_id = interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=4, message_id=340))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("nur ein kurzer Satz"), aid)
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)
    assert klm.aufrufe == 0
    tg.gesendet.clear()

    aufnahme.starte_auswertung(conn, tg, klm, einst, kopf_id).join(timeout=5)

    assert klm.aufrufe == 1
    assert len(repo.verdichtungen(conn, 1)) == 1
    assert any("ist durch" in t for _, t in tg.gesendet)


def _warte_bis(bedingung, sekunden=5.0):
    """Wartet, bis ``bedingung()`` wahr ist -- fuer die Wege, die ueber
    ``aufnahme.starte_abschluss`` in einen eigenen Thread abbiegen (dieselbe
    Zusage wie bei /fertig: kein Befehl und kein Teil-Abschluss haelt den
    Aufrufer fest)."""
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if bedingung():
            return True
        time.sleep(0.02)
    return bedingung()


def _fertig_wenn_gesagt(nutzer):
    """Erkenner-Attrappe fuer N1: erkennt "das Interview ist fertig" im
    Transkript einer Sprachnachricht, sonst nichts."""
    if "interview ist fertig" in nutzer.lower():
        return {"aenderungen": [{"art": "interview_beenden", "wert": ""}]}
    return {"aenderungen": []}


def test_fertig_in_der_sprachnachricht_beendet_das_interview(conn, einst, tg):
    """N1, der Auftragstest: fuenf Teile, der fuenfte endet mit "so, das
    Interview ist fertig" -- gesagt in die Aufnahme hinein, nicht in den Chat.

    Vorher lief der Bot einfach weiter: das Transkript-Echo steht in keinem
    Erkenner-Fenster (repo.TYP_TRANSKRIPT), also sah er den Satz nie."""
    klm = LLMAttrappe(erkenner_antwort=_fertig_wenn_gesagt)
    kopf_id = interview_an(conn, tg, einst)
    texte = [TEIL_A, TEIL_B, "Und dann kam der Sommer.", "Meine Schwester auch.",
             "Ja, so war das. So, das Interview ist fertig."]
    for i, text in enumerate(texte):
        aid = aufnahme.empfange(
            conn, tg, einst, sprachnachricht(dauer=30, message_id=500 + i)
        )
        aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(text), aid)

    assert klm.erkenner_aufrufe == 5, "je Teil ein Erkennerlauf"
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None, "Modus aus"
    assert len(repo.hole_teile(conn, kopf_id)) == 5, (
        "der fuenfte Teil bleibt Teil des Interviews"
    )
    assert texte[-1] in repo.zusammengefuegtes_transkript(conn, kopf_id)
    assert _warte_bis(lambda: repo.verdichtungen(conn, 1)), "die Verdichtung kommt"
    assert len(repo.verdichtungen(conn, 1)) == 1, "genau eine Verdichtung"
    assert repo.hole_aufnahme(conn, kopf_id)["status"] == "fertig"

    gesendet = [t for _, t in tg.gesendet]
    assert "Aufnahme beendet." in gesendet
    assert any("Interview 1 ist durch" in t for t in gesendet)


def test_erkenner_darf_aus_interviewinhalt_nichts_anderes_schreiben(conn, einst, tg):
    """N1, die Grenze: der Lauf ueber ein Teil-Transkript kennt nur
    ``interview_beenden`` und ``interview_benennen``. Was die interviewte
    Person erzaehlt, ist Material -- die Korpusfaelle n12/n26, hier im Code
    durchgesetzt und nicht nur im Prompt erbeten."""
    klm = LLMAttrappe(erkenner_antwort={"aenderungen": [
        {"art": "kernthema_setzen", "wert": "Ankommen"},
        {"art": "figur_setzen", "wert": "Mutter: streng"},
        {"art": "entfernen", "wert": "Kernthema"},
    ]})
    interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=30, message_id=520))
    aufnahme.verarbeite(
        conn, tg, klm, einst,
        stt_attrappe("Mein Kernthema war immer das Ankommen, sagt meine Mutter."), aid,
    )

    assert repo.hole_arbeitsstand(conn, 1) is None
    assert repo.figuren(conn, 1) == []
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is not None


def test_transkript_echo_steht_in_keinem_fenster(conn, einst, tg, klm):
    """§ 10.6, der dritte Auftragstest: das Echo wird gespeichert (Empfangen
    und In-den-Prompt-legen sind zwei Entscheidungen, SPEC § 1), taucht aber
    weder im Erkenner-Fenster (``unextrahierte``) noch im Gespraechsfenster
    (``letzte_nachrichten``) auf.

    Sonst laese der Absichtserkenner, was die interviewte Person erzaehlt, als
    Absicht der Gruppe -- die Korpusfaelle n12/n26."""
    repo.merke_nachricht(conn, 1, 400, "Ada", 0, "text", "wir machen jetzt ein Interview",
                         repo._jetzt())
    _interview_mit_teilen(conn, einst, tg, klm, ["Mein Kernthema ist die Kindheit."],
                          message_id=401)

    echo = conn.execute(
        "SELECT * FROM nachricht WHERE typ = 'transkript'"
    ).fetchall()
    assert len(echo) == 1, "das Echo steht in der Datenbank"
    assert "Mein Kernthema ist die Kindheit." in echo[0]["text"]

    assert all(z["typ"] != "transkript" for z in repo.unextrahierte(conn, 1))
    assert all(z["typ"] != "transkript" for z in repo.letzte_nachrichten(conn, 1))
    assert all(z["typ"] != "transkript" for z in repo.unjournalisierte(conn, 1))
    assert all(z["typ"] != "transkript" for z in repo.unbeantwortete(conn, 1))


def test_fertig_ohne_aufnahme_meldet_und_ruft_kein_modell(conn, einst, tg, klm):
    """§ 10.6, der vierte Auftragstest: Modus an, nichts eingesprochen,
    "fertig". Im Probelauf entstanden aus solchem Nichts Verdichtungen mit
    "Material extrem kurz" -- jetzt gibt es eine Zeile und keinen Aufruf."""
    kopf_id = interview_an(conn, tg, einst)
    tg.gesendet.clear()

    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id)

    assert klm.aufrufe == 0
    assert repo.verdichtungen(conn, 1) == []
    assert repo.hole_aufnahme(conn, kopf_id)["status"] == "fertig"
    assert [t for _, t in tg.gesendet] == [
        "Interview 1 hatte keine Aufnahme - ich habe nichts verdichtet."
    ]


def test_zweites_interview_zaehlt_weiter_und_zuruf_dazwischen_nicht(conn, einst, tg, klm):
    """"Interview N" ist die laufende INTERVIEWnummer (§ 10.6), nicht die
    Zahl aller Aufnahmen: ein Zuruf zwischendurch und die fuenf
    Sprachnachrichten eines Interviews verschieben die Zaehlung nicht."""
    erstes = _interview_mit_teilen(conn, einst, tg, klm, ["eins", "zwei"], message_id=320)
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, klm, einst, erstes)

    aid_kurz = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=330))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("mach mal lauter"), aid_kurz)
    assert repo.hole_aufnahme(conn, aid_kurz)["name"] is None, "ein Zuruf ist kein Interview"

    zweites = _interview_mit_teilen(conn, einst, tg, klm, ["drei"], message_id=340)
    assert repo.hole_aufnahme(conn, zweites)["name"] == "Interview 2"
    assert [a["name"] for a in repo.transkripte(conn, 1) if a["klasse"] == "lang"] == [
        "Interview 1", "Interview 2",
    ]


def test_nachholen_transkribiert_teil_nach_und_verdichtet_das_beendete_interview(
    conn, einst, tg, klm
):
    """§ 10.6, der fuenfte Auftragstest: beide Haelften des Nachhol-Arbeiters.

    Teil 2 scheitert live an Whisper, die Gruppe sagt trotzdem "fertig". Es
    wird NICHT verdichtet, solange der Teil offen ist -- sonst fehlte im
    Transkript ausgerechnet er. Der naechste Nachhol-Lauf holt das Transkript
    nach (samt Echo), fuegt zusammen, verdichtet und meldet."""
    kopf_id = interview_an(conn, tg, einst)
    aid1 = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=60, message_id=350))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(TEIL_A), aid1)
    aid2 = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=60, message_id=351))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid2)
    assert repo.hole_aufnahme(conn, aid2)["status"] == "empfangen"

    aufnahme.beende_interview(conn, 1)
    assert aufnahme.schliesse_ab(conn, tg, klm, einst, kopf_id) is False
    assert klm.aufrufe == 0, "kein Verdichten, solange ein Teil offen ist"
    tg.gesendet.clear()

    aufnahme.nachholen(conn, tg, klm, einst, stt_attrappe(TEIL_B))

    assert repo.hole_aufnahme(conn, aid2)["status"] == "fertig"
    assert any(f"Interview 1, Teil 2:\n{TEIL_B}" == t for _, t in tg.gesendet)
    assert klm.nutzertexte == [f"{TEIL_A}\n\n{TEIL_B}"]
    assert len(repo.verdichtungen(conn, 1)) == 1
    assert any("ist durch" in t for _, t in tg.gesendet)

    # Ein zweiter Nachhol-Lauf greift nichts mehr auf.
    aufnahme.nachholen(conn, tg, klm, einst, stt_attrappe("egal"))
    assert klm.aufrufe == 1


def test_laufendes_interview_wird_vom_nachhol_arbeiter_nicht_verdichtet(conn, einst, tg, klm):
    """Ein Interview, das noch laeuft, ist keine liegengebliebene Arbeit: der
    Nachhol-Arbeiter darf es nicht mitten im Satz verdichten (repo.
    _NICHTS_ZU_TUN)."""
    _interview_mit_teilen(conn, einst, tg, klm, ["laeuft noch"], message_id=360)

    aufnahme.nachholen(conn, tg, klm, einst, stt_kaputt())

    assert klm.aufrufe == 0
    assert repo.verdichtungen(conn, 1) == []


def test_starte_abschluss_laeuft_im_eigenen_thread(conn, einst, tg, klm):
    """/fertig und der Erkenner geben die Verdichtung an einen Thread ab --
    kein Befehl ruft synchron ein Modell (AGENTS.md)."""
    kopf_id = _interview_mit_teilen(conn, einst, tg, klm, [TRANSKRIPT], message_id=370)
    aufnahme.beende_interview(conn, 1)

    thread = aufnahme.starte_abschluss(conn, tg, klm, einst, kopf_id)
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(repo.verdichtungen(conn, 1)) == 1


# ---------------------------------------------------------------------------
# Zusaetzliche Tests fuer die sechs Punkte, die der Auftrag nicht vollstaendig
# ausfuehrt.
# ---------------------------------------------------------------------------

def test_konstanten_haben_die_gemessenen_werte():
    """Auftragshinweis 5: alle Konstanten an genau einer Stelle, mit den
    Werten aus der Messung vom 03.09.2026. KURZ_GRENZE_S gibt es seit
    Aufgabe 5 nicht mehr (die Dauer klassifiziert nicht mehr)."""
    assert not hasattr(aufnahme, "KURZ_GRENZE_S")
    assert aufnahme.HINWEIS_AB_S == 60
    assert aufnahme.TIPPANZEIGE_AB_S == 5
    assert aufnahme.MELDUNG_AB_S == 12
    assert aufnahme.BUDGET_KURZ_S == 45
    assert aufnahme.BUDGET_LANG_S == 90
    assert aufnahme.NACHHOL_INTERVALL_S == 60
    assert aufnahme.MAX_VERSUCHE == 5


def test_junge_kurze_aufnahme_loest_gespraechszug_aus_alte_nicht(conn, einst, tg, klm):
    """Auftragshinweis 1: nur eine zum Zeitpunkt des fertigen Transkripts unter
    15 Minuten alte Nachricht darf unterdrueckt=0 werden und den (hier per
    Parameter hereingereichten) Gespraechszug ausloesen."""
    aufgerufen = []

    def zug(conn, tg, klm, e, chat_id, hinweis=None):
        aufgerufen.append(chat_id)

    n_jung = sprachnachricht(dauer=7, message_id=50)
    aid_jung = aufnahme.empfange(conn, tg, einst, n_jung)
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("frisch"), aid_jung, zug=zug)
    zeile_jung = conn.execute("SELECT * FROM nachricht WHERE message_id=50").fetchone()
    assert zeile_jung["unterdrueckt"] == 0
    assert aufgerufen == [1]

    alt = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(timespec="seconds")
    n_alt = sprachnachricht(dauer=7, message_id=51, gesendet_am=alt)
    aid_alt = aufnahme.empfange(conn, tg, einst, n_alt)
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("spaet"), aid_alt, zug=zug)
    zeile_alt = conn.execute("SELECT * FROM nachricht WHERE message_id=51").fetchone()
    assert zeile_alt["unterdrueckt"] == 1
    assert aufgerufen == [1], "die alte Nachricht darf keinen zweiten Zug ausloesen"


def test_transkript_aktualisiert_bestehende_zeile_ohne_duplikat(conn, einst, tg, klm):
    """Auftragshinweis 2: UPDATE der vorhandenen Zeile, keine zweite Zeile."""
    n = sprachnachricht(dauer=7, message_id=60)
    aid = aufnahme.empfange(conn, tg, einst, n)
    vorher = conn.execute("SELECT count(*) FROM nachricht WHERE chat_id=1").fetchone()[0]
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("Text da"), aid)
    nachher = conn.execute("SELECT count(*) FROM nachricht WHERE chat_id=1").fetchone()[0]
    assert nachher == vorher, "Transkript aktualisiert die vorhandene Zeile statt eine neue anzulegen"


def test_nachholen_beruecksichtigt_nur_aufnahmen_des_eigenen_bots(conn, einst):
    """Auftragshinweis 3 (gewaehlte Loesung): offene_aufnahmen_fuer_bot()
    filtert nach gruppe.bot_name, damit zwei Prozesse auf derselben SQLite-
    Datei sich nicht gegenseitig die Aufnahmen der jeweils anderen Gruppe
    stehlen und doppelt zu Whisper hochladen."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere Gruppe")
    a_eigen = repo.lege_aufnahme_an(conn, 1, 900, "kurz", "sprache", audio_pfad="a.ogg", dauer=7)
    repo.lege_aufnahme_an(conn, 2, 901, "kurz", "sprache", audio_pfad="b.ogg", dauer=7)

    ids = {z["id"] for z in repo.offene_aufnahmen_fuer_bot(conn, "gruppe1")}
    assert ids == {a_eigen}


def test_nach_max_versuchen_gilt_die_aufnahme_als_fehlgeschlagen(conn, einst, tg, klm):
    """Auftragshinweis (SPEC § 10.3): nach MAX_VERSUCHE erfolglosen Anlaeufen
    wird eine Aufnahme fehlgeschlagen, statt bis Sonntagabend im Kreis zu laufen.

    Wichtig 3 (Nachbesserung): eine Aufnahme der Klasse *kurz*, die endgueltig
    scheitert, darf nicht kommentarlos im Verlauf verschwinden -- beim
    Uebergang auf 'fehlgeschlagen' muss die Gruppe eine Zeile bekommen, aber
    (Wichtig 2) NICHT bei jedem der vorherigen Zwischenversuche."""
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=70))
    for _ in range(aufnahme.MAX_VERSUCHE):
        aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "fehlgeschlagen"
    assert zeile["versuche"] == aufnahme.MAX_VERSUCHE

    endgueltig_gemeldet = [t for _, t in tg.gesendet if "verstehen" in t and "nochmal" in t]
    assert len(endgueltig_gemeldet) == 1, "kurz bekommt genau eine Meldung, beim endgueltigen Aufgeben"


def test_verdichtung_scheitert_interview_bleibt_transkribiert_fuer_nachhol_arbeiter(conn, einst, tg):
    """Schlaegt die Verdichtung fehl, bleibt das schon zusammengefuegte
    Transkript erhalten (status='transkribiert') -- der Nachhol-Arbeiter darf
    es beim naechsten Anlauf direkt weiterverdichten, ohne ein zweites Mal
    Whisper zu fragen."""

    class KaputtesLLM:
        def schema(self, chat_id, system, nutzer, schema, art):
            raise RuntimeError("Sprachmodell nicht erreichbar")

    kopf_id = interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=80))
    aufnahme.verarbeite(conn, tg, KaputtesLLM(), einst, stt_attrappe(TRANSKRIPT), aid)
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, tg, KaputtesLLM(), einst, kopf_id)

    zeile = repo.hole_aufnahme(conn, kopf_id)
    assert zeile["status"] == "transkribiert"
    assert zeile["transkript"] == TRANSKRIPT
    assert repo.verdichtungen(conn, 1) == []

    aufnahme.verarbeite(conn, tg, LLMAttrappe(), einst, stt_kaputt(), kopf_id)
    assert repo.hole_aufnahme(conn, kopf_id)["status"] == "fertig"
    assert len(repo.verdichtungen(conn, 1)) == 1


def test_verdichtung_ueber_max_versuchen_gilt_als_fehlgeschlagen(conn, einst, tg):
    """Kritisch 2: eine dauerhaft scheiternde Verdichtung ist ein bezahlter
    Sprachmodell-Aufruf und darf nicht unbegrenzt oft alle NACHHOL_INTERVALL_S
    Sekunden wiederholt werden. Ab MAX_VERSUCHE wird endgueltig aufgegeben,
    das Transkript bleibt aber erhalten und die Gruppe erfaehrt davon."""

    class KaputtesLLM:
        def schema(self, chat_id, system, nutzer, schema, art):
            raise RuntimeError("Sprachmodell nicht erreichbar")

    kopf_id = interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=81))
    aufnahme.verarbeite(conn, tg, KaputtesLLM(), einst, stt_attrappe(TRANSKRIPT), aid)
    aufnahme.beende_interview(conn, 1)
    # Der erste Anlauf fuegt zusammen und scheitert an der Verdichtung; alle
    # weiteren finden schon status='transkribiert' vor und fragen Whisper gar
    # nicht erst -- der STT-Klient ist dort egal.
    aufnahme.schliesse_ab(conn, tg, KaputtesLLM(), einst, kopf_id)
    for _ in range(aufnahme.MAX_VERSUCHE - 1):
        aufnahme.verarbeite(conn, tg, KaputtesLLM(), einst, stt_kaputt(), kopf_id)

    zeile = repo.hole_aufnahme(conn, kopf_id)
    assert zeile["status"] == "fehlgeschlagen"
    assert zeile["versuche"] == aufnahme.MAX_VERSUCHE
    assert zeile["transkript"] == TRANSKRIPT, "das Transkript bleibt trotz gescheiterter Verdichtung erhalten"
    assert repo.verdichtungen(conn, 1) == []
    assert any("auswerten" in t for _, t in tg.gesendet)


def test_interviewteil_bekommt_bitte_nochmal_nur_einmal(conn, einst, tg, klm):
    """Wichtig 2: bei mehreren Nachhol-Anlaeufen derselben Aufnahme (Material,
    also alles ausser Klasse *kurz*) geht die 'schickt sie bitte nochmal'-Bitte
    nur beim ersten Fehlschlag raus, nicht bei jedem der bis zu MAX_VERSUCHE
    Versuche."""
    interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=82))
    for _ in range(3):
        aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)

    bitten = [t for _, t in tg.gesendet if "nochmal" in t]
    assert len(bitten) == 1, "die Bitte, es nochmal zu schicken, wiederholt sich nicht"


def test_bitte_nochmal_benennt_den_teil_und_keinen_ersatznamen(conn, einst, tg, klm):
    """Zwei Faelle, eine Regel: die Gruppe muss wissen, WAS sie nochmal
    schicken soll.

    Bei einem Interview-Teil ist das 'Interview 1, Teil 1' -- bei fuenf
    Sprachnachrichten die einzige brauchbare Angabe (§ 10.6). Bei einem
    Gespraechsbeitrag gibt es nichts zu benennen, und der Ersatzname waere
    unfreiwillig komisch ('Die Aufnahme von Interview 1...') -- dort wird die
    Klasse genannt."""
    interview_an(conn, tg, einst)
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=83))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)

    nachrichten = [t for _, t in tg.gesendet if "nochmal" in t]
    assert len(nachrichten) == 1
    assert "Interview 1, Teil 1" in nachrichten[0]

    repo.setze_interviewmodus(conn, 1, None)
    tg.gesendet.clear()
    aid_kurz = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=84))
    for _ in range(aufnahme.MAX_VERSUCHE):
        aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid_kurz)
    nachrichten_kurz = [t for _, t in tg.gesendet if "nochmal" in t]
    assert len(nachrichten_kurz) == 1
    assert "Interview" not in nachrichten_kurz[0]
    assert "letzte kurze Aufnahme" in nachrichten_kurz[0]


def test_zwischenmeldung_auch_bei_einem_interviewteil(conn, einst, tg, klm, monkeypatch):
    """Die 12-Sekunden-Zwischenmeldung ('Ich hoer noch zu...') gilt seit
    § 10.6 fuer jede Sprachnachricht: die Empfangsbestaetigung, die frueher
    fuer Material sprach, gibt es nicht mehr, und wer gerade eingesprochen
    hat, wartet auf das Transkript.

    Sie feuert nur bei einer wirklich langsamen Transkription -- im Normalfall
    (unter drei Sekunden, gemessen 03.09.2026) nie."""
    interview_an(conn, tg, einst)
    aid_schnell = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=90))
    tg.gesendet.clear()
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("ok"), aid_schnell)
    assert not any("hoer noch zu" in t for _, t in tg.gesendet), "schnell genug, also still"

    monkeypatch.setattr(aufnahme, "MELDUNG_AB_S", 0.01)
    monkeypatch.setattr(aufnahme, "TIPPANZEIGE_AB_S", 100)  # soll hier nicht stoeren

    def handler_langsam(request):
        time.sleep(0.1)
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={"status": "success", "data": json.dumps({"text": "ok"})})

    for message_id, modus in ((91, True), (92, False)):
        klient = httpx.Client(transport=httpx.MockTransport(handler_langsam))
        repo.setze_interviewmodus(conn, 1, repo._jetzt() if modus else None)
        aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=message_id))
        tg.gesendet.clear()
        aufnahme.verarbeite(conn, tg, klm, einst, klient, aid)
        assert any("hoer noch zu" in t for _, t in tg.gesendet), (
            f"Zwischenmeldung fehlt bei langsamer Transkription (Interviewmodus {modus})"
        )


def test_download_scheitert_endgueltig_meldet_vorfall_und_gruppe(conn, einst, monkeypatch):
    """Kritisch 1: die eigentliche Absicherung dieser Aufgabe faengt bei
    Whisper an -- ein fehlschlagender TELEGRAM-Download darf die Aufnahme
    ebenso wenig spurlos verlieren. lade_datei schlaegt hier IMMER fehl."""
    monkeypatch.setattr(aufnahme.time, "sleep", lambda s: None)
    tg = TelegramKaputterDownload()

    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=95))

    assert aid is None
    assert all(z["message_id"] != 95 for z in repo.transkripte(conn, 1)), (
        "kein Download, keine aufnahme-Zeile -- es gibt nichts, das der "
        "Nachhol-Arbeiter aufgreifen koennte"
    )
    vorfaelle = conn.execute(
        "SELECT * FROM vorfall WHERE art='download_fehlgeschlagen'"
    ).fetchall()
    assert len(vorfaelle) == 1

    meldungen = [t for _, t in tg.gesendet if "nicht angekommen" in t]
    assert len(meldungen) == 1, "genau eine Nachricht an die Gruppe, keine pro Wiederholungsversuch"


def test_setze_whisper_stumm_seit_falls_leer_ist_atomar(conn):
    """Grundlage von Wichtig 1: das erste UPDATE gewinnt, jedes weitere findet
    das Feld schon gesetzt vor und liefert False."""
    assert repo.setze_whisper_stumm_seit_falls_leer(conn, 1, "2026-09-04T10:00:00+00:00") is True
    assert repo.setze_whisper_stumm_seit_falls_leer(conn, 1, "2026-09-04T10:00:01+00:00") is False
    assert repo.hole_gruppe(conn, 1)["whisper_stumm_seit"] == "2026-09-04T10:00:00+00:00"

    assert repo.leere_whisper_stumm_seit_falls_gesetzt(conn, 1) is True
    assert repo.leere_whisper_stumm_seit_falls_gesetzt(conn, 1) is False
    assert repo.hole_gruppe(conn, 1)["whisper_stumm_seit"] is None


def test_melde_ausfall_ist_nebenlaeufigkeitsfest(conn, einst, tg):
    """Wichtig 1: mehrere Threads (wie im 8er-Pool von bot.py), die gleichzeitig
    auf denselben Whisper-Ausfall stossen, duerfen zusammen trotzdem nur genau
    eine Ausfallmeldung erzeugen."""
    anzahl_threads = 8
    start = threading.Barrier(anzahl_threads)

    def lauf():
        start.wait()
        aufnahme.melde_ausfall(conn, tg, einst, 1)

    threads = [threading.Thread(target=lauf) for _ in range(anzahl_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    for t in threads:
        assert not t.is_alive(), "Thread nicht innerhalb des Timeouts fertig geworden"

    meldungen = [t for _, t in tg.gesendet if "nicht hoeren" in t]
    assert len(meldungen) == 1
