"""Padua Hotfix Befund 2 (02.10.2026): das Gespraechsmodell (Infomaniak,
reiner Text) sieht keine Bilder -- es soll also kein Foto als Eingabeweg
mehr ANBIETEN ("getippt, von einem Foto abgetippt oder als Sprachnachricht").

Dieser Test prueft die Positivkontrolle aus der Karte: nach dem Streichen
der Angebote darf kein aktiver Prompt- oder Texttext mehr "Foto"/"photo"/
"fotograf" enthalten -- mit genau EINER bewussten Ausnahme, dem neuen Satz
in ``system.md`` (DE + EN), der das Wort nicht mehr anbietend, sondern
VERBIETEND benutzt ("Du kannst keine Bilder oder Dateien sehen" /
"You cannot see images or files"). Dessen Zeilen werden vor der Wortsuche
herausgefiltert, alles andere muss sauber sein.

``workshop/dortmund-2026/`` wird hier bewusst NICHT geprueft: die Karte
verlangt, dass dieses Profil byte-gleich bleibt (``git diff main --
workshop/dortmund-2026`` muss leer sein, von Hand gegengeprueft -- es
enthielt vor diesem Hotfix ohnehin kein "Foto")."""

import re
from pathlib import Path

from interview_theater import anweisungen, kontext, sprache

WURZEL = Path(anweisungen.__file__).resolve().parent.parent

#: Die zwei mandatierten Saetze (Befund 2): ein VERBOT, kein Angebot. Ihre
#: Zeilen werden aus dem zu pruefenden Text entfernt, bevor die Wortsuche
#: laeuft -- das ist die einzige wissentliche Ausnahme.
ERLAUBTE_SAETZE = (
    "Du kannst keine Bilder oder Dateien sehen",
    "You cannot see images or files",
)

#: "fotograf" deckt z.B. "fotografiert" mit ab (Birk nannte das Wort in der
#: Live-Probe: "getippt, abfotografiert oder als Sprachnachricht").
ANGEBOTS_MUSTER = re.compile(r"foto|photo", re.IGNORECASE)


def _ohne_erlaubte_saetze(text: str) -> str:
    zeilen = text.splitlines()
    return "\n".join(
        zeile for zeile in zeilen
        if not any(satz in zeile for satz in ERLAUBTE_SAETZE)
    )


def _treffer(text: str) -> list[str]:
    return ANGEBOTS_MUSTER.findall(_ohne_erlaubte_saetze(text))


def _scanne(verzeichnis: Path, glob: str = "**/*") -> dict[str, list[str]]:
    treffer = {}
    if not verzeichnis.is_dir():
        return treffer
    for pfad in sorted(verzeichnis.rglob(glob)):
        if not pfad.is_file():
            continue
        try:
            text = pfad.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Betriebsordner wie workshop/padua-2026/zugang/ koennen echte
            # Binaerartefakte enthalten (QR-Code-Screenshots, PDFs) -- die
            # pruefen wir nicht auf Promptworte, sie sind kein Text.
            continue
        gefunden = _treffer(text)
        if gefunden:
            treffer[str(pfad.relative_to(WURZEL))] = gefunden
    return treffer


def test_keine_foto_angebote_in_deutschen_prompts():
    assert _scanne(WURZEL / "interview_theater" / "prompts", "*.md") == {}


def test_keine_foto_angebote_in_englischen_prompts():
    verzeichnis = sprache.VERZEICHNIS / "en" / "prompts"
    assert _scanne(verzeichnis, "**/*.md") == {}


def test_keine_foto_angebote_in_texte_toml():
    pfad = sprache.VERZEICHNIS / "en" / "texte.toml"
    assert _treffer(pfad.read_text(encoding="utf-8")) == []


def test_keine_foto_angebote_im_padua_profil():
    assert _scanne(WURZEL / "workshop" / "padua-2026") == {}


def test_keine_foto_angebote_in_kontext_texten():
    """``kontext.py`` traegt eine Ausnahme ausserhalb der Wortsuche: die
    interne Telegram-Typkonstante ``"foto"`` (klein, Code-Literal aus
    ``telegram.py``/``db.py``, keine Prosa) steckt in
    ``_TYPEN_NICHT_SICHTBAR`` und bleibt unangetastet -- wie in ``db.py``
    und ``telegram.py``, die ausserhalb dieser Karte liegen."""
    quelltext = Path(kontext.__file__).read_text(encoding="utf-8")
    ohne_code_literal = quelltext.replace('"foto"', "")
    assert _treffer(ohne_code_literal) == []


def test_system_md_verbietet_statt_anzubieten():
    """Die Kehrseite der Positivkontrolle: der neue Verbotssatz muss
    tatsaechlich da sein -- sonst waere die Ausnahme oben ein Leck, kein
    Fund."""
    de = anweisungen.hole("system")
    en = (sprache.VERZEICHNIS / "en" / "prompts" / "system.md").read_text(encoding="utf-8")
    assert "Du kannst keine Bilder oder Dateien sehen" in de
    assert "Bitte nie um ein Foto" in de
    assert "You cannot see images or files" in en
    assert "Never ask for a photo" in en
