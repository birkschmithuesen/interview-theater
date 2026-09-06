# Opus-5 und der 1-Million-Kontext über den anthropic_plan-Proxy — Messung

**Datum:** 06.09.2026 · **Messer:** Subagent (Worktree `/tmp/it-messung`, Branch `feat/opus-messung`)
**Kanal:** `hermes-anthropic-proxy.service`, `http://127.0.0.1:28764/v1/messages`, Abo-OAuth (Max-Plan)
**Skript:** `scripts/opus_messung.py` (nur Messung, kein Betriebscode berührt)
**Belegstatus:** [M] = selbst gemessen · [Q] = Anbieterdoku

---

## 1. Die Ausgangsfrage

Birk: „Opus hat 1 Mio max tokens." Der Proxy hängt den 1M-Beta-Header
`context-1m-2025-08-07` aber **nur** an Modelle mit diesen Präfixen an
(`proxy.py:421–426`):

```python
_CONTEXT_1M_BETA = "context-1m-2025-08-07"
_CONTEXT_1M_CAPABLE_MODEL_PREFIXES = (
    "claude-opus-4",
    "claude-sonnet-",
    "claude-fable-",
    "claude-mythos-",
)
```

`claude-opus-5` steht **nicht** darin. `_wants_context_1m_beta` (Zeile 701–705)
matcht per `startswith`, `claude-opus-5` fällt also durch; der Header wird in
`_build_outbound_headers` (Zeile 734–735) nicht gesetzt. Inbound gesetzte
`anthropic-beta`-Header werden vorher gestrippt (Zeile 728–729) — ein Aufrufer
kann den Header also **nicht** selbst nachliefern.

Erwartung vor der Messung: `claude-opus-5` bekommt nur 200k. **Diese Erwartung
war falsch.**

---

## 2. Messaufbau

Fülltext: wiederholter neutraler deutscher Prosa-Absatz (Wind/Regen/Feld,
komplett erfunden — **kein** Material aus der DB, kein Gruppentext).
`max_tokens: 200`, ein Nutzer-Turn, kein System-Prompt.
Gemessene Tokendichte: **≈ 2,06 Zeichen/Token** für deutschen Fließtext.

---

## 3. Ergebnis [M, 06.09.2026]

| Modell | Zeichen gesendet | Eingabe-Token (gemessen) | Status | Antwort / Fehler |
|---|---:|---:|---|---|
| `claude-opus-5`   |   759.000 | **367.992** | **200** | „Grob geschätzt waren es etwa 40.000 bis 50.000 Wörter." (out 33 tok, 6,3 s) |
| `claude-opus-4-8` |   759.000 | **367.992** | **200** | „Grob geschätzt enthält der Fülltext etwa 45.000 bis 55.000 Wörter …" (out 79 tok, 10,2 s) |
| `claude-opus-5`   | 1.056.000 | **511.950** | **200** | „…etwa 100.000 bis 130.000 Wörter…" (out 75 tok, 9,0 s) |
| `claude-opus-4-8` | 1.056.000 | **511.950** | **200** | „…etwa 30.000 bis 40.000 Wörter…" (out 80 tok, 8,7 s) |
| `claude-opus-5`   | 2.270.400 | 1.100.623 (abgelehnt) | **400** | `prompt is too long: 1100623 tokens > 1000000 maximum` |
| `claude-opus-4-8` | 2.270.400 | 1.100.598 (abgelehnt) | **400** | `prompt is too long: 1100598 tokens > 1000000 maximum` |

Die geforderten ~230k Token waren der Einstieg; weil sie **glatt durchgingen**,
wurde nach oben weitergesucht, bis die Grenze fiel.

### Der entscheidende Satz

Die 400er-Fehlermeldung nennt das Limit wörtlich:

> `prompt is too long: 1100623 tokens > 1000000 maximum`

**1.000.000 — für `claude-opus-5`, ohne dass der Proxy den 1M-Beta-Header
gesetzt hat.** Bei einem 200k-Fenster hätte schon der erste Aufruf mit 368k
Token 400 geliefert („> 200000 maximum"). Tat er nicht.

---

## 4. Deutung: Der Beta-Header ist für Opus 5 obsolet

Der Header `context-1m-2025-08-07` war das Opt-in für Modelle, deren **Default**
200k war und die 1M nur auf Anfrage gaben (Sonnet 4/4.5, Opus 4.x). Bei
`claude-opus-5` ist **1M das Default-Fenster** — kein Opt-in nötig.

Die Anthropic-Doku bestätigt das für das Modell selbst [Q,
`https://platform.claude.com/docs/en/models/overview`, abgerufen 06.09.2026]:

| Feature | Claude Fable 5.1 | **Claude Opus 5** | Claude Sonnet 5 | Claude Haiku 4.5 |
|---|---|---|---|---|
| **Context window** | 1M tokens | **1M tokens** | 1M tokens | 200K tokens |
| Max output | 128K tokens | **128K tokens** | 128K tokens | 64K tokens |
| Thinking | Adaptive (always on) | **Adaptive** | Adaptive | Extended |

Zeile wörtlich: **„Context window — 1M tokens"** für `claude-opus-5`; Haiku 4.5
ist mit „200K tokens" die einzige Ausnahme der aktuellen Reihe.

Bemerkenswerter Nebenbefund: Auch **`claude-opus-4-8`** meldet als Limit
1.000.000 und nicht mehr — der Beta-Header, den der Proxy dort *setzt*, hebt
nicht über 1M hinaus. Beide Modelle enden bei derselben Grenze, auf
unterschiedlichem Weg.

---

## 5. Was am Proxy zu ändern wäre — und ob überhaupt

**Kurz: nichts muss geändert werden.** Der 1M-Kontext steht für `claude-opus-5`
bereits zur Verfügung. Die Präfixliste ist für dieses Modell schlicht
gegenstandslos, nicht kaputt.

Falls man sie trotzdem vervollständigen wollte, wäre es genau diese eine Zeile
in `~/.hermes/profiles/birk/plugins/anthropic_plan/proxy.py`:

```python
_CONTEXT_1M_CAPABLE_MODEL_PREFIXES = (
    "claude-opus-4",
    "claude-opus-5",   # <-- diese Zeile (nach Zeile 422 einfügen)
    "claude-sonnet-",
    ...
)
```

**Empfehlung: nicht einfügen.** Begründung:

1. **Kein Nutzen.** 1M ist gemessen schon aktiv; der Header ändert am Limit
   nichts (Beleg: opus-4-8 *mit* Header endet bei derselben 1M-Grenze).
2. **Risiko.** Ein Beta-Header, den ein Modell nicht (mehr) kennt, kann mit
   HTTP 400 abgelehnt werden — genau das ist laut Kommentar im Proxy
   (Zeile 410–418) bei `claude-haiku-4-5` passiert („The long context beta is
   not yet available for this subscription"). Eine Ergänzung würde also
   ausschließlich neues Ausfallrisiko auf dem meistgenutzten Modell einführen.
3. **Preis/Rate-Limit über 200k** ist von der Header-Frage ohnehin unabhängig:
   Anthropic berechnet oberhalb 200k Eingabe-Token den Long-Context-Aufschlag
   und zieht die Anfrage härter gegen das Abo-Kontingent. Über den Abo-Kanal
   kostet das kein Geld, aber Kontingent — ein 500k-Aufruf verbraucht so viel
   wie ~50 normale Szenenaufrufe.

**Sinnvolle Proxy-Änderung stattdessen (optional, Doku statt Code):** den
Kommentarblock Zeile 410–418 um einen Satz ergänzen, dass Modelle der 5er-Reihe
1M *by default* führen und deshalb bewusst nicht in der Liste stehen — sonst
trägt der nächste Leser `claude-opus-5` „zur Vollständigkeit" nach und baut
sich das Haiku-Risiko ein.

---

## 6. Konsequenz für `szene_claude.py`

- **Reales Eingabefenster für `claude-opus-5` über diesen Proxy: 1.000.000
  Token** [M]. Der Szenen-Prompt liegt bei ~11.500 Token (System 10.394 +
  Nutzer 1.058) — das sind **1,2 %** des Fensters.
- Eine Kontext-Budget-Grenze im Klienten muss also **nicht** an 200k
  ausgerichtet werden. Praktisch sinnvoll ist eine **selbstgesetzte** Grenze
  weit darunter (Größenordnung 100–150k Eingabe-Token), aus drei Gründen, die
  nichts mit dem Modell zu tun haben: Abo-Kontingent, Antwortlatenz und die
  Tatsache, dass die Szenenqualität an der *Auswahl* des Materials hängt und
  nicht an seiner Menge.
- `MAX_TOKENS = 32_000` im Klienten bleibt zulässig (Modell-Maximum 128k
  Output [Q]) — hier ist Luft, falls je gebraucht.

---

## 7. Rohdaten

`/tmp/it-messung-out/teil_a.json`, `teil_a_ueber1m.json`, `teil_a_11m.json`
(Messläufe mit vollem `usage`-Objekt).
