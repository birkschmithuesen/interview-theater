#!/usr/bin/env bash
# Startet EINEN Bot-Prozess fuer die Gruppe $1 (= betrieb/<gruppe>.env).
# Wird von der systemd-Unit theatersoap@<gruppe>.service aufgerufen; kann
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
exec "$python" -u -c "from theatersoap.bot import main; main()"
