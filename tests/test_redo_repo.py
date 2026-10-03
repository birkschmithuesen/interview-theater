"""Die Ablage des Redo -- der Spiegel von ``tests/test_ruecknahme_repo.py``
(Padua Phasen TEIL 2, Task 1, 04.10.2026).

Ein Redo stellt genau das wieder her, was ein Undo zurueckgenommen hat --
kein Nachbau je Art, sondern dieselbe Diff-Maschinerie wie beim Undo, nur in
der anderen Richtung. Kein Netz, kein Modell -- die Schicht darunter ist
SQLite.
"""

from interview_theater import repo, ruecknahme


def _schnappschuss(conn, arten):
    return repo.schnappschuss(conn, 1, ruecknahme.plan(arten))


def _lauf_um(conn, arten, tat):
    """Nimmt den Schnappschuss um ``tat`` herum und legt den Lauf an -- wie in
    ``tests/test_ruecknahme_repo.py::_lauf_um``."""
    vorher = _schnappschuss(conn, arten)
    tat()
    nachher = _schnappschuss(conn, arten)
    return repo.lege_erkenner_lauf_an(
        conn, 1, "Probe", ruecknahme.schritte(vorher, nachher),
    )


def _undo(conn, lauf_id):
    return repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(),
        ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
    )


def _redo(conn, lauf_id):
    return repo.stelle_erkenner_lauf_wieder_her(
        conn, lauf_id, ruecknahme.verweise(),
        ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
    )


def test_redo_stellt_ein_geaendertes_feld_wieder_her(conn):
    """``geaendert`` (arbeitsstand.fragen): leer -> "11 Fragen", undo -> wieder
    leer, redo -> wieder "11 Fragen"."""
    lauf_id = _lauf_um(
        conn, ("fragen_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "fragen", "11 Fragen"),
    )
    assert _undo(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.hole_arbeitsstand(conn, 1)["fragen"] is None

    assert _redo(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == "11 Fragen"


def test_redo_stellt_eine_weich_entfernte_figur_wieder_her(conn):
    """``angelegt`` + ``weich`` (figur): undo entfernt weich (entfernt_am
    gesetzt), redo macht sie wieder sichtbar -- Felder bleiben unveraendert."""
    lauf_id = _lauf_um(
        conn, ("figur_setzen",),
        lambda: repo.setze_figur(conn, 1, "Mira", "laut"),
    )
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]

    assert _undo(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.hole_figur_nach_id(conn, figur_id)["entfernt_am"] is not None

    assert _redo(conn, lauf_id) == repo.ZURUECK_OK
    wieder = repo.hole_figur_nach_id(conn, figur_id)
    assert wieder["entfernt_am"] is None
    assert wieder["beschreibung"] == "laut"


def test_redo_loescht_eine_vom_undo_wieder_eingefuegte_verknuepfung(conn):
    """``geloescht`` (szene_figur): die Besetzung ist vorher da, nachher weg
    (``repo.setze_szene_figuren``). Undo fuegt sie wieder ein, Redo entfernt
    sie wieder."""
    repo.setze_figur(conn, 1, "Mira", "laut")
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])

    lauf_id = _lauf_um(
        conn, ("szene_planen",),
        lambda: repo.setze_szene_figuren(conn, 1, szene_id, []),
    )
    assert _undo(conn, lauf_id) == repo.ZURUECK_OK
    assert {f["id"] for f in repo.szene_figuren(conn, szene_id)} == {figur_id}

    assert _redo(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.szene_figuren(conn, szene_id) == []


def test_redo_ist_idempotent_und_braucht_ein_vorheriges_undo(conn):
    """Zweimal hintereinander -> der zweite Aufruf ``ZURUECK_SCHON``. Ohne
    vorheriges Undo (Vorbedingung ``zurueckgenommen_am IS NOT NULL`` fehlt)
    -> ebenfalls ``ZURUECK_SCHON``.

    Zwei Schichten sichern das ab, wie beim Undo-Vorbild: die Vorbedingung
    ganz oben (``lauf["wiederhergestellt_am"] is not None``) und das
    bedingte UPDATE beim Stempeln. Fuer EINEN sequentiellen Testlauf greift
    immer schon die obere Schicht -- sie liest den Lauf frisch aus der DB und
    faengt den zweiten Aufruf ab, bevor das UPDATE ueberhaupt erreicht wird
    (genauso beim Vorbild ``test_ruecknahme_wirkt_nur_einmal``, empirisch
    geprueft: dort macht das Weglassen von ``AND zurueckgenommen_am IS NULL``
    im UPDATE diesen Test ebenfalls NICHT rot, aus demselben Grund). Das
    bedingte UPDATE bleibt trotzdem stehen -- es ist die Sperre gegen zwei
    GLEICHZEITIGE Auftraege, die beide die obere Pruefung passieren, bevor
    einer von beiden stempelt; das kann ein einzelner, sequentieller Test
    nicht nachstellen.

    Mutation, die DIESEN Test tatsaechlich rot macht (nachgemessen): die
    Bedingung ``lauf["wiederhergestellt_am"] is not None`` aus der oberen
    Pruefung entfernen."""
    lauf_id = _lauf_um(
        conn, ("fragen_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "fragen", "11 Fragen"),
    )
    # Noch nie zurueckgenommen -- Redo hat nichts zu tun.
    assert _redo(conn, lauf_id) == repo.ZURUECK_SCHON

    assert _undo(conn, lauf_id) == repo.ZURUECK_OK
    assert _redo(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == "11 Fragen"

    repo.setze_arbeitsstand(conn, 1, "fragen", "Noch mehr Fragen")
    assert _redo(conn, lauf_id) == repo.ZURUECK_SCHON
    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == "Noch mehr Fragen"


def test_redo_verweigert_wenn_der_wert_seitdem_von_hand_geaendert_wurde(conn):
    """Nach dem Undo wird der Wert von Hand nochmal geaendert -- Redo liefert
    ``ZURUECK_GEAENDERT``, der Wert bleibt unberuehrt."""
    lauf_id = _lauf_um(
        conn, ("fragen_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "fragen", "11 Fragen"),
    )
    assert _undo(conn, lauf_id) == repo.ZURUECK_OK
    repo.setze_arbeitsstand(conn, 1, "fragen", "Von Hand")

    assert _redo(conn, lauf_id) == repo.ZURUECK_GEAENDERT
    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == "Von Hand"
    assert repo.hole_erkenner_lauf(conn, lauf_id)["wiederhergestellt_am"] is None


def test_letzte_knopf_nachricht_id(conn):
    """Leere Gruppe -> None; zwei Knoepfe unter zwei verschiedenen
    message_ids -> liefert die zuletzt angelegte."""
    assert repo.letzte_knopf_nachricht_id(conn, 1) is None

    erster = repo.lege_knopf_an(conn, 1, "speichern", "rahmen|Bahnhof")
    repo.merke_knopf_nachricht(conn, [erster], 500)
    assert repo.letzte_knopf_nachricht_id(conn, 1) == 500

    zweiter = repo.lege_knopf_an(conn, 1, "undo", "7")
    repo.merke_knopf_nachricht(conn, [zweiter], 501)
    assert repo.letzte_knopf_nachricht_id(conn, 1) == 501
