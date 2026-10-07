"""Die Werkbank aus der read-only Verbindung (Padua, 03.10.2026)."""

import json

import pytest

from interview_theater import db, repo, sprache, web_daten, workshop

CHAT = 7_000_000_000_001


@pytest.fixture
def profil(monkeypatch):
    def setze(name):
        if name is None:
            monkeypatch.delenv(workshop.VARIABLE, raising=False)
        else:
            monkeypatch.setenv(workshop.VARIABLE, name)
        workshop.vergiss()
        sprache.vergiss()
    yield setze
    workshop.vergiss()
    sprache.vergiss()


def _db(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "X")
    conn.commit()
    return pfad, conn


def _werkbank(pfad):
    lesend = web_daten.oeffne_lesend(pfad)   # mode=ro: jeder Schreibversuch wirft
    try:
        return web_daten.werkbank(lesend, CHAT)
    finally:
        lesend.close()


def _zeile(werkbank, nummer, kennung, bezug=None):
    phase = next(p for p in werkbank["phasen"] if p["nummer"] == nummer)
    for z in phase["zeilen"]:
        if z["kennung"] == kennung and (bezug is None or z["bezug"] == bezug):
            return z
    raise AssertionError(f"{nummer}/{kennung}/{bezug} nicht gefunden")


def test_liest_ueber_die_read_only_verbindung(tmp_path, profil):
    profil("padua-2026")
    pfad, _ = _db(tmp_path)
    ergebnis = _werkbank(pfad)
    assert [p["nummer"] for p in ergebnis["phasen"]] == [1, 2, 3, 4, 5, 6, 7]
    assert ergebnis["begriffe_detail"] == []
    assert ergebnis["szenen_anzahl"] is None


def test_die_roadmap_bleibt_dieselbe(tmp_path, profil):
    """Herausloesen von ``_roadmap_lage`` darf ``roadmap()`` nicht aendern."""
    profil(None)
    pfad, conn = _db(tmp_path)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat")
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        from interview_theater import roadmap
        assert web_daten.roadmap(lesend, CHAT) == roadmap.aus_daten(
            web_daten._roadmap_lage(lesend, CHAT))
    finally:
        lesend.close()


def test_diskussion_ist_in_keinem_profil_eine_werkbankzeile(tmp_path, profil):
    """Birk, 05.10.2026: die Diskussionsverdichtung laeuft still im
    Hintergrund und geht in den Phase-2-Prompt -- sie ist kein Schritt der
    Gruppe, also weder offen noch erledigt in der Werkbank, auch nicht in
    Padua und auch nicht, wenn sie schon existiert."""
    pfad, conn = _db(tmp_path)
    for name in (None, "padua-2026"):
        profil(name)
        assert all(z["kennung"] != "diskussion"
                   for z in _werkbank(pfad)["phasen"][0]["zeilen"])
    repo.merke_diskussion_verdichtung(conn, CHAT, "Sie redeten ueber Heimat.", None)
    conn.commit()
    assert all(z["kennung"] != "diskussion"
               for z in _werkbank(pfad)["phasen"][0]["zeilen"])


def test_ueberarbeitung_gesamttext_form_und_sprechweise(tmp_path, profil):
    profil("padua-2026")
    pfad, conn = _db(tmp_path)
    repo.setze_phase(conn, CHAT, 7)
    eins = repo.lege_szene_an(conn, CHAT, 1, "Ankunft", None, "A: Hallo.")
    repo.lege_szene_an(conn, CHAT, 2, "Abschied", None, "A: Tschuess.")
    repo.setze_szene_ueberarbeitung_bestaetigt(conn, eins)
    repo.setze_szenenfeld(conn, eins, "form", "dialog")
    repo.setze_arbeitsstand(conn, CHAT, "gesamttext_fixiert_am", "2026-10-03T10:00:00+00:00")
    repo.setze_figur(conn, CHAT, "Nadia", "die Aeltere")
    repo.setze_figur(conn, CHAT, "Tomas", "der Juengere")
    nadia = next(f for f in repo.figuren(conn, CHAT) if f["name"] == "Nadia")
    repo.setze_figur_sprachstil(conn, nadia["id"], "Knapp: Ja. Nein.")
    conn.commit()
    w = _werkbank(pfad)
    assert _zeile(w, 6, "gesamttext")["status"] == "erledigt"
    assert _zeile(w, 6, "ueberarbeitet", 1)["status"] == "erledigt"
    assert _zeile(w, 6, "ueberarbeitet", 2)["status"] == "offen"
    assert _zeile(w, 7, "form", 1)["status"] == "erledigt"
    assert _zeile(w, 7, "form", 2)["status"] == "offen"
    assert _zeile(w, 7, "sprechweise", "Nadia")["status"] == "erledigt"
    assert _zeile(w, 7, "sprechweise", "Tomas")["status"] == "offen"


def test_begriffe_detail_mit_spalte(tmp_path, profil):
    """Simuliert Karte t_4517d4ad: die Spalte wird hier von Hand angelegt."""
    profil("padua-2026")
    pfad, conn = _db(tmp_path)
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    if "begriffe_detail" not in spalten:
        conn.execute("ALTER TABLE arbeitsstand ADD COLUMN begriffe_detail TEXT")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat")
    conn.execute(
        "UPDATE arbeitsstand SET begriffe_detail = ? WHERE chat_id = ?",
        (json.dumps([{"begriff": "Heimat", "begruendung": "kam dreimal",
                      "zitat": "z", "doppelbedeutung": "Ort und Gefuehl"}]), CHAT),
    )
    conn.commit()
    assert _werkbank(pfad)["begriffe_detail"] == [
        {"begriff": "Heimat", "begruendung": "kam dreimal", "doppelbedeutung": "Ort und Gefuehl"},
    ]


def test_werkbank_traegt_die_recherche_leer_ohne_recherche(tmp_path, profil):
    profil("padua-2026")
    pfad, _ = _db(tmp_path)
    assert _werkbank(pfad)["recherche"] == []


def test_werkbank_traegt_die_recherche_mit_quelle(tmp_path, profil):
    profil("padua-2026")
    pfad, conn = _db(tmp_path)
    repo.speichere_recherche(
        conn, CHAT, "When was the bridge built?",
        "The bridge was built in 1900 (Example, https://x.test).",
        [{"titel": "Example", "url": "https://x.test"}],
    )
    conn.commit()
    assert _werkbank(pfad)["recherche"] == [{
        "frage": "When was the bridge built?",
        "ergebnis_text": "The bridge was built in 1900 (Example, https://x.test).",
        "quellen": ["Example"],
    }]


def test_gruppe_nach_token_traegt_die_werkbank_nur_ohne_bearbeitung(tmp_path, profil):
    pfad, conn = _db(tmp_path)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    for name, erwartet_liste in ((None, False), ("padua-2026", True)):
        profil(name)
        lesend = web_daten.oeffne_lesend(pfad)
        try:
            daten = web_daten.gruppe_nach_token(lesend, token)
        finally:
            lesend.close()
        if erwartet_liste:
            assert isinstance(daten["werkbank"]["phasen"], list)
        else:
            assert daten["werkbank"] is None
