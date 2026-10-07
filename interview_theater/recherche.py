"""Internet-Recherche als eigener Materialstrang (Karte t_c5117c91).

Ein zweiter Weg neben dem Interview: die Gruppe fragt nach einem Faktencheck
("war das damals wirklich so?") oder einer Einordnung, der Bot schlaegt drei
Fragen vor (aus Rahmen und Interview-THEMEN -- nie aus Transkripttext, nie aus
Namen, siehe ``_themen``/``baue_nutzertext_fragen``), die Gruppe waehlt eine
oder tippt ihre eigene, und daraus entstehen 2-3 Suchanfragen, eine
Brave-Suche (ueber den Loopback-Such-Broker, ``IT_SUCHE_URL`` --
``einstellungen.py``), 3-5 abgerufene Seiten (ueber den Fetch-Broker,
``FETCH_URL``) und eine Recherchekarte: hoechstens 150 Woerter, Englisch,
jede Aussage mit Quelle.

**Jede Aussage wird gegen den abgerufenen Seitentext geprueft** -- dieselbe
Normalisierung wie bei einem Interview-Belegzitat (``zitat.pruefe``): eine
Aussage ohne verifizierten Beleg wird verworfen, nie angezeigt, nie
gespeichert. Gibt es nach der Pruefung keine einzige Aussage mehr, entsteht
keine Karte (``starte`` liefert ``None``).

**Suchanfragen kommen NIE aus dem Transkript.** ``baue_suchanfragen`` leitet
sie ausschliesslich von der gewaehlten Forschungsfrage ab (die selbst nur aus
Rahmen und Themen-Kurzform entstanden ist, ``_themen`` liest bewusst nur
``verdichtung_thema.thema``, nie ``beleg_zitat``) -- ein woertliches Zitat
einer interviewten Person darf nie an einen Suchdienst gehen.

Modell: das Gespraechsmodell (``art="recherche"``, Padua: Opus) -- der Input
ist oeffentlicher Webtext plus Themen, keine Rohdaten aus dem Interview."""

import logging
import re

import httpx

from interview_theater import repo, zitat

log = logging.getLogger(__name__)

#: Der Fetch-Broker (Hermes-Profil-Repo, deploy/fetch-broker/): Egress ohne
#: Wissen -- er haelt keine Gruppendaten, interview_theater haelt keinen
#: Netzzugriff auf das offene Web (docs/refactoring-guidelines.md Punkt 7,
#: Profil-Repo). Loopback-only, fest verdrahtet wie beim Fetch-Broker selbst.
FETCH_URL = "http://127.0.0.1:8788/fetch"

#: Hoechstens so viele Suchanfragen je Recherche (Produktvorgabe: 2-3).
MAX_ANFRAGEN = 3
#: Hoechstens so viele abgerufene Seiten je Recherche (Produktvorgabe: 3-5).
MAX_SEITEN = 5
#: So viele Treffer je Suchanfrage werden angefordert.
TREFFER_JE_ANFRAGE = 5

SCHEMA_FRAGEN = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fragen"],
    "properties": {
        "fragen": {"type": "array", "items": {"type": "string"}},
    },
}

SCHEMA_KARTE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["aussagen"],
    "properties": {
        "aussagen": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "beleg", "quelle_index"],
                "properties": {
                    "text": {"type": "string"},
                    "beleg": {"type": "string"},
                    "quelle_index": {"type": "integer"},
                },
            },
        },
    },
}

#: Woerter, die eine Suchanfrage nicht praeziser machen -- fuer die zweite,
#: stichwortartige Anfragevariante (``baue_suchanfragen``).
_STOPPWOERTER = frozenset({
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "is", "are",
    "was", "were", "did", "does", "do", "what", "when", "how", "who",
    "which", "that", "this", "it", "with", "about", "did",
})

_WORT = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+")

#: Erkennt ein Datum im abgerufenen Seitentext -- "Datum, wenn gefunden"
#: (Produktvorgabe); ohne Treffer bleibt die Quelle ohne Datumsfeld.
_DATUM_ISO = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
_MONATE = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)
_DATUM_LANG = re.compile(
    r"\b(?:" + "|".join(_MONATE) + r")\s+\d{1,2},?\s+(?:19|20)\d{2}\b"
)


def prompt_fragen() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    from interview_theater import anweisungen

    return anweisungen.hole("recherche_fragen")


def prompt_karte() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    from interview_theater import anweisungen

    return anweisungen.hole("recherche_karte")


def _themen(conn, chat_id: int) -> list[str]:
    """Nur die Themen-Kurzform (``verdichtung_thema.thema``) ueber alle
    Verdichtungen der Gruppe -- NIE das Belegzitat: das ist woertlicher
    Transkripttext, und eine Forschungsfrage darf nie etwas daraus tragen."""
    themen: list[str] = []
    for v in repo.verdichtungen(conn, chat_id):
        for thema in repo.themen_zu(conn, v["id"]):
            text = (thema["thema"] or "").strip()
            if text and text not in themen:
                themen.append(text)
    return themen


def baue_nutzertext_fragen(conn, chat_id: int) -> str:
    """Der Nutzertext fuer den Fragenvorschlag: Rahmen, Geschichte (falls
    gesetzt) und Themen-Kurzform -- nie Transkripte, nie Namen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    rahmen = (stand["rahmen"] or "").strip() if stand else ""
    geschichte = (stand["geschichte"] or "").strip() if stand else ""
    themen = _themen(conn, chat_id)
    teile = []
    if rahmen:
        teile.append(f"Frame: {rahmen}")
    if geschichte:
        teile.append(f"Story so far: {geschichte}")
    if themen:
        teile.append("Themes from the interviews: " + "; ".join(themen))
    return "\n".join(teile) or "No frame or themes recorded yet."


def schlage_fragen_vor(klm, conn, e, chat_id: int) -> list[str]:
    """Bis zu drei Forschungsfragen, abgeleitet aus Rahmen und Themen
    (nie aus Transkripttext)."""
    ergebnis = klm.schema(
        chat_id, prompt_fragen(), baue_nutzertext_fragen(conn, chat_id),
        SCHEMA_FRAGEN, "recherche",
    )
    fragen = [f.strip() for f in ergebnis.get("fragen", []) if (f or "").strip()]
    return fragen[:3]


def baue_suchanfragen(frage: str) -> list[str]:
    """2-3 Suchanfragen aus der gewaehlten Forschungsfrage -- ausschliesslich
    aus ``frage`` abgeleitet, nie aus einem Transkript (die Frage selbst
    stammt nur aus Rahmen/Themen, siehe Moduldocstring)."""
    frage = (frage or "").strip()
    if not frage:
        return []
    anfragen = [frage]
    schluesselwoerter = " ".join(
        w for w in _WORT.findall(frage) if w.lower() not in _STOPPWOERTER
    )
    if schluesselwoerter and schluesselwoerter.lower() != frage.lower():
        anfragen.append(schluesselwoerter)
    zusatz = f"{frage} fact check"
    if zusatz not in anfragen:
        anfragen.append(zusatz)
    ergebnis = []
    for a in anfragen:
        if a and a not in ergebnis:
            ergebnis.append(a)
    return ergebnis[:MAX_ANFRAGEN]


def suche(query: str, anzahl: int, suche_url: str) -> list[dict]:
    """Ruft den Loopback-Such-Broker (``IT_SUCHE_URL``). Liefert eine leere
    Liste bei jedem Fehler -- eine fehlgeschlagene Teilsuche darf die
    Recherche nicht abbrechen, nur magerer machen."""
    try:
        antwort = httpx.post(suche_url, json={"q": query, "count": anzahl}, timeout=15.0)
        antwort.raise_for_status()
        daten = antwort.json()
    except (httpx.HTTPError, ValueError) as fehler:
        log.warning("Suche fehlgeschlagen, query=%r: %s", query, fehler)
        return []
    return daten if isinstance(daten, list) else []


def hole_seite(url: str) -> dict | None:
    """Ruft den Fetch-Broker (``FETCH_URL``, loopback-only). ``None`` bei
    jedem Fehler -- dieselbe Nachsicht wie bei ``suche``."""
    try:
        antwort = httpx.post(FETCH_URL, json={"url": url}, timeout=30.0)
        antwort.raise_for_status()
        daten = antwort.json()
    except (httpx.HTTPError, ValueError) as fehler:
        log.warning("Seitenabruf fehlgeschlagen, url=%r: %s", url, fehler)
        return None
    return daten if isinstance(daten, dict) else None


def _extrahiere_datum(text: str) -> str | None:
    treffer = _DATUM_ISO.search(text or "")
    if treffer:
        return treffer.group(0)
    treffer = _DATUM_LANG.search(text or "")
    return treffer.group(0) if treffer else None


def _baue_nutzertext_karte(frage: str, seiten: list[dict]) -> str:
    teile = [f"Research question: {frage}", "", "Fetched sources:"]
    for i, seite in enumerate(seiten):
        inhalt = (seite.get("content") or seite.get("raw_content") or "")[:4000]
        titel = seite.get("title") or seite.get("url")
        teile.append(f"[{i}] {titel} ({seite.get('url')})\n{inhalt}")
    return "\n\n".join(teile)


def starte(
    klm, conn, e, chat_id: int, frage: str,
    suche_fn=None, hole_fn=None,
) -> int | None:
    """Fuehrt die ganze Recherche aus: Suchanfragen, Brave-Suche, Seitenabruf,
    Kartenbau, Zitat-Verifikation je Aussage, Speichern.

    ``suche_fn(query, anzahl) -> list[dict]`` und ``hole_fn(url) -> dict |
    None`` sind austauschbar (Tests setzen Attrappen statt echtem Netz;
    ohne Angabe ``suche``/``hole_seite`` ueber ``e.suche_url``).

    Liefert die id der gespeicherten Recherche, oder ``None`` -- ohne jeden
    Treffer, ohne jede abrufbare Seite, oder wenn keine einzige Aussage die
    Zitat-Pruefung ueberlebt (lieber keine Karte als eine mit erfundenen
    Belegen, wie bei ``verdichter.verdichte``)."""
    if suche_fn is None:
        suche_url = getattr(e, "suche_url", None) or "http://127.0.0.1:8789/search"
        suche_fn = lambda q, n: suche(q, n, suche_url)  # noqa: E731
    if hole_fn is None:
        hole_fn = hole_seite

    treffer = []
    gesehene_urls: set[str] = set()
    for anfrage in baue_suchanfragen(frage):
        for t in suche_fn(anfrage, TREFFER_JE_ANFRAGE) or []:
            url = (t.get("url") or "").strip()
            if url and url not in gesehene_urls:
                gesehene_urls.add(url)
                treffer.append(t)

    seiten = []
    for t in treffer:
        if len(seiten) >= MAX_SEITEN:
            break
        seite = hole_fn(t["url"])
        if seite and (seite.get("content") or seite.get("raw_content")):
            seiten.append({**seite, "_treffertitel": t.get("title")})
    if not seiten:
        return None

    ergebnis = klm.schema(
        chat_id, prompt_karte(), _baue_nutzertext_karte(frage, seiten),
        SCHEMA_KARTE, "recherche",
    )

    aussagen_text = []
    quellen = []
    for aussage in ergebnis.get("aussagen", []):
        idx = aussage.get("quelle_index")
        beleg = (aussage.get("beleg") or "").strip()
        text = (aussage.get("text") or "").strip()
        if not text or not beleg or not isinstance(idx, int) or not (0 <= idx < len(seiten)):
            continue
        seite = seiten[idx]
        roh = seite.get("raw_content") or seite.get("content") or ""
        if not zitat.pruefe(beleg, roh):
            continue
        titel = seite.get("title") or seite.get("_treffertitel") or seite["url"]
        quelle = {"titel": titel, "url": seite["url"]}
        datum = _extrahiere_datum(roh)
        if datum:
            quelle["datum"] = datum
        quellenangabe = f"{titel}, {quelle['url']}" + (f", {datum}" if datum else "")
        aussagen_text.append(f"{text} ({quellenangabe})")
        quellen.append(quelle)

    if not aussagen_text:
        return None

    return repo.speichere_recherche(conn, chat_id, frage, " ".join(aussagen_text), quellen)
