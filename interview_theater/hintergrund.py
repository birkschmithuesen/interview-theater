"""Der EINE Hintergrund der Padua-Prompts fuer Szenenkarten (Phase 6) und
Stage Script (Phase 7) -- Birk 07.10.2026 ~19:40: "an EINER Stelle den
Hintergrund holen, damit die Summary-Karte dort andocken kann" (Kanban-Kette
t_1bc96848 "Phasen-Summary je Phase statt Rohdumps").

``hintergrund_fuer_prompt`` liefert, was die Gruppe bis hierher festgelegt hat:
Setting, Format, Uebersicht/Logline, Geschichte, Festlegungen, Verworfenes,
dann zwei weitere Bloecke -- Nachtrag Birk 08.10.2026 ~09:15:

* ``phasen_summary_block`` -- ein Summary je Phase (1-5, ``phasen_summary.py``)
  statt eines einzigen Phase-5-Rohdumps. **Keine Luecken-Fuellung:** fehlt
  einer Phase ihr Summary (noch nicht erzeugt, Profilschalter aus), bleibt
  sie einfach weg -- nie ein Rohdump ("KEINE Chat-Rohtexte mehr aus
  irgendeiner Phase"). Darum der eigene, schlanke Aufbau hier statt
  ``szene.p5_gespraech_block`` (der bewusst auf den Rohdump zurueckfaellt --
  richtig fuer seine drei anderen Aufrufer, falsch fuer diese zwei Prompts).
* ``interview_verdichtungen_block`` -- die Verdichtungen GENAU der
  Interviews, aus denen die Gruppe Stellen uebernommen hat: Hintergrund und
  Ton, keine Quelle fuer Zitate (die stehen woertlich in der nummerierten
  Liste, die ``szenenkarte``/``schaerfung`` je Szene bauen). **Nur auf dem
  Kimi-Weg** (``ueber_claude=False``): die US-Einwilligung
  (``_TEXT_ANGEBOT_MODELLWAHL``) nennt "your recordings and interviews stay
  that way -- no exceptions" und erst ab Phase 5 woertliche Zitate als
  Ausnahme -- Verdichtungen (abgeleitetes Interviewmaterial, aber nicht
  dasselbe wie ein genanntes Zitat) stehen dort nicht. Offene Entscheidung
  fuer Birk (Bericht): die Warnung um einen Satz zu erweitern, dann koennte
  der Block auch mit ``ueber_claude=True`` mitgehen.

Kein Modellaufruf, kein SQL (alles ueber ``repo``)."""

from __future__ import annotations

from interview_theater import repo


def _feld(stand, name: str) -> str:
    if stand is None or name not in stand.keys():
        return ""
    return (stand[name] or "").strip()


def phasen_summary_block(conn, chat_id: int) -> str:
    """Summary je Phase (1-5), aufsteigend -- ``phasen_summary.bloecke_bis``
    ist schon aufsteigend sortiert (``repo.phasen_summaries``). Eine Phase
    ohne Summary fehlt einfach; das ist die ganze Kappung hier."""
    from interview_theater import phasen_summary

    bloecke = phasen_summary.bloecke_bis(conn, chat_id, 6)
    return "\n\n".join(bloecke)


def _akzeptierte_aufnahme_ids(conn, chat_id: int) -> list[int]:
    """Die Interviews, aus denen die Gruppe mindestens eine Stelle
    uebernommen hat (``schaerfung.uebernommen_am``) -- Reihenfolge der
    ersten Uebernahme, dedupliziert (mehrere uebernommene Stellen desselben
    Interviews zaehlen einmal)."""
    ids: list[int] = []
    gesehen: set[int] = set()
    for s in repo.schaerfungen(conn, chat_id):
        if not s["uebernommen_am"]:
            continue
        aufnahme_id = s["aufnahme_id"]
        if aufnahme_id and aufnahme_id not in gesehen:
            gesehen.add(aufnahme_id)
            ids.append(aufnahme_id)
    return ids


def interview_verdichtungen_block(conn, chat_id: int) -> str:
    """Die Verdichtungen (Zusammenfassung + Themen) GENAU der Interviews mit
    mindestens einer uebernommenen Stelle -- NIE der Aufnahmename, NIE das
    Zitat selbst (``kontext.interviewbezeichnung`` nummeriert statt zu
    nennen; Zitate stehen woertlich nur in der nummerierten Liste je
    Szene). Keine Kappung (Birk 08.10.2026: "das wertvollste Material")."""
    from interview_theater import kontext

    zeilen: list[str] = []
    for aufnahme_id in _akzeptierte_aufnahme_ids(conn, chat_id):
        verdichtung = repo.verdichtung_zu_aufnahme(conn, aufnahme_id)
        if verdichtung is None:
            continue
        teile = [kontext.interviewbezeichnung(conn, chat_id, aufnahme_id) + ":"]
        zusammenfassung = (verdichtung["zusammenfassung"] or "").strip()
        if zusammenfassung:
            teile.append(zusammenfassung)
        themen = [
            t["thema"].strip() for t in repo.themen_zu(conn, verdichtung["id"])
            if (t["thema"] or "").strip()
        ]
        if themen:
            teile.append("Themes: " + "; ".join(themen))
        zeilen.append("\n".join(teile))
    if not zeilen:
        return ""
    return _KOPF_INTERVIEWS + "\n\n" + "\n\n".join(zeilen)


def hintergrund_fuer_prompt(conn, chat_id: int, *, ueber_claude: bool = False) -> str:
    """Der Hintergrund als Text-Bloecke (durch Leerzeilen getrennt), leere
    Bloecke fallen weg. ``ueber_claude`` entscheidet, ob der Verdichtungen-
    Block mitgeht (siehe Moduldocstring, Datenschutz) -- Vorgabe ``False``
    (Kimi-Weg), damit kein Aufrufer, der den Parameter noch nicht angibt,
    Material verliert."""
    from interview_theater import szene

    stand = repo.hole_arbeitsstand(conn, chat_id)
    bloecke: list[str] = []
    for name, kopf in (("rahmen", T._KOPF_SETTING), ("format", T._KOPF_FORMAT),
                       ("geschichte_uebersicht", T._KOPF_UEBERSICHT),
                       ("geschichte", T._KOPF_GESCHICHTE)):
        if _feld(stand, name):
            bloecke.append(f"{kopf}\n{_feld(stand, name)}")
    festlegungen = [repo.festlegungszeile(f["bereich"], f["bezug"], f["text"])
                    for f in repo.festlegungen(conn, chat_id)]
    if festlegungen:
        bloecke.append(T._KOPF_FESTLEGUNGEN + "\n" + "\n".join(festlegungen))
    verworfen = szene.verworfene_zeilen(conn, chat_id)
    if verworfen:
        bloecke.append(T._KOPF_VERWORFEN + "\n" + "\n".join(verworfen))
    summary = phasen_summary_block(conn, chat_id)
    if summary:
        bloecke.append(summary)
    if not ueber_claude:
        verdichtungen = interview_verdichtungen_block(conn, chat_id)
        if verdichtungen:
            bloecke.append(verdichtungen)
    return "\n\n".join(bloecke)


_KOPF_SETTING = "Setting:"
_KOPF_FORMAT = "Format:"
_KOPF_UEBERSICHT = "Uebersicht der Gruppe (Logline und Szenen):"
_KOPF_GESCHICHTE = "Geschichte:"
_KOPF_FESTLEGUNGEN = "Festlegungen der Gruppe:"
_KOPF_VERWORFEN = "Von der Gruppe verworfen -- kommt nicht vor:"
_KOPF_INTERVIEWS = "Interviews behind your chosen passages (summaries):"


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
