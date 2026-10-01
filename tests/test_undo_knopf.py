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
