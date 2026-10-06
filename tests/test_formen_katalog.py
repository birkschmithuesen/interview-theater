"""Der Formen-Katalog kommt aus dem Profil -- eine Quelle statt vier.

Bis zum 06.09.2026 stand die Formenliste an vier Stellen im Code
(``szene.FORMEN``, ``web_schreiben.FORMEN``, ``szene.FORM_STICHWOERTER``,
``szenenfolge.FORM_VORGABE``) und mindestens viermal ausgeschrieben in
Prompts. D.8 der Analyse nennt das die haerteste Kopplung im Repo: eine
Weboberflaeche, die eine andere Formenliste zeigt als der Chat, faellt erst
im Workshop auf.

Jetzt steht sie in ``formen.toml``. Dieser Test prueft **Struktur**: dass
alle Leser dieselbe Liste sehen, dass ein anderes Profil wirklich andere
Formen ergibt und dass zu jeder Form ein Regelblock gehoert. Was Dortmund
inhaltlich zusichert -- dass es Dialog, Monolog, Chor, Lied und Rap sind --
steht in ``tests/profile/test_dortmund.py``.
"""

import pytest

from interview_theater import anweisungen, szene, szenenfolge, ueberarbeitung, web_schreiben, workshop

PADUA = """\
vorgabe = "dialogo"
anzahl_wort = "drei"

[[form]]
name = "dialogo"
anzeige = "Dialogo"
stichwoerter = ["dialogo", "conversazione"]

[[form]]
name = "coro"
anzeige = "Coro"
stichwoerter = ["coro", "corale"]

[[form]]
name = "canzone"
anzeige = "Canzone"
stichwoerter = ["canzone", "cantato"]
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
def anderes_profil(tmp_path, monkeypatch):
    verz = tmp_path / "padua-test"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "Test"\n', encoding="utf-8")
    (verz / workshop.FORMEN_DATEI).write_text(PADUA, encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "padua-test")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    return verz


def test_alle_leser_sehen_dieselbe_liste():
    """D.8: Chat und Weboberflaeche duerfen nie auseinanderlaufen."""
    assert tuple(szene.FORMEN) == tuple(web_schreiben.FORMEN) == workshop.formen()


def test_die_vorgabe_ist_eine_der_formen():
    assert szenenfolge.FORM_VORGABE in szene.FORMEN


def test_zu_jeder_form_gibt_es_einen_regelblock():
    for form in szene.FORMEN:
        text = anweisungen.hole_optional(f"formen/{form}")
        assert text and text.strip(), form


def test_ein_anderes_profil_ergibt_andere_formen(anderes_profil):
    assert tuple(szene.FORMEN) == ("dialogo", "coro", "canzone")
    assert tuple(web_schreiben.FORMEN) == ("dialogo", "coro", "canzone")
    assert szenenfolge.FORM_VORGABE == "dialogo"


def test_formdatei_faellt_auf_die_profil_vorgabe_zurueck(anderes_profil):
    assert szene.formdatei("") == "dialogo"
    assert szene.formdatei("Bewegungsszene") == "dialogo"
    assert szene.formdatei("das wird gesungen, eine canzone") == "canzone"


def test_die_formenliste_steht_im_prompt(anderes_profil):
    text = szenenfolge.systemanweisung(4)
    assert "genau drei: Dialogo, Coro, Canzone" in text
    assert "Dialog, Monolog, Chor, Lied, Rap" not in text


def test_jede_form_kommt_in_system_md_vor():
    """``system.md`` nennt die Formen an einer Stelle noch ausgeschrieben:
    dort faellt der Zeilenumbruch mitten in die Liste, und ein eingesetzter
    Wert wird nicht neu umbrochen (sonst waere die Bitgleichheit weg).
    Damit die Aufzaehlung nicht heimlich vom Katalog abweicht, prueft dieser
    Test sie gegen das Profil -- wer eine Form ergaenzt, sieht es hier.

    Ein Profil mit anderen Formen ersetzt ``system.md`` ohnehin ganz (es ist
    dann in einer anderen Sprache geschrieben), deshalb gilt der Test nur
    fuer die Repo-Fassung."""
    text = anweisungen.hole("system")
    satz = text.split("**Jede Szene hat eine Form**", 1)[1].split("Sie steht schon")[0]
    for anzeige in workshop.form_anzeige():
        assert anzeige in satz, anzeige
    assert workshop.platzhalter()["formen_anzahl"] in satz


def test_platzhalter_liste_und_oder():
    werte = workshop.platzhalter()
    assert werte["formen_liste"] == "Dialog, Monolog, Chor, Lied, Rap"
    assert werte["formen_liste_oder"] == "Dialog, Monolog, Chor, Lied oder Rap"
    assert werte["formen_anzahl"] == "fuenf"
    assert werte["form_vorgabe"] == "dialog"
    assert werte["form_vorgabe_anzeige"] == "Dialog"


def test_katalog_ohne_form_bricht_ab(tmp_path, monkeypatch):
    verz = tmp_path / "leer-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "x"\n', encoding="utf-8")
    (verz / workshop.FORMEN_DATEI).write_text('vorgabe = "x"\nform = []\n', encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "leer-2026")
    workshop.vergiss()
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert "form" in str(fehler.value)


def test_unbekannte_vorgabe_bricht_ab(tmp_path, monkeypatch):
    verz = tmp_path / "schief-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "x"\n', encoding="utf-8")
    (verz / workshop.FORMEN_DATEI).write_text(
        'vorgabe = "gibtsnicht"\n[[form]]\nname = "coro"\n', encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "schief-2026")
    workshop.vergiss()
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert "gibtsnicht" in str(fehler.value)


def test_doppelte_form_bricht_ab(tmp_path, monkeypatch):
    verz = tmp_path / "doppelt-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "x"\n', encoding="utf-8")
    (verz / workshop.FORMEN_DATEI).write_text(
        'vorgabe = "coro"\n[[form]]\nname = "coro"\n[[form]]\nname = "coro"\n',
        encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "doppelt-2026")
    workshop.vergiss()
    with pytest.raises(workshop.ProfilFehler) as fehler:
        workshop.aktiv()
    assert "zweimal" in str(fehler.value)


def test_ohne_formen_datei_gilt_die_vorgabe(tmp_path, monkeypatch):
    """Ein Profil, das an den Formen nichts aendert, braucht keine
    formen.toml."""
    verz = tmp_path / "schlicht-2026"
    verz.mkdir()
    (verz / workshop.DATEI).write_text('beschreibung = "x"\n', encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "schlicht-2026")
    workshop.vergiss()
    assert workshop.formen() == ("dialog", "monolog", "chor", "lied", "rap")


def test_dortmund_traegt_denselben_katalog_wie_die_vorgabe(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    profil = workshop.aktiv()
    assert workshop.formen(profil) == workshop.formen(workshop.VORGABE)
    assert workshop.form_stichwoerter(profil) == workshop.form_stichwoerter(workshop.VORGABE)
    assert workshop.form_vorgabe(profil) == workshop.form_vorgabe(workshop.VORGABE)
    assert workshop.form_anzeige(profil) == workshop.form_anzeige(workshop.VORGABE)
    assert profil.formen["anzahl_wort"] == workshop.VORGABE.formen["anzahl_wort"]


# ---------------------------------------------------------------------------
# A1 (06.10.2026): "chor"/"lied" bekamen live die Dialog-Regeln, weil ihre
# Stichwortlisten in ``workshop/padua-2026/formen.toml`` den eigenen Namen
# nicht enthalten -- anders als "dialog", "monolog" und "rap", wo er
# zufaellig schon drinstand. ``formdatei()`` prueft jetzt wie
# ``ueberarbeitung.form_aus_text()`` den Formnamen selbst mit, beide ueber
# das gemeinsame ``workshop.form_treffer()``.
# ---------------------------------------------------------------------------


@pytest.fixture
def padua(monkeypatch):
    """Das echte Padua-Profil, nicht eine Testkopie: der Fehler hing genau
    an ``workshop/padua-2026/formen.toml`` und waere mit einer eigens
    gebauten Stichwortliste nicht aufgefallen."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


@pytest.mark.parametrize("form", ["chor", "lied"])
def test_formdatei_erkennt_chor_und_lied_am_eigenen_namen(padua, form):
    """Vor dem Fix lieferte ``formdatei("chor")`` den Dialog-Rueckfall,
    weil "chor" in keiner Stichwortliste von ``formen.toml`` steht -- auch
    nicht in der eigenen."""
    assert szene.formdatei(form) == form


@pytest.mark.parametrize("form", ["dialog", "monolog", "rap"])
def test_formdatei_dialog_monolog_rap_unveraendert(padua, form):
    """Diese drei standen zufaellig schon in ihrer eigenen Stichwortliste
    und duerfen durch den Fix nicht anders landen."""
    assert szene.formdatei(form) == form


def test_formdatei_stichwoerter_wirken_fuer_chor_lied_rap_weiter(padua):
    """Der Fix darf die bisherigen Stichwoerter nicht verdraengen."""
    assert szene.formdatei("a chorus of voices") == "chor"
    assert szene.formdatei("let's sing a song") == "lied"
    assert szene.formdatei("a short rap battle") == "rap"


def test_formdatei_faellt_bei_unbekannter_form_weiter_auf_dialog(padua):
    assert szene.formdatei("puppetry") == "dialog"
    assert szene.formdatei("") == "dialog"
    assert szene.formdatei(None) == "dialog"


def test_form_aus_text_blieb_fuer_chor_lied_schon_immer_richtig(padua):
    """Gegenprobe: ``ueberarbeitung.form_aus_text`` nahm den Formnamen
    schon vor dem Fix in die Wortmenge auf -- hier aendert er nichts."""
    assert ueberarbeitung.form_aus_text("chor") == "chor"
    assert ueberarbeitung.form_aus_text("lied") == "lied"
    assert ueberarbeitung.form_aus_text("dialog") == "dialog"
    assert ueberarbeitung.form_aus_text("monolog") == "monolog"
    assert ueberarbeitung.form_aus_text("rap") == "rap"
