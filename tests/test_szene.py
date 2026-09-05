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

from interview_theater import anweisungen, repo, szene

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


def _bereit_machen(conn, chat_id=1, nummer=1):
    """Eine Szene, die die Sperre passieren laesst: alle vier Pflichtfelder
    gesetzt und eine Figur mit Sprachprofil. Seit dem 05.09.2026 ist das die
    Voraussetzung fuer jeden Szenen-Aufruf -- ohne sie gibt es keinen.

    Dazu Format und Rahmen im Arbeitsstand (ARBEITSSTAND_PFLICHTFELDER, seit
    05.09.2026 abends): ohne die Ergebnisse von Phase 5 ist nicht entschieden,
    WAS entsteht und WORIN es spielt."""
    repo.setze_figur(conn, chat_id, "Maria", "Naeherin, kam 1998")
    figur_id = repo.hole_figur(conn, chat_id, "Maria")["id"]
    repo.setze_sprachprofil(
        conn, figur_id, "Kurze Saetze, bricht ab.", ["Ich hatte nur einen Koffer."]
    )
    repo.setze_arbeitsstand(conn, chat_id, "format", "Sprechtheater: Dialog")
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "Ein Bahnhof, ein Abend")
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Bahnhof")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Maria kommt an")
    repo.setze_szene_figuren(conn, chat_id, szene_id, [figur_id])
    return szene_id


@pytest.fixture
def bereit(conn):
    """Gruppe 1 mit einer vollstaendig geplanten Szene 1."""
    return _bereit_machen(conn)


# ---------------------------------------------------------------------------
# Prompt-Zusammenbau
# ---------------------------------------------------------------------------


def _figur_mit_stimme(conn, name="Maria", beschreibung="Naeherin, kam 1998",
                      profil="Kurze Saetze, bricht ab.", zitate=("Ich hatte nur einen Koffer.",)):
    repo.setze_figur(conn, 1, name, beschreibung)
    figur_id = repo.hole_figur(conn, 1, name)["id"]
    repo.setze_sprachprofil(conn, figur_id, profil, list(zitate))
    return figur_id


def _geplante_szene(conn, nummer, **felder):
    figuren = felder.pop("figuren", None)
    szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
    for feld, wert in felder.items():
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    if figuren:
        repo.setze_szene_figuren(conn, 1, szene_id, figuren)
    return repo.hole_szene(conn, szene_id)


def test_leere_datenlage_laesst_nur_den_auftrag_stehen(conn, einst):
    text = szene.baue_nutzertext(conn, 1, "Szene 1: irgendwas")

    assert "Kernthema" not in text
    assert szene.FIGUREN_KOPF not in text
    assert szene.CONTINUITY_KOPF not in text
    assert text.startswith("Euer Auftrag:")


def test_keine_transkripte_und_keine_verdichtungen_mehr(conn, einst):
    """Die Umstellung vom 05.09.2026 in einem Test: Rohmaterial gehoert nicht
    mehr in den Szenen-Prompt. Was das Modell braucht, steht destilliert da --
    Sprachprofil je Figur und die Felder der Szene."""
    aufnahme_id = _material(conn)
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Maria erzaehlt von der Ankunft",
        [{"thema": "Ankommen", "beleg_zitat": "mit einem Koffer", "zitat_geprueft": 1}],
    )

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert "mit einem Koffer" not in text
    assert "Maria erzaehlt von der Ankunft" not in text


def test_rahmen_und_kernthema_stehen_vorn(conn, einst):
    """Das Format des Stuecks steht seit dem 05.09.2026 abends NICHT mehr im
    Prompt: es wird nicht mehr gefragt, also auch nicht vorgehalten."""
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "kernthema_begruendung", "dreimal genannt")

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert text.startswith("Die Geschichte / der Rahmen des Stuecks") and "Eine Nacht im Treppenhaus" in text.split("Kernthema")[0]
    assert "Format des Stuecks" not in text
    assert "Musical" not in text
    assert "Kernthema: Ankommen (Begruendung: dreimal genannt)" in text


def test_hauptkonflikt_nur_wenn_es_einen_gibt(conn, einst):
    """Birk 05.09.2026: es muss nicht immer einen Konflikt geben. Eine leere
    Zeile "Hauptkonflikt: -" wuerde das Modell einen erfinden lassen."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    assert "Hauptkonflikt" not in szene.baue_nutzertext(conn, 1, "Szene 1")

    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")

    assert "Hauptkonflikt: bleiben gegen gehen" in szene.baue_nutzertext(conn, 1, "Szene 1")


def test_je_figur_sprachprofil_und_zitate(conn, einst):
    """Der wichtigste Block (Birk: "Zitate als Few-Shots fuer die Sprechweise
    je Figur, das ist das Wichtigste")."""
    _figur_mit_stimme(conn)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: Ankunft")

    assert szene.FIGUREN_KOPF in text
    assert "Maria -- Naeherin, kam 1998" in text
    assert "Kurze Saetze, bricht ab." in text
    assert '"Ich hatte nur einen Koffer."' in text


def test_continuity_nennt_nur_szenen_mit_kleinerer_nummer(conn, einst):
    figur = _figur_mit_stimme(conn)
    _geplante_szene(conn, 1, titel="Ankunft", ort="Bahnhof",
                    was_passiert="Maria kommt an", was_anders="sie bleibt",
                    figuren=[figur])
    _geplante_szene(conn, 3, titel="Spaeter", ort="Kueche", was_passiert="sie kocht")
    ziel = _geplante_szene(conn, 2, form="Dialog", ort="Treppenhaus",
                           was_passiert="sie streiten", figuren=[figur])

    text = szene.baue_nutzertext(conn, 1, "Szene 2 schreiben", ziel)

    assert szene.CONTINUITY_KOPF in text
    assert "Szene 1: Ankunft" in text
    assert "Ort: Bahnhof" in text
    assert "Was anders ist: sie bleibt" in text
    assert "Szene 3" not in text, "was danach kommt, ist keine Vorgeschichte"


def test_diese_szene_traegt_alle_felder_und_ist_bindend(conn, einst):
    figur = _figur_mit_stimme(conn)
    ziel = _geplante_szene(
        conn, 2, form="Lied", ort="Polizeikessel", zeit="am naechsten Morgen",
        anlass="seit zwei Stunden eingekesselt", was_passiert="Pal will raus",
        was_anders="sie bleibt", kernsaetze="Trump macht daraus eine Riviera",
        ton="hitzig", figuren=[figur],
    )

    text = szene.baue_nutzertext(conn, 1, "Szene 2 schreiben", ziel)

    assert szene.DIESE_SZENE_KOPF in text
    for erwartet in (
        "Form: Lied", "Ort: Polizeikessel", "Zeit: am naechsten Morgen",
        "Anlass: seit zwei Stunden eingekesselt", "Wer: Maria",
        "Was passiert: Pal will raus", "Was anders ist: sie bleibt",
        "Kernsaetze: Trump macht daraus eine Riviera", "Ton: hitzig",
    ):
        assert erwartet in text


def test_nur_verworfenes_geht_mit_nicht_das_ganze_journal(conn, einst):
    repo.schreibe_journal(conn, 1, "verworfen", "Kindheitsfragen als Einstieg", "erkenner")
    repo.schreibe_journal(conn, 1, "entschieden", "Kernthema ist Ankommen", "erkenner")

    text = szene.baue_nutzertext(conn, 1, "Szene 1")

    assert "Kindheitsfragen als Einstieg" in text
    assert "Kernthema ist Ankommen" not in text


def test_bei_einer_ueberarbeitung_geht_der_bisherige_text_mit(conn, einst):
    ziel = _geplante_szene(conn, 2, form="Dialog", ort="Kueche")
    repo.aktualisiere_szene(conn, ziel["id"], "Der Koffer", "Elif packt",
                            "ELIF: Der geht nicht zu.")
    ziel = repo.hole_szene(conn, ziel["id"])

    text = szene.baue_nutzertext(conn, 1, "Szene 2 nochmal, kuerzer", ziel)

    assert "ELIF: Der geht nicht zu." in text
    assert "ueberarbeitet werden" in text


def test_der_volltext_der_frueheren_szene_geht_mit(conn, einst):
    """Umgekehrt seit dem 05.09.2026 abends (Birk, nach der Testgruppe):
    frueher ging aus einer frueheren Szene nur die Lage mit, und Szene 2
    kannte Szene 1 nicht wirklich. Jetzt steht ihr Text da -- klar
    gekennzeichnet und mit dem Anschluss-Satz darueber."""
    _geplante_szene(conn, 1, titel="Ankunft", ort="Bahnhof")
    repo.aktualisiere_szene(
        conn, repo.hole_szenen(conn, 1)[0]["id"], "Ankunft", "Maria kommt an", "MARIA: Da."
    )

    text = szene.baue_nutzertext(conn, 1, "Schreib Szene 2")

    assert "Szene 1: Ankunft" in text
    assert szene.CONTINUITY_VOLLTEXT_KOPF.format(nummer=1) in text
    assert "MARIA: Da." in text


def test_auftrag_steht_am_ende(conn, einst):
    """SPEC § 6.1: was am Ende des Prompts steht, wiegt am schwersten."""
    _figur_mit_stimme(conn)
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    text = szene.baue_nutzertext(conn, 1, "Szene 4: der Abschied")

    assert text.endswith("Euer Auftrag:\nSzene 4: der Abschied")


# ---------------------------------------------------------------------------
# Form-Verzweigung: je Form ein eigener Regelblock
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "form, datei",
    [
        ("Dialog", "dialog"),
        ("Text", "dialog"),
        ("Sprechszene", "dialog"),
        ("Lied", "lied"),
        ("gesungen, mit Refrain", "lied"),
        ("Rap", "rap"),
        ("HipHop", "rap"),
        ("Monolog", "monolog"),
        ("Chor", "chor"),
        ("", "dialog"),
        (None, "dialog"),
        ("Bewegungsszene", "dialog"),
        ("stumme Szene", "dialog"),
    ],
)
def test_formdatei_ordnet_die_form_ihrem_regelblock_zu(form, datei):
    assert szene.formdatei(form) == datei


def test_formdatei_kennt_kein_format_mehr():
    """Die Formatfrage ist raus (Birk, 05.09.2026 abends): ``formdatei``
    nimmt genau ein Argument, und der Rueckfall ist immer ``dialog``."""
    import inspect

    assert list(inspect.signature(szene.formdatei).parameters) == ["form"]
    assert szene.FORMEN == ("dialog", "monolog", "chor", "lied", "rap")


def test_systemanweisung_haengt_den_formenblock_dazwischen():
    dialog = szene.systemanweisung("Dialog")
    lied = szene.systemanweisung("Lied")

    assert "Kein Monolog laenger als sechs Zeilen" in dialog
    assert "Kein Monolog laenger als sechs Zeilen" not in lied
    # Der Rueckfall ist derselbe Block: eine Szene ohne Form ist eine
    # Sprechszene, keine getanzte (05.09.2026 abends).
    assert "Kein Monolog laenger als sechs Zeilen" in szene.systemanweisung(None)
    assert "REFRAIN" in lied
    # Grundform und Negativliste stehen in beiden.
    for text in (dialog, lied):
        assert "Figurennamen in GROSSBUCHSTABEN" in text
        assert "Theater-Tells" in text


def test_jede_form_hat_ihren_regelblock():
    for form in szene.FORMEN:
        assert len(anweisungen.hole(f"formen/{form}").splitlines()) >= 8, form


# ---------------------------------------------------------------------------
# Szenenplanung (T2): die Felder, die vor dem Text feststehen
# ---------------------------------------------------------------------------


def test_zerlege_planung_liest_nummer_und_felder():
    nummer, felder = szene.zerlege_planung(
        "Szene 1 | form: Dialog | ort: Polizeikessel | figuren: Mira, Pola, Pal "
        "| was_passiert: Pal will raus, Mira haelt sie fest"
    )

    assert nummer == 1
    assert felder == {
        "form": "Dialog",
        "ort": "Polizeikessel",
        "figuren": "Mira, Pola, Pal",
        "was_passiert": "Pal will raus, Mira haelt sie fest",
    }


def test_zerlege_planung_nennt_nur_was_dasteht():
    """Die Regel, an der die Planung haengt: ein spaeterer Lauf traegt einzelne
    Felder nach, ohne die frueheren zu ueberschreiben."""
    nummer, felder = szene.zerlege_planung("Szene 2 | ton: leise")

    assert nummer == 2
    assert felder == {"ton": "leise"}


def test_zerlege_planung_ohne_nummer_und_mit_aliasen():
    nummer, felder = szene.zerlege_planung("wer: Mira, Pola | handlung: sie warten")

    assert nummer is None
    assert felder == {"figuren": "Mira, Pola", "was_passiert": "sie warten"}


def test_zerlege_planung_uebergeht_leere_werte():
    """Ein leerer Wert heisst 'nicht genannt', nicht 'loeschen' -- weggenommen
    wird ausschliesslich ueber ``entfernen``."""
    assert szene.zerlege_planung("Szene 1 | ort:  | form: Lied") == (1, {"form": "Lied"})


def test_zerlege_planung_vertraegt_muell():
    assert szene.zerlege_planung("") == (None, {})
    assert szene.zerlege_planung("irgendwas ohne Struktur") == (None, {})


def test_planungszeile_nennt_nummer_form_ort_und_besetzung(conn):
    repo.setze_figur(conn, 1, "Mira", "kam mit 19 her")
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Polizeikessel")
    repo.setze_szene_figuren(
        conn, 1, szene_id, [f["id"] for f in repo.figuren(conn, 1)]
    )

    zeile = szene.planungszeile(conn, repo.hole_szene(conn, szene_id))

    assert zeile == "Szene 1 · Dialog · Polizeikessel · Mira, Pola"


def test_planungszeile_laesst_weg_was_fehlt(conn):
    szene_id = repo.stelle_szene_sicher(conn, 1, 4)

    assert szene.planungszeile(conn, repo.hole_szene(conn, szene_id)) == "Szene 4"


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


def test_schreibe_ohne_nummer_trifft_die_zuletzt_bearbeitete_szene(conn, einst, tg, bereit):
    """Umgedreht am 05.09.2026: frueher entstand ohne Nummer eine neue Szene
    mit der naechsten freien Nummer. Seit eine Szene erst geplant und dann
    geschrieben wird, ist das falsch -- "Go, mach den Text" meint die Szene,
    ueber die die Gruppe gerade geredet hat."""
    nummer = szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Mach den Text, Go!")

    assert nummer == 1
    szenen = repo.hole_szenen(conn, 1)
    assert len(szenen) == 1
    assert szenen[0]["titel"] == "Am Bahnhof"
    assert szenen[0]["kurzbeschreibung"] == "Maria kommt an und trifft Elif."
    assert szenen[0]["volltext"] == "MARIA: Da.\nELIF: Ja."


def test_schreibe_laesst_die_planungsfelder_stehen(conn, einst, tg, bereit):
    """``aktualisiere_szene`` fasst nur Titel, Kurzform und Volltext an -- was
    die Gruppe geplant hat, bleibt und steht beim naechsten Lauf wieder im
    Prompt."""
    szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Szene 1 schreiben")

    zeile = repo.hole_szenen(conn, 1)[0]
    assert (zeile["form"], zeile["ort"]) == ("Dialog", "Bahnhof")
    assert [f["name"] for f in repo.szene_figuren(conn, zeile["id"])] == ["Maria"]


def test_schreibe_ueberschreibt_die_szene_mit_der_genannten_nummer(conn, einst, tg, bereit):
    repo.aktualisiere_szene(conn, bereit, "Ankunft", "Maria kommt an", "MARIA: Alt.")

    nummer = szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Szene 1 nochmal, kuerzer")

    assert nummer == 1
    szenen = repo.hole_szenen(conn, 1)
    assert len(szenen) == 1
    assert szenen[0]["titel"] == "Am Bahnhof"
    assert szenen[0]["volltext"] == "MARIA: Da.\nELIF: Ja."


def test_eine_genannte_nummer_ohne_szene_legt_sie_an(conn, einst, tg):
    """Der Platz, an dem die Gruppe die fehlenden Angaben nachtraegt -- und der
    Grund, warum die Sperre eine Szenennummer nennen kann."""
    ziel = szene.ziel_fuer(conn, 1, "Schreib Szene 4")

    assert ziel["nummer"] == 4
    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [4]


def test_erste_szene_bekommt_nummer_eins(conn, einst, tg, bereit):
    assert szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Schreib uns die Szene") == 1


def test_schreibe_haelt_die_szene_im_journal_fest(conn, einst, tg, bereit):
    szene.schreibe(conn, tg, LLMAttrappe(), einst, 1, "Schreib uns die Szene")

    eintraege = repo.journal(conn, 1)
    assert ("entschieden", "Szene 1 geschrieben: Am Bahnhof") in [
        (e["art"], e["text"]) for e in eintraege
    ]


def test_schreibe_schickt_den_ganzen_szenentext(conn, einst, tg, bereit):
    """Seit 05.09.2026 geht der Szenentext VOLLSTAENDIG in die Gruppe (Birk,
    Phase-6-Knopfnavigation): lange Texte teilt der Telegram-Wrapper selbst
    (``telegram.teile_text``), und eine Sechs-Zeilen-Vorschau mit Verweis auf
    die Gruppenseite war fuer eine Gruppe, die im Raum steht und ihren Text
    lesen will, keine Hilfe. Unter dem Text haengen die vier Knoepfe
    (``knoepfe.biete_nach_szenentext``) -- hier faellt die Attrappe darauf
    zurueck, nur zu senden, und der Text muss trotzdem ankommen."""
    lang = "TITEL: Am Bahnhof\nKURZ: Eine Zeile\n\n" + "\n".join(
        f"MARIA: Zeile {i}" for i in range(20)
    )

    szene.schreibe(conn, tg, LLMAttrappe(antwort=lang), einst, 1, "Schreib uns die Szene")

    text = tg.texte[-1]
    assert text.startswith("Szene 1: Am Bahnhof")
    assert "MARIA: Zeile 5" in text
    assert "MARIA: Zeile 19" in text


def test_schreibe_sendet_reasoning_taugliche_grenzen(conn, einst, tg, bereit):
    """Die zwei gemessenen Randbedingungen fuer aktives Reasoning
    (reasoning-stufen-entscheidungshilfe.md § 3.2, § 4.3): genug
    Ausgabebudget, damit der Lauf nicht im Denken endet, und ein Zeitbudget,
    das der 30-Sekunden-Klient aus bot.main nicht hergibt."""
    klm = LLMAttrappe()

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib uns die Szene")

    assert klm.gesehen["max_tokens"] >= 12_000
    assert klm.gesehen["timeout"] >= 90
    assert klm.gesehen["art"] == "szene"


def test_die_form_der_szene_waehlt_den_regelblock(conn, einst, tg, bereit):
    repo.setze_szenenfeld(conn, bereit, "form", "Lied")
    klm = LLMAttrappe()

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib uns die Szene")

    assert "REFRAIN" in klm.gesehen["system"]
    assert "Kein Monolog laenger als sechs Zeilen" not in klm.gesehen["system"]


def test_antwort_ohne_szenentext_ist_ein_fehler(conn, einst, tg, bereit):
    klm = LLMAttrappe(antwort="TITEL: Am Bahnhof\nKURZ: Eine Zeile\n")

    with pytest.raises(szene.SzeneFehler):
        szene.schreibe(conn, tg, klm, einst, 1, "Schreib uns die Szene")

    assert repo.hole_szenen(conn, 1)[0]["volltext"] is None


def test_ohne_titel_faellt_der_code_auf_szene_n_zurueck(conn, einst, tg, bereit):
    klm = LLMAttrappe(antwort="MARIA: Ohne Kopf.")

    szene.schreibe(conn, tg, klm, einst, 1, "Schreib uns die Szene")

    assert repo.journal(conn, 1)[-1]["text"] == "Szene 1 geschrieben: Szene 1"
    assert tg.texte[-1].startswith("Szene 1: Szene 1")


# ---------------------------------------------------------------------------
# Die Sperre (T5): was fehlt, wird gefragt statt geraten
# ---------------------------------------------------------------------------


def test_ohne_pflichtfelder_wird_gar_nicht_erst_gerufen(conn, einst, tg):
    """Birk 05.09.2026: "wenn Figuren fehlen, darf die Szene gar nicht
    erstellt werden". Ein Modell, dem Ort und Besetzung fehlen, scheitert
    nicht -- es erfindet welche."""
    klm = LLMAttrappe()

    thread = szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 1")

    assert thread is None
    assert klm.aufrufe == 0
    assert tg.texte[0].startswith("Fuer Szene 1 fehlt noch: Form, Ort, Wer, Was passiert")


def test_die_sperre_nennt_genau_das_fehlende(conn, einst, tg):
    figur = _figur_mit_stimme(conn)
    _geplante_szene(conn, 1, form="Dialog", was_passiert="sie treffen sich",
                    figuren=[figur])

    szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1")

    assert tg.texte[0].startswith("Fuer Szene 1 fehlt noch: Ort")


def test_eine_figur_ohne_sprachprofil_haelt_die_szene_auf(conn, einst, tg):
    """Ohne Sprachprofil klingen in der Szene alle Figuren gleich -- genau der
    Fehler, den der Probelauf gezeigt hat. Seit 05.09. spaeter: nur, wenn die
    Figur AUCH keine Beschreibung hat -- eine beschriebene, erfundene Figur
    ("fuellst du frei") darf ohne Interview auftreten."""
    repo.setze_figur(conn, 1, "Pola", "")
    figur = repo.hole_figur(conn, 1, "Pola")["id"]
    repo.setze_arbeitsstand(conn, 1, "format", "Sprechtheater: Dialog")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Kessel, ein Abend")
    _geplante_szene(conn, 1, form="Dialog", ort="Kessel",
                    was_passiert="sie warten", figuren=[figur])

    szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1")

    assert tg.texte == [
        "Und Pola hat noch kein Sprachprofil - aus welchem Interview spricht sie?"
    ]


def test_eine_beschriebene_figur_ohne_interview_sperrt_nicht(conn, einst, tg):
    """Simulation 05.09. (Birk): 'kati und hannah fuellst du frei, das ist
    entschieden' -- der Bot sperrte trotzdem dreimal. Eine Figur mit
    Beschreibung ist spielbar; das Modell verteilt die Sprechweise (szene.md)."""
    repo.setze_figur(conn, 1, "Kati", "die Sammlerin, Hawaii im Kopf")
    figur = repo.hole_figur(conn, 1, "Kati")["id"]
    _geplante_szene(conn, 1, form="Dialog", ort="Kessel",
                    was_passiert="sie warten", figuren=[figur])

    szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1")

    assert not any("Sprachprofil" in t for t in tg.texte)


def test_fehlende_felder_und_fehlendes_profil_in_EINER_nachricht(conn, einst, tg):
    """Keine Rueckfragenkette: im Probelauf fragte der Bot viermal
    hintereinander nach einer weiteren Klarstellung (Nachrichten 84, 98, 108,
    114) und schrieb am Ende trotzdem die falsche Szene."""
    repo.setze_figur(conn, 1, "Pola", "")
    figur = repo.hole_figur(conn, 1, "Pola")["id"]
    _geplante_szene(conn, 1, form="Dialog", figuren=[figur])

    szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1")

    assert len(tg.texte) == 1
    assert "Fuer Szene 1 fehlt noch: Ort, Was passiert" in tg.texte[0]
    assert "Pola hat noch kein Sprachprofil" in tg.texte[0]


def test_die_sperre_kuendigt_nichts_an(conn, einst, tg):
    """Die Pruefung steht vor der Ankuendigung: eine Gruppe, der etwas fehlt,
    soll keine Zeile bekommen, in der steht, dass jetzt etwas laeuft."""
    szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1")

    assert not any("das dauert eine Minute" in t for t in tg.texte)
    assert not any("nicht gelungen" in t for t in tg.texte)


def test_eine_neu_auftauchende_figur_ist_ein_hinweis_keine_sperre(conn, einst, tg, bereit):
    """Die Gruppe darf eine Figur einfuehren, wo sie will -- sie soll es nur
    merken, bevor jemand im Durchlauf fragt, wo diese Person war.

    Szene 1 bekommt hier einen Text, sonst zieht die Chronologie-Sperre sie
    vor und Szene 2 kaeme gar nicht dran."""
    repo.aktualisiere_szene(conn, bereit, "Ankunft", "kurz", "MARIA: Da.")
    pal = _figur_mit_stimme(conn, name="Pal", beschreibung="filmt alles mit",
                            zitate=("Ich film das.",))
    ziel = _geplante_szene(conn, 2, form="Dialog", ort="Kueche",
                           was_passiert="sie kommen an", figuren=[pal])

    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 2"))

    assert "Pal taucht in Szene 2 zum ersten Mal auf - wo war sie vorher?" in tg.texte
    assert repo.hole_szene(conn, ziel["id"])["volltext"] == "MARIA: Da.\nELIF: Ja."


def test_in_der_ersten_szene_taucht_niemand_zum_ersten_mal_auf(conn, einst, tg, bereit):
    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Schreib Szene 1"))

    assert not any("zum ersten Mal" in t for t in tg.texte)


# ---------------------------------------------------------------------------
# starte(): Ankuendigung, Thread, Sperre, Fehlerpfad
# ---------------------------------------------------------------------------


def test_starte_kuendigt_sofort_an_und_schreibt_die_szene_im_thread(conn, einst, tg, bereit):
    thread = szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft")
    _warte(thread)

    assert "das dauert eine Minute" in tg.texte[0]
    assert tg.texte[1].startswith("Szene 1: Am Bahnhof")
    assert len(repo.hole_szenen(conn, 1)) == 1


def test_ankuendigung_steht_als_bot_nachricht_im_verlauf(conn, einst, tg, bereit):
    """Wie jede andere Bot-Zeile: sonst fehlte sie im Fenster des naechsten
    Gespraechszugs und der Bot wuesste nicht mehr, was er zugesagt hat."""
    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft"))

    texte = [n["text"] for n in repo.letzte_nachrichten(conn, 1) if n["ist_bot"]]
    assert any("das dauert eine Minute" in t for t in texte)
    assert any(t.startswith("Szene 1: Am Bahnhof") for t in texte)


def test_zweiter_auftrag_waehrend_eines_laufs_wird_abgewiesen(conn, einst, tg, bereit):
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        thread = szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: noch eine")
    finally:
        sperre.release()

    assert thread is None
    assert tg.texte == ["Ich schreibe gerade noch an einer Szene, gleich."]
    assert repo.hole_szenen(conn, 1)[0]["volltext"] is None


def test_die_sperre_gilt_je_gruppe_nicht_global(conn, einst, tg):
    repo.sichere_gruppe(conn, 2, "gruppe1", "Zweite Gruppe")
    _bereit_machen(conn, 2)
    sperre = szene._sperre_fuer(1)
    sperre.acquire()
    try:
        thread = szene.starte(conn, tg, LLMAttrappe(), einst, 2, "Szene 1: Ankunft")
        _warte(thread)
    finally:
        sperre.release()

    assert repo.hole_szenen(conn, 2)[0]["volltext"] == "MARIA: Da.\nELIF: Ja."


def test_leerer_auftrag_stoesst_nichts_an(conn, einst, tg):
    assert szene.starte(conn, tg, LLMAttrappe(), einst, 1, "   ") is None
    assert tg.gesendet == []


def test_fehlgeschlagener_lauf_meldet_sich_und_schreibt_einen_vorfall(
    conn, einst, tg, bereit
):
    klm = LLMAttrappe(fehler=RuntimeError("Sprachmodell weg"))

    _warte(szene.starte(conn, tg, klm, einst, 1, "Szene 1: Ankunft"))

    assert "nicht gelungen" in tg.texte[-1]
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")]
    assert arten == ["szene_fehlgeschlagen"]
    assert repo.hole_szenen(conn, 1)[0]["volltext"] is None


def test_nach_einem_fehlschlag_ist_die_sperre_wieder_frei(conn, einst, tg, bereit):
    _warte(szene.starte(
        conn, tg, LLMAttrappe(fehler=RuntimeError("weg")), einst, 1, "Szene 1: Ankunft",
    ))

    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft"))
    assert repo.hole_szenen(conn, 1)[0]["volltext"] == "MARIA: Da.\nELIF: Ja."


def test_zwei_laeufe_nacheinander_ueberholen_sich_nicht(conn, einst, tg, bereit):
    """Der Grund fuer die Sperre: zwei parallele Laeufe wuerden einander in
    geaendert_am ueberholen. Nacheinander muss es sauber durchlaufen."""
    figur = repo.hole_figur(conn, 1, "Maria")["id"]
    _geplante_szene(conn, 2, form="Dialog", ort="Kueche",
                    was_passiert="sie packt", figuren=[figur])

    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft"))
    _warte(szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 2: Der Koffer"))

    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [1, 2]
    assert repo.hole_letzte_szene(conn, 1)["nummer"] == 2


def test_systemanweisung_enthaelt_prompt_und_negativliste():
    text = szene.systemanweisung()

    assert "Figurennamen in GROSSBUCHSTABEN" in text
    assert "Theater-Tells" in text


def test_der_szenenlauf_ist_nicht_der_gespraechsthread(conn, einst, tg, bereit):
    """Strukturell, nicht per Behauptung: starte() gibt einen Thread zurueck,
    der zum Zeitpunkt der Rueckkehr noch laufen darf."""
    thread = szene.starte(conn, tg, LLMAttrappe(), einst, 1, "Szene 1: Ankunft")

    assert isinstance(thread, threading.Thread)
    assert thread is not threading.current_thread()
    _warte(thread)


def test_szene_ueber_claude_warnt_vor_dem_aufruf(conn, einst, monkeypatch):
    """Birk 05.09.: Opus fuer die Szene, aber mit Warnung, dass die Daten in
    die USA gehen -- vor JEDEM Aufruf. Bei Infomaniak keine Warnung."""
    import dataclasses
    from interview_theater import szene, szene_claude
    e_claude = dataclasses.replace(einst, szene_anbieter="claude")
    assert szene_claude.ist_aktiv(e_claude)
    assert not szene_claude.ist_aktiv(einst)
    assert "USA" in szene._TEXT_WARNUNG_USA
    assert "Audio" in szene._TEXT_WARNUNG_USA


def test_claude_prosa_liest_textbloecke_und_bucht(conn, einst):
    import httpx, dataclasses
    from interview_theater import szene_claude, repo
    repo.sichere_gruppe(conn, 1, "bot", "g")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["anthropic-version"] == szene_claude.API_VERSION
        assert "authorization" not in {k.lower() for k in request.headers}
        return httpx.Response(200, json={
            "content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "TITEL: X\nKURZ: y\n\nMIRA: Hallo."}],
            "stop_reason": "end_turn", "usage": {"input_tokens": 100, "output_tokens": 20},
        })
    klient = httpx.Client(transport=httpx.MockTransport(handler))
    e = dataclasses.replace(einst, szene_anbieter="claude")
    text = szene_claude.prosa(conn, e, klient, 1, "sys", "nutzer", "szene", timeout=10)
    assert text.startswith("TITEL: X")
    zeile = conn.execute("SELECT modus, antwort_token, erfolg FROM aufruf ORDER BY id DESC LIMIT 1").fetchone()
    assert tuple(zeile) == ("C", 20, 1)


def test_usa_frage_blockiert_die_szene_nicht_endlos(conn, einst, tg):
    """Simulation 05.09. (Set birk, Seed 509): Birk sagte "ja stimmt alles"
    und dreimal "jetzt endlich die szene schreiben" -- der Erkenner las das
    als Zustimmung zu den FIGUREN, nicht als Antwort auf die USA-Frage. Der
    Bot wiederholte siebenmal dieselbe Erinnerung, drei Schritte scheiterten,
    kein einziger Szenentext entstand.

    Nach USA_ERINNERUNGEN_MAX Anlaeufen entscheidet der Bot selbst -- und
    zwar fuer die Schweiz: das ist die Seite, auf der keine Daten das Land
    verlassen, ohne dass jemand zugestimmt hat."""
    import dataclasses

    e = dataclasses.replace(einst, szene_anbieter="claude")
    szene._usa_erinnerungen.pop(1, None)
    _bereit_machen(conn)

    # 1. Auftrag: das Angebot kommt.
    szene.starte(conn, tg, LLMAttrappe(), e, 1, "Schreib Szene 1")
    assert repo.szene_usa_stand(conn, 1) == "offen"

    # Erinnerungen, dann die Selbstentscheidung.
    for _ in range(szene.USA_ERINNERUNGEN_MAX):
        szene.starte(conn, tg, LLMAttrappe(), e, 1, "Schreib Szene 1")
        assert repo.szene_usa_stand(conn, 1) == "offen", "noch wird gefragt"

    szene.starte(conn, tg, LLMAttrappe(), e, 1, "Schreib Szene 1")

    assert repo.szene_usa_stand(conn, 1) == "nein", "Schweiz, nicht USA"
    assert any("nicht beantwortet" in t for t in tg.texte)
    szene._usa_erinnerungen.pop(1, None)


def test_ohne_rahmen_wird_keine_szene_geschrieben(conn, einst, tg):
    """Birk 05.09.2026 live: "es wurde gerade szene geschrieben, ohne dass
    nach setting gefragt wurde. das haette nicht passieren duerfen, denn
    diese variablen muessen alle vorher vom user gesetzt sein".

    Seit dem Abend des 05.09.2026 zaehlt nur noch ``rahmen``: das Format ist
    keine Frage mehr."""
    figur = _figur_mit_stimme(conn)
    _geplante_szene(conn, 1, form="Monolog", ort="Kueche",
                    was_passiert="sie erinnert sich", figuren=[figur])
    klm = LLMAttrappe()

    thread = szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 1")

    assert thread is None, "kein Lauf ohne Rahmen"
    assert klm.aufrufe == 0, "und vor allem kein bezahlter Modellaufruf"
    assert "Rahmen" in tg.texte[0]
    assert "Format" not in tg.texte[0]


def test_mit_format_und_rahmen_laeuft_die_szene(conn, einst, tg):
    """Die Gegenprobe: sind beide gesetzt, sperrt nichts mehr -- sonst waere
    die neue Pruefung eine Sackgasse statt einer Sicherung."""
    figur = _figur_mit_stimme(conn)
    _geplante_szene(conn, 1, form="Monolog", ort="Kueche",
                    was_passiert="sie erinnert sich", figuren=[figur])
    repo.setze_arbeitsstand(conn, 1, "format", "Sprechtheater: Monolog")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Kueche, ein Abend")

    assert szene.sperrtext(conn, repo.hole_szene(conn, 1)) is None


# --- Dialog als Rueckfall (05.09.2026 abends) -----------------------------


def test_der_dialog_regelblock_steht_in_der_systemanweisung():
    """Seit Birks Entscheidung vom 05.09.2026 abends entsteht immer zuerst
    ein Sprechtheater-Textbuch (gemessen am Herkules.exe-Textbuch): das
    Textbuch ist Ausgangsmaterial, die Inszenierung macht das Team in der
    Probe. Der Regelblock darf deshalb genau das NICHT mehr enthalten, was
    die verworfene Tanztheater-Recherche vorgab."""
    text = szene.systemanweisung(None)

    assert "Sprechtheater-Textbuch" in text
    assert "Choreografin" in text
    # Die alten Vorgaben sind nicht nur weg, sie stehen jetzt auf der
    # Negativliste -- deshalb wird hier nicht auf Abwesenheit der Woerter
    # geprueft, sondern darauf, dass sie ausdruecklich verboten sind.
    for verbannt in ("[BEWEGUNG]", "Counts und Musiktakte", "Choreografie"):
        assert verbannt in text, verbannt
    for weg in ("Zaehl in Achten", "Hoechstens zwoelf Zeilen gesprochener"):
        assert weg not in text, weg


# ---------------------------------------------------------------------------
# Das Kernpaket im Szenen-Prompt (05.09.2026 abends)
# ---------------------------------------------------------------------------


def _kernpaket(conn):
    """Kernthema, Kernfrage, ein gefiltertes Thema mit Zitat -- und ein
    zweites Interview, das nicht zum Kernthema gehoert."""
    repo.merke_nachricht(conn, 1, 90, "Ada", 0, "sprache", None, "2026-09-06T10:00:00+00:00")
    passend_id = repo.lege_aufnahme_an(conn, 1, 90, "lang", "sprache", "/tmp/a.ogg", 300)
    repo.speichere_verdichtung(
        conn, 1, passend_id, "Maria erzaehlt von der Naeharbeit.",
        [{"thema": "Arbeit ohne Anerkennung",
          "beleg_zitat": "Keiner hat gefragt", "zitat_geprueft": 1}],
    )
    repo.merke_nachricht(conn, 1, 91, "Ada", 0, "sprache", None, "2026-09-06T10:05:00+00:00")
    fremd_id = repo.lege_aufnahme_an(conn, 1, 91, "lang", "sprache", "/tmp/b.ogg", 300)
    repo.speichere_verdichtung(
        conn, 1, fremd_id, "Pal erzaehlt von seinen Wochenendfahrten.",
        [{"thema": "Fahrten am Wochenende",
          "beleg_zitat": "Am Samstag faehrt keiner", "zitat_geprueft": 1}],
    )
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Arbeit, die niemand sieht")
    repo.setze_arbeitsstand(
        conn, 1, "kernfrage",
        "Frage: Was passiert, wenn niemand fragt?\nGegensatz: sehen wollen - "
        "gesehen werden\nEinsatz: ob die Arbeit zaehlt",
    )
    passend = next(
        t for t in repo.gepruefte_themen(conn, 1)
        if t["thema"] == "Arbeit ohne Anerkennung"
    )
    repo.markiere_themen_zum_kernthema(conn, 1, [passend["id"]])
    repo.ersetze_kernzitate(
        conn, 1,
        [{"verdichtung_thema_id": passend["id"], "aufnahme_id": passend_id,
          "zitat": "Keiner hat gefragt", "begruendung": "genau der Einsatz"}],
    )


def test_der_szenen_prompt_traegt_kernfrage_und_kernzitate(conn):
    _kernpaket(conn)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: der Platz")

    assert "Kernfrage:" in text
    assert "Was passiert, wenn niemand fragt?" in text
    assert '"Keiner hat gefragt"' in text
    assert "genau der Einsatz" in text


def test_der_szenen_prompt_traegt_keine_fremden_verdichtungen(conn):
    """Die Zitatquelle sind die Kernzitate, nicht alles Material: was nicht
    zum Kernthema markiert ist, steht nicht im Prompt."""
    _kernpaket(conn)

    text = szene.baue_nutzertext(conn, 1, "Szene 1: der Platz")

    assert "Fahrten am Wochenende" not in text
    assert "Am Samstag faehrt keiner" not in text
    assert "Pal erzaehlt von seinen Wochenendfahrten" not in text


def test_ohne_auswahl_bleibt_der_kernpaket_block_weg(conn):
    """Datengetrieben wie alle Bloecke."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")

    text = szene.baue_nutzertext(conn, 1, "Szene 1")

    assert szene.KERNPAKET_KOPF not in text


def test_nackte_zahl_im_auftrag_ist_die_szenennummer():
    """Live-Fall 05.09. 22:20: "/szene 1" (Rest "1") schrieb Szene 3, weil
    die nackte Zahl nicht als Nummer gelesen wurde."""
    from interview_theater import szene

    assert szene.nummer_aus_auftrag("1") == 1
    assert szene.nummer_aus_auftrag(" 2 ") == 2
    assert szene.nummer_aus_auftrag("Szene 3 nochmal") == 3
    assert szene.nummer_aus_auftrag("mach den Text") is None
    assert szene.nummer_aus_auftrag("3 Freunde am Kiosk") is None


# ---------------------------------------------------------------------------
# Chronologie-Sperre (05.09.2026): nur die kleinste offene Szene wird
# geschrieben. Live-Befund der Testgruppe 22:05 -- Szene 3 wurde vor Szene 1
# und 2 geschrieben, und der Text schloss an nichts an.
# ---------------------------------------------------------------------------


def test_ziel_fuer_zieht_die_kleinste_offene_szene_vor(conn, einst):
    _bereit_machen(conn, nummer=1)
    _bereit_machen(conn, nummer=2)
    _bereit_machen(conn, nummer=3)

    ziel = szene.ziel_fuer(conn, 1, "Schreib Szene 3.")

    assert ziel["nummer"] == 1


def test_ohne_chronologie_bleibt_die_gemeinte_szene_stehen(conn, einst):
    """Der Weg fuer Aufrufer, die nur wissen wollen, wovon die Rede war."""
    _bereit_machen(conn, nummer=1)
    _bereit_machen(conn, nummer=3)

    ziel = szene.ziel_fuer(conn, 1, "Schreib Szene 3.", chronologisch=False)

    assert ziel["nummer"] == 3


def test_auftrag_auf_szene_3_schreibt_szene_1_und_sagt_es(conn, einst, tg):
    _bereit_machen(conn, nummer=1)
    _bereit_machen(conn, nummer=2)
    _bereit_machen(conn, nummer=3)
    klm = LLMAttrappe()

    _warte(szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 3."))

    assert any(
        "Szene 3 kommt nach Szene 1" in t for t in tg.texte
    ), tg.texte
    szenen = {s["nummer"]: s for s in repo.hole_szenen(conn, 1)}
    assert (szenen[1]["volltext"] or "").strip()
    assert not (szenen[3]["volltext"] or "").strip()


def test_eine_geschriebene_szene_darf_jederzeit_neu_geschrieben_werden(conn, einst, tg):
    """\"Neu schreiben\" auf Szene 3 bleibt erlaubt, auch wenn Szene 2 leer
    ist: eine Ueberarbeitung ist keine Vorwegnahme."""
    _bereit_machen(conn, nummer=2)
    szene_id = _bereit_machen(conn, nummer=3)
    repo.aktualisiere_szene(conn, szene_id, "Alt", "kurz", "ALTER TEXT")
    klm = LLMAttrappe()

    _warte(szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 3 neu."))

    assert not any("kommt nach Szene" in t for t in tg.texte), tg.texte
    assert repo.hole_szene(conn, szene_id)["volltext"] != "ALTER TEXT"


def test_ist_die_fruehere_szene_geschrieben_laeuft_die_naechste(conn, einst, tg):
    eins = _bereit_machen(conn, nummer=1)
    repo.aktualisiere_szene(conn, eins, "Ankunft", "kurz", "MARIA: Da.")
    zwei = _bereit_machen(conn, nummer=2)
    klm = LLMAttrappe()

    _warte(szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 2."))

    assert not any("kommt nach Szene" in t for t in tg.texte), tg.texte
    assert (repo.hole_szene(conn, zwei)["volltext"] or "").strip()


# ---------------------------------------------------------------------------
# Volltext der frueheren Szenen im Prompt (05.09.2026)
# ---------------------------------------------------------------------------


def test_continuity_traegt_den_volltext_der_frueheren_szene(conn, einst):
    figur = _figur_mit_stimme(conn)
    eins = _geplante_szene(conn, 1, titel="Ankunft", ort="Bahnhof",
                           was_passiert="Maria kommt an", figuren=[figur])
    repo.aktualisiere_szene(
        conn, eins["id"], "Ankunft", "kurz", "MARIA: Der Koffer ist offen."
    )
    ziel = _geplante_szene(conn, 2, form="Dialog", ort="Treppenhaus",
                           was_passiert="sie streiten", figuren=[figur])

    text = szene.baue_nutzertext(conn, 1, "Szene 2 schreiben", ziel)

    assert szene.CONTINUITY_ANSCHLUSS in text
    assert szene.CONTINUITY_VOLLTEXT_KOPF.format(nummer=1) in text
    assert "MARIA: Der Koffer ist offen." in text
    # Die Stichzeilen bleiben daneben stehen.
    assert "Ort: Bahnhof" in text


def test_ohne_volltext_bleibt_es_bei_den_stichzeilen(conn, einst):
    figur = _figur_mit_stimme(conn)
    _geplante_szene(conn, 1, titel="Ankunft", ort="Bahnhof",
                    was_passiert="Maria kommt an", figuren=[figur])
    ziel = _geplante_szene(conn, 2, form="Dialog", ort="Treppenhaus",
                           was_passiert="sie streiten", figuren=[figur])

    text = szene.baue_nutzertext(conn, 1, "Szene 2 schreiben", ziel)

    assert "Ort: Bahnhof" in text
    assert szene.CONTINUITY_VOLLTEXT_KOPF.format(nummer=1) not in text


def test_zu_lange_volltexte_werden_bei_den_aeltesten_gekuerzt(conn, einst):
    """Ueber CONTINUITY_ZEICHEN_MAX faellt die AELTESTE Szene auf ihren
    Schluss zurueck -- die juengste bleibt vollstaendig, an sie wird
    unmittelbar angeschlossen."""
    figur = _figur_mit_stimme(conn)
    lang = "\n".join(f"ZEILE {i}: " + "x" * 100 for i in range(400))
    for nummer in (1, 2):
        zeile = _geplante_szene(conn, nummer, ort=f"Ort {nummer}",
                                was_passiert="etwas", figuren=[figur])
        repo.aktualisiere_szene(
            conn, zeile["id"], f"Szene {nummer}", "kurz",
            f"ANFANG {nummer}\n{lang}\nSCHLUSS {nummer}",
        )
    ziel = _geplante_szene(conn, 3, form="Dialog", ort="Treppenhaus",
                           was_passiert="sie streiten", figuren=[figur])

    text = szene.baue_nutzertext(conn, 1, "Szene 3 schreiben", ziel)

    assert szene._TEXT_CONTINUITY_GEKUERZT in text
    assert "ANFANG 1" not in text, "die aelteste Szene wird gekuerzt"
    assert "SCHLUSS 1" in text, "ihr Schluss bleibt stehen"
    assert "ANFANG 2" in text, "die juengste Szene bleibt vollstaendig"


def test_kuerzung_laesst_kurze_szenen_in_ruhe(conn, einst):
    kurz = "MARIA: Da.\nELIF: Ja."

    assert szene._gekuerzter_volltext(kurz) == kurz


def test_die_aufgabe_der_szene_steht_im_prompt(conn):
    """06.09.2026: Szene 1 hing nicht mit der Geschichte zusammen -- der Prompt
    sagte nirgends, was die erste Szene LEISTEN muss. Jetzt steht die Aufgabe
    (Exposition: wer, zueinander, warum hier, worum) vor den Angaben."""
    from interview_theater import szene

    repo.sichere_gruppe(conn, 1, "bot", "g")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Vier Freundinnen, eine verliebt")
    a = repo.stelle_szene_sicher(conn, 1, 1)
    b = repo.stelle_szene_sicher(conn, 1, 2)
    c = repo.stelle_szene_sicher(conn, 1, 3)
    erste = szene.baue_nutzertext(conn, 1, "Szene 1", repo.hole_szene(conn, a))
    mitte = szene.baue_nutzertext(conn, 1, "Szene 2", repo.hole_szene(conn, b))
    letzte = szene.baue_nutzertext(conn, 1, "Szene 3", repo.hole_szene(conn, c))
    assert "ERSTE -- Exposition" in erste and "wer die Figuren sind" in erste
    assert "Szene 2 von 3" in mitte
    assert "die LETZTE" in letzte
    assert erste.index("Aufgabe dieser Szene") < erste.index("Diese Szene sollst du schreiben")
    assert "Vorgabe der Gruppe" in erste
