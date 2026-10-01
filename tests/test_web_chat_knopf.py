"""Knopfdruck im Browser -- dieselbe Wirkung wie in Telegram.

Der Server prueft nur EINES: dass ``data`` wirklich in der Leiste steht, die
gerade unter dieser Nachricht in dieser Gruppe haengt. Die Wirkung macht
danach ``knoepfe.behandle`` im Bot-Prozess, unveraendert -- samt Idempotenz
ueber ``repo.beanspruche_knopf`` (Zusage 3). Es gibt hier keinen zweiten
Knopf-Handler.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, telegram, web, web_chat, web_daten, web_kanal

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)

    # Eine Leiste, wie sie der Bot ueber WebKanal hinlegt.
    kanal = web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"), schritt_s=0.01)
    knopf_id = repo.lege_knopf_an(conn, CHAT, "speichern", "begriffe|Ankommen")
    message_id = kanal.sende_mit_knoepfen(
        CHAT, "Speichern?",
        [("Ja, speichern", f"k:{knopf_id}"), ("Nein, nochmal ändern", "k:999")],
    )
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad, message_id, f"k:{knopf_id}"
    dienst.shutdown()


def _post(url: str, koerper: dict):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


# -- die reine Pruefung ----------------------------------------------------


def test_knopf_erlaubt_nur_was_in_der_leiste_steht():
    leiste = [["Ja, speichern", "k:1"], ["Nein", "k:2"]]
    assert web_chat.knopf_erlaubt(leiste, "k:1") is True
    assert web_chat.knopf_erlaubt(leiste, "k:2") is True
    assert web_chat.knopf_erlaubt(leiste, "k:3") is False
    assert web_chat.knopf_erlaubt(leiste, "") is False
    assert web_chat.knopf_erlaubt(leiste, None) is False


def test_keine_leiste_erlaubt_nichts():
    assert web_chat.knopf_erlaubt([], "k:1") is False
    assert web_chat.knopf_erlaubt(None, "k:1") is False


def test_leiste_einer_fremden_gruppe_ist_none(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "A")
    repo.sichere_gruppe(conn, 7_000_000_000_002, "gruppe2", "B")
    message_id = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS,
                                       repo.WEB_TYP_TEXT, text="x",
                                       knoepfe=[("A", "k:1")])
    conn.commit()
    pfad = str(tmp_path / "t.db")
    conn.close()

    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_leiste(lesend, CHAT, message_id) == [["A", "k:1"]]
    assert web_daten.web_leiste(lesend, 7_000_000_000_002, message_id) is None
    assert web_daten.web_leiste(lesend, CHAT, 999_999) is None
    lesend.close()


# -- der Weg ueber HTTP ----------------------------------------------------


def test_ein_gueltiger_druck_legt_ein_callback_update_an(aufbau):
    basis, token, pfad, message_id, daten = aufbau
    status, text = _post(
        f"{basis}/g/{token}/chat/knopf",
        {"nonce": web.nonce(SCHLUESSEL, token), "message_id": message_id, "data": daten},
    )
    assert status == 202
    post_id = json.loads(text)["post_id"]

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, post_id)
    assert zeile["typ"] == repo.WEB_TYP_KNOPF
    assert zeile["daten"] == daten
    assert zeile["bezug_message_id"] == message_id

    # Und der Bot liest daraus einen Knopfdruck, keine Nachricht: ein
    # callback_query darf nie in ``nachricht`` landen, sonst liest ihn der
    # Erkenner als Gruppenbeitrag (AGENTS.md, die Weiche in bot.schleife).
    kanal = web_kanal.WebKanal(conn, CHAT, "/tmp/audio", schritt_s=0.01)
    update = kanal.hole_updates(post_id, timeout=0)[0]
    assert telegram.lies_nachricht(update) is None
    assert telegram.lies_knopfdruck(update)["data"] == daten


def test_fremde_daten_geben_400_und_legen_nichts_an(aufbau):
    basis, token, pfad, message_id, _daten = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": message_id, "data": "k:4711"})
    assert fehler.value.code == 400
    conn = db.verbinde(pfad)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE typ = 'knopf'"
    ).fetchone()[0] == 0


def test_daten_unter_einer_anderen_nachricht_geben_400(aufbau):
    """Genau diese message_id -- nicht 'irgendwo im Chat'."""
    basis, token, pfad, message_id, daten = aufbau
    conn = db.verbinde(pfad)
    andere = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS,
                                   repo.WEB_TYP_TEXT, text="ohne Leiste")
    conn.close()
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": andere, "data": daten})
    assert fehler.value.code == 400


def test_eine_abgenommene_leiste_wirkt_nicht_mehr(aufbau):
    """``entferne_knoepfe`` nimmt die Leiste weg, nachdem ein Knopf gewirkt
    hat. Danach darf derselbe Druck keinen zweiten Eingang erzeugen -- der
    Doppelklick wird schon hier abgefangen, und die Idempotenz ueber
    ``beanspruche_knopf`` bleibt die zweite Sperre dahinter."""
    basis, token, pfad, message_id, daten = aufbau
    conn = db.verbinde(pfad)
    repo.setze_web_knoepfe(conn, CHAT, message_id, None)
    conn.close()
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": message_id, "data": daten})
    assert fehler.value.code == 400


def test_der_zweite_druck_bei_stehender_leiste_wird_angenommen(aufbau):
    """Solange die Leiste haengt, ist ein zweiter Druck ein zweiter Druck --
    und ``repo.beanspruche_knopf`` im Bot-Prozess entscheidet, dass er nicht
    wirkt (Zusage 3, bedingtes UPDATE). Der Server raet das nicht vorweg."""
    basis, token, _pfad, message_id, daten = aufbau
    koerper = {"nonce": web.nonce(SCHLUESSEL, token),
               "message_id": message_id, "data": daten}
    assert _post(f"{basis}/g/{token}/chat/knopf", koerper)[0] == 202
    assert _post(f"{basis}/g/{token}/chat/knopf", koerper)[0] == 202


def test_message_id_ohne_zahl_gibt_400(aufbau):
    basis, token, _pfad, _message_id, daten = aufbau
    for kaputt in ("abc", None, -1, 0):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _post(f"{basis}/g/{token}/chat/knopf",
                  {"nonce": web.nonce(SCHLUESSEL, token),
                   "message_id": kaputt, "data": daten})
        assert fehler.value.code == 400


def test_ohne_nonce_gibt_es_403(aufbau):
    basis, token, _pfad, message_id, daten = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/knopf",
              {"message_id": message_id, "data": daten})
    assert fehler.value.code == 403


def test_die_leiste_steht_im_html_als_knoepfe(aufbau):
    basis, token, _pfad, message_id, daten = aufbau
    with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
        text = antwort.read().decode("utf-8")
    assert f'data-message="{message_id}"' in text
    assert f'data-daten="{daten}"' in text
    assert "Ja, speichern" in text


def test_kein_neuer_knopf_handler_im_web():
    """Die Wirkung eines Knopfes steht an genau einer Stelle:
    ``knoepfe/wirkung.py``. ``web_chat`` legt nur ein Update an -- es
    importiert das Knopf-Paket nicht und beansprucht keinen Knopf."""
    from pathlib import Path

    quelle = Path(web_chat.__file__).read_text(encoding="utf-8")
    assert "beanspruche_knopf" not in quelle
    assert "import knoepfe" not in quelle
    assert "from interview_theater.knoepfe" not in quelle
