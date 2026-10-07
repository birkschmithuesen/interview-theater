"""Jeder Modellaufruf, der in Padua live vorkommt -- als Volltext-Dump.

**Scopes p12, p34 und p57**: dieses Skript hat Treiber fuer die fuenf Dumps
aus Phase 1+2 (Karte t_bf16f3a7, 05.10.2026, ``SCOPE_P1_P2``), die zehn Dumps
aus Phase 3+4 (Task 3, ``SCOPE_P3_P4``) und die 25 Dumps aus Phase 5-7 (Task 5,
Karte t_db7c6b2c, ``SCOPE_P5_P7``) von ``prompt_inventar.INVENTAR``. Die
restlichen Eintraege sind Sache einer spaeteren Karte -- ein Lauf ueber sie
wuerde mit ``TreiberFehler`` abbrechen, weil ``TREIBER`` sie nicht kennt.

Aufruf::

    python3.11 -m scripts.erzeuge_prompts_padua_voll \\
        docs/prompt-audit/2026-10-05-padua-p12

Das Skript setzt ``IT_WORKSHOP=padua-2026`` selbst (eine andere Variable weist
es ab) und baut sich eine Wegwerf-Datenbank mit sieben erfundenen Gruppen,
eine je Phase (``scripts.fixture_padua_voll``). ``IT_DB`` zeigt auf diese
Datei, weil ``anweisungen.system`` den Regie-Zettel (``zusatz.md``) daneben
sucht -- ein Zettel aus dem echten Betriebsverzeichnis stuende sonst im Dump.
Die echte Betriebsdatenbank wird nie geoeffnet.

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
"""

from __future__ import annotations

import contextlib
import os
import sys
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

#: Die fuenf Dumps, fuer die dieser Lauf Treiber hat (Karte t_bf16f3a7,
#: Phase 1+2 -- die Tasks 7 dieser Karte ergaenzen die restlichen 34
#: Inventareintraege nicht in diesem Scope).
SCOPE_P1_P2 = (
    "01-gespraech-phase1", "05-gespraech-phase2", "13-begriffsboard",
    "14-diskussion-verdichtung", "15-fragen-ki",
)

#: Die zehn Dumps aus Phase 3+4, fuer die Task 3 Treiber ergaenzt hat.
SCOPE_P3_P4 = (
    "06-gespraech-phase3", "11-erkenner-aufnahme", "16-verdichter",
    "07-gespraech-phase4", "10-erkenner-verlauf", "12-journal",
    "17-buehnenkarte", "18-szenenfolge", "19-geschichte", "20-szenenfelder",
)

#: Die 25 Dumps aus Phase 5-7 (Task 5, Karte t_db7c6b2c): der Gespraechszug,
#: die Hintergrundwege von Phase 5 (Schaerfung, Uebersicht, Sprachprofil,
#: Kernzitate), Szene/Kurzgeschichte in Phase 6, die sieben Richterfragen des
#: Prueflaufs, Sprechweise und die fuenf Formen in Phase 7, die
#: Stueckpruefung, und die beiden Ueberarbeitungslaeufe (Prueflauf,
#: Nachpass), die ``prompt_inventar`` dafuer bekommen hat.
#:
#: **Reihenfolge ist hier kein Zufall** (gemessen am vollen Lauf, nicht
#: geraten): ``04-szene-prosa-phase6``, ``28``..``32-szene-*`` und
#: ``44-nachpass`` SCHREIBEN wirklich in die geteilte Fixture-Datenbank
#: (``szene.schreibe`` mit der Double-Antwort ``[MITSCHNITT]`` -- ohne
#: Kopfzeilen faellt ``szene.zerlege`` auf "der ganze Text ist die Szene"
#: zurueck und ``aktualisiere_szene`` ueberschreibt Kurzbeschreibung und
#: Prosa/Volltext der Szene wirklich). Jeder Dump, der danach noch
#: realistischen Szeneninhalt braucht (die Dramaturgie-Fragen, die
#: Kurzgeschichte/Kuerzung mit ``vorlage=True``, die Stueckpruefung), steht
#: deshalb VOR diesen drei -- ``kurzgeschichte.schreibe`` selbst schreibt
#: nie (``zerlege`` findet ohne Kopfzeilen keine Abschnitte und wirft, bevor
#: etwas gespeichert ist), ist also unabhaengig von der Stelle.
SCOPE_P5_P7 = (
    "08-gespraech-phase5", "21-schaerfung", "22-entwurf-uebersicht",
    "23-sprachprofil", "24-kernzitate", "46-szenenkern",
    "02-gespraech-phase6", "25-kurzgeschichte", "03-kurzgeschichte-phase6",
    "35-dramaturgie-b1", "36-dramaturgie-a2", "37-dramaturgie-a6",
    "38-dramaturgie-a9", "40-dramaturgie-a11", "43-prueflauf-ueberarbeitung",
    "04-szene-prosa-phase6", "45-skript-spiegel",
    "09-gespraech-phase7", "27-sprechweise", "39-dramaturgie-a10",
    "41-dramaturgie-c1", "34-stueckpruefung",
    "28-szene-dialog", "29-szene-monolog", "30-szene-chor", "31-szene-lied",
    "32-szene-rap", "44-nachpass",
)

#: Welche Dumps `--scope` ausliefert, wenn `--nur` fehlt.
SCOPES = {"p12": SCOPE_P1_P2, "p34": SCOPE_P3_P4, "p57": SCOPE_P5_P7}


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


def _begriffsboard(conn, e, tg, klm, chats):
    from interview_theater import begriffsboard

    chat_id = chats[1]
    bis = max(a["id"] for a in repo.transkripte(conn, chat_id))
    begriffsboard._lauf_einmal(conn, klm, e, chat_id, bis)
    return None


def _warte_bis_fertig(modul, chat_id: int, frist_s: float = THREAD_FRIST_S) -> None:
    """Wartet, bis der Hintergrund-Thread von ``modul.starte`` fertig ist.

    ``starte()`` gibt selbst keinen Thread zurueck (nur ein ``bool``/``None``)
    -- gewartet wird ueber das modulinterne Sperren-Register (``_LAEUFT``),
    das ``versuche_start`` vor dem Thread-Start befuellt und ``beende`` in
    ``_lauf()``s ``finally`` wieder leert."""
    ende = time.monotonic() + frist_s
    while chat_id in modul._LAEUFT and time.monotonic() < ende:
        time.sleep(0.01)


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


def _joine(faden) -> None:
    if faden is not None and hasattr(faden, "join"):
        faden.join(THREAD_FRIST_S)


def _interview_kopf(conn, chat_id):
    from interview_theater import aufnahme
    return aufnahme.interviews(conn, chat_id)[-1]


def _erkenner_aufnahme(conn, e, tg, klm, chats):
    from interview_theater import erkenner
    chat_id = chats[3]
    kopf = _interview_kopf(conn, chat_id)
    with contextlib.suppress(Exception):
        erkenner.erkenne_in_aufnahme(klm, conn, e, chat_id, kopf["transkript"] or "")
    return None


def _verdichter(conn, e, tg, klm, chats):
    from interview_theater import verdichter
    with contextlib.suppress(Exception):
        verdichter.verdichte(klm, conn, e, _interview_kopf(conn, chats[3])["id"])
    return None


def _erkenner_verlauf(conn, e, tg, klm, chats):
    from interview_theater import erkenner
    with contextlib.suppress(Exception):
        erkenner.erkenne(klm, conn, e, chats[4])
    return None


#: Fuellt ``_journal`` unten vorne an: der Phase-4-Verlauf der Fixture allein
#: ist zu kurz, um ueber die 600-Token-Schwelle (``journal.SCHWELLE_
#: VERDRAENGUNG``) zu kommen -- das Fenster schneidet zwar 18 Nachrichten ab,
#: aber ihr Text schaetzt sich auf nur ~280 Token (gemessen). Sechs lange,
#: aeltere Zeilen (vor dem eigentlichen Verlauf, also sicher ausserhalb des
#: Fensters) reissen die Schwelle zuverlaessig.
_JOURNAL_FUELLER = (
    "before we move to anything else I want to go back over every single "
    "thing we said about the first morning here, because I think we are "
    "already starting to forget how uncertain everyone sounded before we "
    "had any plan at all, and that uncertainty is itself material we might "
    "otherwise lose once we are deep into scenes and polish, so let us keep "
    "a plain record of it now while it is still close to how it actually felt."
)


def _journal(conn, e, tg, klm, chats):
    from interview_theater import journal
    chat_id = chats[4]
    sprecher = ("Giulia", "Marco", "Chiara", "Luca", "Giulia", "Marco")
    for i, name in enumerate(sprecher):
        repo.merke_nachricht(conn, chat_id, 500 + i, name, 0, "text",
                              _JOURNAL_FUELLER, f"2026-10-05T04:0{i}:00+00:00")
    with contextlib.suppress(Exception):
        journal.extrahiere(klm, conn, e, chat_id)
    return None


def _buehnenkarte(conn, e, tg, klm, chats):
    from interview_theater import buehnenkarte
    chat_id = chats[4]
    # Die Fixture hat in Phase 4 kein Brainstorm-Transkript -- ein Segment,
    # wie es der Knopf "Brainstorm mithoeren" anlegt.
    aid = repo.lege_aufnahme_an(conn, chat_id, 990, "kurz", "web", status="fertig",
                                brainstorm=True, schnittgrund="ende")
    repo.setze_transkript(conn, aid, "What if Samir never leaves the bench, and the "
                                     "cafe woman brings him the coffee he never orders?")
    with contextlib.suppress(Exception):
        buehnenkarte.erzeuge(conn, e, klm, chat_id)
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
    from interview_theater import szenenfolge
    chat_id = chats[4]
    # Alle drei Szenen aus der Fixture haben ort/was_passiert/figuren schon
    # gesetzt -- szene_modul.fehlendes() liefert dort nichts, und
    # starte_feldvorschlag haette ohne Luecke nichts zu tun (gemessen: kein
    # Aufruf). Eine zusaetzliche, bewusst unvollstaendige Szene (ohne
    # Kurzbeschreibung, ohne Figuren) gibt ``ziel`` eine echte Luecke.
    nummer = max(s["nummer"] for s in repo.hole_szenen(conn, chat_id)) + 1
    szene_id = repo.lege_szene_an(conn, chat_id, nummer, "The platform", None, None)
    ziel = repo.hole_szene(conn, szene_id)
    _joine(szenenfolge.starte_feldvorschlag(conn, tg, klm, e, chat_id, ziel))
    return None


# ---------------------------------------------------------------------------
# Phase 5-7 (Task 5, Karte t_db7c6b2c)
# ---------------------------------------------------------------------------


def _schaerfung(conn, e, tg, klm, chats):
    from interview_theater import schaerfung
    _joine(schaerfung.starte(conn, tg, klm, e, chats[5]))
    return None


def _entwurf_uebersicht(conn, e, tg, klm, chats):
    from interview_theater import entwurf
    _joine(entwurf.starte_uebersicht(conn, tg, klm, e, chats[5]))
    return None


def _sprachprofil(conn, e, tg, klm, chats):
    from interview_theater import repo as repo_modul
    from interview_theater import sprachprofil
    chat_id = chats[5]
    figur = repo_modul.figuren(conn, chat_id)[0]
    aufnahme_id = _interview_kopf(conn, chat_id)["id"]
    repo_modul.setze_figur_quelle(conn, figur["id"], aufnahme_id)
    _joine(sprachprofil.starte(conn, tg, klm, e, chat_id, [figur["id"]]))
    return None


def _kernzitate(conn, e, tg, klm, chats):
    from interview_theater import kernzitate
    _joine(kernzitate.starte(conn, tg, klm, e, chats[5]))
    return None


def _szenenkern(conn, e, tg, klm, chats):
    """``46-szenenkern``: die Kurzform je Szene, wie "Done" in der
    Sortierliste sie ausloest (``szenenkern.starte``)."""
    from interview_theater import szenenkern
    _joine(szenenkern.starte(conn, klm, e, chats[5]))
    return None


def _szene_prosa_phase6(conn, e, tg, klm, chats):
    """``04-szene-prosa-phase6``: derselbe Aufruf wie ``entwurf.
    fixiere_uebersicht``/``bestaetige_szene`` ihn ausloesen -- die Phase (6)
    entscheidet in ``szene.schreibe`` allein, ob Prosa oder Buehnentext
    entsteht (``schreibt_prosa``), der Auftragstext ist zeichengleich."""
    from interview_theater import entwurf, szene
    _joine(szene.starte(conn, tg, klm, e, chats[6],
                        entwurf._AUFTRAG_PROSA.format(nummer=1)))
    return None


def _kurzgeschichte(conn, e, tg, klm, chats):
    from interview_theater import kurzgeschichte
    _joine(kurzgeschichte.starte(conn, tg, klm, e, chats[6]))
    return None


def _kurzgeschichte_kuerzung(conn, e, tg, klm, chats):
    """``03-kurzgeschichte-phase6``: derselbe Aufruf wie 25, aber mit
    ``vorlage=True`` und der Kuerzungsnotiz -- wie ``kuerzung.starte`` ihn
    fuer die ganze Geschichte baut (``kuerzung.py:205``)."""
    from interview_theater import kuerzung, kurzgeschichte
    _joine(kurzgeschichte.starte(conn, tg, klm, e, chats[6],
                                 kuerzung.notiz_fuer_prosa(), vorlage=True))
    return None


def _dramaturgie(schluessel: str, phase: int):
    """Eine der sieben Richterfragen des Prueflaufs (``fanout.pruefe`` mit
    ``fragen=(schluessel,)``) -- dieselbe Aufrufstelle (``Richter.frage``)
    fuer alle sieben, nur die Frage und damit die ``art`` unterscheidet sich.
    ``mechanik=False``: die Mechanik-Pruefung braucht keinen Modellaufruf und
    soll den Dump nicht verlangsamen.

    Fuer a6, a9 und c1 reicht der generische Weg nicht (siehe die drei
    eigenen Treiber unten) -- diese Fabrik bleibt fuer b1, a2, a10, a11."""
    def treiber(conn, e, tg, klm, chats):
        from interview_theater.dramaturgie import fanout
        with contextlib.suppress(Exception):
            fanout.pruefe(conn, e, klm, chats[phase], fragen=(schluessel,),
                          mechanik=False)
        return None
    return treiber


def _dramaturgie_a6(conn, e, tg, klm, chats):
    """``37-dramaturgie-a6``: ``tschechow_kandidaten`` liefert **nie** etwas
    ausserhalb des Deutschen (``mechanik.py``: ``if sprache.code() !=
    sprache.DEUTSCH: return []`` -- Annahme A7). In Padua (Englisch) ist A6
    damit live unerreichbar; der Treiber baut einen Kandidaten von Hand und
    ruft ``frage_a6`` direkt -- derselbe Aufrufer-Code, nur ohne die
    sprachgaengige Vorfilterung (Befund fuer den Bericht, nicht nur ein
    Dump-Kniff)."""
    from interview_theater.dramaturgie import fanout, mechanik
    chat_id = chats[6]
    richter = fanout.waehle_richter(e, conn, chat_id)
    kandidat = mechanik.Kandidat(
        "bag", 1, 2, "He held the broken bag shut with his foot.")
    with contextlib.suppress(Exception):
        fanout.frage_a6(conn, e, klm, chat_id, richter, [kandidat])
    return None


def _dramaturgie_a9(conn, e, tg, klm, chats):
    """``38-dramaturgie-a9``: ohne ``arbeitsstand.hauptkonflikt`` gibt es
    ``"Ohne Hauptkonflikt gibt es keine Frage"`` -- ``frage_a9`` bricht vor
    dem Modellaufruf ab (``fanout.py``). Die Fixture setzt das Feld nicht
    (kein Live-Eintrag dafuer vor Padua Phasen TEIL 2); der Treiber traegt es
    nur fuer diesen Dump nach."""
    from interview_theater import repo as repo_modul
    from interview_theater.dramaturgie import fanout
    chat_id = chats[6]
    repo_modul.setze_arbeitsstand(
        conn, chat_id, "hauptkonflikt",
        "Samir has to let his cousin see him waiting, unsure, not in control.",
    )
    with contextlib.suppress(Exception):
        fanout.pruefe(conn, e, klm, chat_id, fragen=("a9",), mechanik=False)
    return None


def _dramaturgie_c1(conn, e, tg, klm, chats):
    """``41-dramaturgie-c1``: braucht mindestens ``C1_REPLIKEN_MIN`` (6)
    Sprecherzeilen aus mindestens ``C1_FIGUREN_MIN`` (2) Figuren
    (``fanout.py``) -- die zwei Zeilen, die die Fixture fuer die
    Feinschliff-Szene anlegt, reichen nicht. Der Treiber schreibt der ersten
    Szene ein laengeres Wechselgespraech, bevor die Frage laeuft."""
    from interview_theater import repo as repo_modul
    from interview_theater.dramaturgie import fanout
    chat_id = chats[7]
    ziel = next(s for s in repo_modul.hole_szenen(conn, chat_id)
               if s["nummer"] == 1)
    repo_modul.aktualisiere_szene(
        conn, ziel["id"], ziel["titel"], ziel["kurzbeschreibung"],
        "SAMIR: I have been sitting here for three hours.\n"
        "ELENA: And you still have not ordered anything.\n"
        "SAMIR: I was going to.\n"
        "ELENA: You keep saying that.\n"
        "SAMIR: The bag is heavier than it looks.\n"
        "ELENA: Then put it down for a moment.\n",
        ziel["zusammenfassung"],
    )
    with contextlib.suppress(Exception):
        fanout.pruefe(conn, e, klm, chat_id, fragen=("c1",), mechanik=False)
    return None


def _sprechweise(conn, e, tg, klm, chats):
    """``27-sprechweise``: die Fixture setzt ``figur.sprachstil`` fuer ALLE
    Figuren (phasenuebergreifend gleich gebaut) -- ohne eine Figur ohne Stil
    liefe ``sprechweise._lauf`` ganz ohne Modellaufruf (``fehlende`` leer).
    Eine Figur wird deshalb hier auf "ohne Stil" zurueckgesetzt, genau der
    Live-Zustand vor der ersten Uebertragung in Phase 7."""
    from interview_theater import repo as repo_modul
    from interview_theater import sprechweise
    chat_id = chats[7]
    figur = repo_modul.figuren(conn, chat_id)[0]
    repo_modul.setze_figur_sprachstil(conn, figur["id"], "")
    _joine(sprechweise.starte(conn, tg, klm, e, chat_id))
    return None


def _szene_form(form: str):
    """Eine der fuenf Formen des Feinschliffs (28-32): dieselbe Aufrufstelle
    wie 04 (``szene.schreibe``), die Form steht auf der Szene selbst
    (``systemanweisung(form)`` liest ``ziel['form']``)."""
    def treiber(conn, e, tg, klm, chats):
        from interview_theater import repo as repo_modul
        from interview_theater import szene
        chat_id = chats[7]
        ziel = next(s for s in repo_modul.hole_szenen(conn, chat_id)
                   if s["nummer"] == 1)
        repo_modul.setze_szenenfeld(conn, ziel["id"], "form", form)
        auftrag = szene.T.TEXT_AUFTRAG_NEU.format(
            nummer=1, notiz=f"Make it a {form}.")
        _joine(szene.starte(conn, tg, klm, e, chat_id, auftrag))
        return None
    return treiber


def _stueckpruefung(conn, e, tg, klm, chats):
    from interview_theater import stueckpruefung
    _joine(stueckpruefung.starte(conn, tg, klm, e, chats[7]))
    return None


def _prueflauf_ueberarbeitung(conn, e, tg, klm, chats):
    """``43-prueflauf-ueberarbeitung``: derselbe Aufruf wie 03/25
    (``kurzgeschichte.schreibe`` ueber ``starte``), aber direkt ueber
    ``prueflauf._schreibe_geschichte`` wie ``pruefe_geschichte`` ihn
    anstoesst -- synchron, keine Sperre, ``zeigen=False``."""
    from interview_theater import prueflauf
    chat_id = chats[6]
    auftraege = [{"szene": None,
                  "anweisung": "Make the causal chain between scenes clearer."}]
    with contextlib.suppress(Exception):
        prueflauf._schreibe_geschichte(conn, tg, klm, e, chat_id, auftraege)
    return None


def _nachpass(conn, e, tg, klm, chats):
    """``44-nachpass``: derselbe Aufruf wie 04/28-32 (``szene.schreibe``),
    aber mit ``art=nachpass.ART_SZENE`` und der Regie-Notiz, die
    ``nachpass.nach_szene`` baut (``nachpass._notiz``, Laenge erzwungen --
    die Feinschliff-Szenen der Fixture sind zu kurz, um das Budget selbst zu
    reissen, und ohne Notiz gaebe es keinen Aufruf, ``nach_szene`` Zeile
    144f.)."""
    from interview_theater import nachpass, repo as repo_modul, szene
    chat_id = chats[7]
    nummer = min(s["nummer"] for s in repo_modul.hole_szenen(conn, chat_id)
                if s["nummer"] is not None)
    notiz = nachpass._notiz(True, [])
    auftrag = szene.T.TEXT_AUFTRAG_NEU.format(nummer=nummer, notiz=notiz)
    with contextlib.suppress(Exception):
        szene.schreibe(conn, tg, klm, e, chat_id, auftrag,
                       art=nachpass.ART_SZENE, zeigen=False)
    return None


TREIBER = {
    "01-gespraech-phase1": _gespraech(1),
    "05-gespraech-phase2": _gespraech(2),
    "13-begriffsboard": _begriffsboard,
    "14-diskussion-verdichtung": _diskussion,
    "15-fragen-ki": _fragen_ki,
    "06-gespraech-phase3": _gespraech(3),
    "07-gespraech-phase4": _gespraech(4),
    "11-erkenner-aufnahme": _erkenner_aufnahme,
    "16-verdichter": _verdichter,
    "10-erkenner-verlauf": _erkenner_verlauf,
    "12-journal": _journal,
    "17-buehnenkarte": _buehnenkarte,
    "18-szenenfolge": _szenenfolge,
    "19-geschichte": _geschichte,
    "20-szenenfelder": _szenenfelder,
    "08-gespraech-phase5": _gespraech(5),
    "21-schaerfung": _schaerfung,
    "22-entwurf-uebersicht": _entwurf_uebersicht,
    "23-sprachprofil": _sprachprofil,
    "24-kernzitate": _kernzitate,
    "46-szenenkern": _szenenkern,
    "04-szene-prosa-phase6": _szene_prosa_phase6,
    # Derselbe Treiber wie 04: der EN/IT-Spiegelpass (Birk, Live-Workshop
    # 07.10.2026 ~17:20) haengt sich in szene.schreibe an denselben Lauf an
    # und wird dort automatisch mitaufgezeichnet (Padua-Profilschalter
    # [skript] zweisprachig steht in workshop/padua-2026/profil.toml).
    "45-skript-spiegel": _szene_prosa_phase6,
    "02-gespraech-phase6": _gespraech(6),
    "25-kurzgeschichte": _kurzgeschichte,
    "03-kurzgeschichte-phase6": _kurzgeschichte_kuerzung,
    "35-dramaturgie-b1": _dramaturgie("b1", 6),
    "36-dramaturgie-a2": _dramaturgie("a2", 6),
    "37-dramaturgie-a6": _dramaturgie_a6,
    "38-dramaturgie-a9": _dramaturgie_a9,
    "39-dramaturgie-a10": _dramaturgie("a10", 7),
    "40-dramaturgie-a11": _dramaturgie("a11", 6),
    "41-dramaturgie-c1": _dramaturgie_c1,
    "09-gespraech-phase7": _gespraech(7),
    "27-sprechweise": _sprechweise,
    "28-szene-dialog": _szene_form("dialog"),
    "29-szene-monolog": _szene_form("monolog"),
    "30-szene-chor": _szene_form("chor"),
    "31-szene-lied": _szene_form("lied"),
    "32-szene-rap": _szene_form("rap"),
    "34-stueckpruefung": _stueckpruefung,
    "43-prueflauf-ueberarbeitung": _prueflauf_ueberarbeitung,
    "44-nachpass": _nachpass,
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
    # ``startswith(eintrag.art + "_")`` zusaetzlich zur Gleichheit: die
    # Schaerfung (Umbau 07.10.2026, Je-Ziel-Aufrufe) bucht nicht mehr unter
    # dem blossen "schaerfung", sondern je Ziel unter
    # "schaerfung_<art>_<id>" -- derselbe Dump-Zweck, nur mehrere Aufrufe
    # statt einem; der erste repraesentiert den Dump.
    praefix = eintrag.art + "_"
    neu = [
        a for a in klm.aufrufe[vorher:]
        if a.art == eintrag.art or a.art.startswith(praefix)
    ]
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
    # Robo 05.10.: Umgebung nach dem Lauf wiederherstellen -- vorher blieben
    # IT_WORKSHOP/IT_DB gesetzt und verschmutzten jeden spaeteren Test im
    # selben Prozess (6 rote Tests in test_flow_fixes_0609 im Verbund).
    alt = {k: os.environ.get(k) for k in (workshop.VARIABLE, "IT_DB")}
    try:
        return _lauf_innen(ziel, nur)
    finally:
        for k, v in alt.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        workshop.vergiss()
        anweisungen._CACHE.clear()


def _lauf_innen(ziel: Path, nur: list[str] | None) -> list[dict]:
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

    zerleger = argparse.ArgumentParser(description="Padua-Prompt-Dump (Phase 1+2, 3+4, 5-7)")
    zerleger.add_argument(
        "ziel", nargs="?", default="docs/prompt-audit/2026-10-05-padua-p12")
    zerleger.add_argument(
        "--scope", choices=sorted(SCOPES), default="p12",
        help="Welche Dumps ohne --nur laufen (Vorgabe: p12 -- die fuenf "
             "Dumps aus Phase 1+2; p34 die zehn Dumps aus Phase 3+4; p57 die "
             "25 Dumps aus Phase 5-7)")
    zerleger.add_argument(
        "--nur", default=None,
        help="Kommaliste von Dumpnamen (Vorgabe: die Dumps aus --scope -- "
             "dieser Lauf hat nur fuer SCOPE_P1_P2, SCOPE_P3_P4 und "
             "SCOPE_P5_P7 Treiber, nicht fuer die restlichen "
             "Inventareintraege)")
    argumente = zerleger.parse_args()
    nur = argumente.nur.split(",") if argumente.nur else list(SCOPES[argumente.scope])
    zeilen = _lauf(Path(argumente.ziel), nur)
    print("\t".join(TSV_SPALTEN))
    for zeile in zeilen:
        print("\t".join(str(zeile.get(s, "")) for s in TSV_SPALTEN))


if __name__ == "__main__":
    main()
