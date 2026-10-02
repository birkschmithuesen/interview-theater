"""Angriff: gemockte Kosten ueber dem Tagesdeckel -- und der Bot ruft weiter an.

Die Kennzahl ist nicht der Statuscode, sondern die Zahl der Netzaufrufe: die
LLM-Attrappe zaehlt mit, und sie muss auf 0 bleiben. Ein Deckel, der die
Anfrage erst nach dem Absenden abbricht, hat nichts gespart.

Dazu die drei Eigenschaften, an denen so ein Deckel sonst scheitert:
  * Er gilt fuer Telegram UND Web (beide Kanaele laufen durch denselben
    Bot-Code -- ein Test je Kanal zeigt das).
  * Er setzt um Mitternacht Europe/Rome zurueck, nicht UTC: eine Zeile von
    gestern 23:59 Rom darf heute nicht mitzaehlen.
  * Er laesst das Empfangen in Ruhe. Nachrichten und Audio werden weiter
    gespeichert -- nicht aufzunehmen ist unumkehrbar (AGENTS.md).

Zeit kommt ueberall als Parameter herein. Kein sleep, kein echter Kalender.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from interview_theater import (
    aufnahme, db, einstellungen, kosten, llm, repo, stt,
)

CHAT = 1
ROM = ZoneInfo("Europe/Rome")


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def tippt(self, chat_id):
        pass

    def __getattr__(self, name):
        # Jede weitere Kanalmethode (Knoepfe, Tippanzeige, ...) ist hier
        # ein stilles Nichts -- gemessen wird nur, was gesendet wird.
        return lambda *a, **k: None


def _e(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="t", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="http://kein.netz/chat/completions",
        llm_key="k", llm_modell="moonshotai/Kimi-K2.6",
        stt_basis="http://kein.netz", stt_produkt="p",
    )


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Die Ankommenden")
    yield verbindung
    verbindung.close()


def _buche(conn, chf, zeitpunkt_iso=None):
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, kosten_chf, erstellt_am) VALUES (?, ?, ?, ?)",
        (CHAT, "gespraech", chf, zeitpunkt_iso or repo._jetzt()),
    )
    conn.commit()


class Zaehler:
    """Ein httpx.Client, der jeden Aufruf zaehlt und nie ins Netz geht."""

    def __init__(self):
        self.aufrufe = 0

    def post(self, *a, **k):
        self.aufrufe += 1
        raise AssertionError("Es haette gar kein Netzaufruf stattfinden duerfen")

    def get(self, *a, **k):
        self.aufrufe += 1
        raise AssertionError("Es haette gar kein Netzaufruf stattfinden duerfen")


# -- Die Grenze selbst ----------------------------------------------------


def test_unter_der_grenze_ist_alles_frei(conn, tmp_path):
    _buche(conn, 4.99)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path)) is False


def test_genau_auf_der_grenze_ist_erreicht(conn, tmp_path):
    _buche(conn, 5.0)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path)) is True


def test_viele_kleine_summieren_sich(conn, tmp_path):
    for _ in range(50):
        _buche(conn, 0.1)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path)) is True


def test_eine_andere_gruppe_ist_nicht_betroffen(conn, tmp_path):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Die Zweiten")
    _buche(conn, 9.0)
    assert kosten.deckel_erreicht(conn, 2, _e(tmp_path)) is False


def test_ohne_chat_id_greift_der_deckel_nie(conn, tmp_path):
    """Warmlaufen und Pruefskripte laufen ohne Gruppe -- sie gegen den
    Deckel einer Gruppe zu rechnen waere falsch."""
    _buche(conn, 99.0)
    assert kosten.deckel_erreicht(conn, None, _e(tmp_path)) is False


def test_der_deckel_kommt_aus_der_umgebung(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("IT_KOSTEN_DECKEL_CHF", "1.0")
    _buche(conn, 1.5)
    assert kosten.deckel(None) == pytest.approx(1.0)
    assert kosten.deckel_erreicht(conn, CHAT) is True


def _pflicht(monkeypatch):
    for name in ("IT_BOT_TOKEN", "IT_BOT_NAME", "IT_DB", "IT_LLM_URL", "IT_LLM_KEY",
                 "IT_STT_PRODUKT", "IT_LLM_MODELL"):
        monkeypatch.setenv(name, "x")
    monkeypatch.delenv("IT_KANAL", raising=False)


def test_einstellungen_lesen_deckel_und_zeitzone(monkeypatch):
    _pflicht(monkeypatch)
    monkeypatch.setenv("IT_KOSTEN_DECKEL_CHF", "2.5")
    monkeypatch.setenv("IT_ZEITZONE", "UTC")
    e = einstellungen.laden()
    assert e.kosten_deckel_chf == pytest.approx(2.5)
    assert e.zeitzone == "UTC"


def test_ein_unlesbarer_deckel_faellt_auf_die_vorgabe_nicht_auf_unendlich(monkeypatch):
    _pflicht(monkeypatch)
    monkeypatch.setenv("IT_KOSTEN_DECKEL_CHF", "fuenf")
    assert einstellungen.laden().kosten_deckel_chf == pytest.approx(5.0)


# -- Mitternacht Europe/Rome ----------------------------------------------


def test_tagesbeginn_rechnet_nach_utc_um():
    jetzt = datetime(2026, 9, 30, 16, 38, tzinfo=ROM)
    assert kosten.tagesbeginn_utc("Europe/Rome", jetzt) == "2026-09-29T22:00:00+00:00"


def test_gestern_dreiundzwanzig_neunundfuenfzig_zaehlt_heute_nicht(conn, tmp_path):
    """Sommerzeit: Mitternacht Rom ist 22:00 UTC. Eine Zeile von gestern
    23:59 Rom steht als 21:59 UTC in der Datenbank und liegt damit VOR dem
    Tagesbeginn -- mit einem UTC-Tag waere sie mitgezaehlt worden."""
    gestern = datetime(2026, 9, 29, 23, 59, tzinfo=ROM)
    _buche(conn, 9.0, gestern.astimezone(timezone.utc).isoformat(timespec="seconds"))
    jetzt = datetime(2026, 9, 30, 9, 0, tzinfo=ROM)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path), jetzt=jetzt) is False


def test_heute_null_uhr_eins_zaehlt(conn, tmp_path):
    frueh = datetime(2026, 9, 30, 0, 1, tzinfo=ROM)
    _buche(conn, 9.0, frueh.astimezone(timezone.utc).isoformat(timespec="seconds"))
    jetzt = datetime(2026, 9, 30, 9, 0, tzinfo=ROM)
    assert kosten.deckel_erreicht(conn, CHAT, _e(tmp_path), jetzt=jetzt) is True


def test_die_zeitzone_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_ZEITZONE", "UTC")
    jetzt = datetime(2026, 9, 30, 16, 38, tzinfo=ROM)
    assert kosten.tagesbeginn_utc(kosten.zeitzone(None), jetzt) == "2026-09-30T00:00:00+00:00"


# -- Der Angriff: kein Netzaufruf -----------------------------------------


def test_ueber_dem_deckel_faellt_der_llm_aufruf_ohne_netz_aus(conn, tmp_path):
    _buche(conn, 5.0)
    zaehler = Zaehler()
    klm = llm.LLM(_e(tmp_path), zaehler, conn)
    with pytest.raises(kosten.KostendeckelErreicht):
        klm.schema(CHAT, "system", "nutzer", {"type": "object"}, "gespraech")
    assert zaehler.aufrufe == 0


def test_ein_ausgefallener_aufruf_bucht_keine_zeile(conn, tmp_path):
    """Sonst schoebe jeder abgewiesene Versuch die Summe weiter hoch, und
    aus einer Pause bis Mitternacht wuerde eine bis uebermorgen."""
    _buche(conn, 5.0)
    vorher = conn.execute("SELECT COUNT(*) AS n FROM aufruf").fetchone()["n"]
    klm = llm.LLM(_e(tmp_path), Zaehler(), conn)
    for _ in range(5):
        with pytest.raises(kosten.KostendeckelErreicht):
            klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech")
    assert conn.execute("SELECT COUNT(*) AS n FROM aufruf").fetchone()["n"] == vorher


class _Antwort:
    status_code = 200

    def __init__(self, daten):
        self._daten = daten

    def raise_for_status(self):
        pass

    def json(self):
        return self._daten


class _EchterKlient:
    """Liefert eine gueltige Antwort mit ``usage`` -- ohne Netz."""

    def __init__(self, prompt_token, antwort_token):
        self.aufrufe = 0
        self._daten = {
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_token, "completion_tokens": antwort_token},
        }

    def post(self, *a, **k):
        self.aufrufe += 1
        return _Antwort(self._daten)


def test_ein_echter_aufruf_bucht_modell_und_kosten_und_fuellt_die_summe(conn, tmp_path):
    """Der Deckel summiert nur -- er ist so gut wie die Buchung in
    ``llm._anfrage``. Ohne diese Probe koennte die Summe still bei 0 stehen
    bleiben, und der Deckel griffe nie."""
    klm = llm.LLM(_e(tmp_path), _EchterKlient(1_000_000, 1_000_000), conn)
    klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech")
    zeile = conn.execute(
        "SELECT modell, kosten_chf FROM aufruf WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (CHAT,),
    ).fetchone()
    assert zeile["modell"] == "moonshotai/Kimi-K2.6"
    # Kimi: 0.60 Eingabe + 3.00 Ausgabe je Mio Token
    assert zeile["kosten_chf"] == pytest.approx(3.60)
    assert kosten.summe_heute(conn, CHAT, _e(tmp_path)) == pytest.approx(3.60)
    # Ein zweiter solcher Aufruf hebt ueber den Deckel -- der dritte fliegt.
    klient = _EchterKlient(1_000_000, 1_000_000)
    klm = llm.LLM(_e(tmp_path), klient, conn)
    klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech")
    with pytest.raises(kosten.KostendeckelErreicht):
        klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech")
    assert klient.aufrufe == 1


def test_ueber_dem_deckel_faellt_auch_der_claude_weg_aus(conn, tmp_path):
    from interview_theater import szene_claude

    _buche(conn, 5.0)
    zaehler = Zaehler()
    with pytest.raises(kosten.KostendeckelErreicht):
        szene_claude.prosa(conn, _e(tmp_path), zaehler, CHAT, "s", "n", "szene", 10.0)
    assert zaehler.aufrufe == 0


def test_ueber_dem_deckel_wird_nicht_transkribiert_aber_gespeichert(conn, tmp_path, monkeypatch):
    """Empfangen und Antworten sind zwei Entscheidungen: die Datei bleibt,
    der Status bleibt 'empfangen' -- der Nachhol-Arbeiter greift sie nach
    Mitternacht auf."""
    _buche(conn, 5.0)
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS" + b"\x00" * 100)
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 11, "kurz", "sprache",
                                        audio_pfad=str(datei), dauer=120)

    def darf_nicht(*a, **k):
        raise AssertionError("Whisper haette gar nicht gerufen werden duerfen")

    monkeypatch.setattr(stt, "transkribiere", darf_nicht)
    tg = TelegramAttrappe()
    aufnahme.verarbeite(conn, tg, None, _e(tmp_path), Zaehler(), aufnahme_id)
    row = repo.hole_aufnahme(conn, aufnahme_id)
    assert row["status"] == "empfangen"
    assert datei.is_file()
    # Im Live-Pfad sagt der Bot, dass er pausiert -- und keine Whisper-
    # Ausfallmeldung, die schlicht nicht stimmte.
    assert tg.gesendet == [kosten.T._TEXT_PAUSE]


def test_nachgeholt_meldet_nichts(conn, tmp_path, monkeypatch):
    """Der Nachhol-Arbeiter laeuft alle 60 s -- er darf die Gruppe nicht
    anschreiben ('Nachgeholtes loest nie eine Antwort aus')."""
    _buche(conn, 5.0)
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 11, "kurz", "sprache",
                                        audio_pfad=str(tmp_path / "a.ogg"), dauer=120)
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: "darf nicht laufen")
    tg = TelegramAttrappe()
    aufnahme.verarbeite(conn, tg, None, _e(tmp_path), Zaehler(), aufnahme_id, nachgeholt=True)
    assert tg.gesendet == []
    assert repo.hole_aufnahme(conn, aufnahme_id)["status"] == "empfangen"


def test_der_versuchszaehler_bleibt_stehen(conn, tmp_path, monkeypatch):
    """Die Falle dieser Aufgabe: liefe der Deckel ueber
    _melde_transkriptionsfehler, verbraeuchte der Nachhol-Arbeiter (alle
    60 s) MAX_VERSUCHE in fuenf Minuten -- und jedes Interview des Abends
    waere am naechsten Morgen endgueltig 'fehlgeschlagen'."""
    _buche(conn, 5.0)
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS" + b"\x00" * 100)
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 11, "kurz", "sprache",
                                        audio_pfad=str(datei))
    monkeypatch.setattr(stt, "transkribiere", lambda *a, **k: "darf nicht laufen")
    for _ in range(aufnahme.MAX_VERSUCHE + 2):
        aufnahme.verarbeite(conn, TelegramAttrappe(), None, _e(tmp_path),
                            Zaehler(), aufnahme_id, nachgeholt=True)
    row = repo.hole_aufnahme(conn, aufnahme_id)
    assert row["status"] == "empfangen"
    assert (row["versuche"] or 0) == 0


def _transkribiertes_interview(conn):
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 12, "lang", "sprache",
                                        status="transkribiert")
    repo.setze_transkript(conn, aufnahme_id, " ".join(["Wort"] * 200))
    return aufnahme_id


def test_die_verdichtung_verbraucht_keine_versuche(conn, tmp_path):
    """Dieselbe Falle eine Etage hoeher: ein transkribiertes Interview, dessen
    Verdichtung am Deckel scheitert, laeuft ueber ``zaehle_versuch_hoch`` --
    und der Nachhol-Arbeiter setzte es nach fuenf Minuten auf
    'fehlgeschlagen'."""
    _buche(conn, 5.0)
    aufnahme_id = _transkribiertes_interview(conn)
    zaehler = Zaehler()
    klm = llm.LLM(_e(tmp_path), zaehler, conn)
    tg = TelegramAttrappe()
    for _ in range(aufnahme.MAX_VERSUCHE + 2):
        aufnahme.verarbeite(conn, tg, klm, _e(tmp_path), zaehler, aufnahme_id,
                            nachgeholt=True)
    row = repo.hole_aufnahme(conn, aufnahme_id)
    assert row["status"] == "transkribiert"
    assert (row["versuche"] or 0) == 0
    assert zaehler.aufrufe == 0
    assert tg.gesendet == []


def test_die_verdichtung_im_live_pfad_meldet_die_pause(conn, tmp_path):
    _buche(conn, 5.0)
    aufnahme_id = _transkribiertes_interview(conn)
    tg = TelegramAttrappe()
    aufnahme.verarbeite(conn, tg, llm.LLM(_e(tmp_path), Zaehler(), conn),
                        _e(tmp_path), Zaehler(), aufnahme_id)
    assert tg.gesendet == [kosten.T._TEXT_PAUSE]
    assert (repo.hole_aufnahme(conn, aufnahme_id)["versuche"] or 0) == 0


# -- Die Meldung ----------------------------------------------------------


def test_die_pausenmeldung_kommt_einmal(conn, tmp_path):
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    e = _e(tmp_path)
    assert kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT) is True
    assert kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT) is True
    assert len(tg.gesendet) == 1


def test_nach_fuenfzehn_minuten_kommt_sie_wieder(conn, tmp_path):
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    e = _e(tmp_path)
    jetzt = datetime(2026, 9, 30, 14, 0, tzinfo=ROM)
    kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT, jetzt=jetzt)
    kurz_danach = datetime(2026, 9, 30, 14, 10, tzinfo=ROM)
    kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT, jetzt=kurz_danach)
    assert len(tg.gesendet) == 1
    spaeter = datetime(2026, 9, 30, 14, 16, tzinfo=ROM)
    kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT, jetzt=spaeter)
    assert len(tg.gesendet) == 2


def test_der_merkposten_ueberlebt_einen_neustart(conn, tmp_path):
    """Im Prozess gemerkt haette ein Neustart sofort wieder gemeldet -- und
    der Nachhol-Arbeiter laeuft im Minutentakt."""
    _buche(conn, 5.0)
    e = _e(tmp_path)
    tg = TelegramAttrappe()
    kosten.melde_pause_wenn_deckel(conn, tg, e, CHAT)
    conn.close()
    zweite = db.verbinde(str(tmp_path / "t.db"))
    try:
        zweiter_tg = TelegramAttrappe()
        kosten.melde_pause_wenn_deckel(zweite, zweiter_tg, e, CHAT)
        assert zweiter_tg.gesendet == []
    finally:
        zweite.close()


def test_unter_dem_deckel_meldet_sie_nichts(conn, tmp_path):
    _buche(conn, 1.0)
    tg = TelegramAttrappe()
    assert kosten.melde_pause_wenn_deckel(conn, tg, _e(tmp_path), CHAT) is False
    assert tg.gesendet == []


def test_der_text_nennt_keinen_betrag(conn, tmp_path):
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    kosten.melde_pause_wenn_deckel(conn, tg, _e(tmp_path), CHAT)
    text = tg.gesendet[0]
    for verbotenes in ("CHF", "5.0", "5,0", "Fr.", "€", "Euro"):
        assert verbotenes not in text, verbotenes


def test_der_vorfall_kommt_einmal_je_tag(conn, tmp_path):
    _buche(conn, 5.0)
    e = _e(tmp_path)
    for minuten in (0, 20, 40, 120):
        spaeter = datetime(2026, 9, 30, 14 + minuten // 60, minuten % 60, tzinfo=ROM)
        kosten.melde_pause_wenn_deckel(conn, TelegramAttrappe(), e, CHAT, jetzt=spaeter)
    anzahl = conn.execute(
        "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ? AND art = ?",
        (CHAT, "kostendeckel_erreicht"),
    ).fetchone()["n"]
    assert anzahl == 1


def test_der_englische_text_existiert_und_nennt_die_lage():
    """A1-Mechanik: die deutsche Konstante IST die deutsche Tabelle, jede
    weitere Sprache steht in sprachen/<code>/texte.toml."""
    from interview_theater import sprache

    sprache.vergiss()
    englisch = sprache.tabelle("en").get("kosten", {}).get("_TEXT_PAUSE")
    assert englisch, "Kein englischer Pausentext in sprachen/en/texte.toml"
    gesenkt = englisch.lower()
    assert "budget" in gesenkt
    assert "midnight" in gesenkt
    assert "saved" in gesenkt or "kept" in gesenkt
    for verbotenes in ("CHF", "5.0", "Fr.", "€", "Euro"):
        assert verbotenes not in englisch, verbotenes


# -- Beide Kanaele --------------------------------------------------------


def _frage(conn):
    repo.merke_nachricht(conn, CHAT, 5, "Guelten", 0, "text", "Wie geht es weiter?",
                         repo._jetzt())


def test_der_deckel_gilt_im_telegram_kanal(conn, tmp_path):
    from interview_theater import ablauf

    _buche(conn, 5.0)
    _frage(conn)
    tg = TelegramAttrappe()
    zaehler = Zaehler()
    ablauf.bearbeite(conn, tg, llm.LLM(_e(tmp_path), zaehler, conn), _e(tmp_path), CHAT)
    assert zaehler.aufrufe == 0
    assert tg.gesendet == [kosten.T._TEXT_PAUSE], tg.gesendet


def test_der_deckel_gilt_im_web_kanal(conn, tmp_path):
    """Derselbe Bot-Code, nur ein anderes tg-Objekt (Karte A2). Dass beide
    Kanaele denselben Weg nehmen, ist der Grund, warum der Deckel im
    Bot-Prozess sitzt und nicht im Webserver."""
    from interview_theater import ablauf, web_kanal

    _buche(conn, 5.0)
    _frage(conn)
    kanal = web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"))
    zaehler = Zaehler()
    ablauf.bearbeite(conn, kanal, llm.LLM(_e(tmp_path), zaehler, conn), _e(tmp_path), CHAT)
    assert zaehler.aufrufe == 0
    hinausgegangen = [
        z["text"] or "" for z in conn.execute(
            "SELECT text FROM web_post WHERE chat_id = ? AND richtung = ?",
            (CHAT, repo.RICHTUNG_AUS),
        )
    ]
    assert kosten.T._TEXT_PAUSE in hinausgegangen, hinausgegangen


def test_im_bestehenden_gespraech_kommt_pause_statt_hakt(conn, tmp_path):
    """Hat die Gruppe schon eine Bot-Antwort, ginge sonst 'Bei mir hakt
    gerade etwas' hinaus -- eine Fehlermeldung fuer etwas, das kein Fehler
    ist."""
    from interview_theater import ablauf

    repo.merke_nachricht(conn, CHAT, 4, "Bot", 1, "text", "Hallo", repo._jetzt())
    _buche(conn, 5.0)
    _frage(conn)
    tg = TelegramAttrappe()
    ablauf.bearbeite(conn, tg, llm.LLM(_e(tmp_path), Zaehler(), conn), _e(tmp_path), CHAT)
    assert tg.gesendet == [kosten.T._TEXT_PAUSE], tg.gesendet


# -- Was weiterlaeuft -----------------------------------------------------


def test_slash_befehle_laufen_weiter(conn, tmp_path):
    """Kein Befehl ruft synchron ein Modell (AGENTS.md) -- also darf keiner
    am Deckel scheitern."""
    from interview_theater import befehle

    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    assert befehle.behandle(conn, tg, _e(tmp_path), CHAT, "/stand", "Guelten") is True
    assert tg.gesendet
    assert kosten.T._TEXT_PAUSE not in tg.gesendet


def test_der_web_schreibpfad_laeuft_weiter(conn, tmp_path):
    """web_schreiben ruft ausschliesslich repo-Funktionen, kein Modell."""
    from interview_theater import web_schreiben

    _buche(conn, 5.0)
    web_schreiben.wende_an(conn, CHAT, "rahmen", "Ein Hinterhof im Regen", None)
    assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Ein Hinterhof im Regen"


# -- Hintergrundlaeufe: Pause statt Fehlermeldung (Fix-Runde 1) -----------
#
# Drei Stellen meldeten bei Tagesdeckel irrefuehrend: die Stueckpruefung und
# die Dramaturgie-Pruefung mit derselben "versucht es gleich noch einmal"-
# Zeile wie bei einem gewoehnlichen Fehler -- am Deckel scheitert aber JEDER
# weitere Versuch genauso. Die Schaerfung meldete gar nichts, obwohl die
# Gruppe gerade auf "Schaerfung laeuft, einen Moment" wartet.


def _stueck_mit_volltext(conn):
    """Eine Szene mit Volltext -- der Mindeststand, den
    ``stueckpruefung.pruefe`` braucht, um bis zum Modellaufruf zu kommen."""
    eins = repo.lege_szene_an(conn, CHAT, 1, "Am Kiosk", "sie treffen sich", None)
    repo.setze_szenenfeld(conn, eins, "form", "Dialog")
    repo.aktualisiere_szene(conn, eins, "Am Kiosk", "sie treffen sich", "A: Da bist du.")


def test_stueckpruefung_meldet_pause_statt_nochmal_versuchen(conn, tmp_path):
    """Vorher: bei Tagesdeckel kam dieselbe Zeile wie bei jedem anderen
    Fehler ("versucht es gleich noch einmal"), obwohl ein erneuter Versuch
    am Deckel garantiert genauso scheitert."""
    from interview_theater import stueckpruefung

    _stueck_mit_volltext(conn)
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    zaehler = Zaehler()
    klm = llm.LLM(_e(tmp_path), zaehler, conn)

    stueckpruefung._lauf(conn, tg, klm, _e(tmp_path), CHAT)

    # Die erste Zeile ist die Tippanzeige der Arbeitszeilen (nicht Teil
    # dieses Befunds) -- entscheidend ist, DASS die Pausenmeldung kommt und
    # NICHT die "versucht es gleich noch einmal"-Zeile.
    assert kosten.T._TEXT_PAUSE in tg.gesendet, tg.gesendet
    assert stueckpruefung.T.MELDUNG_FEHLGESCHLAGEN not in tg.gesendet, tg.gesendet
    assert zaehler.aufrufe == 0


def _dramaturgie_stueck(conn):
    """Eine Szene mit zwei erkennbaren Sprechern -- der Mindeststand, den
    ``mechanik.lies`` braucht, damit ``fanout.pruefe`` ueberhaupt ein
    Modell fragt."""
    repo.setze_figur(conn, CHAT, "Mira", "Mira ist erfunden.")
    repo.setze_figur(conn, CHAT, "Jonas", "Jonas ist erfunden.")
    szene_id = repo.stelle_szene_sicher(conn, CHAT, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    repo.setze_szenenfeld(conn, szene_id, "titel", "Szene 1")
    conn.execute(
        "UPDATE szene SET volltext = ? WHERE id = ?",
        (
            "MIRA: Der Koffer steht seit gestern hier.\n"
            "JONAS: Und?\n"
            "MIRA: Und niemand holt ihn.\n"
            "JONAS: Dann nehme ich ihn mit.\n",
            szene_id,
        ),
    )
    ids = [repo.hole_figur(conn, CHAT, n)["id"] for n in ("Mira", "Jonas")]
    repo.setze_szene_figuren(conn, CHAT, szene_id, ids)
    conn.commit()


def test_dramaturgie_meldet_pause_statt_nochmal_versuchen(conn, tmp_path, monkeypatch):
    """Dieselbe Falle wie bei der Stueckpruefung, nur mit bis zu 18
    Modellaufrufen je Lauf: ohne den Schutz in ``fanout._versuch`` haette
    jeder einzelne denselben Vorfall geschrieben, und am Ende waere
    trotzdem keine Pausenmeldung dabei herausgekommen."""
    from interview_theater.dramaturgie import fanout

    monkeypatch.setenv(fanout.ENV_MODELL, "mistralai/Mistral-Small-4-119B-2603")
    _dramaturgie_stueck(conn)
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    zaehler = Zaehler()
    klm = llm.LLM(_e(tmp_path), zaehler, conn)

    fanout._lauf(conn, tg, klm, _e(tmp_path), CHAT)

    assert tg.gesendet == [kosten.T._TEXT_PAUSE], tg.gesendet
    assert zaehler.aufrufe == 0
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall")]
    assert "dramaturgie_aufruf_fehlgeschlagen" not in arten, arten


def _interview_mit_thema(conn):
    kopf_id = repo.lege_interview_an(conn, CHAT)
    repo.setze_aufnahme_name(conn, kopf_id, "A")
    zitat_text = "Ich habe zwanzig Jahre genaeht und keiner hat gefragt."
    repo.setze_transkript(conn, kopf_id, zitat_text)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, CHAT, kopf_id, "Eine Zusammenfassung.", [
        {"thema": "Arbeit ohne Anerkennung", "beleg_zitat": zitat_text,
         "zitat_geprueft": 1},
    ])


def test_schaerfung_meldet_die_pause_statt_zu_schweigen(conn, tmp_path):
    """Vorher: die Gruppe bekam 'Schaerfung laeuft, einen Moment' und bei
    einem Fehlschlag danach GAR NICHTS mehr -- auch nicht am Tagesdeckel.
    Jetzt bekommt sie wenigstens die Pausenmeldung."""
    from interview_theater import schaerfung

    _interview_mit_thema(conn)
    _buche(conn, 5.0)
    tg = TelegramAttrappe()
    zaehler = Zaehler()
    klm = llm.LLM(_e(tmp_path), zaehler, conn)

    schaerfung._lauf(conn, tg, klm, _e(tmp_path), CHAT)

    # Die erste Zeile ist die Tippanzeige der Arbeitszeilen (nicht Teil
    # dieses Befunds) -- entscheidend ist, DASS die Pausenmeldung kommt und
    # nicht, wie vorher, gar keine Meldung.
    assert kosten.T._TEXT_PAUSE in tg.gesendet, tg.gesendet
    assert zaehler.aufrufe == 0
