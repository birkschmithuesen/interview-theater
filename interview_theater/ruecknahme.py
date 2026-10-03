"""Was ein Undo-Knopf zurueckdreht -- die reine Differenz zweier
Schnappschuesse (Karte U, 01.10.2026).

**Warum Diff und nicht Nachbau je Art.** Jede ``erkenner._wende_*_an``-Funktion
nachzubilden ("was schreibt ``kernthema_setzen``?") waere eine zweite Wahrheit
neben der ersten, und sie wuerde beim naechsten Umbau still ausscheren: die
Platzhalter-Zusammenfuehrung (``repo.fuehre_figur_zusammen``) beruehrt drei
Tabellen auf einmal, ``repo.korrigiere_transkripte`` vier. Stattdessen nimmt
``erkenner.laufe`` **vor** und **nach** ``wende_an`` einen Schnappschuss der
verfolgten Tabellen dieser ``chat_id``; was hier daraus entsteht, sind die
Schritte, und ein Umbau an den Schreibpfaden kommt automatisch mit.

**Reine Funktionen, kein SQL.** Der Schnappschuss kommt aus
``repo.schnappschuss``, angewendet wird in ``repo.nimm_erkenner_lauf_zurueck``
-- dieses Modul kennt keine Verbindung. ``db`` wird importiert, aber nur fuer
``_tabellenspalten_aus_schema``: die verglichenen Spalten werden **aus dem
Schema hergeleitet**, damit eine spaeter dazukommende Spalte nicht vergessen
wird (``tests/test_ruecknahme_rundreise.py`` haelt das fest).

**Kein Nutzertext.** Die Wortlaute stehen in ``knoepfe/texte.py``, wie alle
Texte des Knopf-Pakets (K1 aus Karte A1).
"""

import json
from typing import Any, Iterable

from interview_theater import db

#: Die Tabellen, die bei JEDEM Erkennerlauf verfolgt werden -- der Inhalt,
#: den die Gruppe erarbeitet. ``gruppe`` fehlt bewusst (USA-Einwilligung und
#: Interviewmodus haben eigene Knoepfe und eine eigene Nachfrage), ``journal``
#: ebenfalls: es ist nur-anhaengend, die Zeilen des Laufs bleiben stehen und
#: die Ruecknahme haengt eine neue an (AGENTS.md).
VERFOLGT = ("arbeitsstand", "figur", "szene", "szene_figur", "festlegung")

#: Nur bei einem ``transkript_korrigieren`` im Lauf -- und dann nur diese
#: Spalten, nicht die ganzen Zeilen. Zwei Gruende, beide am Code gemessen:
#: ``repo.korrigiere_transkripte`` schreibt genau diese fuenf, und ein Lauf
#: kann daneben ein ``interview_beenden`` tragen, das ebenfalls in
#: ``aufnahme`` schreibt (``beendet_am``, ``status``) -- ein
#: Zeilen-Schnappschuss wuerde ein beendetes Interview wieder oeffnen.
#: Ausserdem liegen in ``aufnahme.transkript`` Megabytes.
MATERIAL = {
    "aufnahme": ("transkript",),
    "verdichtung": ("zusammenfassung",),
    "verdichtung_thema": ("thema", "kurz", "beleg_zitat"),
}

#: Die Erkenner-art, die den Materialteil zuschaltet.
ART_MATERIAL = "transkript_korrigieren"

#: Tabelle -> Primaerschluesselspalten. ``szene_figur`` hat einen
#: zusammengesetzten (db.SCHEMA: PRIMARY KEY (szene_id, figur_id)).
SCHLUESSEL = {
    "arbeitsstand": ("chat_id",),
    "figur": ("id",),
    "szene": ("id",),
    "szene_figur": ("szene_id", "figur_id"),
    "festlegung": ("id",),
    "aufnahme": ("id",),
    "verdichtung": ("id",),
    "verdichtung_thema": ("id",),
}

#: Spalten, die weder verglichen noch zurueckgesetzt werden -- je mit Grund.
#:
#: Drei Sorten: der Primaerschluessel selbst (er ist die Adresse), die
#: Zeitstempel (sie sagen nichts ueber den Inhalt), und die Felder, die
#: **ein anderer, spaeterer Lauf** schreibt und ``wende_an`` nie anfasst.
#: Die dritte Sorte ist die wichtige: ohne sie scheiterte ein Kernthema-Undo
#: daran, dass ein Sprachprofil-Thread danach ``figur.sprachprofil``
#: geschrieben hat, und ein Szenen-Undo daran, dass die Gruppe inzwischen
#: eine Form bestaetigt hat. ``szene.form`` traegt allein ein Knopfdruck:
#: ``erkenner._wende_szene_planen_an`` bildet das Feld ``form`` bewusst auf
#: ``form_vorschlag`` ab (AGENTS.md, "Die Form je Szene ist ein Vorschlag").
AUSSEN = {
    "arbeitsstand": frozenset({
        "chat_id", "geaendert_am",
        # Karte U: kein Undo fuer die Phase. Sie setzt allein die Gruppe.
        "phase", "phase_angeboten", "phase_gesetzt_am",
    }),
    "figur": frozenset({
        "id", "geaendert_am",
        # sprachprofil.py (eigener Thread), Ebene 2 der Figurenarbeit.
        "sprachprofil", "zitate", "geprueft_am",
    }),
    "szene": frozenset({
        "id", "geaendert_am",
        # Geschriebene Texte und die Entscheidungen der Gruppe per Knopf.
        "volltext", "prosa", "zusammenfassung", "fertig_am",
        "fruehere_fassungen", "form", "stil",
    }),
    "szene_figur": frozenset(),
    "festlegung": frozenset({"id", "erstellt_am"}),
}

#: Tabellen mit ``entfernt_am``: eine im Lauf ENTSTANDENE Zeile wird weich
#: entfernt, nicht geloescht (N3, "Weiches Loeschen statt Loeschen").
WEICH = ("figur", "szene", "festlegung")

#: Reine Verknuepfungszeilen ohne ``entfernt_am``: die im Lauf entstandene
#: wird geloescht -- genau das tut ``repo.setze_szene_figuren`` heute schon.
HART = ("szene_figur",)

#: Genau eine Zeile je Gruppe und kein ``entfernt_am``: eine im Lauf
#: entstandene Zeile wird GELEERT statt geloescht. Jeder Leser prueft
#: ``(stand[feld] or "")``, eine leere Zeile ist also von keiner Zeile nicht
#: zu unterscheiden -- und die Zeile zu loeschen hiesse, die
#: Phasen-Buchhaltung in derselben Zeile mitzureissen.
GELEERT = ("arbeitsstand",)

#: Die Arten, deren Meldungszeile NICHT in "Rueckgaengig gemacht:" gehoert.
#: Eine Ausschluss- und keine Einschlussliste: ``entschieden`` ist in der
#: Meldung still, setzt aber nebenbei ``arbeitsstand.figuren_anzahl``
#: (erkenner._wende_journal_an) -- diese Zeile MUSS mitgenannt werden.
ZEILEN_OHNE_UNDO = frozenset({"phase_setzen", "szene_usa"})

#: Spaltennamen, die auf eine verfolgte Tabelle zeigen.
_ZEIGT_AUF = {"figur_id": "figur", "szene_id": "szene"}


def spalten(tabelle: str) -> tuple[str, ...]:
    """Die verglichenen Spalten einer Tabelle -- aus ``db.SCHEMA`` hergeleitet
    (Materialtabellen ausgenommen, dort steht die Liste in ``MATERIAL``)."""
    if tabelle in MATERIAL:
        return MATERIAL[tabelle]
    aussen = AUSSEN.get(tabelle, frozenset())
    alle = db._tabellenspalten_aus_schema()[tabelle]
    return tuple(name for name, _ in alle if name not in aussen)


#: Spalten aus ``AUSSEN``, die ein Lauf trotzdem verfolgt, wenn er DIESE Art
#: traegt (Padua Phasen TEIL 2, Task 10). ``szene.form`` steht in ``AUSSEN``,
#: weil sie sonst allein ein Knopfdruck traegt -- die Erkenner-Art
#: ``formen_setzen`` schreibt sie aber selbst (die Antwort der Gruppe auf die
#: Formwahl-Liste), und dann gehoert sie in den Diff dieses Laufs, sonst
#: haette die Notiert-Meldung keinen wirksamen Undo. Nur fuer Laeufe mit
#: dieser Art: ein Szenen-Undo eines anderen Laufs bleibt unberuehrt davon,
#: dass die Gruppe inzwischen eine Form bestaetigt hat.
ZUSATZ_JE_ART = {
    "formen_setzen": {"szene": ("form",)},
}


def plan(arten: Iterable[str]) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Tabelle -> (Schluesselspalten, verglichene Spalten) fuer diesen Lauf.

    Die Materialtabellen kommen nur dazu, wenn im Lauf eine
    Transkriptkorrektur steckt: sonst waere jeder Erkennerlauf ein Lesen aller
    Transkripte einer Gruppe. Dasselbe Prinzip fuer ``ZUSATZ_JE_ART``."""
    arten = set(arten)
    tabellen = list(VERFOLGT)
    if ART_MATERIAL in arten:
        tabellen += list(MATERIAL)
    ergebnis = {t: (SCHLUESSEL[t], spalten(t)) for t in tabellen}
    for art in sorted(arten & set(ZUSATZ_JE_ART)):
        for tabelle, zusatz in ZUSATZ_JE_ART[art].items():
            schluessel, bisher = ergebnis[tabelle]
            ergebnis[tabelle] = (schluessel, bisher + tuple(
                s for s in zusatz if s not in bisher))
    return ergebnis


def gleich(a: Any, b: Any) -> bool:
    """Sind zwei Werte derselbe -- nach JSON-Rundreise?

    Die Rundreise ist der Punkt: ``arbeitsstand.figuren_anzahl`` kommt als
    ``int`` aus ``erkenner.figurenzahl_aus`` und als ``str`` aus einem Knopf.
    Verglichen wird, was nach ``json.dumps``/``loads`` dasteht -- also
    typtreu, aber ohne die Unterschiede, die erst beim Speichern entstehen."""
    return json.loads(json.dumps(a)) == json.loads(json.dumps(b))


def _geaendert(vorher: dict, nachher: dict) -> tuple[dict, dict]:
    """Nur die Spalten, die sich unterscheiden -- Spalte fuer Spalte, nicht
    die ganze Zeile. Sonst schriebe die Ruecknahme ueber Spalten, die dieser
    Lauf nie angefasst hat."""
    namen = [k for k in nachher if not gleich(vorher.get(k), nachher[k])]
    return ({k: vorher.get(k) for k in namen}, {k: nachher[k] for k in namen})


def schritte(vorher: dict, nachher: dict) -> list[dict]:
    """Die Ruecknahme-Schritte aus zwei Schnappschuessen.

    Ein Schnappschuss ist ``{Tabelle: {Schluessel-JSON: {Spalte: Wert}}}``
    (so liefert ihn ``repo.schnappschuss``). Ergebnis: je Zeile hoechstens
    ein Schritt, stabil sortiert nach (Tabelle, Schluessel) -- zwei Laeufe
    ueber denselben Diff liefern dieselbe Reihenfolge."""
    fertig = []
    for tabelle in sorted(set(vorher) | set(nachher)):
        alt = vorher.get(tabelle, {})
        neu = nachher.get(tabelle, {})
        for roh in sorted(set(alt) | set(neu)):
            schluessel = json.loads(roh)
            if roh in alt and roh in neu:
                a, n = _geaendert(alt[roh], neu[roh])
                if not n:
                    continue
                art, a_wert, n_wert = "geaendert", a, n
            elif roh in neu:
                art, a_wert, n_wert = "angelegt", None, dict(neu[roh])
            else:
                art, a_wert, n_wert = "geloescht", dict(alt[roh]), None
            fertig.append({
                "tabelle": tabelle, "schluessel": schluessel, "art": art,
                "vorher": a_wert, "nachher": n_wert,
            })
    return fertig


def verweise() -> tuple[tuple[str, str, str], ...]:
    """(Tabelle, Spalte, Zieltabelle) fuer jede Spalte, die auf eine ``figur``
    oder ``szene`` zeigt -- **aus ``db.SCHEMA`` hergeleitet**, nicht
    aufgezaehlt.

    Gebraucht fuer die Waisen-Probe: zeigt jetzt eine Zeile auf eine im Lauf
    neu angelegte Figur oder Szene und ist sie nicht selbst im Lauf
    entstanden, gilt das als "seitdem geaendert" -- sonst hinterliesse die
    Ruecknahme eine Waise. Kommt eine neue referenzierende Tabelle dazu, steht
    sie hier automatisch (Pruefkommando:
    ``grep -n "figur_id\\|szene_id" interview_theater/db.py``)."""
    return tuple(
        (tabelle, name, _ZEIGT_AUF[name])
        for tabelle, felder in db._tabellenspalten_aus_schema().items()
        for name, _ in felder
        if name in _ZEIGT_AUF
    )
