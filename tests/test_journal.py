"""Tests fuer den Journal-Extraktor (gedaechtnis-extraktion-agenten.md § 6,
§ 8; SPEC-kontext-architektur.md § 4.3).

Anders als der Absichtserkenner (der jeden Zug ueber die letzten paar
Nachrichten laeuft) laeuft der Journal-Extraktor nur bei VERDRAENGUNG: wenn
ein Abschnitt aus dem kurzen Fenster (kontext.fenster_grenzen()) faellt und
dieser Abschnitt SCHWELLE_VERDRAENGUNG geschaetzte Token uebersteigt. Er
sieht dann genau diesen Abschnitt, nicht das ganze Gespraech, und schreibt
ausschliesslich die Kategorie "vorgeschlagen" ins Journal -- "verworfen" und
"entschieden" bleiben Sache des Absichtserkenners (Arbeitsteilung gegen
Doppeleintraege).

Wie in test_erkenner.py: das Sprachmodell wird durch eine Attrappe mit einer
.schema()-Methode ersetzt. Kein Netzzugriff.
"""

import pytest

from interview_theater import journal, kontext, repo


class LLMAttrappe:
    """Ersetzt interview_theater.llm.LLM in Tests: liefert eine vorbereitete Antwort
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
    fenster = [_msg(2, _lang(kontext.FENSTER_ZEICHEN))]  # fuellt das Fenster allein
    nachrichten = verdraengt + fenster

    assert journal.berechne_verdraengten_abschnitt(nachrichten) == []


def test_verdraengter_abschnitt_ueber_schwelle_loest_aus_und_liefert_nur_ihn():
    verdraengt = [_msg(1, _lang(journal.SCHWELLE_VERDRAENGUNG + 200))]
    fenster = [_msg(2, _lang(kontext.FENSTER_ZEICHEN))]
    nachrichten = verdraengt + fenster

    ergebnis = journal.berechne_verdraengten_abschnitt(nachrichten)

    assert [n["message_id"] for n in ergebnis] == [1]


def test_verdraengter_abschnitt_mehrere_nachrichten_zusammen_ueber_schwelle():
    verdraengt = [
        _msg(1, _lang(journal.SCHWELLE_VERDRAENGUNG // 2 + 100)),
        _msg(2, _lang(journal.SCHWELLE_VERDRAENGUNG // 2 + 100)),
    ]
    fenster = [_msg(3, _lang(kontext.FENSTER_ZEICHEN))]
    nachrichten = verdraengt + fenster

    ergebnis = journal.berechne_verdraengten_abschnitt(nachrichten)

    assert [n["message_id"] for n in ergebnis] == [1, 2]


# ---------------------------------------------------------------------------
# Die Kopplung an kontext.fenster_grenzen() (Audit 06.09.2026, Befund C.3)
# ---------------------------------------------------------------------------


def test_verdraengung_rechnet_gegen_dasselbe_fenster_wie_der_prompt():
    """**Der Regressionstest, dessen Fehlen Befund C.3 verursacht hat.**

    ``journal.berechne_verdraengten_abschnitt`` rechnete gegen
    ``kontext.BUDGETS["fenster"] = 8000`` Token, waehrend
    ``kontext._baue_fenster_eintraege`` das Fenster nach Nachrichten und
    Minuten bemass. Gemessen hielt der Extraktor damit **31 Nachrichten fuer
    "noch im Fenster"**, waehrend der Prompt nur 20 sah -- die Nachrichten
    21-31 wurden nie journalisiert und standen danach nirgends mehr.

    Der Test vergleicht die beiden Mengen direkt: was NICHT verdraengt ist,
    muss genau das sein, was ``kontext.waehle_fenster`` ins Fenster nimmt.
    Laufen sie je wieder auseinander, faellt das hier auf und nicht erst in
    einer Messung nach dem Workshop."""
    nachrichten = [
        _msg(i, f"Beitrag {i}: " + "text " * 60) for i in range(60)
    ]

    im_fenster = kontext.waehle_fenster(nachrichten)
    verdraengt = journal.berechne_verdraengten_abschnitt(nachrichten)

    assert verdraengt, "diese Menge muss ueberhaupt etwas verdraengen"
    fenster_ids = [n["message_id"] for n in im_fenster]
    verdraengt_ids = [n["message_id"] for n in verdraengt]
    alle = [n["message_id"] for n in nachrichten]

    assert verdraengt_ids + fenster_ids == alle, (
        "Fenster und verdraengter Abschnitt muessen die Liste luecken- und "
        f"ueberschneidungsfrei teilen: {verdraengt_ids} | {fenster_ids}"
    )
    assert not set(fenster_ids) & set(verdraengt_ids), (
        "keine Nachricht darf zugleich im Fenster und verdraengt sein"
    )


def test_kopplung_zieht_eine_geaenderte_fenstergrenze_mit(monkeypatch):
    """Eine Zahl aendern und die andere vergessen -- genau so ist die
    Kopplung am 06.09. um 00:39 gebrochen. Jetzt gibt es nur noch eine."""
    nachrichten = [_msg(i, f"Beitrag {i}: " + "text " * 60) for i in range(60)]

    monkeypatch.setattr(kontext, "FENSTER_ZEICHEN", 3_000)
    eng = journal.berechne_verdraengten_abschnitt(nachrichten)
    monkeypatch.setattr(kontext, "FENSTER_ZEICHEN", 30_000)
    weit = journal.berechne_verdraengten_abschnitt(nachrichten)

    assert len(eng) > len(weit), (
        "ein kleineres Fenster muss mehr verdraengen -- sonst liest der "
        "Extraktor eine andere Grenze als der Promptbau"
    )


# ---------------------------------------------------------------------------
# Volumen von Tag 1 (Audit 06.09.2026, C.3: der Extraktor lief 0x)
# ---------------------------------------------------------------------------


#: Das gemessene Volumen der drei echten Betriebsgruppen an Tag 1
#: (Audit C.3): 48-66 Nachrichten, 4.671-6.342 Token Verlauf. Der Extraktor
#: sprang bei allen dreien **kein einziges Mal** an -- ihr ganzer Tagesverlauf
#: lag unter dem damaligen Fensterbudget von 8.000 Token.
TAG1_NACHRICHTEN = 60
TAG1_TOKEN = 6_000


def _tag1_verlauf() -> list:
    """Eine Fixture mit dem Volumen von Tag 1: 60 Nachrichten, zusammen rund
    6.000 geschaetzte Token, in realistisch ungleichen Laengen (im Gruppenchat
    sind vier Redebeitraege nicht vier gleich grosse Bloecke)."""
    laengen = [20, 60, 130, 40, 250, 75]  # Token je Nachricht, zyklisch
    nachrichten = []
    for i in range(TAG1_NACHRICHTEN):
        ziel = laengen[i % len(laengen)]
        nachrichten.append(_msg(i, _lang(ziel, buchstabe=chr(97 + i % 26))))
    return nachrichten


def test_bei_tag1_volumen_springt_der_extraktor_mindestens_einmal_an():
    """**Auftrag 2, Test (c).** Gemessen an den drei echten Betriebsgruppen
    von Tag 1: Wasserzeichen bei allen auf 0, kein einziger
    ``extraktor``-Eintrag im Betriebsjournal, obwohl die Gruppen den ganzen
    Tag geredet haben. Was sie beschlossen haben, stand im Chat, bis es aus
    dem Fenster fiel -- und danach nirgends.

    Mit dem tokenbemessenen Fenster (12.000 Zeichen) und
    ``SCHWELLE_VERDRAENGUNG = 600`` muss bei diesem Volumen etwas
    herausfallen."""
    verlauf = _tag1_verlauf()
    gesamt = kontext.schaetze("\n".join(kontext.sprecherzeile(n) for n in verlauf))
    assert TAG1_TOKEN * 0.8 <= gesamt <= TAG1_TOKEN * 1.4, (
        f"die Fixture soll das Tag-1-Volumen treffen, ist aber {gesamt} Token"
    )

    verdraengt = journal.berechne_verdraengten_abschnitt(verlauf)

    assert verdraengt, (
        "bei einem ganzen Workshoptag muss der Extraktor mindestens einmal "
        "anspringen -- an Tag 1 tat er es in keiner einzigen Gruppe"
    )


def test_bei_tag1_volumen_springt_der_extraktor_nicht_bei_jeder_nachricht():
    """**Birk, 06.09.2026, vor dem Merge**: die obere Schranke zur Gegenprobe.

    Die Senkung der Schwelle von 2.000 auf 600 Token soll den Extraktor
    haeufiger, aber nicht dauernd laufen lassen -- jeder Lauf ist ein eigener
    Modellaufruf. Zugesichert wird: **hoechstens ein Lauf je
    ``SCHWELLE_VERDRAENGUNG`` verdraengter Token.**

    Simuliert wird der Betrieb, wie er wirklich laeuft: nach jedem Zug
    ``repo.unjournalisierte`` -> Verdraengung rechnen -> bei Treffer
    Wasserzeichen vorruecken (hier: den Abschnitt aus der Liste nehmen)."""
    verlauf = _tag1_verlauf()
    laeufe = 0
    journalisiert_bis = 0
    verdraengte_token = 0

    for ende in range(1, len(verlauf) + 1):
        offen = verlauf[journalisiert_bis:ende]
        verdraengt = journal.berechne_verdraengten_abschnitt(offen)
        if verdraengt:
            laeufe += 1
            verdraengte_token += kontext.schaetze(
                "\n".join(kontext.sprecherzeile(n) for n in verdraengt)
            )
            journalisiert_bis += len(verdraengt)

    assert laeufe >= 1, "unter Betriebsbedingungen muss er ueberhaupt laufen"
    schranke = verdraengte_token / journal.SCHWELLE_VERDRAENGUNG + 1
    assert laeufe <= schranke, (
        f"{laeufe} Laeufe fuer {verdraengte_token} verdraengte Token -- "
        f"hoechstens {schranke:.1f} erlaubt (ein Lauf je "
        f"{journal.SCHWELLE_VERDRAENGUNG} Token)"
    )
    assert laeufe < len(verlauf) / 4, (
        f"{laeufe} Laeufe bei {len(verlauf)} Nachrichten -- der Extraktor "
        "darf nicht bei jeder Nachricht anspringen"
    )


# ---------------------------------------------------------------------------
# extrahiere() -- der ganze Ablauf: erkennen, schreiben, Wasserzeichen
# ---------------------------------------------------------------------------


def _fuelle_verdraengung(conn, chat_id, ab_message_id=1):
    """Legt genug Nachrichten an, dass tatsaechlich etwas verdraengt wird:
    eine grosse alte Nachricht (ueber der Schwelle) gefolgt von einer
    grossen neuen Nachricht, die das Fenster allein fuellt."""
    _nachricht(conn, chat_id, ab_message_id, _lang(journal.SCHWELLE_VERDRAENGUNG + 200))
    _nachricht(conn, chat_id, ab_message_id + 1, _lang(kontext.FENSTER_ZEICHEN))


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
    _nachricht(conn, 1, 3, _lang(kontext.FENSTER_ZEICHEN, buchstabe="f"))
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
