"""Der Redo-Knopf unter einer Undo-Erledigt-Quittung, und die
Leisten-Kollisionsregel (Befund 1a + Zusatzbefund, Padua Phase-2-Ende,
04.10.2026).

Befund 1a: die Gruppe drueckte Undo versehentlich (oder wollte es sich
anders ueberlegen) -- bis hierher gab es keinen Weg zurueck. Jetzt haengt
unter der "Rueckgaengig gemacht:"-Quittung ein Redo-Knopf, der Spiegel von
``_wirkung_undo``.

Zusatzbefund (Leisten-Kollision): 35 Sekunden nach einem Fragen-Abschluss
drueckte die Gruppe auf den einsamen Undo-Knopf, obwohl direkt darunter
schon ein neues Angebot (weiche Fassungen) stand -- zwei gleich gewichtete
Leisten standen untereinander. Jede neue Leiste laesst seitdem eine einsam
stehende Undo-Quittung (genau ein offener Knopf, keine Grundleiste daneben)
verfallen, bevor sie selbst erscheint.

Kein Netz, kein Modell: Telegram ist eine Attrappe, Auftragszuege werden
aufgezeichnet statt ausgefuehrt (dieselbe Zusage wie in
tests/test_undo_fragen_abschluss.py). Erfundenes Material, keine Echtdaten.
"""

import pytest

from interview_theater import ablauf, knoepfe, phasen, repo


class TelegramAttrappe:
    """Dieselbe Schnittstelle wie ``telegram.Telegram``, soweit diese Tests
    sie brauchen -- inklusive ``aktualisiere_knoepfe``, damit die
    Leisten-Kollision beobachtbar ist statt geschluckt (Vorbild:
    ``tests/test_undo_knopf.py``)."""

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
def auftraege(monkeypatch):
    """Auftragszuege (Eroeffnung etc.) werden aufgezeichnet statt ausgefuehrt
    -- derselbe Fang wie in ``tests/test_undo_fragen_abschluss.py``, damit
    kein Modell gebraucht wird."""
    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None,
              arbeitsart=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


def _druck(daten, chat_id=1, message_id=777, query_id="q1"):
    return {
        "callback_query_id": query_id, "data": daten, "chat_id": chat_id,
        "chat_titel": "Testgruppe", "message_id": message_id,
    }


# --- Bausteine: ein Fragen-Abschluss ohne weiche Fassungen -----------------
#
# Keine der beiden Fragen hat eine weiche Fassung (kein "weich"-Block im
# Vorschlag) -- ``_schliesse_fragen_ab`` nimmt deshalb den klassischen Weg
# direkt zu ``starte_eroeffnung``, nicht ueber
# ``_biete_weiche_fassungen_an``.

VORSCHLAG = (
    "Hier sind ein paar Fragen dazu.\n\nVORSCHLAG FRAGENAUSWAHL:\n"
    "Heimat: Wann hast du dich zuletzt fremd gefuehlt?\n"
    "Streit: Wann habt ihr zuletzt richtig gestritten?"
)


def _vorschlag_zeigen(conn, tg, wert=VORSCHLAG):
    phasen.setze(conn, 1, 2, "test")
    return knoepfe.sende_mit_speicherleiste(conn, tg, 1, wert)


def _schliesse_beide_fragen_ab(conn, tg, einst):
    _vorschlag_zeigen(conn, tg)
    knoepfe.starte_durchgehen(conn, tg, 1)
    knoepfe.entscheide(conn, tg, None, einst, 1, 1, "ja")
    knoepfe.entscheide(conn, tg, None, einst, 1, 2, "ja")


def _knopf_der_letzten_leiste_mit_art(conn, tg, art):
    """``(daten, message_id)`` des Knopfes dieser Art aus der zuletzt
    gesendeten Leiste, die ihn traegt -- rueckwaerts gesucht, damit eine neue
    Quittung (z.B. die Redo-Leiste nach dem Undo) die aeltere nicht
    verdeckt."""
    for _, _, leiste, message_id in reversed(tg.knoepfe):
        for _, daten in leiste:
            knopf_id = int(daten[len(knoepfe.PRAEFIX):])
            if repo.hole_knopf(conn, knopf_id)["art"] == art:
                return daten, message_id
    raise AssertionError(f"kein Knopf der Art {art!r} in {tg.knoepfe!r}")


def _sende_leiste(conn, tg, chat_id: int, text: str, leiste) -> int:
    """Eine beliebige Testleiste ueber den oeffentlichen Sendeweg --
    mitsamt ``merke_knopf_nachricht``, wie es jeder echte Aufrufer tut."""
    message_id = knoepfe._sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [knoepfe._id_aus_daten(d) for _, d in leiste], message_id,
    )
    return message_id


# --- 1. Redo stellt den Wert wieder her ------------------------------------


def test_redo_stellt_den_wert_wieder_her(conn, tg, einst, auftraege):
    _schliesse_beide_fragen_ab(conn, tg, einst)
    gesetzt = repo.hole_arbeitsstand(conn, 1)["fragen"]
    assert gesetzt, "die Fragen stehen nach dem Abschluss"

    undo_daten, undo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_UNDO)
    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(undo_daten, message_id=undo_message, query_id="q-undo"),
    )
    assert not (repo.hole_arbeitsstand(conn, 1)["fragen"] or "").strip(), (
        "Undo hat die Fragen geleert"
    )

    redo_daten, redo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_REDO)
    ergebnis = knoepfe.behandle(
        conn, tg, None, einst,
        _druck(redo_daten, message_id=redo_message, query_id="q-redo"),
    )

    assert ergebnis is True
    assert repo.hole_arbeitsstand(conn, 1)["fragen"] == gesetzt
    assert any(t.startswith("Wiederhergestellt:") for t in tg.texte)


def test_redo_journalisiert_die_wiederherstellung(conn, tg, einst, auftraege):
    _schliesse_beide_fragen_ab(conn, tg, einst)
    undo_daten, undo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_UNDO)
    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(undo_daten, message_id=undo_message, query_id="q-undo"),
    )
    redo_daten, redo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_REDO)
    vorher = len(repo.journal(conn, 1))

    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(redo_daten, message_id=redo_message, query_id="q-redo"),
    )

    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == vorher + 1
    assert eintraege[-1]["quelle"] == "redo"


# --- 2. Redo nur einmal -----------------------------------------------------


def test_redo_wirkt_nur_einmal(conn, tg, einst, auftraege):
    _schliesse_beide_fragen_ab(conn, tg, einst)
    undo_daten, undo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_UNDO)
    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(undo_daten, message_id=undo_message, query_id="q-undo"),
    )
    redo_daten, redo_message = _knopf_der_letzten_leiste_mit_art(
        conn, tg, knoepfe.ART_REDO)

    erstes = knoepfe.behandle(
        conn, tg, None, einst,
        _druck(redo_daten, message_id=redo_message, query_id="q1"),
    )
    zweites = knoepfe.behandle(
        conn, tg, None, einst,
        _druck(redo_daten, message_id=redo_message, query_id="q2"),
    )

    assert erstes is True and zweites is True
    assert any(
        text == knoepfe.T._TEXT_SCHON_BENUTZT for _, text in tg.beantwortet
    )
    # Und der Wert steht weiterhin wiederhergestellt -- der zweite Druck hat
    # nichts noch einmal getan.
    assert (repo.hole_arbeitsstand(conn, 1)["fragen"] or "").strip()


# --- 3. Leisten-Kollision ---------------------------------------------------


def test_eine_neue_leiste_kollabiert_den_einsamen_undo_knopf(conn, tg):
    """Genau ein offener Knopf (Undo) unter der letzten Knopfnachricht:
    verfaellt, sobald eine neue Leiste kommt, und die Tastatur-Aktualisierung
    wird versucht."""
    undo_knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_UNDO, "123")
    lone = _sende_leiste(
        conn, tg, 1, "Notiert:\nKernthema: Ankommen",
        [(knoepfe.T._TEXT_UNDO_KNOPF, knoepfe._daten(undo_knopf_id))],
    )

    speichern_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_SPEICHERN, "rahmen|Bahnhof")
    _sende_leiste(
        conn, tg, 1, "Vorschlag: Bahnhof",
        [(knoepfe.T._TEXT_SPEICHERN_KNOPF, knoepfe._daten(speichern_id))],
    )

    assert repo.hole_knopf(conn, undo_knopf_id)["benutzt_am"] is not None
    assert (1, lone) in tg.entfernt


def test_zwei_offene_knoepfe_bleiben_unberuehrt(conn, tg):
    """Gegenprobe: steht die letzte Knopfnachricht mit MEHR als einem offenen
    Knopf da (eine Grundleiste), kollabiert nichts -- die Regel trifft nur
    den Fall 'genau ein offener Undo-Knopf'."""
    speichern_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_SPEICHERN, "rahmen|Bahnhof")
    anders_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_ANDERS, "rahmen|Bahnhof")
    zwei = _sende_leiste(
        conn, tg, 1, "Vorschlag: Bahnhof",
        [
            (knoepfe.T._TEXT_SPEICHERN_KNOPF, knoepfe._daten(speichern_id)),
            (knoepfe.T._TEXT_ANDERS_KNOPF, knoepfe._daten(anders_id)),
        ],
    )

    neu_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_SPEICHERN, "rahmen|Schulhof")
    _sende_leiste(
        conn, tg, 1, "Vorschlag: Schulhof",
        [(knoepfe.T._TEXT_SPEICHERN_KNOPF, knoepfe._daten(neu_id))],
    )

    assert repo.hole_knopf(conn, speichern_id)["benutzt_am"] is None
    assert repo.hole_knopf(conn, anders_id)["benutzt_am"] is None
    assert (1, zwei) not in tg.entfernt


def test_eine_leere_leiste_kollabiert_nichts(conn, tg):
    """Keine neue Leiste (z.B. eine einfache Textantwort ohne Knoepfe) soll
    die vorherige Undo-Quittung nicht anfassen -- ``_sende_knoepfe`` prueft
    nur, wenn ``leiste`` selbst nicht leer ist."""
    undo_knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_UNDO, "123")
    lone = _sende_leiste(
        conn, tg, 1, "Notiert:\nKernthema: Ankommen",
        [(knoepfe.T._TEXT_UNDO_KNOPF, knoepfe._daten(undo_knopf_id))],
    )

    knoepfe._sende_knoepfe(conn, tg, 1, "Ein Text ohne Knoepfe", [])

    assert repo.hole_knopf(conn, undo_knopf_id)["benutzt_am"] is None
    assert (1, lone) not in tg.entfernt


# --- 4. Englische Texte vollstaendig ---------------------------------------
# (gepruefte Aussage, kein eigener Test hier noetig -- siehe Testlaufbericht:
# ``pytest tests/test_sprache_texte.py`` bleibt gruen.)
