"""Die Auffangtabelle ``festlegung`` (06.09.2026, nach der Phase-4-Analyse).

Belegt in ``docs/analyse-phase4-datenverlust-2026-09-06.md``: von 42
Festlegungen einer Gruppe in Phase 4 sind 22 verloren, weil das Schema nur
feste Slots kennt und alles ausserhalb hoechstens als ``journal``-Eintrag
landet -- der nach ``kontext.JOURNAL_EINTRAEGE`` weiteren Zeilen aus dem
Prompt faellt und nie zurueckkehrt.

Die Fixtures hier sind synthetisch: kein Wortlaut aus einem echten Workshop.
"""

import sqlite3

import pytest

from interview_theater import db, repo


def test_tabelle_existiert_mit_allen_spalten(conn):
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(festlegung)")}
    assert spalten == {
        "id", "chat_id", "bereich", "bezug", "text", "quelle",
        "erstellt_am", "entfernt_am",
    }


def test_tabelle_traegt_chat_id_und_faellt_mit_der_loeschzusage(conn):
    """Jede Tabelle ausser ``bot_zustand`` hat ``chat_id`` (AGENTS.md) --
    sonst waere die Loeschzusage nicht mehr ein DELETE je Tabelle."""
    assert "festlegung" in db.TABELLEN_MIT_CHAT_ID
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene")
    db.loesche_gruppe(conn, 1)
    assert conn.execute("SELECT count(*) FROM festlegung").fetchone()[0] == 0


def test_initialisiere_ist_idempotent_auf_bestehender_datenbank(tmp_path):
    """Additiv per ``CREATE TABLE IF NOT EXISTS``: die Tabelle entsteht auch
    in einer schon gewachsenen Datenbank, und ein zweiter Lauf schadet
    nicht."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    # Eine Datenbank aus der Zeit davor: dasselbe Schema ohne festlegung.
    anfang = db.SCHEMA.index("CREATE TABLE IF NOT EXISTS festlegung")
    ende = db.SCHEMA.index("\n", db.SCHEMA.index("idx_festlegung_chat"))
    alt.executescript(db.SCHEMA[:anfang] + db.SCHEMA[ende:])
    alt.commit()
    with pytest.raises(sqlite3.OperationalError):
        alt.execute("SELECT 1 FROM festlegung")

    db.initialisiere(alt)
    db.initialisiere(alt)
    assert alt.execute("SELECT count(*) FROM festlegung").fetchone()[0] == 0


# --- repo ------------------------------------------------------------------


def test_schreiben_und_lesen_aeltestes_zuerst(conn):
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene, erste Folge")
    repo.schreibe_festlegung(conn, 1, "figur", "Herkunft Russland", bezug="Kassandra")
    zeilen = repo.festlegungen(conn, 1)
    assert [z["text"] for z in zeilen] == [
        "Nur eine Szene, erste Folge", "Herkunft Russland"
    ]
    assert zeilen[1]["bezug"] == "Kassandra"
    assert zeilen[0]["quelle"] == "erkenner"


def test_fremde_gruppe_sieht_nichts(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    repo.schreibe_festlegung(conn, 1, "ort", "Skatepark am Kanal")
    assert repo.festlegungen(conn, 2) == []


def test_leerer_text_schreibt_nichts(conn):
    assert repo.schreibe_festlegung(conn, 1, "sonstiges", "   ") is None
    assert repo.festlegungen(conn, 1) == []


def test_unbekannter_bereich_bleibt_als_freier_titel_stehen(conn):
    """Padua-Brainstorming-Umbau (02.10.2026): "unlimited, free titles" --
    ein Bereich, der zu keinem bekannten Wort passt, wird nicht mehr nach
    "sonstiges" kollabiert, sondern bleibt als Titel stehen (Gross-/
    Kleinschreibung erhalten)."""
    repo.schreibe_festlegung(conn, 1, "Kostueme", "irgendwas")
    assert repo.festlegungen(conn, 1)[0]["bereich"] == "Kostueme"


def test_leerer_bereich_wird_zu_sonstiges(conn):
    repo.schreibe_festlegung(conn, 1, "   ", "irgendwas")
    assert repo.festlegungen(conn, 1)[0]["bereich"] == "sonstiges"


def test_bereiche_enthalten_keinen_bekannten_feldnamen():
    """Risiko 2 der Analyse (\"Doppelte Wahrheit\"): steht \"Setting: X\"
    sowohl in ``arbeitsstand.rahmen`` als auch als Festlegung, widersprechen
    sich beide irgendwann. Ein ``bereich``, der wie ein Arbeitsstandfeld
    heisst, waere die Einladung dazu."""
    verboten = set(repo._ARBEITSSTAND_FELDER) | {"setting", "szene", "journal"}
    assert not (set(repo.FESTLEGUNG_BEREICHE) & verboten)


def test_dieselbe_festlegung_zweimal_wird_nicht_verdoppelt(conn):
    """Anders als das Journal: dort sind zwei gleichlautende Aeusserungen
    zwei Ereignisse, hier ist eine Festlegung ein Zustand. Der Erkenner
    neigt zur Uebererfassung (Analyse § 4.4 Risiko 1)."""
    erste = repo.schreibe_festlegung(conn, 1, "gruppe", "Zwei Fraktionen", bezug="A")
    zweite = repo.schreibe_festlegung(conn, 1, "gruppe", "Zwei Fraktionen", bezug="A")
    assert erste is not None
    assert zweite is None
    assert len(repo.festlegungen(conn, 1)) == 1


def test_derselbe_text_in_anderem_bereich_ist_eine_eigene_zeile(conn):
    repo.schreibe_festlegung(conn, 1, "gruppe", "am Wasser")
    repo.schreibe_festlegung(conn, 1, "ort", "am Wasser")
    assert len(repo.festlegungen(conn, 1)) == 2


def test_entfernen_stempelt_weich_und_liefert_den_text(conn):
    repo.schreibe_festlegung(conn, 1, "ort", "Zweiter Ort: die Schule")
    weg = repo.entferne_festlegung(conn, 1, "schule")
    assert weg == "Zweiter Ort: die Schule"
    assert repo.festlegungen(conn, 1) == []
    # Weich: die Zeile steht noch da.
    zeile = conn.execute("SELECT * FROM festlegung").fetchone()
    assert zeile["entfernt_am"]


def test_entfernen_ohne_treffer_liefert_none(conn):
    repo.schreibe_festlegung(conn, 1, "ort", "Skatepark")
    assert repo.entferne_festlegung(conn, 1, "Bahnhof") is None
    assert len(repo.festlegungen(conn, 1)) == 1


def test_entfernen_trifft_den_juengsten_treffer(conn):
    repo.schreibe_festlegung(conn, 1, "ort", "Ort: Kanal")
    repo.schreibe_festlegung(conn, 1, "ort", "Ort: Kanal und Schule")
    assert repo.entferne_festlegung(conn, 1, "kanal") == "Ort: Kanal und Schule"


def test_entfernen_sucht_auch_im_bezug(conn):
    repo.schreibe_festlegung(conn, 1, "figur", "19, Schauspielerin", bezug="Kassandra")
    assert repo.entferne_festlegung(conn, 1, "Kassandra") == "19, Schauspielerin"


def test_entfernen_nach_id_nur_in_der_eigenen_gruppe(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    fid = repo.schreibe_festlegung(conn, 1, "ort", "Skatepark")
    assert repo.entferne_festlegung_nach_id(conn, 2, fid) is None
    assert len(repo.festlegungen(conn, 1)) == 1
    assert repo.entferne_festlegung_nach_id(conn, 1, fid) == "Skatepark"
    assert repo.festlegungen(conn, 1) == []


def test_entfernte_zeile_blockiert_die_dublettenpruefung_nicht(conn):
    """Zurueckgenommen und neu gesagt ist eine neue Festlegung."""
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene")
    repo.entferne_festlegung(conn, 1, "Nur eine Szene")
    assert repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene") is not None
    assert len(repo.festlegungen(conn, 1)) == 1


def test_zeile_formatiert_bereich_bezug_und_text():
    """Die eine Formatierung, die Prompt, Chat und Weboberflaeche teilen."""
    assert repo.festlegungszeile("figur", "Kassandra", "19, Schauspielerin") == (
        "[figur/Kassandra] 19, Schauspielerin"
    )
    assert repo.festlegungszeile("struktur", None, "Nur eine Szene") == (
        "[struktur] Nur eine Szene"
    )
