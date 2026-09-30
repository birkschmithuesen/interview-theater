"""Kuerzen als eigener Weg (30.09.2026, Massnahme C4).

**Warum es das gibt.** Am 06.09.2026 bat die Gruppe um eine Kuerzung
(``docs/analyse-phase5-chaos-2026-09-06.md`` Abschnitt 4). Der Bot kannte
keinen Kuerzungspfad: die Kritik lief in den Gespraechszug, das
Gespraechsmodell antwortete mit einer neuen, vollstaendigen Szenenliste im
Fliesstext, und der Absichtserkenner las sie als ``szene_planen``. Aus drei
Szenen wurden sechs, und eine Stunde spaeter noch einmal sechs. Der Bot sagte
dabei selbst, er koenne den Text nicht kuerzen -- er lag ihm nicht vor.

**Was hier NICHT passiert.** Keine neue Szenenfolge, keine Aenderung an
Anzahl, Reihenfolge, Form oder Besetzung, keine neue Tabelle, kein zweiter
Anbieterweg. Kuerzen ist eine **Ueberarbeitung** desselben Textes und benutzt
genau die zwei Laeufe, die es dafuer schon gibt:

* mit Szenennummer -> ``szene.starte`` mit der Notiz im Auftrag, wie bei
  "Passt, aber anders". ``szene.schreibe`` legt das Ergebnis in ``prosa``
  (Phase 6) oder ``volltext`` (ab Phase 7) ab und **haengt die Fassung an**
  (``repo.haenge_szenenfassung_an``).
* ohne Nummer -> ``kurzgeschichte.starte`` mit der Notiz als Regie-Notiz, wie
  bei "Etwas aendern". ``lege_szenen_an`` gleicht ab statt zu ersetzen
  (``repo.gleiche_szenenfolge_ab``) und haengt je Abschnitt eine Fassung an.

**Warum die Prosa-Notiz die Abschnittszahl nennt.**
``kurzgeschichte.ANWEISUNG`` stellt dem Modell die Zahl der Abschnitte
ausdruecklich frei ("Du waehlst die Zahl der Abschnitte selbst"). Eine
kuerzere Geschichte mit vier statt sechs Abschnitten waere also ein
plausibles Ergebnis -- und weil der Abgleich ergaenzend ist, blieben zwei
Abschnitte mit ihrem alten, langen Text stehen. Die Notiz bindet deshalb auf
die Zahl, die dasteht.

**Kein Modellaufruf hier** (Zusage 2): beide Wege geben sofort an einen
eigenen Thread ab. Deshalb darf ein Knopf-Handler diese Funktion rufen.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

#: Das Kuerzungsziel in Prozent. EINE Stelle: Notiz und Knopfbeschriftung
#: lesen von hier (Analyse C4: "Kuerzer (25 %)").
PROZENT = 25

#: Die feste Regie-Notiz fuer EINE Szene. Sie sagt, was gleich bleibt, und
#: nicht nur, was kuerzer wird -- ein Modell, dem man "kuerzer" sagt, kuerzt
#: gern die Handlung mit.
TEXT_NOTIZ_SZENE = (
    "Kuerze diese Szene um etwa {prozent} Prozent. Dieselben Ereignisse, "
    "dieselbe Reihenfolge, dieselben Figuren, dasselbe Ende -- nur knapper: "
    "weniger Wiederholung, kuerzere Repliken, nichts Neues dazu."
)

#: Dieselbe Notiz fuer die ganze Kurzgeschichte, plus die Bindung an die
#: Abschnittszahl (siehe Moduldocstring).
TEXT_NOTIZ_PROSA = (
    "Kuerze die Geschichte um etwa {prozent} Prozent. Behalte genau {anzahl} "
    "Abschnitte mit ihren Titeln und in ihrer Reihenfolge und kuerze "
    "innerhalb der Abschnitte -- dieselben Ereignisse, dasselbe Ende, nichts "
    "Neues dazu."
)

#: Wenn es nichts zu kuerzen gibt. Kein bezahlter Lauf auf nichts, und keine
#: stille Abfuhr: die Gruppe hat gerade gedrueckt.
TEXT_NICHTS_ZU_KUERZEN = "Da ist noch kein Text, den ich kuerzen koennte."

#: Die Knopfquittung, wenn der Schreibweg selbst abgelehnt hat (laeuft schon,
#: Pflichtfeld fehlt, USA-Frage offen). In all diesen Faellen hat
#: ``szene.starte`` bzw. ``kurzgeschichte.starte`` den Grund schon in den
#: Chat geschrieben -- die Quittung verweist nur darauf, statt einen Grund
#: zu raten ("Laeuft schon" war bei einer Sperre falsch).
TEXT_KEIN_LAUF = "Nicht gestartet, siehe Chat"

#: Die Quittungen bei angestossenem Lauf.
TEXT_SZENE_GESTARTET = "Szene {nummer} wird kuerzer"
TEXT_GESCHICHTE_GESTARTET = "Die Geschichte wird kuerzer"

#: Quittungen, hinter denen KEIN Lauf steht -- dort darf der Handler auch
#: keine spaeteren Szenen zur Pruefung markieren (``hat_gestartet``).
_OHNE_LAUF = frozenset({TEXT_NICHTS_ZU_KUERZEN, TEXT_KEIN_LAUF})


def hat_gestartet(meldung: str) -> bool:
    """Steht hinter dieser Quittung von ``starte`` ein angestossener Lauf?"""
    return meldung not in _OHNE_LAUF


def notiz_fuer_szene() -> str:
    """Die Regie-Notiz fuer eine einzelne Szene."""
    return TEXT_NOTIZ_SZENE.format(prozent=PROZENT)


def notiz_fuer_prosa(anzahl: int) -> str:
    """Die Regie-Notiz fuer die ganze Kurzgeschichte, gebunden an ``anzahl``
    Abschnitte."""
    return TEXT_NOTIZ_PROSA.format(prozent=PROZENT, anzahl=anzahl)


def nummer_aus_wert(wert: str | None) -> int | None:
    """Die Szenennummer aus dem ``wert`` einer Knopfzeile bzw. aus dem Wert
    des Erkenners -- oder None.

    Absichtlich streng: nur eine Zahl. "Szene drei" ist keine Nummer, und ein
    geratener Bezug schriebe die falsche Szene neu."""
    roh = (wert or "").strip()
    if not roh.isdigit():
        return None
    return int(roh)


def _abschnitte_mit_prosa(conn, chat_id: int) -> int:
    """Wie viele Szenen tragen eine Prosafassung? Reine Leseabfrage."""
    from interview_theater import repo, szene as szene_modul

    return sum(
        1 for s in repo.hole_szenen(conn, chat_id) if szene_modul.prosa_von(s)
    )


def _hat_text(conn, chat_id: int, nummer: int) -> bool:
    from interview_theater import repo, szene as szene_modul

    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] != nummer:
            continue
        return bool((s["volltext"] or "").strip() or szene_modul.prosa_von(s))
    return False


def starte(conn, tg, klm, e, chat_id: int, nummer: int | None = None) -> str:
    """Stoesst die Kuerzung an und liefert die Zeile fuer die Knopfquittung.

    ``nummer`` gesetzt -> diese eine Szene; ``nummer`` None -> die ganze
    Kurzgeschichte. **Kein Modellaufruf hier**: beide Wege geben an einen
    eigenen Thread ab (Zusage 2).

    Gibt es nichts zu kuerzen, gibt es keinen Lauf, sondern einen Satz.
    Ob ein Lauf angestossen wurde, sagt ``hat_gestartet`` ueber die
    Quittung."""
    from interview_theater import kurzgeschichte, szene as szene_modul

    if nummer is not None:
        if not _hat_text(conn, chat_id, nummer):
            tg.sende(chat_id, TEXT_NICHTS_ZU_KUERZEN)
            return TEXT_NICHTS_ZU_KUERZEN
        auftrag = f"Schreib Szene {nummer} neu. {notiz_fuer_szene()}"
        if szene_modul.starte(conn, tg, klm, e, chat_id, auftrag) is None:
            return TEXT_KEIN_LAUF
        return TEXT_SZENE_GESTARTET.format(nummer=nummer)

    anzahl = _abschnitte_mit_prosa(conn, chat_id)
    if not anzahl:
        tg.sende(chat_id, TEXT_NICHTS_ZU_KUERZEN)
        return TEXT_NICHTS_ZU_KUERZEN
    # ``vorlage=True``: die bestehende Prosa steht im Prompt -- sonst schriebe
    # das Modell "25 Prozent kuerzer" ueber einen Text, den es nie sah.
    if kurzgeschichte.starte(
        conn, tg, klm, e, chat_id, notiz_fuer_prosa(anzahl), vorlage=True,
    ) is None:
        return TEXT_KEIN_LAUF
    return TEXT_GESCHICHTE_GESTARTET
