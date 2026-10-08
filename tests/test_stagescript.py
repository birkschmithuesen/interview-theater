"""Phase 7 = Stage Script aus den Szenenkarten (Padua-Phasenumbau, Birk
07.10.2026 ~18:12, ``[karten] aktiv``): Szene fuer Szene aus der Karte, das
Format nach dem Kartentyp, einmal ein Kopf bei Handlungsanweisungen, EN/IT-
Spiegel, Abnahme ueber die vorhandenen Wege."""

import json

import pytest

from interview_theater import (
    phasen, repo, schaerfung, stagescript, szenenkarte, ueberarbeitung, workshop,
)

from test_szenenkarte import LLM as KartenLLM  # noqa: F401
from test_szenenkarte import LLMMitFragen as KartenLLMMitFragen  # noqa: F401
from test_szenenkarte import TG, _karte1, _lage, padua  # noqa: F401


class LLM:
    def __init__(self):
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "nutzer": nutzer})
        if art == stagescript.ART:
            return {"text": "**Theme**\nEMMA: Casa.", "kopf": "Setup: a bar table."}
        if art == "skript_spiegel":
            if nutzer == "Setup: a bar table.":
                return {"prosa_en": "Setup: a bar table.",
                        "prosa_it": "Impostazione: un tavolo al bar."}
            return {"prosa_en": "**Theme**\nEMMA: Home.", "prosa_it": "**Tema**\nEMMA: Casa."}
        return {}


def _karten(conn, typ="instructions"):
    ids = _lage(conn)
    for n, sid in enumerate(ids, start=1):
        repo.setze_szenenkarte(conn, sid, json.dumps({
            "typ": typ, "worum": f"Worum {n}", "ort": "Bar", "wer": "Anna",
            "punkte": [f"Punkt {n}"], "zitate": [], "fragen": []}))
        repo.setze_szenenkarte_bestaetigt(conn, sid)
    phasen.setze(conn, 1, 7, "befehl")
    return ids


def _warte():
    stagescript._sperre_fuer(1).acquire(timeout=5)
    stagescript._sperre_fuer(1).release()


def test_ohne_schalter_bleibt_phase_7_die_formwahl(conn, einst, monkeypatch):
    ids = _karten(conn)
    tg = TG()
    monkeypatch.setattr(ueberarbeitung, "aktiv", lambda: True)
    ueberarbeitung.weiter_7(conn, tg, LLM(), einst, 1)
    assert stagescript.T._TEXT_SCHREIBE.format(nummer=1) not in tg.texte
    assert repo.hole_szene(conn, ids[0])["volltext"] is None


def test_phase_7_szene_fuer_szene_aus_der_karte(conn, einst, padua):
    ids = _karten(conn)
    tg, klm = TG(), LLM()
    ueberarbeitung.weiter_7(conn, tg, klm, einst, 1, aus_eintritt=True).join(5)
    # Birk 08.10. ~12:00: EN sofort, IT kommt im Hintergrund nach.
    import time as _t
    for _ in range(50):
        zeile = repo.hole_szene(conn, ids[0])
        if zeile["volltext_it"]:
            break
        _t.sleep(0.1)
    # EN aus dem Spiegelpass (trennt eine zweisprachige Rohfassung sauber)
    assert zeile["volltext"] == "**Theme**\nEMMA: Home."
    assert zeile["volltext_it"] == "**Tema**\nEMMA: Casa."
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["stage_kopf"] == "Setup: a bar table."
    assert stand["stage_kopf_it"] == "Impostazione: un tavolo al bar."
    nutzer = klm.aufrufe[0]["nutzer"]
    assert "Worum 1" in nutzer and "CAMERA" in nutzer and "\"kopf\"" in nutzer
    # Morgen-Auftrag 4, Nachtrag 2: chat_id 1 steht in keiner
    # italienisch_ab_phase6_chats-Liste -- Statuszeile bleibt englisch.
    assert any("Script tab" in t for t in tg.texte)

    # "No, change" -> neu mit Notiz und bisherigem Text, ohne zweiten Kopf.
    ueberarbeitung.ueberarbeite(conn, tg, klm, einst, 1, "Anna speaks Italian", nummer=1).join(5)
    nutzer = [a for a in klm.aufrufe if a["art"] == stagescript.ART][-1]["nutzer"]
    assert "Anna speaks Italian" in nutzer and "EMMA: Home." in nutzer
    assert "\"kopf\"" not in nutzer

    # "Yes, save" -> fertig_am, naechste Szene.
    ueberarbeitung.bestaetige_szene_7(conn, tg, klm, einst, 1, 1)
    _warte()
    assert repo.hole_szene(conn, ids[0])["fertig_am"]
    assert repo.hole_szene(conn, ids[1])["volltext"]
    assert ueberarbeitung.aktuelle_szene(conn, 1) == 2
    assert ueberarbeitung.bestaetige_szene_7(conn, tg, klm, einst, 1, 1) == \
        stagescript.T._TEXT_NICHT_DRAN
    ueberarbeitung.bestaetige_szene_7(conn, tg, klm, einst, 1, 2)
    assert tg.texte[-1] == stagescript.T._TEXT_ALLES_FERTIG


def test_schalter_aus_ruft_karten_nachzug_nicht(conn, einst, padua, monkeypatch):
    """``[karten] p7_meta_nachziehen`` aus (Vorgabe false ohne das Padua-
    Profilfeld) -- kein zusaetzlicher Modellaufruf nach dem Skript."""
    monkeypatch.setattr(workshop, "p7_meta_nachziehen_aktiv", lambda *a, **k: False)
    ids = _karten(conn)
    tg, klm = TG(), LLM()
    ueberarbeitung.weiter_7(conn, tg, klm, einst, 1, aus_eintritt=True).join(5)
    _warte()
    assert not any(a["art"] == "karten_nachzug" for a in klm.aufrufe)


def test_schalter_an_ruft_karten_nachzug_und_aktualisiert_karte(conn, einst, padua, monkeypatch):
    from interview_theater import karten_nachzug

    monkeypatch.setattr(workshop, "p7_meta_nachziehen_aktiv", lambda *a, **k: True)
    ids = _karten(conn)

    class LLMMitNachzug(LLM):
        def schema(self, chat_id, system, nutzer, schema, art):
            self.aufrufe.append({"art": art, "nutzer": nutzer})
            if art == karten_nachzug.ART:
                return {"ort": "Piazza", "wer": "Anna", "modus": "none"}
            return super().schema(chat_id, system, nutzer, schema, art)

    tg, klm = TG(), LLMMitNachzug()
    ueberarbeitung.weiter_7(conn, tg, klm, einst, 1, aus_eintritt=True).join(5)
    import time as _t
    karte = None
    for _ in range(50):
        karte = szenenkarte.karte_von(repo.hole_szene(conn, ids[0]))
        if karte and karte.get("ort") == "Piazza":
            break
        _t.sleep(0.1)
    assert karte["ort"] == "Piazza"
    assert repo.hole_szene(conn, ids[0])["karte_bestaetigt_am"]
    verlauf = repo.karte_verlauf(conn, 1, ids[0])
    assert verlauf[-1]["ausloeser"] == szenenkarte.AUSLOESER_AENDERUNG


def test_format_nach_kartentyp(conn, padua):
    ids = _karten(conn, typ="moment")
    text = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "microphone" in text and "CAMERA" not in text
    assert stagescript.braucht_kopf(conn, 1) is False


def test_ohne_zitate_chats_traegt_zusaetzlichen_auftrag(conn, padua, monkeypatch):
    ids = _karten(conn)
    text_ohne = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "Interview words that are spoken on stage" not in text_ohne

    monkeypatch.setattr(workshop, "skript_ohne_zitate_chats", lambda *a, **k: frozenset({1}))
    text_mit = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "Interview words that are spoken on stage" in text_mit


def test_italienisch_ab_phase6_chats_steuert_statuszeilen(conn, einst, padua, monkeypatch):
    """Morgen-Auftrag 4, Nachtrag 2: eine Chat-Liste, nicht ein globaler
    Schalter -- chat_id 1 bekommt Italienisch nur, wenn es in der Liste
    steht; die Testgruppe-Analogie (chat_id NICHT in der Liste) bleibt
    englisch, siehe test_phase_7_szene_fuer_szene_aus_der_karte."""
    monkeypatch.setattr(workshop, "italienisch_ab_phase6_chats", lambda *a, **k: frozenset({1}))
    ids = _karten(conn)
    tg, klm = TG(), LLM()
    ueberarbeitung.weiter_7(conn, tg, klm, einst, 1, aus_eintritt=True).join(5)
    assert any("scheda Script" in t for t in tg.texte)


def test_kopf_nur_bei_ueberwiegend_anweisungen(conn, padua):
    ids = _karten(conn, typ="instructions")
    assert stagescript.braucht_kopf(conn, 1) is True
    repo.setze_szenenkarte(conn, ids[0], json.dumps({"typ": "description", "worum": "x",
                                                     "punkte": ["y"]}))
    assert stagescript.braucht_kopf(conn, 1) is False


def test_alle_bisherigen_szenen_voll_ohne_zeichengrenze(conn, padua):
    """Birk 08.10.2026 ~10:55: in Phase 7 gehen IMMER die vollen bisherigen
    Szenentexte mit -- nicht nur ein Teil, keine Zeichengrenze. Mutanten:
    Kuerzung auf ein Ende -> rot (ANFANG fehlt); nur vorige Szene -> rot
    (Szene 1 fehlt bei Szene 3); Block weg -> rot."""
    ids = _karten(conn)
    lang = "ANFANG-DER-SZENE-1 " + "x " * 20000 + "ENDE-SZENE-1"
    repo.setze_stagescript(conn, ids[0], lang, None)
    repo.setze_stagescript(conn, ids[1], "ANFANG-SZENE-2 dialog ENDE-SZENE-2", None)
    # Szene 2 neu schreiben: Szene 1 VOLL drin (40.000 Zeichen, keine Kuerzung)
    text = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[1]))
    assert stagescript.T._KOPF_GESCHRIEBEN in text
    assert lang in text
    # Szene 1 sieht Szene 2 (alle bisher geschriebenen, nicht nur die vorige)
    erste = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "ANFANG-SZENE-2 dialog ENDE-SZENE-2" in erste
    assert lang not in erste.split(stagescript.T._KOPF_KARTE)[0]


def test_baue_nutzertext_nimmt_ueber_claude_parameter_entgegen(conn, padua, monkeypatch):
    """Derselbe Datenschutz-Schalter wie bei den Karten (``hintergrund.py``):
    mit Einwilligung je Gruppe (Vorgabe, hier isoliert von Paduas pauschaler
    Freigabe) gehen die Interview-Verdichtungen nur auf dem Kimi-Weg mit."""
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "modellwahl_einwilligung_aktiv", lambda *a, **k: True)
    ids = _karten(conn)
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    szene_zeile = repo.hole_szene(conn, ids[0])

    ohne_claude = stagescript.baue_nutzertext(conn, 1, szene_zeile)
    mit_claude = stagescript.baue_nutzertext(conn, 1, szene_zeile, ueber_claude=True)

    assert "Interviews behind your chosen passages" in ohne_claude
    assert "Interviews behind your chosen passages" not in mit_claude


# ---------------------------------------------------------------------------
# Verfeinerungen aus Phase 6 (Birk 08.10.2026 ~10:35): was die Gruppe an der
# Karte geaendert hat, geht als eigener Block in den P7-Prompt.
# ---------------------------------------------------------------------------


def test_baue_nutzertext_zeigt_verfeinerungen_aus_phase_6(conn, einst, padua):
    """Szenario aus dem Auftrag: Karte -> No change "piano with pedal" ->
    neue Karte -> der P7-Prompt dieser Szene traegt Notiz UND Diff.
    Mutant: Block weg -> rot; Notiz oder Diff fehlt -> rot."""
    ids = _karte1(conn, einst, KartenLLM())

    class AndereKarte(KartenLLM):
        def schema(self, chat_id, system, nutzer, schema, art):
            if art == szenenkarte.ART:
                return {"typ": "spoken", "worum": "The voices are shared.", "ort": "semicircle",
                        "wer": "Emma, Giada",
                        "punkte": ["Emma opens with pedal down", "Giada answers"],
                        "zitate": [2, 99, 1], "questions": []}
            return super().schema(chat_id, system, nutzer, schema, art)

    szenenkarte.aendere(conn, TG(), AndereKarte(), einst, 1, "piano with pedal", nummer=1)
    szenenkarte._sperre_fuer(1).acquire(timeout=5)
    szenenkarte._sperre_fuer(1).release()

    text = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert stagescript.T._KOPF_VERFEINERUNGEN in text
    assert "piano with pedal" in text
    assert "punkte" in text


def test_baue_nutzertext_ohne_phase_6_aenderung_kein_verfeinerungs_block(conn, einst, padua):
    ids = _karte1(conn, einst, KartenLLM())
    text = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert stagescript.T._KOPF_VERFEINERUNGEN not in text


def test_baue_nutzertext_zeigt_uebersprungene_fragen_als_verfeinerung(conn, einst, padua):
    ids = _karte1(conn, einst, KartenLLMMitFragen())
    szenenkarte.ueberspringe_fragen(conn, TG(), einst, 1, 1)
    text = stagescript.baue_nutzertext(conn, 1, repo.hole_szene(conn, ids[0]))
    assert "questions skipped as not fitting" in text


import time


def test_zweiter_ausloeser_desselben_laufstarts_bleibt_still(conn, einst, padua):
    """Live-Fund 08.10.2026 (Tester-Chat 7000000000099, web_post 2202/2203):
    ein zweiter Ausloeser, der denselben eben erst gestarteten Lauf trifft,
    schickte "Sto ancora scrivendo" direkt nach "Sto scrivendo" in derselben
    Sekunde -- fuer die Gruppe sieht das nach zwei Laeufen aus. Innerhalb der
    Echo-Schwelle bleibt die zweite Meldung aus; die Sperre selbst bleibt
    unberuehrt (``starte`` liefert weiterhin ``None``).
    Mutant: Schwelle auf 0.0 -> rot."""
    ids = _karten(conn)
    tg, klm = TG(), LLM()
    sperre = stagescript._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        stagescript._GESTARTET[1] = time.monotonic()
        assert stagescript.starte(conn, tg, klm, einst, 1, 1) is None
        assert stagescript.T._TEXT_LAEUFT not in tg.texte
    finally:
        sperre.release()
        stagescript._GESTARTET.pop(1, None)


def test_alte_sperre_meldet_weiterhin_laeuft(conn, einst, padua):
    """Gegenstueck zum Test oben: eine Sperre, die NICHT eben erst durch
    einen eigenen Lauf-Start gesetzt wurde (``_GESTARTET`` kennt ``chat_id``
    nicht), meldet weiterhin "Sto ancora scrivendo" -- die Echo-Unterdrueckung
    darf echte Wartemeldungen nicht verschlucken."""
    ids = _karten(conn)
    tg, klm = TG(), LLM()
    sperre = stagescript._sperre_fuer(1)
    assert sperre.acquire(blocking=False)
    try:
        assert stagescript.starte(conn, tg, klm, einst, 1, 1) is None
        assert stagescript.T._TEXT_LAEUFT in tg.texte
    finally:
        sperre.release()


def test_stagescript_lauf_haelt_tippanzeige(conn, padua, monkeypatch):
    """Birk 08.10.2026 ~11:50: waehrend des Schreibens laeuft die Tippanzeige.
    Mutante: Puls weg -> rot (tippt nie gerufen)."""
    import threading as _th
    from interview_theater import stagescript as st
    ids = _karten(conn)
    gerufen = []
    tor = _th.Event()

    class TG:
        def tippt(self, chat_id):
            gerufen.append(chat_id)

    def langsam(*a, **k):
        tor.wait(4.0)
        return False
    monkeypatch.setattr(st, "schreibe", langsam)
    monkeypatch.setattr(st, "_sende", lambda *a, **k: None)
    monkeypatch.setattr(st, "zeige", lambda *a, **k: None)
    faden = st.starte(conn, TG(), object(), None, 1, 1)
    faden.join(6.0)
    assert len(gerufen) >= 2


def test_bot_setzt_stagescript_nach_neustart_fort(conn, padua, monkeypatch):
    """Birk 08.10.2026 ~11:55: Deploy mitten im Lauf -> beim Start neu anstossen.
    Mutante: Fortsetzung weg -> rot."""
    from interview_theater import bot, phasen, stagescript as st
    ids = _karten(conn)
    monkeypatch.setenv("IT_WEB_CHAT_ID", "1")
    monkeypatch.setattr(phasen, "aktuelle", lambda c, ch: 7)
    gestartet = []
    monkeypatch.setattr(st, "starte", lambda c, tg, klm, e, ch, nr, notiz=None: gestartet.append((ch, nr)))
    bot._setze_stagescript_fort(conn, object(), object(), None)
    assert gestartet == [(1, 1)]
    repo.setze_stagescript(conn, ids[0], "TEXT", None)
    gestartet.clear()
    bot._setze_stagescript_fort(conn, object(), object(), None)
    assert gestartet == []


def test_endfassung_ohne_open_und_ohne_zitatkaesten():
    """Birk 08.10.2026 ~12:15: Endfassung -- keine Fragen, keine Zitat-Kaesten."""
    from interview_theater import stagescript as st
    roh = ('1. Emma enters.\n[OPEN: who brings the coffee?]\n'
           '> *Interview quote (4):* "No, non ero ancora nato."\n'
           'GIADA: Home. (Interview 12)\n[APERTO: luce?]\nSAMUELE plays. [OPEN: how long?]')
    t = st.endfassung(roh)
    assert "OPEN" not in t and "APERTO" not in t and "Interview" not in t and ">" not in t
    assert '"No, non ero ancora nato."' in t and "GIADA: Home." in t and "SAMUELE plays." in t


def test_trenne_sprachen_zweisprachige_ausgabe():
    from interview_theater import stagescript as st
    it = "**SCENA 1 — IL PRIMO TOCCO** · *momento*\n" + "Il pubblico entra in silenzio. " * 5
    en = "**SCENE 1 — THE FIRST PRESS** · *moment*\n" + "The audience enters in silence. " * 5
    e, i = st.trenne_sprachen(it + "\n\n" + en)
    assert e.startswith("**SCENE 1") and "SCENA" not in e
    assert i.startswith("**SCENA 1") and "SCENE 1" not in i
    assert st.trenne_sprachen(en) == (en, None)


# --- Chat-Fassung wird Script-Fassung (Birk 08.10.2026 ~13:20, G1 live) ---

_CHAT_S1 = ("Scena 1 di 3: resta l'ultima versione, con una sola differenza.\n\n"
            "1. Il pubblico prende posto attorno al grande tavolo circolare.\n\n"
            "2. Emma e Giada accolgono le persone.\n"
            "EMMA: Benvenuti e benvenute.\n"
            "GIADA: Prepariamo la nostra casa.\n\n"
            "3. Samuele e Giona suonano la tonica.")


def _p7_mit_s1(conn, monkeypatch):
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[0], "1. Old.\n2. Old too.", None)
    monkeypatch.setattr(workshop, "p7_chat_als_script_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(workshop, "p7_meta_nachziehen_aktiv", lambda *a, **k: False)
    # Spiegelpass im Hintergrund still (sonst ueberschreibt der Fake-Spiegel
    # nebenlaeufig mit "EMMA: Home." -- im Betrieb gewollt, im Test ein Rennen).
    from interview_theater import skript_uebersetzung
    monkeypatch.setattr(skript_uebersetzung, "spiegle_text", lambda *a, **k: None)
    return ids


def test_chatfassung_wird_scriptfassung_mit_knoepfen(conn, einst, padua, monkeypatch):
    ids = _p7_mit_s1(conn, monkeypatch)
    tg = TG()
    assert stagescript.uebernimm_chatfassung(conn, tg, LLM(), einst, 1, _CHAT_S1) is True
    zeile = repo.hole_szene(conn, ids[0])
    assert "Prepariamo la nostra casa." in zeile["volltext"]
    assert zeile["fertig_am"] is None
    assert "Scena 1 di 3" not in zeile["volltext"]
    assert any("1" in t for t in tg.texte)  # zeige(): Hinweis + Yes/No


def test_kurze_antwort_ist_keine_fassung(conn, einst, padua, monkeypatch):
    ids = _p7_mit_s1(conn, monkeypatch)
    for t in ("Scena 1 di 3: il testo non cambia.",
              "Scene 1 of 3: the text stays as it is.\n\nFor Scene 3 this changes one thing.",
              "Bene, la scena 1 di 3 resta così."):
        assert stagescript.uebernimm_chatfassung(conn, TG(), LLM(), einst, 1, t) is False
    assert repo.hole_szene(conn, ids[0])["volltext"] == "1. Old.\n2. Old too."


def test_schalter_aus_uebernimmt_nichts(conn, einst, padua, monkeypatch):
    ids = _p7_mit_s1(conn, monkeypatch)
    monkeypatch.setattr(workshop, "p7_chat_als_script_aktiv", lambda *a, **k: False)
    assert stagescript.uebernimm_chatfassung(conn, TG(), LLM(), einst, 1, _CHAT_S1) is False
    assert repo.hole_szene(conn, ids[0])["volltext"] == "1. Old.\n2. Old too."


def test_ausserhalb_phase_7_nichts(conn, einst, padua, monkeypatch):
    ids = _p7_mit_s1(conn, monkeypatch)
    phasen.setze(conn, 1, 6, "befehl")
    assert stagescript.uebernimm_chatfassung(conn, TG(), LLM(), einst, 1, _CHAT_S1) is False


def test_chatfassung_ohne_vorrede_und_schlussfrage(conn, einst, padua, monkeypatch):
    _p7_mit_s1(conn, monkeypatch)
    text = ("Scena 1 di 3: ecco la nuova versione.\nHo cambiato solo il punto 2.\n\n"
            "1. Il pubblico entra.\n\n2. Emma accoglie.\nEMMA: Benvenuti.\n\n"
            "Va bene così o cambio ancora qualcosa?")
    nummer, fassung = stagescript.chatfassung(conn, 1, text)
    assert nummer == 1 and fassung.startswith("1. Il pubblico entra.")
    assert "Ho cambiato" not in fassung and "Va bene così" not in fassung


def test_chatfassung_kopf_ohne_gesamtzahl_mit_szenenkopf(conn, einst, padua, monkeypatch):
    """Tester 08.10. 13:40: "Scene 5: Second Rise" + vollstaendige Szene mit eigenem Kopf."""
    _p7_mit_s1(conn, monkeypatch)
    text = ("Scene 1: Tornare a casa\n\n**SCENE 1 — HOME** · *moment*\n\n"
            "Place / mode: the room.\n\nVOCE 1: First line.\nVOCE 2: Second line.\n"
            "VOCE 1: And now we wait.")
    nummer, fassung = stagescript.chatfassung(conn, 1, text)
    assert nummer == 1 and fassung.startswith("**SCENE 1")
    assert "And now we wait." in fassung
