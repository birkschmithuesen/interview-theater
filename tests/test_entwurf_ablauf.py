"""End-to-end-Nachweis des gesamten zweistufigen Phase-5-Ablaufs (Padua
Phasen TEIL 1, Prose Draft -- Tasks 5 bis 12): Stufe A erzeugt eine
Geschichts-Uebersicht, eine Rueckmeldung PER CHAT (nicht nur ein Knopfdruck)
AENDERT den gespeicherten Stand, "Yes, save" fixiert die Uebersicht und
startet Stufe B, jede abgenommene Szene stoesst automatisch die naechste an,
und die letzte Szene loest den automatischen Sprung nach Phase 6 aus.

Das ist der Nachweis, den der urspruengliche Auftrag verlangt: ein
gezielter Test ueber die neuen Absichts-Pfade, der zeigt, dass
Chat-Rueckmeldung in Phase 5 tatsaechlich den gespeicherten Stand aendert --
nicht nur Knopfdruecke.

Kein Netzzugriff: das Sprachmodell ist eine lokale Attrappe, die beide
Schnittstellen traegt, die dieser Ablauf braucht --
``.schema()`` wie ``tests/test_schaerfung.py``s ``KLMAttrappe`` (fuer Stufe
A) und ``.prosa()`` wie ``tests/test_szene.py``s ``LLMAttrappe`` (fuer Stufe
B, die hier wegen Phase 5 <= ``szene.PHASE_PROSA`` den Prosa-Pfad nimmt).
Keine der beiden geteilten Attrappen traegt beide Methoden, deshalb lokal
hier erweitert statt eine der beiden fuer jeden anderen Test zu aendern.

Jeder Schritt laeuft ueber den echten Produktionspfad -- ``knoepfe.behandle``
fuer die Knopfdruecke, ``erkenner._starte_entwurf_uebersicht`` fuer die
Chat-Rueckmeldung --, wie in ``tests/test_entwurf.py``. Die Threads, die
``entwurf.starte_uebersicht``/``szene.starte`` dabei anstossen, werden ueber
ihre Sperre abgewartet (dieselbe Bauart wie dort: ``sperre.acquire(timeout=
...)`` dann sofort wieder freigeben), nicht mit einer monkeygepatchten
Thread-Klasse ersetzt -- das haelt den Test nah an dem, was im Betrieb
wirklich laeuft."""

from interview_theater import entwurf, erkenner, knoepfe, phasen, repo, szene, workshop

from test_knoepfe import TelegramAttrappe, _druck


class FakeKLM:
    """Traegt beide Modellschnittstellen, die dieser Ablauf braucht.

    ``.schema()`` fuer die Stufe-A-Uebersicht, in derselben Form wie
    ``tests/test_schaerfung.py::KLMAttrappe.schema`` (inklusive ``modell``,
    das ``modellwahl.aufruf_schema`` hier mitgibt). ``.prosa()`` fuer die
    Stufe-B-Szenen, in derselben Form wie ``tests/test_szene.py::LLMAttrappe.
    prosa``. Jede Antwort traegt eine fortlaufende Versionsnummer, damit der
    Test echte Aenderung von blossem Wiederholen unterscheiden kann."""

    def __init__(self):
        self.schema_aufrufe: list[dict] = []
        self.prosa_aufrufe: list[dict] = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               bei_teil=None):
        self.schema_aufrufe.append({"nutzer": nutzer, "art": art})
        n = len(self.schema_aufrufe)
        return {
            "logline": f"Logline, version {n}.",
            "setting": "A hallway, moving boxes.",
            "figuren_zeilen": ["Alex -- drifting away"],
            "spannungsbogen": f"Tension arc, version {n}.",
            "szenen_was_passiert": [
                f"Scene one happens, version {n}.",
                f"Scene two happens, version {n}.",
            ],
        }

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None,
              timeout=None, bei_teil=None):
        self.prosa_aufrufe.append({"nutzer": nutzer, "art": art})
        n = len(self.prosa_aufrufe)
        return (
            f"TITEL: Scene {n}\n\n"
            f"Prose for scene number {n}, written by the fake model."
        )


def _warte(sperre, timeout=20) -> None:
    """Wartet, bis ein im Hintergrund gestarteter Lauf
    (``entwurf.starte_uebersicht``/``szene.starte``) fertig ist: die Sperre
    erneut nehmen und sofort wieder freigeben -- dieselbe Bauart wie in
    ``tests/test_entwurf.py`` (``test_uebersicht_passt_uebernimmt_
    szenenfelder_und_startet_die_erste_szene`` u.a.)."""
    assert sperre.acquire(timeout=timeout), "Hintergrundlauf nicht rechtzeitig fertig"
    sperre.release()


def test_phase5_ueberblick_bis_automatischer_sprung_nach_6(conn, einst, monkeypatch):
    """Demonstriert end-to-end (ohne echtes Modell): Phase 5 betreten ->
    Uebersicht generiert -> Rueckmeldung per Chat AENDERT die gespeicherte
    Uebersicht -> "Yes, save" -> Szene 1 Entwurf -> "Yes, save" -> Szene 2
    Entwurf (letzte) -> "Yes, save" -> automatisch Phase 6."""
    chat_id = 1
    tg = TelegramAttrappe()
    klm = FakeKLM()

    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "A hallway, moving boxes.")
    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte",
        "Two friends drift apart.\nEnding: they don't speak again.",
    )
    repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", repo._jetzt())
    repo.setze_arbeitsstand(conn, chat_id, "szenen_anzahl", "2")
    # Beschreibung gesetzt (nicht leer): ohne sie griffe szene.sperrtext
    # ("Figur ohne Sprachprofil UND ohne Beschreibung") und kein Szenenlauf
    # faende je statt -- ein Sprachprofil ist fuer diesen Ablauf nicht noetig.
    repo.setze_figur(conn, chat_id, "Alex", "quiet, used to notice things")
    phasen.setze(conn, chat_id, 5, "befehl")
    # entwurf.py ist Padua-only (workshop.prosa_entwurf_aktiv()) -- ohne den
    # Schalter waere der Chat-Rueckmeldungspfad (Schritt 2) ein stiller No-Op,
    # wie tests/test_entwurf.py es fuer genau diesen Fall absichert.
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)

    # --- Schritt 1: Stufe A -- die Uebersicht wird generiert und gespeichert.
    thread = entwurf.starte_uebersicht(conn, tg, klm, einst, chat_id)
    assert thread is not None, "kein Uebersicht-Lauf angestossen"
    _warte(entwurf._sperre_fuer(chat_id))

    erste_fassung = repo.hole_arbeitsstand(conn, chat_id)["geschichte_uebersicht"]
    assert erste_fassung
    assert len(klm.schema_aufrufe) == 1

    # --- Schritt 2: Rueckmeldung PER CHAT (die vom Erkenner erkannte art
    # "uebersicht_aendern", kein Knopfdruck) AENDERT den gespeicherten Stand.
    erkenner._starte_entwurf_uebersicht(
        klm, tg, conn, einst, chat_id,
        [{"art": "uebersicht_aendern", "wert": "make the ending sadder"}],
    )
    _warte(entwurf._sperre_fuer(chat_id))

    zweite_fassung = repo.hole_arbeitsstand(conn, chat_id)["geschichte_uebersicht"]
    assert zweite_fassung
    assert zweite_fassung != erste_fassung, (
        "die Chat-Rueckmeldung hat den gespeicherten Stand nicht veraendert"
    )
    assert len(klm.schema_aufrufe) == 2
    assert "make the ending sadder" in klm.schema_aufrufe[1]["nutzer"]
    assert erste_fassung in klm.schema_aufrufe[1]["nutzer"], (
        "die Neugenerierung muss die vorige Fassung als Referenz mitbekommen"
    )

    # --- Schritt 3: "Yes, save" auf der (neu generierten) Uebersicht ->
    # Stufe B, Szene 1 wird als Prosa-Entwurf geschrieben.
    daten_uebersicht_passt = tg.knoepfe[-1][2][0][1]
    assert knoepfe.behandle(
        conn, tg, klm, einst, _druck(daten_uebersicht_passt)
    ) is True
    _warte(szene._sperre_fuer(chat_id))

    stand_nach_fixierung = repo.hole_arbeitsstand(conn, chat_id)
    assert (stand_nach_fixierung["geschichte_uebersicht_fixiert_am"] or "").strip()
    szene1 = next(s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == 1)
    assert (szene1["prosa"] or "").strip()
    assert not (szene1["volltext"] or "").strip(), "Phase 5 schreibt nach prosa, nicht volltext"
    assert len(klm.prosa_aufrufe) == 1
    assert phasen.aktuelle(conn, chat_id) == 5

    # --- Schritt 4: Szene 1 "Yes, save" -> Szene 2 startet automatisch (kein
    # Knopf, kein Warten -- AGENTS.md, die eine Ausnahme von "Datenstand ist
    # nicht Absicht").
    daten_szene1_passt = tg.knoepfe[-1][2][0][1]
    assert knoepfe.behandle(conn, tg, klm, einst, _druck(daten_szene1_passt)) is True
    _warte(szene._sperre_fuer(chat_id))

    szene1_neu = repo.hole_szene(conn, szene1["id"])
    assert (szene1_neu["entwurf_bestaetigt_am"] or "").strip()
    szene2 = next(s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == 2)
    assert (szene2["prosa"] or "").strip()
    assert len(klm.prosa_aufrufe) == 2
    # Die zweite Szene ist ein eigener, unterscheidbarer Text -- kein
    # wiederholter Lauf ueber dieselbe Szene.
    assert szene1_neu["prosa"] != szene2["prosa"]
    assert phasen.aktuelle(conn, chat_id) == 5  # noch nicht gesprungen

    # --- Schritt 5: Szene 2 (letzte) "Yes, save" -> automatischer Sprung
    # nach Phase 6.
    daten_szene2_passt = tg.knoepfe[-1][2][0][1]
    assert knoepfe.behandle(conn, tg, klm, einst, _druck(daten_szene2_passt)) is True

    szene2_neu = repo.hole_szene(conn, szene2["id"])
    assert (szene2_neu["entwurf_bestaetigt_am"] or "").strip()
    assert phasen.aktuelle(conn, chat_id) == 6
    assert len(klm.prosa_aufrufe) == 2, "die letzte Abnahme schreibt keine weitere Szene"
