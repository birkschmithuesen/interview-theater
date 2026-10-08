"""Phase 7 = das Stage Script aus den Szenenkarten (Padua-Phasenumbau, Birk,
Live-Workshop 07.10.2026 ~18:12, Profilschalter ``[karten] aktiv``).

Keine Formwahl, keine Sprechweisen mehr: jede Szene wird -- eine nach der
anderen -- aus ihrer abgenommenen Karte (``szenenkarte.py``) in das Format
der Gruppe geschrieben. Das Format folgt dem Kartentyp:

* ``description`` -- der Ablauf in 5-8 Zeilen (G1 Szene 1 und 3);
* ``spoken`` -- Sprechtext in Abschnitten, ``SPRECHER:``-Zeilen, Interview
  quotes markiert, [Musik-Cues] (G1 Szene 2);
* ``instructions`` -- Thema, Handlungsanweisung je Person, Einstiegssaetze,
  KAMERA, ABBRUCH (G2); dazu EINMAL je Stueck ein Kopf (Versuchsanordnung +
  Rollen mit Charakter, ``arbeitsstand.stage_kopf``);
* ``moment`` -- Ort/Modus (🎤 Mikrofon · 👂 1:1 · 👥 Kollektiv), Wer,
  Wand/Klang, Zitate, Uebergang (G3).

Interview quotes stehen IMMER im Original (``> *Interview quote (N):* "…"``).
Der Text geht nach ``szene.volltext``; mit ``[skript] zweisprachig`` danach
der EN/IT-Spiegel (``skript_uebersetzung.spiegle_text``) nach ``volltext``/
``volltext_it``. Abnahme ueber die vorhandenen Wege (``ueberarbeitung.
weiter_7``/``bestaetige_szene_7``/``ueberarbeite``/``nimm_ab`` verzweigen
hierher); "Yes, save" setzt ``fertig_am``."""

from __future__ import annotations

import difflib
import logging
import re
import threading
import time

from interview_theater import anweisungen, modellwahl, repo, szene_claude, workshop

log = logging.getLogger(__name__)

ART = "stagescript"
PHASE = 7
#: So viel vom Ende der vorigen Szene geht in den Prompt.

SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string",
                 "description": "The stage script of this one scene, in the format "
                                "given for its type."},
        "kopf": {"type": "string",
                 "description": "Only when asked for: the head of the whole script "
                                "(setup and roles). Otherwise an empty string."},
    },
    "required": ["text", "kopf"],
    "additionalProperties": False,
}


def aktiv() -> bool:
    return workshop.szenenkarten_aktiv()


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def _szenen(conn, chat_id: int) -> list:
    from interview_theater import szenenkarte

    return szenenkarte._szenen(conn, chat_id)


def _szene_mit_nummer(conn, chat_id: int, nummer: int):
    return next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)


def aktuelle_nummer(conn, chat_id: int) -> int | None:
    """Die erste Szene ohne abgenommenes Stage Script (``fertig_am``)."""
    for s in _szenen(conn, chat_id):
        if not _gesetzt(s["fertig_am"]):
            return s["nummer"]
    return None


def braucht_kopf(conn, chat_id: int) -> bool:
    """Ein Kopf (Versuchsanordnung + Rollen) gehoert vor ein Skript, das
    UEBERWIEGEND aus Handlungsanweisungen besteht (G2) -- einmal je Stueck.
    Eine einzelne Anweisungsszene (G1: das Ritual) braucht keinen."""
    from interview_theater import szenenkarte

    typen = [(szenenkarte.karte_von(s) or {}).get("typ") for s in _szenen(conn, chat_id)]
    return bool(typen) and sum(t == "instructions" for t in typen) * 2 > len(typen)


#: Will die Notiz eine grammatische/sprachliche Korrektur -- rein ueber das
#: Vokabular der Notiz, bewusst OHNE Namensliste (Live-Fehlerklasse 7, Padua
#: 08.10.2026: Whisper verhoert gelegentlich Eigennamen in den Interviews;
#: nur wenn die Gruppe ausdruecklich um Grammatik/Sprache bittet, darf der
#: Schreiber offensichtliche Transkriptfehler bei Namen mitkorrigieren).
_KORREKTUR_WUNSCH = re.compile(
    r"\b(grammar|grammatical(?:ly)?|grammatica(?:le|lmente)?|correct(?:ion|ed)?|"
    r"correggi|correzione|spelling|ortografia|transcription error|"
    r"errore di trascrizione|mishear(?:d)?|sentito male|capito male|"
    r"wrong name|nome sbagliato|nomi sbagliati)\b",
    re.IGNORECASE,
)


def ist_korrektur_wunsch(notiz: str | None) -> bool:
    """Bittet ``notiz`` erkennbar um eine grammatische/sprachliche
    Korrektur? Siehe ``_KORREKTUR_WUNSCH``."""
    return bool(_KORREKTUR_WUNSCH.search(notiz or ""))


def baue_nutzertext(conn, chat_id: int, szene, notiz: str | None = None,
                    mit_kopf: bool = False, ueber_claude: bool = False) -> str:
    from interview_theater import hintergrund, szenenkarte

    stand = repo.hole_arbeitsstand(conn, chat_id)

    def feld(name: str) -> str:
        return ((stand[name] if stand is not None and name in stand.keys() else "") or "").strip()

    # Der Hintergrund kommt aus EINER Funktion -- derselben wie bei den
    # Karten (Andockstelle der Phasen-Summary, Birk 07.10.2026 ~19:40).
    # ``ueber_claude`` geht unveraendert durch (Datenschutz: der
    # Verdichtungen-Block bleibt dem Kimi-Weg vorbehalten, ``hintergrund.py``).
    teile = []
    hinten = hintergrund.hintergrund_fuer_prompt(conn, chat_id, ueber_claude=ueber_claude)
    if hinten:
        teile.append(hinten)
    if feld("stage_kopf") and not mit_kopf:
        teile.append(T._KOPF_STUECKKOPF + "\n" + feld("stage_kopf"))
    alle = []
    for s in _szenen(conn, chat_id):
        karte = szenenkarte.karte_von(s)
        if karte is None or s["nummer"] == szene["nummer"]:
            continue
        alle.append(f"{s['nummer']}. {s['titel'] or ''} -- {karte.get('worum', '')}")
    if alle:
        teile.append(T._KOPF_ANDERE + "\n" + "\n".join(alle))
    # ALLE bisher geschriebenen Szenen im VOLLEN Wortlaut, ohne Kuerzung und
    # ohne Zeichengrenze (Birk 08.10.2026 ~10:55: "in Phase 7 sollen immer
    # die vollen bisherigen Szenentexte mitgegeben werden, nicht nur ein Teil
    # und auch keine Zeichenbegrenzung"). Ersetzt das 900-Zeichen-Ende der
    # vorigen Szene. Reihenfolge = Szenennummer; die aktuelle Szene steht
    # nur beim Neuschreiben (``_KOPF_BISHER``) drin.
    geschrieben = [
        f"### {s['nummer']}. {s['titel'] or ''}\n{(s['volltext'] or '').strip()}"
        for s in _szenen(conn, chat_id)
        if s["nummer"] != szene["nummer"] and (s["volltext"] or "").strip()
    ]
    if geschrieben:
        teile.append(T._KOPF_GESCHRIEBEN + "\n\n" + "\n\n".join(geschrieben))
    karte = szenenkarte.karte_von(szene) or {}
    teile.append(T._KOPF_KARTE + "\n" + szenenkarte.karte_text(karte, szene, chat_id))
    verfeinerungen = szenenkarte.verfeinerungs_zeilen(conn, chat_id, szene)
    if verfeinerungen:
        teile.append(T._KOPF_VERFEINERUNGEN + "\n"
                     + "\n".join(f"- {zeile}" for zeile in verfeinerungen))
    typ = karte.get("typ") or "description"
    teile.append(T._KOPF_FORMAT_TYP + "\n" + T.FORMAT_JE_TYP.get(typ, T.FORMAT_JE_TYP["description"]))
    if chat_id in workshop.skript_ohne_zitate_chats():
        teile.append(T._AUFTRAG_OHNE_ZITATE)
    if mit_kopf:
        teile.append(T._AUFTRAG_KOPF)
    staendig = repo.stagescript_notizen_verwendet(conn, szene["id"])
    if staendig:
        # Padua Dauernotiz-Fix (08.10.2026, Punkt 1, Live-Befund G3): eine
        # einmal angewandte Notiz gilt fuer JEDEN weiteren Schreiblauf
        # dieser Szene weiter -- sonst verschwand z. B. "nur Sprechtext,
        # keine Didascalie" beim naechsten Wunsch wieder, weil nur
        # unverwendete Notizen (``repo.stagescript_notizen``) in den
        # Auftrag gingen.
        teile.append(T._KOPF_NOTIZ_DAUERHAFT + "\n"
                     + "\n".join(f"- {n}" for n in staendig))
    alt = (szene["volltext"] or "").strip()
    if notiz and alt:
        teile.append(T._KOPF_BISHER + "\n" + alt)
    if notiz:
        teile.append(T._KOPF_NOTIZ + "\n" + notiz.strip())
        if ist_korrektur_wunsch(notiz):
            teile.append(T._AUFTRAG_NAMEN_KORRIGIEREN)
    teile.append(T._AUFTRAG.format(nummer=szene["nummer"]))
    return "\n\n".join(teile)


def _notiz_mit_gespeicherten(conn, szene_id: int, notiz: str | None) -> str | None:
    """Fuegt die noch unverwendeten Notizen dieser Szene
    (``repo.stagescript_notizen``, Padua Quickfix 08.10.2026) vor eine
    uebergebene Notiz -- eine Dublette (dieselbe Notiz schon gespeichert UND
    als Parameter da) wird nicht zweimal aufgefuehrt."""
    aktuelle = (notiz or "").strip()
    gespeicherte = [g for g in repo.stagescript_notizen(conn, szene_id) if g != aktuelle]
    teile = gespeicherte + ([aktuelle] if aktuelle else [])
    return "\n".join(teile) if teile else None


_OPEN_ZEILE = re.compile(r"^\s*[\[(]\s*(?:OPEN|APERTO|OFFEN)\b[^\])]*[\])]\s*$", re.I)
_OPEN_INLINE = re.compile(r"\s*[\[(]\s*(?:OPEN|APERTO|OFFEN)\b[^\])]*[\])]", re.I)
_ZITAT_LABEL = re.compile(r"^\s*>\s*(?:\*?\s*(?:Interview quote|Citazione(?: dall'intervista)?|Interviewzitat)\s*\(?\s*\d*\s*\)?\s*:?\s*\*?\s*)?", re.I)
_INTERVIEW_NR = re.compile(r"\s*\((?:Interview|Intervista)\s*\d+\)", re.I)


def endfassung(text: str | None) -> str | None:
    """Birk 08.10.2026 ~12:15: das Stage Script ist die ENDFASSUNG fuer die
    Spielenden -- keine [OPEN]-Fragen, keine Zitat-Kaesten/Interviewnummern.
    Deterministische Nachreinigung nach dem Modell (Netz unter dem Prompt):
    [OPEN ...]-Zeilen fallen weg, Zitatzeilen ("> *Interview quote (N):* ...")
    werden normaler Text."""
    if not text:
        return text
    zeilen = []
    for z in text.split("\n"):
        if _OPEN_ZEILE.match(z):
            continue
        z = _OPEN_INLINE.sub("", z)
        if z.lstrip().startswith(">"):
            z = _ZITAT_LABEL.sub("", z, count=1)
        z = _INTERVIEW_NR.sub("", z)
        zeilen.append(z)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(zeilen)).strip()


_KOPF_IT = re.compile(r"^[*_\s]*SCENA\s+\d+\b", re.I | re.M)
_KOPF_EN = re.compile(r"^[*_\s]*SCENE\s+\d+\b", re.I | re.M)


def trenne_sprachen(text: str | None) -> tuple[str | None, str | None]:
    """Birk 08.10.2026 ~12:30: das Modell schreibt oft BEIDE Fassungen in
    eine Ausgabe (Block "SCENA N -- ..." + Block "SCENE N -- ..."). Dann
    deterministisch am Kopf trennen -> (en, it). Sonst (text, None)."""
    if not text:
        return text, None
    mi, me = _KOPF_IT.search(text), _KOPF_EN.search(text)
    if not mi or not me:
        return text, None
    if mi.start() < me.start():
        it, en = text[:me.start()], text[me.start():]
    else:
        en, it = text[:mi.start()], text[mi.start():]
    en, it = en.strip(), it.strip()
    if len(en) < 80 or len(it) < 80:
        return text, None
    return en, it


#: Ab dieser difflib-Aehnlichkeit gilt die Modellausgabe als (fast)
#: wortgleich mit einer woertlich bestaetigten Chat-Fassung -- dann wird
#: NICHT die Modellausgabe gespeichert, sondern die Chat-Fassung selbst,
#: woertlich (Live-Fall G1 Szene 2, 08.10.2026: die Gruppe lieferte den
#: Text dreimal woertlich, "esattamente, senza cambiare niente / non
#: dividere tra Giada e Emma", bestaetigte im Chat -- gespeichert wurde
#: trotzdem eine vom Modell neu geschriebene Fassung mit Rollenaufteilung).
#: ``autojunk=False``: der Vorgabewert behandelt bei laengeren Texten
#: haeufige Zeichen (z. B. Leerzeichen) als "Muell" und uebersieht dadurch
#: Uebereinstimmungen -- gemessen an genau dieser Art Fliesstext.
AEHNLICHKEIT_WOERTLICH_SCHWELLE = 0.95


def _woertlich_statt_modell(chat_fassung: str | None, modell_text: str) -> str | None:
    """``None``, wenn die Modellausgabe stehen bleiben soll -- sonst die
    Chat-Fassung selbst als Ersatz. Rein deterministisch (``difflib``), kein
    Modellaufruf: nur wenn ``chat_fassung`` und ``modell_text`` schon (fast)
    wortgleich sind, gilt die Chat-Fassung als die woertlich bestaetigte und
    ersetzt die Modellausgabe; eine echte Ueberarbeitung (deutlich andere
    Modellausgabe) bleibt unberuehrt."""
    kandidat = (chat_fassung or "").strip()
    if not kandidat:
        return None
    aehnlichkeit = difflib.SequenceMatcher(None, kandidat, modell_text, autojunk=False).ratio()
    if aehnlichkeit >= AEHNLICHKEIT_WOERTLICH_SCHWELLE:
        return kandidat
    return None


def schreibe(conn, klm, e, chat_id: int, nummer: int, notiz: str | None = None,
            chat_fassung: str | None = None) -> bool:
    """Der Modellaufruf (plus ggf. der Spiegelpass). ``True`` bei Erfolg.

    ``chat_fassung``: eine bereits im Chat woertlich bestaetigte Fassung
    dieser Szene, falls vorhanden -- weicht die Modellausgabe davon nur noch
    kosmetisch ab (``_woertlich_statt_modell``), wird die Chat-Fassung
    gespeichert, nicht die Modellausgabe."""
    from interview_theater import skript_uebersetzung

    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        return False
    notiz = _notiz_mit_gespeicherten(conn, szene["id"], notiz)
    stand = repo.hole_arbeitsstand(conn, chat_id)
    mit_kopf = (braucht_kopf(conn, chat_id)
                and not _gesetzt(stand["stage_kopf"] if stand is not None else None))
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    try:
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system=anweisungen.hole(ART),
            nutzer=baue_nutzertext(conn, chat_id, szene, notiz, mit_kopf, ueber_claude),
            schema=SCHEMA, art=ART, ueber_claude=ueber_claude, timeout=240.0,
        )
        text = (ergebnis.get("text") or "").strip()
        if workshop.szenenkarten_aktiv():
            text = endfassung(text) or ""
        if not text:
            raise ValueError("Stage Script ohne Text")
        woertlich = _woertlich_statt_modell(chat_fassung, text)
        if woertlich is not None:
            text = woertlich
            try:
                repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                                   "stagescript_woertlich_umgeschrieben",
                                   f"Szene {nummer}: Modellausgabe wich von der woertlich "
                                   "bestaetigten Chat-Fassung ab, Chat-Fassung uebernommen")
            except Exception:
                log.exception("Vorfall stagescript_woertlich_umgeschrieben nicht geschrieben")
        kopf = (ergebnis.get("kopf") or "").strip()
    except Exception:
        log.exception("Stage Script fehlgeschlagen, chat_id=%s, nummer=%s", chat_id, nummer)
        try:
            repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                               "stagescript_fehler", f"Szene {nummer}: Stage Script nicht erzeugt")
        except Exception:
            log.exception("Vorfall stagescript_fehler nicht geschrieben")
        return False
    if mit_kopf and kopf:
        kopf_it = None
        if workshop.skript_zweisprachig_aktiv():
            gespiegelt_kopf = skript_uebersetzung.spiegle_text(
                conn, klm, e, chat_id, kopf, ueber_claude=ueber_claude)
            if gespiegelt_kopf is not None:
                kopf, kopf_it = gespiegelt_kopf
        repo.setze_arbeitsstand(conn, chat_id, "stage_kopf", kopf)
        repo.setze_arbeitsstand(conn, chat_id, "stage_kopf_it", kopf_it)
    _speichere_text(conn, klm, e, chat_id, szene, text, ueber_claude)
    return True


def _speichere_text(conn, klm, e, chat_id: int, szene, text: str, ueber_claude: bool,
                    text_it_sofort: str | None = None) -> None:
    """Speichern + Hintergrund (Nachzug Karte/Werkbank, IT-Spiegelung) -- ein
    Weg fuer ``schreibe`` und ``uebernimm_chatfassung``."""
    from interview_theater import skript_uebersetzung

    # Birk 08.10.2026 ~12:00 ("max Tempo"): die Szene ist SOFORT da (EN),
    # die italienische Spiegelung laeuft danach im Hintergrund und wird
    # nachgetragen -- vorher wartete die Gruppe ~30 s extra auf die IT-Fassung.
    getrennt_en, getrennt_it = trenne_sprachen(text) if workshop.skript_zweisprachig_aktiv() else (text, None)
    if getrennt_it:
        # Modell lieferte beide Fassungen: sofort sauber getrennt, kein Spiegelpass.
        repo.setze_stagescript(conn, szene["id"], getrennt_en, getrennt_it)
    else:
        repo.setze_stagescript(conn, szene["id"], text, text_it_sofort)
    repo.markiere_stagescript_notizen_verwendet(conn, szene["id"])
    if workshop.szenenkarten_aktiv() and workshop.p7_meta_nachziehen_aktiv():
        from interview_theater import karten_nachzug

        szene_id_nachzug = szene["id"]
        text_nachzug = getrennt_en

        def _nachzug() -> None:
            karten_nachzug.ziehe_nach(conn, klm, e, chat_id, szene_id_nachzug,
                                      text_nachzug, ueber_claude=ueber_claude)

        threading.Thread(target=_nachzug, daemon=True).start()
    if workshop.skript_zweisprachig_aktiv() and not getrennt_it:
        szene_id = szene["id"]

        def _spiegel() -> None:
            try:
                gespiegelt = skript_uebersetzung.spiegle_text(
                    conn, klm, e, chat_id, text, ueber_claude=ueber_claude)
                if gespiegelt is None:
                    return
                en, it = gespiegelt
                aktuell = repo.hole_szene(conn, szene_id)
                # Nur nachtragen, wenn der Text inzwischen nicht neu geschrieben
                # wurde. BEIDE Felder setzen: die Rohfassung des Modells kann
                # zweisprachig sein (IT-Block + EN-Block, Tester 08.10. 12:25) --
                # erst der Spiegelpass trennt sauber in EN und IT.
                if aktuell is not None and (aktuell["volltext"] or "").strip() == text.strip():
                    repo.setze_stagescript_beide(conn, szene_id, endfassung(en), endfassung(it))
            except Exception:
                log.exception("IT-Spiegelung im Hintergrund gescheitert, chat_id=%s", chat_id)

        threading.Thread(target=_spiegel, daemon=True).start()


#: Kopfzeile einer Szenenfassung des Gespraechsbots ("Scena 1 di 3: ...",
#: "Scene 2 of 5 ...", "Szene 1 von 3 ...").
_CHATFASSUNG_KOPF = re.compile(r"^\W*(?:Scena|Scene|Szene)\s+(\d+)\b(?:\s+(?:di|of|von)\s+\d+\b)?", re.I)
_CHATFASSUNG_STRUKTUR = re.compile(r"^\s*(?:\d+\.\s|[A-ZÀ-Ý][A-ZÀ-Ý0-9 ]{1,30}:\s)", re.M)


def chatfassung(conn, chat_id: int, text: str | None) -> tuple[int, str] | None:
    """Ist ``text`` (eine Antwort des Gespraechsbots in Phase 7) eine
    vollstaendige Fassung einer Szene? -> ``(nummer, fassung)``, sonst None.

    Birk 08.10.2026 ~13:20 (G1 live): der Bot schrieb sechs Fassungen von
    Szene 1 in den Chat, das Script blieb alt -- gespeichert wurde die falsche.
    Erkennung deterministisch: Kopfzeile "Scena N di M", danach ein Rumpf mit
    nummerierten Punkten oder Sprechzeilen, mindestens halb so lang wie das
    aktuelle Script der Szene. Kurze Antworten ("il testo non cambia") nie."""
    if not text:
        return None
    erste, _, rumpf = text.strip().partition("\n")
    m = _CHATFASSUNG_KOPF.match(erste)
    if not m:
        return None
    rumpf = rumpf.strip()
    if len(_CHATFASSUNG_STRUKTUR.findall(rumpf)) < 2:
        return None
    # Nur die Szene: Erklaerung vor dem ersten Punkt/der ersten Sprechzeile
    # und eine Schlussfrage an die Gruppe ("Va bene cosi?") fallen weg.
    kopf_im_rumpf = _KOPF_EN.search(rumpf) or _KOPF_IT.search(rumpf)
    start = kopf_im_rumpf.start() if kopf_im_rumpf else _CHATFASSUNG_STRUKTUR.search(rumpf).start()
    rumpf = rumpf[start:].strip()
    absaetze = rumpf.split("\n\n")
    while len(absaetze) > 1 and absaetze[-1].strip().endswith("?") \
            and not _CHATFASSUNG_STRUKTUR.match(absaetze[-1]):
        absaetze.pop()
    rumpf = "\n\n".join(absaetze).strip()
    nummer = int(m.group(1))
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        return None
    alt = (szene["volltext"] or "").strip()
    if alt and len(rumpf) < 0.5 * len(alt):
        return None
    fassung = endfassung(rumpf) or ""
    if not fassung or fassung in (alt, (szene["volltext_it"] or "").strip()):
        return None
    return nummer, fassung


def uebernimm_chatfassung(conn, tg, klm, e, chat_id: int, text: str | None) -> int | None:
    """Phase 7: eine vollstaendige Szenenfassung, die der Gespraechsbot in den
    Chat geschrieben hat, wird automatisch die Script-Fassung (Birk
    08.10.2026 ~13:20: "Jede Fassung, die der Gespraechsbot in den Chat
    schreibt, automatisch zur Skriptfassung"). Danach wieder Yes/No -- mit
    ``[karten] p7_aenderung_im_chat`` als Diff statt Volltext
    (``zeige_aenderung``, Birk 08.10.2026 ~14:00): die Bot-Fassung ist schon
    in Gruppensprache und liegt sofort in beiden Sprachfeldern, deshalb wird
    direkt gegen das Feld der Gruppensprache gediffed, ohne auf den
    Spiegelpass zu warten.

    Nur mit ``[karten] p7_chat_als_script``; laeuft ein Stage-Script-Lauf,
    nichts (der schreibt gleich selbst). Liefert die ``message_id`` der
    gesendeten Nachricht, oder ``None``."""
    from interview_theater import phasen

    if not (workshop.szenenkarten_aktiv() and workshop.p7_chat_als_script_aktiv()):
        return None
    if phasen.aktuelle(conn, chat_id) != 7 or laeuft(chat_id):
        return None
    treffer = chatfassung(conn, chat_id, text)
    if treffer is None:
        return None
    nummer, fassung = treffer
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    ist_it = (workshop.skript_zweisprachig_aktiv()
              and chat_id in workshop.italienisch_ab_phase6_chats())
    alt = ((szene["volltext_it"] if ist_it else szene["volltext"]) or "").strip()
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    en, it = trenne_sprachen(fassung) if workshop.skript_zweisprachig_aktiv() else (fassung, None)
    if it:
        _speichere_text(conn, klm, e, chat_id, szene, en + "\n\n" + it, ueber_claude)
    else:
        # Bis die Spiegelung da ist, zeigen beide Sprachansichten die Chat-Fassung.
        _speichere_text(conn, klm, e, chat_id, szene, fassung, ueber_claude,
                        text_it_sofort=fassung if workshop.skript_zweisprachig_aktiv() else None)
    log.info("Chat-Fassung von Szene %s ins Script uebernommen, chat_id=%s", nummer, chat_id)
    neue_szene = _szene_mit_nummer(conn, chat_id, nummer)
    neu = ((neue_szene["volltext_it"] if ist_it else neue_szene["volltext"]) or "").strip()
    return zeige_aenderung(conn, tg, e, chat_id, nummer, alt, neu)


def spiegle_fehlende(conn, klm, e, chat_id: int) -> None:
    """Birk 08.10.2026 ~12:20: eine IT-Spiegelung, die ein Neustart (Deploy)
    abgebrochen hat, fehlt sonst fuer immer -- im Script-Tab stand dann im
    Italienisch-Modus trotzdem Englisch. Beim Start nachholen, im Hintergrund."""
    from interview_theater import skript_uebersetzung

    if not workshop.skript_zweisprachig_aktiv():
        return
    fehlend = [s for s in _szenen(conn, chat_id)
               if (s["volltext"] or "").strip() and not (s["volltext_it"] or "").strip()]
    if not fehlend:
        return
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)

    def _lauf() -> None:
        for s in fehlend:
            try:
                text = s["volltext"]
                gespiegelt = skript_uebersetzung.spiegle_text(
                    conn, klm, e, chat_id, text, ueber_claude=ueber_claude)
                if gespiegelt is None:
                    continue
                aktuell = repo.hole_szene(conn, s["id"])
                if aktuell is not None and (aktuell["volltext"] or "").strip() == text.strip():
                    repo.setze_stagescript_beide(conn, s["id"], endfassung(gespiegelt[0]),
                                                 endfassung(gespiegelt[1]))
            except Exception:
                log.exception("IT-Nachspiegelung gescheitert, chat_id=%s", chat_id)

    threading.Thread(target=_lauf, daemon=True).start()


def _sende(conn, tg, e, chat_id: int, text: str) -> int:
    message_id = tg.sende(chat_id, text)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


def zeige(conn, tg, e, chat_id: int, nummer: int) -> int:
    """Kein Volltext im Chat: der Hinweis aufs Script, "Yes, save" / "No, change"."""
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    text = _T(chat_id)._TEXT_FERTIG.format(nummer=nummer, titel=(szene["titel"] or "").strip(),
                                 gesamt=len(_szenen(conn, chat_id)))
    return _sende_leiste_7(conn, tg, e, chat_id, nummer, text)


def _sende_leiste_7(conn, tg, e, chat_id: int, nummer: int, text: str) -> int:
    """Eine Nachricht mit der Yes/No-Leiste von Phase 7 -- der gemeinsame
    Versandweg fuer ``zeige`` und ``zeige_aenderung`` (Birk 08.10.2026
    ~14:00: "der Prozess ist fuer alle gleich")."""
    from interview_theater import knoepfe
    from interview_theater.knoepfe import basis, szenen as ks

    basis._nimm_alte_leiste_ab(conn, tg, chat_id, ks.ART_SZENE_PASST)
    leiste = [
        ks._knopf(conn, chat_id, knoepfe.T.TEXT_WEITER_KNOPF, ks.ART_SZENE_PASST, str(nummer)),
        ks._knopf(conn, chat_id, knoepfe.T.TEXT_NEIN_AENDERN_KNOPF, ks.ART_SZENE_ANDERS, str(nummer)),
    ]
    message_id = basis._mit_leiste(conn, tg, chat_id, text, leiste)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


#: Ab diesem Anteil veraenderter Zeichen (1 - difflib-Aehnlichkeit) gilt eine
#: Szene als neu geschrieben statt geaendert -- der Diff waere dann selbst
#: eine Wall of Text (Birk 08.10.2026 ~14:00).
DIFF_NEUSCHRIEBEN_SCHWELLE = 0.7
#: Obergrenze fuer den Diff-Text selbst: mehr als ~1 200 Zeichen oder mehr als
#: 40 % der neuen Szene ist keine "Aenderung" mehr, sondern eine Wall of Text.
DIFF_MAX_ZEICHEN = 1200
DIFF_MAX_ANTEIL = 0.4


def _kurz(text: str, laenge: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= laenge else text[: laenge].rstrip() + "…"


def _notiz_kurz(notiz: str | None) -> str | None:
    """Der eine Satz 'was sich geaendert hat' -- deterministisch aus der
    Aenderungsnotiz der Gruppe, kein Modellaufruf: der erste Satz, sonst die
    ganze Notiz gekuerzt."""
    text = (notiz or "").strip()
    if not text:
        return None
    erster = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].strip()
    return _kurz(erster, 140)


def _absaetze_diff(text: str | None) -> list[str]:
    return [a.strip() for a in re.split(r"\n\s*\n", (text or "").strip()) if a.strip()]


def _diff_absaetze(alt: str, neu: str, t) -> tuple[list[str], int, int, int] | None:
    """(Zeilen fuer die Nachricht, Anzahl geaendert, Anzahl neu, Anzahl
    entfernt) -- ``None``, wenn ``alt`` und ``neu`` absatzgleich sind.

    Geaenderte und neue Absaetze stehen VOLL im neuen Wortlaut; entfernte
    als ``"Tolto: <Anfang>…"`` (bzw. die Fassung der Gruppensprache)."""
    a, b = _absaetze_diff(alt), _absaetze_diff(neu)
    if a == b:
        return None
    sm = difflib.SequenceMatcher(None, a, b)
    zeilen: list[str] = []
    geaendert = neu_anzahl = geloescht = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            for p in a[i1:i2]:
                zeilen.append(t._TEXT_DIFF_ENTFERNT.format(auszug=_kurz(p)))
            geloescht += i2 - i1
        elif tag == "insert":
            zeilen.extend(b[j1:j2])
            neu_anzahl += j2 - j1
        elif tag == "replace":
            zeilen.extend(b[j1:j2])
            geaendert += j2 - j1
    return zeilen, geaendert, neu_anzahl, geloescht


def diff_nachricht(chat_id: int, nummer: int, gesamt: int, alt: str | None,
                   neu: str | None, notiz: str | None = None) -> str | None:
    """Die EINE Aenderungsnachricht fuer eine neu gespeicherte Szene (Birk
    08.10.2026 ~14:00, Robo-Entscheidung): keine Wall of Text, nur was sich
    geaendert hat -- deterministisch aus dem alten und neuen Skripttext,
    kein Modellaufruf.

    ``None``, wenn:

    * ``alt`` leer ist (erste Fassung -- der Aufrufer behaelt den
      bisherigen Script-Tab-Hinweis),
    * ``alt`` und ``neu`` nach Absaetzen gleich sind (keine Aenderung).

    Ist der Unterschied zu gross (``DIFF_NEUSCHRIEBEN_SCHWELLE``), bleibt es
    bei einem Kurzsatz plus Verweis aufs Script -- der Diff waere sonst
    selbst eine Wall of Text."""
    alt = (alt or "").strip()
    neu = (neu or "").strip()
    if not alt or alt == neu:
        return None
    t = _T(chat_id)
    anteil = 1.0 - difflib.SequenceMatcher(None, alt, neu).ratio()
    if anteil >= DIFF_NEUSCHRIEBEN_SCHWELLE:
        return t._TEXT_DIFF_NEUSCHRIEBEN.format(nummer=nummer)
    diff = _diff_absaetze(alt, neu, t)
    if diff is None:
        return None
    zeilen, geaendert, neu_anzahl, geloescht = diff
    if not zeilen:
        return None
    # Live G3 08.10.2026 14:33: ein Neuschreiben mit zurueckgekehrten
    # Regiezeilen lag unter der 70-%-Schwelle, der "Diff" war trotzdem fast
    # die ganze Szene. Nach Laenge deckeln, nicht nur nach Aehnlichkeit.
    if sum(len(z) for z in zeilen) > max(DIFF_MAX_ZEICHEN, DIFF_MAX_ANTEIL * len(neu)):
        return t._TEXT_DIFF_NEUSCHRIEBEN.format(nummer=nummer)
    zusammenfassung = _notiz_kurz(notiz) or t._TEXT_DIFF_ZUSAMMENFASSUNG_ZAHLEN.format(
        geaendert=geaendert, neu=neu_anzahl, geloescht=geloescht)
    kopf = t._TEXT_DIFF_KOPF.format(nummer=nummer, gesamt=gesamt, zusammenfassung=zusammenfassung)
    return "\n\n".join([kopf, *zeilen, t._TEXT_DIFF_REST])


def zeige_aenderung(conn, tg, e, chat_id: int, nummer: int, alt: str | None,
                    neu: str | None, notiz: str | None = None) -> int:
    """Die Aenderungsnachricht nach JEDER gespeicherten Szenenaenderung in
    Phase 7 -- egal ob aus "No, change" oder einer Chat-Fassung (Birk
    08.10.2026 ~14:00). Nur mit ``[karten] p7_aenderung_im_chat``; sonst und
    ohne brauchbaren Diff bleibt es beim bisherigen Script-Tab-Hinweis
    (``zeige``)."""
    from interview_theater import workshop

    text = None
    if workshop.p7_aenderung_im_chat_aktiv():
        text = diff_nachricht(chat_id, nummer, len(_szenen(conn, chat_id)), alt, neu, notiz)
    if text is None:
        return zeige(conn, tg, e, chat_id, nummer)
    return _sende_leiste_7(conn, tg, e, chat_id, nummer, text)


_SPERREN: dict[int, threading.Lock] = {}
_SPERREN_LOCK = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _SPERREN_LOCK:
        return _SPERREN.setdefault(chat_id, threading.Lock())


def laeuft(chat_id: int) -> bool:
    return _sperre_fuer(chat_id).locked()


#: Zeitpunkt (``time.monotonic()``) des letzten erfolgreichen Laufstarts je
#: ``chat_id`` -- Live-Fund 08.10.2026 (Tester-Chat 7000000000099,
#: web_post 2202/2203): ein zweiter Ausloeser desselben Starts traf noch auf
#: die frische Sperre und schickte "Sto ancora scrivendo" direkt nach "Sto
#: scrivendo" in derselben Sekunde -- fuer die Gruppe sahen das wie zwei
#: Laeufe aus. Innerhalb von ``_ECHO_SCHWELLE_SEKUNDEN`` gilt die Busy-Zeile
#: als Echo des eigenen Starts und bleibt aus; eine Sperre, die schon LAENGER
#: steht, meldet weiterhin ganz normal "noch am Schreiben".
_GESTARTET: dict[int, float] = {}
_ECHO_SCHWELLE_SEKUNDEN = 3.0


def _ist_echo_des_laufstarts(chat_id: int) -> bool:
    return time.monotonic() - _GESTARTET.get(chat_id, -_ECHO_SCHWELLE_SEKUNDEN) < \
        _ECHO_SCHWELLE_SEKUNDEN


#: Wie lange ``starte`` auf die IT-Fassung aus dem Hintergrund-Spiegelpass
#: wartet (``_speichere_text._spiegel``, ~30-40 s), bevor die Aenderungs-
#: nachricht in Phase 7 doch auf Englisch geht (Robo-Entscheidung
#: 08.10.2026 ~14:00). Danach faellt die Diff-Nachricht auf EN zurueck,
#: statt die Gruppe unbegrenzt warten zu lassen. Auf 30 s gesenkt
#: (Live-Fehlerklasse 6, Padua 08.10.2026): mit 90 s kamen die Yes/No-
#: Knoepfe der Gruppe spuerbar zu spaet, selbst wenn der Spiegelpass (jetzt
#: mit Nachholversuch, ``skript_uebersetzung.spiegle_text``) laengst
#: gescheitert war.
_IT_DIFF_WARTE_TIMEOUT_S = 30.0
_IT_DIFF_WARTE_INTERVALL_S = 0.5


def _warte_it_fassung(conn, chat_id: int, nummer: int, alt_it: str) -> str | None:
    """Wartet bis zu ``_IT_DIFF_WARTE_TIMEOUT_S`` auf eine von ``alt_it``
    verschiedene ``volltext_it`` -- liefert sie, oder ``None`` beim Timeout."""
    frist = time.monotonic() + _IT_DIFF_WARTE_TIMEOUT_S
    while True:
        szene = _szene_mit_nummer(conn, chat_id, nummer)
        neu_it = ((szene["volltext_it"] if szene else None) or "").strip()
        if neu_it and neu_it != alt_it:
            return neu_it
        if time.monotonic() >= frist:
            return None
        time.sleep(_IT_DIFF_WARTE_INTERVALL_S)


def starte(conn, tg, klm, e, chat_id: int, nummer: int, notiz: str | None = None):
    sperre = _sperre_fuer(chat_id)
    if klm is None or not sperre.acquire(blocking=False):
        if not _ist_echo_des_laufstarts(chat_id):
            _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_LAEUFT)
        return None
    _GESTARTET[chat_id] = time.monotonic()
    _sende(conn, tg, e, chat_id, (_T(chat_id)._TEXT_AENDERE if notiz else _T(chat_id)._TEXT_SCHREIBE).format(
        nummer=nummer))
    # Birk 08.10.2026 ~14:00: der ALTE Text VOR dem Ueberschreiben, damit die
    # Aenderungsnachricht danach dagegen diffen kann (``zeige_aenderung``).
    vorher = _szene_mit_nummer(conn, chat_id, nummer)
    alt_en = ((vorher["volltext"] if vorher else None) or "").strip()
    alt_it = ((vorher["volltext_it"] if vorher else None) or "").strip()

    def _lauf() -> None:
        ok = False
        # Birk 08.10.2026 ~11:50: waehrend des Schreibens (30-90 s) die
        # Tippanzeige im Chat am Leben halten -- sonst sieht die Gruppe nur
        # "Sto scrivendo ..." und nichts bewegt sich.
        fertig = threading.Event()

        def _puls() -> None:
            while not fertig.wait(3.0):
                try:
                    tg.tippt(chat_id)
                except Exception:
                    return

        try:
            tg.tippt(chat_id)
        except Exception:
            pass
        threading.Thread(target=_puls, daemon=True).start()
        try:
            ok = schreibe(conn, klm, e, chat_id, nummer, notiz, chat_fassung=alt_en)
        finally:
            fertig.set()
            sperre.release()
        if not ok:
            _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_FEHLER.format(nummer=nummer))
            return
        if (workshop.p7_aenderung_im_chat_aktiv() and alt_en
                and workshop.skript_zweisprachig_aktiv()
                and chat_id in workshop.italienisch_ab_phase6_chats()):
            # Spec 08.10.2026 ~14:00: fuer eine italienischsprachige Gruppe
            # geht der Diff erst raus, wenn die IT-Fassung des Spiegelpasses
            # da ist -- sonst diffte er die noch unuebersetzte Fassung.
            neu_it = _warte_it_fassung(conn, chat_id, nummer, alt_it)
            if neu_it is not None:
                zeige_aenderung(conn, tg, e, chat_id, nummer, alt_it, neu_it, notiz)
                return
        neu_en = _szene_mit_nummer(conn, chat_id, nummer)
        zeige_aenderung(conn, tg, e, chat_id, nummer, alt_en,
                        ((neu_en["volltext"] if neu_en else None) or "").strip(), notiz)

    faden = threading.Thread(target=_lauf, daemon=True)
    try:
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


def weiter(conn, tg, klm, e, chat_id: int, *, aus_eintritt: bool = False):
    """Die aktuelle Szene: Text da -> zeigen, sonst schreiben; alle
    abgenommen -> die Fertig-Zeile."""
    nummer = aktuelle_nummer(conn, chat_id)
    if nummer is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_ALLES_FERTIG)
        return None
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if _gesetzt(szene["volltext"]):
        zeige(conn, tg, e, chat_id, nummer)
        return None
    return starte(conn, tg, klm, e, chat_id, nummer)


def bestaetige(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    if laeuft(chat_id):
        if not _ist_echo_des_laufstarts(chat_id):
            _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_LAEUFT)
        return _T(chat_id)._TEXT_LAEUFT
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    aktuell = aktuelle_nummer(conn, chat_id)
    if nummer != aktuell or szene is None or not _gesetzt(szene["volltext"]):
        # Live-Befund G2 08.10.2026 ~14:44 (chat 7000000000001, Knopf k:831):
        # die Gruppe hatte per Chat-Notiz schon an Szene 2 weitergeschrieben,
        # waehrend Szene 1 (die eigentliche ``aktuelle_nummer``) nie "Yes,
        # save" bekam -- das "Yes, save" auf Szene 2 landete im Nichts
        # ("non e quella attuale") statt zu sagen, was zuerst drankommt. Hat
        # die wirklich offene Szene schon einen Text UND liegt sie VOR der
        # angeklickten (``nummer`` zu neu, nicht ein veralteter Klick auf
        # eine laengst abgenommene fruehere Szene), bekommt die Gruppe genau
        # deren Hinweis samt Yes/No-Leiste (``zeige``) statt stummer
        # Ablehnung.
        vorherige = _szene_mit_nummer(conn, chat_id, aktuell) if aktuell is not None else None
        if (vorherige is not None and _gesetzt(vorherige["volltext"])
                and aktuell < nummer):
            text = _T(chat_id)._TEXT_ERST_VORHERIGE.format(nummer=aktuell)
            _sende(conn, tg, e, chat_id, text)
            zeige(conn, tg, e, chat_id, aktuell)
            return text
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    repo.setze_szene_fertig(conn, szene["id"], True)
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          _T(chat_id)._JOURNAL_GESPEICHERT.format(nummer=nummer,
                                                        titel=szene["titel"] or "").strip(),
                          quelle="knopf")
    antwort = _T(chat_id)._ANTWORT_GESPEICHERT.format(nummer=nummer)
    weiter(conn, tg, klm, e, chat_id)
    return antwort


#: Nach "No, change" ist die naechste Nachricht nicht automatisch die neue
#: Aenderungsnotiz (Padua Quickfix 08.10.2026, Befund G1 web_post 2390-2394:
#: "did you create szene 1 already sfinakl script?" wurde blind als Notiz
#: genommen und Szene 1 damit neu geschrieben). Rein textuell, kein
#: Erkenner-/Modellaufruf -- ein Fragezeichen, ein Frage-/Stand-Wort am Satz-
#: anfang oder eine der italienischen Stand-Wendungen.
_FRAGE_MUSTER = re.compile(
    r"\?\s*$"
    r"|^\s*(did|do|does|have|has|is|are|was|were|can|could|would|should|"
    r"what|where|when|why|how)\b"
    r"|\b(hai\s+gi[aà]|[eè]\s+gi[aà]|gi[aà]\s+pronta|gi[aà]\s+pronto|dove|quando)\b",
    re.IGNORECASE,
)

#: "No, change" wird zurueckgenommen, ohne neu zu schreiben (Punkt 4).
_ABBRUCH_MUSTER = re.compile(r"^\s*(skip|cancel|annulla|niente)\s*[.!]?\s*$", re.IGNORECASE)


def ist_frage_oder_unklar(notiz: str | None) -> bool:
    """Ist ``notiz`` erkennbar eine Frage/Meta-Nachricht statt einer
    Aenderungsnotiz -- oder leer/unklar?"""
    text = (notiz or "").strip()
    if not text:
        return True
    return bool(_FRAGE_MUSTER.search(text))


def ist_abbruch(notiz: str | None) -> bool:
    """Beendet den Aenderungsmodus, ohne neu zu schreiben."""
    return bool(_ABBRUCH_MUSTER.match((notiz or "").strip()))


def _klaerung(conn, chat_id: int, nummer: int) -> str:
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    t = _T(chat_id)
    stand = (t._TEXT_STAND_FERTIG if szene and _gesetzt(szene["volltext"])
             else t._TEXT_STAND_OFFEN)
    return stand.format(nummer=nummer) + " " + t._TEXT_WAS_AENDERN.format(nummer=nummer)


def aendere(conn, tg, klm, e, chat_id: int, notiz: str, nummer: int | None = None):
    from interview_theater import szenenfolge

    n = nummer if nummer is not None else aktuelle_nummer(conn, chat_id)
    if n is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_KEIN_ZIEL)
        return None
    if ist_abbruch(notiz):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_ABBRUCH.format(nummer=n))
        return None
    if ist_frage_oder_unklar(notiz):
        # Aenderungsmodus bleibt offen -- dieselbe Nachricht, die soeben
        # verbraucht wurde (``szenenfolge.nimm_regienotiz`` in
        # ``ablauf._szene_hat_vorfahrt``), wird erneut erwartet.
        szenenfolge.erwarte_regienotiz(chat_id, n)
        _sende(conn, tg, e, chat_id, _klaerung(conn, chat_id, n))
        return None
    return starte(conn, tg, klm, e, chat_id, n, notiz)


# ---------------------------------------------------------------------------
# Texte (W3)
# ---------------------------------------------------------------------------

_KOPF_STUECKKOPF = "Kopf des Skripts (steht schon fest):"
_KOPF_ANDERE = "Die anderen Szenen (nur zur Orientierung):"
_KOPF_VORHER = "So endet die vorige Szene (steht schon -- hier anschliessen, nichts davon wiederholen):"
_KOPF_GESCHRIEBEN = "Die bisher geschriebenen Szenen im vollen Wortlaut (stehen schon -- an die vorige anschliessen, nichts davon wiederholen, Figuren/Motive/Ton konsistent halten):"
_KOPF_KARTE = "Die abgenommene Karte DIESER Szene -- sie ist bindend:"
#: Phase-6-Verfeinerungen dieser Szene (Birk 08.10.2026 ~10:35): Notiz/Antwort
#: der Gruppe plus deterministischer Feld-Diff, aus ``szenenkarte.
#: verfeinerungs_zeilen``. Nur gesetzt, wenn die Karte ueberhaupt
#: ueberarbeitet wurde -- sonst bleibt der Block ganz weg.
_KOPF_VERFEINERUNGEN = "Wie die Gruppe diese Karte in Phase 6 verfeinert hat:"
_KOPF_FORMAT_TYP = "So sieht das Skript dieser Szene aus:"
_KOPF_BISHER = "Bisheriges Skript dieser Szene, es soll ueberarbeitet werden:"
_KOPF_NOTIZ = "Was die Gruppe geaendert haben will (gilt vor allem anderen):"
#: Padua Dauernotiz-Fix (08.10.2026, Punkt 1): staendige Wuensche, die die
#: Gruppe schon einmal zu dieser Szene geaeussert und die das Skript schon
#: einmal umgesetzt hat -- gelten fuer JEDEN weiteren Schreiblauf weiter,
#: nicht nur fuer den naechsten.
_KOPF_NOTIZ_DAUERHAFT = ("Staendige Wuensche der Gruppe zu dieser Szene (gelten "
                        "immer, chronologisch; ein spaeterer Wunsch, der einem "
                        "frueheren widerspricht, gewinnt):")
_AUFTRAG_KOPF = (
    "Schreib zusaetzlich in \"kopf\" EINMAL den Kopf des ganzen Skripts: die "
    "Versuchsanordnung (Ziel, Ort, Regeln, Abbruch) und je beteiligter Person "
    "ihre Rolle -- was sie tut, was nie, wann sie eingreift. Rollen und "
    "Eigenschaften NUR aus Uebersicht und Festlegungen der Gruppe; wo die "
    "Gruppe keine genannt hat, keine."
)
_AUFTRAG_OHNE_ZITATE = (
    "Diese Gruppe will keine Zitatkaesten im Skript (Morgen-Auftrag 1, "
    "Nachtrag Birk 08.10.2026 ~08:30): Interviewworte, die auf der Buehne "
    "gesprochen werden, gehoeren als normaler Text in die Sprechzeilen -- "
    "keine Zitatbloecke, keine Interview-Nummern."
)
_AUFTRAG_NAMEN_KORRIGIEREN = (
    "Die Notiz bittet um eine grammatische/sprachliche Korrektur: offensichtliche "
    "Transkriptfehler bei Eigennamen (vom Spracherkenner falsch verstandene Namen) "
    "duerft ihr dabei mitkorrigieren -- keine neuen Namen erfinden, nur erkennbare "
    "Hoerfehler richtigstellen."
)
_AUFTRAG = "Schreib jetzt das Stage Script von Szene {nummer}."
FORMAT_JE_TYP = {
    "description": (
        "Der Ablauf in 5 bis 8 kurzen Zeilen: Positionen, Musik/Klang, was "
        "gesagt oder gezeigt wird, der Uebergang zur naechsten Szene. Kein "
        "Sprechtext ausser hoechstens 2-3 Kernsaetzen."
    ),
    "spoken": (
        "Sprechtext in Abschnitten: je Abschnitt eine Ueberschrift (**...**), "
        "dann Zeilen \"NAME: ...\". Interviewstellen woertlich im Original als "
        "eigene Zeile: > *Interview quote (N):* \"...\". Kurze Bruecken der "
        "Performer zwischen den Stimmen, Musik-Cues in [eckigen Klammern]."
    ),
    "instructions": (
        "Fuer diesen Moment: **Thema** (mit Interview quote im Original), "
        "**Handlungsanweisung** je Person (WER TUT WAS), **Einstiegssaetze** "
        "der Eingeweihten (2-4, in der Sprache, in der gespielt wird), "
        "**KAMERA** (Position/Einstellung), **ABBRUCH** (wann und wie)."
    ),
    "moment": (
        "Fuer diesen Moment: **Ort / Modus** (🎤 Mikrofon · 👂 1:1 geflüstert, "
        "Ich-Form · 👥 Kollektiv), **Wer** (Voce 1-5), **Wand/Klang** in einer "
        "Zeile ([VIDEO: ...] als Platzhalter), die Interview quotes im Original "
        "als > *Interview quote (N):* \"...\", **Uebergang** (wohin wandert die "
        "Aufmerksamkeit)."
    ),
}
_TEXT_SCHREIBE = "Ich schreibe das Stage Script fuer Szene {nummer}."
_TEXT_AENDERE = "Ich schreibe das Stage Script fuer Szene {nummer} neu."
_TEXT_LAEUFT = "Ich schreibe gerade noch -- gleich."
_TEXT_FEHLER = "Das Stage Script fuer Szene {nummer} hat nicht geklappt. Sagt einfach nochmal Bescheid."
_TEXT_FERTIG = (
    "Szene {nummer} von {gesamt} ({titel}) steht im Script-Tab. Lest sie dort -- "
    "passt sie so? Sonst sagt mir, was anders sein soll."
)
_TEXT_NICHT_DRAN = "Diese Szene ist gerade nicht dran -- gespeichert habe ich nichts."
#: Statt der stummen Ablehnung (Live-Befund G2, siehe ``bestaetige``): die
#: wirklich offene (fruehere) Szene steht schon mit Text da und bekommt hier
#: ihre eigene Zeile samt Yes/No-Leiste (``zeige``).
_TEXT_ERST_VORHERIGE = "Zuerst Szene {nummer} speichern -- die steht noch offen."
_TEXT_KEIN_ZIEL = "Alle Szenen sind gespeichert. Welche wollt ihr aendern?"
#: Bestaetigung einer Notiz zu einer noch nicht geschriebenen oder gerade
#: laufenden Szene (Padua Quickfix 08.10.2026, Punkt 1) -- ``erkenner.
#: _starte_stagescript_notiz``.
_TEXT_NOTIZ_NOTIERT = "Notiert fuer Szene {nummer}: {notiz}"
_TEXT_ALLES_FERTIG = "Das Stage Script ist fertig. Lest es im Script-Tab."
#: Klaerung statt Neuschreiben (Padua Quickfix 08.10.2026, ``ist_frage_oder_unklar``).
_TEXT_ABBRUCH = "Ok, ich aendere Szene {nummer} nicht."
_TEXT_STAND_FERTIG = "Ja, Szene {nummer} steht schon im Script-Tab."
_TEXT_STAND_OFFEN = "Noch nicht -- Szene {nummer} ist noch nicht geschrieben."
_TEXT_WAS_AENDERN = "Was soll sich an Szene {nummer} aendern? Schreibt es in einer Nachricht."
_ANTWORT_GESPEICHERT = "Szene {nummer} gespeichert"
_JOURNAL_GESPEICHERT = "Stage Script Szene {nummer} gespeichert: {titel}"
#: Aenderung im Chat statt Wall of Text (Birk 08.10.2026 ~14:00): die
#: Diff-Nachricht nach jeder gespeicherten Szenenaenderung (``diff_nachricht``).
_TEXT_DIFF_KOPF = "Szene {nummer} von {gesamt} -- Aenderung: {zusammenfassung}"
_TEXT_DIFF_REST = "Der Rest der Szene bleibt gleich."
_TEXT_DIFF_ENTFERNT = "Entfernt: {auszug}"
_TEXT_DIFF_NEUSCHRIEBEN = "Szene {nummer} fast komplett neu geschrieben -- lest sie im Script-Tab."
_TEXT_DIFF_ZUSAMMENFASSUNG_ZAHLEN = "{geaendert} Absaetze geaendert, {neu} neu, {geloescht} entfernt"


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
#: Morgen-Auftrag 4, Nachtrag 2 (08.10.2026): die an die Gruppe gesendeten
#: Statuszeilen italienisch, nur fuer Chats aus
#: ``workshop.italienisch_ab_phase6_chats()`` -- der Prompt-Aufbau
#: (``baue_nutzertext``, oben) bleibt auf ``T``: er geht ans Modell, nicht
#: an die Gruppe, und braucht die Umstellung nicht (Stage Script selbst
#: bleibt zweisprachig, siehe Modul-Docstring).
_T_IT = sprache.Texte(__name__, sprachcode="it")


def _T(chat_id: int) -> sprache.Texte:
    return _T_IT if chat_id in workshop.italienisch_ab_phase6_chats() else T
