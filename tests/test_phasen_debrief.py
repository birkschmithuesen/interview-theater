"""Tests fuer den Phasen-Debrief (Karte phasen-debrief).

**Teil 1** (oben, unveraendert aus der ersten Aufgabe): die Ablage-Schicht --
Tabelle ``phasen_debrief`` und die vier Repo-Funktionen. Kein Modellaufruf,
keine Anbindung an ``phasen.py`` oder ``bot.py``.

**Teil 2** (unten, diese Aufgabe): die eigentliche Pipeline
(``interview_theater/phasen_debrief.py``) und ihre Anbindung an
``phasen.setze``. Geprueft wird: die Umschalter (env), die Mindestschwelle,
dass ``phasen.setze`` mit der VORHERIGEN Phase dispatcht, dass
Transkript-Echos nie in den Nutzertext oder den Zitat-Korpus geraten, die
Modellwahl (Infomaniak unter Phase 4, Claude ab Phase 4 nur mit
Einwilligung, Fallback bei einem Claude-Fehler), der Zitat-Filter (keine
Zeile ohne belegtes Zitat) und dass ein zweiter Lauf fuer dieselbe Phase den
ersten ersetzt statt sich daneben zu haeufen.

Kein Netzzugriff: das Sprachmodell ist in jedem Test eine Attrappe.
"""

import pytest

from interview_theater import db, phasen, phasen_debrief, repo, szene_claude


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    repo.sichere_gruppe(c, 2, "gruppe2", "Zweite Gruppe")
    return c


def test_schema_legt_phasen_debrief_mit_erwarteten_spalten_an(conn):
    spalten = {z["name"] for z in conn.execute("PRAGMA table_info(phasen_debrief)")}
    assert spalten == {
        "id", "chat_id", "phase", "text", "erstellt_am", "modell", "geloescht",
    }


def test_loesche_gruppe_entfernt_nur_die_eigenen_zeilen(conn):
    repo.merke_phasen_debrief(conn, 1, 1, "Text Gruppe 1", "gemma")
    repo.merke_phasen_debrief(conn, 2, 1, "Text Gruppe 2", "gemma")
    db.loesche_gruppe(conn, 1)
    assert repo.phasen_debriefs(conn, 1) == []
    assert len(repo.phasen_debriefs(conn, 2)) == 1


def test_merken_und_lesen_im_rundlauf(conn):
    repo.merke_phasen_debrief(conn, 1, 1, "Die Gruppe hat drei Begriffe notiert.", "gemma")
    zeilen = repo.phasen_debriefs(conn, 1)
    assert len(zeilen) == 1
    zeile = zeilen[0]
    assert zeile["chat_id"] == 1
    assert zeile["phase"] == 1
    assert zeile["text"] == "Die Gruppe hat drei Begriffe notiert."
    assert zeile["modell"] == "gemma"
    assert zeile["geloescht"] == 0
    assert zeile["erstellt_am"]


def test_erneutes_verlassen_derselben_phase_ersetzt_den_text(conn):
    repo.merke_phasen_debrief(conn, 1, 2, "Erster Durchlauf durch Phase 2.", "gemma")
    repo.merke_phasen_debrief(conn, 1, 2, "Zweiter Durchlauf durch Phase 2.", "gemma")
    zeilen = repo.phasen_debriefs(conn, 1)
    assert len(zeilen) == 1
    assert zeilen[0]["text"] == "Zweiter Durchlauf durch Phase 2."


def test_entfernen_blendet_aus_und_ein_neuer_lauf_bringt_es_zurueck(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Urspruenglicher Text.", "gemma")
    repo.entferne_phasen_debrief(conn, 1, 3)
    assert repo.phasen_debriefs(conn, 1) == []

    repo.merke_phasen_debrief(conn, 1, 3, "Neuer Text nach erneutem Verlassen.", "gemma")
    zeilen = repo.phasen_debriefs(conn, 1)
    assert len(zeilen) == 1
    assert zeilen[0]["geloescht"] == 0
    assert zeilen[0]["text"] == "Neuer Text nach erneutem Verlassen."


def test_phasen_debriefs_sortiert_nach_phase(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Phase drei", "gemma")
    repo.merke_phasen_debrief(conn, 1, 1, "Phase eins", "gemma")
    repo.merke_phasen_debrief(conn, 1, 2, "Phase zwei", "gemma")
    assert [z["phase"] for z in repo.phasen_debriefs(conn, 1)] == [1, 2, 3]


def test_nachrichten_zwischen_schliesst_transkript_echo_aus_und_liefert_beide_seiten(conn):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "vorher", "2026-09-05T09:00:00")
    repo.merke_nachricht(conn, 1, 2, "Ada", 0, "text", "im Fenster", "2026-09-05T10:00:00")
    repo.merke_nachricht(conn, 1, 3, "Bot", 1, "text", "Antwort im Fenster", "2026-09-05T10:05:00")
    repo.merke_nachricht(
        conn, 1, 4, "Ada", 0, repo.TYP_TRANSKRIPT, "ein Transkript-Echo",
        "2026-09-05T10:06:00",
    )
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "nachher", "2026-09-05T12:00:00")

    zeilen = repo.nachrichten_zwischen(
        conn, 1, "2026-09-05T09:30:00", "2026-09-05T11:00:00"
    )

    assert [z["message_id"] for z in zeilen] == [2, 3]
    assert [z["text"] for z in zeilen] == ["im Fenster", "Antwort im Fenster"]


def test_nachrichten_zwischen_ist_chronologisch_nach_message_id(conn):
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "fuenf", "2026-09-05T10:00:05")
    repo.merke_nachricht(conn, 1, 3, "Bot", 1, "text", "drei", "2026-09-05T10:00:03")
    repo.merke_nachricht(conn, 1, 4, "Ada", 0, "text", "vier", "2026-09-05T10:00:04")

    zeilen = repo.nachrichten_zwischen(
        conn, 1, "2026-09-05T09:00:00", "2026-09-05T11:00:00"
    )

    assert [z["message_id"] for z in zeilen] == [3, 4, 5]


def test_erste_nachricht_am_liefert_das_fruehste_datum(conn):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "zuerst", "2026-09-05T09:00:00")
    repo.merke_nachricht(conn, 1, 2, "Bo", 0, "text", "danach", "2026-09-05T10:00:00")
    assert repo.erste_nachricht_am(conn, 1) == "2026-09-05T09:00:00"


def test_erste_nachricht_am_ist_none_fuer_eine_leere_gruppe(conn):
    assert repo.erste_nachricht_am(conn, 2) is None


# === Teil 2: die Pipeline (interview_theater/phasen_debrief.py) ============


class SchemaKLM:
    """Attrappe fuer das souveraene Modell (``klm.schema``)."""

    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, temperature=None):
        self.aufrufe += 1
        return self.antwort


def _nachricht(conn, message_id: int, text: str, ist_bot: int = 0,
               typ: str = "text", absender: str = "Gruppe") -> None:
    repo.merke_nachricht(conn, 1, message_id, absender, ist_bot, typ, text, repo._jetzt())


@pytest.fixture
def einst(tmp_path):
    from interview_theater import einstellungen

    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
        erkenner_modell="gemma",
    )


# --- Umschalter und Schwelle ------------------------------------------------


@pytest.mark.parametrize("wert", ["0", "aus", "off", "AUS", "Off"])
def test_starte_liefert_none_wenn_abgeschaltet(conn, einst, monkeypatch, wert):
    monkeypatch.setenv("IT_PHASEN_DEBRIEF", wert)
    aufgerufen = []
    monkeypatch.setattr(phasen_debrief, "_lauf", lambda *a, **k: aufgerufen.append(a))
    ergebnis = phasen_debrief.starte(conn, SchemaKLM({"antwort": "x"}), einst, 1, 2)
    assert ergebnis is None
    assert aufgerufen == []


def test_starte_liefert_none_ohne_klm(conn, einst, monkeypatch):
    monkeypatch.delenv("IT_PHASEN_DEBRIEF", raising=False)
    assert phasen_debrief.starte(conn, None, einst, 1, 2) is None


def test_starte_unter_schwelle_liefert_none(conn, einst, monkeypatch):
    monkeypatch.delenv("IT_PHASEN_DEBRIEF", raising=False)
    monkeypatch.setenv("IT_DEBRIEF_MIN_NACHRICHTEN", "3")
    _nachricht(conn, 1, "Erste Nachricht der Gruppe.")
    _nachricht(conn, 2, "Zweite Nachricht der Gruppe.")
    monkeypatch.setattr(phasen_debrief, "_lauf", lambda *a, **k: pytest.fail("haette nicht laufen duerfen"))
    ergebnis = phasen_debrief.starte(conn, SchemaKLM({"antwort": "x"}), einst, 1, 1)
    assert ergebnis is None


def test_starte_ab_schwelle_liefert_thread(conn, einst, monkeypatch):
    monkeypatch.delenv("IT_PHASEN_DEBRIEF", raising=False)
    monkeypatch.setenv("IT_DEBRIEF_MIN_NACHRICHTEN", "2")
    _nachricht(conn, 1, "Erste Nachricht der Gruppe.")
    _nachricht(conn, 2, "Zweite Nachricht der Gruppe.")
    aufgerufen = []
    monkeypatch.setattr(phasen_debrief, "_lauf", lambda *a, **k: aufgerufen.append(a))
    thread = phasen_debrief.starte(conn, SchemaKLM({"antwort": "x"}), einst, 1, 1)
    assert thread is not None
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert len(aufgerufen) == 1


def test_mindest_nachrichten_vorgabe_ist_sechs(monkeypatch):
    monkeypatch.delenv("IT_DEBRIEF_MIN_NACHRICHTEN", raising=False)
    assert phasen_debrief._mindest_nachrichten() == 6


def test_mindest_nachrichten_ignoriert_kaputten_wert(monkeypatch):
    monkeypatch.setenv("IT_DEBRIEF_MIN_NACHRICHTEN", "nicht-numerisch")
    assert phasen_debrief._mindest_nachrichten() == 6


# --- phasen.setze dispatcht mit der VORHERIGEN Phase ------------------------


def test_setze_dispatcht_mit_vorheriger_phase_nicht_der_neuen(conn, monkeypatch):
    calls = []
    monkeypatch.setattr(phasen_debrief, "starte", lambda *a: calls.append(a))
    repo.setze_phase(conn, 1, 2)
    geaendert = phasen.setze(conn, 1, 4, "befehl", klm=object(), e=object())
    assert geaendert is True
    assert len(calls) == 1
    _, _, _, chat_id, vorherige_phase = calls[0]
    assert chat_id == 1
    assert vorherige_phase == 2  # die verlassene Phase, NICHT die neue (4)


def test_setze_ohne_aenderung_dispatcht_nicht(conn, monkeypatch):
    calls = []
    monkeypatch.setattr(phasen_debrief, "starte", lambda *a: calls.append(a))
    repo.setze_phase(conn, 1, 3)
    geaendert = phasen.setze(conn, 1, 3, "befehl")
    assert geaendert is False
    assert calls == []


def test_setze_ohne_klm_dispatcht_trotzdem_aber_starte_no_opt(conn, monkeypatch):
    """Ohne klm/e (Vorgabewert None) wird ``starte`` weiterhin aufgerufen --
    es ist ``starte`` selbst, das dann sofort None liefert (kein Fehler)."""
    calls = []
    monkeypatch.setattr(phasen_debrief, "starte", lambda *a: calls.append(a))
    repo.setze_phase(conn, 1, 1)
    phasen.setze(conn, 1, 2, "befehl")
    assert len(calls) == 1
    assert calls[0][1] is None and calls[0][2] is None  # klm, e


def test_setze_ohne_vorherige_phase_dispatcht_nicht(conn, monkeypatch):
    """Die allererste Phase einer Gruppe hat nichts, das sie verlaesst --
    ``vorherige`` ist None, und dafuer gibt es keinen Debrief."""
    calls = []
    monkeypatch.setattr(phasen_debrief, "starte", lambda *a: calls.append(a))
    assert repo.hole_phase(conn, 1) is None
    phasen.setze(conn, 1, 1, "befehl", klm=object(), e=object())
    assert calls == []


# --- Eingabe schliesst Transkript-Echos aus ---------------------------------


def test_korpus_und_nachrichtentext_schliessen_transkript_aus(conn):
    von = repo._jetzt()
    _nachricht(conn, 1, "Ein normaler Beitrag der Gruppe.")
    _nachricht(conn, 2, "GEHEIMER INTERVIEWINHALT", typ=repo.TYP_TRANSKRIPT)
    bis = repo._jetzt()
    zeilen = repo.nachrichten_zwischen(conn, 1, von, bis)
    korpus = phasen_debrief._korpus(zeilen)
    text = phasen_debrief._nachrichtentext(zeilen)
    assert "GEHEIMER" not in korpus
    assert "GEHEIMER" not in text
    assert "normaler Beitrag" in korpus
    assert "normaler Beitrag" in text


# --- Modellwahl --------------------------------------------------------------


def test_phase_unter_vier_nutzt_immer_das_souveraene_modell(conn, einst):
    von = repo._jetzt()
    _nachricht(conn, 1, "Wir wollen ein trauriges Ende.")
    bis = repo._jetzt()
    zeilen = repo.nachrichten_zwischen(conn, 1, von, bis)
    klm = SchemaKLM({"antwort": 'Geschmack: mag Melancholie "Wir wollen ein trauriges Ende."'})
    phasen_debrief._lauf(conn, klm, einst, 1, 2, zeilen)
    assert klm.aufrufe == 1
    eintraege = repo.phasen_debriefs(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["modell"] == "sovereign"
    assert "trauriges Ende" in eintraege[0]["text"]


def test_phase_ab_vier_ohne_einwilligung_nutzt_souveraenes_modell(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    von = repo._jetzt()
    _nachricht(conn, 1, "Die Gruppe wollte Ruhe im Ton.")
    bis = repo._jetzt()
    zeilen = repo.nachrichten_zwischen(conn, 1, von, bis)
    klm = SchemaKLM({"antwort": 'Ton: ruhig "Die Gruppe wollte Ruhe im Ton."'})
    phasen_debrief._lauf(conn, klm, einst, 1, 4, zeilen)
    assert klm.aufrufe == 1
    eintraege = repo.phasen_debriefs(conn, 1)
    assert eintraege[0]["modell"] == "sovereign"


def test_phase_ab_vier_mit_einwilligung_nutzt_claude(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: True)
    gesehen = {}

    def fake_schema(conn_, e_, klient, chat_id, system, nutzer, schema_, art, timeout,
                     bei_teil=None, teil_feld=None):
        gesehen["aufgerufen"] = True
        return {"antwort": 'Ton: energisch "Die Gruppe stritt laut."'}

    monkeypatch.setattr(phasen_debrief.szene_claude, "schema", fake_schema)
    von = repo._jetzt()
    _nachricht(conn, 1, "Die Gruppe stritt laut.")
    bis = repo._jetzt()
    zeilen = repo.nachrichten_zwischen(conn, 1, von, bis)
    klm = SchemaKLM({"antwort": "sollte nie aufgerufen werden"})
    phasen_debrief._lauf(conn, klm, einst, 1, 4, zeilen)
    assert gesehen.get("aufgerufen") is True
    assert klm.aufrufe == 0
    eintraege = repo.phasen_debriefs(conn, 1)
    assert "stritt laut" in eintraege[0]["text"]


def test_claude_fehler_faellt_auf_souveraenes_modell_zurueck(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: True)

    def kaputte_schema(*a, **k):
        raise szene_claude.ClaudeFehler("Proxy down")

    monkeypatch.setattr(phasen_debrief.szene_claude, "schema", kaputte_schema)
    von = repo._jetzt()
    _nachricht(conn, 1, "Die Gruppe entschied sich schnell.")
    bis = repo._jetzt()
    zeilen = repo.nachrichten_zwischen(conn, 1, von, bis)
    klm = SchemaKLM({"antwort": 'Arbeitsweise: schnell "Die Gruppe entschied sich schnell."'})
    phasen_debrief._lauf(conn, klm, einst, 1, 4, zeilen)
    # Der Fallback-Pfad hat tatsaechlich geliefert -- das ist das Entscheidende,
    # nicht das (bestenfalls geschaetzte) modell-Label in der Zeile.
    assert klm.aufrufe == 1
    eintraege = repo.phasen_debriefs(conn, 1)
    assert "entschied sich schnell" in eintraege[0]["text"]


# --- Der Zitat-Filter --------------------------------------------------------


def test_gefiltert_behaelt_nur_zeilen_mit_belegtem_zitat():
    korpus = "Jemand sagte: Wir wollen ein trauriges Ende. Niemand widersprach."
    antwort = (
        'Geschmack: Melancholie "Wir wollen ein trauriges Ende."\n'
        'Ton: aufgeregt "Das hat niemand gesagt."\n'
        "Arbeitsweise: schnell entschieden, kaum diskutiert."
    )
    ergebnis = phasen_debrief._gefiltert(antwort, korpus)
    assert "trauriges Ende" in ergebnis
    assert "Das hat niemand gesagt" not in ergebnis
    assert "Arbeitsweise" not in ergebnis


def test_gefiltert_erkennt_deutsche_anfuehrungszeichen():
    korpus = "Ein Satz, den die Gruppe wirklich gesagt hat."
    antwort = 'Geschmack: ernst „Ein Satz, den die Gruppe wirklich gesagt hat.“'
    ergebnis = phasen_debrief._gefiltert(antwort, korpus)
    assert "wirklich gesagt" in ergebnis


@pytest.mark.parametrize("wert", ["NICHTS", "nichts", "Nichts.", "  nichts  "])
def test_gefiltert_nichts_ergibt_leeren_text(wert):
    assert phasen_debrief._gefiltert(wert, "ein beliebiger Korpus") == ""


def test_lauf_mit_nichts_speichert_nichts(conn, einst):
    klm = SchemaKLM({"antwort": "NICHTS"})
    phasen_debrief._lauf(conn, klm, einst, 1, 2, [])
    assert repo.phasen_debriefs(conn, 1) == []


# --- Ein zweiter Lauf ersetzt den ersten ------------------------------------


def test_erneuter_lauf_fuer_dieselbe_phase_ersetzt_den_vorherigen(conn, einst):
    von = repo._jetzt()
    _nachricht(conn, 1, "Erster Satz steht hier. Zweiter Satz auch.")
    bis = repo._jetzt()
    zeilen = repo.nachrichten_zwischen(conn, 1, von, bis)

    klm1 = SchemaKLM({"antwort": 'Geschmack: ruhig "Erster Satz steht hier."'})
    phasen_debrief._lauf(conn, klm1, einst, 1, 2, zeilen)
    eintraege = repo.phasen_debriefs(conn, 1)
    assert len(eintraege) == 1
    assert "Erster Satz" in eintraege[0]["text"]

    klm2 = SchemaKLM({"antwort": 'Geschmack: hektisch "Zweiter Satz auch."'})
    phasen_debrief._lauf(conn, klm2, einst, 1, 2, zeilen)
    eintraege2 = repo.phasen_debriefs(conn, 1)
    assert len(eintraege2) == 1
    assert "Zweiter Satz" in eintraege2[0]["text"]
    assert "Erster Satz" not in eintraege2[0]["text"]
