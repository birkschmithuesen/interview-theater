"""Der Undo-Knopf unter der Notiert-Meldung (Karte U, 01.10.2026).

Birk, 30.09.: "Ein falsch gespeicherter Wert darf nicht STILL bleiben: die
Gruppe muss ihn im Moment sehen und mit EINEM Tipp zuruecknehmen koennen."

Kein Netz, kein Modell: Telegram ist eine Attrappe, das Sprachmodell liefert
vorbereitete Antworten. Erfundenes Material, keine Echtdaten.
"""

import pytest

from interview_theater import erkenner, knoepfe, phasen, repo, ruecknahme, workshop


class TelegramAttrappe:
    """Dieselbe Schnittstelle wie ``telegram.Telegram``, soweit die Karte sie
    braucht -- inklusive ``aktualisiere_knoepfe``, damit die Reduktion einer
    aelteren Leiste auf ihren Undo-Knopf beobachtbar ist statt geschluckt."""

    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.beantwortet = []
        self.entfernt = []
        self.aktualisiert = []
        self.naechste_message_id = 500

    def sende(self, chat_id, text, **_kw):
        self.naechste_message_id += 1
        self.gesendet.append((chat_id, text))
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        message_id = self.sende(chat_id, text)
        self.knoepfe.append((chat_id, text, list(knoepfe_), message_id))
        return message_id

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))

    def aktualisiere_knoepfe(self, chat_id, message_id, knoepfe_):
        self.aktualisiert.append((chat_id, message_id, list(knoepfe_)))

    @property
    def texte(self):
        return [t for _, t in self.gesendet]


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    """Das englische Profil. ``sprache.vergiss`` raeumt den Tabellen-Cache ab,
    ``workshop.vergiss`` das Profil -- beides wie in tests/fixture_sprache.py."""
    from interview_theater import sprache

    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _druck(daten, chat_id=1, message_id=777, query_id="q1"):
    return {
        "callback_query_id": query_id, "data": daten, "chat_id": chat_id,
        "chat_titel": "Testgruppe", "message_id": message_id,
    }


# --- Aufgabe 5: die Bausteine ---------------------------------------------


def test_undo_leiste_traegt_nur_die_lauf_id(conn):
    """Zusage 1: ``callback_data`` ist ``k:<id>``, der Wert steht in der
    Tabelle ``knopf``."""
    leiste = knoepfe.undo_leiste(conn, 1, 42)

    assert len(leiste) == 1
    beschriftung, daten = leiste[0]
    assert daten.startswith(knoepfe.PRAEFIX)
    assert len(daten.encode("utf-8")) < 64
    knopf_id = int(daten[len(knoepfe.PRAEFIX):])
    knopf = repo.hole_knopf(conn, knopf_id)
    assert knopf["art"] == knoepfe.ART_UNDO
    assert knopf["wert"] == "42"


def test_undo_leiste_ohne_lauf_ist_leer(conn):
    assert knoepfe.undo_leiste(conn, 1, None) == []


def test_undo_texte_dortmund_deutsch(conn):
    """Dortmund: deutsch, in der ASCII-Umschrift des Moduls. ``texte.py``
    traegt keinen einzigen Umlaut (grep -c "[aeoeue...]" → 0), deshalb
    "Rueckgaengig" und nicht "Rückgängig"."""
    assert knoepfe.T._TEXT_UNDO_KNOPF == "Rueckgaengig"
    assert knoepfe.T._TEXT_UNDO_ERLEDIGT.startswith("Rueckgaengig gemacht:")
    assert "Arbeitsstand" in knoepfe.T._TEXT_UNDO_GEAENDERT


def test_undo_knopf_traegt_in_padua_englisch(conn, padua):
    assert knoepfe.T._TEXT_UNDO_KNOPF == "Undo"
    assert knoepfe.T._TEXT_UNDO_ERLEDIGT == "Undone:\n{zeilen}"
    assert knoepfe.T._TEXT_UNDO_GEAENDERT == (
        "Changed since - please fix it in the work status"
    )


def test_undo_steht_als_letzte_zeile_unter_der_grundleiste(conn):
    """Mobil gilt: ein Hauptknopf je Bildschirm. Undo ist Nebenknopf und steht
    deshalb unten -- ``telegram.sende_mit_knoepfen`` legt eine Zeile je
    Eintrag an."""
    tg = TelegramAttrappe()
    zusatz = knoepfe.undo_leiste(conn, 1, 7)

    knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Bahnhof", "rahmen", "Bahnhof",
        zusatz=zusatz,
    )

    _, _, leiste, _ = tg.knoepfe[-1]
    assert [b for b, _ in leiste] == [
        knoepfe.T._TEXT_SPEICHERN_KNOPF,
        knoepfe.T._TEXT_ANDERS_KNOPF,
        knoepfe.T._TEXT_UNDO_KNOPF,
    ]


def test_sende_notiert_nur_undo_schreibt_die_nachricht_mit(conn):
    """Wie jede Knopfnachricht: ueber ``_sende_knoepfe``, damit sie im
    Gespraechsfenster des naechsten Zuges steht (06.09.2026, Birk 12:05)."""
    tg = TelegramAttrappe()

    message_id = knoepfe.sende_notiert_nur_undo(
        conn, tg, 1, "Notiert:\nKernthema: Ankommen", 7)

    assert [b for b, _ in tg.knoepfe[-1][2]] == [knoepfe.T._TEXT_UNDO_KNOPF]
    zeile = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = 1 AND ist_bot = 1"
    ).fetchone()
    assert zeile["text"] == "Notiert:\nKernthema: Ankommen"
    daten = tg.knoepfe[-1][2][0][1]
    knopf_id = int(daten[len(knoepfe.PRAEFIX):])
    assert repo.hole_knopf(conn, knopf_id)["message_id"] == message_id


def test_alte_leiste_behaelt_ihren_undo_knopf(conn):
    """Eine ueberholte Leisten-Nachricht verliert ihre Speicher-Knoepfe, aber
    NICHT ihr Undo: sonst verschwaende eine zweite Notiert-Meldung die
    Ruecknahme der ersten.

    Mutation, die diesen Test rot macht: ``_entferne_tastatur`` statt der
    Reduktion auf den Undo-Knopf."""
    tg = TelegramAttrappe()
    erste = knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Bahnhof", "rahmen", "Bahnhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 7),
    )[0]

    knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Schulhof", "rahmen", "Schulhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 8),
    )

    assert tg.entfernt == [], "nicht abgenommen -- reduziert"
    assert len(tg.aktualisiert) == 1, "genau eine Anfrage je Nachricht"
    chat_id, message_id, leiste = tg.aktualisiert[0]
    assert (chat_id, message_id) == (1, erste)
    assert [b for b, _ in leiste] == [knoepfe.T._TEXT_UNDO_KNOPF]


def test_die_speicher_knoepfe_der_alten_leiste_wirken_nicht_mehr(conn):
    """Sie werden verfallen gelassen, auch wenn die App die Tastatur noch
    einen Moment zeigt -- und zwar ALLE Nicht-Undo-Knoepfe der Nachricht auf
    einmal, damit der zweite und dritte ``_nimm_alte_leiste_ab``-Aufruf nichts
    mehr findet (Telegram antwortet auf eine unveraenderte Tastatur mit 400)."""
    tg = TelegramAttrappe()
    erste = knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Bahnhof", "rahmen", "Bahnhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 7),
    )[0]
    knoepfe.sende_notiert_mit_leiste(
        conn, tg, 1, "Notiert:\nSetting: Schulhof", "rahmen", "Schulhof",
        zusatz=knoepfe.undo_leiste(conn, 1, 8),
    )

    offen = repo.offene_knoepfe_der_nachricht(conn, 1, erste)
    assert [k["art"] for k in offen] == [knoepfe.ART_UNDO]


# --- Aufgabe 6: der Handler ----------------------------------------------


def _lauf_mit_kernthema(conn, alt=None, neu="Ankommen"):
    """Ein gespeicherter Lauf, der ``kernthema`` von ``alt`` auf ``neu``
    gesetzt hat -- ohne den Erkenner, damit der Handler allein geprueft wird."""
    if alt is not None:
        repo.setze_arbeitsstand(conn, 1, "kernthema", alt)
    plan = ruecknahme.plan(["kernthema_setzen"])
    vorher = repo.schnappschuss(conn, 1, plan)
    repo.setze_arbeitsstand(conn, 1, "kernthema", neu)
    nachher = repo.schnappschuss(conn, 1, plan)
    return repo.lege_erkenner_lauf_an(
        conn, 1, f"Kernthema: {neu}", ruecknahme.schritte(vorher, nachher)
    )


def _druecke_undo(conn, tg, einst, lauf_id, message_id=777, query_id="q1"):
    daten = knoepfe.undo_leiste(conn, 1, lauf_id)[0][1]
    repo.merke_knopf_nachricht(
        conn, [int(daten[len(knoepfe.PRAEFIX):])], message_id)
    repo.merke_erkenner_lauf_nachricht(conn, lauf_id, message_id)
    return knoepfe.behandle(
        conn, tg, None, einst, _druck(daten, message_id=message_id,
                                      query_id=query_id))


def test_der_handler_stellt_den_alten_wert_wieder_her(conn, tg, einst):
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")

    assert _druecke_undo(conn, tg, einst, lauf_id) is True

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"
    assert any("Rueckgaengig gemacht:" in t for t in tg.texte)
    assert any("Kernthema: Ankommen" in t for t in tg.texte)


def test_der_handler_meldet_seitdem_geaendert_und_aendert_nichts(conn, tg, einst):
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Von Hand")

    _druecke_undo(conn, tg, einst, lauf_id)

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Von Hand"
    assert knoepfe.T._TEXT_UNDO_GEAENDERT in tg.texte
    assert not any("Rueckgaengig gemacht:" in t for t in tg.texte)
    # Review-Fix Aufgabe 6: auch die GEAENDERT-Zeile wird als Bot-Zeile
    # gemerkt, damit der Gespraechs-Bot im naechsten Zug sieht, dass das
    # Undo abgelehnt wurde -- wie die Erfolgszeile (H).
    zeilen = [
        z["text"] for z in conn.execute(
            "SELECT text FROM nachricht WHERE chat_id = 1 AND ist_bot = 1")
    ]
    assert knoepfe.T._TEXT_UNDO_GEAENDERT in zeilen


def test_die_undo_zeile_wird_als_bot_zeile_mitgeschrieben(conn, tg, einst):
    """Damit das Gespraechsmodell im naechsten Zug sieht, dass zurueckgenommen
    wurde -- und nicht behauptet, der Wert stehe (H)."""
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")

    _druecke_undo(conn, tg, einst, lauf_id)

    zeilen = [
        z["text"] for z in conn.execute(
            "SELECT text FROM nachricht WHERE chat_id = 1 AND ist_bot = 1")
    ]
    assert any((t or "").startswith("Rueckgaengig gemacht:") for t in zeilen)


def test_undo_verfallen_laesst_die_grundleiste(conn, tg, einst):
    """Sonst schriebe "Ja, speichern" den gerade zurueckgenommenen Wert wieder
    -- der Wert steckt im Knopf, nicht im Text (basis.speicherleiste).

    Mutation, die diesen Test rot macht: ``repo.verfallen_lassen`` im Handler
    weglassen."""
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    speichern = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN, "kernthema|Ankommen")
    repo.merke_knopf_nachricht(conn, [speichern], 777)

    _druecke_undo(conn, tg, einst, lauf_id, message_id=777)

    assert repo.beanspruche_knopf(conn, speichern) is False, "schon verfallen"
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"


def test_die_ruecknahme_haengt_eine_journalzeile_an(conn, tg, einst):
    """Das Journal wird nur angehaengt (AGENTS.md): die Zeilen des Laufs
    bleiben stehen, die Ruecknahme kommt daneben -- mit ``quelle 'undo'``,
    damit der Weg nachvollziehbar bleibt."""
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    vorher = len(repo.journal(conn, 1))

    _druecke_undo(conn, tg, einst, lauf_id)

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == vorher + 1
    neu = eintraege[-1]
    assert neu["quelle"] == "undo"
    assert "Kernthema: Ankommen" in neu["text"]


def test_ein_unbekannter_lauf_ist_kein_absturz(conn, tg, einst):
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_UNDO, "999")
    assert knoepfe.behandle(
        conn, tg, None, einst, _druck(knoepfe._daten(knopf_id))) is True
    assert tg.beantwortet, "answerCallbackQuery kommt immer"


def test_ein_undo_aus_einer_fremden_gruppe_wirkt_nicht(conn, tg, einst):
    """Dieselbe Datenbank traegt alle Gruppen des Workshops."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    daten = knoepfe.undo_leiste(conn, 1, lauf_id)[0][1]

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, chat_id=2))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"


# --- Review-Fix Aufgabe 6 ---------------------------------------------------


def test_ein_knopf_mit_lauf_aus_fremder_gruppe_erreicht_den_handler_nicht(
    conn, tg, einst,
):
    """Anders als oben (``behandle`` faengt die fremde ``chat_id`` schon am
    Knopf selbst ab): hier gehoert der KNOPF zu Gruppe 2, aber sein ``wert``
    zeigt auf einen Lauf aus Gruppe 1 -- genau die Pruefung
    ``lauf["chat_id"] != d.chat_id`` im Handler selbst, nicht die in
    ``behandle``."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")
    knopf_id = repo.lege_knopf_an(conn, 2, knoepfe.ART_UNDO, str(lauf_id))

    knoepfe.behandle(
        conn, tg, None, einst, _druck(knoepfe._daten(knopf_id), chat_id=2),
    )

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"


def test_eine_ausnahme_beim_zuruecknehmen_bekommt_eine_antwort_und_einen_vorfall(
    conn, tg, einst, monkeypatch,
):
    """Praezedenz ``_wirkung_textbuch``: der Knopf ist schon beansprucht
    (``beanspruche_knopf``), bevor ``repo.nimm_erkenner_lauf_zurueck`` laeuft
    -- scheitert der Aufruf (z.B. 'database is locked', vier Bots und das Web
    teilen dieselbe Datei), darf die Gruppe nicht ohne Antwort dastehen und
    ein zweiter Druck darf nicht die falsche Erfolgsmeldung
    '_TEXT_SCHON_BENUTZT' liefern, waehrend der Wert unveraendert steht."""
    lauf_id = _lauf_mit_kernthema(conn, alt="Alt")

    def kaputt(*args, **kwargs):
        raise RuntimeError("database is locked (simuliert)")

    monkeypatch.setattr(repo, "nimm_erkenner_lauf_zurueck", kaputt)

    ergebnis = _druecke_undo(conn, tg, einst, lauf_id)

    assert ergebnis is True
    assert tg.beantwortet, "answerCallbackQuery kommt auch im Fehlerfall"
    assert knoepfe.T._TEXT_UNDO_FEHLER in tg.texte
    zeilen = [
        z["text"] for z in conn.execute(
            "SELECT text FROM nachricht WHERE chat_id = 1 AND ist_bot = 1")
    ]
    assert knoepfe.T._TEXT_UNDO_FEHLER in zeilen, "als Bot-Zeile gemerkt"
    vorfaelle = conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = 1 AND art = 'undo_fehlgeschlagen'"
    ).fetchall()
    assert len(vorfaelle) == 1
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen", (
        "unveraendert -- nichts wurde zurueckgenommen"
    )


# --- Aufgabe 7: der Knopf steht unter jeder Notiert-Meldung ---------------


class LLMAttrappe:
    def __init__(self, antwort):
        self._antwort = antwort

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        return self._antwort


def _nachricht(conn, text, message_id=1):
    repo.merke_nachricht(
        conn, 1, message_id, "Mert", 0, "text", text, repo._jetzt())


def _laufe(conn, tg, einst, aenderungen, text="wir haben was entschieden",
           message_id=1):
    _nachricht(conn, text, message_id)
    erkenner.laufe(
        LLMAttrappe({"aenderungen": aenderungen}), tg, conn, einst, 1)


def _undo_daten(tg):
    """Die callback_data des Undo-Knopfs unter der letzten Knopfnachricht."""
    for _, _, leiste, _ in reversed(tg.knoepfe):
        for beschriftung, daten in leiste:
            if beschriftung == knoepfe.T._TEXT_UNDO_KNOPF:
                return daten
    raise AssertionError(f"kein Undo-Knopf in {tg.knoepfe!r}")


def test_undo_steht_unter_der_notiert_meldung_ohne_grundleiste(conn, tg, einst):
    """Phase 3: keine Ping-Pong-Art offen, also keine Grundleiste -- der
    Undo-Knopf steht trotzdem da, als einzige Zeile."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    chat_id, text, leiste, _ = tg.knoepfe[-1]
    assert text.startswith("Notiert:")
    assert [b for b, _ in leiste] == [knoepfe.T._TEXT_UNDO_KNOPF]


def test_undo_steht_unter_der_grundleiste_wenn_es_eine_gibt(conn, tg, einst):
    """Phase 2, Fragen offen: die bestehende Grundleiste bleibt, Undo kommt
    als ruhiger Nebenknopf darunter (Karte U Punkt 5). Phase 4 traegt seit
    dem Padua-Brainstorming-Umbau (02.10.2026) keine Grundleiste mehr unter
    ``rahmen_setzen``/``geschichte_setzen`` -- siehe
    ``test_undo_steht_unter_der_notiert_meldung_ohne_grundleiste``, das
    heute genau diesen Fall fuer Phase 4 mitabdeckt."""
    phasen.setze(conn, 1, 2, "test")
    _laufe(conn, tg, einst, [{"art": "fragen_setzen", "wert": "Was war dein erster Job?"}])

    _, text, leiste, _ = tg.knoepfe[-1]
    assert text.startswith("Notiert:")
    assert [b for b, _ in leiste] == [
        knoepfe.T._TEXT_SPEICHERN_KNOPF,
        knoepfe.T._TEXT_ANDERS_KNOPF,
        knoepfe.T._TEXT_UNDO_KNOPF,
    ]


def test_der_meldungstext_bleibt_zeichengleich(conn, tg, einst):
    """Der Knopf kommt dazu, der Text nicht: ``baue_meldung`` ist unveraendert
    die eine Quelle."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert tg.knoepfe[-1][1] == erkenner.baue_meldung(
        [{"art": "kernthema_setzen", "wert": "Ankommen"}])


def test_kein_lauf_ohne_schritte_und_ohne_zeilen(conn, tg, einst):
    """Eine Meldung, die nur die Phase nennt, bekommt keinen Knopf: es gibt
    nichts zurueckzunehmen (``phase`` und ``gruppe`` sind nicht verfolgt).

    Mutation, die diesen Test rot macht: den Lauf auch bei leerem Diff anlegen
    -- ein Knopf ohne Wirkung."""
    phasen.setze(conn, 1, 1, "test")
    _laufe(conn, tg, einst, [{"art": "phase_setzen", "wert": "2"}])

    assert any(t.startswith("Notiert:") for t in tg.texte), "die Meldung kommt"
    assert not any(
        b == knoepfe.T._TEXT_UNDO_KNOPF
        for _, _, leiste, _ in tg.knoepfe for b, _ in leiste
    )
    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0


def test_eine_wiederholte_meldung_bekommt_keinen_lauf(conn, tg, einst):
    """``_steht_schon_da``: die Meldung geht nicht raus, also entsteht auch
    kein Knopf und kein Lauf-Datensatz."""
    phasen.setze(conn, 1, 3, "test")
    repo.merke_nachricht(
        conn, 1, 50, "Bot", 1, "text", "Notiert:\nKernthema: Ankommen",
        repo._jetzt())
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}],
           message_id=51)

    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0


def test_ein_fehlschlag_beim_anlegen_schickt_die_meldung_trotzdem(
        conn, tg, einst, monkeypatch):
    """"Der Wert ist wichtiger als seine Knoepfe" -- wie ``_sende_meldung``
    es heute schon fuer die Grundleiste haelt. Mit Vorfall fuers Dashboard."""
    phasen.setze(conn, 1, 3, "test")

    def kaputt(*_a, **_kw):
        raise RuntimeError("Datenbank zickt")

    monkeypatch.setattr(repo, "lege_erkenner_lauf_an", kaputt)
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert any(t.startswith("Notiert:") for t in tg.texte)
    arten = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")
    ]
    assert "undo_nicht_angelegt" in arten


def test_undo_zeilen_nennen_die_phase_und_die_usa_zeile_nicht(conn):
    """Nur die zurueckgenommenen Zeilen. Die Phase steht in der Meldung, aber
    nicht in "Rueckgaengig gemacht:" -- und die USA-Zeile ebenso nicht
    (offener Punkt fuer Birk)."""
    zeilen = erkenner.undo_zeilen([
        {"art": "kernthema_setzen", "wert": "Ankommen"},
        {"art": "phase_setzen", "wert": "2"},
        {"art": "szene_usa", "wert": "ja"},
    ])
    assert zeilen == ["Kernthema: Ankommen"]


def test_undo_zeilen_nennen_die_figurenanzahl_aus_einem_stillen_entschieden(conn):
    """``entschieden`` ist in der Meldung still, setzt aber nebenbei
    ``arbeitsstand.figuren_anzahl`` -- und diese Spalte ist verfolgt, also
    gehoert die Zeile in die Ruecknahme (Abweichung E.1)."""
    zeilen = erkenner.undo_zeilen([
        {"art": "entschieden", "wert": "Wir nehmen vier Figuren.",
         "figuren_anzahl": 4},
    ])
    assert zeilen == ["Anzahl Figuren: 4"]


def test_nach_undo_liest_der_erkenner_die_alte_nachricht_nicht_erneut(
        conn, tg, einst):
    """Befund H, am Code geprueft: ``erkenne`` rueckt das Wasserzeichen vor
    (``repo.setze_extrahiert_bis``), ``repo.unextrahierte`` liefert nur
    Nachrichten darueber. Die Nachricht, aus der der falsche Wert kam, kommt
    nie wieder -- der Erkenner setzt ihn also nicht von sich aus erneut.

    Und die Undo-Zeile ist als Vorlauf brauchbar: ``letzte_bot_nachricht_vor``
    schliesst nur "Notiert:"/"Noted:" aus."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}],
           text="das Kernthema ist Ankommen", message_id=1)
    lauf_id = conn.execute("SELECT id FROM erkenner_lauf").fetchone()[0]
    _druecke_undo(conn, tg, einst, lauf_id, message_id=777, query_id="q9")
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] is None

    # Der naechste Lauf sieht die alte Nachricht nicht mehr.
    offen = [z["message_id"] for z in repo.unextrahierte(conn, 1)]
    assert 1 not in offen

    vorlauf = repo.letzte_bot_nachricht_vor(conn, 1, 10_000)
    assert (vorlauf["text"] or "").startswith("Rueckgaengig gemacht:")


# --- Review-Fix Aufgabe 7 ---------------------------------------------------


def test_eine_fremde_aenderung_nach_wende_an_ist_kein_schritt_des_laufs(
        conn, tg, einst, monkeypatch):
    """Befund 1: zwischen ``wende_an`` und dem Senden laufen Telegram-Sends
    und Thread-Starts -- in diesen Sekunden schreibt z.B. ein Knopfdruck der
    Hauptschleife in den Arbeitsstand. Das ist die Entscheidung der Gruppe,
    nicht dieses Laufs: sie darf nicht als Schritt erscheinen und muss das
    Undo ueberleben.

    Mutation, die diesen Test rot macht: den Nachher-Schnappschuss wieder erst
    beim Anlegen des Laufs nehmen (nach ``_melde_interviewmodus``)."""
    phasen.setze(conn, 1, 3, "test")
    echt = erkenner._melde_interviewmodus

    def mit_fremdem_druck(tg_, conn_, e_, chat_id, wirkliche):
        repo.setze_arbeitsstand(conn_, chat_id, "begriffe", "Von der Gruppe")
        return echt(tg_, conn_, e_, chat_id, wirkliche)

    monkeypatch.setattr(erkenner, "_melde_interviewmodus", mit_fremdem_druck)
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    lauf_id = conn.execute("SELECT id FROM erkenner_lauf").fetchone()[0]
    schritte = conn.execute(
        "SELECT coalesce(vorher, '') || coalesce(nachher, '') AS t "
        "FROM erkenner_lauf_schritt WHERE lauf_id = ?", (lauf_id,)
    ).fetchall()
    assert schritte, "der Kernthema-Schritt ist da"
    assert not any("Von der Gruppe" in z["t"] for z in schritte)

    _druecke_undo(conn, tg, einst, lauf_id, message_id=778, query_id="q10")
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["kernthema"] is None
    assert stand["begriffe"] == "Von der Gruppe"


def test_ein_ausgefallener_vorher_schnappschuss_hinterlaesst_einen_vorfall(
        conn, tg, einst, monkeypatch):
    """Befund 2 (Plan G): kein Knopf, aber ein Vorfall fuers Dashboard -- und
    die Meldung geht trotzdem raus."""
    phasen.setze(conn, 1, 3, "test")

    def kaputt(*_a, **_kw):
        raise RuntimeError("Datenbank zickt")

    monkeypatch.setattr(repo, "schnappschuss", kaputt)
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert any(t.startswith("Notiert:") for t in tg.texte)
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"
    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0
    arten = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")
    ]
    assert arten.count("undo_nicht_angelegt") == 1


def test_ein_kaputter_vorfall_reisst_die_meldung_nicht_mit(
        conn, tg, einst, monkeypatch):
    """Befund 3a: scheitert das Anlegen UND der Vorfall (busy DB), geht die
    Notiert-Meldung trotzdem raus."""
    phasen.setze(conn, 1, 3, "test")

    def kaputt(*_a, **_kw):
        raise RuntimeError("database is locked (simuliert)")

    monkeypatch.setattr(repo, "lege_erkenner_lauf_an", kaputt)
    monkeypatch.setattr(repo, "merke_vorfall", kaputt)
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert any(t.startswith("Notiert:") for t in tg.texte)


def test_ein_kaputtes_merken_der_nachricht_laesst_den_rest_laufen(
        conn, tg, einst, monkeypatch):
    """Befund 3b: wirft ``merke_erkenner_lauf_nachricht`` nach dem Senden,
    laufen Bot-Zeile, Phaseneintritt und Phasenangebot trotzdem."""
    phasen.setze(conn, 1, 3, "test")
    angeboten = []

    def kaputt(*_a, **_kw):
        raise RuntimeError("database is locked (simuliert)")

    monkeypatch.setattr(repo, "merke_erkenner_lauf_nachricht", kaputt)
    monkeypatch.setattr(
        erkenner, "_biete_phase_an", lambda *a, **kw: angeboten.append(a))
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert any(t.startswith("Notiert:") for t in tg.texte)
    assert angeboten, "das Phasenangebot laeuft trotzdem"


def test_genau_eine_undo_knopfzeile_je_meldung(conn, tg, einst):
    """Befund 4: ohne Grundleiste entstand eine nie gezeigte zweite
    ART_UNDO-Zeile -- verwaist und offen."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    zeilen = conn.execute(
        "SELECT message_id FROM knopf WHERE chat_id = 1 AND art = ?",
        (knoepfe.ART_UNDO,),
    ).fetchall()
    assert len(zeilen) == 1
    assert zeilen[0]["message_id"] == tg.knoepfe[-1][3]


def test_ein_kaputter_undo_knopf_kostet_nicht_die_grundleiste(
        conn, tg, einst, monkeypatch):
    """Befund 5: ``undo_leiste`` hat ihr eigenes try -- wirft sie, bleibt die
    Grundleiste stehen."""
    phasen.setze(conn, 1, 2, "test")

    def kaputt(*_a, **_kw):
        raise RuntimeError("Datenbank zickt")

    monkeypatch.setattr(knoepfe, "undo_leiste", kaputt)
    _laufe(conn, tg, einst, [{"art": "fragen_setzen", "wert": "Was war dein erster Job?"}])

    _, text, leiste, _ = tg.knoepfe[-1]
    assert text.startswith("Notiert:")
    assert [b for b, _ in leiste] == [
        knoepfe.T._TEXT_SPEICHERN_KNOPF,
        knoepfe.T._TEXT_ANDERS_KNOPF,
    ]


# --- Aufgabe 8: die sieben Abnahmepunkte der Karte ------------------------


def _laufe_und_undo(conn, tg, einst, aenderungen, message_id=1):
    """Ein ganzer Erkennerlauf und der Druck auf seinen Undo-Knopf -- der Weg,
    den die Gruppe im Chat geht."""
    _laufe(conn, tg, einst, aenderungen, message_id=message_id)
    daten = _undo_daten(tg)
    knopf_id = int(daten[len(knoepfe.PRAEFIX):])
    message = repo.hole_knopf(conn, knopf_id)["message_id"]
    return knoepfe.behandle(
        conn, tg, None, einst,
        _druck(daten, message_id=message, query_id=f"q{knopf_id}"))


# 1. Kernthema gesetzt -> Undo -> Kernthema wie vorher (auch "leer").

def test_undo_stellt_das_kernthema_wieder_her(conn, tg, einst):
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Zusammenhalten")

    _laufe_und_undo(conn, tg, einst,
                    [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Zusammenhalten"


def test_undo_stellt_ein_leeres_feld_wieder_her(conn, tg, einst):
    """"Wie vorher" heisst auch "leer" -- der haeufigste Fall: der erste,
    falsche Wert ueberhaupt."""
    phasen.setze(conn, 1, 3, "test")

    _laufe_und_undo(conn, tg, einst,
                    [{"art": "kernthema_setzen", "wert": "Ankommen"}])

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand is None or stand["kernthema"] is None


# 2. Figur neu angelegt -> Undo -> Figur weg, keine Waisen.

def test_undo_nimmt_eine_neue_figur_weich_zurueck(conn, tg, einst):
    """Geprueft ueber den LESER (``repo.figuren``), nicht ueber rohes SQL:
    "Figur weg" heisst, dass kein Leser sie mehr sieht (N3).

    Mutation: ``entfernt_am`` nicht setzen -- die Figur bleibt in der Liste."""
    phasen.setze(conn, 1, 4, "test")

    _laufe_und_undo(conn, tg, einst,
                    [{"art": "figur_setzen", "wert": "Mira: laesst nicht locker"}])

    assert [f["name"] for f in repo.figuren(conn, 1)] == []


def test_undo_laesst_keine_waisen_in_szene_figur(conn, tg, einst):
    """Eine im selben Lauf entstandene Besetzung geht mit zurueck -- sonst
    zeigte ``szene_figur`` auf eine Figur, die es nicht mehr gibt.

    Mutation: den ``szene_figur``-Schritt ueberspringen."""
    phasen.setze(conn, 1, 4, "test")
    repo.setze_figur(conn, 1, "Pola", "still")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szene_figuren(conn, 1, szene_id, [repo.hole_figur(conn, 1, "Pola")["id"]])

    _laufe_und_undo(conn, tg, einst, [
        {"art": "figur_setzen", "wert": "Mira: laesst nichts gefallen"},
        {"art": "szene_planen", "wert": "Szene 1 | figuren: Pola, Mira"},
    ])

    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Pola"]
    assert [f["name"] for f in repo.szene_figuren(conn, szene_id)] == ["Pola"]
    # Und roh nachgezaehlt: keine Zeile zeigt auf eine entfernte Figur.
    waisen = conn.execute(
        "SELECT count(*) FROM szene_figur sf "
        "JOIN figur f ON f.id = sf.figur_id WHERE f.entfernt_am IS NOT NULL"
    ).fetchone()[0]
    assert waisen == 0


# 3. Szene geplant -> Undo -> Szene weg.

def test_undo_nimmt_eine_geplante_szene_zurueck(conn, tg, einst):
    """Mutation: ``"szene"`` aus ``ruecknahme.WEICH`` entfernen."""
    phasen.setze(conn, 1, 4, "test")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "szene_planen", "wert": "Szene 1 | ort: Bahnsteig | was_passiert: Warten"},
    ])

    assert repo.hole_szenen(conn, 1) == []


# 4. Zwei Aenderungen in einer Meldung -> ein Undo nimmt beide zurueck.

def test_ein_undo_nimmt_beide_aenderungen_der_meldung_zurueck(conn, tg, einst):
    """Eine Meldung, eine Ruecknahme -- keine Einzelauswahl.

    Mutation: in ``erkenner_lauf_schritte`` ein ``LIMIT 1`` einbauen."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "Alter Konflikt")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "hauptkonflikt_setzen", "wert": "Neuer Konflikt"},
    ])

    stand = repo.hole_arbeitsstand(conn, 1)
    assert (stand["kernthema"], stand["hauptkonflikt"]) == ("Alt", "Alter Konflikt")
    assert "Kernthema: Neu" in tg.texte[-1]
    assert "Hauptkonflikt: Neuer Konflikt" in tg.texte[-1]


# 5. Feld nach dem Lauf erneut geaendert -> Undo aendert nichts, meldet es.

def test_undo_aendert_nichts_wenn_das_feld_seitdem_anders_ist(conn, tg, einst):
    """Mutation: die Wertpruefung in ``nimm_erkenner_lauf_zurueck`` weglassen
    -- dann ueberschriebe das Undo den Wert von Hand."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Neu"}])
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Von Hand gesetzt")

    daten = _undo_daten(tg)
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Von Hand gesetzt"
    assert knoepfe.T._TEXT_UNDO_GEAENDERT in tg.texte


# 6. Doppeltipp -> einmal gewirkt.

def test_doppeltipp_wirkt_einmal(conn, tg, einst):
    """Die Sperre steht doppelt: ``beanspruche_knopf`` in ``behandle`` und das
    bedingte UPDATE auf ``erkenner_lauf``.

    Mutation: ``AND zurueckgenommen_am IS NULL`` weglassen."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Neu"}])
    daten = _undo_daten(tg)

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, query_id="q1"))
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Danach")
    knoepfe.behandle(conn, tg, None, einst, _druck(daten, query_id="q2"))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Danach"
    assert len([t for t in tg.texte if t.startswith("Rueckgaengig gemacht:")]) == 1
    assert len(tg.beantwortet) == 2, "beide Druecke bekommen eine Antwort"


# 7. Dortmund deutsch, Padua englisch -- Verhalten gleich.

def test_undo_wirkt_in_padua_genauso(conn, tg, einst, padua):
    """Dasselbe Verhalten, englische Texte. ``_laufe`` faehrt denselben
    Codepfad; nur die Beschriftung und die Zeilen sind englisch."""
    phasen.setze(conn, 1, 3, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Belonging")
    _laufe(conn, tg, einst, [{"art": "kernthema_setzen", "wert": "Arriving"}])

    beschriftungen = [b for _, _, leiste, _ in tg.knoepfe for b, _ in leiste]
    assert "Undo" in beschriftungen
    daten = next(
        d for _, _, leiste, _ in tg.knoepfe for b, d in leiste if b == "Undo")
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Belonging"
    assert any(t.startswith("Undone:") for t in tg.texte)


# --- Die Waechter daneben -------------------------------------------------


def test_phase_bleibt_nach_undo(conn, tg, einst):
    """Kein Undo fuer die Phase (Karte): sie setzt allein die Gruppe.

    Mutation: ``phase`` aus ``ruecknahme.AUSSEN["arbeitsstand"]`` entfernen."""
    phasen.setze(conn, 1, 1, "test")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "phase_setzen", "wert": "2"},
    ])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"
    assert phasen.aktuelle(conn, 1) == 2, "die Phase bleibt, wo die Gruppe sie hinstellte"


def test_usa_bleibt_nach_undo(conn, tg, einst):
    """Die US-Einwilligung ist eine Datenschutzentscheidung mit eigenen zwei
    Knoepfen -- offener Punkt fuer Birk, nicht diese Karte.

    Mutation: ``gruppe`` in ``ruecknahme.VERFOLGT`` aufnehmen."""
    phasen.setze(conn, 1, 6, "test")
    repo.merke_szene_usa_angeboten(conn, 1)
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Alt")

    _laufe_und_undo(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "szene_usa", "wert": "ja"},
    ])

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Alt"
    assert repo.szene_usa_stand(conn, 1) != "offen", "die Einwilligung steht weiter"


def test_journal_bleibt_stehen_und_bekommt_eine_zeile(conn, tg, einst):
    """Das Journal wird nur angehaengt (AGENTS.md): die Zeilen des Laufs
    bleiben, die Ruecknahme kommt daneben.

    Mutation: ``journal`` in ``VERFOLGT`` aufnehmen (dann verschwaende das Undo
    die Chronik) oder die Ruecknahme-Journalzeile weglassen."""
    phasen.setze(conn, 1, 3, "test")
    _laufe(conn, tg, einst, [
        {"art": "kernthema_setzen", "wert": "Neu"},
        {"art": "entschieden", "wert": "Wir bleiben bei vier Figuren."},
    ])
    vorher = [z["text"] for z in repo.journal(conn, 1)]
    assert any("vier Figuren" in t for t in vorher)

    daten = _undo_daten(tg)
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    nachher = [z["text"] for z in repo.journal(conn, 1)]
    assert all(t in nachher for t in vorher), "keine Zeile verschwindet"
    assert any(t.startswith("Zurueckgenommen:") for t in nachher)
