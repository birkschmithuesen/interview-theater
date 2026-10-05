"""Die Begruessung der Phase 1 in Padua (Birk, Live-Test 05.10.2026).

Birks Beobachtungen, woertlich umgesetzt:
1. erklaeren, wie die ZWEI Handys genutzt werden (eins hoert in der Mitte zu,
   das zweite oeffnet denselben Gruppenlink und zeigt den Tab "CoThinker");
2. der Raumcheck kommt zuerst (Ruhe, dann sagt eine Person einen Satz) --
   dafuer als Erstes "Start listening";
3. keine Zeile "You can follow everything we keep here ..." mehr;
4. keine Abkuerzungs-Knoepfe darunter, sondern der Schlusssatz
   "Now press "Start listening" for mic calibration."

Live greift in Padua der feste Text (``bot.erstkontakt`` ueber den
versteckten ``/start`` beim ersten Seitenaufruf); der Prompt-Weg
(``kontext.ERSTKONTAKT_DISKUSSION``) traegt den Wiedereintritt in Phase 1
und den Erstkontakt ohne ``/start``. Beide verlangen dasselbe."""

import pytest

from interview_theater import (
    ablauf, begriffsboard, bot, db, einstellungen, kontext, repo, sprache, workshop,
)
from interview_theater.knoepfe import stationen

CHAT = 7000000000001
SCHLUSS = 'Now press "Start listening" for mic calibration.'

ERWARTET = (
    "Hi, I'm the theatre bot for this workshop.\n\n"
    "Phone A lies in the middle of the table and listens - that's this chat.\n"
    "Phone B opens the same group link and shows the \"CoThinker\" tab: "
    "your terms appear there live.\n\n"
    "First I check the room briefly: a few seconds of quiet, then one of you "
    "says a sentence.\n"
    "Then discuss which terms matter for your play. Give every term one "
    "sentence on why you chose it - that also helps me hear it right. I only "
    "listen until you tap \"Discussion done\".\n\n"
    + SCHLUSS
)


@pytest.fixture(autouse=True)
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE)
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="padua1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
        web_url="https://lab.test/theatersoap",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "padua1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet, self.mit_knoepfen = [], []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return 100 + len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        self.mit_knoepfen.append((text, list(knoepfe_)))
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


def test_padua_hoert_in_phase_1_mit():
    assert workshop.diskussion_aktiv()


def test_feste_begruessung_woertlich(conn, einst):
    tg = _TG()
    bot.erstkontakt(conn, tg, einst, CHAT)
    assert tg.gesendet == [ERWARTET]


def test_feste_begruessung_ohne_knoepfe_und_ohne_gruppenseite(conn, einst):
    tg = _TG()
    bot.erstkontakt(conn, tg, einst, CHAT)
    assert tg.mit_knoepfen == []
    text = tg.gesendet[0]
    assert "follow everything" not in text
    assert "lab.test" not in text
    assert "buttons below" not in text.lower()
    assert text.endswith(SCHLUSS)
    assert len([z for z in text.splitlines() if z.strip()]) <= 6
    assert "why you chose it" in text          # F: Begruendung je Begriff
    # mitgeschrieben, damit der naechste Zug sie im Fenster sieht
    assert repo.hat_bot_nachricht(conn, CHAT)


def test_prompt_weg_verlangt_dieselben_inhalte_ohne_link_und_knoepfe(conn, einst):
    for anweisung in (kontext._baue_erstkontakt(conn, CHAT, einst),
                      kontext.einstieg_begriffe(conn, CHAT, einst)):
        assert "lab.test" not in anweisung
        assert "group page" not in anweisung
        assert "show the way" not in anweisung      # der alte Knopf-Hinweis
        assert "CoThinker" in anweisung
        assert "same group link" in anweisung
        assert "quiet" in anweisung and "sentence" in anweisung
        assert SCHLUSS in anweisung
        # F (Birk 05.10.2026): jeden Begriff mit einem Satz begruenden.
        assert "one sentence on why they chose it" in anweisung
        assert "Start interview" not in anweisung


def test_nach_der_modellbegruessung_kein_zweiter_handy_satz(conn, einst, monkeypatch):
    """Die Begruessung erklaert die zwei Handys jetzt selbst -- der
    Einstiegssatz (``begriffsboard._TEXT_EINSTIEG``) kaeme sonst doppelt und
    stuende HINTER dem Schlusssatz."""
    monkeypatch.setattr(ablauf, "_erfrage_antwort", lambda *a, **k: "Welcome! " + SCHLUSS)
    repo.merke_nachricht(conn, CHAT, 1, "Gruppe", 0, "text", "Hello", repo._jetzt())
    tg = _TG()
    ablauf.antworte(conn, tg, object(), einst, CHAT, list(repo.unbeantwortete(conn, CHAT)))
    assert begriffsboard.T._TEXT_EINSTIEG not in tg.gesendet
    assert tg.gesendet[-1].endswith(SCHLUSS)


def test_wiedereintritt_mit_modell_ohne_zweiten_handy_satz(conn, einst, monkeypatch):
    auftraege = []
    monkeypatch.setattr(
        ablauf, "starte_auftrag",
        lambda conn_, tg_, klm_, e_, chat_id, anweisung, *a: auftraege.append(anweisung) or object(),
    )
    repo.setze_phase(conn, CHAT, 1)
    tg = _TG()
    stationen.eintritt_in_phase(conn, tg, object(), einst, CHAT, 1)
    assert len(auftraege) == 1
    assert begriffsboard.T._TEXT_EINSTIEG not in tg.gesendet


def test_wiedereintritt_ohne_modell_behaelt_den_handy_satz(conn, einst):
    repo.setze_phase(conn, CHAT, 1)
    tg = _TG()
    stationen.eintritt_in_phase(conn, tg, None, einst, CHAT, 1)
    assert begriffsboard.T._TEXT_EINSTIEG in tg.gesendet


def test_web_gruppe_bekommt_keinen_abkuerzungs_hinweis_vor_der_begruessung(tmp_path, einst):
    """Live gesehen: vor der Begruessung stand "Buttons are shortcuts ...",
    weil die Begruessung die erste Knopfnachricht der Gruppe war."""
    from interview_theater import web_kanal

    kanal = web_kanal.WebKanal(conn_web := _web_db(tmp_path), CHAT, str(tmp_path / "audio"))
    bot.erstkontakt(conn_web, kanal, einst, CHAT)
    texte = [z["text"] for z in conn_web.execute(
        "SELECT text FROM web_post WHERE chat_id = ? ORDER BY id", (CHAT,))]
    # Seit Nachtrag 8 steht die Handy-Karte (Bild + Satz) davor -- eine
    # Systemzeile ohne Knoepfe, also weiterhin kein Abkuerzungs-Hinweis.
    from interview_theater import handykarten
    assert texte == [handykarten.satz(1), ERWARTET]


def _web_db(tmp_path):
    c = db.verbinde(str(tmp_path / "w.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "padua1", "Testgruppe")
    return c


def test_raumcheck_vor_der_diskussion_nennt_die_begruendung():
    from interview_theater import web_chat

    assert "why you chose it" in web_chat.T._TEXT_KALIBRIERUNG_ERFOLG_DISKUSSION
    assert "why" not in web_chat.T._TEXT_KALIBRIERUNG_ERFOLG
    assert "sitzung.art === 'diskussion'" in web_chat._CHAT_JS
    assert "TEXT.kal_erfolg_diskussion" in web_chat._CHAT_JS


# -- Nachtrag 8 (Birk 05.10.2026): die Handy-Karte VOR der Begruessung ------


def test_erster_seitenaufruf_karte_vor_der_begruessung_einmal(tmp_path, einst):
    """Web-Kanal wie live: ``/start`` -> ``bot.erstkontakt``. Erst die
    Phase-1-Karte (Bild + Satz mit Phone A/B), dann die Begruessung; ein
    zweiter Aufruf (Reload) schickt keine zweite Karte."""
    from interview_theater import handykarten, web_kanal

    conn_web = _web_db(tmp_path)
    kanal = web_kanal.WebKanal(conn_web, CHAT, str(tmp_path / "audio"))
    bot.erstkontakt(conn_web, kanal, einst, CHAT)
    bot.erstkontakt(conn_web, kanal, einst, CHAT)
    zeilen = conn_web.execute(
        "SELECT text, bild FROM web_post WHERE chat_id = ? ORDER BY id", (CHAT,)).fetchall()
    assert [z["bild"] for z in zeilen] == ["phase-1-en.png", None]
    assert zeilen[0]["text"] == handykarten.satz(1)
    assert "Phone A" in zeilen[0]["text"] and "Phone B" in zeilen[0]["text"]
    assert zeilen[1]["text"] == ERWARTET


def test_karte_und_begruessung_nennen_die_handys_gleich():
    from scripts.handy_karten import PHASEN_EN

    _nr, _name, satz, phones = PHASEN_EN[0]
    assert [tab for tab, *_ in phones] == ["Chat", "CoThinker"]
    for name in ("Phone A", "Phone B"):
        assert name in satz and name in ERWARTET
    assert "Phone 1" not in ERWARTET and "Phone 2" not in ERWARTET
