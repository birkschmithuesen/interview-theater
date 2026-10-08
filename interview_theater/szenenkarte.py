"""Die Szenenkarten von Phase 6 (Padua-Phasenumbau, Birk, Live-Workshop
07.10.2026 ~18:12, Profilschalter ``[karten] aktiv``,
``workshop.szenenkarten_aktiv``).

Phase 5 waehlt nur noch Interviews aus; Phase 6 macht daraus EINE Karte je
Szene bzw. Moment -- auf einen Blick, statt Prosa:

* ``typ``: ``description`` (Ablauf beschrieben) · ``spoken`` (Sprechtext) ·
  ``instructions`` (Handlungsanweisungen) · ``moment`` (Moment im Raum);
* ``worum`` (1 Satz) · ``ort`` · ``wer`` · ``punkte`` (3-6, was passiert);
* ``zitate`` -- hoechstens 5 der von der Gruppe uebernommenen Stellen, IMMER im
  Originalwortlaut aus der Datenbank (das Modell waehlt nur Nummern) mit
  Interviewnummer;
* ``fragen`` -- offene Fragen an die Gruppe.

Eine Karte nach der anderen ("one scene at a time"): die erste Szene ohne
``karte_bestaetigt_am`` ist dran. "Yes, save" nimmt sie ab, "No, change" +
Textnachricht schreibt sie mit der Notiz neu. Nach der letzten Karte laeuft
die Gesamtpruefung einmal ueber alle Karten (``gesamtpruefung``), danach das
Angebot "Weiter zu Phase 7".

**Solange eine Karte offene Fragen hat** (``karte.fragen``), ersetzen
"Clear the questions" / "Skip questions" die Knoepfe "Yes, save" / "No,
change" (``zeige``) -- eine Karte mit offenen Fragen laesst sich serverseitig
nicht speichern (``bestaetige``, Birk 08.10.2026 ~09:20: eine Gruppe druecke
"No, change" mit einer Notiz zu den Fragen, und der Neubau loeschte sie
klammheimlich). "Skip questions" verwirft alle offenen Fragen der Karte auf
einmal (``ueberspringe_fragen`` -- waren unpassend, nicht ungeklaert, kein
Modellaufruf). "Clear the questions" stellt sie nacheinander im Chat
(``starte_fragenklaerung``/``beantworte_frage``) -- EIN Modellaufruf nach der
letzten Antwort baut die Karte mit allen Antworten neu; der Klaerungsstand
liegt in ``szene.karte_klaerung`` (DB, ueberlebt einen Neustart -- anders als
``szenenfolge._regienotiz_erwartet``).

Die Knopf- und Chatwege bleiben die von ``ueberarbeitung`` (``weiter_6``,
``bestaetige_szene_6``, ``ueberarbeite``, ``nimm_ab``) -- sie verzweigen
unter dem Schalter hierher. Material aus Phase 5 geht vollstaendig ein und
wird nie geloescht: uebernommene Stellen, Kurzform (``szenenkern``),
Phase-5-Gespraech, Logline/Uebersicht.

Kein Modellaufruf im Aufrufer-Thread (Zusage 2): ``starte`` gibt an einen
eigenen Thread ab."""

from __future__ import annotations

import json
import logging
import re
import threading

from interview_theater import anweisungen, modellwahl, repo, szene_claude, workshop

log = logging.getLogger(__name__)

ART = "szenenkarte"
PHASE = 6
TYPEN = ("description", "spoken", "instructions", "moment")
#: Der Modus eines Moments (G3: Orts-Partitur im Script-Tab).
MODI = ("microphone", "one_to_one", "collective", "none")
PUNKTE_MAX = 6
ZITATE_MAX = 5
FRAGEN_MAX = 3
ZEICHEN = 120

SCHEMA = {
    "type": "object",
    "properties": {
        "typ": {"type": "string", "enum": list(TYPEN),
                "description": "description = the course of action is described; "
                               "spoken = a spoken text will be written; instructions = "
                               "instructions for the performers (social experiment, "
                               "film); moment = a moment in the room (immersive)."},
        "modus": {"type": "string", "enum": list(MODI),
                  "description": "Only for typ moment: where the attention is -- "
                                 "microphone, one_to_one (whispered 1:1) or collective "
                                 "(everyone together); otherwise none."},
        "worum": {"type": "string", "description": "One sentence: what this scene is about."},
        "ort": {"type": "string", "description": "Where it happens (place / spot in the room), short."},
        "wer": {"type": "string", "description": "Who is in it, short."},
        "punkte": {"type": "array", "items": {"type": "string"},
                   "description": "3 to 6 short points: what happens, in order. "
                                  "Each point about one line, at most 120 characters."},
        "zitate": {"type": "array", "items": {"type": "integer"},
                   "description": "Numbers of at most 5 interview passages from the "
                                  "list that this scene uses, strongest first."},
        "questions": {"type": "array", "items": {"type": "string"},
                   "description": "0 to 3 open questions the group still has to decide."},
    },
    "required": ["typ", "modus", "worum", "ort", "wer", "punkte", "zitate", "questions"],
    "additionalProperties": False,
}


def aktiv() -> bool:
    return workshop.szenenkarten_aktiv()


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def _szenen(conn, chat_id: int) -> list:
    return sorted(
        (s for s in repo.hole_szenen(conn, chat_id)
         if s["nummer"] is not None and not s["entfernt_am"]),
        key=lambda s: s["nummer"],
    )


def karte_von(szene) -> dict | None:
    """Die gespeicherte Karte als Dict, oder ``None``."""
    try:
        roh = szene["karte"]
    except (IndexError, KeyError):
        return None
    if not _gesetzt(roh):
        return None
    try:
        karte = json.loads(roh)
    except ValueError:
        return None
    return karte if isinstance(karte, dict) else None


def aktuelle_nummer(conn, chat_id: int) -> int | None:
    """Die erste Szene ohne abgenommene Karte."""
    for s in _szenen(conn, chat_id):
        if not _gesetzt(s["karte_bestaetigt_am"]):
            return s["nummer"]
    return None


def _szene_mit_nummer(conn, chat_id: int, nummer: int):
    return next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)


# ---------------------------------------------------------------------------
# Der Modellaufruf
# ---------------------------------------------------------------------------


def baue_nutzertext(conn, chat_id: int, szene, notiz: str | None = None,
                    ueber_claude: bool = False) -> str:
    """Alles, was die Gruppe bis Phase 5 fuer diese Szene entschieden hat --
    und die nummerierte Liste der uebernommenen Stellen zur Wahl.
    ``ueber_claude`` geht unveraendert an ``hintergrund_fuer_prompt`` durch
    (Datenschutz: der Verdichtungen-Block bleibt dort dem Kimi-Weg
    vorbehalten) -- ``erzeuge`` ruft hier mit demselben Wert, den es auch
    an den Modellaufruf gibt."""
    from interview_theater import hintergrund, szenenkern

    # Der Hintergrund kommt aus EINER Funktion (Andockstelle der
    # Phasen-Summary, Birk 07.10.2026 ~19:40).
    zeilen: list[str] = []
    hinten = hintergrund.hintergrund_fuer_prompt(conn, chat_id, ueber_claude=ueber_claude)
    if hinten:
        zeilen.append(hinten)
    alle = [f"{s['nummer']}. {s['titel'] or ''}".strip() for s in _szenen(conn, chat_id)]
    zeilen.append(T._KOPF_ALLE_SZENEN + "\n" + "\n".join(alle))

    teile = [T._KOPF_DIESE.format(nummer=szene["nummer"], titel=szene["titel"] or "")]
    beschreibung = szenenkern.gruppenbeschreibung(conn, chat_id, szene)
    if beschreibung:
        teile.append(T._KOPF_BESCHREIBUNG + " " + beschreibung)
    if _gesetzt(szene["ort"]):
        teile.append(T._KOPF_ORT + " " + szene["ort"].strip())
    namen = [f["name"] for f in repo.szene_figuren(conn, szene["id"])]
    if namen:
        teile.append(T._KOPF_WER + " " + ", ".join(namen))
    for p in szenenkern.kern_punkte(szene):
        teile.append(f"- {p}")
    zeilen.append("\n".join(teile))
    alte = karte_von(szene)
    if alte and notiz:
        zeilen.append(T._KOPF_ALTE_KARTE + "\n" + karte_text(alte, szene, chat_id))
    if notiz:
        zeilen.append(T._KOPF_NOTIZ + "\n" + notiz.strip())
    # Ungekuerzt (Nachtrag Birk 08.10.2026, Vorrang vor Punkt 2): "das
    # wertvollste Material" wird hier nicht auf ZITAT_ZEICHEN_PROMPT gekappt
    # -- anders als der generische Auswahl-Prompt in ``szenenkern.py``.
    liste = [T._KOPF_LISTE]
    for n, (zitat, interview) in enumerate(szenenkern._kandidaten(conn, chat_id, szene), start=1):
        liste.append(f"[{n}] {szenenkern.zitatzeile(zitat, interview)}")
    if len(liste) == 1:
        liste.append(T._KEINE_STELLEN)
    zeilen.append("\n".join(liste))
    return "\n\n".join(zeilen)


def _kappe(text, grenze: int = ZEICHEN) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= grenze:
        return text
    anhang = " …"
    return text[:grenze - len(anhang)].rsplit(" ", 1)[0].rstrip(" ,;:-") + anhang


#: ``ausloeser`` von ``karte_verlauf`` (Birk 08.10.2026 ~10:35) -- "dialog"
#: ist der Neubau nach dem "No, change"-Dialog (Nachtrag ~09:35,
#: ``aktualisiere_mit_dialog`` -> ``starte(..., ausloeser=AUSLOESER_DIALOG)``).
AUSLOESER_ERSTENTWURF = "erstentwurf"
AUSLOESER_AENDERUNG = "aenderung"
AUSLOESER_FRAGEN_GEKLAERT = "fragen_geklaert"
AUSLOESER_FRAGEN_UEBERSPRUNGEN = "fragen_uebersprungen"
AUSLOESER_DIALOG = "dialog"

#: Wortlaut bewusst Englisch (geht in den Prompt, nicht an die Gruppe) --
#: deckungsgleich mit dem Journal-Wortlaut (``T._JOURNAL_FRAGEN_UEBERSPRUNGEN``).
_NOTIZ_FRAGEN_UEBERSPRUNGEN = "questions skipped as not fitting"


def _system_fuer(chat_id: int, art: str) -> str:
    """``anweisungen.hole(art)``, plus den Italienisch-Auftrag fuer Chats
    aus ``workshop.italienisch_ab_phase6_chats()`` (Morgen-Auftrag 4,
    Nachtrag 2 -- eine chat-bezogene Entscheidung, die der profilweite
    Platzhaltermechanismus nicht treffen kann: die Testgruppe teilt sich
    das Profil mit G1-G3, soll aber englisch bleiben)."""
    text = anweisungen.hole(art)
    if chat_id in workshop.italienisch_ab_phase6_chats():
        text += "\n\n" + T._AUFTRAG_AUSGABE_ITALIENISCH
    return text


def erzeuge(conn, klm, e, chat_id: int, nummer: int, notiz: str | None = None,
           ausloeser: str | None = None) -> dict | None:
    """Der EINE Schema-Aufruf je Karte. Speichert und liefert die Karte,
    oder ``None`` bei jedem Fehler (Vorfall ``szenenkarte_fehler``).

    Haengt zugleich eine neue Fassung an den Karten-Verlauf
    (``repo.merke_karte_verlauf``) -- ``ausloeser`` wird, wo der Aufrufer ihn
    nicht kennt (kein Fragen-Spezialfall), aus ``notiz`` abgeleitet:
    keine Notiz -> ``erstentwurf`` (der einzige Aufrufer ohne Notiz ist
    ``weiter``, und der baut nur die allererste Fassung), sonst
    ``aenderung``."""
    from interview_theater import szenenkern

    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        return None
    kandidaten = szenenkern._kandidaten(conn, chat_id, szene)
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    try:
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id,
            system=_system_fuer(chat_id, ART),
            nutzer=baue_nutzertext(conn, chat_id, szene, notiz, ueber_claude=ueber_claude),
            schema=SCHEMA, art=ART,
            ueber_claude=ueber_claude,
        )
        punkte = [_kappe(p) for p in (ergebnis.get("punkte") or []) if str(p).strip()]
        if not punkte or not str(ergebnis.get("worum") or "").strip():
            raise ValueError("Karte ohne Worum oder ohne Punkte")
        gewaehlt: list[int] = []
        for n in ergebnis.get("zitate") or []:
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= len(kandidaten) and n not in gewaehlt:
                gewaehlt.append(n)
        typ = str(ergebnis.get("typ") or "").strip().lower()
        modus = str(ergebnis.get("modus") or "").strip().lower()
        karte = {
            "typ": typ if typ in TYPEN else "description",
            "modus": modus if modus in MODI and typ == "moment" else "none",
            "worum": _kappe(ergebnis.get("worum")),
            "ort": _kappe(ergebnis.get("ort"), 160),
            "wer": _kappe(ergebnis.get("wer"), 160),
            "punkte": punkte[:PUNKTE_MAX],
            "zitate": [
                {"zitat": kandidaten[n - 1][0], "interview": kandidaten[n - 1][1]}
                for n in gewaehlt[:ZITATE_MAX]
            ],
            "fragen": [_kappe(f) for f in (ergebnis.get("questions") or [])
                       if str(f).strip()][:FRAGEN_MAX],
        }
    except Exception:
        log.exception("Szenenkarte fehlgeschlagen, chat_id=%s, nummer=%s", chat_id, nummer)
        try:
            repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                               "szenenkarte_fehler", f"Szene {nummer}: Karte nicht erzeugt")
        except Exception:
            log.exception("Vorfall szenenkarte_fehler nicht geschrieben")
        return None
    repo.setze_szenenkarte(conn, szene["id"], json.dumps(karte, ensure_ascii=False))
    repo.merke_karte_verlauf(
        conn, chat_id, szene["id"], json.dumps(karte, ensure_ascii=False),
        ausloeser or (AUSLOESER_AENDERUNG if notiz else AUSLOESER_ERSTENTWURF), notiz,
    )
    return karte


# ---------------------------------------------------------------------------
# Anzeige
# ---------------------------------------------------------------------------


def karte_text(karte: dict, szene, chat_id: int) -> str:
    """Die Karte als Chatnachricht (Markdown wie im Web-Chat)."""
    t = _T(chat_id)
    titel = (szene["titel"] or "").strip()
    kopf = t._KARTE_KOPF.format(nummer=szene["nummer"], titel=titel).rstrip(" —")
    zeilen = [f"**{kopf}** · *{t.TYP_BESCHRIFTUNG.get(karte.get('typ'), karte.get('typ') or '')}*"]
    if karte.get("worum"):
        zeilen.append(karte["worum"])
    if karte.get("ort"):
        zeilen.append(f"**{t._ZEILE_ORT}** {karte['ort']}")
    if karte.get("wer"):
        zeilen.append(f"**{t._ZEILE_WER}** {karte['wer']}")
    if karte.get("punkte"):
        zeilen.append(f"**{t._ZEILE_PUNKTE}**")
        zeilen += [f"- {p}" for p in karte["punkte"]]
    if karte.get("zitate"):
        zeilen.append(f"**{t._ZEILE_ZITATE}**")
        for z in karte["zitate"]:
            quelle = f" ({z['interview']})" if z.get("interview") else ""
            zeilen.append(f"- *“{z['zitat']}”*{quelle}")
    if karte.get("fragen"):
        zeilen.append(f"**{t._ZEILE_FRAGEN}**")
        zeilen += [f"- {f}" for f in karte["fragen"]]
    return "\n".join(zeilen)


def im_cothinker(conn, chat_id: int) -> bool:
    """Leben die Karten im CoThinker-Tab (Birk 07.10.2026 ~19:25)? Nur fuer
    Web-Gruppen mit CoThinker (``diskussion_aktiv``); Telegram behaelt die
    Karte im Chat."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    kanal = (gruppe["kanal"] if gruppe is not None and "kanal" in gruppe.keys() else None)
    return kanal == "web" and workshop.diskussion_aktiv()


def frage_nach_aenderung(conn, tg, e, chat_id: int, nummer: int) -> None:
    """"No, change" auf der Karte im CoThinker -- startet den Dialog
    (``starte_dialog``, Nachtrag Birk 08.10.2026 ~09:35: KEIN
    Wartezustand mehr, der die naechste Nachricht abfaengt)."""
    starte_dialog(conn, tg, e, chat_id, nummer)


# ---------------------------------------------------------------------------
# Der "No, change"-Dialog (Birk 08.10.2026 ~09:35, Nachtrag, Vorrang)
# ---------------------------------------------------------------------------
#
# Ersetzt den alten Weg "No, change" -> erwarte_regienotiz -> naechste
# Nachricht ist automatisch die Aenderungsnotiz -> aendere() baut sofort neu
# (kein Dialog, keine Rueckfrage -- Birk: "wirklich komisch"). Jetzt: "No,
# change" markiert die Karte als im Dialog (``karte_dialog_am``, DB); der
# Chat bleibt ab da ein GEWOEHNLICHES Gespraech mit dem Gespraechsbot, der
# die Karte im Kontext sieht (``dialog_kontextblock``, eingehaengt in
# ``kontext._bloecke``) und angewiesen ist zu diskutieren statt selbst neu
# zu bauen. Erkennt das Gespraechsmodell eine klare Aenderung, fasst es sie
# in einem VORSCHLAG-KARTE-AENDERUNG-Block zusammen (``vorschlag.py`` --
# derselbe Marker-Mechanismus wie ueberall sonst im Projekt, kein zweiter
# Modellaufruf); ``knoepfe.basis.sende_mit_speicherleiste`` haengt dafuer
# "Update the card" / "Keep the card" an -- IMMER an die neueste
# Zusammenfassung, eine aeltere Leiste verfaellt (``_nimm_alte_leiste_ab``,
# dieselbe Regel wie ueberall).


def dialog_aktive_nummer(conn, chat_id: int) -> int | None:
    """Die Szenennummer, deren Karte gerade im "No, change"-Dialog ist --
    oder ``None``. DB-gestuetzt (``szene.karte_dialog_am``), ueberlebt also
    einen Neustart."""
    for s in _szenen(conn, chat_id):
        if _gesetzt(s["karte_dialog_am"]):
            return s["nummer"]
    return None


def starte_dialog(conn, tg, e, chat_id: int, nummer: int) -> str:
    """"No, change" auf einer Karte: markiert sie als im Dialog, EIN Satz im
    Chat, danach laeuft das Gespraech normal weiter (``ablauf.antworte``)."""
    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    repo.setze_szenenkarte_dialog(conn, szene["id"], repo._jetzt())
    _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_DIALOG_START.format(nummer=nummer))
    return _T(chat_id)._ANTWORT_DIALOG_GESTARTET


def dialog_kontextblock(conn, chat_id: int) -> str:
    """Block fuer ``kontext._bloecke``: solange eine Karte im Dialog ist,
    bekommt JEDER Gespraechszug sie samt Anweisung, zu diskutieren statt
    selbst neu zu bauen -- die Markerzeile ist Technik, die Gruppe sieht
    sie nie (``vorschlag.ohne_marker``)."""
    nummer = dialog_aktive_nummer(conn, chat_id)
    if nummer is None:
        return ""
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    karte = karte_von(szene) if szene is not None else None
    if karte is None:
        return ""
    return T._KOPF_DIALOG.format(nummer=nummer, karte=karte_text(karte, szene))


def biete_update_knopf(conn, tg, e, chat_id: int, text: str, aenderung: str) -> int:
    """Haengt "Update the card" / "Keep the card" an eine Gespraechsantwort,
    die ``VORSCHLAG KARTE AENDERUNG:`` trug (``sende_mit_speicherleiste``).
    Ohne aktiven Dialog (veralteter Block, Dialog schon beendet) geht der
    Text ohne Knoepfe raus -- kein Raten."""
    from interview_theater import vorschlag
    from interview_theater.knoepfe import basis, szenen as ks

    sauber = vorschlag.ohne_marker(text) or text
    nummer = dialog_aktive_nummer(conn, chat_id)
    if nummer is None:
        return tg.sende(chat_id, sauber)
    basis._nimm_alte_leiste_ab(conn, tg, chat_id, ks.ART_KARTE_UPDATE)
    leiste = [
        ks._knopf(conn, chat_id, T._TEXT_UPDATE_KNOPF, ks.ART_KARTE_UPDATE,
                 f"{nummer}{ks.TRENNER}{aenderung}"),
        ks._knopf(conn, chat_id, T._TEXT_KEEP_KNOPF, ks.ART_KARTE_KEEP, str(nummer)),
    ]
    message_id = basis._mit_leiste(conn, tg, chat_id, sauber, leiste)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, sauber)
    return message_id


def _bewahre_fragen(conn, chat_id: int, nummer: int, alte_fragen: list[str]):
    """Nachbereitung fuer ``starte``: Fragen der alten Karte, die im Neubau
    nicht wieder auftauchen, zurueckholen -- eine Aenderung (egal ob aus
    dem alten Einzel-Notiz-Weg oder dem Dialog) kann eine Frage nur dann
    beantwortet haben, wenn sie wirklich darueber ging (Punkt 3)."""
    if not alte_fragen:
        return None

    def _nach(neue_karte: dict) -> None:
        vorhandene = list(neue_karte.get("fragen") or [])
        fehlende = [f for f in alte_fragen if f not in vorhandene]
        if not fehlende:
            return
        ziel = _szene_mit_nummer(conn, chat_id, nummer)
        if ziel is None:
            return
        aktualisiert = dict(neue_karte)
        aktualisiert["fragen"] = (vorhandene + fehlende)[:FRAGEN_MAX]
        repo.setze_szenenkarte(conn, ziel["id"], json.dumps(
            aktualisiert, ensure_ascii=False))

    return _nach


def aktualisiere_mit_dialog(conn, tg, klm, e, chat_id: int, nummer: int,
                            aenderung: str) -> str:
    """"Update the card": Neubau mit der im Dialog zusammengefassten
    Aenderung als Notiz. Beendet den Dialog; offene Fragen der alten Karte
    bleiben, ausser das Gespraech hat sie beantwortet (``_bewahre_fragen``,
    dieselbe Zusage wie beim alten Einzel-Notiz-Weg, Punkt 3)."""
    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    repo.setze_szenenkarte_dialog(conn, szene["id"], None)
    alte_karte = karte_von(szene)
    alte_fragen = (alte_karte or {}).get("fragen") or []
    starte(conn, tg, klm, e, chat_id, nummer, aenderung.strip(),
          nachbereitung=_bewahre_fragen(conn, chat_id, nummer, alte_fragen),
          ausloeser=AUSLOESER_DIALOG)
    return _T(chat_id)._ANTWORT_KARTE_WIRD_AKTUALISIERT.format(nummer=nummer)


def behalte_karte(conn, tg, e, chat_id: int, nummer: int) -> str:
    """"Keep the card": Dialog beenden, dieselbe Karte wieder zur
    Bestaetigung zeigen -- kein Neubau."""
    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    repo.setze_szenenkarte_dialog(conn, szene["id"], None)
    zeige(conn, tg, e, chat_id, nummer)
    return _T(chat_id)._ANTWORT_KARTE_BEHALTEN.format(nummer=nummer)


def biete_klaerweg_im_dialog(conn, tg, e, chat_id: int, nummer: int) -> None:
    """Spricht die Gruppe im Dialog von den FRAGEN selbst (Punkt 4,
    ``notiz_betrifft_fragen``), bietet der Bot den Klaerweg an statt selbst
    zu antworten -- kein Modellaufruf. Der Dialog bleibt stehen (eine
    Gruppe, die stattdessen doch weiterdiskutieren will, kann das)."""
    from interview_theater.knoepfe import basis, szenen as ks

    text = _T(chat_id)._TEXT_KLAERWEG_ANGEBOT.format(nummer=nummer)
    leiste = [ks._knopf(conn, chat_id, T._TEXT_KLAEREN_KNOPF,
                        ks.ART_KARTE_FRAGEN_KLAEREN, str(nummer))]
    message_id = basis._mit_leiste(conn, tg, chat_id, text, leiste)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)


def zeige(conn, tg, e, chat_id: int, nummer: int, *, im_chat: bool = False) -> int | None:
    """Die Karte mit "Yes, save" / "No, change" -- dieselben Knopfarten wie
    unter einem Szenentext, damit Knopf- und Chatweg gleich wirken.

    **Solange die Karte offene Fragen hat** (``karte.fragen``), stehen statt
    dessen NUR "Clear the questions" / "Skip questions" darunter -- "Yes,
    save" waere ohnehin abgelehnt (``bestaetige``), und "No, change" braucht
    es neben "Clear the questions" nicht (Birk 08.10.2026 ~09:25/09:30).

    Im CoThinker-Modus (``im_cothinker``) steht die Karte selbst im
    CoThinker-Tab; der Chat bekommt nur eine Zeile -- AUSSER die Karte ist
    das Ergebnis einer Klaerung im Chat (``im_chat``): dann steht sie dort
    ganz, zur Bestaetigung mit "Yes, save card" / "No, change again" (Birk:
    was im Chat geklaert wurde, wird bestaetigt, nie still gespeichert)."""
    from interview_theater import knoepfe
    from interview_theater.knoepfe import basis, szenen as ks

    szene = _szene_mit_nummer(conn, chat_id, nummer)
    karte = karte_von(szene) if szene is not None else None
    if karte is None:
        return None
    basis._nimm_alte_leiste_ab(conn, tg, chat_id, ks.ART_SZENE_PASST)
    basis._nimm_alte_leiste_ab(conn, tg, chat_id, ks.ART_KARTE_FRAGEN_KLAEREN)
    gesamt = len(_szenen(conn, chat_id))
    cothinker = im_cothinker(conn, chat_id)
    if cothinker and not im_chat:
        return _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_IM_COTHINKER.format(
            nummer=nummer, gesamt=gesamt))
    offene_fragen = karte.get("fragen") or []
    if offene_fragen:
        text = karte_text(karte, szene, chat_id) + "\n\n" + _T(chat_id)._TEXT_FRAGEN_OFFEN.format(
            nummer=nummer, gesamt=gesamt)
        # Knopf-Beschriftungen bleiben IMMER auf der gewoehnlichen ``T``, nicht
        # ``T_IT`` (Morgen-Auftrag 4: "Knoepfe bleiben EN").
        leiste = [
            ks._knopf(conn, chat_id, T._TEXT_KLAEREN_KNOPF,
                     ks.ART_KARTE_FRAGEN_KLAEREN, str(nummer)),
            ks._knopf(conn, chat_id, T._TEXT_UEBERSPRINGEN_KNOPF,
                     ks.ART_KARTE_FRAGEN_UEBERSPRINGEN, str(nummer)),
        ]
    else:
        text = karte_text(karte, szene, chat_id) + "\n\n" + _T(chat_id)._TEXT_FRAGE.format(
            nummer=nummer, gesamt=gesamt)
        ja = T._TEXT_KARTE_JA_KNOPF if cothinker else knoepfe.T.TEXT_WEITER_KNOPF
        nein = T._TEXT_KARTE_NOCHMAL_KNOPF if cothinker else knoepfe.T.TEXT_NEIN_AENDERN_KNOPF
        leiste = [
            ks._knopf(conn, chat_id, ja, ks.ART_SZENE_PASST, str(nummer)),
            ks._knopf(conn, chat_id, nein, ks.ART_SZENE_ANDERS, str(nummer)),
        ]
    message_id = basis._mit_leiste(conn, tg, chat_id, text, leiste)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


def _sende(conn, tg, e, chat_id: int, text: str):
    message_id = tg.sende(chat_id, text)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    return message_id


# ---------------------------------------------------------------------------
# Der Schrittweg
# ---------------------------------------------------------------------------

_SPERREN: dict[int, threading.Lock] = {}
_SPERREN_LOCK = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _SPERREN_LOCK:
        return _SPERREN.setdefault(chat_id, threading.Lock())


def laeuft(chat_id: int) -> bool:
    return _sperre_fuer(chat_id).locked()


def starte(conn, tg, klm, e, chat_id: int, nummer: int,
           notiz: str | None = None, *, nachbereitung=None,
           ausloeser: str | None = None) -> threading.Thread | None:
    """Erzeugt (oder ueberarbeitet mit ``notiz``) die Karte ``nummer`` im
    eigenen Thread und zeigt sie danach. ``None``, wenn schon eine Karte
    dieser Gruppe entsteht (dann eine Zeile statt Stille).

    ``nachbereitung`` (optional, ``dict -> bool | None``) laeuft im selben
    Thread NACH dem Modellaufruf und VOR der Anzeige -- fuer Schreibzugriffe,
    die vom frischen Modellergebnis abhaengen (Fragenklaerung: erzwungene
    "[OPEN] ..."-Punkte, Rueckbau einer anderen Aenderung: Fragen der alten
    Karte bewahren). Liefert sie ``False``, faellt die Anzeige aus -- die
    Nachbereitung hat selbst schon etwas geschickt (z. B. die naechste
    Klaerungsrunde)."""
    sperre = _sperre_fuer(chat_id)
    if klm is None or not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_LAEUFT)
        return None
    _sende(conn, tg, e, chat_id, (_T(chat_id)._TEXT_AENDERE if notiz else _T(chat_id)._TEXT_SCHREIBE).format(
        nummer=nummer))

    def _lauf() -> None:
        try:
            karte = erzeuge(conn, klm, e, chat_id, nummer, notiz, ausloeser=ausloeser)
            if karte is None:
                _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_FEHLER.format(nummer=nummer))
                return
            if nachbereitung is not None and nachbereitung(karte) is False:
                return
            zeige(conn, tg, e, chat_id, nummer, im_chat=bool(notiz))
        finally:
            # Die Sperre gilt fuer den GANZEN Lauf, nicht nur den
            # Modellaufruf (anders bis 08.10.2026): die Nachbereitung einer
            # Fragenklaerung kann selbst eine neue Runde anstossen
            # (``starte_fragenklaerung``) -- bis die Karte angezeigt ist,
            # soll ein zweiter Druck "laeuft noch" sehen, nicht eine Karte
            # mittendrin.
            sperre.release()

    faden = threading.Thread(target=_lauf, daemon=True)
    try:
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


def weiter(conn, tg, klm, e, chat_id: int, *, aus_eintritt: bool = False):
    """Was in Phase 6 als naechstes dran ist: die aktuelle Karte zeigen
    (vorhanden) oder erzeugen (fehlt); sind alle abgenommen, die
    Gesamtpruefung einmal und danach das Angebot Phase 7."""
    from interview_theater import knoepfe

    nummer = aktuelle_nummer(conn, chat_id)
    if nummer is not None:
        szene = _szene_mit_nummer(conn, chat_id, nummer)
        if karte_von(szene) is not None:
            zeige(conn, tg, e, chat_id, nummer)
            return None
        return starte(conn, tg, klm, e, chat_id, nummer)
    if not _szenen(conn, chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_KEINE_SZENEN)
        return None
    stand = repo.hole_arbeitsstand(conn, chat_id)
    geprueft = bool(stand is not None and _gesetzt(stand["karten_geprueft_am"]))
    if geprueft:
        knoepfe.biete_phase(conn, tg, chat_id, _T(chat_id)._TEXT_ALLE_GESPEICHERT, 7)
        return None
    return starte_gesamtpruefung(conn, tg, klm, e, chat_id)


def bestaetige(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    """"Yes, save" auf einer Karte (Knopf oder Chat).

    Serverseitig abgelehnt, solange die Karte offene Fragen hat (Birk
    08.10.2026 ~09:20) -- nicht nur die Anzeige bietet dann andere Knoepfe
    an (``zeige``): ein veralteter Knopf, ein Befehl (``/karte_ja``) oder der
    Erkenner duerfen eine Karte mit offenen Fragen ebenfalls nicht
    speichern."""
    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_LAEUFT)
        return _T(chat_id)._TEXT_LAEUFT
    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    karte = karte_von(szene) if szene is not None else None
    if karte is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    if karte.get("fragen"):
        zeige(conn, tg, e, chat_id, nummer)
        return _T(chat_id)._TEXT_FRAGEN_OFFEN_ABGELEHNT
    repo.setze_szenenkarte_bestaetigt(conn, szene["id"])
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          _T(chat_id)._JOURNAL_GESPEICHERT.format(nummer=nummer,
                                                        titel=szene["titel"] or "").strip(),
                          quelle="knopf")
    antwort = _T(chat_id)._ANTWORT_GESPEICHERT.format(nummer=nummer)
    weiter(conn, tg, klm, e, chat_id)
    return antwort


def aendere(conn, tg, klm, e, chat_id: int, notiz: str, nummer: int | None = None):
    """"No, change" + Textnachricht, oder Rueckmeldung im Chat: die Karte
    (genannte oder aktuelle) neu, mit der Notiz und der alten Karte.

    **Eine Aenderung darf offene Fragen nie still loeschen** (Birk
    08.10.2026 ~09:20, Punkt 3): spricht die Notiz erkennbar von den FRAGEN
    selbst (``notiz_betrifft_fragen`` -- "the questions", "let's discuss the
    questions", "domande"), springt sie direkt in den Klaerweg
    (``starte_fragenklaerung``) statt blind neu zu bauen -- genau der Fall
    vom Workshop: "No, change" + "The questions clearing" baute die Karte
    neu und loeschte die Fragen klammheimlich. Sonst (eine Notiz, die nichts
    mit den Fragen zu tun hat) bewahrt die Nachbereitung jede Frage der
    alten Karte, die im Neubau nicht wieder auftaucht -- eine unverwandte
    Notiz kann sie nicht beantwortet haben."""
    n = nummer if nummer is not None else aktuelle_nummer(conn, chat_id)
    if n is None:
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_KEIN_ZIEL)
        return None
    szene = _szene_mit_nummer(conn, chat_id, n)
    alte_karte = karte_von(szene) if szene is not None else None
    alte_fragen = (alte_karte or {}).get("fragen") or []
    if alte_fragen and notiz_betrifft_fragen(notiz):
        starte_fragenklaerung(conn, tg, e, chat_id, n)
        return None
    return starte(conn, tg, klm, e, chat_id, n, notiz,
                 nachbereitung=_bewahre_fragen(conn, chat_id, n, alte_fragen))


# ---------------------------------------------------------------------------
# Offene Fragen klaeren ("Clear the questions" / "Skip questions")
# ---------------------------------------------------------------------------

#: Wortmuster, mit denen eine Gruppe erkennbar die FRAGEN meint, nicht den
#: Inhalt der Karte ("The questions clearing", "let's discuss the
#: questions", italienisch "domande") -- Birk 08.10.2026 ~09:20, Punkt 3: so
#: eine Notiz darf nie einen stillen Neubau ohne die Fragen ausloesen,
#: sondern springt direkt in den Klaerweg.
_FRAGEN_NOTIZ_MUSTER = re.compile(r"\bquestions?\b|\bdomande?\b", re.IGNORECASE)

#: Eine Antwort, die die Frage bewusst offen laesst (Birk 08.10.2026 ~09:30:
#: "speichern erst, wenn keine [Frage] offen ist" -- also muss "skip" die
#: Frage KLAEREN, nicht blockieren). Nur ganze Antworten, kein Teilsatz --
#: "I don't know yet, but maybe" ist ein Inhalt, keine Ueberspringung.
_SKIP_MUSTER = re.compile(
    r"^\s*(skip|i\s*don'?t\s*know|dont'?\s*know|no\s*idea|idk|keine\s*ahnung|"
    r"non\s*lo\s*so|non\s*saprei)\s*[.!]?\s*$",
    re.IGNORECASE,
)


def notiz_betrifft_fragen(notiz: str | None) -> bool:
    """Spricht die Notiz erkennbar von den offenen Fragen der Karte?"""
    return bool(_FRAGEN_NOTIZ_MUSTER.search(notiz or ""))


def ist_skip(text: str | None) -> bool:
    """Will die Gruppe diese EINE Frage bewusst offen lassen?"""
    return bool(_SKIP_MUSTER.match((text or "").strip()))


def _klaerung_von(szene) -> dict | None:
    """Der laufende Klaerungsstand (``szene.karte_klaerung``, JSON) -- oder
    ``None``, wenn gerade keine Frage-fuer-Frage-Runde laeuft."""
    try:
        roh = szene["karte_klaerung"]
    except (IndexError, KeyError):
        return None
    if not _gesetzt(roh):
        return None
    try:
        klaerung = json.loads(roh)
    except ValueError:
        return None
    return klaerung if isinstance(klaerung, dict) else None


def aktive_klaerung(conn, chat_id: int) -> tuple[int, dict] | None:
    """(Szenennummer, Klaerungsstand) der Karte, die gerade eine Antwort auf
    eine offene Frage erwartet -- oder ``None``. DB-gestuetzt
    (``szene.karte_klaerung``): ein Neustart mitten in der Runde verliert sie
    nicht, anders als ``szenenfolge._regienotiz_erwartet``."""
    nummer = aktuelle_nummer(conn, chat_id)
    if nummer is None:
        return None
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    if szene is None:
        return None
    klaerung = _klaerung_von(szene)
    if klaerung is None:
        return None
    return nummer, klaerung


def starte_fragenklaerung(conn, tg, e, chat_id: int, nummer: int, *, runde: int = 1) -> str:
    """"Clear the questions": stellt die offenen Fragen der Karte
    nacheinander im Chat, eine pro Nachricht. Kein Modellaufruf.

    Statuszeilen ueber ``_T(chat_id)`` (Morgen-Auftrag 4): deterministische
    Zeilen ab Phase 6 italienisch fuer gelistete Chats, wie der Rest des
    Moduls."""
    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    karte = karte_von(szene) if szene is not None else None
    fragen = (karte or {}).get("fragen") or []
    if not fragen:
        zeige(conn, tg, e, chat_id, nummer)
        return _T(chat_id)._ANTWORT_GESPEICHERT.format(nummer=nummer)
    # Der "No, change"-Dialog (Nachtrag Punkt 4) ist damit erledigt --
    # Klaeren und Diskutieren schliessen sich fuer dieselbe Karte aus.
    repo.setze_szenenkarte_dialog(conn, szene["id"], None)
    klaerung = {"index": 0, "antworten": [], "runde": runde}
    repo.setze_szenenkarte_klaerung(conn, szene["id"], json.dumps(klaerung))
    _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_FRAGE_N_VON_M.format(
        n=1, gesamt=len(fragen), frage=fragen[0]))
    return _T(chat_id)._ANTWORT_FRAGEN_KLAEREN


def ueberspringe_fragen(conn, tg, e, chat_id: int, nummer: int) -> str:
    """"Skip questions": alle offenen Fragen dieser Karte auf einmal
    verwerfen -- waren unpassend, nicht ungeklaert (Birk 08.10.2026 ~09:30).
    Punkte und Zitate bleiben unberuehrt, kein Modellaufruf.

    Der Journal-Wortlaut bleibt ausdruecklich auf ``T`` (Englisch) --
    Birk gibt ihn woertlich vor ("Card N: questions skipped as not
    fitting"), anders als die uebrigen Statuszeilen auf ``T_IT``."""
    if nummer != aktuelle_nummer(conn, chat_id):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    karte = karte_von(szene) if szene is not None else None
    if karte is None or not karte.get("fragen"):
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_NICHT_DRAN)
        return _T(chat_id)._TEXT_NICHT_DRAN
    neue_karte = dict(karte)
    neue_karte["fragen"] = []
    repo.setze_szenenkarte(conn, szene["id"], json.dumps(neue_karte, ensure_ascii=False))
    repo.setze_szenenkarte_klaerung(conn, szene["id"], None)
    repo.merke_karte_verlauf(
        conn, chat_id, szene["id"], json.dumps(neue_karte, ensure_ascii=False),
        AUSLOESER_FRAGEN_UEBERSPRUNGEN, _NOTIZ_FRAGEN_UEBERSPRUNGEN,
    )
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          T._JOURNAL_FRAGEN_UEBERSPRUNGEN.format(nummer=nummer).strip(),
                          quelle="web")
    zeige(conn, tg, e, chat_id, nummer)
    return _T(chat_id)._ANTWORT_FRAGEN_UEBERSPRUNGEN.format(nummer=nummer)


# ---------------------------------------------------------------------------
# Verfeinerungs-Zeilen fuer Phase 7 (Birk 08.10.2026 ~10:35): was die Gruppe
# an dieser Karte in Phase 6 geaendert hat -- Notiz/Antwort und der
# deterministische Feld-Diff, aus ``karte_verlauf``. Kein Modellaufruf, kein
# Spracheinhaengepunkt: der Wortlaut geht in den Prompt, nicht an die Gruppe.
# ---------------------------------------------------------------------------

#: Felder, die ein Diff zwischen zwei Kartenfassungen vergleicht --
#: ``fragen`` bewusst nicht (die veraendert sich bei "Skip questions" ohne
#: inhaltliche Verfeinerung der Karte).
_DIFF_FELDER = ("typ", "modus", "worum", "ort", "wer", "punkte", "zitate")


def _diff_wert(wert) -> str:
    if wert is None:
        return "(none)"
    if isinstance(wert, list):
        return "(empty)" if not wert else "; ".join(str(e) for e in wert)
    return str(wert)


def diff_karten(alt: dict, neu: dict) -> list[str]:
    """Welche ``_DIFF_FELDER`` sich zwischen zwei Kartenfassungen
    unterscheiden, als lesbare Zeilen -- deterministisch, kein Modellaufruf."""
    unterschiede = []
    for feld in _DIFF_FELDER:
        alter_wert, neuer_wert = alt.get(feld), neu.get(feld)
        if alter_wert != neuer_wert:
            unterschiede.append(
                f"{feld}: {_diff_wert(alter_wert)} -> {_diff_wert(neuer_wert)}")
    return unterschiede


def verfeinerungs_zeilen(conn, chat_id: int, szene) -> list[str]:
    """Eine Zeile je Verfeinerung dieser Karte in Phase 6: was die Gruppe
    wollte (Notiz/Antwort) und was sich dadurch an der Karte geaendert hat
    (``diff_karten``). Leer, wenn die Karte nie ueberarbeitet wurde.

    Die erste Fassung ist nur dann die Grundlage ohne eigene Zeile, wenn sie
    wirklich ``erstentwurf`` ist. Ein Nachtrag aus dem Chat (``scripts.
    karten_verlauf_nachtrag``) kennt den echten Erstentwurf oft nicht -- die
    frueheste bekannte Fassung ist dann schon eine Aenderung und bekommt
    trotzdem eine Zeile (nur ohne Diff, weil keine Vorgaenger-Fassung da
    ist). Sonst verschwaende genau der haeufigste Fall (eine Karte, eine
    nachgetragene Korrektur) spurlos."""
    reihen = repo.karte_verlauf(conn, chat_id, szene["id"])
    zeilen = []
    vorherige_karte = None
    for reihe in reihen:
        neue_karte = json.loads(reihe["karte_json"])
        ist_verfeinerung = vorherige_karte is not None or reihe["ausloeser"] != AUSLOESER_ERSTENTWURF
        if ist_verfeinerung:
            teile = []
            notiz = reihe["notiz_text"]
            if notiz:
                teile.append(f'wanted: "{notiz}"')
            if vorherige_karte is not None:
                unterschiede = diff_karten(vorherige_karte, neue_karte)
                if unterschiede:
                    teile.append("changed: " + "; ".join(unterschiede))
            if teile:
                zeilen.append(" -- ".join(teile))
        vorherige_karte = neue_karte
    return zeilen


def _klaerungsnotiz(fragen: list[str], antworten: list[str | None]) -> str:
    """Die Notiz fuer den EINEN Neubau nach der letzten Antwort: alle Fragen
    mit ihrer Antwort, oder dem Vermerk, dass die Gruppe sie offen laesst."""
    zeilen = [T._KOPF_KLAERUNG]
    for frage, antwort in zip(fragen, antworten):
        if antwort is None:
            zeilen.append(T._ZEILE_KLAERUNG_OFFEN.format(frage=frage))
        else:
            zeilen.append(T._ZEILE_KLAERUNG_BEANTWORTET.format(frage=frage, antwort=antwort))
    return "\n".join(zeilen)


def beantworte_frage(conn, tg, klm, e, chat_id: int, text: str) -> bool:
    """Verarbeitet eine Gruppennachricht als Antwort auf die Frage, die
    ``starte_fragenklaerung``/die vorige Antwort gerade gestellt hat.
    Liefert ``True``, wenn diese Nachricht dadurch beantwortet ist (der
    Gespraechszug faellt dann aus -- dieselbe Bauart wie
    ``szenenfolge.nimm_regienotiz``, nur DB-gestuetzt).

    "skip"/"I don't know" (``ist_skip``) laesst die Frage bewusst offen: sie
    wird nicht blockierend neu gefragt, sondern spaeter als "[OPEN] ..."-Punkt
    in die Karte uebernommen (Birk: "speichern erst, wenn keine [Frage] mehr
    offen ist" -- die Karte muss also IMMER fertig werden koennen)."""
    gefunden = aktive_klaerung(conn, chat_id)
    if gefunden is None:
        return False
    nummer, klaerung = gefunden
    szene = _szene_mit_nummer(conn, chat_id, nummer)
    karte = karte_von(szene) if szene is not None else None
    fragen = (karte or {}).get("fragen") or []
    index = int(klaerung.get("index") or 0)
    if index >= len(fragen):
        repo.setze_szenenkarte_klaerung(conn, szene["id"], None)
        return False
    antworten = list(klaerung.get("antworten") or [])
    antworten.append(None if ist_skip(text) else text.strip())
    index += 1
    if index < len(fragen):
        repo.setze_szenenkarte_klaerung(conn, szene["id"], json.dumps(
            {"index": index, "antworten": antworten, "runde": klaerung.get("runde", 1)}))
        _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_FRAGE_N_VON_M.format(
            n=index + 1, gesamt=len(fragen), frage=fragen[index]))
        return True
    # Letzte Frage beantwortet: Journal je Frage, dann EIN Neubau mit allen
    # Antworten (weniger Wartezeit/Kosten als je Antwort neu zu bauen, und
    # die Karte springt der Gruppe nicht dreimal unter der Hand weg).
    runde = int(klaerung.get("runde") or 1)
    for frage, antwort in zip(fragen, antworten):
        if antwort is None:
            repo.schreibe_journal(conn, chat_id, "entschieden",
                                  _T(chat_id)._JOURNAL_FRAGE_OFFEN_GELASSEN.format(
                                      nummer=nummer, frage=frage).strip(),
                                  quelle="chat")
        else:
            repo.schreibe_journal(conn, chat_id, "entschieden",
                                  _T(chat_id)._JOURNAL_FRAGE_BEANTWORTET.format(
                                      nummer=nummer, frage=frage, antwort=antwort).strip(),
                                  quelle="chat")
    repo.setze_szenenkarte_klaerung(conn, szene["id"], None)

    def _nachbereitung(neue_karte: dict) -> bool | None:
        """Erzwingt die "[OPEN] ..."-Punkte fuer uebersprungene Fragen
        (deterministisch -- kein Modell soll diese Entscheidung treffen
        oder wieder vergessen), und laesst -- hoechstens EINMAL -- eine neue
        Klaerungsrunde anlaufen, wenn der Neubau selbst wieder Fragen
        anlegt (Birk: "hoechstens EINE solche Runde automatisch, sonst
        Fragen als Hinweis zeigen")."""
        offene_punkte = [T._PUNKT_OFFEN.format(frage=f)
                         for f, a in zip(fragen, antworten) if a is None]
        if offene_punkte:
            ziel = _szene_mit_nummer(conn, chat_id, nummer)
            if ziel is not None:
                aktualisiert = dict(neue_karte)
                aktualisiert["punkte"] = list(neue_karte.get("punkte") or []) + offene_punkte
                repo.setze_szenenkarte(conn, ziel["id"], json.dumps(
                    aktualisiert, ensure_ascii=False))
        if (neue_karte.get("fragen") or []) and runde == 1:
            starte_fragenklaerung(conn, tg, e, chat_id, nummer, runde=2)
            return False
        return None

    starte(conn, tg, klm, e, chat_id, nummer, _klaerungsnotiz(fragen, antworten),
          nachbereitung=_nachbereitung, ausloeser=AUSLOESER_FRAGEN_GEKLAERT)
    return True


# ---------------------------------------------------------------------------
# Gesamtpruefung ueber alle Karten (a2/a6/a9/a11)
# ---------------------------------------------------------------------------


def karten_am_stueck(conn, chat_id: int) -> str:
    teile = []
    for s in _szenen(conn, chat_id):
        karte = karte_von(s)
        if karte is not None:
            teile.append(karte_text(karte, s, chat_id))
    return "\n\n".join(teile)


def _gesamt(conn, tg, klm, e, chat_id: int, sperre: threading.Lock) -> None:
    from interview_theater import knoepfe

    zeilen: list[str] = []
    try:
        zeilen = pruefe_karten(conn, klm, e, chat_id)
    except Exception:
        log.exception("Gesamtpruefung der Karten gescheitert, chat_id=%s", chat_id)
    finally:
        repo.setze_arbeitsstand(conn, chat_id, "karten_geprueft_am", repo._jetzt())
        sperre.release()
    text = _T(chat_id)._TEXT_GESAMT_KOPF
    if zeilen:
        text += "\n" + "\n".join(f"- {z}" for z in zeilen)
    else:
        text += "\n" + _T(chat_id)._TEXT_GESAMT_OHNE
    _sende(conn, tg, e, chat_id, text)
    knoepfe.biete_phase(conn, tg, chat_id, _T(chat_id)._TEXT_ALLE_GESPEICHERT, 7)


def starte_gesamtpruefung(conn, tg, klm, e, chat_id: int):
    sperre = _sperre_fuer(chat_id)
    if klm is None or not sperre.acquire(blocking=False):
        if klm is None:
            from interview_theater import knoepfe

            knoepfe.biete_phase(conn, tg, chat_id, _T(chat_id)._TEXT_ALLE_GESPEICHERT, 7)
        return None
    _sende(conn, tg, e, chat_id, _T(chat_id)._TEXT_GESAMT_LAEUFT)
    faden = threading.Thread(target=_gesamt, args=(conn, tg, klm, e, chat_id, sperre),
                             daemon=True)
    try:
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


GESAMT_SCHEMA = {
    "type": "object",
    "properties": {
        "befunde": {
            "type": "array", "items": {"type": "string"},
            "description": "At most 5 short findings, each one sentence, each naming "
                           "the scene number it concerns.",
        },
    },
    "required": ["befunde"],
    "additionalProperties": False,
}


def pruefe_karten(conn, klm, e, chat_id: int) -> list[str]:
    """EIN Aufruf ueber alle Karten mit den vier Fragen der Gesamtpruefung
    (a2 Bogen, a6 Material, a9 Ende, a11 Format -- ``prompts/szenenkarte_pruefung.md``).
    Nur Befunde, kein Umschreiben: die Karten bleiben, wie die Gruppe sie
    abgenommen hat."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    format_ = ((stand["format"] if stand is not None else "") or "").strip()
    nutzer = (T._KOPF_FORMAT + "\n" + format_ + "\n\n" if format_ else "") + karten_am_stueck(conn, chat_id)
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id,
        system=_system_fuer(chat_id, "szenenkarte_pruefung"), nutzer=nutzer,
        schema=GESAMT_SCHEMA, art=ART_PRUEFUNG,
        ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
    )
    return [_kappe(b) for b in (ergebnis.get("befunde") or []) if str(b).strip()][:5]


ART_PRUEFUNG = "szenenkarte_pruefung"

# ---------------------------------------------------------------------------
# Texte (W3: Sprache des Profils; Padua ueberschreibt in sprachen/en)
# ---------------------------------------------------------------------------

_KOPF_FORMAT = "Format:"
_KOPF_ALLE_SZENEN = "Alle Szenen:"
_KOPF_DIESE = "DIESE Karte: Szene {nummer} -- {titel}"
_KOPF_BESCHREIBUNG = "Was die Gruppe beschrieben hat:"
_KOPF_ORT = "Ort:"
_KOPF_WER = "Wer:"
_KOPF_ALTE_KARTE = "Bisherige Karte:"
_KOPF_NOTIZ = "Was die Gruppe an der Karte geaendert haben will (gilt vor allem anderen):"
_KOPF_LISTE = "Von der Gruppe uebernommene Interviewstellen (nach Nummer waehlen):"
_KEINE_STELLEN = "(keine)"

_KARTE_KOPF = "Szenenkarte {nummer} — {titel}"
TYP_BESCHRIFTUNG = {"description": "Beschreibung", "spoken": "Sprechtext",
                    "instructions": "Handlungsanweisungen", "moment": "Moment"}
_ZEILE_ORT = "Wo:"
_ZEILE_WER = "Wer:"
_ZEILE_PUNKTE = "Was passiert:"
_ZEILE_ZITATE = "Interviewstellen:"
_ZEILE_FRAGEN = "Offene Fragen:"
_TEXT_FRAGE = "Karte {nummer} von {gesamt}. Passt sie so? Sonst sagt mir, was anders sein soll."
_TEXT_SCHREIBE = "Ich baue die Karte fuer Szene {nummer}."
_TEXT_AENDERE = "Ich baue die Karte fuer Szene {nummer} neu."
_TEXT_LAEUFT = "Ich baue gerade noch an einer Karte -- gleich."
_TEXT_FEHLER = "Die Karte fuer Szene {nummer} hat nicht geklappt. Sagt einfach nochmal Bescheid."
_TEXT_NICHT_DRAN = "Diese Karte ist gerade nicht dran -- gespeichert habe ich nichts."
_TEXT_KEIN_ZIEL = "Alle Karten sind gespeichert. Welche Szene wollt ihr aendern?"
_TEXT_KEINE_SZENEN = "Es gibt noch keine Szenen -- legt sie zuerst in der Workbench fest."
_TEXT_ALLE_GESPEICHERT = "Alle Karten sind gespeichert. Weiter zum Stage Script?"
_TEXT_GESAMT_LAEUFT = "Alle Karten stehen. Ich schaue einmal uebers Ganze."
_TEXT_GESAMT_KOPF = "Blick aufs Ganze:"
_TEXT_GESAMT_OHNE = "- Nichts Auffaelliges."
#: Morgen-Auftrag 4, Nachtrag 2: Zusatzsatz an den Modell-Prompt, nur fuer
#: Chats aus workshop.italienisch_ab_phase6_chats() (_system_fuer unten).
_AUFTRAG_AUSGABE_ITALIENISCH = (
    "Schreib alles auf Italienisch. Zitate bleiben genau wie gegeben, in "
    "der Originalsprache, unveraendert."
)
_ANTWORT_GESPEICHERT = "Karte {nummer} gespeichert"
_TEXT_IM_COTHINKER = "Karte {nummer} von {gesamt} steht im CoThinker-Tab."
_TEXT_KARTE_JA_KNOPF = "Yes, save card"
_TEXT_KARTE_NOCHMAL_KNOPF = "No, change again"
_JOURNAL_GESPEICHERT = "Szenenkarte {nummer} gespeichert: {titel}"

#: Offene Fragen klaeren ("Clear the questions" / "Skip questions", Birk
#: 08.10.2026 ~09:20-09:30).
_TEXT_FRAGEN_OFFEN = (
    "Karte {nummer} von {gesamt} hat noch offene Fragen. Klaert sie, oder "
    "lasst sie fallen, wenn sie nicht passen."
)
_TEXT_KLAEREN_KNOPF = "Fragen klaeren"
_TEXT_UEBERSPRINGEN_KNOPF = "Fragen ueberspringen"
_TEXT_FRAGEN_OFFEN_ABGELEHNT = "Erst die offenen Fragen klaeren -- gespeichert habe ich nichts"
_TEXT_FRAGE_N_VON_M = "Frage {n} von {gesamt}: {frage}"
_ANTWORT_FRAGEN_KLAEREN = "Fragen werden geklaert"
_ANTWORT_FRAGEN_UEBERSPRUNGEN = "Fragen von Karte {nummer} uebersprungen"
_JOURNAL_FRAGEN_UEBERSPRUNGEN = "Karte {nummer}: Fragen als unpassend uebersprungen"
_JOURNAL_FRAGE_BEANTWORTET = "Karte {nummer}, Frage geklaert: {frage} -> {antwort}"
_JOURNAL_FRAGE_OFFEN_GELASSEN = "Karte {nummer}: Frage bewusst offen gelassen: {frage}"
_KOPF_KLAERUNG = "Antworten der Gruppe auf die bisher offenen Fragen (gilt vor allem anderen):"
_ZEILE_KLAERUNG_BEANTWORTET = "- {frage} -> {antwort}"
_ZEILE_KLAERUNG_OFFEN = "- {frage} -> (die Gruppe laesst das bewusst offen)"
_PUNKT_OFFEN = "[OPEN] {frage}"

#: Der "No, change"-Dialog (Birk 08.10.2026 ~09:35, Nachtrag).
_TEXT_DIALOG_START = "Lasst uns ueber Karte {nummer} reden. Was wuerdet ihr aendern?"
_ANTWORT_DIALOG_GESTARTET = "Dialog gestartet"
#: Prompt-Scaffolding (geht nur ans Modell, bleibt auf ``T`` -- Morgen-
#: Auftrag 4): die Karte samt Anweisung, zu diskutieren statt neu zu bauen.
_KOPF_DIALOG = (
    "Die Gruppe bespricht gerade Aenderungen an dieser Karte:\n{karte}\n\n"
    "Diskutiere, mache Vorschlaege, frage nach -- baue die Karte NICHT "
    "selbst neu. Zeichnet sich eine klare Aenderung ab, fasse sie am Ende "
    "deiner Antwort so zusammen:\n\nVORSCHLAG KARTE AENDERUNG:\n"
    "<die Aenderung in 1-3 Saetzen>"
)
#: Knopf-Beschriftungen bleiben IMMER auf ``T`` (Englisch), wie "Yes, save"
#: und "Clear the questions".
_TEXT_UPDATE_KNOPF = "Update the card"
_TEXT_KEEP_KNOPF = "Keep the card"
_ANTWORT_KARTE_WIRD_AKTUALISIERT = "Karte {nummer} wird aktualisiert"
_ANTWORT_KARTE_BEHALTEN = "Karte {nummer} bleibt, wie sie ist"
_TEXT_KLAERWEG_ANGEBOT = (
    "Soll ich die offenen Fragen von Karte {nummer} klaeren?"
)


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
#: Morgen-Auftrag 4, Nachtrag 2 (08.10.2026 ~09:00): Kartentexte und
#: Statuszeilen italienisch, aber nur fuer Chats aus
#: ``workshop.italienisch_ab_phase6_chats()`` -- NIE die beiden
#: Knopf-Beschriftungen oben, die bleiben auf ``T``. ``_T`` statt eines
#: globalen Schalters: die Testgruppe teilt sich das Profil mit G1-G3,
#: soll aber englisch bleiben.
_T_IT = sprache.Texte(__name__, sprachcode="it")


def _T(chat_id: int) -> sprache.Texte:
    return _T_IT if chat_id in workshop.italienisch_ab_phase6_chats() else T
