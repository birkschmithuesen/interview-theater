"""Kernbegriffe je Verdichtung: Zerlegung, Abgleich, Schema/Migration, Web.

Die Zuordnung ist deterministisch (interview_theater/begriffe.py) -- kein
Modellaufruf, keine Attrappe noetig. Alle Daten hier sind erfunden.
"""

import sqlite3

import pytest
from interview_theater import begriffe, db, repo, verdichter, web, web_daten


# ---------------------------------------------------------------- Zerlegung

@pytest.mark.parametrize(
    "freitext, erwartet",
    [
        ("Heimat, Arbeit, Angst", ["Heimat", "Arbeit", "Angst"]),
        ("Heimat\nArbeit\nAngst", ["Heimat", "Arbeit", "Angst"]),
        ("- Heimat\n- Arbeit", ["Heimat", "Arbeit"]),
        ("1. Heimat\n2. Arbeit", ["Heimat", "Arbeit"]),
        ("Heimat · Arbeit", ["Heimat", "Arbeit"]),
        ("Heimat; Arbeit/Beruf", ["Heimat", "Arbeit", "Beruf"]),
        ("", []),
        (None, []),
        ("   ", []),
    ],
)
def test_zerlege_erkennt_die_ueblichen_schreibweisen(freitext, erwartet):
    assert begriffe.zerlege(freitext) == erwartet


def test_zerlege_wirft_dubletten_weg_und_haelt_den_wortlaut():
    """Die Gruppe hat den Begriff geschrieben -- er steht so auf der Seite."""
    assert begriffe.zerlege("Heimat, heimat, HEIMAT, Arbeit") == ["Heimat", "Arbeit"]


# ------------------------------------------------------------------ Abgleich

def test_passt_trifft_flexionsformen_und_komposita():
    assert begriffe.passt("Liebe", "Sie erzaehlt vom Lieben und vom Streiten.")
    assert begriffe.passt("Liebe", "Eine Liebesgeschichte, sagt sie.")
    assert begriffe.passt("Arbeit", "Die Arbeitsstelle war weit weg.")


def test_passt_trifft_nicht_mitten_im_wort():
    """Deutsche Komposita haengen hinten an -- ein Treffer am Wortanfang ist
    ein Treffer, einer in der Wortmitte ein Zufall."""
    assert not begriffe.passt("Liebe", "Das war ganz nach ihrem Belieben.")


def test_passt_ist_unempfindlich_gegen_umlaute_und_grossschreibung():
    assert begriffe.passt("Zugehörigkeit", "zugehoerigkeit spielte eine rolle")
    assert begriffe.passt("Straße", "Auf der Strasse war niemand.")


def test_passt_ignoriert_sehr_kurze_begriffe():
    """\"Ich\" oder \"EU\" wuerden in jedem Fliesstext Zufallstreffer
    erzeugen."""
    assert not begriffe.passt("Ich", "Ich bin da. Ichthyologie sowieso.")


def test_passt_sucht_mehrwortige_begriffe_als_ganzes():
    assert begriffe.passt("Ankommen in Bremen", "Es ging ums Ankommen in Bremen.")
    assert not begriffe.passt("Ankommen in Bremen", "Ankommen war schwer, Bremen egal.")


def test_ordne_zu_haelt_die_reihenfolge_der_gruppe():
    liste = ["Heimat", "Arbeit", "Angst"]
    texte = ["Er hat Angst vor der Arbeit."]
    assert begriffe.ordne_zu(liste, texte) == ["Arbeit", "Angst"]


def test_texte_der_verdichtung_nimmt_keine_belegzitate():
    """Ein Zitat ist der Wortlaut eines Menschen -- kein Tag-Material."""
    texte = begriffe.texte_der_verdichtung(
        "Zusammenfassung ueber Arbeit",
        [{"thema": "Ein Thema", "kurz": "kurz", "beleg_zitat": "Heimat war ein Wort"}],
    )
    assert "Heimat war ein Wort" not in " ".join(texte)
    assert "Zusammenfassung ueber Arbeit" in texte


# ------------------------------------------------------------ Schema/Migration

@pytest.fixture
def frisch(tmp_path):
    c = db.verbinde(str(tmp_path / "neu.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_tabelle_verdichtung_begriff_existiert(frisch):
    spalten = {r[1] for r in frisch.execute("PRAGMA table_info(verdichtung_begriff)")}
    assert {"chat_id", "verdichtung_id", "begriff", "quelle", "erstellt_am"} <= spalten


def test_tabelle_steht_in_der_loeschliste():
    assert "verdichtung_begriff" in db.TABELLEN_MIT_CHAT_ID


def test_loesche_gruppe_raeumt_die_zuordnungen_mit(frisch):
    aufnahme_id = _interview(frisch)
    v = repo.speichere_verdichtung(frisch, 1, aufnahme_id, "Text", [])
    repo.setze_verdichtung_begriffe(frisch, 1, v, ["Heimat"])
    db.loesche_gruppe(frisch, 1)
    assert frisch.execute("SELECT count(*) FROM verdichtung_begriff").fetchone()[0] == 0


def test_migration_ruestet_die_tabelle_in_einer_alt_datenbank_nach(tmp_path):
    """Der Fall, der auf die gewachsene Live-Datenbank zutrifft: eine
    Datenbank ohne ``verdichtung_begriff``, mit Inhalt, die ``initialisiere``
    zum zweiten Mal sieht. Sie darf nichts verlieren und muss die Tabelle
    danach haben."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    repo.setze_arbeitsstand(c, 1, "begriffe", "Heimat, Arbeit")
    aufnahme_id = _interview(c)
    v = repo.speichere_verdichtung(c, 1, aufnahme_id, "Text", [])
    # Zurueck auf den Stand vor dieser Aenderung.
    c.execute("DROP TABLE verdichtung_begriff")
    c.commit()
    c.close()

    zweite = db.verbinde(pfad)
    db.initialisiere(zweite)
    assert zweite.execute(
        "SELECT count(*) FROM sqlite_master "
        "WHERE type='table' AND name='verdichtung_begriff'"
    ).fetchone()[0] == 1
    # Der Bestand steht noch.
    assert repo.hole_verdichtung(zweite, v) is not None
    assert repo.hole_arbeitsstand(zweite, 1)["begriffe"] == "Heimat, Arbeit"


def test_initialisiere_ist_idempotent(tmp_path):
    pfad = str(tmp_path / "i.db")
    c = db.verbinde(pfad)
    for _ in range(3):
        db.initialisiere(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


# ------------------------------------------------------------------- repo.py

def _interview(conn, message_id: int = 9) -> int:
    repo.merke_nachricht(conn, 1, message_id, "Ada", 0, "sprache", "",
                         "2026-09-06T09:00:00+00:00")
    return repo.lege_aufnahme_an(conn, 1, message_id, "lang", "sprache", None, 60)


def test_setze_und_lies_begriffe(frisch):
    aufnahme_id = _interview(frisch)
    v = repo.speichere_verdichtung(frisch, 1, aufnahme_id, "Text", [])
    assert repo.setze_verdichtung_begriffe(
        frisch, 1, v, ["Heimat", "Arbeit"], aufnahme_id=aufnahme_id
    ) == 2
    zeilen = repo.begriffe_zu_verdichtung(frisch, v)
    assert [z["begriff"] for z in zeilen] == ["Heimat", "Arbeit"]
    assert zeilen[0]["quelle"] == "abgleich"
    assert zeilen[0]["aufnahme_id"] == aufnahme_id


def test_setze_begriffe_ersetzt_statt_zu_ergaenzen(frisch):
    """Aendert die Gruppe ihre Begriffsliste, duerfen die alten Tags nicht
    stehen bleiben -- und ein zweiter Lauf darf nichts verdoppeln."""
    aufnahme_id = _interview(frisch)
    v = repo.speichere_verdichtung(frisch, 1, aufnahme_id, "Text", [])
    repo.setze_verdichtung_begriffe(frisch, 1, v, ["Heimat", "Arbeit"])
    repo.setze_verdichtung_begriffe(frisch, 1, v, ["Angst"])
    assert [z["begriff"] for z in repo.begriffe_zu_verdichtung(frisch, v)] == ["Angst"]


def test_derselbe_begriff_steht_nur_einmal_an_einer_verdichtung(frisch):
    aufnahme_id = _interview(frisch)
    v = repo.speichere_verdichtung(frisch, 1, aufnahme_id, "Text", [])
    repo.setze_verdichtung_begriffe(frisch, 1, v, ["Heimat", "Heimat"])
    assert len(repo.begriffe_zu_verdichtung(frisch, v)) == 1


def test_n_zu_m_in_beide_richtungen(frisch):
    """Ein Interview traegt mehrere Begriffe, ein Begriff mehrere Interviews."""
    a1 = _interview(frisch, 9)
    a2 = _interview(frisch, 10)
    v1 = repo.speichere_verdichtung(frisch, 1, a1, "Eins", [])
    v2 = repo.speichere_verdichtung(frisch, 1, a2, "Zwei", [])
    repo.setze_verdichtung_begriffe(frisch, 1, v1, ["Heimat", "Arbeit"])
    repo.setze_verdichtung_begriffe(frisch, 1, v2, ["Heimat"])
    assert len(repo.begriffe_zu_verdichtung(frisch, v1)) == 2
    assert [z["verdichtung_id"] for z in
            repo.verdichtungen_zu_begriff(frisch, 1, "heimat")] == [v1, v2]


def test_verdichtungen_zu_begriff_laesst_entfernte_weg(frisch):
    a1 = _interview(frisch)
    v1 = repo.speichere_verdichtung(frisch, 1, a1, "Eins", [])
    repo.setze_verdichtung_begriffe(frisch, 1, v1, ["Heimat"])
    frisch.execute("UPDATE verdichtung SET entfernt_am = '2026-09-06' WHERE id = ?", (v1,))
    frisch.commit()
    assert repo.verdichtungen_zu_begriff(frisch, 1, "Heimat") == []


# ------------------------------------------------------------ Zuordnungslogik

def test_verdichter_ordnet_beim_verdichten_zu(frisch):
    """Der Regelweg: die Zuordnung faellt beim Verdichten ab, ohne zweiten
    Modellaufruf -- die Attrappe zaehlt ihre Aufrufe mit."""
    repo.setze_arbeitsstand(frisch, 1, "begriffe", "Heimat, Arbeit, Angst")
    aufnahme_id = _interview(frisch)
    transkript = ("Die Arbeit war das Schwerste. Von Heimat wollte ich damals "
                  "gar nichts hoeren.")
    repo.setze_transkript(frisch, aufnahme_id, transkript)

    class Attrappe:
        aufrufe = 0

        def schema(self, chat_id, system, nutzer, schema, art):
            Attrappe.aufrufe += 1
            return {
                "zusammenfassung": "Sie spricht ueber die Arbeit.",
                "kernthemen": [
                    {"thema": "Heimat war kein Thema", "kurz": "Heimat",
                     "beleg_zitat": "Die Arbeit war das Schwerste"},
                ],
            }

    v = verdichter.verdichte(Attrappe(), frisch, None, aufnahme_id)
    assert Attrappe.aufrufe == 1
    assert [z["begriff"] for z in repo.begriffe_zu_verdichtung(frisch, v)] == [
        "Heimat", "Arbeit"
    ]


def test_verdichter_ohne_begriffsliste_setzt_keine_tags(frisch):
    aufnahme_id = _interview(frisch)
    repo.setze_transkript(frisch, aufnahme_id, "Ein Satz.")

    class Attrappe:
        def schema(self, *a, **k):
            return {"zusammenfassung": "Ein Satz.", "kernthemen": []}

    v = verdichter.verdichte(Attrappe(), frisch, None, aufnahme_id)
    assert repo.begriffe_zu_verdichtung(frisch, v) == []


def test_nachtraegliche_zuordnung_ist_idempotent(frisch):
    """Das Skript unter scripts/ laeuft gegen eine gewachsene Datenbank --
    zweimal laufen darf nichts verdoppeln und nichts veraendern."""
    import scripts.begriffe_zuordnen as skript

    repo.setze_arbeitsstand(frisch, 1, "begriffe", "Heimat, Arbeit")
    aufnahme_id = _interview(frisch)
    repo.speichere_verdichtung(
        frisch, 1, aufnahme_id, "Ueber die Arbeit und das Ankommen.",
        [{"thema": "Heimat blieb fern", "kurz": "Heimat", "beleg_zitat": "x",
          "zitat_geprueft": 1}],
    )
    erst = skript.zuordnen(frisch, 1)
    zweit = skript.zuordnen(frisch, 1)
    assert erst == zweit == (1, 2)
    assert frisch.execute(
        "SELECT count(*) FROM verdichtung_begriff"
    ).fetchone()[0] == 2


def test_nachtraegliche_zuordnung_trocken_schreibt_nichts(frisch):
    import scripts.begriffe_zuordnen as skript

    repo.setze_arbeitsstand(frisch, 1, "begriffe", "Arbeit")
    aufnahme_id = _interview(frisch)
    repo.speichere_verdichtung(frisch, 1, aufnahme_id, "Ueber die Arbeit.", [])
    assert skript.zuordnen(frisch, 1, trocken=True) == (1, 1)
    assert frisch.execute(
        "SELECT count(*) FROM verdichtung_begriff"
    ).fetchone()[0] == 0


# ----------------------------------------------------------------- Web-Anzeige

def test_web_daten_liefert_die_begriffe_je_interview(tmp_path):
    pfad = str(tmp_path / "w.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    repo.setze_arbeitsstand(c, 1, "begriffe", "Heimat, Arbeit")
    token = repo.stelle_web_token_sicher(c, 1)
    aufnahme_id = _interview(c)
    v = repo.speichere_verdichtung(c, 1, aufnahme_id, "Ueber die Arbeit.", [])
    repo.setze_verdichtung_begriffe(c, 1, v, ["Heimat", "Arbeit"])
    c.commit()

    lesend = web_daten.oeffne_lesend(pfad)
    daten = web_daten.gruppe_nach_token(lesend, token)
    assert daten["interviews"][0]["begriffe"] == ["Heimat", "Arbeit"]

    html = web.gruppe_html(daten)
    assert '<span class="begriff">Heimat</span>' in html
    assert '<span class="begriff">Arbeit</span>' in html
    assert ".begriff {" in html


def test_web_zeigt_ohne_zuordnung_keine_chipzeile(tmp_path):
    pfad = str(tmp_path / "ohne.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    token = repo.stelle_web_token_sicher(c, 1)
    aufnahme_id = _interview(c)
    repo.speichere_verdichtung(c, 1, aufnahme_id, "Text ohne Tags.", [])
    c.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    html = web.gruppe_html(web_daten.gruppe_nach_token(lesend, token))
    assert '<div class="begriffe">' not in html


def test_web_maskiert_begriffe(tmp_path):
    """Der Begriff kommt als Freitext aus dem Chat -- er darf kein HTML
    einschleusen."""
    html = web._begriffe_html(["<script>boese()</script>"])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_web_daten_ohne_tabelle_faellt_auf_leer_zurueck(tmp_path):
    """Zwischen Deploy und Bot-Neustart sieht der Webserver eine Datenbank
    ohne die neue Tabelle. Das ist kein 500, das ist 'keine Tags'."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    token = repo.stelle_web_token_sicher(c, 1)
    aufnahme_id = _interview(c)
    repo.speichere_verdichtung(c, 1, aufnahme_id, "Text", [])
    c.execute("DROP TABLE verdichtung_begriff")
    c.commit()

    lesend = web_daten.oeffne_lesend(pfad)
    daten = web_daten.gruppe_nach_token(lesend, token)
    assert daten["interviews"][0]["begriffe"] == []
