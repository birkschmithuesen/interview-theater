"""Tests fuer die Inline-Knoepfe (interview_theater/knoepfe.py, 05.09.2026).

Kein Netzzugriff: Telegram ist entweder eine Attrappe, die nur aufzeichnet,
oder ein ``httpx.MockTransport`` -- wie im ganzen uebrigen Testbestand.

Gemessen wird hier genau das, was die Knoepfe ueberhaupt rechtfertigt: dass
eine Auswahl DETERMINISTISCH in der Datenbank landet, statt von einem
Erkennerlauf abzuhaengen (der am 05.09.2026 im Live-Fenster 'entschieden'
statt 'kernthema_setzen' schrieb und die Festlegung damit verlor).
"""

import json

import httpx
import pytest

from interview_theater import knoepfe, phasen, repo, telegram


class TelegramAttrappe:
    """Zeichnet auf, was der Bot verschickt -- dieselbe Schnittstelle wie
    ``telegram.Telegram``, soweit die Knoepfe sie brauchen."""

    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.beantwortet = []
        self.entfernt = []
        self.naechste_message_id = 500

    def sende(self, chat_id, text):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_):
        self.gesendet.append((chat_id, text))
        self.knoepfe.append((chat_id, text, list(knoepfe_)))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _druck(daten, chat_id=1, message_id=777, query_id="q1"):
    """Ein normalisierter Knopfdruck, wie ``telegram.lies_knopfdruck`` ihn
    liefert."""
    return {
        "callback_query_id": query_id,
        "data": daten,
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
    }


def _daten_des_ersten_knopfes(tg):
    return tg.knoepfe[0][2][0][1]


# --- lies_knopfdruck ------------------------------------------------------


def test_callback_query_wird_erkannt_und_normalisiert():
    """Der zweite Update-Typ, den dieser Bot kennt -- er hat keine
    'message'-Struktur und wuerde von lies_nachricht verworfen."""
    update = {
        "update_id": 42,
        "callback_query": {
            "id": "cbq-1",
            "data": "k:7",
            "from": {"id": 5, "first_name": "Ada"},
            "message": {
                "message_id": 300,
                "chat": {"id": -100, "title": "Gruppe 1"},
                "date": 1757000000,
            },
        },
    }
    druck = telegram.lies_knopfdruck(update)

    assert druck == {
        "callback_query_id": "cbq-1",
        "data": "k:7",
        "chat_id": -100,
        "chat_titel": "Gruppe 1",
        "message_id": 300,
    }
    # Der Absender geht bewusst NICHT mit (keine PII, die niemand braucht).
    assert "absender" not in druck
    # Und eine gewoehnliche Nachricht ist kein Knopfdruck.
    assert telegram.lies_knopfdruck({"update_id": 1, "message": {}}) is None


def test_knopfdruck_ohne_daten_wird_verworfen():
    """Laut Bot-API moeglich (Spiel-Knoepfe). Darauf laesst sich nichts
    zuordnen -- raten waere hier der teuerste Ausgang."""
    assert telegram.lies_knopfdruck({"callback_query": {"id": "x"}}) is None


def test_knopfdruck_ohne_message_bleibt_verwertbar():
    """Telegram haelt sehr alte Nachrichten nicht vor. answerCallbackQuery
    geht trotzdem -- die callback_query_id reicht dafuer."""
    druck = telegram.lies_knopfdruck(
        {"callback_query": {"id": "cbq-2", "data": "k:1"}}
    )
    assert druck["chat_id"] is None and druck["message_id"] is None
    assert druck["callback_query_id"] == "cbq-2"


# --- Kernthema ------------------------------------------------------------


def test_kernthema_knopf_schreibt_in_den_arbeitsstand(conn, einst, tg):
    """Der eigentliche Zweck der Uebung (05.09.2026): die Auswahl landet
    SOFORT und deterministisch in arbeitsstand.kernthema -- ohne dass ein
    Erkennerlauf sie im richtigen Fenster treffen muss."""
    knoepfe.biete_kernthema(conn, tg, 1, ["Ankommen und Fremdsein"])

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen und Fremdsein"
    assert any("Kernthema notiert" in t for _, t in tg.gesendet)
    # Telegram bekommt IMMER ein answerCallbackQuery -- sonst dreht sich in
    # der App eine Ladeanzeige weiter.
    assert len(tg.beantwortet) == 1
    # Und die Knoepfe verschwinden, sobald sie gewirkt haben.
    assert tg.entfernt == [(1, 777)]


def test_kernthema_knopf_schreibt_ins_journal(conn, einst, tg):
    """Damit die Entscheidung auf der Weboberflaeche auftaucht -- genau das
    fehlte am 05.09.2026, als der Erkenner sie nicht als Arbeitsstand las."""
    knoepfe.biete_kernthema(conn, tg, 1, ["Ankommen"])
    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    eintraege = repo.journal(conn, 1)
    assert any(
        j["art"] == "entschieden" and "Ankommen" in j["text"] and j["quelle"] == "knopf"
        for j in eintraege
    )


def test_kernthema_vorschlaege_kommen_aus_den_verdichtungen(conn, einst, tg):
    """Kein Modellaufruf: die Themen sind beim Verdichten schon entstanden
    und bezahlt (AGENTS.md -- kein Knopf-Handler ruft synchron ein Modell)."""
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "sprache", "kurz")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Zusammenfassung",
        [
            {"thema": "Ankommen in einer fremden Stadt", "kurz": "Ankommen",
             "beleg_zitat": None, "zitat_geprueft": 0},
            {"thema": "Arbeit und Wuerde", "kurz": "Arbeit",
             "beleg_zitat": None, "zitat_geprueft": 0},
        ],
    )

    assert knoepfe.kernthema_vorschlaege(conn, 1) == ["Ankommen", "Arbeit"]


def test_kernthema_ohne_vorschlaege_sagt_das(conn, einst, tg):
    """Statt eine leere Tastatur zu schicken: die Gruppe soll wissen, warum
    da nichts steht, und dass sie es auch einfach sagen kann."""
    assert knoepfe.biete_kernthema(conn, tg, 1) is False
    assert tg.knoepfe == []
    assert "noch keine Vorschlaege" in tg.gesendet[0][1]


def test_hoechstens_drei_vorschlaege(conn, einst, tg):
    """Mehr ist keine Auswahl mehr, sondern eine Liste, die gelesen werden
    will -- die Gruppe steht im Raum vor einem Telefon."""
    knoepfe.biete_kernthema(conn, tg, 1, ["A", "B", "C", "D", "E"])
    assert len(tg.knoepfe[0][2]) == knoepfe.MAX_VORSCHLAEGE == 3


# --- Aufnahme -------------------------------------------------------------


def test_aufnahme_knopf_schaltet_an_und_wieder_aus(conn, einst, tg):
    """Ein Umschalter, genau wie /aufnahme (befehle._befehl_aufnahme) --
    zwei Druecke, zwei Zustaende, kein dritter Weg."""
    knoepfe.biete_aufnahme(conn, tg, 1, "Sollen wir?")
    assert tg.knoepfe[0][2][0][0] == "Aufnahme starten"

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))
    assert repo.ist_interviewmodus_an(conn, 1) is True
    # Die Bestaetigung traegt selbst wieder einen Knopf -- jetzt den zum
    # Beenden, weil sich der Zustand geaendert hat.
    assert tg.knoepfe[1][2][0][0] == "Aufnahme beenden"

    # Zweiter Knopf, zweiter Druck: wieder aus.
    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(tg.knoepfe[1][2][0][1], message_id=778, query_id="q2"),
    )
    assert repo.ist_interviewmodus_an(conn, 1) is False


def test_aufnahme_knopf_legt_je_umschaltung_genau_ein_interview_an(conn, einst, tg):
    """§ 10.6: mit dem Modus entsteht EIN Interview. Der Knopf darf daran
    nichts aendern -- er ist derselbe Weg wie /aufnahme, nicht ein zweiter."""
    knoepfe.biete_aufnahme(conn, tg, 1, "Sollen wir?")
    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))
    assert repo.zaehle_interviews(conn, 1) == 1


# --- Phase ----------------------------------------------------------------


def test_phasen_knopf_schaltet_um_wie_der_befehl(conn, einst, tg):
    knoepfe.biete_phase(conn, tg, 1, "Weitermachen?", 4)
    assert "Weiter zu 4" in tg.knoepfe[0][2][0][0]

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    assert phasen.aktuelle(conn, 1) == 4
    assert any("Wir sind jetzt bei 4" in t for _, t in tg.gesendet)


def test_phasen_knopf_meldet_nichts_wenn_die_phase_schon_stimmt(conn, einst, tg):
    """phasen.setze liefert False bei gleichem Wert -- dann gibt es weder
    Journaleintrag noch Meldung (dieselbe Regel wie ueberall)."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.biete_phase(conn, tg, 1, "Weitermachen?", 4)
    vorher = len(tg.gesendet)

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    assert len(tg.gesendet) == vorher  # keine zweite "Wir sind jetzt bei"-Zeile
    assert len(tg.beantwortet) == 1  # aber beantwortet wird trotzdem


# --- Idempotenz -----------------------------------------------------------


def test_zweiter_druck_wirkt_nicht_noch_einmal(conn, einst, tg):
    """AGENTS.md: zweimal tippen darf nichts doppelt anlegen. Ein bereits
    benutzter Knopf wird beantwortet, ohne die Wirkung zu wiederholen."""
    knoepfe.biete_aufnahme(conn, tg, 1, "Sollen wir?")
    daten = _daten_des_ersten_knopfes(tg)

    knoepfe.behandle(conn, tg, None, einst, _druck(daten))
    assert repo.ist_interviewmodus_an(conn, 1) is True
    nach_erstem = len(tg.gesendet)

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, query_id="q2"))

    # Der Modus ist NICHT wieder ausgeschaltet worden -- der zweite Druck
    # hat den Umschalter nicht ein zweites Mal betaetigt.
    assert repo.ist_interviewmodus_an(conn, 1) is True
    assert len(tg.gesendet) == nach_erstem  # keine zweite Chatnachricht
    assert tg.beantwortet[-1][1] == "Das habe ich schon uebernommen."


def test_zweiter_kernthema_druck_ueberschreibt_nichts(conn, einst, tg):
    """Auch wenn das Ergebnis dasselbe waere: die Sperre haengt an
    repo.beanspruche_knopf, nicht daran, dass jede Wirkung zufaellig
    wiederholbar ist."""
    knoepfe.biete_kernthema(conn, tg, 1, ["Ankommen"])
    daten = _daten_des_ersten_knopfes(tg)
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Von Hand korrigiert")

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, query_id="q2"))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Von Hand korrigiert"


def test_beanspruche_knopf_gewinnt_nur_einmal(conn):
    """Die Idempotenz-Sperre selbst: ein bedingtes UPDATE, das genau einmal
    zieht -- SQLite entscheidet, nicht ein Lesen-dann-Schreiben in Python."""
    knopf_id = repo.lege_knopf_an(conn, 1, "kernthema", "Ankommen")
    assert repo.beanspruche_knopf(conn, knopf_id) is True
    assert repo.beanspruche_knopf(conn, knopf_id) is False


# --- Abgrenzung -----------------------------------------------------------


def test_fremde_callback_data_wird_durchgelassen(conn, einst, tg):
    """In einer Gruppe koennen andere Bots Knoepfe stehen haben. behandle()
    liefert dann False und antwortet nicht -- der fremde Bot tut das."""
    assert knoepfe.behandle(conn, tg, None, einst, _druck("fremd:1")) is False
    assert tg.beantwortet == []


def test_unbekannte_knopf_id_wird_freundlich_beantwortet(conn, einst, tg):
    """Etwa nach einem Loeschlauf (scripts/loeschen.py). Beantworten muss
    der Bot trotzdem, sonst haengt die Ladeanzeige."""
    assert knoepfe.behandle(conn, tg, None, einst, _druck("k:99999")) is True
    assert tg.beantwortet[0][1] == "Diesen Knopf kenne ich nicht mehr."


def test_knopf_einer_anderen_gruppe_wirkt_nicht(conn, einst, tg):
    """Dieselbe Datenbank traegt alle Gruppen des Workshops -- ein Knopf
    darf nie in fremde Daten schreiben."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere Gruppe")
    knopf_id = repo.lege_knopf_an(conn, 2, "kernthema", "Fremdes Thema")

    knoepfe.behandle(conn, tg, None, einst, _druck(f"k:{knopf_id}", chat_id=1))

    assert repo.hole_arbeitsstand(conn, 1) is None
    assert tg.beantwortet[0][1] == "Diesen Knopf kenne ich nicht mehr."


# --- callback_data-Grenze -------------------------------------------------


def test_callback_data_bleibt_unter_64_bytes_auch_bei_langem_kernthema(conn, tg):
    """Die harte Telegram-Grenze (AGENTS.md): niemals der Volltext in
    callback_data. Ein Kernthema kann laenger sein als die ganze Grenze --
    der Knopf traegt trotzdem nur 'k:<id>'."""
    langes_thema = (
        "Ankommen in einer fremden Stadt, in der niemand deinen Namen "
        "richtig ausspricht, und trotzdem bleiben wollen"
    )
    assert len(langes_thema.encode("utf-8")) > telegram.CALLBACK_DATA_GRENZE

    knoepfe.biete_kernthema(conn, tg, 1, [langes_thema])

    beschriftung, daten = tg.knoepfe[0][2][0]
    assert beschriftung == langes_thema  # der Volltext steht sichtbar da
    assert len(daten.encode("utf-8")) <= telegram.CALLBACK_DATA_GRENZE
    assert langes_thema not in daten
    # und der Wert selbst liegt in der Datenbank, nicht im Knopf
    knopf_id = int(daten.removeprefix(knoepfe.PRAEFIX))
    assert repo.hole_knopf(conn, knopf_id)["wert"] == langes_thema


def test_callback_data_bleibt_kurz_auch_bei_hoher_id(conn, tg):
    """Selbst eine siebenstellige id passt mit Abstand -- die Grenze kann
    hier strukturell nicht gerissen werden."""
    conn.execute("INSERT INTO knopf (id, chat_id, art, wert, erstellt_am) "
                 "VALUES (9999999, 1, 'kernthema', 'X', '2026-09-05T00:00:00+00:00')")
    conn.commit()
    assert len(knoepfe._daten(9999999).encode("utf-8")) <= telegram.CALLBACK_DATA_GRENZE


def test_sende_mit_knoepfen_weist_zu_lange_callback_data_ab():
    """Ein Programmierfehler, kein Bedienfehler: waere der Wert zu lang,
    antwortete Telegram mit BUTTON_DATA_INVALID -- und das faende sich erst
    im Betrieb. Deshalb ValueError vor dem HTTP-Aufruf."""
    def handler(request):  # pragma: no cover -- darf nie erreicht werden
        raise AssertionError("es haette gar kein HTTP-Aufruf stattfinden duerfen")

    bot = telegram.Telegram("T", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError):
        bot.sende_mit_knoepfen(1, "Text", [("Label", "k:" + "9" * 70)])


# --- HTTP-Schicht ---------------------------------------------------------


def test_sende_mit_knoepfen_baut_eine_inline_tastatur():
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["url"] = str(request.url)
        gesehen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 55}})

    bot = telegram.Telegram("T", httpx.Client(transport=httpx.MockTransport(handler)))
    assert bot.sende_mit_knoepfen(-100, "Waehlt", [("A", "k:1"), ("B", "k:2")]) == 55

    assert "sendMessage" in gesehen["url"]
    # Je Knopf eine eigene Zeile: die Beschriftungen sind ganze Saetze und
    # wuerden nebeneinander abgeschnitten.
    assert gesehen["body"]["reply_markup"] == {
        "inline_keyboard": [
            [{"text": "A", "callback_data": "k:1"}],
            [{"text": "B", "callback_data": "k:2"}],
        ]
    }


def test_beantworte_knopf_ruft_answer_callback_query():
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["url"] = str(request.url)
        gesehen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = telegram.Telegram("T", httpx.Client(transport=httpx.MockTransport(handler)))
    bot.beantworte_knopf("cbq-9", "Kernthema uebernommen")

    assert "answerCallbackQuery" in gesehen["url"]
    assert gesehen["body"] == {
        "callback_query_id": "cbq-9", "text": "Kernthema uebernommen",
    }


def test_entferne_knoepfe_schickt_leere_tastatur():
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["url"] = str(request.url)
        gesehen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = telegram.Telegram("T", httpx.Client(transport=httpx.MockTransport(handler)))
    bot.entferne_knoepfe(-100, 300)

    assert "editMessageReplyMarkup" in gesehen["url"]
    assert gesehen["body"]["reply_markup"] == {"inline_keyboard": []}


def test_entfernen_scheitert_ohne_die_wirkung_zu_gefaehrden(conn, einst, tg, monkeypatch):
    """Die Wirkung steht schon in der Datenbank -- eine misslungene Kosmetik
    darf die Gruppe keine Fehlermeldung kosten (Fehlerhaltung)."""
    knoepfe.biete_kernthema(conn, tg, 1, ["Ankommen"])

    def kracht(chat_id, message_id):
        raise telegram.TelegramFehler("kaputt")

    monkeypatch.setattr(tg, "entferne_knoepfe", kracht)
    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"


# --- Einhaengung in die Befehle -------------------------------------------


def test_kernthema_befehl_ohne_argument_bietet_knoepfe_an(conn, einst, tg):
    """/kernthema ohne Argument erklaert nicht mehr nur die Syntax, sondern
    bietet an, was schon in den Verdichtungen steht."""
    from interview_theater import befehle

    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "sprache", "kurz")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Z",
        [{"thema": "Ankommen in einer fremden Stadt", "kurz": "Ankommen",
          "beleg_zitat": None, "zitat_geprueft": 0}],
    )

    befehle.behandle(conn, tg, einst, 1, "/kernthema", "Ada")

    assert tg.knoepfe and tg.knoepfe[0][2][0][0] == "Ankommen"


def test_kernthema_befehl_ohne_vorschlaege_erklaert_die_syntax(conn, einst, tg):
    """Gibt es nichts anzubieten, bleibt die alte Erklaerung -- die Gruppe
    soll nie vor einer Sackgasse stehen."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/kernthema", "Ada")

    assert tg.knoepfe == []
    assert any("/kernthema Ankommen" in t for _, t in tg.gesendet)


def test_phase_befehl_haengt_den_weiter_knopf_an(conn, einst, tg):
    """Nur wenn die Materiallage den Schritt hergibt (phasen.voraussetzungen)
    -- sonst waere der Knopf ein Angebot ins Leere."""
    from interview_theater import befehle

    repo.setze_arbeitsstand(conn, 1, "begriffe", "Heimat, Arbeit, Angst")

    befehle.behandle(conn, tg, einst, 1, "/phase", "Ada")

    assert tg.knoepfe and "Weiter zu 2" in tg.knoepfe[0][2][0][0]
    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))
    assert phasen.aktuelle(conn, 1) == 2


def test_phase_befehl_ohne_moegliche_naechste_bleibt_ohne_knopf(conn, einst, tg):
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/phase", "Ada")

    assert tg.knoepfe == []
    assert any("Wir sind bei 1" in t for _, t in tg.gesendet)


def test_aufnahme_befehl_haengt_den_umschalter_an(conn, einst, tg):
    """Der Knopf traegt den Zustand, in den er fuehrt -- nach dem Start
    heisst er 'Aufnahme beenden'."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/aufnahme", "Ada")

    assert tg.knoepfe[0][2][0][0] == "Aufnahme beenden"
    assert repo.ist_interviewmodus_an(conn, 1) is True
