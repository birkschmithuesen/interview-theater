"""Die mechanischen Kennzahlen eines Laufs -- aus Datenbank und Attrappe.

Kein Modellaufruf. Alles hier ist nachzaehlbar, und genau darin liegt der
Wert: die Noten des Richters (``richter.py``) schwanken zwischen zwei Laeufen,
diese Zahlen nicht. Wer eine Prompt-Aenderung bewerten will, schaut zuerst
hierhin.

Gemessen wird gegen die Sollwerte aus dem Auftrag:

===============================  ====================================
``phase_erreicht``               Soll: die Szenen-Phase
``arbeitsstand_vollstaendig``    je Feld 0/1
``zustimmungen_gespeichert``     Anteil der Zustimmungen, nach denen eine
                                 Notiert-Zeile kam (Soll 1,0)
``verdichtungen``                Soll: eine je Interview
``zitate_geprueft``              Anteil der Kernthemen mit geprueftem Zitat
``zitate_soll``                  Anteil der Soll-Zitate, die als Belegzitat
                                 auftauchen
``echo``                         Bot-Antworten, die eine Stimm-Nachricht
                                 zurueckspiegeln (Soll 0)
``rueckfragen_vor_szene``        Soll <= 1
``behauptete_schreibvorgaenge``  Soll 0
``namensanrede``                 Soll 0
``laenge_bot``                   Median Zeichen je Bot-Antwort, Soll < 700
===============================  ====================================
"""

from __future__ import annotations

import statistics
import unicodedata
from dataclasses import dataclass, field

from interview_theater import ablauf, erkenner, phasen, repo, zitat

from simulation import skript

#: Sollwerte, an denen der Bericht die Zahlen misst. An einer Stelle, damit
#: Bericht und Test dieselbe Zahl meinen.
SOLL_LAENGE_BOT = 700
SOLL_RUECKFRAGEN_VOR_SZENE = 1


def _notiert_praefix() -> str:
    """Die erste Zeile der Aenderungsmeldung des Erkenners -- **erzeugt**,
    nicht abgeschrieben.

    Damit erkennt diese Datei die Notiert-Zeile auch dann noch, wenn jemand
    ``erkenner.baue_meldung`` umformuliert; ein hart eingetragenes 'Notiert:'
    wuerde nach so einer Aenderung stillschweigend null Zustimmungen
    finden."""
    beispiel = erkenner.baue_meldung([{"art": "kernthema_setzen", "wert": "Probe"}])
    return beispiel.splitlines()[0] if beispiel else "Notiert:"


NOTIERT = _notiert_praefix()

#: Woerter, mit denen der Bot einen Schreibvorgang behauptet. Ohne Umlaute
#: verglichen (``_falte``), weil der Bot mal 'geloescht' und mal 'gelöscht'
#: schreibt.
SCHREIB_BEHAUPTUNGEN = ("notiert", "korrigiert", "geloescht", "im arbeitsstand")

#: Wie eine Namensanrede aussieht, die der Bot nicht fuehren soll.
_ANREDE_MUSTER = ("{name}:", "{name} hat recht")

_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _falte(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower().translate(_UMSCHRIFT)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Das Protokoll eines Laufs
# ---------------------------------------------------------------------------


@dataclass
class Beitrag:
    """Eine Nachricht einer simulierten Teilnehmerin."""

    kennung: str      # "S7" -- die Kennung, unter der der Richter sie markiert
    schritt: str
    absender: str
    profil: str
    text: str


@dataclass
class Zug:
    """Ein Gespraechszug: ein oder zwei Stimm-Nachrichten und alles, was der
    Bot daraufhin geschickt hat.

    ``marke`` haelt Sonderereignisse fest, die keine Stimme sind -- der
    Textimport eines Interviews (``import``) und der Moment, in dem die Szene
    beauftragt wurde (``szene_aufruf``). Die Kennzahl
    ``rueckfragen_vor_szene`` haengt an der zweiten."""

    schritt: str
    beitraege: list[Beitrag] = field(default_factory=list)
    bot: list[str] = field(default_factory=list)
    marke: str = ""
    notiz: str = ""

    @property
    def hat_notiert(self) -> bool:
        return any(t.strip().startswith(NOTIERT) for t in self.bot)


# ---------------------------------------------------------------------------
# Zahlen aus dem Protokoll
# ---------------------------------------------------------------------------


def bot_antworten(zuege: list[Zug]) -> list[str]:
    return [t for z in zuege for t in z.bot]


def laenge_bot(zuege: list[Zug]) -> int:
    """Median der Zeichenzahl je Bot-Antwort. Median, nicht Mittelwert: eine
    einzige Szenenvorschau von 2.000 Zeichen wuerde den Mittelwert reissen
    und ueber die uebrigen dreissig Antworten nichts mehr aussagen."""
    laengen = [len(t) for t in bot_antworten(zuege)]
    return int(statistics.median(laengen)) if laengen else 0


def echos(zuege: list[Zug]) -> list[str]:
    """Bot-Antworten, die eine Stimm-Nachricht desselben Zuges
    zurueckspiegeln.

    Geprueft mit **derselben Funktion, die im Betrieb entscheidet**
    (``ablauf.ist_echo``, 80 % woertlich) -- etwas Eigenes hier waere eine
    zweite Wahrheit ueber dieselbe Frage, und die Zahl im Bericht liesse sich
    nicht mehr mit dem Vorfall ``echo_verworfen`` vergleichen."""
    treffer = []
    for zug in zuege:
        ausloeser = [{"ist_bot": 0, "text": b.text} for b in zug.beitraege]
        treffer.extend(t for t in zug.bot if ablauf.ist_echo(t, ausloeser))
    return treffer


def namensanreden(zuege: list[Zug], namen: list[str]) -> list[str]:
    """Bot-Antworten, die mit '<Name>:' oder '<Name> hat recht' beginnen.

    Der gemessene Live-Fall vom 04.09.2026: der Bot schickte eine Nachricht
    mit 'Birk:' davor. Anders als bei ``ist_echo`` zaehlt hier nicht, ob
    danach etwas Eigenes kommt -- die Gruppe soll gar nicht erst angesprochen
    werden wie eine Figur im Stueck."""
    muster = [_falte(form.format(name=name)) for name in namen for form in _ANREDE_MUSTER]
    return [
        t for t in bot_antworten(zuege)
        if any(_falte(t).startswith(m) for m in muster)
    ]


def behauptete_schreibvorgaenge(zuege: list[Zug]) -> list[str]:
    """Bot-Antworten, die einen Schreibvorgang behaupten, ohne dass im selben
    Zug eine Notiert-Zeile des Erkenners kam.

    Der Fehler dahinter ist der teuerste, den der Bot machen kann: die Gruppe
    glaubt, etwas sei festgehalten, arbeitet weiter, und am Abend ist die
    Gruppenseite leer. Die Notiert-Zeile selbst zaehlt nicht mit -- sie ist
    der Beleg, nicht die Behauptung."""
    treffer = []
    for zug in zuege:
        if zug.hat_notiert:
            continue
        for text in zug.bot:
            if text.strip().startswith(NOTIERT):
                continue
            gefaltet = _falte(text)
            if any(wort in gefaltet for wort in SCHREIB_BEHAUPTUNGEN):
                treffer.append(text)
    return treffer


def rueckfragen_vor_szene(zuege: list[Zug]) -> list[str]:
    """Bot-Nachrichten mit '?' zwischen dem Beginn der Szenenplanung und dem
    Szenen-Auftrag (Soll <= 1).

    Eine Rueckfrage ist in Ordnung -- 'wo spielt sie?' ist eine gute Frage.
    Drei sind ein Verhoer: die Gruppe hat gesagt, was sie will, und wartet
    darauf, dass etwas entsteht."""
    treffer = []
    for zug in zuege:
        if zug.schritt != "szene":
            continue
        if zug.marke == "szene_aufruf":
            break
        treffer.extend(t for t in zug.bot if "?" in t)
    return treffer


def zustimmungen(zuege: list[Zug], markiert: set[str]) -> tuple[int, int]:
    """``(gespeichert, insgesamt)`` fuer die vom Richter als Zustimmung
    markierten Stimm-Nachrichten.

    'Gespeichert' heisst: im selben Zug kam eine Notiert-Zeile. Das ist die
    Kennzahl aus N7 in ihrer strengsten Form -- im Probelauf stimmte die
    Gruppe dreimal zu, und dreimal blieb der Arbeitsstand leer."""
    gesamt = gespeichert = 0
    for zug in zuege:
        for beitrag in zug.beitraege:
            if beitrag.kennung not in markiert:
                continue
            gesamt += 1
            if zug.hat_notiert:
                gespeichert += 1
    return gespeichert, gesamt


# ---------------------------------------------------------------------------
# Zahlen aus der Datenbank
# ---------------------------------------------------------------------------


def arbeitsstand_vollstaendig(conn, chat_id: int) -> dict[str, int]:
    """Je Feld 0/1: Begriffe, Fragen, Kernthema, drei Figuren, die Felder der
    Phase 5.

    Die letzten kommen aus ``skript.felder_fuer_phase`` und damit aus dem
    Schema -- nach einem Umbau der Phase 5 misst diese Funktion die neuen
    Felder, ohne dass jemand sie nachzieht."""
    ergebnis = {
        "begriffe": int(skript._stand_gesetzt(conn, chat_id, "begriffe")),
        "fragen": int(skript._stand_gesetzt(conn, chat_id, "fragen")),
        "kernthema": int(skript._stand_gesetzt(conn, chat_id, "kernthema")),
        f"figuren_{skript.FIGUREN_SOLL}": int(
            len(repo.figuren(conn, chat_id)) >= skript.FIGUREN_SOLL
        ),
    }
    felder = skript.felder_fuer_phase(conn, skript.PHASE_MITTE)
    if felder:
        for feld in felder:
            ergebnis[feld] = int(skript._stand_gesetzt(conn, chat_id, feld))
    else:
        ergebnis[f"phase_{skript.PHASE_MITTE}_erreicht"] = int(
            phasen.aktuelle(conn, chat_id) >= skript.PHASE_MITTE
        )
    return ergebnis


def zitatlage(conn, chat_id: int, gezogene) -> dict:
    """Verdichtungen, geprueftes Belegzitat, gefundene Soll-Zitate.

    ``zitate_soll`` ist die einzige Zahl im Bericht, die etwas ueber die
    **inhaltliche** Qualitaet der Verdichtung sagt, ohne ein Modell zu
    fragen: die drei Saetze je Interviewdatei sind mit der Hand ausgesucht,
    und ein Verdichter, der keinen davon findet, hat am Material vorbei
    gelesen. Verglichen wird als Teilstring nach ``zitat.normalisiere`` --
    dieselbe Normalisierung, mit der im Betrieb entschieden wird, ob ein
    Zitat stehen bleibt."""
    verdichtungen = repo.verdichtungen(conn, chat_id)
    themen = [t for v in verdichtungen for t in repo.themen_zu(conn, v["id"])]
    geprueft = [t for t in themen if t["zitat_geprueft"] == 1]

    belege = " ".join(
        zitat.normalisiere(t["beleg_zitat"] or "") for t in themen
    )
    soll = [s for interview in gezogene for s in interview.zitate_soll]
    gefunden = [s for s in soll if zitat.normalisiere(s) in belege]

    return {
        "verdichtungen": len(verdichtungen),
        "themen": len(themen),
        "zitate_geprueft": len(geprueft),
        "zitate_soll": len(soll),
        "zitate_soll_gefunden": len(gefunden),
        "zitate_soll_vermisst": [s for s in soll if s not in gefunden],
    }


def kosten(conn, e, preise: dict) -> dict:
    """Kosten in CHF, getrennt nach Bot und Simulation.

    Die Tabelle ``aufruf`` haelt kein Modell fest, nur die ``art`` -- die
    Zuordnung art -> Modell ist deshalb dieselbe wie im Betrieb
    (``scripts.pruefe_prompts.modell_fuer``): Gespraech, Verdichter und Szene
    laufen mit dem Gespraechsmodell, Erkenner und Journal mit gemma. Die
    Stimmen zaehlen zur Simulation, nicht zum Bot: sie kosten Geld, sagen
    aber nichts ueber den Bot aus."""
    modelle = {
        "gespraech": e.llm_modell,
        "verdichter": e.llm_modell,
        "szene": e.llm_modell,
        "erkenner": e.erkenner_modell,
        "journal": e.erkenner_modell,
        "stimme": e.llm_modell,
        "richter": e.erkenner_modell,
    }
    simulation_arten = {"stimme", "richter"}

    summe = {"bot": 0.0, "simulation": 0.0}
    token = {"ein": 0, "aus": 0}
    aufrufe = 0
    for zeile in conn.execute(
        "SELECT art, sum(tatsaechliche_token) AS ein, sum(antwort_token) AS aus, "
        "count(*) AS n FROM aufruf GROUP BY art"
    ):
        art = zeile["art"]
        ein, aus = zeile["ein"] or 0, zeile["aus"] or 0
        token["ein"] += ein
        token["aus"] += aus
        aufrufe += zeile["n"]
        preis = preise.get(modelle.get(art, ""))
        if preis is None:
            continue
        chf = (ein * preis[0] + aus * preis[1]) / 1_000_000
        summe["simulation" if art in simulation_arten else "bot"] += chf
    return {
        "chf_bot": round(summe["bot"], 4),
        "chf_simulation": round(summe["simulation"], 4),
        "chf_gesamt": round(summe["bot"] + summe["simulation"], 4),
        "token_ein": token["ein"],
        "token_aus": token["aus"],
        "aufrufe": aufrufe,
    }


def sammle(conn, chat_id: int, zuege: list[Zug], gezogene, namen, markiert,
           schritte, e, preise, dauer_s: float, notausgaenge: int = 0) -> dict:
    """Alle mechanischen Kennzahlen eines Laufs in einem Dict -- die Form, in
    der sie in den Bericht und nach ``verlauf.jsonl`` gehen."""
    gespeichert, zustimmung_gesamt = zustimmungen(zuege, markiert)
    zahlen = {
        "interviews_soll": len(gezogene),
        "notausgaenge": notausgaenge,
        "phase_erreicht": phasen.aktuelle(conn, chat_id),
        "phase_erreicht_name": phasen.bezeichnung(phasen.aktuelle(conn, chat_id)),
        "phase_soll": skript.phase_szenen(),
        "arbeitsstand_vollstaendig": arbeitsstand_vollstaendig(conn, chat_id),
        "zustimmungen": zustimmung_gesamt,
        "zustimmungen_gespeichert": gespeichert,
        "echo": len(echos(zuege)),
        "rueckfragen_vor_szene": len(rueckfragen_vor_szene(zuege)),
        "behauptete_schreibvorgaenge": len(behauptete_schreibvorgaenge(zuege)),
        "namensanrede": len(namensanreden(zuege, namen)),
        "laenge_bot": laenge_bot(zuege),
        "bot_antworten": len(bot_antworten(zuege)),
        "stimm_nachrichten": sum(len(z.beitraege) for z in zuege),
        "schritte_gescheitert": [s for s, ok in schritte.items() if not ok],
        "dauer_s": round(dauer_s, 1),
    }
    zahlen.update(zitatlage(conn, chat_id, gezogene))
    zahlen.update(kosten(conn, e, preise))
    return zahlen
