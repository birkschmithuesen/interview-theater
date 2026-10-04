# Testgruppe Padua — Kurzanleitung

Eine vierte, vom Betrieb getrennte Padua-Instanz für Tests während des
Workshops (05.–09.10.2026): eigene DB `betrieb/padua-test.db`, eigener
Webdienst (Port 8031, `/padua-test`), eigener Bot `padua-test`, genau **eine**
Gruppe mit der festen chat_id `7000000000099`. Sie erscheint nie auf der
Padua-Übersicht (8030), weil sie eine eigene Datenbank hat. Auf sie lässt sich
jederzeit der Stand einer echten Gruppe spielen. Der Link der Testgruppe
ändert sich dabei nie.

Alle Befehle aus dem Repo-Verzeichnis `~/projekte/interview-theater`.
`PY=~/.local/bin/python3.11` (derselbe wie in der Web-Unit).

## Einmalig einrichten (Robo, nach dem Merge)

1. **Env umstellen.** `betrieb/padua-test.env` auf die Zeilen aus
   `docs/padua-test.env.beispiel` bringen: `IT_KANAL=web`,
   `IT_WEB_CHAT_ID=7000000000099`, `IT_BOT_NAME=padua-test`,
   `IT_WEB_URL=https://lab.artesmobiles.art/padua-test`,
   `IT_DB=betrieb/padua-test.db`, `IT_AUDIO=audio-padua-test`,
   `IT_WORKSHOP=padua-2026`; die Zeile `IT_BOT_TOKEN` **entfernen**. Die
   Modell-/STT-Schlüssel bleiben. Den Inhalt der Datei nie ausgeben; prüfen
   nur so: `grep -c '^IT_KANAL=web$' betrieb/padua-test.env` → `1`,
   `grep -c '^IT_BOT_TOKEN=' betrieb/padua-test.env` → `0`,
   `grep -c '^IT_WORKSHOP=padua-2026$' betrieb/padua-test.env` → `1`.
2. **Alte Testdaten prüfen.** `$PY -m scripts.test_uebernehmen --leer`
   (Trockenlauf). Meldet er „fremde Gruppen" (Reste aus der Telegram-Zeit),
   je Gruppe löschen — das Skript tut das bewusst nicht selbst:
   `set -a; . ./betrieb/padua-test.env; set +a; $PY scripts/loeschen.py <chat_id>`
   (fragt nach, `ja` eintippen).
3. **Testgruppe anlegen.** `$PY -m scripts.test_uebernehmen --leer --ja`.
4. **Dashboard-Token als Drop-in** (nie in eine Datei im Repo):
   ```
   mkdir -p ~/.config/systemd/user/interview-theater-padua-test-web.service.d
   TOKEN=$($PY -c 'import secrets; print(secrets.token_urlsafe(24))')
   printf '[Service]\nEnvironment=IT_WEB_DASHBOARD_TOKEN=%s\n' "$TOKEN" \
     > ~/.config/systemd/user/interview-theater-padua-test-web.service.d/dashboard-token.conf
   chmod 600 ~/.config/systemd/user/interview-theater-padua-test-web.service.d/dashboard-token.conf
   echo "Uebersicht: https://lab.artesmobiles.art/padua-test/dashboard/$TOKEN"
   ```
   Vorlage: `docs/interview-theater-padua-test-web.service.d/dashboard-token.conf.beispiel`.
5. **Units.**
   ```
   cp docs/interview-theater-padua-test-web.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now interview-theater-padua-test-web.service
   systemctl --user enable --now interview-theater@padua-test.service
   ```
   Der Bot braucht **keine** eigene Unit-Datei: `interview-theater@.service`
   ist eine Vorlage, `%i` = `padua-test` → `betrieb/padua-test.env`
   (`scripts/betrieb-start.sh`), Log `betrieb/padua-test.log`. Web-Log:
   `betrieb/padua-test-web.log`.
6. **nginx (Birk, fehlt noch):** auf herkules einen Block `/padua-test/` →
   `http://100.75.24.33:8031/padua-test/`, sonst identisch mit `/padua/`
   (dieselben `proxy_set_header`, `proxy_buffering off;`,
   `X-Forwarded-Prefix /padua-test`). Ohne ihn ist die Testinstanz nur im
   Tailnet erreichbar.

## Benutzen

```
# 1. Was wuerde passieren? (nur Zaehlungen, schreibt nichts)
$PY -m scripts.test_uebernehmen <quell_chat_id>

# 2. Testbot stoppen -- sonst verweigert das Skript
systemctl --user stop interview-theater@padua-test

# 3. Wirklich uebernehmen (legt vorher selbst ein Backup an)
$PY -m scripts.test_uebernehmen <quell_chat_id> --ja

# 4. Testbot starten
systemctl --user start interview-theater@padua-test

# 5. Link der Testgruppe (aendert sich nie)
IT_DB=betrieb/padua-test.db IT_WEB_URL=https://lab.artesmobiles.art/padua-test $PY scripts/web_links.py
```

chat_ids der echten Gruppen: `padua-gruppe1` = `7000000000000`, die anderen
in ihren Env-Dateien (`IT_WEB_CHAT_ID`), ohne die Datei auszugeben:
`grep '^IT_WEB_CHAT_ID=' betrieb/padua-gruppe2.env`.

Zurück auf frische Phase 1: Testbot stoppen,
`$PY -m scripts.test_uebernehmen --leer --ja`, Testbot starten.

Backups liegen als `betrieb/padua-test.db.bak-<zeit>` daneben. Aufräumen von
Hand, wenn die Woche vorbei ist.

## Was übernommen wird

Alles, was in der Quelle an der Gruppe hängt (`db.TABELLEN_MIT_CHAT_ID`),
mit **unveränderten ids**, außer `aufruf` (Kosten — die Testgruppe beginnt
den Tag mit leerem Deckel) und `web_strom` (flüchtig). Die Quelle wird nur
gelesen. Audio wird kopiert, nie verschoben.

## Fallen

- **Nie `cp` auf eine `.db`.** WAL: was im `-wal` steht, fehlte der Kopie.
  Das Skript kopiert per `VACUUM INTO` aus einer read-only-Verbindung.
- **Wasserzeichen.** Der Bot liest im Web-Kanal ab `bot_zustand.letzte_update_id + 1`.
  Das Skript setzt den Offset des Testbots auf die höchste `web_post`-id,
  sonst beantwortete er die ganze Historie noch einmal. Deshalb muss er bei
  `--ja` **gestoppt** sein: sein laufender Poll hält den alten Offset bis zu
  25 s fest. Das Tell, falls es doch passiert: der Testbot antwortet auf
  alte Nachrichten. Das Gegenteil (Bot schweigt, 200 OK, kein Traceback)
  hieße, der Offset steht über neuen Eingängen. Dann `--ja` erneut laufen
  lassen.
- **Fremde chat_ids.** Die Test-DB darf nur die Testgruppe enthalten (die
  ids werden 1:1 übernommen und kollidierten sonst). Das Skript verweigert
  und nennt den Löschbefehl.
- **Laufende Aufnahme in der Quelle.** Verweigert. Später noch einmal.
- **Unfertige Aufnahmen** (Status `empfangen`/`transkribiert`) holt der
  Nachhol-Arbeiter des Testbots nach dem Start nach. Das kostet Whisper auf
  dem Deckel der Testgruppe.
