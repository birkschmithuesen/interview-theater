"""Welche Sprache Whisper hoert: der Gruppenwert vor dem Profilwert (D2)."""

import pytest

from interview_theater import aufnahme, db, repo, stt, workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_neue_spalte_ist_zuerst_leer(conn):
    assert repo.stt_sprache(conn, 1) is None


def test_setzen_und_zuruecknehmen(conn):
    repo.setze_stt_sprache(conn, 1, "it")
    assert repo.stt_sprache(conn, 1) == "it"
    repo.setze_stt_sprache(conn, 1, None)
    assert repo.stt_sprache(conn, 1) is None


def test_alte_datenbank_bekommt_die_spalte(tmp_path):
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.execute("CREATE TABLE gruppe (chat_id INTEGER PRIMARY KEY, bot_name TEXT NOT NULL)")
    c.commit()
    db.initialisiere(c)
    spalten = {z[1] for z in c.execute("PRAGMA table_info(gruppe)")}
    assert "stt_sprache" in spalten


def test_ohne_gruppenwert_gilt_das_profil(conn, monkeypatch):
    assert aufnahme.whisper_sprache(conn, 1) == "de"
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert aufnahme.whisper_sprache(conn, 1) == "auto"


def test_gruppenwert_schlaegt_profil(conn, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_stt_sprache(conn, 1, "it")
    assert aufnahme.whisper_sprache(conn, 1) == "it"


def test_die_aufnahme_reicht_die_sprache_an_whisper(conn, einst, tmp_path, monkeypatch):
    gesehen = []

    def transkribiere(e, klient, pfad, budget, *, sprache="de"):
        gesehen.append(sprache)
        return "Ciao."

    monkeypatch.setattr(stt, "transkribiere", transkribiere)
    repo.setze_stt_sprache(conn, 1, "auto")

    class TG:
        def tippt(self, chat_id): pass
        def sende(self, chat_id, text): return 1

    zeile = {"id": 1, "chat_id": 1, "klasse": "kurz",
             "audio_pfad": str(tmp_path / "a.ogg")}
    assert aufnahme._transkribiere_mit_meldung(conn, TG(), einst, None, zeile) == "Ciao."
    assert gesehen == ["auto"]


# --- Umstellen pro Gruppe: /sprache und drei Knoepfe in Phase 3 (Aufgabe 8) ---

from interview_theater import befehle, knoepfe, sprache  # noqa: E402
from simulation.attrappe import TelegramAttrappe  # noqa: E402


def _padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()


def _druecke(conn, tg, einst, beschriftung):
    knopf = next(k for k in tg.offene_knoepfe() if k["beschriftung"] == beschriftung)
    knoepfe.behandle(conn, tg, None, einst, {
        "callback_query_id": "q", "data": knopf["daten"],
        "chat_id": 1, "message_id": knopf["message_id"]})


def test_phase_3_bietet_in_padua_keine_sprachknoepfe_mehr(conn, einst, monkeypatch):
    """Bis 05.10. bot Padua hier Auto/English/Italiano an; seit 06.10. (Birk)
    steht die Interviewsprache immer auf Auto, ohne Abfrage."""
    _padua(monkeypatch)
    tg = TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, knoepfe.PHASE_INTERVIEWS)
    beschriftungen = [k["beschriftung"] for k in tg.offene_knoepfe()]
    assert not {"Auto", "English", "Italiano"} & set(beschriftungen)


def test_dortmund_sieht_die_sprachknoepfe_nie(conn, einst):
    tg = TelegramAttrappe()
    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 3)
    assert "Italiano" not in [k["beschriftung"] for k in tg.offene_knoepfe()]


def test_knopf_setzt_die_gruppensprache_und_wirkt_nur_einmal(conn, einst, monkeypatch):
    _padua(monkeypatch)
    # Die Leiste ist in Padua seit 06.10. aus (whisper_wahl_anbieten=false);
    # die Knopfwirkung selbst bleibt fuer Profile, die sie anbieten.
    echt = workshop.aktiv().wert
    monkeypatch.setattr(type(workshop.aktiv()), "wert",
                        lambda self, k, d=None: True if k == "sprache.whisper_wahl_anbieten" else echt(k, d))
    tg = TelegramAttrappe()
    knoepfe.biete_stt_sprache(conn, tg, 1)
    _druecke(conn, tg, einst, "Italiano")
    assert repo.stt_sprache(conn, 1) == "it"
    assert "Italiano" in tg.texte()[-1]
    # Zweiter Druck auf "English" derselben Leiste wirkt (andere Knopf-id),
    # ein zweiter Druck auf denselben Knopf nicht.
    knopf = next(k for k in tg.knoepfe[-1]["knoepfe"] if k[0] == "Italiano")
    vorher = len(tg.gesendet)
    knoepfe.behandle(conn, tg, None, einst, {
        "callback_query_id": "q2", "data": knopf[1], "chat_id": 1, "message_id": 1})
    assert len(tg.gesendet) == vorher


def test_befehl_sprache_zeigt_und_setzt(conn, einst):
    tg = TelegramAttrappe()
    assert befehle.behandle(conn, tg, einst, 1, "/sprache", None)
    assert "Deutsch" in tg.texte()[-1]
    befehle.behandle(conn, tg, einst, 1, "/sprache auto", None)
    assert repo.stt_sprache(conn, 1) == "auto"
    befehle.behandle(conn, tg, einst, 1, "/sprache klingonisch", None)
    assert repo.stt_sprache(conn, 1) == "auto"


def test_befehl_sprache_steht_nicht_im_menue():
    assert "sprache" not in {b["command"] for b in befehle.BEFEHLE_LISTE}


def test_englische_texte_des_sprachwegs(conn, einst, monkeypatch):
    _padua(monkeypatch)
    tg = TelegramAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/sprache", None)
    assert tg.texte()[-1] == "Interview language: automatic (I detect it myself)."


def test_padua_zeigt_keine_sprachabfrage_beim_eintritt(conn, einst, monkeypatch):
    """Padua 06.10.2026 (Birk): Interviewsprache immer Auto, keine Leiste.
    Mutant: Profilschalter ``whisper_wahl_anbieten`` ignoriert -> rot."""
    _padua(monkeypatch)
    tg = TelegramAttrappe()
    assert knoepfe.biete_stt_sprache(conn, tg, 1) is False
    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 3)
    assert "Italiano" not in [k["beschriftung"] for k in tg.offene_knoepfe()]
    assert repo.stt_sprache(conn, 1) is None
    assert sprache.whisper_vorgabe() == sprache.AUTO
