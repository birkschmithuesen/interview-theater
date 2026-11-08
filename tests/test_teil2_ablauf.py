"""Die Abnahmespur von Padua Phasen TEIL 2: Phase 5 bis Phase 7 am Stueck.

Ein einziger, deterministischer Durchlauf ohne Netz -- ein falsches
Sprachmodell (``FakeKLM``), ein falscher Richter (``Rundenrichter``) und die
``TelegramAttrappe``, aber der ECHTE ``knoepfe.behandle`` fuer jeden
Knopfdruck und der ECHTE ``erkenner.laufe`` fuer jede Chat-Rueckmeldung. Er
zeigt, dass die Teile von TEIL 2 zusammen tragen:

* **Pruefung vor jeder Anzeige**, hoechstens zwei Runden, protokolliert
  (``repo.prueflaeufe``);
* **Chat wirkt, wo Knoepfe wirken** -- Rueckmeldung zum Ganzen, zu einer
  Szene, "yes, save it", die Formwahl und die Ueberarbeitung im Feinschliff;
* **Formen per Chat, Sprechweisen, die Schlusspruefung** und die
  Stueckpruefung am Ende;
* **kein Volltext im Chat** (``KOERPER-`` steht nur im Text der Szenen,
  nie in einer Nachricht);
* **kein "Noted" ohne Schreibvorgang** im selben Schritt.

Gewartet wird auf jeden Hintergrundlauf ueber seine Sperre UND ueber die
Bedingung, die er am Ende herstellt: ``prueflauf._starte`` gibt die Sperre
VOR der Anzeige frei, eine Sperre allein reicht also nicht als Signal.
"""

import dataclasses
import re
import time

import pytest

import test_dramaturgie_schleife as schleifentest
from interview_theater import (
    entwurf, erkenner, knoepfe, kurzgeschichte, nachpass, phasen, prueflauf,
    repo, sprechweise, stueckpruefung, szene, ueberarbeitung, workshop,
)
from interview_theater.dramaturgie import fanout
from test_dramaturgie_schleife import Rundenrichter
from test_knoepfe import TelegramAttrappe, _druck
from test_stueckpruefung import ANTWORT as STUECK_ANTWORT


@pytest.fixture(autouse=True)
def _ohne_karten(monkeypatch):
    """Diese Tests pruefen den Padua-Prosaweg (P5 Prosa, P6 Rewrite) -- seit
    dem Phasenumbau (Birk 07.10.2026 ~18:12) das Verhalten OHNE
    ``[karten] aktiv``; der Kartenweg steht in ``tests/test_szenenkarte.py``."""
    from interview_theater import workshop as _workshop

    monkeypatch.setattr(_workshop, "szenenkarten_aktiv", lambda *a, **k: False)


CHAT = 1


# ---------------------------------------------------------------------------
# Attrappen
# ---------------------------------------------------------------------------


class FakeKLM:
    """Beide Modellschnittstellen, nach ``art`` verzweigt, ohne Netz.

    ``schema``: die Uebersicht (Stufe A), die Sprechweisen und der Erkenner
    (der die naechste vorbereitete ``aenderungen``-Liste bekommt).
    ``prosa``: Szenen (Koerper ``KOERPER-<n>``), die Kurzgeschichte (zwei
    Abschnitte, ``KOERPER-G<n>``) und die Stueckpruefung. Jeder Aufruf wird
    als ``(art, nutzer)`` gemerkt."""

    def __init__(self):
        self.schema_aufrufe: list[tuple[str, str]] = []
        self.prosa_aufrufe: list[tuple[str, str]] = []
        self.erkenner_antworten: list[list[dict]] = []
        self._szenen = 0
        self._geschichten = 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               bei_teil=None, **_kw):
        self.schema_aufrufe.append((art, nutzer))
        if art == entwurf.ART_UEBERSICHT:
            return {
                "logline": "A mother and her daughter pack up a flat.",
                "setting": "A hallway, moving boxes.",
                "figuren_zeilen": ["Mother -- impatient", "Mira -- drifting away"],
                "spannungsbogen": "From packing to the one box nobody opens.",
                "szenen_was_passiert": [
                    "Mira and her mother carry boxes.",
                    "The mother finds the box Mira hid.",
                ],
            }
        if art == sprechweise.ART:
            return {"sprechweisen": ["Mother: clipped, impatient",
                                     "Mira: short sentences"]}
        if art == "erkenner":
            aenderungen = (self.erkenner_antworten.pop(0)
                           if self.erkenner_antworten else [])
            return {"aenderungen": aenderungen}
        raise AssertionError(f"unerwarteter Schema-Aufruf: {art}")

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None, **_kw):
        self.prosa_aufrufe.append((art, nutzer))
        if art == stueckpruefung.ART:
            return STUECK_ANTWORT
        if art in (kurzgeschichte.ART, nachpass.ART_PROSA):
            self._geschichten += 1
            g = self._geschichten
            return "".join(
                f"## {n}. Part {n}\nZusammenfassung: Part {n} of the story.\n\n"
                f"MIRA: The boxes are still standing here, KOERPER-G{g}, "
                f"part {n}, and nobody moved them.\n"
                f"MOTHER: Then carry them yourself, I am tired of waiting.\n\n"
                for n in (1, 2)
            )
        self._szenen += 1
        n = self._szenen
        return (
            f"TITEL: Hallway {n}\nKURZ: They meet.\n"
            "ZUSAMMENFASSUNG: Mira and her mother meet among the boxes.\n"
            "ANDERS GEMACHT: nothing\n\n"
            f"MIRA: The boxes are still standing here, KOERPER-{n}, "
            "and nobody moved them.\n"
            "MOTHER: Then carry them yourself, I am tired of waiting.\n"
        )

    def szenen_aufrufe(self, *, ab: int = 0) -> list[tuple[str, str]]:
        """Die Prosa-Aufrufe eines Szenenlaufs (nicht Geschichte, nicht
        Stueckpruefung) ab Index ``ab``."""
        return [(a, n) for a, n in self.prosa_aufrufe[ab:]
                if a not in (kurzgeschichte.ART, nachpass.ART_PROSA,
                             stueckpruefung.ART)]


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------


_SPERREN = (
    lambda: szene._sperre_fuer(CHAT),
    lambda: kurzgeschichte._sperre_fuer(CHAT),
    lambda: entwurf._sperre_fuer(CHAT),
    lambda: sprechweise._sperre_fuer(CHAT),
)


def _warte_auf(bedingung, timeout=30.0, was="Bedingung"):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.02)
    raise AssertionError(f"{was} nicht rechtzeitig erfuellt")


def _ruhig() -> bool:
    return not any(s().locked() for s in _SPERREN)


def _warte_bis_ruhig():
    """Jede Sperre, die ein Lauf genommen haben kann, einmal nehmen und
    freigeben -- und danach pruefen, dass keine wieder belegt ist (ein
    ``danach`` kann gleich den naechsten Lauf anstossen)."""
    for _ in range(3):
        for sperre in _SPERREN:
            s = sperre()
            assert s.acquire(timeout=30), "Hintergrundlauf nicht rechtzeitig fertig"
            s.release()
        time.sleep(0.05)
        if _ruhig():
            return
    _warte_auf(_ruhig, was="alle Sperren frei")


def _knopf(conn, daten):
    return repo.hole_knopf(conn, knoepfe._id_aus_daten(daten))


def _letzte_leiste(conn, tg, art, wert=None):
    """``callback_data`` des Knopfes ``art`` in der LETZTEN Leiste -- oder
    ``None``."""
    if not tg.knoepfe:
        return None
    for _b, d in tg.knoepfe[-1][2]:
        k = _knopf(conn, d)
        if k["art"] == art and (wert is None or k["wert"] == wert):
            return d
    return None


def _texte(tg, ab=0):
    return [t for _, t in tg.gesendet[ab:]]


def _laeufe(conn):
    return repo.prueflaeufe(conn, CHAT)


def _fassungen(conn, nummer):
    sid = next(s["id"] for s in repo.hole_szenen(conn, CHAT) if s["nummer"] == nummer)
    return conn.execute(
        "SELECT COUNT(*) FROM szenenfassung WHERE szene_id = ?", (sid,)).fetchone()[0]


def _szene(conn, nummer):
    return next(s for s in repo.hole_szenen(conn, CHAT) if s["nummer"] == nummer)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    # Die Richter-Attrappe findet die Szenennummer auch im englischen Kopf.
    monkeypatch.setattr(schleifentest, "_SZENE_IM_KOPF", re.compile(
        r"(?:Das ist Szene|Repliken von Szene|This is scene) (\d+)"))
    yield
    workshop.vergiss()


# ---------------------------------------------------------------------------
# Die Spur
# ---------------------------------------------------------------------------


def test_padua_teil2_phase_5_bis_7(conn, einst, padua, monkeypatch):
    assert prueflauf.aktiv() and ueberarbeitung.aktiv()
    einst = dataclasses.replace(einst, web_url="https://x/theatersoap")
    tg = TelegramAttrappe()
    klm = FakeKLM()

    # Richterplan: Szene 1, B1 -- Runde 1 Score 0 (Auftrag), Runde 2 Score 2
    # (gut). Alles andere bekommt keine Antwort und damit weder Befund noch
    # Auftrag. (Der Entwurf sagte [1, 2]; ein Score 1 ist aber "verdacht" und
    # erzeugt nach ``fanout.auftraege`` keinen Auftrag -- erst 0 tut das.)
    richter = Rundenrichter({("b1", 1): [0, 2]})
    monkeypatch.setattr(fanout, "waehle_richter", lambda *a, **k: richter)

    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "A hallway, moving boxes.")
    repo.setze_arbeitsstand(
        conn, CHAT, "geschichte",
        "A mother and her daughter pack up a flat.\nEnding: one box stays closed.",
    )
    repo.setze_arbeitsstand(conn, CHAT, "figuren_fixiert_am", repo._jetzt())
    repo.setze_arbeitsstand(conn, CHAT, "szenen_anzahl", "2")
    repo.setze_figur(conn, CHAT, "Mother", "impatient, wants it over")
    repo.setze_figur(conn, CHAT, "Mira", "quiet, keeps one box hidden")
    # Die USA-Frage ist beantwortet (Schweiz) -- sie steht keinem Eintritt
    # und keinem Lauf im Weg.
    repo.setze_szene_usa(conn, CHAT, False)
    phasen.setze(conn, CHAT, 5, "befehl")

    schritte: dict[int, tuple[int, int]] = {}
    beginn = [0]

    def schritt_anfang():
        beginn[0] = len(tg.gesendet)

    def schritt_ende(nummer):
        schritte[nummer] = (beginn[0], len(tg.gesendet))

    def _chat(text, aenderungen):
        """Eine Gruppennachricht in ``nachricht``, dann der echte Erkenner mit
        der vorbereiteten Antwort -- und warten, bis alle Laeufe ruhen."""
        tg.naechste_message_id += 1
        repo.merke_nachricht(conn, CHAT, tg.naechste_message_id, "Mert", 0, "text",
                             text, repo._jetzt())
        klm.erkenner_antworten = [aenderungen]
        erkenner.laufe(klm, tg, conn, einst, CHAT)

    def _druecke(art, wert=None, query=None):
        daten = _letzte_leiste(conn, tg, art, wert)
        assert daten is not None, f"kein Knopf {art} ({wert}) in der letzten Leiste"
        assert knoepfe.behandle(conn, tg, klm, einst,
                                _druck(daten, query_id=query or f"{art}{wert}")) is True

    # --- 1. Stufe A, dann Stufe B Szene 1 durch den Prueflauf ---------------
    schritt_anfang()
    assert entwurf.starte_uebersicht(conn, tg, klm, einst, CHAT) is not None
    _warte_bis_ruhig()
    _druecke(knoepfe.ART_UEBERSICHT_PASST)
    _warte_auf(lambda: len(_laeufe(conn)) == 1
               and _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST) is not None
               and _ruhig(), was="Szene 1 geprueft und gezeigt")
    (lauf1,) = _laeufe(conn)
    assert (lauf1["phase"], lauf1["ziel"], lauf1["szene_nummer"]) == (5, "szene", 1)
    assert lauf1["ueberarbeitungen"] == 1, dict(lauf1)
    assert lauf1["runden"] == 2, dict(lauf1)
    assert lauf1["fragen"] == ",".join(prueflauf.FRAGEN_PROSASZENE)
    # Die Ueberarbeitung lief als eigener Szenenaufruf (Erstfassung + eine).
    assert [a for a, _n in klm.szenen_aufrufe()][:2] == [
        szene.ART, prueflauf.ART_UEBERARBEITUNG]
    # Die Erstfassung ist gemerkt ("Show first draft").
    assert _szene(conn, 1)["erstentwurf_fassung"] is not None
    schritt_ende(1)

    # --- 2. Szene 1 und 2 abnehmen -> automatisch Phase 6, Gesamtpruefung ----
    schritt_anfang()
    _druecke(knoepfe.ART_SZENE_PASST, "1", "s1")
    _warte_auf(lambda: any(z["ziel"] == "szene" and z["szene_nummer"] == 2
                           for z in _laeufe(conn))
               and _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST, "2") is not None
               and _ruhig(), was="Szene 2 geprueft und gezeigt")
    _druecke(knoepfe.ART_SZENE_PASST, "2", "s2")
    assert phasen.aktuelle(conn, CHAT) == 6
    _warte_auf(lambda: any(z["ziel"] == "geschichte" and z["phase"] == 6
                           for z in _laeufe(conn))
               and _letzte_leiste(conn, tg, knoepfe.ART_GESCHICHTE_PASST) is not None
               and _ruhig(), was="Gesamtpruefung beim Eintritt in Phase 6")
    (ganz6,) = [z for z in _laeufe(conn) if z["ziel"] == "geschichte"]
    assert ganz6["fragen"] == "a2,a6,a9,a11"
    assert ganz6["phase"] == 6
    schritt_ende(2)

    # --- 3. Rueckmeldung zum Ganzen per Chat --------------------------------
    schritt_anfang()
    vorher_prosa = len(klm.prosa_aufrufe)
    vorher_leisten = len(tg.knoepfe)
    _chat("make the whole story darker",
          [{"art": "text_ueberarbeiten", "wert": "make the whole story darker"}])
    _warte_auf(lambda: len(tg.knoepfe) > vorher_leisten
               and _letzte_leiste(conn, tg, knoepfe.ART_GESCHICHTE_PASST) is not None
               and _ruhig(), was="ueberarbeitete Geschichte gezeigt")
    geschichte = [n for a, n in klm.prosa_aufrufe[vorher_prosa:]
                  if a == kurzgeschichte.ART]
    assert geschichte and "darker" in geschichte[0]
    hinweis = tg.knoepfe[-1][1]
    assert "KOERPER-" not in hinweis
    assert not ueberarbeitung.gesamttext_fixiert(conn, CHAT)
    schritt_ende(3)

    # --- 4. "yes, save it" per Chat fixiert das Ganze, Szene 1 wird geprueft -
    schritt_anfang()
    _chat("yes, save it", [{"art": "fassung_abnehmen", "wert": ""}])
    assert ueberarbeitung.gesamttext_fixiert(conn, CHAT)
    _warte_auf(lambda: any(z["ziel"] == "szene" and z["phase"] == 6
                           and z["szene_nummer"] == 1 for z in _laeufe(conn))
               and _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST, "1") is not None
               and _ruhig(), was="Szene 1 in Phase 6 geprueft")
    schritt_ende(4)

    # --- 5. Szene 1 per Chat aendern ----------------------------------------
    schritt_anfang()
    fassungen_1 = _fassungen(conn, 1)
    vorher_prosa = len(klm.prosa_aufrufe)
    vorher_leisten = len(tg.knoepfe)
    prosa_vor_5 = (_szene(conn, 1)["prosa"] or "").strip()
    assert "KOERPER-" in prosa_vor_5
    auftraege_5 = []
    echter_starte = szene.starte

    def spion_starte(c, t, k, e, cid, auftrag, *a, **kw):
        auftraege_5.append(auftrag)
        return echter_starte(c, t, k, e, cid, auftrag, *a, **kw)

    monkeypatch.setattr(szene, "starte", spion_starte)
    _chat("scene 1: make the mother angrier",
          [{"art": "text_ueberarbeiten", "wert": "scene 1: make the mother angrier"}])
    _warte_auf(lambda: len(tg.knoepfe) > vorher_leisten
               and _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST, "1") is not None
               and _ruhig(), was="ueberarbeitete Szene 1 gezeigt")
    monkeypatch.setattr(szene, "starte", echter_starte)
    assert len(auftraege_5) == 1, auftraege_5
    neu = [n for a, n in klm.szenen_aufrufe(ab=vorher_prosa) if a == szene.ART]
    assert len(neu) == 1, klm.prosa_aufrufe[vorher_prosa:]
    assert "angrier" in neu[0]
    # Der Prosalauf sieht die bestehende Prosa der Szene: ``BISHER_MARKER``
    # stand im Auftrag (``szene.ueberarbeitungsauftrag``) -- er ist Protokoll
    # und wird vor dem Modell herausgenommen (``szene.py``,
    # ``replace(BISHER_MARKER, "")``), an seiner Stelle steht der Block
    # ``BISHER_KOPF`` mit genau der Prosa, die vor dem Lauf gespeichert war.
    assert auftraege_5 and szene.BISHER_MARKER in auftraege_5[0]
    assert szene.BISHER_MARKER not in neu[0]
    assert szene.T.BISHER_KOPF in neu[0]
    assert prosa_vor_5 in neu[0]
    assert _fassungen(conn, 1) > fassungen_1
    assert phasen.aktuelle(conn, CHAT) == 6
    schritt_ende(5)

    # --- 6. Szene 1 und 2 abnehmen -> EINE Abschlussnachricht, Phase 7 -------
    schritt_anfang()
    _druecke(knoepfe.ART_SZENE_PASST, "1", "p6s1")
    _warte_auf(lambda: _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST, "2") is not None
               and _ruhig(), was="Szene 2 in Phase 6 geprueft")
    _druecke(knoepfe.ART_SZENE_PASST, "2", "p6s2")
    fertig6 = ueberarbeitung.T._TEXT_6_FERTIG.format(gesamt=2)
    assert _texte(tg).count(fertig6) == 1
    assert phasen.aktuelle(conn, CHAT) == 7
    schritt_ende(6)

    # --- 7. Formwahl: EINE Nachricht ohne Knoepfe, Antwort im Chat ----------
    schritt_anfang()
    formwahl = [t for t in _texte(tg) if "Which form for each number?" in t]
    assert len(formwahl) == 1
    assert not any("Which form for each number?" in t for _c, t, _l in tg.knoepfe)
    vorher_leisten = len(tg.knoepfe)
    _chat("1 chorus, 2 dialogue",
          [{"art": "formen_setzen", "wert": "1:chorus|2:dialogue"}])
    assert {s["nummer"]: s["form"] for s in repo.hole_szenen(conn, CHAT)} == {
        1: "chor", 2: "dialog"}
    _warte_bis_ruhig()
    _warte_auf(lambda: _letzte_leiste(conn, tg, knoepfe.ART_SPRECHWEISEN_PASST)
               is not None, was="Sprechweisen angeboten")
    # Zwei neue Leisten: die Notiert-Meldung der Formwahl (nur ihr Undo-Knopf,
    # Karte U) und GENAU EINE Sprechweisen-Nachricht -- je Figur eine Zeile.
    neue = tg.knoepfe[vorher_leisten:]
    # chat_id 1 steht in keiner italienisch_ab_phase6_chats-Liste -- englisch.
    assert [t.splitlines()[0] for _c, t, _l in neue][0].startswith("Noted:")
    assert len(neue) == 2, [t for _c, t, _l in neue]
    sprechweisen = tg.knoepfe[-1][1]
    assert len(sprechweisen.splitlines()) == 1 + 2
    assert "Mother: clipped, impatient" in sprechweisen
    assert "Mira: short sentences" in sprechweisen
    schritt_ende(7)

    # --- 8. Sprechweisen speichern -> Szene 1 in die Buehnenfassung ----------
    schritt_anfang()
    _druecke(knoepfe.ART_SPRECHWEISEN_PASST, query="sw")
    assert ueberarbeitung.sprechweisen_fixiert(conn, CHAT)
    _warte_auf(lambda: any(z["ziel"] == "szene" and z["phase"] == 7
                           and z["szene_nummer"] == 1 for z in _laeufe(conn))
               and _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST, "1") is not None
               and _ruhig(), was="Buehnenszene 1 geprueft und gezeigt")
    assert (_szene(conn, 1)["volltext"] or "").strip()
    (b1,) = [z for z in _laeufe(conn) if z["phase"] == 7 and z["ziel"] == "szene"]
    assert b1["fragen"] == ",".join(prueflauf.FRAGEN_BUEHNENSZENE)
    schritt_ende(8)

    # --- 9. Feinschliff-Rueckmeldung per Chat (B2) --------------------------
    schritt_anfang()
    fassungen_1 = _fassungen(conn, 1)
    vorher_prosa = len(klm.prosa_aufrufe)
    vorher_leisten = len(tg.knoepfe)
    _chat("make the mother angrier",
          [{"art": "text_ueberarbeiten", "wert": "make the mother angrier"}])
    _warte_auf(lambda: len(tg.knoepfe) > vorher_leisten
               and _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST, "1") is not None
               and _ruhig(), was="ueberarbeitete Buehnenszene 1 gezeigt")
    neu = [n for a, n in klm.szenen_aufrufe(ab=vorher_prosa) if a == szene.ART]
    assert len(neu) == 1 and "angrier" in neu[0]
    assert _fassungen(conn, 1) > fassungen_1
    schritt_ende(9)

    # --- 10. Szene 1 und 2 abnehmen -> Schlusspruefung, Stueckpruefung ------
    schritt_anfang()
    _druecke(knoepfe.ART_SZENE_PASST, "1", "p7s1")
    _warte_auf(lambda: _letzte_leiste(conn, tg, knoepfe.ART_SZENE_PASST, "2") is not None
               and _ruhig(), was="Buehnenszene 2 geprueft und gezeigt")
    assert (_szene(conn, 2)["volltext"] or "").strip()
    _druecke(knoepfe.ART_SZENE_PASST, "2", "p7s2")
    fertig = ueberarbeitung.T._TEXT_TEXTBUCH_FERTIG
    _warte_auf(lambda: any(t.startswith(fertig) for t in _texte(tg)),
               was="'The script is complete'")
    _warte_bis_ruhig()
    schluss = [z for z in _laeufe(conn) if z["ziel"] == "geschichte" and z["phase"] == 7]
    assert len(schluss) == 1
    assert any(a == stueckpruefung.ART for a, _n in klm.prosa_aufrufe)
    assert len([t for t in _texte(tg) if t.startswith(fertig)]) == 1
    # Unter dem Padua-Profil ist es die englische Zeile "The script is complete".
    assert (re.search(r"\bscript\b", fertig, re.IGNORECASE)
            and "complete" in fertig.lower()), fertig
    assert all((s["fertig_am"] or "").strip() for s in repo.hole_szenen(conn, CHAT))
    schritt_ende(10)

    # --- Global -------------------------------------------------------------
    # Kein Volltext im Chat -- weder in einer Nachricht noch in einer Leiste.
    for text in _texte(tg):
        assert "KOERPER-" not in text, text
    for _c, text, _l in tg.knoepfe:
        assert "KOERPER-" not in text, text
    # "Noted:" (chat_id 1 steht in keiner italienisch_ab_phase6_chats-Liste
    # -- englisch) nur in dem Schritt, in dem der Erkenner wirklich
    # geschrieben hat: der Formwahl (Schritt 7).
    for i, (_c, text) in enumerate(tg.gesendet):
        if text.lstrip().lower().startswith("noted:"):
            schritt = next(n for n, (a, b) in schritte.items() if a <= i < b)
            assert schritt == 7, (schritt, text)
    anfang7, ende7 = schritte[7]
    assert any(t.lstrip().startswith("Noted:") for _c, t in tg.gesendet[anfang7:ende7])
    for zeile in _laeufe(conn):
        assert zeile["ueberarbeitungen"] <= 2, dict(zeile)
        assert zeile["runden"] <= 2, dict(zeile)
        assert zeile["dauer_ms"] is not None, dict(zeile)
