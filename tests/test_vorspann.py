"""Der Vorspann vor dem Text (07.09.2026).

Gemessen wird dreierlei: der Schnitt der Figurenbeschreibung
(``erster_satz``), die Zusammenstellung der Bloecke (``daten``/``als_*``) und
die beiden Fallen aus dem Auftrag -- angeklebte Schaerfungsnotizen und weich
geloeschte Figuren.

Alle Namen und Texte sind erfunden.
"""

import pytest

from interview_theater import db, repo, vorspann


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Die Ankommenden")
    return c


# --- erster_satz -----------------------------------------------------------


def test_schaerfungsnotiz_ohne_trennzeichen_wird_abgeschnitten():
    # Die gemessene Form (06.09.2026): die Notiz klebt ohne Punkt an.
    roh = "kaempft mit sich selbst liefert den Hintergrund fuer ihre Ablehnung"

    assert vorspann.erster_satz(roh) == "kaempft mit sich selbst"


@pytest.mark.parametrize(
    "formel",
    ["liefert", "macht deutlich", "zeigt", "begründet", "erklaert",
     "verstärkt", "unterstreicht"],
)
def test_jede_schaerfungsformel_schneidet(formel):
    roh = f"sucht einen Platz im Betrieb {formel} etwas ueber die Gruppe"

    assert vorspann.erster_satz(roh) == "sucht einen Platz im Betrieb"


def test_satzende_schneidet_wenn_es_frueher_kommt():
    roh = "Sie kommt aus Duisburg. Das zeigt, woher ihre Ruhe kommt."

    assert vorspann.erster_satz(roh) == "Sie kommt aus Duisburg."


def test_kurzer_erster_satz_mit_formel_bleibt_ganz():
    # Unter MINDEST_ZEICHEN wird nicht an der Formel geschnitten: sonst bliebe
    # von "Mira zeigt Haerte." das Wort "Mira" uebrig.
    assert vorspann.erster_satz("Mira zeigt Haerte.") == "Mira zeigt Haerte."


def test_sehr_langer_satz_wird_gedeckelt():
    roh = "ein Wort " * 60

    kurz = vorspann.erster_satz(roh)

    assert len(kurz) <= vorspann.GRENZE + 2
    assert kurz.endswith("…")


def test_leere_beschreibung_bleibt_leer():
    assert vorspann.erster_satz(None) == ""
    assert vorspann.erster_satz("   ") == ""


def test_zeilenumbrueche_werden_zu_leerzeichen():
    assert vorspann.erster_satz("zwei\n  Zeilen") == "zwei Zeilen"


# --- daten -----------------------------------------------------------------


def test_entfernte_figur_steht_nicht_im_vorspann():
    d = vorspann.daten(
        "", "", "", [],
        [
            {"name": "Mira", "beschreibung": "wartet", "entfernt_am": None},
            {"name": "Jonas", "beschreibung": "geht", "entfernt_am": "2026-09-06"},
        ],
    )

    assert [f["name"] for f in d["figuren"]] == ["Mira"]


def test_figur_ohne_namen_faellt_weg():
    d = vorspann.daten("", "", "", [], [{"name": "  ", "beschreibung": "x"}])

    assert d["figuren"] == []


def test_nur_die_bestaetigte_form_geht_mit():
    d = vorspann.daten(
        "", "", "",
        [{"nummer": 1, "titel": "Am Steg", "form": "", "form_vorschlag": "chor"}],
        [],
    )

    assert d["szenen"][0]["form"] == ""


def test_aus_datenbank_liest_arbeitsstand_figuren_und_szenen(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Hinterhof, Juli, abends")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "Bleiben oder gehen")
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied")
    repo.setze_figur(conn, 1, "Mira", "wartet seit Stunden auf den Bus liefert den Grund")
    repo.setze_figur(conn, 1, "Karim", "raeumt auf.")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")

    d = vorspann.aus_datenbank(conn, 1)

    assert d["rahmen"] == "Ein Hinterhof, Juli, abends"
    assert d["hauptkonflikt"] == "Bleiben oder gehen"
    assert d["format"] == "Musical: Dialog, Lied"
    assert d["szenen"] == [{"nummer": 1, "titel": "Am Steg", "form": "Dialog"}]
    assert [f["name"] for f in d["figuren"]] == ["Mira", "Karim"]
    assert d["figuren"][0]["beschreibung"] == "wartet seit Stunden auf den Bus"


def test_entfernte_figur_kommt_auch_aus_der_datenbank_nicht_mit(conn):
    repo.setze_figur(conn, 1, "Mira", "wartet")
    repo.setze_figur(conn, 1, "Jonas", "geht")
    repo.entferne_figur(conn, 1, "Jonas")

    d = vorspann.aus_datenbank(conn, 1)

    assert [f["name"] for f in d["figuren"]] == ["Mira"]


def test_leere_gruppe_hat_keinen_vorspann(conn):
    d = vorspann.aus_datenbank(conn, 1)

    assert vorspann.ist_leer(d)
    assert vorspann.als_markdown(d) == ""
    assert vorspann.als_chattext(d) == ""


# --- Darstellung -----------------------------------------------------------


def _beispiel():
    return vorspann.daten(
        "Ein Hinterhof, Juli, abends",
        "Bleiben oder gehen",
        "Musical: Dialog, Lied",
        [
            {"nummer": 1, "titel": "Am Steg", "form": "Dialog"},
            {"nummer": 2, "titel": "Die Kueche", "form": ""},
        ],
        [
            {"name": "Mira", "beschreibung": "wartet auf den Bus"},
            {"name": "Karim", "beschreibung": ""},
        ],
    )


def test_markdown_hat_die_fuenf_ueberschriften():
    text = vorspann.als_markdown(_beispiel())

    assert "## Wo und wann\nEin Hinterhof, Juli, abends" in text
    assert "## Worum es geht\nBleiben oder gehen" in text
    assert "## Form\nMusical: Dialog, Lied" in text
    assert "## 2 Szenen" in text
    assert "1. Am Steg (Dialog)" in text
    # Ohne bestaetigte Form keine Klammer.
    assert "2. Die Kueche\n" in text
    assert "## Wer vorkommt" in text
    assert "**Mira** — wartet auf den Bus" in text
    # Eine Figur ohne Beschreibung steht mit ihrem Namen da, ohne Gedankenstrich.
    assert "**Karim**\n" in text or text.rstrip().endswith("**Karim**")


def test_eine_einzige_szene_heisst_szene():
    d = vorspann.daten("", "", "", [{"nummer": 1, "titel": "Am Steg"}], [])

    assert "## 1 Szene\n" in vorspann.als_markdown(d)


def test_chattext_traegt_keine_rauten_und_keine_sternchen():
    text = vorspann.als_chattext(_beispiel())

    assert "#" not in text
    assert "*" not in text
    assert "Wo und wann\nEin Hinterhof, Juli, abends" in text
    assert "Mira — wartet auf den Bus" in text


def test_leere_bloecke_fallen_weg():
    d = vorspann.daten("", "", "", [], [{"name": "Mira", "beschreibung": ""}])

    text = vorspann.als_markdown(d)

    assert "Wo und wann" not in text
    assert "Worum es geht" not in text
    assert "Szenen" not in text
    assert "## Wer vorkommt" in text


def test_der_vorspann_ist_bei_jedem_abruf_derselbe(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Hinterhof")
    repo.setze_figur(conn, 1, "Mira", "wartet")

    erst = vorspann.als_markdown(vorspann.aus_datenbank(conn, 1))
    zweit = vorspann.als_markdown(vorspann.aus_datenbank(conn, 1))

    assert erst == zweit
