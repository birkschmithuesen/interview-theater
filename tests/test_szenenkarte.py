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
    #: Keine offenen Fragen in der Grundausstattung (08.10.2026, Punkt 1/2):
    #: dieser Mock dient dem Ablauf "eine Karte nach der anderen", nicht der
    #: Fragenklaerung -- die hat ihre eigenen Tests mit ``LLMMitFragen``.
    FRAGEN: list[str] = []

    def __init__(self):
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "nutzer": nutzer})
        if art == szenenkarte.ART_PRUEFUNG:
            return {"befunde": ["Scene 2 needs a clearer ending."]}
        if art == szenenkarte.ART:
            return {"typ": "spoken", "worum": "The voices are shared.", "ort": "semicircle",
                    "wer": "Emma, Giada", "punkte": ["Emma opens", "Giada answers"],
                    "zitate": [2, 99, 1], "questions": list(self.FRAGEN)}
        return {"kern": ["a"], "zitate": []}


class LLMMitFragen(LLM):
    """Jede gebaute Karte hat eine offene Frage (Fragenklaerung, Punkt 1/2)."""

    FRAGEN = ["Who sings?"]


class LLMMitZweiFragen(LLM):
    FRAGEN = ["Who sings?", "Where does it end?"]


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


def test_baue_nutzertext_nimmt_ueber_claude_parameter_entgegen(conn, padua, monkeypatch):
    """Padua selbst gibt die Einwilligung pauschal (Birk 08.10.2026), die
    Verdichtungen gingen also auch mit ``ueber_claude=True`` mit (siehe
    ``tests/test_hintergrund.py``) -- hier wird nur die Weiterleitung des
    Parameters geprueft, deshalb mit der Vorgabe (Einwilligung je Gruppe
    noetig) isoliert."""
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "modellwahl_einwilligung_aktiv", lambda *a, **k: True)
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
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "modellwahl_einwilligung_aktiv", lambda *a, **k: True)
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


def test_erzeuge_haengt_italienisch_nur_fuer_gelistete_chats_an(conn, einst, padua, monkeypatch):
    """Morgen-Auftrag 4, Nachtrag 2: eine Chat-Liste, kein globaler
    Schalter -- _system_fuer() haengt den Zusatzsatz nur fuer Chats aus
    workshop.italienisch_ab_phase6_chats() an das System-Prompt."""
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    gesehen = {}

    def fake_aufruf_schema(conn, klm, e, chat_id, *, system, nutzer, schema, art,
                           ueber_claude, **kw):
        gesehen["system"] = system
        return {"typ": "spoken", "worum": "W", "ort": "o", "wer": "w",
                "punkte": ["P"], "zitate": [], "questions": []}

    monkeypatch.setattr(szenenkarte.modellwahl, "aufruf_schema", fake_aufruf_schema)

    szenenkarte.erzeuge(conn, LLM(), einst, 1, 1)
    assert "Write all output in Italian" not in gesehen["system"]

    monkeypatch.setattr(workshop, "italienisch_ab_phase6_chats", lambda *a, **k: frozenset({1}))
    szenenkarte.erzeuge(conn, LLM(), einst, 1, 1, notiz="again")
    assert "Write all output in Italian" in gesehen["system"]


def test_phase_6_eine_karte_nach_der_anderen(conn, einst, padua):
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    phasen.setze(conn, 1, 6, "befehl")
    tg, klm = TG(), LLM()

    ueberarbeitung.weiter_6(conn, tg, klm, einst, 1, aus_eintritt=True).join(5)
    # Morgen-Auftrag 4: Kartentext ab Phase 6 italienisch.
    assert any("Scene card 1" in t for t in tg.texte)
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

    # Veralteter Knopf fuer Karte 1: nichts passiert. chat_id 1 steht in
    # keiner italienisch_ab_phase6_chats-Liste -- englisch (T, nicht T_IT).
    assert ueberarbeitung.bestaetige_szene_6(conn, tg, klm, einst, 1, 1) == \
        szenenkarte.T._TEXT_NICHT_DRAN

    faden = szenenkarte.bestaetige(conn, tg, klm, einst, 1, 2)
    for _ in range(50):
        stand = repo.hole_arbeitsstand(conn, 1)
        if stand["karten_geprueft_am"]:
            break
        import time
        time.sleep(0.05)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    assert faden == "Card 2 saved"
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
    """chat_id 1 steht nicht in ``workshop.italienisch_ab_phase6_chats()``
    (Nachtrag 2: eine Chat-Liste, kein globaler Schalter) -- die Einleitung
    bleibt englisch; siehe tests/test_p67_italienisch_eintritt.py fuer den
    italienischen Fall."""
    from interview_theater import phasentexte

    _lage(conn)
    text = phasentexte.eintritt(conn, 1, 6)
    assert "Scene cards (0 of 2)" in text
    assert "read the whole story" not in text


def test_baue_nutzertext_ohne_alte_prosa(conn, einst, padua):
    """Birk/Robo 08.10.2026, Punkt 4: die Prosa-Aera ist vorbei -- ein
    frueherer Prosatext darf nicht mehr ungeprueft als Material in den
    Karten-Prompt rutschen."""
    ids = _lage(conn)
    conn.execute("UPDATE szene SET prosa = ? WHERE id = ?",
                ("Es war einmal ein Chor am Meer.", ids[0]))
    conn.commit()
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    szene = next(s for s in repo.hole_szenen(conn, 1) if s["nummer"] == 1)
    text = szenenkarte.baue_nutzertext(conn, 1, szene)
    assert "Es war einmal ein Chor am Meer." not in text


# ---------------------------------------------------------------------------
# Offene Fragen klaeren (Birk 08.10.2026 ~09:20, Punkte 1 und 2)
# ---------------------------------------------------------------------------


def _karte1(conn, einst, llm) -> list[int]:
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    szenenkarte.erzeuge(conn, llm, einst, 1, 1)
    return ids


def test_zeige_clear_skip_statt_yes_no_bei_offenen_fragen(conn, einst, padua):
    _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    szenenkarte.zeige(conn, tg, einst, 1, 1)
    assert [c for c, _ in tg.leisten[-1]] == ["Clear the questions", "Skip questions"]


def test_zeige_yes_no_ohne_offene_fragen(conn, einst, padua):
    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.zeige(conn, tg, einst, 1, 1)
    assert [c for c, _ in tg.leisten[-1]] == ["Yes, save", "No, change"]


def test_bestaetige_lehnt_karte_mit_offenen_fragen_ab(conn, einst, padua):
    """Serverseitig: "Yes, save" (Knopf, Befehl oder Chat) speichert nie eine
    Karte mit offenen Fragen -- nicht nur die Anzeige bietet andere
    Knoepfe an."""
    ids = _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    antwort = szenenkarte.bestaetige(conn, tg, LLM(), einst, 1, 1)
    assert antwort == szenenkarte.T._TEXT_FRAGEN_OFFEN_ABGELEHNT
    assert repo.hole_szene(conn, ids[0])["karte_bestaetigt_am"] is None


def test_ueberspringe_fragen_leert_fragen_laesst_punkte_zitate(conn, einst, padua):
    ids = _karte1(conn, einst, LLMMitFragen())
    vorher = szenenkarte.karte_von(repo.hole_szene(conn, ids[0]))
    tg = TG()
    antwort = szenenkarte.ueberspringe_fragen(conn, tg, einst, 1, 1)
    nachher = szenenkarte.karte_von(repo.hole_szene(conn, ids[0]))
    assert nachher["fragen"] == []
    assert nachher["punkte"] == vorher["punkte"]
    assert nachher["zitate"] == vorher["zitate"]
    assert antwort == "Questions on card 1 skipped"
    eintrag = next(j for j in repo.journal(conn, 1) if j["art"] == "entschieden"
                   and "skipped as not fitting" in j["text"])
    assert eintrag["quelle"] == "web"
    assert eintrag["text"] == "Card 1: questions skipped as not fitting"
    # Danach wieder Yes/No -- die Fragen sind weg.
    assert [c for c, _ in tg.leisten[-1]] == ["Yes, save", "No, change"]


def test_ueberspringe_fragen_ohne_offene_fragen_tut_nichts(conn, einst, padua):
    ids = _karte1(conn, einst, LLM())
    vorher = len(repo.journal(conn, 1))
    tg = TG()
    antwort = szenenkarte.ueberspringe_fragen(conn, tg, einst, 1, 1)
    assert antwort == szenenkarte.T._TEXT_NICHT_DRAN
    assert len(repo.journal(conn, 1)) == vorher


def test_starte_fragenklaerung_stellt_erste_frage(conn, einst, padua):
    _karte1(conn, einst, LLMMitZweiFragen())
    tg = TG()
    antwort = szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    assert antwort == "Clearing the questions"
    assert tg.texte[-1] == "Question 1 of 2: Who sings?"
    assert szenenkarte.aktive_klaerung(conn, 1) == (1, {"index": 0, "antworten": [], "runde": 1})


def test_beantworte_frage_ohne_aktive_klaerung_liefert_false(conn, einst, padua):
    _karte1(conn, einst, LLM())
    tg = TG()
    assert szenenkarte.beantworte_frage(conn, tg, LLM(), einst, 1, "Emma sings first") is False


def test_beantworte_frage_stellt_naechste_frage(conn, einst, padua):
    _karte1(conn, einst, LLMMitZweiFragen())
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    treffer = szenenkarte.beantworte_frage(conn, tg, LLM(), einst, 1, "Emma, molto chiaro")
    assert treffer is True
    assert tg.texte[-1] == "Question 2 of 2: Where does it end?"
    _, klaerung = szenenkarte.aktive_klaerung(conn, 1)
    assert klaerung == {"index": 1, "antworten": ["Emma, molto chiaro"], "runde": 1}


def test_beantworte_letzte_frage_baut_karte_mit_allen_antworten_neu(conn, einst, padua):
    ids = _karte1(conn, einst, LLMMitZweiFragen())
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    szenenkarte.beantworte_frage(conn, tg, LLM(), einst, 1, "Emma sings first")
    klm = LLM()
    szenenkarte.beantworte_frage(conn, tg, klm, einst, 1, "Al tramonto, sulla spiaggia")
    # Der Rueckgabewert ist ein bool (beantwortet oder nicht), nicht der
    # Thread -- warten ueber die Sperre wie beim Knopfweg.
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    letzter = klm.aufrufe[-1]["nutzer"]
    assert "Who sings? -> Emma sings first" in letzter
    assert "Where does it end? -> Al tramonto, sulla spiaggia" in letzter
    journal = [j for j in repo.journal(conn, 1) if j["quelle"] == "chat"]
    assert any("Emma sings first" in j["text"] for j in journal)
    assert szenenkarte.aktive_klaerung(conn, 1) is None
    assert repo.hole_szene(conn, ids[0])["karte_klaerung"] is None


def test_beantworte_frage_skip_wird_als_open_punkt_uebernommen(conn, einst, padua):
    """Birk 08.10.2026 ~09:30: "skip" darf den Weg nie blockieren -- die
    Frage wird als "[OPEN] ..."-Punkt uebernommen und gilt als geklaert."""
    ids = _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    szenenkarte.beantworte_frage(conn, tg, LLM(), einst, 1, "skip")
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    karte = szenenkarte.karte_von(repo.hole_szene(conn, ids[0]))
    assert "[OPEN] Who sings?" in karte["punkte"]
    offen = [j for j in repo.journal(conn, 1) if "left open on purpose" in j["text"]]
    assert offen and offen[0]["quelle"] == "chat"


@pytest.mark.parametrize("text", ["skip", "I don't know", "no idea", "IDK", "non lo so"])
def test_ist_skip_erkennt_gaengige_formen(text):
    assert szenenkarte.ist_skip(text) is True


def test_ist_skip_erkennt_keinen_inhalt_als_skip():
    assert szenenkarte.ist_skip("I don't know yet, but maybe Emma") is False


def test_zweite_automatische_runde_dann_hinweis_ohne_dritte(conn, einst, padua):
    """"Hoechstens EINE solche Runde automatisch" (Birk): legt der Neubau
    nach der ersten Klaerungsrunde wieder eine Frage an, laeuft die
    Klaerung automatisch ein zweites Mal -- aber nicht ein drittes Mal."""
    ids = _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    klm = LLMMitFragen()
    szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    fragen_vorher = sum(1 for t in tg.texte if t.startswith("Question 1 of 1"))
    assert fragen_vorher == 1
    # Runde 1 beantworten -> Neubau legt wieder eine Frage an -> Runde 2
    # startet automatisch.
    szenenkarte.beantworte_frage(conn, tg, klm, einst, 1, "Emma sings first")
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    assert sum(1 for t in tg.texte if t.startswith("Question 1 of 1")) == 2
    assert szenenkarte.aktive_klaerung(conn, 1) == (1, {"index": 0, "antworten": [], "runde": 2})
    # Runde 2 beantworten -> Neubau legt WIEDER eine Frage an -> keine
    # dritte automatische Runde, die Karte wird stattdessen gezeigt.
    szenenkarte.beantworte_frage(conn, tg, klm, einst, 1, "Giada answers")
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    assert sum(1 for t in tg.texte if t.startswith("Question 1 of 1")) == 2
    assert szenenkarte.aktive_klaerung(conn, 1) is None
    assert [c for c, _ in tg.leisten[-1]] == ["Clear the questions", "Skip questions"]


def test_ablauf_leitet_antwort_an_offene_frage_um(conn, einst, padua):
    """Die Chat-Antwort auf eine gestellte Frage faellt aus dem normalen
    Gespraechszug heraus -- derselbe Gedanke wie die Regie-Notiz
    (``szenenfolge.erwarte_regienotiz``), hier DB-gestuetzt."""
    from interview_theater import ablauf

    _karte1(conn, einst, LLMMitZweiFragen())
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    nachricht = {"text": "Emma sings first", "message_id": 4242}
    ausgefallen = ablauf._szene_hat_vorfahrt(conn, tg, LLM(), einst, 1, nachricht)
    assert ausgefallen is True
    assert tg.texte[-1] == "Question 2 of 2: Where does it end?"


@pytest.mark.parametrize("notiz", [
    "The questions clearing",
    "let's discuss the questions",
    "Parliamo delle domande",
])
def test_aendere_mit_fragenwort_springt_direkt_in_klaerweg(conn, einst, padua, notiz):
    """Birk 08.10.2026 ~09:20, Punkt 3: der genaue Vorfall vom Workshop --
    "No, change" + eine Notiz ZU den Fragen baute die Karte neu und loeschte
    sie klammheimlich. Jetzt springt so eine Notiz direkt in den Klaerweg,
    kein Modellaufruf."""
    _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    klm = LLM()
    ergebnis = szenenkarte.aendere(conn, tg, klm, einst, 1, notiz, nummer=1)
    assert ergebnis is None
    assert klm.aufrufe == []
    assert tg.texte[-1] == "Question 1 of 1: Who sings?"


def test_aendere_mit_unverwandter_notiz_bewahrt_alte_fragen(conn, einst, padua):
    """Eine Notiz, die nichts mit den Fragen zu tun hat, kann sie nicht
    beantwortet haben -- faellt der Neubau (hier: ``LLM`` ohne Fragen) sie
    weg, holt die Nachbereitung sie zurueck."""
    ids = _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    klm = LLM()
    szenenkarte.aendere(conn, tg, klm, einst, 1, "Emma sings first", nummer=1)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    assert "Emma sings first" in klm.aufrufe[-1]["nutzer"]
    karte = szenenkarte.karte_von(repo.hole_szene(conn, ids[0]))
    assert karte["fragen"] == ["Who sings?"]


def test_aendere_mit_unverwandter_notiz_dupliziert_nicht(conn, einst, padua):
    """Behaelt der Neubau die Frage selbst (hier: ``LLMMitFragen`` liefert
    sie wieder), steht sie trotzdem nur einmal auf der Karte."""
    ids = _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    klm = LLMMitFragen()
    szenenkarte.aendere(conn, tg, klm, einst, 1, "Emma sings first", nummer=1)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    karte = szenenkarte.karte_von(repo.hole_szene(conn, ids[0]))
    assert karte["fragen"] == ["Who sings?"]


def test_zwei_antworten_in_einer_nachricht_blockiert_den_weg_nicht(conn, einst, padua):
    """Eine Gruppe, die beide Antworten in eine Nachricht packt: kein
    Absturz, die ganze Nachricht gilt als Antwort auf die GERADE gestellte
    Frage, die naechste Frage kommt danach wie immer."""
    _karte1(conn, einst, LLMMitZweiFragen())
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    treffer = szenenkarte.beantworte_frage(
        conn, tg, LLM(), einst, 1, "Emma sings first, and it ends at sunset on the beach")
    assert treffer is True
    assert tg.texte[-1] == "Question 2 of 2: Where does it end?"


# ---------------------------------------------------------------------------
# Karten-Verlauf (Birk 08.10.2026 ~10:35): jede Fassung bleibt erhalten --
# Grundlage des Verfeinerungs-Blocks in Phase 7 (``stagescript.py``) und des
# Phase-6-Summary (``phasen_summary.py``).
# ---------------------------------------------------------------------------


def test_erzeuge_erstentwurf_legt_erste_verlauf_fassung_an(conn, einst, padua):
    ids = _karte1(conn, einst, LLM())
    reihen = repo.karte_verlauf(conn, 1, ids[0])
    assert len(reihen) == 1
    assert reihen[0]["ausloeser"] == "erstentwurf"
    assert reihen[0]["notiz_text"] is None
    assert json.loads(reihen[0]["karte_json"])["worum"] == "The voices are shared."


def test_aendere_legt_verlauf_fassung_mit_notiz_an(conn, einst, padua):
    ids = _karte1(conn, einst, LLM())
    szenenkarte.aendere(conn, TG(), LLM(), einst, 1, "piano with pedal", nummer=1)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    reihen = repo.karte_verlauf(conn, 1, ids[0])
    assert len(reihen) == 2
    assert reihen[1]["ausloeser"] == "aenderung"
    assert reihen[1]["notiz_text"] == "piano with pedal"


def test_beantworte_letzte_frage_legt_verlauf_fassung_fragen_geklaert_an(conn, einst, padua):
    ids = _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, einst, 1, 1)
    szenenkarte.beantworte_frage(conn, tg, LLM(), einst, 1, "Emma sings first")
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    reihen = repo.karte_verlauf(conn, 1, ids[0])
    assert reihen[-1]["ausloeser"] == "fragen_geklaert"
    assert "Who sings? -> Emma sings first" in reihen[-1]["notiz_text"]


def test_ueberspringe_fragen_legt_verlauf_fassung_an(conn, einst, padua):
    ids = _karte1(conn, einst, LLMMitFragen())
    szenenkarte.ueberspringe_fragen(conn, TG(), einst, 1, 1)
    reihen = repo.karte_verlauf(conn, 1, ids[0])
    assert reihen[-1]["ausloeser"] == "fragen_uebersprungen"
    assert reihen[-1]["notiz_text"] == "questions skipped as not fitting"


def test_diff_karten_meldet_geaenderte_felder():
    alt = {"typ": "spoken", "modus": "none", "worum": "A", "ort": "beach", "wer": "Emma",
           "punkte": ["a", "b"], "zitate": [{"zitat": "x", "interview": "1"}]}
    neu = dict(alt, worum="B", punkte=["a", "c"])

    unterschiede = szenenkarte.diff_karten(alt, neu)

    text = "; ".join(unterschiede)
    assert "worum" in text
    assert "punkte" in text
    assert "ort" not in text
    assert "zitate" not in text


def test_diff_karten_ignoriert_fragen_feld():
    alt = {"typ": "spoken", "modus": "none", "worum": "A", "ort": "o", "wer": "w",
           "punkte": ["a"], "zitate": [], "fragen": ["Q1"]}
    neu = dict(alt, fragen=[])

    assert szenenkarte.diff_karten(alt, neu) == []


def test_verfeinerungs_zeilen_zeigt_notiz_und_diff(conn, einst, padua):
    """Szenario aus dem Auftrag: Karte -> No change "piano with pedal" ->
    neue Karte -> die Verfeinerungs-Zeilen tragen Notiz UND Diff."""
    ids = _karte1(conn, einst, LLM())

    class AndereKarte(LLM):
        def schema(self, chat_id, system, nutzer, schema, art):
            if art == szenenkarte.ART:
                return {"typ": "spoken", "worum": "The voices are shared.", "ort": "semicircle",
                        "wer": "Emma, Giada",
                        "punkte": ["Emma opens with pedal down", "Giada answers"],
                        "zitate": [2, 99, 1], "questions": []}
            return super().schema(chat_id, system, nutzer, schema, art)

    szenenkarte.aendere(conn, TG(), AndereKarte(), einst, 1, "piano with pedal", nummer=1)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()

    szene = repo.hole_szene(conn, ids[0])
    zeilen = szenenkarte.verfeinerungs_zeilen(conn, 1, szene)

    assert len(zeilen) == 1
    assert "piano with pedal" in zeilen[0]
    assert "punkte" in zeilen[0]


def test_verfeinerungs_zeilen_leer_ohne_aenderung(conn, einst, padua):
    ids = _karte1(conn, einst, LLM())
    szene = repo.hole_szene(conn, ids[0])
    assert szenenkarte.verfeinerungs_zeilen(conn, 1, szene) == []


def test_verfeinerungs_zeilen_fragen_uebersprungen_wortlaut(conn, einst, padua):
    ids = _karte1(conn, einst, LLMMitFragen())
    szenenkarte.ueberspringe_fragen(conn, TG(), einst, 1, 1)
    szene = repo.hole_szene(conn, ids[0])
    zeilen = szenenkarte.verfeinerungs_zeilen(conn, 1, szene)
    assert any("questions skipped as not fitting" in z for z in zeilen)


def test_verfeinerungs_zeilen_ohne_erstentwurf_zeigt_notiz_trotzdem(conn, einst, padua):
    """Nachtrag (Birk 08.10.2026 ~10:48): der Verlauf laesst sich aus dem
    Chat oft nur AB der ersten Aenderung rekonstruieren, der Erstentwurf
    selbst steht nirgends (CoThinker zeigt ihn nie im Chat). Eine einzige
    nachgetragene Fassung ohne vorige ``erstentwurf``-Zeile muss trotzdem
    eine Verfeinerungs-Zeile ergeben -- sonst verschwindet genau die
    haeufigste rekonstruierte Aenderung (eine Karte, eine Korrektur)."""
    ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    szene_id = ids[0]
    # Nur EINE nachgetragene Fassung, kein "erstentwurf" davor -- genau der
    # Luecken-Fall aus dem Chat-Nachtrag.
    repo.merke_karte_verlauf(
        conn, 1, szene_id, json.dumps({"typ": "spoken", "worum": "X"}),
        "aenderung", "Il barattolo è truccato",
    )
    szene = repo.hole_szene(conn, szene_id)
    zeilen = szenenkarte.verfeinerungs_zeilen(conn, 1, szene)
    assert len(zeilen) == 1
    assert "truccato" in zeilen[0]
