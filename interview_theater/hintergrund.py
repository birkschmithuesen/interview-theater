"""Der EINE Hintergrund der Padua-Prompts fuer Szenenkarten (Phase 6) und
Stage Script (Phase 7) -- Birk 07.10.2026 ~19:40: "an EINER Stelle den
Hintergrund holen, damit die Summary-Karte dort andocken kann" (Kanban-Kette
t_1bc96848 "Phasen-Summary je Phase statt Rohdumps").

``hintergrund_fuer_prompt`` liefert, was die Gruppe bis hierher festgelegt hat:
Setting, Format, Uebersicht/Logline, Geschichte, Festlegungen, Verworfenes --
und als einzigen Gespraechsanteil den Phase-5-Wortlaut (``_P5_ROH``). Genau
DIESEN Block soll die Phasen-Summary ersetzen; er steht deshalb nur hier und
nirgends sonst in diesen Prompts. Neue Rohdumps alter Phasen gehoeren nicht
hierher, sondern in die Summary.

Kein Modellaufruf, kein SQL (alles ueber ``repo``)."""

from __future__ import annotations

from interview_theater import repo


def _feld(stand, name: str) -> str:
    if stand is None or name not in stand.keys():
        return ""
    return (stand[name] or "").strip()


def gespraech_block(conn, chat_id: int) -> str:
    """Der Gespraechsanteil des Hintergrunds -- heute der Wortlaut aus Phase 5
    (``szene._p5_gespraech_text``). Andockstelle der Phasen-Summary: liefert
    sie etwas, ersetzt sie diesen Block."""
    from interview_theater import szene

    return szene._p5_gespraech_text(conn, chat_id, ueber_claude=True) or ""


def hintergrund_fuer_prompt(conn, chat_id: int) -> str:
    """Der Hintergrund als Text-Bloecke (durch Leerzeilen getrennt), leere
    Bloecke fallen weg."""
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
    gespraech = gespraech_block(conn, chat_id)
    if gespraech:
        bloecke.append(gespraech)
    return "\n\n".join(bloecke)


_KOPF_SETTING = "Setting:"
_KOPF_FORMAT = "Format:"
_KOPF_UEBERSICHT = "Uebersicht der Gruppe (Logline und Szenen):"
_KOPF_GESCHICHTE = "Geschichte:"
_KOPF_FESTLEGUNGEN = "Festlegungen der Gruppe:"
_KOPF_VERWORFEN = "Von der Gruppe verworfen -- kommt nicht vor:"


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)
