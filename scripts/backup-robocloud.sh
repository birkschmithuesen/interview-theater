#!/usr/bin/env bash
# Sichert die vertraulichen Daten des interview-theater-Bots in die RoboCloud.
#
# Gesichert wird ALLES, was bewusst NICHT im oeffentlichen GitHub-Repo liegt:
# Datenbank, Audiodateien, Zugangsdaten. Ziel:
#
#     Hermes-Agent/RoboCloud/interview-theater/<YYYY-MM-DD_HHMM>/
#
# Die RoboCloud ist nicht-versionierter Arbeitsspeicher neben dem Vault —
# genau der richtige Ort fuer grosse, vertrauliche Betriebsdaten.
#
# 🔴 WICHTIG FUER DIE LOESCHZUSAGE AN DIE TEILNEHMERINNEN:
# Was hier hochgeladen wurde, entfernt scripts/loeschen.py NICHT — das raeumt
# nur die lokale Maschine auf. Wird eine Loeschung verlangt, muss ZUSAETZLICH
# der passende Ordner in der RoboCloud entfernt werden:
#     rclone purge hermes-vault:Hermes-Agent/RoboCloud/interview-theater/<STAND>
# Deshalb sind die Sicherungen nach Zeitpunkt benannt und nicht vermischt.
#
# Zugangsdaten (betrieb/*.env) werden bewusst NICHT gesichert.
#
# Aufruf:
#     bash scripts/backup-robocloud.sh              # Sicherung anlegen
#     bash scripts/backup-robocloud.sh --auflisten  # vorhandene anzeigen
#
# Waehrend des Workshops sinnvollerweise nach jeder Phase laufen lassen,
# mindestens aber am Abend jedes Workshoptags.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RCLONE="$HOME/.local/bin/rclone"
FERN="hermes-vault:Hermes-Agent/RoboCloud/interview-theater"
STAMP="$(date +%Y-%m-%d_%H%M)"

rot()  { printf '\033[31m%s\033[0m\n' "$*"; }
gruen(){ printf '\033[32m%s\033[0m\n' "$*"; }

[ -x "$RCLONE" ] || { rot "FEHLER: $RCLONE nicht gefunden."; exit 1; }

if [ "${1:-}" = "--auflisten" ]; then
    echo "Vorhandene Sicherungen:"
    "$RCLONE" lsd "$FERN" 2>/dev/null || echo "  (noch keine)"
    exit 0
fi

ZIEL="$FERN/$STAMP"
echo "Sichere nach $ZIEL"
echo

GESICHERT=0

# --- Datenbank (WAL mit einschliessen, sonst fehlen die letzten Schreibvorgaenge)
for db in "$REPO"/*.db "$REPO"/betrieb/*.db; do
    [ -e "$db" ] || continue
    echo "  Datenbank: $(basename "$db")"
    for teil in "$db" "$db-wal" "$db-shm"; do
        [ -e "$teil" ] && "$RCLONE" copyto "$teil" "$ZIEL/db/$(basename "$teil")"
    done
    GESICHERT=$((GESICHERT+1))
done

# --- Audiodateien
if [ -d "$REPO/audio" ] && [ -n "$(ls -A "$REPO/audio" 2>/dev/null)" ]; then
    ANZAHL=$(find "$REPO/audio" -type f | wc -l)
    echo "  Audio: $ANZAHL Dateien"
    "$RCLONE" copy "$REPO/audio" "$ZIEL/audio" --transfers 4
    GESICHERT=$((GESICHERT+1))
fi

# --- Zugangsdaten werden BEWUSST NICHT gesichert.
# Bot-Tokens und API-Schluessel im Klartext ausserhalb der Maschine abzulegen
# wuerde den Aufwand zunichte machen, mit dem der Token nicht einmal in einer
# Logzeile auftaucht. Ein verlorener Token ist bei BotFather in zwei Minuten
# neu erzeugt — ein abgeflossener ist nicht zurueckzuholen.

if [ "$GESICHERT" -eq 0 ]; then
    echo "Nichts zu sichern — es gibt noch keine Betriebsdaten."
    exit 0
fi

# --- Gegenprobe: zaehlen, was tatsaechlich angekommen ist
echo
echo "Gegenprobe ..."
FERN_ANZAHL=$("$RCLONE" ls "$ZIEL" 2>/dev/null | wc -l)
if [ "$FERN_ANZAHL" -eq 0 ]; then
    rot "FEHLER: in der RoboCloud ist nichts angekommen."
    exit 1
fi
gruen "$FERN_ANZAHL Dateien gesichert."
echo
echo "Ort:  $ZIEL"
echo "Alle: bash scripts/backup-robocloud.sh --auflisten"
