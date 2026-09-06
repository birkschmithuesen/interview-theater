"""Tests zum Nachtrag vom 06.09.2026, 09:55 (Birk): was nach einem Interview
im Chat steht.

Der Anlass: die Verdichtung lief seit dem 05.09. sofort, aber im Chat stand
nur "ich halte mich damit zurueck" -- die Gruppe erfuhr nie, ob ueberhaupt
etwas herausgekommen war, und hatte keinen Weg, den Wortlaut gegenzupruefen.

Jetzt: EINE knappe Zeile mit der Zaehlung ("Interview 1 ausgewertet: 2
Themen, 2 Zitate.") und darunter die Knoepfe "Zusammenfassung zeigen" ·
"Transkript zeigen" · "Naechstes Interview" · "Weiter zu ...". Der alte
Knopf "Auswerten" ist raus -- er hiess nach einer Handlung, die schon
passiert war. Die art bleibt im Code fuer den Sonderfall unter
``aufnahme.MINDEST_WOERTER`` ("Trotzdem auswerten").

**Kein Verdichtungs-Volltext ohne Knopfdruck** -- das bleibt die Entscheidung
vom 05.09.2026 und wird hier mitgeprueft.
"""

import pytest

from interview_theater import aufnahme, knoepfe, phasen, phasentexte, repo

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


TRANSKRIPT = (
    "Ich bin mit vierzehn hergekommen und habe die Sprache auf der Strasse "
    "gelernt, nicht in der Schule. Meine Mutter hat zwanzig Jahre genaeht "
    "und keiner hat sie je gefragt, wie es ihr dabei ging."
)


def _ausgewertetes_interview(conn, themen=None):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_aufnahme_name(conn, kopf_id, "Interview 1")
    repo.setze_transkript(conn, kopf_id, TRANSKRIPT)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(
        conn, 1, kopf_id, "Sie erzaehlt vom Ankommen.",
        themen if themen is not None else [
            {"thema": "Ankommen", "beleg_zitat": "Ich bin mit vierzehn hergekommen",
             "zitat_geprueft": 1},
            {"thema": "Arbeit", "beleg_zitat": "zwanzig Jahre genaeht",
             "zitat_geprueft": 1},
        ],
    )
    return kopf_id


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
    raise AssertionError(
        f"kein Knopf {beschriftung!r}, gesehen: "
        f"{[b for _, _, l in tg.knoepfe for b, _ in l]}"
    )


# --- Die automatische Zeile mit der Zaehlung ------------------------------


def test_die_zeile_nennt_themen_und_zitate(conn, einst, tg):
    kopf_id = _ausgewertetes_interview(conn)
    phasen.setze(conn, 1, 3, "befehl")

    aufnahme._sende_nach_interview(
        conn, tg, einst, 1,
        aufnahme._TEXT_AUSGEWERTET.format(name="Interview 1", themen=2, zitate=2),
        kopf_id,
    )

    assert tg.gesendet[-1][1] == "Interview 1 ausgewertet: 2 Themen, 2 Zitate."


def test_zitate_werden_nur_gezaehlt_wenn_sie_geprueft_sind(conn, einst, tg, klm=None):
    """``zitat_geprueft`` ist die wichtigste Qualitaetszahl des Projekts --
    ein erfundenes Zitat darf in dieser Zeile nicht mitzaehlen."""
    kopf_id = _ausgewertetes_interview(conn, themen=[
        {"thema": "Ankommen", "beleg_zitat": "Ich bin mit vierzehn hergekommen",
         "zitat_geprueft": 1},
        {"thema": "Schule", "beleg_zitat": "Das hat nie jemand gesagt",
         "zitat_geprueft": 0},
    ])
    themen = repo.themen_zu(conn, repo.verdichtungen(conn, 1)[0]["id"])

    geprueft = sum(
        1 for t in themen if t["zitat_geprueft"] == 1 and t["beleg_zitat"]
    )

    assert (len(themen), geprueft) == (2, 1)
    assert kopf_id


def test_kein_verdichtungstext_ohne_knopfdruck(conn, einst, tg):
    """Die Entscheidung vom 05.09.2026 gilt weiter: die Zeile sagt, DASS
    etwas da ist, nicht WAS."""
    kopf_id = _ausgewertetes_interview(conn)
    phasen.setze(conn, 1, 3, "befehl")

    aufnahme._sende_nach_interview(
        conn, tg, einst, 1,
        aufnahme._TEXT_AUSGEWERTET.format(name="Interview 1", themen=2, zitate=2),
        kopf_id,
    )

    texte = [t for _, t in tg.gesendet]
    assert not any("Sie erzaehlt vom Ankommen" in t for t in texte)
    assert not any("Ankommen" in t for t in texte)


# --- Die Knoepfe darunter -------------------------------------------------


def test_die_leiste_bietet_zusammenfassung_und_transkript(conn, einst, tg):
    kopf_id = _ausgewertetes_interview(conn)
    phasen.setze(conn, 1, 3, "befehl")

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ausgewertet.", kopf_id)

    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen[:2] == ["Zusammenfassung zeigen", "Transkript zeigen"]
    assert "Naechstes Interview" in beschriftungen
    assert "Auswerten" not in beschriftungen, "der alte Knopf ist raus"


def test_zusammenfassung_zeigen_spielt_die_verdichtung_aus(conn, einst, tg):
    """Derselbe Anzeigepfad wie bisher hinter "Auswerten"
    (``aufnahme.zeige_verdichtung``) -- reine Leseabfrage, kein
    Modellaufruf."""
    kopf_id = _ausgewertetes_interview(conn)
    phasen.setze(conn, 1, 3, "befehl")
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ausgewertet.", kopf_id)

    knoepfe.behandle(
        conn, tg, None, einst, _druck(_knopf(tg, "Zusammenfassung zeigen")),
    )

    text = tg.gesendet[-1][1]
    assert "Sie erzaehlt vom Ankommen" in text
    assert "Ankommen" in text and "Arbeit" in text


def test_transkript_zeigen_gibt_den_wortlaut(conn, einst, tg):
    kopf_id = _ausgewertetes_interview(conn)
    phasen.setze(conn, 1, 3, "befehl")
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ausgewertet.", kopf_id)

    knoepfe.behandle(
        conn, tg, None, einst, _druck(_knopf(tg, "Transkript zeigen")),
    )

    text = tg.gesendet[-1][1]
    assert "Interview 1, im Wortlaut:" in text
    assert "zwanzig Jahre genaeht" in text


def test_ein_langes_transkript_kommt_in_teilen(conn, einst, tg):
    """``telegram.NACHRICHT_GRENZE``: ein Wortlaut ueber der Grenze wird
    geteilt, nicht abgeschnitten."""
    from interview_theater import telegram as telegram_modul

    kopf_id = _ausgewertetes_interview(conn)
    lang = "Sie sagte etwas Langes und dann noch etwas. " * 300
    repo.setze_transkript(conn, kopf_id, lang)
    phasen.setze(conn, 1, 3, "befehl")
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ausgewertet.", kopf_id)
    vorher = len(tg.gesendet)

    knoepfe.behandle(
        conn, tg, None, einst, _druck(_knopf(tg, "Transkript zeigen")),
    )

    stuecke = [t for _, t in tg.gesendet[vorher:]]
    assert len(stuecke) > 1
    assert all(len(s) <= telegram_modul.NACHRICHT_GRENZE for s in stuecke)


def test_ohne_transkript_sagt_der_bot_es(conn, einst, tg):
    kopf_id = _ausgewertetes_interview(conn)
    repo.setze_transkript(conn, kopf_id, "")
    phasen.setze(conn, 1, 3, "befehl")
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ausgewertet.", kopf_id)

    knoepfe.behandle(
        conn, tg, None, einst, _druck(_knopf(tg, "Transkript zeigen")),
    )

    assert tg.gesendet[-1][1] == knoepfe._TEXT_KEIN_TRANSKRIPT


# --- Der Sonderfall unter der Mindestlaenge -------------------------------


def test_zu_kurz_bietet_trotzdem_auswerten(conn, einst, tg):
    """Ohne Verdichtung gibt es nichts zu zeigen, nur etwas zu erzwingen --
    ``ART_AUSWERTEN`` bleibt genau dafuer im Code."""
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_aufnahme_name(conn, kopf_id, "Interview 1")
    repo.setze_transkript(conn, kopf_id, "Ganz kurz.")
    repo.setze_status(conn, kopf_id, "fertig")
    phasen.setze(conn, 1, 3, "befehl")

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 war sehr kurz.", kopf_id)

    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen[0] == "Trotzdem auswerten"
    assert "Zusammenfassung zeigen" not in beschriftungen


def test_die_kurz_zeile_nennt_die_wortzahl(conn):
    assert aufnahme._TEXT_ZU_KURZ.format(name="Interview 1", woerter=8) == (
        "Interview 1 war sehr kurz (8 Woerter) - ich habe es nicht ausgewertet."
    )


# --- Die Einleitung der Phase 3 -------------------------------------------


def test_die_einleitung_kuendigt_das_gegenpruefen_an():
    """Birks Wortlaut vom 06.09.2026, mit dem Zusatzsatz aus 09:55."""
    text = phasentexte.EINLEITUNGEN[3]

    assert text.startswith("Jetzt fuehrt ihr die Interviews")
    assert "Aufnahme starten" in text
    assert "Interview beenden" in text
    assert "Am Ende steht zu jedem Interview eine Zusammenfassung." in text
    assert text.endswith(
        "Danach koennt ihr die Zusammenfassung und das Transkript ansehen "
        "und gegenpruefen."
    )
