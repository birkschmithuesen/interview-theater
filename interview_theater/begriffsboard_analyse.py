"""Die fokussierte Analyse-Schicht des Begriffsboards (Karte t_9258d2e9,
04.10.2026) -- EIN Modellaufruf, zwei Fragen:

(i) ``wunsch`` je Boardbegriff (-2..2): wie stark will die Gruppe ihn JETZT?
(ii) ``verhoerer``: welche Woerter sind STT-Verhoerer -- entschieden nach dem
     Sinn des Gespraechs, nicht nach der Zahl der Nennungen (Birks Einwand
     vom 04.10.2026 gegen die Mehrheitsregel im Board-Prompt).

**Nicht im Live-Pfad.** Gerufen wird es nur von
``scripts/rauchtest_begriffsboard_resonanz.py``; ob ein zweiter Live-Aufruf
kommt und mit welchem Modell, entscheidet Birk (Geld, Modellwahl).
``tests/test_begriffsboard_analyse.py::test_kein_live_aufrufer`` haelt das
fest.

**Warum EIN Aufruf fuer beide Fragen.** Die Eingabe ist in beiden Faellen
dasselbe Transkript, und das dominiert die Token. Zwei getrennte Aufrufe
zahlten es zweimal, haetten zwei Latenzen und zwei Prompt-Praefixe. Das
Gegenargument -- ein kombinierter Prompt verduennt den Fokus -- misst der
Rauchtest mit der Variante ``teile=("verhoerer",)``.

**Die Anweisung ist englisch und eine Modul-Konstante** (wie
``sprechweise.ANWEISUNG``): die Schicht ist Padua-only und nicht live. Wird
sie verdrahtet, gehoert sie in die Sprachschicht (deutsche Konstante plus
``sprachen/en/texte.toml``). Kein Zitat und keine Begruendung des Boards im
Nutzertext -- nur Transkript und Begriffe."""

from __future__ import annotations

from interview_theater import begriffsboard

TEILE = ("wunsch", "verhoerer")
_NUR_VERHOERER = ("verhoerer",)
ART = "begriffsboard_analyse"
ART_VERHOERER = "begriffsboard_verhoerer"
WUNSCH_MIN = -2
WUNSCH_MAX = 2
#: Obergrenzen gegen Modellgeschwaetz -- ein Verhoerer ist ein Wort oder
#: eine kurze Wendung, die Begruendung ein Satz.
LESART_MAX = 60
BEGRUENDUNG_MAX = 200

_KOPF = (
    "You analyse a group discussion for a theatre workshop. The group talks "
    "freely about which terms matter to them for their play. The transcript "
    "comes from automatic speech recognition: there are no speaker names, "
    "punctuation is unreliable, and similar-sounding words are sometimes "
    "misheard. You receive the transcript and the list of terms currently on "
    "the group's board -- nothing else.\n\nReturn JSON with these fields:"
)
_TEIL_WUNSCH = (
    "\n\n- wunsch: one object per term on the board list, with begriff (the "
    "term exactly as listed) and wunsch from -2 (the group clearly does not "
    "want it) to 2 (the group clearly wants it). Judge how strongly the group "
    "wants the term at the END of the transcript, by what the others do with "
    "it: picking it up, building on it, agreeing to it -- or doubting, "
    "dropping, replacing it. One voice repeating a term while the others move "
    "on is not agreement."
)
_TEIL_VERHOERER = (
    "\n\n- verhoerer: speech-recognition mishearings. When a word in the "
    "transcript sounds (almost) like another word, and only the other word "
    "makes sense in what the group is talking about, add an object with "
    "lesart_falsch (the spelling as written in the transcript), "
    "lesart_richtig (the spelling that fits the conversation) and "
    "begruendung_kurz (one short sentence naming the context that decides). "
    "Decide by meaning, not by count: a mishearing that occurs more often is "
    "still a mishearing, and a rarer spelling can be the right one. If "
    "nothing was misheard, verhoerer is []."
)
_NICHT_KOPF = "\n\nNot like this:"
_NICHT_WUNSCH = "\n- No entry in wunsch for a term that is not on the board list."
_NICHT_VERHOERER = (
    "\n- No pair in verhoerer whose two spellings do not sound alike."
    "\n- No pair when both words make sense in the conversation and the group "
    "means two different things."
    "\n- No pair decided only because one spelling occurs more often."
)
_NICHT_SCHLUSS = (
    "\n- No description of individual speakers."
    "\n- No text outside the JSON."
)

_TRANSKRIPT_KOPF = "TRANSCRIPT:"
_BOARD_KOPF = "TERMS ON THE BOARD:"

#: Jedes Objekt mit additionalProperties: false und vollem required -- sonst
#: lehnt der Anbieter den erzwungenen Modus ab (wie ``begriffsboard.SCHEMA``).
_VERHOERER_LISTE = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["lesart_falsch", "lesart_richtig", "begruendung_kurz"],
        "properties": {
            "lesart_falsch": {"type": "string"},
            "lesart_richtig": {"type": "string"},
            "begruendung_kurz": {"type": "string"},
        },
    },
}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["wunsch", "verhoerer"],
    "properties": {
        "wunsch": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["begriff", "wunsch"],
                "properties": {
                    "begriff": {"type": "string"},
                    "wunsch": {"type": "integer"},
                },
            },
        },
        "verhoerer": _VERHOERER_LISTE,
    },
}
SCHEMA_VERHOERER = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verhoerer"],
    "properties": {"verhoerer": _VERHOERER_LISTE},
}


def _pruefe_teile(teile) -> tuple[str, ...]:
    teile = tuple(teile)
    if teile not in (TEILE, _NUR_VERHOERER):
        raise ValueError(f"teile muss {TEILE} oder {_NUR_VERHOERER} sein, ist: {teile}")
    return teile


def anweisung(teile=TEILE) -> str:
    """Die Systemanweisung -- kombiniert oder nur die Verhoerer-Frage. Die
    Nur-Verhoerer-Fassung ist derselbe Text ohne die Wunsch-Teile."""
    mit_wunsch = _pruefe_teile(teile) == TEILE
    return (
        _KOPF
        + (_TEIL_WUNSCH if mit_wunsch else "")
        + _TEIL_VERHOERER
        + _NICHT_KOPF
        + (_NICHT_WUNSCH if mit_wunsch else "")
        + _NICHT_VERHOERER
        + _NICHT_SCHLUSS
    )


def schema_fuer(teile=TEILE) -> dict:
    return SCHEMA if _pruefe_teile(teile) == TEILE else SCHEMA_VERHOERER


def art_fuer(teile=TEILE) -> str:
    return ART if _pruefe_teile(teile) == TEILE else ART_VERHOERER


def nutzertext(transkript: str, board: list[dict]) -> str:
    """Transkript vorn (waechst nur hinten an, Praefix cache-stabil), dann
    NUR die Begriffe -- kein Zitat, keine Begruendung, keine Zahl."""
    begriffe = [str(e.get("begriff")).strip() for e in board
                if isinstance(e, dict) and str(e.get("begriff") or "").strip()]
    return (f"{_TRANSKRIPT_KOPF}\n{transkript}\n\n{_BOARD_KOPF}\n"
            + "\n".join(f"- {b}" for b in begriffe))


def _einzeilig(wert) -> str:
    return " ".join(str(wert or "").split())


def validiere(roh, transkript: str, board: list[dict]) -> dict:
    """Die Modellantwort in feste Form. ``wunsch`` nur fuer Begriffe der
    Boardliste (Schluessel ``begriffsboard.schluessel``, erste Nennung gilt),
    geklemmt. Ein Verhoerer nur, wenn beide Lesarten nicht leer, kurz und
    verschieden sind und die FALSCHE im Transkript steht (sonst behauptet
    das Modell einen Hoerfehler, den es nie gab)."""
    roh = roh if isinstance(roh, dict) else {}
    erlaubt = {begriffsboard.schluessel(e.get("begriff")) for e in board if isinstance(e, dict)}
    erlaubt.discard("")
    wunsch: dict[str, int] = {}
    for zeile in roh.get("wunsch") if isinstance(roh.get("wunsch"), list) else []:
        if not isinstance(zeile, dict):
            continue
        k = begriffsboard.schluessel(zeile.get("begriff"))
        if k not in erlaubt or k in wunsch:
            continue
        wunsch[k] = min(WUNSCH_MAX, max(WUNSCH_MIN, begriffsboard._ganzzahl(zeile.get("wunsch"))))
    text = begriffsboard.schluessel(transkript)
    verhoerer: list[dict] = []
    gesehen: set[tuple[str, str]] = set()
    for zeile in roh.get("verhoerer") if isinstance(roh.get("verhoerer"), list) else []:
        if not isinstance(zeile, dict):
            continue
        falsch = _einzeilig(zeile.get("lesart_falsch"))
        richtig = _einzeilig(zeile.get("lesart_richtig"))
        kf, kr = begriffsboard.schluessel(falsch), begriffsboard.schluessel(richtig)
        if (not kf or not kr or kf == kr or len(falsch) > LESART_MAX
                or len(richtig) > LESART_MAX or kf not in text or (kf, kr) in gesehen):
            continue
        gesehen.add((kf, kr))
        verhoerer.append({
            "lesart_falsch": falsch,
            "lesart_richtig": richtig,
            "begruendung_kurz": _einzeilig(zeile.get("begruendung_kurz"))[:BEGRUENDUNG_MAX],
        })
    return {"wunsch": wunsch, "verhoerer": verhoerer}


def analysiere(klm, transkript: str, board: list[dict], *, modell: str | None = None,
               teile=TEILE, chat_id: int | None = None) -> dict:
    """EIN Schema-Aufruf, Reasoning aus (``klm.schema`` laesst es auf
    "none"). ``modell`` nur mitgeben, wenn gesetzt -- ein Testdouble darf
    eine schmalere Signatur haben (wie ``modellwahl.aufruf_schema``)."""
    zusatz = {"modell": modell} if modell is not None else {}
    roh = klm.schema(chat_id, anweisung(teile), nutzertext(transkript, board),
                     schema_fuer(teile), art_fuer(teile), **zusatz)
    return validiere(roh, transkript, board)
