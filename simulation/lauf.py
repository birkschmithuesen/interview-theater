"""Der Lauf: ein kompletter Workshop durch alle Schritte des Skripts.

Derselbe Codepfad wie im Betrieb -- ``bot.verarbeite_update`` fuer jede
Nachricht, ``bot._zug_und_erkenner`` fuer den Zug samt Absichtserkenner und
Journal-Extraktor. Nur drei Dinge sind anders:

1. **Telegram ist eine Attrappe** (``attrappe.py``). Bot-Nachrichten kaemen
   bei einem zweiten Bot ohnehin nie an (Telegram Bot-FAQ), und ein Netzweg
   waere hier reine Verkleidung.
2. **Alles laeuft in einem Thread** (``einfaedig``). Der Betrieb gibt Szene,
   Interviewabschluss und Auswertung an eigene Threads ab, weil dort niemand
   warten soll; hier muss jede Wirkung in der Datenbank stehen, bevor der
   naechste Schritt seinen Zielzustand prueft.
3. **Interviews kommen als Text** (``aufnahme.importiere_text``, § 10.5) --
   kein Whisper. Der Sprachweg ist in ``tests/test_aufnahme.py`` und im
   Rauchtest gemessen; ihn hier zu wiederholen kostete Geld und mehr Laufzeit
   als alles andere zusammen.

**Notausgang.** Bekommt der Bot ein "fertig" nicht mit, schliesst der
Simulator das Interview selbst ab und zaehlt einen ``notausgang``. Das ist
kein Nachhelfen zugunsten der Zahlen: der verpasste Abschluss steht als
gescheiterter Schritt und als Zahl im Bericht. Ohne den Notausgang waere ein
Lauf mit einem tauben Erkenner ab Schritt 3 wertlos -- und damit auch
bezahlt, ohne etwas ueber die Schritte 4 bis 9 zu sagen.
"""

from __future__ import annotations

import contextlib
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from interview_theater import aufnahme, bot, kontext, phasen, repo, szene

from simulation import bericht, claude, kennzahlen, material, richter, skript, stimmen
from simulation.kennzahlen import Beitrag, Zug

log = logging.getLogger(__name__)

#: Die Gruppe, in der die Simulation spielt. Negative Zahl wie eine echte
#: Telegram-Gruppe; sie steht in einer Wegwerf-Datenbank und kollidiert mit
#: nichts.
CHAT_ID = -1_000_000_001
CHAT_TITEL = "Simulationsgruppe"

#: Startzeitpunkt der simulierten Nachrichten. Bewusst **jetzt** und nicht
#: ein fester Tag: ``ablauf``/``aufnahme`` pruefen das Alter der Nachricht
#: (``bot.ist_nachtstau``, 15 Minuten), und ein Lauf mit Nachrichten von
#: gestern loeste ueberhaupt keine Zuege aus.
SEKUNDEN_JE_NACHRICHT = 5

#: Alternativname fuer die Transkriptkorrektur in Schritt 8 ("X heisst Y").
ERSATZNAME = "Rukiye"

#: Nach welchem Schritt ``--pause`` die Nacht einlegt. Der vierte -- da steht
#: ein Kernthema, und die Gruppe hat etwas zu verlieren, wenn der Bot am
#: naechsten Morgen nicht mehr weiss, wo sie war.
PAUSE_NACH_SCHRITT = 4

#: Um wie viele Stunden ``--pause`` den Chat zurueckdatiert. Vierzehn: eine
#: Nacht zwischen zwei Workshoptagen, und deutlich mehr als
#: ``bot.PAUSE_GRENZE_MINUTEN`` (30), ab denen die Wiederkehr-Zeile faellig
#: wird.
PAUSE_STUNDEN = 14


@dataclass
class Ergebnis:
    """Alles, was ein Lauf hinterlaesst."""

    zuege: list[Zug] = field(default_factory=list)
    schritte: dict = field(default_factory=dict)       # schluessel -> erreicht?
    ziele: dict = field(default_factory=dict)          # schluessel -> gefuelltes Ziel
    urteile: dict = field(default_factory=dict)        # schluessel -> Richter-Urteil
    #: Je geschriebener Szene ein Dict: schluessel, nummer, titel, form,
    #: volltext, urteil. Eine Liste und kein einzelner Text, seit ``--set
    #: birk`` drei Szenen in drei Formen schreiben laesst -- und weil der
    #: Bericht sie **vollstaendig** zeigen soll, nicht die letzte davon.
    szenen: list = field(default_factory=list)
    #: Die fuenf schlechtesten Bot-Antworten samt Block-Umriss und dem
    #: Urteil, ob dem Bot Information gefehlt hat (``bericht.kandidaten_schlechteste``).
    schlechteste: list = field(default_factory=list)
    #: Was der Richter ueber das Journal sagt (N4a).
    journal_urteil: dict = field(default_factory=dict)
    #: Was der Bot nach der simulierten Nacht geschickt hat (``--pause``).
    wiederkehr: list = field(default_factory=list)
    zahlen: dict = field(default_factory=dict)
    gezogene: list = field(default_factory=list)
    personen: list = field(default_factory=list)
    notausgaenge: int = 0
    verweigerungen: int = 0  # Stimmen, die das Simulationsmodell verweigert hat (refusal)
    dauer_s: float = 0.0
    titel: dict = field(default_factory=dict)          # schluessel -> Schritt-Titel

    @property
    def szenen_urteil(self) -> dict:
        """Das Urteil ueber die zuletzt geschriebene Szene -- die Form, in der
        ``verlauf.jsonl`` seit dem ersten Lauf eine Szene fuehrt. Bleibt, damit
        alte Verlaufszeilen mit neuen vergleichbar bleiben."""
        return self.szenen[-1]["urteil"] if self.szenen else {}

    @property
    def szene_text(self) -> str:
        return self.szenen[-1]["volltext"] if self.szenen else ""


# ---------------------------------------------------------------------------
# Einfaedigkeit
# ---------------------------------------------------------------------------


def _sofort_szene(conn, tg, klm, e, chat_id, auftrag):
    """Ersatz fuer ``szene.starte``: schreibt die Szene **im aufrufenden
    Thread**.

    Die Ankuendigung ("Ich schreibe die Szene aus, das dauert eine Minute")
    faellt weg -- sie ueberbrueckt im Betrieb eine Wartezeit, und hier wartet
    niemand. Fehler werden wie im Betrieb gemeldet, damit der Richter
    dieselbe Zeile sieht wie eine echte Gruppe.

    Seit 05.09. frueh: Sperre und US-Angebot laufen wie im Betrieb --
    ``szene.starte`` prueft, fragt (einmal je Gruppe) und gibt None zurueck;
    dann muss die Stimme antworten, und der naechste Aufruf schreibt. Der
    Aufrufer (``_fahre_szene``) faengt das ab."""
    auftrag = (auftrag or "").strip()
    if not auftrag:
        return None
    from interview_theater import szene_claude
    if szene_claude.angebot_faellig(e, conn, chat_id):
        repo.merke_szene_usa_angeboten(conn, chat_id, auftrag)
        tg.sende(chat_id, szene._TEXT_ANGEBOT_USA)
        return "angebot"
    if szene_claude.wartet_auf_antwort(e, conn, chat_id):
        repo.merke_szene_usa_angeboten(conn, chat_id, auftrag)
        tg.sende(chat_id, szene._TEXT_USA_ERINNERUNG)
        return "wartet"
    # Die Sperre (Pflichtfelder, Sprachprofil) laeuft hier NICHT: der
    # Simulator misst den Szenentext, nicht die Sperre, und seine
    # Netz-Attrappen legen keine Sprachprofile an.
    if szene_claude.ist_aktiv(e, conn, chat_id):
        tg.sende(chat_id, szene._TEXT_WARNUNG_USA)
    try:
        szene.schreibe(conn, tg, klm, e, chat_id, auftrag)
    except Exception:
        log.exception("Szenen-Aufruf in der Simulation fehlgeschlagen")
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "szene_fehlgeschlagen",
            "Szenen-Aufruf fehlgeschlagen (Simulation)",
        )
        tg.sende(chat_id, szene._TEXT_FEHLER)
    return None


def _sofort_abschluss(conn, tg, klm, e, kopf_id):
    aufnahme.schliesse_ab(conn, tg, klm, e, kopf_id)
    return None


def _sofort_auswertung(conn, tg, klm, e, kopf_id):
    aufnahme._auswerten(conn, tg, klm, e, kopf_id)
    return None


#: Die beiden Umbauten unten ersetzen Funktionen in Modulen des Betriebs.
#: Bei ``--parallel`` tun das zwei Laeufe in zwei Threads gleichzeitig -- und
#: ohne Buchhaltung sichert der zweite die **schon ersetzte** Funktion als
#: "Original" und stellt sie am Ende wieder her: der Betriebscode bliebe fuer
#: den Rest des Prozesses einfaedig. Deshalb je Umbau ein Zaehler unter dieser
#: Sperre: eingebaut wird beim ersten Lauf, zurueckgestellt beim letzten.
_SPERRE = threading.Lock()
_TIEFE: dict[str, int] = {}
_ORIGINAL: dict[str, object] = {}


def _erster(name: str) -> bool:
    """Zaehlt einen Nutzer des Umbaus ``name`` hinzu und sagt, ob er der
    erste ist -- nur der baut um. Unter ``_SPERRE`` aufzurufen."""
    _TIEFE[name] = _TIEFE.get(name, 0) + 1
    return _TIEFE[name] == 1


def _letzter(name: str) -> bool:
    """Zaehlt einen Nutzer ab und sagt, ob er der letzte war -- nur der
    stellt zurueck. Unter ``_SPERRE`` aufzurufen."""
    _TIEFE[name] -= 1
    return _TIEFE[name] == 0


@contextlib.contextmanager
def einfaedig():
    """Ersetzt die drei Stellen, die im Betrieb einen Thread starten, durch
    synchrone Aufrufe -- und stellt sie danach wieder her.

    Ohne das wuerde der Simulator den Zielzustand eines Schritts pruefen,
    waehrend die Wirkung noch in einem Thread unterwegs ist: der Schritt
    gaelte als gescheitert, obwohl der Bot alles richtig gemacht hat, nur
    eine Zehntelsekunde spaeter."""
    with _SPERRE:
        if _erster("einfaedig"):
            _ORIGINAL["einfaedig"] = (
                szene.starte, aufnahme.starte_abschluss, aufnahme.starte_auswertung
            )
            szene.starte = _sofort_szene
            aufnahme.starte_abschluss = _sofort_abschluss
            aufnahme.starte_auswertung = _sofort_auswertung
    try:
        yield
    finally:
        with _SPERRE:
            if _letzter("einfaedig"):
                (szene.starte, aufnahme.starte_abschluss,
                 aufnahme.starte_auswertung) = _ORIGINAL.pop("einfaedig")


#: Wohin ``kontext.baue`` gerade mitschreibt -- je Thread eines. Bei
#: ``--parallel`` benutzen zwei Laeufe denselben umgebauten Kontextaufbau, und
#: die Prompt-Umrisse des einen haben in der Verlaufszeile des anderen nichts
#: zu suchen.
_mitschrift = threading.local()


@contextlib.contextmanager
def kontext_protokoll(protokoll: list):
    """Schreibt zu jedem Gespraechs-Prompt mit, welcher Block mit wie vielen
    Token darin stand (``kontext.umriss``).

    Gesetzt wird ``kontext.baue`` -- nicht ``ablauf.antworte``: die Frage
    "was wird wann injiziert" haengt am Kontextaufbau, und ein Parameter, den
    ``ablauf`` durchreichen muesste, waere im Betrieb ein totes Argument in
    einem Pfad, in dem die Gruppe wartet. Das Argument ``protokoll`` von
    ``kontext.baue`` selbst ist rein additiv und im Betrieb nie gesetzt."""
    vorher = getattr(_mitschrift, "ziel", None)
    _mitschrift.ziel = protokoll
    with _SPERRE:
        if _erster("kontext"):
            original = kontext.baue
            _ORIGINAL["kontext"] = original

            def mitschreiben(*args, **kwargs):
                ziel = getattr(_mitschrift, "ziel", None)
                if ziel is not None:
                    kwargs.setdefault("protokoll", ziel)
                return original(*args, **kwargs)

            kontext.baue = mitschreiben
    try:
        yield protokoll
    finally:
        _mitschrift.ziel = vorher
        with _SPERRE:
            if _letzter("kontext"):
                kontext.baue = _ORIGINAL.pop("kontext")


# ---------------------------------------------------------------------------
# Telegram-Updates bauen
# ---------------------------------------------------------------------------


def bau_update(update_id: int, message_id: int, absender: str, text: str,
               gesendet_am: datetime, chat_id: int = CHAT_ID) -> dict:
    """Ein rohes Telegram-Update, wie ``telegram.lies_nachricht`` es erwartet
    -- dieselbe Form wie ``tests/test_bot.bau_update``."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(gesendet_am.timestamp()),
            "chat": {"id": chat_id, "title": CHAT_TITEL},
            "from": {"first_name": absender},
            "text": text,
        },
    }


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


class Lauf:
    """Fuehrt ein Skript einmal durch. Ein Objekt je Lauf."""

    def __init__(self, conn, tg, klm, e, sim, *, gezogene, seed: int,
                 schritte=skript.SCHRITTE, personen=None, begriffsliste=None,
                 fragenliste=None, stoerung=None, pause: bool = False):
        self.conn = conn
        self.tg = tg
        self.klm = klm          # der Bot-Klient (Infomaniak) -- der Prueflung
        self.e = e
        self.sim = sim          # der Simulationsklient (Claude) -- die Stimmen
        self.gezogene = list(gezogene)
        self.schrittliste = list(schritte)
        self.zufall = random.Random(seed)
        # ``personen`` wird uebergeben, wenn der Lauf keine Gruppe simuliert:
        # ``--set birk`` hat genau eine Stimme, kalibriert auf den echten
        # Chatverlauf (``simulation/birk.py``).
        self.personen = list(personen) if personen else stimmen.personen(self.zufall)
        # Einmal gezogen, nicht je Schritt neu: die Begriffsliste ist die
        # Liste, die die Gruppe an der Wand hat -- sie darf sich zwischen
        # Schritt 1 und Schritt 2 nicht aendern. Bei ``--set birk`` kommt sie
        # aus dem Frontmatter des echten Interviews statt aus den Themen.
        self.begriffsliste = (
            list(begriffsliste) if begriffsliste
            else material.begriffe(self.gezogene, self.zufall)
        )
        self.fragenliste = list(fragenliste) if fragenliste else []
        #: Alle Kontext-Umrisse des Laufs, in der Reihenfolge, in der die
        #: Prompts gebaut wurden (``kontext_protokoll``). Die Zuege schneiden
        #: sich ihren Ausschnitt daraus.
        self.kontexte: list[dict] = []
        self.stoerung = stoerung
        self.pause = pause
        self.ergebnis = Ergebnis(gezogene=self.gezogene, personen=self.personen)
        self._update_id = 0
        self._beitrag_nummer = 0
        self._zeit = datetime.now(timezone.utc) - timedelta(seconds=60)
        self._schritt = self.schrittliste[0].schluessel if self.schrittliste else "-"

    # -- Grundoperationen ---------------------------------------------------

    def _naechste_zeit(self) -> datetime:
        self._zeit += timedelta(seconds=SEKUNDEN_JE_NACHRICHT)
        return self._zeit

    def _verlauf(self) -> list[dict]:
        """Der Chatverlauf, wie eine Teilnehmerin ihn auf dem Handy saehe --
        aus der Datenbank, nicht aus dem eigenen Protokoll: so sieht die
        Stimme genau das, was auch im Chat stuende, inklusive der Zeilen des
        Erkenners und der Verdichtungen."""
        zeilen = repo.letzte_nachrichten(
            self.conn, CHAT_ID, stimmen.VERLAUF_NACHRICHTEN
        )
        return [
            {"absender": ("Bot" if z["ist_bot"] else (z["absender"] or "?")),
             "text": z["text"] or ""}
            for z in zeilen if (z["text"] or "").strip()
        ]

    def _zug(self, marke: str = "", notiz: str = "", art: str = "gespraech") -> Zug:
        zug = Zug(schritt=self._schritt, marke=marke, notiz=notiz, art=art)
        if self.stoerung is not None:
            self.stoerung.neuer_zug()
        self.ergebnis.zuege.append(zug)
        return zug

    def _schliesse_zug(self, zug: Zug, ab_gesendet: int, ab_kontext: int,
                       start: float) -> None:
        """Traegt nach, was erst nach dem Zug feststeht: die Bot-Antworten,
        die Kontext-Umrisse und die Wartezeit.

        Die Latenz wird bis zur **ersten** Bot-Nachricht gemessen, nicht bis
        zum Ende des Zuges: das ist der Moment, in dem in der Gruppe etwas
        aufploppt, und damit die Zahl, die eine Teilnehmerin erlebt. Kam gar
        keine Antwort, bleibt sie ``None`` -- eine Null waere hier die
        Behauptung, es sei schnell gegangen."""
        zug.bot = self.tg.texte(ab_gesendet)
        zug.kontext = self.kontexte[ab_kontext:]
        zug.datenlage = kennzahlen.datenlage(self.conn, CHAT_ID)
        if len(self.tg.gesendet) > ab_gesendet:
            zug.latenz_s = round(
                max(0.0, self.tg.gesendet[ab_gesendet]["zeit"] - start), 2
            )

    def _schicke(self, zug: Zug, texte: list[tuple[str, str, str]]) -> None:
        """Schickt Nachrichten in die Gruppe und faehrt den Zug.

        ``texte`` ist eine Liste ``(absender, profil, text)``. Erst gehen
        **alle** Nachrichten ein, dann laeuft je Nachricht
        ``bot._zug_und_erkenner`` -- genau wie im Betrieb, wo zwei kurz
        hintereinander eintreffende Nachrichten von der Sperre je ``chat_id``
        zu einem einzigen Sammelzug gebuendelt werden (SPEC § 1.3). Der
        zweite Aufruf findet dann nichts Unbeantwortetes mehr und kehrt
        sofort zurueck."""
        vorher = len(self.tg.gesendet)
        ab_kontext = len(self.kontexte)
        start = self.tg.jetzt()
        for absender, profil, text in texte:
            if not text.strip():
                continue
            self._update_id += 1
            self._beitrag_nummer += 1
            zug.beitraege.append(Beitrag(
                kennung=f"S{self._beitrag_nummer}", schritt=self._schritt,
                absender=absender, profil=profil, text=text,
            ))
            # Die message_id kommt aus derselben Folge wie die der
            # Bot-Nachrichten (``TelegramAttrappe.naechste_message_id``) --
            # sonst laege sie unter dem Wasserzeichen des Bots.
            update = bau_update(
                self._update_id, self.tg.naechste_message_id(), absender, text,
                self._naechste_zeit(),
            )
            bot.verarbeite_update(self.conn, self.e, update, datetime.now(timezone.utc), False)
        for _ in zug.beitraege:
            bot._zug_und_erkenner(self.conn, self.tg, self.klm, self.e, CHAT_ID)
        self._schliesse_zug(zug, vorher, ab_kontext, start)

    def _stimmen_zug(self, ziel: str) -> Zug:
        """Ein Zug mit einer -- gelegentlich zwei -- Stimmen. Verweigert das
        Simulationsmodell eine Stimme (stop_reason=refusal, gemessen 05.09.
        beim ersten Zug von set1 -- Ankommen, Papiere, Amt), schweigt diese
        Person in diesem Zug und die naechste spricht; der Lauf scheitert
        daran nicht. Steht als Notiz im Protokoll."""
        zug = self._zug()
        texte = []
        for person in stimmen.waehle_sprecher(self.zufall, self.personen):
            try:
                text = stimmen.sprich(self.sim, person, self._verlauf(), ziel)
            except claude.ClaudeFehler as fehler:
                if "refusal" not in str(fehler):
                    raise
                zug.notiz = (zug.notiz + " | " if zug.notiz else "") + (
                    f"{person.name} verweigert vom Simulationsmodell (refusal)"
                )
                self.ergebnis.verweigerungen += 1
                continue
            if text:
                texte.append((person.name, person.profil, text))
        if not texte:
            # Alle gewaehlten Stimmen verweigert: eine andere Person, mit dem
            # Ziel als knappem Satz, damit der Schritt weitergeht.
            for person in self.personen:
                try:
                    text = stimmen.sprich(self.sim, person, self._verlauf(), ziel)
                except claude.ClaudeFehler:
                    continue
                if text:
                    texte.append((person.name, person.profil, text))
                    break
        self._schicke(zug, texte)
        return zug

    def _ereignis(self, notiz: str, marke: str = "") -> Zug:
        """Ein Zug ohne Stimme: was der Simulator selbst getan hat (Import
        eines Transkripts, Notausgang, Szenen-Auftrag). Steht im Protokoll,
        damit der Bericht keine Luecken hat."""
        vorher = len(self.tg.gesendet)
        zug = self._zug(marke=marke, notiz=notiz)
        self._schliesse_zug(zug, vorher, len(self.kontexte), self.tg.jetzt())
        return zug

    # -- Schrittarten -------------------------------------------------------

    def _fahre_stimmen(self, schritt, merker: dict) -> bool:
        ziel = schritt.ziel_text(merker)
        for _ in range(schritt.max_nachrichten):
            if schritt.fertig(self.conn, CHAT_ID, merker):
                return True
            self._stimmen_zug(ziel)
        return bool(schritt.fertig(self.conn, CHAT_ID, merker))

    def _fahre_zitate(self, schritt, merker: dict) -> bool:
        """Drei Abfragen an den Bot: alle Zitate eines Interviews, eine
        bestimmte Stelle, der ganze Text.

        Reihum, eine je Person -- und wenn nur eine Person da ist
        (``--set birk``), stellt sie alle drei. Die Fragen sind verschieden
        schwer, weil verschieden viel davon ueberhaupt im Prompt steht: die
        Verdichtungen immer, die Volltranskripte nur mit ``/wortlaut``. Der
        Bericht sagt hinterher, was gereicht hat."""
        for nummer, ziel in enumerate(skript.ZITAT_ZIELE):
            person = self.personen[nummer % len(self.personen)]
            zug = self._zug(marke="zitatabfrage")
            text = stimmen.sprich(self.sim, person, self._verlauf(), ziel)
            self._schicke(zug, [(person.name, person.profil, text)] if text else [])
        return True

    def _fahre_befehl(self, schritt, merker: dict) -> bool:
        zug = self._zug()
        self._schicke(zug, [(self.personen[-1].name, self.personen[-1].profil,
                             schritt.befehl)])
        return bool(zug.bot)

    def _fahre_interviews(self, schritt, merker: dict) -> bool:
        """Die Interviews: ansagen, Transkript hereingeben, 'fertig' sagen.

        Eines kommt in **zwei** Textimporten, ein anderes bekommt eine Frage
        an den Bot mittendrin -- beides sind die Faelle, an denen der
        Interviewfluss im Probelauf zerbrochen ist (§ 10.6, N4).

        ``schritt.teile`` setzt das ausser Kraft: bei ``--set birk`` kommt das
        eine Interview in genau drei Importen herein, weil es im Original drei
        Antworten auf drei Fragen waren."""
        anzahl = len(self.gezogene)
        if schritt.teile:
            zwei_teile, frage_dazwischen = -1, -1
        else:
            zwei_teile = self.zufall.randrange(anzahl)
            frage_dazwischen = (zwei_teile + 1) % anzahl

        for index, interview in enumerate(self.gezogene):
            merker = {**merker, "interview_name": interview.name}
            self._ein_interview(
                schritt, merker, index, interview,
                teile=schritt.teile or (2 if index == zwei_teile else 1),
                mit_frage=schritt.mit_frage and index == frage_dazwischen,
            )
        return schritt.fertig(self.conn, CHAT_ID, merker)

    def _ein_interview(self, schritt, merker, index, interview, teile, mit_frage):
        vorher = len(repo.verdichtungen(self.conn, CHAT_ID))

        self._stimmen_zug(
            f"Ihr fangt jetzt ein Interview mit {interview.name} an. Sagt dem Bot, "
            "dass ihr aufnehmen wollt, in einem Satz."
        )
        self._druecke_interview_starten()

        stuecke = interview.teile(teile)
        aufnahme_id = None
        for nummer, stueck in enumerate(stuecke, 1):
            aufnahme_id = self._importiere(stueck, interview.name, an=aufnahme_id)
            self._ereignis(
                f"Transkript von {interview.name} eingegeben "
                f"(Teil {nummer} von {len(stuecke)}, {len(stueck.split())} Woerter)",
                marke="import",
            )
            if mit_frage and nummer < len(stuecke):
                self._stimmen_zug(
                    "Mitten im Interview wollt ihr vom Bot etwas wissen: fragt ihn, "
                    "was nochmal die zweite Frage aus eurer Frageliste war."
                )
        if mit_frage and len(stuecke) == 1:
            self._stimmen_zug(
                "Mitten im Interview wollt ihr vom Bot etwas wissen: fragt ihn, was "
                "nochmal die zweite Frage aus eurer Frageliste war."
            )

        ziel = (
            f"Das Interview mit {interview.name} ist zu Ende. Sagt dem Bot, dass "
            "ihr fertig seid."
        )
        for _ in range(schritt.max_nachrichten):
            if len(repo.verdichtungen(self.conn, CHAT_ID)) > vorher:
                return
            zug = self._stimmen_zug(ziel)
            if len(repo.verdichtungen(self.conn, CHAT_ID)) > vorher:
                # In genau diesem Zug lief der Verdichter -- die Wartezeit
                # gehoert deshalb nicht zu den Gespraechslatenzen, sie ist
                # eine andere Groessenordnung und eine andere Erwartung.
                zug.art = "verdichtung"
                return
        if len(repo.verdichtungen(self.conn, CHAT_ID)) > vorher:
            return
        self._notausgang(aufnahme_id, interview)

    def _druecke_interview_starten(self) -> None:
        """Drueckt den Knopf "Interview starten", wenn der Bot ihn anbietet
        (05.09.2026).

        Bis dahin schaltete der Erkenner den Interviewmodus selbst ein, wenn
        die Gruppe eine Aufnahme ankuendigte. Seit dem Live-Lauf Gruppe 3
        legt er stattdessen nur die Ablauf-Erklaerung mit dem Knopf hin --
        gestartet wird durch eine Handlung. Die simulierten Stimmen sprechen
        nur; diese eine Handlung uebernimmt der Simulator, damit der Rest des
        Laufs (Textimport in den laufenden Kopf) unveraendert bleibt.

        Kein Knopf da, keine Wirkung: dann legt ``_importiere`` den Kopf wie
        bisher selbst an."""
        from interview_theater import knoepfe as knoepfe_modul

        if repo.ist_interviewmodus_an(self.conn, CHAT_ID):
            return
        for angebot in reversed(self.tg.knoepfe):
            for beschriftung, daten in angebot["knoepfe"]:
                if beschriftung != knoepfe_modul._TEXT_AUFNAHME_STARTEN:
                    continue
                knoepfe_modul.behandle(
                    self.conn, self.tg, self.klm, self.e,
                    {
                        "callback_query_id": "sim",
                        "data": daten,
                        "chat_id": CHAT_ID,
                        "message_id": angebot["message_id"],
                    },
                )
                self._ereignis("Knopf \"Interview starten\" gedrueckt", marke="knopf")
                return

    def _importiere(self, text: str, name: str, an: int | None = None) -> int:
        """Gibt Text als Interviewmaterial herein (§ 10.5).

        Laeuft der Interviewmodus, weil der Erkenner "wir machen jetzt ein
        Interview" gehoert hat, bekommt der schon angelegte Kopf den Text --
        sonst legt ``aufnahme.importiere_text`` selbst einen an. Ein zweiter
        Teil (``an``) wird an den Text desselben Kopfes angehaengt: ein
        Interview ist eine Einheit, auch wenn es in zwei Stuecken hereinkommt
        (§ 10.6), und zwei Koepfe waeren zwei Verdichtungen fuer ein
        Gespraech."""
        if an is not None:
            vorhanden = (repo.hole_aufnahme(self.conn, an)["transkript"] or "").strip()
            repo.setze_transkript(
                self.conn, an, f"{vorhanden}\n\n{text}" if vorhanden else text
            )
            return an

        kopf = repo.laufendes_interview(self.conn, CHAT_ID)
        if kopf is None:
            return aufnahme.importiere_text(
                self.conn, self.e, CHAT_ID, self.tg.naechste_message_id(), text, name
            )
        repo.setze_transkript(self.conn, kopf["id"], text)
        repo.setze_aufnahme_name(self.conn, kopf["id"], name)
        return kopf["id"]

    def _notausgang(self, aufnahme_id: int | None, interview) -> None:
        """Schliesst ein Interview ab, das der Bot nicht abgeschlossen hat.

        Gezaehlt und im Protokoll vermerkt: der verpasste Abschluss ist ein
        Befund, kein Betriebsunfall. Ohne diesen Ausgang haette ein Lauf mit
        einem tauben Erkenner ab hier nichts mehr zu messen."""
        self.ergebnis.notausgaenge += 1
        if aufnahme_id is None:
            self._ereignis(f"Notausgang: {interview.name} hat kein Material bekommen.")
            return
        repo.setze_interviewmodus(self.conn, CHAT_ID, None)
        row = repo.hole_aufnahme(self.conn, aufnahme_id)
        if row is not None and row["status"] == "laeuft":
            repo.setze_interview_beendet(self.conn, aufnahme_id)
            aufnahme.schliesse_ab(self.conn, self.tg, self.klm, self.e, aufnahme_id)
        else:
            aufnahme.verarbeite(
                self.conn, self.tg, self.klm, self.e, None, aufnahme_id
            )
        self._ereignis(
            f"Notausgang: der Bot hat das Ende von {interview.name} nicht "
            "mitbekommen, die Simulation hat es selbst abgeschlossen."
        )

    def _fahre_szene(self, schritt, merker: dict) -> bool:
        """Planen lassen, dann die Szene beauftragen.

        Hat der Erkenner den Auftrag schon selbst gehoert (art
        ``szene_schreiben``), steht die Szene bereits -- dann wird kein
        zweiter, teurer Reasoning-Lauf angestossen. Genau das ist die
        Kennzahl, um die es hier geht."""
        ziel = schritt.ziel_text(merker)
        planung = []
        for _ in range(schritt.max_nachrichten):
            if schritt.fertig(self.conn, CHAT_ID, merker):
                return self._merke_szene(schritt, planung)
            zug = self._stimmen_zug(ziel)
            planung.extend(b.text for b in zug.beitraege)

        if schritt.fertig(self.conn, CHAT_ID, merker):
            return self._merke_szene(schritt, planung)

        auftrag = f"Szene {schritt.szene_nummer}: " + " ".join(planung)
        if schritt.form:
            # Die Form steht am Ende des Auftrags, also an der Stelle mit dem
            # meisten Gewicht (SPEC § 6.1) -- und ausdruecklich, nicht nur im
            # Gespraechsverlauf: dass der Bot sie ueberhaupt umsetzt, ist die
            # Frage, die dieser Schritt stellt.
            auftrag += f"\n\nForm: {schritt.form}."
        vorher = len(self.tg.gesendet)
        ab_kontext = len(self.kontexte)
        start = self.tg.jetzt()
        zug = self._zug(
            marke="szene_aufruf", notiz=f"Szenen-Auftrag an den Bot: {auftrag[:200]}",
            art="szene",
        )
        ergebnis = _sofort_szene(self.conn, self.tg, self.klm, self.e, CHAT_ID, auftrag)
        self._schliesse_zug(zug, vorher, ab_kontext, start)
        if ergebnis == "angebot":
            # Der Bot hat das US-Modell angeboten (einmal je Gruppe). Die
            # Stimme antwortet wie eine echte Person -- ja oder nein, in
            # ihren Worten --, der Erkenner setzt es, und der zurueckgestellte
            # Auftrag wird ueber erkenner._starte_szene ausgefuehrt. Falls die
            # Stimme ausweicht, fragt der Simulator NICHT nach: dann bleibt
            # die Szene ungeschrieben und der Bericht zeigt es.
            self._stimmen_zug(
                "Der Bot hat gerade gefragt, ob der Szenentext von einem Modell in den "
                "USA geschrieben werden darf (Kernthema, Figuren, Szenenangaben gehen "
                "dorthin; Aufnahmen und Namen nicht). Antworte darauf, wie du als diese "
                "Person antworten wuerdest -- klar ja oder klar nein, in einem Satz."
            )
            # Wurde die Antwort gehoert, hat _starte_szene die Szene schon
            # angestossen -- in der Simulation synchron, ueber szene.starte,
            # das hier auf _sofort_szene umgebogen ist (einfaedig()).
        return self._merke_szene(schritt, planung)

    def _merke_szene(self, schritt, planung: list[str]) -> bool:
        """Haelt die geschriebene Szene im Ergebnis fest -- Volltext, Form und
        die Planung, die zu ihr gefuehrt hat.

        Der Volltext wird hier gesichert und nicht am Ende aus der Datenbank
        geholt: bei drei Szenen hintereinander liefert ``hole_szenen`` sonst
        drei Texte ohne Zuordnung zu dem Schritt, der sie beauftragt hat --
        und der Richter braucht die Planung neben dem Text, um ueberhaupt
        urteilen zu koennen."""
        szenen = [
            s for s in repo.hole_szenen(self.conn, CHAT_ID)
            if s["nummer"] == schritt.szene_nummer and s["volltext"]
        ]
        if not szenen:
            return False
        szene_zeile = szenen[-1]
        self.ergebnis.szenen.append({
            "schluessel": schritt.schluessel,
            "titel_schritt": schritt.titel,
            "nummer": szene_zeile["nummer"],
            "titel": szene_zeile["titel"] or f"Szene {szene_zeile['nummer']}",
            "form": schritt.form,
            "planung": " ".join(planung),
            "volltext": szene_zeile["volltext"],
            "urteil": {},
        })
        return True

    # -- der Durchlauf ------------------------------------------------------

    # -- Wiederkehr nach einer Nacht (--pause) ------------------------------

    def _lege_pause_ein(self) -> None:
        """Datiert den ganzen Chat um ``PAUSE_STUNDEN`` zurueck, laesst den Bot
        seine Wiederkehr-Zeile schicken und danach eine Stimme schreiben.

        Der Fall zwischen zwei Workshoptagen: die Gruppe kommt am naechsten
        Morgen zurueck, der Bot ist neu gestartet. Gemessen wird zweierlei --
        nennt die Wiederkehr-Zeile die richtige Phase, und faengt der Bot
        wieder von vorn an, die Befehle zu erklaeren?

        Zurueckdatiert wird hier und nicht in ``repo``: eine Funktion, die
        Zeitstempel verschiebt, hat im Betrieb nichts zu suchen -- sie waere
        ein Werkzeug, mit dem sich der Verlauf faelschen liesse. Und
        gerechnet wird in Python statt mit SQLites ``datetime()``: das
        liefert einen String ohne Zeitzone zurueck, und ``bot.begruessung_
        faellig`` vergleicht ihn mit einem zeitzonenbewussten ``jetzt`` --
        das schlaegt mit einem TypeError fehl, mitten im Lauf.

        Angefasst wird ueber ``(chat_id, message_id)``, den Primaerschluessel
        von ``nachricht`` -- die Tabelle hat keine ``id``-Spalte."""
        zeilen = self.conn.execute(
            "SELECT message_id, gesendet_am FROM nachricht WHERE chat_id = ?",
            (CHAT_ID,),
        ).fetchall()
        verschoben = timedelta(hours=PAUSE_STUNDEN)
        for zeile in zeilen:
            frueher = datetime.fromisoformat(zeile["gesendet_am"]) - verschoben
            self.conn.execute(
                "UPDATE nachricht SET gesendet_am = ? "
                "WHERE chat_id = ? AND message_id = ?",
                (frueher.isoformat(), CHAT_ID, zeile["message_id"]),
            )
        self.conn.commit()

        vorher = len(self.tg.gesendet)
        zug = self._zug(
            marke="pause",
            notiz=f"[Simulation] Der Chat wird um {PAUSE_STUNDEN} Stunden "
                  "zurueckdatiert -- die Gruppe kommt am naechsten Morgen wieder.",
        )
        bot.sende_wiederkehr_begruessungen(
            self.conn, self.tg, self.e, datetime.now(timezone.utc)
        )
        self._schliesse_zug(zug, vorher, len(self.kontexte), self.tg.jetzt())
        self.ergebnis.wiederkehr = list(zug.bot)

        self._stimmen_zug(
            "Ihr seid am naechsten Morgen wieder da und wollt weitermachen. "
            "Schreibt eine kurze Nachricht, die anknuepft."
        )

    def _merker(self) -> dict:
        """Die Platzhalter der Schrittziele, frisch aus der Datenbank.

        Frisch, nicht einmal am Anfang: welche Figur in Schritt 8 wieder
        rausfliegen soll, weiss man erst, wenn Schritt 5 welche angelegt
        hat."""
        figuren = [f["name"] for f in repo.figuren(self.conn, CHAT_ID)]
        return {
            "begriffe": ", ".join(self.begriffsliste),
            "fragen": (
                "\n".join(self.fragenliste) if self.fragenliste
                else material.fragenvorschlag(self.begriffsliste)
            ),
            "interviews_soll": len(self.gezogene),
            "interview_name": self.gezogene[0].name if self.gezogene else "",
            "phase_mitte": phasen.bezeichnung(skript.PHASE_MITTE),
            "falscher_name": self.gezogene[0].name if self.gezogene else "Meryem",
            "richtiger_name": ERSATZNAME,
            "figur_weg": figuren[-1] if figuren else "die dritte Figur",
            "figuren_vorher": len(figuren),
        }

    def fahre(self) -> Ergebnis:
        """Faehrt alle Schritte. Ein gescheiterter Schritt haelt den Lauf
        nicht auf -- er wird vermerkt und der naechste beginnt."""
        start = time.monotonic()
        repo.sichere_gruppe(self.conn, CHAT_ID, self.e.bot_name, CHAT_TITEL)
        with einfaedig(), kontext_protokoll(self.kontexte):
            for nummer, schritt in enumerate(self.schrittliste, 1):
                self._schritt = schritt.schluessel
                self.ergebnis.titel[schritt.schluessel] = schritt.titel
                merker = self._merker()
                self.ergebnis.ziele[schritt.schluessel] = schritt.ziel_text(merker)
                print(f"  -> {schritt.titel}", flush=True)
                try:
                    erreicht = self._fahre_einen(schritt, merker)
                except Exception:
                    log.exception("Schritt %s fehlgeschlagen", schritt.schluessel)
                    erreicht = False
                self.ergebnis.schritte[schritt.schluessel] = bool(erreicht)
                print(f"     {'erreicht' if erreicht else 'GESCHEITERT'}", flush=True)
                if self.pause and nummer == PAUSE_NACH_SCHRITT:
                    print("  -> Pause: eine Nacht", flush=True)
                    self._lege_pause_ein()
        self.ergebnis.dauer_s = time.monotonic() - start
        return self.ergebnis

    def _fahre_einen(self, schritt, merker: dict) -> bool:
        if schritt.art == "interviews":
            return self._fahre_interviews(schritt, merker)
        if schritt.art == "szene":
            return self._fahre_szene(schritt, merker)
        if schritt.art == "befehl":
            return self._fahre_befehl(schritt, merker)
        if schritt.art == "zitate":
            return self._fahre_zitate(schritt, merker)
        return self._fahre_stimmen(schritt, merker)


# ---------------------------------------------------------------------------
# Protokoll und Bewertung
# ---------------------------------------------------------------------------


def abschnitt(zuege: list[Zug], schluessel: str) -> str:
    """Der Wortlaut eines Schritts, wie ihn der Richter und der Bericht
    sehen: Stimmen mit Kennung, Bot-Antworten, Ereignisse der Simulation."""
    zeilen = []
    for zug in zuege:
        if zug.schritt != schluessel:
            continue
        if zug.notiz:
            zeilen.append(f"[Simulation] {zug.notiz}")
        for beitrag in zug.beitraege:
            zeilen.append(f"[{beitrag.kennung}] {beitrag.absender}: {beitrag.text}")
        for text in zug.bot:
            zeilen.append(f"Bot: {text}")
    return "\n".join(zeilen)


def protokoll(ergebnis: Ergebnis, schritte) -> str:
    """Das ganze Lauf-Transkript als Markdown -- eine Ueberschrift je
    Schritt, darunter der Wortlaut."""
    teile = []
    for schritt in schritte:
        teile.append(f"## {schritt.titel}")
        teile.append("")
        teile.append(abschnitt(ergebnis.zuege, schritt.schluessel) or "(nichts)")
        teile.append("")
    return "\n".join(teile)


def bewerte(sim, conn, ergebnis: Ergebnis, schritte) -> None:
    """Laesst den Richter alles bewerten, was sich nicht zaehlen laesst:
    jeden Abschnitt, jede geschriebene Szene, das Journal, und bei den fuenf
    schwaechsten Antworten die Frage, ob dem Bot Information gefehlt hat.

    Schreibt alle Urteile in ``ergebnis``."""
    for schritt in schritte:
        text = abschnitt(ergebnis.zuege, schritt.schluessel)
        ziel = ergebnis.ziele.get(schritt.schluessel) or schritt.ziel
        ergebnis.urteile[schritt.schluessel] = richter.bewerte_abschnitt(
            sim, schritt.titel, ziel, text
        )
    for szene in ergebnis.szenen:
        # Die Planung kommt aus dem Abschnitt dieses Schritts, nicht aus
        # ``szene["planung"]`` allein: der Richter soll sehen, was der Bot
        # zurueckgefragt hat, nicht nur, was die Gruppe gesagt hat.
        planung = abschnitt(ergebnis.zuege, szene["schluessel"]) or szene["planung"]
        szene["urteil"] = richter.bewerte_szene(
            sim, planung, szene["volltext"], form=szene.get("form", "")
        )

    ergebnis.journal_urteil = richter.bewerte_journal(
        sim, protokoll(ergebnis, schritte),
        [e["text"] for e in repo.journal(conn, CHAT_ID)],
    )

    ergebnis.schlechteste = bericht.kandidaten_schlechteste(
        ergebnis, schritte,
        kennzahlen.mechanische_treffer(
            ergebnis.zuege, [p.name for p in ergebnis.personen]
        ),
    )
    for kandidat in ergebnis.schlechteste:
        # Nur bei diesen fuenf, nicht bei allen: die Frage "hat dem Bot
        # Information gefehlt" lohnt einen eigenen Aufruf nur dort, wo die
        # Antwort schwach war. Bei einer guten Antwort ist sie beantwortet.
        kandidat["kontext_urteil"] = richter.bewerte_kontext(
            sim, kandidat["text"], kandidat["umriss"],
            kennzahlen.datenlage_text(kandidat["datenlage"]),
        )
