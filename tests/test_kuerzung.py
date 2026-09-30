"""Kuerzen als eigener Weg (30.09.2026, Massnahme C4).

Der gemessene Fall (docs/analyse-phase5-chaos-2026-09-06.md Abschnitt 4): die
Gruppe bat um Kuerzung, der Bot kannte keinen Kuerzungspfad, das
Gespraechsmodell antwortete mit einer NEUEN Szenenliste, und der Erkenner las
sie als Planung -- aus drei Szenen wurden sechs, und spaeter noch einmal
sechs.

Gemessen wird hier genau das Gegenteil: derselbe Text wird ueberarbeitet, die
Fassung wird ANGEHAENGT, und die Szenenfolge bleibt, wie sie ist.

Kein Netz: Telegram und Sprachmodell sind Attrappen.
"""

import pytest

from interview_theater import knoepfe, kuerzung, phasen, repo, szene

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


SZENENTEXT_LANG = (
    "Titel: Am Steg\n"
    "Kurz: Sie treffen sich.\n"
    "Zusammenfassung: Mira und Pal treffen sich am Steg.\n"
    "Anders gemacht: nichts\n"
    "\n"
    "MIRA: Du bist zu spaet.\n"
    "PAL: Ich war da, du hast nicht geschaut.\n"
)


class LLMAttrappe:
    """Liefert einen Szenentext und merkt jeden Nutzertext."""

    def __init__(self, antwort=SZENENTEXT_LANG):
        self.antwort = antwort
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        return self.antwort


# --- Die Notiztexte -------------------------------------------------------


def test_die_notiz_nennt_das_kuerzungsziel():
    """25 Prozent steht an EINER Stelle (``kuerzung.PROZENT``) und wandert von
    dort in Notiz und Knopfbeschriftung -- zwei Zahlen waeren zwei
    Wahrheiten."""
    assert kuerzung.PROZENT == 25
    assert "25" in kuerzung.notiz_fuer_szene()
    assert "25" in knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT)


def test_die_prosa_notiz_bindet_die_abschnittszahl():
    """``kurzgeschichte.ANWEISUNG`` stellt dem Modell die Abschnittszahl frei
    (kurzgeschichte.py:57-60). Ohne diesen Satz waere eine kuerzere Geschichte
    mit weniger Abschnitten ein plausibles Ergebnis -- und zwei Abschnitte
    behielten ihren alten, langen Text."""
    notiz = kuerzung.notiz_fuer_prosa(6)
    assert "6" in notiz
    assert "25" in notiz


def test_nummer_aus_wert_liest_nur_zahlen():
    assert kuerzung.nummer_aus_wert("3") == 3
    assert kuerzung.nummer_aus_wert(" 12 ") == 12
    assert kuerzung.nummer_aus_wert("") is None
    assert kuerzung.nummer_aus_wert(None) is None
    assert kuerzung.nummer_aus_wert("Szene drei") is None


# --- Phase 7: eine Szene --------------------------------------------------


@pytest.fixture
def szene7(conn):
    """Phase 7, eine Szene mit Volltext, Form und Besetzung."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "format", "Sprechtheater")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert", "Sie treffen sich.")
    figur = repo.figuren(conn, 1)[0]
    repo.setze_szene_figuren(conn, 1, szene_id, [figur["id"]])
    repo.aktualisiere_szene(
        conn, szene_id, "Am Steg", "Sie treffen sich.",
        "MIRA: Du bist zu spaet und ich habe lange gewartet, sehr lange.",
        "Mira wartet.",
    )
    repo.haenge_szenenfassung_an(
        conn, 1, szene_id,
        "MIRA: Du bist zu spaet und ich habe lange gewartet, sehr lange.",
        "Mira wartet.",
    )
    phasen.setze(conn, 1, 7, "test")
    return conn


def test_der_kuerzen_knopf_steht_unter_dem_szenentext(szene7, tg):
    knoepfe.biete_nach_szenentext(szene7, tg, 1, 1, "Szene 1\n\nMIRA: …")
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT) in beschriftungen


def test_kuerzen_schreibt_die_szene_neu_und_haengt_die_fassung_an(szene7, tg, einst):
    conn = szene7
    klm = LLMAttrappe()
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    vorher = len(repo.szenenfassungen(conn, szene_id))

    thread = szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 1 neu. "
                          + kuerzung.notiz_fuer_szene())
    assert thread is not None
    thread.join(timeout=20)

    assert len(repo.szenenfassungen(conn, szene_id)) == vorher + 1
    # Der aktuelle Text ist der neue, die alte Fassung steht weiter da.
    aktuell = repo.hole_szene(conn, szene_id)["volltext"]
    assert "du hast nicht geschaut" in aktuell
    assert "sehr lange" in repo.szenenfassungen(conn, szene_id)[0]["volltext"]


def test_der_kuerzen_knopf_traegt_die_notiz_in_den_prompt(szene7, tg, einst):
    """Der Weg hinter dem Knopf, ueber ``knoepfe.behandle`` -- also durch die
    Idempotenz-Wache (Zusage 3) und ohne Modellaufruf im Handler (Zusage 2)."""
    conn = szene7
    klm = LLMAttrappe()
    knoepfe.biete_nach_szenentext(conn, tg, 1, 1, "Szene 1\n\nMIRA: …")
    daten = dict(tg.knoepfe[-1][2])[
        knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT)
    ]
    assert knoepfe.behandle(conn, tg, klm, einst, _druck(daten)) is True
    # Der Lauf haengt in einem eigenen Thread; auf sein Ende wird ueber die
    # Sperre des Szenenlaufs gewartet.
    assert szene._sperre_fuer(1).acquire(timeout=20)
    szene._sperre_fuer(1).release()
    assert klm.aufrufe, "kein Szenenlauf angestossen"
    assert str(kuerzung.PROZENT) in klm.aufrufe[0]["nutzer"]


def test_kuerzen_legt_keine_neue_szenenfolge_an(szene7, tg, einst):
    """Die Wurzel des Chaos: eine Kuerzungsbitte wurde als Neuaufbau wirksam.
    Nach einer Kuerzung muss es dieselbe Szene mit derselben Nummer und
    derselben Form sein."""
    conn = szene7
    klm = LLMAttrappe()
    vorher = [(s["id"], s["nummer"], s["form"]) for s in repo.hole_szenen(conn, 1)]
    thread = szene.starte(conn, tg, klm, einst, 1, "Schreib Szene 1 neu. "
                          + kuerzung.notiz_fuer_szene())
    thread.join(timeout=20)
    nachher = [(s["id"], s["nummer"], s["form"]) for s in repo.hole_szenen(conn, 1)]
    assert nachher == vorher


# --- Phase 6: die ganze Kurzgeschichte ------------------------------------


@pytest.fixture
def prosa6(conn):
    """Phase 6, drei Abschnitte mit Prosa -- der Stand nach einem Prosalauf."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    for nummer, titel in ((1, "Ankunft"), (2, "Das Gestaendnis"), (3, "Der Morgen")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel)
        repo.aktualisiere_szene(
            conn, szene_id, titel, None, None, f"{titel} passiert.",
            prosa=f"{titel}: ein langer Abschnitt, sehr lang, viel zu lang.",
        )
    phasen.setze(conn, 1, 6, "test")
    return conn


def test_der_kuerzen_knopf_steht_unter_der_kurzgeschichte(prosa6, tg):
    knoepfe.zeige_kurzgeschichte(prosa6, tg, 1)
    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert knoepfe.TEXT_KUERZEN_KNOPF.format(prozent=kuerzung.PROZENT) in beschriftungen


def test_kuerzen_ohne_nummer_nennt_die_abschnittszahl(prosa6, tg, einst):
    """Drei Abschnitte -> die Notiz bindet auf drei."""
    conn = prosa6
    gemerkt = {}

    def attrappe(c, t, k, ein, chat_id, regie=None):
        gemerkt["regie"] = regie
        return object()

    import interview_theater.kurzgeschichte as kurzgeschichte_modul
    echt = kurzgeschichte_modul.starte
    kurzgeschichte_modul.starte = attrappe
    try:
        kuerzung.starte(conn, tg, LLMAttrappe(), einst, 1)
    finally:
        kurzgeschichte_modul.starte = echt
    assert "3" in gemerkt["regie"]
    assert str(kuerzung.PROZENT) in gemerkt["regie"]


def test_ohne_text_gibt_es_keinen_lauf(conn, tg, einst):
    """Kein bezahlter Lauf auf nichts -- und eine Zeile, die sagt warum."""
    klm = LLMAttrappe()
    phasen.setze(conn, 1, 6, "test")
    meldung = kuerzung.starte(conn, tg, klm, einst, 1)
    assert meldung == kuerzung.TEXT_NICHTS_ZU_KUERZEN
    assert kuerzung.TEXT_NICHTS_ZU_KUERZEN in tg.texte
    assert klm.aufrufe == []


def test_kuerzen_ist_kein_modellaufruf_im_handler():
    """Zusage 2, hier am Handler selbst: ``kuerzung.starte`` gibt an einen
    Thread ab. ``tests/test_knoepfe_struktur.py`` prueft dasselbe am AST des
    ganzen Pakets."""
    assert knoepfe.ART_SZENE_KUERZEN in knoepfe._WIRKUNGEN
    assert knoepfe.ART_GESCHICHTE_KUERZEN in knoepfe._WIRKUNGEN
