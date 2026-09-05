"""Tests fuer den Absichtserkenner (SPEC-kontext-architektur.md § 4.3,
teil-b.md Aufgabe 2).

Wie in test_verdichter.py: das Sprachmodell wird durch eine Attrappe mit
einer .schema()-Methode ersetzt, die eine vorbereitete Antwort liefert (oder
einen vorbereiteten Fehler wirft) und ihre Aufrufe samt Parametern
aufzeichnet. Kein Netzzugriff.
"""

import pytest

from interview_theater import erkenner, knoepfe, phasen, repo


class LLMAttrappe:
    """Ersetzt interview_theater.llm.LLM in Tests: liefert eine vorbereitete Antwort
    (oder wirft einen vorbereiteten Fehler), zaehlt die Aufrufe und
    zeichnet die zuletzt gesehenen Parameter auf -- insbesondere modell und
    temperature, damit sich pruefen laesst, dass der Erkenner NICHT das
    Gespraechsmodell verwendet."""

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


def test_ohne_neue_nachrichten_wird_das_modell_nicht_gerufen(conn, einst):
    klm = LLMAttrappe(antwort={"aenderungen": []})
    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert klm.aufrufe == 0


def test_leere_aenderungsliste_ist_kein_fehler(conn, einst):
    _nachricht(conn, 1, 1, "guten Morgen zusammen")
    klm = LLMAttrappe(antwort={"aenderungen": []})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 1


def test_interview_starten_erkannt_und_wasserzeichen_vorgerueckt(conn, einst):
    _nachricht(conn, 1, 5, "wir machen jetzt ein Interview")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_starten", "wert": ""}]})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == [{"art": "interview_starten", "wert": ""}]
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 5


def test_mehr_als_fuenf_aenderungen_werden_auf_fuenf_gekappt(conn, einst):
    _nachricht(conn, 1, 1, "diverses")
    sechs = [{"art": "verworfen", "wert": f"Sache {i}"} for i in range(6)]
    klm = LLMAttrappe(antwort={"aenderungen": sechs})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert len(ergebnis) == erkenner.MAX_AENDERUNGEN == 5


def test_unbekannte_art_wird_verworfen_statt_zu_krachen(conn, einst):
    _nachricht(conn, 1, 1, "diverses")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "irgendwas_erfundenes", "wert": "?"},
        {"art": "kernthema_setzen", "wert": "Ankommen"},
    ]})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == [{"art": "kernthema_setzen", "wert": "Ankommen"}]


def test_fehlschlag_laesst_wasserzeichen_stehen_und_schreibt_vorfall(conn, einst):
    _nachricht(conn, 1, 3, "diverses")
    klm = LLMAttrappe(fehler=RuntimeError("Sprachmodell nicht erreichbar"))

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 0
    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None
    assert zeile["art"] == "extraktor_fehler"


def test_deckel_rueckt_wasserzeichen_vor_und_schreibt_vorfall(conn, einst):
    # kontext.schaetze() ist Zeichen // 3. Die Laenge wird aus FENSTER_DECKEL
    # selbst abgeleitet, damit der Test beim Nachjustieren des Deckels nicht
    # still seine Aussage verliert.
    _nachricht(conn, 1, 7, "x" * (erkenner.FENSTER_DECKEL * 3 + 3_000))
    klm = LLMAttrappe(antwort={"aenderungen": []})

    ergebnis = erkenner.erkenne(klm, conn, einst, 1)

    assert ergebnis == []
    assert klm.aufrufe == 0, "das Modell wird beim Deckel gar nicht erst gerufen"
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 7
    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None
    assert zeile["art"] == "fenster_verworfen"


def test_ruft_erkennermodell_mit_temperature_0_2_auf_nicht_das_gespraechsmodell(conn, einst):
    _nachricht(conn, 1, 1, "diverses")
    klm = LLMAttrappe(antwort={"aenderungen": []})

    erkenner.erkenne(klm, conn, einst, 1)

    assert klm.gesehen["modell"] == einst.erkenner_modell
    assert klm.gesehen["modell"] != einst.llm_modell
    assert klm.gesehen["temperature"] == 0.2
    assert klm.gesehen["art"] == "erkenner"


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

    pruefe_objekt(erkenner.SCHEMA)


def test_schema_kennt_kein_maxitems():
    """global-constraints.md § Schema: die Fuenf-Obergrenze steht im
    Prompttext und wird im Code durchgesetzt, nicht im Schema (von strikten
    Modi oft nicht unterstuetzt)."""
    assert "maxItems" not in str(erkenner.SCHEMA)


def test_arten_enthaelt_alle_zwanzig_werte():
    erwartet = {
        # Eine Szene wird seit dem 05.09.2026 zuerst geplant und erst danach
        # geschrieben -- zwei Arten fuer zwei verschiedene Dinge.
        "szene_planen",
        # Aus welchem Interview eine Figur spricht: die Zuordnung, an der das
        # Sprachprofil haengt (interview_theater/sprachprofil.py).
        "figur_quelle_setzen",
        "interview_starten", "interview_beenden", "interview_benennen",
        "begriffe_setzen", "fragen_setzen", "kernthema_setzen",
        # Phase 5 heisst seit dem 05.09.2026 "Rahmen": zwei neue
        # Arten, und der Hauptkonflikt bleibt als optionales Feld daneben.
        "format_setzen", "rahmen_setzen",
        "hauptkonflikt_setzen", "figur_setzen", "wortlaut_an", "wortlaut_aus",
        "verworfen", "entschieden", "szene_schreiben", "phase_setzen",
        "entfernen", "an_den_bot",
        # N5 (05.09.): Korrekturen am Transkript wirken -- statt behauptet
        # zu werden.
        "transkript_korrigieren",
        # 05.09. frueh: Antwort auf das Angebot, Szenentexte in den USA
        # schreiben zu lassen.
        "szene_usa",
    }
    assert set(erkenner.ARTEN) == erwartet


def test_an_den_bot_gilt_nur_aus_einer_aufnahme(conn, einst):
    """N4: die einzige art, die ausserhalb einer Aufnahme keinen Sinn ergibt
    -- sie sagt etwas ueber EINE Sprachnachricht, nicht ueber den
    Gespraechsverlauf. Sie darf deshalb auch nichts schreiben; das Abzweigen
    macht aufnahme.py, wo die Aufnahme bekannt ist."""
    assert "an_den_bot" in erkenner.ARTEN_IN_AUFNAHME

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "an_den_bot", "wert": ""}])

    assert wirkliche == []
    assert erkenner.baue_meldung(wirkliche) is None


def test_prompt_enthaelt_siebzehn_beispiele_davon_vier_leer():
    """Grober Regressionsschutz gegen einen versehentlich verkuerzten Prompt.

    Die Rechercheempfehlung lautete auf 5 Few-Shot-Beispiele, davon 2 leer.
    Sechs sind dazugekommen, jedes fuer eine art, deren Abgrenzung sich in
    Regeln schlecht fassen laesst: ``szene_schreiben`` (die einzige art, die
    eine teure Handlung ausloest statt ein Feld zu setzen), ``phase_setzen``
    (ueber eine Phase zu reden ist kein Setzen) und ``entfernen`` -- dessen
    Beispiel zwei Dinge auf einmal zeigt: die Figur fliegt raus, der
    Loeschwunsch fuer ein INTERVIEW im selben Abschnitt aber nicht, weil
    Material nie entfernbar ist (NACHTRAG N3). Am 04.09.2026 abends kamen
    ``fragen_setzen`` samt seinem Negativfall ("welche Fragen koennten wir
    stellen?") und ein zweites phase_setzen-Beispiel fuer die Abgrenzung
    zwischen Figuren und Hauptkonflikt dazu.

    Das zwoelfte kam am 05.09.2026 mit N7: **Zustimmung zu einem konkreten
    Vorschlag ist eine Festlegung** -- drei vorgeschlagene Figuren, ein "find
    ich stark, nehmen wir", drei Eintraege. Es steht an der Stelle, an der
    frueher der Gegenfall stand, und der bleibt gleich daneben: Lob ohne
    Vorschlag davor traegt weiterhin nichts ein.

    Nummer dreizehn und vierzehn kamen mit Phase 5 ("Rahmen",
    05.09.2026): eines, das ``format_setzen`` und ``rahmen_setzen`` in einem
    Abschnitt zeigt (die Gruppe entscheidet beides oft in einem Zug), und sein
    Negativfall -- "vielleicht wird das ja ein Musical" setzt kein Format.
    Damit sind es vier leere Beispiele.

    Das fuenfzehnte zeigt ``szene_planen`` gegen ``szene_schreiben``: Ort,
    Besetzung und Anlass einer Szene sind eine Planung, kein Schreibauftrag.
    Ohne dieses Beispiel gingen genau die Angaben verloren, wegen denen der
    Probelauf eine Kueche statt eines Polizeikessels lieferte.

    Das sechzehnte zeigt ``figur_quelle_setzen``: der Bot schlaegt eine
    Interview-Zuordnung mit einem Zitat vor, die Gruppe nickt bei der einen
    Figur und widerspricht bei der anderen. Beide Richtungen in einem
    Abschnitt, weil beide dieselbe art sind.

    Das siebzehnte ist die Live-Stelle "Ja, mach den Text fuer Szene 1. Go!"
    (Probelauf, Nachricht 97): nach einer Planung genuegt ein kurzes Wort --
    aber der wert ist der Auftrag aus dem Verlauf, nicht "Go".

    Das achtzehnte kam am 05.09.2026 aus dem Testlauf vor dem Workshop
    (Birk: "die Fragen erscheinen nicht auf der Website"). Der Fall: die
    Gruppe gibt nur den AUFTRAG ("mach die Fragen konkreter"), der BOT
    formuliert die Liste aus, und danach nickt niemand mehr. Der Erkenner
    wartete auf eine Zustimmung, die im Ablauf nie vorgesehen ist, und
    ``arbeitsstand.fragen`` blieb leer (3/3 leer reproduziert). Es traegt die
    Grundregel: ein unfertiger Stand ist besser als kein Stand.

    Neunzehn bis einundzwanzig kamen am 05.09.2026 aus dem Live-Lauf um
    13:42: "ich will noch eine Aufnahme machen" loeste **kein**
    ``interview_starten`` aus, und damit kam auch der Aufnahme-Knopf nicht
    (Birk: "der Knopf soll direkt kommen, ohne Slash-Befehl"). Zwei
    Positivbeispiele (der Live-Satz selbst, und "koennen wir nochmal jemanden
    aufnehmen" als Frage in die Runde) und -- weil eine breitere Beschreibung
    genau hier Falschtreffer einlaedt -- ein Negativbeispiel dazu: ueber
    gestrige Aufnahmen reden faengt keine an. Damit sind es fuenf leere
    Beispiele."""
    anzahl_beispiele = erkenner.prompt().count("<beispiel>")
    anzahl_leer = erkenner.prompt().count('"aenderungen": []')
    assert anzahl_beispiele == 21
    assert anzahl_leer == 5


# ---------------------------------------------------------------------------
# Aufgabe 3: Schreibpfad (erkenner.wende_an)
# ---------------------------------------------------------------------------


def test_kernthema_ueberschreiben_aendert_feld_und_gilt_als_aenderung(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    )

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"
    assert wirkliche == [{"art": "kernthema_setzen", "wert": "Ankommen"}]


def test_kernthema_ueberschreiben_ersetzt_alten_wert(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    erkenner.wende_an(conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Abschied"}])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Abschied"


def test_derselbe_wert_nochmal_gilt_nicht_als_aenderung(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "kernthema_setzen", "wert": "Ankommen"}]
    )

    assert wirkliche == []


def test_hauptkonflikt_und_begriffe_werden_ueberschrieben(conn, einst):
    wirkliche = erkenner.wende_an(
        conn,
        einst,
        1,
        [
            {"art": "hauptkonflikt_setzen", "wert": "Bleiben oder Gehen"},
            {"art": "begriffe_setzen", "wert": "Migration, Ankommen"},
        ],
    )

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["hauptkonflikt"] == "Bleiben oder Gehen"
    assert stand["begriffe"] == "Migration, Ankommen"
    assert len(wirkliche) == 2


def test_fragen_werden_gesetzt_und_gemeldet(conn, einst):
    """Die Frageliste aus Phase 2 (04.09.2026 abends): eigenes Feld, eigener
    Erkennungsweg, dieselbe Meldung wie bei den Begriffen."""
    fragen = "Was war in deinem Koffer? Wer hat dich zum Bahnhof gebracht?"

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "fragen_setzen", "wert": fragen}]
    )

    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == fragen
    assert wirkliche == [{"art": "fragen_setzen", "wert": fragen}]
    assert f"Fragen: {fragen}" in erkenner.baue_meldung(wirkliche)


def test_dieselben_fragen_noch_einmal_sind_keine_aenderung(conn, einst):
    """Wie ueberall sonst: derselbe Wert meldet nicht erneut -- sonst
    bestaetigte der Bot die Frageliste bei jedem Zug aufs Neue."""
    erkenner.wende_an(conn, einst, 1, [{"art": "fragen_setzen", "wert": "Was war im Koffer?"}])

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "fragen_setzen", "wert": "Was war im Koffer?"}]
    )

    assert wirkliche == []


def test_fragen_stehen_im_erkenner_kontext(conn, einst):
    """Der Erkenner sieht die schon gesetzten Fragen -- ohne sie koennte er
    eine Rueckfrage danach nicht von einer neuen Liste unterscheiden."""
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    _nachricht(conn, 1, 1, "was hatten wir nochmal als Fragen")

    nutzer = erkenner._baue_nutzertext(conn, 1, repo.unextrahierte(conn, 1))

    assert "Fragen: Was war in deinem Koffer?" in nutzer


def test_figur_mit_bekanntem_namen_wird_ueberschrieben_nicht_verdoppelt(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Maria: Naeherin"}])

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_setzen", "wert": " maria : kam 1998"}]
    )

    figuren = repo.figuren(conn, 1)
    assert len(figuren) == 1
    assert figuren[0]["beschreibung"] == "kam 1998"
    assert wirkliche == [{"art": "figur_setzen", "wert": "maria"}]


def test_figur_ohne_doppelpunkt_bekommt_leere_beschreibung(conn, einst):
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Peter"}])

    figuren = repo.figuren(conn, 1)
    assert len(figuren) == 1
    assert figuren[0]["name"] == "Peter"
    assert figuren[0]["beschreibung"] == ""
    assert wirkliche == [{"art": "figur_setzen", "wert": "Peter"}]


def test_figur_bekannter_name_ohne_doppelpunkt_behaelt_alte_beschreibung(conn, einst):
    """Korrektur (2026-09-04): nennt das Modell einen bekannten Namen
    beilaeufig ohne Doppelpunkt, darf die vorhandene Beschreibung nicht
    verschwinden -- und das darf auch nicht als Aenderung gemeldet werden."""
    erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Peter: Nachbar, 45"}])

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Peter"}])

    figuren = repo.figuren(conn, 1)
    assert len(figuren) == 1
    assert figuren[0]["beschreibung"] == "Nachbar, 45"
    assert wirkliche == []


def test_figur_gleicher_name_und_gleiche_beschreibung_gilt_nicht_als_aenderung(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "figur_setzen", "wert": "Maria: Naeherin"}])

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_setzen", "wert": "Maria: Naeherin"}]
    )

    assert wirkliche == []


def test_verworfen_landet_im_journal_nicht_im_arbeitsstand(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "verworfen", "wert": "Zeitreise-Idee — zu teuer"}]
    )

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["art"] == "verworfen"
    assert eintraege[0]["text"] == "Zeitreise-Idee — zu teuer"
    assert eintraege[0]["quelle"] == "erkenner"
    assert repo.hole_arbeitsstand(conn, 1) is None
    assert wirkliche == [{"art": "verworfen", "wert": "Zeitreise-Idee — zu teuer"}]


def test_entschieden_landet_im_journal(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "entschieden", "wert": "6 Interviewfragen"}])

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["art"] == "entschieden"
    assert eintraege[0]["quelle"] == "erkenner"


def test_leerer_wert_wird_uebersprungen(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "kernthema_setzen", "wert": "   "}]
    )

    assert wirkliche == []
    assert repo.hole_arbeitsstand(conn, 1) is None


def test_wortlaut_an_setzt_modus_auf_namen(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "wortlaut_an", "wert": "Maria"}]
    )

    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "Maria"
    assert wirkliche == [{"art": "wortlaut_an", "wert": "Maria"}]


def test_wortlaut_an_leerer_wert_setzt_stern(conn, einst):
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "wortlaut_an", "wert": ""}])

    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "*"
    assert wirkliche == [{"art": "wortlaut_an", "wert": "*"}]


def test_wortlaut_aus_setzt_modus_auf_none(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "wortlaut_an", "wert": "Maria"}])

    erkenner.wende_an(conn, einst, 1, [{"art": "wortlaut_aus", "wert": ""}])

    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_interview_benennen_benennt_letztes_interview(conn, einst):
    """"das war Marias Interview" meint das juengste INTERVIEW (§ 10.6) --
    weder einen Zuruf, der zufaellig danach kam, noch eine einzelne der
    Sprachnachrichten, aus denen es besteht."""
    repo.lege_aufnahme_an(conn, 1, 1, "lang", "sprache")
    zweite_id = repo.lege_aufnahme_an(conn, 1, 2, "lang", "sprache")
    repo.lege_aufnahme_an(conn, 1, 3, "teil", "sprache", teil_von=zweite_id)
    repo.lege_aufnahme_an(conn, 1, 4, "kurz", "sprache")

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "interview_benennen", "wert": "Maria"}]
    )

    umbenannt = repo.hole_aufnahme(conn, zweite_id)
    assert umbenannt["name"] == "Maria"
    assert wirkliche == [{"art": "interview_benennen", "wert": "Maria"}]


def test_interview_starten_setzt_interviewmodus_seit(conn, einst):
    """Seit 05.09.2026 (Birk nach Gruppe 3, 16:36) schaltet der Erkenner den
    Modus **nicht** mehr ein: eine Ankuendigung ist eine Ankuendigung. Er
    meldet die Absicht nur -- ``laufe()`` legt daraufhin die
    Ablauf-Erklaerung mit dem Knopf "Interview starten" hin, und erst der
    Druck schaltet an."""
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "interview_starten", "wert": ""}])

    assert wirkliche == [{"art": "interview_starten", "wert": ""}]
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None
    assert repo.laufendes_interview(conn, 1) is None


def test_interview_beenden_leert_interviewmodus_seit(conn, einst):
    repo.setze_interviewmodus(conn, 1, repo._jetzt())

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "interview_beenden", "wert": ""}])

    # aufnahme_id reicht das beendete Interview an laufe() weiter (§ 10.6) --
    # hier None, weil in diesem Test gar keines lief.
    assert wirkliche == [{"art": "interview_beenden", "wert": "", "aufnahme_id": None}]
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None


def test_interview_starten_wenn_schon_an_gilt_nicht_als_aenderung(conn, einst):
    repo.setze_interviewmodus(conn, 1, repo._jetzt())

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "interview_starten", "wert": ""}])

    assert wirkliche == []


def test_interview_beenden_wenn_schon_aus_gilt_nicht_als_aenderung(conn, einst):
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "interview_beenden", "wert": ""}])

    assert wirkliche == []


def test_eine_fehlerhafte_aenderung_reisst_die_anderen_nicht_mit(conn, einst):
    wirkliche = erkenner.wende_an(
        conn,
        einst,
        1,
        [
            {"art": "kernthema_setzen", "wert": "Ankommen"},
            {"art": "figur_setzen", "wert": 12345},  # kein String -> .strip() kracht
            {"art": "hauptkonflikt_setzen", "wert": "Bleiben oder Gehen"},
        ],
    )

    assert {"art": "kernthema_setzen", "wert": "Ankommen"} in wirkliche
    assert {"art": "hauptkonflikt_setzen", "wert": "Bleiben oder Gehen"} in wirkliche
    assert len(wirkliche) == 2
    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None


# ---------------------------------------------------------------------------
# Aufgabe 4: Meldelogik (erkenner.baue_meldung, erkenner.laufe)
# ---------------------------------------------------------------------------


def test_baue_meldung_ohne_aenderungen_ist_none():
    assert erkenner.baue_meldung([]) is None


def test_baue_meldung_nur_journaleintraege_ist_none():
    text = erkenner.baue_meldung(
        [{"art": "verworfen", "wert": "Zeitreise-Idee — zu teuer"}]
    )

    assert text is None


def test_baue_meldung_kernthema_plus_drei_figuren_eine_nachricht_mit_beiden_zeilen():
    text = erkenner.baue_meldung(
        [
            {"art": "kernthema_setzen", "wert": "Ankommen"},
            {"art": "figur_setzen", "wert": "Maria"},
            {"art": "figur_setzen", "wert": "Elif"},
            {"art": "figur_setzen", "wert": "Peter"},
        ]
    )

    assert text is not None
    assert "Kernthema: Ankommen" in text
    assert "drei Figuren: Maria, Elif, Peter" in text
    assert "Falls das nicht stimmt, sagt es mir." in text


def test_baue_meldung_eine_figur_steht_im_singular():
    text = erkenner.baue_meldung([{"art": "figur_setzen", "wert": "Maria"}])

    assert "eine Figur: Maria" in text


def test_baue_meldung_journaleintrag_neben_arbeitsstandaenderung_bleibt_still():
    text = erkenner.baue_meldung(
        [
            {"art": "kernthema_setzen", "wert": "Ankommen"},
            {"art": "verworfen", "wert": "Zeitreise-Idee — zu teuer"},
        ]
    )

    assert "Zeitreise-Idee" not in text
    assert "Kernthema: Ankommen" in text


class TelegramAttrappe:
    """Ersetzt interview_theater.telegram.Telegram: kein Netzzugriff, zeichnet auf."""

    def __init__(self, fehler=None):
        self.gesendet = []
        #: (chat_id, text, [(beschriftung, callback_data), ...]) je Angebot mit
        #: Inline-Tastatur -- seit dem 05.09.2026 nimmt auch der Erkenner-Pfad
        #: diesen Weg (``_melde_interviewmodus``).
        self.mit_knoepfen = []
        self._letzte_message_id = 9000
        self._fehler = fehler

    def sende(self, chat_id, text):
        if self._fehler is not None:
            raise self._fehler
        self._letzte_message_id += 1
        self.gesendet.append((chat_id, text))
        return self._letzte_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_):
        message_id = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return message_id


def test_laufe_ohne_neue_nachrichten_sendet_nichts(conn, einst):
    klm = LLMAttrappe(antwort={"aenderungen": []})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert tg.gesendet == []


def test_laufe_sendet_meldung_und_schreibt_sie_als_bot_nachricht(conn, einst):
    _nachricht(conn, 1, 1, "das Kernthema ist jetzt Ankommen")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "kernthema_setzen", "wert": "Ankommen"}]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert len(tg.gesendet) == 1
    chat_id, text = tg.gesendet[0]
    assert chat_id == 1
    assert "Kernthema: Ankommen" in text

    zeile = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = 1 AND ist_bot = 1"
    ).fetchone()
    assert zeile is not None
    assert zeile["text"] == text


def test_laufe_interview_starten_sendet_bestaetigung_getrennt_von_der_meldung(conn, einst):
    """teil-b.md Aufgabe 5: die Interviewmodus-Bestaetigung ist eine eigene
    Nachricht, nicht mit der Arbeitsstand-Meldung aus Aufgabe 4 vermischt --
    zwei kurze Nachrichten statt einer vermengten."""
    _nachricht(conn, 1, 1, "wir machen jetzt ein Interview, und das Kernthema ist Ankommen")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "interview_starten", "wert": ""},
        {"art": "kernthema_setzen", "wert": "Ankommen"},
    ]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    texte = [t for _, t in tg.gesendet]
    assert len(texte) == 2, "Bestaetigung und Meldung sind getrennte Nachrichten"
    assert any("Interview starten" in t for t in texte), "die Ablauf-Erklaerung"
    assert any("Kernthema: Ankommen" in t for t in texte)
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None, (
        "die Ankuendigung startet nichts -- der Knopf tut es"
    )


def test_laufe_interview_starten_haengt_den_aufnahme_knopf_darunter(conn, einst):
    """Birk, 05.09.2026 nach Gruppe 3, 16:36: kuendigt die Gruppe ein
    Interview an, bekommt sie die **Ablauf-Erklaerung** und den Knopf
    "Interview starten" -- gestartet wird durch den Druck, nicht durch die
    Ankuendigung. Vorher lief die Aufnahme schon, waehrend der Gespraechs-Bot
    daneben erklaerte, wie man sie startet."""
    _nachricht(conn, 1, 1, "ich will noch eine Aufnahme machen")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_starten", "wert": ""}]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert len(tg.mit_knoepfen) == 1
    chat_id, text, tasten = tg.mit_knoepfen[0]
    assert chat_id == 1
    assert text == knoepfe.TEXT_ABLAUF, "die drei Saetze, deterministisch"
    # Der Modus laeuft NICHT -- der Druck startet ihn.
    assert [b for b, _ in tasten] == ["Interview starten"]
    assert all(d.startswith(knoepfe.PRAEFIX) for _, d in tasten)


def test_laufe_interview_beenden_haengt_den_aufnahme_knopf_darunter(conn, einst):
    """Spiegelbildlich: nach dem Ende steht "Interview starten" darunter --
    genau der Knopf, den eine Gruppe braucht, die "noch eine Aufnahme"
    machen will."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    _nachricht(conn, 1, 1, "so, fertig")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_beenden", "wert": ""}]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert len(tg.mit_knoepfen) == 1
    _, text, tasten = tg.mit_knoepfen[0]
    assert "Aufnahme beendet." in text
    assert [b for b, _ in tasten] == ["Interview starten"]


def test_knopf_am_erkennerpfad_wirkt_nur_einmal(conn, einst):
    """Dieselbe Zusage wie bei jedem anderen Knopf (AGENTS.md, Zusage 3):
    der zweite Druck wird beantwortet, wirkt aber nicht. Hier ausdruecklich
    fuer den Knopf, der am Erkenner-Pfad entstanden ist -- er kommt aus einer
    anderen Funktion als der von ``/aufnahme`` und darf deshalb nicht
    stillschweigend an der Idempotenz vorbeilaufen."""
    _nachricht(conn, 1, 1, "ich will noch eine Aufnahme machen")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_starten", "wert": ""}]})
    tg = TelegramAttrappe()
    erkenner.laufe(klm, tg, conn, einst, 1)

    _, daten = tg.mit_knoepfen[0][2][0]
    knopf_id = int(daten[len(knoepfe.PRAEFIX):])

    assert repo.beanspruche_knopf(conn, knopf_id) is True
    assert repo.beanspruche_knopf(conn, knopf_id) is False


def test_laufe_interview_beenden_sendet_bestaetigung(conn, einst):
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    _nachricht(conn, 1, 1, "fertig, das war's fuer heute")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_beenden", "wert": ""}]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert len(tg.gesendet) == 1
    chat_id, text = tg.gesendet[0]
    assert chat_id == 1
    assert "Aufnahme beendet." in text
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None


def test_laufe_interview_starten_legt_ein_interview_an(conn, einst):
    """Spiegelbild zur Aenderung vom 05.09.2026: der Erkenner legt **kein**
    Interview mehr an. Der Live-Fall Gruppe 3: der Gespraechs-Bot erklaerte
    die Bedienung, gleichzeitig lief schon eine Aufnahme -- Text und Knopf
    widersprachen sich."""
    _nachricht(conn, 1, 1, "so, Fatima ist da, wir machen jetzt ein Interview")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_starten", "wert": ""}]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.laufendes_interview(conn, 1) is None
    assert repo.zaehle_interviews(conn, 1) == 0
    # Angeboten wird es trotzdem -- mit dem Knopf, der es startet.
    assert [b for _, _, ks in tg.mit_knoepfen for b, _ in ks] == ["Interview starten"]


def test_laufe_interview_beenden_stoesst_den_abschluss_an(conn, einst, monkeypatch):
    """§ 10.6: nach der Bestaetigung geht das beendete Interview an
    ``aufnahme.starte_abschluss`` -- Zusammenfuegen und die eine Verdichtung
    laufen in einem eigenen Thread, der Erkenner-Nachlauf haengt nicht daran."""
    from interview_theater import aufnahme

    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    kopf_id = aufnahme.stelle_interview_sicher(conn, 1)
    _nachricht(conn, 1, 1, "fertig")
    gestartet = []
    monkeypatch.setattr(
        aufnahme, "starte_abschluss",
        lambda conn, tg, klm, e, kid: gestartet.append(kid),
    )
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_beenden", "wert": ""}]})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    assert gestartet == [kopf_id]
    assert repo.hole_aufnahme(conn, kopf_id)["beendet_am"] is not None


def test_laufe_nur_journaleintrag_sendet_keine_nachricht(conn, einst):
    _nachricht(conn, 1, 1, "die Zeitreise-Idee verwerfen wir, zu teuer")
    klm = LLMAttrappe(
        antwort={"aenderungen": [{"art": "verworfen", "wert": "Zeitreise-Idee — zu teuer"}]}
    )
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert tg.gesendet == []
    assert len(repo.journal(conn, 1)) == 1


def test_laufe_versand_fehlschlag_bleibt_fuer_gruppe_unsichtbar(conn, einst):
    _nachricht(conn, 1, 1, "das Kernthema ist jetzt Ankommen")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "kernthema_setzen", "wert": "Ankommen"}]})
    tg = TelegramAttrappe(fehler=RuntimeError("Telegram nicht erreichbar"))

    erkenner.laufe(klm, tg, conn, einst, 1)  # darf nicht krachen

    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None


# ---------------------------------------------------------------------------
# szene_schreiben: die zwoelfte art (interview_theater/szene.py)
# ---------------------------------------------------------------------------


def test_szene_schreiben_ist_im_schema_enum():
    enum = erkenner.SCHEMA["properties"]["aenderungen"]["items"]["properties"]["art"]["enum"]
    assert "szene_schreiben" in enum


def test_szene_schreiben_veraendert_den_arbeitsstand_nicht(conn, einst):
    """Die einzige art ohne Schreibpfad: sie stoesst eine Handlung an, statt
    ein Feld zu setzen. wende_an() darf sie deshalb still verwerfen -- ihre
    Meldung kommt spaeter von szene.py selbst."""
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "szene_schreiben", "wert": "Szene 2: am Bahnhof"}]
    )

    assert wirkliche == []
    assert repo.hole_arbeitsstand(conn, 1) is None
    assert erkenner.baue_meldung([{"art": "szene_schreiben", "wert": "Szene 2"}]) is None


def test_laufe_stoesst_den_szenen_aufruf_an(conn, einst, monkeypatch):
    from interview_theater import szene

    gesehen = []
    monkeypatch.setattr(
        szene, "starte",
        lambda conn, tg, klm, e, chat_id, auftrag: gesehen.append((chat_id, auftrag)),
    )
    _nachricht(conn, 1, 1, "schreib uns die Szene am Bahnhof aus")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "szene_schreiben", "wert": "Szene 2: Maria kommt am Bahnhof an"},
    ]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert gesehen == [(1, "Szene 2: Maria kommt am Bahnhof an")]
    assert tg.gesendet == []  # die Ankuendigung kommt aus szene.starte


def test_laufe_stoesst_hoechstens_eine_szene_je_lauf_an(conn, einst, monkeypatch):
    """Eine zweite liefe ohnehin in die Sperre je chat_id und wuerde nur mit
    'ich schreibe gerade noch' abgewiesen -- zwei Nachrichten fuer nichts."""
    from interview_theater import szene

    gesehen = []
    monkeypatch.setattr(szene, "starte", lambda *a: gesehen.append(a[5]))
    _nachricht(conn, 1, 1, "schreib beide Szenen")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "szene_schreiben", "wert": "Szene 2: am Bahnhof"},
        {"art": "szene_schreiben", "wert": "Szene 3: im Amt"},
    ]})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    assert gesehen == ["Szene 2: am Bahnhof"]


def test_ohne_erkannten_auftrag_laeuft_keine_szene(conn, einst, monkeypatch):
    """Der teure Fehlerfall: ein falsch ausgeloester Szenentext kostet die
    Gruppe zwei Minuten Wartezeit und eine Nachricht, die sie nicht bestellt
    hat. Die Abgrenzung "Auftrag, nicht Vorhaben" steht im Prompt; hier wird
    geprueft, dass eine leere Erkennung auch wirklich nichts anstoesst."""
    from interview_theater import szene

    monkeypatch.setattr(szene, "starte", lambda *a: pytest.fail("kein Auftrag, kein Lauf"))
    _nachricht(conn, 1, 1, "wir sollten bald mal Szenen machen")
    klm = LLMAttrappe(antwort={"aenderungen": []})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 1


# ---------------------------------------------------------------------------
# phase_setzen (Brief A2/A3): die Gruppe sagt, woran sie arbeitet
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wert, erwartet",
    [("5", 5), ("Figuren", 4), ("Kernthema", 4), ("interview", 3),
     ("Hauptkonflikt", 5)],
)
def test_phase_setzen_mappt_nummer_namen_und_teilstring(conn, einst, wert, erwartet):
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": wert}])

    assert repo.hole_phase(conn, 1) == erwartet
    assert wirkliche == [{"art": "phase_setzen", "wert": str(erwartet)}]


def test_phase_setzen_mit_unbekanntem_wert_aendert_nichts(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "phase_setzen", "wert": "Kaffeepause"}]
    )

    assert wirkliche == []
    assert repo.hole_phase(conn, 1) is None


def test_phase_setzen_auf_denselben_wert_meldet_nicht(conn, einst):
    erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "5"}])

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "5"}])

    assert wirkliche == []
    assert erkenner.baue_meldung(wirkliche) is None


def test_phase_setzen_meldet_die_neue_phase(conn, einst):
    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "5"}])

    meldung = erkenner.baue_meldung(wirkliche)

    assert "Wir sind jetzt bei 5 · Rahmen." in meldung
    assert meldung.endswith("Falls das nicht stimmt, sagt es mir.")


def test_ruecksprung_ueber_den_erkenner(conn, einst):
    """'nee, wir sind noch beim Kernthema' -- der Erkenner greift den
    Ruecksprung als phase_setzen auf, genau wie einen Schritt nach vorn."""
    phasen.setze(conn, 1, 5, "erkenner")

    erkenner.wende_an(conn, einst, 1, [{"art": "phase_setzen", "wert": "Kernthema"}])

    assert repo.hole_phase(conn, 1) == 4


def test_der_erkenner_schaltet_die_phase_nicht_selbst(conn, einst):
    """**Die Entscheidung vom 05.09.2026.** Der Lauf schreibt das Kernthema;
    frueher schaltete der Code daraufhin selbst eine Phase weiter und meldete
    das mit. Das ist verworfen: Datenstand ist nicht Absicht -- ein gesetztes
    Kernthema sagt nicht, dass die Gruppe damit fertig ist. Der Arbeitsstand
    waechst und wird gemeldet, die Phase bleibt, wo sie war."""
    phasen.setze(conn, 1, 4, "befehl")
    _nachricht(conn, 1, 1, "also, unser Kernthema ist Ankommen")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "kernthema_setzen", "wert": "Ankommen"},
    ]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.hole_phase(conn, 1) == 4
    text = tg.gesendet[0][1]
    assert "Kernthema: Ankommen" in text
    assert "Wir sind damit bei" not in text
    assert len(tg.gesendet) == 1, "eine Meldung je Lauf"


def test_auch_eine_zweite_figur_schaltet_nichts(conn, einst):
    """Dasselbe fuer die Aenderung, die frueher am haeufigsten gesprungen ist:
    die zweite Figur. Der Arbeitsstand waechst, die Phase nicht."""
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    _nachricht(conn, 1, 1, "und Elif ist die Nachbarin")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "figur_setzen", "wert": "Elif: Nachbarin"},
    ]})
    tg = TelegramAttrappe()

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.hole_phase(conn, 1) == 4
    assert "Wir sind damit bei" not in tg.gesendet[0][1]


# ---------------------------------------------------------------------------
# entfernen (NACHTRAG N3): weiches Loeschen
# ---------------------------------------------------------------------------


def test_entfernen_nimmt_eine_figur_weg_und_meldet_es(conn, einst):
    repo.setze_figur(conn, 1, "Peter", "Nachbar")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "entfernen", "wert": "Figur Peter"}]
    )

    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Maria"]
    assert wirkliche == [{"art": "entfernen", "wert": "Figur Peter"}]
    assert "Entfernt: Figur Peter" in erkenner.baue_meldung(wirkliche)


def test_format_und_rahmen_landen_im_arbeitsstand_und_in_der_meldung(conn, einst):
    """Phase 5 heisst seit dem 05.09.2026 "Rahmen" -- zwei Felder,
    zwei Arten, und beide bekommen in der Notiert-Zeile eine eigene Zeile im
    Wortlaut (wie Kernthema und Hauptkonflikt)."""
    wirkliche = erkenner.wende_an(conn, einst, 1, [
        {"art": "format_setzen", "wert": "Musical: Dialog, Lied, Rap"},
        {"art": "rahmen_setzen", "wert": "Demo, danach eine Kueche"},
    ])

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["format"] == "Musical: Dialog, Lied, Rap"
    assert stand["rahmen"] == "Demo, danach eine Kueche"
    meldung = erkenner.baue_meldung(wirkliche)
    assert "Format: Musical: Dialog, Lied, Rap" in meldung
    assert "Rahmen: Demo, danach eine Kueche" in meldung


def test_der_rahmen_steht_im_erkenner_kontext(conn, einst):
    """Der Erkenner sieht den Arbeitsstand -- sonst koennte er eine Zustimmung
    ("ja, so machen wir das") nicht auf den Rahmen beziehen, der im Verlauf
    vorgeschlagen wurde. Das Format steht seit dem 05.09.2026 abends nicht
    mehr dabei: es wird nicht mehr gefragt."""
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")

    text = erkenner._arbeitsstand_text(conn, 1)

    assert "Musical: Dialog, Lied, Rap" not in text
    assert "Rahmen: Eine Nacht im Treppenhaus" in text


def _interview(conn, name="Interview 2", text="Pola: Halt so, ne?"):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 200, "lang", "text")
    repo.setze_aufnahme_name(conn, aufnahme_id, name)
    repo.setze_transkript(conn, aufnahme_id, text)
    return aufnahme_id


def test_figur_quelle_setzen_ordnet_die_figur_ihrem_interview_zu(conn, einst):
    aufnahme_id = _interview(conn)
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_quelle_setzen", "wert": "Pola: Interview 2"}]
    )

    assert repo.hole_figur(conn, 1, "Pola")["quelle_aufnahme_id"] == aufnahme_id
    assert wirkliche[0]["figur_id"] == repo.hole_figur(conn, 1, "Pola")["id"]
    # Still: die Zeile, die zaehlt, kommt aus sprachprofil.py, wenn das Profil
    # wirklich steht.
    assert erkenner.baue_meldung(wirkliche) is None


def test_figur_quelle_setzen_braucht_eine_figur_und_ein_interview(conn, einst):
    """Eine falsche Zuordnung praegte ueber das Sprachprofil die Stimme einer
    Figur in jedem weiteren Szenenlauf -- also lieber gar keine."""
    _interview(conn)
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")

    assert erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_quelle_setzen", "wert": "Nina: Interview 2"}]
    ) == []
    assert erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_quelle_setzen", "wert": "Pola: Interview 9"}]
    ) == []
    assert repo.hole_figur(conn, 1, "Pola")["quelle_aufnahme_id"] is None


def test_dieselbe_quelle_mit_fertigem_profil_ist_keine_aenderung(conn, einst):
    """Sonst liefe bei jedem Erkennerlauf ein zweiter bezahlter
    Sprachprofil-Aufruf fuer dasselbe Ergebnis."""
    _interview(conn)
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")
    erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_quelle_setzen", "wert": "Pola: Interview 2"}]
    )
    repo.setze_sprachprofil(conn, repo.hole_figur(conn, 1, "Pola")["id"], "Kurz.", ["Halt so, ne?"])

    assert erkenner.wende_an(
        conn, einst, 1, [{"art": "figur_quelle_setzen", "wert": "Pola: Interview 2"}]
    ) == []


def test_szene_planen_legt_die_szene_an_und_setzt_die_felder(conn, einst):
    repo.setze_figur(conn, 1, "Mira", "kam mit 19 her")
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")

    wirkliche = erkenner.wende_an(conn, einst, 1, [{
        "art": "szene_planen",
        "wert": "Szene 1 | form: Dialog | ort: Polizeikessel | figuren: Mira, Pola "
                "| was_passiert: sie kommen nicht raus",
    }])

    zeile = repo.hole_szenen(conn, 1)[0]
    assert (zeile["nummer"], zeile["form"], zeile["ort"]) == (1, "Dialog", "Polizeikessel")
    assert zeile["was_passiert"] == "sie kommen nicht raus"
    assert [f["name"] for f in repo.szene_figuren(conn, zeile["id"])] == ["Mira", "Pola"]
    assert wirkliche[0]["wert"] == "Szene 1 · Dialog · Polizeikessel · Mira, Pola"
    assert "Szene 1 · Dialog" in erkenner.baue_meldung(wirkliche)


def test_szene_planen_traegt_nach_ohne_zu_ueberschreiben(conn, einst):
    """Die Regel aus Birks Ping-Pong: eine Szene entsteht ueber mehrere
    Nachrichten hinweg, und jede ergaenzt die vorige."""
    repo.setze_figur(conn, 1, "Mira", "kam mit 19 her")
    erkenner.wende_an(conn, einst, 1, [{
        "art": "szene_planen",
        "wert": "Szene 1 | form: Dialog | ort: Polizeikessel | figuren: Mira",
    }])

    erkenner.wende_an(conn, einst, 1, [{
        "art": "szene_planen",
        "wert": 'Szene 1 | kernsaetze: "Trump macht daraus eine Riviera"',
    }])

    zeile = repo.hole_szenen(conn, 1)[0]
    assert zeile["ort"] == "Polizeikessel"
    assert zeile["form"] == "Dialog"
    assert zeile["kernsaetze"] == '"Trump macht daraus eine Riviera"'
    assert [f["name"] for f in repo.szene_figuren(conn, zeile["id"])] == ["Mira"]


def test_szene_planen_nimmt_nur_figuren_aus_dem_arbeitsstand(conn, einst):
    """Birk 05.09.2026: eine Szene wird nur mit Figuren besetzt, die es gibt.
    Im Probelauf standen sonst NINA und MORITZ im Text, die nie jemand
    entwickelt hatte."""
    repo.setze_figur(conn, 1, "Mira", "kam mit 19 her")

    erkenner.wende_an(conn, einst, 1, [{
        "art": "szene_planen", "wert": "Szene 1 | figuren: Mira, Nina, Moritz",
    }])

    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    assert [f["name"] for f in repo.szene_figuren(conn, szene_id)] == ["Mira"]
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Mira"]


def test_szene_planen_laesst_die_besetzung_stehen_wenn_niemand_passt(conn, einst):
    """Eine Besetzung zu leeren waere die schlechtere Fehlerrichtung -- eine
    leere Besetzung meldet ohnehin die Sperre vor dem Szenen-Aufruf."""
    repo.setze_figur(conn, 1, "Mira", "kam mit 19 her")
    erkenner.wende_an(conn, einst, 1, [
        {"art": "szene_planen", "wert": "Szene 1 | figuren: Mira"},
    ])

    erkenner.wende_an(conn, einst, 1, [
        {"art": "szene_planen", "wert": "Szene 1 | figuren: Nina"},
    ])

    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    assert [f["name"] for f in repo.szene_figuren(conn, szene_id)] == ["Mira"]


def test_szene_planen_ohne_nummer_trifft_die_zuletzt_bearbeitete(conn, einst):
    erkenner.wende_an(conn, einst, 1, [
        {"art": "szene_planen", "wert": "Szene 3 | ort: Kueche"},
    ])

    erkenner.wende_an(conn, einst, 1, [
        {"art": "szene_planen", "wert": "ton: leise"},
    ])

    szenen = repo.hole_szenen(conn, 1)
    assert len(szenen) == 1
    assert (szenen[0]["nummer"], szenen[0]["ton"]) == (3, "leise")


def test_szene_planen_ohne_inhalt_aendert_nichts(conn, einst):
    assert erkenner.wende_an(conn, einst, 1, [{"art": "szene_planen", "wert": ""}]) == []
    assert repo.hole_szenen(conn, 1) == []


def test_szene_planen_mit_demselben_wert_ist_keine_aenderung(conn, einst):
    erkenner.wende_an(conn, einst, 1, [
        {"art": "szene_planen", "wert": "Szene 1 | ort: Kueche"},
    ])

    wirkliche = erkenner.wende_an(conn, einst, 1, [
        {"art": "szene_planen", "wert": "Szene 1 | ort: Kueche"},
    ])

    assert wirkliche == []


def test_entfernen_leert_kernthema_samt_begruendung(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "kernthema_begruendung", "dreimal genannt")

    erkenner.wende_an(conn, einst, 1, [{"art": "entfernen", "wert": "Kernthema"}])

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["kernthema"] is None
    assert stand["kernthema_begruendung"] is None


@pytest.mark.parametrize(
    "feld, wert",
    [
        ("format", "Format"),
        ("rahmen", "Rahmen"),
        ("hauptkonflikt", "Hauptkonflikt"),
        ("begriffe", "Begriffe"),
        ("fragen", "Fragen"),
    ],
)
def test_entfernen_leert_die_uebrigen_arbeitsstandfelder(conn, einst, feld, wert):
    repo.setze_arbeitsstand(conn, 1, feld, "irgendwas")

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "entfernen", "wert": wert}])

    assert repo.hole_arbeitsstand(conn, 1)[feld] is None
    assert wirkliche == [{"art": "entfernen", "wert": wert}]


def test_entfernen_nimmt_eine_szene_nach_nummer_weg(conn, einst):
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: Da.")
    repo.lege_szene_an(conn, 1, 2, "Abschied", "Peter geht", "PETER: Weg.")

    erkenner.wende_an(conn, einst, 1, [{"art": "entfernen", "wert": "Szene 2"}])

    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [1]


def test_entfernen_eines_journaleintrags_haelt_den_weg_sichtbar(conn, einst):
    """Das Journal bleibt nur-anhaengend: der alte Eintrag wird gestempelt,
    ein neuer sagt, dass er zurueckgenommen wurde."""
    repo.schreibe_journal(
        conn, 1, "verworfen", "Kindheitsfragen als Einstieg - zu privat", "erkenner"
    )

    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "entfernen", "wert": "Journal: Kindheitsfragen"}]
    )

    texte = [e["text"] for e in repo.journal(conn, 1)]
    assert texte == ["Zurueckgenommen: Kindheitsfragen als Einstieg - zu privat"]
    assert wirkliche[0]["wert"].startswith("Journal: Kindheitsfragen")


@pytest.mark.parametrize(
    "wert",
    ["Aufnahme von Meryem", "Transkript 2", "Verdichtung von Maria", "Interview 3", ""],
)
def test_material_ist_nicht_entfernbar(conn, einst, wert):
    """NACHTRAG N3: Aufnahmen, Transkripte und Verdichtungen haben keinen
    Schreibpfad hierher -- auch dann nicht, wenn der Erkenner es entgegen
    seiner Anweisung doch einmal liefert."""
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "hallo", repo._jetzt())
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", "/tmp/a.ogg", 60)
    repo.speichere_verdichtung(conn, 1, aufnahme_id, "Maria erzaehlt", [])

    wirkliche = erkenner.wende_an(conn, einst, 1, [{"art": "entfernen", "wert": wert}])

    assert wirkliche == []
    assert len(repo.transkripte(conn, 1)) == 1
    assert len(repo.verdichtungen(conn, 1)) == 1
    assert repo.journal(conn, 1) == []


def test_entfernen_ohne_treffer_ist_kein_fehler_und_keine_meldung(conn, einst):
    wirkliche = erkenner.wende_an(
        conn, einst, 1, [{"art": "entfernen", "wert": "Figur Gibtsnicht"}]
    )

    assert wirkliche == []
    assert repo.journal(conn, 1) == []
    assert erkenner.baue_meldung(wirkliche) is None


def test_entfernen_schreibt_eine_journalzeile(conn, einst):
    repo.setze_figur(conn, 1, "Peter", "Nachbar")

    erkenner.wende_an(conn, einst, 1, [{"art": "entfernen", "wert": "Figur Peter"}])

    eintrag = repo.journal(conn, 1)[-1]
    assert eintrag["art"] == "entschieden"
    assert eintrag["text"] == "Entfernt: Figur Peter"
    assert eintrag["quelle"] == "erkenner"


# ---------------------------------------------------------------------------
# N1: der Erkenner ueber das Transkript einer Sprachnachricht im Interviewmodus
# ---------------------------------------------------------------------------


def test_erkenne_in_aufnahme_liefert_nur_die_erlaubten_arten(conn, einst):
    """Was die interviewte Person erzaehlt, ist Material. Der Filter steht im
    Code, nicht nur im Prompt -- ein Modell, das aus einer Lebensgeschichte
    ein Kernthema liest, darf den Arbeitsstand nicht anfassen (n12/n26)."""
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "kernthema_setzen", "wert": "Ankommen"},
        {"art": "interview_beenden", "wert": ""},
        {"art": "entfernen", "wert": "Kernthema"},
    ]})

    ergebnis = erkenner.erkenne_in_aufnahme(klm, conn, einst, 1, "so, das war es dann")

    assert ergebnis == [{"art": "interview_beenden", "wert": ""}]
    assert klm.gesehen["modell"] == einst.erkenner_modell
    assert klm.gesehen["temperature"] == erkenner.TEMPERATURE
    assert "so, das war es dann" in klm.gesehen["nutzer"]


def test_erkenne_in_aufnahme_ruehrt_das_wasserzeichen_nicht_an(conn, einst):
    """Dieser Lauf haengt an einer Aufnahme, nicht am Gespraechsverlauf: er
    darf dem naechsten regulaeren Lauf keine Nachrichten wegnehmen."""
    _nachricht(conn, 1, 7, "wir machen jetzt ein Interview")
    klm = LLMAttrappe(antwort={"aenderungen": [{"art": "interview_beenden", "wert": ""}]})

    erkenner.erkenne_in_aufnahme(klm, conn, einst, 1, "fertig")

    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 0


def test_erkenne_in_aufnahme_ohne_transkript_ruft_kein_modell(conn, einst):
    klm = LLMAttrappe(antwort={"aenderungen": []})

    assert erkenner.erkenne_in_aufnahme(klm, conn, einst, 1, "   ") == []
    assert klm.aufrufe == 0


def test_erkenne_in_aufnahme_fehlschlag_bleibt_still(conn, einst):
    """Ein gescheiterter Lauf laesst die Aufnahme Material bleiben -- der
    harmlose Ausgang. Die Gruppe erfaehrt nichts, das Dashboard schon."""
    klm = LLMAttrappe(fehler=RuntimeError("kaputt"))

    assert erkenner.erkenne_in_aufnahme(klm, conn, einst, 1, "fertig") == []
    assert conn.execute(
        "SELECT count(*) FROM vorfall WHERE art='extraktor_fehler'"
    ).fetchone()[0] == 1


def test_erkenner_bekommt_die_letzte_bot_nachricht_als_vorlauf(conn, einst):
    """05.09. 04:40, dreimal belegt (Live 69/90, Simulation set1, --set birk
    S11): der Vorschlag des Bots liegt im vorigen Zug, das Wasserzeichen ist
    schon darueber, die Zustimmung kommt allein an. Der Vorlauf bringt den
    Vorschlag zurueck ins Fenster -- markiert, nicht als neue Nachricht."""
    repo.sichere_gruppe(conn, 1, "bot", "g")
    repo.merke_nachricht(conn, 1, 10, "Bot", 1, "text", "Drei Figuren: Mira, Pola, Pal. Passt das?", "2026-09-05T04:00:00+00:00")
    repo.setze_extrahiert_bis(conn, 1, 10)
    repo.merke_nachricht(conn, 1, 11, "Birk", 0, "text", "namen nehme ich so", "2026-09-05T04:00:10+00:00")
    neue = repo.unextrahierte(conn, 1)
    assert [n["message_id"] for n in neue] == [11]
    vorlauf = repo.letzte_bot_nachricht_vor(conn, 1, 11)
    assert vorlauf["message_id"] == 10
    text = erkenner._baue_nutzertext(conn, 1, neue, vorlauf)
    assert "Vorlauf" in text and "Mira, Pola, Pal" in text
    assert text.index("Vorlauf") < text.index("Neue Nachrichten")


def test_vorlauf_ueberspringt_notiert_zeilen(conn, einst):
    repo.sichere_gruppe(conn, 1, "bot", "g")
    repo.merke_nachricht(conn, 1, 10, "Bot", 1, "text", "Vorschlag: Mira.", "2026-09-05T04:00:00+00:00")
    repo.merke_nachricht(conn, 1, 11, "Bot", 1, "text", "Notiert:\nPhase 4", "2026-09-05T04:00:01+00:00")
    assert repo.letzte_bot_nachricht_vor(conn, 1, 12)["message_id"] == 10
