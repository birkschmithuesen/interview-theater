"""Tests fuer den Kontext-Zusammenbau (Aufgabe 9, SPEC-kontext-architektur.md
§ 6, § 7). Datengetrieben statt aufgabengetrieben: es gibt keine Phasen, nur
Bloecke, die erscheinen oder verschwinden, je nachdem, was in der DB steht.
"""

from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import db, einstellungen, kontext, phasen, repo


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def _sende(conn, chat_id, message_id, absender, text, gesendet_am, ist_bot=0, typ="text"):
    """Legt eine Nachricht an und liefert die gespeicherte Zeile zurueck --
    Testhelfer, kein Teil der Produktionsschnittstelle."""
    repo.merke_nachricht(conn, chat_id, message_id, absender, ist_bot, typ, text, gesendet_am)
    return repo.hole_nachricht(conn, chat_id, message_id)


BASIS = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)


def _iso(versatz_minuten: int) -> str:
    return (BASIS + timedelta(minutes=versatz_minuten)).isoformat(timespec="seconds")


def test_schaetzung_ist_zeichen_durch_drei():
    assert kontext.schaetze("abcdef") == 2
    assert kontext.schaetze("abcdefg") == 2  # 7 // 3, abgerundet
    assert kontext.schaetze("") == 0
    assert kontext.schaetze("a" * 9000) == 3000


def test_leere_bloecke_fehlen_im_prompt(conn, einst):
    """Samstagvormittag: nichts in der DB ausser der ausloesenden Nachricht --
    also enthaelt der Prompt nichts als die ausloesende Nachricht."""
    ausloeser = [_sende(conn, 1, 1, "Ada", "Womit fangen wir an?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Verdichtungen" not in prompt
    assert "Arbeitsstand" not in prompt
    assert "Journal" not in prompt
    assert "Volltranskripte" not in prompt
    assert "Womit fangen wir an?" in prompt


def test_arbeitsstand_erscheint_sobald_er_existiert(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Ankommen, Fremdheit, Heimat")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie geht's weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Arbeitsstand" in prompt
    assert "Ankommen, Fremdheit, Heimat" in prompt


def test_pausenmarkierung_ab_einer_stunde(conn, einst):
    """18 Stunden zwischen zwei Nachrichten im Fenster -- Uebernachtung."""
    _sende(conn, 1, 1, "Ada", "Bis morgen dann.", _iso(0))
    _sende(conn, 1, 2, "Ben", "Guten Morgen!", _iso(18 * 60))
    ausloeser = [_sende(conn, 1, 3, "Ada", "Wo waren wir stehen geblieben?", _iso(18 * 60 + 1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "[Pause: 18 Stunden]" in prompt


def test_keine_pausenmarkierung_bei_kurzem_abstand(conn, einst):
    """30 Minuten Abstand -- eine Mittagspause reicht nicht fuer die Marke."""
    _sende(conn, 1, 1, "Ada", "Kurze Frage.", _iso(0))
    _sende(conn, 1, 2, "Ben", "Kurze Antwort.", _iso(30))
    ausloeser = [_sende(conn, 1, 3, "Ada", "Und jetzt?", _iso(31))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "[Pause:" not in prompt


def _setze_wortlaut(conn, chat_id, modus):
    """Setzt gruppe.wortlaut_modus direkt per SQL -- der Slash-Befehl
    /wortlaut, der das im Betrieb setzt, gehoert zu einer spaeteren Aufgabe
    (befehle.py); das Feld selbst existiert aber schon seit Aufgabe 1."""
    conn.execute("UPDATE gruppe SET wortlaut_modus = ? WHERE chat_id = ?", (modus, chat_id))
    conn.commit()


def _fuelle_grosse_gruppe(conn, chat_id, anzahl_aufnahmen, anzahl_nachrichten):
    """Simuliert Sonntagnachmittag: viele fertig verdichtete Interviews und
    ein langer Gespraechsverlauf, /wortlaut auf 'alle' gestellt (die Gruppe
    wollte den Originalton nachlesen). Die Volltranskripte sind absichtlich
    lang, damit sie beim Zusammenbau tatsaechlich etwas wegzunehmen geben."""
    _setze_wortlaut(conn, chat_id, "*")

    transkript = (
        "Ich erinnere mich noch genau an den Tag, an dem alles anders wurde. "
        "Wir sassen zusammen und niemand hat etwas gesagt, bis meine Schwester "
        "anfing zu erzaehlen, was wirklich passiert war. "
    ) * 20  # ~ 2500 Zeichen

    for i in range(anzahl_aufnahmen):
        aid = repo.lege_aufnahme_an(conn, chat_id, 10_000 + i, "lang", "sprache")
        repo.setze_transkript(conn, aid, transkript)
        repo.setze_status(conn, aid, "fertig")
        repo.speichere_verdichtung(
            conn, chat_id, aid,
            f"Zusammenfassung von Interview {i}: eine ausfuehrliche Schilderung "
            "eines familiaeren Bruchs, erzaehlt aus der Sicht der juengeren "
            "Schwester, mit vielen Details zu Ort und Stimmung im Raum." * 2,
            [
                {"thema": "Bruch", "beleg_zitat": "alles anders wurde", "zitat_geprueft": 1},
                {"thema": "Schweigen", "beleg_zitat": "niemand hat etwas gesagt", "zitat_geprueft": 1},
                {"thema": "Erzaehlen", "beleg_zitat": "anfing zu erzaehlen", "zitat_geprueft": 1},
            ],
        )

    for i in range(anzahl_nachrichten):
        _sende(conn, chat_id, i + 1, "Ada" if i % 2 == 0 else "Ben",
               f"Nachricht Nummer {i} im laufenden Gespraech ueber die Szene.",
               _iso(i))


def test_kuerzung_haelt_die_reissleine_ein(conn, einst):
    """Sonntagnachmittag: 40 verdichtete Interviews, 400 Chatnachrichten --
    der Bot muss trotzdem antworten koennen, ohne die Reissleine zu reissen."""
    _fuelle_grosse_gruppe(conn, 1, anzahl_aufnahmen=40, anzahl_nachrichten=400)
    ausloeser = [_sende(conn, 1, 999_999, "Ada", "Was ist jetzt unser Kernthema?",
                         _iso(400 + 1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert kontext.schaetze(prompt) <= kontext.REISSLEINE
    vorfaelle = conn.execute(
        "SELECT count(*) FROM vorfall WHERE art = 'kuerzung'"
    ).fetchone()[0]
    assert vorfaelle >= 1, "die Kuerzung muss einen Vorfall hinterlassen"


def test_notbremse_enthaelt_immer_die_ausloesende_nachricht(conn, einst):
    """Selbst unter derselben Last darf die ausloesende Nachricht nie
    wegfallen -- sonst haette der Bot nichts mehr, worauf er antwortet."""
    _fuelle_grosse_gruppe(conn, 1, anzahl_aufnahmen=40, anzahl_nachrichten=400)
    ausloeser_text = "Ganz konkret: was ist jetzt unser Hauptkonflikt?"
    ausloeser = [_sende(conn, 1, 999_999, "Ada", ausloeser_text, _iso(400 + 1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert ausloeser_text in prompt


def test_kuerzung_bei_grossem_fenster_ohne_transkripte_erhaelt_ausloeser(conn, einst):
    """Schritt 2 der Kuerzung (§ 7.2) muss auch dann greifen, wenn es gar
    keine Transkripte gibt -- ein sehr langer Gespraechsverlauf reisst das
    Ziel ganz allein. Anders als test_kuerzung_haelt_die_reissleine_ein (wo
    schon Schritt 1 reicht) muss hier tatsaechlich das Fenster von vorn
    beschnitten werden, und die ausloesende Nachricht darf das nicht
    mitreissen."""
    for i in range(600):
        _sende(
            conn, 1, i + 1, "Ada" if i % 2 == 0 else "Ben",
            "Ein laengerer Gespraechsbeitrag mitten im Probenalltag, der "
            "im kurzen Fenster ordentlich Platz braucht und nicht kurz ist.",
            _iso(i),
        )
    ausloeser_text = "Und worauf einigen wir uns jetzt fuer die naechste Szene?"
    ausloeser = [_sende(conn, 1, 999_999, "Ada", ausloeser_text, _iso(601))]

    ungekuerzte_fensterzeilen = len(kontext._baue_fenster_eintraege(conn, 1, ausloeser))
    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert kontext.schaetze(prompt) <= kontext.REISSLEINE
    assert ausloeser_text in prompt
    verbliebene_fensterzeilen = prompt.count("Ein laengerer Gespraechsbeitrag")
    assert verbliebene_fensterzeilen < ungekuerzte_fensterzeilen, (
        "das Fenster muss tatsaechlich beschnitten worden sein"
    )
    vorfaelle = conn.execute(
        "SELECT count(*) FROM vorfall WHERE art = 'kuerzung'"
    ).fetchone()[0]
    assert vorfaelle >= 1


def test_ohne_wortlaut_schalter_fehlen_die_transkripte(conn, einst):
    """SPEC § 6.2 Block 3: ohne gesetzten Schalter bleiben Transkripte aussen
    vor, auch wenn welche existieren -- sonst waeren sie ab Samstagmittag
    Dauerlast, die jede Antwort unschaerfer macht."""
    aid = repo.lege_aufnahme_an(conn, 1, 500, "lang", "sprache")
    repo.setze_transkript(conn, aid, "Ein sehr langes woertliches Interview ueber die Kindheit.")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steht im Interview?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Volltranskripte" not in prompt
    assert "Kindheit" not in prompt


def test_wortlaut_stern_zeigt_nur_lange_nicht_kurze_aufnahmen(conn, einst):
    """`/wortlaut *` holt alle Volltranskripte -- aber nur die von Aufnahmen
    der Klasse 'lang' (echtes Interview-Material, SPEC § 10.1). Kurze
    Gespraechsbeitraege haben zwar auch ein Transkript in der DB, stehen aber
    schon im Fenster; sie dort zusaetzlich als Material zu zeigen wuerde den
    Inhalt verdoppeln und einen Zuruf faelschlich zu Material erklaeren."""
    _setze_wortlaut(conn, 1, "*")
    lang = repo.lege_aufnahme_an(conn, 1, 500, "lang", "sprache")
    repo.setze_transkript(conn, lang, "MARKIERUNG-LANGES-INTERVIEW ueber die Kindheit.")
    kurz = repo.lege_aufnahme_an(conn, 1, 501, "kurz", "sprache")
    repo.setze_transkript(conn, kurz, "MARKIERUNG-KURZER-ZURUF geht schon los!")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steht im Interview?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Volltranskripte" in prompt
    assert "MARKIERUNG-LANGES-INTERVIEW" in prompt
    assert "MARKIERUNG-KURZER-ZURUF" not in prompt


# ---------------------------------------------------------------------------
# Szenen (SPEC § 6.2 Block 4 und Block 5)
# ---------------------------------------------------------------------------


def test_ohne_szenen_gibt_es_keine_szenenbloecke(conn, einst):
    """Datengetrieben wie alles andere: solange die Gruppe keine Szene hat,
    steht im Prompt kein Wort davon -- kein Zustand, der ihr sagt, sie
    muesste jetzt Szenen machen."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Arbeitsstand" in prompt
    assert "Szene" not in prompt


def test_szenenliste_steht_im_arbeitsstand(conn, einst):
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt am Bahnhof an", "MARIA: Da.")
    repo.lege_szene_an(conn, 1, 2, "Der Koffer", "Elif packt aus", "ELIF: Zu.")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Szene 1: Ankunft - Maria kommt am Bahnhof an" in prompt
    assert "Szene 2: Der Koffer - Elif packt aus" in prompt


def test_nur_die_zuletzt_geaenderte_szene_geht_im_volltext_mit(conn, einst):
    """Block 5 (SPEC § 6.2): sechs Szenen à 800 Woerter waeren 6.000 Token
    Dauerlast. Nur die eine, an der zuletzt gearbeitet wurde, geht mit."""
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: ERSTE-SZENE.")
    repo.lege_szene_an(conn, 1, 2, "Der Koffer", "Elif packt aus", "ELIF: ZWEITE-SZENE.")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Aktuelle Szene" in prompt
    assert "ZWEITE-SZENE" in prompt
    assert "ERSTE-SZENE" not in prompt


def test_ueberarbeiten_holt_eine_aeltere_szene_zurueck_in_den_prompt(conn, einst):
    """Kein gespeicherter Zustand: springt die Gruppe zu Szene 1 zurueck und
    ueberarbeitet sie, folgt der Prompt automatisch (geaendert_am)."""
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: ALT.")
    repo.lege_szene_an(conn, 1, 2, "Der Koffer", "Elif packt aus", "ELIF: ZWEITE-SZENE.")
    erste = repo.hole_szenen(conn, 1)[0]
    repo.aktualisiere_szene(conn, erste["id"], "Ankunft", "Maria kommt an", "MARIA: NEU.")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "MARIA: NEU." in prompt
    assert "ZWEITE-SZENE" not in prompt


# ---------------------------------------------------------------------------
# Phase (Brief A4/A3): Phasenblock, Angebot, weiches Loeschen
# ---------------------------------------------------------------------------


def test_gesetzte_phase_steht_am_anfang_des_arbeitsstands(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    phasen.setze(conn, 1, 5, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    arbeitsstand = prompt.split("Arbeitsstand:\n", 1)[1]
    assert arbeitsstand.startswith("Aktuelle Phase: 5 · Figuren entwickeln")


def test_ohne_gesetzte_phase_kein_phasenblock(conn, einst):
    """Datengetrieben wie jeder andere Block: ein NULL-Feld ist kein Wissen,
    ueber das der Prompt berichten muesste."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    assert "Aktuelle Phase" not in kontext.baue(conn, 1, ausloeser, einst)


def test_hinweisblock_bietet_die_moegliche_phase_an_genau_einmal(conn, einst):
    """Der Bot soll den Wechsel EINMAL anbieten, nicht in jedem Zug erneut --
    sonst wird aus einem Angebot Draengeln (arbeitsstand.phase_angeboten)."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    erster = kontext.baue(conn, 1, ausloeser, einst)
    zweiter = kontext.baue(conn, 1, ausloeser, einst)

    assert "Materiallage erlaubt Phase 4 · Hauptkonflikt" in erster
    assert "Materiallage erlaubt" not in zweiter
    assert repo.hole_phase_angeboten(conn, 1) == 4


def test_neue_stufe_wird_erneut_angeboten(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]
    kontext.baue(conn, 1, ausloeser, einst)  # bietet 4 an

    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "bleiben gegen gehen")

    assert "Materiallage erlaubt Phase 5" in kontext.baue(conn, 1, ausloeser, einst)


def test_ohne_naechste_phase_kein_hinweisblock(conn, einst):
    ausloeser = [_sende(conn, 1, 1, "Ada", "Womit fangen wir an?", _iso(0))]

    assert "Materiallage erlaubt" not in kontext.baue(conn, 1, ausloeser, einst)


def test_entfernte_figuren_szenen_und_journalzeilen_fehlen_im_prompt(conn, einst):
    """Weiches Loeschen (N3) wirkt ueberall dort, wo repo liest -- der Prompt
    ist der wichtigste dieser Orte: was die Gruppe zurueckgenommen hat, darf
    der Bot nicht weiter im Mund fuehren."""
    repo.setze_figur(conn, 1, "Peter", "Nachbar")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.lege_szene_an(conn, 1, 1, "Ankunft", "Maria kommt an", "MARIA: HIERBLEIBEN.")
    repo.lege_szene_an(conn, 1, 2, "Abschied", "Peter geht", "PETER: WEGDAMIT.")
    repo.schreibe_journal(conn, 1, "verworfen", "Kindheitsfragen als Einstieg", "erkenner")
    repo.schreibe_journal(conn, 1, "entschieden", "Wir spielen im Hof", "erkenner")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    repo.entferne_figur(conn, 1, "Peter")
    repo.entferne_szene(conn, 1, 2)
    repo.entferne_journal(conn, 1, "Kindheitsfragen")

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Maria" in prompt and "Peter" not in prompt
    assert "Ankunft" in prompt and "Abschied" not in prompt
    assert "Wir spielen im Hof" in prompt and "Kindheitsfragen" not in prompt
    assert "WEGDAMIT" not in prompt
