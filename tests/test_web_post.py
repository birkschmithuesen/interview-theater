"""Die Tabelle web_post: EINE message_id-Folge fuer Gruppe UND Bot.

Warum das der Kern ist (Lehre aus simulation/attrappe.py.naechste_message_id):
der Bot merkt sich seinen Stand als letzte_beantwortete_message_id und liest
danach nur, was GROESSER ist. Zaehlten Gruppe und Bot in getrennten Folgen,
laege jede Gruppennachricht ab dem zweiten Zug unter dem Wasserzeichen.
"""

import pytest

from interview_theater import db, repo

CHAT = 7_000_000_000_001
ANDERE = 7_000_000_000_002


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    return verbindung


def test_eine_folge_fuer_beide_richtungen(conn):
    ein = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="Hallo")
    aus = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                               text="Auch hallo")
    zweite = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                   text="Und weiter")
    assert ein < aus < zweite


def test_eingang_liefert_nur_eingehende_ab_dem_offset(conn):
    erste = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="a")
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text="botantwort")
    zweite = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="b")

    assert [z["id"] for z in repo.web_eingang(conn, CHAT, 0)] == [erste, zweite]
    assert [z["id"] for z in repo.web_eingang(conn, CHAT, erste + 1)] == [zweite]


def test_eingang_ignoriert_fremde_gruppen(conn):
    repo.sichere_gruppe(conn, ANDERE, "gruppe2", "Andere")
    repo.lege_web_post_an(conn, ANDERE, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="nicht meine")
    assert repo.web_eingang(conn, CHAT, 0) == []


def test_knoepfe_kommen_als_liste_zurueck(conn):
    leiste = [("Ja, speichern", "k:12"), ("Nein, nochmal ändern", "k:13")]
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="Speichern?", knoepfe=leiste)
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == [
        ["Ja, speichern", "k:12"], ["Nein, nochmal ändern", "k:13"],
    ]


def test_leiste_austauschen_und_entfernen(conn):
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="x", knoepfe=[("A", "k:1")])
    assert repo.setze_web_knoepfe(conn, CHAT, post_id, [("B", "k:2")]) is True
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == [["B", "k:2"]]
    assert repo.setze_web_knoepfe(conn, CHAT, post_id, None) is True
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == []


def test_fremde_gruppe_darf_keine_leiste_aendern(conn):
    repo.sichere_gruppe(conn, ANDERE, "gruppe2", "Andere")
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="x", knoepfe=[("A", "k:1")])
    assert repo.setze_web_knoepfe(conn, ANDERE, post_id, None) is False
    assert repo.web_knoepfe(repo.hole_web_post(conn, post_id)) == [["A", "k:1"]]


def test_text_aendern_und_loeschen(conn):
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                    text="alt")
    assert repo.aendere_web_text(conn, CHAT, post_id, "neu") is True
    assert repo.hole_web_post(conn, post_id)["text"] == "neu"
    assert repo.loesche_web_posts(conn, CHAT, [post_id]) == 1
    assert repo.hole_web_post(conn, post_id)["geloescht_am"] is not None
    # Weiches Loeschen zweimal aendert nichts mehr.
    assert repo.loesche_web_posts(conn, CHAT, [post_id]) == 0


def test_antwort_auf_einen_knopfdruck(conn):
    post_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF,
                                    daten="k:7", bezug_message_id=3)
    repo.setze_web_antwort(conn, post_id, "Begriffe uebernommen")
    assert repo.hole_web_post(conn, post_id)["antwort"] == "Begriffe uebernommen"


def test_tippt_steht_in_der_gruppe_und_nicht_als_nachricht(conn):
    vorher = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text="x")
    repo.setze_web_tippt(conn, CHAT, "2026-09-30T10:00:08+00:00")
    assert repo.hole_gruppe(conn, CHAT)["web_tippt_bis"] == "2026-09-30T10:00:08+00:00"
    nachher = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text="y")
    # Die Tippanzeige verbraucht keine message_id: arbeitszeilen.TIPP_S = 4,0 s
    # heisst bei einem vierminuetigen Szenenlauf 60 Anzeigen.
    assert nachher == vorher + 1


def test_kanal_ist_ohne_zutun_telegram(conn):
    assert repo.hole_gruppe(conn, CHAT)["kanal"] == "telegram"
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    assert repo.hole_gruppe(conn, CHAT)["kanal"] == "web"


def test_naechste_web_chat_id_liegt_ausserhalb_der_telegram_bereiche(conn):
    erste = repo.naechste_web_chat_id(conn)
    assert erste > CHAT >= repo.WEB_CHAT_ID_BASIS
    assert repo.hole_gruppe(conn, erste) is None
    repo.sichere_gruppe(conn, erste, "gruppeX", "X")
    assert repo.naechste_web_chat_id(conn) == erste + 1


def test_web_post_steht_im_loeschweg():
    # Die Loeschzusage ist ein DELETE je Tabelle (db.loesche_gruppe) -- eine
    # Tabelle mit chat_id, die dort fehlt, ueberlebt das Loeschen einer Gruppe.
    assert "web_post" in db.TABELLEN_MIT_CHAT_ID


def test_loesche_gruppe_nimmt_web_posts_mit(conn):
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="a")
    db.loesche_gruppe(conn, CHAT)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 0


def test_migration_ruestet_web_post_in_einer_alten_datenbank_nach(tmp_path):
    # db.py migriert ausschliesslich additiv (AGENTS.md): eine Datenbank ohne
    # die Tabelle und ohne die Spalte muss beides beim naechsten Start
    # bekommen, ohne einen user_version-Schritt.
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    db.initialisiere(alt)
    alt.execute("DROP TABLE web_post")
    alt.execute("ALTER TABLE gruppe DROP COLUMN kanal")
    alt.commit()
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)
    repo.sichere_gruppe(neu, CHAT, "gruppe1", "X")
    assert repo.lege_web_post_an(
        neu, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="a"
    ) > 0
    assert repo.hole_gruppe(neu, CHAT)["kanal"] == "telegram"
