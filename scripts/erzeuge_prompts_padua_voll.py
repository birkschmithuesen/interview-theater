"""Jeder Modellaufruf, der in Padua live vorkommt -- als Volltext-Dump.

**Scopes p12 und p34**: dieses Skript hat Treiber fuer die fuenf Dumps aus
Phase 1+2 (Karte t_bf16f3a7, 05.10.2026, ``SCOPE_P1_P2``) und die zehn Dumps
aus Phase 3+4 (Task 3, ``SCOPE_P3_P4``) von ``prompt_inventar.INVENTAR``. Die
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

#: Welche Dumps `--scope` ausliefert, wenn `--nur` fehlt.
SCOPES = {"p12": SCOPE_P1_P2, "p34": SCOPE_P3_P4}


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

    zerleger = argparse.ArgumentParser(description="Padua-Prompt-Dump (Phase 1+2, 3+4)")
    zerleger.add_argument(
        "ziel", nargs="?", default="docs/prompt-audit/2026-10-05-padua-p12")
    zerleger.add_argument(
        "--scope", choices=sorted(SCOPES), default="p12",
        help="Welche Dumps ohne --nur laufen (Vorgabe: p12 -- die fuenf "
             "Dumps aus Phase 1+2; p34 die zehn Dumps aus Phase 3+4)")
    zerleger.add_argument(
        "--nur", default=None,
        help="Kommaliste von Dumpnamen (Vorgabe: die Dumps aus --scope -- "
             "dieser Lauf hat nur fuer SCOPE_P1_P2 und SCOPE_P3_P4 Treiber, "
             "nicht fuer die restlichen Inventareintraege)")
    argumente = zerleger.parse_args()
    nur = argumente.nur.split(",") if argumente.nur else list(SCOPES[argumente.scope])
    zeilen = _lauf(Path(argumente.ziel), nur)
    print("\t".join(TSV_SPALTEN))
    for zeile in zeilen:
        print("\t".join(str(zeile.get(s, "")) for s in TSV_SPALTEN))


if __name__ == "__main__":
    main()
