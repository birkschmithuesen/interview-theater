"""Die Arbeitsphasen als gespeicherter Zustand (interview_theater/phasen.py).

Drei Dinge werden hier geprueft, und alle drei sind Entscheidungen, keine
Implementierungsdetails: dass ``nummer_fuer`` tolerant genug ist, um zu
verstehen, was eine Gruppe im Chat sagt -- auch bei einem Kurznamen aus zwei
Sachen ("Kernthema & Figuren"); dass die Voraussetzungen ausschliesslich aus
der Materiallage folgen, ohne Modell und niemals rueckwaerts; und dass daraus
ein **Angebot** wird und nie ein Wechsel.

Der automatische Sprung (``sprung_nach``, ``ART_ERMOEGLICHT``) ist am
05.09.2026 ersatzlos gestrichen worden -- die Tests dazu sind mit ihm
gegangen. An seiner Stelle steht ``test_kein_weg_vom_datenstand_zur_phase``:
kein Datenstand schaltet mehr irgendetwas.
"""

import pytest

from interview_theater import db, phasen, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def _szene(conn, nummer, volltext):
    repo.lege_szene_an(conn, 1, nummer, f"Szene {nummer}", "eine Zeile", volltext)


def _zwei_figuren(conn):
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_figur(conn, 1, "Elif", "Nachbarin")


def _setting_und_figuren(conn):
    """Der Stand nach Phase 4 (Umbau 05.09.2026 nachts): Setting gesetzt,
    Figurenliste fixiert -- beides frei erfunden, ohne Material."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    _zwei_figuren(conn)
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T20:00:00")


def _geschichte_und_szenen(conn):
    """Der Stand nach Phase 5: Bogen, Ende und mindestens eine Szene."""
    repo.setze_arbeitsstand(
        conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen",
    )
    _szene(conn, 1, None)


# --- die Liste selbst -----------------------------------------------------


def test_acht_phasen_mit_nummer_kurzname_und_satz():
    assert [nummer for nummer, _, _ in phasen.PHASEN] == [1, 2, 3, 4, 5, 6, 7, 8]
    for nummer, name, satz in phasen.PHASEN:
        assert name.strip() and satz.strip(), nummer


def test_die_korrigierte_reihenfolge_der_kurznamen():
    """Das Modell vom 05.09.2026 nachts -- **erst erfinden, dann schaerfen**:
    Setting und Figuren denkt die Gruppe sich aus (4), dann die Geschichte
    (5), und erst danach kommt das Material dazu (6). Szenentexte und
    Durchlauf schliessen an."""
    assert [name for _, name, _ in phasen.PHASEN] == [
        "Begriffe", "Fragen", "Interviews", "Setting & Figuren",
        "Geschichte", "Schaerfung", "Szenentexte", "Durchlauf",
    ]


def test_bezeichnung_ist_ueberall_dieselbe_schreibweise():
    assert phasen.bezeichnung(4) == "4 · Setting & Figuren"


def test_jede_phase_hat_stichwoerter():
    """``nummer_fuer`` faellt ohne sie auf einen Teilstringvergleich gegen den
    Kurznamen zurueck -- und der trifft bei 'Kernthema & Figuren' keinen der
    Saetze, mit denen eine Gruppe die Phase benennt."""
    for nummer, _, _ in phasen.PHASEN:
        assert phasen.STICHWOERTER.get(nummer), nummer


# --- nummer_fuer: was die Gruppe sagt -------------------------------------


@pytest.mark.parametrize(
    "gesagt, erwartet",
    [
        ("5", 5),
        (5, 5),
        ("8", 8),
        ("Begriffe", 1),
        ("Fragen", 2),
        ("fragen", 2),
        ("Interviews", 3),
        ("interview", 3),                  # Singular trifft 'Interviews'
        ("Setting & Figuren", 4),          # der Kurzname genau
        ("Kernthema", 4),                  # Altlast: so hiess die Station
        ("kernthema", 4),
        ("figuren", 4),                    # dieselbe Phase, anderes Wort
        ("figur", 4),
        ("Rahmen", 4),                     # das Setting IST der Rahmen
        ("Format", 4),                     # Altlast
        ("Hauptkonflikt", 4),              # Altlast: so hiess die Phase bis 05.09.
        ("konflikt", 4),                   # Teilstring in die andere Richtung
        ("Geschichte", 5),
        ("Schaerfung", 6),
        ("Szenentexte", 7),
        ("szenen", 7),
        ("Durchlauf.", 8),                 # Satzzeichen stoert nicht
        ("wir sind noch beim Kernthema", 4),      # Stichwort im Satz
        ("lasst uns jetzt Figuren machen", 4),    # dasselbe Ziel, anderes Wort
        ("jetzt der Hauptkonflikt", 4),
    ],
)
def test_nummer_fuer_versteht_nummer_name_und_stichwort(gesagt, erwartet):
    assert phasen.nummer_fuer(gesagt) == erwartet


def test_setting_und_figuren_sind_dieselbe_phase():
    """Wer 'Setting' sagt, wer 'Rahmen' sagt und wer 'Figuren' sagt, meint
    dieselbe Station -- dort wird beides erfunden."""
    assert phasen.nummer_fuer("Setting") == phasen.nummer_fuer("Figuren") == 4
    assert phasen.nummer_fuer("Rahmen") == 4


def test_stichwort_schlaegt_einen_treffer_im_erklaerenden_satz():
    """'interview' steht auch im Satz von Phase 2 ('Interviewfragen
    entwickeln'). Erst wenn kein Stichwort passt, wird in den Saetzen gesucht
    -- sonst landete die Gruppe beim Formulieren statt beim Aufnehmen."""
    assert phasen.nummer_fuer("interview") == 3
    assert phasen.nummer_fuer("verdichten") == 3  # nur im Satz, nirgends im Namen


@pytest.mark.parametrize("gesagt", ["", "   ", "0", "9", "42", "Kaffeepause", None])
def test_nummer_fuer_raet_nicht(gesagt):
    """Was sich keiner Phase zuordnen laesst, ist None -- der Aufrufer
    aendert dann nichts. Eine falsch gesetzte Phase kostet mehr als eine
    nicht gesetzte. Eine Zahl ueber LETZTE wird abgewiesen, nicht auf 8
    gebogen."""
    assert phasen.nummer_fuer(gesagt) is None


# --- aktuelle -------------------------------------------------------------


def test_ohne_gespeicherte_phase_gilt_die_erste(conn):
    assert repo.hole_phase(conn, 1) is None
    assert phasen.aktuelle(conn, 1) == 1


def test_setze_schreibt_phase_und_journalzeile(conn):
    assert phasen.setze(conn, 1, 5, "erkenner") is True

    assert repo.hole_phase(conn, 1) == 5
    eintrag = repo.journal(conn, 1)[-1]
    assert eintrag["art"] == "entschieden"
    assert eintrag["text"] == "Phase 5 · Geschichte"
    assert eintrag["quelle"] == "erkenner"


def test_setze_auf_denselben_wert_ist_keine_aenderung(conn):
    phasen.setze(conn, 1, 5, "erkenner")

    assert phasen.setze(conn, 1, 5, "befehl") is False
    assert len(repo.journal(conn, 1)) == 1


def test_ruecksprung_ist_erlaubt(conn):
    phasen.setze(conn, 1, 7, "erkenner")

    assert phasen.setze(conn, 1, 4, "erkenner") is True
    assert repo.hole_phase(conn, 1) == 4


# --- voraussetzungen: jede Stufe einzeln ----------------------------------


def test_ohne_material_gibt_es_keine_naechste_phase(conn):
    assert phasen.moegliche_naechste(conn, 1) == []
    assert phasen.naechste_moegliche(conn, 1) is None


def test_begriffe_erlauben_zwei(conn):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    assert phasen.moegliche_naechste(conn, 1) == [2]


def test_fragen_erlauben_drei(conn):
    """Erst die Frageliste macht die Interviews moeglich."""
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    assert phasen.moegliche_naechste(conn, 1) == [3]


def test_eine_verdichtung_erlaubt_vier(conn):
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "hallo", repo._jetzt())
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", "/tmp/a.ogg", 60)
    repo.speichere_verdichtung(conn, 1, aufnahme_id, "Maria erzaehlt", [])
    assert phasen.moegliche_naechste(conn, 1) == [4]


def _beendetes_interview(conn, transkript="ein Satz mit genug Material"):
    """Ein beendetes Interview mit Transkript und ohne Verdichtung."""
    from interview_theater import aufnahme

    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    kopf_id = aufnahme.stelle_interview_sicher(conn, 1)
    repo.setze_transkript(conn, kopf_id, transkript)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interviewmodus(conn, 1, None)
    return kopf_id


def test_vier_bleibt_gesperrt_solange_ein_interview_unausgewertet_ist(conn):
    """Die Phase-4-Sperre (05.09.2026): ins Kernthema geht es mit dem GANZEN
    Material -- eine Verdichtung reicht nicht, wenn daneben ein beendetes
    Interview ohne Auswertung liegt."""
    from interview_theater import aufnahme

    erstes = _beendetes_interview(conn)
    repo.speichere_verdichtung(conn, 1, erstes, "Maria erzaehlt", [])
    assert phasen.voraussetzungen(conn, 1)[4] is True

    zweites = _beendetes_interview(conn)
    assert aufnahme.unausgewertete_interviews(conn, 1)
    assert phasen.voraussetzungen(conn, 1)[4] is False

    repo.speichere_verdichtung(conn, 1, zweites, "Pal erzaehlt", [])
    assert aufnahme.unausgewertete_interviews(conn, 1) == []
    assert phasen.voraussetzungen(conn, 1)[4] is True


def test_ein_interview_ohne_transkript_sperrt_nicht(conn):
    """Sonst saesse eine Gruppe fest: ein Interview ohne eine einzige
    Sprachnachricht kann nie verdichtet werden."""
    from interview_theater import aufnahme

    kopf = _beendetes_interview(conn)
    repo.speichere_verdichtung(conn, 1, kopf, "Maria erzaehlt", [])
    _beendetes_interview(conn, transkript="")

    assert aufnahme.unausgewertete_interviews(conn, 1) == []
    assert phasen.voraussetzungen(conn, 1)[4] is True


def test_ein_laufendes_interview_sperrt_nicht(conn):
    """Ein laufendes Interview ist eine laufende Aufnahme, keine offene
    Auswertung."""
    from interview_theater import aufnahme

    kopf = _beendetes_interview(conn)
    repo.speichere_verdichtung(conn, 1, kopf, "Maria erzaehlt", [])
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    aufnahme.stelle_interview_sicher(conn, 1)

    assert aufnahme.unausgewertete_interviews(conn, 1) == []
    assert phasen.voraussetzungen(conn, 1)[4] is True


def test_fuenf_braucht_setting_und_eine_fixierte_figurenliste(conn):
    """Seit dem Umbau vom 05.09.2026 nachts: das **Setting** (rahmen) und
    eine ABGENOMMENE Figurenliste. Auch bei nur einer Figur: ein Monolog ist
    ein Stueck, und eine Schwelle von zwei sperrte genau diese Gruppe aus."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    assert phasen.voraussetzungen(conn, 1)[5] is False

    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    assert phasen.voraussetzungen(conn, 1)[5] is False, "noch nicht fixiert"

    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T20:00:00")
    assert phasen.voraussetzungen(conn, 1)[5] is True, "eine Figur genuegt"


def test_fixierte_liste_ohne_setting_erlaubt_fuenf_nicht(conn):
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T20:00:00")
    assert phasen.voraussetzungen(conn, 1)[5] is False


def test_figuren_ohne_setting_erlauben_fuenf_nicht(conn):
    _zwei_figuren(conn)
    assert phasen.voraussetzungen(conn, 1)[5] is False


def test_geschichte_und_eine_szene_erlauben_sechs_und_sieben(conn):
    """Die Schaerfung (6) und die Szenentexte (7) haengen an derselben Lage:
    es gibt eine Geschichte und mindestens eine Szene. Die Schaerfung ist ein
    Angebot, keine Pflicht -- deshalb sperrt sie 7 nicht."""
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.")
    assert phasen.voraussetzungen(conn, 1)[6] is False, "ohne Szene nicht"

    _szene(conn, 1, None)
    assert phasen.voraussetzungen(conn, 1)[6] is True
    assert phasen.voraussetzungen(conn, 1)[7] is True


def test_szenen_ohne_geschichte_erlauben_sechs_nicht(conn):
    """Geschaerft wird an einer Geschichte. Ohne sie gibt es nichts, woran
    das Material andocken koennte."""
    _szene(conn, 1, None)
    assert phasen.voraussetzungen(conn, 1)[6] is False


def test_erst_ein_szenentext_erlaubt_acht(conn):
    _szene(conn, 1, None)
    assert 8 not in phasen.moegliche_naechste(conn, 1)

    repo.aktualisiere_szene(
        conn, repo.hole_szenen(conn, 1)[0]["id"], "Szene 1", "eine Zeile", "MARIA: Hier."
    )
    assert 8 in phasen.moegliche_naechste(conn, 1)


def test_eine_zweite_szene_ohne_text_haelt_acht_nicht_zurueck(conn):
    """Der Durchlauf beginnt, sobald der erste Text steht -- nicht erst, wenn
    jede Szene ausgeschrieben ist. Eine Gruppe, die eine Szene bewusst
    improvisiert laesst, kaeme sonst nie in die letzte Phase."""
    _szene(conn, 1, "MARIA: Hier.")
    _szene(conn, 2, None)
    assert 8 in phasen.moegliche_naechste(conn, 1)


def test_die_bedingungen_sind_nicht_kumulativ(conn):
    """Eine Gruppe, die ohne Interviews direkt Kernthema und Figuren setzt,
    darf trotzdem nach 5 -- die Reihenfolge ist eine Landkarte, kein Zwang."""
    _setting_und_figuren(conn)
    assert phasen.voraussetzungen(conn, 1)[4] is False
    assert 5 in phasen.moegliche_naechste(conn, 1)


def test_nie_rueckwaerts_und_nie_die_aktuelle(conn):
    _setting_und_figuren(conn)
    phasen.setze(conn, 1, 8, "erkenner")

    assert phasen.moegliche_naechste(conn, 1) == []


def test_erfuellte_stufe_gleich_der_aktuellen_ist_kein_vorschlag(conn):
    _setting_und_figuren(conn)
    phasen.setze(conn, 1, 5, "erkenner")

    assert phasen.moegliche_naechste(conn, 1) == []


def test_naechste_moegliche_ist_die_hoechste(conn):
    """Der Merkposten fuer ``phase_angeboten`` braucht eine Zahl, keine
    Liste -- das ist der einzige Grund, warum es beide Funktionen gibt."""
    _setting_und_figuren(conn)
    _geschichte_und_szenen(conn)
    assert phasen.moegliche_naechste(conn, 1) == [5, 6, 7]
    assert phasen.naechste_moegliche(conn, 1) == 7


def test_entfernte_figuren_zaehlen_fuer_die_materiallage_nicht(conn):
    """Weiches Loeschen wirkt auch hier: sind ALLE Figuren entfernt, faellt
    die Voraussetzung fuer Phase 5 weg, auch wenn die Liste einmal fixiert
    war (N3)."""
    _setting_und_figuren(conn)
    assert phasen.voraussetzungen(conn, 1)[5] is True

    repo.entferne_figur(conn, 1, "Elif")
    repo.entferne_figur(conn, 1, "Maria")
    assert phasen.voraussetzungen(conn, 1)[5] is False


# --- Angebot statt Sprung -------------------------------------------------


def test_kein_weg_vom_datenstand_zur_phase(conn):
    """**Die Entscheidung vom 05.09.2026 als Test.** Es gibt keine Funktion
    mehr, die aus einer Aenderung eine Phase macht: Datenstand ist nicht
    Absicht. Wer sie wieder einbaut, soll hier stolpern."""
    for verschwunden in ("sprung_nach", "ermoeglichte_phase", "ART_ERMOEGLICHT",
                         "FREIE_STELLE"):
        assert not hasattr(phasen, verschwunden), verschwunden


def test_der_datenstand_aendert_die_phase_nicht(conn):
    """Dasselbe von der anderen Seite: Setting und Figuren machen Phase 5
    moeglich -- die gespeicherte Phase bleibt trotzdem, wo sie war."""
    phasen.setze(conn, 1, 4, "befehl")
    _setting_und_figuren(conn)

    assert phasen.moegliche_naechste(conn, 1) == [5]
    assert phasen.aktuelle(conn, 1) == 4


def test_offenes_angebot_liefert_die_hoechste_stufe(conn):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer")
    assert phasen.offenes_angebot(conn, 1) == 2


def test_offenes_angebot_merkt_sich_nichts(conn):
    """Nur Lesen: sonst verschluckte die eine anbietende Stelle das Angebot
    der anderen (Gespraechs-Prompt und Verdichtungs-Nachricht)."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer")

    assert phasen.offenes_angebot(conn, 1) == 2
    assert phasen.offenes_angebot(conn, 1) == 2
    assert repo.hole_phase_angeboten(conn, 1) is None


def test_gemerktes_angebot_kommt_nicht_wieder(conn):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer")
    phasen.merke_angebot(conn, 1, 2)

    assert phasen.offenes_angebot(conn, 1) is None


def test_eine_hoehere_stufe_wird_erneut_angeboten(conn):
    """Der Merkposten haelt genau eine Stufe fest. Kommt Material dazu, das
    eine hoehere erlaubt, ist das ein neues Angebot -- kein Draengeln."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer")
    phasen.merke_angebot(conn, 1, 2)

    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    assert phasen.offenes_angebot(conn, 1) == 3


def test_ohne_moegliche_phase_gibt_es_kein_angebot(conn):
    assert phasen.offenes_angebot(conn, 1) is None
