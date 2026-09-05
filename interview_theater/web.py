"""Der kleine Webserver: Team-Dashboard und Leseansicht je Gruppe.

Zwei Routen derselben Anwendung
(NACHTRAG-weboberflaeche-und-sprache.md N1):

* ``/`` -- Team-Dashboard, alle Gruppen nebeneinander, projiziert. Ohne
  Nachrichtentext und ohne Transkripte: auf dem Beamer stehen sonst
  Lebensgeschichten.
* ``/g/<token>`` -- Leseansicht einer Gruppe fuers Handy, Zugang ueber das
  Zufallstoken aus ``gruppe.web_token``, kein Login.
* ``/gesund`` -- Health-Check, antwortet ohne Datenbankzugriff.

**Nur Standardbibliothek**, kein Framework, kein Build-Schritt: das Ding muss
am Workshoptag starten, nicht gepflegt werden. **Read-only**: geschrieben wird
ausschliesslich ueber den Chat, sonst laufen zwei Schreibwege gegeneinander.

Start::

    IT_DB=betrieb/soap.db python -m interview_theater.web

Umgebung: ``IT_DB`` (Pflicht), ``IT_WEB_BIND`` (Vorgabe ``127.0.0.1:8010``),
``IT_WEB_PREFIX`` (Vorgabe ``/theatersoap``).

Von aussen haengt der Server hinter nginx unter
``https://lab.artesmobiles.art/theatersoap/``. Ob nginx das Praefix
weiterreicht oder abschneidet, entscheidet die dortige Konfiguration und
nicht dieser Code -- deshalb nimmt das Routing beide Formen an
(``/g/<token>`` und ``/theatersoap/g/<token>``), und alle erzeugten Links
sind relativ.
"""

import html
import re
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import phasen, web_daten  # noqa: F401 -- web_daten.SZENENFELDER im HTML

VORGABE_BIND = "127.0.0.1:8010"
#: Externer URL-Pfad, unter dem nginx auf herkules den Server durchreicht.
#: Historischer Name aus dem ersten Einsatz -- er steht in der nginx-Konfig,
#: nicht im Code; aendern heisst dort aendern (und IT_WEB_PREFIX mitziehen).
VORGABE_PRAEFIX = "/theatersoap"

#: Sekunden bis zum Selbst-Neuladen beider Seiten. Per <meta refresh>, damit
#: die Seite ohne JavaScript aktuell bleibt -- ein projizierter Rechner soll
#: nach einem Browserneustart einfach weiterlaufen.
NEULADEN_SEKUNDEN = 10

#: Haelt die Scrollposition ueber das Neuladen hinweg. Das Minimum an
#: JavaScript, das die Seite ertraeglich macht: ohne das springt eine lange
#: Gruppenseite alle zehn Sekunden nach oben, mitten im Lesen. Faellt JS aus,
#: bleibt alles andere benutzbar.
_SCROLL_JS = """
(function () {
  // Sanftes Nachladen (Birk 05.09.: "wenn ich etwas ausklappe, geht es
  // immer wieder zu, sobald die Seite neu laedt"). Kein meta refresh mehr:
  // alle NEULADEN Sekunden wird die Seite per fetch geholt; hat sich der
  // Inhalt nicht geaendert, passiert nichts. Hat er sich geaendert, wird
  // nur der <body> getauscht -- und vorher gemerkt, welche <details> offen
  // waren (am summary-Text), danach wieder geoeffnet. Scrollposition
  // bleibt, weil das Dokument nicht neu geladen wird.
  var INTERVALL_MS = __NEULADEN_MS__;
  var offene = function () {
    var s = {};
    document.querySelectorAll('details[open] > summary').forEach(function (el) {
      s[el.textContent.trim()] = true;
    });
    return s;
  };
  var stelleHer = function (zustand) {
    document.querySelectorAll('details > summary').forEach(function (el) {
      if (zustand[el.textContent.trim()]) { el.parentElement.setAttribute('open', ''); }
    });
  };
  var letzter = document.body.innerHTML;
  var laeuft = false;
  setInterval(function () {
    if (laeuft || document.hidden) { return; }
    laeuft = true;
    fetch(location.href, { cache: 'no-store', headers: { 'X-Nachladen': '1' } })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) { return; }
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var neu = doc.body ? doc.body.innerHTML : null;
        if (!neu || neu === letzter) { return; }
        var zustand = offene();
        var y = window.scrollY;
        document.body.innerHTML = neu;
        stelleHer(zustand);
        window.scrollTo(0, y);
        letzter = neu;
      })
      .catch(function () {})
      .finally(function () { laeuft = false; });
  }, INTERVALL_MS);
})();
"""
_CSS_GEMEINSAM = """
ul.fragen { list-style: none; padding: 0; margin: 0; }
ul.fragen li { margin: .25em 0; }
pre.leitfaden { white-space: pre-wrap; font-family: inherit; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; padding: 1rem 1.2rem 3rem;
       font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
       line-height: 1.45; }
h1 { font-size: 1.5rem; margin: 0 0 .8rem; }
h2 { font-size: 1.15rem; margin: 1.6rem 0 .5rem; }
h3 { font-size: 1rem; margin: 0 0 .4rem; }
.stand { font-weight: normal; font-size: .8rem; opacity: .6; }
.leer { opacity: .45; font-style: italic; }
dt { font-size: .78rem; text-transform: uppercase; letter-spacing: .04em;
     opacity: .6; margin-top: .5rem; }
dd { margin: 0; }
dl { margin: 0; }
"""

_CSS_DASHBOARD = """
body { background: #14161a; color: #e7e9ec; }
.gruppen { display: grid; gap: .9rem;
           grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr)); }
.karte { background: #1d2026; border: 1px solid #2c313a; border-radius: .5rem;
         padding: .8rem .9rem; }
.karte h2 { margin: 0; font-size: 1.2rem; }
.kopf { display: flex; justify-content: space-between; align-items: baseline;
        gap: .5rem; border-bottom: 1px solid #2c313a; padding-bottom: .4rem;
        margin-bottom: .3rem; }
.bot { font-size: .78rem; opacity: .6; }
.marke { display: inline-block; font-size: .72rem; padding: .1rem .45rem;
         border-radius: .8rem; background: #2f4858; color: #cfe8ff; }
.zahlen { display: flex; flex-wrap: wrap; gap: .1rem .9rem; font-size: .85rem;
          margin-top: .6rem; }
.zahlen b { font-weight: 600; }
.vorfaelle { margin-top: .6rem; border-left: 3px solid #e04a4a;
             background: #2a1a1c; padding: .35rem .5rem; font-size: .82rem; }
.vorfaelle div { margin: .15rem 0; }
.vorfaelle .art { color: #ff8f8f; font-weight: 600; }
.zeit { opacity: .55; font-size: .75rem; }
table { border-collapse: collapse; width: 100%; font-size: .85rem; }
th, td { text-align: left; padding: .25rem .6rem .25rem 0;
         border-bottom: 1px solid #2c313a; }
th { opacity: .6; font-weight: 600; }
.figuren li { margin-bottom: .15rem; }
/* Je Interview eine Zeile mit den Ergebnissen als Kurzform (N6) -- ohne
   Zitate und ohne Zusammenfassung, das Dashboard haengt am Beamer. */
.ergebnisse { margin: .5rem 0 0; font-size: .85rem; }
.ergebnisse li { margin-bottom: .15rem; }
ul { margin: .2rem 0; padding-left: 1.1rem; }
"""

_CSS_GRUPPE = """
body { background: #fbfaf7; color: #1b1b1b; font-size: 1.05rem;
       max-width: 44rem; margin: 0 auto; }
h1 { font-size: 1.6rem; }
h2 { border-bottom: 1px solid #ddd8cc; padding-bottom: .2rem; }
.szene { margin: 0 0 1.4rem; }
.szene .volltext { white-space: pre-wrap; background: #fff; border: 1px solid #e6e1d6;
                   border-radius: .4rem; padding: .7rem .8rem; }
.verdichtung { margin: 0 0 1.2rem; }
blockquote { margin: .2rem 0 .5rem; padding-left: .7rem;
             border-left: 3px solid #c9b98d; font-style: italic; }
.thema { margin-bottom: .5rem; }
.art { display: inline-block; font-size: .72rem; text-transform: uppercase;
       letter-spacing: .04em; background: #ece7db; border-radius: .8rem;
       padding: .05rem .5rem; margin-right: .4rem; }
details { margin-top: .5rem; }
summary { cursor: pointer; font-weight: 600; }
details.szene, details.verdichtung { border-bottom: 1px solid #e6e1d6;
                                     padding-bottom: .5rem; }
/* Das Sprachprofil einer Figur: mehrzeilig, so wie es gespeichert ist. */
.profil { white-space: pre-wrap; font-size: .92rem; opacity: .8;
          margin: .2rem 0 .3rem; }
.eintrag { margin: .35rem 0; }
.zeit { opacity: .5; font-size: .78rem; }
"""


def _t(wert, ersatz: str = "—") -> str:
    """Maskiert einen Wert aus der Datenbank fuer HTML.

    ALLES aus der Datenbank laeuft hier durch: Gruppentitel, Figurennamen und
    Szenentexte kommen aus Telegram und aus einem Sprachmodell, beides sind
    fremde Eingaben. ``None`` und Leerstrings werden zum Ersatzzeichen, damit
    im Dashboard kein 'None' steht."""
    if wert is None or wert == "":
        return ersatz
    return html.escape(str(wert))


def _zeitpunkt(iso: str | None) -> str:
    """Formatiert einen UTC-Zeitstempel als Ortszeit 'TT.MM. HH:MM'.

    In der Datenbank steht UTC; auf dem Beamer soll die Uhrzeit im Raum
    stehen. Laesst sich der Wert nicht lesen, wird er maskiert
    durchgereicht -- eine unerwartete Schreibweise ist kein Grund, die Seite
    scheitern zu lassen."""
    if not iso:
        return "—"
    gelesen = web_daten.lies_zeitstempel(iso)
    if gelesen is None:
        return html.escape(str(iso))
    return gelesen.astimezone().strftime("%d.%m. %H:%M")


def _sekunden(millisekunden: int | None) -> str:
    """Millisekunden als Sekunden mit Dezimalkomma -- die Seite ist auf
    Deutsch, '5.1 s' liest sich dort falsch."""
    if millisekunden is None:
        return "—"
    return f"{millisekunden / 1000:.1f}".replace(".", ",") + " s"


def _dauer(sekunden: int | None) -> str:
    """Eine Aufnahmedauer als 'M:SS' -- 'Interview 3 · 4 Teile · 12:07' sagt
    der Gruppe mehr ueber ihr Material als eine Zahl in Sekunden."""
    if not sekunden:
        return ""
    return f"{int(sekunden) // 60}:{int(sekunden) % 60:02d}"


def _umfang(teile: int, sekunden: int | None) -> str:
    """Die Kopfzeile eines Interviews auf der Gruppenseite: aus wie vielen
    Sprachnachrichten es besteht und wie lang es insgesamt ist (§ 10.6).

    Ohne Teile (Textimport, Aufnahme aus der Zeit vor dem Nachtrag) bleibt die
    Teile-Zahl weg statt '0 Teile' zu behaupten."""
    stuecke = []
    if teile == 1:
        stuecke.append("1 Teil")
    elif teile > 1:
        stuecke.append(f"{teile} Teile")
    dauer = _dauer(sekunden)
    if dauer:
        stuecke.append(dauer)
    return " · ".join(stuecke)


def _seite(titel: str, css: str, koerper: str) -> str:
    """Rahmen beider Seiten: ein einziges eingebettetes CSS, keine externe
    Ressource (der Workshopraum haengt an einem Tailnet, nicht am offenen
    Netz), sanftes Nachladen per fetch (siehe _SCROLL_JS) -- kein meta
    refresh mehr, der jedes aufgeklappte <details> wieder zuklappte."""
    return (
        "<!doctype html>\n"
        '<html lang="de"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(titel)}</title>\n"
        f"<style>{_CSS_GEMEINSAM}{css}</style></head>\n<body>\n"
        f"{koerper}\n"
        f"<script>{_SCROLL_JS.replace('__NEULADEN_MS__', str(NEULADEN_SEKUNDEN * 1000))}</script>\n"
        "</body></html>\n"
    )


def _fragen_html(fragen: str | None) -> str:
    """Eine Zeile je Frage, das Thema fett (Birk 04.09.: 'jede Frage eine
    eigene Zeile mit dem Thema der Frage fett gedruckt').

    Der Erkenner liefert die Fragen als einen String; getrennt wird an
    Zeilenumbruch oder ' | ', das Thema ist das, was vor dem ersten
    Doppelpunkt steht -- wenn es kurz genug ist, um ein Thema zu sein.
    Fehlt es, steht die Frage allein. Alles HTML-escaped."""
    if not fragen:
        return _t(None)
    teile = [t.strip(" -•") for t in re.split(r"\n+| \| ", fragen) if t.strip(" -•")]
    zeilen = []
    for teil in teile:
        thema, sep, frage = teil.partition(":")
        if sep and 0 < len(thema.strip()) <= 40 and frage.strip():
            zeilen.append(f"<li><b>{_t(thema.strip())}</b> {_t(frage.strip())}</li>")
        else:
            zeilen.append(f"<li>{_t(teil)}</li>")
    return "<ul class=\"fragen\">" + "".join(zeilen) + "</ul>"


def _leitfaden_html(arbeitsstand: dict) -> str:
    """Der Gespraechsleitfaden als eigener Eintrag unter den Fragen -- oder
    gar nichts (06.09.2026).

    Read-only und ohne Werbung fuer sich selbst: steht kein Leitfaden, fehlt
    die Zeile ganz, statt als leere Aufgabe dazustehen (dieselbe Regel wie
    beim Hauptkonflikt). Der Text kommt aus ``leitfaden.aus_feldern`` -- der
    reinen Funktion, die auch der Chat benutzt, damit auf der Gruppenseite
    nichts anderes steht als auf dem Telefon. ``leitfaden`` selbst haengt an
    keinem Schreib-Lock, solange es nur diese Funktion ist.
    """
    from interview_theater import leitfaden

    text = leitfaden.aus_feldern(arbeitsstand)
    if text == leitfaden.TEXT_LEER:
        return ""
    return f"<dt>Leitfaden</dt><dd><pre class=\"leitfaden\">{_t(text)}</pre></dd>"


def _figur_html(f: dict, mit_stimme: bool) -> str:
    """Eine Figur: Name, Beschreibung -- und auf der Gruppenseite zusaetzlich
    das Interview, aus dem sie spricht, ihr Sprachprofil und ihre woertlichen
    Zitate (05.09.2026).

    ``mit_stimme=False`` auf dem **Dashboard**: das haengt am Beamer, und ein
    woertlicher Satz aus einem Interview gehoert dort nicht hin -- dieselbe
    Grenze wie bei Nachrichtentext und Transkripten. Die Zitate selbst sind
    vor dem Speichern geprueft (``sprachprofil.erstelle``), stehen also unter
    derselben Zusage wie die Belegzitate der Verdichtungen: kein Satz in
    Anfuehrungszeichen, den niemand gesagt hat."""
    teile = [f"<b>{_t(f['name'])}</b> — {_t(f.get('beschreibung'), 'ohne Beschreibung')}"]
    if f.get("quelle"):
        teile.append(f'<div class="zeit">Sprechweise aus {_t(f["quelle"])}</div>')
    if mit_stimme:
        if f.get("sprachprofil"):
            teile.append(f'<div class="profil">{_t(f["sprachprofil"])}</div>')
        for satz in f.get("zitate") or []:
            teile.append(f"<blockquote>„{_t(satz)}“</blockquote>")
    return "<li>" + "".join(teile) + "</li>"


def _arbeitsstand_html(
    arbeitsstand: dict, figuren: list[dict], mit_stimmen: bool = False
) -> str:
    figuren_html = "".join(_figur_html(f, mit_stimmen) for f in figuren)
    # Die Phase steht oben: sie ordnet alles darunter ein. Eine ungesetzte
    # Phase (NULL) gilt wie 1 -- diese Anzeigeregel steht hier, web_daten
    # liefert den rohen Wert (interview_theater/phasen.py).
    phase = arbeitsstand.get("phase") or phasen.ERSTE
    return (
        "<dl>"
        f"<dt>Phase</dt><dd>{_t(phasen.bezeichnung(phase))}</dd>"
        f"<dt>Begriffe</dt><dd>{_t(arbeitsstand['begriffe'])}</dd>"
        f"<dt>Fragen</dt><dd>{_fragen_html(arbeitsstand.get('fragen'))}</dd>"
        # Der Leitfaden steht direkt unter den Fragen -- er ist ihre
        # Gebrauchsanweisung (06.09.2026). Read-only wie alles hier: gebaut
        # wird er aus denselben Feldern wie im Chat (``leitfaden.aus_feldern``),
        # damit auf der Wand nichts anderes steht als auf dem Telefon.
        + _leitfaden_html(arbeitsstand)
        + f"<dt>Kernthema</dt><dd>{_t(arbeitsstand['kernthema'])}"
        + (
            f"<div class=\"zeit\">{_t(arbeitsstand['kernthema_begruendung'], '')}</div>"
            if arbeitsstand["kernthema_begruendung"]
            else ""
        )
        + "</dd>"
        f"<dt>Rahmen</dt><dd>{_t(arbeitsstand.get('rahmen'))}</dd>"
        # Der Hauptkonflikt steht nur da, wenn es einen gibt (05.09.2026): er
        # ist eine moegliche Rahmen-Entscheidung, keine Pflicht -- ein leeres
        # Feld daneben sieht aus wie eine unerledigte Aufgabe.
        + (
            f"<dt>Hauptkonflikt</dt><dd>{_t(arbeitsstand['hauptkonflikt'])}</dd>"
            if arbeitsstand.get("hauptkonflikt")
            else ""
        )
        + "<dt>Figuren</dt><dd>"
        + (f'<ul class="figuren">{figuren_html}</ul>' if figuren else '<span class="leer">noch keine</span>')
        + "</dd></dl>"
    )


def _szenenzahl(anzahl: int, formen: list) -> str:
    """"3 Szenen: 2 Dialog, 1 Lied" -- die Szenenzahl mit ihren Formen
    (05.09.2026).

    Eine blosse Zahl sagt am Beamer wenig; die Formen sagen, was fuer ein
    Abend gerade entsteht. Ohne Szenen bleibt es bei der Zahl."""
    kopf = f"Szenen: <b>{anzahl}</b>"
    if not formen:
        return kopf
    return kopf + " — " + ", ".join(f"{n} {_t(form)}" for form, n in formen)


def _ergebnisse_html(kurzformen: list[dict]) -> str:
    """Je Interview eine Zeile mit den Ergebnissen als Kurzform (N6).

    **Ohne Zitate, ohne Zusammenfassung, ohne Transkript** -- das Dashboard
    haengt am Beamer. Was hier steht, sind Arbeitsergebnisse in hoechstens
    acht Woertern je Thema."""
    if not kurzformen:
        return ""
    zeilen = "".join(
        '<li><b>{name}</b> {ergebnisse}</li>'.format(
            name=_t(v["name"], "Interview"),
            ergebnisse=_t(SUMMARY_TRENNER.join(v["kurzformen"])),
        )
        for v in kurzformen
    )
    return f'<ul class="ergebnisse">{zeilen}</ul>'


def dashboard_html(daten: dict, praefix: str = VORGABE_PRAEFIX) -> str:
    """Das projizierte Team-Dashboard aus web_daten.dashboard().

    ``praefix`` baut den Link zur Gruppenseite (Birk 04.09.: je Gruppe ein
    Link) -- relativ zum Server, damit er hinter nginx genauso geht wie
    direkt auf Port 8010."""
    karten = []
    for g in daten["gruppen"]:
        titel = _t(g["titel"], "Gruppe " + str(g["chat_id"]))
        if g.get("web_token"):
            titel = f'<a href="{praefix}/g/{_t(g["web_token"])}">{titel}</a>'
        marke = (
            '<span class="marke">Interviewmodus</span>'
            if g["interviewmodus_seit"]
            else ""
        )
        aufnahmen = ", ".join(
            f"{_t(status)}: <b>{anzahl}</b>" for status, anzahl in g["aufnahmen"].items()
        ) or '<span class="leer">keine</span>'
        aufrufe = "".join(
            "<tr><td>{art}</td><td>{anzahl}</td><td>{fehl}</td><td>{median}</td></tr>".format(
                art=_t(a["art"]),
                anzahl=a["anzahl"],
                fehl=a["fehlschlaege"],
                median=_sekunden(a["median_ms"]),
            )
            for a in g["aufrufe"]
        )
        aufrufe_html = (
            "<table><tr><th>Aufruf</th><th>heute</th><th>Fehl</th><th>Median</th></tr>"
            f"{aufrufe}</table>"
            if aufrufe
            else '<p class="leer">heute noch keine Modellaufrufe</p>'
        )
        vorfaelle = "".join(
            '<div><span class="art">{art}</span> {detail} '
            '<span class="zeit">{zeit}{botweit}</span></div>'.format(
                art=_t(v["art"]),
                detail=_t(v["detail"], ""),
                zeit=_zeitpunkt(v["erstellt_am"]),
                botweit=", bot-weit" if v["bot_weit"] else "",
            )
            for v in g["vorfaelle"]
        )
        vorfaelle_html = (
            f'<div class="vorfaelle">{vorfaelle}</div>' if vorfaelle else ""
        )
        karten.append(
            "<section class=\"karte\">"
            f'<div class="kopf"><h2>{titel}</h2>'
            f'<span class="bot">{_t(g["bot_name"])} {marke}</span></div>'
            f'{_arbeitsstand_html(g["arbeitsstand"], g["figuren"])}'
            f'{_ergebnisse_html(g.get("interview_kurzformen") or [])}'
            f'<div class="zahlen"><span>Aufnahmen — {aufnahmen}</span>'
            f'<span>Verdichtungen: <b>{g["verdichtungen"]}</b></span>'
            f'<span>{_szenenzahl(g["szenen"], g.get("szenen_formen") or [])}</span>'
            f'<span>zuletzt: {_zeitpunkt(g["letzte_aktivitaet"])}</span></div>'
            f"{vorfaelle_html}"
            f"{aufrufe_html}"
            "</section>"
        )
    gruppen_html = (
        f'<div class="gruppen">{"".join(karten)}</div>'
        if karten
        else '<p class="leer">Noch keine Gruppe hat geschrieben.</p>'
    )

    zuordnung = "".join(
        "<tr><td>{bot}</td><td>{titel}</td><td>{chat}</td><td>{zeit}</td></tr>".format(
            bot=_t(z["bot_name"]),
            titel=_t(z["titel"], "— keine Gruppe —"),
            chat=_t(z["chat_id"]),
            zeit=_zeitpunkt(z["letzte_aktivitaet_am"]),
        )
        for z in daten["bot_zuordnung"]
    )
    return _seite(
        "interview_theater — Dashboard",
        _CSS_DASHBOARD,
        f'<h1>Arbeitsstand aller Gruppen <span class="stand">Stand '
        f'{_zeitpunkt(daten["stand"])}</span></h1>\n'
        f"{gruppen_html}\n"
        "<h2>Bot-Zuordnung</h2>"
        "<table><tr><th>Bot</th><th>Gruppe</th><th>chat_id</th>"
        f"<th>letzte Aktivität</th></tr>{zuordnung}</table>",
    )


#: Trennzeichen der Kurzformen in einer Summary-Zeile. Der Mittelpunkt, weil
#: die Ergebnisse gleichrangig nebeneinanderstehen ("Pfannkuchen mit
#: Schokolade und Banane · Punkerin im autonomen Zentrum").
SUMMARY_TRENNER = " · "


def _szene_summary(s: dict) -> str:
    """Die zusammengeklappte Zeile einer Szene: Nummer, Titel, Form, Ort, Wer.

    Genau so viel, dass die Gruppe die Szene wiedererkennt, ohne aufzuklappen
    -- und genau die Felder, die sie entschieden hat."""
    stuecke = []
    if s["nummer"] is not None:
        stuecke.append(f"Szene {_t(s['nummer'])}")
    if s.get("titel"):
        stuecke.append(_t(s["titel"]))
    for feld in ("form", "ort"):
        if s.get(feld):
            stuecke.append(_t(s[feld]))
    if s.get("figuren"):
        stuecke.append(_t(", ".join(s["figuren"])))
    return SUMMARY_TRENNER.join(stuecke) or "Szene"


def _szene_html(s: dict) -> str:
    """Eine Szene als aufklappbarer Block: Summary-Zeile, darin alle Felder
    der Planung und danach der Volltext (05.09.2026).

    Aufklappbar, weil eine Gruppenseite mit sechs ausgeschriebenen Szenen auf
    dem Handy nicht mehr zu ueberblicken ist -- und weil die Planung das ist,
    was die Gruppe im Gespraech braucht, nicht der ganze Text."""
    felder = "".join(
        f"<dt>{label}</dt><dd>{_t(s[feld])}</dd>"
        for feld, label in web_daten.SZENENFELDER
        if s.get(feld)
    )
    if s.get("figuren"):
        felder = f"<dt>Wer</dt><dd>{_t(', '.join(s['figuren']))}</dd>" + felder
    if s.get("kurzbeschreibung"):
        felder += f"<dt>Kurz</dt><dd>{_t(s['kurzbeschreibung'])}</dd>"
    inhalt = f"<dl>{felder}</dl>" if felder else ""
    if s.get("volltext"):
        inhalt += f'<div class="volltext">{_t(s["volltext"])}</div>'
    else:
        inhalt += '<p class="leer">Noch kein Text — die Szene ist geplant.</p>'
    return (
        f'<details class="szene"><summary>{_szene_summary(s)}</summary>{inhalt}</details>'
    )


def _interview_html(v: dict) -> str:
    """Ein Interview als aufklappbarer Block (N6).

    **Die Summary-Zeile sind die Ergebnisse, nicht der Fliesstext**: je Thema
    die Kurzform, mit Mittelpunkten verbunden. Aufgeklappt steht je Thema das
    Belegzitat (nur geprueft, SPEC § 5) und darunter die Zusammenfassung.

    Bis dahin stand die ganze Verdichtung als Absatz da, und wer wissen
    wollte, was in fuenf Interviews steckt, musste fuenf Absaetze lesen."""
    kurzformen = [t["kurz"] for t in v["themen"] if t.get("kurz")]
    # Interview-Nummer statt Aufnahmename (Birk 05.09.: der Name ist ein
    # Klarname oder der Telegram-Name dessen, der das Handy hielt).
    summary = _t(v.get("bezeichnung") or v["name"], "Interview")
    if kurzformen:
        summary += SUMMARY_TRENNER + SUMMARY_TRENNER.join(_t(k) for k in kurzformen)
    # Je Aspekt eine Unterueberschrift (die Kurzform), darunter die
    # Erklaerung (das Ergebnis in einem Satz) und das Belegzitat -- so, wie
    # Birk es am 05.09. am Dashboard vermisst hat: "pro Interview alle
    # destillierten Aspekte als Unterueberschrift mit Verdichtung,
    # Erklaerung, Zitat".
    themen = "".join(
        '<div class="thema"><h4>{kurz}</h4><p>{thema}</p>{zitat}</div>'.format(
            kurz=_t(t.get("kurz") or t["thema"]),
            thema=_t(t["thema"]),
            zitat=f"<blockquote>„{_t(t['zitat'], '')}“</blockquote>" if t["zitat"] else "",
        )
        for t in v["themen"]
    )
    inhalt = (
        f'<p class="zeit">{_umfang(v["teile"], v["dauer_sekunden"])}</p>'
        + (
            f'<p class="zusammenfassung">{_t(v["zusammenfassung"], "")}</p>{themen}'
            if v["zusammenfassung"]
            else '<p class="leer">Noch nicht verdichtet.</p>'
        )
    )
    return (
        f'<details class="verdichtung"><summary>{summary}</summary>{inhalt}</details>'
    )


def gruppe_html(daten: dict) -> str:
    """Die Leseansicht einer Gruppe aus web_daten.gruppe_nach_token()."""
    szenen = "".join(_szene_html(s) for s in daten["szenen"]) or (
        '<p class="leer">Noch keine Szene. Die entstehen in der letzten Phase.</p>'
    )

    verdichtungen_html = "".join(
        _interview_html(v) for v in daten["interviews"]
    ) or (
        '<p class="leer">Noch kein Interview — sagt „wir machen jetzt ein '
        "Interview“ und sprecht drauflos.</p>"
    )

    journal = "".join(
        '<div class="eintrag"><span class="art">{art}</span>{text} '
        '<span class="zeit">{zeit}</span></div>'.format(
            art=_t(e["art"]), text=_t(e["text"]), zeit=_zeitpunkt(e["erstellt_am"])
        )
        for e in daten["journal"]
    ) or '<p class="leer">Noch nichts notiert.</p>'

    titel = daten["titel"] or f"Gruppe {daten['chat_id']}"
    return _seite(
        f"{titel} — interview-theater",
        _CSS_GRUPPE,
        f"<h1>{_t(titel)}</h1>\n"
        "<h2>Arbeitsstand</h2>"
        f'{_arbeitsstand_html(daten["arbeitsstand"], daten["figuren"], mit_stimmen=True)}\n'
        f"<h2>Szenen</h2>{szenen}\n"
        f"<h2>Aus den Interviews</h2>{verdichtungen_html}\n"
        "<h2>Der Weg dahin</h2>"
        f"<details><summary>Journal ({len(daten['journal'])})</summary>{journal}</details>",
    )


def nicht_gefunden_html() -> str:
    """Antwort auf ein unbekanntes Token oder einen unbekannten Pfad.

    Sagt bewusst nichts darueber, ob es Gruppen gibt oder wie ein gueltiges
    Token aussaehe -- und laedt sich, anders als die beiden echten Seiten,
    nicht selbst neu."""
    return (
        "<!doctype html>\n"
        '<html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Nicht gefunden</title>"
        f"<style>{_CSS_GEMEINSAM}{_CSS_GRUPPE}</style></head>"
        "<body><h1>Nicht gefunden</h1>"
        "<p>Diese Adresse gibt es nicht. Fragt im Workshop nach dem Link.</p>"
        "</body></html>\n"
    )


def _pfad_ohne_praefix(pfad: str, praefix: str) -> str:
    """Schneidet das nginx-Praefix ab, falls es noch dransteht.

    Ob ``proxy_pass`` das Praefix weiterreicht, haengt an der nginx-Zeile und
    nicht an diesem Code -- beide Formen anzunehmen kostet vier Zeilen und
    spart eine Fehlersuche am Workshopmorgen."""
    praefix = praefix.rstrip("/")
    if praefix and (pfad == praefix or pfad.startswith(praefix + "/")):
        pfad = pfad[len(praefix):]
    return pfad or "/"


def mache_handler(db_pfad: str, praefix: str = VORGABE_PRAEFIX):
    """Baut die Handler-Klasse mit ihrer Konfiguration.

    Als Fabrik statt globaler Variablen, damit ein Test einen zweiten Server
    auf eine andere Datenbank stellen kann."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "interview-theater"
        protocol_version = "HTTP/1.1"
        #: HTTP/1.1 haelt die Verbindung offen, und ThreadingHTTPServer bindet
        #: je Verbindung einen Thread. Ohne Zeitlimit blieben die Threads
        #: stiller Browser-Tabs (Beamer, drei Gruppen mit Handy) fuer immer
        #: liegen; nach 30 s ohne neue Anfrage wird die Verbindung geschlossen.
        timeout = 30

        def do_GET(self) -> None:  # noqa: N802 (von BaseHTTPRequestHandler vorgegeben)
            pfad = _pfad_ohne_praefix(
                urllib.parse.unquote(urllib.parse.urlsplit(self.path).path), praefix
            )
            if pfad == "/gesund":
                # Ohne Datenbankzugriff: der Health-Check soll sagen, ob der
                # Prozess laeuft, und nicht ueber die Datenbank mit-scheitern.
                self._antworte(200, "ok", "text/plain; charset=utf-8")
                return
            try:
                if pfad == "/":
                    self._antworte(200, dashboard_html(self._dashboard(), praefix))
                elif pfad.startswith("/g/"):
                    daten = self._gruppe(pfad[len("/g/"):].strip("/"))
                    if daten is None:
                        self._antworte(404, nicht_gefunden_html())
                    else:
                        self._antworte(200, gruppe_html(daten))
                else:
                    self._antworte(404, nicht_gefunden_html())
            except sqlite3.Error as fehler:
                # Typisch: IT_DB zeigt ins Leere, oder die Datei ist noch
                # nicht angelegt. Kurz und ohne Pfade nach aussen, ausfuehrlich
                # ins Log.
                self.log_error("Datenbankfehler: %s", fehler)
                self._antworte(
                    500,
                    "<!doctype html><html lang=\"de\"><meta charset=\"utf-8\">"
                    "<p>Die Datenbank ist gerade nicht lesbar.</p></html>",
                )

        def _dashboard(self) -> dict:
            conn = web_daten.oeffne_lesend(db_pfad)
            try:
                return web_daten.dashboard(conn)
            finally:
                conn.close()

        def _gruppe(self, token: str) -> dict | None:
            conn = web_daten.oeffne_lesend(db_pfad)
            try:
                return web_daten.gruppe_nach_token(conn, token)
            finally:
                conn.close()

        def _antworte(self, status: int, inhalt: str, typ: str = "text/html; charset=utf-8") -> None:
            roh = inhalt.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(roh)))
            # Der Browser soll bei jedem Neuladen wirklich neu fragen --
            # sonst zeigt der Beamer eine Viertelstunde alte Zahlen.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(roh)

        def log_message(self, format: str, *args) -> None:
            """Eine Zeile je Anfrage nach stdout (systemd haengt das an
            betrieb/web.log). Ohne Uhrzeit-Klammern der Vorlage, dafuer mit
            ISO-Zeit -- damit die Zeilen zu denen des Bots passen."""
            print(
                f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} web "
                f"{self.address_string()} {format % args}",
                flush=True,
            )

    return Handler


def lies_bind(wert: str) -> tuple[str, int]:
    """Zerlegt ``IT_WEB_BIND`` in Adresse und Port.

    ``0.0.0.0`` wird abgelehnt: die Gruppenseiten haben kein Login, und der
    Server gehoert ins Tailnet (im Betrieb ``100.75.24.33:8010``), nicht auf
    jede Netzwerkkarte. Ein Tippfehler in einer Env-Datei soll die Interviews
    nicht ins offene Netz stellen."""
    adresse, trenner, port = wert.rpartition(":")
    if not trenner or not port.isdigit():
        raise RuntimeError(f"IT_WEB_BIND muss 'adresse:port' sein, ist: {wert!r}")
    adresse = adresse.strip("[]")
    if adresse in ("0.0.0.0", "::", ""):
        raise RuntimeError(
            "IT_WEB_BIND darf nicht auf allen Adressen lauschen "
            f"(erhalten: {wert!r}) -- die Gruppenseiten haben kein Login. "
            "Tailnet-Adresse oder 127.0.0.1 eintragen."
        )
    return adresse, int(port)


def baue_server(db_pfad: str, bind: str = VORGABE_BIND, praefix: str = VORGABE_PRAEFIX):
    """Baut den Server, ohne ihn zu starten (Tests binden auf Port 0)."""
    adresse, port = lies_bind(bind)
    return ThreadingHTTPServer((adresse, port), mache_handler(db_pfad, praefix))


def main() -> None:
    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        sys.exit(1)
    bind = os.environ.get("IT_WEB_BIND", VORGABE_BIND)
    praefix = os.environ.get("IT_WEB_PREFIX", VORGABE_PRAEFIX)
    server = baue_server(db_pfad, bind, praefix)
    print(
        f"interview-theater-web hoert auf http://{bind}{praefix or '/'} "
        f"(Datenbank {db_pfad}, read-only)",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
