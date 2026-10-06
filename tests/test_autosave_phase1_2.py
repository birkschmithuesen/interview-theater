"""Padua P1-2: Autosave statt Ja/Nein in Phase 1 (Begriffe) und Phase 2
(Eroeffnung) -- Abnahme-Befund t_0b702d1d.

"Ja, speichern"/"Nein, nochmal aendern" schrieben seit dem 02.10.2026
ohnehin denselben Wert (``knoepfe.basis.speicherleiste``) -- die Rueckfrage
war nur noch ein Klick ohne Entscheidung. Mit
``workshop.autosave_phase1_2_aktiv`` (nur Padua) speichert ein Vorschlag
sofort, eine 📌-Zeile ersetzt "Notiert: ...", und EIN Undo-Knopf ersetzt die
Ja/Nein-Leiste -- derselbe Mechanismus wie Phase 4
(``erkenner.lauf_fuer_knopf``), danach derselbe automatische Phasensprung
wie am "Ja, speichern"-Knopf (``uebergang_nach_speichern``).

**Ausnahme Begriffe in Phase 1** (Birk 05.10.2026, Brief "p1-bleiben"):
dort springt nichts mehr -- die Antwort traegt die Frage "Move on?" mit der
gespeicherten Liste und den Knoepfen "Ja, weiter zu den Fragen" · "Etwas
aendern" · Undo. Ausfuehrlich in ``tests/test_begriffe_korrektur_bleibt.py``.

Die begleitenden Pfade (Erkenner-Weg fuer ``begriffe_setzen``/
``fragen_setzen``, die B5-Abschlussnachricht) sind schon in
``tests/test_phasenende_eine_nachricht.py`` abgedeckt -- hier geht es um den
zweiten, bisher ungetesteten Pfad: den Vorschlagsblock-Weg
(``knoepfe.sende_mit_speicherleiste`` -> ``_sende_mit_grundleiste`` ->
``_autospeichere``), den Dortmund-Vergleich und die Leisten-Kollision.

Kein Netz, kein Modell: Telegram ist eine Attrappe, Modellaufrufe werden mit
monkeypatch abgefangen. Erfundenes Material."""

import pytest

from interview_theater import erkenner, knoepfe, phasen, repo, workshop
from interview_theater.knoepfe import stationen

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua_autosave(monkeypatch):
    """Schaltet den Schalter fuer die Tests an, die ihn brauchen. Das
    Verhalten OHNE ihn ist in ``tests/test_knoepfe_navigation.py``
    (``test_ein_wert_traegt_die_ja_nein_rueckspiegelung`` & Co.) bereits
    abgedeckt und bleibt unveraendert gruen -- diese Datei prueft nur die
    neue Seite des Schalters. Nicht ``autouse``: die beiden Tests, die den
    Schalter selbst bzw. sein Gegenteil pruefen, duerfen ihn nicht
    uebergestuelpt bekommen."""
    monkeypatch.setattr(workshop, "autosave_phase1_2_aktiv", lambda *a, **k: True)


def _alle_beschriftungen(tg) -> list[str]:
    return [b for _, _, leiste in tg.knoepfe for b, _ in leiste]


def _knopf(tg, beschriftung):
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}, gesehen: {tg.knoepfe}")


def _druecke(conn, tg, einst, beschriftung):
    return knoepfe.behandle(conn, tg, None, einst, _druck(_knopf(tg, beschriftung)))


class _ErkennerAttrappe:
    def __init__(self, aenderungen):
        self.aenderungen = aenderungen

    def schema(self, *a, **k):
        return {"aenderungen": self.aenderungen}


# --- workshop.py: der Profilschalter selbst --------------------------------


def test_autosave_phase1_2_aktiv_nur_in_padua():
    """Wie ``[laengen] aktiv``: aus in der Vorgabe und in Dortmund, an nur
    in Padua -- derselbe Dreiklang wie jeder andere Padua-Schalter
    (``tests/test_workshop.py``)."""
    assert workshop.autosave_phase1_2_aktiv(None) is False  # eingebautes Vorgabeprofil
    assert workshop.autosave_phase1_2_aktiv(workshop.lade("dortmund-2026")) is False
    assert workshop.autosave_phase1_2_aktiv(workshop.lade("padua-2026")) is True


# --- Phase 1: Begriffe, der Vorschlagsblock-Weg ----------------------------


def test_begriffe_vorschlag_speichert_sofort_ohne_ja_nein(conn, tg, padua_autosave):
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "Here is your list.\n\nVORSCHLAG BEGRIFFE:\nHeimat, Arbeit",
    )

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit"
    beschriftungen = _alle_beschriftungen(tg)
    assert "Ja, speichern" not in beschriftungen
    assert "Nein, nochmal aendern" not in beschriftungen
    # Seit 05.10.2026 mittags (Brief "p1-bleiben"): die Frage statt der
    # 📌-Zeile, in DERSELBEN Nachricht wie die Antwort.
    assert beschriftungen == ["Ja, weiter zu den Fragen", "Etwas aendern", "Rueckgaengig"]
    assert tg.knoepfe[-1][1] == (
        "Here is your list.\n\nGeaendert – gespeichert:\n\n1. Heimat\n2. Arbeit\n\nWeiter?"
    )


def test_begriffe_vorschlag_bleibt_in_phase_eins(conn, tg, padua_autosave):
    """Bis 05.10.2026 mittags sprang der Vorschlagsblock hier automatisch in
    Phase 2 (wie "Ja, speichern"). Birk: eine gespeicherte Begriffs-Korrektur
    wechselt nie die Phase -- weiter nur ueber den Knopf oder auf Wunsch."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")

    assert phasen.aktuelle(conn, 1) == 1
    assert not any(b.startswith("Weiter zu") for b in _alle_beschriftungen(tg))


def test_begriffe_undo_nimmt_den_wert_zurueck(conn, tg, einst, padua_autosave):
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit", e=einst,
    )
    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit"

    ergebnis = _druecke(conn, tg, einst, "Rueckgaengig")

    assert ergebnis is True
    assert not (repo.hole_arbeitsstand(conn, 1)["begriffe"] or "").strip()
    # Die Phase bleibt stehen (seit 05.10.2026 mittags ohnehin Phase 1).
    assert phasen.aktuelle(conn, 1) == 1


def test_begriffe_setzen_per_erkenner_bekommt_festgelegt_zeile_und_nur_undo(
    conn, tg, einst, padua_autosave,
):
    """Derselbe Mechanismus wie Phase 4
    (``test_geschichte_setzen_bekommt_die_festgelegt_zeile_und_nur_undo`` in
    ``tests/test_geschichte.py``), hier fuer den freien Chat-Weg
    (``begriffe_setzen``) -- und zwar fuer den Fall, dass kein
    Phasenangebot faellig ist (schon in Phase 2, siehe
    ``tests/test_phasenende_eine_nachricht.py`` fuer den Fall, der sehr
    wohl die Phase abschliesst)."""
    phasen.setze(conn, 1, 2, "test")
    repo.merke_nachricht(
        conn, 1, 42, "Ada", 0, "text", "unsere begriffe sind heimat und arbeit",
        repo._jetzt(),
    )
    klm = _ErkennerAttrappe([
        {"art": "begriffe_setzen", "wert": "Heimat, Arbeit"},
    ])

    erkenner.laufe(klm, tg, conn, einst, 1)

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit"
    assert "📌 Festgelegt: Begriffe — Heimat, Arbeit" in tg.knoepfe[-1][1]
    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Rueckgaengig"]


def test_begriffe_autosave_fragt_nie_nach_dem_uebergang(
    conn, tg, einst, padua_autosave, monkeypatch,
):
    """Ersetzt den Mutationstest zum Fallback-Zweig in ``_autospeichere``
    (Review t_e5b1df39, Karte t_c980f86c): Begriffe in Phase 1 erreichen
    diesen Zweig seit dem 05.10.2026 mittags gar nicht mehr (Brief
    "p1-bleiben") -- ``uebergang_nach_speichern`` darf nicht einmal gefragt
    werden, und das allgemeine "Weiter zu"-Angebot kommt auch nicht."""
    def _verboten(*a, **k):
        raise AssertionError("kein Uebergang nach einer Begriffs-Korrektur")

    monkeypatch.setattr(stationen, "uebergang_nach_speichern", _verboten)

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit", e=einst,
    )

    assert phasen.aktuelle(conn, 1) == 1
    assert not any(b.startswith("Weiter zu") for b in _alle_beschriftungen(tg))


# --- Phase 2: Eroeffnung, der Vorschlagsblock-Weg --------------------------


VORSCHLAG_EROEFFNUNG = (
    "Here is the opening.\n\nVORSCHLAG EROEFFNUNG:\n"
    "Hi, I am part of a theatre project.\n"
    "ABSCHLUSS: Thank you for your time!"
)


def _phase_zwei_mit_fragen(conn):
    phasen.setze(conn, 1, 2, "test")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Wann warst du zuletzt fremd?")


def test_eroeffnung_vorschlag_speichert_sofort_ohne_ja_nein(conn, tg, einst, padua_autosave):
    _phase_zwei_mit_fragen(conn)

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, VORSCHLAG_EROEFFNUNG, e=einst)

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["interview_eroeffnung"] == "Hi, I am part of a theatre project."
    assert stand["interview_abschluss"] == "Thank you for your time!"
    beschriftungen = _alle_beschriftungen(tg)
    assert "Ja, speichern" not in beschriftungen
    assert beschriftungen == ["Rueckgaengig"]
    # Derselbe Weg wie der bisherige Knopf (``_speichere_eroeffnung``): der
    # Leitfaden geht einmal raus.
    assert any("Euer Leitfaden fuers Interview" in t for _, t in tg.gesendet)


def test_eroeffnung_autosave_zeigt_nie_den_rohen_abschluss_marker(
    conn, tg, einst, padua_autosave,
):
    """Padua-Befund M1 (Lesung Runde 2, 05.10.2026): die Vorschau UND die
    📌-Zeile bauten bisher roh aus dem ``VORSCHLAG EROEFFNUNG:``-Wert, der
    intern den Marker 'ABSCHLUSS:' traegt -- beides landete woertlich im
    Chat (Simulationslauf 2026-10-05-handy-giulia-p12, Nachricht 119/120).
    ``vorschlag.ohne_marker`` streicht die GROSSGESCHRIEBENE Unterzeile aus
    der Vorschau, ``schreibe_eroeffnung_automatisch`` zeigt in der
    📌-Zeile den schon zerlegten Text statt des rohen Werts."""
    _phase_zwei_mit_fragen(conn)

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, VORSCHLAG_EROEFFNUNG, e=einst)

    gesendete_texte = [t for _, t in tg.gesendet]
    assert not any("ABSCHLUSS:" in t for t in gesendete_texte)
    assert any("Thank you for your time!" in t for t in gesendete_texte)


def test_eroeffnung_undo_nimmt_beide_felder_zurueck(conn, tg, einst, padua_autosave):
    _phase_zwei_mit_fragen(conn)
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, VORSCHLAG_EROEFFNUNG, e=einst)

    _druecke(conn, tg, einst, "Rueckgaengig")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand["interview_eroeffnung"] or "").strip()
    assert not (stand["interview_abschluss"] or "").strip()


def test_eroeffnung_autosave_bietet_stille_phasenfrage_wenn_sprung_ausbleibt(
    conn, tg, einst, padua_autosave, monkeypatch,
):
    """Dieselbe Luecke wie bei Begriffe (siehe
    ``test_begriffe_autosave_bietet_stille_phasenfrage_wenn_sprung_ausbleibt``),
    hier fuer den zweiten Fallback-Aufruf in
    ``knoepfe.fragen.schreibe_eroeffnung_automatisch``.

    Materiallage: ``fragen`` steht schon, ``fragen_weich`` ist auf einen
    geprueften (leeren) Stand gesetzt -- die Phase-3-Pruefung zaehlt eine
    leere Fassung als "geprueft, nichts noetig" (``phasen._feld_geprueft``).
    Der Autosave selbst schreibt Eroeffnung UND Abschluss -- damit sind nach
    diesem einen Aufruf alle vier Voraussetzungen von Phase 3 erfuellt, und
    die ungemockte ``biete_phase_proaktiv`` hat wirklich etwas anzubieten.
    ``uebergang_nach_speichern`` wird trotzdem erzwungen auf ``False``
    gesetzt, um gezielt den Zweig DANACH zu pruefen, unabhaengig davon, ob
    die echte Phasenlogik hier zufaellig denselben Weg naehme."""
    phasen.setze(conn, 1, 2, "test")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Wann warst du zuletzt fremd?")
    repo.setze_arbeitsstand(conn, 1, "fragen_weich", "")
    monkeypatch.setattr(stationen, "uebergang_nach_speichern", lambda *a, **k: False)

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, VORSCHLAG_EROEFFNUNG, e=einst)

    # (a) kein automatischer Sprung -- die Phase bleibt stehen.
    assert phasen.aktuelle(conn, 1) == 2
    # (b) die stille Phasenfrage wurde angeboten: ein "Weiter zu"-Knopf.
    assert any(b.startswith("Weiter zu") for b in _alle_beschriftungen(tg))


# --- Dortmund/Vorgabeprofil bleibt unveraendert ----------------------------


def test_ohne_padua_profil_bleibt_es_bei_ja_nein(conn, tg):
    """Ohne den ``padua_autosave``-Schalter dieser Datei (der eingebaute
    Vorgabewert, wie Dortmund ihn auch hat) zeigt derselbe Vorschlag
    weiterhin die alte Ja/Nein-Leiste -- genau das, was
    ``tests/test_knoepfe_navigation.py`` bereits ungeaendert prueft."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand and (stand["begriffe"] or "").strip())
    assert _alle_beschriftungen(tg) == ["Ja, speichern", "Nein, nochmal aendern"]


# --- Keine doppelte 📌-Zeile / kein doppelter Undo-Chip --------------------


def test_zweiter_autosave_laesst_die_erste_einsame_undo_quittung_verfallen(
    conn, tg, einst, padua_autosave,
):
    """Regressionsschutz (Abnahme-Befund t_0b702d1d): zwei Autosaves kurz
    hintereinander duerfen nicht zwei gleichzeitig bedienbare Undo-Knoepfe
    hinterlassen. Der bestehende Kollisionsschutz
    (``knoepfe.basis._kollabiere_letzten_einsamen_undo``, Padua
    Phase-2-Ende) laesst eine einsam stehende Undo-Quittung verfallen,
    sobald die naechste Leiste kommt -- hier die Eroeffnung nach einer
    Begriffe-Festlegung des Erkenners in Phase 2 (bis 05.10.2026 mittags: nach
    dem automatischen Sprung aus Phase 1, den es nicht mehr gibt)."""
    _phase_zwei_mit_fragen(conn)
    repo.merke_nachricht(
        conn, 1, 42, "Ada", 0, "text", "unsere begriffe sind heimat", repo._jetzt(),
    )
    erkenner.laufe(_ErkennerAttrappe([{"art": "begriffe_setzen", "wert": "Heimat"}]),
                   tg, conn, einst, 1)
    erste_undo_nachricht = tg.knoepfe[-1][2]
    assert [b for b, _ in erste_undo_nachricht] == ["Rueckgaengig"]
    assert tg.entfernt == []

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, VORSCHLAG_EROEFFNUNG, e=einst)

    assert len(tg.entfernt) == 1, "die erste, einsame Undo-Quittung ist verfallen"
    letzte_leiste = tg.knoepfe[-1][2]
    assert [b for b, _ in letzte_leiste] == ["Rueckgaengig"]
