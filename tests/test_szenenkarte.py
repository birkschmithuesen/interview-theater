"""Padua-Phasenumbau (Birk 07.10.2026 ~18:12, ``[karten] aktiv``): Phase 5 =
nur Interviews auswaehlen, "Done" bietet Phase 6 an; Phase 6 = eine
Szenenkarte nach der anderen mit "Yes, save" / "No, change"; danach die
Gesamtpruefung einmal ueber alle Karten und das Angebot Phase 7."""

import json

import pytest

from interview_theater import (
    phasen, repo, schaerfung, szene, szenenkarte, szenenkern, ueberarbeitung, workshop,
)

ZITAT_A = "Casa non sono le mura, sono le voci."
ZITAT_B = "L'odore del ragù la domenica."


class TG:
    def __init__(self):
        self.texte = []
        self.leisten = []
        self._n = 100

    def sende(self, chat_id, text, **_kw):
        self._n += 1
        self.texte.append(text)
        return self._n

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        self._n += 1
        self.texte.append(text)
        self.leisten.append(knoepfe_)
        return self._n

    def __getattr__(self, name):
        return lambda *a, **k: None


class LLM:
    def __init__(self):
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "nutzer": nutzer})
        if art == szenenkarte.ART_PRUEFUNG:
            return {"befunde": ["Scene 2 needs a clearer ending."]}
        if art == szenenkarte.ART:
            return {"typ": "spoken", "worum": "The voices are shared.", "ort": "semicircle",
                    "wer": "Emma, Giada", "punkte": ["Emma opens", "Giada answers"],
                    "zitate": [2, 99, 1], "questions": ["Who sings?"]}
        return {"kern": ["a"], "zitate": []}


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def _lage(conn, szenen=2):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, ZITAT_A + " " + ZITAT_B)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Z.", [
        {"thema": "Casa", "beleg_zitat": ZITAT_A, "zitat_geprueft": 1},
        {"thema": "Odori", "beleg_zitat": ZITAT_B, "zitat_geprueft": 1}])
    repo.setze_arbeitsstand(conn, 1, "format", "Concert performance, post-dramatic")
    ids = []
    for n in range(1, szenen + 1):
        sid = repo.stelle_szene_sicher(conn, 1, n)
        repo.setze_szenenfeld(conn, sid, "titel", f"Szene {n}")
        repo.setze_szenenfeld(conn, sid, "was_passiert", f"Was in {n} passiert.")
        ids.append(sid)
    themen = [z["id"] for z in conn.execute("SELECT id FROM verdichtung_thema ORDER BY id")]
    repo.lege_schaerfung_an(conn, 1, [
        {"verdichtung_thema_id": t, "szene_id": sid} for sid in ids for t in themen])
    phasen.setze(conn, 1, 5, "befehl")
    return ids


def test_ohne_schalter_bleibt_phase_6_an_der_geschichte(conn):
    _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    assert workshop.szenenkarten_aktiv() is False
    assert phasen.voraussetzungen(conn, 1)[6] is False


def test_phase_6_braucht_szenen_und_eine_auswahl(conn, padua):
    _lage(conn)
    assert phasen.voraussetzungen(conn, 1)[6] is False
    schaerfung.uebernimm_stellen(conn, 1, [repo.schaerfungen(conn, 1)[0]["id"]])
    assert phasen.voraussetzungen(conn, 1)[6] is True


def test_done_in_phase_5_bietet_phase_6_statt_prosa(conn, einst, padua, monkeypatch):
    from interview_theater import entwurf
    from interview_theater.knoepfe import szenen as ks

    _lage(conn)
    conn.execute("UPDATE schaerfung SET entscheidung = 'ja'")
    conn.commit()
    monkeypatch.setattr(entwurf, "starte_uebersicht",
                        lambda *a, **k: pytest.fail("keine Uebersicht mehr"))
    monkeypatch.setattr(szene, "starte", lambda *a, **k: pytest.fail("kein Prosalauf"))
    ks._letztes_done.clear()
    tg = TG()
    ks.schliesse_schaerfungsliste(conn, tg, None, einst, 1)
    assert any("Taken on: 4" in t for t in tg.texte)
    assert tg.leisten, "Angebot Phase 6 mit Knopf"


def test_kein_szenentext_in_phase_5(conn, einst, padua):
    _lage(conn)
    tg = TG()
    assert szene.starte(conn, tg, LLM(), einst, 1, "Schreib Szene 1.") is None
    assert tg.texte == [szene.T._TEXT_ERST_KARTEN]


def test_karte_nimmt_zitate_im_original_aus_der_db(conn, einst, padua):
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    karte = szenenkarte.erzeuge(conn, LLM(), einst, 1, 1)
    assert karte["typ"] == "spoken"
    assert [z["zitat"] for z in karte["zitate"]] == [ZITAT_B, ZITAT_A]
    gespeichert = json.loads(repo.hole_szene(conn, ids[0])["karte"])
    assert gespeichert == karte


def test_baue_nutzertext_zeigt_zitate_zur_wahl_ungekuerzt(conn, padua):
    """Nachtrag Birk 08.10.2026 (Vorrang vor Punkt 2): die Zitate zur Wahl
    gehen voll in den Prompt -- "das wertvollste Material" wird nicht auf
    ``szenenkern.ZITAT_ZEICHEN_PROMPT`` (400 Zeichen) gekappt."""
    ids = _lage(conn)
    lang = ("Casa " * 120).strip()  # deutlich ueber 400 Zeichen
    assert len(lang) > szenenkern.ZITAT_ZEICHEN_PROMPT
    conn.execute("UPDATE verdichtung_thema SET beleg_zitat = ? WHERE thema = 'Casa'", (lang,))
    conn.commit()
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])

    text = szenenkarte.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))

    assert lang in text


def test_baue_nutzertext_nimmt_ueber_claude_parameter_entgegen(conn, padua):
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    szene_zeile = repo.hole_szene(conn, ids[0])

    ohne_claude = szenenkarte.baue_nutzertext(conn, 1, szene_zeile)
    mit_claude = szenenkarte.baue_nutzertext(conn, 1, szene_zeile, ueber_claude=True)

    assert "Interviews behind your chosen passages" in ohne_claude
    assert "Interviews behind your chosen passages" not in mit_claude


def test_erzeuge_gibt_denselben_ueber_claude_wert_an_hintergrund_und_aufruf(
    conn, einst, padua, monkeypatch,
):
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    monkeypatch.setattr(szenenkarte.szene_claude, "ist_aktiv", lambda e, c, cid: True)
    gesehen = {}

    def fake_aufruf_schema(conn, klm, e, chat_id, *, system, nutzer, schema, art,
                           ueber_claude, **kw):
        gesehen["ueber_claude"] = ueber_claude
        gesehen["nutzer"] = nutzer
        return {"typ": "spoken", "worum": "W", "ort": "o", "wer": "w",
                "punkte": ["P"], "zitate": [], "questions": []}

    monkeypatch.setattr(szenenkarte.modellwahl, "aufruf_schema", fake_aufruf_schema)
    szenenkarte.erzeuge(conn, LLM(), einst, 1, 1)

    assert gesehen["ueber_claude"] is True
    assert "Interviews behind your chosen passages" not in gesehen["nutzer"]


def test_phase_6_eine_karte_nach_der_anderen(conn, einst, padua):
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    phasen.setze(conn, 1, 6, "befehl")
    tg, klm = TG(), LLM()

    ueberarbeitung.weiter_6(conn, tg, klm, einst, 1, aus_eintritt=True).join(5)
    # Morgen-Auftrag 4: Kartentext ab Phase 6 italienisch.
    assert any("Scheda scena 1" in t for t in tg.texte)
    assert any(ZITAT_A in t for t in tg.texte)
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 1

    # "No, change" + Notiz: dieselbe Karte neu, mit Notiz und alter Karte.
    ueberarbeitung.ueberarbeite(conn, tg, klm, einst, 1, "Emma sings first", nummer=1).join(5)
    letzter = klm.aufrufe[-1]["nutzer"]
    assert "Emma sings first" in letzter and "Previous card:" in letzter

    # "Yes, save" (Knopfweg) -> naechste Karte.
    ueberarbeitung.bestaetige_szene_6(conn, tg, klm, einst, 1, 1)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    assert repo.hole_szene(conn, ids[0])["karte_bestaetigt_am"]
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 2
    assert phasen.voraussetzungen(conn, 1)[7] is False

    # Veralteter Knopf fuer Karte 1: nichts passiert. Italienisch ab Phase 6
    # (Morgen-Auftrag 4): T_IT, nicht T.
    assert ueberarbeitung.bestaetige_szene_6(conn, tg, klm, einst, 1, 1) == \
        szenenkarte.T_IT._TEXT_NICHT_DRAN

    faden = szenenkarte.bestaetige(conn, tg, klm, einst, 1, 2)
    for _ in range(50):
        stand = repo.hole_arbeitsstand(conn, 1)
        if stand["karten_geprueft_am"]:
            break
        import time
        time.sleep(0.05)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    assert faden == "Scheda 2 salvata"
    assert any("Scene 2 needs a clearer ending." in t for t in tg.texte)
    assert phasen.voraussetzungen(conn, 1)[7] is True
    # Prosa-Rewrite lief nie.
    assert all(a["art"] in (szenenkarte.ART, szenenkarte.ART_PRUEFUNG) for a in klm.aufrufe)


def test_karte_punkte_begrenzt_auf_120_zeichen(conn, einst, padua):
    """Birk 08.10.2026 ~23:15: Punkte hart auf ~1 Zeile/120 Zeichen begrenzen
    (Prompt + Anzeige) -- lange Modellantworten duerfen keine Textwaende
    auf dem Handy ergeben."""
    _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])

    class LangeLLM(LLM):
        def schema(self, chat_id, system, nutzer, schema, art):
            if art == szenenkarte.ART:
                lang = "Wort " * 40
                return {"typ": "spoken", "worum": "x", "ort": "y", "wer": "z",
                        "punkte": [lang], "zitate": [], "questions": [lang]}
            return super().schema(chat_id, system, nutzer, schema, art)

    karte = szenenkarte.erzeuge(conn, LangeLLM(), einst, 1, 1)
    assert all(len(p) <= 120 for p in karte["punkte"]), karte["punkte"]
    assert all(len(f) <= 120 for f in karte["fragen"]), karte["fragen"]


def test_schema_punkte_beschreibung_nennt_120_zeichen():
    assert "120" in szenenkarte.SCHEMA["properties"]["punkte"]["description"]


def test_eintritt_phase_6_spricht_von_karten(conn, padua):
    from interview_theater import phasentexte

    _lage(conn)
    text = phasentexte.eintritt(conn, 1, 6)
    assert "Scene cards (0 of 2)" in text
    assert "read the whole story" not in text
