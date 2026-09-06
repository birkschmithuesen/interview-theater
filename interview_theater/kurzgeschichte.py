"""Phase 6 als **eine Kurzgeschichte** (06.09.2026, Birk 11:50).

**Warum es das gibt.** Bis heute lief Phase 6 Szene fuer Szene: die Gruppe
bestaetigte eine Szene, ein Opus-Lauf schrieb sie als Prosa, dann die
naechste. Das ergab fuenf Texte, die einander nicht kannten -- jeder Lauf
sah nur Zusammenfassungen der Vorszenen. Birk hat es umgedreht: **ein**
Lauf schreibt die ganze Geschichte aus Setting, Figuren (mit ihrem
Sprachstil) und der gewaehlten Richtung, und **das Modell waehlt die Zahl
der Abschnitte selbst** (typisch drei bis sieben). Die Szenenfolge aus
Phase 4 ist dabei Anregung, nicht Vorgabe.

**Danach werden die Abschnitte zu Szenen** -- Nummer, Titel, Prosa,
``was_passiert`` aus der Pflichtzeile "Zusammenfassung", Ort aus dem
Setting. Die bestehende Szenenfolge wird dabei ersetzt (weich, wie in
``szenenfolge.lege_an``), und das Journal haelt fest, dass sie aus der
Kurzgeschichte stammt.

Der Feinschliff (Phase 7) arbeitet danach je Abschnitt wie je Szene: Form
waehlen, uebersetzen.
"""

from __future__ import annotations

import logging
import re
import threading

from interview_theater import anweisungen, repo

log = logging.getLogger(__name__)

ART = "kurzgeschichte"

#: Wie im Szenenlauf: Reasoning ist an, das Budget ist eine Obergrenze
#: gegen Durchdrehen (AGENTS.md Falle 4).
MAX_TOKENS = 200_000
TIMEOUT_S = 900.0

#: Die Ueberschrift eines Abschnitts. Zwei Formen, beide erlaubt --
#: ``## 1. Titel`` und ``ABSCHNITT 1: Titel``: Modelle liefern Markdown,
#: auch wenn der Prompt es nicht verlangt, und ein Abschnitt, der wegen
#: zweier Rauten verlorengeht, kostet einen ganzen Lauf.
_UEBERSCHRIFT = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:ABSCHNITT\s*)?(\d{1,2})[.):]\s*(.+?)\s*$",
    re.IGNORECASE,
)
#: Die Pflichtzeile je Abschnitt -- sie wird ``szene.was_passiert``.
_ZUSAMMENFASSUNG = re.compile(r"^\s*Zusammenfassung\s*:\s*(.+)$", re.IGNORECASE)

ANWEISUNG = """Du schreibst die Kurzgeschichte eines Theaterstuecks.

Unten stehen das Setting, die Figuren mit ihrem Sprachstil und die
Geschichte, auf die sich die Gruppe geeinigt hat. Daraus schreibst du EINE
zusammenhaengende Kurzgeschichte -- keine Szenenliste, kein Theatertext,
kein Drehbuch.

**Du waehlst die Zahl der Abschnitte selbst.** Typisch sind drei bis sieben;
entscheidend ist, was die Geschichte braucht, nicht eine Zahl. Eine
Szenenfolge aus der Planung ist eine Anregung, keine Vorgabe: passt sie,
nimm sie; passt sie nicht, mach es besser.

Insgesamt 1.500 bis 3.500 Woerter.

Jeder Abschnitt beginnt mit einer Ueberschrift und einer Pflichtzeile:

```
1. Titel des Abschnitts
Zusammenfassung: ein Satz, was in diesem Abschnitt passiert

<der Abschnitt als erzaehlende Prosa>

2. Titel des naechsten Abschnitts
Zusammenfassung: ein Satz
...
```

Die Zeile `Zusammenfassung:` ist **Pflicht** -- aus ihr entsteht spaeter die
Planung der Szene. Ohne sie faellt der Abschnitt durch.

Die Regeln fuer den Text selbst stehen unten (Prosa-Regelblock). Kein
Kommentar davor oder danach, keine Moral am Schluss, keine Zwischentitel
ausser den Abschnitts-Ueberschriften."""

_TEXT_LAEUFT = (
    "Ich schreibe eure Geschichte jetzt am Stueck. Das dauert ein paar Minuten."
)
_TEXT_BESETZT = "Ich schreibe schon, einen Moment."
_TEXT_FEHLER = (
    "Die Geschichte ist mir nicht gelungen. Sagt es nochmal, dann versuche "
    "ich es neu."
)
_TEXT_FERTIG = "Eure Geschichte in {anzahl} Abschnitten:"
JOURNAL = "Szenenfolge aus der Kurzgeschichte: {anzahl} Abschnitte"

_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def laeuft(chat_id: int) -> bool:
    """Schreibt gerade ein Lauf fuer diese Gruppe?"""
    return _sperre_fuer(chat_id).locked()


def zerlege(text: str) -> list[tuple[str, str, str]]:
    """Zerlegt eine Kurzgeschichte in ``(Titel, Zusammenfassung, Prosa)``
    je Abschnitt.

    Deterministisch und nachsichtig: eine Ueberschrift beginnt einen neuen
    Abschnitt, die erste ``Zusammenfassung:``-Zeile darunter gehoert dazu,
    alles weitere ist der Text. Abschnitte ohne Text fallen weg -- eine
    Ueberschrift allein ist keine Szene."""
    abschnitte: list[tuple[str, str, list[str]]] = []
    for zeile in (text or "").splitlines():
        treffer = _UEBERSCHRIFT.match(zeile)
        if treffer is not None and len(treffer.group(2)) <= 80:
            abschnitte.append((treffer.group(2).strip(" .:—-"), "", []))
            continue
        if not abschnitte:
            continue
        titel, fassung, koerper = abschnitte[-1]
        zusammen = _ZUSAMMENFASSUNG.match(zeile)
        if zusammen is not None and not fassung:
            abschnitte[-1] = (titel, zusammen.group(1).strip(), koerper)
            continue
        koerper.append(zeile)
    ergebnis: list[tuple[str, str, str]] = []
    for titel, fassung, koerper in abschnitte:
        prosa = "\n".join(koerper).strip()
        if prosa:
            ergebnis.append((titel, fassung, prosa))
    return ergebnis


def lege_szenen_an(conn, chat_id: int, abschnitte) -> list[int]:
    """Legt aus den Abschnitten die Szenen an -- **ersetzend**, wie
    ``szenenfolge.lege_an``.

    Je Abschnitt: Nummer, Titel, ``prosa``, ``was_passiert`` aus der
    Zusammenfassung und der Ort aus dem Setting (``szene.uebernimm_rahmen``).
    ``form`` bleibt leer: sie entscheidet die Gruppe im Feinschliff."""
    from interview_theater import szene as szene_modul

    for alt in repo.hole_szenen(conn, chat_id):
        if alt["nummer"] is not None:
            repo.entferne_szene(conn, chat_id, alt["nummer"])
    nummern: list[int] = []
    for nummer, (titel, fassung, prosa) in enumerate(abschnitte, start=1):
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel or f"Abschnitt {nummer}")
        if fassung:
            repo.setze_szenenfeld(conn, szene_id, "was_passiert", fassung)
        szene_modul.uebernimm_rahmen(conn, chat_id, szene_id)
        repo.aktualisiere_szene(
            conn, szene_id, titel or f"Abschnitt {nummer}", fassung or None,
            None, fassung or None, prosa,
        )
        nummern.append(nummer)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", JOURNAL.format(anzahl=len(nummern)),
        quelle="szene",
    )
    return nummern


def systemanweisung() -> str:
    """Die Anweisung plus dem Prosa-Regelblock -- heiss nachgeladen wie
    jeder Prompt."""
    teile = [ANWEISUNG]
    prosa = anweisungen.hole_optional("formen/prosa")
    if prosa and prosa.strip():
        teile.append(prosa.strip())
    tells = anweisungen.hole_optional("theater-tells")
    if tells and tells.strip():
        teile.append(tells.strip())
    return "\n\n".join(teile)


def baue_nutzertext(conn, chat_id: int, regie: str | None = None) -> str:
    """Setting, Figuren mit Sprachstil, Geschichte, Szenenfolge als
    Anregung -- und eine Regie-Notiz, wenn die Gruppe eine hatte."""
    from interview_theater import szenenfolge

    teile = [szenenfolge._erfundenes(conn, chat_id)]
    stile = [
        f"- {f['name']}: {(f['sprachstil'] or '').strip()}"
        for f in repo.figuren(conn, chat_id)
        if (f["sprachstil"] or "").strip()
    ]
    if stile:
        teile.append("So sprechen die Figuren:\n" + "\n".join(stile))
    auftrag = "Euer Auftrag:\nSchreib die Geschichte am Stueck."
    if regie and regie.strip():
        auftrag += f"\nDie Gruppe sagt dazu: {regie.strip()}"
    teile.append(auftrag)
    return "\n\n".join(t for t in teile if t)


def starte(conn, tg, klm, e, chat_id: int, regie: str | None = None):
    """Kuendigt an und gibt den Lauf an einen eigenen Thread ab
    (Zusage 2: kein Modellaufruf im Knopf-Handler)."""
    if klm is None:
        log.error("Kurzgeschichte ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        tg.sende(chat_id, _TEXT_BESETZT)
        return None
    from interview_theater import szene as szene_modul

    szene_modul._sende_und_merke(conn, tg, e, chat_id, _TEXT_LAEUFT)

    def _lauf() -> None:
        from interview_theater import arbeitszeilen, szene_claude

        zeilen = arbeitszeilen.sichtbar(tg, chat_id, "prosa")
        try:
            system = systemanweisung()
            nutzer = baue_nutzertext(conn, chat_id, regie)
            if szene_claude.ist_aktiv(e, conn, chat_id):
                import httpx

                antwort = szene_claude.prosa(
                    conn, e,
                    getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S),
                    chat_id, system, nutzer, ART, timeout=TIMEOUT_S,
                )
            else:
                antwort = klm.prosa(
                    chat_id, system, nutzer, ART,
                    max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
                )
            abschnitte = zerlege(antwort or "")
            if not abschnitte:
                raise ValueError("Kurzgeschichte ohne erkennbare Abschnitte")
            nummern = lege_szenen_an(conn, chat_id, abschnitte)
            zeilen.stoppe()
            szene_modul._sende_und_merke(
                conn, tg, e, chat_id, _TEXT_FERTIG.format(anzahl=len(nummern)),
            )
            from interview_theater import knoepfe

            knoepfe.zeige_kurzgeschichte(conn, tg, chat_id)
        except Exception:
            log.exception("Kurzgeschichte fehlgeschlagen, chat_id=%s", chat_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "kurzgeschichte_fehlgeschlagen", "Lauf gescheitert",
                )
                szene_modul._sende_und_merke(conn, tg, e, chat_id, _TEXT_FEHLER)
            except Exception:
                log.exception("Fehlermeldung zur Kurzgeschichte fehlgeschlagen")
        finally:
            zeilen.stoppe()
            sperre.release()

    thread = threading.Thread(target=_lauf, daemon=True)
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread
