"""Phase 7: Ort/Figuren aus dem neu geschriebenen Stage Script ins
Stueckmodell (Karte t_fd88600b ersetzt den Zweit-Schreiber
``repo.aktualisiere_karte_und_werkbank``). Der Modellaufruf ist ein
Testdouble; geschrieben wird NUR ueber ``stueck``."""

from interview_theater import karten_nachzug, repo, stueck
from tests.stueck_hilfe import lege_karte_an


class LLM:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append(art)
        return self.antwort


def _mit_text(conn, text="TEXT", **karte):
    sid = lege_karte_an(conn, bestaetigt=True, **karte)
    repo.setze_stagescript(conn, sid, text, None)
    return sid


def _k(conn, sid):
    return stueck.karte(conn, repo.hole_szene(conn, sid))


def test_neuer_ort_eine_stelle_alle_ansichten(conn, einst):
    sid = _mit_text(conn, ort="Bar")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "Piazza", "wer": "", "modus": "none"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["ort"] == "Piazza" and _k(conn, sid)["ort"] == "Piazza"


def test_veralteter_text_schreibt_nichts(conn, einst):
    sid = _mit_text(conn, text="NEU", ort="Bar")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "Piazza", "wer": "", "modus": "none"}),
                              einst, 1, sid, "ALT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["ort"] == "Bar"


def test_neue_figur_nur_wenn_figur_existiert(conn, einst):
    repo.setze_figur(conn, 1, "Anna", "")
    vorher = len(repo.figuren(conn, 1))
    sid = _mit_text(conn)
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "Anna, an audience member", "modus": "none"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert len(repo.figuren(conn, 1)) == vorher
    assert [b["name"] for b in repo.besetzung(conn, sid)] == ["Anna"]


def test_abnahme_bleibt_und_eigene_szene_nicht_veraltet(conn, einst):
    sid = _mit_text(conn, ort="Bar")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "Piazza", "wer": "", "modus": "none"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["karte_bestaetigt_am"]
    assert repo.offene_veraltet(conn, 1) == []


def test_abschnittskoepfe_und_sprecherzeilen(conn, einst):
    for n in ("Anna", "Berta", "Clara", "Dario"):
        repo.setze_figur(conn, 1, n, "")
    text = "CLARA (moderator)\nArrives.\n\nBERTA, DARIO\nWait.\n\nANNA: Hi.\n"
    sid = _mit_text(conn, text=text, wer="Anna")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "Clara", "modus": "none"}),
                              einst, 1, sid, text, ueber_claude=False)
    assert {b["name"] for b in repo.besetzung(conn, sid)} == {"Anna", "Berta", "Clara", "Dario"}


def test_kopfzeile_erkennt_keine_unbekannten_namen(conn, einst):
    repo.setze_figur(conn, 1, "Clara", "")
    text = "THE CAMERA (one of us, dressed as a passer-by)\nStays away.\n\nEVERYONE\nNods.\n"
    sid = _mit_text(conn, text=text, wer="Clara and friends")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "Clara", "modus": "none"}),
                              einst, 1, sid, text, ueber_claude=False)
    assert {b["name"] for b in repo.besetzung(conn, sid)} == {"Clara"}


def test_modus_nur_bei_moment(conn, einst):
    sid = _mit_text(conn, typ="moment", modus="microphone")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "", "modus": "collective"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert _k(conn, sid)["modus"] == "collective"


def test_modus_bleibt_bei_anderem_typ(conn, einst):
    sid = _mit_text(conn, typ="spoken", modus="none")
    karten_nachzug.ziehe_nach(conn, LLM({"ort": "", "wer": "", "modus": "collective"}),
                              einst, 1, sid, "TEXT", ueber_claude=False)
    assert _k(conn, sid)["modus"] == "none"


def test_fehler_laesst_alles_stehen(conn, einst):
    class Kaputt:
        def schema(self, *a, **k):
            raise RuntimeError("boom")

    sid = _mit_text(conn, ort="Bar")
    karten_nachzug.ziehe_nach(conn, Kaputt(), einst, 1, sid, "TEXT", ueber_claude=False)
    assert repo.hole_szene(conn, sid)["ort"] == "Bar"


def test_ohne_karte_tut_nichts(conn, einst):
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_stagescript(conn, sid, "TEXT", None)
    klm = LLM({"ort": "Piazza", "wer": "", "modus": "none"})
    karten_nachzug.ziehe_nach(conn, klm, einst, 1, sid, "TEXT", ueber_claude=False)
    assert klm.aufrufe == []


def test_kein_zweitschreiber_mehr():
    assert not hasattr(repo, "aktualisiere_karte_und_werkbank")
