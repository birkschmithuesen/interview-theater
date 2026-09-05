"""Tests fuer scripts/interviews_uebernehmen.py -- gegen eine Wegwerf-DB."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo  # noqa: E402
from scripts import interviews_uebernehmen as ui  # noqa: E402

ZIEL = 111
Q1 = 222
Q2 = 333


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, ZIEL, "gruppe1", "Ziel")
    repo.sichere_gruppe(c, Q1, "gruppe2", "Quelle 1")
    repo.sichere_gruppe(c, Q2, "gruppe3", "Quelle 2")
    return c


def _interview(conn, chat_id, audio_dir: Path, teile=2, themen=1, geprueft=1,
               zusammenfassung="Es ging um Arbeit."):
    """Ein vollstaendiges Interview: Kopf, Teile mit Audiodateien, Verdichtung."""
    kopf = repo.lege_interview_an(conn, chat_id)
    for n in range(teile):
        datei = audio_dir / str(chat_id) / f"{kopf}-{n}.ogg"
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_bytes(b"OGG" + str(kopf).encode())
        teil = repo.lege_aufnahme_an(
            conn, chat_id, 900 + kopf * 10 + n, "teil", "sprache",
            audio_pfad=str(datei), teil_von=kopf,
        )
        conn.execute(
            "UPDATE aufnahme SET transkript = ?, status = 'fertig' WHERE id = ?",
            (f"Teil {n} von {kopf}", teil),
        )
    conn.execute(
        "UPDATE aufnahme SET status = 'fertig', transkript = ?, beendet_am = '2026-09-05T12:00:00+02:00' "
        "WHERE id = ?",
        (f"Ganzes Interview {kopf}", kopf),
    )
    conn.commit()
    repo.speichere_verdichtung(
        conn, chat_id, kopf, zusammenfassung,
        [{"thema": f"Thema {i}", "kurz": f"K{i}", "beleg_zitat": "das war hart",
          "zitat_geprueft": geprueft} for i in range(themen)],
    )
    return kopf


def test_import_aus_zwei_quellen_zaehlt_nummern_weiter(conn, tmp_path):
    audio = tmp_path / "audio"
    eigen = _interview(conn, ZIEL, audio)          # Interview 1 der Zielgruppe
    a = _interview(conn, Q1, audio)
    b = _interview(conn, Q1, audio)
    c = _interview(conn, Q2, audio)

    bericht = ui.uebernimm(conn, ZIEL, [Q1, Q2], str(audio))

    assert bericht["neu_gesamt"] == 3
    assert bericht["nachher"] == 4
    assert bericht["posten"][0]["nummern"] == [2, 3]
    assert bericht["posten"][1]["nummern"] == [4]

    from interview_theater import kontext

    koepfe = [z for z in repo.transkripte(conn, ZIEL) if z["klasse"] == "lang"]
    assert [k["name"] for k in koepfe] == [
        "Interview 1", "Interview 2", "Interview 3", "Interview 4"
    ]
    # Das eigene Interview behaelt seine Nummer, die Importe kommen dahinter.
    assert kontext.interviewbezeichnung(conn, ZIEL, eigen) == "Interview 1"
    assert kontext.interviewbezeichnung(conn, ZIEL, koepfe[-1]["id"]) == "Interview 4"
    assert [a, b, c] == [a, b, c]  # Quell-ids unveraendert benutzbar


def test_teile_haengen_am_neuen_kopf_und_audio_wird_kopiert(conn, tmp_path):
    audio = tmp_path / "audio"
    alt = _interview(conn, Q1, audio, teile=3)

    ui.uebernimm(conn, ZIEL, [Q1], str(audio))

    neu = conn.execute(
        "SELECT * FROM aufnahme WHERE chat_id = ? AND klasse = 'lang'", (ZIEL,)
    ).fetchone()
    assert neu["uebernommen_von"] == f"{Q1}:{alt}"
    assert neu["uebernommen_am"]
    assert neu["transkript"] == f"Ganzes Interview {alt}"

    teile = repo.hole_teile(conn, neu["id"])
    assert len(teile) == 3
    assert all(t["chat_id"] == ZIEL for t in teile)
    assert all(t["teil_von"] == neu["id"] for t in teile)
    for t in teile:
        pfad = Path(t["audio_pfad"])
        assert pfad.exists()
        assert str(ZIEL) in pfad.parts
        assert pfad.read_bytes().startswith(b"OGG")
    # Die Teile der Quelle haengen weiter an ihrem eigenen Kopf.
    assert len(repo.hole_teile(conn, alt)) == 3


def test_verdichtung_themen_und_geprueftes_zitat_kommen_mit(conn, tmp_path):
    audio = tmp_path / "audio"
    _interview(conn, Q1, audio, themen=2, geprueft=1)

    ui.uebernimm(conn, ZIEL, [Q1], str(audio))

    verdichtungen = repo.verdichtungen(conn, ZIEL)
    assert len(verdichtungen) == 1
    assert verdichtungen[0]["zusammenfassung"] == "Es ging um Arbeit."
    themen = repo.themen_zu(conn, verdichtungen[0]["id"])
    assert len(themen) == 2
    assert all(t["chat_id"] == ZIEL for t in themen)
    assert all(t["zitat_geprueft"] == 1 for t in themen)
    assert all(t["beleg_zitat"] == "das war hart" for t in themen)
    # Die Kernthema-Markierung der Quelle wandert nicht mit.
    assert all(t["zum_kernthema_am"] is None for t in themen)
    # Und die Verdichtung haengt am NEUEN Kopf.
    kopf = conn.execute(
        "SELECT id FROM aufnahme WHERE chat_id = ? AND klasse = 'lang'", (ZIEL,)
    ).fetchone()["id"]
    assert verdichtungen[0]["aufnahme_id"] == kopf


def test_zweiter_lauf_tut_nichts(conn, tmp_path):
    audio = tmp_path / "audio"
    _interview(conn, Q1, audio)
    _interview(conn, Q1, audio)

    ui.uebernimm(conn, ZIEL, [Q1], str(audio))
    vorher = repo.zaehle_aufnahmen(conn, ZIEL)

    zweiter = ui.uebernimm(conn, ZIEL, [Q1], str(audio))

    assert zweiter["neu_gesamt"] == 0
    assert zweiter["posten"][0]["schon_da"] == 2
    assert repo.zaehle_aufnahmen(conn, ZIEL) == vorher
    assert len(repo.verdichtungen(conn, ZIEL)) == 2


def test_quellen_bleiben_unveraendert(conn, tmp_path):
    audio = tmp_path / "audio"
    _interview(conn, Q1, audio)

    def stand(chat_id):
        return (
            [tuple(z) for z in conn.execute(
                "SELECT * FROM aufnahme WHERE chat_id = ? ORDER BY id", (chat_id,))],
            [tuple(z) for z in conn.execute(
                "SELECT * FROM verdichtung WHERE chat_id = ? ORDER BY id", (chat_id,))],
            [tuple(z) for z in conn.execute(
                "SELECT * FROM verdichtung_thema WHERE chat_id = ? ORDER BY id", (chat_id,))],
            [tuple(z) for z in conn.execute(
                "SELECT * FROM journal WHERE chat_id = ? ORDER BY id", (chat_id,))],
        )

    vorher = stand(Q1)
    ui.uebernimm(conn, ZIEL, [Q1], str(audio))
    assert stand(Q1) == vorher


def test_nichts_ausser_material_wandert(conn, tmp_path):
    audio = tmp_path / "audio"
    kopf = _interview(conn, Q1, audio)
    repo.setze_arbeitsstand(conn, Q1, "kernthema", "Das Kernthema der Quelle")
    repo.setze_figur(conn, Q1, "Maria", "eine Figur")
    repo.schreibe_journal(conn, Q1, "entschieden", "Eintrag der Quelle", "befehl")
    repo.merke_nachricht(conn, Q1, 5, "Anna", 0, "text", "Hallo", "2026-09-05T10:00:00+02:00")
    conn.execute(
        "INSERT INTO kernzitat (chat_id, aufnahme_id, zitat, erstellt_am) "
        "VALUES (?, ?, ?, ?)", (Q1, kopf, "das war hart", "2026-09-05T10:00:00+02:00"),
    )
    conn.commit()

    ui.uebernimm(conn, ZIEL, [Q1], str(audio))

    for tabelle in ("figur", "szene", "knopf", "nachricht", "kernzitat", "arbeitsstand"):
        anzahl = conn.execute(
            f"SELECT count(*) FROM {tabelle} WHERE chat_id = ?", (ZIEL,)
        ).fetchone()[0]
        assert anzahl == 0, tabelle


def test_verweigert_bei_laufender_aufnahme(conn, tmp_path):
    audio = tmp_path / "audio"
    _interview(conn, Q1, audio)
    repo.lege_interview_an(conn, Q1)          # status='laeuft'
    assert ui.laufende_aufnahme(conn, Q1) is True
    assert ui.laufende_aufnahme(conn, ZIEL) is False


def test_verweigert_bei_interviewmodus(conn, tmp_path):
    conn.execute(
        "UPDATE gruppe SET interviewmodus_seit = ? WHERE chat_id = ?",
        ("2026-09-05T12:00:00+02:00", ZIEL),
    )
    conn.commit()
    assert ui.laufende_aufnahme(conn, ZIEL) is True


def test_journaleintrag_und_chatzeile(conn, tmp_path):
    audio = tmp_path / "audio"
    for _ in range(3):
        _interview(conn, Q1, audio)
    _interview(conn, Q2, audio)
    _interview(conn, ZIEL, audio)   # eigenes Interview 1

    bericht = ui.uebernimm(conn, ZIEL, [Q1, Q2], str(audio))
    text = ui.journaltext(bericht)
    assert text == (
        "Interviews uebernommen: 3 aus Gruppe gruppe2 (Interview 2\u20134), "
        "1 aus Gruppe gruppe3 (Interview 5)"
    )
    assert ui.chattext(bericht) == (
        "Ab jetzt liegen hier auch die Interviews der anderen Gruppen: "
        "Interview 2 bis 5."
    )

    repo.schreibe_journal(conn, ZIEL, "entschieden", text, "befehl")
    eintraege = conn.execute(
        "SELECT text FROM journal WHERE chat_id = ?", (ZIEL,)
    ).fetchall()
    assert [e["text"] for e in eintraege] == [text]


def test_trockenlauf_schreibt_nichts(conn, tmp_path):
    audio = tmp_path / "audio"
    _interview(conn, Q1, audio)
    _interview(conn, Q1, audio)

    bericht = ui.plane(conn, ZIEL, [Q1])

    assert bericht["neu_gesamt"] == 2
    assert bericht["posten"][0]["nummern"] == [1, 2]
    assert bericht["posten"][0]["teile"] == 4
    assert bericht["posten"][0]["verdichtungen"] == 2
    assert bericht["posten"][0]["themen"] == 2
    assert bericht["posten"][0]["zitate"] == 2
    assert bericht["posten"][0]["audio"] == 4
    assert repo.zaehle_aufnahmen(conn, ZIEL) == 0
    assert repo.verdichtungen(conn, ZIEL) == []
    assert not (tmp_path / "audio" / str(ZIEL)).exists()
    # Und der Bericht laesst sich anzeigen.
    assert "Trockenlauf" in ui.berichtstext(bericht, trocken=True)


def test_fehlende_audiodatei_warnt_ohne_abbruch(conn, tmp_path):
    audio = tmp_path / "audio"
    kopf = _interview(conn, Q1, audio, teile=2)
    teile = repo.hole_teile(conn, kopf)
    Path(teile[0]["audio_pfad"]).unlink()

    warnungen: list[str] = []
    bericht = ui.uebernimm(conn, ZIEL, [Q1], str(audio), warnungen)

    assert bericht["neu_gesamt"] == 1
    assert len(warnungen) == 1 and "Audiodatei fehlt" in warnungen[0]
    assert bericht["kopierte_audio"] == 1
    neu = conn.execute(
        "SELECT id FROM aufnahme WHERE chat_id = ? AND klasse = 'lang'", (ZIEL,)
    ).fetchone()["id"]
    # Der Teil ohne Datei ist trotzdem da -- mit dem Pfad der Quelle als Beleg.
    assert len(repo.hole_teile(conn, neu)) == 2


def test_entferntes_interview_wandert_nicht(conn, tmp_path):
    audio = tmp_path / "audio"
    a = _interview(conn, Q1, audio)
    _interview(conn, Q1, audio)
    repo.entferne_aufnahme(conn, Q1, a)

    bericht = ui.uebernimm(conn, ZIEL, [Q1], str(audio))
    assert bericht["neu_gesamt"] == 1


def test_rollback_bei_fehler(conn, tmp_path, monkeypatch):
    audio = tmp_path / "audio"
    _interview(conn, Q1, audio)
    _interview(conn, Q1, audio)

    original = ui._kopiere_verdichtungen
    zaehler = {"n": 0}

    def kaputt(*a, **k):
        zaehler["n"] += 1
        if zaehler["n"] == 2:
            raise RuntimeError("absichtlich")
        return original(*a, **k)

    monkeypatch.setattr(ui, "_kopiere_verdichtungen", kaputt)
    with pytest.raises(RuntimeError):
        ui.uebernimm(conn, ZIEL, [Q1], str(audio))

    assert repo.zaehle_aufnahmen(conn, ZIEL) == 0
    assert repo.verdichtungen(conn, ZIEL) == []


def test_uebernommenes_wandert_nicht_weiter(conn, tmp_path):
    """Kette A -> B -> C legt in C keine zweite Kopie mit falscher Herkunft an."""
    audio = tmp_path / "audio"
    _interview(conn, Q1, audio)
    ui.uebernimm(conn, Q2, [Q1], str(audio))

    bericht = ui.uebernimm(conn, ZIEL, [Q2], str(audio))
    assert bericht["neu_gesamt"] == 0


def test_migration_ergaenzt_spalten_in_alter_datenbank(tmp_path):
    """Die beiden neuen Spalten kommen additiv in eine Datenbank, die sie noch
    nicht kennt (_migriere_fehlende_spalten)."""
    pfad = str(tmp_path / "alt.db")
    c = sqlite3.connect(pfad)
    c.execute(
        "CREATE TABLE aufnahme (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, "
        "message_id INTEGER NOT NULL, klasse TEXT NOT NULL, quelle TEXT NOT NULL, "
        "status TEXT NOT NULL, empfangen_am TEXT NOT NULL)"
    )
    c.commit()
    c.close()

    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(aufnahme)")}
    assert {"uebernommen_von", "uebernommen_am", "teil_von"} <= spalten


def test_main_ohne_argumente_meldet_aufruf(capsys):
    assert ui.main([]) == 1
    assert "Aufruf:" in capsys.readouterr().out


def test_main_verweigert_ziel_als_eigene_quelle(capsys):
    assert ui.main(["5", "5"]) == 1
    assert "eigene Quelle" in capsys.readouterr().out
