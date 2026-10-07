"""Phase 4 geschaerft (Karten t_256ec777, t_b19d37ac; Birk 06.10.2026).

Der Live-Fall der G3-Testgruppe als Fixture
(``tests/fixtures/phase4_heiratsantrag_g3.json``): die Gruppe nannte EIN
konkretes Beispiel (Heiratsantrag an die Passantin, die anderen aehnliche
Aktionen) und eine Struktur (zufaellig, gleichwertig, keine Dramaturgie).
Der Bot erfand drei eigene Richtungen, eine davon mit Eskalation, schrieb
die Eskalation spaeter der Gruppe zu ("the escalation you described") und
bot noch in Phase 4 an, Szene 1 zu schreiben.

Ob das Modell sich daran haelt, misst nur ein Lauf gegen das echte Modell
(``scripts.pruefe_prompts``). Hier steht fest, (1) dass jede der drei Regeln
im Prompt steht, den Padua in Phase 4 bekommt -- deutsch wie englisch --,
und (2) dass der deterministische Schutz gegen das Schreibangebot den
Live-Text faengt und die gute Uebergangsfrage durchlaesst.
"""

import json
import pathlib

import pytest

from interview_theater import ablauf, anweisungen, kontext, phasen, repo, sprache, workshop

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "phase4_heiratsantrag_g3.json")
    .read_text(encoding="utf-8")
)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def _flach(text):
    return " ".join(text.split())


def test_padua_phase_4_traegt_alle_regeln(padua):
    system = _flach(kontext.system("gruppe1", 4))
    # 1. Rolle: einordnen, kritisch nur bei Bedarf, bewusste Entscheidung respektieren
    assert "You also bring the background of a dramaturge" in system
    assert "not a duty in every turn" in system
    assert "you don't steer it back to a familiar pattern such as a rising arc" in system
    # 2. Das konkrete Beispiel der Gruppe geht vor
    assert "The group's own concrete example comes first." in system
    assert "Three directions of your own only when the group has no idea of its own yet." in system
    assert "never three entirely new overall directions" in system
    # 3. Nichts von dir als ihres
    assert "Never attribute to the group what you added yourself." in system
    # 4. Phase-4/5-Grenze
    assert "never asks \"Shall I write scene 1 now?\"" in system
    assert "this is the one exception to" in system


def test_deutsche_fassung_traegt_dieselben_regeln():
    system = _flach(kontext.system("gruppe4", 4))
    assert "Du bringst auch dramaturgisches Fachwissen mit" in system
    assert "Kritisch nachfragen nur bei echtem Bedarf" in system
    assert "Das konkrete Beispiel der Gruppe geht vor." in system
    assert "Heiratsantrag" in system
    assert "Drei eigene Richtungen nur, wenn die Gruppe noch keine eigene Idee hat." in system
    assert "Nichts von dir als ihres." in system
    assert "Soll ich Szene 1 jetzt schreiben?" in system
    assert "das ist die eine Ausnahme von" in system


def test_ausnahme_steht_direkt_bei_der_regel_die_sie_bricht(padua):
    """Ohne die markierte Ausnahme widerspraeche sich der Prompt: "Bittet die
    Gruppe ausdruecklich darum, tust du es trotzdem" galt bisher auch fuer
    Szenentexte."""
    for code, satz, ausnahme in (
        ("en", "If the group explicitly asks for it, you do it anyway", "this is the one exception to"),
    ):
        # main-Wortlaut (07.10.2026): die Ausnahme steht als eigener Punkt
        # DIREKT VOR dem Satz, den sie bricht, und verweist auf ihn ("below").
        text = _flach(anweisungen.hole("phasen/4"))
        assert 0 <= text.index(satz) - text.index(ausnahme) < 800


def test_schreibangebot_wird_erkannt():
    assert ablauf.ist_schreibangebot(FIXTURE["fehler_schreibangebot"])
    assert ablauf.ist_schreibangebot("Soll ich Szene 2 jetzt schreiben?")
    assert ablauf.ist_schreibangebot("Want me to draft the first scene?")
    # Nur das Szenenformat, ohne Frage: drei Formatzeilen reichen.
    assert ablauf.ist_schreibangebot("Form: open\nPlace: square\nWho: Mira")


@pytest.mark.parametrize("schluessel", ["gut_uebergang", "gut_verweis"])
def test_gute_antworten_bleiben_frei(schluessel):
    assert not ablauf.ist_schreibangebot(FIXTURE[schluessel])


def test_szenenfolge_ist_kein_schreibangebot():
    """Der VORSCHLAG SZENENFOLGE-Block (Titel -- Satz) und eine Frage nach
    dem Ort sind kein Szenenformat."""
    assert not ablauf.ist_schreibangebot(
        "VORSCHLAG SZENENFOLGE:\nThe Pitch -- a proposal on the square\n"
        "The Fight -- two strangers argue\nWhere should it take place?"
    )
    assert not ablauf.ist_schreibangebot(FIXTURE["fehler_drei_eigene_richtungen"])


class _KLM:
    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.gesehen = []

    def schema(self, chat_id, system, nutzer, schema, art, bei_teil=None):
        self.gesehen.append(nutzer)
        return {"antwort": self.antworten.pop(0)}


class _TG:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return 900 + len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **_kw):
        return self.sende(chat_id, text)


@pytest.fixture(autouse=True)
def _ohne_formberater(monkeypatch):
    """Der Gruppenbeitrag nennt "passantin" -- ein Struktur-Stichwort; der
    Formberater-Thread wuerde sonst dieselbe Attrappe mitbenutzen."""
    from interview_theater import formberater

    monkeypatch.setattr(formberater, "pruefe_zug", lambda *a, **k: None)


def _zug(conn, einst, klm):
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 4, "test")
    # Nicht der allererste Zug (sonst Erstkontakt-Anweisung im Koerper).
    repo.merke_nachricht(conn, 1, 1, "Bot", 1, "text", "Where does it take place?",
                         "2998-01-01T00:00:00+00:00")
    repo.setze_beantwortet_bis(conn, 1, 1)
    repo.merke_nachricht(conn, 1, 2, "Mitglied", 0, "text", FIXTURE["gruppe"][0],
                         "2999-01-01T00:00:00+00:00")
    tg = _TG()
    ablauf.antworte(conn, tg, klm, einst, 1, repo.unbeantwortete(conn, 1))
    return tg


def test_zweiter_anlauf_ersetzt_das_schreibangebot(conn, einst, padua):
    klm = _KLM([FIXTURE["fehler_schreibangebot"], FIXTURE["gut_uebergang"]])
    tg = _zug(conn, einst, klm)
    assert len(klm.gesehen) == 2
    assert klm.gesehen[1].endswith(sprache.text(ablauf.__name__, "_TEXT_SCHREIBANGEBOT_ERMAHNUNG"))
    assert tg.gesendet[-1] == FIXTURE["gut_uebergang"]
    arten = [z[0] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "schreibangebot_phase_4" in arten


def test_nur_ein_zweiter_anlauf(conn, einst, padua):
    klm = _KLM([FIXTURE["fehler_schreibangebot"], FIXTURE["fehler_schreibangebot"]])
    tg = _zug(conn, einst, klm)
    assert len(klm.gesehen) == 2
    assert "Shall I write scene 1 now?" in tg.gesendet[-1]
    arten = [z[0] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "schreibangebot_wiederholt" in arten


def test_gute_antwort_ohne_zweiten_anlauf(conn, einst, padua):
    klm = _KLM([FIXTURE["gut_uebergang"]])
    _zug(conn, einst, klm)
    assert len(klm.gesehen) == 1


def test_ausserhalb_von_padua_phase_4_kein_eingriff(conn, einst, padua):
    klm = _KLM([FIXTURE["fehler_schreibangebot"]])
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 6, "test")
    repo.merke_nachricht(conn, 1, 1, "Mitglied", 0, "text", "write it", "2999-01-01T00:00:00+00:00")
    ablauf.antworte(conn, _TG(), klm, einst, 1, repo.unbeantwortete(conn, 1))
    assert len(klm.gesehen) == 1


def test_szenenfolge_knopf_in_padua_phase_4_stellt_keine_szene_vor(conn, einst, padua):
    """Karte t_b19d37ac: nach dem Speichern der Szenenfolge in Phase 4 keine
    Szenenvorstellung mit "Shall I write scene 1 now?" -- nur die Quittung
    und (falls faellig) das eine Phasenangebot."""
    from interview_theater import knoepfe

    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, 4, "test")
    tg = _TG()
    knoepfe._speichere_szenenfolge(
        conn, tg, None, einst, 1,
        "weiter|The Pitch -- a proposal on the square\nThe Fight -- two strangers argue",
    )
    assert tg.gesendet[0] == "Noted, 2 scenes."
    alles = "\n".join(tg.gesendet)
    assert not ablauf.ist_schreibangebot(alles)
    assert "Yes, write it" not in alles
