"""Gespraechsprompt eines Zugs als JSON auf stdout — fuer den Abgleich der Simulation.

Laeuft als Unterprozess mit PYTHONPATH=<app-wurzel>, damit `interview_theater`
aus dem geprueften App-Stand kommt (auch cb200e4), und immer gegen eine KOPIE
der Simulations-DB. Importiert nichts aus `simulation`.

Abgleich der beiden Staende (05.10.2026, ``git show cb200e4:interview_theater/kontext.py``
gegen HEAD): ``kontext.baue(conn, chat_id, ausloeser, e, erstkontakt=False,
protokoll=None, ueber_claude=False) -> str`` und ``kontext.system(bot_name,
phase) -> str`` sind an beiden Staenden gleich; ``baue`` liefert nur den
Koerper (Nutzertext), die Systemanweisung kommt getrennt. Der Abzug baut
beides genau wie ``ablauf._erfrage_antwort``. Die Argumente von ``baue``
werden trotzdem ueber ``inspect.signature`` gewaehlt, damit ein dritter Stand
ohne ``ueber_claude``/``erstkontakt`` nicht bricht.

**Kein Geld:** ``kontext`` ruft kein Modell (keine ``llm``-Abhaengigkeit, die
Kuerzung ist rein zeichenbasiert). Zur Sicherheit zeigen die Modell-URLs
dieses Prozesses waehrend des Abzugs ins Leere (``_KEIN_MODELL``).

**Schreibt:** ja, in die uebergebene Datei -- die ausloesende Nachricht
(``repo.merke_nachricht``), und ``kontext.baue`` selbst kann einen Vorfall
oder das Phasenangebot merken. Deshalb nur gegen eine Kopie
(``simulation.browser_wissen.kopiere_db``).
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

#: Als Datei gestartet steht ``simulation/`` vorn in ``sys.path`` -- dort
#: liegen Module wie ``claude.py``, die im App-Checkout nichts verloren haben.
_HIER = str(Path(__file__).resolve().parent)
if __name__ == "__main__" and sys.path and str(Path(sys.path[0]).resolve()) == _HIER:
    del sys.path[0]

#: Unerreichbares Ziel fuer jede Modell-URL waehrend des Abzugs.
_KEIN_MODELL = "http://127.0.0.1:9/kein-modell-im-prompt-abzug"
_MODELL_URLS = ("IT_LLM_URL", "IT_SZENE_URL", "IT_STT_BASIS")

#: Absender der ausloesenden Nachricht, falls der App-Stand keine
#: ``web_kanal.ABSENDER`` kennt.
_ABSENDER_VORGABE = "Group"


def _argumente(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", required=True)
    p.add_argument("--chat-id", type=int, required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--workshop", default=None, help="setzt IT_WORKSHOP fuer den Abzug")
    p.add_argument("--bot-name", default=None, help="setzt IT_BOT_NAME fuer den Abzug")
    p.add_argument("--web-url", default=None, help="setzt IT_WEB_URL fuer den Abzug")
    return p.parse_args(argv)


def _umgebung(args) -> dict[str, str]:
    werte = {"IT_DB": args.db}
    werte.update({name: _KEIN_MODELL for name in _MODELL_URLS})
    if args.workshop is not None:
        werte["IT_WORKSHOP"] = args.workshop
    if args.bot_name is not None:
        werte["IT_BOT_NAME"] = args.bot_name
    if args.web_url is not None:
        werte["IT_WEB_URL"] = args.web_url
    return werte


def _einstellungen():
    """Die Einstellungen wie im Bot; fehlt eine Pflichtvariable (in-process
    im Test), eine Attrappe mit den Feldern, die ``kontext`` und
    ``modellwahl`` lesen."""
    from interview_theater import einstellungen

    try:
        return einstellungen.laden()
    except RuntimeError:
        return SimpleNamespace(
            bot_name=os.environ.get("IT_BOT_NAME") or "",
            web_url=(os.environ.get("IT_WEB_URL") or "").rstrip("/"),
            szene_anbieter=(os.environ.get("IT_SZENE_ANBIETER") or "infomaniak").lower(),
            erkenner_modell=None,
        )


def _ueber_claude(e, conn, chat_id: int) -> bool:
    try:
        from interview_theater import modellwahl
    except ImportError:
        return False
    pruefe = getattr(modellwahl, "konversation_ueber_claude", None)
    return bool(pruefe(e, conn, chat_id)) if pruefe else False


def _merke_ausloeser(conn, chat_id: int, text: str):
    """Die Nachricht des Zugs, wie ``bot.verarbeite_update`` sie speichert,
    plus alles, was ``ablauf`` ohnehin als unbeantwortet mitnaehme."""
    from interview_theater import repo

    try:
        from interview_theater import web_kanal
        absender = getattr(web_kanal, "ABSENDER", _ABSENDER_VORGABE)
    except ImportError:
        absender = _ABSENDER_VORGABE
    hoechste = conn.execute(
        "SELECT COALESCE(MAX(message_id), 0) FROM nachricht WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    message_id = int(hoechste) + 1
    repo.merke_nachricht(conn, chat_id, message_id, absender, 0, "text", text, repo._jetzt())
    offen = list(repo.unbeantwortete(conn, chat_id))
    if not any(n["message_id"] == message_id for n in offen):
        offen.append(conn.execute(
            "SELECT * FROM nachricht WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)
        ).fetchone())
    return offen


def _baue(kontext, conn, chat_id: int, offen, e, *, erstkontakt: bool, ueber_claude: bool) -> str:
    parameter = inspect.signature(kontext.baue).parameters
    extra = {}
    if "erstkontakt" in parameter:
        extra["erstkontakt"] = erstkontakt
    if "ueber_claude" in parameter:
        extra["ueber_claude"] = ueber_claude
    return kontext.baue(conn, chat_id, offen, e, **extra)


def _abzug(args) -> str:
    from interview_theater import db, kontext, phasen, repo, workshop

    workshop.vergiss()
    conn = db.verbinde(args.db)
    try:
        db.initialisiere(conn)
        e = _einstellungen()
        chat_id = args.chat_id
        erstkontakt = not repo.hat_bot_nachricht(conn, chat_id)
        offen = _merke_ausloeser(conn, chat_id, args.text)
        phase = phasen.aktuelle(conn, chat_id)
        ueber_claude = _ueber_claude(e, conn, chat_id)
        koerper = _baue(kontext, conn, chat_id, offen, e,
                        erstkontakt=erstkontakt, ueber_claude=ueber_claude)
        system = kontext.system(getattr(e, "bot_name", None), phase)
    finally:
        conn.close()
    return f"{system}\n\n{koerper}"


def main(argv: list[str] | None = None) -> int:
    args = _argumente(argv)
    alt = {name: os.environ.get(name) for name in _umgebung(args)}
    os.environ.update(_umgebung(args))
    try:
        prompt = _abzug(args)
    finally:
        for name, wert in alt.items():
            if wert is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = wert
        from interview_theater import workshop

        workshop.vergiss()
    print(json.dumps({"prompt": prompt}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
