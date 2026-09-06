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


def test_wort_nur_am_satzanfang_ist_kein_kandidat(conn):
    """Deutsch schreibt am Satzanfang alles gross -- das sagt nichts.

    Gemessen am 06.09.2026 an drei echten Opus-Szenen: ohne diese Regel
    meldete die Heuristik „Lass\", „Beim\", „Dreht\", „Ueber\" als aufgeladene
    Elemente, 8 von 11 Befunden waren Rauschen. Alle vier sind Verben oder
    Praepositionen, die ausschliesslich am Satzanfang gross stehen.
    """
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Lass das doch.\nMIRA: Lass mich in Ruhe.\n")
    _szene(conn, 2, "MIRA: Wir gehen.\nMIRA: Jetzt.\n")

    woerter = [k.wort for k in
               mechanik.tschechow_kandidaten(mechanik.lies(conn, 1))]

    assert "Lass" not in woerter


def test_substantiv_mitten_im_satz_bleibt_kandidat(conn):
    """Die Gegenprobe: dasselbe Wort mitten im Satz zaehlt weiter.

    Sonst waere die Regel aus dem vorigen Test zu scharf und wuerde genau
    die Gegenstaende verschlucken, um die es geht.
    """
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Ich habe den Akku vergessen.\n"
                    "MIRA: Ohne Akku geht das nicht.\n")
    _szene(conn, 2, "MIRA: Wir gehen.\nMIRA: Jetzt.\n")

    woerter = [k.wort for k in
               mechanik.tschechow_kandidaten(mechanik.lies(conn, 1))]

    assert "Akku" in woerter


def test_wort_nach_sprecherdoppelpunkt_zaehlt_nicht(conn):
    """Nach „MIRA:\" steht das erste Wort gross wie am Satzanfang."""
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Warte doch.\nMIRA: Warte einen Moment.\n")
    _szene(conn, 2, "MIRA: Gut.\nMIRA: Dann eben.\n")

    woerter = [k.wort for k in
               mechanik.tschechow_kandidaten(mechanik.lies(conn, 1))]

    assert "Warte" not in woerter


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
#
# Die Formregeln gelten erst ab dem Feinschliff: in Phase 6 ist der Text die
# Prosafassung, die Formen sind dort noch nicht umgesetzt (Birk, 06.09.2026:
# "nicht beim Prosa text"). Die Tests setzen die Phase deshalb ausdruecklich.


def _feinschliff(conn, chat_id=1):
    """Setzt die Phase, ab der Formen eingeloest sind."""
    repo.setze_phase(conn, chat_id, mechanik.FORM_AB_PHASE)
    conn.commit()


def test_formregeln_schweigen_in_der_prosaphase(conn):
    """**Der Fall, der das Rauschen erzeugt hat.** Drei Szenen, zwei davon
    keine Dialogszene -- in Phase 6 ist das kein Befund, weil der Text die
    Formen planmaessig noch nicht umsetzt."""
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Los.\n", form="Chor")
    _szene(conn, 2, "MIRA: Text.\n", form="Dialog")
    _szene(conn, 3, "MIRA: Schluss.\n", form="Rap")
    repo.setze_phase(conn, 1, 6)
    conn.commit()

    formbefunde = [b for b in mechanik.pruefe_alles(conn, 1)
                   if b.pruefung in ("form_regel", "formverteilung")]

    assert formbefunde == []


def test_szene_eins_darf_kein_monolog_sein(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Ich rede allein.\n", form="Monolog")
    _szene(conn, 2, "MIRA: Und weiter.\n", form="Dialog")
    _feinschliff(conn)

    regel = [b for b in mechanik.pruefe_alles(conn, 1)
             if b.pruefung == "form_regel" and b.schwere == "hart"]

    assert len(regel) == 1 and regel[0].szene == 1


def test_drei_nicht_dialog_szenen_hintereinander_sind_klumpung(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Los.\n", form="Dialog")
    for nummer, form in ((2, "Lied"), (3, "Rap"), (4, "Chor")):
        _szene(conn, nummer, "MIRA: Text.\n", form=form)
    _szene(conn, 5, "MIRA: Schluss.\n", form="Dialog")
    _feinschliff(conn)

    klumpen = [b for b in mechanik.pruefe_alles(conn, 1)
               if b.pruefung == "formverteilung"]

    assert len(klumpen) == 1 and klumpen[0].szene == 2


def test_hoechstens_eine_nicht_dialog_szene_je_drei(conn):
    _figur(conn, "Mira")
    _szene(conn, 1, "MIRA: Los.\n", form="Dialog")
    _szene(conn, 2, "MIRA: Text.\n", form="Lied")
    _szene(conn, 3, "MIRA: Text.\n", form="Dialog")
    _szene(conn, 4, "MIRA: Text.\n", form="Rap")
    _feinschliff(conn)

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


# --- Fokus: wieviel Text ist echter Nebenschauplatz? ---------------------
#
# Anlass ist Birks Kritik am fertigen Text von Gruppe 1 (06.09.2026): "zu
# wenig Fokus auf die wesentliche Handlung, zu viele belanglose
# Nebenschauplaetze". Auf Nachfrage praezisiert: Figureneinfuehrung,
# Seitenstraenge, die spaeter aufgegriffen werden, und poetische
# Setting-Beschreibung sind KEINE Ablenkung. Die Texte hier sind erfunden,
# das Muster ist echt.

#: Ein Absatz, der weder traegt noch einfuehrt noch zurueckkommt. Karim und
#: Lena sind vorher schon aufgetreten (Absatz 1), damit hier nicht die
#: Einfuehrungs-Ausnahme greift -- geprueft wird der Nebenschauplatz.
FOKUS_DANEBEN = """Mira steht am Wasser und wartet auf Jonas, und Karim und
Lena stehen daneben und sagen nichts dazu.

Karim streitet mit Lena darueber, wer beim letzten Turnier den entscheidenden
Fehlpass gespielt hat, und die beiden zaehlen sich gegenseitig auf, was in
jenem Spiel sonst noch schiefgegangen ist. Lena sagt, das Turnier sei ohnehin
schlecht organisiert gewesen. Karim widerspricht ausfuehrlich und nennt
Einzelheiten ueber die Schiedsrichterin, ueber den Platz und ueber das Wetter
an jenem Tag, und keiner von beiden kommt darauf zurueck.

Jonas kommt und bleibt vor Mira stehen und sagt nichts.
"""

#: Derselbe Aufbau, aber der lange Absatz traegt den Konflikt mit.
FOKUS_DICHT = """Mira steht am Wasser und wartet auf Jonas. Sie hat ihm
gesagt, dass sie nicht mehr warten will, und wartet trotzdem.

Jonas kommt zu spaet und sieht sofort, dass sie geweint hat, und tut so, als
saehe er es nicht, weil das einfacher ist als die Frage, die sonst kaeme. Mira
merkt, dass er es merkt, und sagt trotzdem nichts.

Jonas fragt Mira, ob sie noch bleiben will.
"""

KONFLIKT = "Mira will zu Jonas gehoeren und kann es sich nicht eingestehen."


def _fokuslage(conn, text, zweite=None):
    for name in ("Mira", "Jonas", "Karim", "Lena", "Tom"):
        _figur(conn, name)
    _szene(conn, 1, prosa=text)
    if zweite is not None:
        _szene(conn, 2, prosa=zweite)
    return mechanik.lies(conn, 1)


def test_fokus_meldet_szene_die_ueberwiegend_daneben_spielt(conn):
    lage = _fokuslage(conn, FOKUS_DANEBEN)

    befunde = mechanik.fokus(lage, KONFLIKT)

    assert len(befunde) == 1
    assert befunde[0].szene == 1
    assert befunde[0].pruefung == "fokus"
    assert "Mira und Jonas" in befunde[0].text
    assert "Karim streitet" in befunde[0].text


def test_fokus_schweigt_wenn_die_traeger_den_text_tragen(conn):
    lage = _fokuslage(conn, FOKUS_DICHT)

    assert mechanik.fokus(lage, KONFLIKT) == []


def test_figureneinfuehrung_ist_kein_nebenschauplatz(conn):
    """Ein Stueck muss seine Figuren zeigen -- frueh und mit einem Zug.

    Ohne diese Ausnahme bestraft der Check genau die Arbeit, die eine
    Exposition leisten muss (Birk, 06.09.2026).
    """
    text = ("Karim sitzt auf dem Gelaender und erzaehlt, wie sein Onkel "
            "einmal von einer Bruecke gesprungen ist. Lena hoert nicht zu. "
            "Tom wirft einen Ball gegen die Mauer, immer wieder.\n\n"
            "Mira wartet auf Jonas und sagt nichts dazu.")
    lage = _fokuslage(conn, text)
    erst = mechanik._erstauftritte(lage)

    marke = mechanik.einordnung(text.split("\n\n")[0], 1, 1, "", lage, erst)

    assert marke == "einfuehrung"


def test_seitenstrang_der_zurueckkommt_ist_kein_nebenschauplatz(conn):
    """Was spaeter aufgegriffen wird, war eine Setzung, keine Ablenkung.

    Der Absatz steht an Position 6 -- jenseits von
    ``FOKUS_EINFUEHRUNG_BIS``, damit nicht die Einfuehrungs-Ausnahme greift,
    sondern wirklich der Rueckgriff geprueft wird.
    """
    absatz = ("Karim zeigt Lena seinen Schluesselanhaenger vom Schwimmbad "
              "und erzaehlt, dass er ihn seit dem Ferienlager nicht mehr "
              "abgelegt hat, auch nicht beim Duschen.")
    zweite = ("Jonas findet den Schluesselanhaenger vom Schwimmbad im Sand "
              "und gibt ihn Mira, ohne etwas zu sagen. Das Ferienlager ist "
              "seit Wochen vorbei.")
    lage = _fokuslage(conn, FOKUS_DANEBEN, zweite)
    erst = mechanik._erstauftritte(lage)

    marke = mechanik.einordnung(absatz, 6, 1, zweite, lage, erst)

    assert marke == "seitenstrang"


def test_spaeter_erstauftritt_ist_keine_einfuehrung_mehr(conn):
    """Wer in Absatz 9 zuerst auftaucht, wird nicht eingefuehrt -- da faengt
    die Szene einen neuen Schauplatz an, kurz vor ihrem Ende."""
    text = ("Mira wartet auf Jonas.\n\n"
            "Tom wirft einen Ball gegen die Mauer und trifft nicht.")
    lage = _fokuslage(conn, text)
    erst = mechanik._erstauftritte(lage)
    absatz = text.split("\n\n")[1]

    # Absatz 2 ist der Erstauftritt -> Einfuehrung.
    assert mechanik.einordnung(absatz, 2, 1, "", lage, erst) == "einfuehrung"
    # Derselbe Absatz an Position 9 gedacht: dort steht Tom laengst nicht
    # mehr zum ersten Mal, die Einfuehrungs-Ausnahme greift nicht.
    assert mechanik.einordnung(absatz, 9, 1, "", lage, erst) == "nebenschauplatz"


def test_setting_ohne_figuren_ist_kein_nebenschauplatz(conn):
    """Ein Ort darf beschrieben werden -- auch poetisch, auch laenger."""
    lage = _fokuslage(conn, FOKUS_DICHT)
    erst = mechanik._erstauftritte(lage)
    absatz = ("Der See ist im Oktober grau und riecht nach Oel, und die "
              "Moewen sitzen auf den Pollern wie hingestellt.")

    assert mechanik.einordnung(absatz, 1, 1, "", lage, erst) == "setting"


def test_kurze_allerweltswoerter_machen_keinen_seitenstrang(conn):
    """Gegenprobe zur Wortsuche: "Meter", "Leute", "Danach" kommen in jedem
    Text wieder vor und wuerden sonst jeden Absatz zum Strang erklaeren."""
    lage = _fokuslage(conn, FOKUS_DANEBEN)
    erst = mechanik._erstauftritte(lage)
    absatz = ("Lena zaehlt die Meter bis zum Ufer und sagt, es seien mehr "
              "Leute da als sonst. Danach setzt sie sich wieder hin.")
    spaeter = "Danach gingen alle. Es waren viele Leute, keine zwanzig Meter."

    marke = mechanik.einordnung(absatz, 7, 1, spaeter, lage, erst)

    assert marke == "nebenschauplatz"


def test_fokus_schweigt_ohne_hauptkonflikt(conn):
    """Ohne Konflikt ist unbestimmt, wovon ein Nebenschauplatz abweicht."""
    lage = _fokuslage(conn, FOKUS_DANEBEN)

    assert mechanik.fokus(lage, "") == []


def test_fokus_schweigt_wenn_der_konflikt_nur_eine_figur_nennt(conn):
    """Ein Konflikt braucht zwei Seiten -- sonst misst man Anwesenheit."""
    lage = _fokuslage(conn, FOKUS_DANEBEN)

    assert mechanik.fokus(lage, "Mira will dazugehoeren.") == []


def test_fokusanteil_zaehlt_absatzweise():
    traeger = ["Mira", "Jonas"]
    text = "Mira geht.\n\nKarim redet lange und sagt nichts.\n\nJonas kommt."

    mit, ohne, laengster = mechanik.fokusanteil(text, traeger)

    assert mit == len("Mira geht.") + len("Jonas kommt.")
    assert ohne == len("Karim redet lange und sagt nichts.")
    assert laengster.startswith("Karim")


def test_hauptkonflikt_ohne_arbeitsstand_ist_leer(conn):
    """Kein Arbeitsstand ist kein Fehler, sondern ein stummer Check."""
    assert mechanik.hauptkonflikt(conn, 999) == ""
