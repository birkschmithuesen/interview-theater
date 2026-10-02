"""Das Team-Dashboard: in Padua englisch, in Dortmund byte-gleich wie vorher.

Die Vergleichsdatei ``tests/fixtures/dashboard_de_vorher.html`` ist mit dem
Code VOR der Umstellung erzeugt worden (ohne Profil und mit
``IT_WORKSHOP=dortmund-2026`` -- beide zeichengleich). Sie ist die
Beweisgrundlage dafuer, dass Dortmund kein Zeichen anders sieht.
"""

import pathlib
import re
from html.parser import HTMLParser

import pytest

from interview_theater import sprache, web, workshop

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
VORHER = FIXTURES / "dashboard_de_vorher.html"
VORHER_LEER = FIXTURES / "dashboard_de_vorher_leer.html"


def _arbeitsstand(**felder) -> dict:
    stand = {
        "phase": None, "begriffe": None, "fragen": None,
        "frage_einleitungen": None, "fragen_weich": None,
        "interview_eroeffnung": None, "interview_abschluss": None,
        "kernthema": None, "kernthema_begruendung": None, "format": None,
        "rahmen": None, "kernthema_richtung": None, "kernfrage": None,
        "geschichte": None, "figuren_fixiert_am": None, "hauptkonflikt": None,
        "geaendert_am": None,
    }
    stand.update(felder)
    return stand


#: Feste Daten in der Form von ``web_daten.dashboard()`` -- zwei Gruppen, eine
#: davon mit allem, was das Dashboard zeigen kann. Die Werte aus der
#: Datenbank sind englisch (Padua), die Schluessel (Status, Vorfall- und
#: Aufrufarten, Form ``offen``) roh wie im Protokoll.
DATEN = {
    "gruppen": [
        {
            "chat_id": -1001,
            "titel": "Team Canal",
            "bot_name": "padua_bot1",
            "web_token": "tok123",
            "interviewmodus_seit": "2026-10-02T09:00:00+00:00",
            "arbeitsstand": _arbeitsstand(
                phase=3,
                begriffe="bridge, market, rain",
                fragen="Home: Where do you feel at home?\nWork: What do you do all day?",
                interview_eroeffnung="Hello, we are making a play.",
                interview_abschluss="Thank you very much.",
                kernthema="belonging",
                kernthema_begruendung="came up twice",
                rahmen="a bridge at night",
                geschichte="two friends meet on the bridge",
                hauptkonflikt="stay or leave",
            ),
            "figuren": [
                {"id": 1, "name": "Mira", "beschreibung": "a student",
                 "sprachprofil": None, "zitate": [], "quelle": "Interview 1",
                 "quelle_aufnahme_id": 5},
                {"id": 2, "name": "Luca", "beschreibung": None,
                 "sprachprofil": None, "zitate": [], "quelle": None,
                 "quelle_aufnahme_id": None},
            ],
            "aufnahmen": {"empfangen": 1, "fehlgeschlagen": 1, "fertig": 3,
                          "laeuft": 1, "transkribiert": 2, "unbekannt_x": 1},
            "verdichtungen": 2,
            "szenen": 4,
            "szenen_formen": [("dialog", 2), ("offen", 1), ("tanz", 1)],
            "interview_kurzformen": [
                {"name": "Interview 1", "kurzformen": ["fishing at dawn", "a lost key"]},
                {"name": None, "kurzformen": ["the old bakery"]},
            ],
            "letzte_aktivitaet": "2026-10-02T10:30:00+00:00",
            "vorfaelle": [
                {"art": "wiederholung_verworfen", "stufe": None,
                 "detail": "detail one", "erstellt_am": "2026-10-02T10:01:00+00:00",
                 "bot_weit": False},
                {"art": "transkription_fehlgeschlagen", "stufe": 2,
                 "detail": None, "erstellt_am": "2026-10-02T10:05:00+00:00",
                 "bot_weit": True},
                {"art": "voellig_neue_art", "stufe": None,
                 "detail": "detail two", "erstellt_am": None,
                 "bot_weit": False},
            ],
            "aufrufe": [
                {"art": "erkenner", "anzahl": 7, "fehlschlaege": 0, "median_ms": 812},
                {"art": "gespraech", "anzahl": 5, "fehlschlaege": 1, "median_ms": 5123},
                {"art": "stt", "anzahl": 2, "fehlschlaege": 0, "median_ms": None},
                {"art": "neue_aufrufart", "anzahl": 1, "fehlschlaege": 0, "median_ms": 50},
            ],
        },
        {
            "chat_id": -1002,
            "titel": None,
            "bot_name": "padua_bot2",
            "web_token": None,
            "interviewmodus_seit": None,
            "arbeitsstand": _arbeitsstand(),
            "figuren": [],
            "aufnahmen": {},
            "verdichtungen": 0,
            "szenen": 0,
            "szenen_formen": [],
            "interview_kurzformen": [],
            "letzte_aktivitaet": None,
            "vorfaelle": [],
            "aufrufe": [],
        },
    ],
    "bot_zuordnung": [
        {"bot_name": "padua_bot1", "chat_id": -1001, "titel": "Team Canal",
         "letzte_aktivitaet_am": "2026-10-02T10:31:00+00:00",
         "gestartet_am": "2026-10-02T08:00:00+00:00"},
        {"bot_name": "padua_bot3", "chat_id": None, "titel": None,
         "letzte_aktivitaet_am": None, "gestartet_am": None},
    ],
    "stand": "2026-10-02T10:32:00+00:00",
}

LEER = {"gruppen": [], "bot_zuordnung": [], "stand": "2026-10-02T10:32:00+00:00"}


def _profil(monkeypatch, name: str | None) -> None:
    if name is None:
        monkeypatch.delenv(workshop.VARIABLE, raising=False)
    else:
        monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture(autouse=True)
def _frisch():
    yield
    workshop.vergiss()
    sprache.vergiss()


# --- (c) Dortmund und Vorgabe: byte-gleich wie vor der Umstellung -----------


@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_deutsch_byte_gleich_wie_vorher(monkeypatch, profil):
    _profil(monkeypatch, profil)
    assert web.dashboard_html(DATEN) == VORHER.read_text(encoding="utf-8")


@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_deutsch_leer_byte_gleich_wie_vorher(monkeypatch, profil):
    _profil(monkeypatch, profil)
    assert web.dashboard_html(LEER) == VORHER_LEER.read_text(encoding="utf-8")


# --- (a) Padua: kein deutsches Wort im sichtbaren Text ------------------------

#: Was vor der Umstellung auf dem Dashboard stand -- als Wort im lesbaren
#: Text gesucht (nicht in Klassennamen wie ``zahlen`` oder ``vorfaelle``).
DEUTSCHE_WOERTER = (
    "Arbeitsstand aller Gruppen", "Stand", "Bot-Zuordnung", "letzte Aktivität",
    "Aufruf", "heute", "Fehl", "Modellaufrufe", "Aufnahmen", "keine",
    "Verdichtungen", "zuletzt", "Interviewmodus", "bot-weit",
    "Noch keine Gruppe", "Gruppe", "Szenen", "fertig", "laeuft", "empfangen",
    "transkribiert", "fehlgeschlagen", "wiederholung_verworfen",
    "transkription_fehlgeschlagen", "erkenner", "gespraech", "offen",
)


def _sichtbar(html: str) -> str:
    from scripts import pruefe_sprache

    return pruefe_sprache.nur_text(html)


def _deutsche_treffer(html: str) -> list[str]:
    text = _sichtbar(html)
    return [w for w in DEUTSCHE_WOERTER
            if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text)]


@pytest.fixture
def padua(monkeypatch):
    _profil(monkeypatch, "padua-2026")


def test_padua_ohne_deutsche_woerter(padua):
    assert _deutsche_treffer(web.dashboard_html(DATEN)) == []
    assert _deutsche_treffer(web.dashboard_html(LEER)) == []


def test_padua_ohne_deutsche_signale(padua):
    """Dieselbe Pruefung wie fuer die Gruppenseite (``pruefe_sprache``)."""
    from scripts import pruefe_sprache

    treffer = pruefe_sprache.deutsche_treffer("dashboard", _sichtbar(web.dashboard_html(DATEN)))
    assert [f"{t.wort} | {t.ausschnitt}" for t in treffer] == []


def test_positivkontrolle_deutsch_schlaegt_an(monkeypatch):
    """Ohne sie prueft der Wortfilter womoeglich nichts."""
    _profil(monkeypatch, None)
    assert set(_deutsche_treffer(web.dashboard_html(DATEN))) >= {
        "Arbeitsstand aller Gruppen", "Aufnahmen", "fertig", "wiederholung_verworfen",
        "Interviewmodus", "bot-weit", "offen",
    }


def test_padua_lang_und_datum(padua):
    html = web.dashboard_html(DATEN)
    assert '<html lang="en">' in html
    assert 'lang="de"' not in html
    assert not re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", _sichtbar(html))
    # Eindeutig: Jahr-Monat-Tag, ohne den deutschen Trenner " · ".
    assert "As of 2026-10-02 12:32</span>" in html
    assert "Last activity: 2026-10-02 12:30</span>" in html
    assert "2026-10-02 12:05, bot-wide" in html


def test_padua_dezimalpunkt(padua):
    html = web.dashboard_html(DATEN)
    assert "<td>5.1 s</td>" in html
    assert "5,1" not in html


def test_padua_beschriftet_und_unbekanntes_bleibt_roh(padua):
    text = _sichtbar(web.dashboard_html(DATEN))
    for erwartet in ("received", "done", "running", "transcribed", "failed",
                     "repetition_discarded", "transcription_failed",
                     "conversation", "intent detector", "speech-to-text",
                     "2 dialogue", "1 open", "Interview mode", "Group -1002",
                     "— no group —", "Bot assignment", "Progress of all groups"):
        assert erwartet in text, erwartet
    # Unbekannte Schluessel: roh, kein Fehler.
    for roh in ("unbekannt_x", "voellig_neue_art", "neue_aufrufart", "1 tanz"):
        assert roh in text, roh


# --- (b) Padua: der Technikteil ist eingeklappt -------------------------------


class _Lage(HTMLParser):
    """Merkt sich je interessantem Element, ob es in einem ``<details>``
    steht und ob dieses offen ist."""

    def __init__(self):
        super().__init__()
        self.stapel: list[tuple[str, bool]] = []   # (tag, details_offen)
        self.funde: list[tuple[str, bool | None]] = []
        self.summaries: list[str] = []
        self._in_summary = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        details = [offen for t, offen in self.stapel if t == "details"]
        lage = None if not details else any(details)
        name = tag + ("." + a["class"] if a.get("class") else "")
        self.funde.append((name, lage))
        if tag == "summary":
            self._in_summary = True
            self.summaries.append("")
        if tag not in ("br", "meta", "input"):
            self.stapel.append((tag, "open" in a))

    def handle_endtag(self, tag):
        if tag == "summary":
            self._in_summary = False
        for i in range(len(self.stapel) - 1, -1, -1):
            if self.stapel[i][0] == tag:
                del self.stapel[i:]
                break

    def handle_data(self, data):
        if self._in_summary:
            self.summaries[-1] += data


def _lage(html: str) -> _Lage:
    p = _Lage()
    p.feed(html)
    return p


def _lagen(p: _Lage, name: str) -> list:
    return [lage for n, lage in p.funde if n == name]


def test_padua_technikteil_eingeklappt(padua):
    html = web.dashboard_html(DATEN)
    p = _lage(html)
    # Eingeklappt (in <details>, geschlossen): Zahlenzeile, Vorfaelle,
    # Aufruftabelle bzw. "keine Aufrufe", und die Bot-Zuordnung.
    assert _lagen(p, "div.zahlen") == [False, False]
    assert _lagen(p, "div.vorfaelle") == [False]
    assert _lagen(p, "p.leer") == [False]               # keine Aufrufe, Karte 2
    assert all(lage is False for lage in _lagen(p, "table"))
    assert len(_lagen(p, "table")) == 2                 # Aufrufe + Zuordnung
    assert "<details open" not in html
    # Sichtbar bleiben: Arbeitsstand und Ergebnisse.
    assert _lagen(p, "dl") == [None, None]
    assert _lagen(p, "ul.ergebnisse") == [None]
    assert _lagen(p, "span.marke") == [None]
    assert all(lage is None for lage in _lagen(p, "h2"))
    # Summary-Texte: uebersetzt, ohne Zahl (das Nachladen oeffnet am Text).
    assert p.summaries == ["Log", "Log", "Bot assignment"]
    assert not any(re.search(r"\d", s) for s in p.summaries)


def test_padua_leer_ohne_karte(padua):
    p = _lage(web.dashboard_html(LEER))
    assert _lagen(p, "p.leer") == [None]                # "No group has written yet."
    assert p.summaries == ["Bot assignment"]


@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_deutsch_ohne_details(monkeypatch, profil):
    _profil(monkeypatch, profil)
    p = _lage(web.dashboard_html(DATEN))      # Skript-Kommentare zaehlen nicht
    assert not [n for n, _ in p.funde if n.startswith(("details", "summary"))]


def test_einklappen_nur_im_profil_gesetzt(monkeypatch):
    _profil(monkeypatch, None)
    assert workshop.aktiv().wert("web.dashboard_log_einklappen") is False
    _profil(monkeypatch, "dortmund-2026")
    assert workshop.aktiv().wert("web.dashboard_log_einklappen") is False
    _profil(monkeypatch, "padua-2026")
    assert workshop.aktiv().wert("web.dashboard_log_einklappen") is True


def test_deutsch_unbekanntes_bleibt_roh(monkeypatch):
    _profil(monkeypatch, None)
    text = _sichtbar(web.dashboard_html(DATEN))
    for roh in ("fertig", "unbekannt_x", "voellig_neue_art", "neue_aufrufart",
                "2 dialog", "1 offen", "1 tanz"):
        assert roh in text, roh
