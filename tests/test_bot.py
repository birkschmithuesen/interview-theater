import threading
from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import bot, db, phasen, repo

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

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_):
        # Dasselbe fuer die Einstiegsknoepfe unter der Begruessung
        # (knoepfe.biete_einstieg, 05.09.2026).
        return self.sende(chat_id, text)


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
    (_zug_und_erkenner statt _bearbeite_sprachnachricht).

    Die Nachricht traegt die ECHTE Uhrzeit, nicht das feste ``JETZT``:
    ``schleife`` liest die Zeit selbst (``datetime.now``) und wuerde eine auf
    12:00 datierte Nachricht ab 12:16 als Nachtstau unterdruecken -- der Test
    schlug sonst je nach Tageszeit fehl."""
    tg = FakeTelegramFuerSchleife(
        [bau_update(1, 21, "Text", datetime.now(timezone.utc))]
    )
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
        #: (chat_id, text, [(beschriftung, callback_data), ...]) je Angebot
        #: mit Inline-Tastatur -- Begruessungen tragen seit 05.09.2026 die
        #: Einstiegsknoepfe (knoepfe.biete_einstieg).
        self.mit_knoepfen = []
        self._letzte_message_id = 9000

    def sende(self, chat_id, text):
        self._letzte_message_id += 1
        self.gesendet.append((chat_id, text))
        return self._letzte_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_):
        message_id = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return message_id


def test_erstkontakt_kommt_genau_einmal_und_bietet_die_knoepfe_an(conn, einst):
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Gruppe 1")
    tg = TelegramAttrappe()

    bot.erstkontakt(conn, tg, einst, -100)
    bot.erstkontakt(conn, tg, einst, -100)  # zweiter Aufruf darf nichts mehr senden

    assert len(tg.gesendet) == 1
    text = tg.gesendet[0][1]
    # Phase 1 ist der Regelfall beim Erstkontakt: die Begruessung sagt, dass
    # jetzt die Begriffe aus dem Plenum kommen -- nicht, wie man eine
    # Aufnahme startet (05.09.2026, Birk: "nach der begruessung kommt erst
    # die eingabe der begriffe").
    assert "Begriffe" in text
    assert "Sprachnachricht" in text
    assert "Aufnahme starten" not in text
    # Seit 05.09.2026: kein Slash-Befehl mehr in der Begruessung, dafuer die
    # Einstiegsknoepfe darunter (Birk: "ersetze am besten alle slash befehl
    # vorschlaege mit knoepfen").
    assert "/" not in text
    beschriftungen = [b for b, _ in tg.mit_knoepfen[0][2]]
    assert "Aufnahme starten" not in beschriftungen, "in Phase 1 gibt es nichts aufzunehmen"
    assert "Stand zeigen" in beschriftungen
    assert "Hilfe" in beschriftungen
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

    assert tg.gesendet == [
        (-200, bot._TEXT_WIEDERKEHR.format(phase=phasen.bezeichnung(phasen.ERSTE)))
    ]


def test_wiederkehr_begruessung_nennt_die_phase(conn, einst):
    """Nach einer Nacht Pause ist die erste Frage im Raum, wo man
    stehengeblieben ist -- die Zeile beantwortet sie (A5)."""
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Alte Gruppe")
    repo.merke_nachricht(
        conn, -100, 1, "Ada", 0, "text", "gestern",
        (JETZT - timedelta(hours=5)).isoformat(),
    )
    repo.setze_phase(conn, -100, 5)
    tg = TelegramAttrappe()

    bot.sende_wiederkehr_begruessungen(conn, tg, einst, JETZT)

    assert "5 · Format & Rahmen" in tg.gesendet[0][1]


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
    monkeypatch.setattr(
        bot.journal, "laufe",
        lambda *a, **kw: reihenfolge.append("journal"),
    )

    bot._zug_und_erkenner("conn", "tg", "klm", "e", 1)

    assert reihenfolge == ["zug", "erkenner", "journal"], (
        "Erkenner und Journal-Extraktor muessen NACH dem Zug laufen, je genau einmal"
    )


def test_erstkontakt_nennt_die_gruppenseite_wenn_konfiguriert(conn, einst):
    """Birk 04.09.: den Link muss der Bot mitteilen, nicht das Workshop-Team
    abschreiben. Ohne IT_WEB_URL kein Link, mit: /g/<token> dieser Gruppe."""
    import dataclasses
    repo.sichere_gruppe(conn, -100, einst.bot_name, "Gruppe 1")
    tg = TelegramAttrappe()
    bot.erstkontakt(conn, tg, einst, -100)
    assert "/g/" not in tg.gesendet[0][1]

    repo.sichere_gruppe(conn, -200, einst.bot_name, "Gruppe 2")
    mit_web = dataclasses.replace(einst, web_url="https://lab.test/theatersoap")
    tg = TelegramAttrappe()
    bot.erstkontakt(conn, tg, mit_web, -200)
    token = repo.stelle_web_token_sicher(conn, -200)
    assert f"https://lab.test/theatersoap/g/{token}" in tg.gesendet[0][1]


def test_erstkontakt_nennt_den_link_auch_ohne_vorhandene_gruppenzeile(conn, einst):
    """Birk 05.09.: "stelle sicher, dass zu Beginn bei der Begruessung die
    Website als Link angeboten wird."

    Der Fall, den das absichert: ``repo.gruppenseite_url`` braucht
    ``gruppe.web_token``, und das entsteht erst in ``repo.sichere_gruppe``.
    Wird ``erstkontakt`` aufgerufen, bevor die Zeile existiert (Rueckfallweg
    aus ``ablauf.antworte``), fehlte der Link bisher stillschweigend --
    ``bot.stelle_link_sicher`` legt sie jetzt notfalls selbst an."""
    import dataclasses
    mit_web = dataclasses.replace(einst, web_url="https://lab.test/theatersoap")
    tg = TelegramAttrappe()

    bot.erstkontakt(conn, tg, mit_web, -300)  # -300 gibt es in 'gruppe' nicht

    token = repo.stelle_web_token_sicher(conn, -300)
    assert token is not None
    assert f"https://lab.test/theatersoap/g/{token}" in tg.gesendet[0][1]


# ---------------------------------------------------------------------------
# Inline-Knoepfe (05.09.2026, interview_theater/knoepfe.py): der zweite
# Update-Typ, den die Schleife kennt. Trockenlauf ohne Netz -- FakeTelegram
# liefert einen callback_query-Update, FakePool faengt ab, was geplant wurde.
# ---------------------------------------------------------------------------


def bau_knopfupdate(update_id: int, daten: str = "k:1"):
    """Ein callback_query-Update, wie Telegram es aus getUpdates liefert --
    bewusst OHNE 'message'-Schluessel auf oberster Ebene: genau daran haette
    lies_nachricht() es verworfen, und die Schleife haette den Druck still
    verschluckt."""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cbq-{update_id}",
            "data": daten,
            "from": {"id": 5, "first_name": "Ada"},
            "message": {
                "message_id": 300,
                "chat": {"id": -100, "title": "Testgruppe"},
                "date": int(JETZT.timestamp()),
            },
        },
    }


def test_schleife_gibt_knopfdruck_in_den_pool(conn, einst):
    """Der Trockenlauf: ein callback_query-Update kommt aus getUpdates,
    wird erkannt, normalisiert und als Knopfdruck in den Pool gegeben --
    ohne Netz, ohne Sprachmodell."""
    tg = FakeTelegramFuerSchleife([bau_knopfupdate(7, "k:42")])
    pool = FakePool()

    with pytest.raises(_StoppeSchleife):
        bot.schleife(conn, einst, tg, object(), object(), pool)

    assert len(pool.submits) == 1
    fn, args, _ = pool.submits[0]
    assert fn is bot._bearbeite_knopfdruck
    druck = args[-1]
    assert druck["data"] == "k:42"
    assert druck["chat_id"] == -100
    assert druck["callback_query_id"] == "cbq-7"
    # Die Position rueckt weiter, sonst stellte Telegram denselben Druck
    # beim naechsten Poll erneut zu (Auftragshinweis 4).
    assert repo.hole_update_id(conn, einst.bot_name) == 7


def test_knopfdruck_wird_nicht_als_nachricht_gespeichert(conn, einst):
    """Ein Knopfdruck ist keine Nachricht: er hat nichts in 'nachricht' zu
    suchen, sonst taeuchte er im Gespraechsfenster auf und der Erkenner
    laese ihn wie einen Gruppenbeitrag."""
    tg = FakeTelegramFuerSchleife([bau_knopfupdate(8)])

    with pytest.raises(_StoppeSchleife):
        bot.schleife(conn, einst, tg, object(), object(), FakePool())

    assert conn.execute("SELECT COUNT(*) FROM nachricht").fetchone()[0] == 0


def test_kaputter_knopfdruck_stoppt_die_schleife_nicht(conn, einst):
    """Fehlerhaltung: _bearbeite_knopfdruck faengt jeden Fehlschlag ab --
    ein Knopf darf den Bot einer Gruppe im Workshop nie anhalten."""
    class KaputtesTelegram:
        def beantworte_knopf(self, *a, **k):
            raise RuntimeError("Netz weg")

    # Der Aufruf geht durch, ohne zu werfen -- das ist die ganze Zusage.
    bot._bearbeite_knopfdruck(
        conn, KaputtesTelegram(), None, einst,
        {"callback_query_id": "x", "data": "k:1", "chat_id": 1, "message_id": 2},
    )


def test_neue_knopfarten_laufen_durch_die_update_schleife(conn, einst):
    """Trockenlauf ohne Netz fuer die drei Knopfarten, die am 05.09.2026
    dazugekommen sind (Format, Form je Szene, USA-Einwilligung): ein echter
    callback_query-Update geht durch die Schleife bis in
    _bearbeite_knopfdruck, und die Wirkung steht danach in der Datenbank.

    Geprueft wird hier bewusst der GANZE Weg und nicht nur knoepfe.behandle:
    zwischen Update und Wirkung liegen lies_knopfdruck, die Weiche in
    bot.schleife und der Thread-Pool -- die Knopfarten des Branches waren
    dort schon eingehaengt, die neuen muessen es genauso sein."""
    from interview_theater import knoepfe, repo as repo_modul

    chat_id = -100
    repo_modul.sichere_gruppe(conn, chat_id, einst.bot_name, "Testgruppe")

    class Attrappe:
        def __init__(self):
            self.gesendet = []
            self.knoepfe = []

        def sende(self, chat_id, text):
            self.gesendet.append((chat_id, text))
            return 1

        def sende_mit_knoepfen(self, chat_id, text, knoepfe_):
            self.knoepfe.append(list(knoepfe_))
            return 1

        def beantworte_knopf(self, *a, **k):
            pass

        def entferne_knoepfe(self, *a, **k):
            pass

    tg_att = Attrappe()
    knoepfe.biete_format(conn, tg_att, chat_id, ["Revue"])
    knoepfe.biete_szenenform(conn, tg_att, chat_id, 2)
    knoepfe.biete_szene_usa(conn, tg_att, chat_id)

    daten_format = tg_att.knoepfe[0][0][1]
    daten_form = tg_att.knoepfe[1][1][1]      # "Lied"
    daten_usa_nein = tg_att.knoepfe[2][1][1]  # "Nein, Schweiz"

    for nr, daten in enumerate((daten_format, daten_form, daten_usa_nein), start=20):
        tg = FakeTelegramFuerSchleife([bau_knopfupdate(nr, daten)])
        pool = FakePool()
        with pytest.raises(_StoppeSchleife):
            bot.schleife(conn, einst, tg, object(), object(), pool)
        assert len(pool.submits) == 1
        fn, args, _ = pool.submits[0]
        assert fn is bot._bearbeite_knopfdruck
        # Der Pool ist eine Attrappe: die Arbeit hier ausfuehren, wie sie im
        # Betrieb im Thread liefe.
        fn(args[0], tg_att, args[2], args[3], args[4])

    assert repo_modul.hole_arbeitsstand(conn, chat_id)["format"] == "Revue"
    szene_id = repo_modul.stelle_szene_sicher(conn, chat_id, 2)
    assert repo_modul.hole_szene(conn, szene_id)["form"] == "lied"
    # Der bool-Fall: "nein" ist False, nicht ein wahrer String.
    assert repo_modul.szene_usa_stand(conn, chat_id) == "nein"
