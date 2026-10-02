"""Der Festlegungs-Block im Gespraechs-Prompt (06.09.2026).

Er steht direkt hinter dem Arbeitsstand, ist auf ``FESTLEGUNGEN_ZEILEN``
Zeilen und ``BUDGETS["festlegungen"]`` Token gedeckelt und wird
**aelteste-zuerst** behalten -- anders als das Journal, das die letzten
Zeilen behaelt. Der Grund steht in der Analyse: eine fruehe Grundfestlegung
("nur eine Szene, erste Folge einer Serie") wiegt mehr als eine spaete
Detailnotiz, und genau diese Grundfestlegung ist am 06.09. verloren gegangen.

Fixtures synthetisch.
"""

import pytest

from interview_theater import db, einstellungen, kontext, repo


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_ohne_festlegungen_kein_block(conn):
    assert kontext._baue_festlegungen(conn, 1) == ""


def test_block_traegt_kopf_bereich_und_bezug(conn):
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene, erste Folge")
    repo.schreibe_festlegung(conn, 1, "figur", "19, Schauspielerin", bezug="Kassandra")
    block = kontext._baue_festlegungen(conn, 1)
    assert block.splitlines() == [
        kontext.FESTLEGUNGEN_KOPF,
        "- [struktur] Nur eine Szene, erste Folge",
        "- [figur/Kassandra] 19, Schauspielerin",
    ]


def test_entfernte_festlegung_faellt_aus_dem_prompt(conn):
    """Risiko 3 der Analyse: ein Journaleintrag ueber einen zurueckgenommenen
    zweiten Spielort galt formal weiter, weil ihn nie jemand abgeraeumt hat."""
    repo.schreibe_festlegung(conn, 1, "ort", "Zweiter Ort: die Schule")
    repo.entferne_festlegung(conn, 1, "Schule")
    assert kontext._baue_festlegungen(conn, 1) == ""


def test_block_steht_direkt_hinter_dem_arbeitsstand():
    reihenfolge = list(kontext._REIHENFOLGE)
    assert reihenfolge[reihenfolge.index("arbeitsstand") + 1] == "festlegungen"


def test_block_hat_ein_eigenes_budget():
    assert kontext.BUDGETS["festlegungen"] == 800


def test_kappung_behaelt_die_aeltesten_zeilen(conn):
    """Aeltestes zuerst -- anders als ``_baue_journal``. Die erste Zeile ist
    die Grundfestlegung, die letzte eine Detailnotiz."""
    for nummer in range(kontext.FESTLEGUNGEN_ZEILEN + 5):
        repo.schreibe_festlegung(conn, 1, "sonstiges", f"Festlegung {nummer}")
    zeilen = kontext._baue_festlegungen(conn, 1).splitlines()[1:]
    assert len(zeilen) == kontext.FESTLEGUNGEN_ZEILEN
    assert zeilen[0] == "- [sonstiges] Festlegung 0"
    assert zeilen[-1] == f"- [sonstiges] Festlegung {kontext.FESTLEGUNGEN_ZEILEN - 1}"


def test_kappung_haelt_auch_das_zeichenbudget(conn):
    for nummer in range(kontext.FESTLEGUNGEN_ZEILEN):
        repo.schreibe_festlegung(conn, 1, "sonstiges", f"{nummer} " + "x" * 400)
    block = kontext._baue_festlegungen(conn, 1)
    assert kontext.schaetze(block) <= kontext.BUDGETS["festlegungen"]
    # Und wieder die aeltesten, nicht die juengsten.
    assert block.splitlines()[1].startswith("- [sonstiges] 0 ")


def test_dubletten_stehen_nur_einmal_im_prompt(conn):
    """Der Dublettenschutz sitzt im ``repo``; hier wird belegt, dass er im
    Prompt ankommt -- der Erkenner neigt zur Uebererfassung."""
    repo.schreibe_festlegung(conn, 1, "gruppe", "Zwei Fraktionen")
    repo.schreibe_festlegung(conn, 1, "gruppe", "Zwei Fraktionen")
    assert kontext._baue_festlegungen(conn, 1).count("Zwei Fraktionen") == 1


def test_block_erscheint_im_fertigen_prompt(conn, einst):
    repo.merke_nachricht(conn, 1, 1, "Sara", 0, "text", "los", "2026-09-06T10:00:00")
    ausloeser = [repo.hole_nachricht(conn, 1, 1)]
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene, erste Folge")
    prompt = kontext.baue(conn, 1, ausloeser, einst)
    assert kontext.FESTLEGUNGEN_KOPF in prompt
    assert "Nur eine Szene, erste Folge" in prompt


def test_block_steht_im_umriss(conn, einst):
    repo.merke_nachricht(conn, 1, 1, "Sara", 0, "text", "los", "2026-09-06T10:00:00")
    ausloeser = [repo.hole_nachricht(conn, 1, 1)]
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene")
    protokoll = []
    kontext.baue(conn, 1, ausloeser, einst, protokoll=protokoll)
    assert protokoll[0]["bloecke"]["festlegungen"] > 0


def test_kuerzung_opfert_die_festlegungen_erst_nach_dem_journal(conn, einst, monkeypatch):
    """Die Kuerzungskaskade: Transkripte, Verlauf, Journal, **Festlegungen**,
    Verdichtungen. Sie sind der vorletzte Kandidat -- klein, stabil und
    genau das, was ohne sie verloren ginge."""
    monkeypatch.setattr(kontext, "zeichengrenze", lambda ueber_claude=False: 400)
    for nummer in range(6):
        repo.merke_nachricht(
            conn, 1, nummer + 1, "Sara", 0, "text", "y" * 200,
            f"2026-09-06T10:0{nummer}:00",
        )
    repo.schreibe_journal(conn, 1, "entschieden", "j" * 200, quelle="erkenner")
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene, erste Folge")
    ausloeser = [repo.hole_nachricht(conn, 1, 6)]
    prompt = kontext.baue(conn, 1, ausloeser, einst)
    # Das Journal ist weg, die Festlegung steht noch da.
    assert "j" * 200 not in prompt
    assert "Nur eine Szene, erste Folge" in prompt


def test_kuerzung_gibt_die_festlegungen_zeilenweise_von_hinten_auf(conn, einst, monkeypatch):
    """Und wenn sie doch drankommen: die juengsten Zeilen zuerst, damit die
    Grundfestlegung als letzte faellt."""
    monkeypatch.setattr(kontext, "zeichengrenze", lambda ueber_claude=False: 260)
    repo.merke_nachricht(conn, 1, 1, "Sara", 0, "text", "kurz", "2026-09-06T10:00:00")
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene")
    for nummer in range(8):
        repo.schreibe_festlegung(conn, 1, "sonstiges", f"Detail {nummer} " + "z" * 40)
    ausloeser = [repo.hole_nachricht(conn, 1, 1)]
    prompt = kontext.baue(conn, 1, ausloeser, einst)
    assert "Nur eine Szene" in prompt
    assert "Detail 7" not in prompt
