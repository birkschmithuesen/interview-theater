"""Die EINE gemeinsame Sperre fuer Vorschlagslaeufe (30.09.2026, C7).

Der gemessene Fall (docs/analyse-phase5-chaos-2026-09-06.md Abschnitt 2, Ende):
13:53:42 lief die Schaerfung an, 13:54:10 wurde der Szenenfolge-Lauf fertig,
13:54:20 kam die naechste Schaerfung, 13:54:37 die Szenenspeicherung -- zwei
unabhaengige Fragestraenge im selben Chatfenster. ``schaerfung.starte`` hatte
gar keine Sperre, ``szenenfolge`` eine eigene.

Dieses Modul ist absichtlich abhaengigkeitsfrei: keine Datenbank, kein
Telegram, kein Modell. Damit laesst sich das Verhalten hier pruefen und in
``test_vorschlagskollision.py`` nur noch die Verdrahtung.
"""

import threading

from interview_theater import vorschlagssperre


def test_nimm_gibt_die_sperre_genau_einmal():
    vorschlagssperre.vergiss(1)
    assert vorschlagssperre.nimm(1) is True
    assert vorschlagssperre.nimm(1) is False
    assert vorschlagssperre.laeuft(1) is True
    vorschlagssperre.gib_frei(1)
    assert vorschlagssperre.laeuft(1) is False
    assert vorschlagssperre.nimm(1) is True
    vorschlagssperre.gib_frei(1)


def test_zwei_gruppen_stoeren_sich_nicht():
    """Eine Sperre je chat_id, nicht eine globale -- vier Bots teilen einen
    Prozessraum in den Tests."""
    vorschlagssperre.vergiss(1)
    vorschlagssperre.vergiss(2)
    assert vorschlagssperre.nimm(1) is True
    assert vorschlagssperre.nimm(2) is True
    vorschlagssperre.gib_frei(1)
    vorschlagssperre.gib_frei(2)


def test_gemerkter_auftrag_laeuft_bei_der_freigabe_genau_einmal():
    """Nichts geht verloren: der zweite Auftrag wartet und laeuft danach."""
    vorschlagssperre.vergiss(1)
    gelaufen = []
    assert vorschlagssperre.nimm(1) is True
    assert vorschlagssperre.merke(1, "schaerfung", lambda: gelaufen.append("s"))
    assert vorschlagssperre.gemerkte_arten(1) == ["schaerfung"]
    assert gelaufen == []
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["s"]
    assert vorschlagssperre.gemerkte_arten(1) == []
    # Eine zweite Freigabe holt ihn nicht noch einmal hervor.
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["s"]


def test_ein_platz_je_art_der_zweite_gleiche_auftrag_ersetzt_den_ersten():
    """Ein Platz je (chat_id, art): zwei Schaerfungslaeufe hintereinander
    nachzuholen waere zweimal dasselbe Geld fuer dasselbe Ergebnis."""
    vorschlagssperre.vergiss(1)
    gelaufen = []
    vorschlagssperre.nimm(1)
    vorschlagssperre.merke(1, "schaerfung", lambda: gelaufen.append("erst"))
    vorschlagssperre.merke(1, "schaerfung", lambda: gelaufen.append("dann"))
    vorschlagssperre.merke(1, "szenenfolge", lambda: gelaufen.append("folge"))
    assert sorted(vorschlagssperre.gemerkte_arten(1)) == ["schaerfung", "szenenfolge"]
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["dann", "folge"]


def test_ein_gescheiterter_gemerkter_auftrag_reisst_die_anderen_nicht_mit():
    vorschlagssperre.vergiss(1)
    gelaufen = []

    def kaputt():
        raise RuntimeError("Absicht")

    vorschlagssperre.nimm(1)
    vorschlagssperre.merke(1, "a", kaputt)
    vorschlagssperre.merke(1, "b", lambda: gelaufen.append("b"))
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["b"]
    assert vorschlagssperre.laeuft(1) is False


def test_die_sperre_ist_bei_der_freigabe_schon_frei():
    """Der gemerkte Auftrag nimmt sie selbst wieder -- also muss sie frei
    sein, bevor er laeuft. Sonst waere jeder nachgeholte Auftrag ein
    'gleich, ich denke noch nach'."""
    vorschlagssperre.vergiss(1)
    gesehen = []
    vorschlagssperre.nimm(1)
    vorschlagssperre.merke(
        1, "a", lambda: gesehen.append(vorschlagssperre.laeuft(1))
    )
    vorschlagssperre.gib_frei(1)
    assert gesehen == [False]


def test_sperre_fuer_liefert_immer_dasselbe_objekt():
    """Bestehende Tests warten ueber ``acquire(timeout=10)`` auf das Ende
    eines Laufs (tests/test_szenenfolge.py:169) -- dafuer muss es dasselbe
    Lock-Objekt sein wie das, das der Lauf haelt."""
    vorschlagssperre.vergiss(7)
    eine = vorschlagssperre.sperre_fuer(7)
    assert isinstance(eine, threading.Lock().__class__)
    assert vorschlagssperre.sperre_fuer(7) is eine


def test_freigabe_ohne_sperre_ist_kein_fehler():
    """Ein Thread, der nie genommen hat, darf beim Aufraeumen freigeben --
    dieselbe Haltung wie in ``szenenfolge._lauf`` (finally in JEDEM Fall)."""
    vorschlagssperre.vergiss(99)
    vorschlagssperre.gib_frei(99)
    assert vorschlagssperre.laeuft(99) is False


# --- nimm_oder_merke (30.09.2026, Race-Fund) --------------------------------
#
# ``nimm`` gefolgt von einer langsamen Aktion (Telegram-Sendung) und erst
# danach ``merke`` hatte ein Fenster: endete der laufende Lauf genau
# dazwischen, leerte ``gib_frei`` einen noch leeren Merkplatz, und der spaeter
# gemerkte Auftrag ging verloren. ``nimm_oder_merke`` schliesst das Fenster,
# weil Versuch und Merken denselben ``_schutz`` nehmen wie ``gib_frei``.


def test_nimm_oder_merke_liefert_true_wenn_die_sperre_frei_ist():
    vorschlagssperre.vergiss(1)
    assert vorschlagssperre.nimm_oder_merke(1, "schaerfung", lambda: None) is True
    assert vorschlagssperre.laeuft(1) is True
    # Kein Auftrag auf dem Merkplatz -- die Sperre wurde genommen, nicht
    # gemerkt.
    assert vorschlagssperre.gemerkte_arten(1) == []
    vorschlagssperre.gib_frei(1)


def test_nimm_oder_merke_merkt_den_auftrag_wenn_die_sperre_besetzt_ist():
    vorschlagssperre.vergiss(1)
    gelaufen = []
    assert vorschlagssperre.nimm(1) is True

    ergebnis = vorschlagssperre.nimm_oder_merke(
        1, "schaerfung", lambda: gelaufen.append("s")
    )

    assert ergebnis is False
    assert vorschlagssperre.gemerkte_arten(1) == ["schaerfung"]
    assert gelaufen == []
    vorschlagssperre.gib_frei(1)


def test_nimm_oder_merke_laeuft_nach_der_freigabe_genau_einmal():
    vorschlagssperre.vergiss(1)
    gelaufen = []
    vorschlagssperre.nimm(1)
    vorschlagssperre.nimm_oder_merke(1, "schaerfung", lambda: gelaufen.append("s"))

    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["s"]
    # Eine zweite Freigabe holt ihn nicht noch einmal hervor.
    vorschlagssperre.gib_frei(1)
    assert gelaufen == ["s"]
