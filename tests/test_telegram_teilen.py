"""Lange Nachrichten werden geteilt, nicht verworfen (05.09.2026).

Live-Fall Gruppe 2: ein Teil-Transkript mit 7 957 Zeichen -> Telegram
antwortete HTTP 400 auf beiden Sendewegen, das Echo kam nie im Chat an.
"""
from interview_theater import telegram


def test_kurzer_text_bleibt_ein_stueck():
    assert telegram.teile_text("hallo") == ["hallo"]


def test_leerer_text_bleibt_ein_leeres_stueck():
    assert telegram.teile_text("") == [""]


def test_langer_text_wird_an_absaetzen_geteilt_und_bleibt_vollstaendig():
    absatz = "Satz eins. Satz zwei. " * 100  # ~2200 Zeichen
    text = "\n\n".join([absatz] * 4)  # ~8800 Zeichen
    stuecke = telegram.teile_text(text)
    assert len(stuecke) >= 3
    assert all(len(s) <= telegram.NACHRICHT_GRENZE for s in stuecke)
    # Nichts geht verloren: zusammengesetzt (ohne die Trenner-Leerzeichen)
    assert "".join(stuecke).replace(" ", "").replace("\n", "") == text.replace(" ", "").replace("\n", "")


def test_text_ohne_trenner_wird_hart_geteilt():
    text = "x" * 9000
    stuecke = telegram.teile_text(text)
    assert all(len(s) <= telegram.NACHRICHT_GRENZE for s in stuecke)
    assert "".join(stuecke) == text


class _Antwort:
    def __init__(self, mid):
        self._mid = mid

    def raise_for_status(self):
        pass

    def json(self):
        return {"ok": True, "result": {"message_id": self._mid}}


class _Klient:
    def __init__(self):
        self.gesendet = []

    def post(self, url, json=None, **kw):
        self.gesendet.append(json)
        return _Antwort(len(self.gesendet))


def _tg():
    tg = telegram.Telegram.__new__(telegram.Telegram)
    tg._token = "t"
    tg._klient = _Klient()
    return tg


def test_sende_teilt_und_liefert_letzte_message_id():
    tg = _tg()
    mid = tg.sende(1, "a" * 9000)
    assert len(tg._klient.gesendet) == 3
    assert mid == 3
    assert all(len(j["text"]) <= telegram.NACHRICHT_GRENZE for j in tg._klient.gesendet)


def test_sende_mit_knoepfen_haengt_tastatur_nur_ans_letzte_stueck():
    tg = _tg()
    tg.sende_mit_knoepfen(1, "b" * 9000, [("Weiter", "k:1")])
    gesendet = tg._klient.gesendet
    assert len(gesendet) == 3
    assert all("reply_markup" not in j for j in gesendet[:-1])
    assert gesendet[-1]["reply_markup"]["inline_keyboard"] == [[{"text": "Weiter", "callback_data": "k:1"}]]
