"""Die Texttabelle ist vollstaendig, und jeder Nutzertext laeuft ueber sie (D3).

Am Quelltext geprueft (AST), wie ``test_knoepfe_struktur.py``: ein neuer
Knopftext, der am Zugriff ``T`` vorbeigeht, faellt hier auf und nicht erst
in Padua im Chat.

1. Jeder Zugriff ``T.NAME`` / ``modul.T.NAME`` zeigt auf eine deutsche
   Modul-Konstante und hat einen englischen Eintrag.
2. Kein englischer Eintrag ohne deutsche Konstante.
3. Platzhalter (``{name}``, ``{{name}}``, ``%s``) gleich, Blatt fuer Blatt;
   Behaelter gleich gebaut; ``slug``/``command`` woertlich gleich.
4. In einem umgestellten Modul liest niemand eine registrierte Konstante
   mehr nackt (``_TEXT_X`` statt ``T._TEXT_X``).
5. Ein umgestelltes Modul hat keine deutsche Konstante ausserhalb der
   Tabelle und keine deutschen Inline-Literale -- ausser mit Grund.
"""

import ast
import pathlib
import re

import pytest

from interview_theater import sprache

PAKET = pathlib.Path(sprache.__file__).resolve().parent

#: Module (Kurzname), deren Texte ueber T laufen. Waechst je Aufgabe.
UMGESTELLT: set[str] = {
    "anweisungen", "knoepfe.texte", "knoepfe.basis", "knoepfe.fragen",
    "knoepfe.interviews", "knoepfe.stationen", "knoepfe.figuren",
    "knoepfe.szenen", "knoepfe.wirkung",
    "befehle", "bot", "leitfaden", "phasentexte", "fehlstellen", "phasen",
    "aufnahme", "ablauf", "erkenner", "kontext", "journal", "verdichter",
    "kuerzung", "vorspann", "sprecher", "stile", "arbeitszeilen",
    "szene", "szenenfolge", "kurzgeschichte", "schaerfung", "sprachprofil",
    "sprachstil", "kernzitate", "stueckpruefung", "dramaturgie.beleg",
    "dramaturgie.fanout", "dramaturgie.mechanik", "web_schreiben", "web",
    "laengen", "sprachpass", "web_vereint",
}

#: Was UMGESTELLT in Aufgabe 17 erreicht haben muss.
ALLE_MODULE = {
    "ablauf", "anweisungen", "arbeitszeilen", "aufnahme", "befehle", "bot",
    "dramaturgie.beleg", "dramaturgie.fanout", "dramaturgie.mechanik",
    "erkenner", "fehlstellen", "journal", "kernzitate", "knoepfe.basis",
    "knoepfe.figuren", "knoepfe.fragen", "knoepfe.interviews",
    "knoepfe.stationen", "knoepfe.szenen", "knoepfe.texte", "knoepfe.wirkung",
    "kontext", "kuerzung", "kurzgeschichte", "leitfaden", "phasen",
    "phasentexte", "schaerfung", "sprachprofil", "sprachstil", "sprecher",
    "stile", "stueckpruefung", "szene", "szenenfolge", "verdichter",
    "vorspann", "web", "web_schreiben", "laengen", "sprachpass",
    "web_vereint",
}

#: Bleibt deutsch, mit Grund (nie im Chat, nie im Prompt einer Gruppe).
BLEIBT_DEUTSCH = {
    "dramaturgie.bilanz.KOPF": "Betreiberausgabe (scripts/dramaturgie_pruefen.py)",
    "dramaturgie.bilanz.OHNE_VERGLEICH": "Betreiberausgabe",
    "dramaturgie.schleife.GRUENDE": "Betreiberausgabe (--schleife)",
    "dramaturgie.schleife.MELDUNG_OHNE_GESCHICHTENWEG": "Betreiberausgabe (--schleife)",
    "szenenfolge.DETAIL_RICHTUNG_UNVOLLSTAENDIG": "Vorfall-Detail, Dashboard des Teams",
    "stile._NACH_SLUG": (
        "Aufgabe 15: nur Mitgliedschaftspruefung der Slugs (Protokoll); die "
        "Anzeige liest stile._eintrag zur Aufrufzeit aus T.STILE"
    ),
    # Aufgabe 16
    "dramaturgie.beleg.GRUND_ZU_KURZ": "Log-Grund (Belegstand.grund), nur im Log",
    "dramaturgie.beleg.GRUND_FEHLT": "Log-Grund (Belegstand.grund), nur im Log",
    "dramaturgie.beleg.GRUND_NICHT_GEFUNDEN": "Log-Grund (Belegstand.grund), nur im Log",
    # Aufgabe 23: dramaturgie.fanout.TEXT_SZENENAUFTRAG steht nicht mehr
    # hier -- der Szenennummer-Parser liest jetzt beide Sprachen, der
    # Auftrag geht ueber T. Nachbesserung (Review-Befund 3): die Konstante
    # gibt es seitdem gar nicht mehr, fanout.szenenauftrag delegiert an
    # szene.T.TEXT_AUFTRAG_NEU (wortgleich, eine Quelle statt zwei).
    # Aufgabe 17: Skript und Stil der Webseiten -- deutsch sind nur die
    # Kommentare darin. Die Meldungen des Speicherns liest _BEARBEITEN_JS aus
    # data-Attributen (#meldungen, web._JS_*), nicht aus dem Skript.
    "web._SCROLL_JS": "JavaScript, nur Kommentare deutsch (kein Nutzertext)",
    "web._BEARBEITEN_JS": "JavaScript, nur Kommentare deutsch; Meldungen aus data-Attributen",
    "web._TEXTBUCH_JS": "JavaScript, nur Kommentare deutsch (kein Nutzertext)",
    # Karte R, Aufgabe 5: Protokollwerte der Journalzeile, gelesen von
    # kontext und Weboberflaeche -- kein Nutzertext.
    "laengen.JOURNAL_ART": "Protokoll (journal.art), kein Nutzertext",
    "laengen.JOURNAL_QUELLE": "Protokoll (journal.quelle), kein Nutzertext",
    "web._CSS_DASHBOARD": "CSS, nur Kommentare deutsch",
    "web._CSS_GRUPPE": "CSS, nur Kommentare deutsch",
    "web._CSS_BUEHNE": "CSS, nur Kommentare deutsch",
    "web._TABS_JS": "JavaScript, nur Kommentare deutsch (kein Nutzertext)",
    "web._CSS_LEITFADEN": "CSS, nur Kommentare deutsch",
    "web._CSS_TEXTBUCH": "CSS, nur Kommentare deutsch",
    # Aufgabe 15 (Karte W): Skript und Stil der vereinten Seite -- deutsch
    # sind nur die Kommentare darin, kein Nutzertext.
    "web_vereint._CSS_VEREINT": "CSS, nur Kommentare deutsch",
    "web_vereint._VEREINT_JS": "JavaScript, nur Kommentare deutsch (kein Nutzertext)",
    "web_vereint._STROM_JS": "JavaScript, nur Kommentare deutsch (kein Nutzertext)",
    # erkenner-fp (02.10.2026): eine Fuellwort-Liste zur Erkennung
    # inhaltsloser Festlegungen (_ohne_eigenen_inhalt), kein Nutzertext --
    # sie wird nie angezeigt, nur gegen den Wortlaut der Gruppe geprueft, und
    # ist deshalb wie stile._NACH_SLUG reine Mitgliedschaftspruefung.
    "erkenner._FESTLEGUNG_FUELLWOERTER": "Fuellwortliste, kein Nutzertext (nur Mitgliedschaftspruefung)",
}

#: Wortlisten fuer Parser (D5) -- keine Texttabelle, sondern Code mit
#: englischem Gegenstueck *_EN (Aufgaben 22-24).
PARSER = {
    "ablauf._DENKSPUR_MARKER", "ablauf._DENKSPUR_EINDEUTIG",
    "ablauf._AUFTRAGSFORMEN", "ablauf._SYSTEMZEILEN",
    "befehle._ENTFERNEN_WOERTER", "kontext._SYSTEMANFAENGE",
    # Aufgabe 22: Auswahltabellen je Sprache fuer Befehlsargumente (K5).
    "befehle._ENTFERNEN_JE_SPRACHE", "befehle._AUS",
    "szene._ANDERS_NICHTS", "dramaturgie.mechanik._STRUKTUR",
    "dramaturgie.mechanik._TSCHECHOW_STOPP", "dramaturgie.mechanik._STRANG_STOPP",
    "vorspann.SCHAERFUNGSFORMELN", "stueckpruefung.FRAGEN",
    # Aufgabe 23: Vereinigungen und Parserlisten der Modellausgabe (K5).
    "ablauf._KERN_ANFAENGE", "dramaturgie.mechanik._STRUKTUREN",
}

#: Strukturen mit Funktionen (K4): uebersetzt werden sie ueber eine
#: Beschriftungstabelle im selben Modul, nicht selbst. Schluessel: die
#: Struktur, Wert: der Name ihrer Beschriftungstabelle.
BESCHRIFTET = {
    "phasentexte.PARAMETER": "phasentexte.PARAMETER_BESCHRIFTUNG",
}

#: Registrierte Konstanten, die eine Funktion bewusst NACKT (nicht ueber
#: ``T.``) liest -- mit Grund, wie ``BLEIBT_DEUTSCH``. Regel 4 fängt den
#: Fall ab, in dem ein Text am ``T``-Zugriff vorbeigeht und untranslated an
#: die Gruppe geht; hier geht nichts an die Gruppe -- die deutsche Fassung
#: dient als zweiter, sprachunabhaengiger Vergleichswert.
NACKT_ERLAUBT = {
    "leitfaden.JOURNAL_GEZEIGT":
        "Nachbesserung Aufgabe 14: leitfaden._schon_gezeigt erkennt einen "
        "Journal-Marker aus einer Zeit vor einem Profilwechsel -- dafuer "
        "muss sie die deutsche Konstante UND das aktuelle T.JOURNAL_GEZEIGT "
        "vergleichen, sonst schickt ein Profilwechsel den Leitfaden doppelt.",
    "szene._SZENE_MIT_NUMMER":
        "Aufgabe 16: szene._regienotizen sucht Journalzeilen zu einer Szene "
        "mit beiden Markern (\"Szene N\" und T-Fassung) -- Rundreise ueber "
        "einen Profilwechsel.",
    "szenenfolge._PRUEFVERMERK_ANFANG":
        "Aufgabe 16: zu_pruefen/nimm_pruefvermerk finden Pruef-Vermerke in "
        "beiden Fassungen (Rundreise-Marker).",
    "dramaturgie.fanout.OHNE_SYNOPSE":
        "Aufgabe 16: synopsen_fehlen erkennt den Platzhalter in beiden "
        "Fassungen (Rundreise-Marker).",
}

#: Deutsche Inline-Literale, die bleiben duerfen: Vorfall-Details
#: (repo.merke_vorfall, Dashboard des Teams). Schluessel: Modul und die
#: ersten 40 Zeichen des Literals, wie ``_inline_texte`` sie liefert.
INLINE_ERLAUBT: dict[tuple[str, str], str] = {
    ("knoepfe.basis", "'{}' steht bereits und wurde durch einen"):
        "Vorfall-Detail ueberschreiben_verhindert (repo.merke_vorfall)",
    ("knoepfe.szenen", "Eine Formwahl sollte als Geschichte gesp"):
        "Vorfall-Detail geschichte_war_formwahl (repo.merke_vorfall)",
    # Review-Fix Aufgabe 6 (Karte U): Vorfall-Detail undo_fehlgeschlagen.
    ("knoepfe.wirkung", "nimm_erkenner_lauf_zurueck(lauf_id={}) h"):
        "Vorfall-Detail undo_fehlgeschlagen (repo.merke_vorfall)",
    # Review-Fix Aufgabe 7 (Karte U): Vorfall-Details undo_nicht_angelegt,
    # ueber ``erkenner._merke_undo_vorfall`` an repo.merke_vorfall.
    ("erkenner", "Schnappschuss vor dem Anwenden fehlgesch"):
        "Vorfall-Detail undo_nicht_angelegt (repo.merke_vorfall)",
    ("erkenner", "Schnappschuss nach dem Anwenden fehlgesc"):
        "Vorfall-Detail undo_nicht_angelegt (repo.merke_vorfall)",
    # UX-Knoepfe-Karte, Abschnitt 2: dieselben Vorfall-Details, nur fuer den
    # Knopf-ausgeloesten Zweig (``erkenner.lauf_fuer_knopf``).
    ("erkenner", "Schnappschuss vor dem Knopf-Speichern fe"):
        "Vorfall-Detail undo_nicht_angelegt (repo.merke_vorfall)",
    ("erkenner", "Schnappschuss nach dem Knopf-Speichern f"):
        "Vorfall-Detail undo_nicht_angelegt (repo.merke_vorfall)",
    # Zahlwoerter in ``figuren._zahl_aus``: Parser fuer Gruppentext (D5),
    # die deutsche Liste bleibt im Funktionsrumpf; das englische Gegenstueck
    # steht seit Aufgabe 22 als Modulkonstante ``_ZAHLWOERTER_EN`` daneben.
    ("knoepfe.figuren", "fünf"): "Parser-Wortliste _zahl_aus (Aufgabe 22)",
    ("knoepfe.figuren", "zwölf"): "Parser-Wortliste _zahl_aus (Aufgabe 22)",
    # Aufgabe 15: Vorfall-Details (repo.merke_vorfall, Dashboard des Teams).
    ("ablauf", "kein Kern, zweiter Anlauf"):
        "Vorfall-Detail denkspur_verworfen (repo.merke_vorfall)",
    ("ablauf", "auch der zweite Anlauf war Selbstgesprae"):
        "Vorfall-Detail denkspur_wiederholt (repo.merke_vorfall)",
    ("ablauf", "Antwort war ein Zitat der Gruppe, zweite"):
        "Vorfall-Detail echo_verworfen (repo.merke_vorfall)",
    ("ablauf", "Auch der zweite Anlauf war ein Zitat -- "):
        "Vorfall-Detail echo_wiederholt (repo.merke_vorfall)",
    ("ablauf", "Modellantwort stand zu ueber {} % schon "):
        "Vorfall-Detail wiederholung_verworfen (repo.merke_vorfall)",
    ("ablauf", "Antwort klang wie eine Systemzeile des S"):
        "Vorfall-Detail gespraech_systemzeile_erfunden (repo.merke_vorfall)",
    ("ablauf", "Bot-Antwort in 'nachricht' mitzuschreibe"):
        "Vorfall-Detail gespraechszug_fehlgeschlagen (repo.merke_vorfall)",
    ("aufnahme", "Aufnahme {} ({}) wartet auf Ja/Nein"):
        "Vorfall-Detail interview_ohne_knopf_offen (repo.merke_vorfall)",
    ("erkenner", "Ein Geschichte-Text sollte in den Rahmen"):
        "Vorfall-Detail rahmen_war_geschichte (repo.merke_vorfall)",
    ("erkenner", "Eine Festlegung wiederholte ein gesetzte"):
        "Vorfall-Detail festlegung_stand_schon_im_feld (repo.merke_vorfall)",
    ("erkenner", "Eine Festlegung wiederholte nur die Zuge"):
        "Vorfall-Detail festlegung_ohne_inhalt (repo.merke_vorfall)",
    ("erkenner", "Aenderung art={} konnte nicht angewendet"):
        "Vorfall-Detail erkenner_anwenden_fehler (repo.merke_vorfall)",
    ("kontext", "Nutzertext von {} auf {} Zeichen gekuerz"):
        "Vorfall-Detail kontext_gekuerzt (repo.merke_vorfall)",
    ("kontext", "Nutzertext nach vollstaendiger Kuerzung "):
        "Vorfall-Detail kontext_kuerzung_erfolglos (repo.merke_vorfall)",
    # Aufgabe 16: Vorfall-Details und ein Regex-Muster.
    ("szene", "Chat auf {} Nachrichten"):
        "Vorfall-Detail szene_prompt_gekuerzt (repo.merke_vorfall)",
    ("szene", "Sprachprofil auf {} Zitate je Figur"):
        "Vorfall-Detail szene_prompt_gekuerzt (repo.merke_vorfall)",
    ("szene", ", Systemanweisung {} Token schon abgezog"):
        "Vorfall-Detail szene_prompt_gekuerzt (repo.merke_vorfall)",
    ("szene", " -- REICHT IMMER NOCH NICHT"):
        "Vorfall-Detail szene_prompt_gekuerzt (repo.merke_vorfall)",
    ("dramaturgie.mechanik", "\\b[A-ZÄÖÜ][a-zäöüß]{%d,}\\b"):
        "Regex-Muster fuer Eigennamen (Parser), kein Text",
    # Aufgabe 17 liess das Team-Dashboard deutsch; seit Padua (02.10.2026)
    # laeuft es ueber T -- die vier Ausnahmen dafuer sind entfallen.
    ("web", "interview-theater-web hoert auf http://{"):
        "Startzeile des Dienstes (stdout, betrieb/web.log), Betreiberausgabe",
}

_STOPP = re.compile(
    r"\b(und|nicht|ist|ihr|euch|wir|ich|mit|fuer|für|auf|eine|noch|schon|"
    r"auch|oder|wenn|dass|sich|bitte|jetzt|hier|sind|eure|euer|uns|kein|"
    r"keine|den|dem|du|dein|deine)\b", re.I)
_TEXTNAME = re.compile(r"^_?(TEXT|UEBERSCHRIFT|ANWEISUNG|MELDUNG|JOURNAL|HINWEIS|ZEILE)"
                       r"|_(KOPF|ANSCHLUSS|HINWEIS)$")


def _kurz(pfad: pathlib.Path) -> str:
    return ".".join(pfad.relative_to(PAKET).with_suffix("").parts).removesuffix(".__init__")


BAEUME = {_kurz(p): ast.parse(p.read_text(encoding="utf-8"))
          for p in sorted(PAKET.rglob("*.py"))}


def _konstanten(baum) -> dict[str, ast.AST]:
    fertig = {}
    for knoten in baum.body:
        ziele = []
        if isinstance(knoten, ast.Assign):
            ziele = [z.id for z in knoten.targets if isinstance(z, ast.Name)]
        elif isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Name):
            ziele = [knoten.target.id]
        for z in ziele:
            if re.match(r"^_?[A-Z][A-Z0-9_]*$", z):
                fertig[z] = knoten
    return fertig


KONSTANTEN = {m: _konstanten(b) for m, b in BAEUME.items()}


def _hat_eigenes_t(baum) -> bool:
    return any(
        isinstance(k, ast.Assign)
        and any(isinstance(z, ast.Name) and z.id == "T" for z in k.targets)
        for k in baum.body
    )


def _aliase(modul: str, baum) -> dict[str, str]:
    """Name im Modul -> Kurzname des Moduls, aus dem er stammt, fuer alle
    Importe (auch lokale in Funktionen)."""
    aliase = {}
    for k in ast.walk(baum):
        if isinstance(k, ast.ImportFrom) and k.module and k.module.startswith("interview_theater"):
            basis = k.module[len("interview_theater"):].lstrip(".")
            for n in k.names:
                ziel = f"{basis}.{n.name}".lstrip(".") if f"{basis}.{n.name}".lstrip(".") in BAEUME else basis
                aliase[n.asname or n.name] = ziel
        elif isinstance(k, ast.Import):
            for n in k.names:
                if n.name.startswith("interview_theater."):
                    aliase[n.asname or n.name.split(".")[-1]] = n.name[len("interview_theater."):]
    # ``knoepfe`` re-exportiert T aus knoepfe.texte
    return {name: ("knoepfe.texte" if ziel == "knoepfe" else ziel) for name, ziel in aliase.items()}


def _zugriffe() -> list[tuple[str, str, str, int]]:
    """(lesendes Modul, Zielmodul, NAME, Zeile) fuer jedes T.NAME."""
    fertig = []
    for modul, baum in BAEUME.items():
        aliase = _aliase(modul, baum)
        eigenes = _hat_eigenes_t(baum)
        for k in ast.walk(baum):
            if not isinstance(k, ast.Attribute) or not isinstance(k.value, (ast.Name, ast.Attribute)):
                continue
            wert = k.value
            if isinstance(wert, ast.Name) and wert.id == "T":
                ziel = modul if eigenes else aliase.get("T")
            elif (isinstance(wert, ast.Attribute) and wert.attr == "T"
                  and isinstance(wert.value, ast.Name)):
                ziel = aliase.get(wert.value.id)
                ziel = "knoepfe.texte" if ziel == "knoepfe" else ziel
            else:
                continue
            if ziel is not None:
                fertig.append((modul, ziel, k.attr, k.lineno))
    return fertig


ZUGRIFFE = _zugriffe()


def _tabelle():
    sprache.vergiss()
    return sprache.tabelle("en")


def test_jeder_zugriff_zeigt_auf_eine_deutsche_konstante():
    falsch = [f"{m}:{z} {ziel}.{n}" for m, ziel, n, z in ZUGRIFFE
              if n not in KONSTANTEN.get(ziel, {})]
    assert falsch == []


def test_jeder_zugriff_hat_einen_englischen_eintrag():
    tabelle = _tabelle()
    fehlend = sorted({f"{ziel}.{n}" for _, ziel, n, _ in ZUGRIFFE
                      if n not in tabelle.get(ziel, {})})
    assert fehlend == []


def test_kein_englischer_eintrag_ohne_deutsche_konstante():
    tabelle = _tabelle()
    verwaist = [f"{m}.{n}" for m, eintraege in tabelle.items()
                for n in eintraege if n not in KONSTANTEN.get(m, {})]
    assert verwaist == []


def _paare(deutsch, englisch, pfad):
    if isinstance(deutsch, str):
        yield pfad, deutsch, englisch
    elif isinstance(deutsch, dict):
        assert isinstance(englisch, dict), pfad
        assert {str(k) for k in deutsch} == {str(k) for k in englisch}, pfad
        for k, v in deutsch.items():
            e = englisch[k] if k in englisch else englisch[str(k)]
            if k in ("slug", "command"):
                assert e == v, f"{pfad}.{k} ist Protokoll"
                continue
            yield from _paare(v, e, f"{pfad}.{k}")
    elif isinstance(deutsch, (list, tuple, set, frozenset)):
        assert isinstance(englisch, (list, tuple, set, frozenset)), pfad
        assert len(deutsch) == len(englisch), pfad
        for i, (d, e) in enumerate(zip(deutsch, englisch)):
            yield from _paare(d, e, f"{pfad}[{i}]")


@pytest.mark.parametrize("modul, name", sorted(
    (m, n) for m, eintraege in _tabelle().items() for n in eintraege))
def test_platzhalter_und_form_gleich(modul, name):
    import importlib

    deutsch = getattr(importlib.import_module(f"interview_theater.{modul}"), name)
    englisch = sprache.angleichen(deutsch, _tabelle()[modul][name])
    if isinstance(deutsch, dict) and englisch.keys() != deutsch.keys() and all(
            isinstance(k, str) for k in deutsch):
        # Beschriftungstabelle (K4): deutsche Schluessel, englische Werte
        assert set(englisch) <= set(deutsch), f"{modul}.{name}"
        return
    for pfad, d, e in _paare(deutsch, englisch, f"{modul}.{name}"):
        assert sprache.platzhalter(d) == sprache.platzhalter(e), pfad


def _registriert(tabelle) -> set[tuple[str, str]]:
    return {(m, n) for m, eintraege in tabelle.items() for n in eintraege}


@pytest.mark.parametrize("modul", sorted(UMGESTELLT))
def test_keine_nackte_verwendung(modul):
    tabelle = _tabelle()
    registriert = _registriert(tabelle)
    baum = BAEUME[modul]
    aliase = _aliase(modul, baum)
    nackt = set()
    # Nur Lesezugriffe in Funktionen und Lambdas: dort laeuft Code zur
    # Aufrufzeit. Auf Modulebene setzt die deutsche Tabelle sich aus ihren
    # eigenen Konstanten zusammen -- das ist Definition, keine Verwendung.
    for funktion in ast.walk(baum):
        if not isinstance(funktion, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        for k in ast.walk(funktion):
            if isinstance(k, ast.Name) and isinstance(k.ctx, ast.Load):
                herkunft = modul if k.id in KONSTANTEN[modul] else aliase.get(k.id)
                if (herkunft and (herkunft, k.id) in registriert
                        and f"{herkunft}.{k.id}" not in NACKT_ERLAUBT):
                    nackt.add(f"{modul}:{k.lineno} {k.id}")
    assert sorted(nackt) == []


def _sieht_deutsch_aus(wert) -> bool:
    if isinstance(wert, str):
        return bool(_STOPP.search(wert) or re.search(r"[äöüß]", wert))
    if isinstance(wert, dict):
        return any(_sieht_deutsch_aus(v) for v in wert.values())
    if isinstance(wert, (list, tuple, set, frozenset)):
        return any(_sieht_deutsch_aus(v) for v in wert)
    return False


#: Wachposten: die Zuweisung ist ein leerer Behaelter (Laufzeitzustand wie
#: ``anweisungen._CACHE``), kein Text -- wird von ``test_keine_unuebersetzte_
#: konstante`` uebersprungen, statt seinen (durch andere Tests veraenderten)
#: Laufzeitwert zu bewerten.
_LAUFZEIT = object()

_LEERE_BEHAELTER_AUFRUFE = {"dict", "set", "list", "tuple"}


def _ist_leerer_behaelter(wertknoten) -> bool:
    """True fuer eine Zuweisung wie ``{}``/``[]``/``set()``/``dict()`` --
    ein Behaelter, der zur Laufzeit befuellt wird und keinen Text traegt."""
    if isinstance(wertknoten, ast.Dict):
        return not wertknoten.keys
    if isinstance(wertknoten, (ast.List, ast.Set, ast.Tuple)):
        return not wertknoten.elts
    if (isinstance(wertknoten, ast.Call) and isinstance(wertknoten.func, ast.Name)
            and wertknoten.func.id in _LEERE_BEHAELTER_AUFRUFE
            and not wertknoten.args and not wertknoten.keywords):
        return True
    return False


def _wert_aus_quelltext(modul: str, name: str, knoten):
    """Der Wert einer Modul-Konstante, bevorzugt aus dem Quelltext gelesen.

    Ein leerer Behaelter ist Laufzeitzustand (``_CACHE``, ``_GEMELDET``) und
    wird gar nicht bewertet (Rueckgabe ``_LAUFZEIT``) -- sein tatsaechlicher
    Inhalt haengt von der Testreihenfolge ab, nicht vom Quelltext. Ein
    literaler Wert (String, Zahl, Dict/Liste aus Literalen, ...) kommt per
    ``ast.literal_eval`` direkt aus der Zuweisung. Nur eine abgeleitete,
    nicht-literale Konstante (``re.compile(...)``, ``Pfad / "..."``, ein
    Klassenaufruf) faellt auf ``getattr`` am importierten Modul zurueck --
    wie vor dieser Aenderung.
    """
    wertknoten = knoten.value
    if wertknoten is None:
        wertknoten = ast.Constant(value=None)
    if _ist_leerer_behaelter(wertknoten):
        return _LAUFZEIT
    try:
        return ast.literal_eval(wertknoten)
    except (ValueError, SyntaxError, TypeError):
        import importlib

        m = importlib.import_module(f"interview_theater.{modul}")
        return getattr(m, name, None)


@pytest.mark.parametrize("modul", sorted(UMGESTELLT))
def test_keine_unuebersetzte_konstante(modul):
    tabelle = _tabelle()
    offen = []
    for name, knoten in KONSTANTEN[modul].items():
        schluessel = f"{modul}.{name}"
        if name in tabelle.get(modul, {}) or schluessel in BLEIBT_DEUTSCH or schluessel in PARSER:
            continue
        if schluessel in BESCHRIFTET:
            continue
        if name.startswith("ART_") or name.endswith("_EN"):
            continue
        wert = _wert_aus_quelltext(modul, name, knoten)
        if wert is _LAUFZEIT:
            continue
        if isinstance(wert, re.Pattern):
            continue
        if _sieht_deutsch_aus(wert) or (_TEXTNAME.search(name) and isinstance(wert, str) and wert.strip()):
            offen.append(schluessel)
    assert offen == []


def test_konstanten_menge_ohne_laufzeitzustand_unveraendert():
    """Regressionsanker fuer die Nachbesserung (Review-Befund): die neue
    Bewertung aus dem Quelltext darf keine bisher geprueften echten
    Textkonstanten aus der Pruefung nehmen -- nur die beiden Laufzeit-
    Behaelter ``_CACHE`` und ``_GEMELDET`` fallen weg, die vorher als
    Nebeneffekt der Testreihenfolge geprueft wurden."""
    tabelle = _tabelle()
    modul = "anweisungen"

    def _vorher_geprueft(name) -> bool:
        schluessel = f"{modul}.{name}"
        if name in tabelle.get(modul, {}) or schluessel in BLEIBT_DEUTSCH or schluessel in PARSER:
            return False
        if name.startswith("ART_") or name.endswith("_EN"):
            return False
        return True

    vorher = {n for n in KONSTANTEN[modul] if _vorher_geprueft(n)}
    nachher = {n for n in vorher if _wert_aus_quelltext(modul, n, KONSTANTEN[modul][n]) is not _LAUFZEIT}
    assert vorher - nachher == {"_CACHE", "_GEMELDET"}


def test_gefuellter_cache_faellt_dem_waechter_nicht_zum_opfer():
    """Reproduziert den Review-Befund direkt: ``anweisungen._CACHE`` mit
    einem echten deutschen Prompt gefuellt (wie es ``anweisungen.hole()``
    im Betrieb tut, und wie es in der vollen Suite je nach Reihenfolge vor
    diesem Test passiert) -- der Waechter bleibt gruen, weil er den Cache
    gar nicht mehr bewertet, statt auf eine leere Datenbank zu hoffen."""
    from interview_theater import anweisungen

    anweisungen._CACHE.clear()
    try:
        anweisungen.hole("system")
        assert anweisungen._CACHE, "hole() muesste den Cache fuellen"
        test_keine_unuebersetzte_konstante("anweisungen")
    finally:
        anweisungen._CACHE.clear()


def _inline_texte(baum) -> list[tuple[int, str]]:
    """Deutsche String-Literale in Funktionen -- ohne Docstrings,
    log-/raise-Aufrufe und SQL (dieselbe Heuristik wie
    Anhang A.2 des Plans)."""
    verboten: set[int] = set()
    fertig = []

    class Sammler(ast.NodeVisitor):
        tiefe = 0

        def visit_FunctionDef(self, k):
            if k.body and isinstance(k.body[0], ast.Expr) and isinstance(k.body[0].value, ast.Constant):
                verboten.add(id(k.body[0].value))
            self.tiefe += 1
            self.generic_visit(k)
            self.tiefe -= 1

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, k):
            name = ast.unparse(k.func)
            if re.match(r"^(log|logging|_log|logger)\.", name) or name.endswith(("Fehler", "Error")):
                verboten.update(id(x) for x in ast.walk(k))
            self.generic_visit(k)

        def visit_Raise(self, k):
            verboten.update(id(x) for x in ast.walk(k))
            self.generic_visit(k)

        def visit_JoinedStr(self, k):
            self._pruefe(k, "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in k.values))
            verboten.update(id(x) for x in ast.walk(k))

        def visit_Constant(self, k):
            if isinstance(k.value, str):
                self._pruefe(k, k.value)

        def _pruefe(self, k, text):
            if self.tiefe == 0 or id(k) in verboten:
                return
            if re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|PRAGMA|WITH)\b", text, re.I):
                return
            worte = _STOPP.findall(text)
            if len(worte) >= 2 or (re.search(r"[äöüß]", text) and len(text) > 3) \
                    or (worte and len(text.split()) >= 3):
                fertig.append((k.lineno, text))

    Sammler().visit(baum)
    return fertig


@pytest.mark.parametrize("modul", sorted(UMGESTELLT))
def test_keine_deutschen_inline_texte(modul):
    offen = [f"{modul}:{zeile} {text[:60]!r}"
             for zeile, text in _inline_texte(BAEUME[modul])
             if (modul, text[:40]) not in INLINE_ERLAUBT]
    assert offen == []


@pytest.mark.parametrize("struktur, beschriftung", sorted(BESCHRIFTET.items()))
def test_beschriftungstabelle_deckt_jedes_wort_der_struktur(struktur, beschriftung):
    """K4: jedes sichtbare Wort einer Struktur mit Funktionen steht in ihrer
    Beschriftungstabelle -- deutsch als Identitaet, englisch in der
    Texttabelle. Ein neues Wort in der Struktur ohne Eintrag bliebe in Padua
    stumm deutsch."""
    import importlib

    def woerter(wert):
        if isinstance(wert, str):
            yield wert
        elif isinstance(wert, dict):
            for v in wert.values():
                yield from woerter(v)
        elif isinstance(wert, (list, tuple)):
            for v in wert:
                yield from woerter(v)

    modul, name = struktur.rsplit(".", 1)
    m = importlib.import_module(f"interview_theater.{modul}")
    tabelle = getattr(m, beschriftung.rsplit(".", 1)[1])
    fehlend = sorted(set(woerter(getattr(m, name))) - set(tabelle))
    assert fehlend == []
    assert all(k == v for k, v in tabelle.items())
    englisch = _tabelle()[modul][beschriftung.rsplit(".", 1)[1]]
    assert set(englisch) == set(tabelle)


def test_umgestellt_ist_teilmenge_von_alle_module():
    assert UMGESTELLT <= ALLE_MODULE


def test_alle_module_sind_umgestellt():
    """Aufgabe 17: ab jetzt gilt der Waechter fuer das ganze Paket -- jedes
    Modul mit Nutzertexten liest ueber ``T``."""
    assert UMGESTELLT == ALLE_MODULE
