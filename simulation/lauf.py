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
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from interview_theater import aufnahme, bot, phasen, repo, szene

from simulation import material, richter, skript, stimmen
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


@dataclass
class Ergebnis:
    """Alles, was ein Lauf hinterlaesst."""

    zuege: list[Zug] = field(default_factory=list)
    schritte: dict = field(default_factory=dict)       # schluessel -> erreicht?
    ziele: dict = field(default_factory=dict)          # schluessel -> gefuelltes Ziel
    urteile: dict = field(default_factory=dict)        # schluessel -> Richter-Urteil
    szenen_urteil: dict = field(default_factory=dict)
    zahlen: dict = field(default_factory=dict)
    gezogene: list = field(default_factory=list)
    personen: list = field(default_factory=list)
    notausgaenge: int = 0
    szene_text: str = ""
    dauer_s: float = 0.0
    titel: dict = field(default_factory=dict)          # schluessel -> Schritt-Titel


# ---------------------------------------------------------------------------
# Einfaedigkeit
# ---------------------------------------------------------------------------


def _sofort_szene(conn, tg, klm, e, chat_id, auftrag):
    """Ersatz fuer ``szene.starte``: schreibt die Szene **im aufrufenden
    Thread**.

    Die Ankuendigung ("Ich schreibe die Szene aus, das dauert eine Minute")
    faellt weg -- sie ueberbrueckt im Betrieb eine Wartezeit, und hier wartet
    niemand. Fehler werden wie im Betrieb gemeldet, damit der Richter
    dieselbe Zeile sieht wie eine echte Gruppe."""
    auftrag = (auftrag or "").strip()
    if not auftrag:
        return None
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


@contextlib.contextmanager
def einfaedig():
    """Ersetzt die drei Stellen, die im Betrieb einen Thread starten, durch
    synchrone Aufrufe -- und stellt sie danach wieder her.

    Ohne das wuerde der Simulator den Zielzustand eines Schritts pruefen,
    waehrend die Wirkung noch in einem Thread unterwegs ist: der Schritt
    gaelte als gescheitert, obwohl der Bot alles richtig gemacht hat, nur
    eine Zehntelsekunde spaeter."""
    original = (szene.starte, aufnahme.starte_abschluss, aufnahme.starte_auswertung)
    szene.starte = _sofort_szene
    aufnahme.starte_abschluss = _sofort_abschluss
    aufnahme.starte_auswertung = _sofort_auswertung
    try:
        yield
    finally:
        szene.starte, aufnahme.starte_abschluss, aufnahme.starte_auswertung = original


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

    def __init__(self, conn, tg, klm, e, *, gezogene, seed: int,
                 schritte=skript.SCHRITTE):
        self.conn = conn
        self.tg = tg
        self.klm = klm
        self.e = e
        self.gezogene = list(gezogene)
        self.schrittliste = list(schritte)
        self.zufall = random.Random(seed)
        self.personen = stimmen.personen(self.zufall)
        # Einmal gezogen, nicht je Schritt neu: die Begriffsliste ist die
        # Liste, die die Gruppe an der Wand hat -- sie darf sich zwischen
        # Schritt 1 und Schritt 2 nicht aendern.
        self.begriffsliste = material.begriffe(self.gezogene, self.zufall)
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

    def _zug(self, marke: str = "", notiz: str = "") -> Zug:
        zug = Zug(schritt=self._schritt, marke=marke, notiz=notiz)
        self.ergebnis.zuege.append(zug)
        return zug

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
        zug.bot = self.tg.texte(vorher)

    def _stimmen_zug(self, ziel: str) -> Zug:
        """Ein Zug mit einer -- gelegentlich zwei -- Stimmen."""
        zug = self._zug()
        texte = []
        for person in stimmen.waehle_sprecher(self.zufall, self.personen):
            text = stimmen.sprich(self.klm, self.e, person, self._verlauf(), ziel)
            if text:
                texte.append((person.name, person.profil, text))
        self._schicke(zug, texte)
        return zug

    def _ereignis(self, notiz: str, marke: str = "") -> Zug:
        """Ein Zug ohne Stimme: was der Simulator selbst getan hat (Import
        eines Transkripts, Notausgang, Szenen-Auftrag). Steht im Protokoll,
        damit der Bericht keine Luecken hat."""
        vorher = len(self.tg.gesendet)
        zug = self._zug(marke=marke, notiz=notiz)
        zug.bot = self.tg.texte(vorher)
        return zug

    # -- Schrittarten -------------------------------------------------------

    def _fahre_stimmen(self, schritt, merker: dict) -> bool:
        ziel = schritt.ziel_text(merker)
        for _ in range(schritt.max_nachrichten):
            if schritt.fertig(self.conn, CHAT_ID, merker):
                return True
            self._stimmen_zug(ziel)
        return bool(schritt.fertig(self.conn, CHAT_ID, merker))

    def _fahre_befehl(self, schritt, merker: dict) -> bool:
        zug = self._zug()
        self._schicke(zug, [(self.personen[-1].name, self.personen[-1].profil,
                             schritt.befehl)])
        return bool(zug.bot)

    def _fahre_interviews(self, schritt, merker: dict) -> bool:
        """Fuenf Interviews: ansagen, Transkript hereingeben, 'fertig' sagen.

        Eines kommt in **zwei** Textimporten, ein anderes bekommt eine Frage
        an den Bot mittendrin -- beides sind die Faelle, an denen der
        Interviewfluss im Probelauf zerbrochen ist (§ 10.6, N4)."""
        anzahl = len(self.gezogene)
        zwei_teile = self.zufall.randrange(anzahl)
        frage_dazwischen = (zwei_teile + 1) % anzahl

        for index, interview in enumerate(self.gezogene):
            merker = {**merker, "interview_name": interview.name}
            self._ein_interview(
                schritt, merker, index, interview,
                teile=2 if index == zwei_teile else 1,
                mit_frage=(index == frage_dazwischen),
            )
        return schritt.fertig(self.conn, CHAT_ID, merker)

    def _ein_interview(self, schritt, merker, index, interview, teile, mit_frage):
        vorher = len(repo.verdichtungen(self.conn, CHAT_ID))

        self._stimmen_zug(
            f"Ihr fangt jetzt ein Interview mit {interview.name} an. Sagt dem Bot, "
            "dass ihr aufnehmen wollt, in einem Satz."
        )

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
            self._stimmen_zug(ziel)
        if len(repo.verdichtungen(self.conn, CHAT_ID)) > vorher:
            return
        self._notausgang(aufnahme_id, interview)

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
                return True
            zug = self._stimmen_zug(ziel)
            planung.extend(b.text for b in zug.beitraege)

        if schritt.fertig(self.conn, CHAT_ID, merker):
            return True

        auftrag = "Szene 1: " + " ".join(planung)
        vorher = len(self.tg.gesendet)
        zug = self._zug(
            marke="szene_aufruf", notiz=f"Szenen-Auftrag an den Bot: {auftrag[:200]}"
        )
        _sofort_szene(self.conn, self.tg, self.klm, self.e, CHAT_ID, auftrag)
        zug.bot = self.tg.texte(vorher)
        return bool(schritt.fertig(self.conn, CHAT_ID, merker))

    # -- der Durchlauf ------------------------------------------------------

    def _merker(self) -> dict:
        """Die Platzhalter der Schrittziele, frisch aus der Datenbank.

        Frisch, nicht einmal am Anfang: welche Figur in Schritt 8 wieder
        rausfliegen soll, weiss man erst, wenn Schritt 5 welche angelegt
        hat."""
        figuren = [f["name"] for f in repo.figuren(self.conn, CHAT_ID)]
        return {
            "begriffe": ", ".join(self.begriffsliste),
            "fragen": material.fragenvorschlag(self.begriffsliste),
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
        with einfaedig():
            for schritt in self.schrittliste:
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
        self.ergebnis.dauer_s = time.monotonic() - start
        self.ergebnis.szene_text = self._szenentext()
        return self.ergebnis

    def _fahre_einen(self, schritt, merker: dict) -> bool:
        if schritt.art == "interviews":
            return self._fahre_interviews(schritt, merker)
        if schritt.art == "szene":
            return self._fahre_szene(schritt, merker)
        if schritt.art == "befehl":
            return self._fahre_befehl(schritt, merker)
        return self._fahre_stimmen(schritt, merker)

    def _szenentext(self) -> str:
        szenen = [s for s in repo.hole_szenen(self.conn, CHAT_ID) if s["volltext"]]
        return szenen[-1]["volltext"] if szenen else ""


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


def bewerte(klm, e, ergebnis: Ergebnis, schritte) -> None:
    """Laesst den Richter jeden Abschnitt und -- wenn es eine gibt -- die
    Szene bewerten. Schreibt die Urteile in ``ergebnis``."""
    for schritt in schritte:
        text = abschnitt(ergebnis.zuege, schritt.schluessel)
        ziel = ergebnis.ziele.get(schritt.schluessel) or schritt.ziel
        ergebnis.urteile[schritt.schluessel] = richter.bewerte_abschnitt(
            klm, e, schritt.titel, ziel, text
        )
    if ergebnis.szene_text:
        planung = abschnitt(ergebnis.zuege, "szene")
        ergebnis.szenen_urteil = richter.bewerte_szene(
            klm, e, planung, ergebnis.szene_text
        )
