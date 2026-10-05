"""Jeder Modellaufruf, der in Padua live vorkommt -- als Volltext-Dump.

Aufruf (Karte t_1dcf3864, 05.10.2026)::

    python3.11 -m scripts.erzeuge_prompts_padua_voll \\
        docs/prompt-audit/2026-10-05-padua-voll

Das Skript setzt ``IT_WORKSHOP=padua-2026`` selbst (eine andere Variable weist
es ab) und baut sich eine Wegwerf-Datenbank mit sieben erfundenen Gruppen,
eine je Phase (``scripts.fixture_padua_voll``). ``IT_DB`` zeigt auf diese
Datei, weil ``anweisungen.system`` den Regie-Zettel (``zusatz.md``) daneben
sucht -- ein Zettel aus dem Betriebsverzeichnis stuende sonst im Dump. Die echte
Betriebsdatenbank wird nie geoeffnet.

**Aufgezeichnet wird an der Transportgrenze** (``scripts.mitschnitt``), nicht
nachgebaut: was im Dump steht, ist per Konstruktion das, was der Bot
verschickt haette. Wo das Fahren des echten Pfades unverhaeltnismaessig waere,
steht ``weg="gebaut"`` im Inventar -- mit Grund, und die Spalte ``quelle`` in
``uebersicht.tsv`` macht den Unterschied sichtbar.

Je Dump eine Datei mit Kopfzeile (art, phase, weg, modell, quelle),
``=== SYSTEM ===`` und ``=== NUTZER ===`` -- dasselbe Format wie
``scripts/erzeuge_prompts.py``, plus die Kopfzeile. Dazu ``uebersicht.tsv``
mit den Groessen und, fuer die Gespraechs-Dumps, dem Token-Anteil je
Blockgruppe (Birk, 05.10.2026 00:40).

**Treiber-Signaturen sind gegen den echten Code verifiziert, nicht
angenommen** (siehe ``docs/.../task-6-report.md`` fuer die Grep-Belege):
``erkenner.erkenne``/``erkenne_in_aufnahme`` und ``journal.extrahiere``
nehmen ``klm`` als ERSTES Argument (``(klm, conn, e, chat_id, ...)``), nicht
``conn`` zuerst; ``verdichter.verdichte`` hat nur vier Parameter
(``klm, conn, e, aufnahme_id``) -- es holt Transkript und ``chat_id`` selbst
aus der Aufnahme, es gibt keinen ``text``-Parameter."""

from __future__ import annotations

import contextlib
import os
import tempfile
import time
from pathlib import Path

from interview_theater import (
    anweisungen, db, einstellungen, kontext, repo, workshop,
)
from scripts import fixture_padua_voll as fixture
from scripts import mitschnitt as ms
from scripts import prompt_inventar as inv

#: Die vier Gruppen, in denen Birk den Nutzertext bemessen sehen will
#: (00:40: "token share per block ... (system/status/history/summary)").
#: Die Blocknamen sind die aus ``kontext._REIHENFOLGE`` -- gemessen:
#: verdichtungen, transkripte, kernpaket, arbeitsstand, festlegungen,
#: diskussion, begriffe_detail, phasenhinweis, figurenhinweis, szene, journal,
#: fenster, ausloeser, erstkontakt.
BLOCKGRUPPEN = {
    "tok_status": ("arbeitsstand", "festlegungen", "kernpaket", "szene",
                   "begriffe_detail", "phasenhinweis", "figurenhinweis"),
    "tok_verlauf": ("fenster", "ausloeser", "erstkontakt"),
    "tok_zusammenfassung": ("verdichtungen", "transkripte", "journal",
                            "diskussion"),
}

TSV_SPALTEN = (
    "pfad", "art", "phase", "weg", "modell", "quelle",
    "system_zeichen", "nutzer_zeichen", "token_gesamt",
    "tok_system", "tok_status", "tok_verlauf", "tok_zusammenfassung",
)

#: Wie lange auf einen Thread gewartet wird, den ein ``starte_*`` aufgemacht
#: hat. Das Double antwortet sofort; 30 s sind der Notausgang gegen einen
#: haengenden Lauf, kein Zielwert.
THREAD_FRIST_S = 30.0

#: Die Markierung vor der Profil-Anweisung, nur im Dump -- uebernommen aus
#: ``scripts/erzeuge_prompts_padua.py`` (Birk hat sie am 01.10.2026
#: abgenommen). Der Bot bekommt sie nie.
MARKE = "<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->"


class TreiberFehler(RuntimeError):
    """Ein Treiber hat seinen Modellaufruf nicht erreicht.

    Laut und nicht still: eine fehlende Datei sieht beim Lesen des Audits aus
    wie ein kurzer Prompt, und genau so verschwindet ein Pfad aus dem Check."""


def umgebung() -> einstellungen.Einstellungen:
    """Die Einstellungen des Padua-Live-Betriebs, als echte (frozen) dataclass.

    Echt und nicht ad hoc, weil ``dramaturgie.fanout.Richter.frage``
    ``dataclasses.replace(e, ...)`` ruft -- ein Ad-hoc-Objekt wuerde dort mit
    ``TypeError`` auffliegen."""
    return einstellungen.Einstellungen(
        bot_token="dump",
        bot_name="padua1",
        db_pfad=os.environ.get("IT_DB", ":memory:"),
        audio_verz="audio",
        llm_url="http://127.0.0.1:1/chat/completions",
        llm_key="dump",
        llm_modell="moonshotai/Kimi-K2.6",
        stt_basis="http://127.0.0.1:1",
        stt_produkt="dump",
        erkenner_modell="google/gemma-4-31B-it",
        szene_anbieter="claude",
        szene_modell="claude-opus-5",
    )


def _markiere(system: str) -> str:
    """Setzt die Abnahme-Markierung vor die Profil-Anweisung -- nur im Dump."""
    anweisung = (anweisungen.hole_optional(anweisungen.PROFIL_ANWEISUNG) or "").strip()
    if anweisung and anweisung in system:
        return system.replace(anweisung, f"{MARKE}\n{anweisung}", 1)
    return system


@contextlib.contextmanager
def fange_umriss(sammler: list):
    """Reicht ``protokoll=`` an jedes ``kontext.baue`` durch.

    **Warum gepatcht und nicht zweimal gerufen:** ``ablauf`` ruft
    ``kontext.baue`` ohne ``protokoll`` (``ablauf.py:1322``). Ein zweiter
    Messaufruf mit denselben Argumenten waere nicht derselbe Prompt -- der
    erste merkt sich das Phasenangebot (``arbeitsstand.phase_angeboten``) und
    kann einen Vorfall schreiben, der zweite saehe also eine andere Datenlage.
    Ein Patch misst genau den Aufruf, der auch den Dump fuellt."""
    echt = kontext.baue

    def baue(conn, chat_id, ausloeser, e, erstkontakt=False, protokoll=None,
             ueber_claude=False):
        eigen: list = [] if protokoll is None else protokoll
        text = echt(conn, chat_id, ausloeser, e, erstkontakt=erstkontakt,
                    protokoll=eigen, ueber_claude=ueber_claude)
        sammler.extend(eigen)
        return text

    kontext.baue = baue
    try:
        yield sammler
    finally:
        kontext.baue = echt


def kopfzeile(eintrag, aufruf) -> str:
    return (f"# art={eintrag.art} phase={eintrag.phase} weg={aufruf.weg} "
            f"modell={aufruf.modell} quelle={eintrag.weg}")


def anteile(umriss: dict) -> dict[str, int]:
    """Token je Blockgruppe aus einem ``kontext.umriss``.

    Ein Block, den ``BLOCKGRUPPEN`` nicht nennt, faellt heraus -- deshalb
    prueft ein Test, dass die Summe der Gruppen die Bloecke des Umrisses
    vollstaendig abdeckt."""
    bloecke = umriss.get("bloecke") or {}
    ergebnis = {"tok_system": int(umriss.get("system") or 0)}
    for gruppe, namen in BLOCKGRUPPEN.items():
        ergebnis[gruppe] = sum(int(bloecke.get(name) or 0) for name in namen)
    return ergebnis


def schreibe_dump(ziel: Path, eintrag, aufruf, umriss=None) -> dict:
    system = _markiere(aufruf.system or "")
    nutzer = aufruf.nutzer or ""
    notiz = eintrag.grund or eintrag.art
    (ziel / f"{eintrag.datei}.txt").write_text(
        f"# {eintrag.datei}\n{kopfzeile(eintrag, aufruf)}\n# {notiz}\n"
        f"=== SYSTEM ({len(system)} Zeichen, "
        f"~{kontext.schaetze(system)} Token) ===\n{system}\n\n"
        f"=== NUTZER ({len(nutzer)} Zeichen, "
        f"~{kontext.schaetze(nutzer)} Token) ===\n{nutzer}\n",
        encoding="utf-8",
    )
    zeile = {
        "pfad": eintrag.datei,
        "art": eintrag.art,
        "phase": eintrag.phase,
        "weg": aufruf.weg,
        "modell": aufruf.modell,
        "quelle": eintrag.weg,
        "system_zeichen": len(system),
        "nutzer_zeichen": len(nutzer),
        "token_gesamt": kontext.schaetze(system) + kontext.schaetze(nutzer),
        "tok_system": "", "tok_status": "", "tok_verlauf": "",
        "tok_zusammenfassung": "",
    }
    if umriss:
        zeile.update(anteile(umriss))
    return zeile


def _warte_bis_fertig(modul, chat_id: int) -> None:
    """Wartet, bis ein ``starte()``-Hintergrundthread fertig ist.

    ``diskussion.starte``/``fragen_ki.starte`` geben kein Thread-Objekt
    zurueck (``threading.Thread(target=_lauf, daemon=True).start()`` ohne
    Rueckgabe) -- gejoint werden kann also nichts. Beide raeumen aber ihren
    Sperren-Platz (``versuche_start``/``beende``, Modulattribut ``_LAEUFT``)
    im eigenen Thread ab, und genau das wird hier gepollt. Das Double
    antwortet synchron; ``THREAD_FRIST_S`` ist der Notausgang gegen einen
    haengenden Lauf, kein Zielwert."""
    frist = time.monotonic() + THREAD_FRIST_S
    while chat_id in modul._LAEUFT:
        if time.monotonic() > frist:
            raise TreiberFehler(
                f"{modul.__name__}: Hintergrundlauf fuer chat_id={chat_id} "
                f"nicht innerhalb {THREAD_FRIST_S}s fertig"
            )
        time.sleep(0.01)


def _gespraech(phase: int):
    """Der echte Gespraechszug dieser Phase.

    Gefahren wird ``ablauf.antworte`` -- der oeffentliche Weg, nicht
    ``kontext.baue`` von Hand: nur so stehen Systemanweisung, Streamsenke und
    die Modellwahl (``modellwahl.konversation_ueber_claude``, Phase-3-Ausnahme)
    wirklich wie im Betrieb im Prompt."""
    def treiber(conn, e, tg, klm, chats):
        from interview_theater import ablauf

        chat_id = chats[phase]
        offen = repo.letzte_nachrichten(conn, chat_id, anzahl=1)
        umriss: list = []
        with fange_umriss(umriss):
            ablauf.antworte(conn, tg, klm, e, chat_id, list(offen))
        return umriss[-1] if umriss else None
    return treiber


def _erkenner_verlauf(conn, e, tg, klm, chats):
    from interview_theater import erkenner

    chat_id = chats[4]
    erkenner.erkenne(klm, conn, e, chat_id)
    return None


def _erkenner_aufnahme(conn, e, tg, klm, chats):
    from interview_theater import erkenner

    chat_id = chats[3]
    aufnahme = repo.transkripte(conn, chat_id)[0]
    text = repo.zusammengefuegtes_transkript(conn, aufnahme["id"]) or ""
    erkenner.erkenne_in_aufnahme(klm, conn, e, chat_id, text)
    return None


def _journal(conn, e, tg, klm, chats):
    """Treiber-Fund (Task 6): mit ``chats[4]`` -- wie im Brief-Entwurf --
    bleibt ``journal.unjournalisierte`` unter ``journal.SCHWELLE_VERDRAENGUNG``
    (gemessen: 37 Nachrichten, Fenster 19, verdraengter Rest ~281 Token; die
    Schwelle ist 600). ``journal.extrahiere`` liefert dann ``[]`` OHNE
    Modellaufruf -- kein Fehler im Produktivcode, nur zu wenig Verlauf fuer
    diese eine Gruppe. Nur ``chats[3]`` (die Phase-3-Gruppe mit der
    angehaengten ``_LANGE_TRANSKRIPTDISKUSSION``, eigens dafuer gebaut, siehe
    ``fixture_padua_voll.py``) hat genug Volumen (74 Nachrichten, verdraengt
    ~3189 Token). Der Dump bleibt als Phase 4 inventarisiert
    (``eintrag.phase`` in ``prompt_inventar.py`` ist unveraendert 4, der
    Extraktor ist phasenunabhaengiges Hintergrundhandwerk) -- nur die
    Datenquelle fuer den Treiber wechselt."""
    from interview_theater import journal

    chat_id = chats[3]
    journal.extrahiere(klm, conn, e, chat_id)
    return None


def _begriffsboard(conn, e, tg, klm, chats):
    from interview_theater import begriffsboard

    chat_id = chats[1]
    bis = max(a["id"] for a in repo.transkripte(conn, chat_id))
    begriffsboard._lauf_einmal(conn, klm, e, chat_id, bis)
    return None


def _diskussion(conn, e, tg, klm, chats):
    from interview_theater import diskussion

    chat_id = chats[1]
    diskussion.starte(conn, tg, klm, e, chat_id)
    _warte_bis_fertig(diskussion, chat_id)
    return None


def _fragen_ki(conn, e, tg, klm, chats):
    from interview_theater import fragen_ki

    chat_id = chats[2]
    fragen_ki.starte(conn, tg, klm, e, chat_id)
    _warte_bis_fertig(fragen_ki, chat_id)
    return None


def _verdichter(conn, e, tg, klm, chats):
    from interview_theater import verdichter

    chat_id = chats[3]
    aufnahme = repo.transkripte(conn, chat_id)[0]
    verdichter.verdichte(klm, conn, e, aufnahme["id"])
    return None


def _joine(faden) -> None:
    """Wartet auf einen Thread, den ein ``starte_*`` aufgemacht hat.

    ``None`` heisst: es gab nichts anzustossen (Sperre, Vorbedingung) -- dann
    faellt ``treibe`` mit ``TreiberFehler`` auf, und das ist richtig: ein
    Dump, der still nicht entsteht, ist ein Loch im Check."""
    if faden is not None and hasattr(faden, "join"):
        faden.join(THREAD_FRIST_S)


def _buehnenkarte(conn, e, tg, klm, chats):
    from interview_theater import buehnenkarte

    buehnenkarte.erzeuge(conn, e, klm, chats[4])
    return None


def _szenenfolge(conn, e, tg, klm, chats):
    from interview_theater import szenenfolge

    _joine(szenenfolge.starte(conn, tg, klm, e, chats[4], anzahl=3))
    return None


def _geschichte(conn, e, tg, klm, chats):
    from interview_theater import szenenfolge

    _joine(szenenfolge.starte_geschichte(conn, tg, klm, e, chats[4], anzahl=3))
    return None


def _szenenfelder(conn, e, tg, klm, chats):
    """Treiber-Fund: die Fixture-Szenen der Phase-4-Gruppe haben bereits ALLE
    Pflichtfelder (``ort``/``figuren``/``was_passiert``) -- ``form`` zaehlt in
    Phase 4 nicht mit (``szene.fehlendes``: ``schreibt_prosa`` schliesst es
    aus, solange die Phase <= 6 ist). ``szene_modul.fehlendes`` liefert also
    ``([], [])``, und ``starte_feldvorschlag`` bricht ohne Aufruf ab
    (``szenenfolge.py:1361``: ``if not fehlende: return None``). Ein Feld
    wird deshalb hier im Treiber geleert -- nicht in der Fixture -- derselbe
    Weg wie bei ``_sprechweise``."""
    from interview_theater import szenenfolge

    chat_id = chats[4]
    ziel = repo.hole_szenen(conn, chat_id)[0]
    repo.setze_szenenfeld(conn, ziel["id"], "was_passiert", None)
    ziel = repo.hole_szenen(conn, chat_id)[0]
    _joine(szenenfolge.starte_feldvorschlag(conn, tg, klm, e, chat_id, ziel))
    return None


def _schaerfung(conn, e, tg, klm, chats):
    """Treiber-Fund: ``schaerfung.mappe`` nimmt ``(klm, conn, e, chat_id)`` --
    **nicht** ``(conn, klm, e, chat_id, eintraege)`` wie im Brief-Entwurf. Die
    Funktion holt ihr Material (``_eintraege``) selbst; ein zusaetzliches
    Argument waere ein ``TypeError`` (verifiziert: ``schaerfung.py:197``)."""
    from interview_theater import schaerfung

    chat_id = chats[5]
    schaerfung.mappe(klm, conn, e, chat_id)
    return None


def _entwurf(conn, e, tg, klm, chats):
    from interview_theater import entwurf

    entwurf.generiere_uebersicht(klm, conn, e, chats[5])
    return None


def _sprachprofil(conn, e, tg, klm, chats):
    """Treiber-Fund: ``sprachprofil.erzeuge`` existiert nicht -- der
    synchrone Modellaufruf heisst ``erstelle(klm, conn, e, figur_id)``
    (verifiziert: ``sprachprofil.py:119``). ``starte`` waere der Thread-Weg
    und hinge am selben Aufruf, nur ueber ``_lauf``; ``erstelle`` erreicht
    ihn direkter."""
    from interview_theater import sprachprofil

    chat_id = chats[5]
    aufnahme = repo.transkripte(conn, chat_id)[0]
    figur = repo.figuren(conn, chat_id)[0]
    repo.setze_figur_quelle(conn, figur["id"], aufnahme["id"])
    sprachprofil.erstelle(klm, conn, e, figur["id"])
    return None


def _kernzitate(conn, e, tg, klm, chats):
    """Treiber-Fund: ``kernzitate.waehle`` nimmt ``(klm, conn, e, chat_id)``
    -- dieselbe Reihenfolge wie ``schaerfung.mappe``, nicht
    ``(conn, klm, e, chat_id)`` wie im Brief-Entwurf (verifiziert:
    ``kernzitate.py:179``)."""
    from interview_theater import kernzitate

    chat_id = chats[5]
    repo.setze_arbeitsstand(conn, chat_id, "kernthema", "waiting and belonging")
    repo.setze_arbeitsstand(
        conn, chat_id, "kernfrage",
        "When does a place you only waited in start to be yours?")
    kernzitate.waehle(klm, conn, e, chat_id)
    return None


#: Die Regie-Notiz, mit der die Szenen- und Prosalaeufe gefahren werden.
#: Erfunden, englisch, und genau der Satz aus dem Fixture-Verlauf der Phase 6
#: -- so steht im Dump dieselbe Bitte, die die Gruppe im Chat geaeussert hat.
NOTIZ_PROSA = "Elena should say something to him, a bit rude at first."
NOTIZ_SZENE = "Rewrite scene 2."


def _kurzgeschichte(conn, e, tg, klm, chats):
    """Treiber-Fund: der Brief-Entwurf baute ``system``/``nutzer`` von Hand
    und rief ``klm.prosa`` immer direkt -- das umgeht
    ``szene_claude.ist_aktiv`` und haette in Padua (``szene_anbieter="claude"``,
    AGENTS.md: Phase 6 schreibt ein Opus-Lauf) ``weg=infomaniak`` aufgezeichnet,
    obwohl der echte Lauf ueber Claude ginge. ``kurzgeschichte.hole_text`` ist
    der oeffentliche, synchrone \"nur der Modellaufruf\"-Weg
    (``kurzgeschichte.py:425``): er baut dieselben zwei Texte und verzweigt
    selbst auf ``szene_claude.prosa``/``klm.prosa`` -- echt statt nachgebaut,
    passend zu ``weg=\"abgefangen\"`` in ``prompt_inventar``. Die Laengen-
    Budgets (Padua: ``[laengen] aktiv = true``) kommen wie im echten
    ``schreibe()`` aus ``budget_eintraege``."""
    from interview_theater import kurzgeschichte

    chat_id = chats[6]
    eintraege = kurzgeschichte.budget_eintraege(
        conn, chat_id, faktor=kurzgeschichte._faktor(conn, chat_id))
    kurzgeschichte.hole_text(conn, klm, e, chat_id, NOTIZ_PROSA, eintraege=eintraege)
    return None


def _kurzgeschichte_kuerzer(conn, e, tg, klm, chats):
    """Derselbe Fund wie ``_kurzgeschichte``, hier mit ``vorlage=True`` --
    der Kuerzungslauf der Kuerzung.notiz_fuer_prosa ist dieselbe Aufrufstelle
    wie 25, nur mit anderer Regie-Notiz (Grund in ``prompt_inventar.py``,
    Eintrag ``03-kurzgeschichte-phase6``: \"Der Kuerzungslauf derselben
    Stelle\")."""
    from interview_theater import kuerzung, kurzgeschichte

    chat_id = chats[6]
    eintraege = kurzgeschichte.budget_eintraege(
        conn, chat_id, faktor=kurzgeschichte._faktor(conn, chat_id))
    kurzgeschichte.hole_text(
        conn, klm, e, chat_id, kuerzung.notiz_fuer_prosa(), vorlage=True,
        eintraege=eintraege)
    return None


def _szene(phase: int, form: str, auftrag: str, datei_art: str = "szene"):
    """Ein Szenen-Dump je Form. ``weg="gebaut"`` (siehe Inventar): der live
    verschickte Prompt IST ``systemanweisung(form, stil)`` plus
    ``baue_nutzertext(..., system=system)`` (szene.py:2361-2362)."""
    def treiber(conn, e, tg, klm, chats):
        from interview_theater import szene as szene_modul

        chat_id = chats[phase]
        ziel = repo.hole_szenen(conn, chat_id)[1]
        system = szene_modul.systemanweisung(
            form, ziel["stil"] if "stil" in ziel.keys() else None)
        nutzer = szene_modul.baue_nutzertext(
            conn, chat_id, auftrag, ziel, e, system=system)
        klm.prosa(chat_id, system, nutzer, datei_art)
        return None
    return treiber


def _sprechweise(conn, e, tg, klm, chats):
    """Treiber-Fund: die Fixture setzt ``figur.sprachstil`` fuer jede Figur
    ab Phase 4 (``fixture_padua_voll.baue``, Block ``if phase >= 4``).
    ``sprechweise.fehlende()`` ist dadurch fuer JEDE Gruppe leer, und
    ``sprechweise._lauf`` ruft ohne eine fehlende Figur ueberhaupt kein
    Modell (``sprechweise.py:166``: ``if fehlende(conn, chat_id):``). Eine
    Figur wird deshalb hier im Treiber -- nicht in der Fixture -- auf
    \"noch kein Stil\" zurueckgesetzt, derselbe Weg wie beim
    Kernzitate-Treiber (``repo.setze_arbeitsstand`` direkt im Treiber)."""
    from interview_theater import sprechweise

    chat_id = chats[7]
    figur = repo.figuren(conn, chat_id)[0]
    repo.setze_figur_sprachstil(conn, figur["id"], None)
    _joine(sprechweise.starte(conn, tg, klm, e, chat_id))
    return None


def _stueckpruefung(conn, e, tg, klm, chats):
    from interview_theater import stueckpruefung

    _joine(stueckpruefung.starte(conn, tg, klm, e, chats[7]))
    return None


def _richter(e, conn, chat_id):
    """Der Richter, wie ihn der Prueflauf waehlt.

    Kein eigener Code: ``fanout.waehle_richter`` entscheidet, und mit
    ``szene_anbieter="claude"`` ist das Infomaniak-Modell (``e.llm_modell``)
    -- die Gegenmassnahme gegen den Self-Enhancement Bias."""
    from interview_theater.dramaturgie import fanout

    return fanout.waehle_richter(e, conn, chat_id)


def _dramaturgie(frage: str):
    """Treiber-Fund: ``mechanik.lage`` existiert nicht -- die Funktion, die
    eine ``Szenenlage`` liest, heisst ``mechanik.lies(conn, chat_id)``
    (verifiziert: ``mechanik.py:343``). ``a6`` fehlt hier bewusst: es ist
    in Padua strukturell unerreichbar (siehe ``prompt_inventar.py``,
    Kommentar an der Stelle der frueheren ``37-dramaturgie-a6``) und steht
    deshalb auch nicht mehr in ``TREIBER``.

    ``a9`` braucht einen Hauptkonflikt (``mechanik.hauptkonflikt`` liest
    ``arbeitsstand.hauptkonflikt`` -- ohne ihn liefert ``frage_a9`` sofort
    ``None``, ``fanout.py:631``); die Fixture setzt das Feld nicht, also
    setzt der Treiber es hier, genau wie beim Kernthema in
    ``_kernzitate``."""
    def treiber(conn, e, tg, klm, chats):
        from interview_theater.dramaturgie import fanout, mechanik

        phase = 7 if frage in ("a10", "c1") else 6
        chat_id = chats[phase]
        richter = _richter(e, conn, chat_id)
        szenen = repo.hole_szenen(conn, chat_id)
        if frage == "b1":
            fanout.frage_b1(conn, e, klm, chat_id, richter, szenen[0])
        elif frage == "a9":
            repo.setze_arbeitsstand(
                conn, chat_id, "hauptkonflikt",
                "Samir's quiet refusal to ask for help versus his need for it")
            konflikt = mechanik.hauptkonflikt(conn, chat_id)
            fanout.frage_a9(conn, e, klm, chat_id, richter, szenen[0], konflikt)
        elif frage == "a10":
            fanout.frage_a10(conn, e, klm, chat_id, richter, szenen[0])
        elif frage == "a11":
            fanout.frage_a11(conn, e, klm, chat_id, richter)
        elif frage == "a2":
            fanout.frage_a2(conn, e, klm, chat_id, richter)
        elif frage == "c1":
            ziel = szenen[0]
            figuren = [f["name"] for f in repo.figuren(conn, chat_id)]
            # Treiber-Fund: C1_REPLIKEN_MIN = 6 (fanout.py:112) -- die
            # Fixture-Szene hat nur zwei Repliken ("SAMIR: ...\nELENA: And?"),
            # frage_c1 liefert darunter sofort None (fanout.py:1040). Ein
            # reicherer Dialog wird deshalb hier im Treiber gesetzt, nicht in
            # der Fixture -- derselbe Weg wie bei ``hauptkonflikt`` oben.
            reich = (
                "SAMIR: I did not expect anyone to notice me here.\n"
                "ELENA: I notice everyone, eventually.\n"
                "SAMIR: Three hours, maybe more.\n"
                "ELENA: You could have asked for a coffee.\n"
                "SAMIR: I rehearsed the words. They never came out.\n"
                "ELENA: Next time, just point."
            )
            repo.aktualisiere_szene(
                conn, ziel["id"], ziel["titel"], ziel["kurzbeschreibung"],
                reich, prosa=ziel["prosa"])
            repliken = mechanik.repliken(reich, figuren)
            fanout.frage_c1(conn, e, klm, chat_id, richter, ziel["nummer"],
                            repliken)
        return None
    return treiber


TREIBER = {
    # Phasen 1-3 (Task 6)
    "01-gespraech-phase1": _gespraech(1),
    "05-gespraech-phase2": _gespraech(2),
    "06-gespraech-phase3": _gespraech(3),
    "10-erkenner-verlauf": _erkenner_verlauf,
    "11-erkenner-aufnahme": _erkenner_aufnahme,
    "12-journal": _journal,
    "13-begriffsboard": _begriffsboard,
    "14-diskussion-verdichtung": _diskussion,
    "15-fragen-ki": _fragen_ki,
    "16-verdichter": _verdichter,
    # Phase 4
    "07-gespraech-phase4": _gespraech(4),
    "17-buehnenkarte": _buehnenkarte,
    "18-szenenfolge": _szenenfolge,
    "19-geschichte": _geschichte,
    "20-szenenfelder": _szenenfelder,
    # Phase 5
    "08-gespraech-phase5": _gespraech(5),
    "21-schaerfung": _schaerfung,
    "22-entwurf-uebersicht": _entwurf,
    "23-sprachprofil": _sprachprofil,
    "24-kernzitate": _kernzitate,
    # Phase 6
    "02-gespraech-phase6": _gespraech(6),
    "25-kurzgeschichte": _kurzgeschichte,
    "03-kurzgeschichte-phase6": _kurzgeschichte_kuerzer,
    "04-szene-prosa-phase6": _szene(6, "prosa", NOTIZ_SZENE),
    # Phase 7
    "09-gespraech-phase7": _gespraech(7),
    "27-sprechweise": _sprechweise,
    "28-szene-dialog": _szene(7, "dialog", "Write scene 2."),
    "29-szene-monolog": _szene(7, "monolog", "Write scene 2."),
    "30-szene-chor": _szene(7, "chor", "Write scene 2."),
    "31-szene-lied": _szene(7, "lied", "Write scene 2."),
    "32-szene-rap": _szene(7, "rap", "Write scene 2."),
    "34-stueckpruefung": _stueckpruefung,
    # Die Richterfragen des Prueflaufs (a6 entfaellt, siehe _dramaturgie)
    "35-dramaturgie-b1": _dramaturgie("b1"),
    "36-dramaturgie-a2": _dramaturgie("a2"),
    "38-dramaturgie-a9": _dramaturgie("a9"),
    "39-dramaturgie-a10": _dramaturgie("a10"),
    "40-dramaturgie-a11": _dramaturgie("a11"),
    "41-dramaturgie-c1": _dramaturgie("c1"),
}


def treibe(conn, e, tg, klm, chats, eintrag):
    """Faehrt einen Inventareintrag und liefert ``(Aufruf, Umriss|None)``.

    Ein Treiber, der seinen Aufruf nicht erreicht, ist ein ``TreiberFehler`` --
    nicht eine leere Datei."""
    treiber = TREIBER.get(eintrag.datei)
    if treiber is None:
        raise TreiberFehler(f"kein Treiber fuer {eintrag.datei}")
    vorher = len(klm.aufrufe)
    umriss = treiber(conn, e, tg, klm, chats)
    neu = [a for a in klm.aufrufe[vorher:] if a.art == eintrag.art]
    if not neu:
        gesehen = sorted({a.art for a in klm.aufrufe[vorher:]})
        raise TreiberFehler(
            f"{eintrag.datei}: kein Aufruf mit art={eintrag.art!r} "
            f"aufgezeichnet (gesehen: {gesehen})"
        )
    return neu[0], umriss


def _schreibe_tsv(ziel: Path, zeilen: list[dict]) -> str:
    aus = ["\t".join(TSV_SPALTEN)]
    for zeile in zeilen:
        aus.append("\t".join(str(zeile.get(s, "")) for s in TSV_SPALTEN))
    text = "\n".join(aus) + "\n"
    (ziel / "uebersicht.tsv").write_text(text, encoding="utf-8")
    return text


def _lauf(ziel: Path, nur: list[str] | None) -> list[dict]:
    os.environ.setdefault(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    if workshop.name() != "padua-2026":
        raise SystemExit(
            "IT_WORKSHOP=padua-2026 setzen -- sonst entsteht der Dortmunder Prompt."
        )
    ziel.mkdir(parents=True, exist_ok=True)
    eintraege = [e for e in inv.INVENTAR if not nur or e.datei in nur]
    if nur:
        bekannt = {e.datei for e in inv.INVENTAR}
        fehlend = [n for n in nur if n not in bekannt]
        if fehlend:
            raise TreiberFehler(f"nicht im Inventar: {fehlend}")

    from simulation.attrappe import TelegramAttrappe

    zeilen: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "padua-prompts.db")
        os.environ["IT_DB"] = pfad
        conn = db.verbinde(pfad)
        db.initialisiere(conn)
        chats = fixture.baue_alle(conn)
        e = umgebung()
        tg = TelegramAttrappe()
        klm = ms.Mitschnitt(e)
        with ms.fange_alles(klm):
            for eintrag in eintraege:
                aufruf, umriss = treibe(conn, e, tg, klm, chats, eintrag)
                zeilen.append(schreibe_dump(ziel, eintrag, aufruf, umriss))
        conn.close()
    _schreibe_tsv(ziel, zeilen)
    return zeilen


def main_fuer_test(ziel, nur=None) -> list[dict]:
    """Derselbe Lauf, aber mit Rueckgabewert und ohne ``sys.argv``."""
    return _lauf(Path(ziel), list(nur) if nur else None)


def main() -> None:
    import argparse

    zerleger = argparse.ArgumentParser(description="Padua-Prompt-Dump")
    zerleger.add_argument(
        "ziel", nargs="?", default="docs/prompt-audit/2026-10-05-padua-voll")
    zerleger.add_argument(
        "--nur", default=None,
        help="Kommaliste von Dumpnamen (Vorgabe: alle aus prompt_inventar)")
    argumente = zerleger.parse_args()
    nur = argumente.nur.split(",") if argumente.nur else None
    zeilen = _lauf(Path(argumente.ziel), nur)
    print("\t".join(TSV_SPALTEN))
    for zeile in zeilen:
        print("\t".join(str(zeile.get(s, "")) for s in TSV_SPALTEN))


if __name__ == "__main__":
    main()
