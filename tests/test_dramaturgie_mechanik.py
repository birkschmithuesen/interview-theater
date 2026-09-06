"""Schicht 1: die mechanische Pruefung -- ohne Modell, ohne Netz.

Die Szenentexte hier sind **frei erfunden** und nach den Ausgabeformen aus
``interview_theater/prompts/formen/*.md`` gebaut: Dialog mit Inline-Regie
ohne Leerzeichen, Dialog in Markdown-Fettschrift, Chor mit ``CHOR:``, Rap
mit dem Namen allein auf der Zeile, Lied mit ``STROPHE (NAME)`` -- und ein
Lied ohne jede Sprecherangabe, an dem sich zeigen muss, dass die
sprecherabhaengigen Checks dann **schweigen**.
"""

import pytest
from interview_theater import repo
from interview_theater.dramaturgie import mechanik

# --- Szenentexte in vier realistischen Formatierungen ---------------------

DIALOG = """SZENE 1: AM BAHNHOF ca. 9 min
Ein Bahnsteig, frueher Abend. Zwei Koffer stehen an der Bank.

MIRA:(sieht nicht auf)Der Koffer steht seit gestern hier.
JONAS: Und?
MIRA: Und niemand holt ihn.
(JONAS steht auf. Geht zum Koffer.)
JONAS: Dann nehme ich ihn mit.
MIRA: Lass den Koffer stehen.
JONAS: Nein.
"""

DIALOG_MARKDOWN = """**TITEL:** Die Wohnung
**KURZ:** Mira raeumt auf.

**MIRA:** Ich habe den Schluessel verlegt.
**JONAS:** Schon wieder.
**MIRA:** Such du.
**JONAS:** Ich suche nicht.
"""

CHOR = """(Bushaltestelle, frueher Abend.)

CHOR: Wir warten seit zwei Stunden hier.
MIRA: Ich hab kein Netz.
CHOR: Wir warten seit zwei Stunden hier.
JONAS: Dann geh zu Fuss.
"""

RAP = """(Bahnhof, seit zwei Stunden.)

MIRA
Zwei Stunden hier, kein Meter Platz
Ich hab kein Netz, ich hab kein Satz

HOOK (ALLE)
Wir stehen und wir stehen

JONAS
Ich geh jetzt los und du bleibst hier
"""

LIED_MIT_NAME = """(Wohnzimmer, spaeter Abend.)

STROPHE (MIRA)
Der Schluessel liegt noch oben
seit dreissig Jahren da

REFRAIN
Wir gehen nicht mehr weg
"""

LIED_OHNE_SPRECHER = """(Ein leerer Raum. Licht von hinten.)

Wir haben nichts vergessen
wir haben nur nichts gesagt

Und morgen ist es weg
und uebermorgen auch
"""

PROSA = """Mira sitzt am Tisch. Sie sagt nichts. Jonas kommt herein und stellt
den Koffer ab. Er wartet, bis sie aufsieht. Dann geht er wieder.
"""


def _figur(conn, name, chat_id=1):
    repo.setze_figur(conn, chat_id, name, f"{name} ist erfunden.")


def _szene(conn, nummer, volltext="", form="dialog", besetzung=(), chat_id=1,
           prosa=None):
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    repo.setze_szenenfeld(conn, szene_id, "form", form)
    if volltext:
        conn.execute(
            "UPDATE szene SET volltext = ? WHERE id = ?", (volltext, szene_id)
        )
    if prosa is not None:
        conn.execute("UPDATE szene SET prosa = ? WHERE id = ?", (prosa, szene_id))
    conn.commit()
    if besetzung:
        ids = [repo.hole_figur(conn, chat_id, n)["id"] for n in besetzung]
        repo.setze_szene_figuren(conn, chat_id, szene_id, ids)
    return szene_id


# --- Das Sprecherzeilen-Parsing -------------------------------------------


def test_dialog_mit_inline_regie_ohne_leerzeichen():
    gefunden = mechanik.repliken(DIALOG)
    assert [r.label for r in gefunden] == [
        "MIRA", "JONAS", "MIRA", "JONAS", "MIRA", "JONAS",
    ]
    # Die Regieanweisung faellt aus der Replik heraus, der Sprechtext bleibt.
    assert gefunden[0].text == "Der Koffer steht seit gestern hier."


def test_der_szenenkopf_ist_keine_sprecherzeile():
    """``SZENE 1: AM BAHNHOF`` hat einen Doppelpunkt und ist trotzdem kein
    Sprecher -- sonst haette jedes Stueck eine Figur namens SZENE."""
    assert all(r.label != "SZENE 1" for r in mechanik.repliken(DIALOG))
    assert "SZENE" not in {r.label for r in mechanik.repliken(DIALOG)}


def test_kopfzeilen_der_modellantwort_sind_keine_sprecher():
    labels = {r.label for r in mechanik.repliken(DIALOG_MARKDOWN)}
    assert labels == {"MIRA", "JONAS"}


def test_chorzeilen_zaehlen_als_sprecher_aber_nicht_als_figur(conn):
    labels = [r.label for r in mechanik.repliken(CHOR)]
    assert labels == ["CHOR", "MIRA", "CHOR", "JONAS"]


def test_rap_mit_dem_namen_allein_auf_der_zeile():
    gefunden = mechanik.repliken(RAP)
    assert [r.label for r in gefunden] == [
        "MIRA", "MIRA", "ALLE", "JONAS",
    ]
    assert gefunden[0].text == "Zwei Stunden hier, kein Meter Platz"


def test_lied_mit_strophenmarker_und_name():
    gefunden = mechanik.repliken(LIED_MIT_NAME)
    assert [r.label for r in gefunden] == ["MIRA", "MIRA"]
    # REFRAIN ohne Namen hat keinen Sprecher -- die Zeilen fallen weg, statt
    # der letzten Figur zugeschlagen zu werden.
    assert all("Wir gehen nicht mehr weg" not in r.text for r in gefunden)


def test_lied_ohne_sprecherangabe_liefert_keine_replik():
    assert mechanik.repliken(LIED_OHNE_SPRECHER) == []


def test_prosafassung_liefert_keine_replik():
    """Auch nicht im zweiten Durchgang mit Figurennamen: ``Mira sitzt am
    Tisch.`` ist keine Sprecherzeile."""
    assert mechanik.repliken(PROSA, ["Mira", "Jonas"]) == []


def test_zweiter_durchgang_liest_gemischte_schreibweise():
    text = "Mira: Ich gehe.\nJonas: Bleib.\n"
    assert mechanik.repliken(text) == []
    gefunden = mechanik.repliken(text, ["Mira", "Jonas"])
    assert [r.label for r in gefunden] == ["Mira", "Jonas"]


# --- Namensstabilitaet und Geisterfiguren ---------------------------------


def test_namensvariante_wird_gemeldet(conn):
    _figur(conn, "Leyla")
    _figur(conn, "Jonas")
    _szene(conn, 1, "LEYLA: Ich gehe.\nJONAS: Bleib.\n")
    _szene(conn, 2, "LAYLA: Ich bin zurueck.\nJONAS: Ich sehe es.\n")

    befunde = mechanik.pruefe_alles(conn, 1)
    varianten = [b for b in befunde if b.pruefung == "namensstabilitaet"]

    assert len(varianten) == 1
    assert varianten[0].schwere == "hart"
    assert varianten[0].szene == 2
    assert "LAYLA" in varianten[0].text and "Leyla" in varianten[0].text


def test_sprecher_ohne_figurenzeile_ist_ein_harter_fehler(conn):
    _figur(conn, "Mira")
    _figur(conn, "Jonas")
    _szene(conn, 1, "MIRA: Wer bist du?\nBORIS: Egal.\nJONAS: Lass ihn.\n")

    geister = [b for b in mechanik.pruefe_alles(conn, 1)
               if b.pruefung == "geisterfigur"]

    assert [b.figur for b in geister] == ["BORIS"]
    assert geister[0].schwere == "hart"


def test_chor_ist_keine_geisterfigur(conn):
    _figur(conn, "Mira")
    _figur(conn, "Jonas")
    _szene(conn, 1, CHOR, form="chor")

    assert not [b for b in mechanik.pruefe_alles(conn, 1)
                if b.pruefung == "geisterfigur"]


def test_figur_ohne_auftritt_ist_nur_eine_warnung(conn):
    _figur(conn, "Mira")
    _figur(conn, "Jonas")
    _figur(conn, "Pola")
    _szene(conn, 1, "MIRA: Ich gehe.\nJONAS: Bleib.\n")

    stumm = [b for b in mechanik.pruefe_alles(conn, 1)
             if b.pruefung == "figur_ohne_auftritt"]

    assert [b.figur for b in stumm] == ["Pola"]
    assert stumm[0].schwere == "hinweis"


def test_erwaehnte_figur_gilt_nicht_als_ohne_auftritt(conn):
    _figur(conn, "Mira")
    _figur(conn, "Jonas")
    _figur(conn, "Pola")
    _szene(conn, 1, "MIRA: Wo ist Pola?\nJONAS: Weg.\n")

    assert not [b for b in mechanik.pruefe_alles(conn, 1)
                if b.pruefung == "figur_ohne_auftritt"]


# --- Besetzungsabgleich ---------------------------------------------------


def test_besetzung_ohne_replik_und_replik_ohne_besetzung(conn):
    _figur(conn, "Mira")
    _figur(conn, "Jonas")
    _figur(conn, "Pola")
    _szene(conn, 1, "MIRA: Ich gehe.\nJONAS: Bleib.\n", besetzung=("Mira", "Pola"))

    befunde = mechanik.pruefe_alles(conn, 1)
    stumm = [b for b in befunde if b.pruefung == "besetzung_stumm"]
    fremd = [b for b in befunde if b.pruefung == "besetzung_fremd"]

    assert [b.figur for b in stumm] == ["Pola"]
    assert [b.figur for b in fremd] == ["JONAS"]
    assert stumm[0].schwere == "verdacht" and fremd[0].schwere == "verdacht"


def test_ohne_erkannte_sprecherzeilen_gibt_es_keinen_besetzungsbefund(conn):
    """Der defensive Kern: ein Lied ohne Sprecherangabe darf keine Besetzung
    beanstanden -- sonst meldet die Mechanik bei jeder Liedszene alle
    Mitwirkenden als stumm."""
    _figur(conn, "Mira")
    _figur(conn, "Jonas")
    _szene(conn, 1, LIED_OHNE_SPRECHER, form="lied", besetzung=("Mira", "Jonas"))

    befunde = mechanik.pruefe_alles(conn, 1)

    assert not [b for b in befunde if b.pruefung.startswith("besetzung")]
    assert not [b for b in befunde if b.pruefung == "sprechanteil"]
    assert not [b for b in befunde if b.pruefung == "geisterfigur"]


# --- Erstauftritt ---------------------------------------------------------


def test_vorher_genannt_ist_eine_verdachtszeile(conn):
    _figur(conn, "Mira")
    _figur(conn, "Pola")
    _szene(conn, 1, "MIRA: Pola kommt nie zu spaet.\nMIRA: Nie.\n")
    _szene(conn, 2, "POLA: Ich bin da.\nMIRA: Endlich.\n")

    erst = [b for b in mechanik.pruefe_alles(conn, 1)
            if b.pruefung == "erstauftritt"]

    assert len(erst) == 1
    assert erst[0].schwere == "verdacht"
    assert erst[0].figur == "Pola" and erst[0].szene == 1


# --- Tschechow ------------------------------------------------------------


def test_kandidat_kommt_zweimal_und_danach_nie_wieder(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Der Koffer steht da.\nMIRA: Der Koffer bleibt.\n")
    _szene(conn, 2, "MIRA: Wir gehen zum Bahnsteig.\nMIRA: Jetzt.\n")

    woerter = [k.wort for k in
               mechanik.tschechow_kandidaten(mechanik.lies(conn, 1))]

    assert "Koffer" in woerter
    # Ein Wort aus der LETZTEN Szene ist nie Kandidat -- danach kommt nichts.
    assert "Bahnsteig" not in woerter


def test_kandidat_traegt_seinen_satz_als_kontext(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Der Koffer steht da.\nMIRA: Der Koffer bleibt.\n")
    _szene(conn, 2, "MIRA: Wir gehen.\nMIRA: Jetzt.\n")

    kandidat = next(k for k in
                    mechanik.tschechow_kandidaten(mechanik.lies(conn, 1))
                    if k.wort == "Koffer")

    assert "Koffer steht da" in kandidat.satz
    assert kandidat.anzahl == 2 and kandidat.szene == 1


def test_figurennamen_sind_keine_kandidaten(conn):
    _figur(conn, "Mira")
    _figur(conn, "Pola")
    _szene(conn, 1, "MIRA: Pola, Pola, wo bist du?\nMIRA: Pola!\n")
    _szene(conn, 2, "MIRA: Egal.\nMIRA: Wirklich egal.\n")

    woerter = [k.wort for k in
               mechanik.tschechow_kandidaten(mechanik.lies(conn, 1))]

    assert "Pola" not in woerter


# --- Formverteilung -------------------------------------------------------


def test_szene_eins_darf_kein_monolog_sein(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Ich rede allein.\n", form="Monolog")
    _szene(conn, 2, "MIRA: Und weiter.\n", form="Dialog")

    regel = [b for b in mechanik.pruefe_alles(conn, 1)
             if b.pruefung == "form_regel" and b.schwere == "hart"]

    assert len(regel) == 1 and regel[0].szene == 1


def test_drei_nicht_dialog_szenen_hintereinander_sind_klumpung(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Los.\n", form="Dialog")
    for nummer, form in ((2, "Lied"), (3, "Rap"), (4, "Chor")):
        _szene(conn, nummer, "MIRA: Text.\n", form=form)
    _szene(conn, 5, "MIRA: Schluss.\n", form="Dialog")

    klumpen = [b for b in mechanik.pruefe_alles(conn, 1)
               if b.pruefung == "formverteilung"]

    assert len(klumpen) == 1 and klumpen[0].szene == 2


def test_hoechstens_eine_nicht_dialog_szene_je_drei(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Los.\n", form="Dialog")
    _szene(conn, 2, "MIRA: Text.\n", form="Lied")
    _szene(conn, 3, "MIRA: Text.\n", form="Dialog")
    _szene(conn, 4, "MIRA: Text.\n", form="Rap")

    regel = [b for b in mechanik.pruefe_alles(conn, 1)
             if b.pruefung == "form_regel" and b.schwere == "hinweis"]

    assert len(regel) == 1
    assert "Szene 2, Szene 4" in regel[0].text


def test_ohne_bestaetigte_form_gibt_es_keinen_formbefund(conn):
    """``form_vorschlag`` ist kein ``form``: ein Vorschlag ist keine
    Entscheidung, und ueber eine Entscheidung, die niemand getroffen hat,
    gibt es nichts zu befinden."""
    _figur(conn, "Mira")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form_vorschlag", "Monolog")
    conn.execute("UPDATE szene SET volltext = 'MIRA: Allein.' WHERE id = ?",
                 (szene_id,))
    conn.commit()

    assert not [b for b in mechanik.pruefe_alles(conn, 1)
                if b.pruefung.startswith("form")]


# --- Sprechanteile --------------------------------------------------------


def test_figur_mit_sehr_wenig_text_wird_gemeldet(conn):
    _figur(conn, "Mira")
    _figur(conn, "Pola")
    viel = "\n".join(
        f"MIRA: Das ist eine Replik mit einigen Woertern darin Nummer {i}."
        for i in range(30)
    )
    _szene(conn, 1, viel + "\nPOLA: Ja.\n")

    anteile = [b for b in mechanik.pruefe_alles(conn, 1)
               if b.pruefung == "sprechanteil"]

    assert [b.figur for b in anteile] == ["Pola"]
    assert anteile[0].schwere == "hart"
    # Zahlen ja, Note oder Prozent nein.
    assert "%" not in anteile[0].text
    assert "1 von" in anteile[0].text


def test_befunde_tragen_weder_note_noch_prozent(conn):
    _figur(conn, "Mira")
    _figur(conn, "Pola")
    _szene(conn, 1, "MIRA: Ich gehe.\nBORIS: Nein.\n", besetzung=("Mira",),
           form="Monolog")
    _szene(conn, 2, "MIRA: Egal.\n", form="Dialog")

    befunde = mechanik.pruefe_alles(conn, 1)

    assert befunde
    for b in befunde:
        assert b.schwere in mechanik.SCHWEREN
        assert "%" not in b.text
        assert not any(marke in b.text for marke in ("/5", "Note", "Punkte"))
        assert b.als_dict()["quelle"] == "mechanik"


def test_ohne_szenen_gibt_es_keine_befunde(conn):
    _figur(conn, "Mira")
    assert mechanik.pruefe_alles(conn, 1) == []


def test_pruefe_alles_schreibt_nichts(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Ich gehe.\n")
    vorher = [
        conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("journal", "vorfall", "aufruf", "szene", "figur")
    ]

    mechanik.pruefe_alles(conn, 1)

    nachher = [
        conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("journal", "vorfall", "aufruf", "szene", "figur")
    ]
    assert vorher == nachher


@pytest.mark.parametrize("text", ["", "   \n\n", "(Nur eine Regieanweisung.)"])
def test_leerer_text_ist_kein_fehler(text):
    assert mechanik.repliken(text, ["Mira"]) == []


def test_zwei_szenen_mit_derselben_nummer_zaehlen_einmal(conn):
    """Eine Nummernvergabe von Hand kann zwei Szenen dieselbe Nummer geben.
    Sie darf nicht dazu fuehren, dass der Fan-out dieselbe Szene zweimal
    fragt und zweimal bezahlt."""
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Erste Fassung.\n")
    zweite = repo.lege_szene_an(conn, 1, 1, "Nochmal", "dasselbe", None)
    conn.execute("UPDATE szene SET volltext = ? WHERE id = ?",
                 ("MIRA: Zweite Fassung.\n", zweite))
    conn.commit()

    lage = mechanik.lies(conn, 1)

    assert lage.nummern == [1]
