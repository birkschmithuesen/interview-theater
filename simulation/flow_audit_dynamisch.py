"""Flow-Audit -- Schicht 2 (dynamischer Persona-Lauf, Padua, 04.10.2026).

Schicht 1 (``simulation/flow_audit.py``) prueft rein statisch, ob eine
Handlung einen Erkenner-Intent oder einen Knopf hat. Das sagt nichts darueber,
ob der Chat-Weg, wenn er existiert, tatsaechlich etwas bewirkt: ein Intent
kann im Schema stehen und trotzdem nie greifen, weil eine Wache davor sitzt,
die niemand gemessen hat (Phase, Profilschalter, ein konkurrierender
deterministischer Text-Pfad). Dieses Modul faehrt deshalb zwei Personas durch
Phase 1 (Begriffe), Phase 2 (Fragen), Phase 3 (Interviews) und Phase 4
(Setting, Figuren & Geschichte -- Stationen 15-27, Task B, t_92f99911,
erweitert aus der urspruenglichen Phase-1/2-Karte t_2cdea48b)
**gegen den echten Bot-Code**
(``bot.verarbeite_update``, ``bot._zug_und_erkenner``, ``knoepfe.behandle``,
eine echte SQLite-Verbindung) und misst, nicht vermutet.

**Verbindliche Bauregel** (Auftrag dieser Karte): jede Station nimmt ``klm``
und ``tg`` als Parameter entgegen, baut sie nie selbst. Dieses Modul ist die
Schicht "was zu tun ist und wie es gemessen wird" -- ob dahinter eine
Attrappe (``SkriptLLM`` unten, Schicht 2 dieser Karte) oder ein echtes
Sprachmodell steckt (eine spaetere Karte), entscheidet der Aufrufer. Keine
Station importiert ``SkriptLLM`` fuer sich selbst.

**Zwei Modellaufruf-``art``-Werte, wie der echte Bot sie nutzt** (gefunden
beim Lesen von ``interview_theater/ablauf.py`` und ``erkenner.py``, nicht
geraten):

* ``"gespraech"`` -- der Gespraechszug UND jeder Knopf-Auftrag
  (``ablauf.auftragszug`` ueber ``_starte_auftrag``) rufen ``klm.schema(...)``
  mit diesem einen ``art``-Wert, demselben Schema
  (``{"antwort": "<string>"}``) und derselben Nachbearbeitung (Denkspur-,
  Echo- und Ankuendigungs-Filter). Es gibt KEINEN eigenen ``art``-Wert fuer
  einen "Auftrag" -- ein Knopf, der ein Modell braucht, sieht aus wie ein
  zweiter Gespraechszug.
* ``"erkenner"`` -- der Absichtserkenner-Nachlauf (``erkenner.erkenne``),
  Schema ``{"aenderungen": [{"art": "<intent>", "wert": "<string>"}]}``,
  hoechstens ``erkenner.MAX_AENDERUNGEN`` (5) Eintraege, nur mit ``art in
  erkenner.ARTEN``.

Ein dritter ``art``-Wert taucht am Rand auf: ``"fragen_ki_vorschlag"``
(``interview_theater/fragen_ki.py``, dasselbe ``{"antwort": ...}``-Schema wie
``"gespraech"``) -- der isolierte KI-Fragen-Hintergrundlauf beim Eintritt in
Phase 2. ``SkriptLLM`` unterscheidet Antworten nach ``(stufe, art)``, damit
eine Station fuer verschiedene ``art``-Werte verschiedene Antworten hinterlegen
kann, ohne dass der eine Aufruf den anderen ueberschreibt.

Ablauf-Muster, **ebenfalls gefunden, nicht erfunden** (historische
Referenzimplementierung ``.flow_audit_ref/flow_audit_lauf.py``, Funktion
``_sende_und_fahre``, Zeilen 222-231 -- fuer die Phasen 4/5/7 eines
inzwischen ueberholten Phasenstands, hier fuer Phase 1/2 neu geschrieben):

1. **Nachrichtenzug** -- ``bau_update`` (``simulation/lauf.py``) baut ein
   rohes Telegram-Update, ``bot.verarbeite_update`` speichert es,
   ``bot._zug_und_erkenner`` fuehrt Gespraechszug, Absichtserkenner UND
   Journal-Extraktor synchron aus, in dieser Reihenfolge
   (``tests/test_bot.py::test_zug_und_erkenner_ruft_beides_genau_einmal_auf_nach_dem_zug``).
   Nach der Rueckkehr steht jede ERKANNTE Aenderung schon in der Datenbank --
   ``erkenner.laufe`` lauft NICHT in einem eigenen Thread.
2. **Knopfdruck** -- ``knoepfe.behandle(conn, tg, klm, e, {"callback_query_id",
   "data", "chat_id", "message_id"})``, niemals ueber
   ``bot.verarbeite_update`` (ein Knopfdruck ist keine Nachricht, AGENTS.md
   "Die Weiche sitzt in ``bot.schleife`` vor ``verarbeite_update``").

**Hintergrund-Threads bleiben echt asynchron.** ``ablauf.auftragszug`` (ein
Knopf- oder Markerweg, der ein Modell braucht) laeuft in einem eigenen
Daemon-Thread und wird von der aufrufenden Funktion NICHT mitgewartet --
deshalb ``_warte_bis`` unten: ein kurzes Poll-Fenster auf
``len(tg.gesendet)``, kein ``time.sleep`` fester Laenge (eine Attrappe ist
synchron und schnell, aber eben doch ein zweiter Thread).

**Der eine bewusste Ausnahme**: Station 13 (Wartezustand) laesst ``SkriptLLM``
fuer genau einen Aufruf echte ``time.sleep`` halten (knapp ueber
``ablauf.TIPP_INTERVALL`` = 4 s) -- sonst liefe der Test nie lang genug, dass
der echte Tippanzeige-Hintergrundthread (``ablauf._tippanzeige``) ueberhaupt
einmal ``tg.tippt`` ruft, und die Messung waere ein Nullbefund aus
Schnelligkeit statt aus Verhalten.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from simulation.lauf import bau_update

#: Woerter, die nach einer Bestaetigung klingen, waehrend nichts gespeichert
#: wurde -- uebernommen aus der historischen Referenz
#: (``.flow_audit_ref/flow_audit_lauf.py``, ``WORDS_WORRY_EN``), weil genau
#: diese Liste schon einmal an echten Antworten gemessen wurde.
WORDS_WORRY_EN = (
    "noted", "saved", "changed", "updated", "added", "got it", "done",
    "sure thing", "on it", "noted that", "updating",
)

#: Verbotene Fachjargon-Token fuer den Onboarding-Pflichtpruefpunkt 3
#: (Klartext-Phaseneinstieg) -- case-insensitive Teilstring.
JARGON_TOKEN = ("vad", "segment", "intent", "schema")

#: Was auf ein zweites Handy / den CoThinker-Tab hinweist (Pflichtpruefpunkt
#: 2) -- Deutsch und Englisch, weil ``sprache.code()`` je Profil wechselt.
ZWEITES_HANDY_HINWEISE = ("cothinker", "zweites handy", "second phone")


# ---------------------------------------------------------------------------
# Die zwei Personas -- Stimmen, von Hand geschrieben (keine eigenen
# Modellaufrufe), wie die bestehenden Simulationsstimmen
# (``simulation/stimmen/*.md``).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Persona:
    name: str
    beschreibung: str


GIULIA = Persona(
    "Giulia",
    "23, acting student in Padua, English B2, creative, impatient with "
    "forms, brings her own ideas, contradicts suggestions, changes her "
    "mind, prefers typing over tapping. Drives most stations.",
)

PRIYA = Persona(
    "Priya",
    "First-time chatbot user, unsure of her English, never used "
    "push-to-talk. Appears at a few stations and silently wonders things "
    "she never types out loud -- recorded in advance per station, not "
    "invented at runtime.",
)


# ---------------------------------------------------------------------------
# Die Messgroesse je Station.
# ---------------------------------------------------------------------------


@dataclass
class Sondierung:
    """Eine Sondierung: eine Handlung, gemessen gegen den echten Code.

    Name wie die historische Referenz (``.flow_audit_ref``), nicht ``Station``
    -- dieselbe Form, dieselbe Bedeutung von ``wirkungslos``/
    ``behauptet_nicht_getan``, damit ein spaeterer Vergleich zwischen altem
    und neuem Lauf nicht an einem umbenannten Feld scheitert.

    ``schreibvorgang`` ist ``None``, solange eine Station nichts zu
    schreiben erwartet (z. B. Station 2: der Vorschlag soll NUR erscheinen,
    nicht gleich speichern -- das Speichern ist ausdruecklich Sache des
    Knopfes). ``False`` heisst: eine Aenderung war erwartet, aber die
    Datenbank zeigt sie nicht -- das ist der Befund, den diese Schicht
    jagt."""

    phase: int
    station: str
    persona: str
    aktion: str
    nachricht: str = ""
    bot_antwort: str = ""
    schreibvorgang: bool | None = None
    klickzwang: bool = False
    rueckfragen_vor_aktion: int = 0
    echo_erkannt: bool | None = None
    fragen_der_persona: list[str] = field(default_factory=list)
    hinweis: str = ""

    @property
    def wirkungslos(self) -> bool:
        return self.schreibvorgang is False

    @property
    def behauptet_nicht_getan(self) -> bool:
        """Sagt die Bot-Antwort etwas, das nach "erledigt" klingt
        (``WORDS_WORRY_EN``), waehrend ``wirkungslos`` True ist?"""
        text = self.bot_antwort.lower()
        return self.wirkungslos and any(w in text for w in WORDS_WORRY_EN)

    @property
    def mehrere_fragen_pro_nachricht(self) -> bool:
        """Grobe Heuristik (dokumentiert, nicht versteckt): mehr als ein
        mit "?" beendetes Satzstueck in der Bot-Antwort."""
        return self.bot_antwort.count("?") > 1

    @property
    def antwortlaenge(self) -> int:
        return len(self.bot_antwort)

    def als_dict(self) -> dict:
        return {
            "phase": self.phase,
            "station": self.station,
            "persona": self.persona,
            "aktion": self.aktion,
            "nachricht": self.nachricht,
            "bot_antwort": self.bot_antwort,
            "schreibvorgang": self.schreibvorgang,
            "wirkungslos": self.wirkungslos,
            "behauptet_nicht_getan": self.behauptet_nicht_getan,
            "klickzwang": self.klickzwang,
            "rueckfragen_vor_aktion": self.rueckfragen_vor_aktion,
            "echo_erkannt": self.echo_erkannt,
            "fragen_der_persona": list(self.fragen_der_persona),
            "mehrere_fragen_pro_nachricht": self.mehrere_fragen_pro_nachricht,
            "antwortlaenge": self.antwortlaenge,
            "hinweis": self.hinweis,
        }


# ---------------------------------------------------------------------------
# Die Attrappe fuer das Sprachmodell des Bots (Schicht 2 dieser Karte).
# ---------------------------------------------------------------------------


class SkriptLLM:
    """Eine kleine, von aussen umschaltbare Zustandsmaschine statt des
    echten ``interview_theater.llm.LLM``.

    Jede Station ruft ``.stelle(stufe)``, bevor sie eine Persona-Nachricht
    schickt oder einen Knopf drueckt -- ``stufe`` ist ein frei gewaehlter
    Schluessel (kein Index in eine Liste, damit eine Station ihn lesbar
    benennen kann). Darunter liegen zwei getrennte Plaene:

    * ``.antwort(stufe, art, *antworten)`` -- vorbereitete
      ``{"antwort": "..."}``-Texte fuer den Gespraechszug (``art="gespraech"``)
      oder den isolierten KI-Fragen-Lauf (``art="fragen_ki_vorschlag"``).
      Mehrere Antworten werden der Reihe nach verbraucht (fuer den
      Echo-Kontroll-Pfad, der den echten zweiten Anlauf nach einer
      Ermahnung braucht); ist die Liste erschoepft, wiederholt sich die
      letzte.
    * ``.erkenner(stufe, aenderungen)`` -- vorbereitete
      ``{"aenderungen": [...]}`` fuer den Absichtserkenner-Lauf.

    **Die Mutationsprobe lebt in ``_antwort_erkenner``**: ``erkenner.ARTEN``
    wird bei JEDEM Aufruf frisch importiert und geprueft -- nie beim Bau der
    Attrappe eingefroren. Ein ``monkeypatch.setattr(erkenner, "ARTEN", ...)``
    in einem Test wirkt dadurch auf diesen Aufruf genauso, wie ein echtes
    Sprachmodell nie mehr einen aus dem Schema-Enum entfernten Wert liefern
    wuerde -- die Attrappe spielt keine Absicht, die der Code gar nicht mehr
    anbietet."""

    def __init__(self) -> None:
        self._stufe: str | None = None
        self._text_plan: dict[tuple[str, str], list[str]] = {}
        self._text_zaehler: dict[tuple[str, str], int] = {}
        self._erkenner_plan: dict[str, list[dict]] = {}
        #: Phase-3-Nachtrag (Task B, t_92f99911): eine vorbereitete Antwort
        #: fuer ``art="verdichter"`` (``verdichter.verdichte``). Ohne diesen
        #: Plan liefert ``.schema()`` fuer diese ``art`` dasselbe
        #: ``{"antwort": ...}``-Dict wie fuer den Gespraechszug --
        #: ``verdichter.verdichte`` greift aber am Ende direkt auf
        #: ``ergebnis["zusammenfassung"]`` zu (kein ``.get``) und wuerde mit
        #: einem ``KeyError`` abbrechen, sobald eine Station wirklich eine
        #: Verdichtung durchlaufen laesst (``aufnahme.schliesse_ab`` ->
        #: ``verdichter.verdichte``). Eine Station OHNE diese Konfiguration
        #: darf also nie bis zur Verdichtung durchlaufen (sie wuerde dort
        #: crashen) -- ``.verdichtung(...)`` ist deshalb Pflicht fuer jede
        #: Station, die ``schliesse_ab``/``verarbeite`` tatsaechlich aufruft.
        self._verdichtung_plan: dict[str, dict] = {}
        #: Einmalige kuenstliche Verzoegerung je Stufe (Station 13) -- siehe
        #: Moduldocstring, Abschnitt "Wartezustand".
        self._verzoegerung_s: dict[str, float] = {}
        #: Protokoll jedes Aufrufs, zur Fehlersuche und fuer die Messung in
        #: Station 13/9 (Anzahl Aufrufe je Stufe).
        self.aufrufe: list[dict] = []

    def stelle(self, stufe: str) -> "SkriptLLM":
        self._stufe = stufe
        return self

    def antwort(self, stufe: str, art: str, *antworten: str) -> "SkriptLLM":
        self._text_plan[(stufe, art)] = list(antworten)
        return self

    def gespraech(self, stufe: str, *antworten: str) -> "SkriptLLM":
        """Bequemlichkeit fuer den haeufigsten Fall: ``art="gespraech"``."""
        return self.antwort(stufe, "gespraech", *antworten)

    def erkenner(self, stufe: str, aenderungen: list[dict]) -> "SkriptLLM":
        self._erkenner_plan[stufe] = list(aenderungen)
        return self

    def verdichtung(self, stufe: str, zusammenfassung: str,
                    kernthemen: list[dict] | None = None) -> "SkriptLLM":
        """Bequemlichkeit fuer ``art="verdichter"`` (siehe
        ``_verdichtung_plan`` oben) -- ``kernthemen`` im Schema von
        ``verdichter.SCHEMA`` (``[{"thema":..., "beleg_zitat":...,
        "kurz":...}]``), Vorgabe leer (eine Verdichtung ohne belegtes Thema
        ist fuer eine Station, die nur die Phase-4-Sperre misst, voellig
        ausreichend)."""
        self._verdichtung_plan[stufe] = {
            "zusammenfassung": zusammenfassung,
            "kernthemen": kernthemen or [],
        }
        return self

    def verzoegere(self, stufe: str, sekunden: float) -> "SkriptLLM":
        self._verzoegerung_s[stufe] = sekunden
        return self

    def anzahl_aufrufe(self, stufe: str, art: str | None = None) -> int:
        return sum(
            1 for a in self.aufrufe
            if a["stufe"] == stufe and (art is None or a["art"] == art)
        )

    # -- die Schnittstelle, die interview_theater.llm.LLM auch hat ---------

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None) -> dict:
        stufe = self._stufe
        self.aufrufe.append({"stufe": stufe, "art": art, "nutzer": nutzer})
        verzug = self._verzoegerung_s.get(stufe or "")
        if verzug:
            time.sleep(verzug)
        if art == "erkenner":
            return self._antwort_erkenner(stufe)
        if art == "verdichter":
            geplant = self._verdichtung_plan.get(stufe or "")
            if geplant is not None:
                return dict(geplant)
        return {"antwort": self._antwort_text(stufe, art)}

    def _antwort_text(self, stufe: str | None, art: str) -> str:
        schluessel = (stufe, art)
        plan = self._text_plan.get(schluessel) or [""]
        n = self._text_zaehler.get(schluessel, 0)
        self._text_zaehler[schluessel] = n + 1
        return plan[min(n, len(plan) - 1)]

    def _antwort_erkenner(self, stufe: str | None) -> dict:
        # Live-Import, absichtlich bei jedem Aufruf -- siehe Klassendocstring
        # "Die Mutationsprobe".
        from interview_theater import erkenner as erkenner_modul

        geplant = self._erkenner_plan.get(stufe or "", [])
        erlaubt = [a for a in geplant if a.get("art") in erkenner_modul.ARTEN]
        return {"aenderungen": erlaubt}


# ---------------------------------------------------------------------------
# Die Weiche zwischen Attrappe und echtem Modell (Klasse-A-Fix, 04.10.2026).
#
# Jede Station rief bis dahin die SkriptLLM-KONFIGURATIONSmethoden
# (``.stelle()``, ``.gespraech()``, ``.antwort()``, ``.erkenner()``) direkt
# auf ``klm`` auf. Das ging zwei Review-Runden lang unbemerkt durch, weil
# jeder Testlauf ``klm`` als ``SkriptLLM`` baute -- der erste echte,
# kostenpflichtige Lauf (``scripts/flow_audit_lauf.py`` gegen
# ``interview_theater.llm.LLM``) liess alle 14 Stationen sofort mit
# ``AttributeError: 'LLM' object has no attribute 'stelle'`` abbrechen, noch
# bevor ein echter Modellaufruf stattfand. Der echte ``LLM`` entscheidet
# selbst, was er antwortet, und kennt/braucht keine Vorab-Konfiguration --
# fuer ihn muss jeder dieser Aufrufe ein No-Op sein, nicht ein Fehler.
# ---------------------------------------------------------------------------


class _KeinOpAttrappe:
    """Sentinel fuer jedes ``klm``, das KEINE ``SkriptLLM``-Instanz ist.

    Jede Konfigurationsmethode ist ein No-Op, das sich selbst zurueckgibt --
    damit die bestehende Kettensyntax der Aufrufstellen (``.gespraech(...)``
    nach ``_konfiguriere_falls_attrappe(...)``) unveraendert weiter
    funktioniert, nur dass sie gegen ein echtes Modell nichts tut."""

    def gespraech(self, *_args, **_kwargs) -> "_KeinOpAttrappe":
        return self

    def antwort(self, *_args, **_kwargs) -> "_KeinOpAttrappe":
        return self

    def erkenner(self, *_args, **_kwargs) -> "_KeinOpAttrappe":
        return self


_KEIN_OP = _KeinOpAttrappe()


def _konfiguriere_falls_attrappe(klm, stufe: str):
    """Richtet die ``SkriptLLM``-Attrappe fuer diese Stufe ein -- No-Op fuer
    jeden anderen ``klm`` (insbesondere den echten
    ``interview_theater.llm.LLM``, siehe Abschnittskopf oben). Ersetzt an
    jeder Aufrufstelle genau ``klm.stelle(stufe)`` (nicht die ganze Kette),
    die SkriptLLM-spezifischen Konfigurationsaufrufe wie
    ``.gespraech(...)``/``.antwort(...)`` haengen weiterhin per Kette daran."""
    if isinstance(klm, SkriptLLM):
        return klm.stelle(stufe)
    return _KEIN_OP


# ---------------------------------------------------------------------------
# Die zwei Fahrmuster (Nachricht / Knopf) -- klm und tg sind Parameter,
# dieses Modul baut sie nicht selbst (Bauregel der Karte).
# ---------------------------------------------------------------------------


def sende_nachricht(conn, tg, klm, e, chat_id: int, persona: Persona,
                    text: str) -> str:
    """Schickt EINE Nachricht als ``persona`` und faehrt den Zug synchron
    (Nachrichtenzug-Muster, siehe Moduldocstring). Liefert die neu
    gesendeten Bot-Nachrichten dieses Zuges, zusammengefuegt.

    ``bot._zug_und_erkenner`` ist bis zur Rueckkehr vollstaendig synchron
    FUER Gespraechszug und Absichtserkenner -- nur ein ``auftragszug``, den
    einer der beiden selbst anstoesst (Knopf-/Marker-Auftrag), laeuft in
    einem eigenen Thread und ist nach dieser Funktion ggf. noch nicht
    fertig (siehe ``warte_auf_neue_nachricht``)."""
    from interview_theater import bot

    vorher = len(tg.gesendet)
    update = bau_update(
        tg.naechste_message_id(), tg.naechste_message_id(), persona.name,
        text, datetime.now(timezone.utc), chat_id,
    )
    bot.verarbeite_update(conn, e, update, datetime.now(timezone.utc), False)
    bot._zug_und_erkenner(conn, tg, klm, e, chat_id)
    neue = tg.gesendet[vorher:]
    return "\n".join(n["text"] for n in neue if n.get("text"))


def druecke_knopf(conn, tg, klm, e, chat_id: int, knopf: dict) -> str:
    """Drueckt einen Knopf aus ``tg.offene_knoepfe()`` (Knopfdruck-Muster).

    Geht NICHT ueber ``bot.verarbeite_update`` -- ein Knopfdruck ist keine
    Nachricht (AGENTS.md). Liefert die neu gesendeten Bot-Nachrichten,
    zusammengefuegt (fuer den Fall, dass der Druck selbst synchron
    weiterschaltet, wie ``entscheide``/``_zeige_frage``)."""
    from interview_theater import knoepfe as knoepfe_modul

    vorher = len(tg.gesendet)
    knoepfe_modul.behandle(conn, tg, klm, e, {
        "callback_query_id": "sondierung",
        "data": knopf["daten"],
        "chat_id": chat_id,
        "message_id": knopf["message_id"],
    })
    neue = tg.gesendet[vorher:]
    return "\n".join(n["text"] for n in neue if n.get("text"))


def finde_knopf(tg, beschriftung_enthaelt: str) -> dict | None:
    """Der erste zur Zeit antippbare Knopf, dessen Beschriftung den Text
    enthaelt (case-insensitiv) -- oder ``None``."""
    ziel = beschriftung_enthaelt.lower()
    for knopf in tg.offene_knoepfe():
        if ziel in knopf["beschriftung"].lower():
            return knopf
    return None


def warte_auf_neue_nachricht(tg, vorher: int, mindestanzahl: int = 1,
                             timeout: float = 5.0, intervall: float = 0.02) -> bool:
    """Wartet, bis ``tg.gesendet`` mindestens ``mindestanzahl`` Eintraege MEHR
    hat als ``vorher`` -- fuer einen Hintergrund-``auftragszug``
    (``ablauf.starte_auftrag``), der nicht mitgewartet wird. Liefert, ob es
    angekommen ist.

    ``mindestanzahl`` ist bewusst keine 1 an jeder Aufrufstelle: beim
    Eintritt in Phase 1 steht VOR dem modellgeschriebenen Einstieg schon der
    deterministische Mithoer-Satz des Begriffsboards (synchron, also sofort
    da) -- ein Aufrufer, der nur auf "irgendeine neue Nachricht" wartet,
    misst sonst zu frueh und sieht den eigentlichen (asynchronen) Modelltext
    nie."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if len(tg.gesendet) - vorher >= mindestanzahl:
            return True
        time.sleep(intervall)
    return len(tg.gesendet) - vorher >= mindestanzahl


def _alle_bot_texte(tg) -> str:
    return "\n".join(n["text"] for n in tg.gesendet if n.get("text"))


def jargon_treffer(text: str) -> list[str]:
    """Welche verbotenen Fachjargon-Token in ``text`` stehen (case-
    insensitive Teilstring) -- leer heisst sauber."""
    t = text.lower()
    return [tok for tok in JARGON_TOKEN if tok in t]


def erwaehnt_zweites_handy(text: str) -> bool:
    t = text.lower()
    return any(h in t for h in ZWEITES_HANDY_HINWEISE)


def _begriff_feld(conn, chat_id: int) -> str | None:
    from interview_theater import repo

    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return None
    try:
        return stand["begriffe"]
    except (IndexError, KeyError):
        return None


def _begriffe_detail_feld(conn, chat_id: int) -> str | None:
    from interview_theater import repo

    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return None
    try:
        return stand["begriffe_detail"]
    except (IndexError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Phase 1 -- Begriffe.
# ---------------------------------------------------------------------------


def station_01_eintritt(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Eintritt in Phase 1: Klartext-Pruefung UND das zweite-Handy-/
    CoThinker-Signal (Onboarding-Pflichtpruefpunkte 2+3).

    Mit einem echten ``klm`` traegt der Eintritt in Phase 1 KEINEN festen
    Text (``phasentexte.eintritt``) mehr -- ``knoepfe.eintritt_in_phase``
    gibt den Einstieg an einen Gespraechszug ab
    (``kontext.einstieg_begriffe``, Zeile 350-361 in
    ``interview_theater/knoepfe/stationen.py``) und kehrt zurueck, BEVOR
    dieser Zug fertig ist. Was tatsaechlich zuerst steht, ist der
    deterministische Mithoer-Satz des Begriffsboards
    (``begriffsboard.sende_einstieg``, Zeile 338-343 derselben Funktion,
    nur mit ``[diskussion] aktiv``) -- DORT steht der CoThinker-Hinweis, nicht
    im Modelltext. Diese Station prueft deshalb den GESAMTEN bisherigen
    Chatverlauf, nicht nur eine einzelne Nachricht: genau das, was eine
    Gruppe beim ersten Blick auf ihr Telefon sieht."""
    stufe = "p1_eintritt"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        "Hi! Whenever you're ready, send me the terms from your wall -- "
        "typed out or as a voice note, just as they are. I'll keep them "
        "and we'll look together at anything that still feels too big.",
    )
    from interview_theater import knoepfe as knoepfe_modul

    vorher = len(tg.gesendet)
    knoepfe_modul.eintritt_in_phase(conn, tg, klm, e, chat_id, 1)
    # Zwei Nachrichten erwartet: der synchrone Mithoer-Satz des
    # Begriffsboards UND der asynchrone, modellgeschriebene Einstieg.
    warte_auf_neue_nachricht(tg, vorher, mindestanzahl=2, timeout=5.0)

    gesamter_text = _alle_bot_texte(tg)
    jargon = jargon_treffer(gesamter_text)
    handy = erwaehnt_zweites_handy(gesamter_text)

    s = Sondierung(
        phase=1, station="Eintritt Phase 1", persona=GIULIA.name,
        aktion="Klartext- und Mithoer-Hinweis-Pruefung beim Phaseneintritt",
    )
    s.bot_antwort = gesamter_text
    s.hinweis = (
        f"Jargon-Treffer: {jargon or 'keine'}; "
        f"CoThinker/zweites Handy erwaehnt: {handy}; "
        f"Bot-Nachrichten beim Eintritt: {len(tg.gesendet) - vorher}"
    )
    return s


def station_02_begriffe_vorschlag(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Giulia tippt eine Begriffsliste direkt in den Chat -- erwartet wird
    ein ``VORSCHLAG BEGRIFFE:``-Block plus Speicher-Knopf, hoechstens EINE
    Rueckfrage davor.

    ``schreibvorgang`` ist bewusst ``None``: der Vorschlag soll NICHT von
    selbst speichern (das ist Sache von "Yes, save" bzw. der Korrektur in
    Station 3) -- hier wird nur gemessen, ob der Vorschlagsweg ueberhaupt
    entsteht."""
    stufe = "p2_begriffe_vorschlag"
    nachricht = "arrival, silence, waiting, home, strangers"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        "Nice set, thank you. Here they are:\n\n"
        "VORSCHLAG BEGRIFFE:\nArrival, Silence, Waiting, Home, Strangers",
    )

    vorher = len(tg.gesendet)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    neue_nachrichten = tg.gesendet[vorher:]

    hat_knopf = finde_knopf(tg, "Yes, save") is not None
    # Wie viele Bot-Nachrichten kamen vor der Nachricht mit dem Knopf?
    rueckfragen = 0
    for n in neue_nachrichten:
        if n["message_id"] in {
            k["message_id"] for k in tg.offene_knoepfe()
        }:
            break
        rueckfragen += 1

    s = Sondierung(
        phase=1, station="Begriffs-Vorschlag im Chat", persona=GIULIA.name,
        aktion="Eine Begriffsliste direkt tippen statt vorgegebener Form",
        nachricht=nachricht, bot_antwort=antwort,
        rueckfragen_vor_aktion=rueckfragen,
    )
    s.hinweis = f"Speicher-Knopf ('Yes, save') angeboten: {hat_knopf}"
    return s


def station_03_korrektur_via_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """**Die Mutationsprobe-Station.** Giulia korrigiert die Begriffe per
    Chat-Satz statt per Knopf -- kein ``VORSCHLAG``-Block in der
    Gespraechsantwort, die Aenderung kommt ausschliesslich ueber den
    Absichtserkenner (``begriffe_setzen``).

    Selbststaendig lauffaehig: setzt ``arbeitsstand.begriffe`` vorher direkt
    (ohne Chat) auf einen Ausgangswert, damit diese Station unabhaengig von
    Station 2 wiederholt und gezielt mutiert werden kann."""
    from interview_theater import repo

    repo.setze_arbeitsstand(
        conn, chat_id, "begriffe", "Arrival, Silence, Waiting, Home, Strangers",
    )

    stufe = "p3_korrektur"
    nachricht = "actually, swap Strangers for Neighbours -- that fits better"
    # Bewusst OHNE VORSCHLAG-Block: eine Antwort, die nach Erledigung
    # KLINGT ("Got it"), ohne dass der Gespraechszug selbst etwas schreibt --
    # genau der Live-Fall, gegen den die Erkenner-Meldung antritt.
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Got it -- swapping that in.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [
            {"art": "begriffe_setzen",
             "wert": "Arrival, Silence, Waiting, Home, Neighbours"},
        ])

    vorher = _begriff_feld(conn, chat_id)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher = _begriff_feld(conn, chat_id)

    s = Sondierung(
        phase=1, station="Begriffs-Korrektur im Chat (Mutationsprobe)",
        persona=GIULIA.name,
        aktion="Einen Begriff per Chat-Satz tauschen statt per Knopf",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher != nachher),
    )
    s.hinweis = f"arbeitsstand.begriffe vorher={vorher!r} nachher={nachher!r}"
    return s


def station_04_begriffsboard_korrektur(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Begriffsboard-Pfad: ein Board wird DIREKT ueber ``repo`` angelegt
    (wie die historische Referenz Produktionsfunktionen fuer den
    Szenenaufbau direkt ruft), ``begriffsboard.sende_vorschlag`` zeigt die
    Top-5 mit genau EINEM Knopf ("Take these") -- und Giulia tippt eine
    Korrektur, statt ihn zu druecken.

    Prueft zusaetzlich zu Station 3, dass ``arbeitsstand.begriffe_detail``
    mitgeschrieben wird (``begriffsboard.schreibe_detail``, aufgerufen aus
    ``erkenner._wende_arbeitsstand_an`` auf JEDEM Schreibweg von
    ``begriffe`` -- hier also auch ueber den Erkenner, nicht nur ueber den
    Board-Knopf selbst)."""
    import json

    from interview_theater import begriffsboard, repo

    repo.setze_arbeitsstand(
        conn, chat_id, "begriffe", "Arrival, Silence, Waiting, Home, Strangers",
    )
    eintraege = [
        {"begriff": "Arrival", "nennungen": 3, "zustimmung": 2,
         "begruendung": "came up when talking about the first day",
         "zitat": "", "doppelbedeutung": "", "status": "favorit"},
        {"begriff": "Silence", "nennungen": 2, "zustimmung": 1,
         "begruendung": "several people went quiet here", "zitat": "",
         "doppelbedeutung": "", "status": "kandidat"},
        {"begriff": "Home", "nennungen": 4, "zustimmung": 2,
         "begruendung": "came back again and again", "zitat": "",
         "doppelbedeutung": "", "status": "favorit"},
        {"begriff": "Strangers", "nennungen": 1, "zustimmung": 0,
         "begruendung": "mentioned once, in passing", "zitat": "",
         "doppelbedeutung": "", "status": "kandidat"},
    ]
    assert all(set(e) == set(begriffsboard._FELDER) for e in eintraege)
    repo.lege_begriffsboard_an(
        conn, chat_id, json.dumps(eintraege, ensure_ascii=False), "sovereign", 0,
    )
    begriffsboard.sende_vorschlag(conn, tg, chat_id, None)
    hat_uebernehmen_knopf = finde_knopf(tg, "Take these") is not None

    stufe = "p4_board_korrektur"
    nachricht = "let's swap Arrival for Departure, and add Noise too"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Sure -- updating the list.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [
            {"art": "begriffe_setzen",
             "wert": "Departure, Silence, Home, Strangers, Noise"},
        ])

    vorher_begriffe = _begriff_feld(conn, chat_id)
    vorher_detail = _begriffe_detail_feld(conn, chat_id)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher_begriffe = _begriff_feld(conn, chat_id)
    nachher_detail = _begriffe_detail_feld(conn, chat_id)

    s = Sondierung(
        phase=1, station="Begriffsboard-Korrektur im Chat", persona=GIULIA.name,
        aktion="Statt 'Take these' zu druecken, die Vorschlagsliste per Chat aendern",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher_begriffe != nachher_begriffe),
    )
    s.hinweis = (
        f"'Take these'-Knopf stand vorher da: {hat_uebernehmen_knopf}; "
        f"begriffe geaendert: {vorher_begriffe != nachher_begriffe}; "
        f"begriffe_detail geaendert: {vorher_detail != nachher_detail}"
    )
    return s


def station_05_echo_kontrolle(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Echo-Kontrollstation: die Attrappe liefert beim ERSTEN Aufruf
    woertlich Giulias eigene Nachricht zurueck -- echtes ``ablauf.ist_echo``/
    ``_ohne_echo`` soll das erkennen, verwerfen und GENAU EINEN zweiten
    Anlauf mit angehaengter Ermahnung starten
    (``ablauf._TEXT_ECHO_ERMAHNUNG``).

    Gemessen wird NICHT per Vermutung, sondern per Aufrufzaehler: lief die
    Attrappe fuer diese Stufe zweimal (``SkriptLLM.anzahl_aufrufe``), hat der
    echte Retry-Mechanismus tatsaechlich gegriffen."""
    stufe = "p5_echo"
    nachricht = "I think silence is the strongest one for us"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        nachricht,  # 1. Anlauf: woertliches Echo
        "Noted -- silence stands out. Want me to fold it into the list?",
    )

    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)

    # ``anzahl_aufrufe`` ist eine SkriptLLM-Messgroesse: sie zaehlt, wie oft
    # DIESE ATTRAPPE fuer die Stufe aufgerufen wurde, um den echten Retry
    # nach einem erkannten Echo nachzuweisen. Gegen ein echtes Modell gibt
    # es (a) keinen Zaehler und (b) keine Grundlage: ein echtes
    # Sprachmodell spiegelt eine Nutzernachricht praktisch nie woertlich,
    # die Pruefvoraussetzung dieser Station (ein erzeugtes Echo) entfaellt
    # also von vornherein. Messung wird deshalb bewusst uebersprungen statt
    # einen erfundenen Befund vorzutaeuschen (Aufgabenbrief Punkt 2).
    if isinstance(klm, SkriptLLM):
        aufrufe = klm.anzahl_aufrufe(stufe, "gespraech")
        echo_erkannt = (
            aufrufe >= 2 and nachricht.lower() not in antwort.lower()
        )
        hinweis = f"Gespraech-Aufrufe fuer diese Nachricht: {aufrufe}"
    else:
        echo_erkannt = None
        hinweis = (
            "Messung uebersprungen: der Aufrufzaehler je Stufe "
            "(SkriptLLM.anzahl_aufrufe) gilt nur fuer die Attrappe. Gegen "
            "ein echtes Sprachmodell faellt die Pruefvoraussetzung dieser "
            "Station weg -- ein echtes Modell spiegelt eine Nutzernachricht "
            "praktisch nie woertlich, es gibt also kein Echo zu kontrollieren."
        )

    s = Sondierung(
        phase=1, station="Echo-Kontrolle", persona=GIULIA.name,
        aktion="Pruefen, ob eine woertlich gespiegelte Antwort verworfen "
               "und neu angefordert wird",
        nachricht=nachricht, bot_antwort=antwort,
        echo_erkannt=echo_erkannt,
    )
    s.hinweis = hinweis
    return s


# ---------------------------------------------------------------------------
# Phase 2 -- Fragen.
# ---------------------------------------------------------------------------


def _gehe_nach_phase_2(conn, chat_id: int) -> None:
    from interview_theater import phasen

    phasen.setze(conn, chat_id, 2, "befehl")


def station_06_eintritt_phase2(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Eintritt in Phase 2: derselbe Klartext-Pruefpunkt wie Station 1,
    gegen ``workshop/padua-2026/prompts/phasen/2.md`` (ersetzt die
    gemeinsame Datei komplett fuer dieses Profil -- der A/B-Fragenfluss,
    kein ``VORSCHLAG FRAGEN WEICH:``-Block, weil ``[fragen_weich] aktiv =
    false``).

    Mit ``[fragen_ab] aktiv = true`` stoesst der Eintritt zusaetzlich den
    isolierten KI-Fragen-Hintergrundlauf an (``fragen_ki.starte``,
    ``art="fragen_ki_vorschlag"``) -- die Attrappe bekommt dafuer eine
    eigene, harmlose Antwort, damit der Lauf nicht an einer leeren Antwort
    scheitert (er wuerde sonst nur ``fragen_ki_vorschlag`` leer lassen,
    siehe ``fragen_ki.py``-Doku "Kein Nachbessern")."""
    _gehe_nach_phase_2(conn, chat_id)

    stufe = "p6_eintritt"
    # Nicht gekettet (zwei getrennte ``art``-Plaene auf derselben Stufe) --
    # deshalb ein einzelner Block-Guard statt ``_konfiguriere_falls_attrappe``.
    if isinstance(klm, SkriptLLM):
        klm.stelle(stufe)
        klm.antwort(
            stufe, "gespraech",
            "Now your terms become interview questions. Write your own first -- "
            "I'll tidy the wording, never invent the sense. I'm already "
            "preparing a second set in the background, out of sight, for a "
            "fair comparison later.",
        )
        klm.antwort(
            stufe, "fragen_ki_vorschlag",
            "Arrival: Tell me about the day you arrived.\n"
            "Silence: When did you first notice the silence here?",
        )

    from interview_theater import knoepfe as knoepfe_modul

    vorher = len(tg.gesendet)
    knoepfe_modul.eintritt_in_phase(conn, tg, klm, e, chat_id, 2)
    warte_auf_neue_nachricht(tg, vorher, timeout=5.0)

    gesamter_text = "\n".join(
        n["text"] for n in tg.gesendet[vorher:] if n.get("text")
    )
    jargon = jargon_treffer(gesamter_text)

    s = Sondierung(
        phase=2, station="Eintritt Phase 2", persona=GIULIA.name,
        aktion="Klartext-Pruefung beim Phaseneintritt",
        bot_antwort=gesamter_text,
    )
    s.hinweis = f"Jargon-Treffer: {jargon or 'keine'}"
    return s


def station_07_priya_eigene_frage(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Priya schreibt eine zoegerliche erste Frage in den Chat -- der A/B-
    Fluss soll sie ueber ``VORSCHLAG EIGENE FRAGEN:`` aufnehmen
    (``knoepfe.fragen.uebernimm_eigene``, aus ``knoepfe/basis.py``
    ausgeloest, kein Knopf beteiligt)."""
    from interview_theater import repo

    repo.setze_arbeitsstand(conn, chat_id, "begriffe", "Arrival, Silence, Home")

    stufe = "p7_priya_frage"
    nachricht = "um, I guess... maybe something about the first day here? " \
                "like what was it like arriving"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        "Here's where that one fits:\n\n"
        "VORSCHLAG EIGENE FRAGEN:\n"
        "Arrival: Tell me about the day you arrived here.",
    )

    from interview_theater import repo as repo_mod

    vorher = (repo_mod.hole_arbeitsstand(conn, chat_id) or {})
    vorher_wert = vorher["fragen_eigene_vorschlag"] if vorher else None
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, PRIYA, nachricht)
    nachher = repo_mod.hole_arbeitsstand(conn, chat_id)
    nachher_wert = nachher["fragen_eigene_vorschlag"] if nachher else None

    s = Sondierung(
        phase=2, station="Priya schreibt eine eigene Frage", persona=PRIYA.name,
        aktion="Eine zoegerliche, erste eigene Frage in den Chat tippen",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher_wert != nachher_wert),
        fragen_der_persona=[
            "did that count as a real question?",
            "what do I press now?",
            "will I get to add more questions later?",
        ],
    )
    s.hinweis = f"fragen_eigene_vorschlag: {vorher_wert!r} -> {nachher_wert!r}"
    return s


def station_08_giulia_aendert_frage(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Giulia aendert eine schon notierte eigene Frage per Chat -- keine
    Rueckfrage-Kette, kein Knopf, derselbe Marker-Weg wie Station 7 (eine
    neue, VOLLSTAENDIGE Liste ueberschreibt die alte -- so ist
    ``uebernimm_eigene`` gebaut, siehe sein Docstring: "der Block IST die
    ganze Liste, kein Zuwachs")."""
    from interview_theater import repo

    repo.setze_arbeitsstand(
        conn, chat_id, "fragen_eigene_vorschlag",
        "Arrival: Tell me about the day you arrived here.",
    )

    stufe = "p8_giulia_aendert"
    nachricht = "actually scrap the arrival one, let's ask about silence " \
                "instead: what does silence mean to you here"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        "Updated:\n\nVORSCHLAG EIGENE FRAGEN:\n"
        "Silence: What does silence mean to you here?",
    )

    vorher = repo.hole_arbeitsstand(conn, chat_id)
    vorher_wert = vorher["fragen_eigene_vorschlag"] if vorher else None
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher = repo.hole_arbeitsstand(conn, chat_id)
    nachher_wert = nachher["fragen_eigene_vorschlag"] if nachher else None

    s = Sondierung(
        phase=2, station="Giulia aendert eine Frage per Chat", persona=GIULIA.name,
        aktion="Eine vorher genannte Frage per Chat ersetzen statt per Knopf",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher_wert != nachher_wert),
    )
    s.hinweis = f"fragen_eigene_vorschlag: {vorher_wert!r} -> {nachher_wert!r}"
    return s


def _seed_gegenueberstellung(conn, chat_id: int) -> None:
    """Gemeinsame Vorbereitung fuer Station 9 und 13: beide Seiten des A/B-
    Vergleichs direkt gesetzt (kein echter ``fragen_ki``-Lauf noetig, der
    isolierte KI-Hintergrundlauf ist nicht Gegenstand dieser Stationen)."""
    from interview_theater import repo

    repo.setze_arbeitsstand(conn, chat_id, "begriffe", "Arrival, Silence, Home")
    repo.setze_arbeitsstand(
        conn, chat_id, "fragen_eigene_vorschlag",
        "Arrival: Tell me about the day you arrived here.\n"
        "Silence: What does silence mean to you here?\n"
        "Home: What makes a place feel like home to you?",
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "fragen_ki_vorschlag",
        "Arrival: What do you remember most about arriving?\n"
        "Silence: Is there a kind of silence you miss?\n"
        "Home: Where did you feel at home first?",
    )
    # Vorherigen Rundenstand raeumen, falls ein frueherer Lauf schon
    # geoffenbart hat (``versuche_gegenueberstellung`` ist sonst ein No-Op).
    repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)


def station_09_fruehzeitig_fertig(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Giulia sagt sinngemaess "lass uns zur Gegenueberstellung gehen" --
    die Attrappe liefert dafuer, wie es das Padua-Profil-Prompt
    (``workshop/padua-2026/prompts/phasen/2.md``) dem echten Modell
    vorschreibt, den woertlichen Satz ``"Own questions done."`` MITTEN im
    eigenen Fliesstext. Der Code liest genau diesen Satz
    (``knoepfe.fragen._fruehzeitig_fertig``/``_SATZ_EIGENE_FRAGEN_FRUEHER_FERTIG``)
    und loest die Gegenueberstellung aus, auch wenn noch nicht jeder Begriff
    drei eigene Fragen hat."""
    _seed_gegenueberstellung(conn, chat_id)

    stufe = "p9_fertig"
    nachricht = "let's leave it at that, I think we're ready for the comparison"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        "Sounds good, that's plenty to compare.\n\n"
        "VORSCHLAG EIGENE FRAGEN:\n"
        "Arrival: Tell me about the day you arrived here.\n"
        "Silence: What does silence mean to you here?\n"
        "Home: What makes a place feel like home to you?\n\n"
        "Own questions done.",
    )

    from interview_theater import repo

    vorher = repo.hole_arbeitsstand(conn, chat_id)
    vorher_wert = vorher["fragen_auswahl"] if vorher else None
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher = repo.hole_arbeitsstand(conn, chat_id)
    nachher_wert = nachher["fragen_auswahl"] if nachher else None

    s = Sondierung(
        phase=2, station="Fruehzeitiges 'Own questions done.'",
        persona=GIULIA.name,
        aktion="Vorzeitig zur Gegenueberstellung wechseln, per wortlautgenauem"
               " Satz statt per Knopf",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher_wert != nachher_wert),
    )
    s.hinweis = (
        f"fragen_auswahl gesetzt: {bool(nachher_wert)}; "
        f"Ueberleitungstext in tg.gesendet enthalten: "
        f"{'Your questions and' in _alle_bot_texte(tg)}"
    )
    return s


def station_10_priya_akzeptiert_per_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """**Gefundene Abweichung vom Erwartungsbild der Karte.** Priya sagt im
    Chat "yes, that one's good" zur gerade offenen Frage. Der Code
    (``knoepfe.fragen.nimm_offene_frage_text``, gelesen VOR dem Bau dieser
    Station) hat dafuer gar keinen eigenen Fall "das war eine Zustimmung" --
    JEDE freie Nachricht, waehrend eine Frage offen und unentschieden ist,
    wird als Schaerfungswunsch behandelt (``_starte_schaerfung``), egal ob
    ihr Inhalt zustimmend oder aendernd ist. Ein getipptes "Ja" entscheidet
    die Frage also NICHT -- sie bleibt offen, unter derselben Nummer,
    bestenfalls mit einem unveraendert umformulierten Text.

    Diese Station treibt genau das durch den echten Code und MISST es, statt
    es zu behaupten: ``fragen_entschieden``/``fragen_aktuell`` bleiben
    unberuehrt, waehrend die Bot-Antwort ("Got it...") nach einer Bestaetigung
    klingt -- ``behauptet_nicht_getan`` schlaegt genau deshalb an."""
    from interview_theater import repo

    repo.setze_arbeitsstand(
        conn, chat_id, "fragen_auswahl",
        "Arrival: Tell me about the day you arrived here.\n"
        "Silence: What does silence mean to you here?",
    )
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", "1")
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)

    stufe = "p10_priya_akzeptiert"
    nachricht = "yes, that one's good"
    # Kein VORSCHLAG-FRAGE-Block: ein plausibler, aber verwirrter Modellzug,
    # der auf einen Schaerfungswunsch antwortet, den es inhaltlich gar
    # nicht gab -- und trotzdem wie eine Bestaetigung klingt.
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Got it -- I'll leave this one as it is.",
    )

    vorher_entschieden = repo.hole_arbeitsstand(conn, chat_id)["fragen_entschieden"]
    vorher_aktuell = repo.hole_arbeitsstand(conn, chat_id)["fragen_aktuell"]
    vorher_gesendet = len(tg.gesendet)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, PRIYA, nachricht)
    warte_auf_neue_nachricht(tg, vorher_gesendet, timeout=5.0)
    nachher_entschieden = repo.hole_arbeitsstand(conn, chat_id)["fragen_entschieden"]
    nachher_aktuell = repo.hole_arbeitsstand(conn, chat_id)["fragen_aktuell"]

    entschieden_unveraendert = vorher_entschieden == nachher_entschieden
    aktuell_unveraendert = vorher_aktuell == nachher_aktuell
    antwort_gesamt = antwort or _alle_bot_texte(tg)[-400:]

    s = Sondierung(
        phase=2, station="Priya akzeptiert eine Frage per Chat",
        persona=PRIYA.name,
        aktion="'yes, that one's good' tippen statt 'Accept' zu druecken",
        nachricht=nachricht, bot_antwort=antwort_gesamt,
        schreibvorgang=not (entschieden_unveraendert and aktuell_unveraendert),
        fragen_der_persona=[
            "did that count as yes?",
            "why is it asking about the same question again?",
            "do I need to press something now?",
        ],
    )
    s.hinweis = (
        "GEFUNDENER TOTER WEG: 'yes' im Chat entscheidet die Frage nicht -- "
        "jede freie Nachricht waehrend eine Frage offen ist, wird als "
        "Schaerfungswunsch gelesen (knoepfe.fragen.nimm_offene_frage_text), "
        "nie als Zustimmung. fragen_entschieden "
        f"{vorher_entschieden!r} -> {nachher_entschieden!r}, fragen_aktuell "
        f"{vorher_aktuell!r} -> {nachher_aktuell!r}."
    )
    return s


def station_11_klickzwang(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Klickzwang-Kontrolle: Chat zuerst (erwartet ``wirkungslos``), dann
    der echte Knopf "Accept" -- derselbe offene Zustand wie Station 10
    (eine freie Nachricht entscheidet eine Frage nie; nur der Knopf ruft
    ``entscheide(..., "ja")``/``entscheide(..., "nein")`` auf)."""
    from interview_theater import repo

    repo.setze_arbeitsstand(
        conn, chat_id, "fragen_auswahl",
        "Arrival: Tell me about the day you arrived here.\n"
        "Silence: What does silence mean to you here?",
    )
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", "1")
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
    # Die Frage muss wirklich als Nachricht mit Knoepfen stehen, sonst
    # gibt es nichts zu druecken -- derselbe Weg wie beim echten Eintritt
    # in die Stufe (``starte_durchgehen``).
    from interview_theater.knoepfe import fragen as fragen_modul

    fragen_modul._zeige_frage(conn, tg, chat_id, 1)

    stufe = "p11_klickzwang"
    nachricht = "accept it, that one's fine"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Got it -- keeping it as is.",
    )

    vorher_entschieden = repo.hole_arbeitsstand(conn, chat_id)["fragen_entschieden"]
    sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nach_chat_entschieden = repo.hole_arbeitsstand(conn, chat_id)["fragen_entschieden"]
    chat_wirkungslos = nach_chat_entschieden == vorher_entschieden

    annehmen_knopf = finde_knopf(tg, "Accept")
    knopf_antwort = ""
    knopf_hat_gewirkt = False
    if annehmen_knopf is not None:
        knopf_antwort = druecke_knopf(conn, tg, klm, e, chat_id, annehmen_knopf)
        nach_knopf_entschieden = repo.hole_arbeitsstand(conn, chat_id)["fragen_entschieden"]
        knopf_hat_gewirkt = nach_knopf_entschieden != nach_chat_entschieden

    s = Sondierung(
        phase=2, station="Klickzwang: Frage annehmen", persona=GIULIA.name,
        aktion="Erst per Chat annehmen versuchen, dann den echten Knopf druecken",
        nachricht=nachricht, bot_antwort=knopf_antwort,
        schreibvorgang=knopf_hat_gewirkt,
        klickzwang=(chat_wirkungslos and annehmen_knopf is not None
                    and knopf_hat_gewirkt),
    )
    s.hinweis = (
        f"Chat wirkungslos: {chat_wirkungslos}; 'Accept'-Knopf gefunden: "
        f"{annehmen_knopf is not None}; Knopf hat gewirkt: {knopf_hat_gewirkt}"
    )
    return s


def station_12_phasenwechsel_per_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Nach dem proaktiven Angebot "Weiter zu Phase 3?" antwortet Giulia im
    Chat ("yeah let's go!") statt zu druecken -- ``phase_setzen`` muss ueber
    den Absichtserkenner greifen (``erkenner._wende_phase_an`` ->
    ``phasen.setze``).

    Die drei Voraussetzungen aus ``phasen.voraussetzungen()[3]`` (``fragen``,
    ``interview_eroeffnung``, ``interview_abschluss`` -- ``fragen_weich`` ist
    in Padua abgeschaltet und zaehlt deshalb nicht) werden direkt gesetzt:
    das Zustandekommen von Eroeffnung/Abschluss selbst ist nicht Gegenstand
    dieser Station, nur die Frage, ob ein getipptes "yeah let's go!" die
    schon angebotene Stufe wirklich schaltet."""
    from interview_theater import knoepfe as knoepfe_modul, phasen, repo

    _gehe_nach_phase_2(conn, chat_id)
    repo.setze_arbeitsstand(
        conn, chat_id, "fragen",
        "Tell me about the day you arrived here.\n"
        "What does silence mean to you here?",
    )
    repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "")
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_eroeffnung",
        "Hi, we're a theatre group collecting voices for a play ...",
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_abschluss", "Thank you so much for your time.",
    )
    assert phasen.voraussetzungen(conn, chat_id)[3] is True

    vorher_angebot = len(tg.gesendet)
    knoepfe_modul.biete_phase_proaktiv(conn, tg, chat_id)
    angebot_text = "\n".join(
        n["text"] for n in tg.gesendet[vorher_angebot:] if n.get("text")
    )

    stufe = "p12_phase_wechsel"
    nachricht = "yeah let's go!"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Great, moving on!",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [{"art": "phase_setzen", "wert": "3"}])

    vorher_phase = phasen.aktuelle(conn, chat_id)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher_phase = phasen.aktuelle(conn, chat_id)

    s = Sondierung(
        phase=2, station="Phasenwechsel per Chat statt Knopf", persona=GIULIA.name,
        aktion="'yeah let's go!' tippen statt 'Weiter zu Phase 3' zu druecken",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(nachher_phase == 3 and vorher_phase == 2),
    )
    s.hinweis = (
        f"Angebotstext enthielt 'Phase': {'Phase' in angebot_text}; "
        f"Phase vorher={vorher_phase}, nachher={nachher_phase}"
    )
    return s


def station_13_wartezustand(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Sichtbarer Wartezustand (Onboarding-Pflichtpruefpunkt 4), an dieselbe
    Art Hintergrundarbeit wie Station 9 (Gegenueberstellung) gehaengt --
    mechanische Zaehlung, kein Urteil.

    **Bewusste Abweichung von "schnell und deterministisch":** eine
    Attrappe antwortet synchron und sofort; der echte Tippanzeige-Thread
    (``ablauf._tippanzeige``) ruft ``tg.tippt`` aber erst nach
    ``ablauf.TIPP_INTERVALL`` = 4 Sekunden zum ersten Mal. Ohne eine echte
    Verzoegerung waere ein Nullbefund hier nicht "der Mechanismus fehlt",
    sondern "die Attrappe war schneller als die Schwelle" -- ein
    Scheinbefund. Diese Station haelt deshalb GENAU EINEN Aufruf 4,2
    Sekunden lang (``SkriptLLM.verzoegere``) und zahlt diese Zeit bewusst,
    um den echten Mechanismus wirklich zu beobachten statt ihn zu
    unterlaufen."""
    _seed_gegenueberstellung(conn, chat_id)

    stufe = "p13_wartezustand"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        "Sounds good, that's plenty to compare.\n\n"
        "VORSCHLAG EIGENE FRAGEN:\n"
        "Arrival: Tell me about the day you arrived here.\n"
        "Silence: What does silence mean to you here?\n"
        "Home: What makes a place feel like home to you?\n\n"
        "Own questions done.",
    )
    # Die kuenstliche Verzoegerung ist SkriptLLM-spezifisches Setup (siehe
    # Stationsdocstring) -- ein echtes Modell braucht keine knapp ueber
    # ``ablauf.TIPP_INTERVALL`` gehaltene Antwortzeit kuenstlich erzeugt,
    # seine natuerliche Latenz ist Teil dessen, was hier gemessen wird. Die
    # Zaehlung von ``tg.getippt`` bleibt dagegen SINNVOLL gegen ein echtes
    # Modell (Aufgabenbrief Punkt 2): ob ``ablauf._tippanzeige`` waehrend
    # eines tatsaechlichen, langsameren Netz-Umwegs ueberhaupt einmal
    # ``tg.tippt`` ruft, laesst sich unveraendert messen.
    if isinstance(klm, SkriptLLM):
        klm.verzoegere(stufe, 4.2)
        verzoegerung_hinweis = "Verzoegerung=4.2s (SkriptLLM)"
    else:
        verzoegerung_hinweis = (
            "keine kuenstliche Verzoegerung gesetzt -- gilt nur fuer "
            "SkriptLLM, gemessen wird hier allein die natuerliche "
            "Antwortzeit des echten Modells"
        )

    vorher_getippt = len(tg.getippt)
    sende_nachricht(
        conn, tg, klm, e, chat_id, GIULIA,
        "let's leave it at that, ready for the comparison",
    )
    getippt_waehrend_lauf = len(tg.getippt) - vorher_getippt

    s = Sondierung(
        phase=2, station="Wartezustand sichtbar waehrend Hintergrundarbeit",
        persona=GIULIA.name,
        aktion="Eine 4+ Sekunden dauernde Modellantwort ueber die "
               "Gegenueberstellung laufen lassen",
        schreibvorgang=None,
    )
    s.hinweis = (
        f"tg.tippt() waehrend des Zuges aufgerufen: {getippt_waehrend_lauf} "
        f"Mal (TIPP_INTERVALL=4.0s, {verzoegerung_hinweis})"
    )
    return s


# ---------------------------------------------------------------------------
# Phase 1, Nachtrag (Review-Fund, 04.10.2026): die urspruengliche Fassung
# dieser Karte liess Priya ausschliesslich in Phase 2 auftreten (Stationen
# 7+10) -- der Aufgabenbrief fordert sie aber auch in Phase 1 (mindestens
# einmal). Angehaengt statt eingeschoben, bewusst gemaess der Korrekturregel
# der Karte ("extend the existing ALLE_STATIONEN tuple"): die bestehende
# Nummerierung 01-13 bleibt unberuehrt, kein Test und keine Prosa-Verweisstelle
# auf eine bestehende Stationsnummer muss deshalb mitgeaendert werden.
# ---------------------------------------------------------------------------


def station_14_priya_begriffe_korrektur(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Priya korrigiert einen Begriff per Chat-Satz -- parallel zur Form von
    Station 3 (Korrektur per Chat statt Knopf, derselbe ``begriffe_setzen``-
    Weg ueber den Absichtserkenner, kein ``VORSCHLAG``-Block in der
    Gespraechsantwort), aber mit Priyas eigener Stimme: zoegerlich, unsicher
    ueber ihr Englisch, noch nie mit einem Chatbot oder Push-to-Talk
    gearbeitet. Eigenstaendig lauffaehig wie Station 3 -- setzt
    ``arbeitsstand.begriffe`` vorher direkt (ohne Chat) auf einen
    Ausgangswert."""
    from interview_theater import repo

    repo.setze_arbeitsstand(
        conn, chat_id, "begriffe", "Arrival, Silence, Waiting, Home, Strangers",
    )

    stufe = "p14_priya_korrektur"
    nachricht = (
        "um, sorry, is it ok if I say something here -- I think maybe "
        "'outsiders' fits better than 'strangers'? not sure if that is the "
        "right word though"
    )
    # Bewusst OHNE VORSCHLAG-Block, wie Station 3: eine Antwort, die nach
    # Erledigung klingt, ohne dass der Gespraechszug selbst etwas schreibt.
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Got it -- swapping that in, thank you.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [
            {"art": "begriffe_setzen",
             "wert": "Arrival, Silence, Waiting, Home, Outsiders"},
        ])

    vorher = _begriff_feld(conn, chat_id)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, PRIYA, nachricht)
    nachher = _begriff_feld(conn, chat_id)

    s = Sondierung(
        phase=1, station="Priya korrigiert einen Begriff im Chat (Nachtrag)",
        persona=PRIYA.name,
        aktion="Zoegerlich einen Begriff per Chat-Satz vorschlagen, statt "
               "nach einem Knopf dafuer zu suchen",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher != nachher),
        fragen_der_persona=[
            "did I do this right?",
            "should I wait for a reply?",
            "is my phone the one that's listening?",
        ],
    )
    s.hinweis = f"arbeitsstand.begriffe vorher={vorher!r} nachher={nachher!r}"
    return s


# ---------------------------------------------------------------------------
# Phase 3 -- Interviews (Task B, t_92f99911, erweitert aus der
# urspruenglichen Phase-1/2-Karte t_2cdea48b). Keine Stimme simuliert
# echtes Audio/Whisper -- Interviews kommen als Text herein
# (``aufnahme.importiere_text``), wie im grossen Simulator
# (``simulation/lauf.py``, SPEC § 10.5). Audio/STT/Segmente bleiben
# ausserhalb des Geltungsbereichs dieses Werkzeugs (siehe die bestehende
# Anmerkung am Ende dieser Datei, ``test_phase3_fehlermeldungen_...`` in
# ``tests/test_flow_audit_dynamisch.py``) -- das deckt auch "Sprache
# automatisch" (Whisper-Spracherkennung) ab: das ist ein STT-Pfad, den eine
# Text-Simulation strukturell nicht erreicht.
# ---------------------------------------------------------------------------


def _gehe_nach_phase_3(conn, chat_id: int) -> None:
    from interview_theater import phasen

    phasen.setze(conn, chat_id, 3, "befehl")


def _seed_phase3_voraussetzungen(conn, chat_id: int) -> None:
    """Die drei Felder, die ``phasen.voraussetzungen(...)[3]`` braucht
    (``fragen_weich`` ist in Padua abgeschaltet und zaehlt nicht, wie schon
    in Station 12) -- gemeinsame Vorbereitung fuer jede Phase-3-Station, die
    unabhaengig von einer vorherigen Sitzung lauffaehig bleiben soll."""
    from interview_theater import repo

    repo.setze_arbeitsstand(
        conn, chat_id, "fragen", "Tell me about the day you arrived here.",
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_eroeffnung",
        "Hi, we're a theatre group collecting voices for a play ...",
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_abschluss", "Thank you so much for your time.",
    )


def _starte_interview_direkt(conn, chat_id: int) -> int:
    """Startet ein Interview genau wie ``befehle._befehl_aufnahme``/
    ``_befehl_interview`` es tun (``repo.setze_interviewmodus`` +
    ``aufnahme.stelle_interview_sicher``) -- siehe die Erklaerung bei
    Station 15, warum eine Station den Modus NICHT ueber einen erkannten
    ``interview_starten``-Intent einschalten kann. Liefert die neue
    ``aufnahme_id``."""
    from interview_theater import aufnahme, repo

    repo.setze_interviewmodus(conn, chat_id, repo._jetzt())
    return aufnahme.stelle_interview_sicher(conn, chat_id)


def station_15_interview_starten_ist_knopf_bzw_befehl_only(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """**Gefundene Abweichung von der im Aufgabenbrief erwarteten Pruefung**
    (Punkt 1): ein per Chat erkannter ``interview_starten``-Intent schaltet
    den Interviewmodus NICHT ein. ``erkenner._wende_interview_starten_an``
    sagt das woertlich: 'Ein angekuendigtes Interview startet nichts mehr'
    (05.09.2026, Birk nach dem Live-Lauf Gruppe 3 -- Start und Ende fielen in
    denselben Erkennerlauf, der Kopf blieb leer). Der erkannte Intent loest
    nur noch das ANGEBOT aus: dieselbe Ablauf-Erklaerung und denselben Knopf
    wie ``/aufnahme`` ohne laufenden Modus. **Das widerspricht der Lesart der
    bestehenden Phase-2-Zeile in flow_erwartungen.toml** ('Direkt aus Phase 1
    oder 2 heraus eine Interview-Aufnahme per Chat starten'), die nahelegt,
    der Chat starte direkt -- siehe Report (moeglicher Klasse-B-
    Dokumentationsbefund an der VORHERIGEN Karte t_2cdea48b, nicht an
    dieser; die Zeile selbst bleibt unangetastet). Das eigentliche Starten
    bleibt ``/aufnahme`` oder der danach angebotene Knopf -- diese Station
    drueckt ihn im zweiten Schritt, damit Stationen 16/17 einen wirklich
    laufenden Interviewmodus vorfinden."""
    from interview_theater import repo

    _gehe_nach_phase_3(conn, chat_id)

    stufe = "p15_angebot"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Sounds good -- tap the button below whenever you're ready.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [{"art": "interview_starten", "wert": ""}])

    vor_chat = repo.ist_interviewmodus_an(conn, chat_id)
    antwort = sende_nachricht(
        conn, tg, klm, e, chat_id, GIULIA, "we're starting the recording now",
    )
    nach_chat = repo.ist_interviewmodus_an(conn, chat_id)
    start_knopf = finde_knopf(tg, "Start interview") or finde_knopf(tg, "Aufnahme starten")

    gestartet_ueber_knopf = False
    if start_knopf is not None:
        druecke_knopf(conn, tg, klm, e, chat_id, start_knopf)
        gestartet_ueber_knopf = repo.ist_interviewmodus_an(conn, chat_id)

    s = Sondierung(
        phase=3, station="'interview_starten' per Chat ist nur ein Angebot, kein Start",
        persona=GIULIA.name,
        aktion="Pruefen, ob ein per Chat erkannter 'interview_starten'-Intent "
               "den Modus direkt einschaltet, oder nur den Start-Knopf anbietet",
        nachricht="we're starting the recording now", bot_antwort=antwort,
        schreibvorgang=(
            not vor_chat and not nach_chat
            and start_knopf is not None and gestartet_ueber_knopf
        ),
    )
    s.hinweis = (
        f"Interviewmodus nach dem Chat-Satz allein: {nach_chat} (erwartet: "
        "False -- 'interview_starten' loest nur das Angebot aus); Start-"
        f"Knopf wurde angeboten: {start_knopf is not None}; nach dem "
        f"Knopfdruck wirklich gestartet: {gestartet_ueber_knopf}"
    )
    return s


def station_16_interview_verwerfen_laufend(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """**Die erste MISST-statt-vermutet-Station** (Auftrag, Punkt 2 --
    es gibt keinen eigenen Erkenner-Intent fuer 'Interview abbrechen').
    Priya startet (ueber den echten Umschalter-Mechanismus, siehe Station
    15 -- der Chat allein startet nichts) ein Interview, es bekommt
    Transkriptinhalt, und WAEHREND es noch laeuft, sagt sie 'can we just
    delete this one' -- der Erkenner liest das als ``entfernen`` mit Ziel
    'interview'/'aufnahme'. Gemessen wird, ob das GERADE LAUFENDE Interview
    wirklich weich geloescht wird (nicht nur ein schon beendetes), und dass
    der Interviewmodus danach UNVERAENDERT an bleibt
    (``gruppe.interviewmodus_seit`` wird von ``entferne()`` nicht beruehrt --
    die naechste Sprachnachricht legt einen frischen Kopf an, siehe die
    Phase-3-Zeile 'Ein Interview ... verwerfen' in
    ``flow_erwartungen.toml``)."""
    from interview_theater import repo

    _gehe_nach_phase_3(conn, chat_id)
    _starte_interview_direkt(conn, chat_id)

    kopf_vorher = repo.laufendes_interview(conn, chat_id)
    if kopf_vorher is not None:
        repo.setze_transkript(conn, kopf_vorher["id"], "some early words already spoken")

    stufe2 = "p16_verwerfen"
    _konfiguriere_falls_attrappe(klm, stufe2).gespraech(
        stufe2, "Got it, deleting that one -- start again whenever you like.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe2, [{"art": "entfernen", "wert": "Interview 1"}])

    nachricht = "actually, can we just delete this one and start over"
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, PRIYA, nachricht)

    kopf_nachher = repo.hole_aufnahme(conn, kopf_vorher["id"]) if kopf_vorher else None
    laufendes_danach = repo.laufendes_interview(conn, chat_id)
    modus_noch_an = repo.ist_interviewmodus_an(conn, chat_id)
    geloescht = bool(kopf_nachher and kopf_nachher["entfernt_am"])

    s = Sondierung(
        phase=3, station="Interview per Chat verwerfen (noch laufend)", persona=PRIYA.name,
        aktion="Ein GERADE LAUFENDES Interview per Chat-Satz verwerfen, "
               "statt es erst zu beenden und dann in einem zweiten Schritt zu loeschen",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(kopf_vorher is not None and geloescht and modus_noch_an),
        fragen_der_persona=[
            "did that actually work?",
            "do I need to say start again, or does it just happen?",
        ],
    )
    s.hinweis = (
        f"Kopf vorhanden vor dem Versuch: {kopf_vorher is not None}; "
        f"entfernt_am danach gesetzt: {geloescht}; Interviewmodus danach "
        f"noch an: {modus_noch_an}; laufendes_interview() liefert danach "
        f"{'None (der entfernte Kopf zaehlt nicht mehr)' if laufendes_danach is None else 'einen Kopf -- unerwartet'}"
    )
    return s


def station_17_transkript_korrektur_waehrend_interview(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Investigiert Auftrag Punkt 3: eine Transkript-Korrektur als
    TEXTNACHRICHT waehrend ein Interview laeuft, geht IMMER durch den
    normalen Gespraechs-/Erkennerzug (``erkenner.ARTEN_IN_AUFNAHME`` gilt nur
    fuer SPRACHnachrichten innerhalb der Aufnahme-Pipeline -- eine
    Textnachricht landet nie dort). Die Korrektur muss also unveraendert
    greifen, auch mitten im Interviewmodus."""
    from interview_theater import repo

    _gehe_nach_phase_3(conn, chat_id)
    _starte_interview_direkt(conn, chat_id)

    kopf = repo.laufendes_interview(conn, chat_id)
    repo.setze_transkript(
        conn, kopf["id"], "she told us about the gepoekt market near the station",
    )

    stufe2 = "p17_korrektur"
    _konfiguriere_falls_attrappe(klm, stufe2).gespraech(
        stufe2, "Thanks, I'll fix that in the transcript.",
    )
    nachricht = "quick correction -- Whisper heard 'gepoekt' but it should be 'gepogt'"
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe2, [
            {"art": "transkript_korrigieren", "wert": "gepoekt -> gepogt"},
        ])

    vorher = (repo.hole_aufnahme(conn, kopf["id"])["transkript"] or "")
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher = (repo.hole_aufnahme(conn, kopf["id"])["transkript"] or "")

    s = Sondierung(
        phase=3, station="Transkript-Korrektur als Text waehrend eines laufenden Interviews",
        persona=GIULIA.name,
        aktion="Eine Transkript-Korrektur ALS TEXTNACHRICHT waehrend/nach "
               "einem Interview per Chat vornehmen",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=("gepogt" in nachher and "gepoekt" not in nachher),
    )
    s.hinweis = f"Transkript vorher={vorher!r} nachher={nachher!r}"
    return s


def _seed_fertige_verdichtung(conn, chat_id: int, text: str, name: str) -> int:
    """Legt direkt ueber ``repo`` ein beendetes, VERDICHTETES Interview an --
    ohne einen echten Modellaufruf (kein ``klm.schema(art='verdichter')``
    noetig). Grundlage fuer Stationen, die die Phase-4-Sperre pruefen wollen
    und dafuer selbststaendig (ohne eine vorherige Station in derselben
    Sitzung) eine Baseline brauchen, bei der ``bool(repo.verdichtungen(...))``
    bereits wahr ist (``phasen.voraussetzungen(...)[4]`` braucht BEIDES:
    mindestens eine Verdichtung UND keine unausgewerteten Interviews)."""
    from interview_theater import aufnahme, repo

    aufnahme_id = aufnahme.importiere_text(
        conn, None, chat_id, 0, text, name=name,
    )
    repo.setze_status(conn, aufnahme_id, "fertig")
    repo.speichere_verdichtung(conn, chat_id, aufnahme_id, f"Summary of {name}", [])
    return aufnahme_id


def _raeume_unausgewertete_interviews(conn, chat_id: int) -> None:
    """Entfernt (weich) jedes gerade unausgewertete Interview -- Aufraeumen
    VOR einer Station, die eine SAUBERE Phase-4-Baseline braucht,
    unabhaengig davon, was eine vorherige Station in DERSELBEN Sitzung
    absichtlich offen gelassen hat. Station 20 laesst bewusst ein offenes
    Interview stehen, um die Sperre zu demonstrieren -- ohne dieses
    Aufraeumen wuerde jede danach laufende Station in ``fuehre_alle_aus``
    dieselbe Sperre erben, obwohl sie ihre eigene, unabhaengige Baseline
    aufbauen will (gefunden beim ersten vollen Sitzungslauf aller 27
    Stationen, Task B)."""
    from interview_theater import aufnahme, repo

    for kopf in aufnahme.unausgewertete_interviews(conn, chat_id):
        repo.entferne_aufnahme(conn, chat_id, kopf["id"])


def station_18_normales_interview_wird_echt_verdichtet(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Die Baseline/Gegenprobe: ein Interview mit genug Material (>=
    ``aufnahme.MINDEST_WOERTER``) laeuft durch den ECHTEN Produktionspfad
    (``aufnahme.importiere_text`` -> ``aufnahme.verarbeite`` ->
    ``aufnahme._interview_abschliessen`` -> ``verdichter.verdichte``) --
    anders als die Stationen 19/20 unten, die ihre Baseline direkt ueber
    ``repo`` seeden, exerziert DIESE Station den vollen, bezahlten Lauf
    einmal wirklich durch (ueber ``SkriptLLM.verdichtung``, Task-B-Nachtrag
    an ``simulation.flow_audit_dynamisch.SkriptLLM``), um zu beweisen, dass
    diese Baseline-Annahme der beiden anderen Stationen stimmt und keine
    Fiktion ist."""
    from interview_theater import aufnahme, phasen, repo

    _gehe_nach_phase_3(conn, chat_id)
    _seed_phase3_voraussetzungen(conn, chat_id)
    _raeume_unausgewertete_interviews(conn, chat_id)

    text = (
        "We talked for a long time about the day she arrived in this city, "
        "how quiet the streets were, how she waited at the station for "
        "almost an hour before anyone came, how strange the silence felt "
        "and how she slowly began to feel at home here after meeting her "
        "neighbours and sharing meals with them every week since then."
    )
    assert len(text.split()) >= 40

    stufe = "p18_verdichtung"
    if isinstance(klm, SkriptLLM):
        klm.stelle(stufe).verdichtung(
            stufe, "Arrival, waiting at the station, and slowly feeling at home.",
        )
    aufnahme_id = aufnahme.importiere_text(
        conn, e, chat_id, tg.naechste_message_id(), text, name="Interview 1",
    )
    aufnahme.verarbeite(conn, tg, klm, e, None, aufnahme_id)

    verdichtung = repo.verdichtung_zu_aufnahme(conn, aufnahme_id)
    kopf = repo.hole_aufnahme(conn, aufnahme_id)
    phase4_moeglich = phasen.voraussetzungen(conn, chat_id)[4]

    s = Sondierung(
        phase=3, station="Ein normales Interview wird echt verdichtet", persona=GIULIA.name,
        aktion="Ein ausreichend langes Interview ueber den echten "
               "Verdichtungslauf abschliessen lassen",
        schreibvorgang=(
            verdichtung is not None and not kopf["zu_kurz_uebersprungen"]
            and phase4_moeglich is True
        ),
    )
    s.hinweis = (
        f"Verdichtung angelegt: {verdichtung is not None}; "
        f"zu_kurz_uebersprungen: {bool(kopf['zu_kurz_uebersprungen'])}; "
        f"Phase 4 moeglich: {phase4_moeglich}"
    )
    return s


def station_19_kurzes_interview_blockiert_phase4_nicht(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Investigiert Auftrag Punkt 5 (erster Teil, der Kernbefund der zu-kurz-
    Reparatur 'Padua Phasen TEIL 2, Befund 4a'): ein Interview unter
    ``aufnahme.MINDEST_WOERTER`` (40) wird bei ``aufnahme.verarbeite`` NICHT
    verdichtet (``_zu_kurz_gemeldet`` greift VOR jedem Modellaufruf), bekommt
    ``zu_kurz_uebersprungen=1`` -- und blockiert die Phase-4-Sperre
    (``phasen.voraussetzungen(...)[4]``) TROTZDEM NICHT, solange mindestens
    eine ANDERE, echte Verdichtung existiert. Selbststaendig lauffaehig: die
    Baseline-Verdichtung wird direkt geseedet (``_seed_fertige_verdichtung``),
    unabhaengig davon, ob Station 18 vorher in derselben Sitzung lief."""
    from interview_theater import aufnahme, phasen, repo

    _gehe_nach_phase_3(conn, chat_id)
    _seed_phase3_voraussetzungen(conn, chat_id)
    _raeume_unausgewertete_interviews(conn, chat_id)
    _seed_fertige_verdichtung(
        conn, chat_id, "A long, unrelated interview about the market.", "Interview 1",
    )

    kurzer_text = "Yes. No. It was fine, I guess. Nothing much to say really."
    assert len(kurzer_text.split()) < aufnahme.MINDEST_WOERTER

    vorher_gesendet = len(tg.gesendet)
    aufnahme_id = aufnahme.importiere_text(
        conn, e, chat_id, tg.naechste_message_id(), kurzer_text, name="Interview 2",
    )
    aufnahme.verarbeite(conn, tg, klm, e, None, aufnahme_id)
    neue = tg.gesendet[vorher_gesendet:]

    kopf = repo.hole_aufnahme(conn, aufnahme_id)
    phase4_moeglich = phasen.voraussetzungen(conn, chat_id)[4]
    offen = aufnahme.unausgewertete_interviews(conn, chat_id)

    s = Sondierung(
        phase=3, station="Kurzes Interview blockiert Phase 4 nicht", persona=PRIYA.name,
        aktion="Ein sehr kurzes Interview (< 40 Woerter) abschliessen lassen "
               "und pruefen, dass Phase 4 trotzdem erreichbar bleibt",
        bot_antwort="\n".join(n["text"] for n in neue if n.get("text")),
        schreibvorgang=(
            bool(kopf["zu_kurz_uebersprungen"]) and phase4_moeglich is True
            and aufnahme_id not in {o["id"] for o in offen}
        ),
    )
    s.hinweis = (
        f"zu_kurz_uebersprungen: {bool(kopf['zu_kurz_uebersprungen'])}; "
        f"Phase 4 moeglich: {phase4_moeglich}; dieses Interview noch in "
        f"unausgewertete_interviews(): {aufnahme_id in {o['id'] for o in offen}}"
    )
    return s


def station_20_offenes_interview_blockiert_phase4(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """**Die zweite MISST-statt-vermutet-Station**, das Gegenstueck zu
    Station 19 (Auftrag Punkt 5, zweiter Teil -- 'Phase-4-Sperre nur bei
    echt LAUFENDER Verdichtung'): ein ausreichend langes Interview wird
    importiert (also 'beendet' im Sinn von
    ``aufnahme.unausgewertete_interviews``: ``status='transkribiert'``),
    aber NIE verdichtet (kein ``verarbeite``-Aufruf). Das muss die
    Phase-4-Sperre WIRKLICH blockieren -- anders als das zu-kurze Interview
    aus Station 19, das genau dieselbe Form hat, aber die Sperre NICHT
    bloeckt, weil ``zu_kurz_uebersprungen`` gesetzt ist. Selbststaendig
    lauffaehig wie Station 19 (eigene Baseline-Verdichtung geseedet)."""
    from interview_theater import aufnahme, phasen

    _gehe_nach_phase_3(conn, chat_id)
    _seed_phase3_voraussetzungen(conn, chat_id)
    _raeume_unausgewertete_interviews(conn, chat_id)
    _seed_fertige_verdichtung(
        conn, chat_id, "A long, unrelated interview about the market.", "Interview 1",
    )
    phase4_vorher = phasen.voraussetzungen(conn, chat_id)[4]

    langer_text = (
        "We spoke for quite a while about her childhood neighbourhood, the "
        "shop on the corner that closed years ago, the friends she lost "
        "touch with, and how different the street sounds now compared to "
        "when she was young and everyone still knew each other by name."
    )
    assert len(langer_text.split()) >= aufnahme.MINDEST_WOERTER
    aufnahme_id = aufnahme.importiere_text(
        conn, e, chat_id, tg.naechste_message_id(), langer_text, name="Interview 2",
    )
    # Bewusst KEIN aufnahme.verarbeite(...) hier -- das Interview bleibt
    # 'transkribiert' und unverdichtet, genau der Fall, den diese Station
    # misst.

    offen = aufnahme.unausgewertete_interviews(conn, chat_id)
    phase4_nachher = phasen.voraussetzungen(conn, chat_id)[4]

    s = Sondierung(
        phase=3, station="Offenes, nie verdichtetes Interview blockiert Phase 4",
        persona=GIULIA.name,
        aktion="Ein ausreichend langes, aber nie verdichtetes Interview "
               "liegen lassen und pruefen, dass Phase 4 dadurch gesperrt bleibt",
        schreibvorgang=(
            phase4_vorher is True
            and aufnahme_id in {o["id"] for o in offen}
            and phase4_nachher is False
        ),
    )
    s.hinweis = (
        f"Phase 4 vor dem offenen Interview: {phase4_vorher}; dieses "
        f"Interview in unausgewertete_interviews(): "
        f"{aufnahme_id in {o['id'] for o in offen}}; Phase 4 danach: {phase4_nachher}"
    )
    return s


def station_21_phasenhinweis_genau_einmal(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Investigiert Auftrag Punkt 5 ('Meldung genau 1x'). **Gefundene
    Abweichung vom urspruenglich dokumentierten Mechanismus**:
    ``aufnahme._phasenfrage`` (der in AGENTS.md beschriebene Weg, "Kommen
    noch Interviews, oder gehen wir ans Kernthema?" an die
    Verdichtungsnachricht zu haengen) hat HEUTE keinen einzigen Aufrufer
    mehr im Code -- der Kommentar in ``aufnahme._interview_abschliessen``
    (bei ``Zeile ~1792``) sagt woertlich, dass sie seit dem 05.09.2026
    bewusst entfernt wurde ('die Gruppe macht ein Interview nach dem anderen
    und entscheidet selbst, wann sie weitergeht'). Der tatsaechlich wirkende
    Mechanismus fuer 'genau einmal anbieten' ist seitdem ausschliesslich
    ``kontext._baue_phasenhinweis`` (im naechsten Gespraechszug, nicht an
    der Verdichtungsnachricht) -- mit demselben Merkposten
    (``phasen.offenes_angebot``/``merke_angebot``). Diese Station misst
    GENAU DIESEN, heute wirkenden Mechanismus direkt."""
    from interview_theater import kontext, phasen

    _gehe_nach_phase_3(conn, chat_id)
    _seed_phase3_voraussetzungen(conn, chat_id)
    _raeume_unausgewertete_interviews(conn, chat_id)
    _seed_fertige_verdichtung(
        conn, chat_id, "A complete, verdichted interview.", "Interview 1",
    )

    erstes_angebot = phasen.offenes_angebot(conn, chat_id)
    erster_hinweistext = kontext._baue_phasenhinweis(conn, chat_id)
    zweites_angebot = phasen.offenes_angebot(conn, chat_id)
    zweiter_hinweistext = kontext._baue_phasenhinweis(conn, chat_id)

    s = Sondierung(
        phase=3, station="Phasenhinweis auf Phase 4 kommt genau einmal", persona=PRIYA.name,
        aktion="Nach einem abgeschlossenen Interview pruefen, dass der "
               "Phase-4-Hinweis im naechsten Gespraechszug genau einmal "
               "erscheint und sich danach nicht wiederholt",
        schreibvorgang=(
            erstes_angebot == 4 and bool(erster_hinweistext)
            and zweites_angebot is None and not zweiter_hinweistext
        ),
    )
    s.hinweis = (
        f"offenes_angebot() 1. Aufruf: {erstes_angebot} (Hinweistext "
        f"{'vorhanden' if erster_hinweistext else 'LEER'}); 2. Aufruf: "
        f"{zweites_angebot} (Hinweistext "
        f"{'vorhanden -- unerwartet' if zweiter_hinweistext else 'leer, wie erwartet'}). "
        "aufnahme._phasenfrage ist seit 05.09.2026 toter Code (kein "
        "Aufrufer mehr) -- AGENTS.md beschreibt ihn noch als aktiven Weg, "
        "siehe Report (moeglicher Klasse-B-Dokumentationsbefund)."
    )
    return s


# ---------------------------------------------------------------------------
# Phase 4 -- Setting, Figuren & Geschichte (Padua: "Frame") -- Task B,
# t_92f99911.
# ---------------------------------------------------------------------------


def _gehe_nach_phase_4(conn, chat_id: int) -> None:
    from interview_theater import phasen

    phasen.setze(conn, chat_id, 4, "befehl")


def station_22_eintritt_phase4_offene_frage_ohne_knoepfe(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Eintritt in Phase 4: Klartext-Pruefung wie Station 1/6, PLUS die seit
    06.09.2026 geltende Design-Entscheidung ('unter einer offenen Frage gibt
    es keine Knoepfe, weil dahinter nichts Fixes zu speichern ist',
    ``knoepfe/stationen.py::biete_proaktiv``): der Phaseneintritt bietet
    KEINE Knoepfe 'Ja, wir zuerst'/'Schlag du vor' mehr an -- die Gruppe
    antwortet zwangslaeufig in freier Sprache."""
    stufe = "p22_eintritt"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe,
        "From here on we invent, freely -- what should the people in this "
        "story be like, and where does it take place?",
    )
    from interview_theater import knoepfe as knoepfe_modul

    vorher = len(tg.gesendet)
    knoepfe_modul.eintritt_in_phase(conn, tg, klm, e, chat_id, 4)
    warte_auf_neue_nachricht(tg, vorher, timeout=5.0)

    gesamter_text = "\n".join(
        n["text"] for n in tg.gesendet[vorher:] if n.get("text")
    )
    jargon = jargon_treffer(gesamter_text)
    schlag_vor_knopf = finde_knopf(tg, "Schlag du vor")
    wir_zuerst_knopf = finde_knopf(tg, "wir zuerst")

    s = Sondierung(
        phase=4, station="Eintritt Phase 4", persona=GIULIA.name,
        aktion="Klartext-Pruefung beim Phaseneintritt, UND pruefen, dass "
               "der Einstieg selbst keine 'Ja, wir zuerst'/'Schlag du "
               "vor'-Knoepfe mehr anbietet (offene Frage statt Knopf, seit 06.09.2026)",
        bot_antwort=gesamter_text,
    )
    s.hinweis = (
        f"Jargon-Treffer: {jargon or 'keine'}; 'Schlag du vor'-Knopf beim "
        f"Eintritt angeboten: {schlag_vor_knopf is not None} (erwartet: "
        f"False); 'wir zuerst'-Knopf angeboten: {wir_zuerst_knopf is not None} "
        "(erwartet: False)"
    )
    return s


def station_23_setting_per_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """**Die Mutationsprobe-Station dieser Karte fuer Phase 4** (das
    Abnahmekriterium von t_92f99911: 'einen Intent ... entfernen -> Schicht
    1 UND Schicht 2 melden den Befund'). Giulia nennt das Setting per
    Chat-Satz, ohne VORSCHLAG-Block -- die Aenderung kommt ausschliesslich
    ueber den Absichtserkenner (``rahmen_setzen``), wie Station 3 fuer
    Begriffe."""
    from interview_theater import repo

    _gehe_nach_phase_4(conn, chat_id)

    stufe = "p23_setting"
    nachricht = "let's set it at a late-night laundromat, two years from now"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Got it -- a late-night laundromat, two years from now.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [
            {"art": "rahmen_setzen", "wert": "A late-night laundromat, two years from now."},
        ])

    vorher = repo.hole_arbeitsstand(conn, chat_id)
    vorher_wert = vorher["rahmen"] if vorher else None
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher = repo.hole_arbeitsstand(conn, chat_id)
    nachher_wert = nachher["rahmen"] if nachher else None

    s = Sondierung(
        phase=4, station="Das Setting per Chat nennen (Mutationsprobe)", persona=GIULIA.name,
        aktion="Das Setting (Ort, Zeit, Anlass) per Chat nennen, statt die Grundleiste zu nutzen",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher_wert != nachher_wert and bool(nachher_wert)),
    )
    s.hinweis = f"arbeitsstand.rahmen vorher={vorher_wert!r} nachher={nachher_wert!r}"
    return s


def station_24_figuren_per_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Priya nennt eine Figur per Chat-Satz (``figur_setzen``, Format 'Name:
    Beschreibung') -- parallel zum Knopfweg ueber die Figurenliste
    (``knoepfe/figuren.py``), aber ohne auf den Anzahl-/Namen-Knopf zu
    warten."""
    from interview_theater import repo

    _gehe_nach_phase_4(conn, chat_id)

    stufe = "p24_figur"
    nachricht = "there should be a character called Mira, she's curious and speaks her mind"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Nice -- Mira, curious and speaks her mind. Noted.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [
            {"art": "figur_setzen", "wert": "Mira: curious, speaks her mind"},
        ])

    vorher = repo.figuren(conn, chat_id)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, PRIYA, nachricht)
    nachher = repo.figuren(conn, chat_id)
    mira = next((f for f in nachher if f["name"].strip().lower() == "mira"), None)

    s = Sondierung(
        phase=4, station="Eine Figur per Chat nennen", persona=PRIYA.name,
        aktion="Anzahl oder Namen der Figuren per Chat nennen, statt die "
               "Anzahl-/Namen-Knoepfe der Figurenliste zu benutzen",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(len(nachher) > len(vorher) and mira is not None),
        fragen_der_persona=[
            "do I need to say her age too?",
            "will this be saved even without pressing anything?",
        ],
    )
    s.hinweis = f"Figuren vorher={len(vorher)} nachher={len(nachher)}, Mira gefunden: {mira is not None}"
    return s


def station_25_geschichte_per_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Giulia erzaehlt die Geschichte (Bogen + Ende) einfach per Chat, statt
    auf das Richtungs-Menue des Bots (``knoepfe/szenen.py::sende_geschichte``)
    zu reagieren -- ``geschichte_setzen`` ist phasenfrei und 'wird notiert
    wie jedes andere Arbeitsstandfeld' (Kommentar bei der Definition in
    ``erkenner.ARTEN``)."""
    from interview_theater import repo

    _gehe_nach_phase_4(conn, chat_id)

    stufe = "p25_geschichte"
    nachricht = (
        "here's what happens: two strangers keep running into each other "
        "at the laundromat every week, and in the end they realise they've "
        "been avoiding going home for the same reason"
    )
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "I love that arc -- noted as your story.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [
            {"art": "geschichte_setzen", "wert": (
                "Two strangers keep running into each other at the "
                "laundromat every week, and in the end they realise "
                "they've been avoiding going home for the same reason."
            )},
        ])

    vorher = repo.hole_arbeitsstand(conn, chat_id)
    vorher_wert = vorher["geschichte"] if vorher else None
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher = repo.hole_arbeitsstand(conn, chat_id)
    nachher_wert = nachher["geschichte"] if nachher else None

    s = Sondierung(
        phase=4, station="Die Geschichte per Chat erzaehlen", persona=GIULIA.name,
        aktion="Die Geschichte (Bogen + Ende) per Chat selbst erzaehlen, "
               "statt auf das Richtungs-Menue des Bots zu reagieren",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher_wert != nachher_wert and bool(nachher_wert)),
    )
    s.hinweis = f"arbeitsstand.geschichte gesetzt: {bool(nachher_wert)}"
    return s


def station_26_us_einwilligung_per_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Investigiert Auftrag Punkt 6. **Gefundene Abweichung vom im
    Kartentext erwarteten Zeitpunkt** -- in die GUTE Richtung: die
    Einwilligungsfrage zum US-Modell steht laut Code (``knoepfe/
    stationen.py::eintritt_in_phase``, Zweig ``PHASE_BEGRIFFE``) bereits
    seit dem 03.10.2026 beim Eintritt in PHASE 1, nicht erst bei Phase 4 --
    und zusaetzlich nochmal als Sicherheitsnetz beim Eintritt in Phase 4
    selbst. Diese Station prueft den CHAT-Weg (statt der zwei Knoepfe): die
    Erkenner-art ``szene_usa`` ist phasenfrei und greift, sobald das Angebot
    einmal gestellt wurde (``repo.merke_szene_usa_angeboten``)."""
    from interview_theater import repo

    _gehe_nach_phase_4(conn, chat_id)
    repo.merke_szene_usa_angeboten(conn, chat_id)

    stufe = "p26_usa"
    nachricht = "yes, the US model is fine with us"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(
        stufe, "Great, scenes will use the US model from now on.",
    )
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [{"art": "szene_usa", "wert": "ja"}])

    vorher = repo.szene_usa_stand(conn, chat_id)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, PRIYA, nachricht)
    nachher = repo.szene_usa_stand(conn, chat_id)

    s = Sondierung(
        phase=4, station="US-Einwilligung per Chat beantworten", persona=PRIYA.name,
        aktion="Der Uebermittlung an ein US-Modell per Chat zustimmen, "
               "statt die zwei Knoepfe zu druecken",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(vorher == "offen" and nachher == "ja"),
        fragen_der_persona=["does this mean my voice goes to America too?"],
    )
    s.hinweis = f"szene_usa_stand vorher={vorher!r} nachher={nachher!r}"
    return s


def station_27_phasenwechsel_4_zu_5_per_chat(conn, tg, klm, e, chat_id: int) -> Sondierung:
    """Investigiert Auftrag Punkt 9, Gegenstueck zu Station 12 (Phase 2->3)
    fuer den Uebergang 4->5: ``phase_setzen`` ist phasenfrei, greift also
    auch hier per Chat-Satz statt per Knopf ('Weiter zu Phase 5' /
    ``ART_PHASE``)."""
    from interview_theater import knoepfe as knoepfe_modul, phasen, repo

    _gehe_nach_phase_4(conn, chat_id)
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "A late-night laundromat.")
    repo.setze_figur(conn, chat_id, "Mira", "curious, speaks her mind")
    repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", repo._jetzt())
    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte",
        "Two strangers keep running into each other and finally talk.",
    )
    repo.setze_arbeitsstand(conn, chat_id, "szenen_anzahl", "3")
    assert phasen.voraussetzungen(conn, chat_id)[5] is True

    vorher_angebot = len(tg.gesendet)
    knoepfe_modul.biete_phase_proaktiv(conn, tg, chat_id)
    angebot_text = "\n".join(
        n["text"] for n in tg.gesendet[vorher_angebot:] if n.get("text")
    )

    stufe = "p27_wechsel"
    nachricht = "that's it, let's move on to the next step"
    _konfiguriere_falls_attrappe(klm, stufe).gespraech(stufe, "Great, moving on!")
    if isinstance(klm, SkriptLLM):
        klm.erkenner(stufe, [{"art": "phase_setzen", "wert": "5"}])

    vorher_phase = phasen.aktuelle(conn, chat_id)
    antwort = sende_nachricht(conn, tg, klm, e, chat_id, GIULIA, nachricht)
    nachher_phase = phasen.aktuelle(conn, chat_id)

    s = Sondierung(
        phase=4, station="Phasenwechsel 4->5 per Chat statt Knopf", persona=GIULIA.name,
        aktion="Sagen, dass Phase 4 fertig ist und es weiter zu Phase 5 "
               "gehen soll, statt 'Weiter zu Phase 5' zu druecken",
        nachricht=nachricht, bot_antwort=antwort,
        schreibvorgang=(nachher_phase == 5 and vorher_phase == 4),
    )
    s.hinweis = (
        f"Angebotstext enthielt 'Phase': {'Phase' in angebot_text}; "
        f"Phase vorher={vorher_phase}, nachher={nachher_phase}"
    )
    return s


#: Die Reihenfolge, in der eine Persona-Sitzung die Karte durchlaeuft --
#: dieselbe Reihenfolge wie im Aufgabenbrief, plus Station 14 (Review-
#: Nachtrag Phase 1+2) und die Stationen 15-27 (Task B, t_92f99911: Phase 3
#: Interviews + Phase 4 Setting/Figuren/Geschichte) angehaengt.
#: ``fuehre_alle_aus`` ruft sie alle gegen DIESELBE
#: ``conn``/``tg``/``klm``/``chat_id``, wie eine echte Sitzung; jede
#: einzelne Funktion bleibt trotzdem fuer sich lauffaehig (sie seedet, was
#: sie zusaetzlich zur bisherigen Sitzung braucht, direkt ueber ``repo``).
ALLE_STATIONEN = (
    station_01_eintritt,
    station_02_begriffe_vorschlag,
    station_03_korrektur_via_chat,
    station_04_begriffsboard_korrektur,
    station_05_echo_kontrolle,
    station_06_eintritt_phase2,
    station_07_priya_eigene_frage,
    station_08_giulia_aendert_frage,
    station_09_fruehzeitig_fertig,
    station_10_priya_akzeptiert_per_chat,
    station_11_klickzwang,
    station_12_phasenwechsel_per_chat,
    station_13_wartezustand,
    station_14_priya_begriffe_korrektur,
    station_15_interview_starten_ist_knopf_bzw_befehl_only,
    station_16_interview_verwerfen_laufend,
    station_17_transkript_korrektur_waehrend_interview,
    station_18_normales_interview_wird_echt_verdichtet,
    station_19_kurzes_interview_blockiert_phase4_nicht,
    station_20_offenes_interview_blockiert_phase4,
    station_21_phasenhinweis_genau_einmal,
    station_22_eintritt_phase4_offene_frage_ohne_knoepfe,
    station_23_setting_per_chat,
    station_24_figuren_per_chat,
    station_25_geschichte_per_chat,
    station_26_us_einwilligung_per_chat,
    station_27_phasenwechsel_4_zu_5_per_chat,
)


def fuehre_alle_aus(conn, tg, klm, e, chat_id: int) -> list[Sondierung]:
    """Faehrt alle 27 Stationen in der Reihenfolge des Aufgabenbriefs
    (Station 14 angehaengt als Phase-1/2-Review-Nachtrag; Stationen 15-27
    aus Task B, t_92f99911, siehe Kommentare vor ihren Definitionen) gegen
    EINE geteilte Sitzung. Bricht bei einer werfenden Station nicht ab -- ein
    Fehlschlag einer Station ist selbst ein Befund und wird als Sondierung
    mit dem Fehlertext im ``hinweis`` weitergegeben, damit ein Bericht
    trotzdem vollstaendig bleibt.

    **Klasse-A-Fix (04.10.2026):** eine abgebrochene Station setzt
    ``schreibvorgang=False`` -- NICHT den Default ``None`` --, damit
    ``Sondierung.wirkungslos`` (``schreibvorgang is False``) fuer sie
    ``True`` ist. ``scripts/flow_audit_lauf.py:schreibe_bericht`` gruppiert
    die Abschnitt-"Befunde" ausschliesslich ueber ``wirkungslos``; mit dem
    alten Default ``None`` sah eine mit ``AttributeError`` abgebrochene
    Station in diesem Bericht wie Station 2 aus (``schreibvorgang=None``,
    "nichts zu schreiben erwartet, wie vorgesehen") -- im echten,
    kostenpflichtigen Lauf stand deshalb "Keine -- alle Sondierungen haben
    gewirkt", obwohl alle Stationen gecrasht waren."""
    ergebnisse: list[Sondierung] = []
    for station in ALLE_STATIONEN:
        try:
            ergebnisse.append(station(conn, tg, klm, e, chat_id))
        except Exception as fehler:  # noqa: BLE001 -- ein Befund, kein Testabbruch
            ergebnisse.append(Sondierung(
                phase=0, station=station.__name__, persona="?",
                aktion="(Station ist mit einer Ausnahme abgebrochen)",
                schreibvorgang=False,
                hinweis=f"{type(fehler).__name__}: {fehler}",
            ))
    return ergebnisse
