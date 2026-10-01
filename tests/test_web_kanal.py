"""WebKanal gegen die Tabelle -- ohne Netz, ohne Browser, ohne Bot.

Gemessen wird, dass die zwoelf Methoden genau das in web_post schreiben, was
die Chatansicht spaeter liest, und dass hole_updates Telegram-foermige Updates
liefert, die telegram.lies_nachricht/lies_knopfdruck deuten koennen -- die
Bedingung dafuer, dass bot.schleife unveraendert bleibt.
"""

import threading
import time

import pytest

from interview_theater import db, repo, telegram, web_kanal

CHAT = 7_000_000_000_001


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(verbindung, CHAT, "web")
    return verbindung


@pytest.fixture
def kanal(conn, tmp_path):
    return web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"), schritt_s=0.01)


def test_sende_legt_eine_ausgehende_zeile_an(conn, kanal):
    message_id = kanal.sende(CHAT, "Hallo, ich bin der Theaterbot.")
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["richtung"] == repo.RICHTUNG_AUS
    assert zeile["typ"] == repo.WEB_TYP_TEXT
    assert zeile["text"] == "Hallo, ich bin der Theaterbot."
    assert repo.web_knoepfe(zeile) == []


def test_sende_teilt_nicht_bei_4000_zeichen(conn, kanal):
    """Telegram teilt bei NACHRICHT_GRENZE -- der Browser braucht das nicht.

    Eine Nachricht bleibt eine Zeile: sonst haengt die Knopfleiste am letzten
    Stueck, und der Verlauf zerfaellt in Haeppchen, die niemand zuordnen kann."""
    lang = "A" * 9000
    message_id = kanal.sende(CHAT, lang)
    assert repo.hole_web_post(conn, message_id)["text"] == lang
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 1


def test_sende_nimmt_den_klartext_wenn_es_einen_gibt(conn, kanal):
    """``parse_mode='HTML'`` plus ``klartext`` gehoeren in Telegram zusammen:
    der zweite ist der Rueckfall bei HTTP 400. Im Web gibt es kein 400, aber
    die Chatansicht filtert HTML ohnehin (Entscheidung F) -- gespeichert wird
    die HTML-Fassung, weil sie mehr Information traegt."""
    message_id = kanal.sende(
        CHAT, "1. <b>Ankommen</b> — am Bahnhof", parse_mode="HTML",
        klartext="1. Ankommen — am Bahnhof",
    )
    assert repo.hole_web_post(conn, message_id)["text"] == (
        "1. <b>Ankommen</b> — am Bahnhof"
    )


def test_sende_mit_knoepfen_haelt_die_leiste_fest(conn, kanal):
    leiste = [("Ja, speichern", "k:1"), ("Nein, nochmal ändern", "k:2")]
    message_id = kanal.sende_mit_knoepfen(CHAT, "Speichern?", leiste)
    zeile = repo.hole_web_post(conn, message_id)
    assert repo.web_knoepfe(zeile) == [["Ja, speichern", "k:1"],
                                       ["Nein, nochmal ändern", "k:2"]]


def test_sende_mit_knoepfen_prueft_die_64_byte_grenze(kanal):
    """Dieselbe Pruefung wie in Telegram, und aus demselben Grund: Zusage 1
    sagt, dass ein Knopf nur ``k:<id>`` traegt. Im Web gibt es die
    Byte-Grenze technisch nicht -- sie faellt weg zu lassen hiesse, dass ein
    Fehler gegen Zusage 1 erst im Telegram-Betrieb auffaellt."""
    with pytest.raises(ValueError):
        kanal.sende_mit_knoepfen(CHAT, "x", [("A", "k:" + "9" * 70)])


def test_aendere_text_und_entferne_knoepfe(conn, kanal):
    message_id = kanal.sende_mit_knoepfen(CHAT, "alt", [("A", "k:1")])
    kanal.aendere_text(CHAT, message_id, "neu")
    kanal.entferne_knoepfe(CHAT, message_id)
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["text"] == "neu"
    assert repo.web_knoepfe(zeile) == []


def test_aktualisiere_knoepfe_tauscht_die_leiste(conn, kanal):
    message_id = kanal.sende_mit_knoepfen(CHAT, "x", [("A", "k:1")])
    kanal.aktualisiere_knoepfe(CHAT, message_id, [("✓ A", "k:1"), ("B", "k:2")])
    assert repo.web_knoepfe(repo.hole_web_post(conn, message_id)) == [
        ["✓ A", "k:1"], ["B", "k:2"],
    ]


def test_loesche_nachrichten_liefert_die_zahl(conn, kanal):
    erste = kanal.sende(CHAT, "a")
    zweite = kanal.sende(CHAT, "b")
    assert kanal.loesche_nachrichten(CHAT, [erste, zweite]) == 2
    assert kanal.loesche_nachrichten(CHAT, []) == 0


def test_tippt_schreibt_keine_nachricht(conn, kanal):
    kanal.tippt(CHAT)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 0
    assert repo.hole_gruppe(conn, CHAT)["web_tippt_bis"] is not None


def test_setze_befehle_tut_nichts_und_faellt_nicht_um(conn, kanal):
    """Im Web gibt es kein Slash-Menue -- und Slash-Befehle werden nicht
    beworben (AGENTS.md). Die Methode existiert, damit ``bot.main``
    unveraendert bleibt."""
    kanal.setze_befehle([{"command": "stand", "description": "Stand zeigen"}])
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0


def test_beantworte_knopf_schreibt_die_antwort_an_den_druck(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF, daten="k:9",
        bezug_message_id=5,
    )
    kanal.beantworte_knopf(f"w{post_id}", "Begriffe uebernommen")
    assert repo.hole_web_post(conn, post_id)["antwort"] == "Begriffe uebernommen"


def test_beantworte_knopf_vertraegt_eine_unbekannte_kennung(kanal):
    """``knoepfe.wirkung._beantworte`` schluckt Fehler, aber eine Attrappe
    soll gar keinen werfen: Telegram antwortet auf einen alten Druck mit 400,
    und das ist kein Fehler des Bots."""
    kanal.beantworte_knopf("voellig-anders", "x")
    kanal.beantworte_knopf("w999999", "x")


def test_hole_updates_liefert_eine_textnachricht_die_lies_nachricht_deutet(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
        text="Unsere Begriffe: Ankommen, Arbeit, Nacht",
    )
    updates = kanal.hole_updates(0, timeout=0)
    assert [u["update_id"] for u in updates] == [post_id]

    gedeutet = telegram.lies_nachricht(updates[0])
    assert gedeutet["chat_id"] == CHAT
    assert gedeutet["message_id"] == post_id
    assert gedeutet["typ"] == "text"
    assert gedeutet["text"] == "Unsere Begriffe: Ankommen, Arbeit, Nacht"
    # E8: kein Vorname. "Gruppe" ist ein Rollenwort, kein Name -- und
    # kontext.sprecherzeile braucht EIN Wort, sonst steht "None:" im Prompt.
    assert gedeutet["absender"] == web_kanal.ABSENDER


def test_hole_updates_traegt_den_gruppentitel_mit(conn, kanal):
    """``bot.verarbeite_update`` reicht ``chat_titel`` an
    ``repo.sichere_gruppe`` weiter, und das ``ON CONFLICT DO UPDATE SET titel``
    wuerde einen Titel, der nicht mitkommt, bei JEDER Nachricht auf NULL
    setzen. Der Titel der Web-Gruppe steht in der Datenbank -- also von dort."""
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="x")
    updates = kanal.hole_updates(0, timeout=0)
    assert telegram.lies_nachricht(updates[0])["chat_titel"] == "Web-Gruppe"


def test_hole_updates_liefert_einen_knopfdruck_den_lies_knopfdruck_deutet(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF, daten="k:42",
        bezug_message_id=7,
    )
    updates = kanal.hole_updates(0, timeout=0)
    assert telegram.lies_nachricht(updates[0]) is None

    druck = telegram.lies_knopfdruck(updates[0])
    assert druck == {
        "callback_query_id": f"w{post_id}",
        "data": "k:42",
        "chat_id": CHAT,
        "chat_titel": "Web-Gruppe",
        "message_id": 7,
    }


def test_hole_updates_liefert_eine_sprachnachricht(conn, kanal):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        dauer=44, datei="7000000000001/web-eingang/1.webm", mime="audio/webm",
    )
    gedeutet = telegram.lies_nachricht(kanal.hole_updates(0, timeout=0)[0])
    assert gedeutet["typ"] == "sprache"
    assert gedeutet["dauer"] == 44
    assert gedeutet["file_id"] == web_kanal.datei_verweis(post_id, ".webm")


def test_hole_updates_uebergeht_ausgehende_posts(conn, kanal):
    kanal.sende(CHAT, "Bot spricht")
    assert kanal.hole_updates(0, timeout=0) == []


def test_hole_updates_wartet_bis_zum_timeout_und_kommt_dann_leer(kanal):
    """Der Long-Poll-Ersatz: ``bot.schleife`` ruft ``hole_updates(offset)``
    in einer engen Schleife. Ohne Wartezeit drehte sie mit hundert Prozent
    CPU-Last leer."""
    begonnen = time.monotonic()
    assert kanal.hole_updates(0, timeout=1) == []
    assert 0.5 <= time.monotonic() - begonnen < 3.0


def test_hole_updates_kommt_zurueck_sobald_etwas_eintrifft(conn, kanal):
    def spaeter():
        time.sleep(0.2)
        repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="da")

    threading.Thread(target=spaeter, daemon=True).start()
    begonnen = time.monotonic()
    updates = kanal.hole_updates(0, timeout=10)
    assert len(updates) == 1
    assert time.monotonic() - begonnen < 5.0
