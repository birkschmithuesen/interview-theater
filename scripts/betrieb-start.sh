#!/usr/bin/env bash
# Startet EINEN Bot-Prozess fuer die Gruppe $1 (= betrieb/<gruppe>.env).
# Wird von der systemd-Unit interview-theater@<gruppe>.service aufgerufen; kann
# auch von Hand laufen. Nimmt immer den Python-3.11-Interpreter aus der
# .venv bzw. uv -- das System-Python 3.9 kann den Code nicht importieren.
set -euo pipefail
cd "$(dirname "$0")/.."
gruppe="${1:?Aufruf: betrieb-start.sh <gruppe>}"
env_datei="betrieb/${gruppe}.env"
[ -f "$env_datei" ] || { echo "fehlt: $env_datei" >&2; exit 2; }
set -a; . "./$env_datei"; set +a

if [ -x .venv/bin/python ]; then
  python=.venv/bin/python
else
  python="$(ls -d "$HOME"/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)"
fi

# Das Workshop-Profil VOR dem Bot pruefen (06.09.2026, E.1 Frage 9 der
# Analyse). Ein Profil mit einem Tippfehler im Platzhalternamen faellt sonst
# erst auf, wenn die Gruppe im Chat "{{zielgrupe}}" liest. Ohne IT_WORKSHOP
# wird das eingebaute Vorgabeprofil geprueft -- das kostet zwei Sekunden und
# faengt auch einen kaputten Repo-Prompt ab.
if ! "$python" -m scripts.pruefe_profil "${IT_WORKSHOP:---vorgabe}"; then
  echo "Start abgebrochen: das Workshop-Profil ist nicht in Ordnung." >&2
  exit 3
fi

exec "$python" -u -c "from interview_theater.bot import main; main()"
