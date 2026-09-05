"""Prompt-Audit: ein Test je Prompt-Pfad gegen eine Fixture-Datenbank.

**Warum es diese Datei gibt** (Audit 06.09.2026). Die Fehler, die in der
Nacht zum 06.09. an der Testgruppe gemessen wurden, waren allesamt keine
Ausnahmen und keine Modellfehler: sie standen so im Prompt. Der Verlauf ging
52.361 Zeichen lang raus, Kernthema und Rahmen dreimal, dieselbe
Interview-Zusammenfassung elfmal, "Szene 1 geschrieben" viermal. Jeder
einzelne dieser Befunde ist mechanisch pruefbar -- und genau das passiert
hier, gegen eine Datenbank mit realistischem Spaetstand statt gegen einen
handgeschriebenen Prompt.

Die drei Regeln, die jeder Pfad einhalten muss:

1. **Kein Satz ueber 80 Zeichen steht zweimal drin.** Ein Fakt, eine Stelle.
2. **Der Nutzertext bleibt unter der harten Grenze** (``kontext.zeichengrenze``).
3. **Keine veralteten Reste**: Beispiel-Eigennamen aus alten Prompt-Fassungen
   (Kessel, Mira, Pola, Pal), die alte Phasenzahl, alte Stationsnamen.

Die Regeln stehen als Helfer da und nicht als Parametrisierung ueber alle
Pfade: nicht jeder Pfad hat dieselbe Grenze (der Erkenner darf Beispielnamen
tragen, er ist ein Few-Shot-Prompt), und ein Test, der das mit Ausnahmelisten
erschlaegt, sagt am Ende nicht mehr, was er eigentlich zusichert.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import (
    db, einstellungen, journal, kontext, kernzitate, repo, schaerfung,
    sprachprofil, szene, szenenfolge, verdichter,
)

#: Ab dieser Laenge gilt eine wortgleiche Zeile als Dublette. Kuerzere Zeilen
#: ("Szene 2", "Ja.", eine Ueberschrift) wiederholen sich zu Recht.
DUBLETTE_AB = 80

#: Eigennamen aus frueheren Prompt-Fassungen und Beispielen. Sie gehoeren in
#: keinen erzeugten Prompt -- gemessen am 05.09.2026 sagte der Bot dreimal
#: "Pola", und die Gruppe hatte nie eine Pola.
FREMDE_NAMEN = ("Kessel", "Mira", "Pola", "Pal ")

BASIS = datetime(2026, 9, 6, 0, 33, 0, tzinfo=timezone.utc)


def _iso(versatz_minuten: int) -> str:
    return (BASIS + timedelta(minutes=versatz_minuten)).isoformat(timespec="seconds")


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe4", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def spaetstand(tmp_path):
    """Eine Gruppe im Spaetstand: Phase 7, vier Figuren, vier Szenen, ein
    gewuchertes Journal, ein langer Verlauf und ein Interview mit vielen
    markierten Themen.

    Das ist der Stand, an dem die Fehler sichtbar werden. Eine frische
    Datenbank zeigt keinen davon -- deshalb hat der Audit-Befund so lange
    ueberlebt: die Tests liefen alle gegen den Vormittag.
    """
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe4", "Testgruppe")

    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe, Spass, Streit")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "ungluecklich verliebt sein und Rassismus")
    repo.setze_arbeitsstand(conn, 1, "kernfrage", "Was haelt uns bei jemandem, der uns kleinmacht?")
    repo.setze_arbeitsstand(
        conn, 1, "rahmen",
        "Vier Freundinnen leben im Nordkiez in Dortmund. Eine ist ungluecklich "
        "verliebt in einen rassistischen Typen; die anderen wollen sie ueberzeugen.",
    )
    repo.setze_arbeitsstand(
        conn, 1, "geschichte",
        "Leyla haelt an einem Jungen fest, der sie kleinmacht. Die drei Freundinnen "
        "versuchen erst zu reden, dann zu draengen, dann zu schweigen. Am Ende "
        "bleibt Leyla stehen und entscheidet zum ersten Mal selbst.",
    )
    repo.setze_phase(conn, 1, 7)

    # Ein Interview mit einer langen Zusammenfassung und vielen Themen: genau
    # die Lage, in der die Zusammenfassung elfmal in den Prompt geriet.
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, "T" * 400)
    zusammenfassung = (
        "Die befragte Person erzaehlt von ihrer Freundin, der in der Bahn das "
        "Kopftuch abgezogen wurde, und raet Betroffenen, sich keine Gedanken zu "
        "machen. Sie streitet regelmaessig mit ihrem Bruder, der ihre Sachen "
        "ohne Fragen nimmt. Liebe hat sie noch nie bewusst erlebt."
    )
    themen = [
        {"thema": thema, "beleg_zitat": f"Beleg {i}", "zitat_geprueft": 1,
         "kurz": f"kurz {i}"}
        for i, thema in enumerate(
            ["Rassismus", "Rassismus", "Rassismus", "Streit", "Streit", "Streit",
             "Liebe", "Liebe", "Spass", "Spass", "Spass"]
        )
    ]
    verdichtung_id = repo.speichere_verdichtung(conn, 1, aufnahme_id, zusammenfassung, themen)
    repo.markiere_themen_zum_kernthema(
        conn, 1, [t["id"] for t in repo.themen_zu(conn, verdichtung_id)]
    )

    for name, beschreibung, profil in (
        ("Leyla", "will, dass die Liebe reicht", "Kurze Saetze, bricht ab."),
        ("Cemre", "will ihre Freundin retten", "Direkt, laesst nicht locker."),
        ("Aylin", "will den Frieden halten", "Lange Schachtelsaetze, weicht aus."),
        ("Zeynep", "will Fairness in der Familie", "Nennt Zahlen und Uhrzeiten."),
    ):
        repo.setze_figur(conn, 1, name, beschreibung)
        repo.setze_sprachprofil(
            conn, repo.hole_figur(conn, 1, name)["id"], profil, zitate=[]
        )

    szene_id = repo.lege_szene_an(
        conn, 1, 1, "Einundfuenfzig Stunden",
        "Leyla wartet auf dem Schulhof auf eine Antwort.",
        "LEYLA: Gelesen.\n\nCEMRE: Sie geht nicht.\n",
    )
    for feld, wert in (("form", "dialog"), ("ort", "Schulhof"),
                       ("zeit", "Freitagnachmittag")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    for nummer in (2, 3, 4):
        repo.lege_szene_an(conn, 1, nummer, None, None, None)

    # Ein Journal wie am 06.09.: mit vierfacher Dublette.
    for art, text in (
        ("entschieden", "Begriffe: Rassismus, Liebe, Spass, Streit"),
        ("entschieden", "Phase 4 · Setting & Figuren"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("entschieden", "Szene 1 geschrieben: Einundfuenfzig Stunden"),
        ("vorgeschlagen", "Leyla will, dass die Liebe reicht, basierend auf Interview 1."),
        ("vorgeschlagen", "Cemre will ihre Freundin retten, basierend auf Interview 1."),
        ("vorgeschlagen", "Aylin will den Frieden halten, basierend auf Interview 1."),
        ("vorgeschlagen", "Zeynep will Fairness, basierend auf Interview 1."),
        ("entschieden", "Szene 1 neu geplant: Dialog am Kiosk, Exposition der vier."),
    ):
        repo.schreibe_journal(conn, 1, art, text, quelle="befehl")

    # Ein langer Verlauf: 400 Nachrichten, wie er ueber zwei Workshoptage
    # entsteht. Ohne ihn greift keine Kuerzung.
    for i in range(400):
        repo.merke_nachricht(
            conn, 1, 100 + i, "Bot" if i % 2 else "Birk", i % 2, "text",
            f"Ein laengerer Gespraechsbeitrag ueber Szene 1 und die Figuren, Nummer {i}.",
            _iso(i),
        )
    return conn


def _dubletten(text: str) -> dict[str, int]:
    """Wortgleiche Zeilen ab DUBLETTE_AB Zeichen, die mehr als einmal
    vorkommen -- der mechanische Test auf 'ein Fakt, eine Stelle'."""
    lang = [z.strip() for z in text.splitlines() if len(z.strip()) >= DUBLETTE_AB]
    return {z: n for z, n in Counter(lang).items() if n > 1}


def _pruefe_ohne_dubletten(text: str, pfad: str) -> None:
    doppelt = _dubletten(text)
    assert not doppelt, (
        f"{pfad}: {len(doppelt)} Zeile(n) stehen mehrfach im Prompt -- "
        f"z. B. {sorted(doppelt.items(), key=lambda p: -p[1])[0]}"
    )


# --- Gespraechszug ---------------------------------------------------------


def test_gespraech_ohne_dubletten(spaetstand, einst):
    """Der Befund vom 06.09.: Kernthema und Rahmen dreimal, die
    Interview-Zusammenfassung elfmal, vier gleiche Journalzeilen."""
    ausloeser = [repo.hole_nachricht(spaetstand, 1, 499)]
    prompt = kontext.baue(spaetstand, 1, ausloeser, einst)
    _pruefe_ohne_dubletten(prompt, "gespraech")


def test_gespraech_haelt_die_harte_zeichengrenze(spaetstand, einst):
    """52.361 Zeichen sind rausgegangen, obwohl § 7.2 kuerzen sollte -- weil
    ZIEL in Token gemessen wurde und der Prompt darunter blieb."""
    ausloeser = [repo.hole_nachricht(spaetstand, 1, 499)]
    prompt = kontext.baue(spaetstand, 1, ausloeser, einst)
    assert len(prompt) <= kontext.zeichengrenze(), (
        f"Nutzertext {len(prompt)} Zeichen ueber der Grenze "
        f"{kontext.zeichengrenze()}"
    )


def test_kuerzung_meldet_vorfall_mit_zahlen(spaetstand, einst, monkeypatch):
    """Wer kuerzt, sagt es -- mit Zahlen, damit es hinterher nachweisbar ist.

    Mit einer engen Grenze erzwungen: seit dem Fensterumbau begrenzt schon
    der Fensterbau, und im Normalfall bleibt der Prompt darunter. Die
    Gesamtkuerzung ist die zweite Bremse dahinter -- sie muss trotzdem
    beweisbar funktionieren, sonst faellt sie beim naechsten Wachstum
    unbemerkt aus (genau der Weg, auf dem § 7.2 wirkungslos wurde).
    """
    monkeypatch.setenv("IT_PROMPT_ZEICHEN", "4000")
    ausloeser = [repo.hole_nachricht(spaetstand, 1, 499)]
    kontext.baue(spaetstand, 1, ausloeser, einst)
    zeilen = spaetstand.execute(
        "SELECT detail FROM vorfall WHERE art = 'kontext_gekuerzt'"
    ).fetchall()
    assert zeilen, "Kuerzung ohne Vorfall ist eine unsichtbare Kuerzung"
    assert "Zeichen" in zeilen[0]["detail"]


def test_ausloeser_ueberlebt_jede_kuerzung(spaetstand, einst):
    """Es gibt keinen Zustand, in dem der Bot wegen des Budgets die Frage
    nicht mehr sieht, auf die er antworten soll (§ 7.2)."""
    repo.merke_nachricht(
        spaetstand, 1, 900, "Birk", 0, "text",
        "Und worauf einigen wir uns jetzt fuer die naechste Szene?", _iso(500),
    )
    ausloeser = [repo.hole_nachricht(spaetstand, 1, 900)]
    prompt = kontext.baue(spaetstand, 1, ausloeser, einst)
    assert "worauf einigen wir uns jetzt" in prompt


def test_gespraech_nennt_die_phase_genau_einmal(spaetstand, einst):
    """Der Widerspruch vom 06.09.: der Arbeitsstand sagte Phase 7, das
    Journal Phase 6. Eine Quelle -- ``phasen.aktuelle`` -- und im
    Arbeitsstand genau eine Zeile."""
    ausloeser = [repo.hole_nachricht(spaetstand, 1, 499)]
    prompt = kontext.baue(spaetstand, 1, ausloeser, einst)
    assert prompt.count("Aktuelle Phase:") == 1


def test_gespraech_ohne_fremde_beispielnamen(spaetstand, einst):
    ausloeser = [repo.hole_nachricht(spaetstand, 1, 499)]
    prompt = kontext.baue(spaetstand, 1, ausloeser, einst)
    system = kontext.system(einst.bot_name, 7)
    for name in FREMDE_NAMEN:
        assert name not in prompt, f"Beispielname {name!r} im Gespraechs-Prompt"
        assert name not in system, f"Beispielname {name!r} in der Systemanweisung"


def test_systemanweisung_kennt_acht_stufen(einst):
    """Nach dem Umbau vom 05.09. gibt es acht Stationen -- die Anweisung
    sagte noch 'sieben Stationen' und listete darunter acht."""
    system = kontext.system(einst.bot_name, 7)
    assert "sieben Stationen" not in system
    assert "acht Stationen" in system
    assert "8. Durchlauf" in system


def test_systemanweisung_ohne_alte_stationsnamen(einst):
    """'Kernthema & Figuren' und 'Format & Rahmen' heissen seit dem Umbau
    'Setting & Figuren' und 'Geschichte'."""
    system = kontext.system(einst.bot_name, 7)
    assert "Kernthema & Figuren" not in system
    assert "Format & Rahmen" not in system
    assert "Setting & Figuren" in system


# --- Auftragszuege ---------------------------------------------------------


@pytest.mark.parametrize("anweisung", [
    "Schlag du vor.",
    "Schlag drei andere Namen fuer diese Figur vor.",
    "Schlag drei andere Sprachduktus-Beschreibungen vor.",
    "Schlag drei grobe Richtungen fuer das Kernthema vor.",
])
def test_auftragszug_haelt_grenze_und_ist_dublettenfrei(spaetstand, einst, anweisung):
    """Ein Auftragszug ist ein Gespraechszug ohne ausloesende Nachricht --
    dieselben Regeln, und er darf nicht laenger werden, nur weil ihn ein
    Knopf ausgeloest hat."""
    from interview_theater import ablauf

    koerper = kontext.baue(spaetstand, 1, [], einst)
    koerper = f"{koerper}\n\n{ablauf._AUFTRAG_KOPF}\n{anweisung}"
    _pruefe_ohne_dubletten(koerper, f"auftragszug {anweisung!r}")
    # Die Anweisung selbst kommt oben drauf -- sie ist der Auftrag und
    # ueberlebt die Kuerzung wie die ausloesende Nachricht.
    assert anweisung in koerper
    assert len(koerper) <= kontext.zeichengrenze() + len(anweisung) + 200


# --- Szene -----------------------------------------------------------------


@pytest.mark.parametrize("form", ["dialog", "monolog", "chor", "lied", "rap"])
def test_szene_ohne_dubletten(spaetstand, form):
    """Die Geschichte stand zweimal drin: als 'Bogen und Ende' und als
    'Geschichte:'."""
    ziel = repo.hole_szenen(spaetstand, 1)[0]
    nutzer = szene.baue_nutzertext(spaetstand, 1, "Schreib Szene 1.", ziel)
    system = szene.systemanweisung(form)
    _pruefe_ohne_dubletten(nutzer, f"szene {form} (nutzer)")
    _pruefe_ohne_dubletten(system, f"szene {form} (system)")


def test_szene_stellt_die_aufgabe_vor_das_material(spaetstand):
    """Die Aufgabe der Szene stand hinter rund 8.000 Zeichen Material.
    Jetzt steht sie direkt hinter dem Rahmen des Stuecks."""
    ziel = repo.hole_szenen(spaetstand, 1)[0]
    nutzer = szene.baue_nutzertext(spaetstand, 1, "Schreib Szene 1.", ziel)
    assert nutzer.index("Aufgabe dieser Szene") < nutzer.index("Kernthema:")


def test_szene_verspricht_keine_stimmen_ohne_zitate(spaetstand):
    """Der Kopf 'So spricht jede Figur (woertlich)' mit nichts darunter war
    ein leeres Versprechen -- gemessen am 05.09. um 23:55."""
    ziel = repo.hole_szenen(spaetstand, 1)[0]
    nutzer = szene.baue_nutzertext(spaetstand, 1, "Schreib Szene 1.", ziel)
    if szene.FIGUREN_KOPF in nutzer:
        kopf_ende = nutzer.index(szene.FIGUREN_KOPF) + len(szene.FIGUREN_KOPF)
        rest = nutzer[kopf_ende:kopf_ende + 400]
        assert '"' in rest, "Kopf verspricht woertliche Zitate, darunter steht keines"


@pytest.mark.parametrize("form", ["dialog", "monolog", "chor", "lied", "rap"])
def test_szene_systemanweisung_bleibt_unter_der_obergrenze(form):
    """23.547 Zeichen waren gemessen; Ziel des Audits sind unter 32.000 fuer
    die laengste Form (Dialog traegt 13 eigene Regeln) und unter 26.000 fuer
    die uebrigen. Regeln bleiben, Erklaerprosa und Dubletten nicht."""
    system = szene.systemanweisung(form)
    grenze = 32_000 if form == "dialog" else 26_000
    assert len(system) < grenze, f"{form}: {len(system)} Zeichen"


# --- Erkenner, Verdichter, Journal, Sprachprofil ---------------------------


def test_erkenner_nutzertext_ohne_dubletten(spaetstand):
    from interview_theater import erkenner

    neue = repo.letzte_nachrichten(spaetstand, 1, anzahl=8)
    nutzer = erkenner._baue_nutzertext(spaetstand, 1, neue, None)
    _pruefe_ohne_dubletten(nutzer, "erkenner")


def test_verdichter_nutzertext_ohne_dubletten(spaetstand):
    stand = repo.hole_arbeitsstand(spaetstand, 1)
    nutzer = verdichter.baue_nutzertext("Ein Transkript.", stand["fragen"])
    _pruefe_ohne_dubletten(nutzer, "verdichter")


def test_journal_nutzertext_ohne_dubletten(spaetstand):
    verdraengt = repo.letzte_nachrichten(spaetstand, 1, anzahl=6)
    nutzer = journal._baue_nutzertext(spaetstand, 1, verdraengt)
    _pruefe_ohne_dubletten(nutzer, "journal")


def test_sprachprofil_nutzertext_ist_das_transkript():
    assert sprachprofil.baue_nutzertext("  Ein Transkript.  ") == "Ein Transkript."


def test_kernzitate_nutzertext_ohne_dubletten(spaetstand):
    eintraege = kernzitate._eintraege(spaetstand, 1)
    stand = repo.hole_arbeitsstand(spaetstand, 1)
    nutzer = kernzitate.baue_nutzertext(stand["kernthema"], stand["kernfrage"], eintraege)
    _pruefe_ohne_dubletten(nutzer, "kernzitate")


def test_kernzitate_nennt_die_zusammenfassung_einmal_je_interview(spaetstand):
    """Befund M1: elf geprueffte Themen desselben Interviews schrieben die
    Zusammenfassung elfmal -- 7.700 Zeichen in einem 9.000-Zeichen-Prompt."""
    eintraege = kernzitate._eintraege(spaetstand, 1)
    stand = repo.hole_arbeitsstand(spaetstand, 1)
    nutzer = kernzitate.baue_nutzertext(stand["kernthema"], stand["kernfrage"], eintraege)
    zusammenfassung = eintraege[0]["zusammenfassung"]
    assert zusammenfassung
    assert nutzer.count(zusammenfassung) == 1


def test_schaerfung_nennt_die_zusammenfassung_einmal_je_interview(spaetstand):
    eintraege = schaerfung._eintraege(spaetstand, 1)
    nutzer = schaerfung.baue_nutzertext(spaetstand, 1, eintraege)
    zusammenfassung = eintraege[0]["zusammenfassung"]
    assert zusammenfassung
    assert nutzer.count(zusammenfassung) == 1


def test_schaerfung_nutzertext_ohne_dubletten(spaetstand):
    eintraege = schaerfung._eintraege(spaetstand, 1)
    nutzer = schaerfung.baue_nutzertext(spaetstand, 1, eintraege)
    _pruefe_ohne_dubletten(nutzer, "schaerfung")


def test_szenenfolge_nutzertext_ohne_dubletten(spaetstand):
    nutzer = szenenfolge.baue_nutzertext(spaetstand, 1, 4)
    _pruefe_ohne_dubletten(nutzer, "szenenfolge")


def test_geschichte_nutzertext_ohne_dubletten(spaetstand):
    nutzer = szenenfolge.baue_nutzertext_geschichte(spaetstand, 1)
    _pruefe_ohne_dubletten(nutzer, "geschichte")


# --- Das Journal im Prompt -------------------------------------------------


def test_journalblock_dedupliziert_und_kuerzt(spaetstand, einst):
    """Vier gleiche 'Szene 1 geschrieben'-Zeilen wurden zu einer, und mehr
    als JOURNAL_EINTRAEGE Zeilen gehen nicht in den Prompt."""
    block = kontext._baue_journal(spaetstand, 1)
    zeilen = [z for z in block.splitlines() if z.startswith("- ")]
    assert len(zeilen) <= kontext.JOURNAL_EINTRAEGE
    assert len(zeilen) == len(set(zeilen))


def test_journal_in_der_datenbank_bleibt_vollstaendig(spaetstand):
    """Gekuerzt wird die Sicht des Modells, nicht das Journal: dort steht,
    was die Gruppe entschieden hat, und es wird nur angehaengt (AGENTS.md)."""
    assert len(repo.journal(spaetstand, 1)) == 11


# --- Die konfigurierbare Grenze --------------------------------------------


def test_zeichengrenze_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_PROMPT_ZEICHEN", "9000")
    assert kontext.zeichengrenze() == 9000


def test_zeichengrenze_faellt_bei_unsinn_auf_die_vorgabe(monkeypatch):
    """Ein Tippfehler in einer Umgebungsvariable darf am Workshoptag nicht
    den Bot stumm schalten."""
    monkeypatch.setenv("IT_PROMPT_ZEICHEN", "keine Zahl")
    assert kontext.zeichengrenze() == kontext.ZEICHEN_GRENZE_VORGABE
    monkeypatch.setenv("IT_PROMPT_ZEICHEN", "12")
    assert kontext.zeichengrenze() == kontext.ZEICHEN_GRENZE_VORGABE


def test_engere_grenze_kuerzt_mehr(spaetstand, einst, monkeypatch):
    """Die Grenze wirkt wirklich -- nicht nur als Zahl in der Doku."""
    ausloeser = [repo.hole_nachricht(spaetstand, 1, 499)]
    weit = kontext.baue(spaetstand, 1, ausloeser, einst)
    monkeypatch.setenv("IT_PROMPT_ZEICHEN", "6000")
    eng = kontext.baue(spaetstand, 1, ausloeser, einst)
    assert len(eng) < len(weit)
    assert len(eng) <= 6000
