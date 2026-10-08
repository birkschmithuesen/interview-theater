"""Der EINE Hintergrund fuer Karten- und Stage-Script-Prompts (Birk
07.10.2026 ~19:40): beide holen ihn aus ``hintergrund.hintergrund_fuer_prompt``
-- die Andockstelle der Phasen-Summary (t_1bc96848).

Nachtrag Birk 08.10.2026 ~09:15: kein Rohdump mehr aus irgendeiner Phase.
Statt des Phase-5-Wortlauts steht dort jetzt ein Summary je Phase (1-5,
``phasen_summary_block``) und -- nur auf dem Kimi-Weg, dazu unten mehr --
die Verdichtungen GENAU der Interviews, aus denen die Gruppe Stellen
uebernommen hat (``interview_verdichtungen_block``)."""

import json

import pytest

from interview_theater import hintergrund, phasen_summary, repo, stagescript, szenenkarte

from test_szenenkarte import _lage, padua  # noqa: F401


# ---------------------------------------------------------------------------
# Eine Andockstelle fuer beide Prompts
# ---------------------------------------------------------------------------


def test_beide_prompts_holen_den_hintergrund_an_einer_stelle(conn, padua, monkeypatch):
    ids = _lage(conn)
    repo.setze_szenenkarte(conn, ids[0], json.dumps({"typ": "description", "worum": "W",
                                                     "punkte": ["P"], "zitate": []}))
    monkeypatch.setattr(hintergrund, "phasen_summary_block", lambda c, ch: "SUMMARY-STATT-ROHDUMP")
    karte = szenenkarte.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    stage = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    for text in (karte, stage):
        assert "SUMMARY-STATT-ROHDUMP" in text
        assert "Concert performance, post-dramatic" in text  # Format aus dem Hintergrund


def test_kein_rohdump_wenn_kein_summary_gespeichert_ist(conn, padua, monkeypatch):
    """Vorher fiel ``gespraech_block`` ohne Summary auf den vollen
    Phase-5-Wortlaut zurueck -- jetzt bleibt eine fehlende Phase einfach
    weg, nie ein Rohdump (Birk: "KEINE Chat-Rohtexte mehr")."""
    ids = _lage(conn)
    from interview_theater import szene

    monkeypatch.setattr(szene, "_p5_gespraech_text", lambda *a, **k: "ROHER-P5-WORTLAUT")
    repo.merke_nachricht(conn, 1, 900, "Gruppe", 0, "text", "Raw chat nobody summarized.",
                         repo._jetzt())
    karte = szenenkarte.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "ROHER-P5-WORTLAUT" not in karte
    assert "Raw chat nobody summarized." not in karte


# ---------------------------------------------------------------------------
# phasen_summary_block: P1..P5 in Reihenfolge, nie ein Rohdump
# ---------------------------------------------------------------------------


def test_phasen_summary_block_ist_leer_ohne_gespeicherte_summaries(conn):
    assert hintergrund.phasen_summary_block(conn, 1) == ""


def test_phasen_summary_block_traegt_p1_bis_p5_aufsteigend(conn):
    repo.speichere_phasen_summary(conn, 1, 2, "P2 summary")
    repo.speichere_phasen_summary(conn, 1, 1, "P1 summary")
    repo.speichere_phasen_summary(conn, 1, 5, "P5 summary")

    text = hintergrund.phasen_summary_block(conn, 1)

    assert text.index("P1 summary") < text.index("P2 summary") < text.index("P5 summary")


def test_phasen_summary_block_laesst_fehlende_phase_einfach_weg(conn):
    """Keine Luecken-Fuellung: eine Phase ohne Summary erscheint nicht,
    nie als Rohdump (siehe Modulnachtrag)."""
    repo.speichere_phasen_summary(conn, 1, 1, "P1 summary")
    repo.speichere_phasen_summary(conn, 1, 4, "P4 summary")

    text = hintergrund.phasen_summary_block(conn, 1)

    assert "P1 summary" in text
    assert "P4 summary" in text
    assert text.count("summary") == 2


def test_phasen_summary_block_ignoriert_phase_6_und_danach(conn):
    repo.speichere_phasen_summary(conn, 1, 5, "P5 summary")
    repo.speichere_phasen_summary(conn, 1, 6, "P6 summary")

    text = hintergrund.phasen_summary_block(conn, 1)

    assert "P5 summary" in text
    assert "P6 summary" not in text


# ---------------------------------------------------------------------------
# interview_verdichtungen_block: nur angenommene Interviews, dedupliziert,
# nie ein Name, nie das Zitat selbst (das steht in der nummerierten Liste)
# ---------------------------------------------------------------------------


def test_interview_verdichtungen_block_ist_leer_ohne_uebernahme(conn):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Summary text.", [
        {"thema": "Thema A", "beleg_zitat": "Quote.", "zitat_geprueft": 1},
    ])
    assert hintergrund.interview_verdichtungen_block(conn, 1) == ""


def test_interview_verdichtungen_block_laesst_eine_lange_zusammenfassung_ganz(conn):
    """Nachtrag Birk 08.10.2026 (Vorrang vor Punkt 2): keine Kappung --
    eine Zusammenfassung ueber 600 Zeichen bleibt vollstaendig."""
    lang = ("This interview covered many themes in depth. " * 15).strip()
    assert len(lang) > 600
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, "Transcript.")
    verdichtung_id = repo.speichere_verdichtung(conn, 1, kopf_id, lang, [
        {"thema": "Thema A", "beleg_zitat": "Quote.", "zitat_geprueft": 1},
    ])
    themen_id = conn.execute(
        "SELECT id FROM verdichtung_thema WHERE verdichtung_id = ?", (verdichtung_id,)
    ).fetchone()[0]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.lege_schaerfung_an(conn, 1, [{"verdichtung_thema_id": themen_id, "szene_id": szene_id}])
    schaerfung_id = repo.schaerfungen(conn, 1)[0]["id"]
    repo.merke_schaerfung_uebernommen(conn, schaerfung_id)

    text = hintergrund.interview_verdichtungen_block(conn, 1)

    assert lang in text


def test_interview_verdichtungen_block_traegt_nur_angenommene_interviews(conn, padua):
    _lage(conn)  # legt ein Interview mit zwei Themen und Schaerfungen an
    from interview_theater import schaerfung

    alle = repo.schaerfungen(conn, 1)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in alle])

    text = hintergrund.interview_verdichtungen_block(conn, 1)

    assert "Interview 1" in text
    assert "Casa" in text or "Odori" in text  # Themen stehen drin
    assert "Casa non sono le mura" not in text  # das Zitat selbst nicht (Hintergrund/Ton, keine Quelle)


def test_interview_verdichtungen_block_dedupliziert_je_interview(conn, padua):
    ids = _lage(conn)
    from interview_theater import schaerfung

    alle = repo.schaerfungen(conn, 1)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in alle])

    text = hintergrund.interview_verdichtungen_block(conn, 1)

    assert text.count("Interview 1") == 1


def test_interview_verdichtungen_block_nennt_nie_den_aufnahmenamen(conn, padua):
    _lage(conn)
    from interview_theater import schaerfung

    repo.setze_aufnahme_name(conn, _ersten_aufnahme_id(conn), "Giulia")
    alle = repo.schaerfungen(conn, 1)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in alle])

    text = hintergrund.interview_verdichtungen_block(conn, 1)

    assert "Giulia" not in text


def _ersten_aufnahme_id(conn) -> int:
    return conn.execute(
        "SELECT id FROM aufnahme WHERE chat_id = 1 AND klasse = 'lang' LIMIT 1"
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Datenschutz/Modellwahl: Verdichtungen sind abgeleitetes Interviewmaterial
# und gehen nicht ueber Claude -- die Einwilligung nennt sie nicht (siehe
# ``docs/entscheidung-modellwahl-2026-10-02.md``, Warntext in
# ``_TEXT_ANGEBOT_MODELLWAHL``: "your recordings and interviews stay that
# way -- no exceptions", nur woertliche Zitate sind ab Phase 5 genannt).
# ---------------------------------------------------------------------------


def test_hintergrund_fuer_prompt_traegt_verdichtungen_nur_ohne_claude(conn, padua):
    ids = _lage(conn)
    from interview_theater import schaerfung

    alle = repo.schaerfungen(conn, 1)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in alle])

    ohne_claude = hintergrund.hintergrund_fuer_prompt(conn, 1, ueber_claude=False)
    mit_claude = hintergrund.hintergrund_fuer_prompt(conn, 1, ueber_claude=True)

    assert "Interviews behind your chosen passages" in ohne_claude
    assert "Interviews behind your chosen passages" not in mit_claude


def test_hintergrund_fuer_prompt_ueber_claude_ist_vorgabe_false(conn, padua):
    """Ohne Angabe verhaelt es sich wie bisher (Kimi-Weg) -- kein Aufrufer,
    der den Parameter noch nicht kennt, verliert das Material."""
    ids = _lage(conn)
    from interview_theater import schaerfung

    alle = repo.schaerfungen(conn, 1)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in alle])

    text = hintergrund.hintergrund_fuer_prompt(conn, 1)
    assert "Interviews behind your chosen passages" in text
