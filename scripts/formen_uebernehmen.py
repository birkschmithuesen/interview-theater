"""Uebernimmt den Formen-Katalog aus dem Wiki ins Repository (Formberater,
Karte t_256ec777, 07.10.2026).

Quelle: ``~/hermes-shared/hermes-knowledge/performative-formen/formen/*.md``
(67 Dateien, YAML-Frontmatter + Abschnitte). Ziel:
``interview_theater/formen/<slug>.md`` -- je Form NUR das, was der Bot
braucht: die Frontmatter-Felder ``title``, ``name_en``, ``kurz``,
``aliases``, ``verwandt``, ``confidence`` und der Abschnitt ``## Bot (EN)``.
Definition, Geschichte, Quellen bleiben im Wiki.

Warum eine Kopie statt eines Pfads ins Wiki: der Bot laeuft aus dem
Repository (systemd-Unit, Worktrees, Tests ohne Netz und ohne
``~/hermes-shared``) -- ein Katalog, der beim Start fehlen kann, waere ein
Ausfall, den niemand bemerkt. Neu uebernehmen nach einer Wiki-Aenderung::

    uv run --extra dev python -m scripts.formen_uebernehmen [QUELLE]

Kein Modellaufruf, kein Netz.
"""

from __future__ import annotations

import pathlib
import re
import sys

QUELLE = pathlib.Path.home() / "hermes-shared/hermes-knowledge/performative-formen/formen"
ZIEL = pathlib.Path(__file__).resolve().parent.parent / "interview_theater" / "formen"

#: Der englische Name je Form, wie ihn eine englischsprachige Gruppe liest
#: (``title`` im Wiki ist deutsch). Von Hand, weil der Bot-Block keinen
#: einheitlichen Namensanfang hat.
NAME_EN = {
    "absurdes-theater": "Theatre of the Absurd",
    "aktionskunst-wiener-aktionismus": "Viennese Actionism",
    "antikes-theater": "Ancient Greek theatre",
    "armes-theater": "Poor theatre",
    "audio-walk": "Audio walk",
    "ballett": "Ballet",
    "bauhausbuehne": "Bauhaus stage",
    "body-art": "Body art",
    "butoh": "Butoh",
    "commedia-dell-arte": "Commedia dell'arte",
    "dada-soiree": "Dada soirée",
    "devised-theatre": "Devised theatre",
    "dokumentartheater": "Documentary theatre",
    "durational-performance": "Durational performance",
    "episches-theater": "Epic theatre",
    "experten-des-alltags": "Experts of the everyday",
    "figurentheater": "Puppetry",
    "flashmob-intervention": "Flash mob / art intervention",
    "fluxus-event-score": "Fluxus event score",
    "futuristische-serata": "Futurist serata",
    "game-theater": "Game theatre",
    "guided-tour-performance": "Guided-tour performance",
    "happening": "Happening",
    "immersives-theater": "Immersive theatre",
    "improvisationstheater": "Improvisational theatre",
    "instrumentales-theater": "Instrumental theatre",
    "kabarett": "Cabaret",
    "konzepttanz": "Conceptual dance",
    "konzertperformance": "Concert performance",
    "lecture-performance": "Lecture performance",
    "lehrstueck-agitprop": "Learning play / agitprop",
    "live-art": "Live art",
    "live-cinema": "Live cinema",
    "live-hoerspiel": "Live radio play",
    "live-rollenspiel-larp": "Live action role-play (LARP)",
    "masque-hoffest": "Court masque",
    "multimedia-performance": "Multimedia performance",
    "musical": "Musical",
    "mysterienspiel": "Mystery play",
    "neues-musiktheater": "New music theatre",
    "one-to-one-performance": "One-to-one performance",
    "operette": "Operetta",
    "oper": "Opera",
    "partizipative-performance": "Participatory performance",
    "performance-installation": "Performance installation",
    "postdramatisches-theater": "Postdramatic theatre",
    "postmodern-dance": "Postmodern dance",
    "promenadentheater": "Promenade theatre",
    "rap-hip-hop-theater": "Hip-hop theatre",
    "reenactment-reperformance": "Reenactment / reperformance",
    "robotik-ki-performance": "Robot / AI performance",
    "site-specific-performance": "Site-specific performance",
    "sound-performance": "Sound performance / sound art",
    "soziales-experiment-als-kunst": "Social experiment as art",
    "spoken-word-poetry-slam": "Spoken word / poetry slam",
    "stand-up-comedy": "Stand-up comedy",
    "strassentheater": "Street theatre",
    "szenische-lesung": "Staged reading",
    "szenisches-oratorium": "Staged oratorio",
    "tableau-vivant": "Tableau vivant",
    "tanztheater": "Tanztheater (dance theatre)",
    "telematische-performance": "Telematic performance",
    "theater-der-unterdrueckten": "Theatre of the Oppressed",
    "unsichtbares-theater": "Invisible theatre",
    "variete-neuer-zirkus": "Variety & contemporary circus",
    "verbatim-theatre": "Verbatim theatre",
    "vr-xr-theater": "VR/XR theatre",
}

_FELDER = ("title", "kurz", "aliases", "verwandt", "confidence")


def _frontmatter(text: str) -> dict[str, str]:
    """Die Zeilen ``schluessel: wert`` zwischen den beiden ``---``."""
    teile = text.split("---", 2)
    if len(teile) < 3:
        raise ValueError("keine Frontmatter")
    felder = {}
    for zeile in teile[1].splitlines():
        schluessel, trenner, wert = zeile.partition(":")
        if trenner and schluessel.strip() in _FELDER:
            felder[schluessel.strip()] = wert.strip()
    return felder


def _bot_block(text: str) -> str:
    treffer = re.search(r"^## Bot \(EN\)\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not treffer or not treffer.group(1).strip():
        raise ValueError("kein Abschnitt '## Bot (EN)'")
    return " ".join(treffer.group(1).split())


def uebernimm(quelle: pathlib.Path = QUELLE, ziel: pathlib.Path = ZIEL) -> int:
    ziel.mkdir(parents=True, exist_ok=True)
    anzahl = 0
    for datei in sorted(quelle.glob("*.md")):
        slug = datei.stem
        text = datei.read_text(encoding="utf-8")
        felder = _frontmatter(text)
        fehlend = [f for f in _FELDER if f not in felder]
        if fehlend or slug not in NAME_EN:
            raise ValueError(f"{datei.name}: fehlt {fehlend or 'NAME_EN'}")
        zeilen = ["---", f"title: {felder['title']}",
                  f'name_en: "{NAME_EN[slug]}"']
        zeilen += [f"{f}: {felder[f]}" for f in _FELDER[1:]]
        zeilen += ["---", "", "## Bot (EN)", _bot_block(text), ""]
        (ziel / datei.name).write_text("\n".join(zeilen), encoding="utf-8")
        anzahl += 1
    return anzahl


if __name__ == "__main__":
    quelle = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else QUELLE
    print(f"{uebernimm(quelle)} Formen nach {ZIEL} uebernommen")
