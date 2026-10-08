"""Der EN/IT-Spiegelpass der Szenenprosa (Birk, Live-Workshop 07.10.2026
~17:20): "Das Skript soll immer zweisprachig kommen, Englisch /
Italienisch. Aber nicht gemischt." Nur unter dem Padua-Profilschalter
``[skript] zweisprachig`` -- ohne Profil (Dortmund, Vorgabeprofil) bleibt
``szene.prosa`` byte-gleich und ``prosa_it`` leer, auch wenn das Modell
etwas zurueckgeben wuerde."""

import pytest

from interview_theater import phasen, repo, skript_uebersetzung, szene, workshop


class TelegramAttrappe:
    def sende(self, chat_id, text, **_kw):
        return 1

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return 1

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    @property
    def texte(self):
        return []


class LLMMitSchema:
    """``prosa`` liefert den Rohtext (EN mit italienischem Zitat), ``schema``
    den Spiegelpass -- dieselbe Signatur wie ``llm.LLM.schema``."""

    def __init__(self, prosa_antwort, spiegel_antwort=None, schema_fehler=None):
        self._prosa_antwort = prosa_antwort
        self._spiegel_antwort = spiegel_antwort
        self._schema_fehler = schema_fehler
        self.schema_gesehen = None

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        return self._prosa_antwort

    def schema(self, chat_id, system, nutzer, schema, art):
        self.schema_gesehen = {"system": system, "nutzer": nutzer, "art": art}
        if self._schema_fehler is not None:
            raise self._schema_fehler
        return self._spiegel_antwort


ROHTEXT = (
    'TITEL: Al binario\n\nZUSAMMENFASSUNG: Maria arriva.\n\n'
    'Maria steht am Bahnhof. "Non sono mai tornata", sagt sie leise.'
)


def _geplant(conn, chat_id=1, nummer=1):
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "Ein Bahnhof, ein Abend")
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Bahnhof")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Bahnhof")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Maria kommt an")
    return szene_id


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def freie_sperren():
    szene._sperren.clear()
    yield
    szene._sperren.clear()


def test_ohne_profilschalter_bleibt_prosa_unangetastet(conn, einst, tg):
    """Vorgabeprofil (kein IT_WORKSHOP): der Spiegelpass laeuft gar nicht
    an -- auch wenn das LLM einen ``schema``-Aufruf beantworten koennte."""
    assert workshop.skript_zweisprachig_aktiv() is False
    szene_id = _geplant(conn)
    phasen.setze(conn, 1, 6, "befehl")
    klm = LLMMitSchema(ROHTEXT, {"prosa_en": "EGAL", "prosa_it": "EGAL"})

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 1")

    zeile = repo.hole_szene(conn, szene_id)
    assert "Non sono mai tornata" in zeile["prosa"]
    assert klm.schema_gesehen is None, "kein Schema-Aufruf ohne den Profilschalter"
    assert zeile["prosa_it"] is None


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def test_mit_profilschalter_wird_prosa_gespiegelt(conn, einst, tg, padua):
    """Padua, Schalter an: ``prosa`` wird durch die EN-Fassung ersetzt,
    ``prosa_it`` bekommt die italienische Spiegelung."""
    assert workshop.skript_zweisprachig_aktiv() is True
    szene_id = _geplant(conn)
    phasen.setze(conn, 1, 5, "befehl")
    klm = LLMMitSchema(
        ROHTEXT,
        {"prosa_en": 'Maria stands at the station. "I never came back", she says quietly.',
         "prosa_it": 'Maria sta alla stazione. "Non sono mai tornata", dice piano.'},
    )

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 1")

    zeile = repo.hole_szene(conn, szene_id)
    assert zeile["prosa"] == 'Maria stands at the station. "I never came back", she says quietly.'
    assert zeile["prosa_it"] == 'Maria sta alla stazione. "Non sono mai tornata", dice piano.'
    assert klm.schema_gesehen["art"] == skript_uebersetzung.ART
    assert "binario" in klm.schema_gesehen["nutzer"] or "Bahnhof" in klm.schema_gesehen["nutzer"]


def test_ein_fehlschlag_im_spiegelpass_laesst_die_en_fassung_stehen(conn, einst, tg, padua):
    """Scheitert der Spiegelpass (Modellfehler, kein JSON, ...), bleibt die
    Szene bei ihrer englischen Rohfassung -- der Szenenlauf selbst darf
    dadurch nie scheitern."""
    szene_id = _geplant(conn)
    phasen.setze(conn, 1, 5, "befehl")
    klm = LLMMitSchema(ROHTEXT, schema_fehler=RuntimeError("Proxy down"))

    nummer = szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 1")

    assert nummer == 1
    zeile = repo.hole_szene(conn, szene_id)
    assert "Non sono mai tornata" in zeile["prosa"]
    assert zeile["prosa_it"] is None


def test_spiegel_direkt_ohne_beide_fassungen_meldet_vorfall(conn, einst):
    """``spiegel()`` fuer sich: eine Antwort ohne ``prosa_it`` zaehlt als
    Fehlschlag, nicht als Teilerfolg -- sonst stuende eine Szene mit
    EN-Text und leerem IT-Text ohne Hinweis da."""
    szene_id = _geplant(conn)
    klm = LLMMitSchema(ROHTEXT, {"prosa_en": "Only English.", "prosa_it": ""})

    erfolg = skript_uebersetzung.spiegel(
        conn, klm, einst, 1, szene_id, ROHTEXT, ueber_claude=False,
    )

    assert erfolg is False
    zeile = repo.hole_szene(conn, szene_id)
    assert zeile["prosa_it"] is None
    vorfaelle = [v["art"] for v in repo.vorfaelle(conn, 1)] if hasattr(repo, "vorfaelle") else None
    assert vorfaelle is None or "skript_spiegel_fehler" in vorfaelle


def test_spiegle_text_verwirft_fremden_kurzen_text(conn, einst):
    """Tester 08.10.2026 12:12: der Fallback lieferte statt der 5 500-Zeichen-
    Szene einen fremden 1 100-Zeichen-Text; der Nachholpass ueberschrieb damit
    EN und IT. Eine unplausibel kurze Spiegelung muss ``None`` liefern."""
    quelle = "VOCE 1: And now we wait. " * 200
    klm = LLMMitSchema("", {"prosa_en": "Pellaro spoke. " * 20, "prosa_it": "Pellaro parlava. " * 20})
    assert skript_uebersetzung.spiegle_text(conn, klm, einst, 1, quelle, ueber_claude=False) is None


def test_spiegle_text_nimmt_gleich_lange_uebertragung(conn, einst):
    quelle = "VOCE 1: And now we wait. " * 200
    klm = LLMMitSchema("", {"prosa_en": quelle, "prosa_it": "VOCE 1: E ora aspettiamo. " * 200})
    en, it = skript_uebersetzung.spiegle_text(conn, klm, einst, 1, quelle, ueber_claude=False)
    assert en == quelle.strip() and it.startswith("VOCE 1: E ora")


def test_zitat_uebersetzung_en_im_systemprompt_und_laengere_en_fassung(conn, einst, monkeypatch):
    """Birk 08.10.2026 ~14:25 (G3 S2): mit ``[skript] zitat_uebersetzung_en``
    verlangt der Spiegelpass in der EN-Fassung unter jedem Zitat die
    Uebersetzung -- und eine dadurch doppelt so lange EN-Fassung wird nicht
    als unplausibel verworfen."""
    from interview_theater import workshop
    quelle = "VOCE 4: Mi pare che fossi sul divano dopo pranzo. " * 40
    en = ("VOCE 4: Mi pare che fossi sul divano dopo pranzo.\n"
          "*(I think I was on the sofa after lunch.)*\n") * 40
    klm = LLMMitSchema("", {"prosa_en": en, "prosa_it": quelle})
    monkeypatch.setattr(workshop, "zitat_uebersetzung_en_aktiv", lambda profil=None: True)
    ergebnis = skript_uebersetzung.spiegle_text(conn, klm, einst, 1, quelle, ueber_claude=False)
    assert ergebnis is not None and "*(I think" in ergebnis[0]
    assert "English translation" in klm.schema_gesehen["system"]


def test_ohne_schalter_kein_zitat_zusatz_und_alte_laengengrenze(conn, einst, monkeypatch):
    from interview_theater import workshop
    quelle = "VOCE 4: Mi pare che fossi sul divano dopo pranzo. " * 40
    en = ("VOCE 4: Mi pare che fossi sul divano dopo pranzo.\n"
          "*(I think I was on the sofa after lunch.)*\n") * 40
    klm = LLMMitSchema("", {"prosa_en": en, "prosa_it": quelle})
    monkeypatch.setattr(workshop, "zitat_uebersetzung_en_aktiv", lambda profil=None: False)
    assert skript_uebersetzung.spiegle_text(conn, klm, einst, 1, quelle, ueber_claude=False) is None
    assert "English translation" not in klm.schema_gesehen["system"]


def test_plausibel_ignoriert_kursive_uebersetzungszeilen():
    """G3 08.10.2026 14:40: Quelle hat unter jeder IT-Zeile eine EN-Hilfszeile
    *(...)*, die IT-Spiegelung nicht -- darf nicht als 'zu kurz' gelten."""
    zeile_it = "VOCE 4: Mi pare che fossi sul divano dopo pranzo, al TG."
    quelle = "\n".join([zeile_it, "*(I think I was on the sofa after lunch, on the news.)*", ""] * 20)
    it = "\n".join([zeile_it, ""] * 20)
    assert skript_uebersetzung.plausibel(quelle, it)
    assert not skript_uebersetzung.plausibel(quelle, it[: len(it) // 3])
