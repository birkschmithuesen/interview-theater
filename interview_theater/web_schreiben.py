"""Der Schreibweg der Weboberflaeche -- **derselbe wie der der Knoepfe**.

Bis zum 05.09.2026 abends war die Weboberflaeche read-only, und das mit
Begruendung: "sonst laufen zwei Schreibwege gegeneinander"
(NACHTRAG-weboberflaeche-und-sprache.md N1). Die Begruendung gilt weiter --
deshalb gibt es hier keinen zweiten Schreibweg, sondern nur einen zweiten
**Ausloeser** fuer den vorhandenen: jede Funktion in diesem Modul ruft
``repo``-Funktionen auf, genau die, die ``knoepfe._speichere`` und
``erkenner.wende_an`` auch rufen. Kein SQL, keine eigene Tabelle, kein
eigenes Feld.

Drei Regeln, die dieses Modul traegt:

1. **Nur ueber ``repo``.** ``web_daten.py`` bleibt read-only und bekommt
   keinen einzigen Schreibpfad dazu. Der modulweite ``repo._LOCK`` ist
   prozesslokal und richtet gegen die Bot-Prozesse nichts aus -- dafuer
   sorgen WAL und ``busy_timeout`` aus ``db.verbinde`` (dieselbe Annahme, mit
   der ``scripts/begruessen.py`` seit dem 05.09. aus einem fremden Prozess
   in dieselbe Datei schreibt).
2. **Nur die aufgezaehlten Parameter.** ``FELDER`` ist die vollstaendige
   Liste; alles andere ist ein ``Fehler``. Material (Aufnahmen, Transkripte,
   Verdichtungen, Belegzitate), der Szenen-Volltext, das Journal, die
   USA-Einwilligung, der Sprachprofil-Text und die Schaerfungs-Zuordnungen
   stehen bewusst NICHT darin. Ebenso wenig der **Leitfaden**: er wird aus
   seinen Feldern gebaut (``leitfaden.aus_feldern``), nicht getippt --
   editierbar sind die Quellen, nicht das Ergebnis.
   Seit dem Phasen-Umbau (05.09.2026 nachts) fehlen auch **Kernthema,
   Kernthema-Richtung und Kernfrage**: sie sind keine Station mehr,
   ``geschichte`` hat ihre Rolle uebernommen. Gesetzte Werte bleiben
   sichtbar (``NUR_ANZEIGE``), aenderbar sind sie nicht.
3. **Jede Aenderung ins Journal**, ``art='entschieden'``, ``quelle='web'``,
   mit altem und neuem Wert. Der Gespraechs-Bot liest das Journal bei jedem
   Zug frisch (``kontext._baue_journal``) -- er erfaehrt von einer Aenderung
   also im naechsten Zug, ohne dass der Webserver mit Telegram spricht.

**Kein Modellaufruf.** Wie in einem Knopf-Handler (AGENTS.md, Zusage 2)
faellt hier nie ein Sprachmodell-Aufruf an. Wechselt eine Figur ihr
Interview, wird deshalb kein Sprachprofil erzeugt, sondern das vorhandene
geleert und die Abnahme zurueckgenommen -- ``knoepfe.stelle_figur_vor``
erzeugt es beim naechsten Zug im eigenen Thread nach, und ein Journaleintrag
"Sprachprofil neu noetig" haelt fest, warum.
"""

from interview_theater import repo

#: Was im Journal als Quelle steht. Neben ``extraktor``, ``befehl`` und
#: ``knopf`` -- damit im Nachhinein unterscheidbar bleibt, was im Chat und
#: was auf der Gruppenseite entschieden wurde.
QUELLE = "web"

#: Hoechstlaenge je Seite im Journaltext. Eine Frageliste kann tausend
#: Zeichen haben; im Journal steht sie zweimal (alt und neu), und das Journal
#: geht vollstaendig in jeden Gespraechs-Prompt.
JOURNAL_GRENZE = 120

#: Was im Journal steht, wo vorher nichts stand.
LEER = "(leer)"

#: Die fuenf Formen je Szene -- **kleingeschrieben und wortgleich mit**
#: ``szene.FORMEN``: der Knopf im Chat speichert ``"dialog"``, und das
#: Dropdown muss denselben Wert schreiben, sonst stuenden fuer dieselbe Form
#: zwei Schreibweisen in der Datenbank und ``szene.formdatei`` faende bei
#: einer davon den Regelblock nicht mehr. Die Beschriftung macht ``web.py``
#: mit ``capitalize()``, genau wie ``knoepfe.biete_szenenform``.
#:
#: Hier noch einmal als Literal statt importiert: ``szene`` zieht ``httpx``
#: nach, und der Webserver kommt mit der Standardbibliothek aus. Dass die
#: beiden Listen gleich bleiben, haelt
#: ``test_web_edit.test_formen_sind_die_aus_szene`` fest.
FORMEN = ("dialog", "monolog", "chor", "lied", "rap")

#: Die Stil-Slugs je Szene (06.09.2026, Birk 12:50) -- **wortgleich mit**
#: ``stile.STILE``: der Knopf im Chat speichert ``"litanei"``, und das
#: Dropdown muss denselben Wert schreiben, sonst faende
#: ``stile.regelblock`` die Prompt-Datei nicht mehr. Wie bei ``FORMEN`` hier
#: als Literal statt importiert (``stile`` haengt an ``anweisungen`` und
#: damit am Prompt-Verzeichnis; der Webserver kommt mit der
#: Standardbibliothek aus). Dass die Listen gleich bleiben, haelt
#: ``test_web_edit.test_stile_sind_die_aus_stile`` fest.
STILE = ("schlagabtausch", "litanei", "herkules")

#: Die Beschriftungen dazu -- fuer das Dropdown. Mit der Herkunft, wie im
#: Chat: wer waehlt, soll wissen, woher das Mass kommt (dieselbe Zusage wie
#: in ``stile.menuetext``).
STIL_BESCHRIFTUNG = {
    "schlagabtausch": "Knapper Schlagabtausch (Schatten — Morpheuz x Monet192)",
    "litanei": "Litanei (Lovesong — Adele)",
    "herkules": "Herkules-Maß (Herkules.exe — ArtesMobiles)",
}

#: Die Arbeitsstandfelder, die die Gruppenseite setzen darf, mit ihrer
#: Beschriftung im Journal. Eine echte Teilmenge von
#: ``repo._ARBEITSSTAND_FELDER``: ``format`` fehlt, weil es die Frage seit dem
#: 05.09.2026 abends nicht mehr gibt (was zaehlt, ist die Form je Szene);
#: ``figuren_entwurf``, ``figur_aktuell``, ``aenderung_offen`` und
#: ``figuren_fixiert_am`` sind Merkposten der Knopfwege und keine Parameter
#: des Stuecks.
ARBEITSSTANDFELDER = {
    # ``rahmen`` heisst seit dem Phasen-Umbau nach aussen **Setting** (Ort,
    # Zeit, Anlass) -- der Spaltenname bleibt, die Beschriftung folgt dem, was
    # die Gruppe im Chat hoert (AGENTS.md, "Phase 4 heisst Setting & Figuren").
    "rahmen": "Setting",
    # Die Geschichte im Groben (Phase 5): Bogen und Ende. Sie hat die Rolle
    # uebernommen, die frueher das Kernthema hatte.
    "geschichte": "Geschichte",
}

#: **Was der Chat führt** (Birk, 06.09.2026 10:25). Diese Felder stehen auf der
#: Gruppenseite an ihrem gewohnten Platz -- die Phase ganz oben, Begriffe und
#: Fragen darunter --, aber als Anzeige. Sie entstehen im Gespräch über Knöpfe
#: und Ping-Pong, oft mit einem Modellaufruf dahinter (Sensibilitätsprüfung,
#: Eröffnung/Abschluss), und der Webserver hat keinen Modellklienten. Sie hier
#: umtippen zu lassen hieße, denselben Wert auf zwei Wegen zu pflegen, von
#: denen einer die halbe Kette auslässt. Von den drei Leitfaden-Feldern steht
#: gar nicht das Rohfeld auf der Seite, sondern der **gebaute Leitfaden**
#: (``leitfaden.aus_feldern``): das, was die Gruppe im Interview in der Hand
#: hält.
#:
#: Reine Dokumentation dessen, was ``FELDER`` nicht enthält -- gerendert wird
#: nach dieser Liste nichts (das tut ``web._bearbeiten_html`` an Ort und
#: Stelle). Der Test dazu hält beides zusammen.
FUEHRT_DER_CHAT = (
    "phase", "begriffe", "fragen",
    "frage_einleitungen", "interview_eroeffnung", "interview_abschluss",
)

#: Was die Gruppenseite **anzeigt, aber nicht mehr ändert** -- die Felder der
#: alten Dramaturgie (Umbau 05.09.2026 nachts). Kernthema, Kernfrage und
#: Kernthema-Richtung bleiben im Code funktional und rückwärtskompatibel, sind
#: aber keine Station mehr: ``geschichte`` hat ihre Rolle übernommen. Ein
#: Formular dafür wäre eine Einladung, an einer Stelle weiterzuarbeiten, die
#: der Bot nicht mehr anbietet -- gesetzte Werte einer bestehenden Gruppe
#: sollen trotzdem sichtbar bleiben, statt stumm zu verschwinden.
#:
#: Anders als ``FUEHRT_DER_CHAT`` wird hiernach wirklich gerendert
#: (``web._altbestand_html``), und zwar nur, was gesetzt ist.
NUR_ANZEIGE = {
    "kernthema": "Kernthema",
    "kernthema_richtung": "Kernthema-Richtung",
    "kernfrage": "Kernfrage",
    "hauptkonflikt": "Hauptkonflikt",
}

#: Die Szenenfelder, die die Gruppenseite setzen darf, mit Beschriftung.
#: ``volltext`` fehlt mit Absicht: der Szenentext entsteht im Chat und wird
#: dort abgenommen ("Passt" / "Passt, aber anders"), die Regie-Notiz bleibt
#: Sache des Gespraechs. ``kernsaetze`` und ``kurzbeschreibung`` fehlen, weil
#: die Auswahl klein bleiben soll.
SZENENFELDER = {
    "titel": "Titel",
    "form": "Form",
    # Die Stilvorlage (06.09.2026, Birk 12:50) -- wie die Form ein Dropdown,
    # kein Freitext: ein getippter Slug, den es nicht gibt, waere ein Stil
    # ohne Regelblock.
    "stil": "Stil",
    "ort": "Ort",
    "zeit": "Zeit",
    "anlass": "Anlass",
    "was_passiert": "Was passiert",
    "was_anders": "Was anders ist",
    "ton": "Ton",
}


class Fehler(Exception):
    """Ein Wert, den die Gruppenseite nicht schreiben darf oder kann.

    Der Aufrufer (``web.py``) macht daraus HTTP 400 mit dem Text als Klartext
    -- ein Bedienfehler, kein Serverfehler: die Gruppe soll lesen koennen,
    was nicht ging."""


def _kuerze(wert: str | None) -> str:
    """Ein Wert, wie er im Journal steht: getrimmt, einzeilig, hoechstens
    ``JOURNAL_GRENZE`` Zeichen.

    Einzeilig, weil eine Frageliste sonst zehn Journalzeilen aus einem
    Eintrag macht und der Journalblock im Prompt seine Form verliert."""
    text = " ".join((wert or "").split())
    if not text:
        return LEER
    if len(text) <= JOURNAL_GRENZE:
        return text
    return text[: JOURNAL_GRENZE - 1].rstrip() + "…"


def journaltext(label: str, alt: str | None, neu: str | None) -> str:
    """Die eine Zeile, die jede Web-Aenderung im Journal hinterlaesst.

    Immer mit **altem und neuem** Wert: das Journal ist der Ort, an dem der
    Weg zu einer Entscheidung steht (SPEC § 2), und "Kernthema geaendert"
    allein sagt nicht, was vorher galt -- weder der Gruppe beim Nachlesen
    noch dem Bot im naechsten Zug."""
    return (
        f"{label} geändert über die Gruppenseite: "
        f"{_kuerze(alt)} → {_kuerze(neu)}"
    )


def _notiere(conn, chat_id: int, label: str, alt, neu) -> None:
    repo.schreibe_journal(
        conn, chat_id, "entschieden", journaltext(label, alt, neu), quelle=QUELLE
    )


def _text(wert) -> str:
    """Was aus dem Formular kommt, als getrimmter Text. ``None`` und Zahlen
    inbegriffen -- der Browser schickt JSON, und ein Zahlenfeld kommt als
    Zahl an."""
    if wert is None:
        return ""
    return str(wert).strip()


def _leer_zu_none(text: str) -> str | None:
    """Ein geleertes Formularfeld leert das Datenbankfeld (``NULL``), statt
    einen Leerstring zu speichern -- so "entfernt" der Arbeitsstand seit
    NACHTRAG N3, und nur so gilt ein Feld anschliessend wieder als ungesetzt
    (``phasen.voraussetzungen`` prueft auf Wahrheitswert)."""
    return text or None


# --- Figuren und Szenen: Zugehoerigkeit pruefen ---------------------------


def _figur(conn, chat_id: int, figur_id):
    """Die Figur zu dieser id -- aber nur, wenn sie dieser Gruppe gehoert.

    Die Pruefung ist der Grund, warum es diese Funktion gibt: das Token in
    der URL adressiert **eine** Gruppe, und eine id im Formular darf daran
    nicht vorbeigreifen. Ohne sie koennte ein Token fuer Gruppe 1 die Figuren
    von Gruppe 2 umbenennen -- alle Gruppen teilen sich eine Datenbank
    (AGENTS.md: "Jede Tabelle ausser bot_zustand hat chat_id")."""
    try:
        zeile = repo.hole_figur_nach_id(conn, int(figur_id))
    except (TypeError, ValueError):
        raise Fehler("Figur nicht gefunden.") from None
    if zeile is None or zeile["chat_id"] != chat_id or zeile["entfernt_am"]:
        raise Fehler("Figur nicht gefunden.")
    return zeile


def _szene(conn, chat_id: int, szene_id):
    """Die Szene zu dieser id, mit derselben Zugehoerigkeitspruefung wie
    ``_figur``."""
    try:
        zeile = repo.hole_szene(conn, int(szene_id))
    except (TypeError, ValueError):
        raise Fehler("Szene nicht gefunden.") from None
    if zeile is None or zeile["chat_id"] != chat_id or zeile["entfernt_am"]:
        raise Fehler("Szene nicht gefunden.")
    return zeile


def _szenenname(zeile) -> str:
    nummer = zeile["nummer"]
    return f"Szene {nummer}" if nummer is not None else "Szene"


# --- Die einzelnen Parameter ----------------------------------------------


# Die Phase setzt allein die Gruppe -- und zwar im Chat (AGENTS.md,
# "Die Phase setzt allein die Gruppe"). Sie stand hier einmal als Dropdown und
# ist am 06.09.2026 wieder herausgenommen worden (Birk): der Bot bietet den
# Wechsel im Fluss an, sobald die Materiallage ihn hergibt
# (``knoepfe.biete_phase_proaktiv``), und ein zweiter Weg daneben macht aus
# einem Angebot eine Einstellung. Auf der Gruppenseite steht die Phase weiter
# ganz oben -- als Anzeige, die alles darunter einordnet.


def _setze_arbeitsstand(feld: str):
    """Baut den Handler fuer ein Arbeitsstandfeld -- alle sechs sind
    derselbe Vorgang: alten Wert lesen, ``repo.setze_arbeitsstand`` rufen,
    Journalzeile anhaengen."""

    def handler(conn, chat_id: int, wert, ziel) -> str:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        alt = (stand[feld] if stand else None) or ""
        neu = _text(wert)
        repo.setze_arbeitsstand(conn, chat_id, feld, _leer_zu_none(neu))
        _notiere(conn, chat_id, ARBEITSSTANDFELDER[feld], alt, neu)
        return neu

    return handler


def _setze_figurenfeld(feld: str, label: str):
    """Name oder Beschreibung einer Figur, ueber ihre id."""

    def handler(conn, chat_id: int, wert, ziel) -> str:
        zeile = _figur(conn, chat_id, ziel)
        neu = _text(wert)
        if feld == "name" and not neu:
            raise Fehler("Eine Figur braucht einen Namen.")
        alt = zeile[feld] or ""
        repo.setze_figur_feld(conn, zeile["id"], feld, neu)
        _notiere(conn, chat_id, f"Figur {zeile['name']} · {label}", alt, neu)
        return neu

    return handler


def _setze_figur_quelle(conn, chat_id: int, wert, ziel) -> str:
    """Aus welchem Interview eine Figur spricht.

    Drei Schreibvorgaenge, und der zweite und dritte sind der eigentliche
    Punkt: das gespeicherte Sprachprofil stammt aus dem **alten** Interview
    und waere nach dem Wechsel eine Behauptung ueber eine Stimme, die so nie
    gesprochen hat. Es wird deshalb geleert und die Abnahme der Figur
    zurueckgenommen (``geprueft_am = NULL``, genau wofuer
    ``repo.setze_figur_geprueft`` gedacht ist). ``knoepfe.stelle_figur_vor``
    erzeugt das Profil beim naechsten Zug im eigenen Thread nach -- **hier**
    laeuft kein Modell (AGENTS.md, Zusage 2: kein Modellaufruf im
    Web-Prozess).

    Der Journalvermerk "Sprachprofil neu noetig" steht als ``offen`` da, nicht
    als ``entschieden``: er ist eine offene Aufgabe, keine Entscheidung -- und
    der Bot liest ihn im naechsten Gespraechszug mit."""
    from interview_theater import kontext

    zeile = _figur(conn, chat_id, ziel)
    text = _text(wert)
    if text and not text.isdigit():
        raise Fehler("Interview nicht gefunden.")
    neue_id = int(text) if text else None
    erlaubte = {a["id"] for a in _interviews(conn, chat_id)}
    if neue_id is not None and neue_id not in erlaubte:
        raise Fehler("Interview nicht gefunden.")

    alt_id = zeile["quelle_aufnahme_id"]
    if alt_id == neue_id:
        return text
    alt = kontext.interviewbezeichnung(conn, chat_id, alt_id) if alt_id else ""
    neu = kontext.interviewbezeichnung(conn, chat_id, neue_id) if neue_id else ""

    repo.setze_figur_quelle(conn, zeile["id"], neue_id)
    repo.setze_sprachprofil(conn, zeile["id"], "", [])
    repo.setze_figur_geprueft(conn, zeile["id"], None)
    _notiere(conn, chat_id, f"Figur {zeile['name']} · Interview", alt, neu)
    repo.schreibe_journal(
        conn,
        chat_id,
        "offen",
        f"Sprachprofil neu nötig: {zeile['name']} spricht jetzt aus "
        f"{neu or 'keinem Interview'}.",
        quelle=QUELLE,
    )
    return text


def _entferne_figur(conn, chat_id: int, wert, ziel) -> str:
    """Entfernt eine Figur -- **weich** (NACHTRAG N3), wie ``/figur <Name>
    entfernen``: die Zeile bleibt stehen und bekommt ``entfernt_am``."""
    zeile = _figur(conn, chat_id, ziel)
    name = repo.entferne_figur(conn, chat_id, zeile["name"])
    repo.schreibe_journal(
        conn,
        chat_id,
        "entschieden",
        f"Figur {_kuerze(name or zeile['name'])} entfernt über die Gruppenseite",
        quelle=QUELLE,
    )
    return ""


def _lege_figur_an(conn, chat_id: int, wert, ziel) -> str:
    """Legt eine Figur mit Namen und leerer Beschreibung an -- ueber
    ``repo.setze_figur``, denselben Weg wie der Erkenner."""
    name = _text(wert)
    if not name:
        raise Fehler("Eine Figur braucht einen Namen.")
    if repo.hole_figur(conn, chat_id, name) is not None:
        raise Fehler(f"„{name}“ gibt es schon.")
    repo.setze_figur(conn, chat_id, name, "")
    repo.schreibe_journal(
        conn,
        chat_id,
        "entschieden",
        f"Figur {_kuerze(name)} angelegt über die Gruppenseite",
        quelle=QUELLE,
    )
    return name


def _setze_szenenfeld(feld: str, label: str):
    """Ein Planungsfeld einer Szene, ueber ``repo.setze_szenenfeld`` -- das
    ruehrt nie mehr als dieses eine Feld an (die Regel, an der die additive
    Szenenplanung haengt)."""

    def handler(conn, chat_id: int, wert, ziel) -> str:
        zeile = _szene(conn, chat_id, ziel)
        alt = zeile[feld] or ""
        neu = _text(wert)
        repo.setze_szenenfeld(conn, zeile["id"], feld, _leer_zu_none(neu))
        _notiere(conn, chat_id, f"{_szenenname(zeile)} · {label}", alt, neu)
        return neu

    return handler


def _setze_szene_figuren(conn, chat_id: int, wert, ziel) -> str:
    """Die Besetzung einer Szene, als Liste von Figur-ids.

    ``repo.setze_szene_figuren`` ersetzt die Besetzung, statt zu ergaenzen --
    genau das, was eine Mehrfachauswahl im Formular meint."""
    zeile = _szene(conn, chat_id, ziel)
    roh = wert if isinstance(wert, list) else str(wert or "").split(",")
    ids = []
    for eintrag in roh:
        text = _text(eintrag)
        if not text:
            continue
        ids.append(_figur(conn, chat_id, text)["id"])
    alt = ", ".join(f["name"] for f in repo.szene_figuren(conn, zeile["id"]))
    repo.setze_szene_figuren(conn, chat_id, zeile["id"], ids)
    neu = ", ".join(f["name"] for f in repo.szene_figuren(conn, zeile["id"]))
    _notiere(conn, chat_id, f"{_szenenname(zeile)} · Besetzung", alt, neu)
    return neu


def _interviews(conn, chat_id: int) -> list[dict]:
    """Die zuordenbaren Interviews -- ueber ``repo.transkripte``, damit auch
    hier kein SQL steht. Dieselbe Reihenfolge wie
    ``kontext.interviewbezeichnung`` sie nummeriert."""
    return [
        {"id": a["id"]}
        for a in repo.transkripte(conn, chat_id)
        if a["klasse"] == "lang"
    ]


#: Die vollstaendige Liste dessen, was die Gruppenseite schreiben darf.
#: Alles, was hier nicht steht, ist ein ``Fehler`` -- und das ist der
#: Unterschied zwischen "read-only mit Ausnahmen" und "beschreibbar mit
#: Grenzen".
FELDER = {
    **{feld: _setze_arbeitsstand(feld) for feld in ARBEITSSTANDFELDER},
    "figur_name": _setze_figurenfeld("name", "Name"),
    "figur_beschreibung": _setze_figurenfeld("beschreibung", "Beschreibung"),
    "figur_quelle": _setze_figur_quelle,
    "figur_entfernen": _entferne_figur,
    "figur_neu": _lege_figur_an,
    **{
        f"szene_{feld}": _setze_szenenfeld(feld, label)
        for feld, label in SZENENFELDER.items()
    },
    "szene_figuren": _setze_szene_figuren,
}


def wende_an(conn, chat_id: int, feld: str, wert, ziel=None) -> dict:
    """Schreibt einen Parameter der Gruppenseite. Liefert die Antwort, die
    als JSON zurueckgeht: ``{"ok": True, "feld": ..., "wert": ...}``.

    ``conn`` ist eine **schreibende** Verbindung (``db.verbinde``, also WAL
    und ``busy_timeout``) -- die read-only geoeffnete Leseverbindung der
    GET-Route taugt hier nicht und wuerde von SQLite abgewiesen.

    Ein unbekanntes Feld ist ein ``Fehler`` und keine ``KeyError``: das kommt
    aus einem Formular, also von aussen."""
    handler = FELDER.get(feld)
    if handler is None:
        raise Fehler(f"Unbekannter Parameter: {feld}")
    neu = handler(conn, chat_id, wert, ziel)
    return {"ok": True, "feld": feld, "wert": neu, "id": ziel}
