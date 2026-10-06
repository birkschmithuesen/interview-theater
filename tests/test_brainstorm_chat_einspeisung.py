"""P4-Quickfix (Birk 06.10.2026, Live-Test): ein Brainstorm-Bogen lief bisher
komplett am Absichtserkenner vorbei (``aufnahme._brainstorm_abschliessen``:
"Kein Gespraechszug, kein Absichtserkenner") -- die Werkbank (Rahmen,
Figuren, Geschichte) blieb deshalb leer, obwohl die Gruppe genau das gerade
frei gesprochen hatte.

``aufnahme._fuettere_gespraechszug_aus_brainstorm`` speist das
zusammenhaengende Transkript EINES Bogens einmal, auf dem Ende-Segment, als
normalen Chatbeitrag ein -- ueber ``repo.lege_web_post_an`` denselben Weg wie
eine getippte Textnachricht (``web_chat._text``), damit der ganz normale
Gespraechszug samt Absichtserkenner ihn sieht.

Nur hinter dem Profilschalter ``brainstorm.chat_einspeisen`` (Padua an,
Vorgabe/Dortmund aus). Fixtures aus ``tests/test_brainstorm_bogen.py``
kopiert, damit die Datei allein laeuft."""

import pytest

from interview_theater import aufnahme, db, einstellungen, repo, workshop


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        return 9001

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def aendere_text(self, chat_id, message_id, text):
        pass

    def tippt(self, chat_id):
        pass


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _brainstorm_zeile(conn, chat_id, message_id, transkript, schnittgrund="pause"):
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "kurz", "sprache", status="transkribiert",
        schnittgrund=schnittgrund, brainstorm=True,
    )
    repo.setze_transkript(conn, aufnahme_id, transkript)
    repo.merke_nachricht(
        conn, chat_id, message_id, "Gruppe", 0, "sprache", None,
        "2026-10-06T10:00:00", 1,
    )
    return repo.hole_aufnahme(conn, aufnahme_id)


class _ProfilAttrappe:
    """Steht fuer ``workshop.aktiv()`` -- nur ``wert`` wird gebraucht."""

    def __init__(self, an: bool):
        self._an = an

    def wert(self, pfad, vorgabe=None):
        if pfad == "brainstorm.chat_einspeisen":
            return self._an
        return vorgabe


# -- repo.brainstorm_arc_text -----------------------------------------------


def test_arc_text_haengt_die_segmente_mit_leerzeichen_zusammen(conn):
    _brainstorm_zeile(conn, 1, 100, "Erstens.", schnittgrund="pause")
    ende = _brainstorm_zeile(conn, 1, 101, "Zweitens.", schnittgrund="ende")
    assert repo.brainstorm_arc_text(conn, 1, ende["id"]) == "Erstens. Zweitens."


def test_arc_text_beginnt_erst_nach_dem_vorigen_ende(conn):
    """Mutant: die untere Grenze (``id > start``) entfernt -- der Text des
    VORIGEN Bogens wuerde mit eingespielt, obwohl die Gruppe ihn schon einmal
    gezeigt bekam."""
    _brainstorm_zeile(conn, 1, 200, "Alter Bogen.", schnittgrund="ende")
    _brainstorm_zeile(conn, 1, 201, "Neuer Bogen.", schnittgrund="pause")
    ende = _brainstorm_zeile(conn, 1, 202, "Zweiter Satz.", schnittgrund="ende")
    text = repo.brainstorm_arc_text(conn, 1, ende["id"])
    assert "Alter Bogen" not in text
    assert text == "Neuer Bogen. Zweiter Satz."


def test_arc_text_ohne_voriges_ende_zaehlt_von_anfang_an(conn):
    _brainstorm_zeile(conn, 1, 300, "Ganz am Anfang.", schnittgrund="pause")
    ende = _brainstorm_zeile(conn, 1, 301, "Schluss.", schnittgrund="ende")
    assert repo.brainstorm_arc_text(conn, 1, ende["id"]) == "Ganz am Anfang. Schluss."


def test_arc_text_ueberspringt_segmente_ohne_transkript(conn):
    """Ein noch nicht transkribiertes/verworfenes Segment (``transkript``
    NULL) darf keinen leeren Baustein in den Text schreiben."""
    repo.lege_aufnahme_an(conn, 1, 400, "kurz", "sprache", status="fehlgeschlagen",
                          schnittgrund="pause", brainstorm=True)
    ende = _brainstorm_zeile(conn, 1, 401, "Einziger Satz.", schnittgrund="ende")
    assert repo.brainstorm_arc_text(conn, 1, ende["id"]) == "Einziger Satz."


# -- aufnahme._fuettere_gespraechszug_aus_brainstorm -------------------------


def test_speist_nicht_wenn_der_profilschalter_aus_ist(conn, tg, einst, monkeypatch):
    """Vorgabe/Dortmund: ohne den Profilschalter bleibt das Verhalten von
    vor dem Quickfix -- kein Chatbeitrag. Mutant: der Guard
    (``if not workshop.aktiv().wert(...): return``) entfernt -- dann
    speiste dieser Test trotz ausgeschaltetem Profil ein."""
    monkeypatch.setattr(workshop, "aktiv", lambda: _ProfilAttrappe(an=False))
    row = _brainstorm_zeile(conn, 1, 500, "Setting: ein Theater.", schnittgrund="ende")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    assert repo.web_eingang(conn, 1, 0) == []


def test_speist_den_bogen_ein_wenn_der_profilschalter_an_ist(conn, tg, einst, monkeypatch):
    monkeypatch.setattr(workshop, "aktiv", lambda: _ProfilAttrappe(an=True))
    row = _brainstorm_zeile(conn, 1, 510, "Setting: ein Theater, drei Figuren.",
                            schnittgrund="ende")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    eingang = repo.web_eingang(conn, 1, 0)
    assert len(eingang) == 1
    assert eingang[0]["typ"] == repo.WEB_TYP_TEXT
    assert eingang[0]["text"] == "[Brainstorm, spoken freely:] Setting: ein Theater, drei Figuren."


def test_praefix_markiert_den_text_als_brainstorm(conn, tg, einst, monkeypatch):
    """Mutant: der Praefix (``_BRAINSTORM_EINSPEISUNG_PRAEFIX``) weggelassen
    -- das Modell saehe einen Satz ohne Hinweis, dass es frei gesprochener
    Brainstorm ist, nicht ein getippter Chatbeitrag."""
    monkeypatch.setattr(workshop, "aktiv", lambda: _ProfilAttrappe(an=True))
    row = _brainstorm_zeile(conn, 1, 520, "Irgendein Gedanke.", schnittgrund="ende")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    eingang = repo.web_eingang(conn, 1, 0)
    assert eingang[0]["text"].startswith("[Brainstorm, spoken freely:] ")


def test_kein_web_post_bei_einem_leeren_bogen(conn, tg, einst, monkeypatch):
    """Ein Bogen ohne verwertbares Transkript (z. B. sofort wieder beendet)
    speist nichts ein -- kein leerer Chatbeitrag."""
    monkeypatch.setattr(workshop, "aktiv", lambda: _ProfilAttrappe(an=True))
    row = repo.lege_aufnahme_an(conn, 1, 530, "kurz", "sprache", status="transkribiert",
                                schnittgrund="ende", brainstorm=True)
    repo.merke_nachricht(conn, 1, 530, "Gruppe", 0, "sprache", None,
                         "2026-10-06T10:00:00", 1)
    row = repo.hole_aufnahme(conn, row)
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    assert repo.web_eingang(conn, 1, 0) == []


def test_einspeisung_laeuft_genau_einmal_pro_bogen(conn, tg, einst, monkeypatch):
    """Mutant: der Aufruf von ``_fuettere_gespraechszug_aus_brainstorm`` wird
    in BEIDEN Zweigen (``not soll`` und ``elif``) dupliziert statt einmal
    nach dem if/elif zu stehen -- aus einem Bogen wuerden zwei Chatbeitraege."""
    monkeypatch.setattr(workshop, "aktiv", lambda: _ProfilAttrappe(an=True))
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "1000")
    row = _brainstorm_zeile(conn, 1, 540, "Kurzer Satz.", schnittgrund="ende")
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, row, aufnahme._kein_zug, False)
    assert len(repo.web_eingang(conn, 1, 0)) == 1
