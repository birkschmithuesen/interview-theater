import json

from interview_theater import repo, stueck


def _szene(conn, nummer=1, volltext=None, karte=True):
    sid = repo.stelle_szene_sicher(conn, 1, nummer)
    if karte:
        repo.setze_szenenkarte(conn, sid, json.dumps(
            {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}))
    if volltext:
        repo.setze_stagescript(conn, sid, volltext, None)
    return sid


def test_setze_ort_eine_stelle_und_protokoll(conn):
    sid = _szene(conn)
    e = stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert e.ok and e.aenderung_id
    assert repo.hole_szene(conn, sid)["ort"] == "Piazza"
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["ort"] == "Piazza"
    [a] = repo.stueck_aenderungen(conn, 1)
    assert a["art"] == "setze_ort"


def test_gleicher_ort_ist_kein_ereignis(conn):
    _szene(conn)
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    e = stueck.setze_ort(conn, 1, szene=1, ort="  piazza ")
    assert e.ok and e.aenderung_id is None
    assert len(repo.stueck_aenderungen(conn, 1)) == 1


def test_ort_markiert_eigene_und_erwaehnende_szene_nie_umschreiben(conn):
    s1 = _szene(conn, 1, volltext="Sala prove. ANNA: Ciao.")
    s2 = _szene(conn, 2, volltext="Wieder in der Sala prove.")
    s3 = _szene(conn, 3, volltext="Draussen.")
    stueck.setze_ort(conn, 1, szene=1, ort="Sala prove")
    e = stueck.setze_ort(conn, 1, szene=1, ort="Sala riunioni")
    markiert = {v["szene_id"] for v in repo.offene_veraltet(conn, 1)}
    assert markiert == {s1, s2}
    assert len(e.veraltet) == 2
    assert repo.hole_szene(conn, s1)["volltext"] == "Sala prove. ANNA: Ciao."  # nie still umgeschrieben
    assert s3 not in markiert


def test_quelle_script_markiert_die_eigene_szene_nicht(conn):
    s1 = _szene(conn, 1, volltext="Piazza")
    stueck.setze_ort(conn, 1, szene=1, ort="Piazza", quelle=stueck.QUELLE_SCRIPT)
    assert repo.offene_veraltet(conn, 1) == []


def test_busy_gate(conn, monkeypatch):
    from interview_theater import ueberarbeitung

    _szene(conn)
    monkeypatch.setattr(ueberarbeitung, "laeuft", lambda chat_id: True)
    e = stueck.setze_ort(conn, 1, szene=1, ort="Piazza")
    assert not e.ok and e.fehler == "beschaeftigt"
    assert repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 1))["ort"] is None
    assert stueck.setze_ort(conn, 1, szene=1, ort="Piazza", quelle=stueck.QUELLE_SCRIPT).ok


def test_unbekannte_szene(conn):
    assert stueck.setze_ort(conn, 1, szene=9, ort="x").fehler == "unbekannte_szene"


def test_figur_hinzu_legt_an_und_besetzt_mit_rolle(conn):
    sid = _szene(conn, volltext="ANNA: Ciao.")
    e = stueck.figur_hinzu(conn, 1, name="Chicca", szene=1, rolle="(Cover)")
    assert e.ok
    assert repo.hole_figur(conn, 1, "Chicca") is not None
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["wer"] == "Chicca (Cover)"
    assert {v["szene_id"] for v in repo.offene_veraltet(conn, 1)} == {sid}


def test_figur_hinzu_ueberschreibt_keine_beschreibung(conn):
    repo.setze_figur(conn, 1, "Anna", "Studentin")
    _szene(conn)
    stueck.figur_hinzu(conn, 1, name="anna", szene=1)
    assert repo.hole_figur(conn, 1, "Anna")["beschreibung"] == "Studentin"


def test_figur_aus_szene(conn):
    sid = _szene(conn)
    stueck.figur_hinzu(conn, 1, name="Anna", szene=1)
    stueck.figur_aus_szene(conn, 1, name="Anna", szene=1)
    assert repo.besetzung(conn, sid) == []


def test_setze_besetzung_nur_bekannte_figuren(conn):
    _szene(conn)
    repo.setze_figur(conn, 1, "Anna", "")
    assert stueck.setze_besetzung(conn, 1, szene=1, namen=["Anna", "Niemand"]).fehler == "unbekannte_figur"
    assert stueck.setze_besetzung(conn, 1, szene=1, namen=["Anna"], zusatz="il pubblico").ok


def test_setze_rahmen_markiert_kopf(conn):
    repo.setze_arbeitsstand(conn, 1, "stage_kopf", "SETUP: Sala prove")
    stueck.setze_rahmen(conn, 1, rahmen="Sala prove")
    stueck.setze_rahmen(conn, 1, rahmen="Sala riunioni")
    assert [v["ansicht"] for v in repo.offene_veraltet(conn, 1)] == ["kopf"]


def test_erster_rahmen_markiert_kopf_nicht(conn):
    repo.setze_arbeitsstand(conn, 1, "stage_kopf", "SETUP: irgendwas")
    assert stueck.setze_rahmen(conn, 1, rahmen="Sala prove").ok
    assert repo.offene_veraltet(conn, 1) == []


def test_ergebnis_ist_json_tauglich(conn):
    _szene(conn)
    json.dumps(stueck.setze_ort(conn, 1, szene=1, ort="x").als_dict())


def test_unbekannte_szene_hat_einen_satz_nicht_nur_den_code(conn):
    e = stueck.setze_ort(conn, 1, szene=99, ort="X")
    assert not e.ok
    assert e.warnungen and "unbekannte_szene" not in stueck.meldung(e)
    assert stueck.meldung(e) == e.warnungen[0]


def test_meldung_ohne_warnung_zeigt_nie_den_rohen_code(conn):
    e = stueck.Ergebnis(ok=False, fehler="ungueltig")
    assert "ungueltig" not in stueck.meldung(e)


def test_szene_ohne_nummer_ueber_szene_id(conn):
    """Review 13: die Weboberflaeche adressiert Szenen per id -- auch solche
    ohne Nummer (noch nicht eingereiht)."""
    from interview_theater import web_schreiben

    repo.setze_figur(conn, 1, "Mira", "")
    sid = repo.lege_szene_an(conn, 1, None, "Ohne Nummer", None, None)
    assert repo.hole_szene(conn, sid)["nummer"] is None

    web_schreiben.wende_an(conn, 1, "szene_ort", "Hinterhof", sid)
    assert repo.hole_szene(conn, sid)["ort"] == "Hinterhof"

    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    web_schreiben.wende_an(conn, 1, "szene_figuren", [str(figur_id)], sid)
    assert [f["name"] for f in repo.szene_figuren(conn, sid)] == ["Mira"]


def test_szene_id_einer_fremden_gruppe_wird_abgelehnt(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Zwei")
    fremd = repo.stelle_szene_sicher(conn, 2, 1)
    e = stueck.setze_ort(conn, 1, szene_id=fremd, ort="X")
    assert not e.ok and e.fehler == "unbekannte_szene"
