"""Tests fuer die neun Slash-Befehle (teil-b.md Aufgabe 6, plus /szene,
/phase und /figur).

Kein Netzzugriff: Telegram wird durch eine Attrappe ersetzt, die nur
aufzeichnet, was gesendet wurde. Acht der neun Befehle werden hier ohne
jedes LLM-Objekt aufgerufen -- "/stand ruft kein Modell" bleibt damit an den
Tests ablesbar, auch seit behandle() ein optionales ``klm`` fuer /szene
entgegennimmt.
"""

import pytest

from interview_theater import befehle, phasen, repo


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []  # Liste von (chat_id, text)

    def sende(self, chat_id, text):
        self.gesendet.append((chat_id, text))
        return 9001


@pytest.fixture
def tg():
    return TelegramAttrappe()


def test_normale_nachricht_wird_nicht_behandelt(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "ich hol mir kaffee", "Ada")
    assert behandelt is False
    assert tg.gesendet == []


def test_interview_schaltet_modus_an_und_bestaetigt(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/interview", "Ada")
    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is not None
    assert tg.gesendet == [(1, "Ich zeichne jetzt auf.")]


def test_fertig_schaltet_modus_aus_und_bestaetigt(conn, einst, tg):
    repo.setze_interviewmodus(conn, 1, repo._jetzt())

    behandelt = befehle.behandle(conn, tg, einst, 1, "/fertig", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["interviewmodus_seit"] is None
    assert tg.gesendet == [(1, "Aufnahme beendet.")]


def test_kernthema_setzt_arbeitsstand(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/kernthema Ankommen und Bleiben", "Ada")

    assert behandelt is True
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen und Bleiben"
    assert "Ankommen und Bleiben" in tg.gesendet[0][1]


def test_kernthema_ohne_text_fragt_freundlich_nach(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/kernthema", "Ada")

    assert behandelt is True
    assert repo.hole_arbeitsstand(conn, 1) is None
    assert "kernthema" in tg.gesendet[0][1].lower()


def test_kernthema_korrigiert_vorhandenen_wert(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/kernthema Ankommen", "Ada")
    befehle.behandle(conn, tg, einst, 1, "/kernthema Abschied", "Ada")

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Abschied"


def test_stand_ruft_kein_modell_und_zeigt_arbeitsstand(conn, einst, tg):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_interviewmodus(conn, 1, repo._jetzt())

    behandelt = befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")

    assert behandelt is True
    text = tg.gesendet[0][1]
    assert "Kernthema: Ankommen" in text
    assert "Maria" in text
    assert "Interviewmodus: an" in text


def test_stand_auf_leerer_datenbank_kracht_nicht(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")
    assert behandelt is True
    assert len(tg.gesendet) == 1


def test_wortlaut_mit_bekanntem_namen_schaltet_an(conn, einst, tg):
    repo.lege_aufnahme_an(conn, 1, 1, "lang", "sprache")
    repo.setze_aufnahme_name(conn, 1, "Maria")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut Maria", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "Maria"


def test_wortlaut_mit_unbekanntem_namen_zaehlt_vorhandene_auf(conn, einst, tg):
    repo.lege_aufnahme_an(conn, 1, 1, "lang", "sprache")
    repo.setze_aufnahme_name(conn, 1, "Maria")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut Peter", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None
    assert "Maria" in tg.gesendet[0][1]


def test_wortlaut_aus_schaltet_modus_aus(conn, einst, tg):
    repo.setze_wortlaut_modus(conn, 1, "*")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut aus", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_wortlaut_ohne_argument_schaltet_alle_an(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/wortlaut", "Ada")

    assert behandelt is True
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "*"


def test_hilfe_nennt_ansprache_interviewmodus_und_befehle(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/hilfe", "Ada")

    assert behandelt is True
    text = tg.gesendet[0][1]
    # Live-Test 1: /hilfe behauptet nichts mehr ueber Reply oder @Erwaehnung
    # (die Gruppe ist ein reines Interface zum Bot, er antwortet auf alles).
    assert "antworte" in text
    assert "Interview" in text
    assert "/stand" in text


def test_unbekannter_befehl_antwortet_freundlich_statt_zu_krachen(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/irgendwas", "Ada")

    assert behandelt is True
    assert len(tg.gesendet) == 1
    assert "kenne ich nicht" in tg.gesendet[0][1]


@pytest.mark.parametrize("befehl", ["/interview", "/fertig", "/stand", "/hilfe"])
def test_befehl_mit_botname_wird_erkannt(conn, einst, tg, befehl):
    text = f"{befehl}@{einst.bot_name}"
    behandelt = befehle.behandle(conn, tg, einst, 1, text, "Ada")
    assert behandelt is True
    assert len(tg.gesendet) == 1


def test_kernthema_mit_botname_und_text_wird_erkannt(conn, einst, tg):
    text = f"/kernthema@{einst.bot_name} Ankommen"
    behandelt = befehle.behandle(conn, tg, einst, 1, text, "Ada")

    assert behandelt is True
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"


def test_befehle_liste_enthaelt_alle_neun_ohne_schraegstrich():
    kommandos = {b["command"] for b in befehle.BEFEHLE_LISTE}
    assert kommandos == {
        "interview", "fertig", "phase", "kernthema", "figur", "szene", "stand",
        "wortlaut", "hilfe",
    }


# ---------------------------------------------------------------------------
# /szene -- der deterministische Weg zum Szenentext
# ---------------------------------------------------------------------------


def test_szene_stoesst_den_szenen_aufruf_mit_dem_auftrag_an(conn, einst, tg, monkeypatch):
    from interview_theater import szene

    gesehen = []
    monkeypatch.setattr(
        szene, "starte",
        lambda conn, tg, klm, e, chat_id, auftrag: gesehen.append((chat_id, auftrag)),
    )

    behandelt = befehle.behandle(
        conn, tg, einst, 1, "/szene Szene 2: Maria am Bahnhof", "Ada", klm=object(),
    )

    assert behandelt is True
    assert gesehen == [(1, "Szene 2: Maria am Bahnhof")]
    assert tg.gesendet == []  # die Ankuendigung kommt aus szene.starte


def test_szene_mit_botname_wird_erkannt(conn, einst, tg, monkeypatch):
    from interview_theater import szene

    gesehen = []
    monkeypatch.setattr(szene, "starte", lambda *a: gesehen.append(a[5]))

    befehle.behandle(
        conn, tg, einst, 1, f"/szene@{einst.bot_name} Szene 2: am Bahnhof", "Ada",
        klm=object(),
    )

    assert gesehen == ["Szene 2: am Bahnhof"]


def test_szene_ohne_auftrag_fragt_freundlich_nach(conn, einst, tg, monkeypatch):
    from interview_theater import szene

    monkeypatch.setattr(szene, "starte", lambda *a: pytest.fail("ohne Auftrag kein Lauf"))

    behandelt = befehle.behandle(conn, tg, einst, 1, "/szene", "Ada", klm=object())

    assert behandelt is True
    assert "Auftrag" in tg.gesendet[0][1]


def test_szene_ohne_sprachmodell_krachte_nicht(conn, einst, tg):
    """Ein Aufrufer ohne ``klm`` ist ein Programmierfehler -- aber einer, der
    die Gruppe nicht ratlos zuruecklassen darf."""
    behandelt = befehle.behandle(conn, tg, einst, 1, "/szene Szene 2", "Ada")

    assert behandelt is True
    assert len(tg.gesendet) == 1


# ---------------------------------------------------------------------------
# /phase -- der Notausgang fuer die Arbeitsphase (Brief A2)
# ---------------------------------------------------------------------------


def test_phase_ohne_argument_zeigt_phase_und_liste(conn, einst, tg):
    phasen.setze(conn, 1, 5, "befehl")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/phase", "Ada")

    assert behandelt is True
    text = tg.gesendet[0][1]
    assert "Wir sind bei 5 · Figuren entwickeln." in text
    for nummer, name, _ in phasen.PHASEN:
        assert f"{nummer} · {name}" in text


def test_phase_ohne_gesetzte_phase_zeigt_die_erste(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/phase", "Ada")

    assert "Wir sind bei 1 · Ankommen." in tg.gesendet[0][1]


def test_phase_mit_nummer_schaltet_um_und_meldet(conn, einst, tg):
    behandelt = befehle.behandle(conn, tg, einst, 1, "/phase 5", "Ada")

    assert behandelt is True
    assert repo.hole_phase(conn, 1) == 5
    assert tg.gesendet == [
        (1, "Wir sind jetzt bei 5 · Figuren entwickeln. Falls nicht, sagt es mir.")
    ]


def test_phase_mit_namen_schaltet_auch_zurueck(conn, einst, tg):
    phasen.setze(conn, 1, 8, "befehl")

    befehle.behandle(conn, tg, einst, 1, "/phase Figuren", "Ada")

    assert repo.hole_phase(conn, 1) == 5


def test_phase_journalisiert_nur_die_echte_aenderung(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/phase 5", "Ada")
    befehle.behandle(conn, tg, einst, 1, "/phase 5", "Ada")

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["quelle"] == "befehl"
    assert len(tg.gesendet) == 2, "auf einen getippten Befehl wird immer geantwortet"


def test_phase_mit_unsinn_aendert_nichts_und_zeigt_die_liste(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/phase Kaffeepause", "Ada")

    assert repo.hole_phase(conn, 1) is None
    assert befehle._TEXT_PHASE_UNBEKANNT in tg.gesendet[0][1]


def test_stand_zeigt_die_phase_zuerst(conn, einst, tg):
    phasen.setze(conn, 1, 5, "befehl")

    befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")

    zeilen = tg.gesendet[0][1].splitlines()
    assert zeilen[0] == "Stand:"
    assert zeilen[1] == "Phase: 5 · Figuren entwickeln"


# ---------------------------------------------------------------------------
# Weiches Loeschen ueber Befehle (NACHTRAG N3, Brief B3)
# ---------------------------------------------------------------------------


def test_figur_entfernen_nimmt_die_figur_weg(conn, einst, tg):
    repo.setze_figur(conn, 1, "Peter", "Nachbar")

    behandelt = befehle.behandle(conn, tg, einst, 1, "/figur Peter entfernen", "Ada")

    assert behandelt is True
    assert repo.figuren(conn, 1) == []
    assert tg.gesendet[0][1].startswith("Entfernt: Figur Peter.")
    assert repo.journal(conn, 1)[-1]["quelle"] == "befehl"


def test_figur_entfernen_mit_unbekanntem_namen_sagt_es(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/figur Gibtsnicht entfernen", "Ada")

    assert "kenne ich nicht" in tg.gesendet[0][1]
    assert repo.journal(conn, 1) == []


def test_figur_ohne_entfernen_erklaert_den_befehl(conn, einst, tg):
    """``/figur`` legt bewusst nichts an -- das macht der Erkenner im
    Gespraech."""
    befehle.behandle(conn, tg, einst, 1, "/figur Peter: Nachbar", "Ada")

    assert tg.gesendet == [(1, befehle._TEXT_FIGUR_HILFE)]
    assert repo.figuren(conn, 1) == []


def test_szene_entfernen_nimmt_die_szene_weg(conn, einst, tg):
    repo.lege_szene_an(conn, 1, 2, "Abschied", "Peter geht", "PETER: Weg.")

    befehle.behandle(conn, tg, einst, 1, "/szene 2 entfernen", "Ada")

    assert repo.hole_szenen(conn, 1) == []
    assert tg.gesendet[0][1].startswith("Entfernt: Szene 2.")


def test_szene_schreibauftrag_bleibt_ein_schreibauftrag(conn, einst, tg, monkeypatch):
    """Die Abgrenzung ist eng: nur 'Nummer + Entfernungswort' loescht, alles
    andere geht an szene.starte."""
    from interview_theater import szene

    gesehen = []
    monkeypatch.setattr(szene, "starte", lambda *a: gesehen.append(a[5]))
    repo.lege_szene_an(conn, 1, 2, "Abschied", "Peter geht", "PETER: Weg.")

    befehle.behandle(conn, tg, einst, 1, "/szene 2 nochmal kuerzer", "Ada", klm=object())

    assert gesehen == ["2 nochmal kuerzer"]
    assert len(repo.hole_szenen(conn, 1)) == 1


def test_kernthema_aus_leert_das_kernthema(conn, einst, tg):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    befehle.behandle(conn, tg, einst, 1, "/kernthema aus", "Ada")

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] is None
    assert tg.gesendet[0][1].startswith("Entfernt: Kernthema.")


def test_kernthema_aus_ohne_kernthema_sagt_es(conn, einst, tg):
    befehle.behandle(conn, tg, einst, 1, "/kernthema aus", "Ada")

    assert tg.gesendet == [(1, "Ein Kernthema war nicht gesetzt.")]
