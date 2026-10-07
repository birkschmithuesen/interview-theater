"""QUICKFIX Birk, 07.10.2026 (Testgruppe Padua, chat_id 7000000000099, 07:16
UTC): ein Klick in der Phasenleiste auf eine schon besuchte Phase soll nur
den Zustand WIEDERHERSTELLEN -- Phase setzen, hoechstens eine kurze
System-Zeile, aber keine neue Eintrittskarte und kein Modellzug
(``knoepfe.eintritt_in_phase``). Gemessen: journal zeigte fuer
chat_id=7000000000099 schon lange vor dem Klick 'Phase 3 - Interviews' und
'Phase 4 - Frame' als entschieden -- trotzdem feuerte jeder Klick die volle
Eintrittskarte plus Begruessung erneut.

Der ALLERERSTE Eintritt in eine Phase bleibt unveraendert (volle Karte,
siehe ``test_phase_klick.test_klick_und_befehl_landen_in_derselben_phase``).
"""

from interview_theater import befehle, db, knoepfe, phasen, repo

CHAT = 7_000_000_000_002


class Einstellungen:
    bot_name = "gruppe1"


class TgAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


def _gruppe(tmp_path, name="t.db"):
    conn = db.verbinde(str(tmp_path / name))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    return conn


def test_ein_erneuter_klick_auf_eine_besuchte_phase_zeigt_keine_karte(tmp_path, monkeypatch):
    """Die Gruppe war schon in Phase 3 (journal traegt das), springt auf 4
    und zurueck auf 3 -- der Ruecksprung darf die Eintrittskarte nicht noch
    einmal zeigen."""
    conn = _gruppe(tmp_path)
    tg = TgAttrappe()
    aufrufe = []
    monkeypatch.setattr(
        knoepfe, "eintritt_in_phase",
        lambda *a, **k: aufrufe.append(a[-1] if a else None),
    )
    # Erster Besuch von Phase 3: volle Karte (unveraendertes Verhalten).
    befehle.wechsle_phase(conn, tg, None, Einstellungen(), CHAT, 3, quelle="web")
    assert len(aufrufe) == 1
    # Weiter nach 4 (ebenfalls erster Besuch).
    befehle.wechsle_phase(conn, tg, None, Einstellungen(), CHAT, 4, quelle="web")
    assert len(aufrufe) == 2
    tg.gesendet.clear()
    aufrufe.clear()
    # Zurueck auf 3 -- eine schon besuchte Phase: NUR die kurze Zeile.
    befehle.wechsle_phase(conn, tg, None, Einstellungen(), CHAT, 3, quelle="web")
    assert aufrufe == []
    assert tg.gesendet == [phasen.meldung(3)]


def test_der_allererste_eintritt_bleibt_voll(tmp_path, monkeypatch):
    conn = _gruppe(tmp_path)
    tg = TgAttrappe()
    aufrufe = []
    monkeypatch.setattr(
        knoepfe, "eintritt_in_phase",
        lambda *a, **k: aufrufe.append(True),
    )
    befehle.wechsle_phase(conn, tg, None, Einstellungen(), CHAT, 5, quelle="befehl")
    assert aufrufe == [True]


def test_dieselbe_phase_ohne_vorherigen_journaleintrag_bleibt_voll(tmp_path, monkeypatch):
    """Wie ``test_phase_klick.test_dieselbe_phase_erzeugt_keinen_journaleintrag``:
    ``repo.setze_phase`` direkt (ohne Journal) ist kein 'schon besucht' --
    sonst wuerde ein Gruppenanlage-Vorbeleger die Karte verschlucken."""
    conn = _gruppe(tmp_path)
    repo.setze_phase(conn, CHAT, 4)
    tg = TgAttrappe()
    aufrufe = []
    monkeypatch.setattr(
        knoepfe, "eintritt_in_phase",
        lambda *a, **k: aufrufe.append(True),
    )
    befehle.wechsle_phase(conn, tg, None, Einstellungen(), CHAT, 4, quelle="web")
    assert aufrufe == [True]
