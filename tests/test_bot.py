import threading
from datetime import datetime, timedelta, timezone

import pytest

from theatersoap import bot, db, repo

JETZT = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    return c


def bau_update(update_id: int, message_id: int, text: str, gesendet_am: datetime) -> dict:
    """Baut ein rohes Telegram-Update mit fester Gruppe (-100, 'Gruppe 1')."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(gesendet_am.timestamp()),
            "chat": {"id": -100, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "text": text,
        },
    }


def bau_sprachupdate(update_id: int, message_id: int, gesendet_am: datetime) -> dict:
    """Baut ein rohes Telegram-Update mit einer Sprachnachricht."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(gesendet_am.timestamp()),
            "chat": {"id": -100, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "voice": {"file_id": "AwACabc", "duration": 12},
        },
    }


def test_alte_nachricht_beim_start_wird_gespeichert_aber_unterdrueckt(conn, einst):
    alt = JETZT - timedelta(hours=14)
    n = bot.verarbeite_update(conn, einst, bau_update(1, 10, "Idee", alt), JETZT, True)
    zeile = conn.execute("SELECT * FROM nachricht WHERE message_id = 10").fetchone()
    assert zeile["text"] == "Idee", "Nachtnachricht muss gespeichert werden"
    assert zeile["unterdrueckt"] == 1
    assert n is None, "Nachtnachricht darf keinen Zug ausloesen"


def test_ist_nachtstau_zieht_die_grenze_bei_15_minuten():
    assert bot.ist_nachtstau((JETZT - timedelta(minutes=16)).isoformat(), JETZT)
    assert not bot.ist_nachtstau((JETZT - timedelta(minutes=14)).isoformat(), JETZT)


def test_gruppe_wird_beim_ersten_update_angelegt(conn, einst):
    bot.verarbeite_update(conn, einst, bau_update(3, 12, "hallo", JETZT), JETZT, False)
    assert repo.hole_gruppe(conn, -100)["titel"] == "Gruppe 1"


def test_sprachnachricht_erreicht_pipeline_auch_bei_nachtstau(conn, einst):
    """Auftragshinweis 1: Sprache hat noch kein Transkript und darf deshalb keinen
    Zug ausloesen -- das gilt unabhaengig vom Nachtstau. Die Audiodatei muss aber
    in jedem Fall die Aufnahme-Pipeline (Aufgabe 8) erreichen, sonst verschwindet
    ein Interview, das ueber Nacht eintrifft, spurlos (SPEC § 9.1: teuerster
    Fehlerfall). Zum Gegenbeweis im selben Zug: eine ebenso alte Textnachricht
    bleibt beim Nachtstau unterdrueckt UND liefert None -- nur Sprache ist die
    Ausnahme von der Nachtstau-Rueckgabe."""
    alt = JETZT - timedelta(hours=14)

    n_sprache = bot.verarbeite_update(conn, einst, bau_sprachupdate(4, 13, alt), JETZT, True)
    zeile_sprache = conn.execute("SELECT * FROM nachricht WHERE message_id = 13").fetchone()
    assert zeile_sprache["unterdrueckt"] == 1
    assert n_sprache is not None, "Sprachnachricht muss trotz Nachtstau die Pipeline erreichen"
    assert n_sprache["typ"] == "sprache"

    n_text = bot.verarbeite_update(conn, einst, bau_update(5, 14, "Idee", alt), JETZT, True)
    zeile_text = conn.execute("SELECT * FROM nachricht WHERE message_id = 14").fetchone()
    assert zeile_text["unterdrueckt"] == 1
    assert n_text is None, "Textnachricht bleibt beim Nachtstau ohne Zug"


def test_duplikat_liefert_none(conn, einst):
    update = bau_update(5, 14, "einmal", JETZT)
    erster = bot.verarbeite_update(conn, einst, update, JETZT, False)
    zweiter = bot.verarbeite_update(conn, einst, update, JETZT, False)
    assert erster is not None
    assert zweiter is None


# ---------------------------------------------------------------------------
# Aufgabe 8, Nachbesserung "Wichtig 4": die Einhaengung in bot.py war bisher
# unbelegt -- schleife() mit neuer Signatur, _bearbeite_sprachnachricht und
# _nachhol_schleife hatten keinen einzigen Test.
# ---------------------------------------------------------------------------

class _StoppeSchleife(Exception):
    """Nur zum Testen: bricht die Endlosschleife in schleife() gezielt ab,
    ohne dass bot.schleife selbst einen Ausstieg kennen muss."""


class FakeTelegramFuerSchleife:
    """Liefert einmal die vorgegebenen Updates, danach _StoppeSchleife -- so
    laesst sich die eigentlich endlose Schleife auf einen Durchlauf begrenzen."""

    def __init__(self, updates):
        self._updates = updates
        self.aufrufe = 0
        self._letzte_message_id = 9000

    def hole_updates(self, offset, timeout=25):
        self.aufrufe += 1
        if self.aufrufe == 1:
            return self._updates
        raise _StoppeSchleife()

    def sende(self, chat_id, text):
        # bot.erstkontakt() ruft dies bei der ersten Nachricht einer Gruppe
        # auf (teil-b.md Aufgabe 7) -- fuer diese Tests ohne eigene Bedeutung,
        # nur damit erstkontakt() nicht an einer fehlenden Methode scheitert.
        self._letzte_message_id += 1
        return self._letzte_message_id


class FakePool:
    """Ersetzt den ThreadPoolExecutor: submit() fuehrt nichts aus, sondern
    zeichnet nur auf, WAS geplant wurde -- ausreichend, um die Weiche in
    schleife() zu pruefen, ohne Aufnahme-Pipeline oder Whisper zu beruehren."""

    def __init__(self):
        self.submits = []

    def submit(self, fn, *args, **kwargs):
        self.submits.append((fn, args, kwargs))


def test_schleife_gibt_sprachnachricht_in_den_pool(conn, einst):
    tg = FakeTelegramFuerSchleife([bau_sprachupdate(1, 20, JETZT)])
    pool = FakePool()

    with pytest.raises(_StoppeSchleife):
        bot.schleife(conn, einst, tg, object(), object(), pool)

    assert len(pool.submits) == 1
    fn, args, kwargs = pool.submits[0]
    assert fn is bot._bearbeite_sprachnachricht
    nachricht = args[-1]
    assert nachricht["typ"] == "sprache"
    assert nachricht["chat_id"] == -100
    assert nachricht["message_id"] == 20
    # die update_id ruecke trotzdem weiter, sonst wuerde Telegram dasselbe
    # Update beim naechsten Poll erneut zustellen (Auftragshinweis 4).
    assert repo.hole_update_id(conn, einst.bot_name) == 1


def test_schleife_gibt_textnachricht_in_den_pool(conn, einst):
    """Live-Test 1: die Gruppe ist ein reines Interface zum Bot, also loest
    jede Textnachricht einen Gespraechszug aus (ablauf.ist_ausloeser, SPEC
    § 1.2) -- nicht nur Reply, @Erwaehnung oder Befehl. Sie laeuft im
    selben Pool wie Sprachnachrichten, nur ueber eine andere Funktion
    (_zug_und_erkenner statt _bearbeite_sprachnachricht)."""
    tg = FakeTelegramFuerSchleife([bau_update(1, 21, "Text", JETZT)])
    pool = FakePool()

    with pytest.raises(_StoppeSchleife):
        bot.schleife(conn, einst, tg, object(), object(), pool)

    assert len(pool.submits) == 1
    fn, args, kwargs = pool.submits[0]
    assert fn is bot._zug_und_erkenner
    assert args[-1] == -100  # chat_id


def test_bearbeite_sprachnachricht_ruft_empfange_und_dann_verarbeite_auf(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(bot.aufnahme, "empfange", lambda *a: (aufrufe.append("empfange"), 42)[1])
    monkeypatch.setattr(bot.aufnahme, "verarbeite", lambda *a, **kw: aufrufe.append(("verarbeite", a[-1])))

    nachricht = {"chat_id": -100, "message_id": 1, "typ": "sprache"}
    bot._bearbeite_sprachnachricht(None, None, None, None, None, nachricht)

    assert aufrufe == ["empfange", ("verarbeite", 42)]


def test_bearbeite_sprachnachricht_ueberspringt_verarbeite_wenn_download_scheiterte(monkeypatch):
    """Kritisch 1: empfange() liefert None, wenn der Download endgueltig
    scheiterte -- dann darf verarbeite() gar nicht erst mit einer
    nichtexistenten aufnahme_id aufgerufen werden."""
    aufrufe = []
    monkeypatch.setattr(bot.aufnahme, "empfange", lambda *a: None)
    monkeypatch.setattr(bot.aufnahme, "verarbeite", lambda *a, **kw: aufrufe.append("verarbeite"))

    nachricht = {"chat_id": -100, "message_id": 1, "typ": "sprache"}
    bot._bearbeite_sprachnachricht(None, None, None, None, None, nachricht)

    assert aufrufe == []


def test_nachhol_schleife_ruft_nachholen_auf_und_endet_mit_dem_event(conn, einst, monkeypatch):
    """_nachhol_schleife laesst sich mit einem stop-Event nach einem
    Durchlauf trivial testen (kein echtes Warten auf NACHHOL_INTERVALL_S):
    nachholen() selbst setzt das Event, stop.wait() kehrt dadurch sofort
    zurueck und die Schleife endet."""
    aufrufe = []
    stop = threading.Event()

    def nachholen_und_stoppen(*args, **kwargs):
        aufrufe.append(1)
        stop.set()

    monkeypatch.setattr(bot.aufnahme, "nachholen", nachholen_und_stoppen)

    thread = threading.Thread(
        target=bot._nachhol_schleife,
        args=(stop, conn, einst, object(), object(), object()),
    )
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive(), "die Schleife muss nach dem gesetzten Event enden"
    assert aufrufe == [1]


# ---------------------------------------------------------------------------
# teil-b.md Aufgabe 7: Begruessungsnachricht (erstkontakt, begruessung_faellig,
# sende_wiederkehr_begruessungen)
# ---------------------------------------------------------------------------

class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []  # Liste von (chat_id, text)
        self._letzte_message_id = 9000

    def sende(self, chat_id, text):
        self._letzte_message_id += 1
        self.gesendet.append((chat_id, text))
        return self._letzte_message_id


def test_erstkontakt_kommt_genau_einmal_und_nennt_interviewmodus_und_hilfe(conn, einst):
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Gruppe 1")
    tg = TelegramAttrappe()

    bot.erstkontakt(conn, tg, einst, -100)
    bot.erstkontakt(conn, tg, einst, -100)  # zweiter Aufruf darf nichts mehr senden

    assert len(tg.gesendet) == 1
    text = tg.gesendet[0][1]
    assert "Interview" in text
    assert "/hilfe" in text
    # als Bot-Nachricht mitgeschrieben, sonst würde sie erneut ausgeloest
    zeile = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = -100 AND ist_bot = 1"
    ).fetchone()
    assert zeile is not None
    assert zeile["text"] == text


def test_erstkontakt_sendefehlschlag_wird_nur_geloggt(conn, einst):
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Gruppe 1")

    class KaputtesTG:
        def sende(self, chat_id, text):
            raise RuntimeError("Telegram nicht erreichbar (simuliert)")

    bot.erstkontakt(conn, KaputtesTG(), einst, -100)  # darf nicht krachen
    assert not repo.hat_bot_nachricht(conn, -100)


def test_begruessung_faellig_nach_ueber_zwei_stunden():
    letzte = (JETZT - timedelta(hours=3)).isoformat()
    assert bot.begruessung_faellig(letzte, JETZT) is True


def test_begruessung_faellig_nach_dreissig_sekunden_nicht():
    letzte = (JETZT - timedelta(seconds=30)).isoformat()
    assert bot.begruessung_faellig(letzte, JETZT) is False


def test_sende_wiederkehr_begruessungen_nur_fuer_alte_gruppen(conn, einst):
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Alte Gruppe")
    repo.sichere_gruppe(conn, -200, einst.bot_name, "Frische Gruppe")
    repo.merke_nachricht(
        conn, -100, 1, "Ada", 0, "text", "gestern",
        (JETZT - timedelta(hours=5)).isoformat(),
    )
    repo.merke_nachricht(
        conn, -200, 1, "Ada", 0, "text", "gerade eben",
        (JETZT - timedelta(seconds=10)).isoformat(),
    )
    tg = TelegramAttrappe()

    bot.sende_wiederkehr_begruessungen(conn, tg, einst, JETZT)

    chat_ids = [chat_id for chat_id, _ in tg.gesendet]
    assert chat_ids == [-100]


def test_sende_wiederkehr_begruessungen_ohne_nachrichten_sendet_nichts(conn, einst):
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Leere Gruppe")
    tg = TelegramAttrappe()

    bot.sende_wiederkehr_begruessungen(conn, tg, einst, JETZT)

    assert tg.gesendet == []


def test_sende_wiederkehr_begruessungen_ein_fehlschlag_reisst_andere_nicht_mit(conn, einst):
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Kaputte Gruppe")
    repo.sichere_gruppe(conn, -200, einst.bot_name, "Gesunde Gruppe")
    for chat_id in (-100, -200):
        repo.merke_nachricht(
            conn, chat_id, 1, "Ada", 0, "text", "vor langer zeit",
            (JETZT - timedelta(hours=10)).isoformat(),
        )

    class HalbKaputtesTG(TelegramAttrappe):
        def sende(self, chat_id, text):
            if chat_id == -100:
                raise RuntimeError("kaputt (simuliert)")
            return super().sende(chat_id, text)

    tg = HalbKaputtesTG()
    bot.sende_wiederkehr_begruessungen(conn, tg, einst, JETZT)  # darf nicht krachen

    assert tg.gesendet == [(-200, bot._TEXT_WIEDERKEHR)]


# ---------------------------------------------------------------------------
# teil-b.md Aufgabe 8: Warmlauf (warmlaufen) und Erkenner-Einhaengung
# (_zug_und_erkenner)
# ---------------------------------------------------------------------------

def test_warmlaufen_ruft_erkenner_schema_mit_erkenner_modell_auf(conn, einst):
    aufrufe = []

    class LLMAttrappe:
        def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
            aufrufe.append((modell, temperature, art))
            return {"aenderungen": []}

    bot.warmlaufen(LLMAttrappe(), conn, einst)

    assert aufrufe == [(einst.erkenner_modell, bot.erkenner.TEMPERATURE, "erkenner")]


def test_warmlaufen_fehlschlag_wird_nur_geloggt(conn, einst):
    class KaputtesLLM:
        def schema(self, *a, **kw):
            raise RuntimeError("Modell nicht erreichbar (simuliert)")

    bot.warmlaufen(KaputtesLLM(), conn, einst)  # darf nicht krachen


def test_warmlaufen_in_eigenem_thread_blockiert_den_aufrufer_nicht(conn, einst):
    gestartet = threading.Event()
    weiter = threading.Event()

    class LangsamesLLM:
        def schema(self, *a, **kw):
            gestartet.set()
            assert weiter.wait(5), "der Test haette den Aufruf freigeben muessen"
            return {"aenderungen": []}

    thread = threading.Thread(
        target=bot.warmlaufen, args=(LangsamesLLM(), conn, einst), daemon=True,
    )
    thread.start()
    assert gestartet.wait(5), "der Warmlauf-Aufruf haette starten muessen"
    # Der Aufrufer (dieser Test) ist hier angekommen, waehrend der Warmlauf
    # noch im simulierten Modellaufruf haengt -- er wurde also nicht blockiert.
    weiter.set()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_zug_und_erkenner_ruft_beides_genau_einmal_auf_nach_dem_zug(monkeypatch):
    reihenfolge = []
    monkeypatch.setattr(
        bot.ablauf, "bearbeite",
        lambda *a, **kw: reihenfolge.append("zug"),
    )
    monkeypatch.setattr(
        bot.erkenner, "laufe",
        lambda *a, **kw: reihenfolge.append("erkenner"),
    )

    bot._zug_und_erkenner("conn", "tg", "klm", "e", 1)

    assert reihenfolge == ["zug", "erkenner"], (
        "der Erkenner muss NACH dem Zug laufen, genau einmal"
    )
