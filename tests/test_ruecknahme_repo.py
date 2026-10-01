"""Die Ablage der Ruecknahme: Schema, Schnappschuss, Speichern, die eine
Transaktion (Karte U, 01.10.2026).

Kein Netz, kein Modell -- die Schicht darunter ist SQLite.
"""

import json

import pytest

from interview_theater import db, repo


def test_beide_tabellen_stehen_im_schema(conn):
    """Additiv per CREATE TABLE IF NOT EXISTS, wie jede Tabelle hier."""
    vorhandene = {
        zeile[0]
        for zeile in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"erkenner_lauf", "erkenner_lauf_schritt"} <= vorhandene


def test_beide_tabellen_tragen_chat_id_und_stehen_in_der_loeschzusage(conn):
    """Jede Tabelle ausser bot_zustand hat chat_id -- daran haengt
    db.loesche_gruppe (AGENTS.md)."""
    for tabelle in ("erkenner_lauf", "erkenner_lauf_schritt"):
        spalten = {z[1] for z in conn.execute(f"PRAGMA table_info({tabelle})")}
        assert "chat_id" in spalten, tabelle
        assert tabelle in db.TABELLEN_MIT_CHAT_ID, tabelle


def test_loeschen_einer_gruppe_nimmt_die_laeufe_mit(conn):
    conn.execute(
        "INSERT INTO erkenner_lauf (chat_id, meldung, erstellt_am) "
        "VALUES (1, 'Kernthema: X', '2026-10-01T10:00:00')"
    )
    lauf_id = conn.execute("SELECT id FROM erkenner_lauf").fetchone()[0]
    conn.execute(
        "INSERT INTO erkenner_lauf_schritt "
        "(chat_id, lauf_id, tabelle, schluessel, art, vorher, nachher, erstellt_am) "
        "VALUES (1, ?, 'arbeitsstand', ?, 'geaendert', ?, ?, '2026-10-01T10:00:00')",
        (lauf_id, json.dumps({"chat_id": 1}), json.dumps({"kernthema": None}),
         json.dumps({"kernthema": "X"})),
    )
    conn.commit()

    db.loesche_gruppe(conn, 1)

    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM erkenner_lauf_schritt"
    ).fetchone()[0] == 0


def test_eine_altdatenbank_ohne_die_tabellen_laeuft_durch(tmp_path):
    """db.initialisiere ist additiv: eine Datenbank, die vor dieser Aenderung
    entstanden ist, bekommt die Tabellen beim Start -- ohne
    SCHEMA_VERSION-Schritt, weil nichts umgedeutet wird."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    alt.executescript(db.SCHEMA)
    alt.execute("DROP TABLE erkenner_lauf")
    alt.execute("DROP TABLE erkenner_lauf_schritt")
    # Eine echte Altdatenbank hat die Phasennummern-Migration laengst
    # durchlaufen (jede Betriebsdatenbank seit dem 06.09.2026 steht auf
    # SCHEMA_VERSION); nur die beiden neuen Tabellen fehlen ihr noch.
    alt.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION}")
    alt.commit()
    version_vorher = alt.execute("PRAGMA user_version").fetchone()[0]
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)

    vorhandene = {
        z[0] for z in neu.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"erkenner_lauf", "erkenner_lauf_schritt"} <= vorhandene
    assert neu.execute("PRAGMA user_version").fetchone()[0] == version_vorher
    assert db.SCHEMA_VERSION == 3, "keine Erhoehung: es wird nichts umgedeutet"


from interview_theater import ruecknahme


def _schnappschuss(conn, arten=("kernthema_setzen",)):
    return repo.schnappschuss(conn, 1, ruecknahme.plan(arten))


def test_schnappschuss_liefert_je_tabelle_die_zeilen_nach_schluessel(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_figur(conn, 1, "Mira", "laut")

    stand = _schnappschuss(conn, ("kernthema_setzen", "figur_setzen"))

    assert set(stand) == set(ruecknahme.VERFOLGT)
    assert stand["arbeitsstand"][json.dumps({"chat_id": 1}, sort_keys=True)][
        "kernthema"] == "Ankommen"
    figur = repo.hole_figur(conn, 1, "Mira")
    schluessel = json.dumps({"id": figur["id"]}, sort_keys=True)
    assert stand["figur"][schluessel]["beschreibung"] == "laut"
    assert "geaendert_am" not in stand["figur"][schluessel], "Zeitstempel bleiben aussen"


def test_schnappschuss_sieht_nur_die_eigene_gruppe(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    repo.setze_arbeitsstand(conn, 2, "kernthema", "Fremd")
    repo.setze_figur(conn, 2, "Fremdfigur", "x")

    stand = _schnappschuss(conn, ("kernthema_setzen", "figur_setzen"))

    assert stand["arbeitsstand"] == {}
    assert stand["figur"] == {}


def test_schnappschuss_nimmt_material_nur_mit_korrektur(conn):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "d", "sprache", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "wir haben gepoekt")

    ohne = _schnappschuss(conn, ("kernthema_setzen",))
    mit = _schnappschuss(conn, ("transkript_korrigieren",))

    assert "aufnahme" not in ohne
    schluessel = json.dumps({"id": aufnahme_id}, sort_keys=True)
    assert mit["aufnahme"][schluessel] == {"transkript": "wir haben gepoekt"}


def test_schnappschuss_nimmt_auch_weich_entfernte_zeilen_mit(conn):
    """Sonst saehe ein Undo eine im Lauf weich entfernte Figur als
    "verschwunden" und fuegte sie als geloescht-Schritt neu ein, statt
    ``entfernt_am`` zurueckzunehmen."""
    repo.setze_figur(conn, 1, "Mira", "laut")
    repo.entferne_figur(conn, 1, "Mira")

    stand = _schnappschuss(conn, ("figur_setzen",))

    assert len(stand["figur"]) == 1
    (zeile,) = stand["figur"].values()
    assert zeile["entfernt_am"] is not None


def test_lege_erkenner_lauf_an_speichert_meldung_und_schritte(conn):
    schritte = [
        {"tabelle": "arbeitsstand", "schluessel": {"chat_id": 1},
         "art": "geaendert", "vorher": {"kernthema": None},
         "nachher": {"kernthema": "Ankommen"}},
    ]
    lauf_id = repo.lege_erkenner_lauf_an(conn, 1, "Kernthema: Ankommen", schritte)

    lauf = repo.hole_erkenner_lauf(conn, lauf_id)
    assert lauf["chat_id"] == 1
    assert lauf["meldung"] == "Kernthema: Ankommen"
    assert lauf["message_id"] is None
    assert lauf["zurueckgenommen_am"] is None

    (gespeichert,) = repo.erkenner_lauf_schritte(conn, lauf_id)
    assert gespeichert["tabelle"] == "arbeitsstand"
    assert json.loads(gespeichert["schluessel"]) == {"chat_id": 1}
    assert json.loads(gespeichert["nachher"]) == {"kernthema": "Ankommen"}


def test_kein_lauf_ohne_schritte_und_keiner_ohne_meldung(conn):
    """Ein Knopf, der nichts zurueckzunehmen hat, waere ein Knopf ohne
    Wirkung -- und eine Ruecknahme ohne Zeilen koennte nicht sagen, WAS sie
    zurueckgenommen hat."""
    assert repo.lege_erkenner_lauf_an(conn, 1, "Kernthema: X", []) is None
    assert repo.lege_erkenner_lauf_an(conn, 1, "", [
        {"tabelle": "arbeitsstand", "schluessel": {"chat_id": 1},
         "art": "geaendert", "vorher": {}, "nachher": {"kernthema": "X"}},
    ]) is None
    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0


def test_merke_erkenner_lauf_nachricht(conn):
    lauf_id = repo.lege_erkenner_lauf_an(conn, 1, "Kernthema: X", [
        {"tabelle": "arbeitsstand", "schluessel": {"chat_id": 1},
         "art": "geaendert", "vorher": {}, "nachher": {"kernthema": "X"}},
    ])
    repo.merke_erkenner_lauf_nachricht(conn, lauf_id, 4242)
    assert repo.hole_erkenner_lauf(conn, lauf_id)["message_id"] == 4242


def test_offene_knoepfe_der_nachricht(conn):
    a = repo.lege_knopf_an(conn, 1, "speichern", "rahmen|Bahnhof")
    b = repo.lege_knopf_an(conn, 1, "undo", "7")
    fremd = repo.lege_knopf_an(conn, 1, "speichern", "anderswo")
    repo.merke_knopf_nachricht(conn, [a, b], 500)
    repo.merke_knopf_nachricht(conn, [fremd], 501)

    alle = repo.offene_knoepfe_der_nachricht(conn, 1, 500)
    assert {k["id"] for k in alle} == {a, b}
    nur_undo = repo.offene_knoepfe_der_nachricht(conn, 1, 500, "undo")
    assert [k["id"] for k in nur_undo] == [b]

    repo.verfallen_lassen(conn, [b])
    assert repo.offene_knoepfe_der_nachricht(conn, 1, 500, "undo") == []


def _nimm_zurueck(conn, lauf_id):
    return repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(),
        ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
    )


def _lauf_um(conn, arten, tat):
    """Nimmt den Schnappschuss um ``tat`` herum und legt den Lauf an -- genau
    der Ablauf, den ``erkenner.laufe`` in Aufgabe 7 fahren wird."""
    vorher = repo.schnappschuss(conn, 1, ruecknahme.plan(arten))
    tat()
    nachher = repo.schnappschuss(conn, 1, ruecknahme.plan(arten))
    return repo.lege_erkenner_lauf_an(
        conn, 1, "Probe",
        ruecknahme.schritte(vorher, nachher),
    )


def test_ruecknahme_stellt_ein_feld_wieder_her(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"


def test_ruecknahme_wirkt_nur_einmal(conn):
    """Die zweite Idempotenz-Sperre neben ``beanspruche_knopf``: ein bedingtes
    UPDATE in derselben Transaktion. Zwei direkte Aufrufe -- der zweite aendert
    nichts.

    Mutation, die diesen Test rot macht: ``AND zurueckgenommen_am IS NULL``
    im UPDATE weglassen."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )
    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK

    repo.setze_arbeitsstand(conn, 1, "kernthema", "Spaeter")
    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_SCHON
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Spaeter"


def test_ruecknahme_verweigert_wenn_der_wert_seitdem_anders_ist(conn):
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Von Hand")

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_GEAENDERT
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Von Hand"
    assert repo.hole_erkenner_lauf(conn, lauf_id)["zurueckgenommen_am"] is None


def test_ruecknahme_ist_alles_oder_nichts(conn):
    """Zwei Schritte, einer davon seitdem geaendert: NICHTS wird angefasst.

    Mutation, die diesen Test rot macht: je Schritt einzeln pruefen und
    committen statt erst alle pruefen, dann alle anwenden."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")

    def tat():
        repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu")
        repo.setze_arbeitsstand(conn, 1, "rahmen", "Bahnhof")

    lauf_id = _lauf_um(conn, ("kernthema_setzen", "rahmen_setzen"), tat)
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Schulhof")

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_GEAENDERT
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["kernthema"] == "Neu", "kein halber Rueckschritt"
    assert stand["rahmen"] == "Schulhof"


def test_ruecknahme_entfernt_eine_neue_figur_weich(conn):
    """N3: weich entfernen, nicht loeschen -- und geprueft wird ueber den
    LESER, nicht ueber rohes SQL.

    Mutation: ``entfernt_am`` nicht setzen -- ``repo.figuren`` liefert die
    Figur weiter."""
    lauf_id = _lauf_um(
        conn, ("figur_setzen",),
        lambda: repo.setze_figur(conn, 1, "Mira", "laut"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert [f["name"] for f in repo.figuren(conn, 1)] == []
    assert conn.execute("SELECT count(*) FROM figur").fetchone()[0] == 1, (
        "die Zeile bleibt stehen -- weich, nicht hart"
    )


def test_ruecknahme_nimmt_ein_weiches_entfernen_zurueck(conn):
    repo.setze_figur(conn, 1, "Mira", "laut")
    lauf_id = _lauf_um(
        conn, ("figur_setzen",),
        lambda: repo.entferne_figur(conn, 1, "Mira"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Mira"]


def test_ruecknahme_loescht_eine_neue_verknuepfung_hart(conn):
    """``szene_figur`` hat kein ``entfernt_am`` -- eine im Lauf entstandene
    Verknuepfung wird geloescht, genau wie ``setze_szene_figuren`` es tut."""
    repo.setze_figur(conn, 1, "Mira", "laut")
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    lauf_id = _lauf_um(
        conn, ("szene_planen",),
        lambda: repo.setze_szene_figuren(conn, 1, szene_id, [figur_id]),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert repo.szene_figuren(conn, szene_id) == []


def test_ruecknahme_fuegt_eine_hart_geloeschte_verknuepfung_wieder_ein(conn):
    repo.setze_figur(conn, 1, "Mira", "laut")
    repo.setze_figur(conn, 1, "Pola", "still")
    mira = repo.hole_figur(conn, 1, "Mira")["id"]
    pola = repo.hole_figur(conn, 1, "Pola")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szene_figuren(conn, 1, szene_id, [mira, pola])

    lauf_id = _lauf_um(
        conn, ("szene_planen",),
        lambda: repo.setze_szene_figuren(conn, 1, szene_id, [mira]),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    assert {f["id"] for f in repo.szene_figuren(conn, szene_id)} == {mira, pola}


def test_ruecknahme_verweigert_bei_einer_waise(conn):
    """Zeigt jetzt etwas auf die im Lauf neu angelegte Figur, das nicht im
    Lauf entstanden ist, wird NICHTS geaendert -- sonst blieben Waisen in
    ``szene_figur``/``schaerfung``/``szenenfassung`` stehen.

    Mutation: die Waisen-Probe weglassen."""
    lauf_id = _lauf_um(
        conn, ("figur_setzen",),
        lambda: repo.setze_figur(conn, 1, "Mira", "laut"),
    )
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    # NACH dem Lauf besetzt: die Gruppe hat die Figur inzwischen eingebaut.
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_GEAENDERT
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Mira"]


def test_ruecknahme_leert_eine_neue_arbeitsstandzeile_statt_sie_zu_loeschen(conn):
    """``arbeitsstand`` hat genau eine Zeile je Gruppe und kein
    ``entfernt_am`` -- sie zu loeschen hiesse, die Phasen-Buchhaltung
    mitzureissen."""
    assert repo.hole_arbeitsstand(conn, 1) is None
    lauf_id = _lauf_um(
        conn, ("kernthema_setzen",),
        lambda: repo.setze_arbeitsstand(conn, 1, "kernthema", "Neu"),
    )

    assert _nimm_zurueck(conn, lauf_id) == repo.ZURUECK_OK
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand is not None, "die Zeile bleibt"
    assert stand["kernthema"] is None


def test_ruecknahme_eines_unbekannten_laufs_ist_kein_fehler(conn):
    assert _nimm_zurueck(conn, 999) == repo.ZURUECK_SCHON
