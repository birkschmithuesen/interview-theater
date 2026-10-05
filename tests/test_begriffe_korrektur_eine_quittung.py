"""Padua Phase 1: EINE Korrektur bekommt EINE Quittung (Feedbackloop P1-2,
Befund S5, Runde 1 und 2).

Gemessen im Browserlauf ``2026-10-05-handy-giulia-p12`` (sim.db): die Gruppe
korrigiert im Chat ("we never said foam - we said HOME"). Der Gespraechszug
speichert die Liste ueber den Vorschlagsblock (``basis._korrigiere_begriffe``,
erkenner_lauf 6/8, "Updated – saved ... Move on?"), DANACH laeuft der
Erkenner auf derselben Nachricht und schickt eine zweite Quittung mit
zweitem Undo:

* lauf 7: ``transkript_korrigieren`` -> "Noted: Corrected: foam -> home";
* lauf 9: ``entfernen`` "BEGRIFFE" ("noise comes off the list") -> "Noted:
  Removed: Terms" -- und das Feld ``begriffe`` war danach wirklich LEER
  (erkenner_lauf_schritt 10: nachher ``begriffe = None``); das Board fuellte
  es drei Sekunden spaeter mit seiner eigenen Top 5 wieder auf.

Die Regel jetzt: hat der Gespraechszug in diesem Zug die Begriffe schon
gespeichert, fasst der Erkenner sie nicht noch einmal an (kein
``begriffe_setzen``, kein ``entfernen`` der Begriffe). Eine
Transkriptkorrektur aus demselben Zug wird gespeichert und an den Undo der
schon gezeigten Quittung angehaengt -- keine zweite Nachricht.

Kein Netz, kein Modell. Erfundenes Material."""

import pytest

from interview_theater import erkenner, knoepfe, phasen, repo

from test_undo_knopf import LLMAttrappe, TelegramAttrappe, _druck, padua  # noqa: F401

CHAT = 1


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _daten(tg, beschriftung):
    for _, _, leiste, _ in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r} in {tg.knoepfe!r}")


def _begriffe(conn):
    return repo.hole_arbeitsstand(conn, CHAT)["begriffe"]


def _transkript(conn, aufnahme_id):
    return conn.execute(
        "SELECT transkript FROM aufnahme WHERE id = ?", (aufnahme_id,)
    ).fetchone()[0]


def _aufnahme(conn, text):
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 40, "kurz", "sprache",
                                        diskussion=True)
    repo.setze_transkript(conn, aufnahme_id, text)
    return aufnahme_id


def _zug_und_erkenner(conn, tg, einst, text, block, aenderungen, message_id=50):
    """Wie ``bot._zug_und_erkenner``: die Nachricht der Gruppe steht schon in
    ``nachricht``, dann der Gespraechszug (Vorschlagsblock), dann der
    Erkenner auf DERSELBEN Nachricht."""
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "text", text, repo._jetzt())
    knoepfe.sende_mit_speicherleiste(
        conn, tg, CHAT, f"Here it is.\n\nVORSCHLAG BEGRIFFE:\n{block}", e=einst,
    )
    nach_zug = len(tg.gesendet)
    erkenner.laufe(LLMAttrappe({"aenderungen": aenderungen}), tg, conn, einst, CHAT)
    return nach_zug


def test_entfernen_der_begriffe_im_selben_zug_loescht_nichts_und_meldet_nichts(
        conn, tg, einst, padua):  # noqa: F811
    """Runde 2, msg 98/99: "Noise comes off the list" -- der Zug speichert
    die Liste ohne noise, der Erkenner liest "BEGRIFFE entfernen"."""
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "home, border, noise, night shift")

    nach_zug = _zug_und_erkenner(
        conn, tg, einst, "noise is not a term, take it off",
        "home, border, night shift", [{"art": "entfernen", "wert": "BEGRIFFE"}],
    )

    assert _begriffe(conn) == "home, border, night shift"
    assert tg.texte[nach_zug:] == []
    assert not any("Removed" in t for t in tg.texte)
    assert phasen.aktuelle(conn, CHAT) == 1


def test_begriffe_setzen_im_selben_zug_ueberschreibt_die_liste_des_zugs_nicht(
        conn, tg, einst, padua):  # noqa: F811
    nach_zug = _zug_und_erkenner(
        conn, tg, einst, "language is out",
        "home, belonging, border", [{"art": "begriffe_setzen",
                                     "wert": "home, border, belonging"}],
    )

    assert _begriffe(conn) == "home, belonging, border"
    assert tg.texte[nach_zug:] == []


def test_transkriptkorrektur_im_selben_zug_eine_quittung_ein_undo(
        conn, tg, einst, padua):  # noqa: F811
    """Runde 1/2, msg 90/91: "Updated – saved ... Move on?" und dazu
    "Noted: Corrected: foam -> home" mit zweitem Undo. Jetzt bleibt es bei
    der ersten Nachricht; ihr Undo nimmt beides zurueck."""
    aufnahme_id = _aufnahme(conn, "I keep thinking about foam. Waiting is good.")

    nach_zug = _zug_und_erkenner(
        conn, tg, einst, "we never said foam, we said HOME",
        "home, waiting", [
            {"art": "transkript_korrigieren", "wert": "foam -> home"},
            {"art": "begriffe_setzen", "wert": "home, waiting"},
        ],
    )

    assert tg.texte[nach_zug:] == [], tg.texte[nach_zug:]
    assert _transkript(conn, aufnahme_id) == "I keep thinking about home. Waiting is good."
    assert _begriffe(conn) == "home, waiting"
    # Genau EIN Undo im ganzen Zug, unter der "Move on?"-Frage.
    undos = [b for _, _, leiste, _ in tg.knoepfe for b, _ in leiste if b == "Undo"]
    assert len(undos) == 1

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten(tg, "Undo"), message_id=900))

    assert _transkript(conn, aufnahme_id) == "I keep thinking about foam. Waiting is good."
    assert not _begriffe(conn)
    assert "foam -> home" in tg.texte[-1]


def test_ohne_vorschlagsblock_meldet_der_erkenner_wie_bisher(
        conn, tg, einst, padua):  # noqa: F811
    """Gegenprobe: speichert der Zug nichts, bleibt die Erkenner-Meldung."""
    aufnahme_id = _aufnahme(conn, "I keep thinking about foam.")
    repo.merke_nachricht(conn, CHAT, 50, "Gruppe", 0, "text", "foam is home", repo._jetzt())
    tg.sende(CHAT, "Got it.")
    vorher = len(tg.gesendet)

    erkenner.laufe(LLMAttrappe({"aenderungen": [
        {"art": "transkript_korrigieren", "wert": "foam -> home"}]}), tg, conn, einst, CHAT)

    assert _transkript(conn, aufnahme_id) == "I keep thinking about home."
    assert len(tg.gesendet) - vorher == 1
    assert "foam -> home" in tg.texte[-1]


def test_der_merker_gilt_nur_fuer_den_einen_zug(conn, tg, einst, padua):  # noqa: F811
    """Der naechste Erkennerlauf (neue Nachricht, kein Block) darf die
    Begriffe wieder setzen und fragt wie sonst "Move on?"."""
    _zug_und_erkenner(conn, tg, einst, "language is out", "home, border", [])
    # Ueber den Bot-Nachrichten der Attrappe (ab 501), wie im Betrieb.
    repo.merke_nachricht(conn, CHAT, 900, "Gruppe", 0, "text", "add night shift",
                         repo._jetzt())
    vorher = len(tg.gesendet)

    erkenner.laufe(LLMAttrappe({"aenderungen": [
        {"art": "begriffe_setzen", "wert": "home, border, night shift"}]}),
        tg, conn, einst, CHAT)

    assert _begriffe(conn) == "home, border, night shift"
    assert len(tg.gesendet) - vorher == 1
    assert tg.texte[-1].endswith("Move on?")


def test_entfernen_eines_benannten_begriffs_loescht_nicht_die_ganze_liste(
        conn, tg, einst, padua):  # noqa: F811
    """Datenfehler hinter "Removed: Terms": ``entfernen`` mit Ziel BEGRIFFE
    leerte das ganze Feld, auch wenn nur ein Begriff gemeint war ("BEGRIFFE
    noise"). Jetzt geht nur dieser Begriff."""
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "home, noise, waiting")

    ergebnis = erkenner.entferne(conn, CHAT, "BEGRIFFE noise")

    assert _begriffe(conn) == "home, waiting"
    assert ergebnis is not None


def test_entfernen_eines_unbekannten_begriffs_aendert_nichts(conn, padua):  # noqa: F811
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "home, waiting")

    assert erkenner.entferne(conn, CHAT, "BEGRIFFE noise") is None
    assert _begriffe(conn) == "home, waiting"
