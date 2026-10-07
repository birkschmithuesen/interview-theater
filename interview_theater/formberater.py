"""Der Formberater (Karte t_256ec777, Birk 06./07.10.2026): schlaegt fuer
Phase 4 und den Einstieg in Phase 5 nach, welchen performativen Formen das
nahekommt, was die Gruppe beschreibt -- damit der Bot eine ungewoehnliche
Struktur ("alle Szenen gleichwertig, zufaellige Reihenfolge, keine
Steigerung") einordnen kann, statt sie in einen Spannungsbogen zu
uebersetzen, und damit er einen Gegenpol anbieten kann, an dem die Gruppe
ihre eigene Formentscheidung schaerft.

**Die Wissensquelle** sind die 67 Dateien unter ``interview_theater/formen/``
(Kopie aus dem Wiki, ``scripts/formen_uebernehmen.py``): Frontmatter
(``title``, ``name_en``, ``kurz``, ``aliases``, ``verwandt``) und ein
englischer ``## Bot (EN)``-Block je Form. Alle Bot-Bloecke zusammen sind
~37.000 Zeichen -- mehr als das ganze Kimi-Budget des Koerpers
(``kontext.ZEICHEN_GRENZE_VORGABE``). Deshalb zwei Ebenen: ein Kurzindex
(``kurz`` + Suchbegriffe, eine Zeile je Form) fuer die AUSWAHL, und nur die
Bot-Bloecke der ausgewaehlten Formen im Gespraechs-Prompt
(``kontextblock``, hoechstens ``MAX_IM_KONTEXT``).

**Zwei Ausloeser** (Birk, 06.10.2026 ~23:50, Knopf gestrichen 07.10.2026
~08:05 -- "der Formberater bekommt keinen Knopf", bindend):

A. *Laufend ab Phase 4, ohne obere Grenze* (``pruefe_zug``, aus
   ``ablauf.antworte``): bei JEDEM Zug ein deterministischer Abgleich ohne
   Modellaufruf -- Formnamen und Suchbegriffe (``treffer_formen``) gegen die
   neuen Beitraege der Gruppe; eine genannte Form wird sofort geladen (Zeile
   'stichwort', wirkt schon in DIESEM Zug). NUR in Phase 4 zusaetzlich
   Struktur-Stichwoerter (``treffer_signale``, "random", "gleichwertig",
   "no climax" ...), die bei einem NEUEN Treffer (Delta gegen die Tabelle
   ``formberater``) den teuren Modellaufruf im Hintergrund anstossen (Zeile
   'laufend', wirkt ab dem naechsten Zug). Ab Phase 5 bleibt so der
   deterministische Abgleich als einziges, knopfloses Lazy-Load bestehen --
   kein Modellaufruf mehr, kein eigener Chatbeitrag in jedem Fall.
B. *Einmal beim Eintritt in Phase 5* (``starte_einstieg``, aus
   ``knoepfe.stationen.eintritt_in_phase``): eine Einordnung von Story und
   Framing -- ``passt`` / ``vorschlag`` / ``gegenpol`` -- als klar markierter
   Chatbeitrag, ohne Knopf.

**Modellwahl:** ein Sparring-Schritt, also derselbe Weg wie die
Buehnenkarte -- Claude, wenn ``szene_claude.ist_aktiv`` (Betreiber +
bestehende Einwilligung), sonst Kimi; ``modellwahl.aufruf_schema`` faellt bei
einem Proxy-Fehler fuer diesen einen Aufruf auf Kimi zurueck. **Datenschutz:**
in den Aufruf gehen nur der Kurzindex, die Stueckkarte (Setting, Figuren,
Geschichte, Festlegungen) und die Beitraege der Gruppe SEIT dem Eintritt in
Phase 4 -- Phase 4 ist interview-frei; kein Transkript, keine Verdichtung,
kein Zitat.

Kein SQL hier (``repo``), kein Modellaufruf ausserhalb eines Threads
(Zusage 2: ``starte`` laeuft immer im eigenen Thread unter der Sperre der
Gruppe, auch wenn der Aufrufer selbst -- wie ``ablauf.antworte`` -- es nicht
ist).
"""

from __future__ import annotations

import functools
import logging
import pathlib
import re
import threading
import time
import unicodedata
from typing import NamedTuple

from interview_theater import modellwahl, repo, sprache, szene_claude

log = logging.getLogger(__name__)

ART = "formberater"
VORFALL_FEHLGESCHLAGEN = "formberater_fehlgeschlagen"

AUSLOESER_STICHWORT = "stichwort"
AUSLOESER_LAUFEND = "laufend"
AUSLOESER_EINSTIEG = "einstieg"

#: Ab dieser Phase arbeitet der Formberater (Birk: "NUR ab Phase 4"), ohne
#: obere Grenze -- der deterministische Abgleich (Ausloeser A) laeuft in
#: jeder Phase ab hier.
PHASE_AB = 4
#: Nur in dieser Phase laeuft der teure Modellaufruf laufend (Ausloeser A);
#: danach (ab Phase 5) bleibt vom selben Ausloeser nur der deterministische
#: Abgleich -- kein Modellaufruf mehr, kein Knopf (Birk 07.10.2026 ~08:05).
PHASE_LAUFEND = 4
PHASE_EINSTIEG = 5

#: Wie viele Bot-Bloecke hoechstens im Gespraechs-Prompt stehen (je 300-600
#: Zeichen, also hoechstens ~3.000 Zeichen -- ein Achtel des Kimi-Budgets).
#: Die zuletzt nachgeschlagenen gewinnen: die Richtung der Gruppe kann sich
#: aendern.
MAX_IM_KONTEXT = 5
#: Wie viele Formen ein Aufruf hoechstens nachlaedt (Brief: "die 2-4
#: passendsten").
MAX_JE_AUFRUF = 4
#: Kostenbremse fuer Ausloeser A: hoechstens so viele laufende Aufrufe je
#: Gruppe, und zwischen zweien mindestens so viele Sekunden. Ein Treffer,
#: der in die Sperrzeit faellt, wird NICHT verbraucht -- sagt die Gruppe das
#: Wort spaeter wieder, zaehlt es dann.
MAX_LAUFEND = 8
MIN_ABSTAND_S = 90.0
#: Kuerzerer Abstand, wenn die Gruppe eine NEUE Form beim Namen nennt.
MIN_ABSTAND_NEUE_FORM_S = 20.0

#: Birk 07.10.2026: kommt der Brainstorm bei "Discussion done" als EINE
#: Chatnachricht herein, laeuft der Modellaufruf EINMAL synchron VOR der
#: Antwort (sonst wirkte er erst ab dem naechsten Zug) -- mit hartem
#: Zeitlimit, danach weiter wie bisher im Hintergrund.
AUSLOESER_BRAINSTORM = "brainstorm"
BRAINSTORM_ZEICHEN = 30_000
BRAINSTORM_WARTEN_S = 45.0

#: Birk 07.10.2026: zusaetzlich zum Stichwort-Treffer PFLICHT-Nachschlagen
#: nach so vielen Gruppenbeitraegen seit dem letzten Modellaufruf -- faengt
#: Richtungswechsel ohne neues Stichwort ("random, aber jetzt als Film").
#: Zaehlt ab Phase 4 (auch in 5+, dort als Lazy Load). Im Hintergrund, wirkt
#: ab dem naechsten Zug; MIN_ABSTAND_S gilt, MAX_LAUFEND nicht.
AUSLOESER_TAKT = "takt"
TAKT_ZUEGE = 5

#: Wie viele Beitraege der Gruppe hoechstens in den Aufruf gehen, und wie
#: viele Zeichen davon (das Juengste gewinnt).
BEITRAEGE = 30
BEITRAEGE_ZEICHEN = 6_000

TIMEOUT_S = 90.0

ORDNER = pathlib.Path(__file__).resolve().parent / "formen"


class Form(NamedTuple):
    slug: str
    titel: str
    name_en: str
    kurz: str
    aliases: tuple[str, ...]
    verwandt: tuple[str, ...]
    bot: str

    @property
    def name(self) -> str:
        """Der Name in der Sprache der Gruppe (``title`` ist deutsch)."""
        return sprache.je_sprache({"de": self.titel, "en": self.name_en})

    @property
    def kurz_en(self) -> str:
        """Eine knappe englische Fassung von ``kurz``: der erste Satz des
        ``## Bot (EN)``-Blocks, ohne eine fuehrende Wiederholung des Namens
        (oft mit deutschem Altnamen in Klammern, z. B. "Bauhausbuehne:
        ..."/"Live radio play (Live-Hoerspiel): ...") und ohne Klammern
        (oft Jahreszahlen oder Namen wie "Mühl"). ``kurz`` selbst ist
        Frontmatter-Deutsch (Wissensbasis, auch fuer Dortmund) -- der
        Kurzindex unter einem englischen Profil braucht eine eigene
        Fassung, sonst geht ein deutscher Satz oder Umlaut in den
        Formberater-Modellaufruf (Padua-Invariante "kein Deutsch im
        Prompt", tests/test_pruefe_sprache.py); der Name selbst steht
        schon in der Spalte davor."""
        satz = self.bot.split(". ", 1)[0]
        satz = re.sub(r"\([^)]*\)", "", satz)
        doppelpunkt = satz.find(":")
        if 0 < doppelpunkt <= 60:
            satz = satz[doppelpunkt + 1:]
        satz = " ".join(satz.split()).rstrip(".")
        return f"{satz}."


# ---------------------------------------------------------------------------
# Der Katalog
# ---------------------------------------------------------------------------


def _wert(roh: str) -> str:
    roh = roh.strip()
    if len(roh) >= 2 and roh[0] == roh[-1] and roh[0] in "\"'":
        return roh[1:-1]
    return roh


def _liste(roh: str) -> tuple[str, ...]:
    """``[a, "b c", d]`` -> ``("a", "b c", "d")`` -- die einzige YAML-Form,
    die der Katalog benutzt (keine Abhaengigkeit auf PyYAML)."""
    roh = roh.strip()
    if not (roh.startswith("[") and roh.endswith("]")):
        return (_wert(roh),) if roh else ()
    return tuple(w for w in (_wert(t) for t in roh[1:-1].split(",")) if w)


def lies_form(pfad: pathlib.Path) -> Form:
    """Eine Katalogdatei; ``ValueError``, wenn Frontmatter oder Bot-Block
    fehlen."""
    text = pfad.read_text(encoding="utf-8")
    teile = text.split("---", 2)
    if len(teile) < 3 or teile[0].strip():
        raise ValueError(f"{pfad.name}: keine Frontmatter")
    felder: dict[str, str] = {}
    for zeile in teile[1].splitlines():
        schluessel, trenner, wert = zeile.partition(":")
        if trenner:
            felder[schluessel.strip()] = wert.strip()
    treffer = re.search(r"^## Bot \(EN\)\n(.*?)(?=^## |\Z)", teile[2], re.S | re.M)
    bot = " ".join(treffer.group(1).split()) if treffer else ""
    if not bot or not felder.get("title") or not felder.get("kurz"):
        raise ValueError(f"{pfad.name}: title, kurz oder Bot-Block fehlt")
    titel = _wert(felder["title"])
    return Form(
        slug=pfad.stem,
        titel=titel,
        name_en=_wert(felder.get("name_en", "")) or titel,
        kurz=_wert(felder["kurz"]),
        aliases=_liste(felder.get("aliases", "")),
        verwandt=_liste(felder.get("verwandt", "")),
        bot=bot,
    )


@functools.lru_cache(maxsize=4)
def katalog(ordner: pathlib.Path = ORDNER) -> dict[str, Form]:
    """Alle Formen, nach Slug -- einmal je Prozess gelesen (der Katalog
    aendert sich nur mit einem Deploy)."""
    return {f.slug: f for f in (lies_form(p) for p in sorted(ordner.glob("*.md")))}


#: Name-Ueberschreibung je Slug, NUR fuer den englischen Kurzindex (der
#: Katalog-Name selbst, ``Form.name_en``, bleibt unveraendert -- u. a.
#: ``test_deutsche_nachricht_nennt_den_deutschen_titel`` haengt daran).
#: "Stand-up comedy" zerlegt der Sprachpruefer am Bindestrich in "Stand"
#: (dort ein deutsches UI-Wort, tests/test_pruefe_sprache.py) und "up" --
#: "Standup comedy" ist eine im Katalog selbst gefuehrte Nebenform
#: (``aliases``, stand-up-comedy.md) und meidet den Bindestrich.
_NAME_FUER_KURZINDEX_EN = {"stand-up-comedy": "Standup comedy"}


def kurzindex(ohne: frozenset[str] | set[str] = frozenset()) -> str:
    """Eine Zeile je Form: ``slug | Name | Suchbegriffe | kurz`` -- die
    schlanke Auswahlgrundlage fuer den Modellaufruf (~10.000 Zeichen statt
    ~37.000 fuer alle Bot-Bloecke). Unter Deutsch (Vorgabe, auch Dortmund)
    kommen Name, Suchbegriffe und ``kurz`` direkt aus der Frontmatter --
    unter jeder anderen Profilsprache bleiben nur die englischen Felder
    (``name_en``, ``kurz_en``), die deutschen Aliase (z. B. "Lesebühne")
    fallen aus den Suchbegriffen: kein deutscher Satz im Modellaufruf. Die
    Kennung steht dann mit Unterstrichen statt Strichen (``_slug_fuer``
    normalisiert beides gleich zurueck) -- sonst liest der Sprachpruefer
    einen Bestandteil wie "der" aus "theater-der-unterdrueckten" als
    eigenes Wort (Padua-Invariante "kein Deutsch im Prompt")."""
    deutsch = sprache.code() == sprache.DEUTSCH
    zeilen = []
    for form in katalog().values():
        if form.slug in ohne:
            continue
        if deutsch:
            kennung = form.slug
            name = form.name
            namen = ", ".join(dict.fromkeys((form.name_en, *form.aliases)))
            kurz = form.kurz
        else:
            kennung = form.slug.replace("-", "_")
            name = _NAME_FUER_KURZINDEX_EN.get(form.slug, form.name_en)
            namen = name
            kurz = form.kurz_en
        zeilen.append(f"{kennung} | {name} | {namen} | {kurz}")
    return "\n".join(zeilen)


# ---------------------------------------------------------------------------
# Stufe 1: der deterministische Abgleich (kein Modellaufruf)
# ---------------------------------------------------------------------------


def normalisiere(text: str) -> str:
    """Kleinschreibung, Akzente und Umlaute ohne Zeichen (``ä`` -> ``a``),
    alles ausser Buchstaben und Ziffern zu einem Leerzeichen. "Stand-up"
    und "stand up" sind danach dasselbe."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(z for z in text if not unicodedata.combining(z)).lower()
    text = text.replace("ß", "ss")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


#: Suchbegriffe, die im Alltag etwas anderes heissen und deshalb keinen
#: Formbezug ausloesen ("what's happening", "a musical scene", "Maske").
#: Die Form bleibt ueber ihre uebrigen Namen erreichbar.
MEHRDEUTIG = frozenset({
    "happening", "happenings", "musical", "maske", "to", "stand up",
    "live art", "action art", "text",
})

#: Unter dieser Laenge (normalisiert) kein Suchbegriff -- "TO", "Oper" als
#: Wortteil u. ae.
MINDESTLAENGE = 4


def _begriffe_der_form(form: Form) -> set[str]:
    roh = [form.titel, form.name_en, *form.aliases]
    begriffe = set()
    for wert in roh:
        wert = re.sub(r"\([^)]*\)", " ", wert)
        for teil in re.split(r"\s+/\s+|\s+&\s+", wert):
            norm = normalisiere(teil)
            if len(norm) >= MINDESTLAENGE and norm not in MEHRDEUTIG:
                begriffe.add(norm)
    return begriffe


@functools.lru_cache(maxsize=4)
def _suchbegriffe(ordner: pathlib.Path = ORDNER) -> tuple[tuple[str, str], ...]:
    """``(begriff, slug)``, laengste Begriffe zuerst."""
    paare = {
        (begriff, form.slug)
        for form in katalog(ordner).values()
        for begriff in _begriffe_der_form(form)
    }
    return tuple(sorted(paare, key=lambda p: (-len(p[0]), p[0], p[1])))


def _kommt_vor(begriff: str, heu: str, *, praefix: bool = False) -> bool:
    ende = r"" if praefix else r"s?(?![a-z0-9])"
    return re.search(r"(?<![a-z0-9])" + re.escape(begriff) + ende, heu) is not None


def treffer_formen(text: str) -> dict[str, str]:
    """Welche Formen ``text`` beim Namen nennt: ``{slug: begriff}``, ganze
    Woerter ("durational" trifft, "durationally" nicht), Mehrzahl-s erlaubt."""
    heu = normalisiere(text)
    if not heu:
        return {}
    gefunden: dict[str, str] = {}
    for begriff, slug in _suchbegriffe():
        if slug not in gefunden and _kommt_vor(begriff, heu):
            gefunden[slug] = begriff
    return gefunden


#: Struktur-Stichwoerter: die Gruppe beschreibt eine Form, ohne sie zu
#: nennen (der Live-Fall vom 06.10.2026: "random", "all equal", "no
#: dramaturgy"). Normalisiert, als Wortanfang gesucht ("random" trifft
#: "randomised"). Englisch fuer Padua, Deutsch fuer eine deutschsprachige
#: Gruppe -- beide gelten immer, eine Gruppe mischt.
SIGNALE = (
    # Zufall und Gleichwertigkeit
    "random", "lottery", "by chance", "chance operation", "roll the dice",
    "shuffle", "equal weight", "equally weighted", "all equal", "of equal",
    "same weight", "zufall", "zufallig", "wurfel", "auslosen", "gleichwertig",
    "gleich gewichtet", "gleichrangig",
    # Kein Bogen
    "no climax", "no escalation", "without escalation", "no dramaturgy",
    "no arc", "no plot", "without a plot", "no story", "without a story",
    "non linear", "nonlinear", "no beginning", "no ending", "no end",
    "keine steigerung", "keine eskalation", "kein hohepunkt",
    "keine dramaturgie", "kein bogen", "keine handlung", "ohne handlung",
    "keine geschichte", "ohne geschichte", "kein ende", "nicht linear",
    # Wiederholung, Dauer, Echtzeit
    "loop", "repetition", "repeated", "over and over", "endless",
    "hours long", "for hours", "real time", "schleife", "wiederhol",
    "endlos", "stundenlang", "echtzeit",
    # Partitur, Regeln, Spiel
    "score", "instruction", "rules of the game", "game rules", "partitur",
    "handlungsanweisung", "spielregel",
    # Raum und Publikum
    "passers by", "passer by", "passersby", "public space", "on the street",
    "in the street", "audience participat", "the audience joins",
    "participatory", "one on one", "one to one", "audience of one",
    "walk through", "headphones", "installation", "immersive",
    "passant", "offentlichen raum", "auf der strasse", "mitmach",
    "eins zu eins", "kopfhorer", "immersiv",
    # Material und Haltung
    "documentary", "verbatim", "real people", "lecture", "tableau",
    "living picture", "frozen image", "ritual", "collage", "montage",
    "fragment", "intervention", "provocation", "dokumentar", "standbild",
    "lebendes bild", "provokation",
)


def treffer_signale(text: str) -> list[str]:
    """Welche Struktur-Stichwoerter in ``text`` stehen, in Listenreihenfolge."""
    heu = normalisiere(text)
    if not heu:
        return []
    return [s for s in SIGNALE if _kommt_vor(s, heu, praefix=True)]


# ---------------------------------------------------------------------------
# Was schon nachgeschlagen ist
# ---------------------------------------------------------------------------


def geladene_formen(zeilen: list[dict]) -> list[str]:
    """Die nachgeschlagenen Slugs, ZULETZT nachgeschlagene zuerst, ohne
    Doppelte -- nur solche, die es im Katalog (noch) gibt."""
    bekannt = katalog()
    ergebnis: list[str] = []
    for zeile in reversed(zeilen):
        for slug in zeile["formen"]:
            if slug in bekannt and slug not in ergebnis:
                ergebnis.append(slug)
    return ergebnis


def verbrauchte_signale(zeilen: list[dict]) -> set[str]:
    return {s for zeile in zeilen for s in zeile["signale"]}


def kontextblock(conn, chat_id: int, phase: int | None = None) -> str:
    """Der Block "Performative Formen" im Gespraechs-Prompt: die Bot-Bloecke
    der zuletzt nachgeschlagenen Formen (hoechstens ``MAX_IM_KONTEXT``).
    Leer vor Phase 4 und solange nichts nachgeschlagen ist (datengetrieben,
    wie jeder Block in ``kontext``)."""
    if phase is None:
        from interview_theater import phasen

        phase = phasen.aktuelle(conn, chat_id)
    if phase < PHASE_AB:
        return ""
    slugs = geladene_formen(repo.formberater_zeilen(conn, chat_id))[:MAX_IM_KONTEXT]
    if not slugs:
        return ""
    bekannt = katalog()
    zeilen = [T.KONTEXT_KOPF]
    for slug in slugs:
        zeilen.append(f"- {bekannt[slug].bot}")
    return "\n".join(zeilen)


# ---------------------------------------------------------------------------
# Ausloeser A: der Gespraechszug
# ---------------------------------------------------------------------------

#: Wann zuletzt ein laufender Aufruf je Gruppe gestartet wurde (Monotonuhr).
_zuletzt_gestartet: dict[int, float] = {}


_MODELL_AUSLOESER = {"laufend", "einstieg", "brainstorm", "takt", "knopf"}


def _takt_faellig(conn, chat_id: int) -> bool:
    """Sind seit dem letzten Modellaufruf (oder dem Eintritt in Phase 4)
    mindestens ``TAKT_ZUEGE`` Beitraege der Gruppe eingegangen?"""
    zeilen = repo.formberater_zeilen(conn, chat_id)
    seit = None
    for z in reversed(zeilen):
        if z["ausloeser"] in _MODELL_AUSLOESER:
            seit = z["erstellt_am"]
            break
    if not seit:
        seit = repo.phase_eintritt_am(conn, chat_id, PHASE_LAUFEND)
    if not seit:
        return False
    return len(repo.gruppentexte_seit(conn, chat_id, seit, TAKT_ZUEGE)) >= TAKT_ZUEGE


def ist_brainstorm(texte: list[str]) -> bool:
    """Steckt unter den neuen Beitraegen der bei "Discussion done"
    eingespeiste Brainstorm (``aufnahme._BRAINSTORM_EINSPEISUNG_PRAEFIX``)?"""
    from interview_theater import aufnahme

    praefix = aufnahme._BRAINSTORM_EINSPEISUNG_PRAEFIX.strip()
    return any((t or "").lstrip().startswith(praefix) for t in texte)


def pruefe_zug(conn, tg, klm, e, chat_id: int, texte: list[str],
               phase: int | None = None) -> threading.Thread | None:
    """Stufe 1 fuer einen Gespraechszug: ``texte`` sind die neuen Beitraege
    der Gruppe. Laedt ausdruecklich genannte, noch nicht geladene Formen
    sofort (ohne Modell) und startet in Phase 4 bei einem neuen Treffer den
    Modellaufruf im Hintergrund. Liefert den Thread oder None.

    Wirft nie -- der Gespraechszug darf daran nicht scheitern (der Aufrufer
    faengt trotzdem)."""
    if phase is None:
        from interview_theater import phasen

        phase = phasen.aktuelle(conn, chat_id)
    if phase < PHASE_AB:
        return None
    if klm is not None and ist_brainstorm(texte):
        faden = starte(conn, tg, klm, e, chat_id, AUSLOESER_BRAINSTORM,
                       signale=treffer_signale("\n".join(texte))[:20])
        if faden is not None:
            _zuletzt_gestartet[chat_id] = time.monotonic()
            faden.join(BRAINSTORM_WARTEN_S)
            if faden.is_alive():
                log.warning("Formberater-Brainstorm ueber %ss, Antwort ohne ihn, chat_id=%s",
                            BRAINSTORM_WARTEN_S, chat_id)
            return faden
    if klm is not None and _takt_faellig(conn, chat_id):
        jetzt = time.monotonic()
        vorher = _zuletzt_gestartet.get(chat_id)
        if vorher is None or jetzt - vorher >= MIN_ABSTAND_S:
            text = "\n".join(t for t in texte if t)
            faden = starte(conn, tg, klm, e, chat_id, AUSLOESER_TAKT,
                           signale=[s for s in treffer_signale(text)][:10])
            if faden is not None:
                _zuletzt_gestartet[chat_id] = jetzt
                treffer = treffer_formen(text)
                if treffer:
                    geladen = set(geladene_formen(repo.formberater_zeilen(conn, chat_id)))
                    neu = [slug for slug in treffer if slug not in geladen]
                    if neu:
                        repo.lege_formberater_an(conn, chat_id, AUSLOESER_STICHWORT, phase,
                                                 neu, [treffer[s] for s in neu])
                return faden
    text = "\n".join(t for t in texte if t)
    formen = treffer_formen(text)
    signale = treffer_signale(text) if phase == PHASE_LAUFEND else []
    if not formen and not signale:
        return None
    zeilen = repo.formberater_zeilen(conn, chat_id)
    geladen = set(geladene_formen(zeilen))
    neue_formen = [slug for slug in formen if slug not in geladen]
    verbraucht = verbrauchte_signale(zeilen)
    neue_signale = [s for s in signale if s not in verbraucht]
    if neue_formen:
        repo.lege_formberater_an(
            conn, chat_id, AUSLOESER_STICHWORT, phase, neue_formen,
            [formen[slug] for slug in neue_formen],
        )
    if phase != PHASE_LAUFEND or not (neue_formen or neue_signale) or klm is None:
        return None
    laufende = sum(1 for z in zeilen if z["ausloeser"] == AUSLOESER_LAUFEND)
    if laufende >= MAX_LAUFEND:
        return None
    jetzt = time.monotonic()
    vorher = _zuletzt_gestartet.get(chat_id)
    # Birk 07.10.2026: eine NEU genannte Form ist ein klarer Richtungswechsel
    # -- dann reicht der kurze Abstand (MIN_ABSTAND_NEUE_FORM_S), damit
    # Verwandte und Gegenpol nicht erst nach dem naechsten Takt kommen.
    abstand = MIN_ABSTAND_NEUE_FORM_S if neue_formen else MIN_ABSTAND_S
    if vorher is not None and jetzt - vorher < abstand:
        return None
    faden = starte(conn, tg, klm, e, chat_id, AUSLOESER_LAUFEND,
                   signale=neue_signale + [formen[s] for s in neue_formen])
    if faden is not None:
        _zuletzt_gestartet[chat_id] = jetzt
    return faden


# ---------------------------------------------------------------------------
# Stufe 2: der Modellaufruf
# ---------------------------------------------------------------------------

_EINTRAG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["form", "warum"],
    "properties": {
        "form": {"type": "string"},
        "warum": {"type": "string"},
    },
}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["passt", "vorschlag", "gegenpol"],
    "properties": {
        "passt": {"type": "array", "items": _EINTRAG},
        "vorschlag": {"type": "array", "items": _EINTRAG},
        "gegenpol": {"type": "array", "items": _EINTRAG},
    },
}

#: Wie viele Eintraege je Feld gelten (mehr wird abgeschnitten).
GRENZEN = {"passt": 2, "vorschlag": 2, "gegenpol": 1}

#: Die Systemanweisung des Aufrufs (deutsch; englisch in ``texte.toml``).
#: Eine Modul-Konstante statt einer neuen Prompt-Datei -- wie
#: ``sprechweise.ANWEISUNG`` (eine neue deutsche ``.md`` braucht einen
#: Abschnitt im eingefrorenen Dortmund-Schnappschuss).
ANWEISUNG = (
    "Du bist Dramaturg mit breitem Wissen ueber performative Formen, von den "
    "Klassikern bis zur Performancekunst. Eine Laiengruppe entwickelt ein "
    "eigenes Stueck. Unten stehen (1) ein Katalog performativer Formen -- je "
    "Zeile: Kennung | Titel | Namen | Kurzbeschreibung -- und (2) was die "
    "Gruppe bisher beschrieben und festgelegt hat.\n\n"
    "Ordne ein, welchen Formen das, was die Gruppe beschreibt, am naechsten "
    "kommt. Nimm ihre Beschreibung genau so, wie sie ist: beschreibt sie eine "
    "ungewoehnliche Struktur -- gleichwertige Szenen, Zufall, keine "
    "Steigerung, Aktionen im oeffentlichen Raum --, dann ist das die "
    "Struktur. Uebersetze sie nicht in einen Spannungsbogen.\n\n"
    "Antworte mit drei Listen:\n"
    "- passt: ein bis zwei Formen, denen die Idee der Gruppe am naechsten "
    "kommt;\n"
    "- vorschlag: hoechstens zwei verwandte Formen, die ihre Idee "
    "weitertragen koennten;\n"
    "- gegenpol: hoechstens eine Form mit der gegenteiligen Grundannahme, an "
    "der die Gruppe ihre eigene Entscheidung schaerfen kann.\n"
    "Je Eintrag \"form\": die Kennung GENAU wie in der ersten Spalte des "
    "Katalogs, und \"warum\": ein kurzer Satz, der sich auf das bezieht, was "
    "die Gruppe gesagt hat -- schreib ihr dabei nichts zu, was sie nicht "
    "gesagt hat. Nur Formen aus dem Katalog, keine erfundenen. Formen unter "
    "\"Schon nachgeschlagen\" nimmst du nur, wenn sie weiterhin am besten "
    "passen; ist \"Andere als bisher\" verlangt, nimm sie nicht. Gibt die "
    "Beschreibung keinen Anhaltspunkt fuer eine Form, liefere leere Listen."
)
_KOPF_KATALOG = "Katalog:"
_KOPF_STUECK = "Stueckkarte der Gruppe:"
_KOPF_BEITRAEGE = "Was die Gruppe dazu gesagt hat (aelteste zuerst):"
_KOPF_STICHWORTE = "Neu im Gespraech aufgefallen: {liste}"
_ZEILE_SCHON = "Schon nachgeschlagen: {liste}"


def _beitraege(conn, chat_id: int) -> list[str]:
    """Die Beitraege der Gruppe seit dem Eintritt in Phase 4 (interview-frei).
    Ohne bekannten Eintritt: keine -- dann genuegt die Stueckkarte."""
    seit = repo.phase_eintritt_am(conn, chat_id, PHASE_LAUFEND)
    if not seit:
        return []
    texte = repo.gruppentexte_seit(conn, chat_id, seit, BEITRAEGE)
    behalten: list[str] = []
    summe = 0
    for text in reversed(texte):
        text = " ".join(text.split())
        if not behalten and len(text) > BEITRAEGE_ZEICHEN:
            # Birk 07.10.2026: der bei "Discussion done" eingespeiste
            # Brainstorm ist EINE Nachricht mit 25k+ Zeichen -- frueher fiel
            # sie hier komplett weg. Jetzt: Kopf + Schluss behalten.
            text = _kuerze(text, BRAINSTORM_ZEICHEN)
            behalten.append(text)
            summe += len(text)
            continue
        if summe + len(text) > BEITRAEGE_ZEICHEN:
            break
        behalten.append(text)
        summe += len(text)
    return list(reversed(behalten))


def _kuerze(text: str, grenze: int) -> str:
    if len(text) <= grenze:
        return text
    haelfte = grenze // 2
    return text[:haelfte] + " [...] " + text[-haelfte:]


def baue_nutzertext(conn, chat_id: int, schon: list[str], ausloeser: str,
                    signale: list[str] = ()) -> str:
    from interview_theater import buehnenkarte

    teile = [f"{T._KOPF_KATALOG}\n{kurzindex()}"]
    stueck = buehnenkarte._stueckkarte_text(conn, chat_id)
    if stueck:
        teile.append(f"{T._KOPF_STUECK}\n{stueck}")
    beitraege = _beitraege(conn, chat_id)
    if beitraege:
        teile.append(T._KOPF_BEITRAEGE + "\n" + "\n".join(f"- {b}" for b in beitraege))
    if signale:
        teile.append(T._KOPF_STICHWORTE.format(liste=", ".join(signale)))
    if schon:
        teile.append(T._ZEILE_SCHON.format(liste=", ".join(schon)))
    return "\n\n".join(teile)


def _slug_fuer(wert: str) -> str | None:
    """Kennung oder (zur Not) Titel/englischer Name -> Slug; None fuer alles,
    was nicht im Katalog steht (keine erfundenen Formen)."""
    bekannt = katalog()
    roh = (wert or "").strip()
    if roh in bekannt:
        return roh
    norm = normalisiere(roh)
    for form in bekannt.values():
        if norm in (normalisiere(form.slug), normalisiere(form.titel),
                    normalisiere(form.name_en)):
            return form.slug
    return None


def zerlege(antwort) -> dict[str, list[dict]]:
    """Die Modellantwort, geprueft: nur Formen aus dem Katalog, keine Form
    zweimal, je Feld hoechstens ``GRENZEN``. Liefert
    ``{"passt": [{"form": slug, "warum": satz}], ...}``."""
    ergebnis: dict[str, list[dict]] = {feld: [] for feld in GRENZEN}
    if not isinstance(antwort, dict):
        return ergebnis
    gesehen: set[str] = set()
    for feld, grenze in GRENZEN.items():
        eintraege = antwort.get(feld) or []
        if isinstance(eintraege, dict):
            eintraege = [eintraege]
        for eintrag in eintraege if isinstance(eintraege, list) else []:
            if not isinstance(eintrag, dict):
                continue
            slug = _slug_fuer(str(eintrag.get("form") or ""))
            if slug is None or slug in gesehen or len(ergebnis[feld]) >= grenze:
                continue
            gesehen.add(slug)
            warum = " ".join(str(eintrag.get("warum") or "").split())
            ergebnis[feld].append({"form": slug, "warum": warum})
    return ergebnis


def formen_aus(ergebnis: dict[str, list[dict]]) -> list[str]:
    """Die Slugs in der Reihenfolge passt -> vorschlag -> gegenpol,
    hoechstens ``MAX_JE_AUFRUF``."""
    slugs = [e["form"] for feld in GRENZEN for e in ergebnis.get(feld, [])]
    return list(dict.fromkeys(slugs))[:MAX_JE_AUFRUF]


def berate(conn, klm, e, chat_id: int, ausloeser: str,
           signale: list[str] = ()) -> dict[str, list[dict]]:
    """Der Modellaufruf (Schema-JSON), geprueft. Wirft bei einem Fehler."""
    schon = geladene_formen(repo.formberater_zeilen(conn, chat_id))
    nutzer = baue_nutzertext(conn, chat_id, schon, ausloeser, list(signale))
    antwort = modellwahl.aufruf_schema(
        conn, klm, e, chat_id, T.ANWEISUNG, nutzer, SCHEMA, ART,
        ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
        timeout=TIMEOUT_S,
    )
    return zerlege(antwort)


# ---------------------------------------------------------------------------
# Ausloeser B und C: die Nachricht im Chat
# ---------------------------------------------------------------------------

_TEXT_KOPF = "🎭 Eure Form -- ein Angebot zum Einordnen, keine Vorgabe:"
_ZEILE_PASST = "• Am naechsten an dem, was ihr macht: {name} -- {warum}"
_ZEILE_VORSCHLAG = "• Koennte eure Idee weitertragen: {name} -- {warum}"
_ZEILE_GEGENPOL = "• Gegenpol, zum Schaerfen eurer Entscheidung: {name} -- {warum}"
_TEXT_FUSS = (
    "Nehmt davon, was euch hilft -- an eurem Stueck aendert sich nichts, "
    "solange ihr nichts sagt."
)

_ZEILEN = {"passt": "_ZEILE_PASST", "vorschlag": "_ZEILE_VORSCHLAG",
           "gegenpol": "_ZEILE_GEGENPOL"}


def nachricht(ergebnis: dict[str, list[dict]]) -> str | None:
    """Der Chattext zu einem Ergebnis, oder None, wenn nichts zu sagen ist."""
    bekannt = katalog()
    zeilen = []
    for feld, schluessel in _ZEILEN.items():
        for eintrag in ergebnis.get(feld, []):
            form = bekannt.get(eintrag["form"])
            if form is None:
                continue
            warum = eintrag["warum"] or form.kurz
            zeilen.append(getattr(T, schluessel).format(name=form.name, warum=warum))
    if not zeilen:
        return None
    return "\n".join([T._TEXT_KOPF, "", *zeilen, "", T._TEXT_FUSS])


def _sende(conn, tg, e, chat_id: int, text: str) -> None:
    """Birk 07.10.2026 ~08:05: kein Knopf -- reiner Chatbeitrag."""
    message_id = tg.sende(chat_id, text)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)


# ---------------------------------------------------------------------------
# Der Thread
# ---------------------------------------------------------------------------

_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    """Eine Sperre je Gruppe -- Get-or-create unter einem Meta-Lock (wie
    ``sprechweise._sperre_fuer``)."""
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def _modellname(e, conn, chat_id: int) -> str:
    return "claude" if szene_claude.ist_aktiv(e, conn, chat_id) else "infomaniak"


def _lauf(conn, tg, klm, e, chat_id: int, ausloeser: str, signale: list[str],
          sperre: threading.Lock) -> None:
    from interview_theater import phasen

    try:
        if ausloeser == AUSLOESER_EINSTIEG and _einstieg_gelaufen(conn, chat_id):
            return
        phase = phasen.aktuelle(conn, chat_id)
        modell = _modellname(e, conn, chat_id)
        try:
            ergebnis = berate(conn, klm, e, chat_id, ausloeser, signale)
        except Exception:
            log.exception("Formberater fehlgeschlagen, chat_id=%s", chat_id)
            _melde_fehler(conn, tg, e, chat_id)
            # Die Stichwoerter gelten als verbraucht (sonst loeste dasselbe
            # Wort bei einem Proxy-Ausfall jeden Zug einen neuen Aufruf aus),
            # der Einstieg als gelaufen (er kommt einmal, nicht bei jedem
            # Wiedereintritt nach einem Fehler).
            repo.lege_formberater_an(conn, chat_id, ausloeser, phase, [],
                                     signale, None, modell)
            return
        formen = formen_aus(ergebnis)
        repo.lege_formberater_an(conn, chat_id, ausloeser, phase, formen,
                                 signale, ergebnis, modell)
        if ausloeser == AUSLOESER_EINSTIEG:
            text = nachricht(ergebnis)
            if text:
                _sende(conn, tg, e, chat_id, text)
    except Exception:
        log.exception("Formberater-Lauf gescheitert, chat_id=%s", chat_id)
    finally:
        sperre.release()


def _melde_fehler(conn, tg, e, chat_id: int) -> None:
    try:
        repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None),
                           VORFALL_FEHLGESCHLAGEN, "Formberater fehlgeschlagen")
    except Exception:
        log.exception("Vorfall nicht schreibbar, chat_id=%s", chat_id)
    from interview_theater import kosten

    try:
        kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)
    except Exception:
        log.exception("Pausenmeldung gescheitert, chat_id=%s", chat_id)


def starte(conn, tg, klm, e, chat_id: int, ausloeser: str,
           signale: list[str] = ()) -> threading.Thread | None:
    """Eigener Thread unter der Sperre dieser Gruppe; ``None``, wenn schon
    ein Lauf geht oder es kein Sprachmodell gibt."""
    if klm is None:
        log.error("Formberater ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        return None
    try:
        faden = threading.Thread(
            target=_lauf,
            args=(conn, tg, klm, e, chat_id, ausloeser, list(signale), sperre),
            daemon=True,
        )
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


def _einstieg_gelaufen(conn, chat_id: int) -> bool:
    return any(z["ausloeser"] == AUSLOESER_EINSTIEG
               for z in repo.formberater_zeilen(conn, chat_id))


def starte_einstieg(conn, tg, klm, e, chat_id: int) -> threading.Thread | None:
    """Ausloeser B: EINMAL je Gruppe beim Eintritt in Phase 5."""
    if _einstieg_gelaufen(conn, chat_id):
        return None
    return starte(conn, tg, klm, e, chat_id, AUSLOESER_EINSTIEG)


#: Kopf des Kontextblocks (``kontextblock``). Die Bot-Bloecke darunter sind
#: englisch, auch fuer eine deutschsprachige Gruppe -- sie sind Wissen fuer
#: das Modell, kein Text, den die Gruppe liest.
KONTEXT_KOPF = (
    "Performative Formen (Nachschlagewerk, fuer diese Gruppe nachgeschlagen "
    "-- dein Fachwissen, NICHT Aussagen der Gruppe: nenn eine Form nur, wenn "
    "es der Gruppe beim Einordnen hilft, biete sie an, statt sie "
    "vorzuschreiben, und schreib der Gruppe nie zu, was hier steht):"
)


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
