"""Schicht 3: der Fan-out -- vier Fragen, ein anderer Richter, keine Note.

Alle Modellaufrufe laufen gegen eine **Attrappe**. Was hier geprueft wird,
ist der Code drumherum: der Parser, die Auswahl des Richters, die
Belegschleife, die C1-Rechnung im Code statt im Modell, die Aggregation zu
Auftraegen und die Grenzen (kein Modellaufruf im Knopf-Handler, keine
Gesamtnote, kein Belegzitat im Chat).
"""

import pytest
from interview_theater import einstellungen, knoepfe, repo
from interview_theater.dramaturgie import fanout, mechanik

from test_knoepfe import TelegramAttrappe

# --- Gerüst ---------------------------------------------------------------

SZENE_1 = """SZENE 1: AM BAHNHOF ca. 9 min
Ein Bahnsteig, frueher Abend.

MIRA: Der Koffer steht seit gestern hier.
JONAS: Und?
MIRA: Und niemand holt ihn.
JONAS: Dann nehme ich ihn mit.
MIRA: Lass den Koffer stehen.
JONAS: Nein.
MIRA: Ich habe dich nicht gefragt.
JONAS: Ich dich auch nicht.
"""

SZENE_2 = """SZENE 2: DIE WOHNUNG ca. 7 min

MIRA: Ich habe den Schluessel verlegt.
JONAS: Schon wieder.
MIRA: Such du.
JONAS: Ich suche nicht.
MIRA: Dann bleibt die Tuer zu.
JONAS: Dann bleibt sie zu.
"""

B1_ANTWORT = """WERT: Vertrauen
LADUNG: + nach -
SCORE: 0
BEFUND: Die Szene endet im selben Zustand, in dem sie beginnt.
BELEG: Lass den Koffer stehen.
SCHWERE: hoch
VORSCHLAG: Szene 1: Lass Jonas den Koffer oeffnen, damit Mira sieht, was
darin ist.
UNSICHER: nein
"""

A2_ANTWORT = """ADDITIVE_SZENEN: 2
SCORE: 1
BEFUND: Szene 2 folgt zeitlich, nicht kausal.
BELEG: Mira sucht den Schluessel, Jonas hilft nicht, die Tuer bleibt zu.
SCHWERE: mittel
SZENE: 2
VORSCHLAG: Szene 2: Lass Mira den Schluessel im Koffer aus Szene 1 suchen.
UNSICHER: nein
"""

A6_ANTWORT = """UNEINGELOEST: Koffer
SCORE: 0
BEFUND: Der Koffer wird aufgeladen und nie eingeloest.
BELEG: MIRA: Der Koffer steht seit gestern hier.
SCHWERE: hoch
SZENE: 1
VORSCHLAG: Szene 2: Lass Jonas den Koffer aus Szene 1 mitbringen und Mira
ihn oeffnen.
UNSICHER: nein
"""


B1_ANTWORT_2 = """WERT: Naehe
LADUNG: - nach -
SCORE: 0
BEFUND: Auch Szene 2 endet, wie sie beginnt.
BELEG: Ich habe den Schluessel verlegt.
SCHWERE: hoch
VORSCHLAG: Szene 2: Lass Jonas den Schluessel finden und nicht hergeben.
UNSICHER: nein
"""


class RichterAttrappe(fanout.Richter):
    """Ein Richter, der nicht fragt, sondern nachschlaegt.

    ``antworten`` ist ``art -> Text`` oder ``art -> Funktion(nutzer) -> Text``;
    die Aufrufe werden mitgeschrieben, damit ein Test sehen kann, was der
    Judge zu sehen bekam. Eine Funktion statt einer Liste, weil die Antworten
    zur Szene passen muessen: ein Beleg aus Szene 1 besteht die Pruefung gegen
    Szene 2 zu Recht nicht, und ein Test, der das uebersieht, misst
    versehentlich die Retry-Schleife."""

    def __init__(self, antworten=None, modell="attrappe"):
        super().__init__("attrappe", modell)
        self.antworten = antworten or {}
        self.gesehen = []

    def frage(self, conn, e, klm, chat_id, system, nutzer, art):
        self.aufrufe += 1
        self.gesehen.append((art, system, nutzer))
        wert = self.antworten.get(art, "")
        return wert(nutzer) if callable(wert) else wert


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K",
        llm_modell="kimi", stt_basis="https://stt.test", stt_produkt="P",
    )


#: Die Kurzfassungen, aus denen die Synopsen-Kette (M5) entsteht.
SYNOPSEN = {
    1: "Mira und Jonas streiten am Bahnsteig ueber einen fremden Koffer.",
    2: "Mira sucht den Schluessel, Jonas hilft nicht, die Tuer bleibt zu.",
}


@pytest.fixture
def stueck(conn):
    repo.setze_figur(conn, 1, "Mira", "Mira ist erfunden.")
    repo.setze_figur(conn, 1, "Jonas", "Jonas ist erfunden.")
    for nummer, text in ((1, SZENE_1), (2, SZENE_2)):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
        repo.setze_szenenfeld(conn, szene_id, "titel", f"Szene {nummer}")
        conn.execute(
            "UPDATE szene SET volltext = ?, zusammenfassung = ? WHERE id = ?",
            (text, SYNOPSEN[nummer], szene_id),
        )
        ids = [repo.hole_figur(conn, 1, n)["id"] for n in ("Mira", "Jonas")]
        repo.setze_szene_figuren(conn, 1, szene_id, ids)
    conn.commit()
    return conn


@pytest.fixture
def tg():
    return TelegramAttrappe()


# --- Der getrennte Richter ------------------------------------------------


def test_schreibt_infomaniak_richtet_claude(einst, conn, monkeypatch):
    monkeypatch.delenv(fanout.ENV_MODELL, raising=False)

    richter = fanout.waehle_richter(einst, conn, 1)

    assert richter.weg == "claude"
    assert richter.modell != einst.llm_modell


def test_schreibt_claude_richtet_infomaniak(einst, conn, monkeypatch):
    monkeypatch.delenv(fanout.ENV_MODELL, raising=False)
    mit_claude = type(einst)(**{**einst.__dict__, "szene_anbieter": "claude"})
    repo.setze_szene_usa(conn, 1, True)

    richter = fanout.waehle_richter(mit_claude, conn, 1)

    assert richter.weg == "infomaniak"
    assert richter.modell == mit_claude.llm_modell


def test_gleiches_modell_verweigert_den_lauf(einst, conn, monkeypatch):
    """Kein stiller Abzug, kein "wir gewichten es weniger" -- ein Fehler mit
    einer Meldung, die sagt, was zu tun ist (Recherche § 4,
    Self-Enhancement Bias)."""
    monkeypatch.setenv(fanout.ENV_MODELL, einst.llm_modell)

    with pytest.raises(fanout.RichterFehler) as fehler:
        fanout.waehle_richter(einst, conn, 1)

    assert einst.llm_modell in str(fehler.value)
    assert "IT_JUDGE_MODELL" in str(fehler.value)


def test_gleiches_modell_auch_bei_anderer_schreibweise(einst, conn, monkeypatch):
    monkeypatch.setenv(fanout.ENV_MODELL, einst.llm_modell.upper() + " ")

    with pytest.raises(fanout.RichterFehler):
        fanout.waehle_richter(einst, conn, 1)


def test_eigenes_richtermodell_waehlt_den_weg(einst, conn, monkeypatch):
    monkeypatch.setenv(fanout.ENV_MODELL, "mistralai/Mistral-Large")
    assert fanout.waehle_richter(einst, conn, 1).weg == "infomaniak"
    monkeypatch.setenv(fanout.ENV_MODELL, "claude-sonnet-5")
    assert fanout.waehle_richter(einst, conn, 1).weg == "claude"


def test_pruefe_faellt_ohne_richter_hin(stueck, einst, monkeypatch):
    monkeypatch.setenv(fanout.ENV_MODELL, einst.llm_modell)

    with pytest.raises(fanout.RichterFehler):
        fanout.pruefe(stueck, einst, None, 1)


# --- Der Parser -----------------------------------------------------------


def test_markerantwort_wird_zerlegt():
    ergebnis = fanout.zerlege(B1_ANTWORT)

    assert ergebnis["score"] == 0
    assert ergebnis["schwere"] == "hoch"
    assert ergebnis["beleg"] == "Lass den Koffer stehen."
    assert ergebnis["unsicher"] is False
    # Der Vorschlag geht ueber zwei Zeilen und bleibt zusammen.
    assert ergebnis["vorschlag"].endswith("darin ist.")


def test_markdown_um_die_marker_stoert_nicht():
    ergebnis = fanout.zerlege(
        "**SCORE:** 0\n**BELEG:** Lass den Koffer stehen.\n**UNSICHER:** nein\n"
    )

    assert ergebnis["score"] == 0
    assert ergebnis["beleg"] == "Lass den Koffer stehen."


def test_ein_zitat_mit_sprechernamen_wird_nicht_zerschnitten():
    """Ein Belegzitat aus einer Dialogszene faengt mit ``MIRA:`` an und geht
    ueber zwei Zeilen. Nur bekannte Marker eroeffnen einen Block -- sonst
    waere der Beleg nach der ersten Zeile zu Ende."""
    ergebnis = fanout.zerlege(
        "BELEG: MIRA: Der Koffer steht seit gestern hier.\n"
        "JONAS: Und?\n"
        "SCORE: 0\n"
    )

    assert ergebnis["beleg"] == (
        "MIRA: Der Koffer steht seit gestern hier. JONAS: Und?"
    )
    assert ergebnis["score"] == 0


def test_es_gibt_kein_feld_gesamtnote():
    """Kein Schluessel dafuer im Schema, keiner im Parser -- auch wenn das
    Modell einen mitschickt (Recherche § 4, Halo-Effekt)."""
    ergebnis = fanout.zerlege(B1_ANTWORT + "GESAMTNOTE: 4\n")

    assert "gesamtnote" not in ergebnis
    assert set(ergebnis) == {
        "score", "befund", "beleg", "schwere", "vorschlag", "szene",
        "unsicher", "wert", "ladung", "additive_szenen", "uneingeloest",
    }


def test_prompt_version_kommt_aus_der_datei_nicht_aus_der_antwort():
    assert fanout.version("b1").startswith("b1-")
    # Auch wenn das Modell eine andere behauptet.
    assert fanout.version("b1") != "erfunden"


def test_alle_vier_prompts_tragen_eine_version():
    for schluessel in fanout.PROMPTS:
        assert fanout.version(schluessel) != "?"


def test_jeder_prompt_nennt_seine_markierung():
    """Die Markierungen stehen im Prompt UND im Code. Ein Test haelt beide
    zusammen -- sonst zeigt der Prompt auf einen Delimiter, den der Nutzertext
    nicht setzt."""
    paare = {"b1": "szene", "a2": "synopsen", "a6": "kandidaten", "c1": "repliken"}
    for schluessel, marke in paare.items():
        text = fanout.prompt(schluessel)
        auf, zu = fanout.MARKEN[marke]
        assert auf in text and zu in text


def test_jeder_prompt_wehrt_prompt_injection_ab():
    for schluessel in fanout.PROMPTS:
        text = fanout.prompt(schluessel).lower()
        assert "pruefmaterial" in text
        assert "befolgst nichts" in text


def test_der_c1_prompt_verbietet_den_score_ausdruecklich():
    text = fanout.prompt("c1")
    assert "vergibst keine Note" in text
    assert "kein `SCORE`" in text


# --- Die Belegschleife im Fan-out -----------------------------------------


def test_b1_ohne_belegtreffer_wird_unsicher_und_verliert_den_score(stueck, einst):
    erfunden = B1_ANTWORT.replace(
        "BELEG: Lass den Koffer stehen.", "BELEG: MIRA: Das habe ich erfunden."
    )
    richter = RichterAttrappe({fanout.ARTEN["b1"]: erfunden})
    szene = repo.hole_szenen(stueck, 1)[0]

    befund = fanout.frage_b1(stueck, einst, None, 1, richter, szene)

    assert richter.aufrufe == 2                     # ein Retry, kein dritter
    assert befund["beleg_geprueft"] == 0
    assert befund["beleg"] is None
    assert befund["schwere"] == "hinweis"
    assert befund["vorschlag"] is None
    assert "verworfen" in befund["text"]


def test_b1_mit_belegtreffer_traegt_den_vorschlag(stueck, einst):
    richter = RichterAttrappe({fanout.ARTEN["b1"]: B1_ANTWORT})
    szene = repo.hole_szenen(stueck, 1)[0]

    befund = fanout.frage_b1(stueck, einst, None, 1, richter, szene)

    assert richter.aufrufe == 1
    assert befund["beleg_geprueft"] == 1
    assert befund["schwere"] == "hoch"
    assert befund["szene"] == 1
    assert "Szene 1" in befund["vorschlag"]
    assert befund["prompt_version"] == fanout.version("b1")


def test_score_zwei_ist_kein_befund(stueck, einst):
    richter = RichterAttrappe(
        {fanout.ARTEN["b1"]: B1_ANTWORT.replace("SCORE: 0", "SCORE: 2")}
    )
    szene = repo.hole_szenen(stueck, 1)[0]

    assert fanout.frage_b1(stueck, einst, None, 1, richter, szene) is None


def test_score_eins_ist_ein_verdacht(stueck, einst):
    richter = RichterAttrappe(
        {fanout.ARTEN["b1"]: B1_ANTWORT.replace("SCORE: 0", "SCORE: 1")}
    )
    szene = repo.hole_szenen(stueck, 1)[0]

    assert fanout.frage_b1(stueck, einst, None, 1, richter, szene)["schwere"] == (
        "verdacht"
    )


def test_b1_sieht_nur_den_szenentext(stueck, einst):
    """Kein Klarname, kein Transkript, kein Arbeitsstand, kein Chat."""
    repo.setze_arbeitsstand(stueck, 1, "rahmen", "GEHEIMER RAHMEN")
    richter = RichterAttrappe({fanout.ARTEN["b1"]: B1_ANTWORT})
    szene = repo.hole_szenen(stueck, 1)[0]

    fanout.frage_b1(stueck, einst, None, 1, richter, szene)

    _, _, nutzer = richter.gesehen[0]
    assert "GEHEIMER RAHMEN" not in nutzer
    assert "Der Koffer steht seit gestern hier." in nutzer


def test_a2_sieht_synopsen_und_nie_den_volltext(stueck, einst):
    conn = stueck
    conn.execute("UPDATE szene SET zusammenfassung = 'Mira und Jonas streiten.'")
    conn.commit()
    richter = RichterAttrappe({fanout.ARTEN["a2"]: A2_ANTWORT})

    fanout.frage_a2(conn, einst, None, 1, richter)

    _, _, nutzer = richter.gesehen[0]
    assert "Mira und Jonas streiten." in nutzer
    assert "Lass den Koffer stehen." not in nutzer


def test_a6_laeuft_nur_ueber_die_kandidatenliste(stueck, einst):
    kandidaten = mechanik.tschechow_kandidaten(mechanik.lies(stueck, 1))
    richter = RichterAttrappe({fanout.ARTEN["a6"]: A6_ANTWORT})

    fanout.frage_a6(stueck, einst, None, 1, richter, kandidaten)

    _, _, nutzer = richter.gesehen[0]
    assert "Koffer" in nutzer
    # Kein Szenenvolltext -- die Ersparnis ist der ganze Punkt.
    assert "JONAS: Nein." not in nutzer


def test_a6_ohne_kandidaten_kostet_keinen_aufruf(stueck, einst):
    richter = RichterAttrappe({fanout.ARTEN["a6"]: A6_ANTWORT})

    assert fanout.frage_a6(stueck, einst, None, 1, richter, []) is None
    assert richter.aufrufe == 0


# --- C1: der Score kommt aus dem Code -------------------------------------


def _c1_antwort(zuordnung, beleg="Der Koffer steht seit gestern hier."):
    zeilen = [f"ZUORDNUNG: {i} = {name}" for i, name in zuordnung]
    zeilen += [
        "BEFUND: Beide klingen gleich.",
        f"BELEG: {beleg}",
        "UNSICHER: nein",
    ]
    return "\n".join(zeilen)


def test_c1_anonymisiert_und_verraet_die_zuordnung_nicht(stueck, einst):
    lage = mechanik.lies(stueck, 1)
    richter = RichterAttrappe(
        {fanout.ARTEN["c1"]: _c1_antwort([(i, "MIRA") for i in range(1, 9)])}
    )

    fanout.frage_c1(stueck, einst, None, 1, richter, 1, lage.repliken[1])

    _, _, nutzer = richter.gesehen[0]
    marke = nutzer.split(fanout.MARKEN["repliken"][0])[1]
    # Im Prueftext steht kein einziger Sprechername.
    assert "MIRA:" not in marke and "JONAS:" not in marke
    assert "1. Der Koffer steht seit gestern hier." in marke


def test_c1_score_wird_gerechnet_nicht_gefragt(stueck, einst):
    """Alles MIRA geraten: die Haelfte stimmt, das ist Score 1. Der Judge hat
    keine Zahl genannt und wird auch keine gefragt."""
    lage = mechanik.lies(stueck, 1)
    richter = RichterAttrappe(
        {fanout.ARTEN["c1"]: _c1_antwort([(i, "MIRA") for i in range(1, 9)])}
    )

    befund = fanout.frage_c1(stueck, einst, None, 1, richter, 1, lage.repliken[1])

    assert befund["schwere"] == "verdacht"          # Score 1, im Code gerechnet
    assert "4" in befund["text"]                    # 4 von 8 richtig
    assert befund["pruefung"] == "c1"


def test_c1_alles_falsch_ist_ein_hoher_befund(stueck, einst):
    lage = mechanik.lies(stueck, 1)
    falsch = [
        (i, "JONAS" if r.label == "MIRA" else "MIRA")
        for i, r in enumerate(lage.repliken[1], start=1)
    ]
    richter = RichterAttrappe({fanout.ARTEN["c1"]: _c1_antwort(falsch)})

    befund = fanout.frage_c1(stueck, einst, None, 1, richter, 1, lage.repliken[1])

    assert befund["schwere"] == "hoch"
    assert "MIRA" in befund["vorschlag"] and "JONAS" in befund["vorschlag"]
    assert "Szene 1" in befund["vorschlag"]


def test_c1_alles_richtig_ist_kein_befund(stueck, einst):
    lage = mechanik.lies(stueck, 1)
    richtig = [(i, r.label) for i, r in enumerate(lage.repliken[1], start=1)]
    richter = RichterAttrappe({fanout.ARTEN["c1"]: _c1_antwort(richtig)})

    assert fanout.frage_c1(
        stueck, einst, None, 1, richter, 1, lage.repliken[1]
    ) is None


def test_c1_ueberspringt_zu_kurze_szenen(stueck, einst):
    richter = RichterAttrappe({})
    kurz = [mechanik.Replik("MIRA", "Ja.", 1), mechanik.Replik("JONAS", "Nein.", 2)]

    assert fanout.frage_c1(stueck, einst, None, 1, richter, 3, kurz) is None
    assert richter.aufrufe == 0


def test_c1_parser_liest_keinen_score():
    zuordnung, rest = fanout.zerlege_zuordnung(
        "ZUORDNUNG: 1 = MIRA\nSCORE: 2\nBELEG: Lass den Koffer stehen.\n"
    )

    assert zuordnung == {1: "MIRA"}
    assert "score" not in rest


# --- Der ganze Lauf -------------------------------------------------------


def _b1_passend(nutzer):
    return B1_ANTWORT if "Koffer" in nutzer else B1_ANTWORT_2


def _c1_passend(nutzer):
    if "Koffer" in nutzer:
        return _c1_antwort([(i, "MIRA") for i in range(1, 9)])
    return _c1_antwort([(i, "MIRA") for i in range(1, 7)],
                       beleg="Ich habe den Schluessel verlegt.")


def _voller_richter():
    return RichterAttrappe({
        fanout.ARTEN["b1"]: _b1_passend,
        fanout.ARTEN["a2"]: A2_ANTWORT,
        fanout.ARTEN["a6"]: A6_ANTWORT,
        fanout.ARTEN["c1"]: _c1_passend,
    })


def test_ein_lauf_speichert_mechanik_und_judge_getrennt(stueck, einst):
    ergebnis = fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())

    zeilen = repo.dramaturgie_befunde(stueck, 1, runde=ergebnis.runde)
    quellen = {z["quelle"] for z in zeilen}
    assert quellen == {"judge"} or quellen == {"mechanik", "judge"}
    assert {z["pruefung"] for z in zeilen} >= {"b1", "a2", "a6", "c1"}
    assert ergebnis.runde == 1


def test_zwei_szenen_kosten_zwei_b1_und_je_einen_a2_a6(stueck, einst):
    richter = _voller_richter()

    fanout.pruefe(stueck, einst, None, 1, richter=richter)

    arten = [art for art, _, _ in richter.gesehen]
    assert arten.count(fanout.ARTEN["b1"]) == 2
    assert arten.count(fanout.ARTEN["a2"]) == 1
    assert arten.count(fanout.ARTEN["a6"]) == 1
    assert arten.count(fanout.ARTEN["c1"]) == 2
    assert richter.aufrufe == 6


def test_eine_zweite_runde_loescht_die_erste_nicht(stueck, einst):
    fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())
    zweite = fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())

    assert zweite.runde == 2
    assert repo.letzte_dramaturgie_runde(stueck, 1) == 2
    assert repo.dramaturgie_befunde(stueck, 1, runde=1)


def test_ein_gescheiterter_aufruf_reisst_den_lauf_nicht_mit(stueck, einst):
    class Kaputt(RichterAttrappe):
        def frage(self, conn, e, klm, chat_id, system, nutzer, art):
            if art == fanout.ARTEN["b1"]:
                raise RuntimeError("Proxy weg")
            return super().frage(conn, e, klm, chat_id, system, nutzer, art)

    richter = Kaputt({
        fanout.ARTEN["a2"]: A2_ANTWORT, fanout.ARTEN["a6"]: A6_ANTWORT,
        fanout.ARTEN["c1"]: _c1_passend,
    })

    ergebnis = fanout.pruefe(stueck, einst, None, 1, richter=richter)

    assert {b["pruefung"] for b in ergebnis.befunde} >= {"a2", "a6"}
    arten = [z["art"] for z in stueck.execute("SELECT art FROM vorfall")]
    assert arten.count("dramaturgie_aufruf_fehlgeschlagen") == 2


def test_ohne_szenen_gibt_es_einen_fehler_mit_satz(conn, einst):
    with pytest.raises(fanout.DramaturgieFehler) as fehler:
        fanout.pruefe(conn, einst, None, 1, richter=RichterAttrappe())

    assert "noch keine Szene" in str(fehler.value)


# --- Aggregation: Auftraege statt Mittelwert ------------------------------


def _befund(**anders):
    grund = {
        "pruefung": "b1", "quelle": "judge", "schwere": "hoch", "szene": 1,
        "text": "Die Szene dreht nichts.", "beleg_geprueft": 1,
        "vorschlag": "Szene 1: Lass Mira den Koffer oeffnen.", "id": 1,
    }
    grund.update(anders)
    return grund


def test_hoechstens_drei_auftraege_je_szene():
    befunde = [
        _befund(id=i, pruefung=p, schwere=s)
        for i, (p, s) in enumerate(
            [("b1", "hoch"), ("a2", "blocker"), ("a6", "hoch"),
             ("c1", "hoch"), ("b1", "blocker")], start=1
        )
    ]

    auftraege = fanout.auftraege(befunde, ["Mira"])

    assert len(auftraege) == fanout.AUFTRAEGE_JE_SZENE
    # Priorisiert nach Schwere, dann Ebene: Geschichte (a2) vor Szene (b1).
    assert auftraege[0]["pruefung"] in ("a2", "b1")
    assert all(a["szene"] == 1 for a in auftraege)


def test_geschichte_vor_szene_vor_stimme():
    befunde = [
        _befund(id=1, pruefung="c1", schwere="hoch"),
        _befund(id=2, pruefung="b1", schwere="hoch"),
        _befund(id=3, pruefung="a2", schwere="hoch"),
        _befund(id=4, pruefung="b1", schwere="hoch", szene=2),
    ]

    auftraege = fanout.auftraege(befunde, ["Mira"])

    szene1 = [a["pruefung"] for a in auftraege if a["szene"] == 1]
    assert szene1 == ["a2", "b1", "c1"]


def test_mittlere_und_niedrige_schwere_erzeugen_keinen_auftrag():
    assert fanout.auftraege([_befund(schwere="mittel")], ["Mira"]) == []
    assert fanout.auftraege([_befund(schwere="niedrig")], ["Mira"]) == []
    assert fanout.auftraege([_befund(schwere="verdacht")], ["Mira"]) == []


def test_ungeprueftes_zitat_erzeugt_keinen_auftrag():
    assert fanout.auftraege([_befund(beleg_geprueft=0)], ["Mira"]) == []


def test_mechanischer_harter_befund_erzeugt_einen_auftrag():
    befund = {
        "pruefung": "namensstabilitaet", "quelle": "mechanik", "schwere": "hart",
        "szene": 3, "text": "In Szene 3 spricht LAYLA.", "id": 9,
        "beleg_geprueft": 0, "vorschlag": None,
    }

    auftraege = fanout.auftraege([befund])

    assert len(auftraege) == 1
    assert auftraege[0]["anweisung"] == "In Szene 3 spricht LAYLA."


def test_befund_ohne_szene_erzeugt_keinen_auftrag():
    befund = {
        "pruefung": "sprechanteil", "quelle": "mechanik", "schwere": "hart",
        "szene": None, "figur": "Pola", "text": "Pola spricht 4 von 900 Woertern.",
        "id": 7, "beleg_geprueft": 0, "vorschlag": None,
    }

    assert fanout.auftraege([befund]) == []


def test_vorschlag_ohne_figurennamen_erzeugt_keinen_auftrag():
    """Die Faustregel aus Recherche § 4: "mehr Spannung erzeugen" ist keine
    Anweisung an einen Schreib-LLM."""
    ohne = _befund(vorschlag="Szene 1: mehr Spannung erzeugen.")

    assert fanout.auftraege([ohne], ["Mira", "Jonas"]) == []
    assert fanout.auftraege([_befund()], ["Mira", "Jonas"])


# --- Was im Chat steht ----------------------------------------------------


def test_befunde_gehen_als_zeile_mit_szenennummer_in_den_chat(stueck, tg, einst):
    fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())

    verschickt = knoepfe.zeige_dramaturgie(stueck, tg, 1)

    texte = [t for _, t in tg.gesendet]
    assert verschickt > 0
    assert any("Runde 1" in t for t in texte)
    assert any(t.startswith("Szene 1:") for t in texte)


def test_kein_belegzitat_im_chat(stueck, tg, einst):
    fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())

    knoepfe.zeige_dramaturgie(stueck, tg, 1)

    for _, text in tg.gesendet:
        assert "Lass den Koffer stehen." not in text


def test_je_auftrag_ein_knopf_szene_n_so_ueberarbeiten(stueck, tg, einst):
    fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())

    knoepfe.zeige_dramaturgie(stueck, tg, 1)

    beschriftungen = [b for _, _, leiste in tg.knoepfe for b, _ in leiste]
    assert "Szene 1 so ueberarbeiten" in beschriftungen
    assert "Lassen" in beschriftungen


def test_der_knopf_startet_einen_szenenauftrag_ohne_modellaufruf(
    stueck, tg, einst, monkeypatch,
):
    """Der Bot schlaegt vor, er handelt nicht: erst der Druck loest den Lauf
    aus -- und der geht ueber ``ablauf.starte_auftrag`` in einen eigenen
    Thread (Zusage 2)."""
    from interview_theater import ablauf

    auftraege = []
    monkeypatch.setattr(
        ablauf, "starte_auftrag",
        lambda conn, tg_, klm, e, chat_id, anweisung: auftraege.append(anweisung),
    )
    fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())
    knoepfe.zeige_dramaturgie(stueck, tg, 1)
    knopf = next(
        d for _, _, leiste in tg.knoepfe for b, d in leiste
        if b.startswith("Szene 1 so")
    )

    knoepfe.behandle(stueck, tg, object(), einst, _druck(knopf))

    assert len(auftraege) == 1
    assert auftraege[0].startswith("Schreib Szene 1 neu.")


def test_lassen_schreibt_nichts(stueck, tg, einst):
    fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())
    knoepfe.zeige_dramaturgie(stueck, tg, 1)
    vorher = len(repo.journal(stueck, 1))
    knopf = next(
        d for _, _, leiste in tg.knoepfe for b, d in leiste if b == "Lassen"
    )

    knoepfe.behandle(stueck, tg, None, einst, _druck(knopf))

    assert len(repo.journal(stueck, 1)) == vorher
    assert tg.gesendet[-1][1] == knoepfe._TEXT_DRAMATURGIE_LASSEN


def test_der_startknopf_ruft_kein_modell_im_handler(stueck, tg, einst, monkeypatch):
    from interview_theater.dramaturgie import fanout as fanout_modul

    gestartet = []
    monkeypatch.setattr(
        fanout_modul, "starte", lambda *a, **k: gestartet.append(True) or None
    )
    knoepfe.biete_nach_pruefung(stueck, tg, 1, 1)
    knopf = next(
        d for _, _, leiste in tg.knoepfe for b, d in leiste
        if b == knoepfe.TEXT_DRAMATURGIE_KNOPF
    )

    knoepfe.behandle(stueck, tg, object(), einst, _druck(knopf))

    assert gestartet == [True]


def _druck(daten):
    return {
        "callback_query_id": "q1", "data": daten, "chat_id": 1,
        "chat_titel": "Testgruppe", "message_id": 777,
    }
