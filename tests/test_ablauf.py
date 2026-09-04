"""Aufgabe 10: Gespraechszug -- Durchstich (SPEC-kontext-architektur.md § 1.2,
§ 1.3). Attrappen statt Netzzugriff, wie in test_aufnahme.py.
"""

import threading
import time
from datetime import datetime, timezone

import pytest

from interview_theater import ablauf, bot, repo


class TelegramAttrappe:
    """Ersetzt interview_theater.telegram.Telegram: kein Netzzugriff, zeichnet auf."""

    def __init__(self):
        self.gesendet = []   # Liste von (chat_id, text)
        self.getippt = []    # Liste von chat_id
        self._letzte_message_id = 9000

    def sende(self, chat_id, text):
        self._letzte_message_id += 1
        self.gesendet.append((chat_id, text))
        return self._letzte_message_id

    def tippt(self, chat_id):
        self.getippt.append(chat_id)


@pytest.fixture
def tg():
    return TelegramAttrappe()


class KLMAttrappe:
    """Ersetzt interview_theater.llm.LLM: liefert immer dieselbe gueltige Antwort."""

    def __init__(self, antwort="Klar, machen wir."):
        self._antwort = antwort
        self.gesehen = []  # Liste der 'nutzer'-Prompts, mit denen sie aufgerufen wurde

    def schema(self, chat_id, system, nutzer, schema, art):
        self.gesehen.append(nutzer)
        return {"antwort": self._antwort}


class KLMKaputt:
    """Ersetzt interview_theater.llm.LLM: schlaegt immer fehl."""

    def schema(self, chat_id, system, nutzer, schema, art):
        raise RuntimeError("Sprachmodell nicht erreichbar (simuliert)")


@pytest.fixture
def klm():
    return KLMAttrappe()


def _nachricht(text=None, typ="text", antwortet_auf_bot=False):
    return {"typ": typ, "text": text, "antwortet_auf_bot": antwortet_auf_bot}


# ---------------------------------------------------------------------------
# Live-Test 1: die Gruppe ist ein reines Interface zum Bot -- er antwortet
# auf jede Nachricht (SPEC § 1.2). Reply, @Erwaehnung und /Befehl loesen
# weiterhin aus, aber nicht mehr AUSSCHLIESSLICH sie -- auch beilaeufig
# wirkender Text tut es jetzt.
# ---------------------------------------------------------------------------

def test_reply_auf_bot_loest_aus():
    n = _nachricht(text="ja klar", antwortet_auf_bot=True)
    assert ablauf.ist_ausloeser(n, "gruppe1") is True


def test_erwaehnung_loest_aus():
    n = _nachricht(text="@gruppe1 was meinst du?")
    assert ablauf.ist_ausloeser(n, "gruppe1") is True


def test_befehl_loest_aus():
    n = _nachricht(text="/stand")
    assert ablauf.ist_ausloeser(n, "gruppe1") is True


def test_sprachnachricht_loest_immer_aus():
    n = _nachricht(text=None, typ="sprache")
    assert ablauf.ist_ausloeser(n, "gruppe1") is True


def test_beilaeufiger_text_loest_jetzt_auch_aus():
    """Frueher der Gegenbeweis ('beilaeufiges Geplauder loest nicht aus'):
    seit die Gruppe als reines Interface zum Bot gilt, gibt es kein
    beilaeufiges Geplauder mehr, das er ignorieren duerfte."""
    n = _nachricht(text="ich hol mir Kaffee")
    assert ablauf.ist_ausloeser(n, "gruppe1") is True


def test_ausloeser_ist_unabhaengig_vom_bot_namen():
    """bot_name bleibt Teil der Signatur, wird aber nicht mehr ausgewertet --
    jede Nachricht loest aus, auch ohne bekannten Botnamen."""
    n = _nachricht(text="irgendein Text")
    assert ablauf.ist_ausloeser(n, None) is True


def test_nachzuegler_werden_in_einen_zug_gesammelt(conn, einst, tg):
    """Waehrend ein Aufruf laeuft, sammeln sich Nachrichten (SPEC 1.3):
    erster Zug in einem Thread, zwei Nachzuegler waehrenddessen -- am Ende
    darf es nur EINEN zweiten Aufruf gegeben haben, nicht zwei."""
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "@gruppe1 frage eins", repo._jetzt())

    gestartet = threading.Event()
    weiter = threading.Event()

    class BlockierendesKLM:
        def __init__(self):
            self.gesehen = []

        def schema(self, chat_id, system, nutzer, schema, art):
            self.gesehen.append(nutzer)
            if len(self.gesehen) == 1:
                gestartet.set()
                assert weiter.wait(5), "Test haette den ersten Aufruf freigeben muessen"
            return {"antwort": "ok"}

    klm = BlockierendesKLM()

    erster_zug = threading.Thread(target=ablauf.bearbeite, args=(conn, tg, klm, einst, 1))
    erster_zug.start()
    assert gestartet.wait(5), "der erste Zug haette starten muessen"

    # Zwei Nachzuegler treffen ein, waehrend der erste Aufruf noch im Sprachmodell haengt.
    repo.merke_nachricht(conn, 1, 2, "Bob", 0, "text", "und ausserdem...", repo._jetzt())
    repo.merke_nachricht(conn, 1, 3, "Ada", 0, "text", "nochmal die frage", repo._jetzt())

    # Ein eigener Sammelversuch, waehrend die Sperre haelt, darf nichts ausloesen.
    ablauf.bearbeite(conn, tg, klm, einst, 1)
    assert len(klm.gesehen) == 1, "der zweite Aufruf-Versuch durfte die Sperre nicht bekommen"

    weiter.set()
    erster_zug.join(timeout=5)
    assert not erster_zug.is_alive(), "der erste Zug muss fertig geworden sein"

    assert len(klm.gesehen) == 2, "erster Zug, dann ein Sammelzug - nicht drei"


def test_wasserzeichen_wird_nach_der_antwort_gesetzt(conn, einst, tg, klm):
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "/stand", repo._jetzt())
    ablauf.bearbeite(conn, tg, klm, einst, 1)
    assert repo.hole_gruppe(conn, 1)["letzte_beantwortete_message_id"] == 5


def test_bot_antwort_wird_mitgeschrieben(conn, einst, tg, klm):
    repo.merke_nachricht(conn, 1, 6, "Ada", 0, "text", "@gruppe1 hallo", repo._jetzt())
    ablauf.bearbeite(conn, tg, klm, einst, 1)

    assert len(tg.gesendet) == 1
    gesendete_chat_id, gesendeter_text = tg.gesendet[0]
    assert gesendete_chat_id == 1
    assert gesendeter_text == "Klar, machen wir."

    zeile = conn.execute(
        "SELECT * FROM nachricht WHERE ist_bot = 1 ORDER BY message_id DESC"
    ).fetchone()
    assert zeile is not None, "die Bot-Antwort muss als Nachricht mitgeschrieben werden"
    assert zeile["text"] == "Klar, machen wir."
    assert zeile["message_id"] > 6


def test_llm_fehler_meldet_der_gruppe_und_haelt_nicht_an(conn, einst, tg):
    repo.merke_nachricht(conn, 1, 7, "Ada", 0, "text", "@gruppe1 was meinst du?", repo._jetzt())
    ablauf.bearbeite(conn, tg, KLMKaputt(), einst, 1)

    meldungen = [t for _, t in tg.gesendet if "hakt" in t]
    assert len(meldungen) == 1, "die Gruppe bekommt eine kurze, ehrliche Zeile"

    vorfaelle = conn.execute(
        "SELECT * FROM vorfall WHERE art = 'gespraechszug_fehlgeschlagen'"
    ).fetchall()
    assert len(vorfaelle) == 1

    # Auch ein gescheiterter Zug rueckt vor -- sonst wird endlos wiederholt.
    assert repo.hole_gruppe(conn, 1)["letzte_beantwortete_message_id"] == 7

    # Der Bot bleibt danach voll funktionsfaehig: ohne neue Nachricht loest
    # ein erneuter Aufruf nichts mehr aus (kein zweiter Fehlerhinweis).
    ablauf.bearbeite(conn, tg, KLMKaputt(), einst, 1)
    assert len([t for _, t in tg.gesendet if "hakt" in t]) == 1


def test_teilfehler_nach_erfolgreichem_versand_erzeugt_keine_doppelte_meldung(
    conn, einst, tg, klm, monkeypatch,
):
    """Nachbesserung 'Wichtig': schlaegt repo.merke_nachricht NACH einem
    bereits erfolgreichen tg.sende fehl, darf die Gruppe nicht zusaetzlich
    'Bei mir hakt gerade etwas' unter der schon angekommenen Antwort lesen --
    der bestehende Fehlerfall-Test oben deckt das nicht ab, weil dort schon
    der Modellaufruf scheitert, bevor ueberhaupt etwas gesendet wurde."""
    repo.merke_nachricht(conn, 1, 9, "Ada", 0, "text", "@gruppe1 hallo", repo._jetzt())

    def kaputtes_merke_nachricht(*args, **kwargs):
        raise RuntimeError("Datenbank kurz weg (simuliert)")

    monkeypatch.setattr(ablauf.repo, "merke_nachricht", kaputtes_merke_nachricht)

    ablauf.bearbeite(conn, tg, klm, einst, 1)

    assert len(tg.gesendet) == 1, "es wurde nur die eigentliche Antwort gesendet"
    assert tg.gesendet[0][1] == "Klar, machen wir."
    assert not any("hakt" in t for _, t in tg.gesendet), (
        "keine zusaetzliche Fehlerzeile unter einer bereits erfolgreichen Antwort"
    )

    vorfaelle = conn.execute(
        "SELECT * FROM vorfall WHERE art = 'gespraechszug_fehlgeschlagen'"
    ).fetchall()
    assert len(vorfaelle) == 1, "der Fehler wird trotzdem als Vorfall vermerkt"

    # Das Wasserzeichen rueckt trotzdem vor (finally) -- sonst waere der Zug
    # ab jetzt endlos wiederholbar.
    assert repo.hole_gruppe(conn, 1)["letzte_beantwortete_message_id"] == 9


# ---------------------------------------------------------------------------
# teil-b.md Aufgabe 5: der beilaeufige Materialhinweis haengt sich an die
# ohnehin faellige Antwort an -- keine eigene Nachricht, kein Zustand.
# ---------------------------------------------------------------------------

def test_hinweis_wird_an_die_ohnehin_faellige_antwort_angehaengt(conn, einst, tg, klm):
    repo.merke_nachricht(conn, 1, 40, "Ada", 0, "sprache", "eine lange Erzaehlung", repo._jetzt())

    ablauf.bearbeite(conn, tg, klm, einst, 1, hinweis="Das klingt nach Material.")

    assert len(tg.gesendet) == 1, "Bestaetigung und Antwort sind EINE Nachricht, keine zwei"
    text = tg.gesendet[0][1]
    assert text.startswith("Klar, machen wir.")
    assert "Das klingt nach Material." in text


def test_ohne_hinweis_bleibt_die_antwort_unveraendert(conn, einst, tg, klm):
    repo.merke_nachricht(conn, 1, 41, "Ada", 0, "text", "hallo", repo._jetzt())

    ablauf.bearbeite(conn, tg, klm, einst, 1)

    assert tg.gesendet == [(1, "Klar, machen wir.")]


def test_hinweis_haengt_nur_am_ersten_antwortversuch(conn, einst, tg, klm):
    """Ein Sammelzug mit Nachzueglern (siehe test_nachzuegler_werden_in_einen_
    zug_gesammelt) darf den Hinweis nicht ein zweites Mal anhaengen, falls
    bearbeite() innerhalb desselben Aufrufs mehrfach antwortet."""
    repo.merke_nachricht(conn, 1, 42, "Ada", 0, "sprache", "lang", repo._jetzt())

    ablauf.bearbeite(conn, tg, klm, einst, 1, hinweis="Hinweis-Zeile")
    anzahl_mit_hinweis = sum(1 for _, t in tg.gesendet if "Hinweis-Zeile" in t)
    assert anzahl_mit_hinweis == 1


# ---------------------------------------------------------------------------
# teil-b.md Aufgabe 6: Befehle werden VOR dem Kontextaufbau abgefangen -- ein
# Befehl loest keinen Sprachmodell-Aufruf aus.
# ---------------------------------------------------------------------------

def test_befehl_loest_keinen_llm_aufruf_aus(conn, einst, tg, klm):
    repo.merke_nachricht(conn, 1, 50, "Ada", 0, "text", "/stand", repo._jetzt())

    ablauf.bearbeite(conn, tg, klm, einst, 1)

    assert klm.gesehen == [], "ein Befehl darf das Sprachmodell nie aufrufen"
    assert len(tg.gesendet) == 1
    assert repo.hole_gruppe(conn, 1)["letzte_beantwortete_message_id"] == 50


def test_befehl_mit_botname_wird_ueber_bearbeite_erkannt(conn, einst, tg, klm):
    repo.merke_nachricht(
        conn, 1, 51, "Ada", 0, "text", f"/fertig@{einst.bot_name}", repo._jetzt(),
    )

    ablauf.bearbeite(conn, tg, klm, einst, 1)

    assert klm.gesehen == []
    assert tg.gesendet == [(1, "Aufnahme beendet.")]


def test_szene_befehl_bekommt_das_sprachmodell_durchgereicht(conn, einst, tg, klm, monkeypatch):
    """/szene ist der einzige Befehl, der ein Modell braucht -- er bekommt es
    ueber ``behandle(..., klm=klm)``. Der Gespraechszug selbst ruft trotzdem
    nichts: szene.starte gibt sofort an einen eigenen Thread ab."""
    from interview_theater import szene

    gesehen = []
    monkeypatch.setattr(
        szene, "starte",
        lambda conn, tg, k, e, chat_id, auftrag: gesehen.append((k, auftrag)),
    )
    repo.merke_nachricht(
        conn, 1, 52, "Ada", 0, "text", "/szene Szene 2: am Bahnhof", repo._jetzt(),
    )

    ablauf.bearbeite(conn, tg, klm, einst, 1)

    assert gesehen == [(klm, "Szene 2: am Bahnhof")]
    assert klm.gesehen == [], "der Gespraechszug selbst ruft kein Modell"


# ---------------------------------------------------------------------------
# Zusaetzliche Tests fuer die Tippanzeige (Auftragshinweis 4) und die
# Einhaengung in bot.py (Auftragshinweis 2).
# ---------------------------------------------------------------------------

def test_tippanzeige_tickt_und_meldet_sich_nach_dem_hinweis(tg, monkeypatch):
    """Alle TIPP_INTERVALL Sekunden tippt(), nach HINWEIS_NACH Sekunden
    zusaetzlich eine kurze Zeile -- mit sehr kleinen Werten, damit der Test
    schnell bleibt. Der Hintergrund-Thread muss beim Verlassen sauber enden."""
    monkeypatch.setattr(ablauf, "TIPP_INTERVALL", 0.02)
    monkeypatch.setattr(ablauf, "HINWEIS_NACH", 0.05)

    laufende_threads_vorher = set(threading.enumerate())
    with ablauf._tippanzeige(tg, chat_id=1):
        time.sleep(0.2)
    neue_threads = set(threading.enumerate()) - laufende_threads_vorher

    assert len(tg.getippt) >= 2, "die Tippanzeige muss mehrfach erneuert werden"
    assert any("Moment" in t for _, t in tg.gesendet), "nach dem Hinweis-Schwellwert eine Zeile"
    for t in neue_threads:
        assert not t.is_alive(), "der Tippanzeige-Thread muss beim Verlassen sauber enden"


def test_tippanzeige_fehlschlag_stoert_den_zug_nicht(einst, conn, klm, monkeypatch):
    """Ein Fehlschlag der Tippanzeige (Telegram down) darf den Gespraechszug
    nie stoeren -- die Antwort muss trotzdem ankommen."""

    class KaputteTippanzeige(TelegramAttrappe):
        def tippt(self, chat_id):
            raise RuntimeError("sendChatAction kaputt (simuliert)")

    monkeypatch.setattr(ablauf, "TIPP_INTERVALL", 0.01)
    tg_kaputt = KaputteTippanzeige()
    repo.merke_nachricht(conn, 1, 8, "Ada", 0, "text", "@gruppe1 was meinst du?", repo._jetzt())

    ablauf.bearbeite(conn, tg_kaputt, klm, einst, 1)

    assert any(t == "Klar, machen wir." for _, t in tg_kaputt.gesendet)


# ---------------------------------------------------------------------------
# Einhaengung in bot.py: Live-Weg und Nachhol-Arbeiter reichen den echten
# Gespraechszug durch (Auftragshinweis 2); die Text-Weiche in schleife()
# ruft ihn ueber ablauf.ist_ausloeser auf, das heute bei jeder Textnachricht
# True liefert (SPEC § 1.2, Live-Test 1).
# ---------------------------------------------------------------------------

def test_live_weg_reicht_echten_zug_durch(monkeypatch):
    """teil-b.md Aufgabe 8: der 'zug', den die Aufnahme-Pipeline bekommt, ist
    seit der Erkenner-Einhaengung bot._zug_und_erkenner, nicht mehr direkt
    ablauf.bearbeite -- der Wrapper ruft ablauf.bearbeite unveraendert auf,
    haengt aber noch erkenner.laufe danach an (siehe eigener Test unten)."""
    aufrufe = []
    monkeypatch.setattr(bot.aufnahme, "empfange", lambda *a: (aufrufe.append("empfange"), 42)[1])
    monkeypatch.setattr(
        bot.aufnahme, "verarbeite",
        lambda *a, **kw: aufrufe.append(("verarbeite", kw.get("zug"))),
    )

    nachricht = {"chat_id": -100, "message_id": 1, "typ": "sprache"}
    bot._bearbeite_sprachnachricht(None, None, None, None, None, nachricht)

    assert aufrufe == ["empfange", ("verarbeite", bot._zug_und_erkenner)]


def test_nachhol_arbeiter_reicht_echten_zug_durch(einst, monkeypatch):
    aufrufe = []
    stop = threading.Event()

    def nachholen_und_stoppen(*args, **kwargs):
        aufrufe.append(kwargs.get("zug"))
        stop.set()

    monkeypatch.setattr(bot.aufnahme, "nachholen", nachholen_und_stoppen)

    thread = threading.Thread(
        target=bot._nachhol_schleife,
        args=(stop, None, einst, object(), object(), object()),
    )
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "die Schleife muss nach dem gesetzten Event enden"

    assert aufrufe == [bot._zug_und_erkenner]


class _StoppeSchleife(Exception):
    """Nur zum Testen: bricht die Endlosschleife in bot.schleife gezielt ab."""


class _FakeTGSchleife:
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


class _FakePool:
    def __init__(self):
        self.submits = []

    def submit(self, fn, *args, **kwargs):
        self.submits.append((fn, args, kwargs))


def _text_update(update_id, message_id, text, chat_id=-100):
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(datetime.now(timezone.utc).timestamp()),
            "chat": {"id": chat_id, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "text": text,
        },
    }


def test_schleife_gibt_ausloesende_textnachricht_in_den_pool(conn, einst):
    tg_schleife = _FakeTGSchleife([_text_update(1, 30, f"@{einst.bot_name} hallo")])
    pool = _FakePool()

    with pytest.raises(_StoppeSchleife):
        bot.schleife(conn, einst, tg_schleife, object(), object(), pool)

    assert len(pool.submits) == 1
    fn, args, kwargs = pool.submits[0]
    assert fn is bot._zug_und_erkenner
    assert args[-1] == -100


def test_schleife_gibt_auch_beilaeufig_wirkenden_text_in_den_pool(conn, einst):
    """Live-Test 1: die Gruppe ist ein reines Interface zum Bot -- auch ein
    Satz wie 'ich hol mir Kaffee', frueher der Musterfall fuer 'loest nicht
    aus', landet heute im Pool wie jede andere Textnachricht (SPEC § 1.2)."""
    tg_schleife = _FakeTGSchleife([_text_update(1, 31, "ich hol mir Kaffee")])
    pool = _FakePool()

    with pytest.raises(_StoppeSchleife):
        bot.schleife(conn, einst, tg_schleife, object(), object(), pool)

    assert len(pool.submits) == 1
    fn, _args, _kwargs = pool.submits[0]
    assert fn is bot._zug_und_erkenner
