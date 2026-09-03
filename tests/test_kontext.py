"""Tests fuer den Kontext-Zusammenbau (Aufgabe 9, SPEC-kontext-architektur.md
§ 6, § 7). Datengetrieben statt aufgabengetrieben: es gibt keine Phasen, nur
Bloecke, die erscheinen oder verschwinden, je nachdem, was in der DB steht.
"""

from datetime import datetime, timedelta, timezone

import pytest

from theatersoap import db, einstellungen, kontext, repo


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


def _fuelle_grosse_gruppe(conn, chat_id, anzahl_aufnahmen, anzahl_nachrichten):
    """Simuliert Sonntagnachmittag: viele fertig verdichtete Interviews und
    ein langer Gespraechsverlauf. Die Volltranskripte sind absichtlich lang,
    damit sie beim Zusammenbau tatsaechlich etwas wegzunehmen geben."""
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
