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

from interview_theater import knoepfe, phasen, repo, szenenfolge

from test_szenenfolge import TelegramAttrappe


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
    assert tg.beschriftungen == ["Ja, wir zuerst", "Schlag du vor"]


def test_wir_zuerst_ruft_kein_modell(conn, tg, einst):
    knoepfe.biete_proaktiv(conn, tg, 1, 4)

    knoepfe.behandle(
        conn, tg, None, einst, _druck(_knopf(tg, "Ja, wir zuerst"))
    )

    assert tg.gesendet[-1][1] == knoepfe._TEXT_WIR_ZUERST


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

    knoepfe.behandle(
        erfunden, tg, klm, einst, _druck(_knopf(tg, "Schlag du vor"))
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
        "Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter",
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
        erfunden, tg, None, einst, _druck(_knopf(tg, "Gefaellt uns, weiter"))
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
        erfunden, tg, None, einst, _druck(_knopf(tg, "Gefaellt uns, weiter"))
    )

    assert phasen.voraussetzungen(erfunden, 1)[5] is True
    # Angeboten wird die hoechste moegliche Stufe; die Schaerfung ist ein
    # Angebot, keine Pflicht, deshalb steht hier der Weg zu den Szenentexten.
    assert tg.beschriftungen == ["Weiter zu Szenentexte"]


def test_passt_aber_anders_speichert_trotzdem_und_fragt(erfunden, tg, einst):
    """Dieselbe Regel wie ueberall (05.09.2026 abends): damit ueberhaupt
    etwas in der Datenbank steht, auch wenn die Gruppe danach abbricht."""
    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Passt, aber anders"))
    )

    assert repo.hole_arbeitsstand(erfunden, 1)["geschichte"]
    assert repo.hole_arbeitsstand(erfunden, 1)["aenderung_offen"] == "geschichte"


def test_ein_vorschlag_ohne_szenen_wird_nicht_gespeichert(erfunden, tg, einst):
    """Eine Geschichte ohne Szenenfolge ist eine halbe Entscheidung -- und
    eine halbe Festlegung im Arbeitsstand ist schlimmer als gar keine."""
    knoepfe.sende_geschichte(
        erfunden, tg, 1, "VORSCHLAG GESCHICHTE:\nZwei verlieren sich."
    )

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Gefaellt uns, weiter"))
    )

    assert not (repo.hole_arbeitsstand(erfunden, 1)["geschichte"] or "")
    assert repo.hole_szenen(erfunden, 1) == []


# --- die Form ist ein Vorschlag, keine Entscheidung (06.09.2026) ----------


def test_die_szenen_werden_ohne_bestaetigte_form_angelegt(erfunden, tg, einst):
    """Birk, 06.09.2026 00:30: "Die Form Monolog habe ich niemals eingegeben
    und aktiv bestaetigt." Der Vorschlag steht in ``form_vorschlag``, ``form``
    bleibt leer -- gesetzt wird sie allein durch einen Knopfdruck."""
    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)

    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Gefaellt uns, weiter"))
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
        erfunden, tg, None, einst, _druck(_knopf(tg, "Gefaellt uns, weiter"))
    )

    szene = repo.hole_szenen(erfunden, 1)[0]
    assert szene["form_vorschlag_grund"] == "zwei, die sich widersprechen"


def test_ohne_bestaetigte_form_wird_nicht_geschrieben(erfunden, tg, einst):
    """Die Sperre (``szene.PFLICHTFELDER``): ``form`` ist Pflichtfeld, und
    ein Formvorschlag ist keine Form."""
    from interview_theater import szene

    knoepfe.sende_geschichte(erfunden, tg, 1, GESCHICHTE)
    knoepfe.behandle(
        erfunden, tg, None, einst, _druck(_knopf(tg, "Gefaellt uns, weiter"))
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
    assert tg.beschriftungen == [
        "Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter",
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

    assert tg.knoepfe == []
    assert any("bleiben gegen gehen" in t for _, t in tg.gesendet)
