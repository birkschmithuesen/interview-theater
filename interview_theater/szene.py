"""Szenentexte schreiben -- der erste Aufruf mit aktivem Reasoning
(SPEC-kontext-architektur.md § 4.5, § 6.2 Block 4/5).

Das Hauptziel des ganzen Werkzeugs ist ein guter Theatertext. Genau dort
hoerte der Code bisher auf: die Tabelle ``szene`` stand leer im Schema,
``LLM.prosa`` war toter Code. Bekaeme die Gruppe ihren Szenentext im normalen
Gespraechszug, bekaeme sie ihn von einem Aufruf, der auf Dialog optimiert ist
-- Reasoning aus, erzwungenes Schema ``{"antwort"}``, Systemanweisung "fass
dich kurz". Deshalb ein eigener Weg.

**Warum hier Reasoning AN ist und sonst nirgends.** Die Entscheidung folgt
der Matrix in ``reasoning-stufen-entscheidungshilfe.md`` § 4.2, nicht dem
Gefuehl, dass Szenentext "wichtiger" waere: nicht die Wichtigkeit einer
Aufgabe entscheidet, sondern ob ein Mensch auf die Antwort wartet und ob die
Aufgabe strukturell profitiert. Beim Szenentext ist beides guenstig --
dramaturgische Abwaegung ueber viele Interviewstellen hinweg, und **niemand
wartet**, weil dieser Aufruf ausdruecklich nicht im Gespraechszug laeuft,
sondern in einem eigenen Thread. Extraktion, Klassifikation und der
Gespraechszug bleiben unveraendert bei ``"none"``; dort kostete Reasoning nur
Latenz (Faktor 7-23) und koennte bei Regeln mit Ausnahmen sogar schaden.

Zwei gemessene Randbedingungen, die daran haengen (dieselbe Wissensdatei
§ 3.2, § 4.3): bei aktivem Reasoning ``max_tokens >= 12.000``, sonst endet
der Lauf im Denken und liefert HTTP 200 mit leerem Inhalt; und ein
Zeitbudget, das nicht der 30-Sekunden-Klient aus ``bot.main`` vorgibt.

**Ablauf.** Der Absichtserkenner (art ``szene_schreiben``) oder der Befehl
``/szene`` rufen ``starte()``. Das schickt sofort eine Zeile in die Gruppe --
sie soll wissen, dass etwas laeuft, und derweil weiterarbeiten koennen -- und
gibt den eigentlichen Aufruf an einen Thread ab (Muster: der Nachhol-Arbeiter
in ``aufnahme.py``). Der baut den Prompt, ruft ``LLM.prosa``, trennt
TITEL/KURZ vom Text, speichert die Szene, schreibt einen
``entschieden``-Journaleintrag und schickt Titel samt Anfang in die Gruppe.

**Eine Szene je Gruppe gleichzeitig** (Sperre je ``chat_id``, wie in
``ablauf.py``). Anders als dort wird aber nichts gesammelt: ein zweiter
Auftrag waehrend eines laufenden Laufs bekommt eine kurze Zeile und wird
verworfen. Zwei parallele Szenenlaeufe waeren zwei teure, langsame Aufrufe,
deren Ergebnisse einander in ``geaendert_am`` ueberholen -- die Gruppe saehe
zwei Szenen und wuesste nicht, welche gilt.

**Fehler werden gemeldet** (SPEC § 11.1): anders als beim Absichtserkenner
wartet die Gruppe hier tatsaechlich, sie hat gerade eine Ankuendigung
bekommen. Also eine kurze, ehrliche Zeile plus ``vorfall``
``szene_fehlgeschlagen``. Kein eigener Wiederholungsversuch ueber die drei
aus ``llm.py`` hinaus -- ein vierter Anlauf an einem 90-Sekunden-Aufruf
haette die Gruppe minutenlang hingehalten.
"""

from __future__ import annotations

import logging
import re
import threading

from interview_theater import anweisungen, kontext, repo

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf`` (Modus B setzt ``LLM.prosa``).
ART = "szene"

#: Ausgabebudget. Aktives Reasoning verbraucht es VOR dem eigentlichen
#: Inhalt; unter 12.000 endet der Lauf im Denken und liefert HTTP 200 mit
#: leerem Inhalt (gemessen 04.09.2026, reasoning-stufen-entscheidungshilfe.md
#: § 3.2 Fussnote 1 und § 4.3). Deutlich groesser als llm.MAX_TOKENS = 9000,
#: das fuer Aufrufe ohne Reasoning bemessen ist.
MAX_TOKENS = 12_000

#: Zeitbudget des einzelnen Versuchs. Der httpx.Client aus ``bot.main`` hat
#: 30 s -- das reicht fuer einen Reasoning-Lauf nicht: gemessen wurden 33,8 s
#: fuer freien Prosatext bei Kimi und 20-50 s bei Qwen, ohne die zusaetzliche
#: Laenge eines Szenentextes. Die Wissensdatei nennt 60 s als Untergrenze fuer
#: Reasoning-Aufrufe (§ 4.4), der Auftrag 90 s; hier grosszuegiger, weil ein
#: Timeout hier nichts spart -- niemand wartet aktiv, und ein abgebrochener
#: Lauf ist trotzdem bezahlt.
TIMEOUT_S = 150.0

#: Obergrenze des Nutzertextes in geschaetzten Token (kontext.schaetze,
#: Zeichen // 3). Darueber fliegen die Volltranskripte raus und die
#: Verdichtungen ruecken nach. Bewusst hoch -- doppelt so hoch wie
#: kontext.ZIEL fuer den Gespraechszug: hier SOLL das Rohmaterial mit, der
#: Text soll aus dem Material kommen und nicht aus Zusammenfassungen davon.
DECKEL = 40_000

#: So viele nichtleere Zeilen der Szene gehen als Vorschau in die Gruppe.
VORSCHAU_ZEILEN = 6

#: Nur in den ersten paar Zeilen der Modellantwort wird nach TITEL/KURZ
#: gesucht -- weiter unten waere ein "TITEL:" Teil der Szene, nicht ihr Kopf.
_KOPFZEILEN = 6

_TEXT_ANGEKUENDIGT = (
    "Ich schreibe die Szene aus, das dauert eine Minute - ihr koennt derweil "
    "weiterarbeiten."
)
_TEXT_BESETZT = "Ich schreibe gerade noch an einer Szene, gleich."
_TEXT_FEHLER = (
    "Die Szene ist mir nicht gelungen. Sagt es nochmal, dann versuche ich es neu."
)
_TEXT_VOLLSTAENDIG = "Vollstaendig auf eurer Gruppenseite."


class SzeneFehler(Exception):
    """Der Szenen-Aufruf lieferte nichts Verwertbares."""


# Eine Sperre je chat_id, genau wie in ablauf.py -- Szenenlaeufe verschiedener
# Gruppen duerfen sich nie gegenseitig blockieren. Sie wird im aufrufenden
# Thread genommen (in starte(), damit ein zweiter Auftrag SOFORT eine Antwort
# bekommt) und im Arbeitsthread wieder freigegeben; das ist der Grund fuer
# threading.Lock statt RLock -- ein RLock liesse sich vom fremden Thread gar
# nicht freigeben.
_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    """Liefert die (ggf. neu angelegte) Sperre fuer eine chat_id."""
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def systemanweisung() -> str:
    """Die Systemanweisung des Szenen-Aufrufs: ``prompts/szene.md`` plus die
    Negativliste ``prompts/theater-tells.md``, beide heiss nachgeladen.

    Die Tells stehen ausdruecklich in einer eigenen Datei und werden erst
    hier im Code angehaengt: sie sind der Teil, den die Gruppe im Workshop
    laufend erweitert ("das klingt schon wieder wie ChatGPT"), waehrend die
    Anweisung selbst stehen bleibt. Zwei Dateien, zwei Aenderungsrhythmen --
    und dank des Hot-Reloads in ``anweisungen.py`` wirkt eine Ergaenzung ohne
    Neustart, beim naechsten Szenen-Auftrag."""
    return anweisungen.hole("szene") + "\n\n" + anweisungen.hole("theater-tells")


# ---------------------------------------------------------------------------
# Auftrag lesen
# ---------------------------------------------------------------------------

#: Erkennt eine Szenennummer im Auftrag ("Szene 2: ...", "schreib Szene 3
#: nochmal", "szene nr. 4"). Ausgeschriebene Zahlwoerter ("die zweite Szene")
#: erkennt das bewusst nicht: ein falsch geratener Treffer wuerde eine
#: bestehende Szene ueberschreiben, ein verpasster legt nur eine neue an. Die
#: Fehlerrichtung ist damit die harmlose.
_NUMMER = re.compile(r"\bszene\s*(?:nr\.?|nummer)?\s*(\d{1,3})\b", re.IGNORECASE)


def nummer_aus_auftrag(auftrag: str) -> int | None:
    """Liest die Szenennummer aus dem Auftrag, oder None.

    Nennt der Auftrag eine Nummer, zu der es schon eine Szene gibt, wird
    diese ueberschrieben (der Normalfall "Szene 2 nochmal, aber kuerzer");
    sonst entsteht eine neue."""
    treffer = _NUMMER.search(auftrag or "")
    return int(treffer.group(1)) if treffer else None


def _szene_mit_nummer(szenen, nummer: int | None):
    if nummer is None:
        return None
    return next((s for s in szenen if s["nummer"] == nummer), None)


def _naechste_nummer(szenen) -> int:
    vorhandene = [s["nummer"] for s in szenen if s["nummer"] is not None]
    return max(vorhandene) + 1 if vorhandene else 1


# ---------------------------------------------------------------------------
# Prompt-Zusammenbau (eigener, nicht kontext.baue)
# ---------------------------------------------------------------------------


def _arbeitsstand_text(conn, chat_id: int) -> str:
    """Kernthema, Hauptkonflikt, Begriffe und Figuren -- eine eigene, schlanke
    Formatierung statt der privaten ``kontext._baue_arbeitsstand``, aus
    demselben Grund wie in ``erkenner._arbeitsstand_text``: dort haengt seit
    heute die Szenenliste mit dran, die hier einen eigenen Block bekommt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)

    zeilen = []
    if stand:
        if stand["kernthema"]:
            zeilen.append(f"Kernthema: {stand['kernthema']}")
        if stand["hauptkonflikt"]:
            zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
        if stand["begriffe"]:
            zeilen.append(f"Begriffe: {stand['begriffe']}")
    for figur in figuren:
        beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
        zeilen.append(f"Figur {figur['name']}{beschreibung}")

    if not zeilen:
        return ""
    return "Arbeitsstand der Gruppe:\n" + "\n".join(zeilen)


def _transkripte_text(conn, chat_id: int) -> str:
    """ALLE Volltranskripte, ohne den Schalter ``/wortlaut`` zu fragen.

    Im Gespraechs-Prompt sind sie 5.000 Token Dauerlast, die jede Antwort
    unschaerfer macht (SPEC § 6.2 Block 3) -- hier sind sie der Punkt: der
    Szenentext soll aus dem Material kommen und Repliken woertlich daraus
    uebernehmen duerfen. Nur Klasse *lang* zaehlt als Material, kurze
    Gespraechsbeitraege sind Zurufe -- und je Interview ein zusammengefuegtes
    Transkript ueber alle seine Teile (§ 10.6)."""
    zeilen = []
    for a in repo.transkripte(conn, chat_id):
        if a["klasse"] != "lang":
            continue
        transkript = repo.zusammengefuegtes_transkript(conn, a["id"])
        if transkript:
            zeilen.append(f"--- {a['name']} ---\n{transkript}")
    if not zeilen:
        return ""
    return "Interviews im Wortlaut:\n" + "\n\n".join(zeilen)


def _verdichtungen_text(conn, chat_id: int) -> str:
    """Der Ersatz fuer die Transkripte, wenn der Deckel reisst -- Verdichtungen
    samt Belegzitaten sind knapp und behalten wenigstens den Originalton der
    Zitate."""
    bloecke = []
    for v in repo.verdichtungen(conn, chat_id):
        aufnahme = repo.hole_aufnahme(conn, v["aufnahme_id"])
        name = aufnahme["name"] if aufnahme else f"Aufnahme {v['aufnahme_id']}"
        eintrag = [f"{name}: {v['zusammenfassung']}"]
        for thema in repo.themen_zu(conn, v["id"]):
            if thema["beleg_zitat"]:
                eintrag.append(f'  - {thema["thema"]}: "{thema["beleg_zitat"]}"')
            else:
                eintrag.append(f'  - {thema["thema"]}')
        bloecke.append("\n".join(eintrag))
    if not bloecke:
        return ""
    return (
        "Verdichtungen der Interviews (die Volltranskripte waren zu lang):\n"
        + "\n\n".join(bloecke)
    )


def _szenenliste_text(conn, chat_id: int, ziel) -> str:
    """Die bisherigen Szenen als Titel plus Kurzbeschreibung. Die Szene, die
    ueberarbeitet werden soll, bleibt hier weg -- sie kommt gleich darunter
    im Volltext, und zweimal dasselbe Stichwort verwirrt nur."""
    zeilen = [
        kontext.szenenzeile(s)
        for s in repo.hole_szenen(conn, chat_id)
        if ziel is None or s["id"] != ziel["id"]
    ]
    if not zeilen:
        return ""
    return "Bisherige Szenen:\n" + "\n".join(zeilen)


def _ueberarbeitung_text(ziel) -> str:
    """Die zu ueberarbeitende Szene im Volltext.

    Sie geht nur bei einer Ueberarbeitung mit -- also dann, wenn der Auftrag
    die Nummer einer schon vorhandenen Szene nennt. Bei einer neuen Szene
    waere ein fremder Volltext vor allem eine Vorlage zum Abschreiben."""
    if ziel is None or not ziel["volltext"]:
        return ""
    return (
        f"Diese Szene soll ueberarbeitet werden ({kontext.szenenzeile(ziel)}):\n"
        f"{ziel['volltext']}"
    )


def _verworfen_text(conn, chat_id: int) -> str:
    """Die ``verworfen``-Zeilen des Journals -- damit Verworfenes nicht durch
    die Hintertuer im Szenentext wiederkommt. Das Journal ist der einzige Ort,
    an dem eine Ablehnung samt Grund ueberhaupt festgehalten ist (SPEC § 2)."""
    zeilen = [
        f"- {e['text']}" for e in repo.journal(conn, chat_id) if e["art"] == "verworfen"
    ]
    if not zeilen:
        return ""
    return (
        "Das hat die Gruppe verworfen, es kommt nicht wieder vor:\n" + "\n".join(zeilen)
    )


#: Reihenfolge des Nutzertextes. Wie in kontext.py: stabil nach vorn,
#: entscheidend nach hinten -- was am Ende des Prompts steht, wiegt am
#: schwersten (SPEC § 6.1). Der Auftrag steht deshalb zuletzt und nicht
#: zuerst: er ist die eine Zeile, die diesen Lauf von jedem anderen
#: unterscheidet, und darf nicht hinter 40.000 Token Rohmaterial verschwinden.
_REIHENFOLGE = (
    "arbeitsstand", "material", "szenenliste", "ueberarbeitung", "verworfen", "auftrag",
)


def _zusammen(bloecke: dict) -> str:
    return "\n\n".join(bloecke[k] for k in _REIHENFOLGE if bloecke.get(k))


def baue_nutzertext(conn, e, chat_id: int, auftrag: str, ziel=None) -> str:
    """Baut den Nutzertext des Szenen-Aufrufs -- ein eigener Zusammenbau, nicht
    ``kontext.baue``.

    Die Budgets dort sind fuer den Chat bemessen: Transkripte nur auf
    ``/wortlaut``, Szenen nur die zuletzt geaenderte, Ziel 20.000 Token. Hier
    ist die Materiallage eine andere -- alle Interviews im Wortlaut, alle
    Szenentitel, das ganze Verworfene.

    Jeder Block faellt weg, solange seine Daten leer sind (dasselbe
    datengetriebene Prinzip wie in ``kontext.baue``). Reisst der Deckel
    DECKEL, fliegen die Volltranskripte raus und die Verdichtungen ruecken
    nach -- eine einzige Kuerzungsstufe, keine zweite: das Fenster des
    Gespraechs ist hier gar nicht dabei, und alles andere ist entweder kurz
    (Arbeitsstand, Szenenliste) oder unverzichtbar (Auftrag)."""
    bloecke = {
        "arbeitsstand": _arbeitsstand_text(conn, chat_id),
        "material": _transkripte_text(conn, chat_id),
        "szenenliste": _szenenliste_text(conn, chat_id, ziel),
        "ueberarbeitung": _ueberarbeitung_text(ziel),
        "verworfen": _verworfen_text(conn, chat_id),
        "auftrag": f"Euer Auftrag:\n{auftrag.strip()}",
    }

    if kontext.schaetze(_zusammen(bloecke)) > DECKEL:
        bloecke["material"] = _verdichtungen_text(conn, chat_id)
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "kuerzung",
            "Szenen-Prompt ueber Deckel: Volltranskripte durch Verdichtungen ersetzt",
        )

    return _zusammen(bloecke)


# ---------------------------------------------------------------------------
# Antwort lesen
# ---------------------------------------------------------------------------


def _kopfwert(zeile: str, schluessel: str) -> str | None:
    """Liest ``TITEL: ...`` bzw. ``KURZ: ...`` aus einer Zeile, oder None.

    Fuehrende Sternchen, Rauten und Backticks werden abgeraeumt, bevor
    verglichen wird: das Modell setzt seine Kopfzeilen gern in Markdown
    (``**TITEL:** Am Bahnhof``), und daran soll das Auslesen nicht scheitern."""
    nackt = zeile.strip().lstrip("*#`> ").strip()
    if not nackt.upper().startswith(schluessel):
        return None
    rest = nackt[len(schluessel):].lstrip("*` ")
    if not rest.startswith(":"):
        return None
    return rest[1:].strip().strip("*` ").strip()


def zerlege(text: str) -> tuple[str | None, str | None, str]:
    """Trennt ``TITEL:``/``KURZ:`` vom eigentlichen Szenentext.

    Liefert ``(titel, kurzbeschreibung, volltext)``; die ersten beiden koennen
    None sein. Fehlt der Kopf ganz, ist der gesamte Text die Szene -- ein
    fehlender Titel ist kein Grund, einen fertigen Szenentext wegzuwerfen. Der
    Aufrufer setzt dann 'Szene N' ein."""
    zeilen = text.splitlines()
    titel = kurz = None
    ab = 0
    for i, zeile in enumerate(zeilen[:_KOPFZEILEN]):
        if not zeile.strip():
            ab = i + 1
            continue
        wert = _kopfwert(zeile, "TITEL")
        if wert is not None and titel is None:
            titel, ab = wert, i + 1
            continue
        wert = _kopfwert(zeile, "KURZ")
        if wert is not None and kurz is None:
            kurz, ab = wert, i + 1
            continue
        break

    volltext = "\n".join(zeilen[ab:]).strip()
    return (titel or None), (kurz or None), volltext


def _vorschau(nummer: int, titel: str, volltext: str) -> str:
    """Titel, die ersten VORSCHAU_ZEILEN nichtleeren Zeilen, der Verweis auf
    die Gruppenseite. Nicht der ganze Text: ein bis drei Seiten Dialog in
    einer Telegram-Nachricht waeren auf dem Handy unlesbar, und die Szene
    stuende danach mitten im Verlaufsfenster jedes weiteren Aufrufs."""
    zeilen = [z for z in volltext.splitlines() if z.strip()][:VORSCHAU_ZEILEN]
    return "\n".join([f"Szene {nummer}: {titel}", "", *zeilen, "", _TEXT_VOLLSTAENDIG])


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


def _sende_und_merke(conn, tg, e, chat_id: int, text: str) -> None:
    """Schickt eine Zeile und schreibt sie als Bot-Nachricht mit -- wie
    ``ablauf.antworte`` und ``erkenner._melde_interviewmodus``, damit sie im
    Verlaufsfenster des naechsten Gespraechszugs steht. Ein Fehlschlag beim
    Senden wird nur geloggt: er darf den Szenenlauf nicht mitreissen."""
    try:
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
            text, repo._jetzt(),
        )
    except Exception:
        log.exception("Szenen-Nachricht fehlgeschlagen, chat_id=%s", chat_id)


def schreibe(conn, tg, klm, e, chat_id: int, auftrag: str) -> int:
    """Der eigentliche Szenen-Aufruf: Prompt bauen, Modell fragen, Szene
    speichern, Journal schreiben, Vorschau in die Gruppe schicken. Liefert
    die Nummer der geschriebenen Szene.

    Laeuft im Thread aus ``starte()``; wer sie direkt aufruft (Tests, ein
    kuenftiger Stapellauf), bekommt sie synchron und muss sich selbst um die
    Sperre kuemmern. Fehler fliegen heraus -- ``_lauf()`` faengt sie."""
    nummer = nummer_aus_auftrag(auftrag)
    ziel = _szene_mit_nummer(repo.hole_szenen(conn, chat_id), nummer)

    nutzer = baue_nutzertext(conn, e, chat_id, auftrag, ziel)
    antwort = klm.prosa(
        chat_id, systemanweisung(), nutzer, ART,
        max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
    )

    titel, kurz, volltext = zerlege(antwort)
    if not volltext:
        raise SzeneFehler("Antwort des Sprachmodells enthielt keinen Szenentext")

    if ziel is not None:
        nummer = ziel["nummer"]
        repo.aktualisiere_szene(conn, ziel["id"], titel or ziel["titel"], kurz, volltext)
    else:
        if nummer is None:
            nummer = _naechste_nummer(repo.hole_szenen(conn, chat_id))
        repo.lege_szene_an(conn, chat_id, nummer, titel, kurz, volltext)

    titel = titel or f"Szene {nummer}"
    # Das Journal haelt fest, was gilt (SPEC § 2) -- eine geschriebene Szene
    # ist eine Festlegung der Gruppe, kein Vorschlag. Der Eintrag steht
    # danach im Gespraechs-Prompt und im Szenen-Prompt jedes weiteren Laufs.
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Szene {nummer} geschrieben: {titel}",
        quelle="szene",
    )
    _sende_und_merke(conn, tg, e, chat_id, _vorschau(nummer, titel, volltext))
    return nummer


def _lauf(conn, tg, klm, e, chat_id: int, auftrag: str, sperre: threading.Lock) -> None:
    """Der Thread-Rumpf: ``schreibe()`` mit Fehlerbehandlung und garantierter
    Freigabe der Sperre. Bliebe sie bei einem Fehlschlag liegen, koennte die
    Gruppe fuer den Rest des Workshops keine Szene mehr schreiben lassen."""
    try:
        schreibe(conn, tg, klm, e, chat_id, auftrag)
    except Exception:
        log.exception("Szenen-Aufruf fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), "szene_fehlgeschlagen",
                "Szenen-Aufruf fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall zum Szenen-Fehler nicht schreibbar, chat_id=%s", chat_id)
        # Anders als beim Absichtserkenner erfaehrt die Gruppe davon: sie hat
        # gerade die Ankuendigung bekommen und wartet (SPEC § 11.1).
        _sende_und_merke(conn, tg, e, chat_id, _TEXT_FEHLER)
    finally:
        sperre.release()


def starte(conn, tg, klm, e, chat_id: int, auftrag: str) -> threading.Thread | None:
    """Kuendigt die Szene an und gibt den Aufruf an einen eigenen Thread ab.

    Liefert den gestarteten Thread, oder None, wenn nichts angestossen wurde
    (leerer Auftrag, oder es laeuft schon eine Szene fuer diese Gruppe). Der
    Rueckgabewert ist fuer Tests da, die auf das Ende warten wollen -- im
    Betrieb interessiert sich niemand dafuer, das ist der Sinn der Sache."""
    auftrag = (auftrag or "").strip()
    if not auftrag:
        return None

    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende_und_merke(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None

    _sende_und_merke(conn, tg, e, chat_id, _TEXT_ANGEKUENDIGT)
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, auftrag, sperre), daemon=True,
    )
    try:
        thread.start()
    except Exception:
        # Kommt der Thread nicht hoch, gibt ihn auch niemand mehr frei --
        # dann bliebe die Sperre bis zum Prozessende liegen.
        sperre.release()
        raise
    return thread
