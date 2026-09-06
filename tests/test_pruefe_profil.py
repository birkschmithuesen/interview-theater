"""Die Profilpruefung vor dem Start (E.1 Frage 9).

"Fehlerbild am Workshoptag ist die teuerste Waehrung": ein Profil mit einem
Tippfehler im Platzhalternamen soll den Start abbrechen, nicht die Gruppe
``{{zielgrupe}}`` lesen lassen. Geprueft wird hier, dass jeder dieser Faelle
wirklich als Fehler herauskommt -- und dass ein unfertiges Profil ohne
eigenen Korpus **nicht** scheitert (E.1 Frage 8).
"""

import pytest

from interview_theater import anweisungen, workshop
from scripts import pruefe_profil


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def _profil(tmp_path, monkeypatch, name="test-2026", inhalt='beschreibung = "T"\n'):
    verz = tmp_path / name
    (verz / "prompts").mkdir(parents=True)
    (verz / workshop.DATEI).write_text(inhalt, encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    return verz


def test_dortmund_ist_in_ordnung(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    workshop.vergiss()
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert bericht.fehler == []


def test_das_eingebaute_profil_ist_in_ordnung():
    bericht = pruefe_profil.pruefe(workshop.VORGABE)
    assert bericht.fehler == []


def test_ein_platzhalter_ohne_wert_ist_ein_fehler(tmp_path, monkeypatch):
    verz = _profil(tmp_path, monkeypatch)
    (verz / "prompts" / "system.md").write_text(
        "Die Gruppe sind {{zielgrupe}}.\n", encoding="utf-8")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert any("zielgrupe" in f for f in bericht.fehler), bericht.fehler


def test_eine_form_ohne_regelblock_ist_ein_fehler(tmp_path, monkeypatch):
    verz = _profil(tmp_path, monkeypatch)
    (verz / workshop.FORMEN_DATEI).write_text(
        'vorgabe = "commedia"\nanzahl_wort = "eine"\n'
        '[[form]]\nname = "commedia"\n', encoding="utf-8")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert any("commedia" in f and "Regelblock" in f for f in bericht.fehler)


def test_ein_falsches_zahlwort_ist_ein_fehler(tmp_path, monkeypatch):
    verz = _profil(tmp_path, monkeypatch)
    (verz / workshop.FORMEN_DATEI).write_text(
        'vorgabe = "dialog"\nanzahl_wort = "sieben"\n'
        '[[form]]\nname = "dialog"\nanzeige = "Dialog"\n', encoding="utf-8")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert any("anzahl_wort" in f for f in bericht.fehler), bericht.fehler


def test_ein_fremdsprachiges_zahlwort_ist_nur_ein_hinweis(tmp_path, monkeypatch):
    verz = _profil(tmp_path, monkeypatch)
    (verz / workshop.FORMEN_DATEI).write_text(
        'vorgabe = "dialog"\nanzahl_wort = "tre"\n'
        '[[form]]\nname = "dialog"\nanzeige = "Dialogo"\n', encoding="utf-8")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert bericht.fehler == []
    assert any("anzahl_wort" in h for h in bericht.hinweise)


def test_eine_fehlende_einleitung_ist_ein_fehler(tmp_path, monkeypatch):
    verz = _profil(tmp_path, monkeypatch)
    (verz / workshop.PHASEN_DATEI).write_text(
        '[[phase]]\nnummer = 1\nname = "A"\nsatz = "a"\n', encoding="utf-8")
    (verz / workshop.PHASENTEXTE_DATEI).write_text(
        '[einleitung]\n1 = ""\n', encoding="utf-8")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert any("Einleitung" in f for f in bericht.fehler), bericht.fehler


def test_eine_abweichende_zielgruppe_im_rahmen_ist_ein_hinweis(tmp_path, monkeypatch):
    """Der Fall, den sonst niemand faende: profil.toml sagt das eine, die
    kurze Rahmenfassung das andere."""
    _profil(tmp_path, monkeypatch,
            inhalt='beschreibung = "T"\n[zielgruppe]\nbeschreibung = "Erwachsene"\n')
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert any("Zielgruppe" in h for h in bericht.hinweise), bericht.hinweise


def test_ohne_eigenen_korpus_wird_nichts_geprueft(tmp_path, monkeypatch):
    """E.1 Frage 8: ein halbfertiges zweites Profil darf den Betrieb des
    ersten nicht blockieren."""
    _profil(tmp_path, monkeypatch)
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert not any("korpus" in f for f in bericht.fehler)


def test_ein_zu_kleiner_eigener_korpus_ist_ein_fehler(tmp_path, monkeypatch):
    verz = _profil(tmp_path, monkeypatch)
    korpus = verz / "korpus"
    korpus.mkdir()
    for name in pruefe_profil.KORPUS_MINDEST:
        (korpus / f"{name}.jsonl").write_text('{"id": 1}\n', encoding="utf-8")
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert len([f for f in bericht.fehler if "korpus/" in f]) == 4


def test_eine_kaputte_korpuszeile_ist_ein_fehler(tmp_path, monkeypatch):
    verz = _profil(tmp_path, monkeypatch)
    korpus = verz / "korpus"
    korpus.mkdir()
    (korpus / "erkenner.jsonl").write_text("{kein json\n", encoding="utf-8")
    bericht = pruefe_profil.pruefe(workshop.aktiv())
    assert any("Zeile 1" in f for f in bericht.fehler)


def test_ein_fehlendes_profil_liefert_rueckgabewert_eins(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    assert pruefe_profil.pruefe_namen("gibtsnicht-2026") == 1
    assert "gibtsnicht-2026" in capsys.readouterr().out


def test_dortmund_liefert_rueckgabewert_null(capsys):
    assert pruefe_profil.pruefe_namen("dortmund-2026") == 0
    assert "in Ordnung" in capsys.readouterr().out
