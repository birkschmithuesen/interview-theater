"""Die mechanischen Kennzahlen an einem synthetischen Transkript -- ohne Netz.

Synthetisch, damit jede Zahl von Hand nachzaehlbar ist: nach einer
Prompt-Aenderung muss man dem Bericht glauben koennen, ohne den Lauf
nachzulesen.
"""

import pytest

from interview_theater import repo
from simulation import kennzahlen
from simulation.kennzahlen import Beitrag, Zug


def beitrag(kennung, text, absender="Ines", schritt="fragen"):
    return Beitrag(kennung=kennung, schritt=schritt, absender=absender,
                   profil="skeptisch", text=text)


def zug(schritt, beitraege, bot, marke=""):
    return Zug(schritt=schritt, beitraege=beitraege, bot=bot, marke=marke)


@pytest.fixture
def protokoll():
    return [
        zug("fragen",
            [beitrag("S1", "Wir nehmen die sechs Fragen so, wie du sie hast.")],
            [f"{kennzahlen.NOTIERT}\nFragen: Koffer: Was war drin?"]),
        zug("fragen",
            [beitrag("S2", "Nein, die zweite Frage ist zu privat, nimm sie raus.")],
            ["Ich habe das korrigiert und im Arbeitsstand vermerkt."]),
        zug("kernthema",
            [beitrag("S3", "Das Kernthema ist das Warten zwischen zwei Laendern.")],
            ["Ines: Das Kernthema ist das Warten zwischen zwei Laendern."]),
    ]


def test_notiert_praefix_kommt_aus_dem_erkenner():
    assert kennzahlen.NOTIERT.startswith("Notiert")


def test_laenge_bot_ist_der_median(protokoll):
    laengen = sorted(len(t) for z in protokoll for t in z.bot)
    assert kennzahlen.laenge_bot(protokoll) == laengen[1]


def test_leeres_protokoll_ergibt_null_laenge():
    assert kennzahlen.laenge_bot([]) == 0


def test_echo_findet_die_zurueckgespiegelte_antwort(protokoll):
    """Die dritte Antwort ist Zug 3 wortgleich, mit 'Ines:' davor -- genau der
    Live-Fall vom 04.09.2026."""
    treffer = kennzahlen.echos(protokoll)
    assert len(treffer) == 1
    assert treffer[0].startswith("Ines:")


def test_namensanrede_zaehlt_nur_die_beteiligten_namen(protokoll):
    assert len(kennzahlen.namensanreden(protokoll, ["Ines", "Jo"])) == 1
    assert kennzahlen.namensanreden(protokoll, ["Marlen"]) == []


def test_namensanrede_erkennt_auch_hat_recht():
    protokoll = [zug("fragen", [beitrag("S1", "doch")], ["Jo hat recht damit."])]
    assert len(kennzahlen.namensanreden(protokoll, ["Jo"])) == 1


def test_behauptete_schreibvorgaenge_nur_ohne_notiert_zeile(protokoll):
    """Zug 1 behauptet nichts und notiert; Zug 2 behauptet 'korrigiert' und
    'im Arbeitsstand', ohne dass der Erkenner etwas geschrieben hat."""
    treffer = kennzahlen.behauptete_schreibvorgaenge(protokoll)
    assert len(treffer) == 1
    assert "korrigiert" in treffer[0]


def test_die_notiert_zeile_selbst_gilt_nicht_als_behauptung():
    protokoll = [zug("fragen", [beitrag("S1", "ja")],
                     [f"{kennzahlen.NOTIERT}\nBegriffe: Koffer"])]
    assert kennzahlen.behauptete_schreibvorgaenge(protokoll) == []


def test_rueckfragen_vor_szene_endet_am_auftrag():
    protokoll = [
        zug("szene", [beitrag("S1", "Am Bahnhof.", schritt="szene")],
            ["Wo genau soll sie spielen?", "Und wer kommt vor?"]),
        zug("szene", [], ["Szene 1: Am Bahnhof"], marke="szene_aufruf"),
        zug("szene", [], ["Passt das so?"]),
    ]
    assert len(kennzahlen.rueckfragen_vor_szene(protokoll)) == 2


def test_rueckfragen_zaehlen_nur_im_szenen_schritt(protokoll):
    assert kennzahlen.rueckfragen_vor_szene(protokoll) == []


def test_zustimmungen_zaehlen_die_markierten(protokoll):
    gespeichert, gesamt = kennzahlen.zustimmungen(protokoll, {"S1", "S3"})
    assert (gespeichert, gesamt) == (1, 2)


def test_zustimmungen_ohne_markierung_sind_null(protokoll):
    assert kennzahlen.zustimmungen(protokoll, set()) == (0, 0)


# --- aus der Datenbank ----------------------------------------------------


def test_arbeitsstand_vollstaendig_zaehlt_je_feld(conn):
    # Das letzte Feld kommt aus dem Schema (``skript.pflichtfeld_fuer_phase``)
    # -- seit dem Umbau vom 05.09.2026 nachts ist das ``geschichte``, und die
    # Kennzahl zieht ohne Zutun mit.
    stand = kennzahlen.arbeitsstand_vollstaendig(conn, 1)
    assert set(stand) == {"begriffe", "fragen", "kernthema", "figuren_3",
                          "geschichte"}
    assert sum(stand.values()) == 0

    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.")
    for name in ("Meryem", "Ferzan", "Aynur"):
        repo.setze_figur(conn, 1, name, "eine Frau")
    stand = kennzahlen.arbeitsstand_vollstaendig(conn, 1)
    assert stand["begriffe"] == 1
    assert stand["geschichte"] == 1
    assert stand["figuren_3"] == 1
    assert stand["fragen"] == 0


class _Interview:
    def __init__(self, zitate):
        self.zitate_soll = zitate


def test_zitatlage_findet_die_sollzitate(conn):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "text")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Meryem erzaehlt vom Koffer",
        [{"thema": "Koffer", "beleg_zitat": "Ein Koffer und eine Tuete mit Brot",
          "zitat_geprueft": 1},
         {"thema": "Warten", "beleg_zitat": None, "zitat_geprueft": 0}],
    )
    gezogen = [_Interview(["Ein Koffer und eine Tuete mit Brot", "steht nicht da"])]
    lage = kennzahlen.zitatlage(conn, 1, gezogen)
    assert lage["verdichtungen"] == 1
    assert lage["themen"] == 2
    assert lage["zitate_geprueft"] == 1
    assert lage["zitate_soll_gefunden"] == 1
    assert lage["zitate_soll_vermisst"] == ["steht nicht da"]


def test_zitatlage_vergleicht_ueber_zeilenumbrueche_hinweg(conn):
    """Die Soll-Zitate stehen in den Dateien umgebrochen, die Belegzitate
    kommen einzeilig aus dem Modell -- ohne die Normalisierung aus
    ``zitat.py`` waere diese Kennzahl dauerhaft null."""
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 11, "lang", "text")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "z",
        [{"thema": "T", "beleg_zitat": "Ein Koffer und eine Tuete mit Brot",
          "zitat_geprueft": 1}],
    )
    gezogen = [_Interview(["Ein Koffer und\neine Tuete   mit Brot"])]
    assert kennzahlen.zitatlage(conn, 1, gezogen)["zitate_soll_gefunden"] == 1


class _E:
    llm_modell = "moonshotai/Kimi-K2.6"
    erkenner_modell = "google/gemma-4-31B-it"


def test_kosten_sind_bot_kosten_je_art(conn):
    """Was hier steht, ist genau das, was ein echter Workshoptag an
    Infomaniak zahlen wuerde -- die Simulationsseite laeuft ueber ein
    Abonnement und steht gar nicht mehr in dieser Tabelle."""
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    for art in ("gespraech", "erkenner"):
        repo.merke_aufruf(conn, 1, art, "A", 0, 1_000_000, 1_000_000, "stop", 10, 1)
    zahlen = kennzahlen.kosten(conn, _E(), PREISE_CHF_JE_MIO_TOKEN)
    # Kimi: 0,60 ein + 3,00 aus je Mio -> 3,60; gemma: 0,20 + 0,40 -> 0,60
    assert zahlen["chf_je_art"]["gespraech"] == pytest.approx(3.6)
    assert zahlen["chf_je_art"]["erkenner"] == pytest.approx(0.6)
    assert zahlen["chf_bot"] == pytest.approx(4.2)
    assert zahlen["aufrufe"] == 2


def test_kosten_ohne_hinterlegten_preis_bleiben_null(conn):
    repo.merke_aufruf(conn, 1, "gespraech", "A", 0, 1_000, 1_000, "stop", 10, 1)
    zahlen = kennzahlen.kosten(conn, _E(), {})
    assert zahlen["chf_bot"] == 0
    assert zahlen["token_ein"] == 1_000


def test_sammle_liefert_alle_schluessel_des_berichts(conn):
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    zahlen = kennzahlen.sammle(
        conn, 1, [], [], ["Jo"], set(), {"begriffe": True}, _E(),
        PREISE_CHF_JE_MIO_TOKEN, 12.3, notausgaenge=1,
    )
    for schluessel in ("phase_erreicht", "arbeitsstand_vollstaendig", "echo",
                       "verdichtungen", "laenge_bot", "chf_bot", "sim_aufrufe",
                       "interviews_soll", "notausgaenge", "dauer_s"):
        assert schluessel in zahlen
    assert zahlen["notausgaenge"] == 1
    assert zahlen["schritte_gescheitert"] == []


# --- Festlegungen: was ueberlebt, was nur im Journal steht, was fehlt -----
#
# Die Kennzahl zu docs/analyse-phase4-datenverlust-2026-09-06.md: 22 von 42
# Festlegungen waren verloren, und das Kriterium der Analyse ist mechanisch --
# liegt die Angabe in einem Feld, das ein Prompt noch sieht, oder nur in einem
# journal-Eintrag, der nach acht Zeilen faellt?

from simulation import mutation, skript as skript_modul  # noqa: E402

PROBEN = (
    ("struktur", "nur eine Szene", "Das Stueck ist nur eine Szene, erste Folge."),
    ("gruppe", "Outsider", "Es gibt zwei Gruppen: die Coolen und die Outsider."),
)


def test_die_proben_des_skripts_sind_vollstaendig_und_eindeutig():
    """Jede Probe traegt Bereich, Stichwort und Satz; der Bereich muss ein
    ``repo.FESTLEGUNG_BEREICHE`` sein, sonst faellt sie beim Schreiben auf
    'sonstiges' und die Zuordnung im Bericht ist falsch. Und das Stichwort
    muss im Satz stehen -- sonst sucht die Kennzahl etwas, das die Stimme nie
    gesagt bekommt."""
    proben = skript_modul.FESTLEGUNGSPROBEN
    assert len(proben) >= 3
    stichworte = [s for _b, s, _t in proben]
    assert len(set(stichworte)) == len(stichworte)
    for bereich, stichwort, satz in proben:
        assert bereich in repo.FESTLEGUNG_BEREICHE
        assert stichwort.lower() in satz.lower()


def test_eine_festlegung_in_der_tabelle_gilt_als_erhalten(conn):
    for bereich, _stichwort, satz in PROBEN:
        repo.schreibe_festlegung(conn, 1, bereich, satz)
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungen"] == 2
    assert lage["festlegungen_je_bereich"] == {"gruppe": 1, "struktur": 1}
    assert lage["festlegungsproben_erhalten"] == 2
    assert lage["festlegungsproben_nur_journal"] == []
    assert lage["festlegungsproben_nirgends"] == []


def test_ein_arbeitsstandfeld_gilt_genauso(conn):
    """Die Kennzahl bestraft keine Angabe, die ordentlich in einem Feld
    gelandet ist -- gefragt ist, ob sie dauerhaft steht, nicht, ob sie in der
    Auffangtabelle steht."""
    repo.setze_arbeitsstand(conn, 1, "geschichte",
                            "Das Stueck ist nur eine Szene, erste Folge.")
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 1
    assert lage["festlegungsproben_nirgends"] == ["Outsider"]


def test_eine_figurenbeschreibung_gilt_genauso(conn):
    repo.setze_figur(conn, 1, "Sara", "gehoert zu den Outsider, redet zurueck")
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 1
    assert "nur eine Szene" in lage["festlegungsproben_nirgends"]


def test_nur_im_journal_ist_nicht_erhalten(conn):
    """Der Kern des Befunds: ``kontext.JOURNAL_EINTRAEGE = 8`` kappt das
    Journal, ein ``vorgeschlagen``-Eintrag kommt nie zurueck. Die Kennzahl
    zaehlt ihn deshalb getrennt und nicht als Erfolg."""
    for _bereich, _stichwort, satz in PROBEN:
        repo.schreibe_journal(conn, 1, "vorgeschlagen", satz, quelle="erkenner")
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 0
    assert sorted(lage["festlegungsproben_nur_journal"]) == ["Outsider",
                                                            "nur eine Szene"]
    assert lage["festlegungsproben_nirgends"] == []


def test_ohne_alles_fehlt_jede_probe(conn):
    lage = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert lage["festlegungsproben_erhalten"] == 0
    assert len(lage["festlegungsproben_nirgends"]) == 2


def test_die_kennzahl_schlaegt_unter_der_mutation_an_und_sonst_nicht(conn):
    """Beide Richtungen in einem Test, weil nur der Unterschied etwas sagt:
    derselbe Schreibweg, einmal mit und einmal ohne Mutation."""
    def schreibe():
        for bereich, _stichwort, satz in PROBEN:
            geschrieben = repo.schreibe_festlegung(conn, 1, bereich, satz)
            if geschrieben is None:
                # So verhielt sich der Bot vor e56a892: der Inhalt blieb
                # hoechstens als Journalzeile zurueck.
                repo.schreibe_journal(conn, 1, "vorgeschlagen", satz,
                                      quelle="erkenner")

    with mutation.aktiv("festlegung_verloren"):
        schreibe()
    mutiert = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert mutiert["festlegungen"] == 0
    assert mutiert["festlegungsproben_erhalten"] == 0

    schreibe()
    heute = kennzahlen.festlegungslage(conn, 1, PROBEN)
    assert heute["festlegungen"] == 2
    assert heute["festlegungsproben_erhalten"] == 2


def test_festlegungslage_steckt_in_sammle(conn):
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    zahlen = kennzahlen.sammle(
        conn, 1, [], [], ["Jo"], set(), {}, _E(), PREISE_CHF_JE_MIO_TOKEN, 1.0,
    )
    for schluessel in ("festlegungen", "festlegungen_je_bereich",
                       "festlegungsproben", "festlegungsproben_erhalten",
                       "festlegungsproben_nur_journal",
                       "festlegungsproben_nirgends"):
        assert schluessel in zahlen
    # Ohne Argument nimmt sie die Proben des Skripts, nicht die des Tests.
    assert zahlen["festlegungsproben"] == len(skript_modul.FESTLEGUNGSPROBEN)


def test_in_sammle_zaehlt_festlegungen_die_tabelle_nicht_die_notiert_zeilen(conn):
    """``nachrichten_je_festlegung`` (ueber ``sammle_knopfzahlen``) schreibt
    ebenfalls den Schluessel ``festlegungen`` -- dort die Zahl der
    Notiert-Abschnitte. Laeuft es nach ``festlegungslage``, ueberschreibt es
    die Tabellenzahl, und unter der Mutation stuende im Bericht eine Zahl
    groesser null, obwohl ``festlegung`` leer ist."""
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    zuege = [zug("figuren", [beitrag("S1", "Passt so.")],
                 [f"{kennzahlen.NOTIERT}\nFigur: Sara"]) for _ in range(3)]
    repo.schreibe_festlegung(conn, 1, "gruppe", "Die Outsider halten zusammen.")
    zahlen = kennzahlen.sammle(
        conn, 1, zuege, [], ["Jo"], set(), {}, _E(), PREISE_CHF_JE_MIO_TOKEN, 1.0,
    )
    assert zahlen["festlegungen"] == 1
    assert len(zahlen["nachrichten_je_festlegung"]) == 3


# --- Szenen: bleibt die Folge stehen? (Analyse Phase 5, 06.09.2026) -------
#
# Der Befund: aus drei geplanten Szenen mit festgelegter Form wurden sechs,
# und eine Stunde spaeter noch einmal sechs. Ausgeloest vom Regelweg der
# Richtungswahl, die am Ende immer starte_geschichte_szenen rief.


def _szene_mit_form(conn, nummer, form="", entfernt=None):
    """Eine Szenenzeile von Hand -- der Simulator soll hier nichts modellieren
    muessen."""
    szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
    if form:
        repo.setze_szenenfeld(conn, szene_id, "form", form)
    if entfernt:
        conn.execute("UPDATE szene SET entfernt_am = ? WHERE id = ?",
                     (entfernt, szene_id))
        conn.commit()
    return szene_id


def _datiere_letzte(conn, tabelle, zeit):
    """Setzt ``erstellt_am`` der juengsten Zeile. ``repo._jetzt`` ist
    sekundengenau; ohne feste Zeiten faellt ein Journal- und ein Aufrufeintrag
    im Test in dieselbe Sekunde, und die Reihenfolge waere Zufall."""
    conn.execute(
        f"UPDATE {tabelle} SET erstellt_am = ? "
        f"WHERE id = (SELECT max(id) FROM {tabelle})",
        (zeit,),
    )
    conn.commit()


def test_eine_stehende_folge_hat_keine_neuaufbauten(conn):
    for nummer in (1, 2, 3):
        _szene_mit_form(conn, nummer, "dialog")
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenen_aktiv"] == 3
    assert lage["szenen_ersetzt"] == 0
    assert lage["szenen_neuaufbauten"] == 0
    assert lage["szenen_form_verloren"] == 0


def test_zwei_neuaufbauten_werden_an_den_zeitpunkten_gezaehlt(conn):
    """Der Live-Fall: ids 1-3 entfernt um 13:54:37, ids 4-9 um 14:09:35 --
    zwei Zeitpunkte, zwei Neuaufbauten, auch wenn neun Zeilen betroffen sind."""
    for nummer in (1, 2, 3):
        _szene_mit_form(conn, nummer, "chor", entfernt="2026-09-06T13:54:37")
    for nummer in (4, 5, 6):
        _szene_mit_form(conn, nummer, "", entfernt="2026-09-06T14:09:35")
    for nummer in (7, 8):
        _szene_mit_form(conn, nummer)
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenen_ersetzt"] == 6
    assert lage["szenen_neuaufbauten"] == 2
    assert lage["szenen_form_verloren"] == 3, "nur die mit bestaetigter Form"
    assert lage["szenen_aktiv"] == 2


def test_ein_szenenfolge_lauf_nach_der_richtungswahl_ist_ein_befund(conn):
    """Genau das, was C9 abgeschafft hat: die Gruppe hat eine Richtung
    gedrueckt, und danach erfindet ein Lauf Titel und Form neu."""
    repo.schreibe_journal(conn, 1, "entschieden",
                          "Geschichte: Nacht am Kanal — Szene 1: Ankunft",
                          quelle="knopf")
    _datiere_letzte(conn, "journal", "2026-09-06T13:50:00+00:00")
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    _datiere_letzte(conn, "aufruf", "2026-09-06T13:51:50+00:00")
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenenfolge_laeufe"] == 1
    assert lage["szenenfolge_nach_richtung"] == 1
    assert lage["szenen_aus_richtung"] is False


def test_ein_lauf_in_derselben_sekunde_wie_der_druck_zaehlt_nicht(conn):
    """``erstellt_am`` ist sekundengenau; ein Gleichstand ist nicht
    'danach'. Ein echter Folge-Lauf kostet Modellzeit und liegt strikt
    spaeter -- in derselben Sekunde kann nur der Ur-Vorschlag liegen."""
    repo.schreibe_journal(conn, 1, "entschieden", "Geschichte: Nacht am Kanal",
                          quelle="knopf")
    _datiere_letzte(conn, "journal", "2026-09-06T13:50:00+00:00")
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    _datiere_letzte(conn, "aufruf", "2026-09-06T13:50:00+00:00")
    assert kennzahlen.szenenlage(conn, 1)["szenenfolge_nach_richtung"] == 0


def test_der_ur_vorschlag_in_derselben_sekunde_ist_kein_befund(conn):
    """Der Review-Fall: ``szenenfolge.starte`` liefert den Vorschlag, die
    Gruppe drueckt sofort eine Richtung -- beide Zeilen tragen dieselbe
    Sekunde. Das ist der legitime Vorschlag, kein Neuaufbau."""
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    _datiere_letzte(conn, "aufruf", "2026-09-06T13:50:00+00:00")
    repo.schreibe_journal(conn, 1, "entschieden", "Geschichte: Nacht am Kanal",
                          quelle="knopf")
    _datiere_letzte(conn, "journal", "2026-09-06T13:50:00+00:00")
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenenfolge_laeufe"] == 1
    assert lage["szenenfolge_nach_richtung"] == 0


def test_ein_lauf_vor_der_richtungswahl_zaehlt_nicht(conn):
    """Der Vorschlag, aus dem die Richtungen ueberhaupt entstanden sind, ist
    kein Befund -- gezaehlt wird nur, was NACH dem Druck kommt."""
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    _datiere_letzte(conn, "aufruf", "2026-09-06T13:48:10+00:00")
    repo.schreibe_journal(conn, 1, "entschieden", "Geschichte: Nacht am Kanal",
                          quelle="knopf")
    _datiere_letzte(conn, "journal", "2026-09-06T13:50:00+00:00")
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenenfolge_laeufe"] == 1
    assert lage["szenenfolge_nach_richtung"] == 0


def test_der_inline_weg_wird_erkannt(conn):
    from interview_theater import szenenfolge

    repo.schreibe_journal(conn, 1, "entschieden", "Geschichte: Nacht am Kanal",
                          quelle="knopf")
    repo.schreibe_journal(
        conn, 1, "entschieden",
        szenenfolge.JOURNAL_INLINE.format(liste="1. Ankunft; 2. Gestaendnis"),
        quelle="knopf",
    )
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenen_aus_richtung"] is True
    assert lage["szenenfolge_nach_richtung"] == 0


def test_ohne_richtungswahl_bleibt_die_zahl_null(conn):
    repo.merke_aufruf(conn, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["szenenfolge_nach_richtung"] == 0
    assert lage["szenen_aus_richtung"] is False


def test_der_prosalauf_wird_getrennt_gezaehlt(conn):
    """``kurzgeschichte`` ersetzt in Phase 6 bestimmungsgemaess -- die Zahl
    steht daneben, damit ein Neuaufbau nicht falsch zugeordnet wird."""
    repo.merke_aufruf(conn, 1, "kurzgeschichte", "A", 0, 10, 10, "stop", 1, 1)
    lage = kennzahlen.szenenlage(conn, 1)
    assert lage["kurzgeschichte_laeufe"] == 1
    assert lage["szenenfolge_laeufe"] == 0


def test_szenenlage_steckt_in_sammle(conn):
    from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN

    zahlen = kennzahlen.sammle(
        conn, 1, [], [], ["Jo"], set(), {}, _E(), PREISE_CHF_JE_MIO_TOKEN, 1.0,
    )
    for schluessel in ("szenen_aktiv", "szenen_ersetzt", "szenen_neuaufbauten",
                       "szenen_form_verloren", "szenenfolge_laeufe",
                       "kurzgeschichte_laeufe", "szenenfolge_nach_richtung",
                       "szenen_aus_richtung"):
        assert schluessel in zahlen


def test_szenenlage_schlaegt_unter_der_mutation_an_und_sonst_nicht(
        conn, einst, monkeypatch):
    """Beide Richtungen am echten Knopfweg, ohne Netz: heute nimmt die
    Richtungswahl ihre Szenen mit (Inline-Weg, kein Folge-Lauf), unter
    ``richtung_ohne_szenen`` kommt danach ein ``szenenfolge``-Lauf. Die
    Attrappe protokolliert ihren Aufruf wie ``llm.LLM.prosa`` es tut --
    sonst stuende der Lauf nicht in ``aufruf``, und die Kennzahl saehe ihn
    so wenig wie im Betrieb ohne diese Zeile.

    ``repo._jetzt`` laeuft hier als fortlaufende Uhr (eine Sekunde je
    Aufruf): die Attrappe antwortet sofort, und ohne sie fielen Druck und
    Folge-Lauf in dieselbe Sekunde -- ein Gleichstand zaehlt bewusst nicht.
    Im Betrieb liegt die Modellzeit dazwischen."""
    import itertools
    from datetime import datetime, timedelta, timezone

    from interview_theater import knoepfe, phasen, szenenfolge, vorschlagssperre

    start = datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
    takt = itertools.count()
    monkeypatch.setattr(
        repo, "_jetzt",
        lambda: (start + timedelta(seconds=next(takt))).isoformat(
            timespec="seconds"),
    )
    from simulation import mutation
    from test_szenenfolge import TelegramAttrappe

    class ProtokollierendeAttrappe:
        def __init__(self, c):
            self.c = c

        def prosa(self, chat_id, system, nutzer, art, max_tokens=None,
                  timeout=None):
            repo.merke_aufruf(self.c, chat_id, art, "A", 0, 10, 10, "stop", 1, 1)
            return ("VORSCHLAG SZENENFOLGE:\n"
                    "Am Steg — sie treffen sich — Mira — Dialog\n"
                    "Im Flur — sie streiten — Mira, Pal — Dialog")

    richtung = ("Nacht am Kanal — Mira stellt sich, Pal gesteht. "
                "Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis.")

    def lage_nach_druck(c, mutiert):
        repo.setze_arbeitsstand(c, 1, "begriffe", "Koffer, Bahnhof, Winter")
        repo.setze_arbeitsstand(c, 1, "rahmen", "Ein Treppenhaus, nachts")
        repo.setze_figur(c, 1, "Mira", "will gefragt werden")
        repo.setze_figur(c, 1, "Pal", "haelt an seiner Route fest")
        repo.setze_arbeitsstand(c, 1, "figuren_fixiert_am", "2026-09-05T23:00:00")
        phasen.setze(c, 1, 4, "test")
        vorschlagssperre.vergiss(1)
        with mutation.aktiv("richtung_ohne_szenen" if mutiert else None):
            knoepfe._wirke(
                c, TelegramAttrappe(), ProtokollierendeAttrappe(c), einst,
                {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
                 "wert": f"weiter{knoepfe.TRENNER}{richtung}"},
                1,
            )
            assert szenenfolge._sperre_fuer(1).acquire(timeout=10)
            szenenfolge._sperre_fuer(1).release()
        vorschlagssperre.vergiss(1)
        return kennzahlen.szenenlage(c, 1)

    heute = lage_nach_druck(conn, mutiert=False)
    assert heute["szenenfolge_nach_richtung"] == 0
    assert heute["szenen_aus_richtung"] is True

    from interview_theater import db

    zweite = db.verbinde(str(einst.db_pfad) + ".mutiert")
    db.initialisiere(zweite)
    repo.sichere_gruppe(zweite, 1, "gruppe1", "Testgruppe")
    mutiert = lage_nach_druck(zweite, mutiert=True)
    assert mutiert["szenenfolge_nach_richtung"] == 1
    assert mutiert["szenen_aus_richtung"] is False
