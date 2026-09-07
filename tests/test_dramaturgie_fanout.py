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
    repo.setze_szene_usa(conn, 1, True)

    richter = fanout.waehle_richter(einst, conn, 1)

    assert richter.weg == "claude"
    assert richter.modell != einst.llm_modell


def test_ohne_usa_zustimmung_kein_richter_in_den_usa(einst, conn, monkeypatch):
    """Der Judge liest den Szenentext. Dieselbe Zustimmung, die der
    Szenenlauf braucht, braucht deshalb auch die Pruefung -- sonst ginge auf
    dem Umweg ueber den Richter in die USA, was die Gruppe fuer das Schreiben
    abgelehnt hat."""
    monkeypatch.delenv(fanout.ENV_MODELL, raising=False)

    with pytest.raises(fanout.RichterFehler) as fehler:
        fanout.waehle_richter(einst, conn, 1)

    assert "US-Modell" in str(fehler.value)
    assert "IT_JUDGE_MODELL" in str(fehler.value)


def test_ein_schweizer_richter_braucht_keine_usa_zustimmung(einst, conn, monkeypatch):
    monkeypatch.setenv(fanout.ENV_MODELL, "mistralai/Mistral-Large")

    richter = fanout.waehle_richter(einst, conn, 1)

    assert richter.weg == "infomaniak"


def test_abgelehnte_usa_zustimmung_sperrt_den_claude_richter(einst, conn, monkeypatch):
    monkeypatch.setenv(fanout.ENV_MODELL, "claude-opus-5")
    repo.setze_szene_usa(conn, 1, False)

    with pytest.raises(fanout.RichterFehler):
        fanout.waehle_richter(einst, conn, 1)


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
    repo.setze_szene_usa(conn, 1, True)
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
        # A10: Richtung der Korrektur plus die zwei Felder, aus denen sie
        # hergeleitet wird.
        "richtung", "abweichung", "gewinn",
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


def test_a2_laeuft_nicht_ohne_kurzfassungen(stueck, einst):
    """Fehlt einer Szene die Kurzfassung, gibt es KEINEN Aufruf.

    Gemessen 06.09.2026 im ersten echten Judge-Lauf gegen Opus: die
    Synopsen-Kette bestand aus Titeln und dem Platzhalterwort, und der Judge
    meldete pflichtgemaess, es gebe keinen kausalen Anschluss -- ein wahrer
    Satz ueber unsere Datenlage, ein falscher ueber das Stueck. Ein bezahlter
    Aufruf fuer einen Befund, der eine Gruppe zu einem unnoetigen Umbau
    verleitet haette.
    """
    conn = stueck
    conn.execute("UPDATE szene SET zusammenfassung = NULL, kurzbeschreibung = NULL")
    conn.commit()
    richter = RichterAttrappe({fanout.ARTEN["a2"]: A2_ANTWORT})

    ergebnis = fanout.frage_a2(conn, einst, None, 1, richter)

    assert ergebnis is None
    assert richter.gesehen == [], "A2 hat trotz fehlender Kurzfassungen gefragt"


def test_a2_laeuft_wenn_jede_szene_eine_kurzfassung_hat(stueck, einst):
    """Die Gegenprobe -- sonst waere die Sperre zu scharf.

    Geprueft wird nur, DASS gefragt wurde: die Zahl der Aufrufe haengt an der
    Belegschleife (ein Retry, wenn das Zitat nicht woertlich vorkommt) und ist
    hier nicht die Aussage.
    """
    conn = stueck
    conn.execute("UPDATE szene SET zusammenfassung = 'Mira und Jonas streiten.'")
    conn.commit()
    richter = RichterAttrappe({fanout.ARTEN["a2"]: A2_ANTWORT})

    fanout.frage_a2(conn, einst, None, 1, richter)

    assert richter.gesehen, "A2 hat trotz vollstaendiger Kurzfassungen nicht gefragt"


def test_a2_laeuft_nicht_bei_inhaltsleerer_kurzfassung(stueck, einst):
    """Der zweite, gefaehrlichere Fall: Feld gefuellt, Inhalt leer.

    Im Gegenprobelauf am 06.09.2026 stand als Kurzbeschreibung das Wort
    "szene". Formal belegt, inhaltlich nichts -- und die erste Fassung der
    Sperre, die nur auf den Platzhalter prueft, liess den Aufruf durch. Opus
    meldete daraufhin erneut einen Befund ueber unsere Datenlage.
    """
    conn = stueck
    conn.execute(
        "UPDATE szene SET zusammenfassung = NULL, kurzbeschreibung = 'szene'")
    conn.commit()
    richter = RichterAttrappe({fanout.ARTEN["a2"]: A2_ANTWORT})

    ergebnis = fanout.frage_a2(conn, einst, None, 1, richter)

    assert ergebnis is None
    assert richter.gesehen == [], "A2 hat bei inhaltsleerer Kurzfassung gefragt"


def test_synopsen_fehlen_nennt_die_szenennummern():
    """Reine Funktion, ohne Datenbank -- die Sperre muss sagen, WO es fehlt."""
    material = (
        "Szene 1: Am Kiosk (dialog)\n"
        f"{fanout.OHNE_SYNOPSE}\n"
        "Szene 2: Zweite\n"
        "Sie streiten laut.\n"
        "Szene 3: Dritte\n"
        f"{fanout.OHNE_SYNOPSE}"
    )

    assert fanout.synopsen_fehlen(material) == [1, 3]
    assert fanout.synopsen_fehlen("Szene 1: A\nSie streiten.") == []
    assert fanout.synopsen_fehlen("") == []


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


def test_c1_parser_liest_auch_mehrere_paare_je_zeile():
    """Der Prompt bittet um eine Zeile je Replik. Fasst das Modell sie
    zusammen, ist das kein Grund, "nichts zugeordnet" zu melden -- das waere
    ein Befund ueber den Parser, der als Befund ueber das Stueck ankaeme."""
    zuordnung, _ = fanout.zerlege_zuordnung(
        "ZUORDNUNG: 1 = MIRA, 2 = JONAS, 3 = MIRA\n"
    )

    assert zuordnung == {1: "MIRA", 2: "JONAS", 3: "MIRA"}


def test_c1_ohne_zuordnung_gibt_es_keinen_befund(stueck, einst):
    """Keine Zuordnung ist **kein** Score 0: die Trefferquote waere null und
    der Befund "alle klingen gleich" -- ein Urteil ueber einen abgebrochenen
    Aufruf, nicht ueber das Stueck."""
    lage = mechanik.lies(stueck, 1)
    richter = RichterAttrappe({
        fanout.ARTEN["c1"]:
            "BEFUND: Ich kann nichts zuordnen.\n"
            "BELEG: Der Koffer steht seit gestern hier.\nUNSICHER: nein\n"
    })

    assert fanout.frage_c1(
        stueck, einst, None, 1, richter, 1, lage.repliken[1]
    ) is None


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
    """Was ein Lauf ueber zwei Szenen kostet, Frage fuer Frage.

    Szenenweise gefragt wird B1, A9, A10 und C1; einmal fuers ganze Stueck
    A2 und A6. A9 und A10 fragen nur, wenn ihr Material da ist -- ohne
    Hauptkonflikt bzw. ohne Szenenfestlegungen schweigen sie, und die
    Fixture setzt beides nicht.
    """
    richter = _voller_richter()

    fanout.pruefe(stueck, einst, None, 1, richter=richter)

    arten = [art for art, _, _ in richter.gesehen]
    assert arten.count(fanout.ARTEN["b1"]) == 2
    assert arten.count(fanout.ARTEN["a2"]) == 1
    assert arten.count(fanout.ARTEN["a6"]) == 1
    assert arten.count(fanout.ARTEN["c1"]) == 2
    assert richter.aufrufe == len(arten)


def test_ein_lauf_legt_die_scores_je_frage_und_szene_ab(stueck, einst):
    """Schicht 4 braucht die Scores, nicht die Befunde: was in ``befunde``
    steht, ist die Auswahl der Fehlschlaege."""
    ergebnis = fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter())

    adressen = {(b["pruefung"], b["szene"]) for b in ergebnis.bewertungen}
    # B1 wird je Szene gefragt, A2 und A6 einmal fuers ganze Stueck -- und
    # tragen deshalb keine Szenennummer, auch wenn ihre Antwort eine nennt.
    assert ("b1", 1) in adressen and ("b1", 2) in adressen
    assert ("a2", None) in adressen and ("a6", None) in adressen
    assert all(0 <= b["score"] <= 2 for b in ergebnis.bewertungen)

    gespeichert = repo.dramaturgie_bewertungen(stueck, 1, runde=ergebnis.runde)
    assert len(gespeichert) == len(ergebnis.bewertungen)


def test_die_erfuellte_frage_gibt_keinen_befund_aber_eine_bewertung(stueck, einst):
    """Der Grund, warum die Zahl der Befunde als Erfolgsmass nicht taugt: eine
    erfuellte Frage ist unsichtbar, solange nur Befunde gezaehlt werden."""
    gut = B1_ANTWORT.replace("SCORE: 0", "SCORE: 2")
    richter = RichterAttrappe({fanout.ARTEN["b1"]: gut})
    bewertungen = []
    szene = {s["nummer"]: s for s in repo.hole_szenen(stueck, 1)}[1]

    befund = fanout.frage_b1(stueck, einst, None, 1, richter, szene, bewertungen)

    assert befund is None
    assert bewertungen == [{"pruefung": "b1", "szene": 1, "score": 2}]


def test_ein_verworfener_score_geht_nicht_in_die_bilanz(stueck, einst):
    """Kein Score ohne bestaetigtes Belegzitat -- dieselbe Grenze wie beim
    Schreibauftrag. Eine Note ohne Beleg ist keine schlechtere Note, sie ist
    keine."""
    erfunden = B1_ANTWORT.replace(
        "BELEG: Lass den Koffer stehen.", "BELEG: Das steht so nirgends im Text."
    )
    richter = RichterAttrappe({fanout.ARTEN["b1"]: erfunden})
    bewertungen = []
    szene = {s["nummer"]: s for s in repo.hole_szenen(stueck, 1)}[1]

    befund = fanout.frage_b1(stueck, einst, None, 1, richter, szene, bewertungen)

    assert befund["schwere"] == "hinweis"
    assert bewertungen == []


def test_c1_legt_auch_die_volle_trefferquote_als_bewertung_ab(stueck, einst):
    """C1 rechnet seinen Score im Code aus -- auch die Zwei muss abgelegt
    werden, obwohl sie keinen Befund erzeugt."""
    lage = mechanik.lies(stueck, 1)
    richtige = _c1_antwort(
        [(i, r.label) for i, r in enumerate(lage.repliken[1], start=1)]
    )
    richter = RichterAttrappe({fanout.ARTEN["c1"]: richtige})
    bewertungen = []

    befund = fanout.frage_c1(
        stueck, einst, None, 1, richter, 1, lage.repliken[1], bewertungen
    )

    assert befund is None
    assert bewertungen == [{"pruefung": "c1", "szene": 1, "score": 2}]


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


# --- A10 Materialtreue: welche Richtung wird korrigiert? -----------------
#
# Birk, 06.09.2026: "die szene kann und darf sich in der entwicklung auch von
# den ursprungsparametern aendern, wenn es die szene oder die handlung
# verbessert... wenn die aenderung gut begruendet wird, sollte der parameter
# angepasst werden". Eine reine Treuepruefung waere die Falle -- sie wuerde
# einen besseren Text auf eine ueberholte Planung zurueckbiegen.

A10_TEXT_ZIEHT_NACH = """GEPRUEFT: anlass, kernsaetze
ABWEICHUNG: Der Kernsatz der Gruppe kommt in der Szene nicht vor.
GEWINN: nein
SCORE: 0
BEFUND: Der festgelegte Kernsatz fehlt ersatzlos.
BELEG: MIRA: Der Koffer steht seit gestern hier.
SCHWERE: hoch
RICHTUNG: text
VORSCHLAG: Szene 1: Lass Mira den festgelegten Kernsatz sagen, bevor Jonas
den Koffer nimmt.
UNSICHER: nein
"""

A10_PARAMETER_ZIEHT_NACH = """GEPRUEFT: anlass, was_passiert
ABWEICHUNG: Nicht Mira nimmt den Koffer, sondern Jonas -- und das ist staerker.
GEWINN: ja
SCORE: 0
BEFUND: Die Handlung ist umgekehrt zur Planung, die Umkehrung traegt die Szene.
BELEG: MIRA: Lass den Koffer stehen.
SCHWERE: hoch
RICHTUNG: parameter
VORSCHLAG: anlass: Jonas nimmt den Koffer, obwohl Mira es verbietet
UNSICHER: nein
"""


def test_a10_legt_die_festlegungen_vor(stueck, einst):
    """Der Judge muss die Parameter sehen -- sonst prueft er nichts."""
    conn = stueck
    conn.execute("UPDATE szene SET anlass = ?, kernsaetze = ? WHERE nummer = 1",
                 ("Mira will den Koffer loswerden", "Lass den Koffer stehen."))
    conn.commit()
    szene = conn.execute("SELECT * FROM szene WHERE nummer = 1").fetchone()
    richter = RichterAttrappe({fanout.ARTEN["a10"]: A10_TEXT_ZIEHT_NACH})

    fanout.frage_a10(conn, einst, None, 1, richter, szene)

    _, _, nutzer = richter.gesehen[0]
    assert "Mira will den Koffer loswerden" in nutzer
    assert "anlass" in nutzer  # der technische Feldname fuer die Rueckgabe


def test_a10_fragt_nicht_ohne_festlegungen(stueck, einst):
    """Ohne Parameter gibt es nichts zu pruefen -- und keinen Aufruf."""
    conn = stueck
    conn.execute(
        "UPDATE szene SET anlass=NULL, was_passiert=NULL, kernsaetze=NULL, "
        "ton=NULL, zeit=NULL, ort=NULL, form=NULL WHERE nummer = 1")
    conn.commit()
    szene = conn.execute("SELECT * FROM szene WHERE nummer = 1").fetchone()
    richter = RichterAttrappe({fanout.ARTEN["a10"]: A10_TEXT_ZIEHT_NACH})

    assert fanout.frage_a10(conn, einst, None, 1, richter, szene) is None
    assert richter.gesehen == []


def test_a10_prueft_die_form_nicht_in_der_prosaphase(stueck, einst):
    """**Die Form ist in Phase 6 noch nicht eingeloest.**

    Dort schreibt das Modell ausdruecklich Prosa (``szene.py``: "In Phase 6
    geht IMMER prosa.md in die Systemanweisung -- die Form der Szene ist dort
    noch gar nicht entschieden"). Gemessen 06.09.2026: A10 verlangte fuer
    Szene 3 gesprochenen Rap in einem Text, der ihn planmaessig noch nicht
    haben konnte -- ein Fehlbefund, der einen Ueberarbeitungsauftrag ausloeste.
    """
    conn = stueck
    conn.execute("UPDATE szene SET form = 'rap', anlass = ? WHERE nummer = 1",
                 ("Die Gruppen prallen aufeinander",))
    repo.setze_phase(conn, 1, 6)
    conn.commit()
    szene = conn.execute("SELECT * FROM szene WHERE nummer = 1").fetchone()
    richter = RichterAttrappe({fanout.ARTEN["a10"]: A10_TEXT_ZIEHT_NACH})

    fanout.frage_a10(conn, einst, None, 1, richter, szene)

    _, _, nutzer = richter.gesehen[0]
    assert "Die Gruppen prallen aufeinander" in nutzer
    assert "Form (form)" not in nutzer


def test_a10_prueft_die_form_im_feinschliff(stueck, einst):
    """Gegenprobe: ab Phase 7 ist die Form eingeloest und wird geprueft."""
    conn = stueck
    conn.execute("UPDATE szene SET form = 'rap' WHERE nummer = 1")
    repo.setze_phase(conn, 1, fanout.A10_FORM_AB_PHASE)
    conn.commit()
    szene = conn.execute("SELECT * FROM szene WHERE nummer = 1").fetchone()
    richter = RichterAttrappe({fanout.ARTEN["a10"]: A10_TEXT_ZIEHT_NACH})

    fanout.frage_a10(conn, einst, None, 1, richter, szene)

    _, _, nutzer = richter.gesehen[0]
    assert "Form (form)" in nutzer


def test_parameterkorrektur_liest_feld_und_wert():
    befund = {
        "pruefung": "a10", "richtung": "parameter", "beleg_geprueft": 1,
        "vorschlag": "anlass: Jonas nimmt den Koffer, obwohl Mira es verbietet",
    }

    assert fanout.parameterkorrektur(befund) == (
        "anlass", "Jonas nimmt den Koffer, obwohl Mira es verbietet")


def test_parameterkorrektur_nur_mit_gepruefte_beleg():
    """Ohne verifiziertes Zitat wird keine Festlegung der Gruppe angefasst."""
    befund = {
        "pruefung": "a10", "richtung": "parameter", "beleg_geprueft": 0,
        "vorschlag": "anlass: irgendetwas",
    }

    assert fanout.parameterkorrektur(befund) is None


def test_parameterkorrektur_nur_bei_richtung_parameter():
    befund = {
        "pruefung": "a10", "richtung": "text", "beleg_geprueft": 1,
        "vorschlag": "anlass: irgendetwas",
    }

    assert fanout.parameterkorrektur(befund) is None


def test_parameterkorrektur_lehnt_unbekanntes_feld_ab():
    """Der Judge darf nur die Felder setzen, die ihm vorgelegt wurden."""
    befund = {
        "pruefung": "a10", "richtung": "parameter", "beleg_geprueft": 1,
        "vorschlag": "titel: Ein neuer Titel",
    }

    assert fanout.parameterkorrektur(befund) is None


def test_parameterbefund_geht_nicht_an_den_schreiber():
    """**Die zentrale Sperre.** Bei ``richtung=parameter`` sagt der Judge,
    dass der Text recht hat. Ein Auftrag daraus wuerde ihn auf die
    ueberholte Planung zurueckbiegen -- genau verkehrt herum."""
    befunde = [{
        "pruefung": "a10", "quelle": "judge", "schwere": "hoch",
        "szene": 1, "beleg_geprueft": 1, "richtung": "parameter",
        "vorschlag": "anlass: Jonas nimmt den Koffer",
    }]

    assert fanout.auftraege(befunde) == []


def test_die_sperre_haelt_auch_aus_der_datenbank(conn):
    """**Die Sperre darf nicht ueber die Datenbank zu umgehen sein.** Der
    Knopfweg (``knoepfe.zeige_dramaturgie``), das Skript und die
    Rueckkopplungsschleife lesen die Befunde nicht aus dem Lauf, sondern aus
    ``dramaturgie_befund`` -- stand die Richtung nur im Arbeitsspeicher, war
    sie fuer sie alle verschwunden, und aus einem Parameterbefund wurde doch
    ein Schreibauftrag."""
    befunde = [
        {
            "pruefung": "a10", "quelle": "judge", "schwere": "hoch", "szene": 1,
            "text": "Der Anlass stimmt nicht mehr.", "beleg": "Der Koffer.",
            "beleg_geprueft": 1, "richtung": "parameter",
            "vorschlag": "anlass: Jonas nimmt den Koffer",
        },
        {
            "pruefung": "b1", "quelle": "judge", "schwere": "hoch", "szene": 2,
            "text": "Szene 2 endet, wie sie anfaengt.", "beleg": "Der Koffer.",
            "beleg_geprueft": 1, "richtung": "text",
            "vorschlag": "Szene 2: Lass Mira den Koffer oeffnen.",
        },
    ]
    repo.lege_dramaturgie_befunde_an(conn, 1, befunde, runde=1)

    zeilen = repo.dramaturgie_befunde(conn, 1, runde=1)

    assert {z["pruefung"]: z["richtung"] for z in zeilen} == {
        "a10": "parameter", "b1": "text",
    }
    assert [a["pruefung"] for a in fanout.auftraege(zeilen)] == ["b1"]


def test_textbefund_geht_sehr_wohl_an_den_schreiber():
    """Gegenprobe -- sonst waere die Sperre zu breit."""
    befunde = [{
        "pruefung": "a10", "quelle": "judge", "schwere": "hoch",
        "szene": 1, "beleg_geprueft": 1, "richtung": "text",
        "vorschlag": "Szene 1: Lass Mira den Kernsatz sagen.",
    }]

    auftraege = fanout.auftraege(befunde)

    assert len(auftraege) == 1
    assert auftraege[0]["szene"] == 1


def test_zerlege_liest_die_richtung():
    assert fanout.zerlege(A10_PARAMETER_ZIEHT_NACH)["richtung"] == "parameter"
    assert fanout.zerlege(A10_TEXT_ZIEHT_NACH)["richtung"] == "text"
    # Was keine der beiden Richtungen ist, wird nicht geraten.
    assert fanout.zerlege("RICHTUNG: vielleicht\nSCORE: 1\n")["richtung"] is None


# --- A11 Stueckvorgaben: Format, Rahmen, Figurenzahl --------------------

A11_ANTWORT = """GEPRUEFT: format, rahmen, figuren_anzahl
ABWEICHUNG: Das Stueck loest am Ende alles auf statt offen zu bleiben.
GEWINN: nein
SCORE: 0
BEFUND: Das vorgegebene offene Ende ist zu einem Schluss geworden.
BELEG: Szene 2: Die Wohnung
SCHWERE: hoch
RICHTUNG: text
VORSCHLAG: Szene 2: Lass die letzte Frage unbeantwortet stehen.
UNSICHER: nein
"""


def test_a11_legt_die_stueckvorgaben_vor(stueck, einst):
    conn = stueck
    conn.execute("UPDATE szene SET zusammenfassung = 'Mira und Jonas streiten.'")
    repo.setze_arbeitsstand(conn, 1, "format", "Eine Folge, Ende offen")
    repo.setze_arbeitsstand(conn, 1, "figuren_anzahl", "10-12")
    conn.commit()
    richter = RichterAttrappe({fanout.ARTEN["a11"]: A11_ANTWORT})

    fanout.frage_a11(conn, einst, None, 1, richter)

    _, _, nutzer = richter.gesehen[0]
    assert "Eine Folge, Ende offen" in nutzer
    assert "10-12" in nutzer
    # Die Synopsen, nicht der Volltext -- eine Frage ueber das Ganze.
    assert "Mira und Jonas streiten." in nutzer
    assert "Lass den Koffer stehen." not in nutzer


def test_a11_fragt_nicht_ohne_vorgaben(stueck, einst):
    """Kein Format, kein Rahmen, keine Figurenzahl -> nichts zu pruefen."""
    conn = stueck
    conn.execute("UPDATE szene SET zusammenfassung = 'Mira und Jonas streiten.'")
    for feld in fanout.A11_FELDER:
        repo.setze_arbeitsstand(conn, 1, feld, None)
    conn.commit()
    richter = RichterAttrappe({fanout.ARTEN["a11"]: A11_ANTWORT})

    assert fanout.frage_a11(conn, einst, None, 1, richter) is None
    assert richter.gesehen == []


def test_a11_fragt_nicht_bei_luecken_in_den_synopsen(stueck, einst):
    """Dieselbe Sperre wie A2: eine Kette aus Platzhaltern beantwortet
    keine Frage ueber den Bogen des Stuecks."""
    conn = stueck
    conn.execute("UPDATE szene SET zusammenfassung = NULL, kurzbeschreibung = NULL")
    repo.setze_arbeitsstand(conn, 1, "format", "Eine Folge, Ende offen")
    conn.commit()
    richter = RichterAttrappe({fanout.ARTEN["a11"]: A11_ANTWORT})

    assert fanout.frage_a11(conn, einst, None, 1, richter) is None
    assert richter.gesehen == []


def test_stueckparameterkorrektur_liest_feld_und_wert():
    befund = {
        "pruefung": "a11", "richtung": "parameter", "beleg_geprueft": 1,
        "vorschlag": "format: Zwei Folgen, die zweite bleibt offen",
    }

    assert fanout.stueckparameterkorrektur(befund) == (
        "format", "Zwei Folgen, die zweite bleibt offen")


def test_stueckparameterkorrektur_lehnt_szenenfeld_ab():
    """``anlass`` gehoert zu einer Szene, nicht zum Stueck -- A11 darf es
    nicht setzen, auch wenn A10 es duerfte."""
    befund = {
        "pruefung": "a11", "richtung": "parameter", "beleg_geprueft": 1,
        "vorschlag": "anlass: irgendetwas",
    }

    assert fanout.stueckparameterkorrektur(befund) is None


def test_a11_parameterbefund_geht_nicht_an_den_schreiber():
    """Dieselbe Sperre wie bei A10, auf Stueckebene."""
    befunde = [{
        "pruefung": "a11", "quelle": "judge", "schwere": "hoch",
        "szene": 1, "beleg_geprueft": 1, "richtung": "parameter",
        "vorschlag": "format: Zwei Folgen",
    }]

    assert fanout.auftraege(befunde) == []
