"""Tests fuer den Journal-Extraktor (gedaechtnis-extraktion-agenten.md § 6,
§ 8; SPEC-kontext-architektur.md § 4.3).

Anders als der Absichtserkenner (der jeden Zug ueber die letzten paar
Nachrichten laeuft) laeuft der Journal-Extraktor nur bei VERDRAENGUNG: wenn
ein Abschnitt aus dem kurzen Fenster (kontext.BUDGETS["fenster"]) faellt und
dieser Abschnitt SCHWELLE_VERDRAENGUNG geschaetzte Token uebersteigt. Er
sieht dann genau diesen Abschnitt, nicht das ganze Gespraech, und schreibt
ausschliesslich die Kategorie "vorgeschlagen" ins Journal -- "verworfen" und
"entschieden" bleiben Sache des Absichtserkenners (Arbeitsteilung gegen
Doppeleintraege).

Wie in test_erkenner.py: das Sprachmodell wird durch eine Attrappe mit einer
.schema()-Methode ersetzt. Kein Netzzugriff.
"""

import pytest

from theatersoap import journal, kontext, repo


class LLMAttrappe:
    """Ersetzt theatersoap.llm.LLM in Tests: liefert eine vorbereitete Antwort
    (oder wirft einen vorbereiteten Fehler), zaehlt die Aufrufe und
    zeichnet die zuletzt gesehenen Parameter auf."""

    def __init__(self, antwort=None, fehler=None):
        self._antwort = antwort
        self._fehler = fehler
        self.aufrufe = 0
        self.gesehen = {}

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
        self.aufrufe += 1
        self.gesehen = {
            "chat_id": chat_id,
            "system": system,
            "nutzer": nutzer,
            "schema": schema,
            "art": art,
            "modell": modell,
            "temperature": temperature,
        }
        if self._fehler is not None:
            raise self._fehler
        return self._antwort


def _nachricht(conn, chat_id, message_id, text, absender="Mert", ist_bot=0):
    repo.merke_nachricht(conn, chat_id, message_id, absender, ist_bot, "text", text, repo._jetzt())


def _lang(anzahl_token: int, buchstabe: str = "x") -> str:
    """Liefert einen Text, dessen kontext.schaetze() ungefaehr anzahl_token
    ergibt (Zeichen // 3) -- plus etwas Puffer, damit der Sprecherzeilen-
    Praefix ("Name: ") die Schaetzung nicht unter das Ziel drueckt.
    ``buchstabe`` erlaubt es, verdraengten und Fenster-Fuellstoff in Tests
    optisch auseinanderzuhalten."""
    return buchstabe * (anzahl_token * 3 + 30)


# ---------------------------------------------------------------------------
# Verdraengungsberechnung -- eigenstaendige, testbare Funktion
# ---------------------------------------------------------------------------


def _msg(message_id, text, ist_bot=0, absender="Mert"):
    return {
        "message_id": message_id, "ist_bot": ist_bot, "absender": absender,
        "typ": "text", "text": text,
    }


def test_verdraengung_ohne_nachrichten_ist_leer():
    assert journal.berechne_verdraengten_abschnitt([]) == []


def test_alles_passt_ins_fenster_nichts_verdraengt():
    """Ein einziger kurzer Satz ist weit unter dem Fensterbudget -- nichts
    ist herausgefallen, die leere Liste ist der Normalfall."""
    nachrichten = [_msg(1, "kurzer Satz")]
    assert journal.berechne_verdraengten_abschnitt(nachrichten) == []


def test_verdraengter_abschnitt_unter_schwelle_loest_nicht_aus():
    """Ein Abschnitt faellt zwar aus dem Fenster, ist aber kleiner als
    SCHWELLE_VERDRAENGUNG -- der Extraktor soll noch warten, statt bei jedem
    kleinen Ausschnitt einen eigenen Modellaufruf zu machen."""
    verdraengt = [_msg(1, "kurz")]  # winzig, weit unter der Schwelle
    fenster = [_msg(2, _lang(kontext.BUDGETS["fenster"] + 500))]  # fuellt das Fenster allein
    nachrichten = verdraengt + fenster

    assert journal.berechne_verdraengten_abschnitt(nachrichten) == []


def test_verdraengter_abschnitt_ueber_schwelle_loest_aus_und_liefert_nur_ihn():
    verdraengt = [_msg(1, _lang(journal.SCHWELLE_VERDRAENGUNG + 200))]
    fenster = [_msg(2, _lang(kontext.BUDGETS["fenster"] + 500))]
    nachrichten = verdraengt + fenster

    ergebnis = journal.berechne_verdraengten_abschnitt(nachrichten)

    assert [n["message_id"] for n in ergebnis] == [1]


def test_verdraengter_abschnitt_mehrere_nachrichten_zusammen_ueber_schwelle():
    verdraengt = [
        _msg(1, _lang(journal.SCHWELLE_VERDRAENGUNG // 2 + 100)),
        _msg(2, _lang(journal.SCHWELLE_VERDRAENGUNG // 2 + 100)),
    ]
    fenster = [_msg(3, _lang(kontext.BUDGETS["fenster"] + 500))]
    nachrichten = verdraengt + fenster

    ergebnis = journal.berechne_verdraengten_abschnitt(nachrichten)

    assert [n["message_id"] for n in ergebnis] == [1, 2]


# ---------------------------------------------------------------------------
# extrahiere() -- der ganze Ablauf: erkennen, schreiben, Wasserzeichen
# ---------------------------------------------------------------------------


def _fuelle_verdraengung(conn, chat_id, ab_message_id=1):
    """Legt genug Nachrichten an, dass tatsaechlich etwas verdraengt wird:
    eine grosse alte Nachricht (ueber der Schwelle) gefolgt von einer
    grossen neuen Nachricht, die das Fenster allein fuellt."""
    _nachricht(conn, chat_id, ab_message_id, _lang(journal.SCHWELLE_VERDRAENGUNG + 200))
    _nachricht(conn, chat_id, ab_message_id + 1, _lang(kontext.BUDGETS["fenster"] + 500))


def test_leere_liste_ist_der_normalfall_kein_fehler(conn, einst):
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(antwort={"eintraege": []})

    ergebnis = journal.extrahiere(klm, conn, einst, 1)

    assert ergebnis == []
    assert klm.aufrufe == 1


def test_ohne_verdraengung_wird_das_modell_nicht_gerufen(conn, einst):
    _nachricht(conn, 1, 1, "kurzer Satz")
    klm = LLMAttrappe(antwort={"eintraege": []})

    ergebnis = journal.extrahiere(klm, conn, einst, 1)

    assert ergebnis == []
    assert klm.aufrufe == 0


def test_vorschlag_wird_als_vorgeschlagen_geschrieben(conn, einst):
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(antwort={"eintraege": [
        {"kategorie": "vorgeschlagen", "text": "Sechs feste Fragen fuer alle Interviews."},
    ]})

    ergebnis = journal.extrahiere(klm, conn, einst, 1)

    assert ergebnis == [
        {"kategorie": "vorgeschlagen", "text": "Sechs feste Fragen fuer alle Interviews."}
    ]
    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["art"] == "vorgeschlagen"
    assert eintraege[0]["text"] == "Sechs feste Fragen fuer alle Interviews."
    assert eintraege[0]["quelle"] == "extraktor"


def test_andere_kategorien_werden_verworfen_arbeitsteilung(conn, einst):
    """Der Absichtserkenner schreibt weiterhin verworfen/entschieden. Kaeme
    trotzdem eine dieser Kategorien aus dem Modell zurueck (Attrappe oder
    ein kuenftiger Anbieterwechsel), darf sie hier NICHT landen."""
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(antwort={"eintraege": [
        {"kategorie": "verworfen", "text": "Zeitreise-Idee - zu teuer"},
        {"kategorie": "entschieden", "text": "Kernthema ist Ankommen"},
        {"kategorie": "vorgeschlagen", "text": "Sechs feste Fragen fuer alle Interviews."},
    ]})

    ergebnis = journal.extrahiere(klm, conn, einst, 1)

    assert ergebnis == [
        {"kategorie": "vorgeschlagen", "text": "Sechs feste Fragen fuer alle Interviews."}
    ]
    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["art"] == "vorgeschlagen"


def test_mehr_als_fuenf_eintraege_werden_auf_fuenf_gekappt(conn, einst):
    _fuelle_verdraengung(conn, 1)
    sechs = [{"kategorie": "vorgeschlagen", "text": f"Sache Nummer {i} als Vorschlag"} for i in range(6)]
    klm = LLMAttrappe(antwort={"eintraege": sechs})

    ergebnis = journal.extrahiere(klm, conn, einst, 1)

    assert len(ergebnis) == journal.MAX_EINTRAEGE == 5
    assert len(repo.journal(conn, 1)) == 5


def test_wasserzeichen_rueckt_bei_erfolg_vor(conn, einst):
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(antwort={"eintraege": []})

    journal.extrahiere(klm, conn, einst, 1)

    # Das Wasserzeichen rueckt genau bis zum Ende des verdraengten
    # Abschnitts vor (Nachricht 1), NICHT bis zur Fensternachricht (2) --
    # die ist noch nicht aus dem Fenster gefallen.
    assert repo.hole_gruppe(conn, 1)["letzte_journalisierte_message_id"] == 1


def test_wasserzeichen_bleibt_bei_fehlschlag_stehen_und_schreibt_vorfall(conn, einst):
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(fehler=RuntimeError("Sprachmodell nicht erreichbar"))

    ergebnis = journal.extrahiere(klm, conn, einst, 1)

    assert ergebnis == []
    assert repo.hole_gruppe(conn, 1)["letzte_journalisierte_message_id"] == 0
    assert repo.journal(conn, 1) == []
    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None


def test_extraktor_bekommt_nur_verdraengten_abschnitt_nicht_das_ganze_gespraech(conn, einst):
    _nachricht(conn, 1, 2, _lang(journal.SCHWELLE_VERDRAENGUNG + 200, buchstabe="d"))
    _nachricht(conn, 1, 3, _lang(kontext.BUDGETS["fenster"] + 500, buchstabe="f"))
    klm = LLMAttrappe(antwort={"eintraege": []})

    journal.extrahiere(klm, conn, einst, 1)

    nutzer = klm.gesehen["nutzer"]
    assert "d" * 30 in nutzer  # der verdraengte Abschnitt (Nachricht 2) steht drin
    assert "f" * 30 not in nutzer  # die Fensternachricht (3) ist noch nicht verdraengt


def test_bisherige_journaleintraege_werden_beigelegt_aber_nicht_das_ganze_journal(conn, einst):
    for i in range(journal.LETZTE_JOURNALEINTRAEGE + 3):
        repo.schreibe_journal(conn, 1, "vorgeschlagen", f"uralter Eintrag Nummer {i}", quelle="extraktor")
    repo.schreibe_journal(conn, 1, "vorgeschlagen", "ganz frischer Eintrag ueber Ankommen", quelle="extraktor")
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(antwort={"eintraege": []})

    journal.extrahiere(klm, conn, einst, 1)

    nutzer = klm.gesehen["nutzer"]
    assert "uralter Eintrag Nummer 0" not in nutzer
    assert "ganz frischer Eintrag ueber Ankommen" in nutzer


def test_es_wird_nichts_in_der_gruppe_gemeldet(conn, einst):
    """Journaleintraege werden nie in der Gruppe gemeldet: journal.laufe
    nimmt gar kein Telegram-Objekt entgegen und darf keine Bot-Nachricht in
    der Datenbank erzeugen."""
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(antwort={"eintraege": [
        {"kategorie": "vorgeschlagen", "text": "Sechs feste Fragen fuer alle Interviews."},
    ]})

    journal.laufe(klm, conn, einst, 1)

    bot_nachrichten = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = 1 AND ist_bot = 1"
    ).fetchall()
    assert bot_nachrichten == []
    assert len(repo.journal(conn, 1)) == 1


def test_laufe_faengt_fehlschlag_ab_und_schreibt_vorfall(conn, einst):
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(fehler=RuntimeError("Sprachmodell nicht erreichbar"))

    journal.laufe(klm, conn, einst, 1)  # darf nicht krachen

    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None


def test_ruft_erkennermodell_mit_temperature_0_2_auf(conn, einst):
    _fuelle_verdraengung(conn, 1)
    klm = LLMAttrappe(antwort={"eintraege": []})

    journal.extrahiere(klm, conn, einst, 1)

    assert klm.gesehen["modell"] == einst.erkenner_modell
    assert klm.gesehen["modell"] != einst.llm_modell
    assert klm.gesehen["temperature"] == journal.TEMPERATURE == 0.2
    assert klm.gesehen["art"] == "journal"


def test_schema_hat_additional_properties_false_und_vollstaendiges_required():
    def pruefe_objekt(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, node
                eigenschaften = set(node.get("properties", {}).keys())
                assert set(node.get("required", [])) == eigenschaften, node
            for wert in node.values():
                pruefe_objekt(wert)
        elif isinstance(node, list):
            for element in node:
                pruefe_objekt(element)

    pruefe_objekt(journal.SCHEMA)


def test_schema_kennt_kein_begruendungsfeld():
    schema_text = str(journal.SCHEMA)
    assert "begruendung" not in schema_text
    assert "reasoning" not in schema_text


def test_schema_kennt_kein_maxitems():
    assert "maxItems" not in str(journal.SCHEMA)


def test_prompt_enthaelt_fuenf_beispiele_davon_zwei_leer():
    anzahl_beispiele = journal.prompt().count("<beispiel>")
    anzahl_leer = journal.prompt().count('"eintraege": []')
    assert anzahl_beispiele == 5
    assert anzahl_leer == 2


def test_prompt_erzeugt_nur_die_kategorie_vorgeschlagen():
    """Der Prompt darf keine Beispielausgabe mit einer anderen Kategorie
    zeigen -- sonst lernt das Modell etwas, das das Schema gleich wieder
    verwirft (Arbeitsteilung: verworfen/entschieden bleiben beim
    Absichtserkenner)."""
    assert '"kategorie": "verworfen"' not in journal.prompt()
    assert '"kategorie": "entschieden"' not in journal.prompt()


# ---------------------------------------------------------------------------
# db-Migration: neue Spalte
# ---------------------------------------------------------------------------


def test_gruppe_hat_journal_wasserzeichen_spalte(conn):
    zeile = repo.hole_gruppe(conn, 1)
    assert "letzte_journalisierte_message_id" in zeile.keys()
    assert zeile["letzte_journalisierte_message_id"] == 0
