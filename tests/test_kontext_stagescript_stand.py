"""Padua Quickfix (Birk 08.10.2026, Punkt 2): der Gespraechs-Bot kennt den
Stand des Stage Scripts je Szene (Phase 7, Kartenprofil) -- geschrieben /
in Arbeit / gespeichert / offen, plus gesammelte Notizen. Ohne diesen Block
riet der Bot ("still being written"), statt den Stand zu lesen -- Befund
Tester 08.10.2026, chat_id 7000000000099, web_post 2207-2209: eine Frage
("wo kann ich szene 2 sehen? ist sie fertig?") traf auf eine Szene, die
3 Sekunden zuvor als fertig gemeldet worden war, und bekam "Not yet: scene
2 of 3 is still being written" -- obwohl sie bereits im Script-Tab stand."""

import json

from interview_theater import kontext, phasen, repo, stagescript

from test_szenenkarte import _lage, padua  # noqa: F401


def _karten(conn, szenen=2, typ="instructions"):
    """Wie ``test_stagescript._karten``, nur mit einstellbarer Szenenzahl --
    eigene Fassung statt den geteilten Testhelfer anzufassen, den eine
    parallele Sitzung gerade bearbeitet (NICHT anfassen)."""
    ids = _lage(conn, szenen)
    for n, sid in enumerate(ids, start=1):
        repo.setze_szenenkarte(conn, sid, json.dumps({
            "typ": typ, "worum": f"Worum {n}", "ort": "Bar", "wer": "Anna",
            "punkte": [f"Punkt {n}"], "zitate": [], "fragen": []}))
        repo.setze_szenenkarte_bestaetigt(conn, sid)
    phasen.setze(conn, 1, 7, "befehl")
    return ids


def _ausloeser(conn, chat_id, text):
    repo.merke_nachricht(conn, chat_id, 1, "Ada", 0, "text", text, repo._jetzt())
    return [repo.hole_nachricht(conn, chat_id, 1)]


def test_leer_ausserhalb_phase_7(conn, padua):
    _karten(conn)
    phasen.setze(conn, 1, 4, "test")
    assert kontext._baue_stagescript_stand(conn, 1) == ""


def test_leer_ohne_karten_profil(conn, padua, monkeypatch):
    from interview_theater import workshop

    _karten(conn)
    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: False)
    assert kontext._baue_stagescript_stand(conn, 1) == ""


def test_zeigt_offen_geschrieben_und_gespeichert(conn, padua):
    ids = _karten(conn, szenen=3)
    repo.setze_stagescript(conn, ids[0], "EMMA: Home.", None)
    repo.setze_szene_fertig(conn, ids[0], True)
    repo.setze_stagescript(conn, ids[1], "EMMA: Still here.", None)

    text = kontext._baue_stagescript_stand(conn, 1)

    zeilen = text.splitlines()
    assert any("1" in z and "saved" in z.lower() for z in zeilen)
    assert any("2" in z and ("written" in z.lower() or "ready" in z.lower()) for z in zeilen)
    assert any("3" in z and ("open" in z.lower() or "not started" in z.lower()) for z in zeilen)


def test_zeigt_in_arbeit_fuer_die_laufende_szene(conn, padua):
    _karten(conn, szenen=2)
    sperre = stagescript._sperre_fuer(1)
    sperre.acquire()
    try:
        text = kontext._baue_stagescript_stand(conn, 1)
    finally:
        sperre.release()

    zeilen = text.splitlines()
    assert any("1" in z and "writ" in z.lower() for z in zeilen)


def test_zeigt_gesammelte_notizen(conn, padua):
    ids = _karten(conn, szenen=2)
    repo.merke_stagescript_notiz(conn, 1, ids[1], "needs a dialog")

    text = kontext._baue_stagescript_stand(conn, 1)

    zeilen = [z for z in text.splitlines() if "2" in z]
    assert zeilen and "needs a dialog" in zeilen[0]


def test_block_steht_im_vollen_nutzertext(conn, einst, padua):
    ids = _karten(conn, szenen=2)
    repo.setze_stagescript(conn, ids[0], "EMMA: Home.", None)
    repo.setze_szene_fertig(conn, ids[0], True)
    ausloeser = _ausloeser(conn, 1, "wo kann ich szene 2 sehen?")

    text = kontext.baue(conn, 1, ausloeser, einst)

    zeilen = [z for z in text.splitlines() if "1" in z and "saved" in z.lower()]
    assert zeilen


def test_mutationsprobe_block_fehlt_ohne_eintrag_in_bloecke(conn, einst, padua, monkeypatch):
    """Mutationsprobe: ohne den Eintrag in ``_bloecke`` erscheint der Block
    nie im vollen Nutzertext, egal was ``_baue_stagescript_stand`` liefert --
    dieser Test waere dann rot."""
    monkeypatch.setattr(kontext, "_baue_stagescript_stand",
                        lambda *a, **k: "EINDEUTIGE-MARKE-PUNKT-2")
    ids = _karten(conn, szenen=1)
    ausloeser = _ausloeser(conn, 1, "status?")

    text = kontext.baue(conn, 1, ausloeser, einst)

    assert "EINDEUTIGE-MARKE-PUNKT-2" in text
