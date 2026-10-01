"""Der kostenlose Nachweis fuer Laengen-Budget und Sprachpass (30.09.2026,
Karte R).

**Warum es das gibt.** Der Simulator (``scripts/simulation.py``) erreicht
gemessen die Prosa-Phase, aber nicht den Feinschliff und nicht den
Kuerzungsweg. Ein bezahlter Lauf ist damit kein vollstaendiger Nachweis fuer
die Zusagen dieser Karte. Dieses Skript fuehrt denselben Codepfad
(``szene.starte`` -> ``szene.schreibe`` -> ``nachpass.nach_szene``) mit einer
**Attrappe** statt eines Modells und zeigt die Zahlen als Tabelle.

**Kein Test, kein Ersatz fuer pytest -- aber auch kein Geld.** Es hat keine
Sollwerte; die Zusagen stehen in ``tests/test_nachpass*.py``. Es ist ein
Berichtswerkzeug wie ``scripts/dramaturgie_pruefen.py --nur-mechanik``.

**Die Datenbank ist eine Wegwerf-Datei** (``tempfile``), nie ``IT_DB`` -- wie
``scripts/pruefe_prompts.py``. Das Material ist erfunden.

    $PY -m scripts.laengen_probe
    $PY -m scripts.laengen_probe --formen dialog,chor,rap,lied --faktor 0.25
    $PY -m scripts.laengen_probe --markdown   # fuer BEFUND.md
"""

from __future__ import annotations

import argparse
import os
import tempfile

#: Erfundenes Material, jedes Stueck absichtlich auffaellig: zu lang UND mit
#: mindestens einem der vier Sprachmuster. Eine Probe, deren Material nichts
#: ausloest, beweist eine leere Tabelle.
TEXTE: dict[str, str] = {
    "lang_und_dashes": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: She waited—and waited—and waited—and then she left.\n"
    ),
    "lang_und_nicht_sondern": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: It was not a home but a waiting room.\n"
    ),
    "lang_und_dreier": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: She was tired, angry, and alone.\n"
    ),
    "lang_und_fazit": (
        "MIRA: " + ("word " * 700)
        + "\nPAL: Maybe home is just where you stop explaining.\n"
    ),
}

#: Die Antwort des Nachpasses: kurz und sauber. Damit zeigt die Tabelle den
#: Erfolgsfall; den Fehlschlagfall zeigen die Tests.
SAUBER = "MIRA: You are late.\nPAL: I was here.\n"

_KOPF = ("TITEL: At the pier\nKURZ: They meet.\n"
         "ZUSAMMENFASSUNG: Mira and Pal meet at the pier.\n"
         "ANDERS GEMACHT: nothing\n\n")


class Attrappe:
    """Erst der lange Text, danach der saubere -- und sie zaehlt mit."""

    def __init__(self, lang: str):
        self.antworten = [_KOPF + lang, _KOPF + SAUBER]
        self.aufrufe: list[str] = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe.append(art)
        return self.antworten[min(len(self.aufrufe) - 1, 1)]


class TelegramStumm:
    """Nimmt alles an und sagt nichts. Kein Netz."""

    def sende(self, *a, **k):
        return None

    def __getattr__(self, name):
        return lambda *a, **k: None


def probe(formen: list[str], faktor: float = 1.0) -> list[dict]:
    """Fuehrt je Form eine Szene durch den echten Codepfad und liefert je
    Szene eine Zeile.

    ``IT_WORKSHOP`` wird hier gesetzt, nicht vom Aufrufer erwartet: das Skript
    misst ausdruecklich das Padua-Verhalten. **Und danach zurueckgesetzt**,
    samt Profil-Cache: ohne das bliebe der Prozess, der ``probe`` gerufen hat,
    auf Padua stehen -- gemessen an der Testsuite, in der danach rund hundert
    Tests englische statt deutscher Texte lasen."""
    from interview_theater import workshop

    vorher = os.environ.get("IT_WORKSHOP")
    os.environ["IT_WORKSHOP"] = "padua-2026"
    try:
        return _probe(formen, faktor)
    finally:
        if vorher is None:
            os.environ.pop("IT_WORKSHOP", None)
        else:
            os.environ["IT_WORKSHOP"] = vorher
        workshop.vergiss()


def _probe(formen: list[str], faktor: float) -> list[dict]:
    from interview_theater import (
        db, einstellungen, laengen, nachpass, phasen, repo, sprachpass,
        szene, workshop,
    )

    workshop.vergiss()
    verzeichnis = tempfile.mkdtemp(prefix="laengen-probe-")
    conn = db.verbinde(os.path.join(verzeichnis, "probe.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "probe", "Probe")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "At the canal, at night")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Two lose each other.\nEnd: open")
    repo.setze_figur(conn, 1, "Mira", "wants to be asked")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    if faktor != 1.0:
        laengen.setze_faktor(conn, 1, faktor)
    e = einstellungen.Einstellungen(
        bot_token="T", bot_name="probe",
        db_pfad=os.path.join(verzeichnis, "probe.db"),
        audio_verz=os.path.join(verzeichnis, "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K",
        llm_modell="attrappe", stt_basis="https://stt.test",
        stt_produkt="P", erkenner_modell="attrappe",
    )
    for nummer, form in enumerate(formen, start=1):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        for feld, wert in (("form", form), ("ort", "pier"),
                           ("was_passiert", "They meet.")):
            repo.setze_szenenfeld(conn, szene_id, feld, wert)
        repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "probe")

    zeilen: list[dict] = []
    namen = list(TEXTE)
    tg = TelegramStumm()
    for nummer, form in enumerate(formen, start=1):
        klm = Attrappe(TEXTE[namen[(nummer - 1) % len(namen)]])
        ziel = szene.ziel_fuer(conn, 1, f"Schreib Szene {nummer}")
        budget = szene.budget_fuer_szene(conn, 1, ziel)
        thread = szene.starte(conn, tg, klm, e, 1, f"Schreib Szene {nummer}")
        if thread is not None:
            thread.join(timeout=60)
        # Nach dem Lauf: was steht in der Szene, und was fand der Zaehler?
        aktuell = next(s for s in repo.hole_szenen(conn, 1)
                       if s["nummer"] == nummer)
        vorher_text = _KOPF + TEXTE[namen[(nummer - 1) % len(namen)]]
        nachher_text = aktuell["volltext"] or ""
        zeilen.append({
            "nummer": nummer,
            "form": form,
            "budget": budget,
            "woerter_vorher": laengen.zaehle_woerter(vorher_text),
            "woerter_nachher": laengen.zaehle_woerter(nachher_text),
            "zaehler_vorher": sprachpass.rohzahlen(vorher_text),
            "zaehler_nachher": sprachpass.rohzahlen(nachher_text),
            "laeufe": len(klm.aufrufe),
            "arten": ",".join(klm.aufrufe),
        })
    conn.close()
    return zeilen


def tabelle(zeilen: list[dict]) -> str:
    """Die Zeilen als Markdown-Tabelle -- dieselbe Form, die in
    ``BEFUND.md`` steht."""
    kopf = ("| Szene | Form | Budget | Woerter vorher | Woerter nachher | "
            "Zaehler vorher | Zaehler nachher | Laeufe |")
    strich = "|---|---|---|---|---|---|---|---|"
    def kurz(z: dict) -> str:
        return ", ".join(f"{k[:4]}={v}" for k, v in z.items() if v)
    reihen = [
        f"| {z['nummer']} | {z['form']} | {z['budget']} | "
        f"{z['woerter_vorher']} | {z['woerter_nachher']} | "
        f"{kurz(z['zaehler_vorher']) or '-'} | "
        f"{kurz(z['zaehler_nachher']) or '-'} | {z['laeufe']} ({z['arten']}) |"
        for z in zeilen
    ]
    return "\n".join([kopf, strich] + reihen)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--formen", default="dialog,chor,rap,lied,monolog",
                   help="Kommaliste der Formen, eine Szene je Form")
    p.add_argument("--faktor", type=float, default=1.0,
                   help="Laengen-Faktor (0,25 = Instagram)")
    p.add_argument("--markdown", action="store_true",
                   help="nur die Tabelle, zum Einfuegen in BEFUND.md")
    a = p.parse_args(argv)
    zeilen = probe([f.strip() for f in a.formen.split(",") if f.strip()],
                   a.faktor)
    text = tabelle(zeilen)
    if not a.markdown:
        text = (f"Laengen-Probe, Faktor {a.faktor:g}, Attrappe statt Modell "
                f"-- kostet nichts.\n\n{text}")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
