"""Padua: ein Interview = EINE Transkriptblase im Web-Chat (Karte
t_ea994c7f, ``[interview] fliesstext``). Telegram und das Vorgabeprofil
bleiben beim Echo je Teil."""

import inspect
import re
import threading
import time

import pytest

from interview_theater import (
    aufnahme, db, phasen, repo, sprache, telegram, web_daten, web_kanal, workshop,
)
from tests.test_aufnahme import (
    LLMAttrappe, TEIL_A, TEIL_B, TelegramAttrappe, interview_an, sprachnachricht,
    stt_attrappe,
)

#: Vier Teile ohne die Woerter "Teil"/"part" -- der Test sucht genau die.
TEILE = [
    "Ich kam im Winter an.",
    "Der Bahnhof war leer.",
    "Niemand hat gewartet.",
    "Dann kam meine Tante.",
]


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    # Phase 3: in Padua liefe eine Sprachnachricht in Phase 1 sonst in die
    # Hintergrund-Diskussion ([diskussion] aktiv).
    phasen.setze(c, 1, 3, "befehl")
    return c


@pytest.fixture
def klm():
    return LLMAttrappe()


class _Kanal(web_kanal.WebKanal):
    """Der echte WebKanal (schreibt ``web_post``), nur ohne Upload-Verzeichnis:
    ``lade_datei`` legt eine fingierte Audiodatei hin wie die
    TelegramAttrappe aus ``tests/test_aufnahme.py``."""

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")


@pytest.fixture
def web(conn, tmp_path):
    repo.setze_gruppe_kanal(conn, 1, "web")
    return _Kanal(conn, 1, str(tmp_path / "audio"), schritt_s=0.01)


@pytest.fixture
def fliesstext(monkeypatch):
    monkeypatch.setattr(workshop, "interview_fliesstext", lambda profil=None: True)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _interview(conn, kanal, einst, klm, texte, message_id=600):
    """Modus an, je Text eine Sprachnachricht durch den echten Weg
    (``empfange`` + ``verarbeite``). Liefert die id des Kopfes."""
    kopf_id = interview_an(conn)
    for i, text in enumerate(texte):
        aid = aufnahme.empfange(
            conn, kanal, einst, sprachnachricht(dauer=20, message_id=message_id + i)
        )
        aufnahme.verarbeite(conn, kanal, klm, einst, stt_attrappe(text), aid)
    return kopf_id


def _posts(conn, typ):
    return conn.execute(
        "SELECT * FROM web_post WHERE chat_id = 1 AND richtung = 'aus' AND typ = ? "
        "ORDER BY id", (typ,),
    ).fetchall()


# -- Aufgabe 3: die Kanalflaeche ---------------------------------------------


def test_webkanal_legt_eine_transkriptzeile_an_und_aendert_sie(conn, web):
    mid = web.sende(1, "🎙 Interview 1\n\nHallo", transkript=True)
    zeile = conn.execute("SELECT typ FROM web_post WHERE id = ?", (mid,)).fetchone()
    assert zeile["typ"] == repo.WEB_TYP_TRANSKRIPT == "transkript"

    web.aendere_text(1, mid, "🎙 Interview 1\n\nHallo\n\nWelt")
    zeile = conn.execute("SELECT typ, text, aenderung FROM web_post WHERE id = ?", (mid,)).fetchone()
    assert zeile["typ"] == "transkript", "aendere_text laesst den typ stehen"
    assert zeile["text"].endswith("Welt")
    assert zeile["aenderung"] is not None


def test_der_poll_liefert_die_transkriptzeile_und_ihre_aenderung(conn, web):
    mid = web.sende(1, "🎙 Interview 1\n\nHallo", transkript=True)
    assert [z["typ"] for z in web_daten.web_chatverlauf(conn, 1) if z["id"] == mid] == ["transkript"]

    web.aendere_text(1, mid, "🎙 Interview 1\n\nHallo\n\nWelt")
    geaendert, _stand = web_daten.web_chataenderungen(conn, 1, 0)
    assert mid in [z["id"] for z in geaendert]


def test_telegram_kennt_transkript_als_no_op():
    parameter = inspect.signature(telegram.Telegram.sende).parameters
    assert parameter["transkript"].default is False
    assert list(parameter)[-2:] == ["system", "transkript"]


# -- Aufgabe 4: eine Blase je Interview --------------------------------------


def test_vier_teile_sind_genau_eine_transkriptblase(conn, web, einst, klm, fliesstext):
    _interview(conn, web, einst, klm, TEILE)

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1, "eine Blase je Interview, nicht eine je Teil"
    text = blasen[0]["text"]
    assert text == "🎙 Interview 1\n\n" + "\n\n".join(TEILE)
    assert not re.search(r"\b(Teil|part)\b", text)
    assert not any(", Teil " in (p["text"] or "") for p in _posts(conn, repo.WEB_TYP_TEXT))


def test_die_blase_wird_einmal_mitgeschrieben(conn, web, einst, klm, fliesstext):
    """Entscheidung F: die nachricht-Zeile entsteht beim Anlegen, spaetere
    Aenderungen schreiben sie nicht nach (sie steht in keinem Fenster)."""
    kopf_id = _interview(conn, web, einst, klm, TEILE[:3])
    mitschrift = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = 1 AND typ = 'transkript'"
    ).fetchall()
    assert len(mitschrift) == 1
    assert mitschrift[0]["text"] == "🎙 Interview 1\n\n" + TEILE[0]
    assert repo.echo_message_id(conn, kopf_id) == _posts(conn, repo.WEB_TYP_TRANSKRIPT)[0]["id"]


def test_ohne_schalter_bleibt_es_im_web_ein_echo_je_teil(conn, web, einst, klm):
    _interview(conn, web, einst, klm, TEILE[:2])

    assert _posts(conn, repo.WEB_TYP_TRANSKRIPT) == []
    echos = [p["text"] for p in _posts(conn, repo.WEB_TYP_TEXT) if ", Teil " in (p["text"] or "")]
    assert echos == [
        f"Interview 1, Teil 1:\n{TEILE[0]}",
        f"Interview 1, Teil 2:\n{TEILE[1]}",
    ]


def test_telegram_bleibt_auch_mit_schalter_beim_echo_je_teil(conn, einst, klm, fliesstext):
    tg = TelegramAttrappe()  # hat kein aendere_text -- ein Aufruf waere ein Fehler
    _interview(conn, tg, einst, klm, TEILE[:2])

    assert [t for _, t, _ in tg.mit_knoepfen] == [
        f"Interview 1, Teil 1:\n{TEILE[0]}",
        f"Interview 1, Teil 2:\n{TEILE[1]}",
    ]
    assert all(leiste for _, _, leiste in tg.mit_knoepfen), "die Leiste aus biete_nach_teil bleibt"


# -- Aufgabe 5: Nebenlaeufigkeit ---------------------------------------------


class _LangsamerKanal(_Kanal):
    """Haelt ``sende`` 0,2 s auf -- genug, damit zwei Threads ohne Sperre
    beide "noch keine Blase" lesen und beide eine anlegen."""

    def sende(self, *args, **kw):
        time.sleep(0.2)
        return super().sende(*args, **kw)


def test_zwei_gleichzeitige_teile_ergeben_eine_blase(conn, einst, tmp_path, fliesstext):
    repo.setze_gruppe_kanal(conn, 1, "web")
    kanal = _LangsamerKanal(conn, 1, str(tmp_path / "audio"), schritt_s=0.01)
    kopf_id = interview_an(conn)
    for i, text in enumerate(TEILE[:2]):
        aid = repo.lege_aufnahme_an(
            conn, 1, 700 + i, "teil", "sprache", dauer=5, teil_von=kopf_id,
            status="transkribiert",
        )
        repo.setze_transkript(conn, aid, text)

    start = threading.Barrier(2)

    def lauf():
        start.wait()
        aufnahme._sende_transkript_blase(conn, kanal, einst, 1, kopf_id)

    faeden = [threading.Thread(target=lauf) for _ in range(2)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(timeout=10)

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1
    assert TEILE[0] in blasen[0]["text"] and TEILE[1] in blasen[0]["text"]


# -- Aufgabe 6: an_den_bot ----------------------------------------------------


def test_ein_abgezweigter_teil_verschwindet_aus_der_blase(conn, web, einst, klm, fliesstext, monkeypatch):
    from interview_theater import erkenner

    kopf_id = interview_an(conn)
    erster = repo.lege_aufnahme_an(conn, 1, 710, "teil", "sprache", dauer=5,
                                   teil_von=kopf_id, status="fertig")
    repo.setze_transkript(conn, erster, TEILE[0])
    frage = repo.lege_aufnahme_an(conn, 1, 711, "teil", "sprache", dauer=5,
                                  teil_von=kopf_id, status="transkribiert")
    repo.setze_transkript(conn, frage, "Zeig mir die Verdichtungen.")
    # Ein paralleler Teil hat die Blase schon gebaut -- mit der Frage darin.
    aufnahme._sende_transkript_blase(conn, web, einst, 1, kopf_id)
    assert "Zeig mir" in _posts(conn, repo.WEB_TYP_TRANSKRIPT)[0]["text"]

    monkeypatch.setattr(
        erkenner, "erkenne_in_aufnahme",
        lambda *a, **k: [{"art": "an_den_bot", "wert": ""}],
    )
    aufnahme._teil_abschliessen(conn, web, klm, einst, repo.hole_aufnahme(conn, frage))

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1
    assert blasen[0]["text"] == "🎙 Interview 1\n\n" + TEILE[0]


def test_nur_aendern_legt_nie_eine_blase_an(conn, web, einst, fliesstext):
    kopf_id = interview_an(conn)
    aufnahme._sende_transkript_blase(conn, web, einst, 1, kopf_id, nur_aendern=True)
    assert _posts(conn, repo.WEB_TYP_TRANSKRIPT) == []


# -- Aufgabe 7: die Abschlusszeile spricht die Workshop-Sprache ----------------


def _verdichtetes_interview(conn):
    kopf_id = repo.lege_interview_an(conn, 1)
    teil = repo.lege_aufnahme_an(conn, 1, 720, "teil", "sprache", dauer=120,
                                 teil_von=kopf_id, status="fertig")
    repo.setze_transkript(conn, teil, "egal")
    vid = repo.speichere_verdichtung(conn, 1, kopf_id, "Zusammenfassung", [
        {"thema": "Ankommen", "kurz": "Ankommen", "beleg_zitat": "egal", "zitat_geprueft": 1},
    ])
    return repo.hole_aufnahme(conn, kopf_id), vid


def test_abschlusszeile_deutsch_ohne_profil(conn, einst):
    row, vid = _verdichtetes_interview(conn)
    zeilen = aufnahme._text_interview_gespeichert_web(conn, row, vid, einst).split("\n")
    assert re.fullmatch(r"Interview 1 gespeichert · \d\d:\d\d Uhr · 2 Min", zeilen[0])
    assert zeilen[1:] == ["Themen: Ankommen", "Ganze Auswertung im Tab Arbeitsstand."]


def test_abschlusszeile_deutsch_in_dortmund(conn, einst, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        row, vid = _verdichtetes_interview(conn)
        zeilen = aufnahme._text_interview_gespeichert_web(conn, row, vid, einst).split("\n")
    finally:
        workshop.vergiss()
        sprache.vergiss()
    assert re.fullmatch(r"Interview 1 gespeichert · \d\d:\d\d Uhr · 2 Min", zeilen[0])
    assert zeilen[1:] == ["Themen: Ankommen", "Ganze Auswertung im Tab Arbeitsstand."]


def test_abschlusszeile_englisch_in_padua(conn, einst, padua):
    row, vid = _verdichtetes_interview(conn)
    zeilen = aufnahme._text_interview_gespeichert_web(conn, row, vid, einst).split("\n")
    assert re.fullmatch(r"Interview 1 saved · \d\d:\d\d · 2 min", zeilen[0])
    assert zeilen[1:] == ["Topics: Ankommen", "Full analysis in the Workbench tab."]


# -- Aufgabe 8: Abschluss und "sehr kurz" als Systemzeilen ---------------------


def _texte(conn, typ):
    return [p["text"] or "" for p in _posts(conn, typ)]


def test_abschlusszeile_ist_im_web_mit_schalter_eine_systemzeile(conn, web, einst, klm, fliesstext):
    kopf_id = _interview(conn, web, einst, klm, [TEIL_A, TEIL_B])
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, web, klm, einst, kopf_id)

    assert any(t.startswith("Interview 1 gespeichert · ") for t in _texte(conn, repo.WEB_TYP_SYSTEM))
    assert not any("gespeichert · " in t for t in _texte(conn, repo.WEB_TYP_TEXT))


def test_zu_kurz_ist_im_web_mit_schalter_eine_systemzeile(conn, web, einst, klm, fliesstext):
    kopf_id = _interview(conn, web, einst, klm, ["nur ein kurzer Satz"])
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, web, klm, einst, kopf_id)

    assert any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_SYSTEM))
    assert not any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_TEXT))


def test_ohne_schalter_bleibt_zu_kurz_eine_textzeile(conn, web, einst, klm):
    kopf_id = _interview(conn, web, einst, klm, ["nur ein kurzer Satz"])
    aufnahme.beende_interview(conn, 1)
    aufnahme.schliesse_ab(conn, web, klm, einst, kopf_id)

    assert any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_TEXT))
    assert not any("war sehr kurz" in t for t in _texte(conn, repo.WEB_TYP_SYSTEM))


# -- Aufgabe 9: "Aufnahme beendet." als Systemzeile ---------------------------


def test_fertig_befehl_meldet_als_systemzeile(conn, web, einst, fliesstext):
    from interview_theater import befehle

    befehle.behandle(conn, web, einst, 1, "/interview", "Ada")
    befehle.behandle(conn, web, einst, 1, "/fertig", "Ada")

    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_SYSTEM)
    assert "Aufnahme beendet." not in _texte(conn, repo.WEB_TYP_TEXT)


def test_aufnahme_umschalter_meldet_als_systemzeile(conn, web, einst, fliesstext):
    from interview_theater import befehle

    befehle.behandle(conn, web, einst, 1, "/aufnahme", "Ada")
    befehle.behandle(conn, web, einst, 1, "/aufnahme", "Ada")

    assert "Bereit - schickt eure Sprachnachrichten." not in _texte(conn, repo.WEB_TYP_SYSTEM)
    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_SYSTEM)


def test_erkenner_meldet_das_ende_als_systemzeile(conn, web, einst, fliesstext):
    from interview_theater import erkenner

    erkenner._melde_interviewmodus(web, conn, einst, 1, [{"art": "interview_beenden"}])

    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_SYSTEM)


def _alle_texte(conn):
    return [z["text"] for z in conn.execute(
        "SELECT text FROM web_post WHERE chat_id = 1 AND richtung = 'aus' ORDER BY id"
    ).fetchall()]


@pytest.mark.parametrize("befehl", ["/interview", "/aufnahme"])
def test_web_interviewstart_spricht_nicht_von_sprachnachrichten(conn, web, einst, padua, befehl):
    """P34 Runde 1, Befund A1 (= J-p3-eintritt-1, Lauf 205532, Screenshot
    006): nach ``/interview`` stand im Web-Chat "Ready - send your voice
    messages ..." -- Telegram-Bedienung; im Browser laeuft die Aufnahme
    ueber den Rekorder. Der Web-Text nennt den Beenden-Knopf der Oberflaeche."""
    from interview_theater import befehle, web_chat

    befehle.behandle(conn, web, einst, 1, befehl, "Ada")

    texte = " ".join(_alle_texte(conn))
    assert "voice message" not in texte
    assert "send your" not in texte
    assert web_chat.T._TEXT_INTERVIEW_AUS in texte


def test_web_interviewstart_deutsch_ohne_sprachnachrichten(conn, web, einst):
    """Dito ohne Profil (Deutsch): Gegenprobe, dass die DE-Konstante
    mitgezogen ist."""
    from interview_theater import befehle, web_chat

    befehle.behandle(conn, web, einst, 1, "/interview", "Ada")

    texte = " ".join(_alle_texte(conn))
    assert "Sprachnachricht" not in texte
    assert web_chat.T._TEXT_INTERVIEW_AUS in texte


def test_ohne_schalter_bleibt_aufnahme_beendet_text(conn, web, einst):
    from interview_theater import befehle

    befehle.behandle(conn, web, einst, 1, "/interview", "Ada")
    befehle.behandle(conn, web, einst, 1, "/fertig", "Ada")

    assert "Aufnahme beendet." in _texte(conn, repo.WEB_TYP_TEXT)
    assert "Aufnahme beendet." not in _texte(conn, repo.WEB_TYP_SYSTEM)
