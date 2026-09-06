"""Der Sprachstil je Figur in Phase 4 (06.09.2026, Birk 12:20).

**Warum es das gibt.** Bis heute wurde die Figur in Phase 4 mit Name und
einem Satz ("wer sie ist, was sie will") festgelegt, und die Frage, WIE sie
spricht, kam erst in der Schaerfung -- als Zuordnung zu einem Interview
(``knoepfe.ebene2_erlaubt``). Birk hat das umgedreht: der Stil gehoert zur
Figur, und er gehoert dahin, wo die Figur entsteht. In 6 und 7 wird nicht
mehr danach gefragt.

**Stil ist nicht Material** (Birks Entscheidung, aus der der Kontext-Filter
folgt). In Phase 4 wird erfunden, und der Bot sieht deshalb weder
Verdichtungen noch Transkripte (``kontext.material_erlaubt``). Fuer DIESEN
einen Auftragszug wird eine schmale Ausnahme geoeffnet: je Interview das
Sprachprofil und **ein** geprueftes Zitat -- keine Verdichtungen, keine
Zusammenfassungen, keine Themen. Das Zitat zeigt eine Sprechweise; es
erzaehlt nicht, worum es im Interview ging.

Der Vorschlag ist ein Optionen-Menue (``VORSCHLAG STIL:``): je Zeile ein
kurzer Titel, das gepruefte Zitat und ein vom Modell erzeugter
**Beispielsatz** -- wie die Figur in diesem Stil ueber den Kernkonflikt des
Stuecks sprechen wuerde. Dazu "Eigener Stil" als Freitextweg.
"""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, repo

log = logging.getLogger(__name__)

#: Die Art, unter der der Aufruf im ``aufruf``-Protokoll steht.
ART = "sprachstil"

#: Wie viele Stiloptionen hoechstens vorgeschlagen werden. Drei plus
#: "Eigener Stil" ist auf dem Telefon noch eine Leiste.
MAX_OPTIONEN = 3

#: Hoechstens EIN Zitat je Interview im Nutzertext (PII-Regel und
#: Stil-nicht-Material zugleich): mehr waere eine Verdichtung durch die
#: Hintertuer.
ZITATE_JE_INTERVIEW = 1

MAX_TOKENS = 20_000
TIMEOUT_S = 180.0

ANWEISUNG = """Du schlaegst einer Theatergruppe vor, WIE eine ihrer Figuren spricht.

Die Figur heisst {name}. Unten stehen Sprechweisen aus den Interviews der
Gruppe, je mit einem woertlichen Zitat.

Schlag zwei bis drei Stile vor, je einer in einer Zeile, in GENAU dieser
Form, ohne Einleitung und ohne Nachwort:

VORSCHLAG STIL:
Kurzer Titel — "das woertliche Zitat" — Beispielsatz, wie {name} in diesem Stil ueber den Kernkonflikt des Stuecks sprechen wuerde — Interview N
Kurzer Titel — "das woertliche Zitat" — Beispielsatz — Interview N

Vier Spalten je Zeile, mit Gedankenstrich getrennt:

1. **Titel** unter 25 Zeichen -- er steht spaeter auf einem Knopf.
2. **Das Zitat** buchstabengetreu aus der Liste unten. Erfinde keins, glaette
   keins, setz keine Auslassungszeichen. Ein Zitat, das dort nicht woertlich
   steht, fliegt raus.
3. **Der Beispielsatz** ist von dir: EIN Satz, wie {name} in diesem Stil ueber
   den Kernkonflikt des Stuecks reden wuerde. Er zeigt den Stil an der
   Geschichte der Gruppe, nicht am Interview.
4. **Interview N** -- die Nummer, aus der der Stil kommt, genau so
   geschrieben.

Danach ein Satz und eine offene Frage, hoechstens zwei Zeilen."""

_TEXT_LAEUFT = "Ich hoere durch, wie {name} sprechen koennte …"
_TEXT_FEHLER = "Die Stilvorschlaege sind mir nicht gelungen. Sagt es nochmal."
_TEXT_KEIN_MATERIAL = (
    "Fuer den Sprachstil brauche ich Interviews mit geprueften Zitaten - "
    "es sind noch keine da."
)

_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def stilmaterial(conn, chat_id: int) -> str:
    """Der schmale Materialblock fuer diesen einen Zug: je Interview das
    Sprachprofil (soweit vorhanden) und **ein** geprueftes Zitat.

    Keine Verdichtungen, keine Themen, keine Zusammenfassungen -- Stil ist
    nicht Material. Ohne ein einziges geprueftes Zitat liefert die Funktion
    einen leeren String, und der Aufrufer laesst den Zug aus: lieber keine
    Vorschlaege als erfundene."""
    from interview_theater import kontext

    je_interview: dict[int, list[str]] = {}
    for eintrag in repo.gepruefte_themen(conn, chat_id):
        zitate = je_interview.setdefault(eintrag["aufnahme_id"], [])
        if len(zitate) < ZITATE_JE_INTERVIEW:
            zitate.append(eintrag["beleg_zitat"])
    if not je_interview:
        return ""
    profile = {
        f["quelle_aufnahme_id"]: (f["sprachprofil"] or "").strip()
        for f in repo.figuren(conn, chat_id)
        if f["quelle_aufnahme_id"] is not None
    }
    zeilen = ["Sprechweisen aus den Interviews:"]
    for aufnahme_id, zitate in je_interview.items():
        name = kontext.interviewbezeichnung(conn, chat_id, aufnahme_id)
        zeilen.append(f"- {name}")
        profil = profile.get(aufnahme_id, "")
        if profil:
            zeilen.append(f"    Sprachduktus: {profil}")
        for zitat in zitate:
            zeilen.append(f'    "{zitat}"')
    return "\n".join(zeilen)


def baue_nutzertext(conn, chat_id: int, name: str) -> str:
    """Das Erfundene (Setting, Figuren, Geschichte), dann der schmale
    Stilblock, dann der Auftrag."""
    from interview_theater import szenenfolge

    teile = [szenenfolge._erfundenes(conn, chat_id), stilmaterial(conn, chat_id)]
    teile.append(
        "Euer Auftrag:\n"
        f"Schlag zwei bis drei Sprechweisen fuer {name} vor."
    )
    return "\n\n".join(t for t in teile if t)


def systemanweisung(name: str) -> str:
    """Die Anweisung plus dem Phasenfokus aus ``prompts/phasen/4.md`` --
    derselbe Aufbau wie in ``szenenfolge``."""
    teile = [ANWEISUNG.format(name=name)]
    phase = anweisungen.hole_optional("phasen/4")
    if phase and phase.strip():
        teile.append(phase.strip())
    return "\n\n".join(teile)


def starte(conn, tg, klm, e, chat_id: int, name: str):
    """Kuendigt an und gibt den Stil-Vorschlag an einen eigenen Thread ab.

    **Kein Modellaufruf im aufrufenden Thread** (Zusage 2) -- ein Knopf und
    der Figuren-Durchgang duerfen ihn deshalb ausloesen."""
    if klm is None:
        log.error("Sprachstil ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    if not stilmaterial(conn, chat_id):
        tg.sende(chat_id, _TEXT_KEIN_MATERIAL)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        return None
    tg.sende(chat_id, _TEXT_LAEUFT.format(name=name))
    system = systemanweisung(name)
    nutzer = baue_nutzertext(conn, chat_id, name)

    from interview_theater import arbeitszeilen

    def _lauf() -> None:
        zeilen = arbeitszeilen.sichtbar(tg, chat_id, ART)
        try:
            antwort = klm.prosa(
                chat_id, system, nutzer, ART,
                max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
            )
            if not (antwort or "").strip():
                raise ValueError("Antwort des Sprachmodells war leer")
            from interview_theater import knoepfe

            knoepfe.sende_stil(conn, tg, chat_id, name, antwort)
        except Exception:
            log.exception("Sprachstil-Aufruf fehlgeschlagen, chat_id=%s", chat_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "sprachstil_fehlgeschlagen", "Stil-Aufruf gescheitert",
                )
                tg.sende(chat_id, _TEXT_FEHLER)
            except Exception:
                log.exception("Fehlermeldung zum Stil-Lauf fehlgeschlagen")
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


def zerlege(wert: str) -> list[tuple[str, str, str, int | None]]:
    """Zerlegt einen ``VORSCHLAG STIL:``-Block in ``(Titel, Zitat,
    Beispielsatz, Interviewnummer)`` je Zeile.

    Fehlende Spalten sind leer bzw. ``None`` -- geraten wird nichts."""
    import re

    from interview_theater import vorschlag

    ergebnis: list[tuple[str, str, str, int | None]] = []
    for zeile in vorschlag.zeilen(wert)[:MAX_OPTIONEN]:
        teile = [t.strip() for t in vorschlag._FIGUR_TRENNER.split(zeile)]
        titel = teile[0].strip(" .;:") if teile else ""
        if not titel:
            continue
        zitat = teile[1].strip(' "„“') if len(teile) > 1 else ""
        beispiel = teile[2].strip() if len(teile) > 2 else ""
        nummer = None
        if len(teile) > 3:
            treffer = re.search(r"(\d{1,3})", teile[3])
            if treffer:
                nummer = int(treffer.group(1))
        ergebnis.append((titel, zitat, beispiel, nummer))
    return ergebnis
