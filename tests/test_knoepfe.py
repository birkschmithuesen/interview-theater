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


# --- Format des Stuecks (Phase 5, 05.09.2026) -----------------------------


def test_format_knopf_schreibt_in_den_arbeitsstand(conn, einst, tg):
    """Derselbe Zweck wie beim Kernthema, eine Station spaeter: phasen/5.md
    stellt das Format als nummerierte Auswahl, und auf "das erste" kann der
    Erkenner nicht schliessen. Der Knopf traegt die Auswahl selbst."""
    knoepfe.biete_format(conn, tg, 1, ["Sprechtheater: Dialog und Chor", "Musical"])

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    # Wirklich nachgelesen, nicht nur gesendet:
    assert repo.hole_arbeitsstand(conn, 1)["format"] == "Sprechtheater: Dialog und Chor"
    assert any("Format notiert" in t for _, t in tg.gesendet)
    assert len(tg.beantwortet) == 1
    assert tg.entfernt == [(1, 777)]


def test_format_knopf_schreibt_ins_journal(conn, einst, tg):
    knoepfe.biete_format(conn, tg, 1, ["Revue"])
    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    assert any(
        j["art"] == "entschieden" and "Revue" in j["text"] and j["quelle"] == "knopf"
        for j in repo.journal(conn, 1)
    )


def test_format_knopf_ist_idempotent(conn, einst, tg):
    """Zweimal tippen darf nichts doppelt tun (AGENTS.md): der zweite Druck
    wird beantwortet, aber ueberschreibt nichts -- auch dann nicht, wenn die
    Gruppe zwischendurch etwas anderes gesetzt hat."""
    knoepfe.biete_format(conn, tg, 1, ["Musical"])
    daten = _daten_des_ersten_knopfes(tg)
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))
    repo.setze_arbeitsstand(conn, 1, "format", "Sprechtheater")

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, message_id=778, query_id="q2"))

    assert repo.hole_arbeitsstand(conn, 1)["format"] == "Sprechtheater"
    assert tg.beantwortet[-1][1] == knoepfe._TEXT_SCHON_BENUTZT


def test_format_callback_data_bleibt_unter_64_bytes_auch_bei_langem_wert(conn, tg):
    """Der Grund fuer die Knopf-Tabelle: ein ausformuliertes Format ist
    laenger als die ganze Telegram-Grenze. In callback_data steht deshalb nur
    die id -- geprueft wird an der echten Grenzpruefung
    (telegram.sende_mit_knoepfen), nicht an einer nachgebauten."""
    lang = ("Musical mit Sprechtheater, Chorpassagen, Liedern und Rap " * 4).strip()
    assert len(lang.encode("utf-8")) > telegram.CALLBACK_DATA_GRENZE

    knoepfe.biete_format(conn, tg, 1, [lang])

    daten = _daten_des_ersten_knopfes(tg)
    assert len(daten.encode("utf-8")) < telegram.CALLBACK_DATA_GRENZE
    # Der Volltext ist trotzdem vollstaendig da -- er steht in der Tabelle.
    assert repo.hole_knopf(conn, int(daten[len(knoepfe.PRAEFIX):]))["wert"] == lang


def test_format_ohne_vorschlaege_faellt_auf_die_standardformate(conn, einst, tg):
    """Ohne Argument gelten die vier Formen aus phasen/5.md -- kein
    Modellaufruf, wie AGENTS.md es fuer Knopf-Wege verlangt."""
    assert knoepfe.biete_format(conn, tg, 1) is True
    beschriftungen = [b for b, _ in tg.knoepfe[0][2]]
    assert beschriftungen == list(knoepfe.STANDARD_FORMATE)


def test_format_hoechstens_vier_knoepfe(conn, einst, tg):
    knoepfe.biete_format(conn, tg, 1, ["A", "B", "C", "D", "E", "F"])
    assert len(tg.knoepfe[0][2]) == knoepfe.MAX_FORMATE == 4


def test_stueck_format_ohne_wert_bietet_knoepfe_an(conn, einst, tg):
    """Einhaengung: /stueck format ohne Wert erklaert nicht mehr die Syntax,
    sondern legt die Auswahl hin."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/stueck format", "Ada")

    assert tg.knoepfe and tg.knoepfe[0][2][0][0] == knoepfe.STANDARD_FORMATE[0]


def test_stueck_rahmen_ohne_wert_bleibt_bei_der_erklaerung(conn, einst, tg):
    """Der Rahmen ist Freitext -- dort gibt es keine Liste, aus der sich
    waehlen liesse, also auch keinen Knopf."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/stueck rahmen", "Ada")

    assert tg.knoepfe == []
    assert any("/stueck rahmen" in t for _, t in tg.gesendet)


# --- Form je Szene (Phase 6, 05.09.2026) ----------------------------------


def test_szenenform_knopf_schreibt_das_feld_der_richtigen_szene(conn, einst, tg):
    """Am 05.09. stand in einer fertigen Szene "Monolog", ohne dass es
    jemand gewaehlt hatte. Der Knopf schreibt genau die Form, die draufsteht,
    in genau die Szene, deren Nummer er traegt."""
    from interview_theater import szene as szene_modul

    knoepfe.biete_szenenform(conn, tg, 1, 3)
    beschriftungen = [b for b, _ in tg.knoepfe[0][2]]
    assert beschriftungen == [f.capitalize() for f in szene_modul.FORMEN]

    # "Lied" ist der zweite Eintrag von szene.FORMEN.
    daten_lied = tg.knoepfe[0][2][1][1]
    knoepfe.behandle(conn, tg, None, einst, _druck(daten_lied))

    szene_id = repo.stelle_szene_sicher(conn, 1, 3)
    assert repo.hole_szene(conn, szene_id)["form"] == "lied"


def test_szenenform_knopf_trifft_nicht_die_falsche_szene(conn, einst, tg):
    """Die Nummer wandert im wert der Knopfzeile mit -- ohne sie wuesste der
    Druck nicht, welche Szene gemeint ist, und wuerde die zuletzt
    angesprochene erwischen."""
    knoepfe.biete_szenenform(conn, tg, 1, 2)
    daten_zwei = tg.knoepfe[0][2][0][1]
    tg.knoepfe.clear()
    knoepfe.biete_szenenform(conn, tg, 1, 5)
    daten_fuenf = tg.knoepfe[0][2][1][1]

    knoepfe.behandle(conn, tg, None, einst, _druck(daten_fuenf))
    knoepfe.behandle(conn, tg, None, einst, _druck(daten_zwei, message_id=778, query_id="q2"))

    assert repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 5))["form"] == "lied"
    assert repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 2))["form"] == "dialog"


def test_szenenform_knopf_ist_idempotent(conn, einst, tg):
    knoepfe.biete_szenenform(conn, tg, 1, 1)
    daten = tg.knoepfe[0][2][0][1]
    knoepfe.behandle(conn, tg, None, einst, _druck(daten))
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "chor")

    knoepfe.behandle(conn, tg, None, einst, _druck(daten, message_id=778, query_id="q2"))

    assert repo.hole_szene(conn, szene_id)["form"] == "chor"
    assert tg.beantwortet[-1][1] == knoepfe._TEXT_SCHON_BENUTZT


def test_szenenform_callback_data_bleibt_kurz_auch_bei_hoher_nummer(conn, tg):
    """Nummer UND Form stehen im wert der Knopfzeile, nicht in
    callback_data -- deshalb ist die Grenze unabhaengig von beiden."""
    knoepfe.biete_szenenform(conn, tg, 1, 999)

    for _, daten in tg.knoepfe[0][2]:
        assert len(daten.encode("utf-8")) < telegram.CALLBACK_DATA_GRENZE
    assert repo.hole_knopf(
        conn, int(tg.knoepfe[0][2][0][1][len(knoepfe.PRAEFIX):])
    )["wert"] == "999:dialog"


def test_szene_form_ohne_wert_bietet_knoepfe_an(conn, einst, tg):
    """Einhaengung: "/szene 2 form" ohne Wert legt die Auswahl hin, statt
    als Szenen-SCHREIBauftrag ins Sprachmodell zu laufen."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/szene 2 form", "Ada", klm=None)

    assert tg.knoepfe and tg.knoepfe[0][2][0][0] == "Dialog"
    assert "Szene 2" in tg.knoepfe[0][1]


# --- USA-Einwilligung (05.09.2026) ----------------------------------------


def test_usa_knopf_ja_setzt_einen_bool_und_der_stand_ist_ja(conn, einst, tg):
    """Der Fall, der am 05.09.2026 eine Sackgasse erzeugt hat: der Bot
    fragte, die Gruppe bejahte siebenmal, der Erkenner las es als Zustimmung
    zu den Figuren.

    Geprueft wird ausdruecklich der BOOL: repo.setze_szene_usa nimmt keinen
    String -- "nein" waere als nicht-leerer String wahr und damit die
    Zustimmung zu einer Datenuebermittlung, die niemand gegeben hat."""
    knoepfe.biete_szene_usa(conn, tg, 1)
    assert [b for b, _ in tg.knoepfe[0][2]] == ["Ja, US-Modell", "Nein, Schweiz"]

    knoepfe.behandle(conn, tg, None, einst, _druck(tg.knoepfe[0][2][0][1]))

    assert repo.szene_usa_stand(conn, 1) == "ja"


def test_usa_knopf_nein_setzt_false_und_nicht_wahr(conn, einst, tg):
    """Die Gegenprobe -- und der eigentliche Regressionstest: mit dem String
    "nein" statt False stuende hier 'ja'."""
    knoepfe.biete_szene_usa(conn, tg, 1)

    knoepfe.behandle(conn, tg, None, einst, _druck(tg.knoepfe[0][2][1][1]))

    assert repo.szene_usa_stand(conn, 1) == "nein"
    assert repo.szene_usa_stand(conn, 1) != "offen"
    assert any("Schweiz" in t for _, t in tg.gesendet)


def test_usa_stand_ist_vor_dem_druck_offen(conn, einst, tg):
    """Damit die beiden Tests oben etwas beweisen: 'offen' ist der
    Ausgangszustand, nicht das Ergebnis."""
    assert repo.szene_usa_stand(conn, 1) == "offen"


def test_usa_knopf_ist_idempotent(conn, einst, tg):
    """Ein zweiter Druck auf 'Ja' darf die Entscheidung nicht erneut
    schreiben -- und schon gar nicht ein zwischenzeitliches Nein kippen."""
    knoepfe.biete_szene_usa(conn, tg, 1)
    daten_ja = tg.knoepfe[0][2][0][1]
    knoepfe.behandle(conn, tg, None, einst, _druck(daten_ja))
    repo.setze_szene_usa(conn, 1, False)

    knoepfe.behandle(conn, tg, None, einst, _druck(daten_ja, message_id=778, query_id="q2"))

    assert repo.szene_usa_stand(conn, 1) == "nein"
    assert tg.beantwortet[-1][1] == knoepfe._TEXT_SCHON_BENUTZT


def test_usa_knoepfe_bleiben_unter_64_bytes(conn, tg):
    knoepfe.biete_szene_usa(conn, tg, 1)
    for _, daten in tg.knoepfe[0][2]:
        assert len(daten.encode("utf-8")) < telegram.CALLBACK_DATA_GRENZE


def test_usa_knopf_schreibt_ins_journal(conn, einst, tg):
    """Eine Einwilligung muss nachlesbar sein -- sie betrifft eine
    Datenuebermittlung, nicht nur eine Formatfrage."""
    knoepfe.biete_szene_usa(conn, tg, 1)
    knoepfe.behandle(conn, tg, None, einst, _druck(tg.knoepfe[0][2][0][1]))

    assert any(
        j["art"] == "entschieden" and "US-Modell" in j["text"] and j["quelle"] == "knopf"
        for j in repo.journal(conn, 1)
    )


def test_szene_usa_ohne_antwort_bietet_knoepfe_an(conn, einst, tg):
    """Einhaengung: "/szene usa" ohne ja/nein legt die beiden Knoepfe hin."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/szene usa", "Ada", klm=None)

    assert [b for b, _ in tg.knoepfe[0][2]] == ["Ja, US-Modell", "Nein, Schweiz"]


def test_szene_usa_ja_per_text_wirkt_weiter_wie_bisher(conn, einst, tg):
    """Der Slash-Weg bleibt unangetastet -- die Knoepfe treten daneben, nicht
    an seine Stelle."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/szene usa nein", "Ada", klm=None)

    assert repo.szene_usa_stand(conn, 1) == "nein"
    assert tg.knoepfe == []


# --- Slash-Befehle und Knoepfe nebeneinander (Rauchtest) ------------------


def test_slash_und_knopf_setzen_dasselbe_feld_ohne_sich_zu_stoeren(conn, einst, tg):
    """Der Rauchtest: erst /stueck format per Text, dann derselbe Wert per
    Knopf. Beides landet im Arbeitsstand, und es gibt nur EINEN Schreibweg
    (repo.setze_arbeitsstand) -- kein zweiter Mechanismus daneben."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/stueck format Musical", "Ada")
    assert repo.hole_arbeitsstand(conn, 1)["format"] == "Musical"

    knoepfe.biete_format(conn, tg, 1, ["Musical"])
    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    assert repo.hole_arbeitsstand(conn, 1)["format"] == "Musical"

    # Und andersherum: der Text gewinnt danach wieder, ohne dass der schon
    # verbrauchte Knopf etwas zurueckdreht.
    befehle.behandle(conn, tg, einst, 1, "/stueck format Revue", "Ada")
    assert repo.hole_arbeitsstand(conn, 1)["format"] == "Revue"


def test_slash_und_knopf_setzen_dieselbe_szenenform(conn, einst, tg):
    """Dasselbe fuer die Form je Szene: /szene 1 form lied per Text, dann
    derselbe Wert per Knopf -- ein Feld, ein Schreibweg."""
    from interview_theater import befehle

    befehle.behandle(conn, tg, einst, 1, "/szene 1 form lied", "Ada", klm=None)
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    assert repo.hole_szene(conn, szene_id)["form"] == "lied"

    knoepfe.biete_szenenform(conn, tg, 1, 1)
    knoepfe.behandle(conn, tg, None, einst, _druck(tg.knoepfe[-1][2][1][1]))

    assert repo.hole_szene(conn, szene_id)["form"] == "lied"


# --- Knopfleiste nach einem beendeten Interview ---------------------------
#
# Der Live-Befund vom 05.09.2026 (Gruppe 2, 13:59): ein Interview von drei
# Sekunden endete mit "Interview 1 ist sehr kurz ... sagt Bescheid, wenn ich
# es trotzdem soll." Die Gruppe fragte zweimal nach, der Gespraechs-Bot
# antwortete zweimal mit rund 300 Zeichen Text ("Gerade spielt /auswerten
# ..."), und ausgewertet wurde nie. Birk: "ersetze am besten alle slash
# befehl vorschlaege mit knoepfen. und gib auch immer sinnvolle
# alternativvorschlaege."


def _interview_kopf(conn, transkript="ein kurzer Satz"):
    """Ein beendetes Interview mit Transkript, ohne Verdichtung.

    Setzt die Phase auf 3 (Interviews): dort und nur dort wird aufgenommen,
    und seit 05.09.2026 haengt die Leiste danach davon ab
    (``knoepfe._aufnahme_anbieten``)."""
    from interview_theater import aufnahme

    phasen.setze(conn, 1, 3, "befehl")
    repo.setze_interviewmodus(conn, 1, repo._jetzt())
    kopf_id = aufnahme.stelle_interview_sicher(conn, 1)
    repo.setze_transkript(conn, kopf_id, transkript)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interviewmodus(conn, 1, None)
    return kopf_id


def test_nach_aufnahme_bietet_auswerten_und_naechste_aufnahme(conn, einst, tg):
    """Die beiden Wege, die es nach jedem Interview gibt -- als Knopf, nicht
    als Slash-Empfehlung im Text."""
    kopf_id = _interview_kopf(conn)

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ist sehr kurz.", kopf_id)

    beschriftungen = [b for b, _ in tg.knoepfe[0][2]]
    assert beschriftungen == ["Auswerten", "Naechste Aufnahme"]
    assert "/" not in tg.knoepfe[0][1], "kein Slash-Befehl mehr im Text"


def test_nach_aufnahme_haengt_die_phase_an_wenn_die_lage_sie_hergibt(conn, einst, tg):
    """Die Alternative, die im Live-Fall gefehlt hat: statt direkt das
    naechste Interview zu starten, haette die Gruppe auch in die Auswertung
    gehen koennen (phasen.naechste_moegliche, reine Leseabfrage)."""
    kopf_id = _interview_kopf(conn)
    repo.speichere_verdichtung(conn, 1, kopf_id, "eine Zusammenfassung", [])

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ist abgelegt.", kopf_id)

    beschriftungen = [b for b, _ in tg.knoepfe[0][2]]
    assert beschriftungen == [
        "Auswerten", "Naechste Aufnahme", "Weiter zu 4 · Kernthema & Figuren",
    ]


def test_nach_aufnahme_ohne_interview_bietet_nur_die_aufnahme_an(conn, einst, tg):
    """"fertig" ohne eine einzige Sprachnachricht: es gibt nichts
    auszuwerten, also steht der Knopf auch nicht da."""
    phasen.setze(conn, 1, 3, "befehl")

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Das Interview hatte keine Aufnahme.", None)

    assert [b for b, _ in tg.knoepfe[0][2]] == ["Naechste Aufnahme"]


def test_nach_aufnahme_bietet_in_phase_4_keine_naechste_aufnahme_an(conn, einst, tg):
    """Der Live-Befund vom 05.09.2026 (Birk: "hast du die reihenfolge der
    phasen beachtet?"), gespiegelt auf die Leiste nach dem Interview: ist die
    Gruppe inzwischen bei Kernthema & Figuren, ist "Naechste Aufnahme" kein
    Angebot mehr, sondern ein Rueckschritt. "Auswerten" bleibt -- das
    Material aus Phase 3 will ja gerade jetzt gelesen werden."""
    kopf_id = _interview_kopf(conn)
    phasen.setze(conn, 1, 4, "befehl")

    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ist abgelegt.", kopf_id)

    assert [b for b, _ in tg.knoepfe[0][2]] == ["Auswerten"]


def test_auswerten_knopf_spielt_eine_vorhandene_verdichtung_aus(conn, einst, tg):
    """Der Kern des Live-Befunds: verdichtet wird sofort, ausgespielt erst
    auf Wunsch -- und der Wunsch ist dieser Knopf. Kein Modellaufruf, der
    Text kommt aus der Datenbank (aufnahme.zeige_verdichtung)."""
    kopf_id = _interview_kopf(conn)
    repo.speichere_verdichtung(
        conn, 1, kopf_id, "Es ging ums Ankommen.",
        [{"thema": "Ankommen", "kurz": "Ankommen", "beleg_zitat": None,
          "zitat_geprueft": 0}],
    )
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ist abgelegt.", kopf_id)

    knoepfe.behandle(conn, tg, None, einst, _druck(_daten_des_ersten_knopfes(tg)))

    text = tg.gesendet[-1][1]
    assert "Interview 1 ist durch" in text
    assert "Es ging ums Ankommen." in text
    assert len(repo.verdichtungen(conn, 1)) == 1, "keine zweite Verdichtung"


def test_auswerten_knopf_verdichtet_ein_zu_kurzes_interview_im_thread(conn, einst, tg, monkeypatch):
    """Unter aufnahme.MINDEST_WOERTER gibt es noch keine Verdichtung -- dann
    tut der Knopf wortgleich das, was /auswerten tut: der Aufruf geht sofort
    an einen eigenen Thread (kein Modellaufruf im Knopf-Handler, AGENTS.md)."""
    from interview_theater import aufnahme

    kopf_id = _interview_kopf(conn)
    gestartet = []
    monkeypatch.setattr(
        aufnahme, "starte_auswertung",
        lambda conn, tg, klm, e, kid: gestartet.append(kid),
    )
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ist sehr kurz.", kopf_id)

    knoepfe.behandle(
        conn, tg, object(), einst, _druck(_daten_des_ersten_knopfes(tg))
    )

    assert gestartet == [kopf_id]
    assert tg.gesendet[-1][1] == "Ich werte Interview 1 aus."


def test_zweiter_auswerten_druck_wertet_nicht_zweimal_aus(conn, einst, tg, monkeypatch):
    """Idempotenz ueber repo.beanspruche_knopf: der zweite Druck wird
    beantwortet, loest aber keinen zweiten (bezahlten) Lauf aus."""
    from interview_theater import aufnahme

    kopf_id = _interview_kopf(conn)
    gestartet = []
    monkeypatch.setattr(
        aufnahme, "starte_auswertung",
        lambda conn, tg, klm, e, kid: gestartet.append(kid),
    )
    knoepfe.biete_nach_aufnahme(conn, tg, 1, "Interview 1 ist sehr kurz.", kopf_id)
    daten = _daten_des_ersten_knopfes(tg)

    knoepfe.behandle(conn, tg, object(), einst, _druck(daten))
    knoepfe.behandle(conn, tg, object(), einst, _druck(daten, query_id="q2"))

    assert gestartet == [kopf_id]
    assert tg.beantwortet[-1][1] == "Das habe ich schon uebernommen."


# --- Einstiegsknoepfe (Begruessung, unbekannter Befehl) -------------------


def test_einstieg_bietet_in_phase_1_keine_aufnahme_an(conn, einst, tg):
    """Der Live-Befund vom 05.09.2026 (Birk: "aber direkt schon mit aufnahme
    starten? nach der begruessung kommt erst die eingabe der begriffe"): in
    Phase 1 gibt es nichts aufzunehmen -- die Begriffe kommen als Text oder
    Sprachnachricht aus dem Plenum. Der Knopf zeigte zwei Arbeitsschritte zu
    weit und stand dabei an erster Stelle."""
    assert phasen.aktuelle(conn, 1) == 1

    knoepfe.biete_einstieg(conn, tg, 1, "Hallo.")

    assert [b for b, _ in tg.knoepfe[0][2]] == ["Stand zeigen", "Hilfe"]


def test_einstieg_bietet_ab_phase_3_die_aufnahme_an(conn, einst, tg):
    """Ab den Interviews ist "Aufnahme starten" genau der Weg -- und steht
    wieder vorn, wo die Gruppe im Raum hintippt."""
    phasen.setze(conn, 1, 3, "befehl")

    knoepfe.biete_einstieg(conn, tg, 1, "Bin wieder da.")

    assert [b for b, _ in tg.knoepfe[0][2]] == [
        "Aufnahme starten", "Stand zeigen", "Hilfe",
    ]


def test_einstieg_bietet_das_beenden_auch_in_phase_1_an(conn, einst, tg):
    """Die Ausnahme zur Phasenregel: laeuft eine Aufnahme, MUSS der
    Ausschalter da sein. Ein laufendes Interview ohne Knopf waere die
    schlechtere Falle als ein Angebot zur falschen Zeit -- und ausdruecklich
    aufnehmen darf die Gruppe jederzeit (AGENTS.md, "Fokus, kein Kaefig")."""
    repo.setze_interviewmodus(conn, 1, repo._jetzt())

    knoepfe.biete_einstieg(conn, tg, 1, "Hallo.")

    assert [b for b, _ in tg.knoepfe[0][2]] == [
        "Aufnahme beenden", "Stand zeigen", "Hilfe",
    ]


def test_einstieg_haengt_die_phase_dazwischen(conn, einst, tg):
    """Nach einer Nacht Pause ist "weiter zur naechsten Station" die
    wahrscheinlichste Absicht -- deshalb steht sie direkt hinter der
    Aufnahme, nicht am Ende."""
    kopf_id = _interview_kopf(conn)
    repo.speichere_verdichtung(conn, 1, kopf_id, "eine Zusammenfassung", [])

    knoepfe.biete_einstieg(conn, tg, 1, "Bin wieder da.")

    assert [b for b, _ in tg.knoepfe[0][2]] == [
        "Aufnahme starten", "Weiter zu 4 · Kernthema & Figuren",
        "Stand zeigen", "Hilfe",
    ]


def test_einstieg_stellt_die_phase_ohne_aufnahme_nach_vorn(conn, einst, tg):
    """Ohne Aufnahme-Knopf (Phase 1/2) rutscht "Weiter zu Phase N" an die
    erste Stelle: dann ist der Schritt weiter die wahrscheinlichste
    Absicht."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Heimat, Bahnhof, Koffer")

    knoepfe.biete_einstieg(conn, tg, 1, "Hallo.")

    assert [b for b, _ in tg.knoepfe[0][2]] == [
        "Weiter zu 2 · Fragen", "Stand zeigen", "Hilfe",
    ]


def test_stand_knopf_zeigt_denselben_stand_wie_der_befehl(conn, einst, tg):
    knoepfe.biete_einstieg(conn, tg, 1, "Hallo.")
    daten = tg.knoepfe[0][2][0][1]  # "Stand zeigen"

    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert tg.gesendet[-1][1].startswith("Stand:")


def test_hilfe_knopf_zeigt_die_bedienung(conn, einst, tg):
    knoepfe.biete_einstieg(conn, tg, 1, "Hallo.")
    daten = tg.knoepfe[0][2][1][1]  # "Hilfe"

    knoepfe.behandle(conn, tg, None, einst, _druck(daten))

    assert "SO MACHT IHR EIN INTERVIEW" in tg.gesendet[-1][1]
