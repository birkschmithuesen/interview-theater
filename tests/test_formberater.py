"""Der Formberater (Karte t_256ec777, Birk 06./07.10.2026).

(a) der Katalog unter ``interview_theater/formen/`` und sein Kurzindex,
(b) der Schema-Aufruf mit Modellattrappe (keine erfundenen Formen),
(c) der deterministische Abgleich (Ausloeser A, laeuft ab Phase 4 ohne
    obere Grenze) samt Delta-Logik,
(d) Einstieg in Phase 5 (Ausloeser B, ohne Knopf -- Birk 07.10.2026 ~08:05),
und der Block im Gespraechs-Prompt.
"""

import json
import pathlib

import pytest

from interview_theater import formberater, knoepfe, kontext, phasen, repo, workshop
from test_knoepfe import TelegramAttrappe


class KLM:
    """Modellattrappe mit derselben Schema-Signatur wie ``llm.LLM``."""

    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort if antwort is not None else {
            "passt": [{"form": "fluxus-event-score", "warum": "equal actions from a score"}],
            "vorschlag": [{"form": "Happening", "warum": "actions in everyday space"}],
            "gegenpol": [{"form": "episches-theater", "warum": "a told story with a point"}],
        }
        self.fehler = fehler
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art, "schema": schema})
        if self.fehler:
            raise self.fehler
        return self.antwort


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


@pytest.fixture(autouse=True)
def _ohne_abstand(monkeypatch):
    monkeypatch.setattr(formberater, "MIN_ABSTAND_S", 0.0)
    formberater._zuletzt_gestartet.clear()


def _phase(conn, nummer):
    repo.setze_szene_usa(conn, 1, False)
    phasen.setze(conn, 1, nummer, "test")


def _gruppe_sagt(conn, message_id, text, gesendet_am="2999-01-01T00:00:00+00:00"):
    repo.merke_nachricht(conn, 1, message_id, "Mitglied", 0, "text", text, gesendet_am)


# --- (a) Katalog und Kurzindex -----------------------------------------------


def test_katalog_hat_alle_67_formen_mit_bot_block():
    katalog = formberater.katalog()
    assert len(katalog) == 67
    for form in katalog.values():
        assert form.titel and form.name_en and form.kurz
        assert 200 <= len(form.bot) <= 900, form.slug
        assert len(form.kurz) <= 160, form.slug
        # verwandt zeigt nur auf Formen, die es gibt
        assert set(form.verwandt) <= set(katalog), form.slug


def test_kurzindex_eine_zeile_je_form_und_schlank():
    index = formberater.kurzindex()
    zeilen = index.splitlines()
    assert len(zeilen) == 67
    assert all(z.count(" | ") >= 3 for z in zeilen)
    assert zeilen[0].startswith("absurdes-theater | Absurdes Theater | Theatre of the Absurd")
    # Der Kurzindex ist die schlanke Auswahlgrundlage, kein Volltext:
    # deutlich kleiner als alle Bot-Bloecke zusammen.
    bot_gesamt = sum(len(f.bot) for f in formberater.katalog().values())
    assert len(index) < 20_000 < bot_gesamt
    assert "fluxus-event-score" in index and "Fluxus-Partitur" in index


def test_kurzindex_ohne_schliesst_aus():
    assert "durational-performance" not in formberater.kurzindex({"durational-performance"})


def test_frontmatter_mit_anfuehrungszeichen_und_listen(tmp_path):
    datei = tmp_path / "probe-form.md"
    datei.write_text(
        '---\ntitle: "Probe Form"\nname_en: "Test form"\n'
        'kurz: "Kurz: mit Doppelpunkt."\naliases: ["a b", c, \'d e\']\n'
        "verwandt: [x, y]\nconfidence: high\n---\n\n## Bot (EN)\nLine one.\n"
        "Line two.\n\n## Definition\nnicht mitlesen\n",
        encoding="utf-8",
    )
    form = formberater.lies_form(datei)
    assert form.slug == "probe-form"
    assert form.titel == "Probe Form" and form.name_en == "Test form"
    assert form.kurz == "Kurz: mit Doppelpunkt."
    assert form.aliases == ("a b", "c", "d e")
    assert form.verwandt == ("x", "y")
    assert form.bot == "Line one. Line two."


def test_datei_ohne_bot_block_ist_ein_fehler(tmp_path):
    datei = tmp_path / "kaputt.md"
    datei.write_text('---\ntitle: "X"\nkurz: "y"\n---\n\n## Definition\nz\n', encoding="utf-8")
    with pytest.raises(ValueError):
        formberater.lies_form(datei)


def test_uebernahmeskript_erzeugt_dieselbe_form(tmp_path):
    from scripts import formen_uebernehmen

    quelle = tmp_path / "wiki"
    quelle.mkdir()
    (quelle / "durational-performance.md").write_text(
        '---\ntitle: "Durational Performance"\ntype: form\n'
        'kurz: "Lang."\naliases: [durational]\nverwandt: [happening]\n'
        "confidence: high\nsources: [raw/x.md]\n---\n\n## Bot (EN)\nDurational "
        "performance: long.\n\n## Definition\nWiki-Text\n",
        encoding="utf-8",
    )
    ziel = tmp_path / "formen"
    assert formen_uebernehmen.uebernimm(quelle, ziel) == 1
    text = (ziel / "durational-performance.md").read_text(encoding="utf-8")
    assert "Wiki-Text" not in text and "sources" not in text
    form = formberater.lies_form(ziel / "durational-performance.md")
    assert form.name_en == "Durational performance"
    assert form.bot == "Durational performance: long."


# --- (c) Stufe 1: der deterministische Abgleich -------------------------------


def test_durational_im_chat_loest_aus():
    assert formberater.treffer_formen("We want it durational, six hours") == {
        "durational-performance": "durational",
    }


@pytest.mark.parametrize("text", [
    "We meet at the station at noon and then we have lunch.",
    "What's happening next? A musical moment, maybe with a mask.",
    "Wir proben morgen um zehn, bringt Wasser mit.",
    "",
])
def test_ohne_formbezug_loest_nichts_aus(text):
    assert formberater.treffer_formen(text) == {}
    assert formberater.treffer_signale(text) == []


def test_namen_ganze_woerter_mehrzahl_und_schreibweisen():
    assert "stand-up-comedy" in formberater.treffer_formen("some STANDUP COMEDY bits")
    assert "absurdes-theater" in formberater.treffer_formen("like Theatre of the Absurd")
    assert "fluxus-event-score" in formberater.treffer_formen("eine Fluxus-Partitur")
    assert "tableau-vivant" in formberater.treffer_formen("two tableaux vivants")
    # Teilwort trifft nicht
    assert formberater.treffer_formen("durationally") == {}


def test_struktur_stichwoerter_der_live_fall():
    """06.10.2026, G3: "random, gleichwertig, keine Eskalation" -- ohne
    einen Formnamen."""
    text = ("All performances are random and of equal weight, no escalation, "
            "no dramaturgy.")
    assert formberater.treffer_formen(text) == {}
    assert formberater.treffer_signale(text) == [
        "random", "equal weight", "of equal", "no escalation", "no dramaturgy",
    ]
    assert "zufall" in formberater.treffer_signale("Die Reihenfolge ist Zufall")
    assert "gleichwertig" in formberater.treffer_signale("alle Szenen gleichwertig")


def test_pruefe_zug_vor_phase_4_tut_nichts(conn, tg, einst):
    _phase(conn, 3)
    klm = KLM()
    assert formberater.pruefe_zug(conn, tg, klm, einst, 1, ["durational, random"]) is None
    assert repo.formberater_zeilen(conn, 1) == []
    assert klm.aufrufe == []


def test_pruefe_zug_phase_4_laedt_sofort_und_beraet_im_hintergrund(conn, tg, einst):
    _phase(conn, 4)
    klm = KLM()

    faden = formberater.pruefe_zug(conn, tg, klm, einst, 1, ["make it durational"])
    # Die genannte Form steht SOFORT da (ohne Modell) ...
    zeilen = repo.formberater_zeilen(conn, 1)
    assert zeilen[0]["ausloeser"] == "stichwort"
    assert zeilen[0]["formen"] == ["durational-performance"]
    faden.join(10)
    # ... und der Modellaufruf hat nachgeladen.
    assert len(klm.aufrufe) == 1
    assert klm.aufrufe[0]["art"] == formberater.ART
    zeilen = repo.formberater_zeilen(conn, 1)
    assert [z["ausloeser"] for z in zeilen] == ["stichwort", "laufend"]
    assert zeilen[1]["formen"] == ["fluxus-event-score", "happening", "episches-theater"]
    assert zeilen[1]["signale"] == ["durational"]
    # Kein eigener Chatbeitrag in Phase 4.
    assert tg.gesendet == []


def test_pruefe_zug_delta_dasselbe_nicht_zweimal(conn, tg, einst):
    _phase(conn, 4)
    klm = KLM()
    formberater.pruefe_zug(conn, tg, klm, einst, 1, ["random order"]).join(10)
    assert len(klm.aufrufe) == 1

    # Dasselbe Stichwort, dieselbe (schon geladene) Form: kein neuer Aufruf.
    assert formberater.pruefe_zug(conn, tg, klm, einst, 1, ["still random"]) is None
    assert formberater.pruefe_zug(
        conn, tg, klm, einst, 1, ["more like epic theatre"]) is None
    assert len(klm.aufrufe) == 1

    # Ein NEUES Stichwort: die Richtung hat sich geaendert, neu nachschlagen.
    formberater.pruefe_zug(conn, tg, klm, einst, 1, ["in public space"]).join(10)
    assert len(klm.aufrufe) == 2
    assert "public space" in klm.aufrufe[1]["nutzer"]
    assert "Schon nachgeschlagen: " in klm.aufrufe[1]["nutzer"]


def test_pruefe_zug_kostenbremse(conn, tg, einst, monkeypatch):
    _phase(conn, 4)
    klm = KLM()
    monkeypatch.setattr(formberater, "MAX_LAUFEND", 1)
    formberater.pruefe_zug(conn, tg, klm, einst, 1, ["random"]).join(10)
    assert formberater.pruefe_zug(conn, tg, klm, einst, 1, ["a loop"]) is None
    assert len(klm.aufrufe) == 1


def test_pruefe_zug_sperrzeit_verbraucht_das_stichwort_nicht(conn, tg, einst, monkeypatch):
    _phase(conn, 4)
    klm = KLM()
    monkeypatch.setattr(formberater, "MIN_ABSTAND_S", 3600.0)
    formberater.pruefe_zug(conn, tg, klm, einst, 1, ["random"]).join(10)
    assert formberater.pruefe_zug(conn, tg, klm, einst, 1, ["a loop"]) is None
    assert "loop" not in formberater.verbrauchte_signale(repo.formberater_zeilen(conn, 1))


def test_ab_phase_5_nur_noch_lazy_load_ohne_modell(conn, tg, einst):
    _phase(conn, 5)
    klm = KLM()
    assert formberater.pruefe_zug(
        conn, tg, klm, einst, 1, ["random, maybe like Body Art"]) is None
    assert klm.aufrufe == []
    zeilen = repo.formberater_zeilen(conn, 1)
    assert [(z["ausloeser"], z["formen"]) for z in zeilen] == [
        ("stichwort", ["body-art"]),
    ]


def test_fehlschlag_verbraucht_stichwort_und_meldet_vorfall(conn, tg, einst):
    _phase(conn, 4)
    klm = KLM(fehler=RuntimeError("weg"))
    formberater.pruefe_zug(conn, tg, klm, einst, 1, ["random"]).join(10)
    zeilen = repo.formberater_zeilen(conn, 1)
    assert zeilen[-1]["formen"] == [] and zeilen[-1]["signale"] == ["random"]
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert formberater.VORFALL_FEHLGESCHLAGEN in arten
    assert tg.gesendet == []
    assert formberater.pruefe_zug(conn, tg, klm, einst, 1, ["random"]) is None


# --- (b) der Schema-Aufruf ----------------------------------------------------


def test_zerlege_nur_katalogformen_grenzen_und_keine_doppelten():
    ergebnis = formberater.zerlege({
        "passt": [
            {"form": "fluxus-event-score", "warum": " a  score "},
            {"form": "Lottery Theatre", "warum": "erfunden"},
            {"form": "Durational performance", "warum": "englischer Name"},
            {"form": "happening", "warum": "dritte passt -- zu viel"},
        ],
        "vorschlag": [{"form": "fluxus-event-score", "warum": "doppelt"}],
        "gegenpol": [{"form": "Episches Theater", "warum": "Titel"},
                     {"form": "oper", "warum": "zweiter Gegenpol"}],
    })
    assert ergebnis == {
        "passt": [{"form": "fluxus-event-score", "warum": "a score"},
                  {"form": "durational-performance", "warum": "englischer Name"}],
        "vorschlag": [],
        "gegenpol": [{"form": "episches-theater", "warum": "Titel"}],
    }


@pytest.mark.parametrize("roh", [None, "text", [], {"passt": "x"}, {"passt": [1, None]}])
def test_zerlege_vertraegt_unsinn(roh):
    assert formberater.zerlege(roh) == {"passt": [], "vorschlag": [], "gegenpol": []}


def test_schema_verlangt_drei_listen():
    assert formberater.SCHEMA["required"] == ["passt", "vorschlag", "gegenpol"]
    for feld in ("passt", "vorschlag", "gegenpol"):
        eintrag = formberater.SCHEMA["properties"][feld]["items"]
        assert eintrag["required"] == ["form", "warum"]


def test_nutzertext_katalog_stueckkarte_und_nur_beitraege_seit_phase_4(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "A square in Padua")
    _gruppe_sagt(conn, 1, "Interview-Zeit: meine Oma sagte etwas", "2000-01-01T00:00:00+00:00")
    _phase(conn, 4)
    _gruppe_sagt(conn, 2, "one performer proposes to a passer-by, the others similar")
    repo.merke_nachricht(conn, 1, 3, "Bot", 1, "text", "BOT-ZEILE", "2999-01-01T00:00:01+00:00")

    text = formberater.baue_nutzertext(conn, 1, ["happening"], "laufend", ["random"])
    assert formberater.kurzindex() in text
    assert "A square in Padua" in text
    assert "proposes to a passer-by" in text
    assert "Oma" not in text          # vor Phase 4: nicht mitgeschickt
    assert "BOT-ZEILE" not in text    # nur die Gruppe
    assert "random" in text and "happening" in text


def test_aufruf_geht_ueber_modellwahl_mit_claude_wenn_aktiv(conn, tg, einst, monkeypatch):
    gesehen = {}

    def aufruf(conn_, klm_, e_, chat_id, system, nutzer, schema, art, **kw):
        gesehen.update(kw, art=art, system=system)
        return {"passt": [{"form": "happening", "warum": "x"}], "vorschlag": [], "gegenpol": []}

    monkeypatch.setattr(formberater.modellwahl, "aufruf_schema", aufruf)
    monkeypatch.setattr(formberater.szene_claude, "ist_aktiv", lambda *a, **k: True)
    _phase(conn, 4)
    ergebnis = formberater.berate(conn, KLM(), einst, 1, "laufend")
    assert gesehen["ueber_claude"] is True
    assert gesehen["art"] == formberater.ART
    assert ergebnis["passt"] == [{"form": "happening", "warum": "x"}]


# --- Der Block im Gespraechs-Prompt --------------------------------------------


def test_kontextblock_leer_vor_phase_4_und_ohne_nachschlagen(conn):
    _phase(conn, 3)
    repo.lege_formberater_an(conn, 1, "stichwort", 3, ["happening"], [])
    assert formberater.kontextblock(conn, 1) == ""
    _phase(conn, 4)
    conn.execute("DELETE FROM formberater")
    assert formberater.kontextblock(conn, 1) == ""


def test_kontextblock_juengste_zuerst_und_gedeckelt(conn):
    _phase(conn, 4)
    alle = list(formberater.katalog())
    repo.lege_formberater_an(conn, 1, "laufend", 4, alle[:4], [])
    repo.lege_formberater_an(conn, 1, "stichwort", 4, ["durational-performance"], [])
    block = formberater.kontextblock(conn, 1)
    zeilen = block.splitlines()
    assert zeilen[0] == formberater.T.KONTEXT_KOPF
    assert len(zeilen) == 1 + formberater.MAX_IM_KONTEXT
    assert zeilen[1] == "- " + formberater.katalog()["durational-performance"].bot


def test_block_steht_im_gespraechs_prompt(conn, einst):
    _phase(conn, 4)
    repo.lege_formberater_an(conn, 1, "stichwort", 4, ["fluxus-event-score"], [])
    _gruppe_sagt(conn, 10, "hallo")
    offen = repo.unbeantwortete(conn, 1)
    koerper = kontext.baue(conn, 1, offen, einst)
    assert formberater.katalog()["fluxus-event-score"].bot in koerper
    assert "Performative Formen" in koerper


def test_block_faellt_bei_platznot_vor_dem_fenster(conn, einst, monkeypatch):
    _phase(conn, 4)
    repo.lege_formberater_an(conn, 1, "stichwort", 4, list(formberater.katalog())[:5], [])
    for i in range(1, 40):
        _gruppe_sagt(conn, i, f"Beitrag {i} " + "x" * 150, f"2999-01-01T00:{i:02d}:00+00:00")
    monkeypatch.setenv("IT_PROMPT_ZEICHEN", "4000")
    offen = repo.unbeantwortete(conn, 1)
    koerper = kontext.baue(conn, 1, offen, einst)
    assert "Performative Formen" not in koerper
    assert "Beitrag 39" in koerper


def test_ablauf_prueft_vor_dem_kontextbau(conn, einst, monkeypatch):
    """Ausloeser A haengt im Gespraechszug: eine genannte Form steht schon im
    Prompt DIESES Zugs."""
    from interview_theater import ablauf
    from test_ablauf import KLMAttrappe

    _phase(conn, 5)  # ab 5 ohne Hintergrundaufruf -- deterministisch
    _gruppe_sagt(conn, 1, "Could this be Body Art?")
    klm = KLMAttrappe()
    tg_ = TelegramAttrappe()
    ablauf.antworte(conn, tg_, klm, einst, 1, repo.unbeantwortete(conn, 1))
    assert any(formberater.katalog()["body-art"].bot in n for n in klm.gesehen)


# --- (d) Einstieg in Phase 5, ohne Knopf -----------------------------------------


def test_einstieg_laeuft_still_ohne_chatkarte(conn, tg, einst, padua):
    """Birk 07.10.2026 (Testgruppe, 10:30): die Form ist beim Eintritt in
    Phase 5 schon festgelegt und im P5-Check bestaetigt -- die Einordnung
    laeuft weiter (Zeile + Prompt), aber KEINE Chat-Karte mehr, die sich
    wie ein neuer Vorschlag liest. Einmal, nie doppelt."""
    _phase(conn, 5)
    klm = KLM()
    formberater.starte_einstieg(conn, tg, klm, einst, 1).join(10)

    assert tg.gesendet == []
    assert tg.knoepfe == []
    zeilen = repo.formberater_zeilen(conn, 1)
    assert [z["ausloeser"] for z in zeilen] == [formberater.AUSLOESER_EINSTIEG]
    assert "Fluxus event score" in formberater.kontextblock(conn, 1)

    # Ein zweiter Eintritt: nichts mehr.
    assert formberater.starte_einstieg(conn, tg, klm, einst, 1) is None
    assert len(klm.aufrufe) == 1


def test_eintritt_in_phase_5_startet_den_einstieg(conn, tg, einst, monkeypatch):
    gestartet = []
    monkeypatch.setattr(formberater, "starte_einstieg",
                        lambda *a, **k: gestartet.append(a[-1]))
    _phase(conn, 5)
    knoepfe.eintritt_in_phase(conn, tg, KLM(), einst, 1, 5)
    assert gestartet == [1]


def test_eintritt_ohne_modell_startet_nichts(conn, tg, einst, monkeypatch):
    monkeypatch.setattr(formberater, "starte_einstieg",
                        lambda *a, **k: pytest.fail("ohne Modell kein Einstieg"))
    _phase(conn, 5)
    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 5)


def test_deutsche_nachricht_nennt_den_deutschen_titel(monkeypatch):
    from interview_theater import sprache

    monkeypatch.setattr(sprache, "code", lambda: "de")
    text = formberater.nachricht({
        "passt": [{"form": "episches-theater", "warum": ""}],
        "vorschlag": [], "gegenpol": [],
    })
    assert "Episches Theater -- " + formberater.katalog()["episches-theater"].kurz in text


def test_tabelle_steht_in_der_loeschzusage():
    from interview_theater import db

    assert "formberater" in db.TABELLEN_MIT_CHAT_ID


def test_zeilen_json_bleibt_lesbar(conn):
    repo.lege_formberater_an(conn, 1, "laufend", 4, ["happening"], ["random"],
                             {"passt": [{"form": "happening", "warum": "ü"}]}, "claude")
    zeile = repo.formberater_zeilen(conn, 1)[0]
    assert zeile["ergebnis"]["passt"][0]["warum"] == "ü"
    roh = conn.execute("SELECT ergebnis FROM formberater").fetchone()[0]
    assert json.loads(roh)["passt"][0]["form"] == "happening"


def test_katalog_im_repo_entspricht_dem_ordner():
    ordner = pathlib.Path(formberater.__file__).parent / "formen"
    assert sorted(p.stem for p in ordner.glob("*.md")) == sorted(formberater.katalog())


def test_takt_alle_5_beitraege_pflichtaufruf(monkeypatch):
    """Birk 07.10.2026: nach TAKT_ZUEGE Gruppenbeitraegen seit dem letzten
    Modellaufruf laeuft der Formberater auch ohne Stichwort."""
    from interview_theater import formberater as f

    gestartet = []
    def _starte(*a, **k):
        gestartet.append(a[5])
        return object()
    monkeypatch.setattr(f, "starte", _starte)
    monkeypatch.setattr(f.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(f, "MIN_ABSTAND_S", 90.0)
    monkeypatch.setattr(f.repo, "formberater_zeilen", lambda c, ch: [
        {"ausloeser": "brainstorm", "erstellt_am": "2026-10-07T06:00:00+00:00", "formen": [], "signale": []}])
    zaehler = {"n": 4}
    monkeypatch.setattr(f.repo, "gruppentexte_seit", lambda c, ch, seit, n: ["x"] * min(n, zaehler["n"]))
    monkeypatch.setattr(f.repo, "lege_formberater_an", lambda *a, **k: None)
    f._zuletzt_gestartet.clear()
    assert f.pruefe_zug(None, None, object(), None, 1, ["film statt live"], phase=4) is None
    assert gestartet == []
    zaehler["n"] = 5
    assert f.pruefe_zug(None, None, object(), None, 1, ["film statt live"], phase=4) is not None
    assert gestartet == [f.AUSLOESER_TAKT]
    # Sperrzeit: direkt danach kein zweiter Takt
    f.pruefe_zug(None, None, object(), None, 1, ["noch was"], phase=4)
    assert gestartet == [f.AUSLOESER_TAKT]


def test_takt_nicht_vor_phase_4(monkeypatch):
    from interview_theater import formberater as f

    monkeypatch.setattr(f, "starte", lambda *a, **k: (_ for _ in ()).throw(AssertionError("kein Aufruf")))
    f._zuletzt_gestartet.clear()
    assert f.pruefe_zug(None, None, object(), None, 1, ["random"], phase=3) is None



def test_neue_form_beim_namen_kuerzt_den_abstand(monkeypatch):
    """Birk 07.10.2026 (Lecture Performance 32 s nach dem Takt): eine neu
    genannte Form startet den Modellaufruf schon nach MIN_ABSTAND_NEUE_FORM_S."""
    from interview_theater import formberater as f

    gestartet = []
    def _starte(*a, **k):
        gestartet.append(a[5])
        return object()
    monkeypatch.setattr(f, "starte", _starte)
    monkeypatch.setattr(f, "MIN_ABSTAND_S", 90.0)
    monkeypatch.setattr(f, "_takt_faellig", lambda c, ch: False)
    monkeypatch.setattr(f.repo, "formberater_zeilen", lambda c, ch: [])
    monkeypatch.setattr(f.repo, "lege_formberater_an", lambda *a, **k: None)
    f._zuletzt_gestartet.clear()
    f._zuletzt_gestartet[1] = 1000.0
    monkeypatch.setattr(f.time, "monotonic", lambda: 1000.0 + f.MIN_ABSTAND_NEUE_FORM_S + 1)
    assert f.pruefe_zug(None, None, object(), None, 1, ["as a lecture performance"], phase=4) is not None
    assert gestartet == [f.AUSLOESER_LAUFEND]
    # ohne neue Form (nur Struktur-Stichwort) gilt weiter der lange Abstand
    gestartet.clear(); f._zuletzt_gestartet[1] = 1000.0
    assert f.pruefe_zug(None, None, object(), None, 1, ["random order"], phase=4) is None
    assert gestartet == []



# --- Musikalische Strukturen nur fuer freigeschaltete Gruppen (Birk 07.10.2026) ---

def test_musik_nur_fuer_freigeschaltete_gruppe(monkeypatch):
    from interview_theater import formberater as f, workshop
    monkeypatch.setattr(workshop, "musik_chats", lambda profil=None: frozenset({7}))
    satz = "and then the cadence brings everyone home, like a rondo"
    assert {"kadenz-tonika", "rondo-ritornello"} <= set(f.treffer_formen(satz, 7))
    assert not ({"kadenz-tonika", "rondo-ritornello"} & set(f.treffer_formen(satz, 8)))
    def hat(index):
        return "kadenz_tonika" in index or "kadenz-tonika |" in index
    assert hat(f.kurzindex(f._gesperrt_fuer(7)))
    assert not hat(f.kurzindex(f._gesperrt_fuer(8)))
    assert not hat(f.kurzindex())


def test_italienischer_alltag_loest_keine_musik_aus(monkeypatch):
    from interview_theater import formberater as f, workshop
    monkeypatch.setattr(workshop, "musik_chats", lambda profil=None: frozenset({7}))
    alltag = "sono d'accordo, sto crescendo, è ostinato, facciamo la coda, il canone d'affitto"
    assert not (set(f.treffer_formen(alltag, 7)) & f.musik_slugs())


def test_musik_katalog_vollstaendig():
    from interview_theater import formberater as f
    assert len(f.musik_slugs()) == 14
    assert len(f.katalog()) == 67
