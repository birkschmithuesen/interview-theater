"""Die Kurzform einer Szene (Birk, Live-Workshop 07.10.2026 ~17:45:
"Reduktion auf das Wesentliche. Fokus halten."), Padua-Profilschalter
``[skript] verdichtet`` (``workshop.skript_verdichtet_aktiv``).

Bis hierher haengte ``schaerfung._ergaenze_szene`` jede uebernommene
Interviewstelle an ``szene.was_passiert`` (Begruendung) und
``szene.kernsaetze`` (Zitat) -- G1 Szene 2 kam so auf 3.849 bzw. 7.332
Zeichen, unlesbar im Script-Tab und Brei im Prosa-Prompt. Jetzt:

* ``was_passiert`` bleibt die Beschreibung der Gruppe; die Begruendungen
  bleiben an den ``schaerfung``-Zeilen. Fuer Altbestand liefert
  ``gruppenbeschreibung`` die Beschreibung ohne die angehaengte Kette
  (deterministisch, kein Modell).
* ``szene.kern`` -- 3 bis 6 Punkte "worum es in der Szene geht" -- und
  ``szene.kernsaetze_kurz`` -- die 5 staerksten uebernommenen Zitate --
  entstehen in EINEM Schema-Aufruf je Szene (``verdichte``). Das Modell
  waehlt die Zitate nur per Nummer; der Wortlaut kommt aus der Datenbank,
  ein erfundenes oder verbogenes Zitat ist damit ausgeschlossen.
* ``szene.kern_quelle`` haelt den Fingerabdruck der Eingabe: steht sie
  unveraendert, laeuft kein zweiter Aufruf (Kostendeckel).

Ausgeloest im Thread (``starte``, Zusage 2: kein Modellaufruf in Knopf-
oder Erkenner-Handlern) nach "Done" in der Sortierliste und nach einer
Aenderung der Szene im Chat. **Fehler = altes Verhalten**: die Anzeige
faellt auf die gekappte Liste zurueck, der Prompt auf die bereinigte
Beschreibung."""

from __future__ import annotations

import hashlib
import logging
import threading

from interview_theater import anweisungen, modellwahl, repo, szene_claude, workshop

log = logging.getLogger(__name__)

#: Erkenner-art in der Tabelle ``aufruf`` und Name der Prompt-Datei.
ART = "szenenkern"

KERN_MIN = 3
KERN_MAX = 6
KERN_ZEICHEN = 160
ZITATE_MAX = 5
#: So viele Zeichen eines Zitats gehen in den Nutzertext (Auswahl, nicht
#: Wortlaut -- gespeichert wird das volle Zitat aus der Datenbank).
ZITAT_ZEICHEN_PROMPT = 400

SCHEMA = {
    "type": "object",
    "properties": {
        "kern": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "3 to 6 short bullet points: what this scene is about and "
                "what happens in it, in the group's language, each under "
                "160 characters. No interview numbers, no reasons."
            ),
        },
        "zitate": {
            "type": "array",
            "items": {"type": "integer"},
            "description": (
                "The numbers of at most 5 lines from the list that carry this "
                "scene most strongly, strongest first. Only numbers from the list."
            ),
        },
    },
    "required": ["kern", "zitate"],
    "additionalProperties": False,
}


def aktiv() -> bool:
    return workshop.skript_verdichtet_aktiv()


def uebernommene(conn, chat_id: int, szene_id: int) -> list:
    """Die von der Gruppe uebernommenen Interviewstellen dieser Szene, in
    ihrer Reihenfolge -- nicht die bloss zugeordneten (G1 Szene 2: 163
    zugeordnet, 53 uebernommen)."""
    return [
        z for z in repo.schaerfungen(conn, chat_id, szene_id=szene_id)
        if z["uebernommen_am"]
    ]


def _begruendungen(conn, chat_id: int, szene_id: int) -> list[str]:
    """Was ``_ergaenze_szene`` frueher angehaengt hat: je Stelle die
    Begruendung, ersatzweise das Thema."""
    texte = []
    for z in uebernommene(conn, chat_id, szene_id):
        text = (z["begruendung"] or z["thema"] or "").strip()
        if text:
            texte.append(text)
    return texte


def bereinige_beschreibung(text: str | None, begruendungen: list[str]) -> str:
    """``was_passiert`` ohne die angehaengte Begruendungskette -- rein, ohne
    Datenbank (die Weboberflaeche liest read-only und ruft das direkt).

    Jede Begruendung fliegt samt ihrem ``"; "``-Trenner heraus, die
    laengsten zuerst (eine kurze koennte Teil einer langen sein). Was
    bleibt, ist der Satz der Gruppe."""
    text = (text or "").strip()
    if not text:
        return ""
    for b in sorted({b.strip() for b in begruendungen if b and b.strip()},
                    key=len, reverse=True):
        for muster in ("; " + b, b + "; ", " " + b, b):
            if muster in text:
                text = text.replace(muster, "", 1)
                break
    return " ".join(text.split()).strip(" ;")


def bereinige_kernsaetze(text: str | None, zitate: list[str]) -> list[str]:
    """Die eigenen Kernsaetze der Gruppe -- ohne die Zitate, die
    ``_ergaenze_szene`` frueher mit ``" | "`` angehaengt hat."""
    weg = {" ".join(str(z or "").split()) for z in zitate}
    return [
        t.strip() for t in (text or "").split("|")
        if t.strip() and " ".join(t.split()) not in weg
    ]


def gruppenbeschreibung(conn, chat_id: int, szene) -> str:
    return bereinige_beschreibung(
        szene["was_passiert"], _begruendungen(conn, chat_id, szene["id"]),
    )


def gruppen_kernsaetze(conn, chat_id: int, szene) -> list[str]:
    """Die Zitate stehen an den ``schaerfung``-Zeilen und gehen als
    Kernpaket woertlich mit -- hier bleibt nur, was die Gruppe selbst
    gesetzt hat."""
    return bereinige_kernsaetze(
        szene["kernsaetze"],
        [z["zitat"] for z in repo.schaerfungen(conn, chat_id, szene_id=szene["id"])],
    )


def zeilen(roh: str | None) -> list[str]:
    return [z.strip() for z in (roh or "").splitlines() if z.strip()]


def kern_punkte(szene) -> list[str]:
    return zeilen(szene["kern"])


def kernsaetze_kurz(szene) -> list[str]:
    return zeilen(szene["kernsaetze_kurz"])


def _kandidaten(conn, chat_id: int, szene) -> list[tuple[str, str]]:
    """Die Zitate zur Wahl: ``(zitat, interview)`` -- erst die uebernommenen
    Stellen, dann die eigenen Kernsaetze der Gruppe (ohne Interview)."""
    from interview_theater import kontext

    liste: list[tuple[str, str]] = []
    gesehen: set[str] = set()
    for z in uebernommene(conn, chat_id, szene["id"]):
        zitat = " ".join(str(z["zitat"] or "").split())
        if zitat and zitat not in gesehen:
            gesehen.add(zitat)
            liste.append((zitat, kontext.interviewbezeichnung(conn, chat_id, z["aufnahme_id"])))
    for satz in gruppen_kernsaetze(conn, chat_id, szene):
        satz = " ".join(satz.split())
        if satz not in gesehen:
            gesehen.add(satz)
            liste.append((satz, ""))
    return liste


def zitatzeile(zitat: str, interview: str) -> str:
    return f'"{zitat}" ({interview})' if interview else f'"{zitat}"'


def baue_nutzertext(conn, chat_id: int, szene) -> str:
    """Setting, Format, die Szene (Titel, Beschreibung der Gruppe), dann die
    Liste zur Wahl -- mit Thema und Begruendung als Hilfe, die aber nicht
    gespeichert wird."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    zeilen = []
    if stand is not None:
        for feld, kopf in (("rahmen", T._KOPF_SETTING), ("format", T._KOPF_FORMAT)):
            if feld in stand.keys() and (stand[feld] or "").strip():
                zeilen.append(f"{kopf} {stand[feld].strip()}")
    zeilen.append(T._KOPF_SZENE.format(nummer=szene["nummer"], titel=szene["titel"] or ""))
    beschreibung = gruppenbeschreibung(conn, chat_id, szene)
    if beschreibung:
        zeilen.append(T._KOPF_BESCHREIBUNG + " " + beschreibung)
    zeilen.append("")
    zeilen.append(T._KOPF_LISTE)
    stellen = {
        " ".join(str(z["zitat"] or "").split()): z
        for z in uebernommene(conn, chat_id, szene["id"])
    }
    for n, (zitat, interview) in enumerate(_kandidaten(conn, chat_id, szene), start=1):
        zeile = f"[{n}] {zitatzeile(zitat[:ZITAT_ZEICHEN_PROMPT], interview)}"
        z = stellen.get(zitat)
        if z is not None:
            hilfe = " -- ".join(
                t for t in ((z["thema"] or "").strip(), (z["begruendung"] or "").strip()) if t
            )
            if hilfe:
                zeile += f" -- {hilfe}"
        zeilen.append(zeile)
    return "\n".join(zeilen)


def fingerabdruck(nutzertext: str) -> str:
    return hashlib.sha1(nutzertext.encode("utf-8")).hexdigest()


def _kappe(text: str) -> str:
    text = " ".join(str(text).split())
    if len(text) <= KERN_ZEICHEN:
        return text
    return text[:KERN_ZEICHEN].rsplit(" ", 1)[0].rstrip(" ,;:-") + " …"


def verdichte(conn, klm, e, chat_id: int, szene_id: int) -> bool:
    """Der EINE Modellaufruf je Szene. ``True`` bei Erfolg oder wenn die
    Eingabe unveraendert ist; ``False`` bei jedem Fehler (geloggt, als
    Vorfall vermerkt, nie geworfen) -- dann bleibt die alte Kurzform bzw.
    die Rueckfallanzeige stehen."""
    szene = repo.hole_szene(conn, szene_id)
    if szene is None or szene["nummer"] is None:
        return False
    nutzer = baue_nutzertext(conn, chat_id, szene)
    abdruck = fingerabdruck(nutzer)
    if szene["kern_quelle"] == abdruck and (szene["kern"] or "").strip():
        return True
    kandidaten = _kandidaten(conn, chat_id, szene)
    try:
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id,
            system=anweisungen.hole(ART), nutzer=nutzer, schema=SCHEMA, art=ART,
            ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id),
        )
        punkte = [_kappe(p) for p in (ergebnis.get("kern") or []) if str(p).strip()]
        if not punkte:
            raise ValueError("Kurzform ohne Punkte zurueckgekommen")
        punkte = punkte[:KERN_MAX]
        gewaehlt: list[int] = []
        for n in ergebnis.get("zitate") or []:
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= len(kandidaten) and n not in gewaehlt:
                gewaehlt.append(n)
        gewaehlt = gewaehlt[:ZITATE_MAX]
    except Exception:
        log.exception("Szenen-Kurzform fehlgeschlagen, chat_id=%s, szene_id=%s",
                      chat_id, szene_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), "szenenkern_fehler",
                f"Szene {szene['nummer']}: Kurzform nicht erzeugt -- alte Anzeige bleibt",
            )
        except Exception:
            log.exception("Vorfall szenenkern_fehler nicht geschrieben")
        return False
    zitate = "\n".join(zitatzeile(*kandidaten[n - 1]) for n in gewaehlt)
    repo.setze_szenenkern(conn, szene_id, "\n".join(punkte), zitate, abdruck)
    return True


_SPERREN: dict[int, threading.Lock] = {}
_SPERREN_LOCK = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _SPERREN_LOCK:
        return _SPERREN.setdefault(chat_id, threading.Lock())


def starte(conn, klm, e, chat_id: int, szene_ids: list[int] | None = None):
    """Verdichtet die genannten Szenen (ohne Angabe: alle nummerierten) in
    EINEM Thread, seriell (Infomaniak drosselt Parallelitaet). Mehrere
    Ausloeser hintereinander warten aufeinander; der Fingerabdruck sorgt
    dafuer, dass der zweite nichts doppelt bezahlt. Ohne Schalter oder ohne
    Sprachmodell: nichts."""
    if not aktiv() or klm is None:
        return None

    def _lauf() -> None:
        with _sperre_fuer(chat_id):
            ids = szene_ids
            if ids is None:
                ids = [
                    s["id"] for s in repo.hole_szenen(conn, chat_id)
                    if s["nummer"] is not None and not s["entfernt_am"]
                ]
            for szene_id in ids:
                try:
                    verdichte(conn, klm, e, chat_id, szene_id)
                except Exception:
                    log.exception("Szenen-Kurzform abgebrochen, szene_id=%s", szene_id)

    thread = threading.Thread(target=_lauf, daemon=True)
    thread.start()
    return thread


#: Die Koepfe des Nutzertexts (W3: Sprache des Profils).
_KOPF_SETTING = "Setting:"
_KOPF_FORMAT = "Format:"
_KOPF_SZENE = "Szene {nummer}: {titel}"
_KOPF_BESCHREIBUNG = "Was die Gruppe beschrieben hat:"
_KOPF_LISTE = "Zitate zur Wahl (nach Nummer):"


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
