"""Ein echter Stream-Aufruf gegen Infomaniak und gegen den Proxy.

**Kein Test, laeuft nie automatisch, kostet Geld** -- wie
``scripts/rauchtest.py``. Zwei Aufrufe mit kleinem ``max_tokens``, gegen eine
**Wegwerf-Datenbank**, mit **erfundenem** Material. Gemessen wird nur, was die
Karte wissen muss:

1. Kommt mehr als ein Teilstueck, und verteilt ueber mehr als eine Sekunde?
2. Steht am Ende eine ``usage`` (sonst greift der Rueckfall, und der
   Kostendeckel E7 stuende auf Schaetzungen)?
3. Ist die ``aufruf``-Zeile dieselbe wie ohne Stream?
4. Geht bei einem Reasoning-Modell wirklich nichts aus der Denkspur an die
   Gruppe?

Das Protokoll enthaelt **nur Zahlen** -- Zeitpunkte, Laengen, Anzahl, usage.
Kein Prompt, keine Antwort, keine Echtdaten.

    set -a; . ./betrieb/gruppe1.env; set +a
    python -m scripts.strom_probe --bericht

**IT_DB wird ausdruecklich verworfen** (wie ``scripts/pruefe_prompts.py``):
dieser Lauf schreibt seine ``aufruf``- und ``vorfall``-Zeilen in eine
Wegwerf-Datenbank in einem Temporaerverzeichnis, nie in die Betriebsdatenbank
-- egal, was ``IT_DB`` gerade sagt. Verweigert wird damit nicht durch einen
Vergleich und einen Fehlerabbruch, sondern dadurch, dass der Schreibpfad
dieses Skripts die Betriebsdatenbank nie erreicht.

**Wenn Infomaniak ``stream`` mit ``json_schema`` ablehnt**, faellt
``llm.py`` selbst auf einen blockierenden Versuch zurueck (Prozessflagge
``_STROM_AUS``) -- dieses Skript wirft dafuer keinen Fehler, sondern liest
den Vorfall ``strom_nicht_verfuegbar`` aus der Wegwerf-Datenbank und meldet
ihn als Befund. Exit-Code ist in jedem Fall ``0``: eine Messung hat kein
Ergebnis, das "falsch" waere.

**Nichts am Prompt oder am Schema wird veraendert, um Streaming zu
erzwingen** -- ``ablauf.SCHEMA`` ist genau das Schema des Gespraechszugs,
unveraendert.
"""

import argparse
import re
import sys
import tempfile
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import ablauf, db, einstellungen, llm, szene_claude

#: Wohin --bericht ohne Pfadangabe schreibt.
BERICHTE = Path(__file__).resolve().parent.parent / "docs" / "web-vereint"

#: Erfundener Auftrag fuer den Gespraechsweg -- klein und ohne jeden Bezug zu
#: echtem Workshop-Material.
SYSTEM_INFOMANIAK = (
    "Du bist der Gespraechs-Bot eines Theaterworkshops. Antworte kurz und "
    "sachlich auf die Bitte der Gruppe."
)
NUTZER_INFOMANIAK = "Schreib drei Saetze ueber einen Bahnhof bei Nacht."

#: Erfundener Auftrag fuer den Proxy-Weg (Szenen-/Prosalauf-Form).
SYSTEM_PROXY = (
    "Du schreibst einen kurzen Theatertext fuer einen Jugend-Workshop."
)
NUTZER_PROXY = (
    "Schreib einen kurzen Dialog (hoechstens fuenf Zeilen) zwischen zwei "
    "Personen an einem Bahnhof bei Nacht."
)

#: Voruebergehend klein gesetzt (Schritt 1 Punkt 5 der Karte): der Messlauf
#: soll billig bleiben, nicht die produktive Szenenlaenge abbilden. Kein
#: Monkeypatch -- der Modulwert wird direkt gesetzt und danach wieder
#: zurueckgesetzt (``_messe_proxy``).
PROXY_MAX_TOKENS = 400


class _Sammler:
    """Nimmt jedes Teilstueck eines Streams entgegen und merkt sich nur
    Zahlen fuer den Bericht (Zeitpunkt, Laenge) -- der Text selbst bleibt im
    Prozessspeicher, damit ``nicht_praefix`` ihn gegen die Endantwort
    pruefen kann, geht aber nie in den Bericht."""

    def __init__(self, start: float) -> None:
        self._start = start
        self.zeiten: list[float] = []
        self.laengen: list[int] = []
        self._texte: list[str] = []

    def __call__(self, text: str) -> None:
        self.zeiten.append(time.monotonic() - self._start)
        self.laengen.append(len(text))
        self._texte.append(text)

    @property
    def anzahl(self) -> int:
        return len(self.zeiten)

    @property
    def erstes_bei(self) -> float | None:
        return self.zeiten[0] if self.zeiten else None

    @property
    def letztes_bei(self) -> float | None:
        return self.zeiten[-1] if self.zeiten else None

    def nicht_praefix(self, endtext: str) -> int:
        """Wie viele Teilstuecke KEIN Praefix der Endantwort waren -- die
        mechanische Gegenprobe zu Schritt 1 Punkt 4: geht etwas aus einer
        Denkspur an ein Teilstueck, waere es dort ein Fremdkoerper und kein
        wachsender Praefix mehr. Normalerweise 0."""
        if not endtext:
            return 0
        return sum(1 for t in self._texte if t and not endtext.startswith(t))


def _max_id(conn, tabelle: str) -> int:
    zeile = conn.execute(f"SELECT COALESCE(MAX(id), 0) AS m FROM {tabelle}").fetchone()
    return zeile["m"]


def _neue_vorfaelle(conn, art: str, seit_id: int) -> list[str]:
    zeilen = conn.execute(
        "SELECT detail FROM vorfall WHERE art = ? AND id > ? ORDER BY id",
        (art, seit_id),
    ).fetchall()
    return [z["detail"] for z in zeilen]


def _letzte_aufruf_zeile(conn) -> dict:
    zeile = conn.execute(
        "SELECT tatsaechliche_token, antwort_token, finish_reason "
        "FROM aufruf ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(zeile) if zeile else {}


def _http_code_aus(detail_zeilen: list[str]) -> str | None:
    for detail in detail_zeilen:
        treffer = re.search(r"HTTP (\d+)", detail or "")
        if treffer:
            return treffer.group(1)
    return None


def _messe_infomaniak(conn, e, klient) -> tuple[list[dict], list[str], str | None]:
    """Zwei Aufrufe (Schritt 1 Punkt 3+4 der Karte): einmal mit ``bei_teil``
    (Stream), einmal ohne (Vergleich). Beide ueber ``LLM.schema`` mit
    ``ablauf.SCHEMA`` -- demselben Schema wie der Gespraechszug."""
    klm = llm.LLM(e, klient, conn)
    hinweise: list[str] = []

    vorfall_vorher = _max_id(conn, "vorfall")
    start = time.monotonic()
    sammler = _Sammler(start)
    fehler_text = None
    antwort = ""
    try:
        ergebnis = klm.schema(
            None, SYSTEM_INFOMANIAK, NUTZER_INFOMANIAK, ablauf.SCHEMA,
            "strom_probe", bei_teil=sammler,
        )
        antwort = ergebnis.get("antwort") or ""
    except llm.LLMFehler as fehler:
        fehler_text = str(fehler)
    letzte = _letzte_aufruf_zeile(conn)
    neue_vorfaelle = _neue_vorfaelle(conn, "strom_nicht_verfuegbar", vorfall_vorher)
    http_code = _http_code_aus(neue_vorfaelle)
    nicht_praefix = sammler.nicht_praefix(antwort)

    zeile_stream = {
        "weg": "Infomaniak (schema + stream)",
        "teilstuecke": sammler.anzahl or None,
        "erstes_bei": sammler.erstes_bei,
        "letztes_bei": sammler.letztes_bei,
        "zeichen": len(antwort),
        "prompt_tokens": letzte.get("tatsaechliche_token"),
        "completion_tokens": letzte.get("antwort_token"),
        "finish": letzte.get("finish_reason") or fehler_text,
    }

    if neue_vorfaelle:
        hinweise.append(
            "Infomaniak hat den Stream fuer diesen Prozess abgeschaltet "
            f"({neue_vorfaelle[0]})."
        )
    if not llm.strom_moeglich():
        hinweise.append(
            "llm.strom_moeglich() ist jetzt False: jeder weitere "
            "Infomaniak-Aufruf dieses Prozesses laeuft blockierend "
            "(Prozessflagge _STROM_AUS)."
        )
    elif sammler.anzahl <= 1:
        hinweise.append(
            "Infomaniak: nur ein Teilstueck erhalten -- kein erkennbares "
            "Streaming in diesem Lauf."
        )
    if nicht_praefix:
        hinweise.append(
            f"Infomaniak: {nicht_praefix} Teilstueck(e) waren KEIN Praefix "
            "der Endantwort (Gegenprobe gegen Denkspur-Text im Teilstueck)."
        )

    # Vergleichsaufruf ohne Stream (Schritt 1 Punkt 4 der Karte).
    start2 = time.monotonic()
    fehler_text2 = None
    antwort2 = ""
    try:
        ergebnis2 = klm.schema(
            None, SYSTEM_INFOMANIAK, NUTZER_INFOMANIAK, ablauf.SCHEMA,
            "strom_probe",
        )
        antwort2 = ergebnis2.get("antwort") or ""
    except llm.LLMFehler as fehler:
        fehler_text2 = str(fehler)
    dauer2 = time.monotonic() - start2
    letzte2 = _letzte_aufruf_zeile(conn)

    zeile_blockierend = {
        "weg": "Infomaniak (ohne stream)",
        "teilstuecke": None,
        "erstes_bei": None,
        "letztes_bei": dauer2,
        "zeichen": len(antwort2),
        "prompt_tokens": letzte2.get("tatsaechliche_token"),
        "completion_tokens": letzte2.get("antwort_token"),
        "finish": letzte2.get("finish_reason") or fehler_text2,
    }

    if (zeile_stream["prompt_tokens"], zeile_stream["completion_tokens"]) != (
        zeile_blockierend["prompt_tokens"], zeile_blockierend["completion_tokens"],
    ):
        hinweise.append(
            "Infomaniak: die aufruf-Zeile unterscheidet sich zwischen Stream "
            f"(prompt_tokens={zeile_stream['prompt_tokens']}, "
            f"completion_tokens={zeile_stream['completion_tokens']}) und "
            f"Nicht-Stream (prompt_tokens={zeile_blockierend['prompt_tokens']}, "
            f"completion_tokens={zeile_blockierend['completion_tokens']})."
        )

    return [zeile_stream, zeile_blockierend], hinweise, http_code


def _messe_proxy(conn, e, klient) -> tuple[dict, list[str]]:
    """Ein Aufruf ueber ``szene_claude.prosa`` mit kleinem ``MAX_TOKENS``
    (Schritt 1 Punkt 5 der Karte). Kein Monkeypatch: der Modulwert wird
    direkt gesetzt und im ``finally`` wieder zurueckgenommen."""
    alter_max_tokens = szene_claude.MAX_TOKENS
    szene_claude.MAX_TOKENS = PROXY_MAX_TOKENS
    hinweise: list[str] = []
    vorfall_vorher = _max_id(conn, "vorfall")
    start = time.monotonic()
    sammler = _Sammler(start)
    fehler_text = None
    text = ""
    try:
        text = szene_claude.prosa(
            conn, e, klient, None, SYSTEM_PROXY, NUTZER_PROXY,
            "strom_probe_claude", timeout=120.0, bei_teil=sammler,
        )
    except szene_claude.ClaudeFehler as fehler:
        fehler_text = str(fehler)
    finally:
        szene_claude.MAX_TOKENS = alter_max_tokens

    letzte = _letzte_aufruf_zeile(conn)
    neue_vorfaelle = _neue_vorfaelle(conn, "strom_nicht_verfuegbar", vorfall_vorher)
    nicht_praefix = sammler.nicht_praefix(text)

    zeile = {
        "weg": "Proxy (prosa + stream)",
        "teilstuecke": sammler.anzahl or None,
        "erstes_bei": sammler.erstes_bei,
        "letztes_bei": sammler.letztes_bei,
        "zeichen": len(text),
        "prompt_tokens": letzte.get("tatsaechliche_token"),
        "completion_tokens": letzte.get("antwort_token"),
        "finish": letzte.get("finish_reason") or fehler_text,
    }

    if neue_vorfaelle:
        hinweise.append(
            f"Proxy hat den Stream fuer diesen Prozess abgeschaltet "
            f"({neue_vorfaelle[0]})."
        )
    if szene_claude._abgeschaltet():
        hinweise.append(
            "szene_claude._abgeschaltet() ist jetzt True: jeder weitere "
            "Szenenlauf dieses Prozesses ueber den Proxy laeuft blockierend."
        )
    elif sammler.anzahl <= 1:
        hinweise.append(
            "Proxy: nur ein Teilstueck erhalten -- kein erkennbares "
            "Streaming in diesem Lauf."
        )
    if nicht_praefix:
        hinweise.append(
            f"Proxy: {nicht_praefix} Teilstueck(e) waren KEIN Praefix der "
            "Endantwort (Gegenprobe gegen Denkspur-Text im Teilstueck)."
        )

    return zeile, hinweise


def _zahl(wert) -> str:
    return "—" if wert is None else str(wert)


def _sekunden(wert: float | None) -> str:
    if wert is None:
        return "—"
    return f"{wert:.2f}".replace(".", ",") + " s"


def _zeile_markdown(z: dict) -> str:
    return (
        f"| {z['weg']} | {_zahl(z.get('teilstuecke'))} | "
        f"{_sekunden(z.get('erstes_bei'))} | {_sekunden(z.get('letztes_bei'))} | "
        f"{_zahl(z.get('zeichen'))} | {_zahl(z.get('prompt_tokens'))} | "
        f"{_zahl(z.get('completion_tokens'))} | {z.get('finish') or '—'} |"
    )


def baue_bericht(
    zeilen: list[dict], befund: str, *, datum: str | None = None,
    hinweise: list[str] | None = None,
) -> str:
    """Baut den Markdown-Bericht aus Schritt 1 Punkt 6 der Karte -- eine
    reine Funktion aus Zahlen, kein Prompt, keine Antwort. Pruefbar ohne
    Netz, siehe Modultest-Aufruf in ``.superpowers/sdd/task-17-report.md``."""
    datum = datum or date.today().isoformat()
    zeilen_text = [
        f"# Strom-Probe {datum}",
        "",
        "| Weg | Teilstuecke | erstes bei | letztes bei | Zeichen | "
        "prompt_tokens | completion_tokens | finish |",
        "|---|---|---|---|---|---|---|---|",
    ]
    zeilen_text += [_zeile_markdown(z) for z in zeilen]
    zeilen_text.append("")
    if hinweise:
        zeilen_text += [f"Hinweis: {h}" for h in hinweise]
        zeilen_text.append("")
    zeilen_text.append(f"Befund: {befund}")
    return "\n".join(zeilen_text)


def befund_satz(zeilen: list[dict], http_code: str | None = None) -> str:
    """Schritt 3 der Karte: EIN Satz, automatisch aus den Messwerten gewaehlt.

    Traegt ANNAHME 4 (mehr als ein Teilstueck, Abstand > 1 s, usage gesetzt),
    gilt der tragende Satz; sonst der Rueckfall-Satz mit dem gemessenen
    HTTP-Code (oder 'unbekannt', wenn keiner vorlag -- z. B. bei einem
    Abbruch mitten im Stream statt einer sofortigen Ablehnung)."""
    stream_zeile = next(
        (z for z in zeilen if z["weg"] == "Infomaniak (schema + stream)"), None
    )
    if stream_zeile is None:
        return "Infomaniak wurde in diesem Lauf nicht gemessen (--nur proxy)."

    mehr_als_eins = (stream_zeile.get("teilstuecke") or 0) > 1
    erstes = stream_zeile.get("erstes_bei")
    letztes = stream_zeile.get("letztes_bei")
    abstand_gross = (
        erstes is not None and letztes is not None and (letztes - erstes) > 1
    )
    usage_da = bool(
        stream_zeile.get("prompt_tokens") and stream_zeile.get("completion_tokens")
    )

    if mehr_als_eins and abstand_gross and usage_da:
        return (
            "Infomaniak streamt json_schema mit usage; der Gespraechszug "
            "streamt im Betrieb."
        )
    code = http_code or "unbekannt"
    return (
        f"Infomaniak lehnt stream mit json_schema ab (HTTP {code}): der "
        "Gespraechszug streamt nicht, Szene und Kurzgeschichte schon. "
        "Entscheidung fuer Birk: Schema aufgeben und den Chat-Zug auf Prosa "
        "umstellen -- oder so lassen."
    )


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m scripts.strom_probe",
        description=(
            "Echter Stream-Lauf gegen Infomaniak und den Claude-Proxy "
            "(ANNAHME 4/5). Kein Test, laeuft nie automatisch, kostet Geld."
        ),
    )
    p.add_argument(
        "--bericht", action="store_true",
        help="Markdown-Bericht nach docs/web-vereint/strom-probe-<Datum>.md schreiben",
    )
    p.add_argument(
        "--nur", choices=("infomaniak", "proxy"),
        help="nur einen der beiden Wege laufen lassen",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = baue_argumente(argv)
    e = einstellungen.laden()

    zeilen: list[dict] = []
    hinweise: list[str] = []
    http_code: str | None = None

    with tempfile.TemporaryDirectory(prefix="interview_theater-strom_probe-") as verzeichnis:
        # IT_DB wird ausdruecklich verworfen (wie scripts/pruefe_prompts.py):
        # aufruf- und vorfall-Zeilen dieses Laufs gehoeren nicht in die
        # Betriebsdatenbank.
        db_pfad = str(Path(verzeichnis) / "strom_probe.db")
        e = replace(e, db_pfad=db_pfad)
        conn = db.verbinde(db_pfad)
        db.initialisiere(conn)

        with httpx.Client(timeout=120.0) as klient:
            if args.nur in (None, "infomaniak"):
                print("--- Infomaniak (schema + stream, dann ohne stream) ---")
                zeilen_info, hinweise_info, http_code = _messe_infomaniak(conn, e, klient)
                zeilen += zeilen_info
                hinweise += hinweise_info
            if args.nur in (None, "proxy"):
                print("--- Proxy (prosa + stream) ---")
                zeile_proxy, hinweise_proxy = _messe_proxy(conn, e, klient)
                zeilen.append(zeile_proxy)
                hinweise += hinweise_proxy

        conn.close()

    befund = befund_satz(zeilen, http_code)
    text = baue_bericht(zeilen, befund, hinweise=hinweise)
    print()
    print(text)

    if args.bericht:
        pfad = BERICHTE / f"strom-probe-{date.today().isoformat()}.md"
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(text + "\n", encoding="utf-8")
        print(f"\nBericht: {pfad}")

    # Eine Messung hat kein Ergebnis, das "falsch" waere -- auch eine
    # abgelehnte Annahme ist ein gueltiges Ergebnis (Schritt 1 Punkt 7 der
    # Karte).
    return 0


if __name__ == "__main__":
    sys.exit(main())
