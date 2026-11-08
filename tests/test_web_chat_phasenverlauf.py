"""Kanban-Karte t_60d72fd6: der Web-Chat zeigt nur den Verlauf der AKTUELLEN
Phase -- frühere Besuche DERSELBEN Phase inklusive, aber nicht die Phasen
dazwischen.

Die Phase je Nachricht wird ohne eigene DB-Spalte abgeleitet: eine Bot-
Nachricht, die mit ``▶️ Phase N`` beginnt (``phasentexte._KOPF_EINTRITT``,
sprachunabhängiges Präfix), setzt die massgebliche Phase ab dieser Zeile neu.
Nachrichten vor der ersten solchen Zeile zählen als Phase 1.
"""

from interview_theater import db, repo, web_daten

CHAT = 7_000_000_000_777


def _db(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    conn.commit()
    conn.close()
    return pfad


def _eintritt(schreibend, nummer: int) -> int:
    text = f"▶️ Phase {nummer} von 7 · Testphase"
    return repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                 repo.WEB_TYP_TEXT, text=text)


def _text(schreibend, text: str) -> int:
    return repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                 repo.WEB_TYP_TEXT, text=text)


def test_nur_die_aktuelle_phase_erscheint_im_verlauf(tmp_path):
    pfad = _db(tmp_path)
    schreibend = db.verbinde(pfad)
    vor_eins = _text(schreibend, "noch vor jeder Eintrittsnachricht")
    _eintritt(schreibend, 2)
    zwei = _text(schreibend, "aus Phase 2")
    _eintritt(schreibend, 3)
    drei = _text(schreibend, "aus Phase 3")
    repo.setze_phase(schreibend, CHAT, 3)
    schreibend.commit()
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()

    ids = [z["id"] for z in verlauf]
    assert vor_eins not in ids
    assert zwei not in ids
    assert drei in ids


def test_nachrichten_vor_der_ersten_eintrittsnachricht_zaehlen_als_phase_eins(tmp_path):
    pfad = _db(tmp_path)
    schreibend = db.verbinde(pfad)
    erste = _text(schreibend, "Begruessung")
    schreibend.commit()
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()

    assert [z["id"] for z in verlauf] == [erste]


def test_ein_rueckkehrender_besuch_derselben_phase_zeigt_beide_abschnitte(tmp_path):
    """p2 -> p3 -> zurueck zu p2: beide p2-Abschnitte sichtbar, p3 nicht."""
    pfad = _db(tmp_path)
    schreibend = db.verbinde(pfad)
    _eintritt(schreibend, 2)
    erster_p2 = _text(schreibend, "erster Besuch in Phase 2")
    _eintritt(schreibend, 3)
    p3 = _text(schreibend, "aus Phase 3")
    zweiter_eintritt_p2 = _eintritt(schreibend, 2)
    zweiter_p2 = _text(schreibend, "zweiter Besuch in Phase 2")
    repo.setze_phase(schreibend, CHAT, 2)
    schreibend.commit()
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()

    ids = [z["id"] for z in verlauf]
    assert erster_p2 in ids
    assert zweiter_eintritt_p2 in ids
    assert zweiter_p2 in ids
    assert p3 not in ids


def test_ohne_gesetzte_phase_bleibt_alles_wie_bisher_phase_eins(tmp_path):
    """Keine arbeitsstand-Zeile (frische Gruppe): Vorgabe ist Phase 1, und
    ohne jede Eintrittsnachricht zaehlt alles dazu -- Rueckfallpruefung
    fuer die bisherigen, phasenlosen Tests in test_web_chat.py."""
    pfad = _db(tmp_path)
    schreibend = db.verbinde(pfad)
    eins = _text(schreibend, "a")
    zwei = _text(schreibend, "b")
    schreibend.commit()
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()

    assert [z["id"] for z in verlauf] == [eins, zwei]
