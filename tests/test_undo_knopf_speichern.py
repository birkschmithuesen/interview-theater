"""Rueckgaengig auch unter "Ja, speichern" (UX-Knoepfe-Karte, 02.10.2026).

Birk: "Jede Speicherquittung bekommt ein Rueckgaengig." Bis dahin trug nur
die Erkenner-"Notiert:"-Meldung einen Undo-Knopf (Karte U); ein Druck auf
"Ja, speichern" (``knoepfe.basis._speichere``) schrieb den Arbeitsstand
genauso, aber ohne jede Ruecknahme-Moeglichkeit. Dieselbe Maschine wie
Karte U -- Schnappschuss vor/nach dem Schreiben, ``erkenner_lauf`` +
``erkenner_lauf_schritt``, derselbe ``ART_UNDO``-Knopf -- keine zweite.
"""

from interview_theater import knoepfe, phasen, repo

from tests.test_knoepfe import TelegramAttrappe, _druck

RAHMEN_NEU = "Vier Freundinnen leben im Nordkiez in Dortmund."


def _drucke_speichern(conn, tg, feld="rahmen", wert=RAHMEN_NEU):
    knopf_id = repo.lege_knopf_an(
        conn, 1, knoepfe.ART_SPEICHERN, f"{feld}{knoepfe.TRENNER}{wert}",
    )
    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{knopf_id}"))


def test_ja_speichern_haengt_einen_undo_knopf_an(conn):
    tg = TelegramAttrappe()
    phasen.setze(conn, 1, 4, "befehl")

    _drucke_speichern(conn, tg)

    arten = {
        repo.hole_knopf(conn, int(daten.split(":")[1]))["art"]
        for _, _, leiste in tg.knoepfe
        for _, daten in leiste
    }
    assert knoepfe.ART_UNDO in arten


def test_undo_nach_ja_speichern_stellt_den_leeren_vorzustand_wieder_her(conn):
    tg = TelegramAttrappe()
    phasen.setze(conn, 1, 4, "befehl")

    _drucke_speichern(conn, tg)
    undo_knopf_id = next(
        int(daten.split(":")[1])
        for _, _, leiste in tg.knoepfe
        for _, daten in leiste
        if repo.hole_knopf(conn, int(daten.split(":")[1]))["art"] == knoepfe.ART_UNDO
    )

    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{undo_knopf_id}"))

    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand["rahmen"] or "").strip()


def test_undo_nach_ja_speichern_stellt_den_vorherigen_wert_wieder_her(conn):
    """Nicht nur loeschen -- der ALTE Wert kommt zurueck, wie bei Karte U."""
    tg = TelegramAttrappe()
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Alte Fassung")
    repo.setze_arbeitsstand(conn, 1, "aenderung_offen", "rahmen")

    _drucke_speichern(conn, tg, wert=RAHMEN_NEU)
    undo_knopf_id = next(
        int(daten.split(":")[1])
        for _, _, leiste in tg.knoepfe
        for _, daten in leiste
        if repo.hole_knopf(conn, int(daten.split(":")[1]))["art"] == knoepfe.ART_UNDO
    )

    knoepfe.behandle(conn, tg, None, None, _druck(f"k:{undo_knopf_id}"))

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["rahmen"] == "Alte Fassung"
    assert (stand["aenderung_offen"] or "").strip() == "rahmen"


def test_ein_zweiter_druck_auf_denselben_undo_knopf_wirkt_nicht_doppelt(conn):
    tg = TelegramAttrappe()
    phasen.setze(conn, 1, 4, "befehl")

    _drucke_speichern(conn, tg)
    undo_knopf_id = next(
        int(daten.split(":")[1])
        for _, _, leiste in tg.knoepfe
        for _, daten in leiste
        if repo.hole_knopf(conn, int(daten.split(":")[1]))["art"] == knoepfe.ART_UNDO
    )

    erstes = knoepfe.behandle(conn, tg, None, None, _druck(f"k:{undo_knopf_id}", message_id=778, query_id="q1"))
    zweites = knoepfe.behandle(conn, tg, None, None, _druck(f"k:{undo_knopf_id}", message_id=778, query_id="q2"))

    assert erstes is True and zweites is True
    assert any(knoepfe.T._TEXT_SCHON_BENUTZT in t for _, t in tg.beantwortet)
