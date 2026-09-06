"""Tests fuer die Sprechanteile je Figur (06.09.2026).

Der kritische Punkt ist das Sprecherzeilen-Parsing, und gemessen wird es
hier an **vier realistischen Formatierungen** plus den echten Opus-Texten aus
``docs/prompt-audit/2026-09-06/opus-thinking-texte/`` (PII-frei und im
Repository). Dazu die drei Faelle, in denen nichts oder fast nichts
herauskommen darf: eine Szene ohne erkennbare Sprecher, eine Figur ohne jede
Replik, eine Szene ohne Volltext.

Kein Netzzugriff, kein Sprachmodell -- die Zaehlung ist deterministisch.
"""

import glob

import pytest

from interview_theater import knoepfe, repo, sprecher, szene, web, web_daten

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


NAMEN = {"leyla", "cemre", "aylin", "zeynep"}


# --- vier Formatierungen ---------------------------------------------------


DICHT = """LEYLA:Gelesen. Steht klein drunter, grau.
CEMRE:Sie geht nicht.
AYLIN:Also ich sag ja nur."""

MIT_LEERZEICHEN = """LEYLA: Gelesen. Steht klein drunter, grau.
CEMRE: Sie geht nicht.
AYLIN: Also ich sag ja nur."""

MIT_REGIE = """(Cemre nimmt Leyla das Handy aus der Hand.)

LEYLA:(dreht das Handy um)Gelesen.

CEMRE:(liest)Sie geht nicht.

AYLIN:Also ich sag ja nur."""

MEHRZEILIG = """Schulhof, Freitagnachmittag. Die Schule ist leer.

LEYLA:
Gelesen, steht klein drunter
grau wie der Tag

CEMRE:Sie geht nicht.

AYLIN:Also ich sag ja nur."""


@pytest.mark.parametrize(
    "text", [DICHT, MIT_LEERZEICHEN, MIT_REGIE, MEHRZEILIG],
    ids=["dicht", "mit-leerzeichen", "mit-regie", "mehrzeilig"],
)
def test_vier_formatierungen_finden_dieselben_drei_sprecher(text):
    """Dieselbe Szene in vier Schreibweisen -- dieselben drei Sprecher."""
    ergebnis = sprecher.zaehle_szene(text, NAMEN)

    assert sorted(ergebnis) == ["AYLIN", "CEMRE", "LEYLA"]
    assert all(e["repliken"] == 1 for e in ergebnis.values())


def test_regieanweisungen_zaehlen_nicht_als_gesprochenes_wort():
    """"(dreht das Handy um)Gelesen." ist ein Wort, nicht fuenf."""
    ergebnis = sprecher.zaehle_szene(MIT_REGIE, NAMEN)

    assert ergebnis["LEYLA"]["worte"] == 1


def test_vorspann_vor_der_ersten_sprecherzeile_faellt_weg():
    """Die Ortsangabe gehoert keiner Figur."""
    ergebnis = sprecher.zaehle_szene(MEHRZEILIG, NAMEN)

    assert "Schulhof" not in "".join(ergebnis)
    assert ergebnis["LEYLA"]["worte"] == 8


# --- die Regel und ihre Grenze ---------------------------------------------


def test_normaler_satz_mit_doppelpunkt_ist_keine_sprecherzeile():
    assert sprecher.sprecher_der_zeile("Sie sagt: nein.", NAMEN) is None


def test_name_aus_der_figurenliste_auch_klein_geschrieben():
    assert sprecher.sprecher_der_zeile("Leyla: Gelesen.", NAMEN) == "Leyla"


def test_grossgeschriebener_name_ohne_figurenliste():
    assert sprecher.sprecher_der_zeile("MIRA:Gelesen.", set()) == "MIRA"


def test_bekannte_grenze_name_mit_punkt_wird_nicht_erkannt():
    """Ehrlich benannt im Docstring von ``sprecher.py``: ``FRAU K.:`` faellt
    durch. Der Test haelt die Grenze fest, damit sie niemand fuer einen
    Zufall haelt."""
    assert sprecher.sprecher_der_zeile("FRAU K.:Guten Tag.", set()) is None


def test_bekannte_grenze_name_mit_komma_wird_nicht_erkannt():
    assert sprecher.sprecher_der_zeile("MIRA, LEISE:Gelesen.", set()) is None


def test_szenenueberschrift_ist_kein_sprecher():
    """Gemessen an den echten Opus-Texten: ``SZENE 1: … ca. 10 min`` stand
    ueber jedem Text und zaehlte ohne diese Regel mit rund 30 Woertern mit."""
    assert sprecher.sprecher_der_zeile(
        "SZENE 1: EINUNDFUENFZIG STUNDEN ca. 10 min", NAMEN
    ) is None


# --- die drei Faelle, in denen nichts herauskommt --------------------------


def test_szene_ohne_erkennbare_sprecher_liefert_gar_nichts():
    """Lied, Rap, Chor koennen ohne Sprecherkopf geschrieben sein -- dann
    lieber nichts als etwas Falsches."""
    lied = "Einundfuenfzig Stunden\nund keine Antwort\nder Bus faehrt ohne uns"

    assert sprecher.zaehle_szene(lied, NAMEN) is None


def test_szene_ohne_volltext_liefert_gar_nichts():
    assert sprecher.zaehle_szene("", NAMEN) is None
    assert sprecher.zaehle_szene(None, NAMEN) is None


def test_figur_ohne_jede_replik_steht_mit_null_da():
    """Genau dafuer gibt es die Zaehlung: die Spielerin mit vier Zeilen soll
    es vor der Probe sehen -- also auch die mit null."""
    daten = sprecher.anteile(
        [{"nummer": 1, "volltext": DICHT}],
        [{"name": n} for n in ("Leyla", "Cemre", "Aylin", "Zeynep")],
    )

    zeynep = next(f for f in daten["figuren"] if f["name"] == "Zeynep")
    assert zeynep == {
        "name": "Zeynep", "worte": 0, "repliken": 0, "szenen": 0, "anteil": 0.0,
    }


def test_ohne_zaehlbare_szene_bleibt_alles_leer():
    """Kein Szenentext, keine Zahlen -- und damit kein Abschnitt."""
    daten = sprecher.anteile(
        [{"nummer": 1, "volltext": None}, {"nummer": 2, "volltext": "La la la"}],
        [{"name": "Leyla"}],
    )

    assert daten == {"szenen": 0, "worte": 0, "figuren": []}


def test_nicht_zaehlbare_szene_zaehlt_nicht_in_den_nenner():
    """"1 von 2 Szenen" -- gezaehlt werden nur Szenen mit Sprecherzeilen."""
    daten = sprecher.anteile(
        [{"nummer": 1, "volltext": DICHT}, {"nummer": 2, "volltext": "La la la"}],
        [{"name": "Leyla"}],
    )

    assert daten["szenen"] == 1


# --- echte Szenentexte -----------------------------------------------------


def _echte_szenen():
    szenen = []
    for pfad in sorted(
        glob.glob("docs/prompt-audit/2026-09-06/opus-thinking-texte/*-lauf*.txt")
    ):
        with open(pfad, encoding="utf-8") as datei:
            volltext = szene.zerlege(datei.read())[4]
        szenen.append({"nummer": len(szenen) + 1, "volltext": volltext})
    return szenen


def test_echte_opus_texte_werden_vollstaendig_gelesen():
    """Sechs echte Szenentexte aus dem Prompt-Audit -- vier Figuren, keine
    erfundene."""
    szenen = _echte_szenen()
    assert len(szenen) == 6

    daten = sprecher.anteile(
        szenen, [{"name": n} for n in ("Leyla", "Cemre", "Aylin", "Zeynep")]
    )

    assert daten["szenen"] == 6
    assert {f["name"] for f in daten["figuren"]} == {
        "Leyla", "Cemre", "Aylin", "Zeynep"
    }
    assert all(f["szenen"] == 6 for f in daten["figuren"])
    assert abs(sum(f["anteil"] for f in daten["figuren"]) - 100) < 0.5


def test_echte_texte_ohne_figurenliste_finden_dieselben_sprecher():
    """Auch ohne Figurenliste: die Namen stehen in Grossbuchstaben da."""
    ergebnis = sprecher.zaehle_szene(_echte_szenen()[0]["volltext"], set())

    assert sorted(ergebnis) == ["AYLIN", "CEMRE", "LEYLA", "ZEYNEP"]


# --- Ausspielen ------------------------------------------------------------


def _mit_szene(conn, volltext, chat_id=1):
    for name in ("Leyla", "Cemre", "Aylin", "Zeynep"):
        repo.setze_figur(conn, chat_id, name, f"{name}, sechzehn.")
    szene_id = repo.stelle_szene_sicher(conn, chat_id, 1)
    repo.aktualisiere_szene(conn, szene_id, "Warten", None, volltext, None)
    return szene_id


def test_gruppenseite_zeigt_die_liste_und_den_hinweis(conn):
    _mit_szene(conn, DICHT)
    token = repo.stelle_web_token_sicher(conn, 1)

    daten = web_daten.gruppe_nach_token(conn, token)
    seite = web.gruppe_html(daten)

    assert sprecher.UEBERSCHRIFT in seite
    assert "Zeynep spricht in 0 von 1 Szenen, 0 % der Worte." in seite


def test_gruppenseite_ohne_zaehlbare_szene_ohne_abschnitt(conn):
    _mit_szene(conn, "La la la")
    token = repo.stelle_web_token_sicher(conn, 1)

    daten = web_daten.gruppe_nach_token(conn, token)

    assert daten["sprechanteile"]["szenen"] == 0
    assert sprecher.UEBERSCHRIFT not in web.gruppe_html(daten)


def test_kein_szenentext_im_abschnitt(conn):
    """Die Zahlen gehen aufs Handy, der Satz aus der Szene nicht -- der
    Abschnitt zeigt nur Name, Anteil, Repliken, Szenen."""
    _mit_szene(conn, DICHT)
    token = repo.stelle_web_token_sicher(conn, 1)

    seite = web._sprechanteile_html(
        web_daten.sprechanteile(conn, 1)
    )

    assert "Steht klein drunter" not in seite
    assert token


def test_durchlauf_knopf_zeigt_die_anteile(conn, tg):
    """Der Durchlauf ist der Ort, an dem die Gruppe das Stueck als Ganzes
    ansieht -- dort haengt die Zeile."""
    _mit_szene(conn, DICHT)

    knoepfe.biete_durchlauf(conn, tg, 1)
    daten = next(
        d for _, _, leiste in tg.knoepfe for t, d in leiste
        if t == knoepfe.TEXT_SPRECHANTEILE_KNOPF
    )
    knoepfe.behandle(conn, tg, None, None, _druck(daten))

    text = "\n".join(t for _, t in tg.gesendet)
    assert f"{sprecher.UEBERSCHRIFT} ueber 1 Szenen:" in text
    assert "Leyla:" in text


def test_durchlauf_knopf_ruft_kein_modell(conn, tg):
    """Zusage 2: kein Modellaufruf in einem Knopf-Handler. ``klm=None``
    genuegt als Beweis -- ein Aufruf wuerde hier scheitern."""
    _mit_szene(conn, DICHT)
    knoepfe.biete_durchlauf(conn, tg, 1)
    daten = next(
        d for _, _, leiste in tg.knoepfe for t, d in leiste
        if t == knoepfe.TEXT_SPRECHANTEILE_KNOPF
    )

    assert knoepfe.behandle(conn, tg, None, None, _druck(daten)) is True


def test_ohne_szenentext_sagt_der_knopf_das(conn, tg):
    """Kein Platzhalter mit Nullen: eine Zeile, die sagt, was fehlt."""
    _mit_szene(conn, "La la la")
    knoepfe.biete_durchlauf(conn, tg, 1)
    daten = next(
        d for _, _, leiste in tg.knoepfe for t, d in leiste
        if t == knoepfe.TEXT_SPRECHANTEILE_KNOPF
    )
    knoepfe.behandle(conn, tg, None, None, _druck(daten))

    assert sprecher.TEXT_LEER in "\n".join(t for _, t in tg.gesendet)
