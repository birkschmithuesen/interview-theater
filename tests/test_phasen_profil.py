"""Phasen und Phasentexte kommen aus dem Profil -- generisch geprueft.

Was hier steht, prueft **Struktur**: dass die Liste lueckenlos ist, dass ein
anderes Profil wirklich andere Stationen ergibt, dass die Mechanik
(``nummer_fuer``, ``meldung``, ``eintritt``) der Profilliste folgt und nicht
einer Zahl im Code. Der **Wortlaut** fuer Dortmund steht in
``tests/profile/test_dortmund.py`` und im Fingerabdruck
(``tests/test_profil_bitgleich.py``), der ihn Zeichen fuer Zeichen gegen den
Stand vor dem Umbau haelt.
"""

import pytest

from interview_theater import anweisungen, phasen, phasentexte, workshop

DREI = """\
erste = 1
meldung = "Ora siamo a {bezeichnung}."

[[phase]]
nummer = 1
name = "Parole"
satz = "Raccogliere le parole."
stichwoerter = ["parole", "parola"]

[[phase]]
nummer = 2
name = "Domande"
satz = "Sviluppare le domande."
stichwoerter = ["domande", "domanda"]

[[phase]]
nummer = 3
name = "Interviste"
satz = "Fare le interviste."
stichwoerter = ["interviste", "intervista"]
"""


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


@pytest.fixture
def drei_phasen(tmp_path, monkeypatch):
    verz = tmp_path / "drei-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "Test"\n', encoding="utf-8")
    (verz / workshop.PHASEN_DATEI).write_text(DREI, encoding="utf-8")
    (verz / workshop.PHASENTEXTE_DATEI).write_text(
        'letzte_offen = "ancora aperto"\n'
        '[einleitung]\n1 = "Prima"\n2 = "Seconda"\n3 = "Terza"\n',
        encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "drei-2026")
    workshop.vergiss()
    return verz


# --- Struktur ------------------------------------------------------------

def test_die_nummern_sind_lueckenlos_und_fangen_bei_eins_an():
    nummern = [n for n, _, _ in phasen.PHASEN]
    assert nummern == list(range(1, len(nummern) + 1))
    assert phasen.ERSTE == 1
    assert phasen.LETZTE == nummern[-1]


def test_zu_jeder_phase_gibt_es_eine_einleitung_und_einen_prompt():
    for nummer, name, satz in phasen.PHASEN:
        assert name.strip() and satz.strip(), nummer
        assert phasentexte.EINLEITUNGEN[nummer].strip(), nummer
        assert anweisungen.hole_optional(f"phasen/{nummer}"), nummer


def test_keine_einleitung_traegt_noch_einen_platzhalter():
    for nummer, text in phasentexte.EINLEITUNGEN.items():
        assert "{{" not in text, nummer
    assert "{{" not in phasentexte.EINLEITUNG_LETZTE_OFFEN


def test_die_einleitungen_bleiben_unter_der_grenze():
    for nummer, text in phasentexte.EINLEITUNGEN.items():
        assert len(text) <= phasentexte.EINLEITUNG_GRENZE, (nummer, len(text))


# --- Ein anderes Profil --------------------------------------------------

def test_ein_anderes_profil_hat_andere_phasen(drei_phasen):
    assert phasen.PHASEN == (
        (1, "Parole", "Raccogliere le parole."),
        (2, "Domande", "Sviluppare le domande."),
        (3, "Interviste", "Fare le interviste."),
    )
    assert phasen.LETZTE == 3
    assert phasen.bezeichnung(2) == "2 · Domande"
    assert phasen.meldung(2) == "Ora siamo a 2 · Domande."


def test_das_tolerante_mapping_folgt_dem_profil(drei_phasen):
    assert phasen.nummer_fuer("domande") == 2
    assert phasen.nummer_fuer("siamo alle interviste") == 3
    assert phasen.nummer_fuer("Fragen") is None
    assert phasen.nummer_fuer(4) is None
    assert phasen.nummer_fuer(3) == 3


def test_die_einleitungen_folgen_dem_profil(drei_phasen):
    assert phasentexte.EINLEITUNGEN == {1: "Prima", 2: "Seconda", 3: "Terza"}
    assert phasentexte.EINLEITUNG_LETZTE_OFFEN == "ancora aperto"


def test_die_kopfzeile_zaehlt_die_phasen_des_profils(drei_phasen, conn):
    text = phasentexte.eintritt(conn, 1, 2)
    assert text.startswith("▶️ Phase 2 von 3 · Domande")


# --- Fehlerbild ----------------------------------------------------------

def test_luecke_in_den_nummern_bricht_ab(tmp_path, monkeypatch):
    verz = tmp_path / "luecke-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "x"\n', encoding="utf-8")
    (verz / workshop.PHASEN_DATEI).write_text(
        '[[phase]]\nnummer = 1\nname = "A"\n[[phase]]\nnummer = 3\nname = "B"\n',
        encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "luecke-2026")
    workshop.vergiss()
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert "lueckenlos" in str(fehler.value)


def test_einleitung_fuer_eine_phase_die_es_nicht_gibt_bricht_ab(tmp_path, monkeypatch):
    verz = tmp_path / "zuviel-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "x"\n', encoding="utf-8")
    (verz / workshop.PHASEN_DATEI).write_text(
        '[[phase]]\nnummer = 1\nname = "A"\n', encoding="utf-8")
    (verz / workshop.PHASENTEXTE_DATEI).write_text(
        '[einleitung]\n1 = "a"\n9 = "b"\n', encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "zuviel-2026")
    workshop.vergiss()
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert "9" in str(fehler.value)


def test_dortmund_traegt_dieselben_phasen_wie_die_vorgabe(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    profil = workshop.aktiv()
    assert workshop.phasenliste(profil) == workshop.phasenliste(workshop.VORGABE)
    assert workshop.phasen_stichwoerter(profil) == workshop.phasen_stichwoerter(workshop.VORGABE)
    assert workshop.phasen_mehrdeutig(profil) == workshop.phasen_mehrdeutig(workshop.VORGABE)
    assert workshop.phasen_meldung(profil) == workshop.phasen_meldung(workshop.VORGABE)
    assert workshop.phase_erste(profil) == workshop.phase_erste(workshop.VORGABE)
    assert (workshop.phasentexte_einleitungen(profil)
            == workshop.phasentexte_einleitungen(workshop.VORGABE))
    assert (workshop.phasentexte_letzte_offen(profil)
            == workshop.phasentexte_letzte_offen(workshop.VORGABE))
