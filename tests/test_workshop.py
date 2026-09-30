"""Der Profil-Lader: Auswahl ueber IT_WORKSHOP, Vorgabe, Fehlerbild.

Die Zusage, um die es hier geht, steht in ``interview_theater/workshop.py``:
ohne Variable gilt das eingebaute Vorgabeprofil, mit
``IT_WORKSHOP=dortmund-2026`` gilt ein Profil mit denselben Werten -- und ein
kaputtes Profil bricht den Start ab, statt halb zu starten.
"""

import pytest

from interview_theater import workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    """Kein Profil aus einem frueheren Test, keine Variable aus der Umgebung."""
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_ohne_variable_gilt_das_eingebaute_profil():
    profil = workshop.aktiv()
    assert profil.name == workshop.VORGABE_NAME
    assert profil.verzeichnis is None
    assert profil.wert("zielgruppe.beschreibung") == "junge Frauen zwischen 15 und 18 Jahren"


def test_leere_variable_gilt_wie_keine(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "   ")
    assert workshop.aktiv() is workshop.VORGABE


def test_dortmund_traegt_dieselben_werte_wie_die_vorgabe(monkeypatch):
    """Die Kernzusage des Umbaus, als Test statt als Absichtserklaerung."""
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    profil = workshop.aktiv()
    assert profil.name == "dortmund-2026"
    assert _entpacke(profil.werte) == workshop.VORGABE_WERTE


def _entpacke(wert):
    """Ein eingefrorener Baum wieder als dict/list -- fuer den Vergleich."""
    if hasattr(wert, "items"):
        return {k: _entpacke(v) for k, v in wert.items()}
    if isinstance(wert, tuple):
        return [_entpacke(v) for v in wert]
    return wert


def test_profil_ist_eingefroren(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    profil = workshop.aktiv()
    with pytest.raises(TypeError):
        profil.werte["beschreibung"] = "andere"
    with pytest.raises(TypeError):
        profil.werte["sprache"]["code"] = "it"


def test_wert_mit_punktpfad_und_vorgabe():
    profil = workshop.VORGABE
    assert profil.wert("sprache.anrede") == "ihr"
    assert profil.wert("gibtsnicht") is None
    assert profil.wert("sprache.gibtsnicht", "ersatz") == "ersatz"
    assert profil.wert("sprache.code.tiefer", "ersatz") == "ersatz"


def test_fehlendes_profil_bricht_mit_klarer_meldung_ab(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "gibtsnicht-2026")
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    text = str(fehler.value)
    assert "gibtsnicht-2026" in text and "IT_WORKSHOP" in text


def test_profilname_darf_nicht_aus_dem_verzeichnis_zeigen(monkeypatch):
    for boese in ("../../etc", "a/b", ".versteckt", ""):
        monkeypatch.setenv(workshop.VARIABLE, boese)
        workshop.vergiss()
        if not boese.strip():
            assert workshop.aktiv() is workshop.VORGABE
            continue
        with pytest.raises(workshop.ProfilFehler):
            workshop.aktiv()


def test_kaputtes_toml_bricht_ab(monkeypatch, tmp_path):
    verz = tmp_path / "kaputt-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text("das ist [kein toml", encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "kaputt-2026")
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert "TOML" in str(fehler.value)


def test_fehlendes_pflichtfeld_bricht_ab(monkeypatch, tmp_path):
    verz = tmp_path / "leer-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text(
        'beschreibung = ""\n[sprache]\ncode = "it"\nanrede = "voi"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "leer-2026")
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert "beschreibung" in str(fehler.value)


def test_fehlende_datei_bricht_ab(monkeypatch, tmp_path):
    (tmp_path / "ohnedatei-2026").mkdir()
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "ohnedatei-2026")
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert workshop.DATEI in str(fehler.value)


def test_teilprofil_erbt_die_uebrigen_felder(monkeypatch, tmp_path):
    """Ein Profil, das nur ein Feld setzt, verliert die anderen nicht --
    sonst muesste jedes neue Profil alles abschreiben."""
    verz = tmp_path / "teil-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Teilprofil"\n[zielgruppe]\nbeschreibung = "Erwachsene"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "teil-2026")
    profil = workshop.aktiv()
    assert profil.wert("zielgruppe.beschreibung") == "Erwachsene"
    assert profil.wert("zielgruppe.traeger") == "Migrantinnenverein Dortmund"
    assert profil.wert("sprache.code") == "de"


def test_profil_wird_je_name_nur_einmal_gelesen(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    assert workshop.aktiv() is workshop.aktiv()


def test_zwei_profile_im_selben_prozess_bleiben_getrennt(monkeypatch, tmp_path):
    """D.5 der Analyse: kein Profilzustand in einem Modul-Global, das ein
    zweites Profil im selben Prozess falsch beantwortet."""
    for name, gruppe in (("eins-2026", "Kinder"), ("zwei-2026", "Erwachsene")):
        verz = tmp_path / name
        verz.mkdir()
        (verz / workshop.DATEI).write_text(
            f'beschreibung = "{name}"\n[zielgruppe]\nbeschreibung = "{gruppe}"\n',
            encoding="utf-8",
        )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "eins-2026")
    assert workshop.aktiv().wert("zielgruppe.beschreibung") == "Kinder"
    monkeypatch.setenv(workshop.VARIABLE, "zwei-2026")
    assert workshop.aktiv().wert("zielgruppe.beschreibung") == "Erwachsene"
    monkeypatch.setenv(workshop.VARIABLE, "eins-2026")
    assert workshop.aktiv().wert("zielgruppe.beschreibung") == "Kinder"


def test_vorgabe_hoert_deutsch_und_ohne_pseudonyme():
    """D1/A5: ohne Profil bleibt Whisper auf Deutsch und niemand wird
    pseudonymisiert -- das heutige Verhalten."""
    profil = workshop.aktiv()
    assert profil.wert("sprache.whisper") == "de"
    assert profil.wert("datenschutz.pseudonyme") is False


def test_nur_gebaute_sprachen():
    assert workshop.SPRACHEN == ("de", "en")
