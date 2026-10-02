#!/usr/bin/env bash
# Schaltet Padua öffentlich: https://lab.artesmobiles.art/padua/
#
# EIN Befehl, als admin (sudo) auf herkules:
#   ssh admin@91.98.143.165 'sudo bash -s' < padua-nginx-einrichten.sh
#
# Muster: buehne-nginx-einrichten.sh. Idempotent. Rollback bei nginx -t-Fehler.
# Ziel: vServer im Tailnet, Port 8030 (Padua-Webdienst, getrennt von theatersoap:8010).
# Streaming (SSE) braucht proxy_buffering off + lange read_timeout.
# limit_req: max 10 Anfragen/s je IP, Burst 40 — Schutz gegen Flut, ohne Gruppen zu bremsen.
set -euo pipefail

CONF=/etc/nginx/sites-available/lab-artesmobiles
ZONE=/etc/nginx/conf.d/padua-limit.conf
ZIEL="http://100.75.24.33:8030/"
MARKE="location /padua/"

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }
[[ -f $CONF ]] || { echo "FEHLER: $CONF nicht gefunden." >&2; exit 1; }

SICHER="${CONF}.bak-$(date +%Y%m%d-%H%M%S)"
cp -a "$CONF" "$SICHER"; echo "Sicherung: $SICHER"
ZONE_NEU=0
if [[ ! -f $ZONE ]]; then
  echo 'limit_req_zone $binary_remote_addr zone=padua:10m rate=10r/s;' > "$ZONE"; ZONE_NEU=1
fi

if ! grep -q "$MARKE" "$CONF"; then
  LETZTE=$(grep -n '^}' "$CONF" | tail -1 | cut -d: -f1)
  [[ -n ${LETZTE:-} ]] || { echo "FEHLER: Server-Block-Ende nicht gefunden." >&2; exit 1; }
  BLOCK=$(cat <<EOF

    # --- Padua (InScribe-Workshop 05.-09.10.2026) ---
    location /padua/ {
        limit_req zone=padua burst=40 nodelay;
        client_max_body_size 30m;
        proxy_pass $ZIEL;
        proxy_http_version 1.1;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix /padua;
        proxy_buffering off;
        proxy_cache off;
        proxy_connect_timeout 5s;
        proxy_read_timeout    300s;
    }
EOF
)
  TMP=$(mktemp)
  head -n $((LETZTE - 1)) "$CONF" >  "$TMP"
  printf '%s\n' "$BLOCK"        >> "$TMP"
  tail -n +$LETZTE "$CONF"      >> "$TMP"
  cp "$TMP" "$CONF"; rm -f "$TMP"
else
  echo "Block existiert bereits."
fi

if ! nginx -t; then
  echo "nginx-Test FEHLGESCHLAGEN — Sicherung wird zurückgespielt." >&2
  cp -a "$SICHER" "$CONF"; [[ $ZONE_NEU == 1 ]] && rm -f "$ZONE"
  nginx -t && systemctl reload nginx || true
  exit 1
fi
systemctl reload nginx
sleep 1
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 https://lab.artesmobiles.art/padua/ || echo 000)
echo "nginx neu geladen. https://lab.artesmobiles.art/padua/ -> HTTP $CODE"
[[ $CODE == 502 ]] && echo "(502 = nginx ok, Padua-Dienst auf dem vServer läuft noch nicht — kommt von Karte A6)"
exit 0
