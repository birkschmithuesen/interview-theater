"""Flow-Audit Schicht 3 (Padua Flow Audit, 04.10.2026) -- derselbe dynamische
Lauf wie ``simulation/flow_audit_dynamisch.py`` (Schicht 2), aber gegen die
echten Dienste statt der ``SkriptLLM``-Attrappe: ein echtes
``interview_theater.llm.LLM`` (Kimi/gemma ueber Infomaniak) treibt die
14 Stationen, ein Sonnet-Richter (``simulation.claude.Claude``) urteilt
anschliessend ueber das ganze Transkript. Dazu kommt Schicht 1
(``simulation.flow_audit.pruefe()``) in denselben Bericht -- "ein Kommando",
auch wenn es innerlich drei Schichten zusammenfasst.

**Kein Test, laeuft nie automatisch, kostet Geld** -- wie
``scripts/rauchtest.py`` und ``scripts/pruefe_prompts.py``.

**Die Wiederverwendung ist der ganze Punkt dieser Karte.** Keine
Stationslogik wird hier neu geschrieben: ``simulation.flow_audit_dynamisch.
fuehre_alle_aus(conn, tg, klm, e, chat_id)`` ist die eine Stelle, die alle
14 Stationen faehrt -- genau dieselbe Funktion, die Schicht 2 mit der
Attrappe aufruft. Nur ``klm`` ist hier ein echtes ``LLM``-Objekt statt
``SkriptLLM``; ``tg`` bleibt eine ``TelegramAttrappe`` (dieser Lauf schickt
keine echten Telegram-Nachrichten, siehe Aufgabenbrief -- nur das
Gespraechs-/Erkennermodell wird real, der Chat-Transport bleibt simuliert).

**Nur Sonnet** (globale Randbedingung dieser Karte): kein Opus irgendwo.
``simulation.claude.Claude`` wird in diesem Modul **immer** mit
``modellname="claude-sonnet-5"`` konstruiert -- nie ueber den
Vorgabewert (``claude-opus-5``) und nie nur ueber eine Umgebungsvariable,
die veraltet sein kann. ``Einstellungen.szene_modell`` wird aus demselben
Grund erzwungen, auch wenn dieser Lauf ``szene.py`` nicht aufruft: kein Feld
soll je auf ein Opus-Modell zeigen.

Die Betriebsdaten kommen aus ``betrieb/gruppe1.env``, geladen NUR fuer diesen
Prozess und nie ausgegeben (vgl. die historische Referenzimplementierung
``.flow_audit_ref/flow_audit_lauf.py``, von der dieses Modul die Form von
``_lade_env_datei``/``_baue_einstellungen``/``richte``/``schreibe_bericht``/
``schreibe_verlaufszeile`` uebernimmt -- mit den heutigen 14 Stationen und
Schicht 1 statt der drei Phase-4-7-Sondierungen jenes aelteren Codestands).

**Diese Umgebung hat kein ``betrieb/``** (dieser Worktree ist gitignored
dafuer) -- ein Lauf hier endet deshalb immer bei ``_lade_env_datei()`` mit
einer klaren Fehlermeldung. Das ist beabsichtigt: dieses Skript soll fuer
einen Betreiber KORREKT UND BEREIT sein, nicht selbst in dieser Sitzung
gegen echte Dienste laufen (vgl. ``scripts/strom_probe.py``, das auf
dieselbe Weise fuer spaeter gebaut und hinterlegt wurde).

Aufruf::

    PY=~/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
    $PY -m scripts.flow_audit_lauf [--bericht]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import db, llm, repo
from interview_theater.einstellungen import Einstellungen

from simulation import claude, flow_audit, flow_audit_dynamisch
from simulation.attrappe import TelegramAttrappe
from simulation.flow_audit_dynamisch import Sondierung
from simulation.lauf import CHAT_ID, CHAT_TITEL

log = logging.getLogger(__name__)

#: Kandidatenpfade fuer die Betriebsdatei -- dieser Worktree selbst hat kein
#: ``betrieb/`` (gitignored, lebt nur im Hauptcheckout). Gleiches Muster wie
#: ``.flow_audit_ref/flow_audit_lauf.py::_ENV_KANDIDATEN``.
_ENV_KANDIDATEN = (
    Path(__file__).resolve().parent.parent / "betrieb" / "gruppe1.env",
    Path("/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/gruppe1.env"),
)

#: Keine Opus-Spur irgendwo -- siehe Moduldocstring.
RICHTER_MODELL = "claude-sonnet-5"


def _lade_env_datei(kandidaten: tuple[Path, ...] | None = None) -> dict:
    """Parst ``KEY=VALUE``-Zeilen aus der ersten gefundenen Betriebsdatei in
    ein lokales Dict -- NIE nach ``os.environ``, NIE ausgegeben oder
    geloggt. Wirft ``RuntimeError`` mit einer fuer einen Betreiber
    verstaendlichen Meldung, wenn keine der beiden Kandidatendateien da ist
    (der Regelfall in dieser Sandbox).

    ``kandidaten`` ist nur fuer Tests gedacht (Vorgabe: das Modul-Global
    ``_ENV_KANDIDATEN``, als Name nachgeschlagen statt als gebundener
    Default-Parameter -- ein ``monkeypatch.setattr(modul, "_ENV_KANDIDATEN",
    ...)`` wirkt dadurch auch ohne diesen Parameter). Ein Test gibt
    ausdruecklich Pfade unter ``tmp_path`` mit, damit niemals versehentlich
    die echten Betriebsdaten des Hauptcheckouts gelesen werden -- siehe
    ``tests/test_flow_audit_lauf.py`` fuer den gemessenen Grund."""
    verwendete = kandidaten if kandidaten is not None else _ENV_KANDIDATEN
    for pfad in verwendete:
        try:
            gefunden = pfad.exists()
        except OSError:
            # Diese Sitzung darf teils nicht einmal pruefen, ob ein Pfad
            # ausserhalb des Worktrees existiert (Berechtigungsfehler statt
            # eines einfachen "nicht da") -- zaehlt wie "nicht gefunden".
            gefunden = False
        if not gefunden:
            continue
        try:
            text = pfad.read_text(encoding="utf-8")
        except OSError:
            continue
        werte: dict[str, str] = {}
        for zeile in text.splitlines():
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#") or "=" not in zeile:
                continue
            schluessel, _, wert = zeile.partition("=")
            werte[schluessel.strip()] = wert.strip().strip('"').strip("'")
        return werte
    raise RuntimeError(
        "betrieb/gruppe1.env nicht gefunden -- weder im Worktree "
        f"({verwendete[0]}) noch im Hauptcheckout "
        f"({verwendete[-1]}). Diese Datei traegt die echten "
        "Zugangsdaten fuer das Gespraechsmodell (IT_LLM_URL/_KEY/_MODELL) -- "
        "ohne sie kann dieser Lauf keinen echten LLM-Client bauen. Die "
        "kostenlose Schicht-1-Pruefung ist davon unabhaengig: "
        "`python -m simulation.flow_audit`."
    )


def _pflichtwert(env_werte: dict, schluessel: str) -> str:
    wert = env_werte.get(schluessel)
    if not wert:
        raise RuntimeError(
            f"{schluessel} fehlt oder ist leer in betrieb/gruppe1.env -- "
            "ohne diesen Wert kann kein echter LLM-Client gebaut werden."
        )
    return wert


def _baue_einstellungen(db_pfad: str, env_werte: dict) -> Einstellungen:
    """Baut eine echte ``Einstellungen`` (``interview_theater.einstellungen``)
    aus den geladenen Env-Werten -- Feldnamen gegen den heutigen Stand der
    Dataclass gelesen (nicht aus der aelteren Referenz uebernommen; seit
    deren Entstehung sind ``kanal``/``web_chat_id``/``web_segment_ms``/
    ``zeitzone`` dazugekommen, alle mit Vorgabewerten, die fuer einen
    Flow-Audit-Lauf unveraendert passen).

    ``szene_modell`` wird auf ``"claude-sonnet-5"`` erzwungen und
    ``kosten_deckel_chf`` niedrig gehalten (3.0 CHF) -- dieser Lauf ist ein
    Werkzeug, kein Workshoptag, und kein Feld soll je auf Opus zeigen
    (globale Randbedingung dieser Karte)."""
    return Einstellungen(
        bot_token=env_werte.get("IT_BOT_TOKEN", ""),
        bot_name="flow-audit-lauf",
        db_pfad=db_pfad,
        audio_verz=str(Path(tempfile.gettempdir()) / "flow-audit-lauf-audio"),
        llm_url=_pflichtwert(env_werte, "IT_LLM_URL"),
        llm_key=_pflichtwert(env_werte, "IT_LLM_KEY"),
        llm_modell=_pflichtwert(env_werte, "IT_LLM_MODELL"),
        stt_basis=env_werte.get("IT_STT_BASIS", "https://api.infomaniak.com"),
        stt_produkt=env_werte.get("IT_STT_PRODUKT", ""),
        erkenner_modell=env_werte.get("IT_MODELL_ERKENNER", "google/gemma-4-31B-it"),
        szene_anbieter=env_werte.get("IT_SZENE_ANBIETER", "infomaniak"),
        szene_url=env_werte.get("IT_SZENE_URL", "http://127.0.0.1:28764/v1/messages"),
        # Globale Randbedingung dieser Karte: kein Opus irgendwo -- auch
        # nicht in einem Feld, das dieser Lauf selbst nie liest.
        szene_modell="claude-sonnet-5",
        kosten_deckel_chf=3.0,
    )


# ---------------------------------------------------------------------------
# Schicht 3: EIN Sonnet-Urteil ueber das ganze Transkript (alle 14 Stationen).
# ---------------------------------------------------------------------------

RICHTER_SYSTEM = (
    "You are judging a theatre-devising chatbot. The transcript below has "
    "14 stations; each one was driven by one of two personas, named in its "
    "'persona' field: Giulia (23, acting student in Padua, English B2, "
    "creative, impatient with forms, brings her own ideas, prefers typing "
    "over tapping buttons) or Priya (first-time chatbot user, unsure of her "
    "English, never used push-to-talk). You did NOT write the bot's "
    "replies. Judge each station from ITS OWN persona's point of view -- "
    "a station driven by Priya should be judged as Priya would feel it, "
    "not as Giulia would. Answer only with a JSON object."
)

#: Woertlich aus dem Aufgabenbrief uebernommen (verbatim, Englisch -- das
#: Padua-Profil ist ein EN-Profil).
RICHTER_FRAGEN = (
    "fuehle_ich_mich_als_urheberin",
    "bekomme_ich_angebote_statt_vorgaben",
    "kommt_mein_feedback_an",
    "weiss_ich_wo_wir_sind",
    "ist_der_bot_knapp_im_richtigen_moment",
    "wurde_ich_gebremst",
)


def richte(sondierungen: list[Sondierung]) -> dict:
    """EIN Sonnet-Aufruf ueber ``Sondierung.als_dict()`` aller Stationen.

    Ein gescheiterter Richterlauf darf den Bericht nicht reissen -- wie bei
    ``.flow_audit_ref/flow_audit_lauf.py::richte`` wird die Ausnahme
    geloggt und ``{"fehler": str(...)}`` zurueckgegeben; die Schicht-1/2-
    Befunde bleiben auch ohne Richterurteil nuetzlich."""
    klient = claude.Claude(modellname=RICHTER_MODELL)
    nutzer = json.dumps(
        {
            "sondierungen": [s.als_dict() for s in sondierungen],
            "fragen": RICHTER_FRAGEN,
            "anleitung": (
                "For each station (one entry per 'phase'/'station' pair), give a score "
                "0, 1 or 2 for EACH of 'fragen', plus one 'satz' (one sentence, in "
                "English, from the point of view of that station's own 'persona') "
                "summarising how it felt. Base your judgement on the mechanical "
                "counters (wirkungslos, behauptet_nicht_getan, klickzwang, "
                "rueckfragen_vor_aktion) together with the actual message and reply "
                "-- never on the counters alone. Return JSON: {\"stationen\": "
                "[{\"phase\":int, \"station\":str, \"persona\":str, "
                "\"noten\": {frage: 0|1|2}, \"satz\": str}]}"
            ),
        },
        ensure_ascii=False,
    )
    try:
        ergebnis = klient.json_objekt(RICHTER_SYSTEM, nutzer, art="flow_audit_richter")
    except Exception as fehler:  # noqa: BLE001 -- ein Richterfehler darf den Bericht nicht reissen
        log.exception("Richter-Aufruf (Schicht 3) fehlgeschlagen")
        return {"fehler": str(fehler)}
    finally:
        klient.schliesse()
    return ergebnis


# ---------------------------------------------------------------------------
# Bericht + Verlaufszeile.
# ---------------------------------------------------------------------------


def schreibe_bericht(
    sondierungen: list[Sondierung],
    schicht1_befunde: list,
    richterurteil: dict,
    pfad: Path,
) -> None:
    """Markdown-Bericht ueber alle drei Schichten.

    Reihenfolge (Aufgabenbrief): rote Befunde zuerst (nach Schwere -- der
    schon bekannte, bestaetigte Fund aus Station 10
    (``knoepfe.fragen.nimm_offene_frage_text`` behandelt jede freie
    Chatnachricht auf eine offene Frage als Schaerfungswunsch statt als
    Zustimmung) wird dabei ALS ERSTES gezeigt, erkannt an ihrem eigenen
    Hinweistext statt an ihrer Stationsnummer -- robust, falls die
    Stationsreihenfolge sich einmal aendert), dann die Kontrollen, die
    gewirkt haben, dann die Schicht-1-Matrix + Befunde, dann das
    Richterurteil (oder eine klare Zeile, warum es fehlt)."""
    datum = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    zeilen = [f"# Flow-Audit -- vollstaendiger Lauf {datum}\n"]

    rote = [s for s in sondierungen if s.wirkungslos]
    rote_sortiert = sorted(
        rote,
        key=lambda s: (
            0 if "GEFUNDENER TOTER WEG" in s.hinweis else 1,
            s.phase,
            s.station,
        ),
    )

    zeilen.append("## Befunde (Schicht 2, nach Schwere)\n")
    if not rote_sortiert:
        zeilen.append("Keine -- alle Sondierungen haben gewirkt.\n")
    for s in rote_sortiert:
        zeilen.append(
            f"### Phase {s.phase} · {s.station} ({s.persona})\n"
            f"- Aktion: {s.aktion}\n"
            f"- Nachricht der Persona (woertlich): „{s.nachricht}“\n"
            f"- Bot-Antwort (woertlich): „{s.bot_antwort}“\n"
            f"- Was gefehlt hat: {s.hinweis}\n"
            f"- Behauptet, nicht getan: {'JA' if s.behauptet_nicht_getan else 'nein'}\n"
        )

    gruene = [s for s in sondierungen if s.schreibvorgang]
    zeilen.append("## Kontrollen, die gewirkt haben\n")
    if not gruene:
        zeilen.append("Keine.\n")
    for s in gruene:
        zeilen.append(
            f"- Phase {s.phase} · {s.station} ({s.persona}): {s.aktion} "
            f"-> Schreibvorgang bestaetigt ({s.hinweis})\n"
        )

    zeilen.append("\n## Schicht 1 (statisch) -- Matrix\n")
    zeilen.append(flow_audit.matrix_text())
    zeilen.append("\n\n## Schicht 1 -- Befunde\n")
    zeilen.append(flow_audit.befunde_text(schicht1_befunde))

    zeilen.append("\n\n## Richterurteil (Schicht 3, Sonnet)\n")
    if "fehler" in richterurteil:
        zeilen.append(f"Richter ist nicht gelaufen: {richterurteil['fehler']}\n")
    else:
        zeilen.append(
            "```json\n" + json.dumps(richterurteil, indent=2, ensure_ascii=False) + "\n```"
        )

    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def schreibe_verlaufszeile(
    sondierungen: list[Sondierung], schicht1_befunde: list, pfad: Path,
) -> None:
    """Eine JSON-Zeile je Lauf -- Vergleichsmassstab zwischen zwei
    Codestaenden, wie ``simulation/berichte/verlauf.jsonl`` es fuer die
    grosse Simulation schon tut."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
            cwd=Path(__file__).resolve().parent.parent,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 -- kein git, kein Abbruch
        head = ""
    zeile = {
        "kennung": f"flow-audit-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "datum": datetime.now(timezone.utc).isoformat(),
        "git": head,
        "sondierungen": [s.als_dict() for s in sondierungen],
        "rote_befunde": sum(1 for s in sondierungen if s.wirkungslos),
        "schicht1_rote_befunde": sum(
            1 for b in schicht1_befunde
            if b.schwere in ("sackgasse", "toter_gespraechsweg")
        ),
    }
    with pfad.open("a", encoding="utf-8") as f:
        f.write(json.dumps(zeile, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Der echte Lauf.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--bericht", action="store_true",
        help="Markdown-Bericht nach simulation/berichte/ + Verlaufszeile schreiben",
    )
    args = ap.parse_args(argv)

    # Wirft RuntimeError mit einer fuer einen Betreiber verstaendlichen
    # Meldung, wenn betrieb/gruppe1.env fehlt -- in dieser Sandbox immer der
    # Fall. main() faengt das bewusst NICHT selbst ab: ruft jemand main()
    # als Funktion (``simulation.flow_audit --voll``), soll die Ausnahme
    # dort ankommen und einen freundlichen Satz ausloesen; ruft jemand
    # dieses Skript direkt auf der Kommandozeile, faengt der
    # ``__main__``-Block unten sie ab.
    env_werte = _lade_env_datei()

    # Padua ist ein EN-Profil (workshop/padua-2026) -- die Phasentexte und
    # der Basisprompt lesen das Profil erst bei Zugriff (PEP 562
    # ``__getattr__``), deshalb reicht es, die Variable HIER zu setzen statt
    # beim Modulimport. Damit hinterlaesst ein blosser Import dieses Moduls
    # (fuer die Tests der reinen Teile, oder der lazy Import aus
    # ``simulation.flow_audit --voll``) keine bleibende Umgebungsaenderung,
    # solange main() nicht tatsaechlich laeuft -- derselbe Mechanismus wie in
    # ``.flow_audit_ref/flow_audit_lauf.py`` (``os.environ.setdefault``),
    # nur an eine Stelle verschoben, an der er nur bei echtem Gebrauch wirkt.
    os.environ.setdefault("IT_WORKSHOP", "padua-2026")

    with tempfile.TemporaryDirectory() as tmp:
        db_pfad = str(Path(tmp) / "flow-audit-lauf.db")
        conn = db.verbinde(db_pfad)
        db.initialisiere(conn)
        e = _baue_einstellungen(db_pfad, env_werte)
        repo.sichere_gruppe(conn, CHAT_ID, e.bot_name, CHAT_TITEL)

        klient = httpx.Client(timeout=120.0)
        klm = llm.LLM(e, klient, conn)
        tg = TelegramAttrappe()

        try:
            sondierungen = flow_audit_dynamisch.fuehre_alle_aus(conn, tg, klm, e, CHAT_ID)
        except Exception as fehler:  # noqa: BLE001 -- siehe Aufgabenbrief: kein Stacktrace fuer den Betreiber
            log.exception("Schicht 2 gegen die echten Dienste ist fehlgeschlagen")
            klient.close()
            print(
                "Der dynamische Lauf gegen die echten Dienste ist "
                f"fehlgeschlagen: {fehler}\n"
                "Pruefen Sie Netzzugriff und die Zugangsdaten in "
                "betrieb/gruppe1.env. Die kostenlose Schicht-1-Pruefung ist "
                "davon unabhaengig und laeuft jederzeit mit "
                "`python -m simulation.flow_audit`.",
                file=sys.stderr,
            )
            return 1
        klient.close()

    richterurteil = richte(sondierungen)
    schicht1_befunde = flow_audit.pruefe()

    print("\n=== Sondierungen (Schicht 2, echte Dienste) ===")
    for s in sondierungen:
        print(f"Phase {s.phase} ({s.station}) [{s.persona}]: {s.aktion}")
        print(f"  -> {s.nachricht!r}")
        print(f"  <- {s.bot_antwort!r}")
        print(
            f"  wirkungslos={s.wirkungslos} "
            f"behauptet_nicht_getan={s.behauptet_nicht_getan}"
        )
        print(f"  {s.hinweis}")

    print("\n=== Richterurteil (Schicht 3, Sonnet) ===")
    print(json.dumps(richterurteil, indent=2, ensure_ascii=False))

    print("\n=== Schicht 1 (statisch) ===")
    print(flow_audit.befunde_text(schicht1_befunde))

    if args.bericht:
        berichte = Path(__file__).resolve().parent.parent / "simulation" / "berichte"
        berichte.mkdir(parents=True, exist_ok=True)
        datum = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        schreibe_bericht(
            sondierungen, schicht1_befunde, richterurteil,
            berichte / f"flow-audit-{datum}.md",
        )
        schreibe_verlaufszeile(sondierungen, schicht1_befunde, berichte / "verlauf.jsonl")

    rot_schicht1 = any(
        b.schwere in ("sackgasse", "toter_gespraechsweg") for b in schicht1_befunde
    )
    rot_schicht2 = any(s.wirkungslos for s in sondierungen)
    return 1 if (rot_schicht1 or rot_schicht2) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as fehler:
        print(f"Flow-Audit (voller Lauf) kann nicht starten: {fehler}", file=sys.stderr)
        sys.exit(1)
