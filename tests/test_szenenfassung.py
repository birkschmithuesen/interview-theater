"""Tests fuer die Szenenfassungen (06.09.2026).

„Neu schreiben" ersetzte bis heute den Volltext -- die Gruppe konnte nicht
zurueck, und in der Probe will man zwei Fassungen nebeneinander lesen. Seitdem
haengt jeder erfolgreiche Szenenlauf seine Fassung zusaetzlich an
``szenenfassung`` an.

Gemessen wird hier vor allem, was **nicht** passiert: ``szene.volltext``
bleibt die aktuelle Fassung, kein Aufrufer ausserhalb aendert sich, und die
Migration einer Alt-Datenbank laeuft ohne Datenverlust und beliebig oft.
"""

import pytest

from interview_theater import db, knoepfe, kurzgeschichte, repo, szene, web, web_daten

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


class ModellAttrappe:
    """Liefert einen fertigen Szenentext, ohne das Netz anzufassen."""

    def __init__(self, texte):
        self.texte = list(texte)
        self.aufrufe = 0

    def prosa(self, chat_id, system, nutzer, art, **kw):
        self.aufrufe += 1
        return self.texte.pop(0)


def _antwort(volltext, anders="Kuerzer, ohne den Bruder."):
    return (
        "TITEL: Am Bahnhof\n"
        "KURZ: Sie warten.\n"
        f"ZUSAMMENFASSUNG: Sie warten auf den Bus.\n"
        f"ANDERS GEMACHT: {anders}\n\n"
        f"{volltext}"
    )


def _geplante_szene(conn, chat_id=1, nummer=1):
    """Eine Szene im **Feinschliff**, die alle Pflichtfelder hat -- sonst
    greift die Sperre, und unter Phase 7 schriebe der Lauf Prosa statt eines
    Theatertexts (``szene.schreibt_prosa``)."""
    repo.setze_phase(conn, chat_id, 7)
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "Bahnhof, abends")
    repo.setze_figur(conn, chat_id, "Maria", "Sechzehn.")
    figur_id = repo.hole_figur(conn, chat_id, "Maria")["id"]
    repo.setze_sprachprofil(conn, figur_id, "Kurze Saetze.", ["Da bin ich."])
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    for feld, wert in (
        ("form", "Dialog"), ("ort", "Bahnhof"), ("was_passiert", "Sie warten."),
    ):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, chat_id, szene_id, [figur_id])
    return szene_id


# --- zwei Laeufe, zwei Fassungen -------------------------------------------


def test_zwei_laeufe_ergeben_zwei_fassungen(conn, einst, tg):
    szene_id = _geplante_szene(conn)
    klm = ModellAttrappe([
        _antwort("MARIA:Da bin ich.", "Erste Fassung."),
        _antwort("MARIA:Immer noch da.", "Kuerzer gemacht."),
    ])

    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")

    fassungen = repo.szenenfassungen(conn, szene_id)
    assert [f["nummer"] for f in fassungen] == [1, 2]
    assert fassungen[0]["volltext"] == "MARIA:Da bin ich."
    assert fassungen[1]["volltext"] == "MARIA:Immer noch da."
    assert fassungen[1]["anders_gemacht"] == "Kuerzer gemacht."


def test_volltext_bleibt_die_aktuelle_fassung(conn, einst, tg):
    """Der Punkt der ganzen Aenderung: kein Aufrufer ausserhalb liest
    ploetzlich woanders."""
    szene_id = _geplante_szene(conn)
    klm = ModellAttrappe([
        _antwort("MARIA:Da bin ich."), _antwort("MARIA:Immer noch da."),
    ])

    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")

    zeile = next(s for s in repo.hole_szenen(conn, 1) if s["id"] == szene_id)
    assert zeile["volltext"] == "MARIA:Immer noch da."
    assert repo.hole_letzte_szene(conn, 1)["volltext"] == "MARIA:Immer noch da."


def test_fassung_haelt_anbieter_und_modell_fest(conn, einst, tg):
    szene_id = _geplante_szene(conn)
    klm = ModellAttrappe([_antwort("MARIA:Da bin ich.")])

    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")

    fassung = repo.szenenfassungen(conn, szene_id)[-1]
    assert fassung["anbieter"] == "infomaniak"
    assert fassung["modell"] == einst.llm_modell


def test_eine_fassung_wird_nie_geaendert(conn, einst, tg):
    """Nur anhaengen -- wie beim Journal. Es gibt bewusst keine
    Aktualisierungsfunktion."""
    assert not hasattr(repo, "aktualisiere_szenenfassung")
    assert not hasattr(repo, "entferne_szenenfassung")

    szene_id = _geplante_szene(conn)
    klm = ModellAttrappe([
        _antwort("MARIA:Da bin ich."), _antwort("MARIA:Immer noch da."),
    ])
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    erste = dict(repo.szenenfassungen(conn, szene_id)[0])
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")

    assert dict(repo.szenenfassungen(conn, szene_id)[0]) == erste


def test_leerer_lauf_haengt_nichts_an(conn):
    szene_id = _geplante_szene(conn)

    assert repo.haenge_szenenfassung_an(conn, 1, szene_id, "") is None
    assert repo.haenge_szenenfassung_an(conn, 1, szene_id, None) is None
    assert repo.szenenfassungen(conn, szene_id) == []


def test_der_prosalauf_haengt_auch_an(conn):
    """Phase 6 ist ebenfalls ein Szenenlauf."""
    kurzgeschichte.lege_szenen_an(
        conn, 1, [("Am Bahnhof", "Sie warten.", "Sie stehen und warten.")]
    )

    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    fassungen = repo.szenenfassungen(conn, szene_id)
    assert [f["nummer"] for f in fassungen] == [1]
    assert fassungen[0]["volltext"] == "Sie stehen und warten."


# --- Migration einer Alt-Datenbank -----------------------------------------


def test_migration_gibt_bestehenden_szenen_fassung_eins(conn):
    """Damit die Ansicht nie leer aussieht, wo es einen Text gibt."""
    szene_id = repo.lege_szene_an(conn, 1, 1, "Am Bahnhof", None, "MARIA:Da.")

    assert db._migriere_erste_szenenfassung(conn) == 1

    fassungen = repo.szenenfassungen(conn, szene_id)
    assert [(f["nummer"], f["volltext"]) for f in fassungen] == [(1, "MARIA:Da.")]
    assert fassungen[0]["anbieter"] is None


def test_migration_ist_idempotent(conn):
    repo.lege_szene_an(conn, 1, 1, "Am Bahnhof", None, "MARIA:Da.")

    db._migriere_erste_szenenfassung(conn)
    zweiter_lauf = db._migriere_erste_szenenfassung(conn)
    db.initialisiere(conn)

    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    assert zweiter_lauf == 0
    assert len(repo.szenenfassungen(conn, szene_id)) == 1


def test_migration_laesst_szenen_ohne_text_in_ruhe(conn):
    """Eine geplante Szene ohne Volltext ist kein halbes Ergebnis."""
    _geplante_szene(conn)

    assert db._migriere_erste_szenenfassung(conn) == 0


def test_alte_datenbank_laeuft_ohne_datenverlust_durch(tmp_path):
    """Die Zusage: eine bestehende Datenbank verliert nichts."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    db.initialisiere(alt)
    repo.sichere_gruppe(alt, 1, "gruppe1", "Testgruppe")
    repo.setze_arbeitsstand(alt, 1, "begriffe", "Ankommen")
    szene_id = repo.lege_szene_an(alt, 1, 1, "Am Bahnhof", None, "MARIA:Da.")
    alt.execute("DROP TABLE szenenfassung")
    alt.commit()
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)

    assert repo.hole_arbeitsstand(neu, 1)["begriffe"] == "Ankommen"
    assert repo.hole_szenen(neu, 1)[0]["volltext"] == "MARIA:Da."
    assert len(repo.szenenfassungen(neu, szene_id)) == 1
    neu.close()


def test_die_tabelle_faellt_mit_der_gruppe(conn):
    """Jede Tabelle mit ``chat_id`` gehoert in die Loeschzusage."""
    assert "szenenfassung" in db.TABELLEN_MIT_CHAT_ID

    szene_id = repo.lege_szene_an(conn, 1, 1, "Am Bahnhof", None, "MARIA:Da.")
    db._migriere_erste_szenenfassung(conn)
    db.loesche_gruppe(conn, 1)

    assert repo.szenenfassungen(conn, szene_id) == []


# --- Ausspielen: Gruppenseite ----------------------------------------------


def test_gruppenseite_zeigt_fruehere_fassungen(conn, einst, tg):
    """Seit dem 07.09.2026 wird **umgeschaltet** statt aufgeklappt: die Leiste
    nennt jede Fassung, angezeigt wird genau eine. Die fruehere ist damit
    nicht mehr sofort sichtbar, aber einen Klick weit weg -- und der Klick ist
    ein GET auf dieselbe Seite, kein neuer Zustand irgendwo."""
    klm = ModellAttrappe([
        _antwort("MARIA:Da bin ich.", "Erste Fassung."),
        _antwort("MARIA:Immer noch da.", "Kuerzer gemacht."),
    ])
    _geplante_szene(conn)
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    token = repo.stelle_web_token_sicher(conn, 1)
    daten = web_daten.gruppe_nach_token(conn, token)
    szene_id = daten["szenen"][0]["id"]

    seite = web.gruppe_html(daten)

    assert web.TEXT_FASSUNGEN in seite
    # Beschriftet mit der "Anders gemacht"-Zeile des Laufs, der sie schrieb.
    assert "Erste Fassung." in seite
    # Ohne Auswahl steht die aktuelle da, die erste nur als Weg dorthin.
    assert "MARIA:Immer noch da." in seite
    assert web.fassungslink(szene_id, 1).replace("&", "&amp;") in seite

    gewaehlt = web.gruppe_html(daten, fassungswahl={szene_id: 1})

    assert "MARIA:Da bin ich." in gewaehlt


def test_gruppenseite_ohne_fruehere_fassung_ohne_block(conn, einst, tg):
    """Die aktuelle Fassung steht ohnehin oben -- ein Block, der sie noch
    einmal zeigt, waere Doppelung."""
    _geplante_szene(conn)
    szene.schreibe(
        conn, tg, ModellAttrappe([_antwort("MARIA:Da bin ich.")]), einst, 1, "Szene 1",
    )
    token = repo.stelle_web_token_sicher(conn, 1)

    daten = web_daten.gruppe_nach_token(conn, token)

    assert daten["szenen"][0]["fassungen"] == []
    assert web.TEXT_FASSUNGEN not in web.gruppe_html(daten)


def test_gruppenseite_setzt_nichts_zurueck(conn, einst, tg):
    """Zuruecksetzen ist eine Entscheidung mit Datenwirkung und bewusst nicht
    gebaut -- also gibt es dafuer auch kein Formularfeld."""
    from interview_theater import web_schreiben

    assert not any("fassung" in feld for feld in web_schreiben.FELDER)

    _geplante_szene(conn)
    klm = ModellAttrappe([_antwort("MARIA:Eins."), _antwort("MARIA:Zwei.")])
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    token = repo.stelle_web_token_sicher(conn, 1)

    seite = web.gruppe_html(
        web_daten.gruppe_nach_token(conn, token), nonce_wert="n"
    )

    assert "Zuruecksetzen" not in seite and "Zurücksetzen" not in seite


# --- Ausspielen: Chat ------------------------------------------------------


def test_knopf_unter_der_angesehenen_szene(conn, einst, tg):
    _geplante_szene(conn)
    klm = ModellAttrappe([
        _antwort("MARIA:Eins.", "Erste Fassung."),
        _antwort("MARIA:Zwei.", "Kuerzer gemacht."),
    ])
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")

    knoepfe.zeige_szenentext(conn, tg, 1, 1)
    daten = next(
        d for _, _, leiste in tg.knoepfe for t, d in leiste
        if t == knoepfe.TEXT_FASSUNGEN_KNOPF
    )
    knoepfe.behandle(conn, tg, None, None, _druck(daten))

    text = "\n".join(t for _, t in tg.gesendet)
    assert "Fruehere Fassungen von Szene 1:" in text
    assert "MARIA:Eins." in text
    assert "Erste Fassung." in text


def test_ohne_fruehere_fassung_kein_knopf(conn, einst, tg):
    """Kein neuer automatischer Text und kein Knopf, der nichts zeigt."""
    _geplante_szene(conn)
    szene.schreibe(
        conn, tg, ModellAttrappe([_antwort("MARIA:Eins.")]), einst, 1, "Szene 1",
    )
    tg.knoepfe.clear()

    knoepfe.zeige_szenentext(conn, tg, 1, 1)

    beschriftungen = [t for _, _, leiste in tg.knoepfe for t, _ in leiste]
    assert knoepfe.TEXT_FASSUNGEN_KNOPF not in beschriftungen


def test_knopf_ruft_kein_modell(conn, einst, tg):
    """Zusage 2: ``klm=None`` genuegt als Beweis."""
    _geplante_szene(conn)
    klm = ModellAttrappe([_antwort("MARIA:Eins."), _antwort("MARIA:Zwei.")])
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    szene.schreibe(conn, tg, klm, einst, 1, "Szene 1")
    knoepfe.zeige_szenentext(conn, tg, 1, 1)
    daten = next(
        d for _, _, leiste in tg.knoepfe for t, d in leiste
        if t == knoepfe.TEXT_FASSUNGEN_KNOPF
    )
    vorher = klm.aufrufe

    assert knoepfe.behandle(conn, tg, None, None, _druck(daten)) is True
    assert klm.aufrufe == vorher
