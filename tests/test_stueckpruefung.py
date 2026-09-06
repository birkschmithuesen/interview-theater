"""Tests fuer die Schaerfung des GANZEN Stuecks (Phase 7, 06.09.2026).

Der Auftrag von Birk, 09:20: *"Das ganze Stueck -- ohne sonstige
Informationen -- wird als kompletter Szenentext an ein Judge-LLM gegeben und
im Durchlauf mit neuen Fragen bewertet, die Verbesserungsmoeglichkeiten
aufzeigen."*

Gemessen wird genau das:

* **die geschlossene Eingabe** -- nur das Textbuch, kein Arbeitsstand, keine
  Interviews, keine Zitate, kein Chat (der Negativtest ist der wichtigste
  hier: wer spaeter aus Bequemlichkeit einen Block dazunimmt, soll stolpern),
* das **Marker-Parsing** der Antwort (Bewertung, Begruendung, Vorschlag,
  Szenennummer) samt Verwerfen dessen, was nicht zuordenbar ist,
* die **Speicherung** in ``stueckpruefung`` (additiv, mit Runde),
* die **Nachrichten und Knoepfe** im Chat,
* dass *"Szene N ueberarbeiten"* den bestehenden Weg geht (Szenenauftrag mit
  dem Vorschlag als Regie-Notiz) und dabei **kein Modell im Handler** ruft,
* dass *"Noch eine Pruefrunde"* die Rundennummer erhoeht.

Kein Netzzugriff: das Sprachmodell ist eine Attrappe.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, stueckpruefung

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


class LLMAttrappe:
    """Liefert eine feste Prosa-Antwort und merkt sich, was sie sah."""

    def __init__(self, antwort=""):
        self.antwort = antwort
        self.aufrufe = 0
        self.gesehen = {}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe += 1
        self.gesehen = {"system": system, "nutzer": nutzer, "art": art}
        return self.antwort


ANTWORT = """BEFUND: Spannungsbogen
BEWERTUNG: 3
BEGRUENDUNG: Der Auftakt traegt, danach flacht es ab. Szene 2 wiederholt, was Szene 1 schon gezeigt hat.
VORSCHLAG: Kuerz Szene 2 auf den Moment, in dem die Entscheidung faellt.
SZENE: 2

BEFUND: Figuren
BEWERTUNG: 4
BEGRUENDUNG: Beide sind unterscheidbar. Die zweite bleibt im Ton etwas blass.
VORSCHLAG: Gib ihr in Szene 1 einen Satz, den nur sie sagen wuerde.
SZENE: 1

BEFUND: Spannung
BEWERTUNG: 2
BEGRUENDUNG: Man weiss von Anfang an, wie es ausgeht. Es fehlt ein Punkt, an dem es kippen koennte.
VORSCHLAG: Lass in Szene 2 offen, wer nachgibt.
SZENE: 2

BEFUND: Nachvollziehbarkeit
BEWERTUNG: 4
BEGRUENDUNG: Die Motivationen stehen da. Der Uebergang zwischen den Szenen ist knapp.
VORSCHLAG: Nimm den Ortswechsel in die erste Replik von Szene 2.
SZENE: 2

BEFUND: Anfang und Ende
BEWERTUNG: 3
BEGRUENDUNG: Der Anfang macht eine Frage auf. Das Ende beantwortet eine andere.
VORSCHLAG: Greif im Schluss das Bild vom Anfang noch einmal auf.
SZENE: 2

BEFUND: Sprechbarkeit
BEWERTUNG: 5
BEGRUENDUNG: Die Saetze sind kurz und liegen gut im Mund. Nichts stolpert.
VORSCHLAG: So lassen.
SZENE: -
"""


def _stueck(conn):
    """Zwei Szenen mit Volltext -- der Stand, den Phase 7 voraussetzt."""
    eins = repo.lege_szene_an(conn, 1, 1, "Am Kiosk", "sie treffen sich", None)
    repo.setze_szenenfeld(conn, eins, "form", "Dialog")
    repo.aktualisiere_szene(conn, eins, "Am Kiosk", "sie treffen sich", "A: Da bist du.")
    zwei = repo.lege_szene_an(conn, 1, 2, "Im Treppenhaus", "sie streiten", None)
    repo.setze_szenenfeld(conn, zwei, "form", "Dialog")
    repo.aktualisiere_szene(
        conn, zwei, "Im Treppenhaus", "sie streiten", "B: Und jetzt?"
    )
    return conn


@pytest.fixture
def stueck(conn):
    return _stueck(conn)


def _druck(daten):
    return {
        "callback_query_id": "q1", "data": daten, "chat_id": 1,
        "chat_titel": "Testgruppe", "message_id": 777,
    }


def _knopf(tg, beschriftung):
    for _, _, leiste in tg.knoepfe:
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(
        f"kein Knopf {beschriftung!r}, gesehen: "
        f"{[b for _, _, l in tg.knoepfe for b, _ in l]}"
    )


# --- Die Eingabe: NUR das Textbuch ----------------------------------------


def test_der_nutzertext_ist_das_textbuch(stueck):
    nutzer = stueckpruefung.baue_nutzertext(stueck, 1)

    assert "Szene 1: Am Kiosk (Dialog)" in nutzer
    assert "A: Da bist du." in nutzer
    assert "Szene 2: Im Treppenhaus (Dialog)" in nutzer
    assert "B: Und jetzt?" in nutzer
    # Die Reihenfolge ist die des Stuecks, nicht die der Datenbank-ids.
    assert nutzer.index("Szene 1") < nutzer.index("Szene 2")


def test_kein_arbeitsstand_kein_interview_kein_zitat(stueck):
    """**Der Kern des Auftrags** (Birk: "ohne sonstige Informationen"). Der
    Richter soll lesen wie ein Zuschauer im Saal: wer weiss, was gemeint war,
    sieht nicht mehr, was dasteht."""
    repo.setze_arbeitsstand(stueck, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_arbeitsstand(stueck, 1, "geschichte", "Zwei verlieren sich.")
    repo.setze_arbeitsstand(stueck, 1, "kernthema", "Arbeit, die niemand sieht")
    repo.setze_figur(stueck, 1, "Nesrin", "will weg und bleibt")
    kopf_id = repo.lege_interview_an(stueck, 1)
    repo.setze_transkript(stueck, kopf_id, "Ich hatte nur einen Koffer dabei.")
    repo.speichere_verdichtung(
        stueck, 1, kopf_id, "Sie erzaehlt vom Ankommen.",
        [{"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer dabei.",
          "zitat_geprueft": 1}],
    )
    repo.merke_nachricht(
        stueck, 1, 42, "Ada", 0, "text", "Koennen wir das anders machen?",
        repo._jetzt(),
    )

    nutzer = stueckpruefung.baue_nutzertext(stueck, 1)

    for verboten in ("Treppenhaus, nachts", "Zwei verlieren sich",
                     "Arbeit, die niemand sieht", "Nesrin", "Koffer",
                     "Ankommen", "Koennen wir das anders machen"):
        assert verboten not in nutzer, verboten


def test_szenen_ohne_volltext_stehen_nicht_im_prompt(conn):
    """Ein "(noch nicht geschrieben)" waere fuer einen Richter, der wie ein
    Zuschauer liest, eine Behauptung ueber etwas, das er nicht sieht."""
    eins = repo.lege_szene_an(conn, 1, 1, "Am Kiosk", "sie treffen sich", None)
    repo.aktualisiere_szene(conn, eins, "Am Kiosk", "kurz", "A: Da bist du.")
    repo.lege_szene_an(conn, 1, 2, "Im Treppenhaus", "sie streiten", None)

    nutzer = stueckpruefung.baue_nutzertext(conn, 1)

    assert "Szene 1" in nutzer
    assert "Szene 2" not in nutzer
    assert "noch nicht geschrieben" not in nutzer


# --- Die Antwort: Marker-Parsing ------------------------------------------


def test_zerlege_liest_alle_sechs_befunde():
    befunde = stueckpruefung.zerlege(ANTWORT)

    assert [b["frage"] for b in befunde] == [
        name for name, _ in stueckpruefung.FRAGEN
    ]
    erster = befunde[0]
    assert erster["bewertung"] == 3
    assert erster["begruendung"].startswith("Der Auftakt traegt")
    assert erster["vorschlag"].startswith("Kuerz Szene 2")
    assert erster["szene_nummer"] == 2
    assert befunde[-1]["szene_nummer"] is None, "'-' ist keine Szene"


def test_zerlege_verwirft_was_sich_keiner_frage_zuordnen_laesst():
    """Dieselbe Haltung wie in ``schaerfung.mappe``: verworfen, nicht
    geraten."""
    befunde = stueckpruefung.zerlege(
        "BEFUND: Buehnenbild\nBEWERTUNG: 2\nBEGRUENDUNG: Es fehlt.\n"
        "VORSCHLAG: Stell einen Stuhl hin.\nSZENE: 1"
    )

    assert befunde == []


def test_zerlege_nimmt_je_frage_nur_den_ersten_block():
    doppelt = ANTWORT + "\nBEFUND: Spannungsbogen\nBEWERTUNG: 1\n"
    befunde = stueckpruefung.zerlege(doppelt)

    assert len([b for b in befunde if b["frage"] == "Spannungsbogen"]) == 1
    assert befunde[0]["bewertung"] == 3, "der erste gilt"


@pytest.mark.parametrize("zeile,erwartet", [
    ("BEWERTUNG: 3", 3),
    ("BEWERTUNG: 3/5", 3),
    ("BEWERTUNG: 3 von 5", 3),
    ("BEWERTUNG: gut", None),
])
def test_die_bewertung_wird_tolerant_gelesen(zeile, erwartet):
    befunde = stueckpruefung.zerlege(f"BEFUND: Spannungsbogen\n{zeile}")

    assert befunde[0]["bewertung"] == erwartet


# --- Speicherung ----------------------------------------------------------


def test_ein_lauf_speichert_alle_befunde_mit_runde(stueck, einst):
    klm = LLMAttrappe(ANTWORT)

    anzahl, runde = stueckpruefung.pruefe(klm, stueck, einst, 1)

    assert anzahl == 6
    assert runde == 1
    zeilen = repo.stueckpruefungen(stueck, 1)
    assert [z["frage"] for z in zeilen] == [n for n, _ in stueckpruefung.FRAGEN]
    assert zeilen[0]["bewertung"] == 3
    assert zeilen[0]["szene_nummer"] == 2
    assert klm.gesehen["art"] == stueckpruefung.ART


def test_die_zweite_runde_kommt_daneben_nicht_darueber(stueck, einst):
    """Additiv wie die Schaerfung: die Gruppe soll sehen, ob sich etwas
    gebessert hat."""
    klm = LLMAttrappe(ANTWORT)
    stueckpruefung.pruefe(klm, stueck, einst, 1)

    _, runde = stueckpruefung.pruefe(klm, stueck, einst, 1)

    assert runde == 2
    assert repo.letzte_pruefrunde(stueck, 1) == 2
    assert len(repo.stueckpruefungen(stueck, 1)) == 12
    assert len(repo.stueckpruefungen(stueck, 1, runde=1)) == 6


def test_ein_lauf_schreibt_eine_journalzeile(stueck, einst):
    stueckpruefung.pruefe(LLMAttrappe(ANTWORT), stueck, einst, 1)

    zeilen = [(e["art"], e["text"]) for e in repo.journal(stueck, 1)]
    assert ("entschieden", "Stueckpruefung Runde 1: 6 Befunde") in zeilen


def test_ohne_szenentext_laeuft_kein_modell(conn, einst):
    """Ein Urteil ueber ein Stueck, das es nicht gibt, waere keins."""
    klm = LLMAttrappe(ANTWORT)

    with pytest.raises(stueckpruefung.PruefungFehler) as fehler:
        stueckpruefung.pruefe(klm, conn, einst, 1)

    assert klm.aufrufe == 0
    assert "noch keine Szene" in str(fehler.value)


def test_ein_zu_langes_textbuch_wird_nicht_gekuerzt(stueck, einst, monkeypatch):
    """Birk, 06.09.2026: "Nichts darf stillschweigend abgeschnitten werden."
    Passt das Textbuch nicht, gibt es eine klare Meldung und keinen Lauf."""
    monkeypatch.setenv("IT_SZENE_TOKEN_MAX", "1000")
    from interview_theater import szene as szene_modul

    monkeypatch.setattr(szene_modul, "schaetze_token", lambda t: 99_999)
    klm = LLMAttrappe(ANTWORT)

    with pytest.raises(stueckpruefung.PruefungFehler) as fehler:
        stueckpruefung.pruefe(klm, stueck, einst, 1)

    assert klm.aufrufe == 0
    assert "laenger, als ich am Stueck lesen kann" in str(fehler.value)
    arten = [
        z["art"] for z in stueck.execute(
            "SELECT art FROM vorfall WHERE chat_id = 1"
        )
    ]
    assert arten == ["stueckpruefung_zu_lang"]


# --- Was im Chat steht ----------------------------------------------------


def test_je_frage_eine_nachricht_mit_knoepfen(stueck, einst, tg):
    stueckpruefung.pruefe(LLMAttrappe(ANTWORT), stueck, einst, 1)

    verschickt = knoepfe.zeige_stueckpruefung(stueck, tg, 1, 1)

    assert verschickt == 6
    texte = [t for _, t in tg.gesendet]
    assert any("Runde 1" in t for t in texte)
    assert any(t.startswith("Spannungsbogen 3/5 - Der Auftakt traegt") for t in texte)
    assert any("Vorschlag: Szene 2 -" in t for t in texte)
    # Je Befund mit Szenennummer der Ueberarbeiten-Knopf, immer "Lassen".
    beschriftungen = [b for _, _, leiste in tg.knoepfe for b, _ in leiste]
    assert "Szene 2 ueberarbeiten" in beschriftungen
    assert beschriftungen.count("Lassen") == 6
    # Ohne Szenennummer gibt es nichts zu ueberarbeiten -- nur "Lassen".
    letzter = [leiste for _, _, leiste in tg.knoepfe][-2]
    assert [b for b, _ in letzter] == ["Lassen"]


def test_am_ende_stehen_pruefrunde_textbuch_und_die_szenen(stueck, einst, tg):
    stueckpruefung.pruefe(LLMAttrappe(ANTWORT), stueck, einst, 1)

    knoepfe.zeige_stueckpruefung(stueck, tg, 1, 1)

    letzte = [b for b, _ in tg.knoepfe[-1][2]]
    assert letzte[:2] == ["Noch eine Pruefrunde", knoepfe.TEXT_TEXTBUCH_KNOPF]
    assert "Szene 1 ansehen" in letzte
    assert "Szene 2 ansehen" in letzte


def test_szene_ueberarbeiten_startet_den_auftrag_mit_der_notiz(
    stueck, einst, tg, monkeypatch,
):
    """Der bestehende Weg "Passt, aber anders": ein Szenenauftrag mit dem
    Vorschlag als Regie-Notiz -- und **kein Modellaufruf im Handler**
    (Zusage 2), ``ablauf.starte_auftrag`` gibt an einen Thread ab."""
    from interview_theater import ablauf

    auftraege = []
    monkeypatch.setattr(
        ablauf, "starte_auftrag",
        lambda conn, tg_, klm, e, chat_id, anweisung: auftraege.append(anweisung),
    )
    stueckpruefung.pruefe(LLMAttrappe(ANTWORT), stueck, einst, 1)
    knoepfe.zeige_stueckpruefung(stueck, tg, 1, 1)

    knoepfe.behandle(
        stueck, tg, object(), einst, _druck(_knopf(tg, "Szene 2 ueberarbeiten")),
    )

    assert len(auftraege) == 1
    assert auftraege[0].startswith("Schreib Szene 2 neu.")
    assert "Spannungsbogen: Kuerz Szene 2" in auftraege[0]
    # Nach einer Ueberarbeitung gilt der Stand als ungeprueft -- gesagt, nicht
    # automatisch nachgelaufen.
    assert any("ueberholt" in t for _, t in tg.gesendet)


def test_lassen_schreibt_nichts_und_ruft_kein_modell(stueck, einst, tg):
    stueckpruefung.pruefe(LLMAttrappe(ANTWORT), stueck, einst, 1)
    knoepfe.zeige_stueckpruefung(stueck, tg, 1, 1)
    vorher = len(repo.journal(stueck, 1))

    knoepfe.behandle(stueck, tg, None, einst, _druck(_knopf(tg, "Lassen")))

    assert len(repo.journal(stueck, 1)) == vorher
    assert tg.gesendet[-1][1] == knoepfe._TEXT_PRUEFUNG_LASSEN


def test_noch_eine_pruefrunde_zaehlt_hoch(stueck, einst, tg, monkeypatch):
    """Der Knopf ruft kein Modell im Handler: ``starte_stueckpruefung`` gibt
    an einen Thread ab (dasselbe Muster wie die Schaerfung)."""
    gestartet = []
    monkeypatch.setattr(
        stueckpruefung, "starte",
        lambda *a, **k: gestartet.append(True) or None,
    )
    stueckpruefung.pruefe(LLMAttrappe(ANTWORT), stueck, einst, 1)
    knoepfe.zeige_stueckpruefung(stueck, tg, 1, 1)

    knoepfe.behandle(
        stueck, tg, object(), einst, _druck(_knopf(tg, "Noch eine Pruefrunde")),
    )

    assert gestartet == [True]
    # Die naechste Runde zaehlt aus den Daten hoch, nicht aus einem Merkposten.
    assert repo.letzte_pruefrunde(stueck, 1) + 1 == 2


def test_der_phaseneintritt_stoesst_die_pruefung_an(stueck, einst, tg, monkeypatch):
    """Beim Eintritt in Phase 7 laeuft EIN Lauf automatisch -- im Thread,
    ohne Modellaufruf im Knopf-Handler (Zusage 2)."""
    gestartet = []
    monkeypatch.setattr(
        stueckpruefung, "starte",
        lambda *a, **k: gestartet.append(True) or None,
    )

    knoepfe.eintritt_in_phase(stueck, tg, object(), einst, 1, 7)

    assert gestartet == [True]
    # Bis der Befund da ist, steht die Uebersicht mit dem Textbuch-Knopf.
    assert knoepfe.TEXT_TEXTBUCH_KNOPF in [
        b for _, _, leiste in tg.knoepfe for b, _ in leiste
    ]


def test_die_pruefung_braucht_alle_szenentexte(stueck):
    """``phasen.voraussetzungen[7]``: ein Urteil ueber ein Stueck, dem eine
    Szene fehlt, ist keins."""
    assert phasen.voraussetzungen(stueck, 1)[7] is True

    repo.lege_szene_an(stueck, 1, 3, "Am Bahnhof", "sie geht", None)
    assert phasen.voraussetzungen(stueck, 1)[7] is False
