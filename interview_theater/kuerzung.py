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
import re

log = logging.getLogger(__name__)

#: Eine fuehrende "Szene"-Vorsilbe (gross/klein, beliebig viele Leerzeichen),
#: gefolgt von genau einer Zahl -- oder die blosse Zahl. Eng gehalten: "Szene
#: 3 und 4" oder "drei" liefern None, wie zuvor.
_MUSTER_NUMMER = re.compile(r"^\s*(?:szene\s*)?(\d+)\s*$", re.IGNORECASE)

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

#: Die Rueckfrage auf dem Erkenner-Weg, wenn ab dem Feinschliff (die Phase,
#: in der Theatertexte statt Geschichten entstehen, ``szene.schreibt_prosa``
#: ist falsch) keine Szenennummer genannt wurde. Dort liest die Gruppe einen
#: Theatertext, und ein Lauf ueber die ganze Kurzgeschichte waere teuer und
#: am Gemeinten vorbei. **Vorlaeufige Voreinstellung** (30.09.2026) -- die
#: endgueltige Entscheidung trifft Birk.
TEXT_WELCHE_SZENE = "Welche Szene soll kuerzer werden? Sagt mir die Nummer."


def notiz_fuer_szene() -> str:
    """Die Regie-Notiz fuer eine einzelne Szene."""
    return T.TEXT_NOTIZ_SZENE.format(prozent=PROZENT)


def notiz_fuer_prosa(anzahl: int) -> str:
    """Die Regie-Notiz fuer die ganze Kurzgeschichte, gebunden an ``anzahl``
    Abschnitte."""
    return T.TEXT_NOTIZ_PROSA.format(prozent=PROZENT, anzahl=anzahl)


def nummer_aus_wert(wert: str | None) -> int | None:
    """Die Szenennummer aus dem ``wert`` einer Knopfzeile bzw. aus dem Wert
    des Erkenners -- oder None.

    Absichtlich streng: nur eine Zahl, optional mit fuehrendem "Szene"
    (gross/klein -- der Erkenner liefert manchmal "Szene 3" statt der
    blossen Zahl). "Szene drei" und "Szene 3 und 4" sind keine Nummer, und
    ein geratener Bezug schriebe die falsche Szene neu."""
    treffer = _MUSTER_NUMMER.match(wert or "")
    if treffer is None:
        return None
    return int(treffer.group(1))


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


def starte(conn, tg, klm, e, chat_id: int,
           nummer: int | None = None) -> tuple[str, bool]:
    """Stoesst die Kuerzung an und liefert ``(quittung, gestartet)``.

    ``nummer`` gesetzt -> diese eine Szene; ``nummer`` None -> die ganze
    Kurzgeschichte. **Kein Modellaufruf hier**: beide Wege geben an einen
    eigenen Thread ab (Zusage 2).

    Gibt es nichts zu kuerzen, gibt es keinen Lauf, sondern einen Satz.
    ``gestartet`` kommt aus dem Rueckgabewert des Schreibwegs (Thread oder
    None), nicht aus dem Wortlaut der Quittung.

    **Der Pruef-Vermerk haengt hier, nicht am Aufrufer** (30.09.2026): wird
    eine Szene gekuerzt, bekommen die spaeteren geschriebenen Szenen ihren
    Vermerk (``knoepfe._melde_spaetere``) -- eine kuerzere Szene 2 aendert,
    was Szene 3 voraussetzen darf. So gilt das fuer Knopf und Erkenner
    gleich, und nur, wenn wirklich ein Lauf gestartet ist."""
    from interview_theater import kurzgeschichte, szene as szene_modul

    if nummer is not None:
        if not _hat_text(conn, chat_id, nummer):
            tg.sende(chat_id, T.TEXT_NICHTS_ZU_KUERZEN)
            return T.TEXT_NICHTS_ZU_KUERZEN, False
        # ``BISHER_MARKER``: im Prosalauf (Phase 6) ist ``volltext`` leer --
        # ohne den Marker saehe das Modell die Prosa dieser Szene nicht und
        # schriebe sie neu, statt sie zu kuerzen.
        auftrag = (
            f"Schreib Szene {nummer} neu. {notiz_fuer_szene()} "
            f"{szene_modul.BISHER_MARKER}"
        )
        if szene_modul.starte(conn, tg, klm, e, chat_id, auftrag) is None:
            return T.TEXT_KEIN_LAUF, False
        # Spaeter Import: knoepfe ist die Oberflaeche und liest selbst von
        # hier -- ein Modulkopf-Import waere ein Zyklus.
        from interview_theater.knoepfe import szenen as knoepfe_szenen

        knoepfe_szenen._melde_spaetere(conn, tg, chat_id, nummer)
        return T.TEXT_SZENE_GESTARTET.format(nummer=nummer), True

    anzahl = _abschnitte_mit_prosa(conn, chat_id)
    if not anzahl:
        tg.sende(chat_id, T.TEXT_NICHTS_ZU_KUERZEN)
        return T.TEXT_NICHTS_ZU_KUERZEN, False
    # ``vorlage=True``: die bestehende Prosa steht im Prompt -- sonst schriebe
    # das Modell "25 Prozent kuerzer" ueber einen Text, den es nie sah.
    if kurzgeschichte.starte(
        conn, tg, klm, e, chat_id, notiz_fuer_prosa(anzahl), vorlage=True,
    ) is None:
        return T.TEXT_KEIN_LAUF, False
    return T.TEXT_GESCHICHTE_GESTARTET, True


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)
