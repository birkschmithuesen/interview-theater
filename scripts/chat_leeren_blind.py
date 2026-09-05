"""Einen Gruppen-Chat bei Telegram leeren, auch wenn die Datenbank die
Nachrichten nicht mehr kennt (nach ``scripts.loeschen``).

``scripts.chat_leeren`` loescht nur IDs aus der DB. Hier: ein Marker wird
gesendet (liefert die aktuelle message_id), dann werden die letzten
``--zurueck`` IDs rueckwaerts per ``deleteMessages`` (Batch 100) geloescht,
mit Einzel-Fallback. Nicht existierende IDs sind kein Fehler.

Grenze: Telegram loescht per Bot nur Nachrichten der letzten 48 h und nur,
wenn der Bot Admin ist oder es seine eigenen sind.

Aufruf (Env der Gruppe laden):
    set -a; . ./betrieb/gruppe1.env; set +a
    python -m scripts.chat_leeren_blind -5143986099 [--zurueck 300]
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chat_id", type=int)
    ap.add_argument("--zurueck", type=int, default=300)
    a = ap.parse_args(argv)
    tok = os.environ.get("IT_BOT_TOKEN")
    if not tok:
        raise SystemExit("IT_BOT_TOKEN fehlt (Env der Gruppe laden)")
    api = f"https://api.telegram.org/bot{tok}"
    with httpx.Client(timeout=30) as k:
        r = k.post(f"{api}/sendMessage", json={"chat_id": a.chat_id, "text": "…"}).json()
        if not r.get("ok"):
            raise SystemExit(f"Marker nicht gesendet: {r}")
        top = r["result"]["message_id"]
        ids = list(range(max(1, top - a.zurueck), top + 1))
        ok_ids = 0
        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            rr = k.post(f"{api}/deleteMessages", json={"chat_id": a.chat_id, "message_ids": batch}).json()
            if rr.get("ok"):
                ok_ids += len(batch)
                continue
            for m in batch:
                if k.post(f"{api}/deleteMessage", json={"chat_id": a.chat_id, "message_id": m}).json().get("ok"):
                    ok_ids += 1
    print(f"Marker {top}; Loeschaufrufe akzeptiert fuer {ok_ids} IDs (viele davon leer).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
