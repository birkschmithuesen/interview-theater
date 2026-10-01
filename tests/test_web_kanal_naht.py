"""Die Nahtpruefung: traegt die Ersetzung von telegram.Telegram?

Der Test liest ``interview_theater/`` per AST und sammelt JEDEN Attributaufruf
auf einem Objekt, das ein Kanal ist (heisst ``tg`` oder ``_tg``). Jede so
gefundene Methode muss ``web_kanal.WebKanal`` mit derselben Signatur haben.

Warum per AST und nicht per grep: ein neuer Aufrufer, der eine
dreizehnte Methode benutzt, soll HIER auffallen und nicht im Betrieb, wenn
eine Gruppe im Browser vor einem AttributeError sitzt.

Dazu drei Sperren gegen Wege, die an ``tg`` VORBEI gehen -- gemessen am
30.09.2026, alle drei damals leer. Sie muessen leer bleiben.
"""

import ast
import inspect
from pathlib import Path

from interview_theater import telegram, web_kanal

WURZEL = Path(telegram.__file__).resolve().parent

#: Wie ein Kanal-Objekt in diesem Repo heisst. ``tg`` ueberall,
#: ``self._tg`` in ``arbeitszeilen.Lauf``.
KANALNAMEN = {"tg", "_tg"}

#: Dateien, die die Naht selbst sind und deshalb nicht dagegen gemessen werden.
AUSGENOMMEN = {"telegram.py", "web_kanal.py"}


def _kanalaufrufe() -> dict[str, set[str]]:
    """Methode -> {"datei:zeile", ...} fuer jeden Aufruf auf einem Kanal."""
    gefunden: dict[str, set[str]] = {}
    for pfad in sorted(WURZEL.rglob("*.py")):
        if pfad.name in AUSGENOMMEN:
            continue
        baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            ziel = knoten.func
            if not isinstance(ziel, ast.Attribute):
                continue
            basis = ziel.value
            name = None
            if isinstance(basis, ast.Name):
                name = basis.id
            elif isinstance(basis, ast.Attribute):
                name = basis.attr
            if name not in KANALNAMEN:
                continue
            gefunden.setdefault(ziel.attr, set()).add(
                f"{pfad.relative_to(WURZEL.parent)}:{ziel.lineno}"
            )
    return gefunden


def test_die_naht_ist_nicht_leer():
    """Ein Test, der nichts findet, prueft nichts."""
    aufrufe = _kanalaufrufe()
    assert "sende" in aufrufe
    assert "hole_updates" in aufrufe
    assert len(aufrufe) >= 10, aufrufe


def test_webkanal_kann_jede_benutzte_kanalmethode():
    fehlend = {
        name: sorted(stellen)
        for name, stellen in _kanalaufrufe().items()
        if not callable(getattr(web_kanal.WebKanal, name, None))
    }
    assert not fehlend, (
        "WebKanal fehlen Methoden, die interview_theater/ auf einem Kanal "
        f"ruft: {fehlend}"
    )


def test_signaturen_stimmen_mit_telegram_ueberein():
    """Gleiche Parameternamen in gleicher Reihenfolge.

    Nicht nur gleiche Namen der Methoden: ``sende(chat_id, text)`` und
    ``sende(text, chat_id)`` sind beide aufrufbar und genau einmal richtig.
    Vorgabewerte werden nicht verglichen -- ``hole_updates(offset,
    timeout=25)`` darf im Web einen anderen Vorgabewert haben."""
    for name in _kanalaufrufe():
        original = getattr(telegram.Telegram, name, None)
        if original is None:
            continue   # eine Methode, die es in Telegram nie gab
        erwartet = list(inspect.signature(original).parameters)
        gemessen = list(
            inspect.signature(getattr(web_kanal.WebKanal, name)).parameters
        )
        assert gemessen == erwartet, f"{name}: {gemessen} != {erwartet}"


def test_webkanal_deckt_die_ganze_telegram_flaeche_ab():
    """Auch die Methoden, die HEUTE keinen Aufrufer haben.

    ``aktualisiere_knoepfe`` hat seit dem 06.09.2026 keinen (die
    Fragenauswahl laeuft per Nummer im Text, knoepfe/fragen.py:137-141) --
    der naechste Toggle bringt sie zurueck, und dann soll sie im Web da
    sein."""
    oeffentlich = {
        name for name, _ in inspect.getmembers(
            telegram.Telegram, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    }
    fehlend = {
        name for name in oeffentlich
        if not callable(getattr(web_kanal.WebKanal, name, None))
    }
    assert not fehlend, fehlend


def test_niemand_spricht_selbst_mit_telegram():
    """Kein Modul baut eine eigene HTTP-Verbindung zur Bot-API.

    Gemessen am 30.09.2026: der einzige Treffer im Repo steht in
    ``scripts/chat_leeren_blind.py`` -- ein Handwerkzeug, kein Bot-Pfad."""
    treffer = [
        f"{p.name}:{i}"
        for p in WURZEL.rglob("*.py")
        for i, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "api.telegram.org" in zeile and p.name != "telegram.py"
    ]
    assert treffer == [], treffer


def test_der_vorname_steht_an_genau_einer_stelle():
    """E8: Web-Nachrichten tragen keinen Absendernamen.

    Das ist eine Eigenschaft des Adapters, solange ``from.first_name`` nur in
    ``telegram.lies_nachricht`` GELESEN wird. Kommt eine zweite Lesestelle
    dazu, muss E8 dort eigens gesichert werden.

    ``web_kanal.py`` ist von dieser Zaehlung ausgenommen (wie in
    ``AUSGENOMMEN`` oben): ``WebKanal._update`` baut ein Telegram-foermiges
    Update, das ``telegram.lies_nachricht`` anschliessend liest -- dafuer
    MUSS es den Schluessel ``"first_name"`` selbst tragen (``{"from":
    {"first_name": ABSENDER}}``). Das ist die Naht, die Telegrams Form
    nachbildet, kein zweiter Lesezugriff auf einen echten Vornamen."""
    treffer = [
        f"{p.name}:{i}"
        for p in WURZEL.rglob("*.py")
        for i, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "first_name" in zeile and p.name != "web_kanal.py"
    ]
    assert len(treffer) == 1 and treffer[0].startswith("telegram.py:"), treffer


def test_keine_stelle_leitet_aus_dem_vorzeichen_einer_chat_id_ab():
    """Web-Gruppen haben POSITIVE chat_ids (repo.WEB_CHAT_ID_BASIS), echte
    Telegram-Gruppen negative. Eine Stelle, die daraus etwas ableitet, waere
    fuer Web-Gruppen falsch."""
    import re

    muster = re.compile(r"chat_id\s*[<>]\s*0|abs\(\s*chat_id|-100\d")
    treffer = [
        f"{p.name}:{i}"
        for p in WURZEL.rglob("*.py")
        for i, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if muster.search(zeile)
    ]
    assert treffer == [], treffer
