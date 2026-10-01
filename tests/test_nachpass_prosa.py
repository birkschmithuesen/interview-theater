"""Der EINE Nachpass fuer die ganze Kurzgeschichte (30.09.2026, Karte R).

Phase 6 schreibt alle Abschnitte in einem Lauf -- ein Nachpass je Abschnitt
waere bei sechs Abschnitten sechs Laeufe. Also einer fuer alle, mit allen
Befunden in einer Notiz. Und er prueft VOR dem Speichern: kommt eine andere
Abschnittszahl zurueck oder fehlt ein Zitat, wird gar nichts geschrieben.
"""

import pytest

from interview_theater import (
    kuerzung, kurzgeschichte, laengen, nachpass, phasen, repo, sprachpass,
    workshop,
)

from test_knoepfe import TelegramAttrappe
from test_nachpass import _vorfallarten


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _geschichte(*abschnitte: tuple[str, str, str]) -> str:
    """``(titel, zusammenfassung, koerper)`` je Abschnitt zu einer Antwort."""
    teile = []
    for i, (titel, fassung, koerper) in enumerate(abschnitte, start=1):
        teile.append(f"## {i}. {titel}\nZusammenfassung: {fassung}\n\n{koerper}")
    return "\n\n".join(teile)


LANG = _geschichte(
    ("Ankunft", "Sie kommt an.", "wort " * 900),
    ("Streit", "Es kracht.", "wort " * 900),
)
KURZ = _geschichte(
    ("Ankunft", "Sie kommt an.", "Sie kommt an. Es ist kalt."),
    ("Streit", "Es kracht.", "Sie streiten. Dann gehen sie."),
)
DREI = _geschichte(
    ("Ankunft", "Sie kommt an.", "Kurz."),
    ("Streit", "Es kracht.", "Kurz."),
    ("Morgen", "Es wird hell.", "Kurz."),
)


class LLMAttrappe:
    def __init__(self, *antworten):
        self.antworten = list(antworten) or [KURZ]
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        i = min(len(self.aufrufe) - 1, len(self.antworten) - 1)
        return self.antworten[i]


@pytest.fixture
def prosa6(conn, monkeypatch):
    """Phase 6, zwei Abschnitte mit langer Prosa -- der Stand nach einem Lauf."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    for nummer, titel in ((1, "Ankunft"), (2, "Streit")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "form_vorschlag", "chor")
        repo.aktualisiere_szene(conn, szene_id, titel, "kurz", None, "passiert",
                                prosa="wort " * 900)
    phasen.setze(conn, 1, 6, "test")
    yield conn
    workshop.vergiss()


# --- Der Befund ---------------------------------------------------------


def test_der_befund_nennt_jeden_abschnitt_mit_budget_und_wortzahl(prosa6):
    stand = nachpass.befund_prosa(prosa6, 1)
    assert [n for n, _f, _b, _w in stand["eintraege"]] == [1, 2]
    assert all(b > 0 for _n, _f, b, _w in stand["eintraege"])
    assert all(w > b for _n, _f, b, w in stand["eintraege"])
    assert stand["zu_lang"] is True


def test_der_befund_ruft_kein_modell(prosa6):
    import inspect
    quelle = inspect.getsource(nachpass.befund_prosa)
    for verboten in ("klm", ".prosa(", "hole_text"):
        assert verboten not in quelle, verboten


def test_ohne_profil_meldet_der_befund_nichts(prosa6, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    stand = nachpass.befund_prosa(prosa6, 1)
    assert stand["eintraege"] == []
    assert stand["zu_lang"] is False


# --- Genau EIN Lauf fuer alle Abschnitte -------------------------------


def test_ein_lauf_fuer_alle_abschnitte(prosa6, tg, einst):
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert notiz
    assert len(klm.aufrufe) == 1, "ein Lauf, nicht einer je Abschnitt"
    assert klm.aufrufe[0]["art"] == nachpass.ART_PROSA


def test_die_notiz_bindet_die_abschnittszahl(prosa6, tg, einst):
    """``kuerzung.notiz_fuer_prosa`` bindet sie schon -- hier dieselbe
    Formulierung und keine zweite."""
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert kuerzung.notiz_fuer_prosa(2) in notiz


def test_die_notiz_traegt_laenge_und_sprache(prosa6, tg, einst):
    szenen = repo.hole_szenen(prosa6, 1)
    repo.aktualisiere_szene(
        prosa6, szenen[0]["id"], "Ankunft", "kurz", None, "passiert",
        # Abweichung vom Plan: der Sprachpass zaehlt am GANZEN Text (~1.800
        # Woerter). Je ein Vorkommen laege unter 2,0 je 1.000 -- also je
        # Muster vier.
        prosa=("wort " * 900)
              + " She was tired, angry, and alone." * 4
              + " It was not a home but a waiting room." * 4,
    )
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert kuerzung.notiz_fuer_prosa(2) in notiz
    assert sprachpass.T.NOTIZ_KOPF in notiz          # Padua: englisch
    assert len(klm.aufrufe) == 1


def test_die_neue_fassung_kommt_an(prosa6, tg, einst):
    klm = LLMAttrappe(KURZ)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    prosa = {s["nummer"]: (s["prosa"] or "") for s in repo.hole_szenen(prosa6, 1)}
    assert "Es ist kalt" in prosa[1]
    assert "wort wort" not in prosa[1]


def test_ein_sauberer_stand_loest_keinen_lauf_aus(prosa6, tg, einst):
    for s in repo.hole_szenen(prosa6, 1):
        repo.aktualisiere_szene(prosa6, s["id"], s["titel"], "kurz", None,
                                "passiert", prosa="Kurz und sauber.")
    klm = LLMAttrappe(KURZ)
    assert nachpass.nach_geschichte(prosa6, tg, klm, einst, 1) is None
    assert klm.aufrufe == []


def test_zwei_zu_lange_ergebnisse_ergeben_einen_lauf(prosa6, tg, einst):
    klm = LLMAttrappe(LANG)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert len(klm.aufrufe) == 1
    arten = _vorfallarten(prosa6)
    assert nachpass.VORFALL_IMMER_NOCH in arten


# --- Die Wachen vor dem Speichern -------------------------------------


def test_eine_andere_abschnittszahl_wird_verworfen(prosa6, tg, einst):
    """Der Abgleich in ``lege_szenen_an`` ist ERGAENZEND: kaeme eine dritte
    Szene dazu, behielten die vorhandenen ihren alten Text und die neue waere
    frei erfunden. Also gar nicht speichern."""
    klm = LLMAttrappe(DREI)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert len(repo.hole_szenen(prosa6, 1)) == 2
    assert all("wort wort" in (s["prosa"] or "")
               for s in repo.hole_szenen(prosa6, 1))
    arten = _vorfallarten(prosa6)
    assert nachpass.VORFALL_ABSCHNITTSZAHL in arten


def test_ein_verlorenes_zitat_wird_verworfen(prosa6, tg, einst):
    repo.setze_figur(prosa6, 1, "Mira", "wartet")
    figur_id = repo.figuren(prosa6, 1)[0]["id"]
    repo.setze_sprachprofil(prosa6, figur_id, "kurze Saetze",
                            ["also ich, ja, ich weiss nicht"])
    szenen = repo.hole_szenen(prosa6, 1)
    repo.aktualisiere_szene(
        prosa6, szenen[0]["id"], "Ankunft", "kurz", None, "passiert",
        prosa="also ich, ja, ich weiss nicht. " + ("wort " * 900),
    )
    klm = LLMAttrappe(KURZ)          # ohne das Zitat
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    prosa = {s["nummer"]: (s["prosa"] or "") for s in repo.hole_szenen(prosa6, 1)}
    assert "also ich, ja, ich weiss nicht" in prosa[1], "alte Fassung muss bleiben"
    arten = _vorfallarten(prosa6)
    assert nachpass.VORFALL_VERWORFEN in arten


def test_bei_verwerfen_wird_nichts_geschrieben(prosa6, tg, einst):
    """Phase 6 braucht keinen Rueckweg: geprueft wird VOR dem Speichern, also
    gibt es nichts zurueckzunehmen -- und auch keine Fassungszeile."""
    szene_id = repo.hole_szenen(prosa6, 1)[0]["id"]
    vorher = len(repo.szenenfassungen(prosa6, szene_id))
    klm = LLMAttrappe(DREI)
    nachpass.nach_geschichte(prosa6, tg, klm, einst, 1)
    assert len(repo.szenenfassungen(prosa6, szene_id)) == vorher


def test_ein_gescheiterter_lauf_laesst_alles_stehen(prosa6, tg, einst):
    class Kaputt:
        def prosa(self, *a, **k):
            raise RuntimeError("Modell weg")

    vorher = [(s["nummer"], s["prosa"]) for s in repo.hole_szenen(prosa6, 1)]
    assert nachpass.nach_geschichte(prosa6, tg, Kaputt(), einst, 1) is None
    assert [(s["nummer"], s["prosa"]) for s in repo.hole_szenen(prosa6, 1)] == vorher
