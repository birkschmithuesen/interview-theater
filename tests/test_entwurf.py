"""Tests fuer die Stufe A des Phase-5-Entwurfs (Padua Phasen TEIL 1,
03.10.2026): die Geschichts-Uebersicht.

Gemessen werden hier nur die reinen Funktionen -- Nutzertextbau und
Anzeige-Zusammenbau, kein Modellaufruf und kein Thread. ``entwurf.py``
spiegelt ``schaerfung.py``s Bauart (ein Schema-Aufruf, eigener Thread,
eigene Textbau-Funktionen); die Fixture-Konventionen (``conn``, kein
Netzzugriff) sind dieselben wie in ``tests/test_schaerfung.py``.
"""

import pytest

from interview_theater import entwurf, knoepfe, phasen, repo, szene

from test_knoepfe import TelegramAttrappe, _druck
from test_kuerzung import LLMAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


def test_baue_anzeige_enthaelt_alle_abschnitte():
    ergebnis = {
        "logline": "Two sisters meet again after years apart.",
        "setting": "A station cafe, late evening.",
        "figuren_zeilen": ["Mira -- wants closeness", "Nora -- wants distance"],
        "spannungsbogen": "Neither says what they want.",
        "szenen_was_passiert": ["They arrive.", "A photo surfaces.", "A confession."],
    }

    anzeige = entwurf.baue_anzeige(ergebnis)

    assert "Logline: Two sisters meet again after years apart." in anzeige
    assert "Setting: A station cafe, late evening." in anzeige
    assert "Characters:" in anzeige
    assert "- Mira -- wants closeness" in anzeige
    assert "- Nora -- wants distance" in anzeige
    assert "Tension arc: Neither says what they want." in anzeige
    assert "Scenes:" in anzeige
    assert "1. They arrive." in anzeige
    assert "2. A photo surfaces." in anzeige
    assert "3. A confession." in anzeige


def test_baue_nutzertext_uebersicht_traegt_vorige_fassung_und_notiz(conn):
    chat_id = 1
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "A hallway, moving boxes.")
    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte", "Two neighbours drift apart.\nEnding: open"
    )
    repo.setze_figur(conn, chat_id, "Mira", "wants to be heard")
    repo.setze_arbeitsstand(conn, chat_id, "geschichte_uebersicht", "Logline: old one")

    text = entwurf.baue_nutzertext_uebersicht(conn, chat_id, notiz="make it sadder")

    assert "Setting: A hallway, moving boxes." in text
    assert "Two neighbours drift apart." in text
    assert "- Mira -- wants to be heard" in text
    assert "Logline: old one" in text
    assert "make it sadder" in text


def test_baue_nutzertext_uebersicht_traegt_die_szenenanzahl(conn):
    chat_id = 1
    repo.setze_arbeitsstand(conn, chat_id, "szenen_anzahl", "5")

    text = entwurf.baue_nutzertext_uebersicht(conn, chat_id)

    assert "Number of scenes: 5" in text


def test_baue_nutzertext_uebersicht_ist_leer_ohne_stand(conn):
    """Ohne jede Festlegung bleibt der Nutzertext leer -- kein erfundener
    Platzhaltertext, der das Modell in die Irre fuehrt."""
    assert entwurf.baue_nutzertext_uebersicht(conn, 1) == ""


def test_generiere_uebersicht_ruft_modellwahl_mit_dem_schema(conn, einst, monkeypatch):
    aufrufe = []

    def _fake_aufruf_schema(conn_, klm, e, chat_id, system, nutzer, schema, art,
                             *, ueber_claude, modell=None):
        aufrufe.append({
            "system": system, "nutzer": nutzer, "schema": schema, "art": art,
        })
        return {
            "logline": "L", "setting": "S", "figuren_zeilen": [],
            "spannungsbogen": "B", "szenen_was_passiert": ["Eins."],
        }

    monkeypatch.setattr(entwurf.modellwahl, "aufruf_schema", _fake_aufruf_schema)
    monkeypatch.setattr(entwurf.szene_claude, "ist_aktiv", lambda e, conn_, chat_id: False)

    ergebnis = entwurf.generiere_uebersicht(object(), conn, einst, 1)

    assert aufrufe[0]["art"] == entwurf.ART_UEBERSICHT
    assert aufrufe[0]["schema"] == entwurf.SCHEMA_UEBERSICHT
    assert ergebnis["logline"] == "L"


def test_starte_uebersicht_ohne_modell_liefert_none(conn, einst):
    assert entwurf.starte_uebersicht(conn, None, None, einst, 1) is None


def test_starte_uebersicht_gibt_none_wenn_die_sperre_schon_haelt(conn, einst):
    sperre = entwurf._sperre_fuer(1)
    sperre.acquire()
    try:
        assert entwurf.starte_uebersicht(conn, None, object(), einst, 1) is None
    finally:
        sperre.release()


# ---------------------------------------------------------------------------
# Stufe A im Chat: die Knoepfe "Yes, save" / "No, change it again"
# (Padua Phasen TEIL 1, Task 10) -- Zusage 1 im Moduldocstring von
# knoepfe/__init__.py (callback_data unter 64 Bytes) wird strukturell von
# tests/test_knoepfe_struktur.py geprueft, hier geht es um die Wirkung.
# ---------------------------------------------------------------------------


def test_biete_uebersicht_zeigt_genau_die_zwei_knoepfe(conn, tg):
    knoepfe.biete_uebersicht(conn, tg, 1, "Logline: Two sisters meet again.")

    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen == [knoepfe.T.TEXT_WEITER_KNOPF, knoepfe.T.TEXT_ANDERS_KNOPF]
    assert tg.knoepfe[-1][1] == "Logline: Two sisters meet again."


def test_uebersicht_passt_uebernimmt_szenenfelder_und_startet_die_erste_szene(
    conn, tg, einst,
):
    """"Yes, save" (``ART_UEBERSICHT_PASST``): die Pflichtfelder der einzigen
    geplanten Szene kommen aus der Uebersicht, und der bestehende
    ``szene.starte``-Weg schreibt sie los -- kein neuer Schreibpfad."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "A station cafe, late evening.")
    repo.setze_arbeitsstand(conn, 1, "szenen_anzahl", "1")
    repo.setze_arbeitsstand(
        conn, 1, "geschichte_uebersicht_szenen",
        "They meet again after years apart.",
    )
    repo.setze_figur(conn, 1, "Mira", "wants to be heard")
    klm = LLMAttrappe()

    knoepfe.biete_uebersicht(conn, tg, 1, "Logline: Two sisters meet again.")
    daten_passt = tg.knoepfe[-1][2][0][1]

    assert knoepfe.behandle(conn, tg, klm, einst, _druck(daten_passt)) is True

    stand = repo.hole_arbeitsstand(conn, 1)
    assert (stand["geschichte_uebersicht_fixiert_am"] or "").strip()

    zeile = repo.hole_szenen(conn, 1)[0]
    assert zeile["was_passiert"] == "They meet again after years apart."
    assert zeile["ort"] == "A station cafe, late evening."
    assert [f["name"] for f in repo.szene_figuren(conn, zeile["id"])] == ["Mira"]

    # szene.starte gibt sofort an einen eigenen Thread ab (Zusage 2) -- auf
    # sein Ende wird ueber die Sperre des Szenenlaufs gewartet, wie in
    # tests/test_kuerzung.py.
    assert szene._sperre_fuer(1).acquire(timeout=20)
    szene._sperre_fuer(1).release()
    assert klm.aufrufe, "kein Szenenlauf angestossen"


def test_uebersicht_passt_ohne_offene_szene_schreibt_keine(conn, tg, einst):
    """Keine Szenenanzahl notiert -> ``erste_offene_szene`` liefert nichts,
    und es darf trotzdem kein Fehler entstehen."""
    knoepfe.biete_uebersicht(conn, tg, 1, "Logline: X")
    daten_passt = tg.knoepfe[-1][2][0][1]

    assert knoepfe.behandle(conn, tg, object(), einst, _druck(daten_passt)) is True
    stand = repo.hole_arbeitsstand(conn, 1)
    assert (stand["geschichte_uebersicht_fixiert_am"] or "").strip()


def test_uebersicht_anders_stoesst_einen_neuen_lauf_im_thread_an(
    conn, tg, einst, monkeypatch,
):
    """"No, change it again" (``ART_UEBERSICHT_ANDERS``): kein Modellaufruf im
    Handler selbst -- ``entwurf.starte_uebersicht`` macht das im eigenen
    Thread und zeigt am Ende wieder die zwei Knoepfe."""
    aufrufe = []

    def _fake_aufruf_schema(conn_, klm, e, chat_id, system, nutzer, schema, art,
                             *, ueber_claude, modell=None):
        aufrufe.append(nutzer)
        return {
            "logline": "L", "setting": "S", "figuren_zeilen": [],
            "spannungsbogen": "B", "szenen_was_passiert": ["Eins."],
        }

    monkeypatch.setattr(entwurf.modellwahl, "aufruf_schema", _fake_aufruf_schema)
    monkeypatch.setattr(entwurf.szene_claude, "ist_aktiv", lambda e, conn_, chat_id: False)

    knoepfe.biete_uebersicht(conn, tg, 1, "Logline: old one")
    daten_anders = tg.knoepfe[-1][2][1][1]

    assert knoepfe.behandle(conn, tg, object(), einst, _druck(daten_anders)) is True

    assert entwurf._sperre_fuer(1).acquire(timeout=20)
    entwurf._sperre_fuer(1).release()
    assert aufrufe, "kein Uebersicht-Lauf angestossen"
    # Die neue Anzeige steht wieder mit denselben zwei Knoepfen im Chat.
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen == [knoepfe.T.TEXT_WEITER_KNOPF, knoepfe.T.TEXT_ANDERS_KNOPF]


# ---------------------------------------------------------------------------
# Freitext-Rueckmeldung ueber erkenner.laufe (die art ``uebersicht_aendern``,
# phasen- UND profilgebunden -- Task 5/8 legten die art und die Phasentabelle
# an, dieses Modul liefert erst jetzt einen Effekt).
# ---------------------------------------------------------------------------


def test_erkenner_startet_die_uebersicht_in_phase_5(conn, tg, einst, monkeypatch):
    from interview_theater import erkenner, phasen, workshop

    phasen.setze(conn, 1, 5, "befehl")
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    gestartet = []
    monkeypatch.setattr(
        entwurf, "starte_uebersicht",
        lambda *a, **k: gestartet.append(a) or object(),
    )
    klm = object()

    erkenner._starte_entwurf_uebersicht(
        klm, tg, conn, einst, 1,
        [{"art": "uebersicht_aendern", "wert": "make it sadder"}],
    )

    assert gestartet == [(conn, tg, klm, einst, 1, "make it sadder")]


def test_erkenner_uebersicht_aendern_ist_stiller_no_op_ohne_padua_profil(
    conn, tg, einst, monkeypatch,
):
    """Jede Gruppe, auch Dortmund, bekommt ``uebersicht_aendern`` im
    Schema-Enum angeboten (geteilter, profilunabhaengiger Code) -- ohne
    ``workshop.prosa_entwurf_aktiv()`` darf trotzdem kein bezahlter
    Modellaufruf entstehen."""
    from interview_theater import erkenner, phasen, workshop

    phasen.setze(conn, 1, 5, "befehl")
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: False)
    gestartet = []
    monkeypatch.setattr(
        entwurf, "starte_uebersicht",
        lambda *a, **k: gestartet.append(a) or object(),
    )

    erkenner._starte_entwurf_uebersicht(
        object(), tg, conn, einst, 1,
        [{"art": "uebersicht_aendern", "wert": "make it sadder"}],
    )

    assert gestartet == []


def test_erkenner_uebersicht_aendern_wirkt_nur_in_phase_5(
    conn, tg, einst, monkeypatch,
):
    """``PHASEN_SPEZIFISCHE_ARTEN`` bindet ``uebersicht_aendern`` an Phase 5
    -- ``wende_an()`` filtert das nur fuer seine eigene, lokale Kopie der
    Liste (Grundlage von ``wirkliche``), nicht fuer die ``aenderungen``, die
    ``laufe()`` an diese Funktion weiterreicht. Ohne eine eigene Pruefung
    hier wuerde eine Rueckmeldung ausserhalb Phase 5 trotzdem einen neuen,
    bezahlten Lauf anstossen."""
    from interview_theater import erkenner, phasen, workshop

    phasen.setze(conn, 1, 6, "befehl")  # nicht Phase 5
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    gestartet = []
    monkeypatch.setattr(
        entwurf, "starte_uebersicht",
        lambda *a, **k: gestartet.append(a) or object(),
    )

    erkenner._starte_entwurf_uebersicht(
        object(), tg, conn, einst, 1,
        [{"art": "uebersicht_aendern", "wert": "make it sadder"}],
    )

    assert gestartet == []


def test_erkenner_uebersicht_aendern_ist_no_op_wenn_schon_fixiert(
    conn, tg, einst, monkeypatch,
):
    """Final-Review-Fund (03.10.2026): sobald die Uebersicht fixiert ist
    (``arbeitsstand.geschichte_uebersicht_fixiert_am`` gesetzt, wie
    ``knoepfe._wirkung_uebersicht_passt`` es tut), darf ein erkannter
    ``uebersicht_aendern``-Treffer keinen neuen, bezahlten Stufe-A-Lauf mehr
    anstossen -- der Kommentar an ``erkenner.ARTEN`` hatte das lange
    behauptet, ohne dass es je geprueft wurde. Plausibler Ausloeser: eine
    generische Rueckmeldung zu einer laufenden Szene in Stufe B wird vom
    Erkenner als Uebersicht-Kritik gelesen."""
    from interview_theater import erkenner, phasen, workshop

    phasen.setze(conn, 1, 5, "befehl")
    repo.setze_arbeitsstand(conn, 1, "geschichte_uebersicht_fixiert_am", repo._jetzt())
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    gestartet = []
    monkeypatch.setattr(
        entwurf, "starte_uebersicht",
        lambda *a, **k: gestartet.append(a) or object(),
    )

    erkenner._starte_entwurf_uebersicht(
        object(), tg, conn, einst, 1,
        [{"art": "uebersicht_aendern", "wert": "the tension arc feels too flat"}],
    )

    assert gestartet == []


# ---------------------------------------------------------------------------
# Stufe B im Chat: "Yes, save" auf einem Prosa-Entwurf (Padua Phasen TEIL 1,
# Task 12) -- derselbe Knopf wie in Phase 7 (``ART_SZENE_PASST``,
# ``_wirkung_szene_passt``), hier aber mit dem neuen, auf Phase 5
# beschraenkten Zweig ``_wirkung_entwurf_szene_passt``. Die Regression fuer
# jede andere Phase (heute 7) steht in ``tests/test_szenenfolge.py``.
# ---------------------------------------------------------------------------


def _zwei_entworfene_szenen(conn, chat_id=1):
    """Zwei Szenen mit den Pflichtfeldern aus Stufe A
    (``entwurf.uebernimm_szenenfelder`` haette sie so hinterlassen), keine
    davon schon abgenommen."""
    phasen.setze(conn, chat_id, 5, "befehl")
    repo.setze_figur(conn, chat_id, "Mira", "wants to be heard")
    figur_id = repo.hole_figur(conn, chat_id, "Mira")["id"]
    szenen_ids = []
    for nummer, was in ((1, "They arrive."), (2, "A confession.")):
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        repo.setze_szenenfeld(conn, szene_id, "was_passiert", was)
        repo.setze_szene_figuren(conn, chat_id, szene_id, [figur_id])
        szenen_ids.append(szene_id)
    return szenen_ids


def test_entwurf_szene_passt_startet_naechste_szene_automatisch(
    conn, tg, einst, monkeypatch,
):
    """"Yes, save" auf Szene 1: abgenommen, und SOFORT geht Szene 2 los --
    kein Knopf, kein Warten (AGENTS.md, die eine Ausnahme vom sonst
    geltenden "Datenstand ist nicht Absicht")."""
    szene_1, _szene_2 = _zwei_entworfene_szenen(conn)
    gestartet = []
    monkeypatch.setattr(
        szene, "starte",
        lambda conn_, tg_, klm_, e_, chat_id_, auftrag: gestartet.append(
            (chat_id_, auftrag)
        ),
    )
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1")
    daten_passt = tg.knoepfe[-1][2][0][1]

    assert knoepfe.behandle(conn, tg, None, einst, _druck(daten_passt)) is True

    zeile = repo.hole_szene(conn, szene_1)
    assert (zeile["entwurf_bestaetigt_am"] or "").strip()
    assert len(gestartet) == 1
    assert gestartet[0][0] == 1
    assert "SZENE 2" in gestartet[0][1]
    # Kein Phasenwechsel, solange noch eine Szene offen ist.
    assert phasen.aktuelle(conn, 1) == 5


def test_entwurf_letzte_szene_passt_springt_automatisch_nach_phase_6(
    conn, tg, einst, monkeypatch,
):
    """"Yes, save" auf der letzten noch offenen Szene: keine weitere Szene
    mehr -> automatisch Phase 6, ohne Knopf und ohne Rueckfrage."""
    phasen.setze(conn, 1, 5, "befehl")
    repo.setze_figur(conn, 1, "Mira", "wants to be heard")
    figur_id = repo.hole_figur(conn, 1, "Mira")["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "They arrive.")
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    eingetreten = []
    # Seit Padua Phasen TEIL 2 (Task 10) steht der Rumpf in
    # ``entwurf.bestaetige_szene`` (Knopf und Erkenner teilen ihn), und der
    # ruft den Eintritt ueber das Paket ``knoepfe``.
    monkeypatch.setattr(
        knoepfe, "eintritt_in_phase",
        lambda conn_, tg_, klm_, e_, chat_id_, nummer_: eingetreten.append(nummer_),
    )
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1")
    daten_passt = tg.knoepfe[-1][2][0][1]

    assert knoepfe.behandle(conn, tg, None, einst, _druck(daten_passt)) is True

    zeile = repo.hole_szene(conn, szene_id)
    assert (zeile["entwurf_bestaetigt_am"] or "").strip()
    assert phasen.aktuelle(conn, 1) == 6
    assert eingetreten == [6]
