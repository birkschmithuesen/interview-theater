"""Die Kurzform je Szene (Birk, Live-Workshop 07.10.2026 ~17:45: "Reduktion
auf das Wesentliche"), Padua-Profilschalter ``[skript] verdichtet``.

Geprueft wird: ``_ergaenze_szene`` haengt unter dem Schalter nichts mehr an
``was_passiert``/``kernsaetze`` (ohne Schalter wie bisher); die bereinigte
Beschreibung fuer Altbestand; ``verdichte`` speichert 3-6 Punkte und die
gewaehlten Zitate im Wortlaut der Datenbank, laeuft bei unveraenderter
Eingabe nicht doppelt und laesst bei einem Fehler alles stehen."""

import pytest

from interview_theater import repo, schaerfung, szenenkern, workshop

ZITAT_A = "Ich habe zwanzig Jahre genaeht und keiner hat gefragt."
ZITAT_B = "Am Samstag faehrt keiner, da steht die Stadt."


class LLM:
    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort
        self.fehler = fehler
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        if self.fehler is not None:
            raise self.fehler
        return self.antwort


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def _lage(conn):
    """Eine Szene mit Beschreibung, zwei zugeordneten Interviewstellen."""
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, ZITAT_A + " " + ZITAT_B)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Zusammenfassung.", [
        {"thema": "Arbeit", "beleg_zitat": ZITAT_A, "zitat_geprueft": 1},
        {"thema": "Stillstand", "beleg_zitat": ZITAT_B, "zitat_geprueft": 1},
    ])
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Naeherei am Stadtrand")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Die Naeherin")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Mira naeht allein.")
    themen = conn.execute("SELECT id FROM verdichtung_thema ORDER BY id").fetchall()
    repo.lege_schaerfung_an(conn, 1, [
        {"verdichtung_thema_id": themen[0]["id"], "szene_id": szene_id,
         "begruendung": "gibt der Naeherin ihren Grundton"},
        {"verdichtung_thema_id": themen[1]["id"], "szene_id": szene_id,
         "begruendung": "zeigt den Stillstand am Wochenende"},
    ])
    ids = [z["id"] for z in repo.schaerfungen(conn, 1, szene_id=szene_id)]
    return szene_id, ids


def test_ohne_schalter_haengt_die_uebernahme_weiter_an(conn):
    """Vorgabeprofil: das alte Verhalten, byte-gleich."""
    assert workshop.skript_verdichtet_aktiv() is False
    szene_id, ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, ids)
    zeile = repo.hole_szene(conn, szene_id)
    assert zeile["was_passiert"] == (
        "Mira naeht allein. gibt der Naeherin ihren Grundton; "
        "zeigt den Stillstand am Wochenende"
    )
    assert zeile["kernsaetze"] == f"{ZITAT_A} | {ZITAT_B}"


def test_mit_schalter_bleibt_die_beschreibung_der_gruppe(conn, padua):
    szene_id, ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, ids)
    zeile = repo.hole_szene(conn, szene_id)
    assert zeile["was_passiert"] == "Mira naeht allein."
    assert not zeile["kernsaetze"]
    # Die Stellen sind trotzdem uebernommen -- sie stehen an der Zeile.
    assert len(szenenkern.uebernommene(conn, 1, szene_id)) == 2


def test_gruppenbeschreibung_bereinigt_altbestand(conn):
    """Altbestand (vor dem Schalter angehaengt): die Begruendungskette faellt
    beim Lesen heraus, die Zitate aus den Kernsaetzen ebenso."""
    szene_id, ids = _lage(conn)
    repo.setze_szenenfeld(conn, szene_id, "kernsaetze", "Eigener Satz der Gruppe")
    schaerfung.uebernimm_stellen(conn, 1, ids)
    zeile = repo.hole_szene(conn, szene_id)
    assert "Grundton" in zeile["was_passiert"]
    assert szenenkern.gruppenbeschreibung(conn, 1, zeile) == "Mira naeht allein."
    assert szenenkern.gruppen_kernsaetze(conn, 1, zeile) == ["Eigener Satz der Gruppe"]


def test_verdichte_speichert_punkte_und_zitate_aus_der_db(conn, einst, padua):
    szene_id, ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, ids)
    klm = LLM({"kern": ["Mira naeht allein", "Niemand fragt", "x " * 200],
               "zitate": [2, 99, 2, "1"]})
    assert szenenkern.verdichte(conn, klm, einst, 1, szene_id) is True
    zeile = repo.hole_szene(conn, szene_id)
    punkte = szenenkern.kern_punkte(zeile)
    assert punkte[:2] == ["Mira naeht allein", "Niemand fragt"]
    assert len(punkte[2]) <= szenenkern.KERN_ZEICHEN + 2
    # Nummer 99 ungueltig, 2 doppelt: es bleiben 2 und 1, im DB-Wortlaut.
    assert szenenkern.kernsaetze_kurz(zeile) == [
        f'"{ZITAT_B}" (Interview 1)', f'"{ZITAT_A}" (Interview 1)',
    ]
    assert klm.aufrufe[0]["art"] == szenenkern.ART
    assert "Mira naeht allein." in klm.aufrufe[0]["nutzer"]
    assert "Grundton" in klm.aufrufe[0]["nutzer"]

    # Unveraenderte Eingabe: kein zweiter Aufruf.
    assert szenenkern.verdichte(conn, klm, einst, 1, szene_id) is True
    assert len(klm.aufrufe) == 1
    # Geaenderte Beschreibung: neuer Aufruf.
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Mira naeht und singt.")
    szenenkern.verdichte(conn, klm, einst, 1, szene_id)
    assert len(klm.aufrufe) == 2


def test_verdichte_bei_fehler_bleibt_alles_stehen(conn, einst, padua):
    szene_id, ids = _lage(conn)
    schaerfung.uebernimm_stellen(conn, 1, ids)
    assert szenenkern.verdichte(conn, LLM(fehler=RuntimeError("down")), einst, 1, szene_id) is False
    assert szenenkern.verdichte(conn, LLM({"kern": [], "zitate": [1]}), einst, 1, szene_id) is False
    zeile = repo.hole_szene(conn, szene_id)
    assert zeile["kern"] is None and zeile["kernsaetze_kurz"] is None


def test_starte_ohne_schalter_tut_nichts(conn, einst):
    szene_id, _ = _lage(conn)
    klm = LLM({"kern": ["a"], "zitate": []})
    assert szenenkern.starte(conn, klm, einst, 1) is None
    assert klm.aufrufe == []


def test_starte_mit_schalter_laeuft_im_thread(conn, einst, padua):
    szene_id, ids = _lage(conn)
    klm = LLM({"kern": ["a", "b", "c"], "zitate": []})
    thread = szenenkern.starte(conn, klm, einst, 1)
    thread.join(5)
    assert szenenkern.kern_punkte(repo.hole_szene(conn, szene_id)) == ["a", "b", "c"]


def test_done_in_der_sortierliste_stoesst_die_kurzform_an(conn, einst, padua, monkeypatch):
    """"Done" (``schliesse_schaerfungsliste``) uebernimmt die Yes-Stellen und
    stoesst danach ``szenenkern.starte`` an -- im Thread, nicht im Handler."""
    from interview_theater.knoepfe import szenen as knoepfe_szenen

    szene_id, ids = _lage(conn)
    conn.execute("UPDATE schaerfung SET entscheidung = 'ja'")
    conn.commit()
    gesehen = []
    monkeypatch.setattr(szenenkern, "starte", lambda *a, **k: gesehen.append(a[3]))
    knoepfe_szenen._letztes_done.clear()

    class TG:
        def sende(self, *a, **k):
            return 1

    knoepfe_szenen.schliesse_schaerfungsliste(conn, TG(), None, einst, 1)
    assert gesehen == [1]
    assert len(szenenkern.uebernommene(conn, 1, szene_id)) == 2
