"""Der Chat im Browser (30.09.2026, Karte Padua A2).

Die Gegenseite zu ``web_kanal.py``: dort schreibt der Bot in ``web_post``,
hier liest der Browser es. **Eigenes Modul und nicht in ``web.py``**, weil
``web.py`` ein Kollisions-Hotspot mit Karte A1 ist -- dort stehen nur die
Routing-Zeilen, alles andere (HTML, CSS, JS, Handler) liegt hier.

**Kein SQL, kein Modell.** Gelesen wird ueber ``web_daten`` (read-only),
geschrieben ueber ``repo`` (Aufgaben 7-10). Der Webserver hat keinen
Modellklienten und soll keinen bekommen.

**Der HTML-Filter ist der Kern.** Bot-Ausgaben tragen Telegram-HTML
(``parse_mode="HTML"``, fuenf Stellen im Repo, u. a. ``vorschlag.menuetext``):
die Ansicht muss es darstellen und darf nichts anderes durchlassen. Der Weg
ist bewusst der langweilige: **alles maskieren, dann eine geschlossene Liste
wieder zulassen** -- nicht "das Gefaehrliche entfernen".
"""

import html
import json
import os
import re
import urllib.parse
from pathlib import Path

from interview_theater import web_daten

#: Der Unterpfad unter ``/g/<token>/``. Steht wortgleich in
#: ``scripts/web_gruppe.CHAT_PFAD`` (Test).
CHAT_PFAD = "chat"

#: Die Telegram-Teilmenge ohne Attribute. ``a`` steht nicht dabei, weil es
#: eins hat und eigens behandelt wird.
ERLAUBTE_TAGS = ("b", "i", "u", "s", "code", "pre", "blockquote")

_TAGS = re.compile(
    r"&lt;(/?)(" + "|".join(ERLAUBTE_TAGS) + r")&gt;", re.IGNORECASE
)
#: Nur http und https, nur ohne maskiertes Ampersand im Ziel. Eine URL mit
#: Query-Parametern (``&amp;``) bleibt deshalb Text statt Link -- die
#: Fehlerrichtung ist bewusst: ein nicht klickbarer Link ist ein
#: Schoenheitsfehler, ein durchgelassenes Attribut ist ein Loch.
#: (Korrektur: eine Zeichenklasse kennt nur einzelne Zeichen, keine
#: Entitaeten -- ``[^&quot;&lt;&gt;\s]`` schloss faelschlich auch q/u/o/t/
#: l/g aus. Das Ausschliessen von ``&`` allein reicht: eine Entitaet --
#: auch die abschliessende ``&quot;&gt;`` selbst -- beginnt immer mit ``&``.)
_LINK = re.compile(
    r"&lt;a href=&quot;(https?://[^&\s]+)&quot;&gt;", re.IGNORECASE
)
_LINK_ENDE = re.compile(r"&lt;/a&gt;", re.IGNORECASE)

#: Event-Attribute (``onclick=``, ``onerror=``, ``onload=`` ...) -- werden
#: schon aus dem Rohtext entfernt, nicht erst maskiert. Maskiert bliebe das
#: Wort selbst lesbar (``onerror=alert(1)`` als Chattext), und genau das soll
#: in der Ansicht nicht einmal als Text auftauchen.
_EVENT_ATTR = re.compile(
    r'\bon\w+\s*=\s*(".*?"|\'.*?\'|[^\s>]*)', re.IGNORECASE
)
#: Dieselbe Ueberlegung fuer URI-Schemata, die ein Browser ausfuehren oder
#: einbetten wuerde (``javascript:``, ``data:``, ``vbscript:``) -- entfernt
#: vor der Maskierung, damit das Schema selbst nicht als Text sichtbar bleibt.
_DANGEROUS_SCHEME = re.compile(r"\b(javascript|data|vbscript):", re.IGNORECASE)


def sichere_html(text) -> str:
    """Telegram-HTML als sicheres HTML fuer die Chatansicht.

    Schritte in dieser Reihenfolge: (0) einmal entmaskieren -- Telegram-HTML
    mischt echte Tags (``<b>``) mit maskierten Literalen (``&amp;``); ohne
    diesen Schritt wuerde ein schon maskiertes ``&amp;`` beim naechsten
    ``html.escape`` zu ``&amp;amp;`` doppelt maskiert. (0b) Event-Attribute
    und gefaehrliche URI-Schemata aus dem so gewonnenen Rohtext entfernen --
    nicht erst maskieren, sie sollen nicht einmal als Text auftauchen. (1)
    alles maskieren (``html.escape``, inklusive Anfuehrungszeichen), (2) die
    geschlossene Liste wieder zulassen, (3) Zeilenumbrueche sichtbar machen.

    Dass Schritt 1 (nach 0/0b) kommt, ist die ganze Sicherheit: danach gibt
    es im Text kein einziges ``<`` mehr, und Schritt 2 kann nur das
    erzeugen, was er ausdruecklich erlaubt. Ein Filter, der stattdessen
    ``<script>`` entfernt, ist eine Liste von Dingen, an die jemand gedacht
    hat."""
    roh = html.unescape(text or "")
    roh = _EVENT_ATTR.sub("", roh)
    roh = _DANGEROUS_SCHEME.sub("", roh)
    maskiert = html.escape(roh, quote=True)
    mit_tags = _TAGS.sub(lambda t: f"<{t.group(1)}{t.group(2).lower()}>", maskiert)
    mit_links = _LINK.sub(
        lambda t: (
            f'<a href="{t.group(1)}" target="_blank" rel="noopener noreferrer">'
        ),
        mit_tags,
    )
    mit_links = _LINK_ENDE.sub("</a>", mit_links)
    return mit_links.replace("\n", "<br>")


_TEXT_TITEL = "Chat mit dem Theaterbot"
_TEXT_LEER = "Noch nichts da. Schreibt mir, womit ihr anfangen wollt."
_TEXT_EINGABE = "Schreiben …"
_TEXT_SENDEN = "Senden"
_TEXT_TIPPT = "schreibt …"
_TEXT_SPRACHE = "Sprachnachricht ({dauer})"
_TEXT_DATEI = "Datei: {name}"
_TEXT_ZUR_GRUPPENSEITE = "Zur Gruppenseite"
_TEXT_INTERVIEW_AN = "Interview aufnehmen"
_TEXT_INTERVIEW_AUS = "Aufnahme beenden"
_TEXT_PTT = "Halten und sprechen"
_TEXT_OHNE_JS = (
    "Fuer Chat und Aufnahme braucht diese Seite JavaScript. "
    "Die Gruppenseite und das Textbuch funktionieren auch ohne."
)

#: Die Seite ist gross gesetzt: sie liegt auf einem Telefon in einem
#: Probenraum, und die Gruppe liest im Stehen.
_CSS_CHAT = """
body { background: #fbfaf8; color: #17181b; padding: .6rem .7rem 9rem;
       max-width: 44rem; margin: 0 auto; }
.verlauf { display: flex; flex-direction: column; gap: .55rem; }
.blase { padding: .55rem .7rem; border-radius: .8rem; max-width: 88%;
         font-size: 1.02rem; overflow-wrap: anywhere; }
.blase.bot { background: #fff; border: 1px solid #e0ddd6; align-self: flex-start;
             border-bottom-left-radius: .2rem; }
.blase.gruppe { background: #1f6f5c; color: #fff; align-self: flex-end;
                border-bottom-right-radius: .2rem; }
.blase.sprache { font-style: italic; opacity: .85; }
.leiste { display: flex; flex-direction: column; gap: .35rem; margin: .1rem 0 .3rem;
          align-self: flex-start; width: 88%; }
.leiste button { font: inherit; text-align: left; padding: .65rem .8rem;
                 border-radius: .7rem; border: 1px solid #1f6f5c;
                 background: #fff; color: #17181b; min-height: 2.9rem; }
.leiste button:disabled { opacity: .45; }
.quittung { font-size: .82rem; opacity: .7; align-self: flex-start; }
.tippt { font-size: .85rem; opacity: .6; height: 1.2em; }
.fuss { position: fixed; left: 0; right: 0; bottom: 0; background: #fbfaf8;
        border-top: 1px solid #e0ddd6; padding: .5rem .7rem .8rem;
        display: flex; flex-direction: column; gap: .5rem; }
.zeile { display: flex; gap: .4rem; align-items: stretch; }
.zeile input { flex: 1; font: inherit; padding: .6rem .7rem; min-height: 2.9rem;
               border-radius: .7rem; border: 1px solid #c9c4b8; }
.zeile button { font: inherit; min-width: 3.4rem; min-height: 2.9rem;
                border-radius: .7rem; border: 0; background: #1f6f5c; color: #fff; }
#interview { font: inherit; font-weight: 600; min-height: 3.2rem; width: 100%;
             border-radius: .8rem; border: 1px solid #1f6f5c; background: #fff; }
#interview[data-laeuft="1"] { background: #a8201a; border-color: #a8201a;
                              color: #fff; min-height: 4rem; font-size: 1.15rem; }
#ptt[hidden], #interview[hidden] { display: none; }
.pegel { height: .45rem; border-radius: .3rem; background: #e0ddd6; overflow: hidden; }
.pegel span { display: block; height: 100%; width: 0; background: #a8201a; }
.uhr { font-variant-numeric: tabular-nums; font-size: 1.3rem; text-align: center; }
.warteschlange { font-size: .82rem; opacity: .7; text-align: center; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e7e9ec; }
  .blase.bot { background: #1d2026; border-color: #2c313a; }
  .fuss { background: #14161a; border-color: #2c313a; }
  .zeile input { background: #1d2026; color: #e7e9ec; border-color: #2c313a; }
  .leiste button { background: #1d2026; color: #e7e9ec; }
}
"""

#: Wird in Aufgabe 11 gefuellt.
_CHAT_JS = ""


def _blase_html(n: dict) -> str:
    """Eine Nachricht als Blase, gegebenenfalls mit ihrer Leiste darunter."""
    if n["typ"] == "sprache":
        minuten, sekunden = divmod(int(n["dauer"] or 0), 60)
        inhalt = html.escape(_TEXT_SPRACHE.format(dauer=f"{minuten}:{sekunden:02d}"))
        klasse = "sprache"
    elif n["typ"] == "datei":
        inhalt = (
            f'<a href="{CHAT_PFAD}/datei/{n["id"]}">'
            + html.escape(_TEXT_DATEI.format(name=n["dateiname"] or "datei"))
            + "</a>"
        )
        if n["text"]:
            inhalt = sichere_html(n["text"]) + "<br>" + inhalt
        klasse = "datei"
    else:
        inhalt = sichere_html(n["text"])
        klasse = "text"

    teile = [
        f'<div class="blase {n["von"]} {klasse}" data-id="{n["id"]}">{inhalt}</div>'
    ]
    if n["knoepfe"]:
        knoepfe = "".join(
            f'<button type="button" data-message="{n["id"]}" '
            f'data-daten="{html.escape(daten, quote=True)}">'
            f"{html.escape(beschriftung)}</button>"
            for beschriftung, daten in n["knoepfe"]
        )
        teile.append(f'<div class="leiste" data-message="{n["id"]}">{knoepfe}</div>')
    return "\n".join(teile)


def chat_html(daten: dict, nonce_wert: str, token: str, praefix: str,
              segment_ms: int) -> str:
    """Die Chatansicht.

    Sie haengt sich in ``web._seite`` ein (dieselbe Klammer, dasselbe
    Grund-CSS), aber **ohne** dessen sanftes Nachladen: das tauscht den
    ``<body>`` aus, und mitten in einer laufenden Aufnahme wuerde das
    Recorder, Timer und Warteschlange mitreissen. Nachgeladen wird hier
    gezielt, per Poll (``_CHAT_JS``), und nur der Verlauf."""
    from interview_theater import web   # spaeter Import: web importiert web_chat

    blasen = "\n".join(_blase_html(n) for n in daten["nachrichten"])
    if not blasen:
        blasen = f'<p class="leer">{html.escape(_TEXT_LEER)}</p>'

    koerper = (
        f"<h1>{html.escape(daten.get('titel') or _TEXT_TITEL)}</h1>\n"
        f'<p><a href="{html.escape(token)}">'
        f"{html.escape(_TEXT_ZUR_GRUPPENSEITE)}</a></p>\n"
        f'<noscript><p class="leer">{html.escape(_TEXT_OHNE_JS)}</p></noscript>\n'
        f'<div class="verlauf" id="verlauf" data-letzte="{daten["letzte"]}">\n'
        f"{blasen}\n</div>\n"
        f'<div class="tippt" id="tippt"></div>\n'
        f'<input type="hidden" id="nonce" value="{html.escape(nonce_wert, quote=True)}">\n'
        f'<div class="fuss" id="fuss" data-segment-ms="{int(segment_ms)}"\n'
        f'     data-interview="{1 if daten["interviewmodus"] else 0}">\n'
        f'  <div class="uhr" id="uhr" hidden></div>\n'
        f'  <div class="pegel" id="pegel" hidden><span></span></div>\n'
        f'  <div class="warteschlange" id="warteschlange"></div>\n'
        f'  <button type="button" id="interview">'
        f'{html.escape(_TEXT_INTERVIEW_AN)}</button>\n'
        f'  <div class="zeile">\n'
        f'    <input type="text" id="eingabe" autocomplete="off" '
        f'placeholder="{html.escape(_TEXT_EINGABE, quote=True)}">\n'
        f'    <button type="button" id="ptt" title="'
        f'{html.escape(_TEXT_PTT, quote=True)}">🎤</button>\n'
        f'    <button type="button" id="senden">'
        f'{html.escape(_TEXT_SENDEN)}</button>\n'
        f"  </div>\n"
        f"</div>\n"
    )
    return web._seite(
        daten.get("titel") or _TEXT_TITEL, _CSS_CHAT, koerper,
        nachladen=False, skript=_CHAT_JS,
    )


def beantworte_get(handler, db_pfad: str, token: str, unterpfad: str,
                   praefix: str, schluessel: bytes, query: str) -> None:
    """Alles unter ``/g/<token>/chat``: die Seite, der Zustands-Poll und die
    Dateien aus ``sende_datei``. Alles Unbekannte ist 404 -- wie bei
    ``web._beantworte_gruppenseite``."""
    from interview_theater import web

    if unterpfad == "":
        _sende_seite(handler, db_pfad, token, praefix, schluessel)
        return
    if unterpfad == "zustand":
        _sende_zustand(handler, db_pfad, token, query)
        return
    if unterpfad.startswith("datei/"):
        _sende_datei(handler, db_pfad, token, unterpfad[len("datei/"):])
        return
    handler._antworte(404, web.nicht_gefunden_html())


def beantworte_post(handler, db_pfad: str, token: str, unterpfad: str,
                    schluessel: bytes) -> None:
    """Wird in den Aufgaben 7-10 gefuellt."""
    from interview_theater import web

    handler._antworte(404, web.nicht_gefunden_html())


def _zustand(db_pfad: str, token: str, nach: int = 0) -> dict | None:
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        return web_daten.web_chatzustand(conn, token, nach)
    finally:
        conn.close()


def _sende_seite(handler, db_pfad: str, token: str, praefix: str,
                 schluessel: bytes) -> None:
    from interview_theater import web

    daten = _zustand(db_pfad, token)
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(
        200,
        chat_html(daten, web.nonce(schluessel, token), token, praefix,
                  _segment_ms()),
    )


def _sende_zustand(handler, db_pfad: str, token: str, query: str) -> None:
    from interview_theater import web

    daten = _zustand(db_pfad, token, _nach(query))
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    # Der Verlauf enthaelt HTML aus Bot-Ausgaben -- er wird HIER gefiltert,
    # nicht im Browser: ein Filter im JavaScript liegt auf der Seite, die er
    # schuetzen soll.
    for nachricht in daten["nachrichten"]:
        nachricht["html"] = sichere_html(nachricht["text"])
    daten["segment_ms"] = _segment_ms()
    handler._antworte(
        200, json.dumps(daten, ensure_ascii=False),
        "application/json; charset=utf-8",
    )


def _sende_datei(handler, db_pfad: str, token: str, roh_id: str) -> None:
    from interview_theater import web

    if not roh_id.isdigit():
        handler._antworte(404, web.nicht_gefunden_html())
        return
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.chat_id_nach_token(conn, token)
        datei = (
            web_daten.web_ausgangsdatei(conn, chat_id, int(roh_id))
            if chat_id is not None else None
        )
    finally:
        conn.close()
    if datei is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    try:
        inhalt = Path(datei["pfad"]).read_text(encoding="utf-8")
    except OSError:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(
        200, inhalt, "text/markdown; charset=utf-8",
        dateiname=datei["dateiname"],
    )


def _nach(query: str) -> int:
    """``?nach=<id>`` -- alles, was keine Zahl ist, gilt als 0. Ein
    Tippfehler in der Adresszeile soll keine 500 geben (wie
    ``web.fassungswahl``)."""
    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return 0
    roh = (werte.get("nach") or ["0"])[0]
    return int(roh) if roh.isdigit() else 0


def _segment_ms() -> int:
    """Die Segmentlaenge fuer den Browser. Aus der Umgebung, weil der
    Webserver keine ``Einstellungen`` laedt (er braucht weder LLM- noch
    STT-Variablen) -- derselbe Name wie dort
    (``einstellungen.VORGABE_SEGMENT_MS``)."""
    roh = (os.environ.get("IT_WEB_SEGMENT_MS") or "").strip()
    return int(roh) if roh.isdigit() and int(roh) > 0 else 45_000
