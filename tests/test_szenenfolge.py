"""Tests fuer die Knopf-Navigation durch Phase 6 und 7 (05.09.2026).

Gemessen wird hier dasselbe wie in ``test_knoepfe.py``: dass eine Auswahl
DETERMINISTISCH in der Datenbank landet -- und zusaetzlich die eine Regel, an
der die ganze Konstruktion haengt: **kein Modellaufruf im Knopf-Handler**.
Jeder Knopf, der ein Modell braucht, gibt den Aufruf an einen eigenen Thread
ab (``szenenfolge.starte``); der Handler selbst kehrt sofort zurueck.

Kein Netzzugriff: Telegram ist eine Attrappe, das Sprachmodell ebenso.
"""

import pytest

from interview_theater import knoepfe, phasen, repo, szene, szenenfolge


class TelegramAttrappe:
    """Wie die Attrappe in ``test_knoepfe.py``, plus ``sende_datei`` -- der
    Textbuch-Export in Phase 7."""

    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.beantwortet = []
        self.entfernt = []
        self.dateien = []
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

    def sende_datei(self, chat_id, dateiname, inhalt, beschreibung=""):
        self.dateien.append((chat_id, dateiname, inhalt, beschreibung))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))

    @property
    def texte(self):
        return [t for _, t in self.gesendet]

    @property
    def beschriftungen(self):
        """Alle Knopfbeschriftungen der zuletzt verschickten Leiste."""
        return [b for b, _ in self.knoepfe[-1][2]]


class LLMAttrappe:
    def __init__(self, antwort="VORSCHLAG SZENENFOLGE:\nAm Bahnhof — Maria wartet — Maria"):
        self._antwort = antwort
        self.aufrufe = 0
        self.gesehen = {}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe += 1
        self.gesehen = {
            "chat_id": chat_id, "system": system, "nutzer": nutzer, "art": art,
            "max_tokens": max_tokens, "timeout": timeout,
        }
        return self._antwort


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def freie_sperren():
    szenenfolge._sperren.clear()
    szenenfolge._regienotiz_erwartet.clear()
    szene._sperren.clear()
    yield
    szenenfolge._sperren.clear()
    szenenfolge._regienotiz_erwartet.clear()
    szene._sperren.clear()


def _druecke(conn, tg, einst, beschriftung, klm=None, chat_id=1):
    """Findet den Knopf mit dieser Beschriftung in der zuletzt verschickten
    Leiste und drueckt ihn -- ueber ``behandle``, also inklusive
    Idempotenz-Sperre und answerCallbackQuery, wie im Betrieb."""
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                knoepfe.behandle(
                    conn, tg, klm, einst,
                    {
                        "callback_query_id": "q",
                        "data": daten,
                        "chat_id": chat_id,
                        "chat_titel": "Testgruppe",
                        "message_id": 777,
                    },
                )
                return
    raise AssertionError(f"Knopf {beschriftung!r} steht nicht im Chat: "
                         f"{[b for _, _, l in tg.knoepfe for b, _ in l]}")


def _warte(thread):
    assert thread is not None
    thread.join(timeout=10)
    assert not thread.is_alive()


def _figuren(conn, *namen, chat_id=1):
    for name in namen:
        repo.setze_figur(conn, chat_id, name, f"{name}, aus dem Material")


VORSCHLAG = (
    "Ich habe mir das so gedacht.\n\n"
    "VORSCHLAG SZENENFOLGE:\n"
    "Am Bahnhof — Mira kommt an — Mira, Pal — Dialog\n"
    "In der Kueche — Pal kocht, es wird laut — Pal, Pola — Lied\n"
    "Der Kessel — alle drei stehen fest — Mira, Pola, Pal — Chor\n"
    "\n"
    "Passt euch die Reihenfolge?"
)


# --- Eintritt in Phase 6 --------------------------------------------------


def test_phasenknopf_7_fragt_zuerst_nach_eigenen_ideen(conn, einst, tg):
    """Birk 05.09.2026: eine Gruppe, die schon Szenenideen hat, soll sie
    nicht gegen eine fertige Liste verteidigen muessen. Der Eintritt in die
    Szenentexte ist deshalb dieselbe proaktive Frage wie in jeder anderen
    Phase (``knoepfe.biete_proaktiv``) -- kein eigener Weg fuer dieselbe
    Sache."""
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", 7)

    _druecke(conn, tg, einst, "Weiter zu Szenentexte")

    assert any(t.endswith(knoepfe._TEXT_PROAKTIV) for t in tg.texte)
    assert tg.beschriftungen == [
        knoepfe._TEXT_WIR_ZUERST_KNOPF, knoepfe._TEXT_SCHLAG_VOR_KNOPF,
    ]


def test_schlag_du_vor_in_phase_7_geht_ueber_szenenfolge(conn, einst, tg):
    """"Schlag du vor" braucht ein Modell -- und ruft es NICHT im Handler:
    ``szenenfolge.starte`` kuendigt an und startet einen Thread (Muster:
    ``szene.starte``). In Phase 6 ist es dieser Weg und nicht der allgemeine
    Auftragszug: der Vorschlag hat eine feste Zeilenform und traegt danach
    seine eigenen Knoepfe."""
    klm = LLMAttrappe(VORSCHLAG)
    knoepfe.biete_proaktiv(conn, tg, 1, 7)

    _druecke(conn, tg, einst, knoepfe._TEXT_SCHLAG_VOR_KNOPF, klm=klm)
    # Der Thread laeuft nebenher; auf ihn wird ueber die Sperre gewartet.
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()

    assert klm.aufrufe == 1
    assert klm.gesehen["art"] == szenenfolge.ART


# --- Szenenfolge ----------------------------------------------------------


def test_vorschlag_traegt_die_grundleiste_und_die_zwei_aenderungsknoepfe(conn, tg):
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    assert tg.beschriftungen == [
        knoepfe.TEXT_ANZAHL_KNOPF,
        knoepfe.TEXT_REIHENFOLGE_KNOPF,
        knoepfe.TEXT_EIGENE_IDEE_KNOPF,
        knoepfe.TEXT_ANDERS_KNOPF,
        knoepfe.TEXT_WEITER_KNOPF,
    ]
    # Die Markerzeile geht nie in den Chat -- sie ist Technik, kein Inhalt.
    assert "VORSCHLAG SZENENFOLGE" not in tg.knoepfe[-1][1]
    assert "Am Bahnhof" in tg.knoepfe[-1][1]


def test_vorschlag_ohne_marker_bekommt_keine_knoepfe(conn, tg):
    """Kein Raten: lieber ein Vorschlag ohne Leiste als eine Leiste, die den
    falschen Text speichert (dieselbe Regel wie bei der Speicher-Leiste)."""
    knoepfe.sende_szenenfolge(conn, tg, 1, "Ich haette da drei Szenen im Kopf.")

    assert tg.knoepfe == []
    assert tg.texte == ["Ich haette da drei Szenen im Kopf."]


def test_gefaellt_uns_weiter_legt_die_szenen_an(conn, einst, tg):
    """Der eigentliche Punkt: die zugestimmte Folge landet in der Tabelle
    ``szene`` -- vorher stand sie nur als Fliesstext im Chat."""
    _figuren(conn, "Mira", "Pola", "Pal")
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    _druecke(conn, tg, einst, knoepfe.TEXT_WEITER_KNOPF)

    szenen = repo.hole_szenen(conn, 1)
    assert [s["nummer"] for s in szenen] == [1, 2, 3]
    assert [s["titel"] for s in szenen] == ["Am Bahnhof", "In der Kueche", "Der Kessel"]
    assert szenen[0]["was_passiert"] == "Mira kommt an"
    # Die vierte Spalte ist seit dem 06.09.2026 ein VORSCHLAG: ``form``
    # bleibt leer, bis die Gruppe sie Szene fuer Szene per Knopf bestaetigt
    # (Birk: "Die Form Monolog habe ich niemals eingegeben und aktiv
    # bestaetigt.").
    assert [s["form"] for s in szenen] == [None, None, None]
    assert [s["form_vorschlag"] for s in szenen] == ["dialog", "lied", "chor"]
    # Die Besetzung nur, soweit die Figuren im Arbeitsstand stehen.
    assert [f["name"] for f in repo.szene_figuren(conn, szenen[0]["id"])] == ["Mira", "Pal"]


def test_gefaellt_uns_weiter_fragt_zuerst_nach_der_form_von_szene_1(conn, einst, tg):
    """Nach dem Speichern geht es weiter, ohne dass jemand etwas tippen muss
    -- aber die erste Frage ist die nach der FORM (Birk, 06.09.2026 00:30).
    Der Vorschlag des Bots steht zuerst und ist als solcher markiert."""
    _figuren(conn, "Mira", "Pal")
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    _druecke(conn, tg, einst, knoepfe.TEXT_WEITER_KNOPF)

    assert "Welche Form soll Szene 1 haben?" in tg.knoepfe[-1][1]
    assert tg.beschriftungen[0] == "Dialog" + knoepfe.TEXT_FORM_VORSCHLAG_ZUSATZ
    assert sorted(b.split(" (")[0] for b in tg.beschriftungen) == [
        "Chor", "Dialog", "Lied", "Monolog", "Rap",
    ]


def test_erst_nach_der_form_kommt_die_schreibfrage(conn, einst, tg):
    _figuren(conn, "Mira", "Pal")
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)
    _druecke(conn, tg, einst, knoepfe.TEXT_WEITER_KNOPF)

    _druecke(conn, tg, einst, "Dialog" + knoepfe.TEXT_FORM_VORSCHLAG_ZUSATZ)

    assert repo.hole_szenen(conn, 1)[0]["form"] == "dialog"
    assert tg.beschriftungen == [
        knoepfe.TEXT_SZENE_SCHREIBEN_KNOPF,
        knoepfe.TEXT_SZENE_PLANEN_KNOPF,
        knoepfe.TEXT_SZENE_FORM_KNOPF,
        knoepfe.TEXT_SZENE_UEBERSPRINGEN_KNOPF,
        knoepfe.TEXT_EIGENE_IDEE_KNOPF,
    ]
    assert "Szene 1: Am Bahnhof" in tg.knoepfe[-1][1]


def test_die_gruppe_darf_gegen_den_vorschlag_entscheiden(conn, einst, tg):
    """Der Vorschlag steht zuerst -- er gilt aber nicht. Gesetzt wird, was
    gedrueckt wurde."""
    _figuren(conn, "Mira", "Pal")
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)
    _druecke(conn, tg, einst, knoepfe.TEXT_WEITER_KNOPF)

    _druecke(conn, tg, einst, "Rap")

    assert repo.hole_szenen(conn, 1)[0]["form"] == "rap"


def test_passt_aber_anders_speichert_auch_und_fragt_danach(conn, einst, tg):
    """Birk: eine Gruppe soll einen brauchbaren Vorschlag nicht wegwerfen
    muessen, nur weil ein Detail nicht stimmt."""
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    _druecke(conn, tg, einst, knoepfe.TEXT_ANDERS_KNOPF)

    assert len(repo.hole_szenen(conn, 1)) == 3
    assert knoepfe._TEXT_EIGENE_IDEE in tg.texte


def test_anzahl_aendern_zeigt_die_zahlen_und_ruft_kein_modell(conn, einst, tg):
    klm = LLMAttrappe(VORSCHLAG)
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    _druecke(conn, tg, einst, knoepfe.TEXT_ANZAHL_KNOPF, klm=klm)

    assert klm.aufrufe == 0
    assert tg.beschriftungen == [str(z) for z in szenenfolge.ANZAHL_MOEGLICH]


def test_eine_zahl_stoesst_einen_neuen_vorschlag_mit_dieser_anzahl_an(conn, einst, tg):
    klm = LLMAttrappe(VORSCHLAG)
    # Ab Phase 7 ist \"Anzahl aendern\" eine Angabe zur Szenenfolge; in 5
    # waere es eine zur Geschichte (eigener Weg, eigener Test).
    phasen.setze(conn, 1, 7, "befehl")
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)
    _druecke(conn, tg, einst, knoepfe.TEXT_ANZAHL_KNOPF, klm=klm)

    _druecke(conn, tg, einst, "4", klm=klm)
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()

    assert "genau 4 Szenen" in klm.gesehen["system"]


def test_reihenfolge_aendern_fragt_nur(conn, einst, tg):
    """Ein Satz, kein Modellaufruf: was die Gruppe danach schreibt, laeuft
    ueber den normalen Gespraechszug."""
    klm = LLMAttrappe(VORSCHLAG)
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    _druecke(conn, tg, einst, knoepfe.TEXT_REIHENFOLGE_KNOPF, klm=klm)

    assert klm.aufrufe == 0
    assert knoepfe._TEXT_REIHENFOLGE_FRAGE in tg.texte


def test_eine_neue_folge_ersetzt_die_alte(conn, einst, tg):
    """Eine neue Folge ist eine neue Folge -- die alten Szenen fallen weich
    heraus (N3), statt neben den neuen stehenzubleiben."""
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)
    _druecke(conn, tg, einst, knoepfe.TEXT_WEITER_KNOPF)

    zweiter = "VORSCHLAG SZENENFOLGE:\nNur eine Szene — alles passiert — Mira"
    knoepfe.sende_szenenfolge(conn, tg, 1, zweiter)
    _druecke(conn, tg, einst, knoepfe.TEXT_WEITER_KNOPF)

    szenen = repo.hole_szenen(conn, 1)
    assert [s["titel"] for s in szenen] == ["Nur eine Szene"]


# --- Szene fuer Szene -----------------------------------------------------


def _eine_szene(conn, chat_id=1, nummer=1, vollstaendig=True):
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Bahnhof")
    if vollstaendig:
        repo.setze_figur(conn, chat_id, "Maria", "Naeherin")
        figur_id = repo.hole_figur(conn, chat_id, "Maria")["id"]
        repo.setze_sprachprofil(conn, figur_id, "Kurze Saetze.", ["Ein Koffer."])
        repo.setze_szene_figuren(conn, chat_id, szene_id, [figur_id])
        repo.setze_szenenfeld(conn, szene_id, "form", "Tanztheater")
        repo.setze_szenenfeld(conn, szene_id, "ort", "Bahnhof")
        repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Maria wartet")
        repo.setze_arbeitsstand(conn, chat_id, "format", "Urban Dance Tanztheater")
        repo.setze_arbeitsstand(conn, chat_id, "rahmen", "Ein Bahnhof, ein Abend")
    return szene_id


def test_die_vorstellung_markiert_fehlende_pflichtfelder_als_offen(conn, tg):
    szene_id = _eine_szene(conn, vollstaendig=False)

    text = szenenfolge.vorstellung(conn, repo.hole_szene(conn, szene_id))

    assert "Szene 1: Am Bahnhof" in text
    assert "Ort: noch offen" in text
    assert "Wer: noch offen" in text


def test_form_aendern_oeffnet_die_formknoepfe_fuer_diese_szene(conn, einst, tg):
    szene_id = _eine_szene(conn)
    knoepfe.biete_szene(conn, tg, 1, repo.hole_szene(conn, szene_id))

    _druecke(conn, tg, einst, knoepfe.TEXT_SZENE_FORM_KNOPF)
    _druecke(conn, tg, einst, "Lied")

    assert repo.hole_szene(conn, szene_id)["form"] == "lied"


def test_ueberspringen_entfernt_die_szene_weich(conn, einst, tg):
    _eine_szene(conn, nummer=1)
    _eine_szene(conn, nummer=2)
    knoepfe.biete_szene(conn, tg, 1, repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 1)))

    _druecke(conn, tg, einst, knoepfe.TEXT_SZENE_UEBERSPRINGEN_KNOPF)

    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [2]
    # Und direkt danach steht die naechste Szene mit ihrem Menue da.
    assert knoepfe.TEXT_SZENE_SCHREIBEN_KNOPF in tg.beschriftungen


def test_anders_planen_fragt_nur_und_ruft_kein_modell(conn, einst, tg):
    klm = LLMAttrappe()
    szene_id = _eine_szene(conn)
    knoepfe.biete_szene(conn, tg, 1, repo.hole_szene(conn, szene_id))

    _druecke(conn, tg, einst, knoepfe.TEXT_SZENE_PLANEN_KNOPF, klm=klm)

    assert klm.aufrufe == 0
    assert knoepfe._TEXT_SZENE_PLANEN_FRAGE in tg.texte


def test_passt_schreiben_bei_fehlenden_feldern_schlaegt_sie_vor_statt_zu_sperren(
    conn, einst, tg
):
    """Birk 05.09.2026: statt einer Liste von Luecken (``szene.sperrtext``)
    bekommt die Gruppe Vorschlaege mit Knoepfen darunter. Der Sperrtext bleibt
    der richtige Weg beim direkten Schreibauftrag (``/szene``)."""
    klm = LLMAttrappe(
        "VORSCHLAG SZENE:\nort: Bahnhofshalle\nwas_passiert: Maria wartet\n\nPasst das?"
    )
    szene_id = _eine_szene(conn, vollstaendig=False)
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_szene_figuren(
        conn, 1, szene_id, [repo.hole_figur(conn, 1, "Maria")["id"]]
    )
    repo.setze_szenenfeld(conn, szene_id, "form", "Tanztheater")
    knoepfe.biete_szene(conn, tg, 1, repo.hole_szene(conn, szene_id))

    _druecke(conn, tg, einst, knoepfe.TEXT_SZENE_SCHREIBEN_KNOPF, klm=klm)
    szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()

    assert klm.gesehen["art"] == szenenfolge.ART_FELDER
    # Kein Sperrtext -- stattdessen der Vorschlag mit der Grundleiste.
    assert not any("fehlt noch" in t for t in tg.texte)
    assert tg.beschriftungen == [
        knoepfe.TEXT_EIGENE_IDEE_KNOPF,
        knoepfe.TEXT_ANDERS_KNOPF,
        knoepfe.TEXT_WEITER_KNOPF,
    ]


def test_feldvorschlag_speichern_schreibt_die_felder_und_stellt_neu_vor(conn, einst, tg):
    szene_id = _eine_szene(conn, vollstaendig=False)
    # Die Form ist bestaetigt -- sonst kaeme zuerst die Formfrage (06.09.2026).
    repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    knoepfe.sende_szenenfelder(
        conn, tg, 1, 1,
        "VORSCHLAG SZENE:\nort: Bahnhofshalle\nwas_passiert: Maria wartet",
    )

    _druecke(conn, tg, einst, knoepfe.TEXT_WEITER_KNOPF)

    zeile = repo.hole_szene(conn, szene_id)
    assert zeile["ort"] == "Bahnhofshalle"
    assert zeile["was_passiert"] == "Maria wartet"
    assert knoepfe.TEXT_SZENE_SCHREIBEN_KNOPF in tg.beschriftungen


def test_passt_schreiben_startet_den_szenenlauf_wenn_nichts_fehlt(conn, einst, tg):
    klm = LLMAttrappe("TITEL: Am Bahnhof\n\nMARIA: Da bin ich.")
    szene_id = _eine_szene(conn)
    knoepfe.biete_szene(conn, tg, 1, repo.hole_szene(conn, szene_id))

    _druecke(conn, tg, einst, knoepfe.TEXT_SZENE_SCHREIBEN_KNOPF, klm=klm)
    szene._sperre_fuer(1).acquire(timeout=10)
    szene._sperre_fuer(1).release()

    assert klm.gesehen["art"] == szene.ART
    assert (repo.hole_szene(conn, szene_id)["volltext"] or "").strip()


# --- Nach dem Szenentext --------------------------------------------------


def test_unter_dem_szenentext_stehen_die_vier_knoepfe(conn, tg):
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1: Am Bahnhof\n\nMARIA: Da.")

    assert tg.beschriftungen == [
        knoepfe.TEXT_PASST_KNOPF,
        knoepfe.TEXT_ANDERS_KNOPF,
        knoepfe.TEXT_NEU_KNOPF,
        knoepfe.TEXT_NAECHSTE_KNOPF,
    ]


def test_passt_stempelt_die_szene_fertig(conn, einst, tg):
    """Ein geschriebener Text ist ein Entwurf; erst "Passt" macht daraus ein
    Ergebnis -- und nur das zaehlt im Durchlauf als fertig."""
    szene_id = _eine_szene(conn)
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1")

    _druecke(conn, tg, einst, knoepfe.TEXT_PASST_KNOPF)

    assert szenenfolge.ist_fertig(repo.hole_szene(conn, szene_id))
    assert ("entschieden", "Szene 1 abgenommen: Am Bahnhof") in [
        (e["art"], e["text"]) for e in repo.journal(conn, 1)
    ]


def test_passt_bei_der_letzten_szene_bietet_weiter_zu_durchlauf(conn, einst, tg):
    """Nach der letzten abgenommenen Szene steht der Weg in den Durchlauf da,
    nicht nichts -- und ohne Nummer im Knopftext (``phasen.bezeichnung``)."""
    szene_id = _eine_szene(conn)
    repo.aktualisiere_szene(conn, szene_id, "Am Bahnhof", None, "MARIA: Da.")
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1")

    _druecke(conn, tg, einst, knoepfe.TEXT_PASST_KNOPF)

    assert "Weiter zu Durchlauf" in tg.beschriftungen, tg.beschriftungen


def test_naechste_szene_springt_zur_naechsten_offenen(conn, einst, tg):
    _eine_szene(conn, nummer=1)
    _eine_szene(conn, nummer=2)
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1")

    _druecke(conn, tg, einst, knoepfe.TEXT_NAECHSTE_KNOPF)

    assert "Szene 2" in tg.knoepfe[-1][1]
    assert knoepfe.TEXT_SZENE_SCHREIBEN_KNOPF in tg.beschriftungen


def test_neu_schreiben_hebt_die_alte_fassung_auf(conn, einst, tg):
    """Nichts wird weggeworfen (N3-Haltung): die alte Fassung bleibt in der
    Datenbank, der Fertig-Stempel faellt -- ein neuer Text ist wieder ein
    Entwurf."""
    klm = LLMAttrappe("TITEL: Am Bahnhof\n\nMARIA: Jetzt anders.")
    szene_id = _eine_szene(conn)
    repo.aktualisiere_szene(conn, szene_id, "Am Bahnhof", None, "MARIA: Erste Fassung.")
    repo.setze_szene_fertig(conn, szene_id, True)
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1")

    _druecke(conn, tg, einst, knoepfe.TEXT_NEU_KNOPF, klm=klm)
    szene._sperre_fuer(1).acquire(timeout=10)
    szene._sperre_fuer(1).release()

    zeile = repo.hole_szene(conn, szene_id)
    assert "Erste Fassung" in zeile["fruehere_fassungen"]
    assert "Jetzt anders" in zeile["volltext"]
    assert not szenenfolge.ist_fertig(zeile)


def test_die_regienotiz_geht_als_auftrag_in_den_szenenlauf(conn, einst, tg):
    """Der ganze Weg: "Passt, aber anders" fragt, die naechste Nachricht ist
    die Antwort -- und sie landet als Auftrag im Szenenlauf, nicht im
    Gespraechszug. Ohne das bekaeme die Gruppe eine freundliche
    Gespraechsantwort und die Notiz waere verloren."""
    from interview_theater import ablauf

    klm = LLMAttrappe("TITEL: Am Bahnhof\n\nMARIA: Jetzt leiser.")
    szene_id = _eine_szene(conn, nummer=1)
    repo.aktualisiere_szene(conn, szene_id, "Am Bahnhof", None, "MARIA: Erste.")
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1")
    _druecke(conn, tg, einst, knoepfe.TEXT_ANDERS_KNOPF, klm=klm)

    repo.merke_nachricht(conn, 1, 4711, "Ada", 0, "text", "Leiser bitte.", repo._jetzt())
    ablauf.antworte(conn, tg, klm, einst, 1, repo.unbeantwortete(conn, 1))
    szene._sperre_fuer(1).acquire(timeout=10)
    szene._sperre_fuer(1).release()

    assert klm.gesehen["art"] == szene.ART
    assert "Leiser bitte." in klm.gesehen["nutzer"]
    assert "Jetzt leiser" in repo.hole_szene(conn, szene_id)["volltext"]


def test_passt_aber_anders_merkt_sich_die_erwartete_regienotiz(conn, einst, tg):
    """Der Knopf fragt nur (kein Modellaufruf); die naechste Nachricht wird in
    ``ablauf.antworte`` als Auftrag in den Szenenlauf gegeben."""
    klm = LLMAttrappe()
    _eine_szene(conn, nummer=2)
    knoepfe.biete_nach_szenentext(conn, tg, 1, 2, "Szene 2")

    _druecke(conn, tg, einst, knoepfe.TEXT_ANDERS_KNOPF, klm=klm)

    assert klm.aufrufe == 0
    assert szenenfolge.nimm_regienotiz(1) == 2
    # Und nur EINMAL -- sonst schriebe jede weitere Nachricht die Szene neu.
    assert szenenfolge.nimm_regienotiz(1) is None


# --- Phase 7 · Durchlauf --------------------------------------------------


def test_durchlauf_zeigt_die_szenenfolge_mit_status(conn, tg):
    szene_id = _eine_szene(conn, nummer=1)
    repo.aktualisiere_szene(conn, szene_id, "Am Bahnhof", None, "MARIA: Da.")
    repo.setze_szene_fertig(conn, szene_id, True)
    _eine_szene(conn, nummer=2, vollstaendig=False)

    knoepfe.biete_durchlauf(conn, tg, 1)

    text = tg.knoepfe[-1][1]
    assert "Szene 1: Am Bahnhof — fertig" in text
    assert "Szene 2: Am Bahnhof — offen" in text
    assert tg.beschriftungen == [
        "Szene 1 ansehen", "Szene 2 ansehen",
        knoepfe.TEXT_TEXTBUCH_KNOPF, knoepfe.TEXT_EIGENE_IDEE_KNOPF,
    ]


def test_szene_ansehen_schickt_den_volltext(conn, einst, tg):
    szene_id = _eine_szene(conn)
    repo.aktualisiere_szene(conn, szene_id, "Am Bahnhof", None, "MARIA: Da bin ich.")
    knoepfe.biete_durchlauf(conn, tg, 1)

    _druecke(conn, tg, einst, "Szene 1 ansehen")

    assert any("MARIA: Da bin ich." in t for t in tg.texte)


def test_szene_ansehen_ohne_text_sagt_es(conn, einst, tg):
    _eine_szene(conn)
    knoepfe.biete_durchlauf(conn, tg, 1)

    _druecke(conn, tg, einst, "Szene 1 ansehen")

    assert any("noch nicht geschrieben" in t for t in tg.texte)


def test_textbuch_geht_als_datei_raus(conn, einst, tg):
    szene_id = _eine_szene(conn)
    repo.aktualisiere_szene(conn, szene_id, "Am Bahnhof", None, "MARIA: Da bin ich.")
    knoepfe.biete_durchlauf(conn, tg, 1)

    _druecke(conn, tg, einst, knoepfe.TEXT_TEXTBUCH_KNOPF)

    assert len(tg.dateien) == 1
    _, name, inhalt, _ = tg.dateien[0]
    assert name.endswith(".md")
    assert "MARIA: Da bin ich." in inhalt
    assert "## Szene 1: Am Bahnhof" in inhalt


def test_textbuch_nennt_ungeschriebene_szenen_statt_sie_wegzulassen(conn, tg):
    _eine_szene(conn, nummer=1, vollstaendig=False)

    text = szenenfolge.textbuch(conn, 1)

    assert "(noch nicht geschrieben)" in text


def test_textbuch_fehler_laesst_die_gruppe_nicht_ratlos(conn, einst, tg):
    """Scheitert sendDocument (Rechte in der Gruppe), kommt eine Zeile -- und
    die Szenen bleiben ueber "Szene N ansehen" erreichbar."""
    _eine_szene(conn)

    def kaputt(*_a, **_k):
        raise RuntimeError("kein sendDocument")

    tg.sende_datei = kaputt
    knoepfe.biete_durchlauf(conn, tg, 1)

    _druecke(conn, tg, einst, knoepfe.TEXT_TEXTBUCH_KNOPF)

    assert knoepfe._TEXT_TEXTBUCH_FEHLER in tg.texte


def test_phasenknopf_8_zeigt_gleich_den_durchlauf(conn, einst, tg):
    szene_id = _eine_szene(conn)
    repo.aktualisiere_szene(conn, szene_id, "Am Bahnhof", None, "MARIA: Da.")
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", 8)

    _druecke(conn, tg, einst, "Weiter zu Durchlauf")

    assert phasen.aktuelle(conn, 1) == 8
    assert knoepfe.TEXT_TEXTBUCH_KNOPF in tg.beschriftungen


# --- Grundleiste und Idempotenz ------------------------------------------


def test_eigene_idee_ruft_kein_modell_und_schreibt_nichts(conn, einst, tg):
    klm = LLMAttrappe()
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    _druecke(conn, tg, einst, knoepfe.TEXT_EIGENE_IDEE_KNOPF, klm=klm)

    assert klm.aufrufe == 0
    assert repo.hole_szenen(conn, 1) == []
    assert knoepfe._TEXT_EIGENE_IDEE in tg.texte


def test_zweiter_druck_legt_nichts_doppelt_an(conn, einst, tg):
    """Die Idempotenz-Sperre (``repo.beanspruche_knopf``) gilt auch hier: zwei
    Leute im Raum tippen denselben Knopf, und die Folge entsteht einmal."""
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)
    daten = [d for b, d in tg.knoepfe[-1][2] if b == knoepfe.TEXT_WEITER_KNOPF][0]
    druck = {
        "callback_query_id": "q", "data": daten, "chat_id": 1,
        "chat_titel": "Testgruppe", "message_id": 777,
    }

    knoepfe.behandle(conn, tg, None, einst, druck)
    knoepfe.behandle(conn, tg, None, einst, druck)

    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [1, 2, 3]
    assert tg.beantwortet[-1][1] == knoepfe._TEXT_SCHON_BENUTZT


def test_callback_data_bleibt_unter_der_telegram_grenze(conn, tg):
    """Zusage 1 aus ``knoepfe.py``: der Wert steht in der Tabelle ``knopf``,
    nie in ``callback_data`` -- ein Szenenfolge-Vorschlag sprengt die 64 Bytes
    muehelos."""
    knoepfe.sende_szenenfolge(conn, tg, 1, VORSCHLAG)

    for _, daten in tg.knoepfe[-1][2]:
        assert len(daten.encode("utf-8")) <= 64


# --- Zerlegen -------------------------------------------------------------


def test_zerlege_kommt_mit_nummerierung_und_beiden_strichen_klar(conn):
    zeilen = szenenfolge.zerlege(
        "1. Am Bahnhof — Mira kommt an — Mira, Pal — Dialog\n"
        "Szene 2: In der Kueche - Pal kocht - Pal - gesungen\n"
        "\n"
        "Ohne Trenner"
    )

    assert zeilen == [
        ("Am Bahnhof", "Mira kommt an", ["Mira", "Pal"], "dialog", ""),
        ("In der Kueche", "Pal kocht", ["Pal"], "lied", ""),
        ("Ohne Trenner", "", [], szenenfolge.FORM_VORGABE, ""),
    ]


def test_zerlege_liest_die_begruendung_als_fuenfte_spalte():
    """Der Formvorschlag muss begruendet sein (Birk, 06.09.2026): die Gruppe
    soll sehen, WARUM der Bot Chor vorschlaegt, bevor sie drueckt."""
    assert szenenfolge.zerlege(
        "Der Kessel — alle reden zugleich — Mira, Pal — Chor — viele sagen dasselbe"
    ) == [
        ("Der Kessel", "alle reden zugleich", ["Mira", "Pal"], "chor",
         "viele sagen dasselbe"),
    ]


def test_zerlege_faellt_ohne_vierte_spalte_auf_die_vorgabe_zurueck(conn):
    """Die Form ist Pflicht -- laesst das Modell die Spalte weg, wird nichts
    geraten, sondern die Vorgabe gesetzt (und die Gruppe sieht sie in der
    Vorstellung, Zeile 2)."""
    assert szenenfolge.zerlege("Am Bahnhof — Mira kommt an — Mira") == [
        ("Am Bahnhof", "Mira kommt an", ["Mira"], "dialog", ""),
    ]


def test_die_anweisung_verlangt_die_form_je_zeile():
    """Der Marker traegt vier Spalten (05.09.2026 abends): ohne Form in der
    Zeile bekaeme jede Szene die Vorgabe, und die Mischung aus Dialog, Lied
    und Rap entstuende nie."""
    anweisung = szenenfolge.systemanweisung(5)

    assert "— Form" in anweisung
    for form in ("Dialog", "Monolog", "Chor", "Lied", "Rap"):
        assert form in anweisung
    assert "**nicht jede Szene ist ein Dialog**" in anweisung


def test_lege_an_legt_keine_figuren_an(conn):
    """Figuren entstehen in Phase 4 mit Beschreibung und Interview -- sie aus
    einer Szenenzeile zu raten waere genau der Fehler, den ``vorschlag.py``
    vermeidet."""
    szenenfolge.lege_an(
        conn, 1, [("Am Bahnhof", "Mira kommt an", ["Mira"], "dialog")]
    )

    assert repo.figuren(conn, 1) == []


def test_budget_reicht_fuer_reasoning():
    """Der Szenenfolge-Lauf geht ueber ``klm.prosa`` -- Reasoning ist AN und
    verbraucht das Ausgabebudget VOR dem Inhalt (AGENTS.md Falle 4). Mit
    4000 Token endete am 05.09.2026 abends jeder Live-Lauf in
    ``finish_reason: length``; die Gruppe sah nur die Fehlerzeile."""
    assert szenenfolge.MAX_TOKENS >= 50_000
    assert szenenfolge.TIMEOUT_S >= 300.0


# --- Aenderung an Szene N markiert die spaeteren (05.09.2026) --------------


def _geschriebene(conn, nummer, text="MARIA: Da.", chat_id=1):
    szene_id = _eine_szene(conn, chat_id=chat_id, nummer=nummer)
    repo.aktualisiere_szene(conn, szene_id, f"Szene {nummer}", "kurz", text)
    repo.setze_szene_fertig(conn, szene_id, True)
    return szene_id


def test_markiere_spaetere_nimmt_den_fertig_stempel_und_schreibt_einen_vermerk(conn):
    _geschriebene(conn, 1)
    drei = _geschriebene(conn, 3)

    betroffen = szenenfolge.markiere_spaetere(conn, 1, 1)

    assert betroffen == [3]
    assert repo.hole_szene(conn, drei)["fertig_am"] is None
    texte = [e["text"] for e in repo.journal(conn, 1)]
    assert "Szene 3 muss nach Aenderung an Szene 1 geprueft werden" in texte
    assert szenenfolge.zu_pruefen(conn, 1, 3)


def test_markiere_spaetere_laesst_ungeschriebene_szenen_in_ruhe(conn):
    _geschriebene(conn, 1)
    _eine_szene(conn, nummer=2)  # geplant, kein Volltext

    assert szenenfolge.markiere_spaetere(conn, 1, 1) == []
    assert not szenenfolge.zu_pruefen(conn, 1, 2)


def test_markiere_spaetere_schreibt_keine_szene_neu(conn):
    """Kein automatisches Neuschreiben (Birk): der Text bleibt, wie er war."""
    _geschriebene(conn, 1)
    drei = _geschriebene(conn, 3, text="ALTER TEXT VON DREI")

    szenenfolge.markiere_spaetere(conn, 1, 1)

    assert repo.hole_szene(conn, drei)["volltext"] == "ALTER TEXT VON DREI"


def test_passt_aber_anders_markiert_die_spaeteren_szenen(conn, einst, tg):
    _geschriebene(conn, 1)
    _geschriebene(conn, 2)
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1\n\nMARIA: Da.")

    _druecke(conn, tg, einst, knoepfe.TEXT_ANDERS_KNOPF)

    assert szenenfolge.zu_pruefen(conn, 1, 2)
    assert any("Szene 2" in t and "geaendert" in t for t in tg.texte), tg.texte


def test_neu_schreiben_markiert_die_spaeteren_szenen(conn, einst, tg):
    klm = LLMAttrappe("TITEL: Neu\n\nMARIA: Wieder da.")
    _geschriebene(conn, 1)
    _geschriebene(conn, 2)
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1\n\nMARIA: Da.")

    _druecke(conn, tg, einst, knoepfe.TEXT_NEU_KNOPF, klm=klm)
    szene._sperre_fuer(1).acquire(timeout=10)
    szene._sperre_fuer(1).release()

    assert szenenfolge.zu_pruefen(conn, 1, 2)


def test_die_vorstellung_einer_markierten_szene_bietet_neu_oder_so_lassen(conn, einst, tg):
    zwei = _geschriebene(conn, 2)
    szenenfolge.markiere_spaetere(conn, 1, 1)

    knoepfe.biete_szene(conn, tg, 1, repo.hole_szene(conn, zwei))

    assert szenenfolge.TEXT_ZU_PRUEFEN in tg.texte[-1]
    assert tg.beschriftungen == [
        knoepfe.TEXT_NEU_KNOPF, knoepfe.TEXT_SZENE_SO_LASSEN_KNOPF,
    ]


def test_so_lassen_nimmt_den_vermerk_zurueck_ohne_modellaufruf(conn, einst, tg):
    klm = LLMAttrappe()
    zwei = _geschriebene(conn, 2, text="TEXT VON ZWEI")
    szenenfolge.markiere_spaetere(conn, 1, 1)
    knoepfe.biete_szene(conn, tg, 1, repo.hole_szene(conn, zwei))

    _druecke(conn, tg, einst, knoepfe.TEXT_SZENE_SO_LASSEN_KNOPF, klm=klm)

    assert klm.aufrufe == 0
    assert not szenenfolge.zu_pruefen(conn, 1, 2)
    assert repo.hole_szene(conn, zwei)["volltext"] == "TEXT VON ZWEI"


# --- Die Form je Szene ist Pflicht (05.09.2026 abends) --------------------


def test_die_vorstellung_zeigt_die_form_in_zeile_zwei(conn):
    """Seit dem Wegfall der Formatfrage ist die Form die eine Entscheidung,
    die je Szene faellt -- sie steht direkt unter dem Titel, nicht als Angabe
    unter acht."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Bahnhof")
    repo.setze_szenenfeld(conn, szene_id, "form", "Lied")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Bahnhof")

    zeilen = szenenfolge.vorstellung(
        conn, repo.hole_szene(conn, szene_id)
    ).splitlines()

    assert zeilen[0] == "Szene 1: Am Bahnhof"
    assert zeilen[1] == "Form: Lied"


def test_eine_leere_form_steht_als_offen_in_zeile_zwei(conn):
    """Pflichtfeld: fehlt sie, sagt die Vorstellung es -- und `sperrtext`
    nennt sie als erstes, damit \"Ja, schreiben\" sie zuerst vorschlaegt."""
    from interview_theater import szene as szene_modul

    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Bahnhof")
    zeile = repo.hole_szene(conn, szene_id)

    assert szenenfolge.vorstellung(conn, zeile).splitlines()[1] == "Form: noch offen"
    fehlende, _ = szene_modul.fehlendes(conn, zeile)
    assert fehlende[0] == "form", "die Form wird zuerst vorgeschlagen"
    assert "Form" in szene_modul.sperrtext(conn, zeile)
