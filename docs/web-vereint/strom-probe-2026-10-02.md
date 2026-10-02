# Strom-Probe 2026-10-02

| Weg | Teilstuecke | erstes bei | letztes bei | Zeichen | prompt_tokens | completion_tokens | finish |
|---|---|---|---|---|---|---|---|
| Infomaniak (schema + stream) | 51 | 0,35 s | 1,16 s | 171 | 61 | 63 | stop |
| Infomaniak (ohne stream) | — | — | 1,87 s | 158 | 61 | 68 | stop |
| Proxy (prosa + stream) | 45 | 5,38 s | 5,38 s | 277 | 118 | 264 | end_turn |

Hinweis: Infomaniak: die aufruf-Zeile unterscheidet sich zwischen Stream (prompt_tokens=61, completion_tokens=63) und Nicht-Stream (prompt_tokens=61, completion_tokens=68).

Befund: Infomaniak lehnt stream mit json_schema ab (HTTP unbekannt): der Gespraechszug streamt nicht, Szene und Kurzgeschichte schon. Entscheidung fuer Birk: Schema aufgeben und den Chat-Zug auf Prosa umstellen -- oder so lassen.
