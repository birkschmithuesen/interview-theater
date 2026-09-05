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
    """Eine Pause im Fenster wird markiert.

    Seit dem 06.09.2026 reicht das Fenster hoechstens ``FENSTER_MINUTEN``
    zurueck (30) -- eine Uebernachtung liegt also nie mehr DARIN, sondern
    davor. Die Pausenzeile bleibt trotzdem noetig: das Fenster kann eine
    Kaffeepause enthalten, und die Uhrzeit soll sichtbar sein. Geprueft wird
    deshalb die Funktion selbst, nicht mehr ein 18-Stunden-Fenster.
    """
    assert kontext._pausenzeile(_iso(0), _iso(18 * 60)) == "[Pause: 18 Stunden]"
    assert kontext._pausenzeile(_iso(0), _iso(65)) == "[Pause: 1 Stunde]"


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

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert kontext.schaetze(prompt) <= kontext.REISSLEINE
    assert ausloeser_text in prompt
    # Seit dem 06.09.2026 beschneidet nicht mehr erst die Kuerzung, sondern
    # schon der Fensterbau: hoechstens FENSTER_NACHRICHTEN Nachrichten und
    # hoechstens FENSTER_MINUTEN zurueck. Von 600 Beitraegen bleibt damit ein
    # Bruchteil -- und der Ausloeser bleibt in jedem Fall stehen.
    verbliebene_fensterzeilen = prompt.count("Ein laengerer Gespraechsbeitrag")
    assert verbliebene_fensterzeilen <= kontext.FENSTER_NACHRICHTEN
    assert verbliebene_fensterzeilen < 600


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


def test_wortlaut_fuegt_die_teile_eines_interviews_zusammen(conn, einst):
    """§ 10.6: je Interview EIN Transkript, die Teile in Reihenfolge durch
    eine Leerzeile getrennt -- kein Block je Sprachnachricht. Ein Interview
    aus fuenf Sprachnachrichten ist ein Gespraech; als fuenf Bloecke gelesen
    zerfiele es genau dort, wo es interessant wird."""
    _setze_wortlaut(conn, 1, "*")
    kopf = repo.lege_interview_an(conn, 1)
    for i, text in enumerate(["Ich bin 1998 gekommen.", "Der Koffer stand im Flur."]):
        teil = repo.lege_aufnahme_an(conn, 1, 510 + i, "teil", "sprache", teil_von=kopf)
        repo.setze_transkript(conn, teil, text)
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steht im Interview?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert prompt.count("(Volltranskript)") == 1
    assert "Ich bin 1998 gekommen.\n\nDer Koffer stand im Flur." in prompt


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
# Verdichtungen: der Block, an dem ab Phase 3 alles Weitere haengt
# ---------------------------------------------------------------------------


def _verdichtetes_interview(conn, name="Maria"):
    """Ein fertig verdichtetes Interview: Aufnahme, Zusammenfassung, zwei
    Kernthemen -- eines mit geprueftem Belegzitat, eines ohne."""
    repo.merke_nachricht(conn, 1, 90, "Ada", 0, "sprache", None, _iso(0))
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 90, "lang", "sprache", "/tmp/a.ogg", 300)
    repo.setze_aufnahme_name(conn, aufnahme_id, name)
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id,
        "Maria erzaehlt von der Ankunft 1998 und vom ersten Winter.",
        [
            {"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer",
             "zitat_geprueft": 1},
            {"thema": "Arbeit", "beleg_zitat": None, "zitat_geprueft": 0},
        ],
    )
    return aufnahme_id


def test_verdichtungen_stehen_ab_der_ersten_fertigen_im_prompt(conn, einst):
    """Brief-Punkt (3), geprueft statt angenommen: sobald eine Verdichtung
    fertig ist, stehen Zusammenfassung UND Kernthemen mit ihren Belegzitaten
    im Gespraechs-Prompt -- unabhaengig von der Phase, weil der Block
    datengetrieben ist. Ohne das arbeitet die Gruppe ab Phase 4 an einem
    Material, das der Bot gar nicht sieht."""
    _verdichtetes_interview(conn)
    phasen.setze(conn, 1, 3, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steckt da drin?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Verdichtungen:" in prompt
    assert "Interview 1: Maria erzaehlt von der Ankunft 1998" in prompt
    assert '- Ankommen: "Ich hatte nur einen Koffer"' in prompt
    assert "- Arbeit" in prompt


def test_verdichtungen_stehen_bis_einschliesslich_phase_drei(conn, einst):
    """Bis Phase 3 haengt der Block an den Daten, nicht an der Phase: dort
    wird aufgenommen und ausgewertet, und die Verdichtung gehoert in den
    Chat.

    Ab 4 wird erfunden -- das ist der eigene Test
    ``test_in_vier_und_fuenf_gibt_es_weder_material_noch_kernpaket``."""
    _verdichtetes_interview(conn)
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(1))]

    for nummer in (1, 2, 3):
        phasen.setze(conn, 1, nummer, "befehl")
        prompt = kontext.baue(conn, 1, ausloeser, einst)
        assert '"Ich hatte nur einen Koffer"' in prompt, nummer


# ---------------------------------------------------------------------------
# Phase (Brief A4/A3): Phasenblock, Angebot, weiches Loeschen
# ---------------------------------------------------------------------------


def test_gesetzte_phase_steht_am_anfang_des_arbeitsstands(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    phasen.setze(conn, 1, 5, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    arbeitsstand = prompt.split("Arbeitsstand:\n", 1)[1]
    assert arbeitsstand.startswith("Aktuelle Phase: 5 · Geschichte")


def test_die_frageliste_steht_im_arbeitsstand(conn, einst):
    """Das neue Feld aus Phase 2: die Fragen gehen in den Prompt wie die
    Begriffe -- datengetrieben, also nur, wenn es sie gibt."""
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    assert "Fragen: Was war in deinem Koffer?" in kontext.baue(conn, 1, ausloeser, einst)


def test_ohne_gesetzte_phase_kein_phasenblock(conn, einst):
    """Datengetrieben wie jeder andere Block: ein NULL-Feld ist kein Wissen,
    ueber das der Prompt berichten muesste."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    assert "Aktuelle Phase" not in kontext.baue(conn, 1, ausloeser, einst)


def test_hinweisblock_fragt_nach_der_moeglichen_phase_genau_einmal(conn, einst):
    """Der Bot soll EINMAL fragen, nicht in jedem Zug erneut -- sonst wird aus
    einer Frage Draengeln (arbeitsstand.phase_angeboten)."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    erster = kontext.baue(conn, 1, ausloeser, einst)
    zweiter = kontext.baue(conn, 1, ausloeser, einst)

    assert "Materiallage wuerde Phase 2 · Fragen hergeben" in erster
    assert "Materiallage wuerde" not in zweiter
    assert repo.hole_phase_angeboten(conn, 1) == 2


def test_der_hinweisblock_sagt_dass_der_bot_nicht_selbst_umschaltet(conn, einst):
    """Die Entscheidung vom 05.09.2026 im Prompt: der Datenstand ist eine
    Frage, keine Erlaubnis. Der Bot fragt, die Gruppe antwortet, der Erkenner
    setzt -- niemand schaltet still."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Du schaltest nicht selbst um" in prompt


def _interview(conn, name="Interview 1"):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 900, "lang", "text")
    repo.setze_aufnahme_name(conn, aufnahme_id, name)
    repo.setze_transkript(conn, aufnahme_id, "Pola: Halt so, ne?")
    return aufnahme_id


def test_figuren_ohne_quelle_bringen_die_frage_in_den_prompt(conn, einst):
    """05.09.2026: der Bot fragt im Fluss, aus welchem Interview eine Figur
    spricht -- die Antwort loest den Sprachprofil-Aufruf aus, und ohne ihn
    klingen in einer Szene alle Figuren gleich.

    Seit dem Umbau vom 05.09.2026 nachts erst **ab der Schaerfung** (6): in
    4 und 5 wird erfunden, und die Interviewfrage waere dort die Ruecklenkung
    aufs Material, die der Umbau vermeidet."""
    _interview(conn)
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")
    phasen.setze(conn, 1, 6, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "fehlt noch das Interview" in prompt
    assert "Pola" in prompt


def test_die_figurenfrage_verschwindet_mit_der_zuordnung(conn, einst):
    """Kein Merkposten wie bei der Phasenfrage: hier sagen die Daten selbst,
    ob die Frage noch offen ist."""
    aufnahme_id = _interview(conn)
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")
    repo.setze_figur_quelle(conn, repo.hole_figur(conn, 1, "Pola")["id"], aufnahme_id)
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    assert "fehlt noch das Interview" not in kontext.baue(conn, 1, ausloeser, einst)


def test_ohne_interview_wird_nicht_nach_der_quelle_gefragt(conn, einst):
    """Eine unbeantwortbare Frage ist keine: ohne Material gibt es nichts
    zuzuordnen."""
    repo.setze_figur(conn, 1, "Pola", "war auf jeder Demo")
    phasen.setze(conn, 1, 6, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    assert "fehlt noch das Interview" not in kontext.baue(conn, 1, ausloeser, einst)


def test_setting_und_figuren_fuehren_zur_geschichte(conn, einst):
    """Steht das Setting und ist die Figurenliste fixiert, ist die naechste
    Station eindeutig die Geschichte (5)."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_figur(conn, 1, "Elif", "Nachbarin")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T20:00:00")
    phasen.setze(conn, 1, 4, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Materiallage wuerde Phase 5 · Geschichte hergeben" in prompt
    assert repo.hole_phase_angeboten(conn, 1) == 5


def test_gefragt_wird_immer_nach_der_hoechsten_moeglichen_phase(conn, einst):
    """Stehen mehrere Stufen offen, nennt der Block die hoechste: die Gruppe
    kann in ihrer Antwort jede andere nennen, und der Erkenner nimmt sie."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.")
    repo.lege_szene_an(conn, 1, 1, "Am Kiosk", "sie treffen sich", None)
    repo.setze_figur(conn, 1, "Maria", "Naeherin")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T20:00:00")
    phasen.setze(conn, 1, 4, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]

    assert "Materiallage wuerde Phase 7 · Szenentexte hergeben" in kontext.baue(
        conn, 1, ausloeser, einst
    )


def test_neue_stufe_wird_erneut_erfragt(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Wie weiter?", _iso(0))]
    kontext.baue(conn, 1, ausloeser, einst)  # fragt nach 2

    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")

    assert "Materiallage wuerde Phase 3" in kontext.baue(conn, 1, ausloeser, einst)


def test_ohne_naechste_phase_kein_hinweisblock(conn, einst):
    ausloeser = [_sende(conn, 1, 1, "Ada", "Womit fangen wir an?", _iso(0))]

    assert "Materiallage wuerde" not in kontext.baue(conn, 1, ausloeser, einst)


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


# ---------------------------------------------------------------------------
# Der Kontext-Filter je Phase und das Kernpaket (05.09.2026 abends)
# ---------------------------------------------------------------------------


def _kernpaket_lage(conn):
    """Kernthema, Kernfrage, ein gefiltertes Thema, ein Kernzitat, eine Figur
    mit Sprachprofil -- und ein zweites Interview, das NICHT dazugehoert."""
    aufnahme_id = _verdichtetes_interview(conn)
    repo.merke_nachricht(conn, 1, 91, "Ada", 0, "sprache", None, _iso(0))
    fremd_id = repo.lege_aufnahme_an(conn, 1, 91, "lang", "sprache", "/tmp/b.ogg", 300)
    repo.setze_aufnahme_name(conn, fremd_id, "Pal")
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
        t for t in repo.gepruefte_themen(conn, 1) if t["thema"] == "Ankommen"
    )
    repo.markiere_themen_zum_kernthema(conn, 1, [passend["id"]])
    repo.ersetze_kernzitate(
        conn, 1,
        [{"verdichtung_thema_id": passend["id"], "aufnahme_id": aufnahme_id,
          "zitat": "Ich hatte nur einen Koffer",
          "begruendung": "das Wenige ist der Einsatz"}],
    )
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    figur = repo.hole_figur(conn, 1, "Mira")
    repo.setze_figur_quelle(conn, figur["id"], aufnahme_id)
    repo.setze_sprachprofil(conn, figur["id"], "Kurze Saetze, bricht ab", ["Halt."])
    return aufnahme_id


def test_in_vier_und_fuenf_gibt_es_weder_material_noch_kernpaket(conn, einst):
    """**Der Kern des Umbaus vom 05.09.2026 nachts.** In Setting & Figuren (4)
    und Geschichte (5) erfindet die Gruppe -- der Bot sieht dort keine
    Verdichtung, kein Transkript und auch kein Kernpaket. Sonst schlaegt er
    nicht Erfundenes vor, sondern referiert das Material."""
    _kernpaket_lage(conn)
    repo.setze_wortlaut_modus(conn, 1, "*")  # selbst mit Wortlaut-Schalter
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(1))]

    for nummer in (4, 5):
        phasen.setze(conn, 1, nummer, "befehl")
        prompt = kontext.baue(conn, 1, ausloeser, einst)
        assert "Verdichtungen:" not in prompt, nummer
        assert "Volltranskripte:" not in prompt, nummer
        assert kontext.KERNPAKET_KOPF not in prompt, nummer
        # Und auch kein Zitat ueber einen anderen Weg.
        assert "Ich hatte nur einen Koffer" not in prompt, nummer


def test_in_vier_und_fuenf_stehen_begriffe_und_fragen_im_prompt(conn, einst):
    """Was in den Erfindungsphasen erlaubt IST: Begriffe, Fragen, Rahmen und
    der bisherige Arbeitsstand -- daraus schlaegt der Bot vor."""
    _kernpaket_lage(conn)
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    phasen.setze(conn, 1, 4, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Begriffe: Koffer, Bahnhof" in prompt
    assert "Fragen: Was war in deinem Koffer?" in prompt


def test_das_kernpaket_traegt_nur_die_gefilterten_verdichtungen(conn, einst):
    """Die Verdichtungen fliegen nicht raus, sie werden gefiltert: was zum
    Kernthema markiert ist, steht da -- alles andere nicht."""
    _kernpaket_lage(conn)
    phasen.setze(conn, 1, 7, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Ankommen" in prompt
    assert "Maria erzaehlt von der Ankunft 1998" in prompt
    # Die nicht passende Verdichtung fehlt vollstaendig.
    assert "Fahrten am Wochenende" not in prompt
    assert "Pal erzaehlt von seinen Wochenendfahrten" not in prompt
    # Kernfrage, Kernzitat mit Interview-Nummer, Figur mit Sprachprofil.
    assert "Kernfrage:" in prompt
    assert 'Interview 1: "Ich hatte nur einen Koffer"' in prompt
    assert "Mira" in prompt
    assert "Kurze Saetze, bricht ab" in prompt


def test_ab_der_schaerfung_traegt_das_kernpaket(conn, einst):
    _kernpaket_lage(conn)
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(1))]

    for nummer in (6, 7, 8):
        phasen.setze(conn, 1, nummer, "befehl")
        prompt = kontext.baue(conn, 1, ausloeser, einst)
        assert "Verdichtungen:" not in prompt, nummer
        assert "Volltranskripte:" not in prompt, nummer
        assert kontext.KERNPAKET_KOPF in prompt, nummer


def test_die_phasen_eins_bis_drei_bleiben_unveraendert(conn, einst):
    _kernpaket_lage(conn)
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(1))]

    for nummer in (1, 2, 3):
        phasen.setze(conn, 1, nummer, "befehl")
        prompt = kontext.baue(conn, 1, ausloeser, einst)
        assert "Verdichtungen:" in prompt, nummer
        assert kontext.KERNPAKET_KOPF not in prompt, nummer


def test_ein_ruecksprung_nach_drei_holt_das_material_zurueck(conn, einst):
    """Datengetrieben und ohne gespeicherten Zustand: geht die Gruppe zurueck
    in die Interviews, steht das Material wieder da."""
    _kernpaket_lage(conn)
    phasen.setze(conn, 1, 3, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Verdichtungen:" in prompt
