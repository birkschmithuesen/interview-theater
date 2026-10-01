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
