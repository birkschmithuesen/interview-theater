"""Tests fuer die Geschichte (seit 06.09.2026 der dritte Teil von Phase 4)
und den Ping-Pong derselben Phase.

**Erst erfinden, dann schaerfen** (Birk, 05.09.2026 nachts). Gemessen wird
hier die Erfindungsseite: dass der Bot in 4 und 5 offen fragt statt
vorzuschlagen, dass seine Vorschlaege **nur** aus Begriffen, Fragen und dem
schon Festgelegten kommen (pruefbar am gebauten Nutzertext), und dass aus
einem ``VORSCHLAG GESCHICHTE:``-Block beides entsteht: der Bogen im
Arbeitsstand UND die Szenenfolge in der Tabelle.

Kein Netzzugriff: Telegram und Sprachmodell sind Attrappen.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, szenenfolge, vorschlagssperre

from test_szenenfolge import TelegramAttrappe


@pytest.fixture(autouse=True)
def freie_vorschlagssperre():
    """Einige Tests hier loesen ``szenenfolge.starte_geschichte``/
    ``starte_geschichte_szenen`` wirklich aus (ueber ``knoepfe._wirke``/
    ``behandle``, chat_id=1) statt sie wegzupatchen -- kein Zustand aus
    einem frueheren Test soll die gemeinsame Vorschlagssperre besetzt
    lassen (wie ``tests/test_szenenfolge.py``)."""
    vorschlagssperre.vergiss(1)
    yield
    vorschlagssperre.vergiss(1)


GESCHICHTE = """Ich schlage euch das vor.

VORSCHLAG GESCHICHTE:
Zwei Freundinnen verlieren sich auf dem Weg nach Hause.
Ende: sie sehen sich nicht wieder, aber eine geht weiter
Im Treppenhaus — sie streiten sich um einen Schluessel — Mira, Pal — Dialog
Am Kiosk — Mira wartet allein — Mira — Monolog
Der Weg — alle erzaehlen dasselbe anders — Mira, Pal — Chor

Passt das so, oder soll es anders enden?"""


class LLMAttrappe:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = 0
        self.gesehen = {}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe += 1
        self.gesehen = {"system": system, "nutzer": nutzer, "art": art}
        return self.antwort


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def erfunden(conn):
    """Der Stand nach Phase 4: Begriffe, Fragen, Setting, zwei Figuren."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof, Winter")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Pal", "haelt an seiner Route fest")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T23:00:00")
    phasen.setze(conn, 1, 4, "test")
    return conn


def _druck(daten):
    return {
        "callback_query_id": "q1", "data": daten, "chat_id": 1,
        "chat_titel": "Testgruppe", "message_id": 777,
    }


def _knopf(tg, beschriftung):
    for _, _, leiste in tg.knoepfe:
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}, gesehen: {tg.beschriftungen}")


# --- der Eintritt: offene Frage zuerst ------------------------------------


@pytest.mark.parametrize("phase", [4])
def test_der_eintritt_fragt_offen_und_schlaegt_nichts_vor(conn, tg, einst, phase):
    """Der Bot faengt eine Erfindungsphase nicht mit einem Vorschlag an: erst
    die Frage, ob die Gruppe selbst schon Ideen hat -- \"Eigene Idee\" oder
    \"Schlag du vor\"."""
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", phase)

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf(tg, tg.beschriftungen[0])))

    # Der Phasenrahmen steht davor, die Frage darunter -- EINE Nachricht
    # (06.09.2026).
    assert tg.gesendet[-1][1].startswith(
        f"\u25b6\ufe0f Phase {phase} von {phasen.LETZTE}"
    )
    assert tg.gesendet[-1][1].endswith(knoepfe._TEXT_PROAKTIV)
    # Keine Einstiegsknoepfe mehr unter der offenen Frage (Birk, 06.09.2026).
    assert "Ja, wir zuerst" not in tg.beschriftungen
    assert "Schlag du vor" not in tg.beschriftungen


def test_der_eintritt_traegt_keine_knoepfe(conn, tg, einst):
    """Unter einer offenen Frage steht nichts Antippbares (Birk, 11:10)."""
    knoepfe.biete_proaktiv(conn, tg, 1, 4)

    assert tg.knoepfe == []
    assert tg.gesendet[-1][1] == knoepfe._TEXT_PROAKTIV


# --- Vorschlaege kommen NUR aus Begriffen, Fragen und Festgelegtem --------


def test_der_geschichte_prompt_enthaelt_kein_material(erfunden, tg, einst):
    """**Der Kontext-Filter der Erfindungsphase, im Code und nicht nur im Prompt.**
    Der Nutzertext traegt Begriffe, Fragen, Setting und Figuren -- und weder
    Verdichtung noch Zitat noch Transkript."""
    kopf_id = repo.lege_interview_an(erfunden, 1)
    repo.setze_transkript(erfunden, kopf_id, "Ich hatte nur einen Koffer dabei.")
    repo.speichere_verdichtung(
        erfunden, 1, kopf_id, "Sie erzaehlt vom Ankommen.",
        [{"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer dabei.",
          "zitat_geprueft": 1}],
    )

    nutzer = szenenfolge.baue_nutzertext_geschichte(erfunden, 1)

    assert "Begriffe der Gruppe: Koffer, Bahnhof, Winter" in nutzer
    assert "Was war in deinem Koffer?" in nutzer
    assert "Setting: Ein Treppenhaus, nachts" in nutzer
    assert "Mira" in nutzer
    # Und nichts aus dem Material.
    assert "Ankommen" not in nutzer
    assert "Ich hatte nur einen Koffer dabei." not in nutzer
    assert "Sie erzaehlt vom Ankommen." not in nutzer


def test_die_anweisung_verbietet_das_material_ausdruecklich(erfunden):
    system = szenenfolge.systemanweisung_geschichte()

    assert "VORSCHLAG GESCHICHTE:" in system
    assert "frei" in system
    assert "Interviews" in system


def test_schlag_du_vor_in_phase_4_geht_ueber_die_geschichte(erfunden, tg, einst):
    """Steht die Figurenliste, meint "Schlag du vor" in Phase 4 die
    GESCHICHTE (``offene_art``) -- und Zusage 2 gilt weiter: der Handler
    ruft kein Modell, ``starte_geschichte`` kuendigt an und gibt an einen
    Thread ab."""
    klm = LLMAttrappe(GESCHICHTE)
    knoepfe.biete_proaktiv(erfunden, tg, 1, 4)

    knoepfe._wirke(
        erfunden, tg, klm, einst,
        {"art": knoepfe.ART_SCHLAG_VOR, "wert": "4"}, 1,
    )
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()

    assert klm.aufrufe == 1
    assert klm.gesehen["art"] == szenenfolge.ART_GESCHICHTE


# --- der Marker: Bogen, Ende und Szenenfolge ------------------------------


def test_zerlege_geschichte_trennt_bogen_ende_und_szenen():
    from interview_theater import vorschlag

    wert = vorschlag.lies(GESCHICHTE, "geschichte")
    geschichte, zeilen = szenenfolge.zerlege_geschichte(wert)

    assert geschichte == (
        "Zwei Freundinnen verlieren sich auf dem Weg nach Hause.\n"
        "Ende: sie sehen sich nicht wieder, aber eine geht weiter"
    )
    assert [z[0] for z in zeilen] == ["Im Treppenhaus", "Am Kiosk", "Der Weg"]
    assert [z[3] for z in zeilen] == ["dialog", "monolog", "chor"]


def test_ohne_ende_zeile_bleibt_der_bogen_allein():
    """Geraten wird nichts: laesst das Modell die Ende-Zeile weg, steht sie
    auch nicht da."""
    geschichte, zeilen = szenenfolge.zerlege_geschichte(
        "Zwei verlieren sich.\nTitel — was passiert — Mira — Dialog"
    )

    assert geschichte == "Zwei verlieren sich."
    assert len(zeilen) == 1


def test_der_vorschlag_traegt_anzahl_reihenfolge_und_die_grundleiste(erfunden, tg):
    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)

    assert tg.beschriftungen == [
        knoepfe.TEXT_ANZAHL_KNOPF, knoepfe.TEXT_REIHENFOLGE_KNOPF,
        "Ja, speichern", "Nein, nochmal aendern",
    ]
    # Die Markerzeile geht nie in den Chat.
    assert "VORSCHLAG GESCHICHTE:" not in tg.knoepfe[-1][1]
    assert "Zwei Freundinnen verlieren sich" in tg.knoepfe[-1][1]


def test_ohne_marker_gibt_es_keine_leiste(erfunden, tg):
    """Kein Raten: lieber ein Vorschlag ohne Knoepfe als Knoepfe, die den
    falschen Text speichern."""
    knoepfe.sende_geschichte(erfunden, tg, 1, "Ich haette da eine Idee.")

    assert tg.knoepfe == []


# --- die Uebernahme: Arbeitsstand UND Szenen ------------------------------


def test_gefaellt_uns_weiter_speichert_geschichte_und_szenen(erfunden, tg, einst):
    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Ja, speichern"))
    )

    stand = repo.hole_arbeitsstand(erfunden, 1)
    assert stand["geschichte"].startswith("Zwei Freundinnen verlieren sich")
    assert "Ende: sie sehen sich nicht wieder" in stand["geschichte"]
    szenen = repo.hole_szenen(erfunden, 1)
    assert [s["titel"] for s in szenen] == ["Im Treppenhaus", "Am Kiosk", "Der Weg"]
    # Die Form ist ein VORSCHLAG (Birk, 06.09.2026): bestaetigt wird sie
    # Szene fuer Szene per Knopf, ``form`` bleibt bis dahin leer.
    assert [s["form"] for s in szenen] == [None, None, None]
    assert [s["form_vorschlag"] for s in szenen] == ["dialog", "monolog", "chor"]
    # Die Besetzung kommt aus der dritten Spalte, soweit die Namen bekannt sind.
    assert [f["name"] for f in repo.szene_figuren(erfunden, szenen[1]["id"])] == ["Mira"]


def test_erst_die_geschichte_gibt_die_schaerfung_frei(erfunden, tg, einst):
    assert phasen.voraussetzungen(erfunden, 1)[5] is False

    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)
    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Ja, speichern"))
    )

    assert phasen.voraussetzungen(erfunden, 1)[5] is True
    # Seit 06.09.2026 13:15 wird die NAECHSTE Stufe angeboten: erst
    # schaerfen (5), dann die Prosa (6).
    assert tg.beschriftungen == ["Weiter zu Schaerfung"]


def test_nein_nochmal_aendern_speichert_nicht(erfunden, tg, einst):
    """Neue Regel (06.09.2026, Birk 11:00): "Nein" schreibt nichts und macht
    den Weg frei."""
    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Nein, nochmal aendern"))
    )

    stand = repo.hole_arbeitsstand(erfunden, 1)
    assert not (stand and (stand["geschichte"] or "").strip())


def test_eine_richtung_wird_gespeichert_und_legt_noch_keine_szenen_an(
    erfunden, tg, einst
):
    """Der neue Weg (06.09.2026, Birk 11:42): die Geschichte kommt als drei
    Richtungen, gespeichert wird die gewaehlte -- die Szenenfolge ist der
    naechste, eigene Schritt."""
    knoepfe.sende_geschichte(
        erfunden, tg, 1, "VORSCHLAG GESCHICHTE:\nZwei verlieren sich."
    )

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Ja, speichern"))
    )

    assert repo.hole_arbeitsstand(erfunden, 1)["geschichte"] == "Zwei verlieren sich."
    assert repo.hole_szenen(erfunden, 1) == []


DREI_RICHTUNGEN = """Woran wollt ihr entlang?

VORSCHLAG GESCHICHTE:
Der lange Weg — Mira geht, Pal bleibt. Am Ende sieht keiner den anderen wieder.
Zurueck — Beide kehren um, aber zu spaet. Das Ende ist ein Schweigen.
Der Schluessel — Sie streiten um eine Wohnung, die keinem gehoert. Offenes Ende.
"""


def test_die_geschichte_kommt_als_menue_mit_drei_richtungen(erfunden, tg):
    knoepfe.sende_geschichte(erfunden, tg, 1, DREI_RICHTUNGEN)

    assert tg.beschriftungen == [
        "1 · Der lange Weg", "2 · Zurueck", "3 · Der Schluessel", "Anders",
    ]
    # Kein Sammelknopf: nie still die erste Richtung.
    assert "Ja, speichern" not in tg.beschriftungen


def test_eine_gewaehlte_richtung_startet_die_szenenfolge(erfunden, tg, einst):
    """Nach der Wahl kommt die Szenenfolge als eigener Vorschlag -- und der
    Handler ruft dafuer kein Modell (Zusage 2), sondern gibt an einen Thread
    ab."""
    klm = LLMAttrappe(
        "VORSCHLAG SZENENFOLGE:\nIm Treppenhaus — sie streiten — Mira, Pal — Dialog — Begegnung"
    )
    knoepfe.sende_geschichte(erfunden, tg, 1, DREI_RICHTUNGEN)

    knoepfe.behandle(
        erfunden, tg, klm, einst, _druck(_knopf(tg, "2 · Zurueck"))
    )
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()

    assert repo.hole_arbeitsstand(erfunden, 1)["geschichte"].startswith("Zurueck")
    assert klm.aufrufe == 1
    assert klm.gesehen["art"] == szenenfolge.ART


# --- die Form ist ein Vorschlag, keine Entscheidung (06.09.2026) ----------


def test_die_szenen_werden_ohne_bestaetigte_form_angelegt(erfunden, tg, einst):
    """Birk, 06.09.2026 00:30: "Die Form Monolog habe ich niemals eingegeben
    und aktiv bestaetigt." Der Vorschlag steht in ``form_vorschlag``, ``form``
    bleibt leer -- gesetzt wird sie allein durch einen Knopfdruck."""
    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Ja, speichern"))
    )

    szenen = repo.hole_szenen(erfunden, 1)
    assert [s["form"] for s in szenen] == [None, None, None]
    assert [s["form_vorschlag"] for s in szenen] == ["dialog", "monolog", "chor"]


def test_die_begruendung_des_formvorschlags_wird_mitgespeichert(erfunden, tg, einst):
    """Die Gruppe soll sehen, WARUM der Bot eine Form vorschlaegt, bevor sie
    drueckt -- sonst waere der Knopf eine Formalie."""
    knoepfe.sende_geschichte(
        erfunden, tg, 1,
        "VORSCHLAG GESCHICHTE:\nZwei verlieren sich.\nEnde: offen\n"
        "Im Treppenhaus — sie streiten — Mira, Pal — Dialog — zwei, die sich "
        "widersprechen",
    )

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Ja, speichern"))
    )

    szene = repo.hole_szenen(erfunden, 1)[0]
    assert szene["form_vorschlag_grund"] == "zwei, die sich widersprechen"


def test_ohne_bestaetigte_form_wird_nicht_geschrieben(erfunden, tg, einst):
    """Die Sperre (``szene.PFLICHTFELDER``): ``form`` ist Pflichtfeld, und
    ein Formvorschlag ist keine Form.

    **Im Feinschliff** (Phase 7) -- in Phase 6 entsteht die Szene als
    Geschichte, dort wird die Form gar nicht verlangt (06.09.2026, 10:30)."""
    from interview_theater import phasen, szene

    phasen.setze(erfunden, 1, 7, "befehl")
    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)
    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Ja, speichern"))
    )

    ziel = repo.hole_szenen(erfunden, 1)[0]
    felder, _ = szene.fehlendes(erfunden, ziel)

    assert "form" in felder
    assert szene.sperrtext(erfunden, ziel) is not None


# --- die Grundleiste haengt unter dem WERT, nicht unter der Antwort ------


class _ErkennerAttrappe:
    def __init__(self, aenderungen):
        self.aenderungen = aenderungen

    def schema(self, *a, **k):
        return {"aenderungen": self.aenderungen}


def test_die_notiert_meldung_traegt_die_grundleiste(erfunden, tg, einst):
    """Live-Befund 05.09.2026 23:37: der Erkenner-Nachlauf laeuft NACH der
    Gespraechsantwort. Speicherte er einen Ping-Pong-Wert, hing die
    Grundleiste unter der Antwort davor -- unter einem Text, der den Wert noch
    gar nicht kannte -- und die Nachricht mit dem Wert stand nackt da. Jetzt
    haengt sie dort, wo der Wert steht."""
    from interview_theater import erkenner

    repo.merke_nachricht(
        erfunden, 1, 42, "Ada", 0, "text", "zwei verlieren sich, offenes ende",
        repo._jetzt(),
    )
    klm = _ErkennerAttrappe([
        {"art": "geschichte_setzen", "wert": "Zwei verlieren sich."},
    ])

    erkenner.laufe(klm, tg, erfunden, einst, 1)

    assert repo.hole_arbeitsstand(erfunden, 1)["geschichte"] == "Zwei verlieren sich."
    assert "Geschichte: Zwei verlieren sich." in tg.knoepfe[-1][1]
    # Seit Karte U (01.10.2026) steht der Undo-Knopf als ruhige letzte Zeile
    # unter der Grundleiste -- die Grundleiste selbst ist unveraendert.
    assert tg.beschriftungen == [
        "Ja, speichern", "Nein, nochmal aendern", "Rueckgaengig",
    ]


def test_ohne_offene_art_bleibt_die_meldung_nackt(erfunden, tg, einst):
    """Kein Knopf um des Knopfes willen: was in dieser Phase nicht offen ist,
    bekommt auch keine Leiste."""
    from interview_theater import erkenner

    repo.merke_nachricht(
        erfunden, 1, 43, "Ada", 0, "text", "es geht um bleiben gegen gehen",
        repo._jetzt(),
    )
    klm = _ErkennerAttrappe([
        {"art": "hauptkonflikt_setzen", "wert": "bleiben gegen gehen"},
    ])

    erkenner.laufe(klm, tg, erfunden, einst, 1)

    # Keine Grundleiste -- aber seit Karte U (01.10.2026) der Undo-Knopf als
    # einzige Zeile: jeder gespeicherte Wert muss mit einem Tipp
    # zuruecknehmbar sein, auch ohne offene Ping-Pong-Art.
    assert [[b for b, _ in leiste] for _, _, leiste in tg.knoepfe] == [
        ["Rueckgaengig"],
    ]
    assert any("bleiben gegen gehen" in t for _, t in tg.gesendet)


# --- Die Szenen INNERHALB einer Richtungszeile (30.09.2026, C9) -----------
#
# Die Praemissenpruefung zu dieser Massnahme steht in
# docs/superpowers/plans/2026-09-30-padua-a5-dortmund-reste.md: die Zeile
# ``if not alter_block: zeilen = []`` verwirft heute nichts (auf dem
# Menue-Weg ist der wert immer einzeilig). Was wirklich verlorengeht, sind
# Szenen, die eine Richtung INNERHALB ihrer Zeile nennt.

RICHTUNG_MIT_SZENEN = (
    "Nacht am Kanal — Mira stellt sich, Pal gesteht, am Ende bleiben beide. "
    "Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis. "
    "Szene 3: Der Morgen danach."
)
RICHTUNG_MIT_SZENEN_UND_FORMEN = (
    "Nacht am Kanal — Mira stellt sich, Pal gesteht. "
    "Szene 1: Ankunft am Steg (Dialog). Szene 2: Das Gestaendnis (Monolog)."
)


def test_szenen_in_zeile_liest_titel_und_form():
    assert szenenfolge.szenen_in_zeile(RICHTUNG_MIT_SZENEN) == [
        (1, "Ankunft am Steg", ""),
        (2, "Das Gestaendnis", ""),
        (3, "Der Morgen danach", ""),
    ]
    assert szenenfolge.szenen_in_zeile(RICHTUNG_MIT_SZENEN_UND_FORMEN) == [
        (1, "Ankunft am Steg", "dialog"),
        (2, "Das Gestaendnis", "monolog"),
    ]
    # Mutationsnachweis (Schritt 6.3): ein ungebundener Formname wuerde
    # "Der Chor am Morgen" auf "Der am Morgen" verstuemmeln -- die Form wird
    # nur am ENDE eines Stuecks gelesen.
    assert szenenfolge.szenen_in_zeile(
        "Bogen. Szene 1: Ankunft (Dialog). Szene 2: Der Chor am Morgen (Chor)."
    ) == [(1, "Ankunft", "dialog"), (2, "Der Chor am Morgen", "chor")]


def test_szenen_in_zeile_erkennt_eng():
    """Eine Handlung bleibt eine Handlung: eine einzelne Szenennennung, eine
    Formenkette ohne Titel und eine Zeile ohne Szenen ergeben nichts.

    Die Fehlerrichtung ist bewusst gewaehlt -- eine nicht erkannte
    Szenennennung kostet, was sie heute kostet; eine faelschlich erkannte
    kostet die Handlung."""
    assert szenenfolge.szenen_in_zeile("Nur eine: Szene 1: Ankunft am Steg.") == []
    assert szenenfolge.szenen_in_zeile("Chor-Dialog-Rap ueber drei Szenen") == []
    assert szenenfolge.szenen_in_zeile(
        "Ein Bogen ohne Szenen: Mira geht, Pal bleibt, am Ende regnet es."
    ) == []
    assert szenenfolge.szenen_in_zeile("") == []


def test_szenen_in_zeile_verlangt_zusammenhaengende_nummern_ab_eins():
    """``repo.gleiche_szenenfolge_ab`` nummeriert nach Position in der Liste
    (repo.py:2350). "Szene 2" und "Szene 4" wuerden daraus 1 und 2 -- falsche
    Zuordnung ist schlimmer als keine."""
    assert szenenfolge.szenen_in_zeile(
        "Ein Bogen. Szene 2: Ankunft. Szene 4: Abschied."
    ) == []


def test_richtungswahl_speichert_die_szenen_der_zeile_mit(erfunden, tg, einst):
    """Der Kern von C9: nach dem Druck stehen Geschichte UND Szenen da.

    Und: kein zweiter, teurer Folge-Lauf -- ``titel`` ist nicht geschuetzt,
    ein frischer Vorschlag wuerde die Titel der Gruppe ueberschreiben."""
    conn = erfunden
    klm = LLMAttrappe("")
    knoepfe._wirke(
        conn, tg, klm, einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}{RICHTUNG_MIT_SZENEN}"},
        1,
    )

    stand = repo.hole_arbeitsstand(conn, 1)
    assert "Nacht am Kanal" in stand["geschichte"]
    assert "Szene 1" in stand["geschichte"]  # die ganze Zeile IST die Richtung

    titel = [(s["nummer"], s["titel"]) for s in repo.hole_szenen(conn, 1)]
    assert titel == [
        (1, "Ankunft am Steg"), (2, "Das Gestaendnis"), (3, "Der Morgen danach")
    ]
    assert klm.aufrufe == 0, "kein zweiter Folge-Lauf nach der Uebernahme"


def test_die_form_aus_der_zeile_ist_gesetzt_nicht_vorgeschlagen(erfunden, tg, einst):
    """Die Regel aus 3290d70: der Vorschlag eines MODELLS bleibt aus
    ``szene.form`` heraus -- die Wahl der GRUPPE nicht, und hier hat sie
    gedrueckt. Ohne Form in der Zeile bleibt ``form`` leer."""
    conn = erfunden
    knoepfe._wirke(
        conn, tg, LLMAttrappe(""), einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}{RICHTUNG_MIT_SZENEN_UND_FORMEN}"},
        1,
    )
    formen = {s["nummer"]: (s["form"] or "") for s in repo.hole_szenen(conn, 1)}
    assert formen == {1: "dialog", 2: "monolog"}


def test_eine_richtung_ohne_szenen_startet_weiter_den_folge_lauf(erfunden, tg, einst):
    """Der Regelfall bleibt, wie er ist: eine Richtung ohne Szenen fuehrt in
    ``starte_geschichte_szenen``."""
    conn = erfunden
    klm = LLMAttrappe(
        "VORSCHLAG SZENENFOLGE:\nAm Steg — sie treffen sich — Mira — Dialog"
    )
    knoepfe._wirke(
        conn, tg, klm, einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}Nacht am Kanal — Mira stellt sich, "
                 "Pal gesteht, am Ende bleiben beide."},
        1,
    )
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()
    assert klm.aufrufe == 1
    assert klm.gesehen["art"] == szenenfolge.ART


def test_eine_reine_formabfolge_bleibt_die_formwahl(erfunden, tg, einst):
    """Die Praezedenz von 3290d70 bleibt: eine Zeile, die NUR eine Formwahl
    ueber Szenen beschreibt, geht weiter in ``_uebernimm_formwahl`` -- die
    Geschichte bleibt dort leer, und das ist die gemessene Entscheidung
    (docs/analyse-phase4-datenverlust-2026-09-06.md § 2.1)."""
    conn = erfunden
    knoepfe._wirke(
        conn, tg, LLMAttrappe(""), einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}Szene 1: Chor mit Dance. "
                 "Szene 2: Dialog mit Einschueben. Szene 3: Rap eskaliert."},
        1,
    )
    zeile = conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert zeile is not None and zeile["art"] == "geschichte_war_formwahl"


# --- Fix-Runde zu C9: die Formwahl bleibt vorn ---------------------------
#
# Die erste Fassung unterschied Formwahl und Richtung nur daran, ob vor dem
# ersten "Szene N" ein Satz steht. Die drei Zeilen unten haben einen und sind
# trotzdem Formwahlen -- die Wahl ging verloren.

FORMWAHL_MIT_KETTE = "Chor-Dialog-Rap — Szene 1: Chor, Szene 2: Dialog, Szene 3: Rap"
FORMWAHL_MIT_ZUSAETZEN = (
    "Drei Formen: Szene 1: Chor mit Dance. Szene 2: Dialog mit Einschueben. "
    "Szene 3: Rap eskaliert."
)
FORMWAHL_NACH_BOGEN = "Bogen. Szene 1: Ankunft — Dialog. Szene 2: Rap"


def _druecke_richtung(conn, tg, einst, zeile):
    knoepfe._wirke(
        conn, tg, LLMAttrappe(""), einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}{zeile}"},
        1,
    )


def _vorfaelle(conn):
    return [z["art"] for z in conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = 1 ORDER BY id"
    )]


@pytest.mark.parametrize("zeile, erwartet", [
    (FORMWAHL_MIT_KETTE, [(1, "chor"), (2, "dialog"), (3, "rap")]),
    (FORMWAHL_MIT_ZUSAETZEN, [(1, "chor"), (2, "dialog"), (3, "rap")]),
    (FORMWAHL_NACH_BOGEN, [(1, "dialog"), (2, "rap")]),
])
def test_eine_formwahl_mit_vorspann_bleibt_die_formwahl(
    erfunden, tg, einst, zeile, erwartet
):
    conn = erfunden
    nummern_vorher = {s["nummer"] for s in repo.hole_szenen(conn, 1)}
    _druecke_richtung(conn, tg, einst, zeile)

    assert "geschichte_war_formwahl" in _vorfaelle(conn)
    stand = repo.hole_arbeitsstand(conn, 1)
    assert not stand["geschichte"], "Menuezeile nicht als Geschichte"
    # Keine Formwahl verloren: szene.form oder Festlegung (Bestandsweg).
    formen = {s["nummer"]: (s["form"] or "") for s in repo.hole_szenen(conn, 1)}
    festgelegt = " ".join(z["text"] for z in repo.festlegungen(conn, 1))
    for nummer, form in erwartet:
        assert formen.get(nummer) == form or f"Szene {nummer}: {form}" in festgelegt
    # Und keine Szenen mit Titeln wie "Chor mit Dance".
    assert {s["nummer"] for s in repo.hole_szenen(conn, 1)} == nummern_vorher


def test_szenen_der_richtung_grenzt_die_formwahl_ab():
    assert szenenfolge.szenen_der_richtung(FORMWAHL_MIT_KETTE) == []
    assert szenenfolge.szenen_der_richtung(FORMWAHL_MIT_ZUSAETZEN) == []
    assert szenenfolge.szenen_der_richtung(FORMWAHL_NACH_BOGEN) == []
    assert szenenfolge.szenen_der_richtung(RICHTUNG_MIT_SZENEN_UND_FORMEN) == [
        (1, "Ankunft am Steg", "dialog"), (2, "Das Gestaendnis", "monolog"),
    ]
    assert len(szenenfolge.szenen_der_richtung(RICHTUNG_MIT_SZENEN)) == 3


def test_eine_bestaetigte_form_bleibt_stehen(erfunden, tg, einst):
    """``lege_inline_an`` setzt nur eine LEERE Form: was die Gruppe per Knopf
    bestaetigt hat, ueberschreibt eine spaeter gewaehlte Richtung nicht."""
    conn = erfunden
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "rap")
    _druecke_richtung(conn, tg, einst, RICHTUNG_MIT_SZENEN_UND_FORMEN)
    formen = {s["nummer"]: (s["form"] or "") for s in repo.hole_szenen(conn, 1)}
    assert formen[1] == "rap"
    assert formen[2] == "monolog"


@pytest.mark.parametrize("zeile", [
    "Ein Bogen. Szene 1: Ankunft. Szene 2: Streit. Szene 4: Abschied.",
    "Ein Bogen. Szene 1: Ankunft. Szene 1: Streit.",
])
def test_luecken_in_der_nummerierung_hinterlassen_einen_vorfall(
    erfunden, tg, einst, zeile
):
    conn = erfunden
    _druecke_richtung(conn, tg, einst, zeile)
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()
    assert szenenfolge.VORFALL_RICHTUNG_UNVOLLSTAENDIG in _vorfaelle(conn)


def test_eine_lueckenlose_richtung_hinterlaesst_keinen_vorfall(erfunden, tg, einst):
    conn = erfunden
    _druecke_richtung(conn, tg, einst, RICHTUNG_MIT_SZENEN)
    assert szenenfolge.VORFALL_RICHTUNG_UNVOLLSTAENDIG not in _vorfaelle(conn)


def test_ein_zu_langer_titel_ist_fliesstext():
    lang = "x" * (szenenfolge.TITEL_MAX + 1)
    assert szenenfolge.szenen_in_zeile(
        f"Bogen. Szene 1: Ankunft. Szene 2: {lang}."
    ) == []
    genau = "y" * szenenfolge.TITEL_MAX
    assert szenenfolge.szenen_in_zeile(
        f"Bogen. Szene 1: Ankunft. Szene 2: {genau}."
    ) == [(1, "Ankunft", ""), (2, genau, "")]
    assert szenenfolge.szenen_in_zeile(
        "Pal wartet am Steg. Szene 1: Ankunft. Und dann kommt es so, weil er in "
        "Szene 2: nie wieder zurueckkommen will, obwohl Mira ihn ruft und die "
        "ganze Nacht am Kanal auf ihn wartet und wartet."
    ) == []


def test_eine_formwahl_mit_luecke_hinterlaesst_nur_den_formwahl_vorfall(
    erfunden, tg, einst,
):
    """Eine Formabfolge mit Luecke ist eine Formwahl, keine unvollstaendige
    Szenenliste: EIN Vorfall (``geschichte_war_formwahl``), nicht zwei."""
    conn = erfunden
    _druecke_richtung(
        conn, tg, einst, "Szene 1: Chor mit Dance, Szene 3: Rap eskaliert",
    )
    vorfaelle = _vorfaelle(conn)
    assert "geschichte_war_formwahl" in vorfaelle
    assert szenenfolge.VORFALL_RICHTUNG_UNVOLLSTAENDIG not in vorfaelle
