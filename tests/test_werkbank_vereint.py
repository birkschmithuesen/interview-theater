"""Die vereinte Seite mit read-only Werkbank (Padua, 03.10.2026)."""

import re

import pytest

from interview_theater import db, repo, sprache, web, web_chat, web_daten, web_vereint, workshop
from tests.fixture_sprache import baue_volle_englische_gruppe

FORMULAR = re.compile(r"<(select|textarea|input|button)\b|contenteditable", re.I)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _vereint(tmp_path, chat: bool = True) -> str:
    pfad = str(tmp_path / "v.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    token = baue_volle_englische_gruppe(conn)
    if chat:
        repo.setze_gruppe_kanal(conn, 1, "web")
    conn.commit()
    conn.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
        chatdaten = web_daten.web_chatzustand(lesend, token)
        roadmapdaten = web_daten.roadmap(lesend, daten["chat_id"])
    finally:
        lesend.close()
    if chatdaten is None:
        chatdaten = {"titel": daten["titel"], "nachrichten": [], "letzte": 0,
                     "interviewmodus": False, "tippt": False, "antworten": {}}
    for nachricht in chatdaten["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    return web_vereint.seite(daten, chatdaten, roadmapdaten, "nonce-x", token,
                             "/theatersoap", 45000, chat_vorhanden=chat)


def _panel(seite: str, tab: str) -> str:
    anfang = seite.index(f'id="tab-{tab}"')
    return seite[anfang:seite.index("</section>", anfang)]


def test_padua_ohne_speicher_skript_und_ohne_formular(tmp_path, padua):
    seite = _vereint(tmp_path)
    assert web._BEARBEITEN_JS not in seite
    assert not FORMULAR.search(_panel(seite, "stand"))


def test_padua_genau_ein_nonce_und_der_steht_im_chat(tmp_path, padua):
    seite = _vereint(tmp_path)
    assert seite.count('id="nonce"') == 1
    assert 'id="nonce"' in _panel(seite, "chat")


def test_padua_telegram_gruppe_ohne_nonce(tmp_path, padua):
    seite = _vereint(tmp_path, chat=False)
    assert 'id="nonce"' not in seite
    assert web._BEARBEITEN_JS not in seite


def test_padua_traegt_das_werkbank_css_gescopt(tmp_path, padua):
    assert ".panel-stand .wb-punkt.wb-erledigt" in _vereint(tmp_path)


def test_padua_der_leitfaden_steht_fuer_den_interview_modus_bereit(tmp_path, padua):
    assert '<pre class="leitfaden">' in _panel(_vereint(tmp_path), "stand")
