"""Wie eine Figur spricht -- ein Aufruf je Figur, aus ihrem Interview.

**Warum das das Wichtigste ist** (Birk, 05.09.2026, nach dem Probelauf):
*"Zitate als Few-Shots fuer die Sprechweise je Figur, das ist das
Wichtigste."* Der Szenentext aus dem Probelauf hatte drei Figuren, die alle
gleich klangen -- weil der Prompt Volltranskripte bekam und daraus selbst
heraushoeren sollte, wer wie spricht. Umgekehrt ist es richtig: **je Figur
eine destillierte Analyse und drei bis fuenf woertliche Saetze**, direkt vor
dem Auftrag. Regel 4 des Szenen-Prompts ("Figuren klingen verschieden") haengt
seitdem an dieser Datei.

**Der Ablauf, in einem Satz:** die Gruppe legt eine Figur an → der
Gespraechs-Prompt bekommt einen Hinweisblock (``kontext._baue_figurenhinweis``)
und der Bot schlaegt im Fluss eine Interview-Zuordnung vor, mit einem Zitat →
die Gruppe nickt oder aendert (Erkenner-art ``figur_quelle_setzen``) → **ein**
Aufruf hier, in einem eigenen Thread → Profil und Zitate stehen in ``figur``.

**Nichts davon raet der Code.** Die Zuordnung Figur ↔ Interview ist eine
Entscheidung ueber einen Menschen, den die Gruppe interviewt hat: welche Figur
aus wessen Erzaehlung spricht, kann kein Namensvergleich beantworten. Deshalb
schlaegt der Bot vor und die Gruppe entscheidet -- dieselbe Regel wie ueberall.

**Die Zitate werden geprueft wie beim Verdichter** (``zitat.pruefe``, SPEC
§ 5): was nicht woertlich im Transkript steht, wird verworfen, ohne Retry und
ohne Segmentzerlegung. Ein erfundenes Zitat waere hier besonders teuer -- es
ginge als Few-Shot in jeden weiteren Szenenlauf ein und praegte die Stimme
einer Figur, die eine anwesende Person spielt.

**Reasoning aus, gemma, eigener Thread.** Die Aufgabe ist Extraktion, kein
Abwaegen (AGENTS.md 'Die Fallen' Nr. 4/5): ``LLM.schema`` mit
``reasoning_effort: "none"`` und dem Erkenner-Modell. Der Thread ist nicht
wegen der Latenz da, sondern wegen der Zusage, dass ein Erkennerlauf nichts
aufhaelt -- niemand wartet auf ein Sprachprofil.
"""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, repo, zitat

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf``.
ART = "sprachprofil"

#: Wie viele Zitate hoechstens gespeichert werden. Der Prompt nennt drei bis
#: fuenf; die Obergrenze steht zusaetzlich hier, weil sie im Szenen-Prompt
#: Platz kostet und ein Modell, das zehn liefert, sonst zehn davon in jeden
#: weiteren Lauf traegt.
MAX_ZITATE = 5

#: Flach wie ueberall (global-constraints.md 'Schema'): ein Objekt mit einem
#: Text und einer Liste von Strings, keine Verschachtelung tiefer als
#: ``array > string``. ``additionalProperties: false`` und ein vollstaendiges
#: ``required`` sind Pflicht, sonst lehnt der Anbieter den erzwungenen Modus
#: ab.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["profil", "zitate"],
    "properties": {
        "profil": {"type": "string"},
        "zitate": {"type": "array", "items": {"type": "string"}},
    },
}

#: Die Notiert-Zeile. Sie nennt die Quelle mit, weil genau das die
#: Entscheidung war, die die Gruppe getroffen hat: "Sprachprofil fuer Pola aus
#: Interview 2: kurze Saetze, 'halt', bricht ab".
MELDUNG = "Sprachprofil fuer {name} aus {quelle}: {kurz}"

#: So viele Zeichen der Analyse gehen in die Meldung. Der ganze Block waere
#: fuenf Zeilen im Chat, und die Gruppe soll hier nur erfahren, DASS es das
#: Profil gibt -- nachlesen kann sie es auf der Gruppenseite.
MELDUNG_ZEICHEN = 120

_TEXT_KEIN_TRANSKRIPT = (
    "Zu {quelle} habe ich kein Transkript - ohne das kann ich nicht hoeren, "
    "wie {name} spricht."
)
_TEXT_KEIN_ZITAT = (
    "Ich konnte fuer {name} keinen Satz woertlich belegen. Sagt mir ein "
    "anderes Interview, dann versuche ich es damit."
)


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("sprachprofil")


def baue_nutzertext(transkript: str) -> str:
    """Der Nutzertext: das Transkript, sonst nichts.

    Oeffentlich, damit ``scripts/pruefe_prompts.py`` denselben Text baut wie
    der Betrieb (dieselbe Ueberlegung wie bei ``verdichter.baue_nutzertext``)
    -- und bewusst ohne Arbeitsstand und ohne Figurennamen: was hier gefragt
    ist, ist die Sprechweise einer Person, nicht die Rolle, die aus ihr wird."""
    return (transkript or "").strip()


def _kurzfassung(profil: str) -> str:
    """Die erste Zeile der Analyse, auf MELDUNG_ZEICHEN gekuerzt -- das, was
    in die Notiert-Zeile passt."""
    erste = next((z.strip(" -*") for z in (profil or "").splitlines() if z.strip()), "")
    if len(erste) <= MELDUNG_ZEICHEN:
        return erste
    return erste[: MELDUNG_ZEICHEN - 1].rstrip() + "…"


def erstelle(klm, conn, e, figur_id: int) -> str | None:
    """Der eigentliche Aufruf: Transkript holen, Modell fragen, Zitate
    pruefen, speichern. Liefert die Meldung fuer die Gruppe, oder None, wenn
    nichts gespeichert wurde.

    Fehler fliegen heraus -- ``_lauf()`` faengt sie. Die beiden Faelle, die
    hier **kein** Fehler sind, bekommen ihre eigene Zeile: ein Interview ohne
    Transkript und ein Lauf, in dem kein einziges Zitat die Pruefung
    besteht. Beides kann die Gruppe beheben (ein anderes Interview nennen),
    also erfaehrt sie davon (SPEC § 11.1)."""
    figur = repo.hole_figur_nach_id(conn, figur_id)
    if figur is None or figur["quelle_aufnahme_id"] is None:
        return None
    aufnahme = repo.hole_aufnahme(conn, figur["quelle_aufnahme_id"])
    quelle = (aufnahme["name"] if aufnahme else None) or "dem Interview"
    transkript = repo.zusammengefuegtes_transkript(conn, figur["quelle_aufnahme_id"])
    if not transkript.strip():
        return _TEXT_KEIN_TRANSKRIPT.format(quelle=quelle, name=figur["name"])

    ergebnis = klm.schema(
        figur["chat_id"], prompt(), baue_nutzertext(transkript), SCHEMA, ART,
        modell=e.erkenner_modell,
    )

    geprueft = []
    for satz in ergebnis.get("zitate", []):
        satz = (satz or "").strip()
        if satz and zitat.pruefe(satz, transkript) and satz not in geprueft:
            geprueft.append(satz)
        if len(geprueft) >= MAX_ZITATE:
            break

    if not geprueft:
        # Wie beim Verdichter (N2): ohne Beleg wird nichts gespeichert. Ein
        # Profil ohne Zitate waere die Behauptung, so spreche ein Mensch, den
        # die Gruppe kennt -- und im Szenen-Prompt haengt die Stimme der Figur
        # genau an diesen Saetzen.
        repo.merke_vorfall(
            conn, figur["chat_id"], getattr(e, "bot_name", None), "zitat_ungeprueft",
            f"Sprachprofil ohne belegtes Zitat verworfen (figur={figur['name']!r})",
        )
        return _TEXT_KEIN_ZITAT.format(name=figur["name"])

    profil = (ergebnis.get("profil") or "").strip()
    repo.setze_sprachprofil(conn, figur_id, profil, geprueft)
    repo.schreibe_journal(
        conn, figur["chat_id"], "entschieden",
        f"Sprachprofil fuer {figur['name']} aus {quelle}", quelle="sprachprofil",
    )
    return MELDUNG.format(
        name=figur["name"], quelle=quelle, kurz=_kurzfassung(profil) or "steht",
    )


def _sende_und_merke(conn, tg, e, chat_id: int, text: str) -> None:
    """Schickt eine Zeile und schreibt sie als Bot-Nachricht mit -- wie
    ``szene._sende_und_merke``, damit sie im Verlaufsfenster des naechsten
    Gespraechszugs steht."""
    try:
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
            text, repo._jetzt(),
        )
    except Exception:
        log.exception("Sprachprofil-Nachricht fehlgeschlagen, chat_id=%s", chat_id)


def _lauf(conn, tg, klm, e, chat_id: int, figur_ids: list[int]) -> None:
    """Der Thread-Rumpf: ein Aufruf je Figur, jeder in seinem eigenen
    try/except. Ein Fehlschlag bei der einen Figur darf die andere nicht
    mitreissen -- die Gruppe hat im selben Zug oft drei Zuordnungen genickt.

    Ein Fehlschlag bleibt fuer die Gruppe still (``vorfall`` fuers Dashboard):
    sie kann ihn nicht beheben und wartet nicht darauf, und die Zuordnung
    steht -- ein spaeterer Anlauf ueber dieselbe Zuordnung kostet nur einen
    Satz im Chat."""
    for figur_id in figur_ids:
        try:
            meldung = erstelle(klm, conn, e, figur_id)
        except Exception:
            log.exception("Sprachprofil fehlgeschlagen, figur_id=%s", figur_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "sprachprofil_fehlgeschlagen",
                    f"Sprachprofil-Aufruf fehlgeschlagen (figur_id={figur_id})",
                )
            except Exception:
                log.exception("Vorfall zum Sprachprofil nicht schreibbar")
            continue
        if meldung:
            _sende_und_merke(conn, tg, e, chat_id, meldung)


def starte(conn, tg, klm, e, chat_id: int, figur_ids: list[int]) -> threading.Thread | None:
    """Gibt die Sprachprofil-Aufrufe an einen eigenen Thread ab und kehrt
    sofort zurueck -- dasselbe Muster wie ``szene.starte`` und
    ``aufnahme.starte_abschluss``.

    Keine Sperre je chat_id wie bei den Szenen: zwei gleichzeitige Laeufe
    schreiben in **verschiedene** Figuren und koennen sich nicht ueberholen,
    und der Aufruf dauert Sekunden, nicht Minuten. Auch keine Ankuendigung --
    die Gruppe hat gerade eine Zuordnung bestaetigt und arbeitet weiter; die
    Meldung kommt, wenn das Profil steht.

    Liefert den Thread (fuer Tests) oder None, wenn nichts anzustossen war."""
    figur_ids = [f for f in figur_ids if f]
    if not figur_ids:
        return None
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, figur_ids), daemon=True,
    )
    thread.start()
    return thread
