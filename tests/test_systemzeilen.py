"""Entschlackte Systemzeilen (06.09.2026, Fix e und f).

Der Befund vom Testabend: 13 von 104 Nachrichten waren "Notiert:"-Meldungen,
und **alle 13** trugen die Zeile "Falls das nicht stimmt, sagt es mir." --
eine Zeile, die die Grundleiste darunter ohnehin als Knopf anbietet. Dazu
Systemzeilen mit Beiwerk ("ihr koennt derweil weiterarbeiten") und eine
Wiederkehr-Zeile, die zweimal wortgleich in eine arbeitende Gruppe fiel.

Die Regel, die diese Tests festhalten: **eine Systemzeile sagt, was ist --
nicht, wozu es gut ist und nicht, was man sonst noch tun koennte.**
"""

from datetime import datetime, timedelta

import pytest

from interview_theater import aufnahme, befehle, bot, erkenner, knoepfe, szene


#: Die Konstanten, die im Chat als eigene Nachricht landen. Formatvorlagen mit
#: Platzhaltern sind dabei; sie werden auf ihre Rohlaenge geprueft, das
#: eingesetzte Stueck macht sie nur unwesentlich laenger.
_MODULE = (befehle, knoepfe, aufnahme, szene, erkenner)

#: Was in keiner Systemzeile mehr stehen darf. Jede dieser Wendungen erklaert
#: etwas, wonach niemand gefragt hat, oder wiederholt, was ein Knopf sagt.
VERBOTENE_WENDUNGEN = (
    "Falls das nicht stimmt",
    "ihr koennt derweil",
    "Wenn ihr weitermachen wollt",
    "sagt mir Bescheid",
)

#: Ausnahmen: Texte, die aus einem eigenen, begruendeten Anlass laenger sind.
#: ``_TEXT_HILFE`` ist die Bedienungsanleitung selbst (sie wird nur auf
#: ``/hilfe`` geschickt), ``_TEXT_ANGEBOT_USA`` und ``_TEXT_WARNUNG_USA``
#: sind die Einwilligung in eine Datenweitergabe -- dort ist Vollstaendigkeit
#: wichtiger als Kuerze.
LANG_ERLAUBT = {"_TEXT_HILFE", "_TEXT_ANGEBOT_USA", "_TEXT_WARNUNG_USA"}


def _systemzeilen():
    for modul in _MODULE:
        for name in dir(modul):
            if not name.startswith("_TEXT_"):
                continue
            wert = getattr(modul, name)
            if isinstance(wert, str):
                yield f"{modul.__name__.split('.')[-1]}.{name}", wert


def test_keine_systemzeile_traegt_eine_verbotene_wendung():
    treffer = [
        (name, wendung)
        for name, text in _systemzeilen()
        for wendung in VERBOTENE_WENDUNGEN
        if wendung in text
    ]
    assert treffer == []


def test_systemzeilen_bleiben_bei_hoechstens_zwei_saetzen():
    """Zwei Saetze sind die Grenze -- die dritte Zeile ist erfahrungsgemaess
    immer die Erklaerung, wozu etwas gut ist."""
    import re

    zu_lang = []
    for name, text in _systemzeilen():
        if name.split(".")[-1] in LANG_ERLAUBT:
            continue
        saetze = [s for s in re.split(r"[.!?]\s", text.strip()) if s.strip()]
        if len(saetze) > 2:
            zu_lang.append((name, len(saetze)))
    assert zu_lang == []


def test_notiert_meldung_endet_mit_dem_wert():
    """Kein Nachsatz mehr unter der Notiert-Zeile."""
    text = erkenner.baue_meldung([{"art": "rahmen_setzen", "wert": "Schulhof"}])

    # Die Beschriftung kommt aus ``erkenner._NOTIERT`` (seit dem
    # Phasen-Umbau "Setting"); geprueft wird hier, dass NICHTS dahinter steht.
    assert text.startswith("Notiert:\n")
    assert text.endswith("Schulhof")
    assert len(text.splitlines()) == 2


# --- (f) "Bin wieder da" ---------------------------------------------------


def test_wiederkehr_zeile_nennt_nur_die_phase():
    """Kein "Wenn ihr weitermachen wollt, sagt mir Bescheid" mehr: die
    Knoepfe darunter sagen das (``knoepfe.biete_einstieg``)."""
    text = bot._TEXT_WIEDERKEHR.format(phase="4 · Setting & Figuren")

    assert text == "Bin wieder da. Wir sind bei 4 · Setting & Figuren."


def test_wiederkehr_erst_nach_einer_halben_stunde():
    """Am Testabend fiel die Zeile zweimal in eine arbeitende Gruppe, weil
    die Schwelle bei zwei Stunden lag und der Bot dazwischen neu startete."""
    jetzt = datetime.fromisoformat("2026-09-06T12:00:00+00:00")

    assert bot.begruessung_faellig("2026-09-06T11:50:00+00:00", jetzt) is False
    assert bot.begruessung_faellig("2026-09-06T11:20:00+00:00", jetzt) is True


def test_wiederkehr_nimmt_die_gespeicherte_phase(conn):
    """Die Phase kommt aus ``phasen.aktuelle``, nicht aus einer Vermutung --
    am Testabend stand dort "1 · Begriffe", waehrend die Gruppe bei 3 war."""
    from interview_theater import phasen

    phasen.setze(conn, 1, 4, "befehl")

    text = bot._TEXT_WIEDERKEHR.format(
        phase=phasen.bezeichnung(phasen.aktuelle(conn, 1))
    )

    assert "4 ·" in text
