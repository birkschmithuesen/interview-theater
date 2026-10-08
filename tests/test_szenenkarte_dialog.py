"""Der "No, change"-Dialog einer Szenenkarte (Birk 08.10.2026 ~09:35,
Nachtrag, Vorrang -- ersetzt den alten Weg "No, change" -> erwarte_regienotiz
-> naechste Nachricht ist automatisch die Aenderungsnotiz).

"No, change" markiert die Karte als im Dialog (``karte_dialog_am``); der
Chat bleibt ab da ein gewoehnliches Gespraech mit der Karte im Kontext
(``dialog_kontextblock``). Erkennt das Gespraechsmodell eine klare
Aenderung, haengt ``VORSCHLAG KARTE AENDERUNG:`` -- derselbe Marker-
Mechanismus wie ueberall sonst (``vorschlag.py``) -- "Update the card" /
"Keep the card" an (``knoepfe.basis.sende_mit_speicherleiste``)."""

import pytest

from interview_theater import phasen, repo, szenenkarte, workshop
from interview_theater.knoepfe.texte import ART_KARTE_UPDATE

from test_szenenkarte import LLM, LLMMitFragen, TG, _karte1, padua  # noqa: F401


def test_starte_dialog_setzt_flag_statt_regienotiz(conn, einst, padua):
    from interview_theater import szenenfolge

    _karte1(conn, einst, LLM())
    tg = TG()
    antwort = szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    assert antwort == "Dialog started"
    assert tg.texte[-1] == "Let's talk about card 1. What would you change?"
    assert szenenkarte.dialog_aktive_nummer(conn, 1) == 1
    assert szenenfolge.nimm_regienotiz(1) is None


def test_starte_dialog_veraltete_karte_wirkungslos(conn, einst, padua):
    _karte1(conn, einst, LLM())
    tg = TG()
    antwort = szenenkarte.starte_dialog(conn, tg, einst, 1, 99)
    assert antwort == szenenkarte.T._TEXT_NICHT_DRAN
    assert szenenkarte.dialog_aktive_nummer(conn, 1) is None


def test_dialog_kontextblock_leer_ohne_dialog(conn, einst, padua):
    _karte1(conn, einst, LLM())
    assert szenenkarte.dialog_kontextblock(conn, 1) == ""


def test_dialog_kontextblock_zeigt_karte_und_anweisung(conn, einst, padua):
    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    block = szenenkarte.dialog_kontextblock(conn, 1)
    assert "VORSCHLAG KARTE AENDERUNG" in block
    assert "do NOT rebuild the card yourself" in block
    assert "Scene card 1" in block  # die eingebettete Karte geht ueber dieselbe _T(chat_id)-Weiche


def test_kontext_baue_bindet_dialogblock_ein(conn, einst, padua):
    """Der Block haengt wirklich in ``kontext.baue`` (nicht nur isoliert
    aufrufbar) -- sonst saehe das Gespraechsmodell die Karte nie."""
    from interview_theater import kontext

    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    koerper = kontext.baue(conn, 1, [], einst)
    assert "VORSCHLAG KARTE AENDERUNG" in koerper


def test_biete_update_knopf_haengt_leiste_an_und_entfernt_marker(conn, einst, padua):
    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    message_id = szenenkarte.biete_update_knopf(
        conn, tg, einst, 1,
        "Sure, let's open with Emma.\n\nVORSCHLAG KARTE AENDERUNG:\n"
        "Emma sings first.",
        "Emma sings first.",
    )
    assert message_id
    assert [c for c, _ in tg.leisten[-1]] == ["Update the card", "Keep the card"]
    assert "VORSCHLAG" not in tg.texte[-1]
    # Der Fliesstext selbst sagt etwas anderes ("Sure, let's open
    # with Emma.") -- "Emma sings first." steht nur einmal, im
    # Block, der uebrig bleibt.
    assert tg.texte[-1].count("Emma sings first.") == 1


def test_biete_update_knopf_ohne_aktiven_dialog_keine_leiste(conn, einst, padua):
    """Ein veralteter Block (Dialog inzwischen beendet): Text ohne Knoepfe,
    kein Raten."""
    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.biete_update_knopf(conn, tg, einst, 1, "Just chatting.", "x")
    assert tg.leisten == []
    assert tg.texte[-1] == "Just chatting."


def test_neue_zusammenfassung_ersetzt_alte_leiste(conn, einst, padua):
    """Punkt 2, und Pruefung-Szenario "Hin-und-Her ueber 3 Runden mit
    Meinungswechsel": jede neue Zusammenfassung laesst die alte Leiste
    verfallen -- der Knopf steht nur an der neuesten, auch nach drei
    Runden."""
    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    szenenkarte.biete_update_knopf(conn, tg, einst, 1, "First idea.", "First idea.")
    szenenkarte.biete_update_knopf(conn, tg, einst, 1, "Second thought.", "Second thought.")
    szenenkarte.biete_update_knopf(conn, tg, einst, 1, "Actually, back to the first.",
                                   "Actually, back to the first.")
    offen = repo.offene_knoepfe(conn, 1, ART_KARTE_UPDATE)
    assert len(offen) == 1
    assert offen[0]["wert"] == "1|Actually, back to the first."


# ---------------------------------------------------------------------------
# Szenario-Tests (Pflicht, simulated-user-evaluation Paragraph 8c): die
# naheliegenden menschlichen Zuege aus dem Auftrag.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "The questions clearing",
    "let's discuss the questions",
    "parliamo delle domande",  # eine italienische Nachricht
])
def test_szenario_fragenwort_bei_offenen_fragen_bietet_klaerweg(conn, einst, padua, text):
    from interview_theater import ablauf

    _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    nachricht = {"text": text, "message_id": 4242}
    ausgefallen = ablauf._szene_hat_vorfahrt(conn, tg, LLM(), einst, 1, nachricht)
    assert ausgefallen is True
    assert [c for c, _ in tg.leisten[-1]] == ["Clear the questions"]


def test_szenario_vage_antwort_laeuft_normal_weiter(conn, einst, padua):
    """"hmm, not sure" ist weder eine Antwort auf die Fragen noch eine
    Aenderung -- der Zug faellt NICHT aus, das Gespraech geht normal
    weiter (das Modell fragt selbst nach, kein Marker, kein Knopf)."""
    from interview_theater import ablauf, knoepfe

    _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    nachricht = {"text": "hmm, not sure", "message_id": 4242}
    ausgefallen = ablauf._szene_hat_vorfahrt(conn, tg, LLM(), einst, 1, nachricht)
    assert ausgefallen is False
    # Keine Zusammenfassung ohne Marker -- kein Update-Knopf, kein Raten.
    _mid, hat_leiste = knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "Got it, can you say more about why?", e=einst,
    )
    assert hat_leiste is False
    assert tg.texte[-1] == "Got it, can you say more about why?"


def test_szenario_update_ohne_vorherige_zusammenfassung_tut_nichts_falsches(
    conn, einst, padua, monkeypatch,
):
    """"update it" als blosser Chattext (kein Knopfdruck): kein Marker, also
    auch kein automatischer Neubau -- und der Erkenner darf das ebenfalls
    nicht als text_ueberarbeiten automatisch umsetzen (Phase-6-Guard)."""
    from interview_theater import ablauf, erkenner, ueberarbeitung

    _karte1(conn, einst, LLM())
    phasen.setze(conn, 1, 6, "befehl")
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    nachricht = {"text": "update it", "message_id": 4242}
    ausgefallen = ablauf._szene_hat_vorfahrt(conn, tg, LLM(), einst, 1, nachricht)
    assert ausgefallen is False
    aufgerufen = []
    monkeypatch.setattr(ueberarbeitung, "ueberarbeite",
                        lambda *a, **k: aufgerufen.append(a))
    erkenner._starte_teil2(
        LLM(), tg, conn, einst, 1,
        [{"art": "text_ueberarbeiten", "wert": "update it"}], [],
    )
    assert aufgerufen == []


def test_aktualisiere_mit_dialog_baut_neu_bewahrt_fragen_beendet_dialog(conn, einst, padua):
    ids = _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    klm = LLM()  # liefert keine Fragen -> alte muss bewahrt werden
    antwort = szenenkarte.aktualisiere_mit_dialog(
        conn, tg, klm, einst, 1, 1, "Emma sings first.")
    assert antwort == "Card 1 is being updated"
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()
    assert "Emma sings first." in klm.aufrufe[-1]["nutzer"]
    assert szenenkarte.dialog_aktive_nummer(conn, 1) is None
    karte = szenenkarte.karte_von(repo.hole_szene(conn, ids[0]))
    assert karte["fragen"] == ["Who sings?"]
    # Die bewahrte Frage ist noch offen -- also Clear/Skip, nicht Yes/No.
    assert [c for c, _ in tg.leisten[-1]] == ["Clear the questions", "Skip questions"]


def test_behalte_karte_beendet_dialog_ohne_neubau(conn, einst, padua):
    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    antwort = szenenkarte.behalte_karte(conn, tg, einst, 1, 1)
    assert antwort == "Card 1 stays as it is"
    assert szenenkarte.dialog_aktive_nummer(conn, 1) is None
    assert [c for c, _ in tg.leisten[-1]] == ["Yes, save", "No, change"]


def test_behalte_karte_veraltete_nummer_wirkungslos(conn, einst, padua):
    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    antwort = szenenkarte.behalte_karte(conn, tg, einst, 1, 99)
    assert antwort == szenenkarte.T._TEXT_NICHT_DRAN
    assert szenenkarte.dialog_aktive_nummer(conn, 1) == 1


# ---------------------------------------------------------------------------
# Punkt 4: die Gruppe spricht im Dialog von den Fragen selbst
# ---------------------------------------------------------------------------


def test_ablauf_bietet_klaerweg_im_dialog_bei_fragenwort(conn, einst, padua):
    from interview_theater import ablauf

    _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    nachricht = {"text": "let's discuss the questions", "message_id": 999}
    ausgefallen = ablauf._szene_hat_vorfahrt(conn, tg, LLM(), einst, 1, nachricht)
    assert ausgefallen is True
    assert [c for c, _ in tg.leisten[-1]] == ["Clear the questions"]
    # Der Dialog bleibt stehen -- die Gruppe kann weiterreden statt zu klaeren.
    assert szenenkarte.dialog_aktive_nummer(conn, 1) == 1


def test_ablauf_fragenwort_ohne_offene_fragen_laesst_gespraech_normal(conn, einst, padua):
    """"The questions clearing" o.ae., aber die Karte hat gar keine offenen
    Fragen (mehr): kein Klaerweg-Angebot, der normale Zug laeuft."""
    from interview_theater import ablauf

    _karte1(conn, einst, LLM())
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    nachricht = {"text": "The questions clearing", "message_id": 999}
    ausgefallen = ablauf._szene_hat_vorfahrt(conn, tg, LLM(), einst, 1, nachricht)
    assert ausgefallen is False


def test_ablauf_fragenwort_ohne_dialog_laesst_gespraech_normal(conn, einst, padua):
    """Ausserhalb eines Dialogs (z. B. normales Gespraech) wirkt das
    Fragenwort-Muster nicht -- es ist an den Dialog gebunden."""
    from interview_theater import ablauf

    _karte1(conn, einst, LLMMitFragen())
    tg = TG()
    nachricht = {"text": "let's discuss the questions", "message_id": 999}
    ausgefallen = ablauf._szene_hat_vorfahrt(conn, tg, LLM(), einst, 1, nachricht)
    assert ausgefallen is False


# ---------------------------------------------------------------------------
# Der Erkenner baut eine Karte nie automatisch neu
# ---------------------------------------------------------------------------


def test_erkenner_text_ueberarbeiten_verworfen_bei_karten_in_phase_6(
    conn, einst, padua, monkeypatch,
):
    from interview_theater import erkenner, ueberarbeitung

    _karte1(conn, einst, LLM())
    phasen.setze(conn, 1, 6, "befehl")
    tg = TG()
    szenenkarte.starte_dialog(conn, tg, einst, 1, 1)
    aufgerufen = []
    monkeypatch.setattr(ueberarbeitung, "ueberarbeite",
                        lambda *a, **k: aufgerufen.append(a))
    erkenner._starte_teil2(
        LLM(), tg, conn, einst, 1,
        [{"art": "text_ueberarbeiten", "wert": "Emma sings first"}], [],
    )
    assert aufgerufen == []
