"""Die kleine, sichere Markdown-Teilmenge einer Buehnenkarte
(``web._buehne_markdown``, Birk 06.10.2026 P4-Quickfix): das Modell schreibt
``**fett**``/``*kursiv*``/``- Punkte``, die Tafel zeigte das vorher roh an
(Sternchen sichtbar, keine Absaetze) -- siehe auch
``tests/test_buehne_markdown_js.py`` fuer die wortgleiche JS-Teilmenge in
``web_vereint._VEREINT_JS``.

Jeder Test nennt den Mutanten, den er faengt (Brief: "name the mutant")."""

from interview_theater import web


def test_fett_wird_strong():
    """Mutant: ``_BUEHNE_FETT.sub(...)`` entfernt -- ``**x**`` bliebe
    woertlich im Ausgabetext stehen statt ``<strong>x</strong>``."""
    assert web._buehne_markdown("Das ist **wichtig**.") == "<p>Das ist <strong>wichtig</strong>.</p>"


def test_kursiv_wird_em():
    """Mutant: ``_BUEHNE_KURSIV.sub(...)`` entfernt -- ``*x*`` bliebe
    woertlich stehen statt ``<em>x</em>``."""
    assert web._buehne_markdown("Das ist *betont*.") == "<p>Das ist <em>betont</em>.</p>"


def test_fett_vor_kursiv_frisst_kein_sternpaar():
    """Mutant: Reihenfolge Fett/Kursiv vertauscht -- die Kursiv-Regel griffe
    zuerst auf den ersten/letzten Stern eines Fett-Paares und zerstueckelte
    ``**x**`` in ``<em>*x</em>*`` statt in ``<strong>x</strong>``."""
    ergebnis = web._buehne_markdown("**fett** und *kursiv*")
    assert ergebnis == "<p><strong>fett</strong> und <em>kursiv</em></p>"


def test_aufzaehlung_wird_eine_liste():
    """Mutant: ``schliesse_liste()`` wird vor jeder Aufzaehlungszeile statt
    nur bei Nicht-Aufzaehlung aufgerufen -- aus EINER ``<ul>`` wuerden drei
    einzelne."""
    text = "- eins\n- zwei\n- drei"
    assert web._buehne_markdown(text) == "<ul><li>eins</li><li>zwei</li><li>drei</li></ul>"


def test_aufzaehlung_mit_aufzaehlungspunkt():
    assert web._buehne_markdown("• eins") == "<ul><li>eins</li></ul>"


def test_zeile_aus_nur_einem_fett_label_wird_ueberschrift():
    """Mutant: ``_BUEHNE_UEBERSCHRIFT``-Zweig entfernt -- die Zeile liefe in
    den normalen ``<p>``-Zweig und bliebe eine Flieszeile ohne
    ``buehne-ueberschrift``-Klasse."""
    ergebnis = web._buehne_markdown("**What has emerged:**")
    assert ergebnis == '<p class="buehne-ueberschrift"><strong>What has emerged:</strong></p>'


def test_label_mit_text_auf_derselben_zeile_bleibt_absatz():
    """Eine Zeile mit INHALT nach dem Fett-Label ist keine Blockueberschrift
    -- Mutant: ``_BUEHNE_UEBERSCHRIFT`` wuerde faelschlich auch hier greifen
    (z. B. ein ``.+`` statt ``[^*]+`` im Fett-Teil), die Zeile verloere den
    Rest des Satzes."""
    ergebnis = web._buehne_markdown("**Topic right now:** How it continues.")
    assert ergebnis == "<p><strong>Topic right now:</strong> How it continues.</p>"
    assert "buehne-ueberschrift" not in ergebnis


def test_leerzeilen_trennen_absaetze():
    ergebnis = web._buehne_markdown("Erstens.\n\nZweitens.")
    assert ergebnis == "<p>Erstens.</p><p>Zweitens.</p>"


def test_script_tag_bleibt_reiner_text():
    """XSS-Schutz: ``html.escape`` MUSS vor den Markdown-Regeln laufen.
    Mutant: ``html.escape(text or \"\")`` durch ``text or \"\"`` ersetzt --
    ein woertliches ``<script>`` im Kartentext wuerde zu echtem Markup."""
    ergebnis = web._buehne_markdown("<script>alert(1)</script> und **fett**")
    assert "<script>" not in ergebnis
    assert "&lt;script&gt;" in ergebnis
    assert "<strong>fett</strong>" in ergebnis


def test_leerer_text_liefert_leeren_string():
    assert web._buehne_markdown("") == ""
    assert web._buehne_markdown(None) == ""


def test_buehne_html_rendert_die_karte_als_markdown():
    """Integration: ``_buehne_html`` muss ``_buehne_markdown`` tatsaechlich
    aufrufen, nicht nur ``html.escape`` (Mutant: der alte
    ``html.escape(neueste["text"] or "")``-Aufruf wieder eingesetzt -- dann
    stuenden die Sternchen wieder roh in der Tafel)."""
    from datetime import datetime, timezone

    daten = {
        "buehnenkarten": [
            {"id": 1, "text": "**Topic:** AI takes over.", "schweigen": 0,
             "erstellt_am": datetime.now(timezone.utc).isoformat()},
        ],
    }
    ausgabe = web._buehne_html(daten)
    tafel = ausgabe.split('<div id="buehne-tafel">', 1)[1].split("</div>", 1)[0]
    assert "<strong>Topic:</strong> AI takes over." in tafel
    assert "**Topic:**" not in tafel
