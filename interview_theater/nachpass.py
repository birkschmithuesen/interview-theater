"""Der EINE Ueberarbeitungslauf am Ende eines Schreibvorgangs (30.09.2026,
Karte R).

**Warum es das gibt.** Zwei Befunde vom 06.09.2026 haben dieselbe Wurzel: der
Bot liefert einen Text, und **danach** passiert nichts mehr. Er ist zu lang
(die Gruppe hatte Instagram-Kuerze beschlossen), und er traegt
Maschinensprache (Gedankenstrich-Inflation, "nicht X, sondern Y",
Adjektiv-Trippel, Fazitsatz). Birk hat beides von Hand nachgearbeitet. Die
Negativliste ``theater-tells.md`` steht **praeventiv** im Prompt -- das ist
die halbe Massnahme; hier ist die andere.

**Der Kostendeckel ist gebaut, nicht abgesprochen.** Nachzaehlen und
Sprachpass ergeben **eine** Notiz und **einen** Lauf, und der Pfad ist gerade:
``nach_szene`` ruft den Schreibweg genau einmal und kehrt danach zurueck --
egal, wie das Ergebnis aussieht. Bleibt der gekuerzte Text ueber dem Budget,
gibt es einen **Vorfall** und keinen zweiten Lauf. Eine Schleife hier waere
die teuerste Zeile des Repos.

**Wo er laeuft.** In dem Thread, den der Schreibweg ohnehin schon aufgemacht
hat, **unter dessen Sperre**. Deshalb ``szene.schreibe`` und nicht
``szene.starte``: ``starte`` wollte die Sperre nehmen, die der eigene Thread
gerade haelt, und liefe ins Leere. Genau so macht es
``dramaturgie/schleife.py`` schon.

**Der Zitatschutz ist die wichtigste einzelne Massnahme.** Ein Lauf, der einen
woertlichen Interviewsatz glattzieht, nimmt der Gruppe genau das, was sie
selbst gesammelt hat -- aus "also ich, ja, ich weiss nicht" wird "Es war eine
schwierige Zeit fuer mich" (theater-tells Nr. 21). Gemessen wird mit
``zitat.pruefe``, der EINEN Normalisierung des Repos. Verliert der Lauf ein
Zitat, wird sein Ergebnis **verworfen**: die alte Fassung wird
zurueckgeschrieben, und der Vorfall nennt das Zitat nicht (Belegzitate gehoeren
nicht in ein projiziertes Dashboard) -- nur seine Zahl und die Szene.

**Die Gruppe erfaehrt nichts davon.** Der Nachpass ist eine Zugabe: sie hat
ihren Text, sie wartet nicht darauf, und sie kann nichts tun. Ein
gescheiterter Nachpass ist deshalb unsichtbar und bekommt einen Vorfall
(SPEC § 11.1) -- anders als ein gescheiterter Szenenlauf, auf den die Gruppe
gerade wartet.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

#: Die ``art`` in der Tabelle ``aufruf``. Eigene Werte, damit Dashboard und
#: Kostenzeile den Nachpass **getrennt** zaehlen koennen -- so wie
#: ``dramaturgie_b1`` es vormacht. Ohne das waere "+1 Lauf je Szene" im Befund
#: nicht nachweisbar.
ART_SZENE = "szene_nachpass"
ART_PROSA = "kurzgeschichte_nachpass"

#: Vorfaelle. Alle drei sind fuer das Dashboard, nicht fuer den Chat.
VORFALL_GELAUFEN = "nachpass_gelaufen"
VORFALL_VERWORFEN = "nachpass_verworfen_zitat"
VORFALL_IMMER_NOCH = "nachpass_reicht_nicht"
VORFALL_FEHLER = "nachpass_fehlgeschlagen"


def befund(conn, chat_id: int, nummer: int | None) -> dict:
    """Was an dieser Szene zu beanstanden ist -- **reine Leseabfrage**.

    Liefert ``{"budget", "woerter", "zu_lang", "zahlen", "gemeldet"}``. Kein
    Modellaufruf, keine Schreiboperation; damit darf sie jeder Ort rufen, auch
    ein Knopf-Handler (Zusage 2) und ``scripts/laengen_probe.py``.

    Steht das Profil aus, ist das Budget 0 und ``gemeldet`` leer -- dann ist
    nichts zu tun, und der Aufrufer sieht das an einer Zahl statt an einem
    Schalter."""
    from interview_theater import laengen, repo, sprachpass, szene as szene_modul

    leer = {"budget": 0, "woerter": 0, "zu_lang": False, "zahlen": {},
            "gemeldet": []}
    ziel = None
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] == nummer and not s["entfernt_am"]:
            ziel = s
            break
    if ziel is None:
        return leer
    # Der Text dieses Laufs: im Feinschliff der Theatertext, in Phase 6 die
    # Prosafassung. ``szene.schreibt_prosa`` entscheidet das schon fuer den
    # Schreibweg -- hier dieselbe Weiche, damit nicht zwei Lesarten entstehen.
    text = (szene_modul.prosa_von(ziel)
            if szene_modul.schreibt_prosa(conn, chat_id)
            else (ziel["volltext"] or ""))
    budget = szene_modul.budget_fuer_szene(conn, chat_id, ziel)
    woerter = laengen.zaehle_woerter(text)
    zahlen: dict = {}
    gemeldet: list[str] = []
    if laengen.sprachpass_aktiv():
        zahlen = sprachpass.zaehle(text)
        gemeldet = sprachpass.ueberschreitungen(zahlen, sprachpass.grenzwerte())
    return {
        "budget": budget,
        "woerter": woerter,
        "zu_lang": laengen.zu_lang(woerter, budget),
        "zahlen": zahlen,
        "gemeldet": gemeldet,
    }


def _notiz(zu_lang: bool, gemeldet: list[str]) -> str:
    """Laenge und Sprache in EINER Regie-Notiz.

    Die Laengenhaelfte ist wortgleich die des Kuerzen-Wegs
    (``kuerzung.notiz_fuer_szene``) -- **nicht** eine zweite Formulierung
    desselben Auftrags: der Prozentwert steht an einer Stelle
    (``kuerzung.PROZENT``), und zwei Notizen fuer dieselbe Sache waeren zwei
    Wahrheiten."""
    from interview_theater import kuerzung, sprachpass

    teile = []
    if zu_lang:
        teile.append(kuerzung.notiz_fuer_szene())
    sprachlich = sprachpass.notiz(gemeldet)
    if sprachlich:
        teile.append(sprachlich)
    return "\n\n".join(teile)


def nach_szene(conn, tg, klm, e, chat_id: int, nummer: int | None,
               zeigen: bool = True) -> str | None:
    """Der Nachpass fuer EINE Szene. Liefert die Notiz, mit der gelaufen wurde
    -- oder ``None``, wenn nichts lief.

    **Genau ein Lauf**, ohne Schleife: gemessen, Notiz gebaut, ``schreibe``
    einmal gerufen, geprueft, zurueck. Wird auch der neue Text nicht kurz
    genug, gibt es ``VORFALL_IMMER_NOCH`` und keinen zweiten Aufruf.

    Aufgerufen wird sie am Ende von ``szene._lauf``, also **im schon
    laufenden Thread und unter dessen Sperre** -- deshalb ``szene.schreibe``
    und nicht ``szene.starte``.

    ``zeigen`` (Padua Phasen TEIL 2) geht unveraendert an ``szene.schreibe``
    durch -- der Prueflauf ruft den Nachpass, bevor er etwas zeigt."""
    from interview_theater import laengen, repo, sprachpass, szene as szene_modul

    if not laengen.aktiv():
        return None
    stand = befund(conn, chat_id, nummer)
    notiz = _notiz(stand["zu_lang"], stand["gemeldet"])
    if not notiz:
        return None

    ziel = next((s for s in repo.hole_szenen(conn, chat_id)
                 if s["nummer"] == nummer and not s["entfernt_am"]), None)
    if ziel is None:
        return None
    # Der Rueckweg, falls ein Zitat verlorengeht. Gemerkt wird, was
    # ``repo.aktualisiere_szene`` zurueckschreiben kann.
    alt = {
        "id": ziel["id"],
        "titel": ziel["titel"],
        "kurzbeschreibung": ziel["kurzbeschreibung"],
        "zusammenfassung": ziel["zusammenfassung"],
        "volltext": ziel["volltext"],
        "prosa": szene_modul.prosa_von(ziel),
    }
    prosa_lauf = szene_modul.schreibt_prosa(conn, chat_id)
    alter_text = alt["prosa"] if prosa_lauf else (alt["volltext"] or "")
    zitate = sprachpass.gepruefte_zitate(conn, chat_id)

    # Derselbe Auftragssatz wie beim Kuerzen und in der Dramaturgie-Pruefung
    # (``szene.TEXT_AUFTRAG_NEU``), ueber ``T`` -- unter einem englischen
    # Profil also englisch. Kein eigener Wortlaut: zwei Saetze fuer denselben
    # Auftrag waeren zwei Wahrheiten.
    auftrag = szene_modul.T.TEXT_AUFTRAG_NEU.format(nummer=nummer, notiz=notiz)
    if prosa_lauf:
        # Wie beim Kuerzen in Phase 6: ohne den Marker saehe das Modell die
        # Prosa dieser Szene nicht, weil ``volltext`` dort leer ist.
        auftrag += f" {szene_modul.BISHER_MARKER}"
    try:
        szene_modul.schreibe(conn, tg, klm, e, chat_id, auftrag, art=ART_SZENE,
                             zeigen=zeigen)
    except Exception:
        # Der Nachpass ist eine Zugabe. Reisst er, bleibt die Szene, die die
        # Gruppe schon hat -- und sie erfaehrt nichts davon: sie wartet nicht
        # darauf und kann nichts tun (SPEC § 11.1).
        log.exception("Nachpass fehlgeschlagen, chat_id=%s, Szene %s",
                      chat_id, nummer)
        _vorfall(conn, chat_id, e, VORFALL_FEHLER,
                 f"Szene {nummer}: Nachpass-Lauf gescheitert, alte Fassung bleibt")
        return None

    neu = next((s for s in repo.hole_szenen(conn, chat_id)
                if s["id"] == alt["id"]), None)
    if neu is None:
        return notiz
    neuer_text = (szene_modul.prosa_von(neu) if prosa_lauf
                  else (neu["volltext"] or ""))
    verloren = sprachpass.verlorene(alter_text, neuer_text, zitate)
    if verloren:
        # Verworfen, nicht abgewertet: die alte Fassung wird
        # zurueckgeschrieben. Die Fassungszeile des Laufs bleibt in
        # ``szenenfassung`` stehen -- diese Tabelle wird nur angehaengt, und
        # die Spur ist richtig.
        repo.aktualisiere_szene(
            conn, alt["id"], alt["titel"], alt["kurzbeschreibung"],
            alt["volltext"], alt["zusammenfassung"],
            prosa=alt["prosa"] or None,
        )
        _vorfall(
            conn, chat_id, e, VORFALL_VERWORFEN,
            f"Szene {nummer}: Nachpass verworfen, {len(verloren)} geprueftes "
            f"Belegzitat/e waere(n) verlorengegangen -- alte Fassung bleibt",
        )
        return notiz

    nachher = laengen.zaehle_woerter(neuer_text)
    _vorfall(
        conn, chat_id, e, VORFALL_GELAUFEN,
        f"Szene {nummer}: {stand['woerter']} -> {nachher} Woerter "
        f"(Budget {stand['budget']}), Sprachmuster "
        f"{', '.join(stand['gemeldet']) or 'keine'}",
    )
    if laengen.zu_lang(nachher, stand["budget"]):
        # Kein zweiter Lauf. "Noch zu lang" ist eine Meldung und kein Auftrag
        # -- ein Modell, das zweimal zu lang schreibt, schreibt es beim
        # dritten Mal auch (dieselbe Begruendung wie bei
        # ``ablauf.echo_wiederholt``).
        _vorfall(
            conn, chat_id, e, VORFALL_IMMER_NOCH,
            f"Szene {nummer}: nach dem Nachpass {nachher} Woerter bei Budget "
            f"{stand['budget']} -- kein zweiter Lauf",
        )
    return notiz


def _vorfall(conn, chat_id: int, e, art: str, text: str) -> None:
    """Ein Vorfall fuer das Dashboard -- nie eine Nachricht in den Chat, und
    **nie** mit einem Belegzitat darin (dieselbe Grenze wie bei den
    Verdichtungen: das Dashboard haengt am Beamer)."""
    from interview_theater import repo

    log.info("%s: %s", art, text)
    try:
        repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None), art, text)
    except Exception:
        log.exception("Vorfall %s nicht schreibbar", art)


#: Der Lauf hat eine andere Abschnittszahl geliefert und wurde verworfen.
#: Eigener Vorfall, weil er etwas anderes heisst als ein verlorenes Zitat:
#: hier hat das Modell die Struktur geaendert, nicht den Wortlaut.
VORFALL_ABSCHNITTSZAHL = "nachpass_abschnittszahl"


def befund_prosa(conn, chat_id: int) -> dict:
    """Was an der ganzen Kurzgeschichte zu beanstanden ist -- **reine
    Leseabfrage**.

    ``eintraege`` sind ``(nummer, form, budget, woerter)`` je Abschnitt,
    ``zu_lang`` ist wahr, sobald **ein** Abschnitt ueber der Schwelle liegt
    (einer reicht: der Lauf geht ohnehin ueber alle), und ``gemeldet`` sind die
    Sprachmuster ueber dem Grenzwert, gezaehlt am **ganzen** Text -- ein
    Fazitsatz gehoert zum Schluss der Geschichte, nicht zum Schluss jedes
    Abschnitts."""
    from interview_theater import (
        kurzgeschichte, laengen, repo, sprachpass, szene as szene_modul,
    )

    leer = {"eintraege": [], "zu_lang": False, "zahlen": {}, "gemeldet": []}
    if not laengen.aktiv():
        return leer
    budgets = kurzgeschichte.budget_eintraege(
        conn, chat_id, faktor=kurzgeschichte._faktor(conn, chat_id))
    if not budgets:
        return leer
    texte = {}
    for s in repo.hole_szenen(conn, chat_id):
        if not s["entfernt_am"] and s["nummer"] is not None:
            texte[s["nummer"]] = szene_modul.prosa_von(s)
    eintraege = [
        (n, f, b, laengen.zaehle_woerter(texte.get(n, "")))
        for n, f, b in budgets
    ]
    ganz = "\n\n".join(texte[n] for n, _f, _b, _w in eintraege if texte.get(n))
    zahlen: dict = {}
    gemeldet: list[str] = []
    if laengen.sprachpass_aktiv() and ganz:
        zahlen = sprachpass.zaehle(ganz)
        gemeldet = sprachpass.ueberschreitungen(zahlen, sprachpass.grenzwerte())
    return {
        "eintraege": eintraege,
        # Einer reicht: der Lauf geht ohnehin ueber die ganze Geschichte.
        "zu_lang": any(laengen.zu_lang(w, b) for _n, _f, b, w in eintraege),
        "zahlen": zahlen,
        "gemeldet": gemeldet,
    }


def nach_geschichte(conn, tg, klm, e, chat_id: int) -> str | None:
    """Der Nachpass fuer die ganze Kurzgeschichte (Phase 6). Liefert die
    Notiz, mit der gelaufen wurde -- oder ``None``.

    **Ein Lauf fuer alle Abschnitte.** Einer je Abschnitt waere bei sechs
    Abschnitten sechs Laeufe; so ist es +1 fuer sechs Szenen.

    **Geprueft wird VOR dem Speichern.** ``kurzgeschichte.hole_text`` liefert
    die Antwort, ohne etwas zu schreiben -- damit koennen zwei Dinge die
    Fassung noch verhindern: eine geaenderte Abschnittszahl (der Abgleich in
    ``lege_szenen_an`` ist **ergaenzend**, also behielten vorhandene
    Abschnitte ihren alten, langen Text -- genau der Fall, gegen den die
    gebundene Abschnittszahl im Nutzertext steht) und ein verlorenes
    Belegzitat. Deshalb braucht dieser Weg keinen Rueckweg: es steht nichts
    da, was zurueckzunehmen waere.

    **Wer die Abschnittszahl bindet** (02.10.2026, Karte P2-Fix,
    Restspannung 5): dieser Lauf uebergibt immer ``eintraege``, also traegt
    ``laengen.block_prosa`` die Zahl im Nutzertext
    (``laengen.SATZ_BINDUNG``) -- auch dann, wenn nur der Sprachpass
    ausgeloest hat. Die Regie-Notiz nennt sie nie --
    ``kuerzung.notiz_fuer_prosa`` traegt seit dem Abschlussreview keine Zahl
    mehr, ein Fakt hat genau eine Stelle im Prompt. Ohne
    diese Bindung wuerde die Pruefung unten still verwerfen, was sie selbst
    nicht bestellt hat (Vorfall ``nachpass_abschnittszahl``, die Gruppe
    merkt nichts). Test:
    ``tests/test_nachpass_prosa.py::test_ein_reiner_sprachpass_lauf_traegt_die_abschnittszahl``.
    """
    from interview_theater import (
        kuerzung, kurzgeschichte, laengen, repo, sprachpass,
        szene as szene_modul,
    )

    if not laengen.aktiv():
        return None
    stand = befund_prosa(conn, chat_id)
    if not stand["eintraege"]:
        return None
    anzahl = len(stand["eintraege"])
    teile = []
    if stand["zu_lang"]:
        # Wortgleich die Notiz des Kuerzen-Wegs -- der Prozentwert steht an
        # einer Stelle (``kuerzung.PROZENT``). Die Abschnittszahl bindet
        # ``laengen.SATZ_BINDUNG`` im Budget-Block, nicht die Notiz.
        teile.append(kuerzung.notiz_fuer_prosa())
    sprachlich = sprachpass.notiz(stand["gemeldet"])
    if sprachlich:
        teile.append(sprachlich)
    if not teile:
        return None
    notiz = "\n\n".join(teile)

    alte_texte = {}
    for s in repo.hole_szenen(conn, chat_id):
        if not s["entfernt_am"] and s["nummer"] is not None:
            alte_texte[s["nummer"]] = szene_modul.prosa_von(s)
    zitate = sprachpass.gepruefte_zitate(conn, chat_id)
    budgets = [(n, f, b) for n, f, b, _w in stand["eintraege"]]

    try:
        # ``vorlage=True``: ohne die bestehende Fassung im Prompt schriebe das
        # Modell "kuerzer" ueber einen Text, den es nie sah -- dieselbe
        # Begruendung wie in ``kuerzung.starte``.
        antwort = kurzgeschichte.hole_text(
            conn, klm, e, chat_id, notiz, vorlage=True, eintraege=budgets,
            art=ART_PROSA,
        )
        abschnitte = kurzgeschichte.zerlege(antwort or "")
    except Exception:
        log.exception("Prosa-Nachpass fehlgeschlagen, chat_id=%s", chat_id)
        _vorfall(conn, chat_id, e, VORFALL_FEHLER,
                 "Prosa-Nachpass gescheitert, alte Fassung bleibt")
        return None

    if len(abschnitte) != anzahl:
        _vorfall(
            conn, chat_id, e, VORFALL_ABSCHNITTSZAHL,
            f"Prosa-Nachpass verworfen: {len(abschnitte)} statt {anzahl} "
            "Abschnitte -- nichts gespeichert, alte Fassung bleibt",
        )
        return notiz

    neu_ganz = "\n\n".join(prosa for _t, _z, prosa in abschnitte)
    alt_ganz = "\n\n".join(alte_texte[n] for n in sorted(alte_texte)
                           if alte_texte[n])
    verloren = sprachpass.verlorene(alt_ganz, neu_ganz, zitate)
    if verloren:
        _vorfall(
            conn, chat_id, e, VORFALL_VERWORFEN,
            f"Prosa-Nachpass verworfen: {len(verloren)} geprueftes "
            "Belegzitat/e waere(n) verlorengegangen -- nichts gespeichert",
        )
        return notiz

    kurzgeschichte.lege_szenen_an(conn, chat_id, abschnitte)
    nachher = {n: laengen.zaehle_woerter(p)
               for n, (_t, _z, p) in enumerate(abschnitte, start=1)}
    _vorfall(
        conn, chat_id, e, VORFALL_GELAUFEN,
        "Prosa-Nachpass: "
        + "; ".join(
            f"Abschnitt {n} {w} -> {nachher.get(n, 0)} Woerter (Budget {b})"
            for n, _f, b, w in stand["eintraege"]
        )
        + f"; Sprachmuster {', '.join(stand['gemeldet']) or 'keine'}",
    )
    if any(laengen.zu_lang(nachher.get(n, 0), b)
           for n, _f, b, _w in stand["eintraege"]):
        _vorfall(
            conn, chat_id, e, VORFALL_IMMER_NOCH,
            "Prosa-Nachpass: mindestens ein Abschnitt liegt weiter ueber dem "
            "Budget -- kein zweiter Lauf",
        )
    return notiz
