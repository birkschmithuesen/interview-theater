"""Tests fuer den Szenen-Aufruf (interview_theater/szene.py).

Kein Netzzugriff: das Sprachmodell ist eine Attrappe mit einer
``.prosa()``-Methode, die eine vorbereitete Antwort liefert (oder einen
vorbereiteten Fehler wirft) und aufzeichnet, womit sie gerufen wurde --
insbesondere ``max_tokens`` und ``timeout``, an denen die beiden gemessenen
Randbedingungen fuer aktives Reasoning haengen.

Die Threads aus ``szene.starte()`` werden in den Tests eingesammelt
(``.join()``), damit kein Test dem naechsten in die Datenbank schreibt.
"""

import threading

import pytest

from interview_theater import repo, szene

ANTWORT = "TITEL: Am Bahnhof\nKURZ: Maria kommt an und trifft Elif.\n\nMARIA: Da.\nELIF: Ja."


class LLMAttrappe:
    def __init__(self, antwort=ANTWORT, fehler=None):
        self._antwort = antwort
        self._fehler = fehler
        self.aufrufe = 0
        self.gesehen = {}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe += 1
        self.gesehen = {
            "chat_id": chat_id, "system": system, "nutzer": nutzer, "art": art,
            "max_tokens": max_tokens, "timeout": timeout,
        }
        if self._fehler is not None:
            raise self._fehler
        return self._antwort


class TelegramAttrappe:
    """Vergibt aufsteigende message_ids -- ``repo.merke_nachricht`` hat
    ``(chat_id, message_id)`` als Primaerschluessel, eine feste Nummer wuerde
    ab der zweiten Nachricht still verschluckt."""

    def __init__(self):
        self.gesendet = []
        self._naechste = 9000

    def sende(self, chat_id, text):
        self.gesendet.append((chat_id, text))
        self._naechste += 1
        return self._naechste

    @property
    def texte(self):
        return [t for _, t in self.gesendet]


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def freie_sperren():
    """Jeder Test faengt mit unbenutzten Sperren an -- ``szene._sperren`` lebt
    sonst ueber die ganze Testsitzung."""
    szene._sperren.clear()
    yield
    szene._sperren.clear()


def _material(conn, text="Ich bin 1998 hergekommen, mit einem Koffer.", name="Maria"):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 100, "lang", "text")
    repo.setze_aufnahme_name(conn, aufnahme_id, name)
    repo.setze_transkript(conn, aufnahme_id, text)
    return aufnahme_id


def _warte(thread):
    assert thread is not None
    thread.join(timeout=10)
    assert not thread.is_alive()


# ---------------------------------------------------------------------------
# Prompt-Zusammenbau
# ---------------------------------------------------------------------------


def test_leere_datenlage_laesst_nur_den_auftrag_stehen(conn, einst):
    text = szene.baue_nutzertext(conn, einst, 1, "Szene 1: irgendwas")

    assert "Arbeitsstand" not in text
    assert "Interviews im Wortlaut" not in text
    assert "Bisherige Szenen" not in text
    assert "verworfen" not in text
    assert text.startswith("Euer Auftrag:")


def test_arbeitsstand_und_transkripte_erscheinen_sobald_es_sie_gibt(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "Bleiben oder gehen")
    repo.setze_figur(conn, 1, "Maria", "Naeherin, kam 1998")
    _material(conn)

    text = szene.baue_nutzertext(conn, einst, 1, "Szene 1: Ankunft")

    assert "Kernthema: Ankommen" in text
    assert "Hauptkonflikt: Bleiben oder gehen" in text
    assert "Figur Maria: Naeherin, kam 1998" in text
    assert "Interviews im Wortlaut" in text
    assert "mit einem Koffer" in text


def test_kurze_aufnahmen_sind_kein_material(conn, einst):
    """Nur Klasse 'lang' zaehlt als Interview -- ein Zuruf gehoert nicht in
    den Szenen-Prompt (SPEC § 10.1)."""
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 101, "kurz", "sprache")
    repo.setze_transkript(conn, aufnahme_id, "mach mal lauter")

    text = szene.baue_nutzertext(conn, einst, 1, "Szene 1")

    assert "mach mal lauter" not in text


def test_nur_verworfenes_geht_mit_nicht_das_ganze_journal(conn, einst):
    repo.schreibe_journal(conn, 1, "verworfen", "Kindheitsfragen als Einstieg", "erkenner")
    repo.schreibe_journal(conn, 1, "entschieden", "Kernthema ist Ankommen", "erkenner")

    text = szene.baue_nutzertext(conn, einst, 1, "Szene 1")

    assert "Kindheitsfragen als Einstieg" in text
    assert "Kernthema ist Ankommen" not in text


def test_ueberarbeitete_szene_steht_im_volltext_die_anderen_nur_als_zeile(conn, einst):
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: Da.")
    repo.lege_szene_an(conn, 1, 2, "Der Koffer", "Elif packt", "ELIF: Der geht nicht zu.")
    ziel = repo.hole_szenen(conn, 1)[1]

    text = szene.baue_nutzertext(conn, einst, 1, "Szene 2 nochmal, kuerzer", ziel)

    assert "Szene 1: Ankunft - Maria kommt an" in text
    assert "MARIA: Da." not in text          # Szene 1 nur als Zeile
    assert "ELIF: Der geht nicht zu." in text  # Szene 2 im Volltext
    assert "ueberarbeitet werden" in text


def test_ohne_ueberarbeitung_geht_kein_volltext_mit(conn, einst):
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: Da.")

    text = szene.baue_nutzertext(conn, einst, 1, "Schreib eine neue Szene")

    assert "Szene 1: Ankunft" in text
    assert "MARIA: Da." not in text


def test_auftrag_steht_am_ende(conn, einst):
    """SPEC § 6.1: was am Ende des Prompts steht, wiegt am schwersten. Der
    Auftrag darf nicht hinter dem Rohmaterial verschwinden."""
    _material(conn)
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    text = szene.baue_nutzertext(conn, einst, 1, "Szene 4: der Abschied")

    assert text.endswith("Euer Auftrag:\nSzene 4: der Abschied")


def test_ueber_dem_deckel_ruecken_verdichtungen_an_die_stelle_der_transkripte(conn, einst):
    aufnahme_id = _material(conn, text="w " * (3 * szene.DECKEL))
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Maria erzaehlt von der Ankunft",
        [{"thema": "Ankommen", "beleg_zitat": "mit einem Koffer", "zitat_geprueft": 1}],
    )

    text = szene.baue_nutzertext(conn, einst, 1, "Szene 1: Ankunft")

    assert "Interviews im Wortlaut" not in text
    assert "Maria erzaehlt von der Ankunft" in text
    assert '"mit einem Koffer"' in text
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")]
    assert "kuerzung" in arten


# ---------------------------------------------------------------------------
# Antwort lesen
# ---------------------------------------------------------------------------


def test_zerlege_trennt_titel_kurz_und_text():
    titel, kurz, volltext = szene.zerlege(ANTWORT)

    assert titel == "Am Bahnhof"
    assert kurz == "Maria kommt an und trifft Elif."
    assert volltext == "MARIA: Da.\nELIF: Ja."


def test_zerlege_vertraegt_markdown_um_die_kopfzeilen():
    titel, kurz, volltext = szene.zerlege("**TITEL:** Am Bahnhof\n**KURZ:** Eine Zeile\n\nMARIA: Da.")

    assert (titel, kurz, volltext) == ("Am Bahnhof", "Eine Zeile", "MARIA: Da.")


def test_zerlege_ohne_kopf_liefert_den_ganzen_text():
    """Ein fehlender Titel ist kein Grund, einen fertigen Szenentext
    wegzuwerfen -- der Aufrufer setzt dann 'Szene N' ein."""
    titel, kurz, volltext = szene.zerlege("MARIA: Ohne Kopf.\nELIF: Trotzdem gut.")

    assert titel is None and kurz is None
    assert volltext == "MARIA: Ohne Kopf.\nELIF: Trotzdem gut."


def test_nummer_wird_aus_dem_auftrag_gelesen():
    assert szene.nummer_aus_auftrag("Szene 2: Maria am Bahnhof") == 2
    assert szene.nummer_aus_auftrag("schreib szene nr. 12 nochmal") == 12
    assert szene.nummer_aus_auftrag("schreib uns die Szene mit dem Koffer") is None
    assert szene.nummer_aus_auftrag("") is None


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


def test_schreibe_legt_szene_an_und_vergibt_die_naechste_nummer(conn, einst, tg):
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: Da.")

    nummer = szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Schreib die naechste Szene")

    assert nummer == 2
    szenen = repo.hole_szenen(conn, 1)
    assert len(szenen) == 2
    assert szenen[1]["titel"] == "Am Bahnhof"
    assert szenen[1]["kurzbeschreibung"] == "Maria kommt an und trifft Elif."
    assert szenen[1]["volltext"] == "MARIA: Da.\nELIF: Ja."


def test_schreibe_ueberschreibt_die_szene_mit_der_genannten_nummer(conn, einst, tg):
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: Alt.")

    nummer = szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Szene 1 nochmal, kuerzer")

    assert nummer == 1
    szenen = repo.hole_szenen(conn, 1)
    assert len(szenen) == 1
    assert szenen[0]["titel"] == "Am Bahnhof"
    assert szenen[0]["volltext"] == "MARIA: Da.\nELIF: Ja."


def test_erste_szene_bekommt_nummer_eins(conn, einst, tg):
    assert szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Schreib uns eine Szene") == 1


def test_schreibe_haelt_die_szene_im_journal_fest(conn, einst, tg):
    szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Schreib uns eine Szene")

    eintraege = repo.journal(conn, 1)
    assert [(e["art"], e["text"]) for e in eintraege] == [
        ("entschieden", "Szene 1 geschrieben: Am Bahnhof")
    ]


def test_schreibe_schickt_titel_anfang_und_verweis_nicht_die_ganze_szene(conn, einst, tg):
    lang = "TITEL: Am Bahnhof\nKURZ: Eine Zeile\n\n" + "\n".join(
        f"MARIA: Zeile {i}" for i in range(20)
    )

    szene.schreibe(conn, tg, LLMAttrappe(antwort=lang), einst, 1, "Schreib uns eine Szene")

    text = tg.texte[-1]
    assert text.startswith("Szene 1: Am Bahnhof")
    assert "MARIA: Zeile 5" in text
    assert "MARIA: Zeile 6" not in text  # nur VORSCHAU_ZEILEN Zeilen
    assert "Gruppenseite" in text


def test_schreibe_sendet_reasoning_taugliche_grenzen(conn, einst, tg):
    """Die zwei gemessenen Randbedingungen fuer aktives Reasoning
    (reasoning-stufen-entscheidungshilfe.md § 3.2, § 4.3): genug
    Ausgabebudget, damit der Lauf nicht im Denken endet, und ein Zeitbudget,
    das der 30-Sekunden-Klient aus bot.main nicht hergibt."""
    klm = LLMAttrappe()

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib uns eine Szene")

    assert klm.gesehen["max_tokens"] >= 12_000
    assert klm.gesehen["timeout"] >= 90
    assert klm.gesehen["art"] == "szene"


def test_antwort_ohne_szenentext_ist_ein_fehler(conn, einst, tg):
    klm = LLMAttrappe(antwort="TITEL: Am Bahnhof\nKURZ: Eine Zeile\n")

    with pytest.raises(szene.SzeneFehler):
        szene.schreibe(conn, tg, klm, einst, 1, "Schreib uns eine Szene")

    assert repo.hole_szenen(conn, 1) == []


def test_ohne_titel_faellt_der_code_auf_szene_n_zurueck(conn, einst, tg):
    klm = LLMAttrappe(antwort="MARIA: Ohne Kopf.")

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib uns eine Szene")

    assert repo.journal(conn, 1)[0]["text"] == "Szene 1 geschrieben: Szene 1"
    assert tg.texte[-1].startswith("Szene 1: Szene 1")


# ---------------------------------------------------------------------------
# starte(): Ankuendigung, Thread, Sperre, Fehlerpfad
# ---------------------------------------------------------------------------


def test_starte_kuendigt_sofort_an_und_schreibt_die_szene_im_thread(conn, einst, tg):
    thread = szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft")
    _warte(thread)

    assert "das dauert eine Minute" in tg.texte[0]
    assert tg.texte[1].startswith("Szene 1: Am Bahnhof")
    assert len(repo.hole_szenen(conn, 1)) == 1


def test_ankuendigung_steht_als_bot_nachricht_im_verlauf(conn, einst, tg):
    """Wie jede andere Bot-Zeile: sonst fehlte sie im Fenster des naechsten
    Gespraechszugs und der Bot wuesste nicht mehr, was er zugesagt hat."""
    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft"))

    texte = [n["text"] for n in repo.letzte_nachrichten(conn, 1) if n["ist_bot"]]
    assert any("das dauert eine Minute" in t for t in texte)
    assert any(t.startswith("Szene 1: Am Bahnhof") for t in texte)


def test_zweiter_auftrag_waehrend_eines_laufs_wird_abgewiesen(conn, einst, tg):
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        thread = szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 2: noch eine")
    finally:
        sperre.release()

    assert thread is None
    assert tg.texte == ["Ich schreibe gerade noch an einer Szene, gleich."]
    assert repo.hole_szenen(conn, 1) == []


def test_die_sperre_gilt_je_gruppe_nicht_global(conn, einst, tg):
    repo.sichere_gruppe(conn, 2, "gruppe1", "Zweite Gruppe")
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        thread = szene.starte(conn, tg, LLMAttrappe(), einst, 2, "Szene 1: Ankunft")
        _warte(thread)
    finally:
        sperre.release()

    assert len(repo.hole_szenen(conn, 2)) == 1


def test_leerer_auftrag_stoesst_nichts_an(conn, einst, tg):
    assert szene.starte(conn, tg, LLMAttrappe(), einst, 1, "   ") is None
    assert tg.gesendet == []


def test_fehlgeschlagener_lauf_meldet_sich_und_schreibt_einen_vorfall(conn, einst, tg):
    klm = LLMAttrappe(fehler=RuntimeError("Sprachmodell weg"))

    _warte(szene.starte(conn, tg, klm, einst, 1, "Szene 1: Ankunft"))

    assert "nicht gelungen" in tg.texte[-1]
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")]
    assert arten == ["szene_fehlgeschlagen"]
    assert repo.hole_szenen(conn, 1) == []


def test_nach_einem_fehlschlag_ist_die_sperre_wieder_frei(conn, einst, tg):
    _warte(szene.starte(
        conn, tg, LLMAttrappe(fehler=RuntimeError("weg")), einst, 1, "Szene 1: Ankunft",
    ))

    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft"))
    assert len(repo.hole_szenen(conn, 1)) == 1


def test_zwei_laeufe_nacheinander_ueberholen_sich_nicht(conn, einst, tg):
    """Der Grund fuer die Sperre: zwei parallele Laeufe wuerden einander in
    geaendert_am ueberholen. Nacheinander muss es sauber durchlaufen."""
    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft"))
    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 2: Der Koffer"))

    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [1, 2]
    assert repo.hole_letzte_szene(conn, 1)["nummer"] == 2


def test_systemanweisung_enthaelt_prompt_und_negativliste():
    text = szene.systemanweisung()

    assert "Figurennamen in GROSSBUCHSTABEN" in text
    assert "Theater-Tells" in text


def test_der_szenenlauf_ist_nicht_der_gespraechsthread(conn, einst, tg):
    """Strukturell, nicht per Behauptung: starte() gibt einen Thread zurueck,
    der zum Zeitpunkt der Rueckkehr noch laufen darf."""
    thread = szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft")

    assert isinstance(thread, threading.Thread)
    assert thread is not threading.current_thread()
    _warte(thread)
