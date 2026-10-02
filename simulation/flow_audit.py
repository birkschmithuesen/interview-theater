"""Flow-Audit (Padua, 02.10.2026) -- findet automatisch Stellen, an denen der
Bot die Kreativitaet einer Gruppe nicht ideal unterstuetzt.

Anlass: in Birks Generalprobe kam in Phase 5 Chat-Feedback an, aber es
passierte NICHTS -- Phase 5 hat im Erkenner keinen eigenen Intent, nur
Knoepfe wirken. Das Gespraechsmodell antwortete freundlich, nichts wurde
gespeichert. Kein Test hat das gemeldet.

Dieses Modul ist **Schicht 1**: statisch, ohne Modellaufruf, laeuft in
pytest (``tests/test_flow_abdeckung.py``). Es vergleicht die von Hand
gepflegte Liste typischer Handlungen je Phase (``simulation/
flow_erwartungen.toml``) mechanisch gegen den Code: hat eine Handlung, die
per Chat ankommen soll, einen Erkenner-Intent (``erkenner.ARTEN``)? Gibt es
ueberhaupt einen Weg -- Intent oder Knopf?

Drei Befundarten:
    - ``sackgasse``           -- weder Intent noch Knopf: kein Weg.
    - ``toter_gespraechsweg`` -- nur der Knopf wirkt, der Chat soll es auch
      koennen (``weg`` ist ``chat`` oder ``beides``). Genau der Phase-5-Fall.
    - ``geist``               -- die Erwartungsliste nennt einen Intent oder
      Knopf, den es im Code nicht (mehr) gibt -- die Liste ist veraltet,
      nicht der Code.

Schicht 2 (dynamischer Persona-Lauf) und Schicht 3 (Richter-Urteil) stehen in
``scripts/flow_audit_lauf.py`` -- sie rufen echte Modelle auf und kosten
Geld, deshalb nicht im ``pytest``-Pfad und nicht beim blossen Import dieser
Datei.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from interview_theater import erkenner
from interview_theater.knoepfe import texte as knopf_texte

#: Die von Hand gepflegte Liste. Mechanisch geprueft wird NUR dagegen --
#: eine zweite, aus dem Code erratene Liste waere der erste Stand, der
#: ausschert (dieselbe Regel wie bei ``fehlstellen.py``/``roadmap.py``).
ERWARTUNGEN_PFAD = Path(__file__).resolve().parent / "flow_erwartungen.toml"

#: Sortierung der Befundliste -- schwerstes zuerst.
SCHWERE_RANG = {"sackgasse": 0, "toter_gespraechsweg": 1, "geist": 2}

SCHWERE_TEXT = {
    "sackgasse": "Sackgasse (kein Intent, kein Knopf)",
    "toter_gespraechsweg": "Toter Gespraechsweg (nur Knopf wirkt)",
    "geist": "Veraltete Erwartung (Intent/Knopf existiert nicht mehr)",
}


@dataclass(frozen=True)
class Handlung:
    phase: int
    aktion: str
    weg: str  # "chat" | "knopf" | "beides"
    intent: str  # "" oder "a|b"
    knopf: str  # "" oder "ART_A|ART_B"
    beleg: str


@dataclass(frozen=True)
class Befund:
    schwere: str
    phase: int
    aktion: str
    was_fehlt: str
    vorschlag: str
    beleg: str


def lade_erwartungen(pfad: Path = ERWARTUNGEN_PFAD) -> list[Handlung]:
    """Liest ``flow_erwartungen.toml``. Eine Phase ohne Eintraege ist ein
    Zeichen, dass die Liste nicht mitgewachsen ist -- kein stiller Fall."""
    rohdaten = tomllib.loads(pfad.read_text(encoding="utf-8"))
    handlungen: list[Handlung] = []
    for schluessel, eintraege in rohdaten.get("phase", {}).items():
        phase = int(schluessel)
        for e in eintraege:
            handlungen.append(
                Handlung(
                    phase=phase,
                    aktion=e["aktion"],
                    weg=e["weg"],
                    intent=(e.get("intent") or "").strip(),
                    knopf=(e.get("knopf") or "").strip(),
                    beleg=(e.get("beleg") or "").strip(),
                )
            )
    return handlungen


def bekannte_intents() -> frozenset[str]:
    """Alle Erkenner-Intents, wie sie der Code heute kennt."""
    return frozenset(erkenner.ARTEN)


def bekannte_knoepfe() -> frozenset[str]:
    """Alle ``ART_*``-Konstanten aus ``knoepfe.texte`` -- die vollstaendige
    Knopfflaeche (``tests/test_knoepfe_struktur.py`` haelt bereits fest, dass
    jede ``ART_*`` einen Handler hat)."""
    return frozenset(n for n in dir(knopf_texte) if n.startswith("ART_"))


def _namen(feld: str) -> list[str]:
    return [n.strip() for n in feld.split("|") if n.strip()]


def pruefe(
    handlungen: list[Handlung] | None = None,
    intents: frozenset[str] | None = None,
    knoepfe: frozenset[str] | None = None,
) -> list[Befund]:
    """Die mechanische Pruefung. Nimmt Listen/Mengen als Parameter entgegen
    (statt sie selbst zu laden), damit ein Test sie fuer die Mutationsprobe
    austauschen kann, ohne Dateien oder Module anzufassen."""
    handlungen = lade_erwartungen() if handlungen is None else handlungen
    intents = bekannte_intents() if intents is None else intents
    knoepfe = bekannte_knoepfe() if knoepfe is None else knoepfe

    befunde: list[Befund] = []
    for h in handlungen:
        intent_namen = _namen(h.intent)
        knopf_namen = _namen(h.knopf)

        for name in intent_namen:
            if name not in intents:
                befunde.append(
                    Befund(
                        schwere="geist",
                        phase=h.phase,
                        aktion=h.aktion,
                        was_fehlt=f"Intent '{name}' steht in flow_erwartungen.toml, aber nicht in erkenner.ARTEN",
                        vorschlag="simulation/flow_erwartungen.toml korrigieren oder den Intent wiederherstellen",
                        beleg=h.beleg,
                    )
                )
        for name in knopf_namen:
            if name not in knoepfe:
                befunde.append(
                    Befund(
                        schwere="geist",
                        phase=h.phase,
                        aktion=h.aktion,
                        was_fehlt=f"Knopf '{name}' steht in flow_erwartungen.toml, aber nicht in knoepfe.texte",
                        vorschlag="simulation/flow_erwartungen.toml korrigieren oder den Knopf wiederherstellen",
                        beleg=h.beleg,
                    )
                )

        hat_intent = bool(intent_namen) and all(n in intents for n in intent_namen)
        hat_knopf = bool(knopf_namen) and all(n in knoepfe for n in knopf_namen)

        if not hat_intent and not hat_knopf:
            befunde.append(
                Befund(
                    schwere="sackgasse",
                    phase=h.phase,
                    aktion=h.aktion,
                    was_fehlt="kein Erkenner-Intent und kein Knopf",
                    vorschlag=f"Einen Weg fuer '{h.aktion}' bauen (Phase {h.phase})",
                    beleg=h.beleg,
                )
            )
        elif h.weg in ("chat", "beides") and not hat_intent and hat_knopf:
            befunde.append(
                Befund(
                    schwere="toter_gespraechsweg",
                    phase=h.phase,
                    aktion=h.aktion,
                    was_fehlt="kein Erkenner-Intent -- nur der Knopf wirkt",
                    vorschlag=f"Erkenner-Intent fuer '{h.aktion}' ergaenzen (Phase {h.phase})",
                    beleg=h.beleg,
                )
            )
    return sorted(befunde, key=lambda b: (SCHWERE_RANG[b.schwere], b.phase))


def matrix_text(handlungen: list[Handlung] | None = None) -> str:
    """Die Matrix aus Schicht 1 als Klartext -- fuer den Bericht."""
    handlungen = lade_erwartungen() if handlungen is None else handlungen
    zeilen = ["Phase | Weg | Aktion | Intent | Knopf", "---|---|---|---|---"]
    for h in sorted(handlungen, key=lambda h: h.phase):
        zeilen.append(
            f"{h.phase} | {h.weg} | {h.aktion} | {h.intent or '--'} | {h.knopf or '--'}"
        )
    return "\n".join(zeilen)


def befunde_text(befunde: list[Befund]) -> str:
    if not befunde:
        return "Keine Befunde."
    zeilen = []
    for b in befunde:
        zeilen.append(
            f"[{SCHWERE_TEXT[b.schwere]}] Phase {b.phase}: {b.aktion}\n"
            f"  Was fehlt: {b.was_fehlt}\n"
            f"  Vorschlag: {b.vorschlag}\n"
            f"  Beleg: {b.beleg}"
        )
    return "\n\n".join(zeilen)


def main(argv: list[str] | None = None) -> int:
    befunde = pruefe()
    print("# Flow-Audit -- Schicht 1 (statisch)\n")
    print("## Befunde\n")
    print(befunde_text(befunde))
    print("\n\n## Matrix\n")
    print(matrix_text())
    rot = [b for b in befunde if b.schwere in ("sackgasse", "toter_gespraechsweg")]
    return 1 if rot else 0


if __name__ == "__main__":
    sys.exit(main())
