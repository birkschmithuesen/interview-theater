"""Der zweite Anbieterweg streamt ebenfalls -- im Anthropic-Format.

Die Ereignisse heissen anders (``message_start``, ``content_block_delta``,
``message_delta``), die Zusage ist dieselbe: gleiche Rueckgabe, gleiche
``aufruf``-Zeile, kein halber Text, keine Denkspur an die Gruppe.
"""

import json

import httpx
import pytest

from interview_theater import db, repo, szene_claude

CHAT = 7_000_000_000_001


class Einstellungen:
    szene_anbieter = "claude"
    szene_url = "http://127.0.0.1:28764/v1/messages"
    szene_modell = "claude-opus-5"
    bot_name = "gruppe1"


@pytest.fixture(autouse=True)
def frischer_prozesszustand():
    szene_claude.vergiss_strom()
    yield
    szene_claude.vergiss_strom()


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "X")
    return verbindung


_FERTIG = {
    "content": [{"type": "text", "text": "Es war einmal"}],
    "usage": {"input_tokens": 700, "output_tokens": 12},
    "stop_reason": "end_turn",
}


def _sse(stuecke, stop="end_turn"):
    zeilen = [
        "event: message_start",
        "data: " + json.dumps({"type": "message_start",
                               "message": {"usage": {"input_tokens": 700}}}),
    ]
    for stueck in stuecke:
        zeilen += [
            "event: content_block_delta",
            "data: " + json.dumps({"type": "content_block_delta",
                                   "delta": {"type": "text_delta", "text": stueck}}),
        ]
    zeilen += [
        "event: message_delta",
        "data: " + json.dumps({"type": "message_delta",
                               "delta": {"stop_reason": stop},
                               "usage": {"output_tokens": 12}}),
        "event: message_stop",
        "data: " + json.dumps({"type": "message_stop"}),
    ]
    return ("\n".join(zeilen) + "\n\n").encode("utf-8")


def _klient(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ohne_bei_teil_steht_kein_stream_im_koerper(conn):
    gesehen = {}

    def handler(anfrage):
        gesehen["body"] = json.loads(anfrage.content)
        return httpx.Response(200, json=_FERTIG)

    szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                       "sys", "nutz", "szene", timeout=5)
    assert "stream" not in gesehen["body"]


def test_stream_liefert_teilstuecke_und_denselben_text(conn):
    teile = []
    text = szene_claude.prosa(
        conn, Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["Es war ", "einmal"]))),
        CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=teile.append,
    )
    assert teile == ["Es war ", "Es war einmal"]
    assert text == "Es war einmal"


def test_die_aufrufzeile_ist_dieselbe_wie_ohne_stream(conn):
    szene_claude.prosa(conn, Einstellungen(),
                       _klient(lambda a: httpx.Response(200, json=_FERTIG)),
                       CHAT, "sys", "nutz", "szene", timeout=5)
    ohne = conn.execute("SELECT * FROM aufruf ORDER BY id DESC LIMIT 1").fetchone()

    szene_claude.prosa(
        conn, Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["Es war ", "einmal"]))),
        CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None,
    )
    mit = conn.execute("SELECT * FROM aufruf ORDER BY id DESC LIMIT 1").fetchone()
    for spalte in ("art", "modus", "geschaetzte_token", "tatsaechliche_token",
                   "antwort_token", "finish_reason", "erfolg"):
        assert mit[spalte] == ohne[spalte], spalte


def test_thinking_deltas_gehen_nie_an_bei_teil(conn):
    inhalt = (
        'event: content_block_delta\n'
        'data: {"type": "content_block_delta", "delta": {"type": "thinking_delta", '
        '"thinking": "ich ueberlege"}}\n\n'
        'event: content_block_delta\n'
        'data: {"type": "content_block_delta", "delta": {"type": "text_delta", '
        '"text": "Text"}}\n\n'
        'event: message_delta\n'
        'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, '
        '"usage": {"output_tokens": 3}}\n\n'
    ).encode("utf-8")
    teile = []
    szene_claude.prosa(conn, Einstellungen(),
                       _klient(lambda a: httpx.Response(200, content=inhalt)),
                       CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=teile.append)
    assert teile == ["Text"]


def test_ein_abgeschnittener_stream_bleibt_ein_fehler(conn):
    """Birk, 06.09.2026: 'Nichts darf stillschweigend abgeschnitten werden.'"""
    with pytest.raises(szene_claude.ClaudeFehler) as fehler:
        szene_claude.prosa(
            conn, Einstellungen(),
            _klient(lambda a: httpx.Response(200, content=_sse(["halb"], stop="max_tokens"))),
            CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None,
        )
    assert "abgeschnitten" in str(fehler.value)
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "szene_abgeschnitten" in arten


def test_ein_abriss_nach_dem_ersten_stueck_wird_ohne_stream_wiederholt(conn):
    versuche = []

    def handler(anfrage):
        streamt = bool(json.loads(anfrage.content).get("stream"))
        versuche.append(streamt)
        if streamt:
            return httpx.Response(200, content=(
                b'event: content_block_delta\n'
                b'data: {"type": "content_block_delta", "delta": '
                b'{"type": "text_delta", "text": "Es war "}}\n\n'
                b'data: {kaputt'
            ))
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=Senke())
    assert text == "Es war einmal"
    assert versuche == [True, False]
    assert abbrueche == [True]


# -- Lehren aus der Review von Aufgabe 5 (llm.py), hier von Anfang an --------
#
# Fuenf Befunde aus Fix Runde 1 (llm.py), hier gegen den Anthropic-Zweig
# nachgezogen, jeder mit eigenem Test: ein sauberes Verbindungsende ohne
# message_stop/stop_reason ist ein Abbruch, eine werfende Senke reisst den
# Zug nicht mit, ein voruebergehender Fehler schaltet die Flagge nicht ab
# (nur ein echtes "nicht unterstuetzt" tut das), und Dekodier-/Stream-Fehler
# werden wie Transportfehler behandelt.


def test_sauberes_ende_ohne_message_stop_ist_ein_abbruch(conn):
    """Die Verbindung schliesst sauber nach einem Stueck, aber ohne
    message_delta/message_stop -- das ist ein Abbruch, kein Erfolg, sonst
    kaeme ein abgeschnittener Satz als vollstaendige Szene durch."""
    versuche = []

    def handler(anfrage):
        streamt = bool(json.loads(anfrage.content).get("stream"))
        versuche.append(streamt)
        if streamt:
            return httpx.Response(200, content=(
                b'event: content_block_delta\n'
                b'data: {"type": "content_block_delta", "delta": '
                b'{"type": "text_delta", "text": "halb"}}\n\n'
            ))
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=Senke())
    assert text == "Es war einmal"
    assert versuche == [True, False]
    assert abbrueche == [True]


def test_eine_werfende_senke_bricht_den_zug_nicht_ab(conn):
    """Eine Anzeige, die wirft (z. B. eine gesperrte DB), darf die Antwort
    nicht kosten -- nur die Anzeige stoppt, der Text wird weiter gesammelt
    und normal zurueckgegeben."""
    aufrufe = []

    def bad(text):
        aufrufe.append(text)
        raise RuntimeError("db locked")

    text = szene_claude.prosa(
        conn, Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["Es war ", "einmal"]))),
        CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=bad,
    )
    assert text == "Es war einmal"
    assert len(aufrufe) == 1  # die Senke wurde versucht, aber nicht erneut


@pytest.mark.parametrize("status", [408, 429, 500, 503, 529])
def test_transiente_fehler_setzen_die_flagge_nicht(conn, status):
    """Ein einzelner Drosselimpuls (408/429/5xx, Anthropics eigener
    "overloaded"-Code 529) darf nicht jede weitere Szene dieses Prozesses auf
    Nichtstreaming umschalten -- stiller Rueckfall, Flagge bleibt an."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(status)
        return httpx.Response(200, json=_FERTIG)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None)
    assert text == "Es war einmal"
    assert szene_claude._abgeschaltet() is False
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" not in arten


def test_transportfehler_vor_dem_ersten_stueck_faellt_zurueck_ohne_flagge(conn):
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            raise httpx.ConnectError("weg", request=anfrage)
        return httpx.Response(200, json=_FERTIG)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None)
    assert text == "Es war einmal"
    assert szene_claude._abgeschaltet() is False


def test_ein_4xx_auf_stream_schaltet_dauerhaft_ab(conn):
    """Lehnt der Proxy ``stream`` grundsaetzlich ab (z. B. unbekannter
    Parameter), ist das ein echtes "nicht unterstuetzt" -- die Flagge wird
    gesetzt, und der naechste Aufruf dieses Prozesses streamt gar nicht erst."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(400, json={"error": "unknown parameter"})
        return httpx.Response(200, json=_FERTIG)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None)
    assert text == "Es war einmal"
    assert szene_claude._abgeschaltet() is True
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" in arten

    teile = []
    szene_claude.prosa(conn, Einstellungen(),
                       _klient(lambda a: httpx.Response(200, json=_FERTIG)),
                       CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=teile.append)
    assert teile == []  # der zweite Aufruf streamt gar nicht erst


class _ReisstNachEinemStueck(httpx.SyncByteStream):
    """Liefert ein gueltiges Ereignis, dann wirft das Lesen ``fehler``."""

    def __init__(self, fehler):
        self._fehler = fehler

    def __iter__(self):
        yield (
            b'data: {"type": "content_block_delta", "delta": '
            b'{"type": "text_delta", "text": "Hal"}}\n\n'
        )
        raise self._fehler


@pytest.mark.parametrize("fehler", [
    httpx.DecodingError("kaputt"),
    httpx.StreamClosed(),
    httpx.ReadError("weg"),
])
def test_lesefehler_nach_dem_ersten_stueck_ist_ein_abbruch(conn, fehler):
    """httpx.DecodingError und httpx.StreamError sind keine
    httpx.TransportError (eigene Hierarchien), muessen aber genauso behandelt
    werden -- nach dem ersten Stueck ein Abbruch, kein Dauerausfall."""
    versuche = []

    def handler(anfrage):
        streamt = bool(json.loads(anfrage.content).get("stream"))
        versuche.append(streamt)
        if streamt:
            return httpx.Response(200, stream=_ReisstNachEinemStueck(fehler))
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=Senke())
    assert text == "Es war einmal"
    assert versuche == [True, False]
    assert abbrueche == [True]
    assert szene_claude._abgeschaltet() is False


def test_decoding_fehler_vor_dem_ersten_stueck_faellt_zurueck_ohne_flagge(conn):
    """Ein Dekodierfehler VOR dem ersten Stueck ist voruebergehend, keine
    Dauerabschaltung."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            # Deklariert gzip, liefert aber keins -- httpx wirft beim Lesen
            # DecodingError.
            return httpx.Response(200, headers={"content-encoding": "gzip"},
                                  content=b"keine-gzip-daten")
        return httpx.Response(200, json=_FERTIG)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None)
    assert text == "Es war einmal"
    assert szene_claude._abgeschaltet() is False


# -- Fix Runde 1 (Review von Aufgabe 6) ---------------------------------------
#
# Vier Befunde: eine leere, aber ordentlich beendete Antwort loeste faelschlich
# einen "kann nicht streamen"-Dauerzustand aus; das Anthropic-eigene
# ``error``-SSE-Ereignis (HTTP 200!) wurde komplett ignoriert; ein scheiternder
# ``bei_teil.abbruch()``-Hook riss den ganzen Zug mit; und zwei Textbloecke
# wurden ohne Trenner zusammengeklebt statt wie im blockierenden Weg mit
# ``\n`` verbunden.


def test_leere_aber_vollstaendig_beendete_antwort_ist_kein_nichtverfuegbar_fall(conn):
    """Ein komplett leerer Text (kein einziger text_delta -- Ablehnung,
    max_tokens waehrend des Denkens, leere Antwort), der aber ordentlich mit
    message_delta/message_stop endet, ist KEIN Beweis dafuer, dass der Proxy
    nicht streamen kann. Die Flagge bleibt aus, es gibt keinen zweiten,
    blockierenden Opus-Lauf -- ``prosa`` wirft stattdessen seinen gewohnten
    Fehler ueber den leeren Text."""
    versuche = []

    def handler(anfrage):
        streamt = bool(json.loads(anfrage.content).get("stream"))
        versuche.append(streamt)
        if streamt:
            return httpx.Response(200, content=(
                b'event: message_start\n'
                b'data: {"type": "message_start", "message": '
                b'{"usage": {"input_tokens": 700}}}\n\n'
                b'event: message_delta\n'
                b'data: {"type": "message_delta", "delta": '
                b'{"stop_reason": "end_turn"}, "usage": {"output_tokens": 0}}\n\n'
                b'event: message_stop\n'
                b'data: {"type": "message_stop"}\n\n'
            ))
        return httpx.Response(200, json=_FERTIG)

    with pytest.raises(szene_claude.ClaudeFehler) as fehler:
        szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                           "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None)
    assert "keine Textbloecke" in str(fehler.value)
    assert versuche == [True]  # kein blockierender Nachversuch
    assert szene_claude._abgeschaltet() is False
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" not in arten


def test_overload_error_ereignis_vor_dem_ersten_stueck_faellt_still_zurueck(conn):
    """Anthropic schickt Ueberlast als SSE-Ereignis INNERHALB einer
    HTTP-200-Antwort (``{"type": "error", "error": {"type":
    "overloaded_error"}}``) -- das ist voruebergehend wie 429/5xx, kein
    "kann grundsaetzlich nicht streamen"."""
    versuche = []

    def handler(anfrage):
        streamt = bool(json.loads(anfrage.content).get("stream"))
        versuche.append(streamt)
        if streamt:
            return httpx.Response(200, content=(
                b'event: error\n'
                b'data: {"type": "error", "error": {"type": "overloaded_error", '
                b'"message": "Overloaded"}}\n\n'
            ))
        return httpx.Response(200, json=_FERTIG)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None)
    assert text == "Es war einmal"
    assert versuche == [True, False]
    assert szene_claude._abgeschaltet() is False
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" not in arten


def test_unbekanntes_error_ereignis_vor_dem_ersten_stueck_schaltet_dauerhaft_ab(conn):
    """Ein ``error``-Ereignis, dessen Typ nicht zu den bekannten
    voruebergehenden gehoert (z. B. ``invalid_request_error``), ist ein
    echtes "das geht so nicht" -- dauerhafte Abschaltung wie bei einem 4xx."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(200, content=(
                b'event: error\n'
                b'data: {"type": "error", "error": '
                b'{"type": "invalid_request_error", "message": "kaputt"}}\n\n'
            ))
        return httpx.Response(200, json=_FERTIG)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None)
    assert text == "Es war einmal"
    assert szene_claude._abgeschaltet() is True
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" in arten

    teile = []
    szene_claude.prosa(conn, Einstellungen(),
                       _klient(lambda a: httpx.Response(200, json=_FERTIG)),
                       CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=teile.append)
    assert teile == []  # der zweite Aufruf streamt gar nicht erst


def test_error_ereignis_nach_dem_ersten_stueck_ist_ein_abbruch(conn):
    """Kommt das ``error``-Ereignis erst NACH dem ersten Textstueck, ist es
    ein Abbruch -- die vorlaeufige Blase verschwindet, EIN blockierender
    Nachversuch liefert den vollstaendigen Text."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(200, content=(
                b'event: content_block_delta\n'
                b'data: {"type": "content_block_delta", "delta": '
                b'{"type": "text_delta", "text": "Es war "}}\n\n'
                b'event: error\n'
                b'data: {"type": "error", "error": {"type": "overloaded_error"}}\n\n'
            ))
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=Senke())
    assert text == "Es war einmal"
    assert abbrueche == [True]
    assert szene_claude._abgeschaltet() is False


def test_scheiternder_abbruch_hook_verhindert_den_nachversuch_nicht(conn):
    """Ein scheiternder ``bei_teil.abbruch()`` (z. B. ein DB-Schreibfehler
    beim Entfernen der vorlaeufigen Blase) darf den blockierenden
    Nachversuch nicht verhindern."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(200, content=(
                b'event: content_block_delta\n'
                b'data: {"type": "content_block_delta", "delta": '
                b'{"type": "text_delta", "text": "Es war "}}\n\n'
                b'data: {kaputt'
            ))
        return httpx.Response(200, json=_FERTIG)

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            raise RuntimeError("db locked")

    text = szene_claude.prosa(conn, Einstellungen(), _klient(handler), CHAT,
                              "sys", "nutz", "szene", timeout=5, bei_teil=Senke())
    assert text == "Es war einmal"


def test_zwei_textbloecke_werden_wie_im_blockierenden_weg_verbunden(conn):
    """Der blockierende Weg verbindet mehrere Textbloecke mit ``\\n``
    (``prosa``: ``"\\n".join(teile)``) -- der Stream-Weg muss denselben Text
    liefern, auch wenn die Bloecke ueber mehrere ``content_block_delta``-
    Indizes verteilt ankommen, statt sie roh aneinanderzukleben."""
    inhalt = (
        'event: content_block_delta\n'
        'data: {"type": "content_block_delta", "index": 0, "delta": '
        '{"type": "text_delta", "text": "Erster Block"}}\n\n'
        'event: content_block_delta\n'
        'data: {"type": "content_block_delta", "index": 1, "delta": '
        '{"type": "text_delta", "text": "Zweiter Block"}}\n\n'
        'event: message_delta\n'
        'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, '
        '"usage": {"output_tokens": 5}}\n\n'
        'event: message_stop\n'
        'data: {"type": "message_stop"}\n\n'
    ).encode("utf-8")
    text = szene_claude.prosa(
        conn, Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=inhalt)),
        CHAT, "sys", "nutz", "szene", timeout=5, bei_teil=lambda t: None,
    )
    assert text == "Erster Block\nZweiter Block"
