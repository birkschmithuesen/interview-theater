"""Aufgabe 8: Aufnahme-Pipeline, Nachhol-Arbeiter, Whisper-Ausfall
(SPEC-kontext-architektur.md § 10).

Attrappen statt Netzzugriff: TelegramAttrappe ersetzt theatersoap.telegram.Telegram,
LLMAttrappe ersetzt theatersoap.llm.LLM (wie in test_verdichter.py), stt_attrappe/
stt_kaputt bauen einen httpx.Client mit MockTransport, der genau wie ein echter
Whisper-Endpunkt antwortet (wie in test_stt.py) -- so laeuft der echte
theatersoap.stt.transkribiere() in den Tests, nur ohne Netz.
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from theatersoap import aufnahme, db, einstellungen, repo

TRANSKRIPT = (
    "Wir haben letzte Woche ueber das Buehnenbild gesprochen. Ich erinnere mich, "
    "wie wir als Kinder auf dem Hof Theater gespielt haben, mit Bettlaken als "
    "Vorhang. Meine Grossmutter hat immer zugeschaut und geklatscht."
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
    """Ersetzt theatersoap.telegram.Telegram: kein Netzzugriff, zeichnet auf."""

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
    """Ersetzt theatersoap.llm.LLM: liefert immer dieselbe gueltige Antwort."""

    def __init__(self, antwort=None):
        self._antwort = antwort or {
            "zusammenfassung": "Eine Erinnerung an Theaterspiele im Kindesalter.",
            "kernthemen": [
                {"thema": "Kindheit", "beleg_zitat": "wie wir als Kinder auf dem Hof Theater gespielt haben"},
            ],
        }
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe += 1
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
    Versuche (theatersoap.stt.transkribiere wiederholt genau einmal) scheitern
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


# ---------------------------------------------------------------------------
# Die neun wichtigsten Tests aus dem Auftrag
# ---------------------------------------------------------------------------

def test_klasse_fuer_modus_an_ergibt_lang_unabhaengig_von_der_dauer(conn):
    """Aufgabe 5 (teil-b.md, § 10.1): die Dauer spielt keine Rolle mehr --
    nur der Modus. Selbst sieben Sekunden zaehlen bei aktivem Modus als
    Material."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    assert aufnahme.klasse_fuer(conn, 1) == "lang"


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


def test_lang_bekommt_empfangsbestaetigung_kurz_nicht(conn, einst, tg):
    """Klasse *lang* entsteht seit Aufgabe 5 ausschliesslich ueber den
    Interviewmodus, nicht mehr ueber die Dauer -- die 300 Sekunden hier sind
    nur noch ein beliebiger Wert, keine Grenzwertpruefung mehr."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    assert any("hoere durch" in t for _, t in tg.gesendet)
    tg.gesendet.clear()
    repo.setze_interviewmodus(conn, 1, None)
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=11))
    assert tg.gesendet == [], "bei ausgeschaltetem Modus keine Bestaetigung"


def test_kurz_landet_als_nachricht_im_verlauf(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("Mach mal lauter"), aid)
    zeile = conn.execute("SELECT * FROM nachricht WHERE typ='text' AND ist_bot=0 "
                         "ORDER BY message_id DESC").fetchone()
    assert zeile["text"] == "Mach mal lauter"
    assert repo.hole_aufnahme(conn, aid)["status"] == "fertig"
    assert repo.verdichtungen(conn, 1) == [], "kurz wird nicht verdichtet"


def test_lang_wird_verdichtet(conn, einst, tg, klm):
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(TRANSKRIPT), aid)
    assert len(repo.verdichtungen(conn, 1)) == 1


def test_fuenf_sprachnachrichten_im_modus_ergeben_fuenf_materialaufnahmen(conn, einst, tg):
    """Aufgabe 5, Auftragstest: ein Interview kann aus mehreren kurzen
    Sprachnachrichten bestehen -- jede einzelne zaehlt trotzdem als Material,
    solange der Modus an ist."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    for i in range(5):
        n = sprachnachricht(dauer=7, message_id=200 + i)
        aid = aufnahme.empfange(conn, tg, einst, n)
        assert repo.hole_aufnahme(conn, aid)["klasse"] == "lang"


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
    assert aufnahme.klasse_fuer(zweite_verbindung, 1) == "lang"


def test_aktiver_modus_loest_bei_sprachnachricht_keinen_gespraechszug_aus(conn, einst, tg, klm):
    """Aufgabe 5, Auftragstest: waehrend des Interviewmodus ist eine
    Sprachnachricht Material, kein Gespraechsbeitrag -- sie darf keinen Zug
    ausloesen, sondern muss stattdessen (klassenabhaengig) verdichtet
    werden."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aufgerufen = []

    def zug(conn, tg, klm, e, chat_id, hinweis=None):
        aufgerufen.append(chat_id)

    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=210))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(TRANSKRIPT), aid, zug=zug)

    assert aufgerufen == [], "Material darf keinen Gespraechszug ausloesen"
    assert len(repo.verdichtungen(conn, 1)) == 1, "es wurde trotzdem als Material verdichtet"


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
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
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


def test_verdichtung_scheitert_aufnahme_bleibt_transkribiert_fuer_nachhol_arbeiter(conn, einst, tg):
    """Schlaegt die Verdichtung fehl, bleibt das schon vorhandene Transkript
    erhalten (status='transkribiert') -- der Nachhol-Arbeiter darf es beim
    naechsten Anlauf direkt weiterverdichten, ohne ein zweites Mal Whisper zu
    fragen."""

    class KaputtesLLM:
        def schema(self, chat_id, system, nutzer, schema, art):
            raise RuntimeError("Sprachmodell nicht erreichbar")

    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=80))
    aufnahme.verarbeite(conn, tg, KaputtesLLM(), einst, stt_attrappe(TRANSKRIPT), aid)
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "transkribiert"
    assert zeile["transkript"] == TRANSKRIPT
    assert repo.verdichtungen(conn, 1) == []

    aufnahme.verarbeite(conn, tg, LLMAttrappe(), einst, stt_kaputt(), aid)
    assert repo.hole_aufnahme(conn, aid)["status"] == "fertig"
    assert len(repo.verdichtungen(conn, 1)) == 1


def test_verdichtung_ueber_max_versuchen_gilt_als_fehlgeschlagen(conn, einst, tg):
    """Kritisch 2: eine dauerhaft scheiternde Verdichtung ist ein bezahlter
    Sprachmodell-Aufruf und darf nicht unbegrenzt oft alle NACHHOL_INTERVALL_S
    Sekunden wiederholt werden. Ab MAX_VERSUCHE wird endgueltig aufgegeben,
    das Transkript bleibt aber erhalten und die Gruppe erfaehrt davon."""

    class KaputtesLLM:
        def schema(self, chat_id, system, nutzer, schema, art):
            raise RuntimeError("Sprachmodell nicht erreichbar")

    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=81))
    # Der erste Anlauf muss die Transkription noch erfolgreich hinter sich
    # bringen (sonst zaehlt der Versuch als Transkriptions-, nicht als
    # Verdichtungsfehlschlag); alle weiteren finden schon status='transkribiert'
    # vor und fragen Whisper gar nicht erst -- der STT-Klient ist dort egal.
    aufnahme.verarbeite(conn, tg, KaputtesLLM(), einst, stt_attrappe(TRANSKRIPT), aid)
    for _ in range(aufnahme.MAX_VERSUCHE - 1):
        aufnahme.verarbeite(conn, tg, KaputtesLLM(), einst, stt_kaputt(), aid)

    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "fehlgeschlagen"
    assert zeile["versuche"] == aufnahme.MAX_VERSUCHE
    assert zeile["transkript"] == TRANSKRIPT, "das Transkript bleibt trotz gescheiterter Verdichtung erhalten"
    assert repo.verdichtungen(conn, 1) == []
    assert any("auswerten" in t for _, t in tg.gesendet)


def test_lange_aufnahme_bekommt_bitte_nochmal_nur_einmal(conn, einst, tg, klm):
    """Wichtig 2: bei mehreren Nachhol-Anlaeufen derselben Aufnahme (Klasse
    *lang*) geht die 'schickt sie bitte nochmal'-Bitte nur beim ersten
    Fehlschlag raus, nicht bei jedem der bis zu MAX_VERSUCHE Versuche."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=82))
    for _ in range(3):
        aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)

    bitten = [t for _, t in tg.gesendet if "nochmal" in t]
    assert len(bitten) == 1, "die Bitte, es nochmal zu schicken, wiederholt sich nicht"


def test_bitte_nochmal_nennt_keinen_ersatznamen(conn, einst, tg, klm):
    """Kleinigkeit: 'Die Aufnahme von Interview 1 konnte ich nicht verstehen'
    wirkt in einer Chatnachricht unfreiwillig komisch. Ohne einen von der
    Gruppe vergebenen echten Namen wird stattdessen die Klasse genannt."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=83))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)

    nachrichten = [t for _, t in tg.gesendet if "nochmal" in t]
    assert len(nachrichten) == 1
    assert "Interview" not in nachrichten[0]
    assert "letzte lange Aufnahme" in nachrichten[0]

    # Mit einem echten Namen wird der auch genannt.
    aid2 = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=84))
    repo.setze_aufnahme_name(conn, aid2, "Maria")
    tg.gesendet.clear()
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid2)
    nachrichten2 = [t for _, t in tg.gesendet if "nochmal" in t]
    assert len(nachrichten2) == 1
    assert "Maria" in nachrichten2[0]


def test_zwischenmeldung_nur_bei_kurz(conn, einst, tg, klm, monkeypatch):
    """Kleinigkeit: die 12-Sekunden-Zwischenmeldung ('Ich hoer noch zu...')
    darf bei Klasse *lang* nicht feuern -- die hat mit der Empfangsbestaetigung
    aus empfange() schon eine Nachricht fuer dieselbe Sache bekommen. Fuer
    Klasse *kurz* soll sie bei einer langsamen Transkription dagegen wirklich
    feuern -- die Abschaltung ist strukturell (Klasse), nicht zufaellig."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aid_lang = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300, message_id=90))
    tg.gesendet.clear()
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("ok"), aid_lang)
    assert not any("hoer noch zu" in t for _, t in tg.gesendet), "lang bekommt keine Zwischenmeldung"

    monkeypatch.setattr(aufnahme, "MELDUNG_AB_S", 0.01)
    monkeypatch.setattr(aufnahme, "TIPPANZEIGE_AB_S", 100)  # soll hier nicht stoeren

    def handler_langsam(request):
        time.sleep(0.1)
        if "audio/transcriptions" in request.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={"status": "success", "data": json.dumps({"text": "ok"})})

    klient = httpx.Client(transport=httpx.MockTransport(handler_langsam))
    repo.setze_interviewmodus(conn, 1, None)
    aid_kurz = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=91))
    tg.gesendet.clear()
    aufnahme.verarbeite(conn, tg, klm, einst, klient, aid_kurz)
    assert any("hoer noch zu" in t for _, t in tg.gesendet), "kurz bekommt die Zwischenmeldung bei langsamer Transkription"


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
