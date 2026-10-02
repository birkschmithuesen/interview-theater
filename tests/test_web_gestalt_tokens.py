"""Die Design-Tokens: vollstaendig, umschaltbar, und der Kontrast gerechnet.

Der Kontrasttest ist der Kern dieser Datei. Er liest die Tabelle
``web_gestalt.KONTRAST`` und rechnet fuer jedes deklarierte Paar das
WCAG-Verhaeltnis aus den Tokenwerten -- fuer BEIDE Entwuerfe. Eine Farbe,
die jemand spaeter "nur ein bisschen" abdunkelt, faellt hier auf und nicht
erst an einem Telefon im Sonnenlicht eines Probenraums in Padua.
"""

import re

import pytest

from interview_theater import web_gestalt

FARBE = re.compile(r"^#[0-9a-f]{6}$")


# -- Vollstaendigkeit --------------------------------------------------------


def test_es_gibt_genau_zwei_entwuerfe():
    assert web_gestalt.ENTWUERFE == ("a", "b")
    assert set(web_gestalt.TOKENS) == set(web_gestalt.ENTWUERFE)


def test_beide_entwuerfe_tragen_dieselben_tokennamen():
    """Sonst waere der Tausch kein Tausch: eine Regel des
    Komponenten-CSS liefe beim anderen Entwurf ins Leere."""
    a, b = web_gestalt.TOKENS["a"], web_gestalt.TOKENS["b"]
    assert set(a) == set(b), set(a) ^ set(b)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jeder_entwurf_hat_die_pflichttokens(name):
    tokens = web_gestalt.TOKENS[name]
    for pflicht in ("grund", "grund-2", "grund-3", "linie", "rand",
                    "text", "text-leise", "signal", "signal-tief", "auf-signal",
                    "warn", "auf-warn", "rec", "auf-rec",
                    "radius", "radius-gross", "tippflaeche", "rec-hoehe",
                    "tabs-hoehe", "schrift-lesen", "schrift-tech",
                    "schrift-skript", "takt-schnell", "takt-moment"):
        assert pflicht in tokens, f"{name}: {pflicht} fehlt"


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_farbtokens_sind_sechsstellige_hexwerte(name):
    """Kein ``rgba()``, kein Farbname: der Kontrasttest rechnet damit."""
    for schluessel, wert in web_gestalt.TOKENS[name].items():
        if schluessel in web_gestalt.FARBTOKENS:
            assert FARBE.match(wert), f"{name}.{schluessel} = {wert!r}"


# -- Kontrast ----------------------------------------------------------------


def test_die_rechnung_stimmt_an_zwei_bekannten_werten():
    """Schwarz auf Weiss ist 21, Weiss auf Weiss ist 1 -- wenn das nicht
    herauskommt, misst der Test unten gar nichts."""
    assert round(web_gestalt.kontrastverhaeltnis("#000000", "#ffffff"), 2) == 21.0
    assert round(web_gestalt.kontrastverhaeltnis("#ffffff", "#ffffff"), 2) == 1.0


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jedes_deklarierte_paar_haelt_seine_wcag_schwelle(name):
    tokens = web_gestalt.TOKENS[name]
    schwach = []
    for paar in web_gestalt.KONTRAST:
        wert = web_gestalt.kontrastverhaeltnis(tokens[paar.vorn], tokens[paar.hinten])
        if wert < paar.mindest:
            schwach.append(
                f"{name}: {paar.vorn} auf {paar.hinten} ({paar.zweck}) "
                f"= {wert:.2f}, soll >= {paar.mindest}"
            )
    assert not schwach, "\n".join(schwach)


def test_die_tabelle_deckt_die_tragenden_paare_ab():
    """Eine Tabelle, die man leer machen kann, prueft nichts. Diese Zeile
    haelt fest, WELCHE Paare drinstehen muessen."""
    paare = {(p.vorn, p.hinten) for p in web_gestalt.KONTRAST}
    for pflicht in (("text", "grund"), ("text", "grund-2"),
                    ("text-leise", "grund"), ("signal", "grund"),
                    ("auf-signal", "signal"), ("warn", "grund"),
                    ("auf-rec", "rec"), ("rec", "grund"), ("rand", "grund")):
        assert pflicht in paare, pflicht


def test_linie_steht_bewusst_nicht_in_der_tabelle():
    """``--linie`` ist eine dekorative Trennlinie zwischen Listenzeilen --
    WCAG 1.4.11 gilt fuer BEDEUTUNGSTRAGENDE Komponentengrenzen. Wo ein
    Rand einen Zustand traegt (Knopfrahmen), steht ``--rand``, und der ist
    in der Tabelle. Diese Zeile haelt die Entscheidung fest, damit sie
    niemand als Luecke liest."""
    paare = {p.vorn for p in web_gestalt.KONTRAST}
    assert "linie" not in paare
    assert "rand" in paare


# -- Die Umschaltung ---------------------------------------------------------


def test_ohne_umgebung_gilt_die_vorgabe(monkeypatch):
    monkeypatch.delenv(web_gestalt.UMGEBUNG, raising=False)
    assert web_gestalt.entwurf() == web_gestalt.VORGABE_ENTWURF


def test_die_umgebung_schaltet_um(monkeypatch):
    monkeypatch.setenv(web_gestalt.UMGEBUNG, "b")
    assert web_gestalt.entwurf() == "b"


@pytest.mark.parametrize("wert", ["", "c", "A B", "0"])
def test_ein_unbekannter_wert_faellt_auf_die_vorgabe_zurueck(monkeypatch, wert):
    """Ein Tippfehler in einer Env-Datei soll am Workshoptag keine
    ungestylte Seite ergeben."""
    monkeypatch.setenv(web_gestalt.UMGEBUNG, wert)
    assert web_gestalt.entwurf() == web_gestalt.VORGABE_ENTWURF


def test_grossschreibung_ist_egal(monkeypatch):
    monkeypatch.setenv(web_gestalt.UMGEBUNG, "B")
    assert web_gestalt.entwurf() == "b"


# -- Der ausgegebene Block ---------------------------------------------------


def test_tokens_css_ist_ein_root_block():
    css = web_gestalt.tokens_css("a")
    assert css.strip().startswith(":root {")
    assert css.strip().endswith("}")


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jedes_token_steht_als_custom_property_drin(name):
    css = web_gestalt.tokens_css(name)
    for schluessel, wert in web_gestalt.TOKENS[name].items():
        assert f"--{schluessel}: {wert};" in css, schluessel


def test_tokens_css_ohne_argument_nimmt_den_aktiven_entwurf(monkeypatch):
    monkeypatch.setenv(web_gestalt.UMGEBUNG, "b")
    assert web_gestalt.TOKENS["b"]["grund"] in web_gestalt.tokens_css()
    assert web_gestalt.TOKENS["a"]["grund"] not in web_gestalt.tokens_css()
