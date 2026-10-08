"""Die Sprache eines Workshops: Chat- und Promptsprache, Whisper-Vorgabe,
Pseudonyme, und der Nachschlagezugriff auf die Texttabelle (Karte A1,
30.09.2026).

**Kein i18n-Framework.** Die deutschen Nutzertexte stehen als
Python-Konstanten in ihren Modulen und **sind** die deutsche Tabelle -- sie
bleiben zeichengleich stehen, damit Dortmund bitgleich bleibt
(``tests/test_sprache_bitgleich.py``). Jede weitere Sprache steht in genau
einer Datei ``sprachen/<code>/texte.toml``: eine Tabelle je definierendem
Modul, darin der Konstantenname als Schluessel.

**Nachgeschlagen wird zur Aufrufzeit, nie beim Import.** Ein Modul mit
Nutzertexten traegt am Ende ``T = sprache.Texte(__name__)`` und liest
``T._TEXT_X`` dort, wo der Text gebraucht wird. Das ist dieselbe Regel wie
bei den PEP-562-Zugriffen in ``phasen``/``szene``/``szenenfolge`` (D.5 der
Profil-Analyse): ein Web-Prozess bedient mehrere Gruppen, und Tests
schalten das Profil per monkeypatch um.

**Deutsch ist die Konstante selbst** -- dasselbe Objekt, kein Umweg ueber
eine Datei. **Fehlt ein englischer Eintrag, bleibt es Deutsch** und die
Luecke wird einmal je Prozess geloggt: ein Zug, der mitten im Workshop an
einem vergessenen Knopftext abbricht, waere teurer als ein deutsches Wort.
``tests/test_sprache_texte.py`` sorgt dafuer, dass es die Luecke gar nicht
erst gibt.

Nur Standardbibliothek plus ``workshop`` -- Dienste-Schicht, von jedem
Modul aus importierbar.
"""

import logging
import contextlib
import contextvars
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from interview_theater import workshop

log = logging.getLogger(__name__)

DEUTSCH = "de"
#: Whisper-Wert fuer "Sprache selbst erkennen" (Birk E5).
AUTO = "auto"
GEBAUT = workshop.SPRACHEN
VERZEICHNIS = Path(__file__).resolve().parent / "sprachen"
TABELLENDATEI = "texte.toml"
PAKET = "interview_theater."

#: Sprachnamen in ihrer eigenen Sprache -- fuer Knopf und /sprache. Nicht
#: uebersetzt: wer Italienisch spricht, sucht "Italiano".
SPRACHNAMEN = {"de": "Deutsch", "en": "English", "it": "Italiano"}


def code() -> str:
    """Die Chat- und Promptsprache des aktiven Profils."""
    return str(workshop.aktiv().wert("sprache.code", DEUTSCH) or DEUTSCH)


def whisper_vorgabe() -> str:
    """Was Whisper erkennen soll, solange die Gruppe nichts anderes sagt:
    ein ISO-639-1-Code oder ``AUTO``."""
    return str(workshop.aktiv().wert("sprache.whisper", DEUTSCH) or DEUTSCH)


def pseudonyme() -> bool:
    """E8: Vornamen im Gespraechsverlauf durch "Member N" ersetzen?"""
    return bool(workshop.aktiv().wert("datenschutz.pseudonyme", False))


def je_sprache(werte: dict[str, Any]) -> Any:
    """Waehlt aus ``{"de": …, "en": …}`` den Wert der aktiven Sprache.
    Fehlt er, gilt der deutsche -- ein Parser ohne englische Fassung
    verhaelt sich dann wie vorher."""
    return werte.get(code(), werte[DEUTSCH])


_TABELLEN: dict[str, dict[str, dict[str, Any]]] = {}
_GEMELDET: set[tuple[str, str, str]] = set()


def tabelle(sprachcode: str) -> dict[str, dict[str, Any]]:
    """Die Tabelle einer Sprache, einmal je Prozess gelesen (wie das Profil:
    kein Hot-Reload, eine halb gespeicherte Datei waere ein Halbstart)."""
    if sprachcode not in _TABELLEN:
        pfad = VERZEICHNIS / sprachcode / TABELLENDATEI
        _TABELLEN[sprachcode] = (
            tomllib.loads(pfad.read_text(encoding="utf-8")) if pfad.is_file() else {}
        )
    return _TABELLEN[sprachcode]


def vergiss() -> None:
    """Nur fuer Tests und Pruefskripte."""
    _TABELLEN.clear()
    _GEMELDET.clear()


def modulschluessel(modul: str) -> str:
    """``interview_theater.knoepfe.texte`` -> ``knoepfe.texte``."""
    return modul[len(PAKET):] if modul.startswith(PAKET) else modul


def angleichen(deutsch: Any, eintrag: Any) -> Any:
    """Gibt dem Tabelleneintrag die Form der deutschen Konstante: TOML kennt
    weder Tupel noch Zahlen als Schluessel, der Code erwartet beides."""
    if isinstance(deutsch, dict) and isinstance(eintrag, dict):
        schluesseltyp = type(next(iter(deutsch))) if deutsch else str
        muster = next(iter(deutsch.values())) if deutsch else None
        return {schluesseltyp(k): angleichen(muster, v) for k, v in eintrag.items()}
    if isinstance(deutsch, (tuple, list, set, frozenset)) and isinstance(eintrag, list):
        muster = next(iter(deutsch)) if deutsch else None
        return type(deutsch)(angleichen(muster, v) for v in eintrag)
    return eintrag


def text(modul: str, name: str, sprachcode: str | None = None) -> Any:
    """Der Text ``name`` aus ``modul`` in der aktiven Sprache, oder
    erzwungen in ``sprachcode`` (``Texte(..., sprachcode=...)``,
    Morgen-Auftrag 4)."""
    deutsch = getattr(sys.modules[modul], name)
    sprachcode = sprachcode or code()
    if sprachcode == DEUTSCH:
        return deutsch
    eintrag = tabelle(sprachcode).get(modulschluessel(modul), {}).get(name)
    if eintrag is None and _ERZWUNGEN.get() == sprachcode and code() not in (sprachcode, DEUTSCH):
        # erzwungen ohne IT-Eintrag -> aktive Sprache (EN), nicht Deutsch
        eintrag = tabelle(code()).get(modulschluessel(modul), {}).get(name)
        if eintrag is not None:
            return angleichen(deutsch, eintrag)
    if eintrag is None:
        schluessel = (sprachcode, modul, name)
        if schluessel not in _GEMELDET:
            _GEMELDET.add(schluessel)
            log.warning("Kein %s-Text fuer %s.%s -- es bleibt Deutsch",
                        sprachcode, modulschluessel(modul), name)
        return deutsch
    return angleichen(deutsch, eintrag)


#: PDF IT (Birk 08.10.2026 ~11:00, Quickfix): waehrend ``erzwinge("it")``
#: liefern ALLE ``Texte``-Instanzen Italienisch (Ueberschriften der IT-PDF);
#: fehlt ein IT-Eintrag, gilt die aktive Sprache (nicht Deutsch).
_ERZWUNGEN: "contextvars.ContextVar[str | None]" = contextvars.ContextVar("sprache_erzwungen", default=None)


@contextlib.contextmanager
def erzwinge(sprachcode: str | None):
    marke = _ERZWUNGEN.set(sprachcode)
    try:
        yield
    finally:
        _ERZWUNGEN.reset(marke)


class Texte:
    """Die Texte eines Moduls, zur Aufrufzeit in der aktiven Sprache:
    ``T = sprache.Texte(__name__)``, dann ``T._TEXT_X``.

    ``sprachcode`` (Morgen-Auftrag 4, 08.10.2026, Nachtrag 2): erzwingt eine
    Sprache statt der Profilsprache -- fuer eine zweite, chat-abhaengige
    ``Texte``-Instanz je Modul (``szenenkarte.py``/``stagescript.py``/
    ``web.py``: ``_T_IT = Texte(__name__, sprachcode="it")``, vom Aufrufer
    nur fuer Chats aus ``workshop.italienisch_ab_phase6_chats()`` gewaehlt --
    die Wahl *welcher* Chat ist bewusst NICHT hier drin, ``Texte`` kennt
    keinen chat_id). Knopf-Beschriftungen bleiben auf der gewoehnlichen,
    ungezwungenen Instanz im selben Modul."""

    __slots__ = ("_modul", "_sprachcode", "_p67")

    def __init__(self, modul: str, *, sprachcode: str | None = None,
                 ab_phase67_italienisch: bool = False) -> None:
        object.__setattr__(self, "_modul", modul)
        object.__setattr__(self, "_sprachcode", sprachcode)
        # Kompatibilitaet (Robo 08.10.2026 12:25): zwei Aufrufer (erkenner,
        # phasentexte) nutzen noch die alte Form; sie gilt chat-genau ueber
        # IT_WEB_CHAT_ID (ein Bot-Prozess = eine Gruppe).
        object.__setattr__(self, "_p67", ab_phase67_italienisch)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        sprachcode = _ERZWUNGEN.get() or self._sprachcode
        if sprachcode is None and self._p67:
            if workshop.p67_italienisch_aktiv():
                sprachcode = "it"
        return text(self._modul, name, sprachcode)

    def __setattr__(self, name: str, wert: Any) -> None:
        raise AttributeError("Texte sind nur lesbar")


_FELD = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)(?:[!:][^{}]*)?\}(?!\})")
_PROFIL = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
_PROZENT = re.compile(r"%(?:\([^)]*\))?[#0\- +]*\d*(?:\.\d+)?[sdifr]")


def platzhalter(text: str) -> frozenset[str]:
    """Die Platzhalter eines Textes als Menge: ``{name}``, ``{{name}}``,
    ``%s``. Deutsch und Englisch muessen dieselbe Menge tragen (K3)."""
    return frozenset(
        [f"{{{n}}}" for n in _FELD.findall(text)]
        + [f"{{{{{n}}}}}" for n in _PROFIL.findall(text)]
        + _PROZENT.findall(text)
    )
