"""Das Stage Script im Script-Tab und im PDF -- das abgenommene Design
(Birk 08.10.2026 ~00:05: "Das PDF-Design gefaellt mir, das kann so
bleiben"; Vorlage ``var/padua-nacht/stagescript-design-draft.py``).

Der Text bleibt Markdown, wie ihn der Stage-Script-Lauf schreibt; dieses
Modul liest die kleine Teilmenge, die dort vorkommt (Absaetze, ``- ``-Listen,
nummerierte Absaetze, ``|``-Tabellen, ``**fett**``/``*kursiv*``, ``---``,
``> ``-Zitate) und gibt HTML mit Klassen aus -- das Aussehen macht allein das
CSS (``CSS`` fuer das Handy, ``web_pdf.DRUCK_CSS`` fuer A4). Nur
Standardbibliothek: der Webserver hat keine weiteren Abhaengigkeiten.

Nur unter ``[skript] verdichtet`` (Padua) aufgerufen -- ohne Schalter bleibt
jede Seite byte-gleich. Kein Modellaufruf, kein Datenbankzugriff."""

from __future__ import annotations

import html
import re

from interview_theater import sprache

T = sprache.Texte(__name__)

_TEXT_ZITAT_KOPF = "Interviewzitat · {nummer}"
_TEXT_KOPF = "Aufbau & Rollen"
_TEXT_WER = "Wer"
_TEXT_ROLLE = "Rolle"
_TEXT_CHARAKTER = "Charakter"
_TEXT_ROLLE_MEHR = "{name} — was, nie, wann"
_TEXT_UEBERSICHT = "Übersicht"
_TEXT_PARTITUR = "Partitur auf einen Blick"
_TEXT_NR = "#"
_TEXT_MOMENT = "Moment"
_TEXT_THEMA = "Thema"
_TEXT_SKRIPT = "Skript"
_TEXT_WO = "Wo"

#: Die drei Orte eines Moments (G3), kurz fuer Tabelle und Badge.
MODUS = {"microphone": "🎤 Mikro", "one_to_one": "👂 1:1", "collective": "👥 Alle"}

#: Hoechstens so viele Stichworte in der Spalte Character (Merkmal 5).
CHARAKTER_STICHWORTE = 3
THEMA_ZEICHEN = 70


def _e(wert) -> str:
    return html.escape(str(wert or ""))


def _inline(zeile: str) -> str:
    """Maskiert eine Zeile und setzt **fett**, *kursiv* und ``NAME:`` am
    Anfang fett; in einer Replik werden Klammern zur Regie (grau-kursiv)."""
    # Ein maskierter Stern (``\*``) ist ein woertlicher Stern -- so markiert
    # das Modell erfundene Zeilen (G3-Beschluss); er setzt nie Kursiv.
    z = _e(zeile).replace("\\*", _STERN)
    z = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", z)
    z = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", z)
    # Ziffern gehoeren dazu: G3 spricht als "VOCE 2:".
    sprecher = re.match(r"([A-ZÀ-Ý][A-ZÀ-Ý0-9' .()/-]{1,30}):\s", z)
    if sprecher and re.search(r"[A-ZÀ-Ý]{2}", sprecher.group(1)):
        rest = re.sub(r"\(([^()]*)\)", r'<span class="regie">(\1)</span>', z[sprecher.end():])
        z = f"<strong>{sprecher.group(1)}:</strong> {rest}"
    return z.replace(_STERN, "*")


_STERN = "\x00"


_NUMMER_KOPF = re.compile(r"^\*[^*]*?\((\d+)\):?\*:?\s*")
_NUMMER_FUSS = re.compile(r"\s*\((?:Interview|Intervista|Interviewzitat)\s+(\d+)\)\s*[.,;:]?\s*$")
_ZITAT_IM_ABSATZ = re.compile(
    r"[“\"]([^”\"]{12,}?)[”\"]\s*\((?:Interview|Intervista)\s+(\d+)\)\s*[.,;:]?\s*")


def _zitat_html(text: str, nummer: str | None) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = f"“{text[1:-1]}”"
    kopf = (f'<span class="zitat-kopf">{_e(T._TEXT_ZITAT_KOPF.format(nummer=nummer))}</span>'
            if nummer else "")
    return f'<blockquote class="interviewzitat">{kopf}<span class="zitat-text">{_inline(text)}</span></blockquote>'


def _zitatzeile_html(zeile: str) -> str:
    inhalt = zeile.lstrip()[1:].strip()
    nummer = None
    kopf = _NUMMER_KOPF.match(inhalt)
    if kopf:
        nummer, inhalt = kopf.group(1), inhalt[kopf.end():]
    fuss = _NUMMER_FUSS.search(inhalt)
    if fuss:
        nummer, inhalt = nummer or fuss.group(1), inhalt[:fuss.start()]
    return _zitat_html(inhalt, nummer)


def _ist_label(zeile: str) -> bool:
    """``THEME``, ``INSTRUCTIONS (WHO DOES WHAT)``, ``OPENING LINES (Italian,
    as played)``: Versalien vor der ersten Klammer, kein Doppelpunkt."""
    vorne = zeile.split("(")[0].strip()
    buchstaben = [z for z in vorne if z.isalpha()]
    return (":" not in zeile and len(buchstaben) >= 3 and len(zeile) <= 60
            and all(z.isupper() for z in buchstaben))


def _ist_listenpunkt(zeile: str) -> bool:
    return bool(re.match(r"\s*[-*•]\s+\S", zeile)) and not zeile.lstrip().startswith("**")


def _absatz_html(zeilen: list[str]) -> str:
    erste = re.match(r"(\d+)\.\s+(.*)", zeilen[0])
    if erste:
        innen = "<br>".join([_inline(erste.group(2))] + [_inline(z) for z in zeilen[1:]])
        return f'<ol start="{erste.group(1)}"><li>{innen}</li></ol>'
    return "<p>" + "<br>".join(_inline(z) for z in zeilen) + "</p>"


def _tabelle_html(zeilen: list[str]) -> str:
    def zellen(z: str) -> list[str]:
        return [c.strip() for c in z.strip().strip("|").split("|")]

    kopf = "".join(f"<th>{_inline(c)}</th>" for c in zellen(zeilen[0]))
    rumpf = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in zellen(z)) + "</tr>"
                    for z in zeilen[2:])
    return (f'<table class="skript-tabelle"><thead><tr>{kopf}</tr></thead>'
            f"<tbody>{rumpf}</tbody></table>")


def _ist_tabelle(zeilen: list[str]) -> bool:
    return (len(zeilen) >= 2 and all(z.strip().startswith("|") for z in zeilen)
            and bool(re.fullmatch(r"\|?(\s*:?-{3,}:?\s*\|)+\s*:?-*:?\s*\|?", zeilen[1].strip())))


def _block_html(block: str, ohne_zitate: bool = False) -> str:
    zeilen = [z.rstrip() for z in block.splitlines() if z.strip()]
    if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", block.strip()):
        return '<hr class="trenner">'
    if _ist_tabelle(zeilen):
        return _tabelle_html(zeilen)
    stuecke: list[str] = []
    normal: list[str] = []
    liste: list[str] = []

    def leere() -> None:
        if normal:
            stuecke.append(_absatz_html(normal))
            normal.clear()
        if liste:
            stuecke.append("<ul>" + "".join(f"<li>{_inline(p)}</li>" for p in liste) + "</ul>")
            liste.clear()

    for i, zeile in enumerate(zeilen):
        blank = zeile.strip()
        if blank.startswith(">"):
            leere()
            if not ohne_zitate:
                stuecke.append(_zitatzeile_html(blank))
        elif _ist_listenpunkt(blank):
            if normal:
                stuecke.append(_absatz_html(normal))
                normal.clear()
            liste.append(re.sub(r"^[-*•]\s+", "", blank))
        elif re.match(r"#{2,4}\s", blank):
            leere()
            ebene = "h4" if blank.startswith("####") else "h3"
            stuecke.append(f"<{ebene}>{_inline(blank.lstrip('#').strip())}</{ebene}>")
        elif _ist_label(blank):
            leere()
            stuecke.append(f"<h4>{_e(blank)}</h4>")
        elif re.match(r"(Place|Who|Luogo|Chi|Ort|Wer):\s", blank):
            leere()
            stuecke.append(f'<p class="meta">{_inline(blank)}</p>')
        elif (i + 1 < len(zeilen) and _ist_listenpunkt(zeilen[i + 1]) and len(blank) <= 40
              and not normal and blank[0].isupper() and blank[-1] not in ".:;!?"):
            leere()
            stuecke.append(f'<p class="person"><strong>{_e(blank)}</strong></p>')
        elif re.fullmatch(r"\*?\([^()]*\)\*?", blank):
            leere()
            stuecke.append(f'<p class="regie">{_e(blank.strip("*"))}</p>')
        else:
            if liste:
                leere()
            # Ein Zitat mitten im Absatz wird ein eigener Block; der Satz
            # danach beginnt einen neuen Absatz (Merkmal 4).
            rest = blank
            while True:
                treffer = _ZITAT_IM_ABSATZ.search(rest)
                if not treffer:
                    break
                vorher = rest[:treffer.start()].rstrip()
                if ohne_zitate:
                    if vorher:
                        normal.append(vorher)
                    rest = rest[treffer.end():].lstrip()
                    continue
                if vorher:
                    normal.append(vorher)
                leere()
                stuecke.append(_zitat_html(f"“{treffer.group(1)}”", treffer.group(2)))
                rest = rest[treffer.end():]
            if rest:
                normal.append(rest)
    leere()
    return "".join(stuecke)


def text_html(text: str, ohne_zitate: bool = False) -> str:
    """Ein Stage-Script-Text (EN oder IT) als HTML. Die erste Zeile
    ``SCENE 1 — ...`` faellt weg: sie steht schon als Szenenkopf darueber.

    ``ohne_zitate`` (Morgen-Auftrag 1, G1, ``workshop.skript_ohne_zitate_chats``):
    die Interviewzitat-Bloecke (eigene Zeile UND mitten im Absatz) fallen
    weg -- der Rest des Textes bleibt stehen, auch wenn dadurch an einer
    Stelle eine reine Regieanweisung ohne Sprechzeile uebrigbleibt (siehe
    Bericht, G1 Szene 2 "Le voci")."""
    text = (text or "").strip()
    text = re.sub(r"\A(?:SCENE|SCENA|SZENE)\s+\d+\b[^\n]*\n?", "", text).strip()
    bloecke = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    return "".join(_block_html(b, ohne_zitate) for b in bloecke)


# --- Setup & roles (G2, ``arbeitsstand.stage_kopf``) ------------------------

#: Drei Schreibweisen der Rollenzeile: "Wer — Rolle. Character: a, b. Rest"
#: (G2), "Wer - Rolle (a, b). Rest" (G1), "Wer — Rolle. Rest" (ohne Charakter).
_ROLLE_CHARAKTER = re.compile(
    r"(?P<wer>.+?)\s+[—–-]\s+(?P<rolle>[^.]+?)\.\s*Character:\s*(?P<char>.+?)\.\s*(?P<rest>.*)$")
_ROLLE_KLAMMER = re.compile(
    r"(?P<wer>[^—–()]+?)\s+[—–-]\s+(?P<rolle>[^().]+?)\s*\((?P<char>[^()]+)\)\.?\s*(?P<rest>.*)$")
_ROLLE_SCHLICHT = re.compile(
    r"(?P<wer>[^—–()]+?)\s+[—–]\s+(?P<rolle>[^.]+?)\.\s*(?P<char>)(?P<rest>.*)$")
_ROLLE_TEIL = re.compile(
    r"\s*(What (?:she|he|they) do(?:es)?|What never|When (?:she|he|they) steps? (?:in|out)[^:]*):\s*")
_KOPF_ABSCHNITTE = ("SETUP", "ROLES", "IMPOSTAZIONE", "RUOLI")


def _rolle(zeile: str) -> tuple[str, str, str, str] | None:
    treffer = (_ROLLE_CHARAKTER.match(zeile) or _ROLLE_KLAMMER.match(zeile)
               or _ROLLE_SCHLICHT.match(zeile))
    if not treffer:
        return None
    return (treffer["wer"].strip(), treffer["rolle"].strip(), treffer["char"].strip(),
            treffer["rest"].strip())


def _rolle_mehr_html(wer: str, rest: str) -> str:
    teile = _ROLLE_TEIL.split(rest)
    absaetze = [f"<p>{_inline(teile[0].strip())}</p>"] if teile[0].strip() else []
    for label, inhalt in zip(teile[1::2], teile[2::2]):
        absaetze.append(f"<p><strong>{_e(label)}:</strong> {_inline(inhalt.strip())}</p>")
    return (f'<details class="rolle-mehr"><summary>{_e(T._TEXT_ROLLE_MEHR.format(name=wer))}'
            f"</summary>{''.join(absaetze)}</details>")


def kopf_html(text: str, sprache: str | None = None) -> str:
    """Setup & roles: Abschnittstitel, ``Label: Text`` als Label ueber dem
    Text, Rollen als Tabelle Who | Role | Character (hoechstens drei
    Stichworte), "what, never, when" je Person aufklappbar darunter.

    ``sprache`` (G2-Nachtrag, 08.10.2026): gesetzt, wenn der Kopf zweisprachig
    gezeigt wird (EN und IT nacheinander, Aufrufer traegt die Fassungs-
    Label) -- nur das ``lang``-Attribut auf der Section, damit zwei
    Abschnitte entstehen statt einem gemischten."""
    lang_attr = f' lang="{sprache}"' if sprache else ""
    stuecke: list[str] = [f'<h2 class="szenenkopf">{_e(T._TEXT_KOPF)}</h2>']
    rollen: list[tuple[str, str, str, str]] = []
    liste: list[str] = []
    abschnitt = None

    def leere_liste() -> None:
        if liste:
            stuecke.append("<ul>" + "".join(f"<li>{_inline(p)}</li>" for p in liste) + "</ul>")
            liste.clear()

    def leere_rollen() -> None:
        if not rollen:
            return
        kopf = "".join(f"<th>{_e(t)}</th>" for t in (T._TEXT_WER, T._TEXT_ROLLE, T._TEXT_CHARAKTER))
        zeilen = []
        for wer, rolle, char, _rest in rollen:
            stichworte = [w.strip() for w in re.split(r"[,;]", char) if w.strip()]
            zeilen.append(f"<tr><td><strong>{_e(wer)}</strong></td><td>{_e(rolle)}</td>"
                          f"<td>{_e(', '.join(stichworte[:CHARAKTER_STICHWORTE]))}</td></tr>")
        stuecke.append(f'<table class="skript-tabelle rollen-tabelle"><thead><tr>{kopf}</tr></thead>'
                       f"<tbody>{''.join(zeilen)}</tbody></table>")
        stuecke.extend(_rolle_mehr_html(wer, rest) for wer, _r, _c, rest in rollen if rest)
        rollen.clear()

    for zeile in (text or "").splitlines():
        blank = zeile.strip()
        if not blank:
            continue
        if blank.upper() in _KOPF_ABSCHNITTE and blank == blank.upper():
            leere_liste()
            leere_rollen()
            abschnitt = blank
            stuecke.append(f"<h3>{_e(blank)}</h3>")
            continue
        if _ist_listenpunkt(blank):
            liste.append(re.sub(r"^[-*•]\s+", "", blank))
            continue
        leere_liste()
        if abschnitt in ("ROLES", "RUOLI") and (rolle := _rolle(blank)):
            rollen.append(rolle)
            continue
        feld = re.match(r"([A-Z][A-Za-z ]{2,14}(?: \([^()]{1,24}\))?):\s*(.*)$", blank)
        if feld:
            inhalt = f"<br>{_inline(feld.group(2))}" if feld.group(2) else ""
            stuecke.append(f'<p class="feld"><strong>{_e(feld.group(1))}</strong>{inhalt}</p>')
            continue
        stuecke.append(f"<p>{_inline(blank)}</p>")
    leere_liste()
    leere_rollen()
    return f'<section class="probe-szene stage-kopf"{lang_attr}>{"".join(stuecke)}</section>'


# --- Uebersicht vorn (G2 Anweisungen, G3 Momente) ---------------------------

def _kappe(text: str, grenze: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= grenze:
        return text
    return text[:grenze].rsplit(" ", 1)[0].rstrip(" ,;:-") + " …"


def modus_beschriftung(karte: dict | None) -> str:
    karte = karte or {}
    if karte.get("typ") != "moment":
        return ""
    return T.MODUS.get(karte.get("modus") or "", "")


def uebersicht_html(szenen: list[dict]) -> str:
    """Vorn eine Tabelle: bei ueberwiegend Momenten "Score at a glance"
    (# | Moment | Where -- statt drei Spalten nebeneinander), bei
    ueberwiegend Anweisungen "Overview" (# | Moment | Theme | Script);
    sonst nichts."""
    karten = [s.get("karte") or {} for s in szenen]
    # Gezaehlt wird unter den Szenen, die schon eine Karte haben -- die
    # uebrigen stehen trotzdem in der Tabelle.
    typen = [k.get("typ") for k in karten if k]
    if typen and typen.count("moment") * 2 > len(typen):
        titel = T._TEXT_PARTITUR
        spalten = (T._TEXT_NR, T._TEXT_MOMENT, T._TEXT_WO)
        zeilen = [(s.get("nummer"), s.get("titel"), modus_beschriftung(k) or "—")
                  for s, k in zip(szenen, karten)]
    elif typen and typen.count("instructions") * 2 > len(typen):
        titel = T._TEXT_UEBERSICHT
        spalten = (T._TEXT_NR, T._TEXT_MOMENT, T._TEXT_THEMA, T._TEXT_SKRIPT)
        zeilen = [(s.get("nummer"), s.get("titel"), _kappe(k.get("worum"), THEMA_ZEICHEN),
                   "✓" if (s.get("volltext") or "").strip() else "—")
                  for s, k in zip(szenen, karten)]
    else:
        return ""
    kopf = "".join(f"<th>{_e(t)}</th>" for t in spalten)
    rumpf = "".join("<tr>" + "".join(f"<td>{_e(w)}</td>" for w in z) + "</tr>" for z in zeilen)
    return (f'<section class="probe-szene uebersicht"><h2 class="szenenkopf">{_e(titel)}</h2>'
            f'<table class="skript-tabelle"><thead><tr>{kopf}</tr></thead><tbody>{rumpf}</tbody>'
            "</table></section>")


def meta_html(karte: dict | None) -> str:
    """Die Zeile unter dem Szenenkopf: ``Typ · Ort``, bei einem Moment
    ``Ort · Wer`` (der Typ steht dort als Badge im Kopf)."""
    from interview_theater import szenenkarte

    karte = karte or {}
    if karte.get("typ") == "moment":
        teile = [karte.get("ort"), karte.get("wer")]
    else:
        teile = [szenenkarte.T.TYP_BESCHRIFTUNG.get(karte.get("typ"), karte.get("typ")),
                 karte.get("ort")]
    teile = [str(t).strip() for t in teile if t and str(t).strip()]
    return f'<p class="meta">{_e(" · ".join(teile))}</p>' if teile else ""


def badge_html(karte: dict | None) -> str:
    beschriftung = modus_beschriftung(karte)
    return f' <span class="badge">{_e(beschriftung)}</span>' if beschriftung else ""


#: Das Handy-Design (dunkel, Serifentext ~17px/1.6, ~65 Zeichen, Akzent
#: #e3a440). Ohne Kommentar vor einer Regel (``web_vereint.scope_css``).
CSS = """
.stueck { --sk-text: #ece7dc; --sk-leise: #9a9488; --sk-akzent: #e3a440; --sk-linie: #2c2a26; --sk-zitat: #1d1a15; color: var(--sk-text); font: 17px/1.6 'DejaVu Serif', Georgia, serif; }
.stueck .probe-szene { max-width: 65ch; margin: 0 0 1rem; }
.stueck .probe-szene .szenenkopf { font: 600 19px/1.3 'DejaVu Sans', system-ui, sans-serif; color: var(--sk-text); margin: 34px 0 4px; padding-top: 14px; border-top: 1px solid var(--sk-linie); border-bottom: 0; }
.stueck .probe-szene .text { max-width: 65ch; margin-top: .4rem; }
.stueck .probe-szene .text p, .stueck .probe-szene p { margin: 0 0 12px; font-size: 17px; line-height: 1.6; hyphens: manual; }
.stueck .probe-szene h3 { font: 600 13px/1.2 'DejaVu Sans', system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: var(--sk-akzent); margin: 22px 0 6px; }
.stueck .probe-szene h4 { font: 600 12px/1.2 'DejaVu Sans', system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: var(--sk-leise); margin: 20px 0 6px; }
.stueck .probe-szene p.meta, .stueck .probe-szene .text p.meta, .stueck .probe-szene p.angaben, .stueck .probe-szene p.besetzung, .stueck .probe-szene p.sprache-kopf { font: 13px/1.4 'DejaVu Sans', system-ui, sans-serif; color: var(--sk-leise); margin: 0 0 12px; }
.stueck .probe-szene strong { font-family: 'DejaVu Sans', system-ui, sans-serif; font-size: .92em; letter-spacing: .02em; }
.stueck .probe-szene p.sprache-kopf { margin: 22px 0 4px; letter-spacing: .08em; text-transform: uppercase; font-size: 12px; }
.stueck .probe-szene .feld { margin: 0 0 12px; }
.stueck .probe-szene .person { margin: 14px 0 4px; }
.stueck .probe-szene .regie { font-style: italic; color: var(--sk-leise); }
.stueck .probe-szene ul, .stueck .probe-szene ol { padding-left: 20px; margin: 6px 0 14px; }
.stueck .probe-szene li { margin: 4px 0; font-size: 17px; line-height: 1.6; }
.stueck .probe-szene blockquote.interviewzitat { margin: 14px 0; padding: 8px 14px; border: 0; border-left: 3px solid var(--sk-akzent); background: var(--sk-zitat); border-radius: 0 6px 6px 0; font-style: italic; }
.stueck .zitat-kopf { display: block; font: 600 11px/1.6 'DejaVu Sans', system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: var(--sk-akzent); font-style: normal; }
.stueck .zitat-text { display: block; }
.stueck .skript-tabelle { width: 100%; border-collapse: collapse; font: 13.5px/1.4 'DejaVu Sans', system-ui, sans-serif; margin: 8px 0 18px; }
.stueck .skript-tabelle th { text-align: left; color: var(--sk-leise); font-weight: 600; border-bottom: 1px solid var(--sk-akzent); padding: 6px; }
.stueck .skript-tabelle td { border-bottom: 1px solid var(--sk-linie); padding: 7px 6px; vertical-align: top; }
.stueck .skript-tabelle strong { font-size: 1em; }
.stueck .badge { font: 600 12px 'DejaVu Sans', system-ui, sans-serif; color: #121212; background: var(--sk-akzent); border-radius: 10px; padding: 2px 8px; margin-left: 6px; vertical-align: middle; white-space: nowrap; }
.stueck details.rolle-mehr { margin: 4px 0 8px; font-size: 15px; }
.stueck details.rolle-mehr summary { color: var(--sk-akzent); font: 13.5px/1.6 'DejaVu Sans', system-ui, sans-serif; cursor: pointer; }
.stueck details.rolle-mehr p { font-size: 15px; }
.stueck .trenner { border: 0; border-top: 1px solid var(--sk-linie); margin: 18px 0; }
"""
