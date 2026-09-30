"""Die Knopftabelle: Deutsch unveraendert ueber knoepfe.X und knoepfe.T.X,
Englisch ueber knoepfe.T.X (D3)."""

import pytest

from interview_theater import knoepfe, repo, sprache, workshop

from test_knoepfe import TelegramAttrappe


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_reexport_bleibt_deutsch():
    assert knoepfe._TEXT_SCHON_BENUTZT == "Das habe ich schon uebernommen."
    assert knoepfe.T._TEXT_SCHON_BENUTZT is knoepfe._TEXT_SCHON_BENUTZT
    assert knoepfe._ERLEDIGT_FUER[2] == "Eure Begriffe"


def test_padua_liest_englisch(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert knoepfe.T._TEXT_SPEICHERN_KNOPF == "Yes, save"
    assert knoepfe.T._ERLEDIGT_FUER[2] == "Your terms"
    assert knoepfe.T.ANWEISUNGEN.keys() == knoepfe.ANWEISUNGEN.keys()
    assert "{{projekt_kurz}}" in knoepfe.T.ANWEISUNG_EROEFFNUNG
    assert "VORSCHLAG EROEFFNUNG:" in knoepfe.T.ANWEISUNG_EROEFFNUNG


def test_englischer_eroeffnungsauftrag_nennt_das_abschluss_token(monkeypatch):
    """Bis Aufgabe 23 liest ``fragen._speichere_eroeffnung`` nur eine Zeile,
    deren Kopf (klein geschrieben) mit "abschluss" beginnt. Der englische
    Auftrag nennt das Token deshalb woertlich -- in Grossbuchstaben, als
    Protokoll-Token wie VORSCHLAG ...: (K6)."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert "'ABSCHLUSS:'" in knoepfe.T.ANWEISUNG_EROEFFNUNG


def test_eroeffnung_speichert_den_englischen_abschluss(conn):
    """Nachbesserung (Review zu Commit 50572f6): keine Tautologie mehr,
    sondern der echte Parser (``fragen._speichere_eroeffnung``, um Zeile
    297) mit einer Antwort im Format, das der englische Auftrag erzeugt --
    'ABSCHLUSS:' als woertliches Protokoll-Token (K6). Gepruft wird, dass
    Eroeffnung und Abschluss tatsaechlich getrennt im Arbeitsstand landen,
    nicht nur, dass der String im Prompt vorkommt."""
    tg = TelegramAttrappe()
    wert = "Hi, we are from the theatre project.\nABSCHLUSS: Thank you for your time."

    knoepfe._speichere_eroeffnung(conn, tg, 1, wert)

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["interview_eroeffnung"] == "Hi, we are from the theatre project."
    assert stand["interview_abschluss"] == "Thank you for your time."


def _beschriftungen(tg):
    return [text for _, _, leiste in tg.knoepfe for text, _daten in leiste]


@pytest.mark.parametrize("profil, weiter, notiert, quittung", [
    (None, "Weiter zu ", "Notiert:\nSetting: Ein Bahnhof", "Setting uebernommen"),
    ("padua-2026", "On to ", "Noted:\nSetting: Ein Bahnhof", "Setting saved"),
])
def test_phasenknopf_und_notiert_zeile_folgen_dem_profil(
        monkeypatch, conn, profil, weiter, notiert, quittung):
    """Aufgabe 11: die frueheren Inline-Literale in ``basis`` (Phasenknopf,
    Notiert-Zeile, Knopf-Quittung) laufen ueber T -- Deutsch zeichengleich
    wie vorher, Englisch unter Padua."""
    if profil:
        monkeypatch.setenv(workshop.VARIABLE, profil)
        workshop.vergiss()
    tg = TelegramAttrappe()
    knoepfe.biete_phase(conn, tg, 1, "Text", 2)
    assert _beschriftungen(tg)[0].startswith(weiter)

    antwort = knoepfe._speichere(conn, tg, 1, "rahmen|Ein Bahnhof", weiterfrage=False)
    assert notiert in tg.texte
    assert antwort == quittung


@pytest.mark.parametrize("profil, notiert, quittung, journal", [
    (None, "Notiert:\n", "Figuren uebernommen", "Figuren: Mira"),
    ("padua-2026", "Noted:\n", "Characters saved", "Characters: Mira"),
])
def test_figurenliste_quittung_und_journal_folgen_dem_profil(
        monkeypatch, conn, profil, notiert, quittung, journal):
    """Aufgabe 12: ``figuren._uebernimm_figurenliste`` -- Notiert-Kopf,
    Knopf-Quittung und Journalzeile laufen ueber T; Deutsch zeichengleich."""
    if profil:
        monkeypatch.setenv(workshop.VARIABLE, profil)
        workshop.vergiss()
    tg = TelegramAttrappe()
    antwort = knoepfe._uebernimm_figurenliste(conn, tg, 1, "Mira — hat einen Plan")
    assert antwort == quittung
    assert any(t.startswith(notiert) for t in tg.texte)
    assert journal in [z["text"] for z in repo.journal(conn, 1)]


@pytest.mark.parametrize("profil, kopf, journal, quittung", [
    (None, "Szene 1: Ankunft", "Szenenfolge: 1. Ankunft", "Szene 1"),
    ("padua-2026", "Scene 1: Ankunft", "Scene sequence: 1. Ankunft", "Scene 1"),
])
def test_szenenfolge_und_szenentext_folgen_dem_profil(
        monkeypatch, conn, profil, kopf, journal, quittung):
    """Aufgabe 12: ``szenen._speichere_szenenfolge`` (Journalzeile) und
    ``szenen.zeige_szenentext`` (Kopf der Szene, Knopf-Quittung) laufen
    ueber T; Deutsch zeichengleich wie vorher."""
    if profil:
        monkeypatch.setenv(workshop.VARIABLE, profil)
        workshop.vergiss()
    tg = TelegramAttrappe()
    knoepfe._speichere_szenenfolge(conn, tg, None, None, 1, "weiter|Ankunft — sie kommt an")
    assert journal in [z["text"] for z in repo.journal(conn, 1)]
    repo.lege_szene_an(conn, 2, nummer=1, titel="Ankunft", kurzbeschreibung=None,
                       volltext="MIRA: Da bin ich.")
    assert knoepfe.zeige_szenentext(conn, tg, 2, 1) == quittung
    assert tg.texte[-1].startswith(kopf + "\n\n")


@pytest.mark.parametrize("profil, einblendung, journal", [
    (None, "Bleibt in der Schweiz", "US-Modell fuer Szenentexte: nein"),
    ("padua-2026", "Stays in Switzerland", "US model for scene texts: no"),
])
def test_usa_nein_einblendung_und_journal_folgen_dem_profil(
        monkeypatch, conn, profil, einblendung, journal):
    """Aufgabe 13: Einblendung (answerCallbackQuery) und Journalzeile der
    USA-Einwilligung laufen ueber T -- die Entscheidung faellt weiter am
    internen Knopfwert "nein" und bleibt in beiden Sprachen ein Nein."""
    if profil:
        monkeypatch.setenv(workshop.VARIABLE, profil)
        workshop.vergiss()
    tg = TelegramAttrappe()
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_SZENE_USA, "nein")
    druck = {"callback_query_id": "q1", "data": knoepfe._daten(knopf_id),
             "chat_id": 1, "chat_titel": "Testgruppe", "message_id": 7}
    assert knoepfe.behandle(conn, tg, None, None, druck)
    assert tg.beantwortet[-1] == ("q1", einblendung)
    assert repo.szene_usa_stand(conn, 1) == "nein"
    assert journal in [z["text"] for z in repo.journal(conn, 1)]


@pytest.mark.parametrize("profil, einblendung", [
    (None, "Passt"), ("padua-2026", "Good"),
])
def test_einblendung_passt_folgt_dem_profil(monkeypatch, conn, profil, einblendung):
    """Aufgabe 13: ``_wirkung_figur_passt`` liefert die Einblendung aus der
    Tabelle -- Deutsch zeichengleich wie vorher."""
    if profil:
        monkeypatch.setenv(workshop.VARIABLE, profil)
        workshop.vergiss()
    tg = TelegramAttrappe()
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_FIGUR_PASST, "Niemand")
    druck = {"callback_query_id": "q2", "data": knoepfe._daten(knopf_id),
             "chat_id": 1, "chat_titel": "Testgruppe", "message_id": 8}
    assert knoepfe.behandle(conn, tg, None, None, druck)
    assert tg.beantwortet[-1] == ("q2", einblendung)


def test_kein_handler_gibt_ein_textliteral_zurueck():
    """Die Einblendung nach einem Druck ist Nutzertext (Karte A1): sie kommt
    aus der Tabelle, nie als Literal aus dem Handler."""
    import ast
    import inspect

    from interview_theater.knoepfe import wirkung

    baum = ast.parse(inspect.getsource(wirkung))
    literal = []
    for funktion in ast.walk(baum):
        if isinstance(funktion, ast.FunctionDef) and funktion.name.startswith("_wirkung_"):
            for k in ast.walk(funktion):
                if isinstance(k, ast.Return) and isinstance(k.value, (ast.Constant, ast.JoinedStr)):
                    if not (isinstance(k.value, ast.Constant) and not isinstance(k.value.value, str)):
                        literal.append(f"{funktion.name}:{k.lineno}")
    assert literal == []
