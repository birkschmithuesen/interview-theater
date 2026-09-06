#!/usr/bin/env python3
"""Messskript: (A) 1M-Kontext je Modell ueber den anthropic_plan-Proxy,
(B) Thinking-Vergleich am realen Szenen-Prompt.

Nur Messung, kein Betriebscode. Schreibt JSON nach /tmp/it-messung-out/.
"""
import json, os, re, sys, time, urllib.request, urllib.error

PROXY = "http://127.0.0.1:28764/v1/messages"
OUT = "/tmp/it-messung-out"
os.makedirs(OUT, exist_ok=True)


def call(body, timeout=900):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        PROXY, data=data,
        headers={"content-type": "application/json",
                 "anthropic-version": "2023-06-01"},
        method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        dt = time.time() - t0
        return {"status": r.status, "dauer_s": round(dt, 1), "body": json.loads(raw)}
    except urllib.error.HTTPError as e:
        dt = time.time() - t0
        raw = e.read().decode(errors="replace")
        return {"status": e.code, "dauer_s": round(dt, 1), "fehler": raw[:2000]}
    except Exception as e:  # noqa
        return {"status": -1, "dauer_s": round(time.time() - t0, 1), "fehler": repr(e)[:2000]}


# ---------------------------------------------------------------- Teil A
FUELL = (
    "Der Wind trieb den feinen Regen ueber die leeren Felder, und die Reihen "
    "der Pappeln standen still am Rand des Weges. Ein Wagen fuhr langsam "
    "vorbei, die Scheinwerfer schnitten helle Streifen in den Dunst, dann war "
    "es wieder ruhig. Am Zaun haengte ein Schild, dessen Schrift die Jahre "
    "ausgewaschen hatten, sodass nur noch der Rahmen zu erkennen war. Weiter "
    "hinten lag ein Hof mit einem gedeckten Dach aus roten Ziegeln, und aus "
    "dem Schornstein stieg Rauch, den der Wind sofort flach zog. Die Tage "
    "wurden kuerzer, das Licht kam spaeter und ging frueher, und wer den Weg "
    "kannte, ging ihn auch im Halbdunkel ohne zu stolpern. "
)


def teil_a(modelle, ziel_token=230_000):
    # Kalibrieren: ein kurzer Aufruf sagt uns Token pro Zeichen nicht; wir
    # rechnen konservativ mit 3,3 Zeichen/Token fuer deutschen Text und
    # berichten den echten usage.input_tokens.
    n_zeichen = int(ziel_token * 3.3)
    text = (FUELL * (n_zeichen // len(FUELL) + 1))[:n_zeichen]
    res = []
    for m in modelle:
        body = {"model": m, "max_tokens": 200,
                "messages": [{"role": "user", "content":
                              "Hier ist ein langer Fuelltext, ignoriere ihn inhaltlich:\n\n"
                              + text +
                              "\n\nAntworte mit genau einem Satz: wie viele Woerter etwa "
                              "hast du oben gesehen? Schaetze grob."}]}
        r = call(body, timeout=600)
        u = (r.get("body") or {}).get("usage") or {}
        ct = (r.get("body") or {}).get("content") or []
        txt = " ".join(c.get("text", "") for c in ct if c.get("type") == "text")
        res.append({"modell": m, "zeichen": n_zeichen, "status": r["status"],
                    "dauer_s": r["dauer_s"],
                    "input_tokens": u.get("input_tokens"),
                    "output_tokens": u.get("output_tokens"),
                    "antwort": txt[:400], "fehler": r.get("fehler", "")[:600]})
        print(json.dumps(res[-1], ensure_ascii=False)[:900], flush=True)
    json.dump(res, open(f"{OUT}/teil_a.json", "w"), ensure_ascii=False, indent=1)
    return res


# ---------------------------------------------------------------- Teil B
def lade_prompt(pfad):
    roh = open(pfad, encoding="utf-8").read()
    sys_m = re.search(r"=== SYSTEM \([^)]*\) ===\n(.*?)\n=== NUTZER \([^)]*\) ===\n(.*)",
                      roh, re.S)
    return sys_m.group(1).strip(), sys_m.group(2).strip()


def masse(text):
    zeilen = [z.strip() for z in text.split("\n") if z.strip()]
    regie = [z for z in zeilen if z.startswith("(")]
    # Sprechzeile: FIGURENNAME: ... (Grossbuchstaben vor Doppelpunkt)
    sprech = [z for z in zeilen if re.match(r"^[A-ZÄÖÜ][A-ZÄÖÜa-zäöüß\- ]{1,25}:", z)]
    repliken = []
    figuren = set()
    for z in sprech:
        name, _, rest = z.partition(":")
        figuren.add(name.strip())
        repliken.append(len(rest.split()))
    n = len(regie) + len(sprech)
    return {"zeichen": len(text), "zeilen_gesamt": len(zeilen),
            "regie_zeilen": len(regie), "sprech_zeilen": len(sprech),
            "regie_anteil_pct": round(100 * len(regie) / n, 1) if n else 0.0,
            "figuren": sorted(figuren), "figurenzahl": len(figuren),
            "replik_woerter_mittel": round(sum(repliken) / len(repliken), 1) if repliken else 0,
            "replik_woerter_max": max(repliken) if repliken else 0}


def teil_b(modell, prompt_datei, varianten, laeufe=2):
    sys_txt, user_txt = lade_prompt(prompt_datei)
    tdir = f"{OUT}/texte"
    os.makedirs(tdir, exist_ok=True)
    res = []
    for vname, thinking in varianten:
        for i in range(1, laeufe + 1):
            body = {"model": modell, "max_tokens": 32_000,
                    "system": sys_txt,
                    "messages": [{"role": "user", "content": user_txt}]}
            if thinking:
                body["thinking"] = thinking
            r = call(body, timeout=1200)
            u = (r.get("body") or {}).get("usage") or {}
            ct = (r.get("body") or {}).get("content") or []
            txt = "\n".join(c.get("text", "") for c in ct if c.get("type") == "text").strip()
            think = "\n".join(c.get("thinking", "") for c in ct if c.get("type") == "thinking")
            rec = {"variante": vname, "lauf": i, "status": r["status"],
                   "dauer_s": r["dauer_s"], "stop_reason": (r.get("body") or {}).get("stop_reason"),
                   "input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                   "thinking_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
                   "thinking_zeichen": len(think),
                   "fehler": (r.get("fehler") or "")[:600]}
            if txt:
                fn = f"{tdir}/{vname}-lauf{i}.txt"
                open(fn, "w", encoding="utf-8").write(txt)
                rec.update(masse(txt))
                rec["datei"] = fn
            if think:
                open(f"{tdir}/{vname}-lauf{i}.thinking.txt", "w", encoding="utf-8").write(think)
            res.append(rec)
            print(json.dumps(rec, ensure_ascii=False)[:700], flush=True)
            json.dump(res, open(f"{OUT}/teil_b.json", "w"), ensure_ascii=False, indent=1)
    return res


if __name__ == "__main__":
    was = sys.argv[1]
    if was == "a":
        teil_a(["claude-opus-5", "claude-opus-4-8"])
    elif was == "a-klein":
        teil_a(["claude-opus-5", "claude-opus-4-8"], ziel_token=int(sys.argv[2]))
    elif was == "b-probe":
        # nur pruefen, welche thinking-Syntax das Modell akzeptiert (billig)
        s, u = lade_prompt(sys.argv[2])
        for name, th in [("enabled8k", {"type": "enabled", "budget_tokens": 8000}),
                         ("adaptive", {"type": "adaptive"})]:
            b = {"model": "claude-opus-5", "max_tokens": 9000, "thinking": th,
                 "messages": [{"role": "user", "content": "Sag nur: ok."}]}
            r = call(b, timeout=180)
            print(name, r["status"], (r.get("fehler") or json.dumps(
                (r.get("body") or {}).get("usage", {})))[:400], flush=True)
    elif was == "b":
        varianten = json.load(open(sys.argv[3]))
        teil_b("claude-opus-5", sys.argv[2], [(v["name"], v["thinking"]) for v in varianten])
