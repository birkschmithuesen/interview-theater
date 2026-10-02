"""Phase 6: das Budget im Prosa-Prompt (30.09.2026, Karte R).

Zwei Zusagen in einer Datei: ohne aktives Profil ist die Systemanweisung
**zeichengleich** zu dem Stand, der auf ``d8deb6c`` gemessen wurde -- und mit
aktivem Profil tritt die Summe an die Stelle der festen Zeile "Insgesamt
1.500 bis 3.500 Woerter", waehrend die Liste je Abschnitt im Nutzertext steht.
"""

import hashlib

import pytest

from interview_theater import kurzgeschichte, laengen, repo, workshop

#: Selbst gemessen am 30.09.2026 auf ``d8deb6c``, vor jeder Aenderung dieser
#: Karte. Der Massstab fuer Dortmund -- er steht hier und nicht in einer
#: Golden-Datei, weil eine Zahl in einem Test schwerer zu uebersehen ist.
SYSTEM_SHA_D8DEB6C = "704119e3dd886eef7ac619511b4ab70cc7c6fb6858a8618e4ee2da19ffddc729"
SYSTEM_LAENGE_D8DEB6C = 12785


@pytest.fixture(autouse=True)
def ohne_profil(monkeypatch):
    from interview_theater import anweisungen
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Dortmund bleibt zeichengleich ----------------------------------------


def test_ohne_budget_ist_die_systemanweisung_zeichengleich():
    text = kurzgeschichte.systemanweisung()
    assert len(text) == SYSTEM_LAENGE_D8DEB6C
    assert _sha(text) == SYSTEM_SHA_D8DEB6C


def test_budget_none_ist_derselbe_text_wie_kein_argument():
    assert kurzgeschichte.systemanweisung(None) == kurzgeschichte.systemanweisung()


def test_die_ersetzbare_zeile_steht_wirklich_in_der_anweisung():
    """Eine Ersetzung, die ins Leere greift, ist ein stiller Durchfall: der
    Prompt behielte die feste Zahl, das Budget stuende daneben, und beides
    waere wahr. Deshalb ist die Anwesenheit der Zeile ein Test und keine
    Annahme."""
    anweisung = getattr(kurzgeschichte, "T", kurzgeschichte).ANWEISUNG
    zeile = getattr(kurzgeschichte, "T", kurzgeschichte).ZEILE_GESAMTLAENGE
    assert anweisung.count(zeile) == 1, "genau einmal, sonst ersetzt es zu viel"


def test_die_ersetzbare_zeile_steht_auch_englisch_genau_einmal(monkeypatch):
    """Padua liest ``ANWEISUNG`` und ``ZEILE_GESAMTLAENGE`` aus
    ``sprachen/en/texte.toml``. Greift die Ersetzung dort ins Leere, behielte
    gerade das Profil mit Budget die feste Zahl."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert kurzgeschichte.T.ANWEISUNG.count(
        kurzgeschichte.T.ZEILE_GESAMTLAENGE) == 1
    text = kurzgeschichte.systemanweisung([100, 450, 120])
    assert kurzgeschichte.T.ZEILE_GESAMTLAENGE not in text
    assert "670" in text


# --- Mit Budget -----------------------------------------------------------


def test_mit_budget_tritt_die_summe_an_die_stelle_der_festen_zahl():
    text = kurzgeschichte.systemanweisung([100, 450, 120])
    zeile = getattr(kurzgeschichte, "T", kurzgeschichte).ZEILE_GESAMTLAENGE
    assert zeile not in text, "die feste Zahl steht noch da"
    assert "670" in text
    # Abweichung vom Plan: ``formen/prosa.md`` nennt "1.500 bis 3.500" selbst,
    # und diese Zeile bleibt laut Plan ("Nicht im Umfang") stehen -- der
    # Vorrang-Satz im Nutzertext uebersteuert sie. Verschwinden muss also
    # genau die EINE ersetzbare Stelle aus ``ANWEISUNG``.
    ohne = kurzgeschichte.systemanweisung()
    assert text.count("1.500 bis 3.500") == ohne.count("1.500 bis 3.500") - 1


def test_der_prompt_nennt_die_gesamtlaenge_nur_einmal():
    """Prompt-Audit-Regel: ein Fakt hat genau eine Stelle. Die Summe steht in
    der Systemanweisung, die Liste je Abschnitt im Nutzertext."""
    text = kurzgeschichte.systemanweisung([100, 450, 120])
    assert text.count("670") == 1


# --- Die Eintraege aus den Szenen -----------------------------------------


@pytest.fixture
def drei_szenen(conn, monkeypatch):
    """Drei Szenen, wie sie beim Eintritt in Phase 6 dastehen: Nummer, Titel,
    Form teils bestaetigt, teils nur vorgeschlagen, kein Text."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    for nummer, form, vorschlag in ((1, "chor", None), (2, None, "dialog"),
                                    (3, None, None)):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        if form:
            repo.setze_szenenfeld(conn, szene_id, "form", form)
        if vorschlag:
            repo.setze_szenenfeld(conn, szene_id, "form_vorschlag", vorschlag)
    return conn


def test_die_eintraege_lesen_form_bestaetigt_vor_vorgeschlagen(drei_szenen):
    eintraege = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    assert [n for n, _f, _b in eintraege] == [1, 2, 3]
    assert [f for _n, f, _b in eintraege] == ["chor", "dialog",
                                              workshop.form_vorgabe()]
    assert all(b > 0 for _n, _f, b in eintraege)


def test_die_eintraege_haengen_nicht_an_der_zahl_der_szenen(drei_szenen):
    """Zyklisches Muster: eine vierte Szene darf das Budget von Szene 1 nicht
    verschieben -- sonst rechnet das Nachzaehlen gegen eine andere Zahl."""
    vorher = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    repo.stelle_szene_sicher(drei_szenen, 1, 4)
    nachher = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    assert nachher[:3] == vorher
    assert len(nachher) == 4


def test_ohne_aktives_profil_gibt_es_keine_eintraege(conn, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    repo.stelle_szene_sicher(conn, 1, 1)
    assert kurzgeschichte.budget_eintraege(conn, 1) == []


def test_der_faktor_verkuerzt_die_eintraege(drei_szenen):
    voll = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    kurz = kurzgeschichte.budget_eintraege(drei_szenen, 1, faktor=0.25)
    assert [b for _n, _f, b in kurz] != [b for _n, _f, b in voll]
    assert all(k <= v for (_a, _b, k), (_c, _d, v) in zip(kurz, voll))


# --- Der Nutzertext -------------------------------------------------------


def test_ohne_eintraege_bleibt_der_nutzertext_zeichengleich(conn, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    ohne = kurzgeschichte.baue_nutzertext(conn, 1)
    mit_none = kurzgeschichte.baue_nutzertext(conn, 1, eintraege=None)
    leer = kurzgeschichte.baue_nutzertext(conn, 1, eintraege=[])
    assert ohne == mit_none == leer


def test_mit_eintraegen_steht_der_block_im_nutzertext(drei_szenen):
    repo.setze_arbeitsstand(drei_szenen, 1, "rahmen", "Am Kanal, nachts")
    eintraege = kurzgeschichte.budget_eintraege(drei_szenen, 1)
    text = kurzgeschichte.baue_nutzertext(drei_szenen, 1, eintraege=eintraege)
    # Padua spricht Englisch: der Block kommt ueber ``T`` in der aktiven
    # Sprache (Abweichung vom Plan, der die deutsche Konstante pruefte).
    assert laengen.T.BLOCK_KOPF_PROSA in text
    assert laengen.T.SATZ_BINDUNG.format(anzahl=3) in text
    for nummer, form, budget in eintraege:
        assert f"{budget}" in text
        assert form in text


def test_der_schnappschuss_deckt_die_prosa_systemanweisung_ab():
    """``scripts/prompt_schnappschuss.py`` ist der Waechter gegen ein undichtes
    Profil. Was dort nicht steht, prueft der Bitgleichheits-Test nicht --
    und diese Anweisung stand bis heute nicht drin."""
    from scripts import prompt_schnappschuss
    namen = {name for name, _ in prompt_schnappschuss.teile()}
    assert "kurzgeschichte.systemanweisung()" in namen


# --- Der synchrone Einstieg (Aufgabe 7) -----------------------------------

from test_knoepfe import TelegramAttrappe  # noqa: E402


@pytest.fixture
def tg():
    return TelegramAttrappe()


class ProsaAttrappe:
    """Liefert eine Kurzgeschichte und merkt jeden Aufruf samt ``art``."""

    ANTWORT = (
        "## 1. Ankunft\nZusammenfassung: Sie kommt an.\n\nText eins.\n\n"
        "## 2. Streit\nZusammenfassung: Es kracht.\n\nText zwei.\n"
    )

    def __init__(self, antwort=None):
        self.antwort = antwort or self.ANTWORT
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return self.antwort


@pytest.fixture
def prosa_bereit(conn, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    for nummer in (1, 2):
        repo.stelle_szene_sicher(conn, 1, nummer)
    return conn


def test_hole_text_ruft_nur_das_modell(prosa_bereit, einst):
    """Kein Speichern, keine Chatnachricht -- der Nachpass muss erst pruefen
    duerfen, bevor etwas in der Datenbank steht."""
    klm = ProsaAttrappe()
    vorher = [dict(s) for s in repo.hole_szenen(prosa_bereit, 1)]
    text = kurzgeschichte.hole_text(prosa_bereit, klm, einst, 1)
    assert "Ankunft" in text
    assert len(klm.aufrufe) == 1
    nachher = [dict(s) for s in repo.hole_szenen(prosa_bereit, 1)]
    assert [s["prosa"] for s in nachher] == [s["prosa"] for s in vorher]


def test_hole_text_gibt_die_art_weiter(prosa_bereit, einst):
    """Eigene ``art``-Werte machen die Nachpass-Laeufe in der Tabelle
    ``aufruf`` getrennt zaehlbar -- so wie ``dramaturgie_b1`` es vormacht."""
    klm = ProsaAttrappe()
    kurzgeschichte.hole_text(prosa_bereit, klm, einst, 1, art="kurzgeschichte_nachpass")
    assert klm.aufrufe[0]["art"] == "kurzgeschichte_nachpass"


def test_hole_text_legt_das_budget_in_den_nutzertext(prosa_bereit, einst):
    klm = ProsaAttrappe()
    eintraege = kurzgeschichte.budget_eintraege(prosa_bereit, 1)
    kurzgeschichte.hole_text(prosa_bereit, klm, einst, 1, eintraege=eintraege)
    assert laengen.T.BLOCK_KOPF_PROSA in klm.aufrufe[0]["nutzer"]
    assert laengen.gesamtzeile([b for _n, _f, b in eintraege]) in \
        klm.aufrufe[0]["system"]


def test_schreibe_speichert_und_meldet(prosa_bereit, einst, tg):
    klm = ProsaAttrappe()
    nummern = kurzgeschichte.schreibe(prosa_bereit, tg, klm, einst, 1)
    assert nummern == [1, 2]
    prosa = {s["nummer"]: (s["prosa"] or "") for s in repo.hole_szenen(prosa_bereit, 1)}
    assert "Text eins" in prosa[1] and "Text zwei" in prosa[2]


def test_schreibe_haengt_die_journalzeile_mit_seed_an(prosa_bereit, einst, tg):
    """Reproduzierbar heisst nachrechenbar: Seed, Muster, Budgets stehen in
    EINER angehaengten Journalzeile."""
    klm = ProsaAttrappe()
    kurzgeschichte.schreibe(prosa_bereit, tg, klm, einst, 1)
    texte = [j["text"] for j in prosa_bereit.execute(
        "SELECT text FROM journal WHERE chat_id = 1").fetchall()]
    assert any("seed 1" in t or "Seed 1" in t for t in texte), texte


def test_starte_verhaelt_sich_wie_vorher(prosa_bereit, einst, tg):
    """Die Zerlegung darf am aeusseren Weg nichts aendern: ein Thread, eine
    Sperre, dieselbe Meldung."""
    klm = ProsaAttrappe()
    thread = kurzgeschichte.starte(prosa_bereit, tg, klm, einst, 1)
    assert thread is not None
    thread.join(timeout=20)
    assert kurzgeschichte.laeuft(1) is False
    fertig = kurzgeschichte.T._TEXT_FERTIG.format(anzahl=2)
    assert any(fertig in t for t in tg.texte), tg.texte
