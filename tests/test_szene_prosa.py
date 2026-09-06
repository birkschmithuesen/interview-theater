"""Phase 6 als Geschichte und Phase 7 als Feinschliff (06.09.2026, 10:30,
Birk).

Im Wortlaut: *"In der Phase des Szenenbauens soll vom Format her zuerst eine
Geschichte rauskommen, so wie wir sie als Buch lesen -- kein
Theaterskript-Dialog, sondern eine Beschreibung von dem, was passiert. Erst
im Feinschliff-Schritt wird entschieden, was aus jeder Szene wird: Dialog,
Monolog, Rap, Lied. Die Herkules-Vorgaben (Regieanteil, Dialoglaenge,
Repliken, Formenbloecke) sind fuer das erste Szenenschreiben NICHT zu
benutzen."*

Gemessen wird deshalb beides: dass in Phase 6 KEINE Theaterregel im Prompt
steht und der Text nach ``szene.prosa`` geht -- und dass Phase 7 die
Prosafassung als bindende Vorlage traegt und nach ``volltext`` schreibt.
"""

import pytest

from interview_theater import anweisungen, phasen, repo, szene


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.naechste_message_id = 500

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        self.gesendet.append((chat_id, text))
        self.knoepfe.append((chat_id, text, list(knoepfe_)))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    @property
    def texte(self):
        return [t for _, t in self.gesendet]


class LLMAttrappe:
    def __init__(self, antwort="TITEL: Am Bahnhof\n\nSie steht am Bahnhof und wartet."):
        self._antwort = antwort
        self.gesehen = {}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.gesehen = {"system": system, "nutzer": nutzer, "art": art}
        return self._antwort


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def freie_sperren():
    szene._sperren.clear()
    yield
    szene._sperren.clear()


def _geplant(conn, chat_id=1, nummer=1, form=None):
    repo.setze_figur(conn, chat_id, "Maria", "Naeherin, kam 1998")
    figur_id = repo.hole_figur(conn, chat_id, "Maria")["id"]
    repo.setze_sprachprofil(conn, figur_id, "Kurze Saetze.", ["Ein Koffer."])
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "Ein Bahnhof, ein Abend")
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Bahnhof")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Bahnhof")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Maria kommt an")
    if form:
        repo.setze_szenenfeld(conn, szene_id, "form", form)
    repo.setze_szene_figuren(conn, chat_id, szene_id, [figur_id])
    return szene_id


# --- Die Systemanweisung der Phase 6 --------------------------------------


def test_die_prosa_anweisung_traegt_keine_herkules_zahlen():
    """Der Kern des Auftrags: keine Laengenvorgaben, keine Regie-Prozente,
    keine Replikenregeln. Die stehen in ``formen/dialog.md`` und gelten fuer
    Sprechtheater -- hier entsteht eine Geschichte."""
    system = szene.systemanweisung(szene.PROSA)

    for verboten in ("700", "1500", "80 %", "Regieanweisungen in runden"):
        assert verboten not in system, verboten


def test_die_prosa_anweisung_traegt_keinen_formenblock():
    """Weder ``szene.md`` noch ein Regelblock einer Theaterform gehen mit."""
    system = szene.systemanweisung(szene.PROSA)

    assert "Form: Dialog" not in system
    assert "Form: Rap" not in system
    assert "REFRAIN" not in system, "der Liedblock gehoert nicht hierher"
    assert anweisungen.hole("szene")[:60] not in system


def test_die_prosa_anweisung_sagt_was_sie_will():
    system = szene.systemanweisung(szene.PROSA)

    assert "erzaehlende prosa" in system.lower()
    assert "500 bis 900 Woerter" in system
    assert "dritte person" in system.lower()
    # Die Sprachhygiene bleibt: sie gilt fuer jeden Text.
    assert "ZUSAMMENFASSUNG:" in system


def test_die_theaterformen_bleiben_unveraendert():
    """Die Gegenprobe: ausserhalb der Prosa gilt weiter der Regelblock."""
    system = szene.systemanweisung("dialog")

    assert "700 bis 1500 Woerter" in system


# --- Phase 6 schreibt nach prosa ------------------------------------------


def test_in_phase_6_landet_der_text_als_geschichte(conn, einst, tg):
    szene_id = _geplant(conn)
    phasen.setze(conn, 1, 6, "befehl")

    szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1")

    zeile = repo.hole_szene(conn, szene_id)
    assert "Sie steht am Bahnhof" in zeile["prosa"]
    assert not (zeile["volltext"] or "").strip()


def test_in_phase_6_geht_prosa_md_in_den_aufruf(conn, einst, tg):
    _geplant(conn)
    phasen.setze(conn, 1, 6, "befehl")
    klm = LLMAttrappe()

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 1")

    assert "Form: Prosa" in klm.gesehen["system"]
    assert "700 bis 1500" not in klm.gesehen["system"]


def test_in_phase_6_wird_die_form_nicht_verlangt(conn):
    """``form`` bleibt NULL, und die Sperre fragt nicht danach."""
    szene_id = _geplant(conn)
    phasen.setze(conn, 1, 6, "befehl")

    felder, _ = szene.fehlendes(conn, repo.hole_szene(conn, szene_id))

    assert "form" not in felder
    assert szene.sperrtext(conn, repo.hole_szene(conn, szene_id)) is None


def test_ein_formvorschlag_bleibt_eine_notiz(conn, einst, tg):
    """Er wird in Phase 6 nicht zur Form -- das entscheidet der Feinschliff."""
    szene_id = _geplant(conn)
    repo.setze_szenenfeld(conn, szene_id, "form_vorschlag", "dialog")
    phasen.setze(conn, 1, 6, "befehl")

    szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1")

    zeile = repo.hole_szene(conn, szene_id)
    assert not (zeile["form"] or "").strip()
    assert zeile["form_vorschlag"] == "dialog"


# --- Phase 7: Feinschliff -------------------------------------------------


def test_der_feinschliff_traegt_die_prosa_als_vorlage(conn, einst, tg):
    szene_id = _geplant(conn, form="Dialog")
    repo.aktualisiere_szene(
        conn, szene_id, "Am Bahnhof", None, None, None,
        prosa="Sie steht am Bahnhof und wartet auf ihre Schwester.",
    )
    phasen.setze(conn, 1, 7, "befehl")
    klm = LLMAttrappe("TITEL: Am Bahnhof\n\nMARIA: Da bin ich.")

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 1")

    assert "Uebersetze sie in die Form" in klm.gesehen["nutzer"]
    assert "wartet auf ihre Schwester" in klm.gesehen["nutzer"]
    assert "nichts hinzu" in klm.gesehen["nutzer"]


def test_der_feinschliff_schreibt_nach_volltext_und_laesst_die_prosa_stehen(
    conn, einst, tg,
):
    """Die Geschichte bleibt: sie ist die Vorlage, gegen die sich der
    Theatertext pruefen laesst."""
    szene_id = _geplant(conn, form="Dialog")
    repo.aktualisiere_szene(
        conn, szene_id, "Am Bahnhof", None, None, None, prosa="Sie wartet.",
    )
    phasen.setze(conn, 1, 7, "befehl")

    szene.schreibe(
        conn, tg, LLMAttrappe("TITEL: Am Bahnhof\n\nMARIA: Da bin ich."),
        einst, 1, "Schreib Szene 1",
    )

    zeile = repo.hole_szene(conn, szene_id)
    assert "MARIA: Da bin ich." in zeile["volltext"]
    assert zeile["prosa"] == "Sie wartet."


def test_der_feinschliff_nimmt_den_regelblock_der_form(conn, einst, tg):
    szene_id = _geplant(conn, form="Dialog")
    repo.aktualisiere_szene(
        conn, szene_id, "Am Bahnhof", None, None, None, prosa="Sie wartet.",
    )
    phasen.setze(conn, 1, 7, "befehl")
    klm = LLMAttrappe("TITEL: Am Bahnhof\n\nMARIA: Da.")

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 1")

    assert "700 bis 1500 Woerter" in klm.gesehen["system"]


def test_in_phase_6_steht_keine_vorlage_im_prompt(conn, einst, tg):
    """Die Gegenprobe: die Prosa einer Szene ist nicht die Vorlage fuer sich
    selbst."""
    szene_id = _geplant(conn)
    repo.aktualisiere_szene(
        conn, szene_id, "Am Bahnhof", None, None, None, prosa="Alte Fassung.",
    )
    phasen.setze(conn, 1, 6, "befehl")
    klm = LLMAttrappe()

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 1")

    assert "Uebersetze sie in die Form" not in klm.gesehen["nutzer"]


# --- Voraussetzungen und Continuity ---------------------------------------


def test_phase_7_verlangt_alle_szenen_als_geschichte(conn):
    ids = [_geplant(conn, nummer=n) for n in (1, 2)]
    phasen.setze(conn, 1, 6, "befehl")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Sie kommt an, sie bleibt.")

    assert phasen.voraussetzungen(conn, 1)[7] is False

    for szene_id in ids:
        repo.aktualisiere_szene(
            conn, szene_id, "Am Bahnhof", None, None, None, prosa="Sie wartet.",
        )

    assert phasen.voraussetzungen(conn, 1)[7] is True


def test_die_vorszene_geht_als_geschichte_in_die_naechste(conn, einst, tg):
    """In Phase 6 gibt es keinen Volltext -- die Continuity haengt an der
    Prosa, sonst schriebe jede Szene an der vorigen vorbei."""
    erste = _geplant(conn, nummer=1)
    repo.aktualisiere_szene(
        conn, erste, "Am Bahnhof", None, None, None,
        prosa="Maria kommt am Bahnhof an und findet niemanden.",
    )
    _geplant(conn, nummer=2)
    phasen.setze(conn, 1, 6, "befehl")
    klm = LLMAttrappe()

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib Szene 2")

    assert "findet niemanden" in klm.gesehen["nutzer"]


# --- Die Phasentexte ------------------------------------------------------


def test_die_phasen_heissen_nach_dem_was_dort_passiert():
    assert phasen.kurzname(6) == "Szenen als Geschichte"
    assert phasen.kurzname(7) == "Feinschliff"


def test_der_phasentext_6_kuendigt_eine_geschichte_an():
    from interview_theater import phasentexte

    text = phasentexte.EINLEITUNGEN[6]

    assert "als Geschichte" in text
    assert "Kein Theatertext" in text
    assert "Form" in text


def test_der_phasentext_7_kuendigt_form_und_uebersetzung_an():
    from interview_theater import phasentexte

    text = phasentexte.EINLEITUNGEN[7]

    assert "Feinschliff" in text
    assert "uebersetze" in text.lower()
    assert "Rap" in text
