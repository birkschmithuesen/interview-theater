"""Kanban-Karte t_9dd91550, Annahme A3: staerbt ``web_daten.web_chataenderungen``
("geaendert") hinter mehr als ``CHAT_GRENZE`` (200) gleichzeitigen Aenderungen
derselben Gruppe eine spaete Zeile aus? Fuer den Vorfall selbst widerlegt
(G1/Interview 4 hatte nur rund 25 geaenderte Zeilen im fraglichen Fenster --
siehe Karte), aber die Karte verlangt ausdruecklich einen Test genau dafuer,
weil die Paginierung (``ORDER BY aenderung ASC LIMIT`` + ``stand = max(...)``)
sonst ungeprueft blieb.

Befund: nichts geht verloren, nur spaeter. Ueberschreitet die Zahl der
geaenderten Zeilen ``CHAT_GRENZE``, liefert ein Poll die AELTESTEN
``CHAT_GRENZE`` Aenderungen und ruckt ``stand`` nur bis zur letzten davon vor
-- der naechste Poll (``seit=stand``) holt den Rest. Kein Poll laesst eine
Zeile endgueltig aus (anders als Karte t_9dd91550s eigentlicher Fund in
``ersetze()``, siehe ``tests/test_web_chat_ersetze_fehlende_blase.py``)."""

from interview_theater import db, repo, web_daten

WEB = repo.WEB_CHAT_ID_BASIS


def _conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, WEB, "gruppe1", "Webgruppe")
    repo.setze_gruppe_kanal(c, WEB, "web")
    return c


def test_mehr_als_chat_grenze_aenderungen_gehen_ueber_zwei_polls_vollstaendig_raus(tmp_path):
    conn = _conn(tmp_path)
    anzahl = web_daten.CHAT_GRENZE + 1
    ids = [
        repo.lege_web_post_an(conn, WEB, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT, text=f"x{i}")
        for i in range(anzahl)
    ]
    # Jede Zeile einmal aendern -- derselbe Weg wie die wechselnden
    # Arbeitszeilen (``WebKanal.aendere_text``), nur hier direkt ueber
    # ``repo``, damit die Reihenfolge der Aenderung feststeht.
    for post_id in ids:
        assert repo.aendere_web_text(conn, WEB, post_id, f"geaendert-{post_id}")

    erste_seite, erster_stand = web_daten.web_chataenderungen(conn, WEB, seit=0)
    assert len(erste_seite) == web_daten.CHAT_GRENZE
    assert erster_stand < anzahl  # noch nicht alle Aenderungen gesehen

    zweite_seite, zweiter_stand = web_daten.web_chataenderungen(conn, WEB, seit=erster_stand)
    assert len(zweite_seite) == anzahl - web_daten.CHAT_GRENZE
    assert zweiter_stand > erster_stand

    # Jede id genau einmal ueber beide Seiten -- keine Luecke, keine Dublette.
    gesehen = [z["id"] for z in erste_seite] + [z["id"] for z in zweite_seite]
    assert sorted(gesehen) == sorted(ids)
    for z in erste_seite + zweite_seite:
        assert z["text"] == f"geaendert-{z['id']}"

    # Ein dritter Poll mit dem letzten Stand bringt nichts mehr -- alles
    # schon ausgeliefert.
    dritte_seite, dritter_stand = web_daten.web_chataenderungen(conn, WEB, seit=zweiter_stand)
    assert dritte_seite == []
    assert dritter_stand == zweiter_stand
