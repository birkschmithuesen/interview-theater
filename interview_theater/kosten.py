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

**Der Tagesdeckel** (``pruefe``, ``deckel_erreicht``) steht an drei Stellen
VOR dem Netzaufruf: ``llm.LLM._anfrage``, ``szene_claude.prosa`` und
``aufnahme._verarbeite``. Weil das im Bot-Prozess sitzt, gilt er fuer
Telegram und Web gleichermassen. Pausieren heisst: Empfangen laeuft weiter
(AGENTS.md, "Empfangen, Antworten und In-den-Prompt-legen sind drei
getrennte Entscheidungen"); nur Modell- und Whisper-Aufrufe fallen aus, die
Gruppe bekommt hoechstens alle ``PAUSE_WIEDERHOLUNG_S`` eine Zeile.

**Kein SQL hier.** Gelesen wird ueber ``repo.kostensumme_seit`` (AGENTS.md:
SQL nur in ``repo.py``, ``db.py``, ``web_daten.py``). Dieses Modul rechnet
und entscheidet, es speichert nicht.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from interview_theater import repo, sprache

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
    sofort auf.

    Der Vorfall steht **einmal je Gruppe und Tag** (wie beim Deckel,
    ``tagesbeginn_utc``): gebucht wird jeder Aufruf, vermerkt nur der erste --
    sonst schriebe jeder Gespraechszug mit dem neuen Modell eine Zeile."""
    wert = kosten_chf(modell or "", eingabe_token, ausgabe_token)
    if wert is not None:
        return wert
    eingabe, ausgabe = teuerster_preis()
    wert = ((eingabe_token or 0) * eingabe + (ausgabe_token or 0) * ausgabe) / 1_000_000
    try:
        if repo.gab_es_vorfall_seit(
            conn, chat_id, "kosten_modell_unbekannt", tagesbeginn_utc(zeitzone())
        ):
            return wert
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


#: Der Tagesdeckel je Gruppe, in CHF. Ueber ``IT_KOSTEN_DECKEL_CHF``
#: umstellbar; 5 CHF ist die Vorgabe aus der Karte.
VORGABE_DECKEL_CHF = 5.0

#: Wonach sich "heute" richtet. Padua liegt in Italien -- ein Workshoptag
#: soll nicht um 02:00 Ortszeit umschlagen, weil UTC es tut.
VORGABE_ZEITZONE = "Europe/Rome"

#: Wie oft die Pausenmeldung hoechstens wiederholt wird. Der
#: Nachhol-Arbeiter laeuft alle 60 s (``aufnahme.NACHHOL_INTERVALL_S``) --
#: ohne Drosselung stuenden sechzig Zeilen je Stunde im Chat.
PAUSE_WIEDERHOLUNG_S = 15 * 60

VORFALL_ART = "kostendeckel_erreicht"

#: Die Nachricht an die Gruppe. **Kein Betrag** (Entscheidung 30.09.2026):
#: "5 CHF" sagt einer Theatergruppe nichts darueber, was sie tun soll, und
#: lenkt die Aufmerksamkeit auf eine Zahl, die der Betreiber setzt. Der Text
#: sagt vier Dinge: Budget erreicht, bis wann, was gesichert ist, was
#: weitergeht.
_TEXT_PAUSE = (
    "Das Tagesbudget für heute ist erreicht — ich mache bis Mitternacht "
    "(italienische Zeit) Pause und antworte solange nicht.\n\n"
    "Eure Arbeit ist gespeichert. Aufnehmen könnt ihr weiter (ich höre sie "
    "morgen ab), und eure Gruppenseite bleibt lesbar."
)


class KostendeckelErreicht(Exception):
    """Der Tagesdeckel dieser Gruppe ist erreicht -- **es fand kein
    Netzaufruf statt**.

    Eine eigene Ausnahme und kein ``LLMFehler``: die Aufrufer behandeln sie
    anders (eine Pausenmeldung statt "bei mir hakt gerade etwas"), und ein
    ``LLMFehler`` haette Wiederholungslogik ausgeloest, wo es nichts zu
    wiederholen gibt."""


def zeitzone(e=None) -> str:
    """Die Zeitzone: aus den Einstellungen, sonst aus der Umgebung, sonst
    Rom. Zwei Quellen, weil der Bot ``Einstellungen`` hat und Skripte und
    Tests nicht."""
    aus_e = getattr(e, "zeitzone", None)
    return (
        (aus_e if isinstance(aus_e, str) else None)
        or os.environ.get("IT_ZEITZONE")
        or VORGABE_ZEITZONE
    )


def deckel(e=None) -> float:
    """Der Tagesdeckel in CHF, aus denselben zwei Quellen. Ein unlesbarer
    Wert faellt auf die Vorgabe zurueck, nie auf 'kein Deckel'."""
    aus_e = getattr(e, "kosten_deckel_chf", None)
    if isinstance(aus_e, (int, float)):
        return float(aus_e)
    roh = os.environ.get("IT_KOSTEN_DECKEL_CHF")
    try:
        wert = float(roh) if roh else VORGABE_DECKEL_CHF
    except ValueError:
        return VORGABE_DECKEL_CHF
    if wert != wert or wert in (float("inf"), float("-inf")):
        return VORGABE_DECKEL_CHF
    return wert


def _ort(zone: str) -> ZoneInfo:
    try:
        return ZoneInfo(zone)
    except Exception:  # noqa: BLE001 -- eine unbekannte Zone darf nichts reissen
        log.warning("Unbekannte Zeitzone %r -- es gilt %s", zone, VORGABE_ZEITZONE)
        return ZoneInfo(VORGABE_ZEITZONE)


def tagesbeginn_utc(zone: str, jetzt: datetime | None = None) -> str:
    """Mitternacht der Ortszeit, umgerechnet nach UTC, im Format von
    ``repo._jetzt()``.

    **Warum nach UTC und nicht andersherum:** ``aufruf.erstellt_am`` steht in
    UTC (``repo._jetzt``), und ISO-8601 in UTC sortiert lexikographisch
    richtig -- ein Textvergleich im SQL genuegt, und ``repo`` muss nichts von
    Zeitzonen wissen.

    Am 30.09.2026 (Sommerzeit) ist Mitternacht Rom ``2026-09-29T22:00:00+00:00``.
    Eine Zeile von gestern 23:59 Rom liegt damit VOR dem Tagesbeginn -- mit
    einem UTC-Tag waere sie mitgezaehlt worden."""
    ort = _ort(zone)
    jetzt = datetime.now(ort) if jetzt is None else jetzt.astimezone(ort)
    mitternacht = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    return mitternacht.astimezone(timezone.utc).isoformat(timespec="seconds")


def summe_heute(conn, chat_id: int, e=None, jetzt=None) -> float:
    """Was diese Gruppe seit Mitternacht Ortszeit ausgegeben hat."""
    return repo.kostensumme_seit(conn, chat_id, tagesbeginn_utc(zeitzone(e), jetzt))


def deckel_erreicht(conn, chat_id, e=None, jetzt=None) -> bool:
    """Ist der Tagesdeckel dieser Gruppe erreicht?

    ``chat_id is None`` gibt immer False: das Warmlaufen
    (``bot.warmlaufen``) und die Pruefskripte laufen ohne Gruppe. Sie gegen
    den Deckel einer Gruppe zu rechnen waere falsch, und gegen "alle" hiesse,
    dass ein Skriptlauf den Workshop anhaelt."""
    if chat_id is None or conn is None:
        return False
    try:
        return summe_heute(conn, chat_id, e, jetzt) >= deckel(e)
    except Exception:  # noqa: BLE001
        # Eine Datenbank, die gerade nicht lesbar ist, darf den Bot nicht
        # anhalten: der Deckel ist eine Bremse, keine Sicherung.
        log.exception("Tagessumme nicht lesbar, chat_id=%s -- Deckel gilt als offen", chat_id)
        return False


def pruefe(conn, chat_id, e=None, jetzt=None) -> None:
    """Wirft ``KostendeckelErreicht``, wenn nichts mehr ausgegeben werden
    darf. **Vor** dem Netzaufruf zu rufen -- der Sinn ist, dass er nicht
    stattfindet."""
    if deckel_erreicht(conn, chat_id, e, jetzt):
        raise KostendeckelErreicht(
            f"Tagesdeckel {deckel(e)} CHF fuer chat_id={chat_id} erreicht"
        )


def melde_pause_wenn_deckel(conn, tg, e, chat_id, jetzt=None) -> bool:
    """Sagt der Gruppe, dass pausiert wird -- hoechstens alle
    ``PAUSE_WIEDERHOLUNG_S``. Liefert True, wenn der Deckel erreicht ist
    (unabhaengig davon, ob gerade gemeldet wurde).

    **Der Rueckgabewert ist die Weiche an den Fehlerstellen:** wer True
    bekommt, schickt **kein** "bei mir hakt gerade etwas" hinterher. Deshalb
    prueft die Funktion den Zustand neu, statt eine Ausnahme entgegen-
    zunehmen -- die ``except Exception``-Bloecke in ``ablauf`` und den
    Schreibwegen binden das Ausnahmeobjekt gar nicht, und der Zustand steht
    ohnehin in der Datenbank.

    **Der Merkposten liegt in der Datenbank** (``gruppe.kostenpause_gemeldet_am``):
    im Prozess gemerkt meldete ein Neustart sofort wieder, und der
    Nachhol-Arbeiter laeuft im Minutentakt."""
    if not deckel_erreicht(conn, chat_id, e, jetzt):
        return False
    jetzt_utc = datetime.now(timezone.utc) if jetzt is None else jetzt.astimezone(timezone.utc)
    nicht_vor = (jetzt_utc - timedelta(seconds=PAUSE_WIEDERHOLUNG_S)).isoformat(timespec="seconds")
    try:
        darf = repo.merke_kostenpause(
            conn, chat_id, nicht_vor, jetzt_utc.isoformat(timespec="seconds"),
        )
    except Exception:  # noqa: BLE001
        log.exception("Merkposten zur Kostenpause nicht gesetzt, chat_id=%s", chat_id)
        return True
    if not darf:
        return True
    try:
        tg.sende(chat_id, T._TEXT_PAUSE)
    except Exception:  # noqa: BLE001 -- die Meldung darf nichts mitreissen
        log.exception("Pausenmeldung nicht zugestellt, chat_id=%s", chat_id)
    try:
        tagesbeginn = tagesbeginn_utc(zeitzone(e), jetzt)
        if not repo.gab_es_vorfall_seit(conn, chat_id, VORFALL_ART, tagesbeginn):
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), VORFALL_ART,
                f"Tagesdeckel {deckel(e)} CHF erreicht "
                f"(Summe {summe_heute(conn, chat_id, e, jetzt):.2f} CHF seit {tagesbeginn})",
            )
    except Exception:  # noqa: BLE001
        log.exception("Vorfall zum Kostendeckel nicht geschrieben, chat_id=%s", chat_id)
    return True


#: A1-Mechanik: die deutschen Konstanten oben SIND die deutsche Tabelle,
#: jede weitere Sprache steht in ``sprachen/<code>/texte.toml``. Gelesen wird
#: zur Aufrufzeit ueber ``T._TEXT_PAUSE`` -- ein Web-Prozess bedient mehrere
#: Gruppen, und Tests schalten das Profil per monkeypatch um.
T = sprache.Texte(__name__)
