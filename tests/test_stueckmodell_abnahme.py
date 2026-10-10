"""Abnahme Karte t_fd88600b, Probleme 1-4. Jeder Test wird rot, wenn eine
Ansicht ihre Tatsache wieder aus einer ZWEITEN Stelle liest (Giftwert im
Karten-JSON) oder wenn Prosa still umgeschrieben wird."""

import json

import pytest

from interview_theater import phasen, repo, stagescript, stueck, szenenkarte, web, web_daten, workshop
from interview_theater.knoepfe import szenen as ks
from tests.stueck_hilfe import TG, lege_karte_an

GIFT = "GIFTWERT-ZWEITE-SPALTE"


class E:
    bot_name = "test"


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def _vergifte(conn, sid, **felder):
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    roh.update(felder)
    conn.execute("UPDATE szene SET karte = ? WHERE id = ?", (json.dumps(roh), sid))
    conn.commit()


def _alle_ansichten(conn, sid) -> str:
    token = repo.stelle_web_token_sicher(conn, 1)
    daten = web_daten.gruppe_nach_token(conn, token)
    szene = repo.hole_szene(conn, sid)
    k = stueck.karte(conn, szene)
    return "\n".join([
        szenenkarte.karte_text(k, szene, 1),                       # Karte im Chat
        web._szenenkarten_html(web_daten.szenenkarten(conn, 1), 1),  # Karte im CoThinker
        web.textbuch_html(daten, token),                           # Script-Kopf + PDF-Quelle
        web._wb_szenen_verdichtet_html(
            [dict(s, verdichtet=s.get("verdichtet") or {}) for s in daten["szenen"]]),  # Werkbank
        stagescript.baue_nutzertext(conn, 1, szene),               # Prompt-Block
    ])


def test_problem_1_ort_in_p7_aendern_alle_ansichten_ohne_nachzug(conn, padua):
    phasen.setze(conn, 1, 7, "test")
    sid = lege_karte_an(conn, ort="Sala prove", bestaetigt=True)
    repo.setze_stagescript(conn, sid, "SCENE 1 -- Sala prove.", None)
    _vergifte(conn, sid, ort=GIFT)

    assert stueck.setze_ort(conn, 1, szene=1, ort="Sala riunioni").ok

    alles = _alle_ansichten(conn, sid)
    assert alles.count("Sala riunioni") >= 5
    assert GIFT not in alles


def test_problem_1_wer_eine_stelle(conn, padua):
    repo.setze_figur(conn, 1, "Anna", "")
    sid = lege_karte_an(conn, wer="Anna")
    _vergifte(conn, sid, wer=GIFT)
    stueck.figur_hinzu(conn, 1, name="Chicca", szene=1, rolle="(Cover)")
    alles = _alle_ansichten(conn, sid)
    assert "Chicca (Cover)" in alles and GIFT not in alles


def test_problem_2_jede_mutation_in_jeder_phase(conn):
    lege_karte_an(conn, 1, 1, bestaetigt=True)
    lege_karte_an(conn, 1, 2, bestaetigt=True)
    repo.setze_figur(conn, 1, "Anna", "")
    for phase in range(1, 8):
        phasen.setze(conn, 1, phase, "test")
        assert stueck.setze_ort(conn, 1, szene=1, ort=f"Ort {phase}").ok, phase
        assert stueck.figur_hinzu(conn, 1, name=f"Figur {phase}", szene=2).ok, phase
        assert stueck.karte_aendern(conn, 1, szene=1, worum=f"w{phase}").ok, phase
        assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="karte").ok, phase
        assert stueck.reihenfolge_aendern(conn, 1, folge=[2, 1]).ok, phase
        f = stueck.frage_stellen(conn, 1, szene=1, frage=f"Frage {phase}?")
        assert stueck.frage_beantworten(conn, 1, frage_id=f.frage_id, antwort="ja").ok, phase


def test_problem_2_abgenommene_karte_nach_p6_ueber_den_chatweg(conn):
    phasen.setze(conn, 1, 7, "test")
    lege_karte_an(conn, 1, 1, bestaetigt=True)
    lege_karte_an(conn, 1, 2)
    szenenkarte.starte_dialog(conn, TG(), E(), 1, 1)
    assert szenenkarte.dialog_aktive_nummer(conn, 1) == 1


def test_problem_3_prosa_nie_still_umgeschrieben_aber_angeboten(conn):
    sid = lege_karte_an(conn, ort="Bar")
    repo.setze_stagescript(conn, sid, "SCENE 1 -- Bar.", None)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert repo.hole_szene(conn, sid)["volltext"] == "SCENE 1 -- Bar."
    [v] = repo.offene_veraltet(conn, 1)
    tg = TG()
    assert ks.biete_veraltete(conn, tg, E(), 1) == 1
    assert "1" in tg.gesendet[-1] and "Piazza" in tg.gesendet[-1]


def test_problem_3_veraltet_kommt_aus_der_tabelle_nicht_aus_einem_flag(conn):
    """Rot, wenn jemand statt ``veraltet`` wieder fertig_am/einen Zweitstatus
    als Wahrheit nimmt: das Angebot haengt allein an der veraltet-Zeile."""
    sid = lege_karte_an(conn, ort="Bar")
    repo.setze_stagescript(conn, sid, "SCENE 1 -- Bar.", None)
    repo.setze_szene_fertig(conn, sid, True)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert repo.hole_szene(conn, sid)["fertig_am"]  # Abnahme bleibt
    assert len(repo.offene_veraltet(conn, 1)) == 1


def test_problem_4_im_chat_beantwortet_ist_geschlossen(conn, padua):
    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    _vergifte(conn, sid, fragen=[GIFT], punkte=["p", f"[OPEN] {GIFT}"])
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, E(), 1, 1)
    szenenkarte.beantworte_frage(conn, tg, None, E(), 1, "Im Loch")
    alles = _alle_ansichten(conn, sid)
    assert "Wo steht Giona?" not in alles
    assert not any("[OPEN]" in p for p in
                   stueck.karte(conn, repo.hole_szene(conn, sid))["punkte"])
    assert GIFT not in json.dumps(stueck.karte(conn, repo.hole_szene(conn, sid)))
