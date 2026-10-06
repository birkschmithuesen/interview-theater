"""Englische Uebersetzung der gespeicherten Gruppenfelder fuers Regie-
Dashboard (Padua, Karte t_f7770dc4).

Das Dashboard (``web.py``) ist read-only und darf pro Seitenaufruf kein
Modell rufen (``docs/refactoring-guidelines.md`` § 6) -- die Uebersetzung
entsteht deshalb hier, ausserhalb des Web-Request-Pfads, im Bot-Prozess
(``bot._uebersetzungs_schleife``), und landet in der Tabelle ``uebersetzung``
(eine Zeile je Gruppe, Cache ueber einen Hash des Quelltexts).

**Ein Hash, Haeppchen beim Schreiben:** ``segmente()`` sammelt alle
uebersetzungspflichtigen Werte einer Gruppe (Setting, Geschichte, Kernthema,
Hauptkonflikt, Begriffe, Fragen, Figurennamen, Interview-Kurzformen) in ein
flaches Dict fester Schluessel. Weicht der Hash dieses Dicts vom
gespeicherten ``quelle_hash`` ab, uebernimmt ``aktualisiere`` unveraenderte
Schluessel aus dem alten Cache (Vergleich ueber die mitgespeicherten
Quellsegmente, Spalte ``quelle``) und uebersetzt nur die neuen/geaenderten
in Haeppchen von ``HAEPPCHEN_GROESSE`` Schluesseln je Modellaufruf -- ein
einziger Aufruf mit allen (teils ueber 200) Schluesseln einer grossen Gruppe
scheiterte regelmaessig mit ReadTimeout. Die Zeile wird komplett ersetzt,
aber erst, wenn ALLE Schluessel vorhanden sind (wiederverwendet oder frisch
uebersetzt) -- scheitert ein Haeppchen endgueltig, bleibt der alte Cache
unveraendert stehen, und der naechste Lauf setzt dort an.

**Fragen und Begriffe je Zeile/Begriff, nicht als ein Block:** zusaetzlich zu
``FELDER_EINFACH`` bekommt jeder Begriff (``begriff_schluessel``) und jede
Zeile aus ``fragen``/``fragen_auswahl`` (``zeile_schluessel``, Kopf schon
entfernt wie im Dashboard, ``auswahl.zeile_ohne_kopf``) einen eigenen,
inhaltsbasierten Schluessel. So trifft der Cache dieselbe Frage/Ueberschrift
wieder, auch wenn eine neue Sortierung oder A/B-Runde Reihenfolge oder Anzahl
aendert -- die fruehere Uebersetzung von ``fragen`` als EIN Block verfiel bei
jeder solchen Aenderung durch einen Zeilenzahl-Vergleich beim Lesen.

**Alles oder nichts beim Lesen:** ``englisch()`` liefert die gecachten Werte
nur, wenn ihr ``quelle_hash`` zur AKTUELL gespeicherten Quelle passt; sonst
ein leeres Dict. Eine Karte mit teils frischer, teils veralteter Uebersetzung
waere verwirrender als eine Karte, die ehrlich sagt "noch nicht uebersetzt"
und das Original zeigt (``web._dashboard_inhalt_html``, Klasse
``ux-ausstehend``).

Modell: die bestehende Modellkette des Gruppen-Bots (Infomaniak/Kimi via
``e.erkenner_modell`` -- Teilnehmerinhalte bleiben beim souveraenen Anbieter,
keine Claude-Option hier)."""

import hashlib
import json
import logging

log = logging.getLogger(__name__)

#: Sekunden zwischen zwei Laeufen des Uebersetzungs-Schreibers
#: (``bot._uebersetzungs_schleife``). Deutlich laenger als
#: ``aufnahme.NACHHOL_INTERVALL_S`` (60 s): eine Uebersetzung ist nicht
#: zeitkritisch, und ein Lauf kostet einen Modellaufruf je geaenderter Gruppe.
INTERVALL_S = 180

#: Hoechstzahl Schluessel je Modellaufruf. Nach dem Zusammenfuehren mehrerer
#: Klon-Gruppen (Padua, 06.10.2026: eine Gruppe mit 205 Schluesseln) schlug
#: EIN Aufruf mit allen Segmenten regelmaessig mit ReadTimeout fehl (9 von 16
#: Laeufen, Median 125 s). Ein fester, kleiner Wert statt eines gemessenen
#: Optimums: jeder Versuch mit mehr als ein paar Dutzend Schluesseln zeigte
#: in der Praxis denselben Fehler.
HAEPPCHEN_GROESSE = 15

#: Die einfachen, 1:1 uebersetzten Arbeitsstandfelder.
FELDER_EINFACH = ("rahmen", "geschichte", "kernthema", "hauptkonflikt", "begriffe", "fragen")

ART = "uebersetzung"

_SYSTEM = (
    "You translate short fields from a theatre workshop's working document "
    "into English. Translate meaning, not word for word; keep names and "
    "short phrases short. Reply with a JSON object: each key from the input "
    "maps to its English translation as a plain string. Do not add or drop "
    "keys."
)


def hauptthema_quelle(stand: dict) -> str | None:
    """Was auf der Karte als Hauptthema stehen soll, bevor es uebersetzt
    ist: das Kernthema, wenn gesetzt, sonst die ersten Begriffe als kurze
    Zeile -- siehe Kartenbeschreibung ('aus kernthema ableiten, falls
    gesetzt, sonst aus Begriffen/Board')."""
    kernthema = (stand or {}).get("kernthema")
    if kernthema:
        return kernthema
    begriffe = (stand or {}).get("begriffe")
    if begriffe:
        erste = [b.strip() for b in begriffe.split(",") if b.strip()][:3]
        if erste:
            return ", ".join(erste)
    return None


def zeile_schluessel(zeile: str) -> str:
    """Der ``segmente()``-Schluessel einer rohen Fragenzeile aus ``fragen``
    oder ``fragen_auswahl`` -- ueber den INHALT, nicht die Position, damit
    eine neue Sortierung oder A/B-Runde (andere Reihenfolge, andere Anzahl)
    den Cache nicht zerreisst wie die fruehere Zeilen-fuer-Zeile-Zaehlung.
    Auch von ``web._fragen_dashboard_html`` benutzt, um denselben Schluessel
    fuer eine Zeile zu treffen."""
    return "q_" + hashlib.sha1(zeile.strip().encode("utf-8")).hexdigest()[:12]


def begriff_schluessel(text: str) -> str:
    """Der ``segmente()``-Schluessel einer Ueberschrift -- ein Begriff der
    Gruppe ODER ein fremder Kopf (``auswahl.zeile_ohne_kopf``), den die
    Fragengenerierung sich selbst als Zwischenthema gegeben hat. Dieselbe
    Hash-ueber-Inhalt-Logik wie ``zeile_schluessel``."""
    return "b_" + hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


def segmente(stand: dict, figuren: list[dict], kurzformen: list[dict]) -> dict[str, str]:
    """Alle uebersetzungspflichtigen Werte einer Gruppe als flaches Dict,
    Schluessel -> Quelltext. Leere/fehlende Felder bleiben draussen -- ein
    leerer Schluessel waere nichts zu uebersetzen.

    Zusaetzlich zu den Feldern aus ``FELDER_EINFACH``: je Begriff und je
    Fragenzeile (aus ``fragen`` UND ``fragen_auswahl``, waehrend eine Gruppe
    noch sortiert) ein eigener Schluessel (``begriff_schluessel``/
    ``zeile_schluessel``) -- Begriff und Fragetext getrennt, mit dem Kopf
    bereits entfernt (``auswahl.zeile_ohne_kopf``, derselbe Abgleich, den
    das Dashboard beim Anzeigen macht). So trifft ein Hash je Zeile/Begriff
    dieselbe Uebersetzung unabhaengig von Reihenfolge oder Anzahl -- anders
    als die fruehere Uebersetzung von ``fragen`` als EIN Block, die bei
    jeder Umsortierung oder A/B-Runde durch Zeilenzahl-Vergleich verfiel."""
    from interview_theater import auswahl
    from interview_theater import begriffe as begriffe_modul
    from interview_theater import vorschlag

    stand = stand or {}
    seg: dict[str, str] = {}
    for feld in FELDER_EINFACH:
        if stand.get(feld):
            seg[feld] = stand[feld]
    for i, figur in enumerate(figuren or []):
        name = (figur or {}).get("name")
        if name:
            seg[f"figur_{i}"] = name
    for i, eintrag in enumerate(kurzformen or []):
        for j, kurz in enumerate((eintrag or {}).get("kurzformen") or []):
            if kurz:
                seg[f"interview_{i}_{j}"] = kurz
    hauptthema = hauptthema_quelle(stand)
    if hauptthema:
        seg["hauptthema"] = hauptthema

    begriffe_liste = begriffe_modul.zerlege(stand.get("begriffe") or "")
    for begriff in begriffe_liste:
        seg[begriff_schluessel(begriff)] = begriff
    zeilen = (vorschlag.zeilen(stand.get("fragen") or "")
              + vorschlag.zeilen(stand.get("fragen_auswahl") or ""))
    for zeile in zeilen:
        schluessel = zeile_schluessel(zeile)
        if schluessel in seg:
            continue
        frage, fremder_kopf = auswahl.zeile_ohne_kopf(zeile, begriffe_liste)
        seg[schluessel] = frage
        if fremder_kopf:
            seg.setdefault(begriff_schluessel(fremder_kopf), fremder_kopf)
    return seg


def quelle_hash(stand: dict, figuren: list[dict], kurzformen: list[dict]) -> str:
    """Ein Hash ueber alle Segmente -- leer, wenn es nichts zu uebersetzen
    gibt (dann gibt es auch keinen Cache-Eintrag, ``aktualisiere`` legt
    keinen an)."""
    seg = segmente(stand, figuren, kurzformen)
    if not seg:
        return ""
    text = json.dumps(seg, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def englisch(g: dict) -> dict[str, str]:
    """Die gecachten englischen Segmente einer Dashboard-Gruppe
    (``web_daten.dashboard()``-Form), nur wenn der Cache zur aktuell
    gespeicherten Quelle passt -- sonst ein leeres Dict (ausstehend)."""
    cache = g.get("uebersetzung")
    if not cache or not cache.get("felder"):
        return {}
    aktuell = quelle_hash(
        g.get("arbeitsstand") or {}, g.get("figuren") or [],
        g.get("interview_kurzformen") or [],
    )
    if not aktuell or aktuell != cache.get("quelle_hash"):
        return {}
    return cache["felder"]


def _schema(schluessel: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {k: {"type": "string"} for k in schluessel},
        "required": schluessel,
        "additionalProperties": False,
    }


def _uebersetze(klm, chat_id: int, e, seg: dict[str, str]) -> dict[str, str]:
    nutzer = json.dumps(seg, ensure_ascii=False)
    ergebnis = klm.schema(
        chat_id, _SYSTEM, nutzer, _schema(sorted(seg)), ART, modell=e.erkenner_modell,
    )
    return {k: v for k, v in ergebnis.items() if k in seg}


def aktualisiere(conn, klm, e, chat_id: int) -> bool:
    """Uebersetzt die Gruppenfelder ins Englische, wenn sich die Quelle
    seit dem letzten Lauf geaendert hat. Schluessel, deren Quelltext
    unveraendert ist, werden aus dem alten Cache uebernommen; der Rest wird
    in Haeppchen von ``HAEPPCHEN_GROESSE`` neu uebersetzt. Scheitert ein
    Haeppchen endgueltig (nach den eigenen Wiederholungen von
    ``klm.schema``), reisst die Ausnahme durch -- der Cache wird nur
    geschrieben, wenn ALLE Schluessel vorhanden sind, alt bleibt alt stehen.

    Liefert ``True``, wenn der Cache aktualisiert wurde (mit oder ohne
    Modellaufruf, falls alle Schluessel wiederverwendet werden konnten),
    ``False`` bei einem vollstaendigen Cache-Hit (Hash unveraendert) oder
    wenn es nichts zu uebersetzen gibt."""
    from interview_theater import repo

    stand = repo.hole_arbeitsstand(conn, chat_id)
    stand = dict(stand) if stand is not None else {}
    figuren = [dict(f) for f in repo.figuren(conn, chat_id)]
    kurzformen = repo.interview_kurzformen(conn, chat_id)
    seg = segmente(stand, figuren, kurzformen)
    if not seg:
        return False
    hash_ = quelle_hash(stand, figuren, kurzformen)
    vorhanden = repo.hole_uebersetzung(conn, chat_id)
    if vorhanden is not None and vorhanden["quelle_hash"] == hash_:
        return False

    alte_quelle = json.loads(vorhanden["quelle"]) if vorhanden is not None and vorhanden["quelle"] else {}
    alte_felder = json.loads(vorhanden["felder"]) if vorhanden is not None and vorhanden["felder"] else {}
    felder = {
        k: alte_felder[k] for k in seg
        if k in alte_felder and alte_quelle.get(k) == seg[k]
    }
    offen = [k for k in seg if k not in felder]
    for i in range(0, len(offen), HAEPPCHEN_GROESSE):
        haeppchen = offen[i:i + HAEPPCHEN_GROESSE]
        teil = {k: seg[k] for k in haeppchen}
        felder.update(_uebersetze(klm, chat_id, e, teil))
    repo.setze_uebersetzung(conn, chat_id, hash_, seg, felder)
    return True


def aktualisiere_fuer_bot(conn, klm, e) -> int:
    """Uebersetzt alle Gruppen dieses Bot-Prozesses, aber nur mit
    ``[web] dashboard_uebersetzen_en`` im Profil (Padua) -- ohne den
    Schalter (Dortmund/Vorgabe) ist diese Funktion ein No-Op, kein
    Modellaufruf. Liefert die Zahl der tatsaechlichen Uebersetzungslaeufe."""
    from interview_theater import repo, workshop

    if not bool(workshop.aktiv().wert("web.dashboard_uebersetzen_en", False)):
        return 0
    laeufe = 0
    for gruppe in repo.gruppen_fuer_bot(conn, e.bot_name):
        try:
            if aktualisiere(conn, klm, e, gruppe["chat_id"]):
                laeufe += 1
        except Exception:
            log.exception("Uebersetzung fehlgeschlagen, chat_id=%s", gruppe["chat_id"])
    return laeufe
