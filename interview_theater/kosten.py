"""Was ein Workshoptag kostet -- und ab wann der Bot pausiert.

**Der Anlass ist ein Befund.** Die Karte ging davon aus, die Kosten stuenden
schon im ``aufruf``-Protokoll. Sie standen nicht dort: die Tabelle trug bis
zum 30.09.2026 weder eine Modell- noch eine Kostenspalte (``db.py``), und
Whisper buchte gar nicht. Nachtraeglich rechnen ging auch nicht -- aus
``aufruf.art`` folgt das Modell nicht, ``LLM.schema`` waehlt es je Aufruf.

**Also wird beim Buchen gerechnet.** Jeder Aufruf schreibt sein Modell und
seine Kosten mit; der Deckel summiert nur noch. Eine Preisaenderung
ruecktdatiert damit keine alte Zeile.

**Unbekanntes Modell => teuerster Preis, nicht 0.** Fuer den Bericht von
``scripts/pruefe_prompts.py`` ist ``None`` richtig ("lieber keine Zahl als
eine erfundene"); fuer einen Deckel ist es die falsche Richtung -- sonst
umgeht der naechste Modellwechsel die Grenze, ohne dass es jemand merkt.
Deshalb zwei Funktionen: ``kosten_chf`` (unveraendert, ``None``) und
``kosten_oder_teuerster`` (Betriebspfad, Vorfall).

**Kein SQL hier.** Gelesen wird ueber ``repo.kostensumme_seit`` (AGENTS.md:
SQL nur in ``repo.py``, ``db.py``, ``web_daten.py``). Dieses Modul rechnet
und entscheidet, es speichert nicht.
"""

import logging

from interview_theater import repo

log = logging.getLogger(__name__)

#: Stand der Preise: **04.09.2026**, uebernommen aus
#: ``scripts/pruefe_prompts.py`` und seither nicht nachgezogen. Das Skript
#: importiert sie seit dem 30.09.2026 von hier -- zwei Tabellen waeren zwei
#: Wahrheiten, und der Bericht rechnete bald anders als der Deckel.
#: Eingabe- und Ausgabepreis je Million Token, in CHF.
PREISE_STAND = "04.09.2026"
PREISE_CHF_JE_MIO_TOKEN = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8": (0.05, 0.20),
    "google/gemma-4-31B-it": (0.20, 0.40),
    "mistralai/Mistral-Small-4-119B-2603": (0.20, 0.75),
    "mistralai/Ministral-3-14B-Instruct-2512": (0.30, 0.40),
    "Qwen/Qwen3.5-122B-A10B-FP8": (0.40, 3.20),
    "moonshotai/Kimi-K2.6": (0.60, 3.00),
    "swiss-ai/Apertus-v1.5-70B": (0.70, 2.50),
    "Qwen/Qwen3.5-397B-A17B-FP8": (0.80, 3.60),
}

#: Whisper rechnet nach Audiodauer, nicht nach Token. Quelle:
#: ``~/hermes-shared/hermes-knowledge/infomaniak-modelle.md`` § 6.4 --
#: **ausserhalb dieses Repositories**, Stand unten. Nachgemessen ist der Wert
#: nicht (das kostete einen bezahlten Aufruf); er steht hier als Konstante
#: mit Datum, damit klar ist, was zu pruefen waere.
WHISPER_CHF_JE_MINUTE = 0.006
WHISPER_STAND = "30.09.2026"

#: Der Claude-Weg ueber den lokalen Proxy laeuft ueber ein Abonnement und
#: zaehlt deshalb nicht gegen den Tagesdeckel (Birk bestaetigt, dass
#: Claude-Proxy-Aufrufe nicht gegen den 5-CHF-Deckel zaehlen; siehe auch den
#: Docstring von ``szene_claude.prosa``: "mit 0 CHF, weil Abo").
#:
#: **An genau einer Stelle**, damit aus dem Abo eine Abrechnung werden kann,
#: ohne dass jemand suchen muss.
CLAUDE_CHF_JE_AUFRUF = 0.0


def kosten_chf(modell: str, eingabe_token: int, ausgabe_token: int) -> float | None:
    """Kostenschaetzung nach der Preistabelle. ``None`` fuer ein Modell, das
    nicht in der Liste steht -- lieber keine Zahl als eine erfundene.

    Wortgleich das Verhalten von ``scripts/pruefe_prompts.kosten_chf``, das
    diese Funktion seit dem Umzug ist."""
    preise = PREISE_CHF_JE_MIO_TOKEN.get(modell)
    if preise is None:
        return None
    eingabe, ausgabe = preise
    return ((eingabe_token or 0) * eingabe + (ausgabe_token or 0) * ausgabe) / 1_000_000


def teuerster_preis() -> tuple[float, float]:
    """Das Maximum je Richtung ueber die ganze Tabelle. Die konservative
    Annahme fuer ein Modell, das wir nicht kennen."""
    return (
        max(p[0] for p in PREISE_CHF_JE_MIO_TOKEN.values()),
        max(p[1] for p in PREISE_CHF_JE_MIO_TOKEN.values()),
    )


def kosten_oder_teuerster(conn, chat_id, bot_name, modell,
                          eingabe_token, ausgabe_token) -> float:
    """Die Kosten fuer die Buchung -- konservativ.

    Kennt die Tabelle das Modell nicht, wird mit dem **teuersten** Preis
    gerechnet und ein Vorfall vermerkt. Mit 0 zu buchen hiesse, dass der
    naechste Modellwechsel den Deckel aushebelt, ohne dass es jemand merkt;
    zu teuer zu buchen kostet hoechstens eine fruehe Pause, und die faellt
    sofort auf."""
    wert = kosten_chf(modell or "", eingabe_token, ausgabe_token)
    if wert is not None:
        return wert
    eingabe, ausgabe = teuerster_preis()
    wert = ((eingabe_token or 0) * eingabe + (ausgabe_token or 0) * ausgabe) / 1_000_000
    try:
        repo.merke_vorfall(
            conn, chat_id, bot_name, "kosten_modell_unbekannt",
            f"Kein Preis fuer {modell!r} (Tabelle Stand {PREISE_STAND}) -- "
            f"konservativ mit {eingabe}/{ausgabe} CHF je Mio gerechnet, "
            f"{wert:.4f} CHF gebucht",
        )
    except Exception:  # noqa: BLE001 -- ein Vorfall darf keine Buchung mitreissen
        log.exception("Vorfall zum unbekannten Modell nicht geschrieben")
    return wert


def stt_kosten_chf(dauer_s) -> float:
    """Was eine Transkription kostet: Audiodauer mal Minutenpreis.

    ``None`` oder 0 gibt 0.0 -- eine Aufnahme ohne bekannte Dauer wird nicht
    geraten. Das ist die einzige Stelle, an der der Deckel etwas **nicht**
    sieht; im Betrieb traegt jede Telegram-Sprachnachricht ihre
    ``dauer_sekunden``, und der Web-Upload meldet sie (``MAX_DAUER_S``)."""
    try:
        sekunden = float(dauer_s or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, sekunden) / 60.0 * WHISPER_CHF_JE_MINUTE
