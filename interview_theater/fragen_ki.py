"""Aufgabe 12 (Padua Phase 1+2 Umbau, 03.10.2026): die isolierten KI-Fragen
fuer den A/B-Vergleich eigene-vs-KI-Fragen in Phase 2.

Birk: "wie man das hinbekommt, dass die KI eigene Fragen entwickelt, ohne
dass die Fragen von den Studierenden uebernommen werden. Also es soll
wirklich ein sauberer A-B-Vergleich sein. [...] dass die Fragen von der KI
im Hintergrund schon entwickelt werden, bevor die Fragen von den Usern
eingesprochen werden, weil sonst weiss die KI ja die Fragen der User."
(AB-AENDERUNG-PHASE2.md).

**Beim Eintritt in Phase 2, nicht danach.** ``starte`` laeuft aus
``knoepfe/stationen.py::eintritt_in_phase`` an -- noch bevor die Gruppe eine
einzige eigene Frage geschrieben hat. Gespeichert wird sofort mit
Zeitstempel (``fragen_ki_erzeugt_am``), aber fuer die Gruppe versteckt, bis
die Gegenueberstellung so weit ist (Aufgabe 13).

**Kontext-Isolation per Code, nicht per Prompt** (AB-AENDERUNG-PHASE2.md
Punkt 2): ``_nutzertext`` nimmt NUR ``begriffe``/``diskussion_text`` als
Klartext entgegen -- keine ``conn``, keine ``chat_id`` in der Signatur.
Dieser Aufruf kann strukturell nichts anderes sehen als die Begriffe und,
falls vorhanden, die Verdichtung der Phase-1-Hintergrunddiskussion -- kein
``kontext.baue``, kein Phase-2-Chatfenster, keine eigene Frage der Gruppe.

**Kein Nachbessern** (Punkt 3): einmal erzeugt, bleibt
``fragen_ki_vorschlag`` stehen. Faellt der Hintergrundlauf aus, bleibt das
Feld leer, und ein spaeterer Aufruf von ``starte`` (z.B. ein erneuter
Phase-2-Eintritt) ist damit automatisch ein zulaessiger Retry -- derselbe
isolierte Nutzertext, keine zusaetzliche Wiederholungslogik noetig.

Nach einem erfolgreichen, nicht-leeren Lauf wird
``knoepfe.fragen.versuche_gegenueberstellung`` angestossen (Aufgabe 13, noch
nicht gebaut): sie prueft, ob BEIDE Seiten -- KI und Gruppe -- fertig sind,
und zeigt dann die Gegenueberstellung. Ein gescheiterter oder leerer Lauf
ruft sie nicht auf, weil die Gegenueberstellung ohne echten KI-Inhalt
nichts zu vergleichen haette.

**Dasselbe Sperrenmuster wie ``diskussion.py``** (``versuche_start``/
``beende``), hier bewusst noch einmal geschrieben statt importiert: eine
gemeinsame Sperre wuerde die Hintergrund-Diskussion (Phase 1) und die
KI-Fragen (Phase 2) aneinanderketten, obwohl die beiden nie gleichzeitig
eine Gruppe betreffen (docs/agents/aufbau.md: "Gleicher Code, verschiedene Sperren")."""

import logging
import threading

from interview_theater import anweisungen, modellwahl, repo, sprache, workshop
from interview_theater import begriffe as begriffe_modul

log = logging.getLogger(__name__)

#: Framing-Zeilen des isolierten Nutzertexts -- ueber ``T`` sprachabhaengig
#: (Karte A1): ein englischsprachiger Workshop (z.B. Padua) darf im
#: Modellaufruf keinen deutschen Satz sehen, auch nicht als blosse
#: Ueberschrift (``tests/test_pruefe_sprache.py::test_padua_ist_frei_von_deutsch``).
#: Die englische Fassung steht in ``sprachen/en/texte.toml`` unter
#: ``["fragen_ki"]``.
_BEGRIFFE_KOPF = "Die Begriffe der Gruppe:"
_DISKUSSION_KOPF = (
    "Verdichtung einer vorangegangenen Diskussion der Gruppe (nur "
    "Hintergrund, kein Diktat):"
)
_BEGRUENDUNG_KOPF = "Warum die Gruppe diese Begriffe gewaehlt hat:"
_ANZAHL_ZEILE = "Fragen je Begriff: {n}"

#: Live Padua 05.10.2026 (G3, ein einziger Begriff): die Zahl der KI-Fragen
#: je Begriff war fest drei. Seit die Zahl der Begriffe frei ist, ergibt sich
#: die Zahl je Begriff aus einem Ziel fuer die GESAMTZAHL -- ein Begriff
#: bekommt mehr, viele Begriffe bekommen weniger je Begriff.
ZIEL_GESAMT = 12
MIN_JE_BEGRIFF = 2
MAX_JE_BEGRIFF = 8


def fragen_je_begriff(anzahl_begriffe: int) -> int:
    if anzahl_begriffe <= 0:
        return 0
    n = round(ZIEL_GESAMT / anzahl_begriffe)
    return max(MIN_JE_BEGRIFF, min(MAX_JE_BEGRIFF, n))
T = sprache.Texte(__name__)

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["antwort"],
    "properties": {
        "antwort": {"type": "string"},
    },
}

ART = "fragen_ki_vorschlag"


def _nutzertext(begriffe: str, diskussion_text: str | None,
                begriffe_detail: list[dict] | None = None) -> str:
    """Der isolierte Nutzertext -- NUR die Begriffe, ihre Begruendungen aus
    dem Begriffsboard (Karte t_4517d4ad, ohne Zitat) und, falls vorhanden,
    die Verdichtung einer vorangegangenen Diskussion. Kein ``conn``, keine
    ``chat_id`` in der Signatur: dieser Aufruf kann strukturell nichts
    anderes sehen, insbesondere keine eigene Frage der Gruppe."""
    from interview_theater import begriffsboard

    liste = begriffe_modul.zerlege(begriffe)
    text = T._BEGRIFFE_KOPF + "\n" + "\n".join(f"- {b}" for b in liste)
    text += "\n\n" + T._ANZAHL_ZEILE.format(n=fragen_je_begriff(len(liste)))
    zeilen = begriffsboard.detail_zeilen(begriffe_detail or [])
    if zeilen:
        text += "\n\n" + T._BEGRUENDUNG_KOPF + "\n" + "\n".join(zeilen)
    if diskussion_text and diskussion_text.strip():
        text += "\n\n" + T._DISKUSSION_KOPF + "\n" + diskussion_text.strip()
    return text


#: Ein Sperren-Register je Nebenlaeufigkeit (docs/agents/aufbau.md: "Gleicher Code,
#: verschiedene Sperren"), in Form kopiert aus ``diskussion.py``: nie mehr
#: als ein KI-Fragen-Lauf je Gruppe gleichzeitig.
_LAEUFT_LOCK = threading.Lock()
_LAEUFT: set[int] = set()


def versuche_start(chat_id: int) -> bool:
    """True und merkt sich den Lauf, wenn fuer diese Gruppe gerade KEIN
    KI-Fragen-Lauf laeuft -- sonst False, ohne etwas zu veraendern."""
    with _LAEUFT_LOCK:
        if chat_id in _LAEUFT:
            return False
        _LAEUFT.add(chat_id)
        return True


def beende(chat_id: int) -> None:
    """Gibt die Sperre wieder frei -- immer in einem ``finally``, auch nach
    einem Fehlschlag oder einem fruehen Abbruch vor dem Thread-Start."""
    with _LAEUFT_LOCK:
        _LAEUFT.discard(chat_id)


def _melde_fehler(conn, e, chat_id: int, detail: str) -> None:
    """Schreibt den ``fragen_ki_fehler``-Vorfall fuers Dashboard (SPEC § 11.1:
    ein gescheiterter Hintergrundlauf ist fuer die Gruppe unsichtbar, aber
    nicht fuer den Vorfall). Gemeinsamer Weg fuer BEIDE Fehlerarten -- eine
    Ausnahme UND eine "erfolgreiche", aber leere/unbrauchbare Modellantwort
    sind aus Sicht des Dashboards derselbe Fall: kein KI-Fragen-Vorschlag ist
    entstanden. Das Logging selbst bleibt beim Aufrufer (``log.exception`` mit
    Traceback bei einer echten Ausnahme, ``log.warning`` ohne bei einer
    leeren Antwort) -- nur das Schreiben des Vorfalls ist hier gemeinsam."""
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "fragen_ki_fehler", detail,
        )
    except Exception:
        log.exception(
            "Vorfall fragen_ki_fehler nicht geschrieben, chat_id=%s", chat_id,
        )


def _hat_vorschlag(stand) -> bool:
    """Steht ein brauchbarer KI-Vorschlag? Ein Feld ohne eine einzige
    Fragezeile (``vorschlag.zeilen`` leer) zaehlt nicht: aus ihm entsteht
    keine Gegenueberstellung, und ohne neuen Lauf bliebe die Gruppe in der
    Wartezeile haengen (Review T2)."""
    from interview_theater import vorschlag

    if stand is None:
        return False
    zeilen = vorschlag.zeilen(stand["fragen_ki_vorschlag"] or "")
    if not zeilen:
        return False
    return passt_zu_begriffen(stand["begriffe"] or "", zeilen)


def passt_zu_begriffen(begriffe_feld: str, zeilen: list[str]) -> bool:
    """Deckt der KI-Vorschlag JEDEN aktuellen Begriff mit mindestens einer
    Frage ab? Live Padua 05.10.2026 (G3): der Lauf entstand beim Eintritt in
    Phase 2 auf fuenf Begriffen, danach reduzierte die Gruppe auf EINEN
    neuen -- die Gegenueberstellung zeigte trotzdem die Fragen zu den
    verworfenen Begriffen. Ein Vorschlag, der die jetzigen Begriffe nicht
    abdeckt, ist veraltet und wird neu erzeugt."""
    from interview_theater.knoepfe.fragen import _ordne_zeilen

    begriffe = begriffe_modul.zerlege(begriffe_feld)
    if not begriffe:
        return True
    je_begriff, rest = _ordne_zeilen(begriffe, zeilen)
    # Veraltet heisst: ein jetziger Begriff hat keine einzige Frage UND der
    # Vorschlag traegt Fragen zu Begriffen, die es nicht mehr gibt (``rest``).
    # Nur eines davon reicht nicht -- ein Modell, das zu einem Begriff
    # nichts lieferte, ist kein Grund fuer einen zweiten bezahlten Lauf.
    return not (rest and any(not je_begriff.get(b) for b in begriffe))


def starte(conn, tg, klm, e, chat_id: int) -> bool:
    """Stoesst den EINEN isolierten KI-Fragen-Lauf dieser Gruppe an.

    Kein Modellaufruf hier selbst (Zusage 2): der eigentliche Aufruf laeuft
    in einem eigenen Thread. Diese Funktion prueft nur, ob ueberhaupt etwas
    zu tun ist, und gibt die Sperre selbst zurueck, wenn sie es doch nicht
    ist -- sonst gaebe niemand sie je wieder frei.

    Idempotent (kein Nachbessern): ist ``fragen_ki_vorschlag`` schon
    gesetzt, passiert nichts -- weder ein zweiter Modellaufruf noch eine
    Aenderung des gespeicherten Werts.

    Liefert True, wenn ein Lauf angestossen wurde (Feedbackloop P1-2, R-3:
    der Knopf "Yes, suggest some" holt einen beim Eintritt gescheiterten Lauf
    ueber genau diese Funktion nach -- nie doppelt, weil ein laufender Lauf
    die Sperre haelt)."""
    if klm is None:
        return False
    if not workshop.fragen_ab_aktiv():
        return False

    stand = repo.hole_arbeitsstand(conn, chat_id)
    if _hat_vorschlag(stand):
        return False

    if not versuche_start(chat_id):
        return False
    # Review T2: zwischen Lesen und Sperre kann ein anderer Lauf fertig
    # geworden sein -- nach der Sperre neu lesen, sonst zahlt ein zweiter.
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if _hat_vorschlag(stand):
        beende(chat_id)
        return False

    begriffe_feld = stand["begriffe"] if stand is not None else None
    diskussion_text = repo.diskussion_verdichtung_text(conn, chat_id)
    from interview_theater import roadmap

    begriffe_detail = roadmap.begriffe_detail(stand)

    def _lauf() -> None:
        try:
            nutzertext = _nutzertext(begriffe_feld or "", diskussion_text, begriffe_detail)
            ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
            ergebnis = modellwahl.aufruf_schema(
                conn, klm, e, chat_id,
                system=anweisungen.hole("fragen_ki_vorschlag"),
                nutzer=nutzertext, schema=SCHEMA, art=ART,
                ueber_claude=ueber_claude,
            )
            antwort = (ergebnis.get("antwort") or "").strip()
            if not antwort:
                # Eine "erfolgreiche", aber leere/unbrauchbare Antwort ist
                # kein stiller Fall: ohne Vorfall saehe das Dashboard einen
                # Lauf, der nie etwas ergab, als haette er nie stattgefunden
                # (Review-Befund, Task 12). Kein Schreiben, kein Reveal-
                # Aufruf -- derselbe Weg wie bei einer Ausnahme.
                log.warning("KI-Fragen-Lauf lieferte eine leere Antwort, chat_id=%s", chat_id)
                _melde_fehler(conn, e, chat_id, f"Leere Antwort fuer chat_id={chat_id}")
                return
            repo.setze_arbeitsstand(conn, chat_id, "fragen_ki_vorschlag", antwort)
            repo.setze_arbeitsstand(
                conn, chat_id, "fragen_ki_erzeugt_am", repo._jetzt(),
            )

            # Review-Hinweis (Task 12, Minor): solange Aufgabe 13 nicht
            # gebaut ist, wirft dieser Aufruf ein AttributeError, das vom
            # ``except Exception`` unten aufgefangen wird -- NACHDEM die
            # beiden Felder oben schon geschrieben sind. Ein wirklich
            # erfolgreicher Lauf traegt also bis zur Aufgabe-13-Landung
            # zusaetzlich einen spurious ``fragen_ki_fehler``-Vorfall. Das
            # ist akzeptiert und nur fuer dieses Zwischenstadium wahr: der
            # Profilschalter (``fragen_ab.aktiv``) steht fuer Dortmund und
            # jedes bestehende Profil auf False, also kann das heute
            # nirgends auftreten.
            from interview_theater.knoepfe import fragen as fragen_modul

            fragen_modul.versuche_gegenueberstellung(conn, tg, chat_id)
        except Exception:
            log.exception("KI-Fragen-Lauf fehlgeschlagen, chat_id=%s", chat_id)
            _melde_fehler(
                conn, e, chat_id,
                f"KI-Fragen-Lauf fehlgeschlagen fuer chat_id={chat_id}",
            )
        finally:
            beende(chat_id)

    threading.Thread(target=_lauf, daemon=True).start()
    return True
