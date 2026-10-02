"""Flow-Audit Schicht 2+3 (Padua, 02.10.2026) -- ein dynamischer Persona-Lauf,
der Birks Generalprobe nachstellt: eine ungeduldige Schauspielstudentin
probiert gezielt Chat statt Knopf an den Stellen, die Schicht 1
(``simulation/flow_audit.py``) als "toter Gespraechsweg" markiert hat, plus
eine Gegenprobe an einer Stelle, die laut Schicht 1 funktioniert.

**Kein Test, laeuft nie automatisch, kostet Geld** -- wie
``scripts/rauchtest.py`` und ``scripts/pruefe_prompts.py``.

Drei Sondierungen, Phasen 4-7 (1-3 werden direkt ueber ``repo`` vorbefuellt,
kein Modellaufruf -- Phase 1-3 ist nicht der Pruefgegenstand dieser Karte):

1. **Phase 4, Kontrolle:** eine Figur per Chat benennen -- soll wirken
   (``figur_setzen`` existiert als Intent, Schicht 1 meldet hier nichts).
2. **Phase 5, Hauptbefund:** einem Schaerfungsvorschlag per Chat zustimmen --
   soll laut Schicht 1 wirkungslos bleiben (kein Intent, nur die Knoepfe aus
   ``knoepfe.biete_schaerfung`` wirken).
3. **Phase 7, zweiter Befund:** inhaltliches Feedback zu einer Szene per Chat
   ("mach die Mutter wuetender") -- soll ebenfalls wirkungslos bleiben (kein
   Intent; nur der Knopf "Passt, aber anders" / ``ART_SZENE_ANDERS`` wirkt).

Jede Sondierung zaehlt mechanisch (kein Modell): **wirkungslos** (kein
Schreibvorgang trotz klarer Aenderungsabsicht) und **behauptet, nicht getan**
(die Bot-Antwort enthaelt ein Zusagewort wie "noted"/"changed"/"saved", ohne
dass etwas geschrieben wurde). Ein Sonnet-Richter (Schicht 3, EIN Aufruf
ueber das ganze Transkript) ergaenzt das qualitative Urteil aus Sicht der
Studentin.

**Nur Sonnet** (JETZT-Lauf, Birk): kein Opus irgendwo. Das Bot-Gespraechs-
und Erkennermodell bleiben unveraendert (Kimi/gemma, Infomaniak) -- die
Betriebsdaten kommen aus ``betrieb/gruppe1.env``, geladen NUR fuer diesen
Prozess und nie ausgegeben.

Aufruf::

    PY=~/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
    $PY -m scripts.flow_audit_lauf [--bericht]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

# Padua ist ein EN-Profil (workshop/padua-2026) -- vor jedem Projektimport
# gesetzt, weil die Phasentexte und der Basisprompt das Profil beim ersten
# Zugriff lesen (interview_theater.workshop, PEP 562 __getattr__).
os.environ.setdefault("IT_WORKSHOP", "padua-2026")

from interview_theater import bot, db, erkenner, knoepfe, llm, phasen, repo  # noqa: E402
from interview_theater.einstellungen import Einstellungen  # noqa: E402

from simulation import claude, flow_audit  # noqa: E402
from simulation.attrappe import TelegramAttrappe  # noqa: E402
from simulation.lauf import CHAT_ID, CHAT_TITEL, bau_update  # noqa: E402

log = logging.getLogger(__name__)

#: Kandidatenpfade fuer die Betriebsdatei -- der Worktree selbst hat kein
#: ``betrieb/`` (gitignored, lebt nur im Hauptcheckout).
_ENV_KANDIDATEN = (
    Path(__file__).resolve().parent.parent / "betrieb" / "gruppe1.env",
    Path("/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/gruppe1.env"),
)

ABSENDER = "Giulia"
WORDS_WORRY_EN = (
    "noted", "saved", "changed", "updated", "added", "got it", "done",
    "sure thing", "on it", "noted that", "updating",
)


def _lade_env_datei() -> dict:
    """Parst ``KEY=VALUE``-Zeilen, ohne sie in ``os.environ`` zu schreiben
    oder je auszugeben -- die Werte bleiben lokal in diesem Dict."""
    for pfad in _ENV_KANDIDATEN:
        if pfad.exists():
            werte = {}
            for zeile in pfad.read_text(encoding="utf-8").splitlines():
                zeile = zeile.strip()
                if not zeile or zeile.startswith("#") or "=" not in zeile:
                    continue
                schluessel, _, wert = zeile.partition("=")
                werte[schluessel.strip()] = wert.strip().strip('"').strip("'")
            return werte
    raise RuntimeError(
        "betrieb/gruppe1.env nicht gefunden -- weder im Worktree noch im "
        f"Hauptcheckout ({_ENV_KANDIDATEN[-1]})."
    )


def _baue_einstellungen(db_pfad: str, env_werte: dict) -> Einstellungen:
    return Einstellungen(
        bot_token=env_werte.get("IT_BOT_TOKEN", ""),
        bot_name="flow-audit-sim",
        db_pfad=db_pfad,
        audio_verz=str(Path(tempfile.gettempdir()) / "flow-audit-audio"),
        llm_url=env_werte["IT_LLM_URL"],
        llm_key=env_werte["IT_LLM_KEY"],
        llm_modell=env_werte["IT_LLM_MODELL"],
        stt_basis=env_werte.get("IT_STT_BASIS", "https://api.infomaniak.com"),
        stt_produkt=env_werte.get("IT_STT_PRODUKT", ""),
        erkenner_modell=env_werte.get("IT_MODELL_ERKENNER", "google/gemma-4-31B-it"),
        szene_anbieter=env_werte.get("IT_SZENE_ANBIETER", "infomaniak"),
        szene_url=env_werte.get("IT_SZENE_URL", "http://127.0.0.1:28764/v1/messages"),
        # JETZT-Lauf, Birk: kein Opus irgendwo -- auch nicht als Rueckfall
        # eines Szenenlaufs, der diese Sondierungen (bei einem echten
        # Intent) versehentlich ausloesen wuerde.
        szene_modell="claude-sonnet-5",
        kosten_deckel_chf=3.0,
    )


def warte_bis(bedingung, timeout: float = 30.0, intervall: float = 0.2) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if bedingung():
            return True
        time.sleep(intervall)
    return bedingung()


# ---------------------------------------------------------------------------
# Vorbefuellen (Phasen 1-3 direkt ueber repo -- kein Modellaufruf, nicht der
# Pruefgegenstand dieser Karte)
# ---------------------------------------------------------------------------

ZITAT_SCHAERFUNG = (
    "I came here ten years ago without a word of Italian, and every "
    "single evening I cried myself to sleep."
)


def seed_bis_phase_5(conn, chat_id: int) -> int:
    repo.sichere_gruppe(conn, chat_id, "flow-audit-sim", CHAT_TITEL)
    repo.setze_arbeitsstand(conn, chat_id, "begriffe", "Arrival, Homesickness, Silence")
    repo.setze_arbeitsstand(conn, chat_id, "fragen", "What was your first impression of this city?")
    phasen.setze(conn, chat_id, 4, "flow-audit")

    kopf_id = repo.lege_interview_an(conn, chat_id)
    repo.setze_aufnahme_name(conn, kopf_id, "Interview 1")
    repo.setze_transkript(conn, kopf_id, ZITAT_SCHAERFUNG)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(
        conn, chat_id, kopf_id, "Arrival without the language, loneliness at first.",
        [{
            "thema": "The loneliness of arriving",
            "beleg_zitat": ZITAT_SCHAERFUNG,
            "zitat_geprueft": 1,
        }],
    )
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "A small rented flat, early evening")
    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte",
        "A woman waits by the phone for a call that never comes.\nEnd: she stops waiting and leaves the flat.",
    )
    repo.setze_figur(conn, chat_id, "Rosa", "waits by the phone, afraid to go out")
    szene_id = repo.stelle_szene_sicher(conn, chat_id, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "The Phone")
    phasen.setze(conn, chat_id, 5, "flow-audit")
    return szene_id


def seed_bis_phase_7(conn, chat_id: int) -> int:
    szene_id = seed_bis_phase_5(conn, chat_id)
    repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    repo.aktualisiere_szene(
        conn, szene_id, "The Phone", "Rosa waits, Toni tries to reassure her.",
        "ROSA: Still nothing.\nTONI: Maybe tomorrow.\nROSA: You always say that.",
    )
    phasen.setze(conn, chat_id, 7, "flow-audit")
    return szene_id


# ---------------------------------------------------------------------------
# Eine Sondierung: Nachricht schicken, Zug fahren, Wirkung messen
# ---------------------------------------------------------------------------

class Sondierung:
    def __init__(self, phase: int, station: str, aktion: str):
        self.phase = phase
        self.station = station
        self.aktion = aktion
        self.nachricht = ""
        self.bot_antwort = ""
        self.schreibvorgang = None  # bool, von der Sondierung selbst gesetzt
        self.hinweis = ""

    @property
    def wirkungslos(self) -> bool:
        return self.schreibvorgang is False

    @property
    def behauptet_nicht_getan(self) -> bool:
        text = self.bot_antwort.lower()
        return self.wirkungslos and any(w in text for w in WORDS_WORRY_EN)

    def als_dict(self) -> dict:
        return {
            "phase": self.phase, "station": self.station, "aktion": self.aktion,
            "nachricht": self.nachricht, "bot_antwort": self.bot_antwort,
            "schreibvorgang": self.schreibvorgang,
            "wirkungslos": self.wirkungslos,
            "behauptet_nicht_getan": self.behauptet_nicht_getan,
            "hinweis": self.hinweis,
        }


def _sende_und_fahre(conn, tg, klm, e, chat_id: int, text: str, update_id: int) -> str:
    """Schickt EINE Nachricht als Giulia, faehrt den Zug synchron (wie
    ``simulation.lauf._schicke``, hier ohne Skript-Maschinerie) und liefert
    die erste Bot-Antwort danach."""
    vorher = len(tg.gesendet)
    update = bau_update(update_id, tg.naechste_message_id(), ABSENDER, text, datetime.now(timezone.utc), chat_id)
    bot.verarbeite_update(conn, e, update, datetime.now(timezone.utc), False)
    bot._zug_und_erkenner(conn, tg, klm, e, chat_id)
    neue = tg.gesendet[vorher:]
    return "\n".join(n["text"] for n in neue if n.get("text"))


def sondiere_phase4_kontrolle(conn, tg, klm, e, chat_id: int, update_id: int) -> Sondierung:
    s = Sondierung(4, "Setting, Figuren & Geschichte",
                    "Figur per Chat benennen (Kontrolle -- soll wirken)")
    s.nachricht = "actually let's name her Giulia, not just 'the woman' -- she's the landlady downstairs"
    vorher = {f["name"] for f in repo.figuren(conn, chat_id)}
    s.bot_antwort = _sende_und_fahre(conn, tg, klm, e, chat_id, s.nachricht, update_id)
    nachher = {f["name"] for f in repo.figuren(conn, chat_id)}
    s.schreibvorgang = nachher != vorher
    s.hinweis = f"Figuren vorher={sorted(vorher)} nachher={sorted(nachher)}"
    return s


def sondiere_phase5_schaerfung(conn, tg, klm, e, chat_id: int, update_id: int) -> Sondierung:
    s = Sondierung(5, "Schaerfung am Material",
                    "Schaerfungsvorschlag per Chat annehmen statt per Knopf")
    vorher_gesendet = len(tg.gesendet)
    knoepfe.starte_schaerfung(conn, tg, klm, e, chat_id)
    kam = warte_bis(lambda: len(tg.gesendet) > vorher_gesendet, timeout=45.0)
    menue = "\n".join(n["text"] for n in tg.gesendet[vorher_gesendet:] if n.get("text"))
    if not kam:
        s.hinweis = "Kein Schaerfungs-Menue innerhalb von 45s -- Sondierung abgebrochen."
        s.schreibvorgang = None
        return s

    vorher = [dict(z) for z in repo.schaerfungen(conn, chat_id)]
    s.nachricht = (
        "yes, that line about crying every evening -- let's use it for "
        "scene 1, it fits Rosa so well"
    )
    s.bot_antwort = _sende_und_fahre(conn, tg, klm, e, chat_id, s.nachricht, update_id)
    nachher = [dict(z) for z in repo.schaerfungen(conn, chat_id)]
    uebernommen_vorher = {z["id"] for z in vorher if z["uebernommen_am"]}
    uebernommen_nachher = {z["id"] for z in nachher if z["uebernommen_am"]}
    s.schreibvorgang = uebernommen_nachher != uebernommen_vorher
    s.hinweis = (
        f"Menue: {menue[:300]!r}; uebernommen vorher={len(uebernommen_vorher)} "
        f"nachher={len(uebernommen_nachher)}"
    )
    return s


def sondiere_phase7_feedback(conn, tg, klm, e, chat_id: int, update_id: int) -> Sondierung:
    s = Sondierung(7, "Feinschliff",
                    "Inhaltliches Feedback per Chat statt Knopf 'Passt, aber anders'")
    szene_vorher = dict(repo.hole_szenen(conn, chat_id)[0])
    s.nachricht = (
        "can we make Rosa angrier in this scene? right now she just sounds "
        "sad, I think she should snap at Toni instead of accepting it"
    )
    s.bot_antwort = _sende_und_fahre(conn, tg, klm, e, chat_id, s.nachricht, update_id)
    szene_nachher = dict(repo.hole_szenen(conn, chat_id)[0])
    s.schreibvorgang = (
        szene_vorher.get("volltext") != szene_nachher.get("volltext")
        or szene_vorher.get("geaendert_am") != szene_nachher.get("geaendert_am")
    )
    s.hinweis = f"volltext_gleich={szene_vorher.get('volltext') == szene_nachher.get('volltext')}"
    return s


# ---------------------------------------------------------------------------
# Schicht 3: EIN Sonnet-Urteil ueber das ganze Transkript
# ---------------------------------------------------------------------------

RICHTER_SYSTEM = (
    "You are judging a theatre-devising chatbot from the point of view of "
    "a 23-year-old acting student in Padua, creative and impatient with "
    "forms, who prefers typing over tapping buttons. You did NOT write the "
    "bot's replies. Answer only with a JSON object."
)

RICHTER_FRAGEN = (
    "fuehle_ich_mich_als_urheberin",
    "bekomme_ich_angebote_statt_vorgaben",
    "kommt_mein_feedback_an",
    "weiss_ich_wo_wir_sind",
    "ist_der_bot_knapp_im_richtigen_moment",
    "wurde_ich_gebremst",
)


def richte(sondierungen: list[Sondierung]) -> dict:
    modell = os.environ.get("IT_JUDGE_MODELL") or os.environ.get("IT_SIM_MODELL") or claude.modell()
    klient = claude.Claude(modellname=modell)
    nutzer = json.dumps(
        {
            "sondierungen": [s.als_dict() for s in sondierungen],
            "fragen": RICHTER_FRAGEN,
            "anleitung": (
                "For each station (one entry per 'phase'/'station' pair), give a score "
                "0, 1 or 2 for EACH of 'fragen', plus one 'satz' (one sentence, in "
                "English) summarising how it felt as the student. Base your judgement "
                "on the mechanical counters (wirkungslos, behauptet_nicht_getan) "
                "together with the actual message and reply -- never on the counters "
                "alone. Return JSON: {\"stationen\": [{\"phase\":int, "
                "\"station\":str, \"noten\": {frage: 0|1|2}, \"satz\": str}]}"
            ),
        },
        ensure_ascii=False,
    )
    try:
        ergebnis = klient.json_objekt(RICHTER_SYSTEM, nutzer, art="flow_audit_richter")
    except Exception as fehler:  # noqa: BLE001 -- ein Richterfehler darf den Bericht nicht reissen
        log.exception("Richter-Aufruf fehlgeschlagen")
        return {"fehler": str(fehler)}
    return ergebnis


# ---------------------------------------------------------------------------
# Bericht
# ---------------------------------------------------------------------------

def schreibe_bericht(sondierungen: list[Sondierung], richterurteil: dict, pfad: Path) -> None:
    datum = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    zeilen = [f"# Flow-Audit -- dynamischer Lauf {datum}\n"]

    rote = [s for s in sondierungen if s.wirkungslos]
    zeilen.append("## Befunde (Schicht 2, nach Schwere)\n")
    if not rote:
        zeilen.append("Keine -- alle Sondierungen haben gewirkt.\n")
    for s in sorted(rote, key=lambda s: s.phase):
        zeilen.append(
            f"### Phase {s.phase} · {s.station}\n"
            f"- Aktion: {s.aktion}\n"
            f"- Nachricht der Studentin (woertlich): „{s.nachricht}“\n"
            f"- Bot-Antwort (woertlich): „{s.bot_antwort}“\n"
            f"- Was gefehlt hat: kein Erkenner-Intent fuer diese Aenderungsabsicht\n"
            f"- Behauptet, nicht getan: {'JA' if s.behauptet_nicht_getan else 'nein'}\n"
            f"- Hinweis: {s.hinweis}\n"
        )

    gruene = [s for s in sondierungen if s.schreibvorgang]
    zeilen.append("## Kontrollen, die gewirkt haben\n")
    for s in gruene:
        zeilen.append(
            f"- Phase {s.phase} · {s.station}: {s.aktion} -> Schreibvorgang bestaetigt ({s.hinweis})\n"
        )

    zeilen.append("\n## Matrix aus Schicht 1 (statisch)\n")
    zeilen.append(flow_audit.matrix_text())
    zeilen.append("\n\n## Schicht-1-Befunde\n")
    zeilen.append(flow_audit.befunde_text(flow_audit.pruefe()))

    zeilen.append("\n\n## Richterurteil (Schicht 3)\n")
    zeilen.append("```json\n" + json.dumps(richterurteil, indent=2, ensure_ascii=False) + "\n```")

    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def schreibe_verlaufszeile(sondierungen: list[Sondierung], pfad: Path) -> None:
    import subprocess

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
            cwd=Path(__file__).resolve().parent.parent,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        head = ""
    zeile = {
        "kennung": f"flow-audit-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "datum": datetime.now(timezone.utc).isoformat(),
        "git": head,
        "sondierungen": [s.als_dict() for s in sondierungen],
        "rote_befunde": sum(1 for s in sondierungen if s.wirkungslos),
    }
    with pfad.open("a", encoding="utf-8") as f:
        f.write(json.dumps(zeile, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--bericht", action="store_true", help="Markdown-Bericht + Verlaufszeile schreiben")
    args = ap.parse_args(argv)

    env_werte = _lade_env_datei()

    with tempfile.TemporaryDirectory() as tmp:
        db_pfad = str(Path(tmp) / "flow-audit.db")
        conn = db.verbinde(db_pfad)
        db.initialisiere(conn)
        e = _baue_einstellungen(db_pfad, env_werte)
        klient = httpx.Client(timeout=120.0)
        klm = llm.LLM(e, klient, conn)
        tg = TelegramAttrappe()
        chat_id = CHAT_ID
        update_id = 1

        sondierungen: list[Sondierung] = []

        seed_bis_phase_5(conn, chat_id)
        sondierungen.append(sondiere_phase4_kontrolle(conn, tg, klm, e, chat_id, update_id)); update_id += 1
        sondierungen.append(sondiere_phase5_schaerfung(conn, tg, klm, e, chat_id, update_id)); update_id += 1

        seed_bis_phase_7(conn, chat_id)
        sondierungen.append(sondiere_phase7_feedback(conn, tg, klm, e, chat_id, update_id)); update_id += 1

        klient.close()

    print("\n=== Sondierungen ===")
    for s in sondierungen:
        print(f"Phase {s.phase} ({s.station}): {s.aktion}")
        print(f"  -> {s.nachricht!r}")
        print(f"  <- {s.bot_antwort!r}")
        print(f"  wirkungslos={s.wirkungslos} behauptet_nicht_getan={s.behauptet_nicht_getan}")
        print(f"  {s.hinweis}")

    richterurteil = richte(sondierungen)
    print("\n=== Richterurteil ===")
    print(json.dumps(richterurteil, indent=2, ensure_ascii=False))

    if args.bericht:
        berichte = Path(__file__).resolve().parent.parent / "simulation" / "berichte"
        berichte.mkdir(parents=True, exist_ok=True)
        datum = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        schreibe_bericht(sondierungen, richterurteil, berichte / f"flow-audit-{datum}.md")
        schreibe_verlaufszeile(sondierungen, berichte / "verlauf.jsonl")

    return 1 if any(s.wirkungslos for s in sondierungen) else 0


if __name__ == "__main__":
    sys.exit(main())
