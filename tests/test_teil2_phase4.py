"""Teil 2 der Live-Zusaetze vom 06.09.2026 (Birk, 11:42/12:00/12:20):
Geschichte als drei Richtungen, Setting als Vorgabe fuer die Szenenfelder,
Sprachstil je Figur mit Zitat und Beispielsatz.

Kein Netzzugriff: Telegram und Sprachmodell sind Attrappen.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, sprachstil, szene, szenenfolge

from test_szenenfolge import TelegramAttrappe


class LLMAttrappe:
    def __init__(self, antwort=""):
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


def _druck(daten):
    return {
        "callback_query_id": "q1", "data": daten, "chat_id": 1,
        "chat_titel": "Testgruppe", "message_id": 777,
    }


def _knopf(tg, beschriftung):
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}: {tg.beschriftungen}")


# --- Setting -> Szenenfelder (Birk, 12:00/12:05) --------------------------


def test_rahmenfelder_liest_ort_zeit_anlass():
    assert szene.rahmenfelder(
        "Ort: Treppenhaus, Zeit: nachts, Anlass: eine Party"
    ) == {"ort": "Treppenhaus", "zeit": "nachts", "anlass": "eine Party"}


def test_ein_setting_ohne_doppelpunkte_ist_der_ort():
    """Geraten wird nichts: ein Freitext-Setting beschreibt den Ort."""
    assert szene.rahmenfelder("Ein Treppenhaus, nachts") == {
        "ort": "Ein Treppenhaus, nachts"
    }


def test_neue_szenen_bekommen_ort_aus_dem_setting(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ort: Treppenhaus, Zeit: nachts")

    szenenfolge.lege_an(conn, 1, [("Ankunft", "sie kommen an", [], "dialog", "")])

    zeile = repo.hole_szenen(conn, 1)[0]
    assert zeile["ort"] == "Treppenhaus"
    assert zeile["zeit"] == "nachts"


def test_mit_setting_fehlt_der_ort_nie(conn):
    """Nie mehr "fehlt noch: Ort", wenn das Setting steht (Birk, 12:00)."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    zeile = repo.hole_szene(conn, szene_id)

    felder, _ = szene.fehlendes(conn, zeile)

    assert "ort" not in felder
    assert "was_passiert" in felder


# --- Sprachstil je Figur (Birk, 12:20) ------------------------------------


def _interview(conn, text="Ich sag das ganz kurz, immer kurz."):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, text)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(
        conn, 1, kopf_id, "Kurz und knapp",
        [{"thema": "Knappheit", "kurz": "kurz",
          "beleg_zitat": "Ich sag das ganz kurz", "zitat_geprueft": 1}],
    )
    return kopf_id


def test_stilmaterial_gibt_je_interview_hoechstens_ein_zitat(conn):
    """Stil ist nicht Material (Birk): ein Zitat je Interview, keine
    Verdichtungen, keine Zusammenfassungen."""
    _interview(conn)

    text = sprachstil.stilmaterial(conn, 1)

    assert "Ich sag das ganz kurz" in text
    assert "Kurz und knapp" not in text, "keine Verdichtung"


def test_ohne_geprueftes_zitat_gibt_es_keinen_stil_lauf(conn, tg, einst):
    klm = LLMAttrappe()
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")

    assert knoepfe.stelle_stil_vor(conn, tg, klm, einst, 1) is False
    assert klm.aufrufe == 0


def test_stil_menue_traegt_titel_zitat_und_beispielsatz(conn, tg):
    _interview(conn)
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")

    knoepfe.sende_stil(
        conn, tg, 1, "Mira",
        'VORSCHLAG STIL:\n'
        'Kurz und hart — "Ich sag das ganz kurz" — Ich geh, fertig. — Interview 1\n'
        'Weit ausholend — "Ich sag das ganz kurz" — Weisst du, das ist so eine '
        'Sache mit dem Gehen. — Interview 1',
    )

    assert [b for b, _ in tg.knoepfe[-1][2]] == [
        "1 · Kurz und hart", "2 · Weit ausholend", "Eigener Stil",
        # Der Ausweg aus der Figur-fuer-Figur-Schleife (06.09.2026, Analyse
        # Abschnitt 1): eine Figur ohne Quelle und ein Interview sind da.
        knoepfe._TEXT_FIGUREN_ZUFALL_KNOPF,
    ]
    text = tg.knoepfe[-1][1]
    assert "Ich sag das ganz kurz" in text
    assert "Ich geh, fertig." in text


def test_ein_erfundenes_zitat_faellt_raus(conn, tg):
    """Dieselbe Pruefung wie beim Verdichter: ein Zitat, das nicht woertlich
    im Transkript steht, geht nicht als Few-Shot in den Szenenlauf ein."""
    _interview(conn)
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")

    knoepfe.sende_stil(
        conn, tg, 1, "Mira",
        'VORSCHLAG STIL:\n'
        'Kurz und hart — "Das habe ich nie gesagt" — Ich geh, fertig. — Interview 1',
    )

    assert "Das habe ich nie gesagt" not in tg.knoepfe[-1][1]
    assert "Ich geh, fertig." in tg.knoepfe[-1][1]


def test_die_wahl_setzt_stil_und_quelle(conn, tg, einst):
    kopf_id = _interview(conn)
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    knoepfe.sende_stil(
        conn, tg, 1, "Mira",
        'VORSCHLAG STIL:\n'
        'Kurz und hart — "Ich sag das ganz kurz" — Ich geh, fertig. — Interview 1',
    )

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf(tg, "1 · Kurz und hart")))

    figur = repo.hole_figur(conn, 1, "Mira")
    assert "Ich geh, fertig." in figur["sprachstil"]
    assert figur["quelle_aufnahme_id"] == kopf_id


def test_eigener_stil_speichert_nichts(conn, tg, einst):
    _interview(conn)
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    knoepfe.sende_stil(
        conn, tg, 1, "Mira",
        'VORSCHLAG STIL:\n'
        'Kurz und hart — "Ich sag das ganz kurz" — Ich geh, fertig. — Interview 1',
    )

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf(tg, "Eigener Stil")))

    assert not (repo.hole_figur(conn, 1, "Mira")["sprachstil"] or "")


# --- Der Rahmen ist das Setting, nicht die Handlung (Birk, 11:42) ---------


def test_ein_geschichte_text_landet_nie_im_rahmen(conn, einst):
    """Live gemessen: der Erkenner schrieb einen Geschichte-Vorschlag in
    ``rahmen``, und das Setting war um die ganze Handlung erweitert."""
    from interview_theater import erkenner

    erkenner.wende_an(conn, einst, 1, [
        {"art": "rahmen_setzen",
         "wert": "Zwei verlieren sich im Treppenhaus. Ende: keine kommt zurueck."},
    ])

    stand = repo.hole_arbeitsstand(conn, 1)
    assert not (stand and (stand["rahmen"] or "").strip())
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "rahmen_war_geschichte" in arten


def test_ein_echtes_setting_geht_weiterhin_durch(conn, einst):
    from interview_theater import erkenner

    erkenner.wende_an(conn, einst, 1, [
        {"art": "rahmen_setzen", "wert": "Ein Treppenhaus, nachts, nach einer Party"},
    ])

    assert repo.hole_arbeitsstand(conn, 1)["rahmen"].startswith("Ein Treppenhaus")
