"""Tests fuer ``scripts/pruefe_prompts.py`` -- ohne Netz.

Das Skript selbst kostet Geld und laeuft nie automatisch. Was hier geprueft
wird, ist alles daran, was **nicht** vom Modell abhaengt: die Bewertung
(Treffer, Falsch-Positive, Falsch-Negative, Normalisierung) und die
Verdrahtung (Aufruf, Exit-Code, Bericht) mit einer Attrappe fuer
``LLM.schema``.

Die Bewertung getrennt testbar zu halten ist der eigentliche Zweck des
Zuschnitts: nach einer Prompt-Aenderung muss man dem Ergebnis eines
kostenpflichtigen Laufs glauben koennen, ohne es von Hand nachzuzaehlen.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import pruefe_prompts as pp
from interview_theater import einstellungen, llm


# --- Normalisierung -------------------------------------------------------

def test_normalisiere_faellt_kleinschreibung_umschrift_und_satzzeichen():
    assert pp.normalisiere("Ankommen, Arbeit!") == "ankommen arbeit"
    assert pp.normalisiere("ohne Bühnenbild") == pp.normalisiere("ohne Buehnenbild")
    assert pp.normalisiere("Straße") == "strasse"
    assert pp.normalisiere("  viel   Luft \n dazwischen ") == "viel luft dazwischen"
    assert pp.normalisiere(None) == ""


def test_wert_passt_in_beide_richtungen():
    assert pp.wert_passt("Meryem", "Interview mit Meryem")
    assert pp.wert_passt("Interview mit Meryem", "Meryem")
    assert not pp.wert_passt("Meryem", "Rukiye")


def test_leerer_erwarteter_wert_prueft_nur_die_art():
    """interview_starten/-beenden und wortlaut_aus tragen im Prompt einen
    leeren wert, und erkenner._wende_eine_an sieht ihn sich nie an."""
    assert pp.wert_passt("", "")
    assert pp.wert_passt("", "irgendwas, was das Modell dazuschreibt")


# --- Erkenner-Vergleich ---------------------------------------------------

def test_erkenner_treffer_trotz_laengerer_formulierung():
    ergebnis = pp.vergleiche_erkenner(
        [{"art": "verworfen", "wert": "Kindheitsfragen"}],
        [{"art": "verworfen", "wert": "Kindheitsfragen als Einstieg - zu privat"}],
    )
    assert len(ergebnis["treffer"]) == 1
    assert ergebnis["fehlend"] == []
    assert ergebnis["ueberzaehlig"] == []


def test_erkenner_falsche_art_ist_fp_und_fn_zugleich():
    """Der Nemotron-Fehler: 'Kindheitsfragen lassen wir weg' als
    kernthema_setzen gelesen. Das ist beides -- eine verpasste Verwerfung und
    ein falsch gesetztes Kernthema."""
    ergebnis = pp.vergleiche_erkenner(
        [{"art": "verworfen", "wert": "Kindheitsfragen"}],
        [{"art": "kernthema_setzen", "wert": "Kindheitsfragen"}],
    )
    assert len(ergebnis["fehlend"]) == 1
    assert len(ergebnis["ueberzaehlig"]) == 1
    assert ergebnis["treffer"] == []


def test_erkenner_negativfall_zaehlt_jede_aenderung_als_fp():
    ergebnis = pp.vergleiche_erkenner(
        [], [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    )
    assert len(ergebnis["ueberzaehlig"]) == 1
    assert ergebnis["treffer"] == []


def test_erkenner_eine_lieferung_bedient_hoechstens_eine_erwartung():
    """Zwei erwartete Figuren duerfen nicht durch eine einzige gelieferte
    abgedeckt werden -- sonst saehe ein halbes Ergebnis aus wie ein ganzes."""
    ergebnis = pp.vergleiche_erkenner(
        [{"art": "figur_setzen", "wert": "Nesrin"},
         {"art": "figur_setzen", "wert": "Derya"}],
        [{"art": "figur_setzen", "wert": "Nesrin: kam 1974"}],
    )
    assert len(ergebnis["treffer"]) == 1
    assert len(ergebnis["fehlend"]) == 1
    assert ergebnis["ueberzaehlig"] == []


def test_erkenner_alles_richtig_ergibt_null_fp_und_null_fn():
    ergebnis = pp.vergleiche_erkenner(
        [{"art": "interview_starten", "wert": ""}],
        [{"art": "interview_starten", "wert": ""}],
    )
    assert len(ergebnis["treffer"]) == 1
    assert not ergebnis["fehlend"] and not ergebnis["ueberzaehlig"]


# --- Journal-Bewertung ----------------------------------------------------

def test_journal_stichwortset_trifft_einen_eintrag():
    ergebnis = pp.vergleiche_journal(
        [{"kategorie": "vorgeschlagen", "text": "sechs|fragen"}],
        [{"kategorie": "vorgeschlagen",
          "text": "Sechs feste Fragen fuer alle Interviews, damit die "
                  "Gespraeche vergleichbar werden."}],
    )
    assert len(ergebnis["treffer"]) == 1
    assert not ergebnis["fehlend"] and not ergebnis["ueberzaehlig"]


def test_journal_fehlendes_stichwort_ist_fn_und_der_eintrag_fp():
    ergebnis = pp.vergleiche_journal(
        [{"kategorie": "vorgeschlagen", "text": "hinterhof"}],
        [{"kategorie": "vorgeschlagen", "text": "Das Stueck woanders spielen."}],
    )
    assert len(ergebnis["fehlend"]) == 1
    assert len(ergebnis["ueberzaehlig"]) == 1


def test_journal_leerfall_zaehlt_jeden_eintrag_als_fp():
    ergebnis = pp.vergleiche_journal(
        [], [{"kategorie": "vorgeschlagen", "text": "Irgendetwas Erfundenes."}]
    )
    assert len(ergebnis["ueberzaehlig"]) == 1
    assert ergebnis["treffer"] == []


def test_journal_mehrdeutiges_stichwortset_ist_kein_treffer():
    """'Genau ein Eintrag': passt ein Set auf zwei, hat das Modell entweder
    gedoppelt oder zu unscharf formuliert."""
    ergebnis = pp.vergleiche_journal(
        [{"kategorie": "vorgeschlagen", "text": "fragen"}],
        [{"kategorie": "vorgeschlagen", "text": "Sechs feste Fragen fuer alle."},
         {"kategorie": "vorgeschlagen", "text": "Am Ende offene Fragen stellen."}],
    )
    assert len(ergebnis["fehlend"]) == 1
    assert len(ergebnis["mehrdeutig"]) == 1
    assert len(ergebnis["ueberzaehlig"]) == 2


def test_journal_umschrift_und_umlaut_zaehlen_gleich():
    ergebnis = pp.vergleiche_journal(
        [{"kategorie": "vorgeschlagen", "text": "buehnenbild"}],
        [{"kategorie": "vorgeschlagen", "text": "Ohne Bühnenbild spielen, nur mit Stühlen."}],
    )
    assert len(ergebnis["treffer"]) == 1


def test_fragen_format_verlangt_ein_thema_je_zeile():
    """§ 10.6 / Erkenner-Prompt Punkt 5: der ``wert`` von ``fragen_setzen``
    traegt eine Frage je Zeile im Format "Thema: Frage". Sollwert ist
    mechanisch pruefbar -- mindestens ein ':' je Zeile; die Gruppenseite
    rendert daraus die Liste mit fett gesetztem Thema (web._fragen_html)."""
    gut = [{"art": "fragen_setzen", "wert":
            "Koffer: Was war in deinem Koffer?\nBahnhof: Wer hat dich gebracht?"}]
    assert pp.fragen_ohne_thema(gut) == []

    schlecht = [{"art": "fragen_setzen", "wert":
                 "Koffer: Was war in deinem Koffer?\nWer hat dich gebracht?"}]
    assert pp.fragen_ohne_thema(schlecht) == ["Wer hat dich gebracht?"]


def test_fragen_format_geht_nur_fragen_setzen_an_und_nicht_in_fp_fn_ein():
    """Eine Frage ohne Thema ist inhaltlich richtig, nur schlecht
    dargestellt: ein gezaehlter Hinweis wie der Pronomen-Anfang, kein Fehler
    -- die Trefferquote und der Exit-Code bleiben unberuehrt."""
    aenderungen = [
        {"art": "kernthema_setzen", "wert": "Ankommen"},
        {"art": "fragen_setzen", "wert": "Was war in deinem Koffer?"},
    ]
    assert pp.fragen_ohne_thema(aenderungen) == ["Was war in deinem Koffer?"]

    ergebnis = pp.vergleiche_erkenner(
        [{"art": "fragen_setzen", "wert": "Koffer"}],
        [{"art": "fragen_setzen", "wert": "Was war in deinem Koffer?"}],
    )
    assert len(ergebnis["treffer"]) == 1
    assert not ergebnis["fehlend"] and not ergebnis["ueberzaehlig"]


def test_pronomen_check():
    assert pp.beginnt_mit_pronomen("Das koennte man machen.")
    assert pp.beginnt_mit_pronomen("Sie schlagen es vor.")
    assert not pp.beginnt_mit_pronomen("Sechs feste Fragen fuer alle Interviews.")
    assert not pp.beginnt_mit_pronomen("")


def test_pronomen_geht_nicht_in_fp_fn_ein():
    """Ein Artikel am Satzanfang ist ein Hinweis, kein Fehler -- er darf die
    Trefferquote nicht verfaelschen und den Exit-Code nicht beeinflussen."""
    ergebnis = pp.vergleiche_journal(
        [{"kategorie": "vorgeschlagen", "text": "hinterhof"}],
        [{"kategorie": "vorgeschlagen", "text": "Die Auffuehrung im Hinterhof spielen."}],
    )
    assert len(ergebnis["treffer"]) == 1
    assert not ergebnis["fehlend"] and not ergebnis["ueberzaehlig"]
    assert len(ergebnis["pronomen"]) == 1


# --- Verdichter-Bewertung -------------------------------------------------

TRANSKRIPT = (
    "Sara: Wann bist du hergekommen?\n"
    "Nesrin: 1974. Ich hatte einen Koffer und eine Adresse auf einem Zettel.\n"
    "Sara: Und die Arbeit?\n"
    "Nesrin: In der Waescherei. Die Haende waren immer rot."
)


def test_verdichter_alles_richtig():
    bewertung = pp.bewerte_verdichter(
        {"themen_min": 2, "themen_max": 4, "stichwoerter": ["arbeit", "koffer"]},
        {
            "zusammenfassung": "Nesrin kam 1974 mit einem Koffer und arbeitete.",
            "kernthemen": [
                {"thema": "Ankommen", "beleg_zitat": "Ich hatte einen Koffer"},
                {"thema": "Arbeit", "beleg_zitat": "In der Waescherei"},
            ],
        },
        TRANSKRIPT,
    )
    assert bewertung["anzahl_ok"]
    assert len(bewertung["zitate_ok"]) == 2
    assert bewertung["zitate_fehlerhaft"] == []
    assert bewertung["stichwoerter_vermisst"] == []
    assert pp.zaehle_verdichter(bewertung) == (4, 0, 0)


def test_verdichter_erfundenes_zitat_ist_fp():
    """Die direkte Halluzinationsmessung: das Zitat steht nicht im
    Transkript. Geprueft wird mit interview_theater.zitat.pruefe, also mit genau der
    Funktion, die auch im Betrieb entscheidet."""
    bewertung = pp.bewerte_verdichter(
        {"themen_min": 2, "themen_max": 4, "stichwoerter": []},
        {
            "zusammenfassung": "",
            "kernthemen": [
                {"thema": "Ankommen", "beleg_zitat": "Ich hatte einen Koffer"},
                {"thema": "Heimat", "beleg_zitat": "Heimat ist ein Gefuehl"},
            ],
        },
        TRANSKRIPT,
    )
    assert len(bewertung["zitate_fehlerhaft"]) == 1
    assert pp.zaehle_verdichter(bewertung) == (1, 1, 0)


def test_verdichter_zu_wenige_themen_und_fehlendes_stichwort():
    bewertung = pp.bewerte_verdichter(
        {"themen_min": 2, "themen_max": 4, "stichwoerter": ["sprache"]},
        {
            "zusammenfassung": "Nesrin kam 1974.",
            "kernthemen": [{"thema": "Ankommen", "beleg_zitat": "Ich hatte einen Koffer"}],
        },
        TRANSKRIPT,
    )
    assert not bewertung["anzahl_ok"]
    assert bewertung["stichwoerter_vermisst"] == ["sprache"]
    assert pp.zaehle_verdichter(bewertung) == (1, 0, 2)


def test_verdichter_zaehlt_zu_lange_kurzformen_getrennt():
    """N3/N6: die Kurzform traegt die eine Zeile je Interview auf dem
    Dashboard. Zu lang ist ein Hinweis, kein Fehler -- sie geht weder in FP
    noch in FN ein, sonst faerbte eine Formalie den Exit-Code."""
    bewertung = pp.bewerte_verdichter(
        {"themen_min": 1, "themen_max": 4, "stichwoerter": []},
        {
            "zusammenfassung": "",
            "kernthemen": [
                {"thema": "Ankommen", "kurz": "Koffer und ein Zettel",
                 "beleg_zitat": "Ich hatte einen Koffer"},
                {"thema": "Arbeit",
                 "kurz": "sie hat in der Waescherei gearbeitet und die Haende "
                         "waren immer rot",
                 "beleg_zitat": "In der Waescherei"},
            ],
        },
        TRANSKRIPT,
    )
    assert len(bewertung["kurz_zu_lang"]) == 1
    assert pp.zaehle_verdichter(bewertung) == (2, 0, 0)


def test_verdichter_nutzertext_mit_und_ohne_frageliste():
    """N3: die Frageliste steht vor dem Transkript -- und ohne sie ist der
    Nutzertext wortidentisch mit dem Transkript, wie vor N3."""
    from interview_theater import verdichter

    assert verdichter.baue_nutzertext(TRANSKRIPT) == TRANSKRIPT
    mit = verdichter.baue_nutzertext(TRANSKRIPT, "Koffer: Was war im Koffer?")
    assert mit.index("Koffer: Was war im Koffer?") < mit.index(TRANSKRIPT)


# --- Kosten und Bericht ---------------------------------------------------

def test_kostenschaetzung_nach_hinterlegten_preisen():
    # gemma: 0,20 CHF/Mio ein, 0,40 aus
    assert pp.kosten_chf("google/gemma-4-31B-it", 1_000_000, 1_000_000) == pytest.approx(0.60)


def test_kostenschaetzung_ohne_hinterlegten_preis_ist_none():
    """Lieber keine Zahl als eine erfundene -- die Preisliste hat ein Datum
    und veraltet."""
    assert pp.kosten_chf("irgendein/neues-modell", 1000, 1000) is None


def test_berichtspfad_ohne_angabe_landet_in_korpus_berichte():
    pfad = pp.berichtspfad("", ["erkenner"])
    assert pfad.parent == pp.BERICHTE
    assert pfad.name.endswith("-erkenner.md")


def test_berichtspfad_mit_angabe_wird_uebernommen(tmp_path):
    ziel = tmp_path / "eigener.md"
    assert pp.berichtspfad(str(ziel), ["erkenner"]) == ziel


# --- Korpus laden ---------------------------------------------------------

def test_lade_korpus_filtert_auf_ids():
    faelle = pp.lade_korpus("erkenner", ["e01-interview-starten-fatma"])
    assert [f["id"] for f in faelle] == ["e01-interview-starten-fatma"]


def test_modellwahl_folgt_dem_betrieb():
    """Erkenner und Journal laufen mit gemma, der Verdichter mit dem
    Gespraechsmodell (SPEC § 4.3a). Ein Korpuslauf, der das nicht
    nachbildet, misst ein anderes System."""
    e = einstellungen.Einstellungen(
        bot_token="T", bot_name="b", db_pfad="x", audio_verz="a",
        llm_url="u", llm_key="k", llm_modell="kimi",
        stt_basis="s", stt_produkt="p", erkenner_modell="gemma",
    )
    assert pp.modell_fuer("erkenner", e, None) == "gemma"
    assert pp.modell_fuer("journal", e, None) == "gemma"
    assert pp.modell_fuer("verdichter", e, None) == "kimi"
    assert pp.modell_fuer("erkenner", e, "anderes") == "anderes"


# --- Durchlauf mit Attrappe ----------------------------------------------

@pytest.fixture
def attrappe(monkeypatch, tmp_path):
    """Ersetzt ``einstellungen.laden`` und ``LLM.schema``, damit ``main()``
    komplett ohne Netz und ohne Betriebsdatenbank laeuft.

    ``LLM.schema`` wird auf der Klasse ersetzt: damit faellt auch
    ``_anfrage`` weg, es entstehen keine ``aufruf``-Zeilen und die
    Token-Spalten bleiben null. Genau das soll der Test mit abdecken -- ein
    Lauf ohne Nutzungsdaten darf nicht abstuerzen, sondern muss eine
    Kostenschaetzung von 0 ausweisen."""
    antworten = {}

    def falsche_einstellungen():
        return einstellungen.Einstellungen(
            bot_token="T", bot_name="korpus", db_pfad=str(tmp_path / "unbenutzt.db"),
            audio_verz=str(tmp_path / "audio"),
            llm_url="https://llm.test/v1/chat/completions", llm_key="K",
            llm_modell="moonshotai/Kimi-K2.6",
            stt_basis="https://stt.test", stt_produkt="P",
            erkenner_modell="google/gemma-4-31B-it",
        )

    def falsches_schema(self, chat_id, system, nutzer, schema, art,
                        modell=None, temperature=None):
        antworten.setdefault("gesehen", []).append(
            {"art": art, "modell": modell, "nutzer": nutzer}
        )
        return antworten["antwort"](art, nutzer)

    monkeypatch.setattr(pp.einstellungen, "laden", falsche_einstellungen)
    monkeypatch.setattr(llm.LLM, "schema", falsches_schema)
    return antworten


def test_durchlauf_ohne_falsch_positive_endet_mit_null(attrappe, tmp_path, capsys):
    attrappe["antwort"] = lambda art, nutzer: {
        "aenderungen": [{"art": "interview_starten", "wert": ""}]
    }
    bericht = tmp_path / "bericht.md"
    code = pp.main([
        "erkenner", "--nur", "e01-interview-starten-fatma", "--bericht", str(bericht)
    ])
    assert code == 0

    text = bericht.read_text(encoding="utf-8")
    assert "e01-interview-starten-fatma" in text
    assert "Falsch-Positive: **0**" in text
    assert "Trefferquote: 1/1" in text
    assert "Keine Auffaelligkeiten." in text
    # Ohne aufruf-Zeilen gibt es keine Token -- die Schaetzung muss trotzdem
    # eine Zahl sein, keine Ausnahme.
    assert "0.0000 CHF" in text


def test_durchlauf_mit_falsch_positiv_endet_mit_eins(attrappe, tmp_path, capsys):
    """Der Ernstfall: ein Negativfall liefert etwas. Exit-Code 1, damit eine
    Prompt-Aenderung nicht unbemerkt durchgeht (SPEC § 4.3a: 0 FP)."""
    attrappe["antwort"] = lambda art, nutzer: {
        "aenderungen": [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    }
    code = pp.main(["erkenner", "--nur", "n01-beinahe-entscheidung"])
    assert code == 1
    ausgabe = capsys.readouterr().out
    assert "Falsch-Positive: **1**" in ausgabe
    assert "FEHLGESCHLAGEN" in ausgabe
    # Zum auffaelligen Fall gehoert die Notiz aus dem Korpus und die volle
    # Antwort -- sonst weiss beim Lesen niemand, ob der Fehlschlag schlimm ist.
    assert "Auffaellige Faelle" in ausgabe
    assert "blieb korrekt stumm" in ausgabe


def test_durchlauf_ohne_auffaelligkeiten_sagt_das_auch(attrappe):
    attrappe["antwort"] = lambda art, nutzer: {"aenderungen": []}
    assert pp.main(["erkenner", "--nur", "n01-beinahe-entscheidung"]) == 0


def test_durchlauf_baut_den_nutzertext_wie_das_modul(attrappe):
    """Der Arbeitsstand aus dem Korpus muss im Nutzertext landen -- sonst
    prueft der Lauf einen anderen Prompt als den, der im Betrieb laeuft."""
    attrappe["antwort"] = lambda art, nutzer: {"aenderungen": []}
    pp.main(["erkenner", "--nur", "n10-rueckfrage-bereits-gesetzt"])
    nutzer = attrappe["gesehen"][0]["nutzer"]
    assert "Arbeitsstand:" in nutzer
    assert "Kernthema: Ankommen" in nutzer
    assert "Neue Nachrichten:" in nutzer
    assert "Elif: war ankommen jetzt unser kernthema?" in nutzer
    assert attrappe["gesehen"][0]["modell"] == "google/gemma-4-31B-it"


def test_durchlauf_journal_reicht_das_bisherige_journal_mit(attrappe):
    attrappe["antwort"] = lambda art, nutzer: {"eintraege": []}
    code = pp.main(["journal", "--nur", "j02-bereits-entschieden"])
    assert code == 0
    nutzer = attrappe["gesehen"][0]["nutzer"]
    assert "Bisheriges Journal:" in nutzer
    assert "[entschieden]" in nutzer
    assert "Ausschnitt:" in nutzer


def test_durchlauf_verdichter_prueft_das_belegzitat(attrappe, tmp_path):
    fall = pp.lade_korpus("verdichter", ["v01-nesrin-erste-generation"])[0]
    echtes_zitat = fall["transkript"].splitlines()[1].split(": ", 1)[1][:40]

    attrappe["antwort"] = lambda art, nutzer: {
        "zusammenfassung": "Nesrin erzaehlt von Arbeit und Sprache.",
        "kernthemen": [
            {"thema": "Arbeit", "beleg_zitat": echtes_zitat},
            {"thema": "Sprache", "beleg_zitat": "steht so nicht im Transkript"},
        ],
    }
    bericht = tmp_path / "v.md"
    code = pp.main([
        "verdichter", "--nur", "v01-nesrin-erste-generation", "--bericht", str(bericht)
    ])
    # Der Exit-Code haengt allein am Erkenner -- ein erfundenes Zitat beim
    # Verdichter ist eine Zahl im Bericht, kein Abbruch.
    assert code == 0
    text = bericht.read_text(encoding="utf-8")
    assert "Zitate 1/2 geprueft" in text
    assert "Falsch-Positive: **1**" in text
    assert attrappe["gesehen"][0]["modell"] == "moonshotai/Kimi-K2.6"


def test_durchlauf_faengt_einen_modellfehler_ab(attrappe, capsys, monkeypatch):
    """Ein Fall, der scheitert, darf den Rest des Laufs nicht mitreissen --
    sonst kostet ein einzelner 5xx den ganzen bezahlten Durchlauf.
    (502 statt 429: bei 429 wartet das Skript und wiederholt -- siehe unten.)"""
    def kaputt(art, nutzer):
        raise llm.LLMFehler("Sprachmodell lehnte den Aufruf ab: HTTP 502")

    attrappe["antwort"] = kaputt
    code = pp.main(["erkenner", "--nur", "e01-interview-starten-fatma,n01-beinahe-entscheidung"])
    assert code == 0
    ausgabe = capsys.readouterr().out
    assert ausgabe.count("FEHLER") >= 2
    assert "davon 2 mit Fehler" in ausgabe


def test_wiederholungen_ergeben_mehrere_zeilen(attrappe, capsys):
    attrappe["antwort"] = lambda art, nutzer: {"aenderungen": []}
    pp.main(["erkenner", "--nur", "n01-beinahe-entscheidung", "--wiederholungen", "3"])
    ausgabe = capsys.readouterr().out
    for durchgang in (1, 2, 3):
        assert f"n01-beinahe-entscheidung#{durchgang}" in ausgabe


def test_unbekannte_id_bricht_ab(attrappe):
    attrappe["antwort"] = lambda art, nutzer: {"aenderungen": []}
    with pytest.raises(SystemExit) as fehler:
        pp.main(["erkenner", "--nur", "gibtsnicht"])
    assert "gibtsnicht" in str(fehler.value)


def test_der_lauf_fasst_die_betriebsdatenbank_nicht_an(attrappe, tmp_path):
    """IT_DB wird ausdruecklich verworfen: die aufruf- und vorfall-Zeilen
    eines Korpuslaufs gehoeren nicht in die Datenbank des Workshops."""
    attrappe["antwort"] = lambda art, nutzer: {"aenderungen": []}
    pp.main(["erkenner", "--nur", "n01-beinahe-entscheidung"])
    assert not (tmp_path / "unbenutzt.db").exists()


def test_token_und_kosten_kommen_aus_der_aufruf_tabelle(monkeypatch, tmp_path):
    """Der einzige Durchlauf, der ``llm.LLM.schema`` NICHT ersetzt, sondern
    nur den HTTP-Transport: nur so laeuft ``_anfrage`` mit, schreibt eine
    ``aufruf``-Zeile, und nur so laesst sich pruefen, dass Dauer, Token und
    Kostenschaetzung wirklich aus dieser Zeile stammen und nicht aus dem
    vorherigen Fall."""
    import httpx

    def falsche_einstellungen():
        return einstellungen.Einstellungen(
            bot_token="T", bot_name="korpus", db_pfad=str(tmp_path / "unbenutzt.db"),
            audio_verz=str(tmp_path / "audio"),
            llm_url="https://llm.test/v1/chat/completions", llm_key="K",
            llm_modell="moonshotai/Kimi-K2.6",
            stt_basis="https://stt.test", stt_produkt="P",
            erkenner_modell="google/gemma-4-31B-it",
        )

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"aenderungen": []})},
                     "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
            },
        )

    echter_klient = httpx.Client
    monkeypatch.setattr(pp.einstellungen, "laden", falsche_einstellungen)
    monkeypatch.setattr(
        httpx, "Client",
        lambda *a, **k: echter_klient(transport=httpx.MockTransport(handler)),
    )

    bericht = tmp_path / "t.md"
    code = pp.main([
        "erkenner", "--nur", "n01-beinahe-entscheidung", "--bericht", str(bericht)
    ])
    assert code == 0
    text = bericht.read_text(encoding="utf-8")
    assert "Token: 1000000 ein, 1000000 aus" in text
    # gemma: 0,20 CHF/Mio ein + 0,40 aus
    assert "0.6000 CHF" in text


def test_json_zeilen_des_korpus_sind_stabil_ueber_das_skript_lesbar():
    """lade_korpus liest dieselben Dateien wie die Testsuite -- wenn hier
    etwas anderes herauskommt als in test_korpus.py, stimmt eine der beiden
    Leseroutinen nicht."""
    for name, mindestens in (("erkenner", 40), ("journal", 20), ("verdichter", 6)):
        faelle = pp.lade_korpus(name)
        assert len(faelle) >= mindestens
        roh = (pp.KORPUS / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(faelle) == len([z for z in roh if z.strip()])
        assert all(json.loads(z)["id"] for z in roh if z.strip())


def test_429_wird_nach_pause_wiederholt(attrappe, monkeypatch):
    """Gemessen 04.09.2026: nach ~50 Aufrufen in Folge drosselt Infomaniak mit
    429 fuer alle weiteren. Das Skript wartet und wiederholt denselben Fall,
    statt zehn Faelle als 'Fehler' zu verbuchen."""
    monkeypatch.setattr(pp, "PAUSE_429_S", 0)
    schlaefer = []
    monkeypatch.setattr(pp.time, "sleep", lambda s: schlaefer.append(s))
    zaehler = {"n": 0}

    def erst_429(art, nutzer):
        zaehler["n"] += 1
        if zaehler["n"] == 1:
            raise llm.LLMFehler("Sprachmodell lehnte den Aufruf ab: HTTP 429")
        return {"aenderungen": [{"art": "interview_starten", "wert": ""}]}

    attrappe["antwort"] = erst_429
    code = pp.main(["erkenner", "--nur", "e01-interview-starten-fatma"])
    assert code == 0
    assert zaehler["n"] == 2
    assert schlaefer == [0]
