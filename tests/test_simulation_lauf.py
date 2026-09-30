"""Der Lauf und die Verdrahtung von ``scripts/simulation.py`` -- ohne Netz.

Das Herzstueck ist ``test_mini_lauf_schreibt_bericht_und_json``: zwei
Schritte, eine Attrappe fuer ``LLM.schema`` wie in
``tests/test_pruefe_prompts.py``, und danach muss ein Bericht dastehen und
eine Zeile in ``verlauf.jsonl``. Wenn das laeuft, ist der Weg von der
Stimm-Nachricht ueber ``bot.verarbeite_update`` und
``bot._zug_und_erkenner`` bis in den Bericht durchgaengig -- alles andere ist
dann eine Frage der Modelle, nicht des Codes.
"""

import inspect
import json
from datetime import datetime, timezone

import pytest

from interview_theater import (
    ablauf, aufnahme, bot, einstellungen, kontext, llm, repo, szene, telegram,
)
from simulation import bericht, claude, lauf, skript
from simulation.attrappe import TelegramAttrappe

from scripts import simulation as sim


class ClaudeAttrappe:
    """Der Simulationsklient ohne Netz.

    Zwei Wege, wie im Ernstfall: ``text`` fuer die Stimmen, ``json_objekt``
    fuer den Richter. Die Statistik wird mitgefuehrt, weil der Bericht sie
    ausweist -- ein Lauf mit null Simulationsaufrufen waere ein Lauf, in dem
    keine Stimme gesprochen hat."""

    def __init__(self, text_antwort, urteil_fuer):
        self.modell = "claude-opus-5"
        self._text = text_antwort
        self._urteil_fuer = urteil_fuer
        self.statistik = claude.Statistik()
        self.gesehen = []

    def text(self, system, nutzer, art="sim", max_tokens=None):
        self.gesehen.append(art)
        self.statistik.buche(art, 100, 20, True)
        return self._text

    def json_objekt(self, system, nutzer, art="sim", max_tokens=None):
        self.gesehen.append(art)
        self.statistik.buche(art, 200, 50, True)
        return self._urteil_fuer(nutzer)

    def schliesse(self):
        pass


# --- Update-Dict ----------------------------------------------------------


def test_bau_update_hat_die_form_die_der_bot_erwartet(conn, einst):
    jetzt = datetime.now(timezone.utc)
    update = lauf.bau_update(1, 10, "Ines", "wir fangen an", jetzt)
    nachricht = telegram.lies_nachricht(update)
    assert nachricht["chat_id"] == lauf.CHAT_ID
    assert nachricht["absender"] == "Ines"
    assert nachricht["text"] == "wir fangen an"
    assert nachricht["typ"] == "text"


def test_ein_update_landet_ueber_den_bot_in_der_datenbank(conn, einst):
    jetzt = datetime.now(timezone.utc)
    update = lauf.bau_update(1, 10, "Ines", "hallo", jetzt)
    ergebnis = bot.verarbeite_update(conn, einst, update, jetzt, False)
    assert ergebnis is not None
    zeile = repo.hole_nachricht(conn, lauf.CHAT_ID, 10)
    assert zeile["text"] == "hallo"
    assert zeile["unterdrueckt"] == 0


def test_stimmen_und_bot_teilen_sich_eine_message_id_folge(conn, einst):
    """Der Bot liest nur, was ueber seinem Wasserzeichen liegt. Zaehlten die
    Stimmen in einer eigenen, niedrigeren Folge, laege jede ihrer Nachrichten
    ab dem zweiten Zug darunter -- er beantwortete sie nie, der Erkenner
    saehe sie nie, und der Lauf bestuende aus dem Bot, der mit sich selbst
    spricht."""
    tg = TelegramAttrappe()
    ids = [tg.naechste_message_id(), tg.sende(lauf.CHAT_ID, "Antwort"),
           tg.naechste_message_id()]
    assert ids == sorted(ids)
    assert len(set(ids)) == 3
    assert tg.gesendet[0]["message_id"] == ids[1]


def test_attrappe_haelt_die_no_ops_bereit(tmp_path):
    """``setze_befehle``, ``loesche_nachrichten`` und ``lade_datei`` kommen im
    vollen Codepfad vor und duerfen nicht mit AttributeError abbrechen."""
    tg = TelegramAttrappe()
    tg.setze_befehle([("start", "los")])
    tg.loesche_nachrichten(lauf.CHAT_ID, [1, 2])
    tg.tippt(lauf.CHAT_ID)
    tg.lade_datei("AwACabc", tmp_path / "unter" / "a.ogg")
    assert (tmp_path / "unter" / "a.ogg").exists()
    assert tg.befehle and tg.geloescht and tg.getippt


# --- Einfaedigkeit --------------------------------------------------------


def test_einfaedig_ersetzt_die_drei_threadstarter_und_stellt_sie_zurueck():
    vorher = (szene.starte, aufnahme.starte_abschluss, aufnahme.starte_auswertung)
    with lauf.einfaedig():
        assert szene.starte is lauf._sofort_szene
        assert aufnahme.starte_abschluss is lauf._sofort_abschluss
        assert aufnahme.starte_auswertung is lauf._sofort_auswertung
    assert (szene.starte, aufnahme.starte_abschluss,
            aufnahme.starte_auswertung) == vorher


def test_einfaedig_stellt_auch_nach_einem_fehler_zurueck():
    vorher = szene.starte
    with pytest.raises(RuntimeError):
        with lauf.einfaedig():
            raise RuntimeError("mittendrin")
    assert szene.starte is vorher


def test_zwei_gleichzeitige_laeufe_stellen_den_betrieb_wieder_her():
    """Der Fall ``--parallel``: der zweite Lauf betritt den Umbau, waehrend
    der erste noch drin ist. Ohne Zaehler wuerde er ``_sofort_szene`` als
    Original sichern und beim Verlassen wieder einsetzen -- der Bot bliebe
    fuer den Rest des Prozesses einfaedig, und die naechste echte Szene liefe
    nicht mehr in einem eigenen Thread."""
    vorher = szene.starte
    erster, zweiter = lauf.einfaedig(), lauf.einfaedig()
    with erster:
        with zweiter:
            assert szene.starte is lauf._sofort_szene
        assert szene.starte is lauf._sofort_szene, "der erste ist noch drin"
    assert szene.starte is vorher


def test_zwei_gleichzeitige_laeufe_schreiben_in_ihr_eigenes_protokoll():
    """Auch der Kontext-Mitschrieb wird nur einmal eingebaut -- und muss
    trotzdem beim Verlassen des letzten Laufs verschwinden."""
    vorher = kontext.baue
    eins, zwei = [], []
    with lauf.kontext_protokoll(eins):
        with lauf.kontext_protokoll(zwei):
            assert kontext.baue is not vorher
        assert kontext.baue is not vorher
    assert kontext.baue is vorher


#: Die vier Ersatzpaare aus ``einfaedig()``: Original im Betrieb, Ersatz im
#: Simulator. Dieselbe Reihenfolge wie in ``lauf._ORIGINAL["einfaedig"]``.
_ERSATZPAARE = [
    (szene.starte, lauf._sofort_szene),
    (aufnahme.starte_abschluss, lauf._sofort_abschluss),
    (aufnahme.starte_auswertung, lauf._sofort_auswertung),
    (ablauf.starte_auftrag, lauf._sofort_auftrag),
]


@pytest.mark.parametrize(
    "original, ersatz", _ERSATZPAARE,
    ids=[e.__name__ for _, e in _ERSATZPAARE],
)
def test_ersatzfunktion_nimmt_die_parameter_des_originals_an(original, ersatz):
    """Jede Ersatzfunktion in ``einfaedig()`` muss die Parameter ihres
    Originals annehmen -- Namen, Reihenfolge, Defaults. Sonst faellt eine
    kuenftige Signaturdrift (wie bei ``ablauf.starte_auftrag`` seit
    Commit 347f28d, 06.09.2026: ``arbeitszeile``/``arbeitsart`` kamen dazu,
    ``lauf._sofort_auftrag`` reichte sie nicht durch) erst im bezahlten
    Simulationslauf auf statt in der Suite."""
    parameter_original = [
        (p.name, p.default) for p in inspect.signature(original).parameters.values()
    ]
    parameter_ersatz = [
        (p.name, p.default) for p in inspect.signature(ersatz).parameters.values()
    ]
    assert parameter_ersatz == parameter_original, (
        f"{ersatz.__name__} weicht von {original.__qualname__} ab: "
        f"{parameter_ersatz} != {parameter_original}"
    )


def test_sofort_auftrag_reicht_arbeitszeile_und_arbeitsart_an_auftragszug_durch(
    monkeypatch,
):
    """Der Bug aus dem ersten bezahlten Lauf: ``knoepfe._starte_auftrag``
    ruft ``ablauf.starte_auftrag`` mit acht Positionsargumenten --
    ``_sofort_auftrag`` muss ``arbeitszeile`` und ``arbeitsart`` genauso
    entgegennehmen und an ``ablauf.auftragszug`` weiterreichen wie der
    Betriebsweg (``ablauf.starte_auftrag`` startet nur einen Thread mit
    denselben Argumenten)."""
    aufgezeichnet = {}

    def falscher_auftragszug(conn, tg, klm, e, chat_id, anweisung,
                             arbeitszeile=None, arbeitsart=None):
        aufgezeichnet["conn"] = conn
        aufgezeichnet["chat_id"] = chat_id
        aufgezeichnet["anweisung"] = anweisung
        aufgezeichnet["arbeitszeile"] = arbeitszeile
        aufgezeichnet["arbeitsart"] = arbeitsart

    monkeypatch.setattr(ablauf, "auftragszug", falscher_auftragszug)
    ergebnis = lauf._sofort_auftrag(
        "conn", "tg", "klm", "e", 1, "Anweisung fuer den Zug",
        "Arbeitszeile-Text", "arbeitsart-wert",
    )
    assert aufgezeichnet == {
        "conn": "conn", "chat_id": 1, "anweisung": "Anweisung fuer den Zug",
        "arbeitszeile": "Arbeitszeile-Text", "arbeitsart": "arbeitsart-wert",
    }
    assert ergebnis is lauf._AUFTRAG_GELAUFEN


# --- Abschnitt und Protokoll ---------------------------------------------


def test_abschnitt_zeigt_kennungen_stimmen_und_bot():
    from simulation.kennzahlen import Beitrag, Zug

    zuege = [
        Zug(schritt="begriffe",
            beitraege=[Beitrag("S1", "begriffe", "Jo", "knapp", "koffer bahnhof")],
            bot=["Soll ich die so notieren?"]),
        Zug(schritt="fragen", beitraege=[], bot=["andere Phase"]),
    ]
    text = lauf.abschnitt(zuege, "begriffe")
    assert "[S1] Jo: koffer bahnhof" in text
    assert "Bot: Soll ich die so notieren?" in text
    assert "andere Phase" not in text


# --- Der Mini-Lauf --------------------------------------------------------


ANTWORTEN = {
    "gespraech": {"antwort": "Ich habe eure Begriffe. Soll ich sie festhalten?"},
    "journal": {"eintraege": []},
}


def _erkenner_antwort(nutzer: str) -> dict:
    """Erst Begriffe, dann Fragen -- am Arbeitsstand im Nutzertext erkannt,
    wie der echte Erkenner ihn sieht."""
    if "Begriffe:" not in nutzer:
        return {"aenderungen": [
            {"art": "begriffe_setzen", "wert": "Koffer, Bahnhof, Winter"}
        ]}
    return {"aenderungen": [
        {"art": "fragen_setzen", "wert": "Koffer: Was war in deinem Koffer?"}
    ]}


def _richter_antwort(nutzer: str) -> dict:
    if "stimmen_unterscheidbar" in nutzer:
        return {"szene_stimmt_zur_planung": 2, "stimmen_unterscheidbar": 1,
                "satz": "geht so"}
    return {
        "geht_auf_gesagtes_ein": 2, "bietet_an_statt_vorzuschreiben": 1,
        "phase_transparent": 1, "korrektur_angenommen": 2,
        "satz": "Der Bot bleibt am Thema.",
        "zustimmungen": ["S1"],
        "schlechteste_antwort": "Ich habe eure Begriffe. Soll ich sie festhalten?",
        "begruendung": "Fragt nach, statt zu handeln.",
    }


@pytest.fixture
def attrappe(monkeypatch, tmp_path):
    """Ersetzt ``einstellungen.laden``, ``LLM.schema`` und die drei
    Ausgabepfade -- der Lauf schreibt in tmp_path, nie ins Repository."""
    gesehen = []

    def falsche_einstellungen():
        return einstellungen.Einstellungen(
            bot_token="T", bot_name="simulation", db_pfad=str(tmp_path / "unbenutzt.db"),
            audio_verz=str(tmp_path / "audio"),
            llm_url="https://llm.test/v1/chat/completions", llm_key="K",
            llm_modell="moonshotai/Kimi-K2.6",
            stt_basis="https://stt.test", stt_produkt="P",
            erkenner_modell="google/gemma-4-31B-it",
        )

    def falsches_schema(self, chat_id, system, nutzer, schema, art,
                        modell=None, temperature=None):
        gesehen.append({"art": art, "modell": modell})
        if art == "erkenner":
            return _erkenner_antwort(nutzer)
        return ANTWORTEN[art]

    sim_klient = ClaudeAttrappe("ja passt, nimm die so", _richter_antwort)

    monkeypatch.setattr(sim.einstellungen, "laden", falsche_einstellungen)
    monkeypatch.setattr(llm.LLM, "schema", falsches_schema)
    monkeypatch.setattr(sim.claude, "Claude", lambda *a, **k: sim_klient)
    monkeypatch.setattr(bericht, "LAEUFE", tmp_path / "laeufe")
    monkeypatch.setattr(bericht, "BERICHTE", tmp_path / "berichte")
    monkeypatch.setattr(bericht, "VERLAUF", tmp_path / "berichte" / "verlauf.jsonl")
    monkeypatch.setattr(
        sim, "_schritte",
        lambda ohne: (skript.schritt_fuer("begriffe"), skript.schritt_fuer("fragen")),
    )
    return {"gesehen": gesehen, "tmp": tmp_path, "sim": sim_klient}


def test_mini_lauf_schreibt_bericht_und_json(attrappe, capsys):
    code = sim.main(["--set", "1", "--seed", "3", "--ohne-szene", "--bericht"])
    assert code == 0

    tmp = attrappe["tmp"]
    berichte = list((tmp / "berichte").glob("*.md"))
    laeufe = list((tmp / "laeufe").glob("*.md"))
    assert len(berichte) == 1 and len(laeufe) == 1

    text = berichte[0].read_text(encoding="utf-8")
    assert "## Kennzahlen" in text
    assert "## Noten des Richters" in text
    assert "Was der Prompt-Pfleger daraus ableiten koennte" in text
    assert "set1" in text

    zeilen = (tmp / "berichte" / "verlauf.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    daten = json.loads(zeilen[0])
    assert daten["mischung"] == "set1"
    assert daten["seed"] == 3
    assert daten["arbeitsstand_vollstaendig"]["begriffe"] == 1
    assert daten["arbeitsstand_vollstaendig"]["fragen"] == 1
    assert daten["schritte_gescheitert"] == []


def test_ohne_bericht_bleiben_transkript_und_verlauf_trotzdem_stehen(attrappe):
    """Ein Lauf, der Geld gekostet hat, soll beides hinterlassen -- auch wenn
    niemand an ``--bericht`` gedacht hat."""
    sim.main(["--set", "1", "--seed", "3", "--ohne-szene"])
    tmp = attrappe["tmp"]
    assert list((tmp / "laeufe").glob("*.md"))
    assert (tmp / "berichte" / "verlauf.jsonl").exists()
    assert list((tmp / "berichte").glob("2*.md")) == []


def test_bericht_mit_pfad_landet_dort(attrappe, tmp_path):
    ziel = tmp_path / "woanders" / "b.md"
    sim.main(["--set", "1", "--seed", "3", "--ohne-szene", "--bericht", str(ziel)])
    assert "## Kennzahlen" in ziel.read_text(encoding="utf-8")


def test_der_bot_laeuft_ueber_infomaniak_die_simulation_ueber_claude(attrappe):
    """Die Trennlinie des Auftrags: alles, was der Bot tut, geht an
    Infomaniak; Stimmen und Richter an den lokalen Proxy. Faellt sie, misst
    der Simulator sein eigenes Modell mit."""
    sim.main(["--set", "2", "--seed", "1", "--ohne-szene"])
    bot_arten = {(g["art"], g["modell"]) for g in attrappe["gesehen"]}
    assert ("gespraech", None) in bot_arten
    assert ("erkenner", "google/gemma-4-31B-it") in bot_arten
    assert not any(art in {"stimme", "richter"} for art, _ in bot_arten)
    assert {"stimme", "richter"} <= set(attrappe["sim"].gesehen)


def test_die_verlaufszeile_weist_beide_seiten_getrennt_aus(attrappe):
    """Kosten sind Bot-Kosten: der Simulationsklient laeuft ueber ein
    Abonnement und kostet je Aufruf nichts -- seine Aufrufe stehen als Zahl
    daneben, nicht als Betrag darin."""
    sim.main(["--set", "1", "--seed", "3", "--ohne-szene"])
    zeile = json.loads(
        (attrappe["tmp"] / "berichte" / "verlauf.jsonl").read_text(
            encoding="utf-8").splitlines()[0]
    )
    assert zeile["sim_modell"] == "claude-opus-5"
    assert zeile["sim_aufrufe"] > 0
    assert "stimme" in zeile["sim_aufrufe_je_art"]
    assert "richter" in zeile["sim_aufrufe_je_art"]
    assert "chf_simulation" not in zeile


def test_der_lauf_fasst_die_betriebsdatenbank_nicht_an(attrappe):
    """IT_DB wird ueberschrieben -- die aufruf- und vorfall-Zeilen eines
    Simulationslaufs gehoeren nicht in die Datenbank des Workshops."""
    sim.main(["--set", "1", "--seed", "1", "--ohne-szene"])
    assert not (attrappe["tmp"] / "unbenutzt.db").exists()


def test_mix_und_set_schliessen_sich_aus(attrappe):
    with pytest.raises(SystemExit):
        sim.main(["--set", "1", "--mix", "1,2"])


def test_unbekanntes_set_im_mix_bricht_ab(attrappe):
    with pytest.raises(SystemExit):
        sim.main(["--mix", "1,9"])


def test_alle_faehrt_die_drei_sets_und_birk(attrappe, monkeypatch):
    """birk laeuft in ``--alle`` immer mit: es ist das einzige Set auf echten
    Daten und damit das einzige, dessen Zahlen sich mit einem echten
    Chatverlauf vergleichen lassen."""
    monkeypatch.setattr(sim.birk, "vorhanden", lambda: False)
    with pytest.raises(SystemExit, match="birk"):
        sim.main(["--alle", "--seed", "2", "--ohne-szene"])
    zeilen = (attrappe["tmp"] / "berichte" / "verlauf.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert [json.loads(z)["mischung"] for z in zeilen] == ["set1", "set2", "set3"]


def test_mischungsname_folgt_den_argumenten():
    import argparse

    def args(**kwargs):
        return argparse.Namespace(set=None, mix=None, **kwargs)

    assert sim.mischungsname(argparse.Namespace(set=1, mix=None)) == "set1"
    assert sim.mischungsname(argparse.Namespace(set=None, mix=[1, 3])) == "mix1-3"
    assert sim.mischungsname(argparse.Namespace(set=None, mix=None)) == "alle15"


# --- 429 ------------------------------------------------------------------


def test_429_wird_nach_pause_wiederholt(monkeypatch):
    """Ein Simulationslauf sind einige hundert Aufrufe in Folge -- deutlich
    ueber der gemessenen Drosselgrenze von rund fuenfzig."""
    schlaefer = []
    monkeypatch.setattr(sim.time, "sleep", lambda s: schlaefer.append(s))
    zaehler = {"n": 0}

    class Innen:
        def schema(self, *a, **k):
            zaehler["n"] += 1
            if zaehler["n"] == 1:
                raise llm.LLMFehler("Sprachmodell lehnte den Aufruf ab: HTTP 429")
            return {"antwort": "da"}

    klm = sim.LLMMitPause(Innen(), pause=0)
    assert klm.schema(1, "s", "n", {}, "gespraech") == {"antwort": "da"}
    assert zaehler["n"] == 2
    assert schlaefer == [0]


def test_andere_fehler_werden_nicht_wiederholt(monkeypatch):
    zaehler = {"n": 0}

    class Innen:
        def prosa(self, *a, **k):
            zaehler["n"] += 1
            raise llm.LLMFehler("Sprachmodell lehnte den Aufruf ab: HTTP 502")

    with pytest.raises(llm.LLMFehler):
        sim.LLMMitPause(Innen(), pause=0).prosa(1, "s", "n", "szene")
    assert zaehler["n"] == 1


# --- Bericht --------------------------------------------------------------


def _zahlen(**abweichungen):
    grund = {
        "phase_erreicht": 6, "phase_erreicht_name": "6 · Szenen", "phase_soll": 6,
        "arbeitsstand_vollstaendig": {"begriffe": 1, "fragen": 1, "kernthema": 1,
                                      "figuren_3": 1, "format": 1},
        "zustimmungen": 4, "zustimmungen_gespeichert": 4,
        "echo": 0, "rueckfragen_vor_szene": 1, "behauptete_schreibvorgaenge": 0,
        "namensanrede": 0, "laenge_bot": 420, "bot_antworten": 30,
        "stimm_nachrichten": 25, "schritte_gescheitert": [], "dauer_s": 300.0,
        "verdichtungen": 5, "themen": 15, "zitate_geprueft": 15,
        "zitate_soll": 15, "zitate_soll_gefunden": 12, "zitate_soll_vermisst": [],
        "interviews_soll": 5, "notausgaenge": 0,
        "chf_bot": 0.4, "chf_je_art": {"gespraech": 0.3, "erkenner": 0.1},
        "token_ein": 10, "token_aus": 10, "aufrufe": 40,
        "sim_aufrufe": 30, "sim_aufrufe_je_art": {"stimme": 22, "richter": 8},
        "sim_token_ein": 100, "sim_token_aus": 20, "sim_fehler": 0,
    }
    grund.update(abweichungen)
    return grund


def test_ableitung_liefert_immer_genau_drei_saetze():
    assert len(bericht.ableitung(_zahlen())) == 3
    schlecht = _zahlen(
        behauptete_schreibvorgaenge=3, zustimmungen_gespeichert=1, echo=2,
        laenge_bot=1200, namensanrede=4, verdichtungen=2,
        arbeitsstand_vollstaendig={"begriffe": 1, "fragen": 0, "kernthema": 0,
                                   "figuren_3": 0, "format": 0},
    )
    saetze = bericht.ableitung(schlecht)
    assert len(saetze) == 3
    assert "behaupten eine" in saetze[0]


def test_ableitung_nennt_bei_gutem_lauf_keinen_fehler():
    saetze = bericht.ableitung(_zahlen())
    assert all(satz == bericht._FALLBACK for satz in saetze)


def test_kennzahlen_tabelle_nennt_soll_und_urteil():
    zeilen = bericht.kennzahlen_tabelle(_zahlen(echo=3))
    tabelle = "\n".join(zeilen)
    assert "| echo | 3 | 0 | **daneben** |" in tabelle
    assert "| namensanrede | 0 | 0 | ok |" in tabelle


def test_kennung_ist_datum_mischung_seed():
    assert bericht.kennung("set1", 7, tag="2026-09-05") == "2026-09-05-set1-7"


# --- Die Kennzahlen der Gegenpruefung im Bericht ---------------------------


def _zahlen_mit(**extra):
    """Eine Kennzahlenmenge, die ``kennzahlen_tabelle`` durchlaeuft."""
    grund = {
        "festlegungen": 0, "festlegungen_je_bereich": {},
        "festlegungsproben": 3, "festlegungsproben_erhalten": 3,
        "festlegungsproben_nur_journal": [], "festlegungsproben_nirgends": [],
        "szenen_aktiv": 3, "szenen_ersetzt": 0, "szenen_neuaufbauten": 0,
        "szenen_form_verloren": 0, "szenenfolge_laeufe": 1,
        "kurzgeschichte_laeufe": 0, "szenenfolge_nach_richtung": 0,
        "szenen_aus_richtung": True,
    }
    grund.update(extra)
    return grund


def test_die_gegenpruefzeilen_stehen_mit_sollwert_da():
    zeilen = "\n".join(bericht._gegenpruefzeilen(_zahlen_mit()))
    assert "Festlegungsproben erhalten" in zeilen
    assert "3/3" in zeilen
    assert "Szenen neu aufgebaut" in zeilen
    assert "Szenenfolge-Lauf nach der Richtungswahl" in zeilen
    assert "**daneben**" not in zeilen


def test_ein_verlust_wird_als_daneben_markiert():
    zeilen = "\n".join(bericht._gegenpruefzeilen(_zahlen_mit(
        festlegungsproben_erhalten=1,
        festlegungsproben_nur_journal=["Outsider"],
        festlegungsproben_nirgends=["hoechstens eine Seite"],
    )))
    assert "1/3" in zeilen
    assert "**daneben**" in zeilen


def test_ein_neuaufbau_wird_als_daneben_markiert():
    zeilen = "\n".join(bericht._gegenpruefzeilen(_zahlen_mit(
        szenen_neuaufbauten=2, szenen_form_verloren=3,
        szenenfolge_nach_richtung=1, szenen_aus_richtung=False,
    )))
    assert zeilen.count("**daneben**") >= 3


def test_eine_alte_verlaufszeile_ohne_die_schluessel_bleibt_lesbar():
    """Wie bei den Knopfzahlen (06.09.2026): fehlt der Block, steht er nicht
    da -- ein KeyError im Bericht waere schlimmer als eine fehlende Zeile."""
    assert bericht._gegenpruefzeilen({"echo": 0}) == []


def test_die_verlaufszeile_traegt_die_mutation():
    class _Ergebnis:
        urteile = {}
        szenen = []
        gezogene = []
        personen = []
        szenen_urteil = {}

    kopf = {"kennung": "k", "mischung": "set1", "seed": 1, "git": "abc",
            "llm_modell": "kimi", "erkenner_modell": "gemma",
            "sim_modell": "claude-opus-5", "mutation": "festlegung_verloren"}
    zeile = bericht.verlaufszeile(_zahlen_mit(), _Ergebnis(), kopf)
    assert zeile["mutation"] == "festlegung_verloren"

    kopf_ohne = {**kopf}
    kopf_ohne.pop("mutation")
    assert bericht.verlaufszeile(_zahlen_mit(), _Ergebnis(), kopf_ohne)["mutation"] == ""


# --- Hintergrundlaeufe abwarten (30.09.2026) -------------------------------
#
# lauf.einfaedig() macht szene.starte und drei Geschwister synchron -- nicht
# aber szenenfolge.starte_geschichte_szenen, schaerfung.starte,
# sprachstil.starte, kurzgeschichte.starte. Deren Wirkung landete zu einem
# beliebigen Zeitpunkt in der Datenbank, unter Umstaenden nach conn.close().

import threading
import time


def test_warte_auf_hintergrund_wartet_auf_neue_threads():
    gemerkt = []

    def arbeite():
        time.sleep(0.05)
        gemerkt.append("da")

    vorher = frozenset(threading.enumerate())
    threading.Thread(target=arbeite, daemon=True).start()
    abgewartet = lauf.warte_auf_hintergrund(vorher, grenze_s=5.0)
    assert gemerkt == ["da"]
    assert abgewartet == 1


def test_warte_auf_hintergrund_ignoriert_alte_threads():
    """Bei ``--parallel`` laufen zwei Laeufe in Threads. Der eine darf nicht
    auf den anderen warten -- gewartet wird nur auf Threads, die es beim
    Beginn dieses Zuges noch nicht gab."""
    halt = threading.Event()
    alt = threading.Thread(target=halt.wait, daemon=True)
    alt.start()
    try:
        vorher = frozenset(threading.enumerate())
        assert alt in vorher
        start = time.monotonic()
        assert lauf.warte_auf_hintergrund(vorher, grenze_s=5.0) == 0
        assert time.monotonic() - start < 1.0
    finally:
        halt.set()


def test_warte_auf_hintergrund_gibt_nach_der_grenze_auf():
    """Ein haengender Lauf darf den Simulator nicht festhalten: nach der
    Grenze geht es weiter, und der Bericht zeigt am fehlenden Zielzustand,
    dass etwas nicht fertig wurde."""
    halt = threading.Event()
    vorher = frozenset(threading.enumerate())
    threading.Thread(target=halt.wait, daemon=True).start()
    try:
        start = time.monotonic()
        lauf.warte_auf_hintergrund(vorher, grenze_s=0.2)
        assert time.monotonic() - start < 2.0
    finally:
        halt.set()


def test_der_lauf_merkt_sich_die_threads_beim_zuganfang(conn, einst):
    """``_zug`` legt die Momentaufnahme an, ``_schliesse_zug`` wartet -- damit
    die Nachrichten des Hintergrundlaufs noch in DIESEN Zug fallen und nicht
    in den naechsten."""
    from simulation.attrappe import TelegramAttrappe

    durchlauf = lauf.Lauf(
        conn, TelegramAttrappe(), None, einst, None,
        gezogene=[], seed=1, schritte=[],
    )
    zug = durchlauf._zug()
    assert isinstance(durchlauf._threads_vorher, frozenset)
    assert threading.current_thread() in durchlauf._threads_vorher
    assert zug is durchlauf.ergebnis.zuege[-1]


# --- Review-Befunde zu Aufgabe 7: Handlungen des Simulators ---------------
#
# _druecke_interview_starten und _notausgang rufen selbst Bot-Code. Ein dort
# gestarteter Thread stand frueher schon in der Momentaufnahme des Zuges und
# wurde nie abgewartet.


def _starte_nachzuegler(gemerkt, text="da"):
    def arbeite():
        time.sleep(0.05)
        gemerkt.append(text)

    threading.Thread(target=arbeite, daemon=True).start()


def _leerer_lauf(conn, einst, schritte=()):
    from simulation.attrappe import TelegramAttrappe

    return lauf.Lauf(
        conn, TelegramAttrappe(), None, einst, None,
        gezogene=[], seed=1, schritte=list(schritte),
    )


def test_der_knopfdruck_wartet_auf_seinen_hintergrundlauf(conn, einst, monkeypatch):
    from interview_theater import knoepfe as knoepfe_modul

    gemerkt = []
    monkeypatch.setattr(knoepfe_modul, "behandle",
                        lambda *a, **k: _starte_nachzuegler(gemerkt))
    durchlauf = _leerer_lauf(conn, einst)
    repo.sichere_gruppe(conn, lauf.CHAT_ID, einst.bot_name, lauf.CHAT_TITEL)
    durchlauf.tg.knoepfe.append({
        "message_id": 7,
        "knoepfe": [(knoepfe_modul._TEXT_AUFNAHME_STARTEN, "k:1")],
    })
    durchlauf._druecke_interview_starten()
    assert gemerkt == ["da"]
    assert durchlauf.ergebnis.zuege[-1].marke == "knopf"


def test_der_notausgang_wartet_auf_seinen_hintergrundlauf(conn, einst, monkeypatch):
    from types import SimpleNamespace

    gemerkt = []
    monkeypatch.setattr(repo, "setze_interviewmodus", lambda *a, **k: None)
    monkeypatch.setattr(repo, "hole_aufnahme", lambda *a, **k: {"status": "fertig"})
    monkeypatch.setattr(aufnahme, "verarbeite",
                        lambda *a, **k: _starte_nachzuegler(gemerkt))
    durchlauf = _leerer_lauf(conn, einst)
    durchlauf._notausgang(1, SimpleNamespace(name="Interview X"))
    assert gemerkt == ["da"]
    assert durchlauf.ergebnis.notausgaenge == 1
    assert "Notausgang" in durchlauf.ergebnis.zuege[-1].notiz


def test_fahre_wartet_am_ende_auf_alles_seit_laufbeginn(conn, einst):
    """Ein Thread, der ausserhalb jedes Zuges entsteht (hier aus der
    Zielzustand-Pruefung), wird vor Kennzahlen und conn.close() abgewartet."""
    gemerkt = []

    def fertig(_conn, _chat_id, _merker):
        _starte_nachzuegler(gemerkt)
        return True

    schritt = skript.Schritt("probe", "Probe", "nichts", fertig)
    durchlauf = _leerer_lauf(conn, einst, [schritt])
    durchlauf.fahre()
    assert gemerkt == ["da"]


def test_lauf_threads_des_nachbarn_werden_nie_abgewartet():
    halt = threading.Event()
    vorher = frozenset(threading.enumerate())
    threading.Thread(target=halt.wait, daemon=True,
                     name=f"{lauf.LAUF_THREAD_PRAEFIX}-2").start()
    try:
        start = time.monotonic()
        assert lauf.warte_auf_hintergrund(vorher, grenze_s=5.0) == 0
        assert time.monotonic() - start < 1.0
    finally:
        halt.set()
