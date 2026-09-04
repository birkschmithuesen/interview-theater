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


def _kernthema_und_figuren(conn):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    _zwei_figuren(conn)


# --- die Liste selbst -----------------------------------------------------


def test_sieben_phasen_mit_nummer_kurzname_und_satz():
    assert [nummer for nummer, _, _ in phasen.PHASEN] == [1, 2, 3, 4, 5, 6, 7]
    for nummer, name, satz in phasen.PHASEN:
        assert name.strip() and satz.strip(), nummer


def test_die_korrigierte_reihenfolge_der_kurznamen():
    """Das Modell vom 05.09.2026: Begriffe kommen aus dem Plenum, Fragen sind
    eine eigene Phase, **Kernthema und Figuren sind eine**, danach **Format &
    Rahmen** (nicht mehr 'Hauptkonflikt' -- ein Konflikt ist eine
    Moeglichkeit, keine Pflicht), Szenenfolge und Szenentexte sind eine
    Phase."""
    assert [name for _, name, _ in phasen.PHASEN] == [
        "Begriffe", "Fragen", "Interviews", "Kernthema & Figuren",
        "Format & Rahmen", "Szenen", "Durchlauf",
    ]


def test_bezeichnung_ist_ueberall_dieselbe_schreibweise():
    assert phasen.bezeichnung(4) == "4 · Kernthema & Figuren"


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
        ("Begriffe", 1),
        ("Fragen", 2),
        ("fragen", 2),
        ("Interviews", 3),
        ("interview", 3),                  # Singular trifft 'Interviews'
        ("Kernthema & Figuren", 4),        # der Kurzname genau
        ("Kernthema", 4),
        ("kernthema", 4),
        ("figuren", 4),                    # dieselbe Phase, anderes Wort
        ("figur", 4),
        ("Format & Rahmen", 5),            # der Kurzname genau
        ("Format", 5),
        ("Rahmen", 5),
        ("Hauptkonflikt", 5),              # Altlast: so hiess die Phase bis 05.09.
        ("konflikt", 5),                   # Teilstring in die andere Richtung
        ("Szenen", 6),
        ("szenentexte", 6),                # Szenenfolge und Texte sind eine Phase
        ("Durchlauf.", 7),                 # Satzzeichen stoert nicht
        ("wir sind noch beim Kernthema", 4),      # Stichwort im Satz
        ("lasst uns jetzt Figuren machen", 4),    # dasselbe Ziel, anderes Wort
        ("jetzt der Hauptkonflikt", 5),
    ],
)
def test_nummer_fuer_versteht_nummer_name_und_stichwort(gesagt, erwartet):
    assert phasen.nummer_fuer(gesagt) == erwartet


def test_kernthema_und_figuren_sind_dieselbe_phase():
    """Die Entscheidung vom 05.09.2026 in einer Zeile: wer 'Kernthema' sagt
    und wer 'Figuren' sagt, meint dieselbe Station."""
    assert phasen.nummer_fuer("Kernthema") == phasen.nummer_fuer("Figuren") == 4


def test_stichwort_schlaegt_einen_treffer_im_erklaerenden_satz():
    """'interview' steht auch im Satz von Phase 2 ('Interviewfragen
    entwickeln'). Erst wenn kein Stichwort passt, wird in den Saetzen gesucht
    -- sonst landete die Gruppe beim Formulieren statt beim Aufnehmen."""
    assert phasen.nummer_fuer("interview") == 3
    assert phasen.nummer_fuer("verdichten") == 3  # nur im Satz, nirgends im Namen


@pytest.mark.parametrize("gesagt", ["", "   ", "0", "8", "42", "Kaffeepause", None])
def test_nummer_fuer_raet_nicht(gesagt):
    """Was sich keiner Phase zuordnen laesst, ist None -- der Aufrufer
    aendert dann nichts. Eine falsch gesetzte Phase kostet mehr als eine
    nicht gesetzte. '8' war einmal der Durchlauf und ist jetzt keine Phase
    mehr: eine Zahl ueber LETZTE wird abgewiesen, nicht auf 7 gebogen."""
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
    assert eintrag["text"] == "Phase 5 · Format & Rahmen"
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


def test_fuenf_braucht_kernthema_und_zwei_figuren(conn):
    """Ein Konflikt braucht zwei Wollen: ohne zwei Figuren gibt es nichts,
    wogegen etwas stehen koennte."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    assert phasen.voraussetzungen(conn, 1)[5] is False

    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    assert phasen.voraussetzungen(conn, 1)[5] is False

    repo.setze_figur(conn, 1, "Elif", "Nachbarin")
    assert phasen.voraussetzungen(conn, 1)[5] is True


def test_figuren_ohne_kernthema_erlauben_fuenf_nicht(conn):
    _zwei_figuren(conn)
    assert phasen.voraussetzungen(conn, 1)[5] is False


def test_format_erlaubt_sechs(conn):
    """Seit dem 05.09.2026 haengt Phase 6 am **Format**, nicht mehr am
    Hauptkonflikt: ein Konflikt ist eine Moeglichkeit, keine Pflicht -- ohne
    Format weiss dagegen niemand, ob die naechste Szene ein Dialog oder ein
    Rap wird."""
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")
    assert phasen.voraussetzungen(conn, 1)[6] is False

    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    assert phasen.voraussetzungen(conn, 1)[6] is True


def test_rahmen_allein_erlaubt_sechs_nicht(conn):
    """``rahmen`` darf leer bleiben und traegt deshalb keine Voraussetzung."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    assert phasen.voraussetzungen(conn, 1)[6] is False


def test_erst_ein_szenentext_erlaubt_sieben(conn):
    _szene(conn, 1, None)
    assert 7 not in phasen.moegliche_naechste(conn, 1)

    repo.aktualisiere_szene(
        conn, repo.hole_szenen(conn, 1)[0]["id"], "Szene 1", "eine Zeile", "MARIA: Hier."
    )
    assert 7 in phasen.moegliche_naechste(conn, 1)


def test_eine_zweite_szene_ohne_text_haelt_sieben_nicht_zurueck(conn):
    """Der Durchlauf beginnt, sobald der erste Text steht -- nicht erst, wenn
    jede Szene ausgeschrieben ist. Eine Gruppe, die eine Szene bewusst
    improvisiert laesst, kaeme sonst nie in die letzte Phase."""
    _szene(conn, 1, "MARIA: Hier.")
    _szene(conn, 2, None)
    assert 7 in phasen.moegliche_naechste(conn, 1)


def test_die_bedingungen_sind_nicht_kumulativ(conn):
    """Eine Gruppe, die ohne Interviews direkt Kernthema und Figuren setzt,
    darf trotzdem nach 5 -- die Reihenfolge ist eine Landkarte, kein Zwang."""
    _kernthema_und_figuren(conn)
    assert phasen.voraussetzungen(conn, 1)[4] is False
    assert 5 in phasen.moegliche_naechste(conn, 1)


def test_nie_rueckwaerts_und_nie_die_aktuelle(conn):
    _kernthema_und_figuren(conn)
    phasen.setze(conn, 1, 7, "erkenner")

    assert phasen.moegliche_naechste(conn, 1) == []


def test_erfuellte_stufe_gleich_der_aktuellen_ist_kein_vorschlag(conn):
    _kernthema_und_figuren(conn)
    phasen.setze(conn, 1, 5, "erkenner")

    assert phasen.moegliche_naechste(conn, 1) == []


def test_naechste_moegliche_ist_die_hoechste(conn):
    """Der Merkposten fuer ``phase_angeboten`` braucht eine Zahl, keine
    Liste -- das ist der einzige Grund, warum es beide Funktionen gibt."""
    _kernthema_und_figuren(conn)
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    assert phasen.moegliche_naechste(conn, 1) == [5, 6]
    assert phasen.naechste_moegliche(conn, 1) == 6


def test_entfernte_figuren_zaehlen_fuer_die_materiallage_nicht(conn):
    """Weiches Loeschen wirkt auch hier: Kernthema und zwei Figuren erlauben
    Phase 5, eine entfernte Figur nimmt die Voraussetzung wieder weg (N3)."""
    _kernthema_und_figuren(conn)
    assert phasen.voraussetzungen(conn, 1)[5] is True

    repo.entferne_figur(conn, 1, "Elif")
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
    """Dasselbe von der anderen Seite: ein Kernthema und zwei Figuren machen
    Phase 5 moeglich -- die gespeicherte Phase bleibt trotzdem, wo sie war."""
    phasen.setze(conn, 1, 4, "befehl")
    _kernthema_und_figuren(conn)

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
