"""Der Web-Kanal: derselbe Bot, nur ohne Telegram (30.09.2026, Karte Padua A2).

**Die Idee in einem Satz:** der Webserver ist fuer den Bot das, was Telegrams
Server heute ist -- er nimmt Browser-Ereignisse an und legt sie als
Telegram-foermige Updates in eine Tabelle; diese Klasse liest sie und schreibt
die Antworten dorthin zurueck.

Damit bleibt ``bot.schleife`` unveraendert, und ``knoepfe/`` (rund 4.500
Zeilen) wird nicht angefasst: der Weg vom Knopfdruck zur Wirkung ist derselbe
wie in Telegram, bis hinunter zu ``repo.beanspruche_knopf``.

**Warum das traegt, ist gemessen und nicht geraten.** ``simulation/attrappe.py``
ersetzt ``telegram.Telegram`` seit dem 06.09.2026 mit neun Methoden und faehrt
damit einen ganzen Workshop durch (``simulation/lauf.py``). Was hier
zusaetzlich dazukommt, ist genau eine Methode, die die Simulation nicht
braucht: ``hole_updates`` -- sie ruft ``bot.verarbeite_update`` direkt.
``tests/test_web_kanal_naht.py`` haelt die Flaeche am Quelltext fest.

**Kein SQL hier.** Alles geht ueber ``repo`` -- dieselbe Schicht, dieselbe
``RLock``-Serialisierung (Falle 6), derselbe Loeschweg. Und **kein Modell**:
diese Klasse importiert weder ``llm`` noch ``stt``.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from interview_theater import repo, sprache
from interview_theater import strom as strom_modul
from interview_theater.telegram import CALLBACK_DATA_GRENZE

log = logging.getLogger(__name__)

#: Der einmalige Hinweis "Knoepfe sind Abkuerzungen" (UX-Knoepfe-Karte,
#: Abschnitt 1) -- gezeigt vor der ersten Knopfnachricht, die eine Gruppe je
#: im Web-Chat bekommt (repo.beanspruche_abkuerzungen_hinweis). Englisches
#: Gegenstueck in sprachen/en/texte.toml, Abschnitt [web_kanal].
TEXT_ABKUERZUNG_HINWEIS = (
    "Knöpfe sind Abkürzungen – ihr könnt immer auch einfach schreiben "
    "oder sprechen."
)

T = sprache.Texte(__name__)

#: Was in ``nachricht.absender`` steht, wenn eine Gruppe im Browser schreibt.
#:
#: E8 (Birk): Web-Nachrichten tragen **keinen Vornamen**. Sie tragen aber
#: irgendein Wort, denn ``kontext.sprecherzeile`` baut
#: ``f"{sprecher}: {text}"`` und schriebe bei ``None`` woertlich ``"None:"``
#: in jeden Gespraechs-Prompt. "Gruppe" ist ein Rollenwort und kein Name --
#: und es ist ehrlich: im Browser gibt es keine Absenderin, es gibt die
#: Gruppe an einem Telefon.
ABSENDER = "Gruppe"

#: Wie lange eine Tippanzeige gilt. ``arbeitszeilen.TIPP_S`` ist 4,0 s --
#: acht Sekunden ueberbruecken einen ausgefallenen Takt, ohne die Anzeige
#: nach dem Ende eines Laufs minutenlang stehen zu lassen.
TIPPT_GUELTIG_S = 8

#: In welchen Schritten ``hole_updates`` die Tabelle abfragt, solange sie
#: leer ist. 0,25 s ist unter der Wahrnehmungsschwelle und kostet bei drei
#: Gruppen zwoelf Abfragen je Sekunde auf eine WAL-Datei im Dateisystem --
#: das ist billiger als jede Signalisierung, die wir selbst bauen muessten.
POLL_SCHRITT_S = 0.25

#: Praefix der ``file_id`` einer im Browser aufgenommenen Datei.
_VERWEIS = "web:"

#: Wo die im Browser aufgenommenen Segmente landen, bevor
#: ``aufnahme.empfange`` sie an ihren Platz kopiert -- ein Unterverzeichnis
#: je Gruppe unterhalb von ``IT_AUDIO``, damit der Loeschweg
#: (``scripts/loeschen.py`` entfernt das Audioverzeichnis einer Gruppe) sie
#: ohne Zutun mitnimmt.
EINGANG_VERZ = "web-eingang"

#: Wo Dateien liegen, die der Bot verschickt (Textbuch-Export).
AUSGANG_VERZ = "web-ausgang"

#: Was der Browser liefern darf, und mit welcher Endung es abgelegt wird.
#:
#: **Content-Type -> ENDUNG und nicht Content-Type -> ja/nein**, und das ist
#: Falle 3: ``stt.mime_typ()`` leitet den MIME-Typ, den Whisper sieht, aus der
#: Dateiendung ab. Ein WebM als ``.ogg`` abgelegt wird von Infomaniak mit
#: einer ``batch_id`` quittiert -- kein HTTP-Fehler -- und bleibt danach
#: dauerhaft auf 'pending': 89,7 s statt 2,0 s, im Betrieb nur als "haengt"
#: sichtbar.
#:
#: Chrome und Firefox liefern ``audio/webm;codecs=opus``, Safari
#: ``audio/mp4``. ``audio/ogg`` und ``audio/mpeg`` stehen daneben, weil ein
#: Browser sie waehlen darf und beide bei Whisper unstrittig sind.
#:
#: **Die eine Stelle** (Abschlussreview C1): der Webserver nimmt danach an
#: (``web_chat.MIME_ERLAUBT`` ist dieselbe Tabelle), und ``hole_updates``
#: leitet daraus die Endung im Update ab -- aus der Spalte ``mime``, nicht
#: aus dem Dateipfad, der beim Lesen noch fehlen kann.
MIME_ERLAUBT = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}

#: Wie lange eine Sprachzeile ohne ``datei`` zurueckgehalten wird
#: (Abschlussreview C1). Der Webserver legt erst die Zeile an, schreibt dann
#: die Datei und setzt erst danach den Verweis -- dazwischen liegen
#: Millisekunden. Ist die Datei nach dieser Frist immer noch nicht da (der
#: Webserver ist dazwischen abgestuerzt), geht die Zeile trotzdem raus:
#: ``lade_datei`` wirft, und ``aufnahme`` bittet die Gruppe, es nochmal zu
#: schicken. Ewig zu warten hiesse, dass alles dahinter mit wartet.
DATEI_FRIST_S = 30

#: Wie lange ein Befehl, ein Knopfdruck oder ein Text auf fruehere Segmente
#: wartet (Abschlussreview I1). Ein Segment ist "angekommen", sobald
#: ``aufnahme.empfange`` seine ``aufnahme``-Zeile angelegt hat, oder
#: endgueltig gescheitert, sobald dort der Vorfall ``download_fehlgeschlagen``
#: steht. Beides dauert bei einer lokalen Datei Millisekunden, mit allen
#: Wiederholungen (``stt.WARTEZEITEN``) gut fuenf Sekunden. Die Frist faengt
#: den Fall ab, in dem keines von beiden je kommt (eine Ausnahme vor
#: ``empfange``): danach wird ausgeliefert und geloggt.
ANKUNFT_FRIST_S = 60

#: Wie weit zurueck ueberhaupt nach unterwegs gebliebenen Segmenten gesucht
#: wird. Aelteres ist laengst geloggt und haelt nichts mehr auf.
_NACHSCHAU_S = 600


def endung_fuer_mime(mime) -> str | None:
    """Die Endung zu einem MIME-Typ, oder None.

    Parameter werden abgeschnitten (``audio/webm;codecs=opus``), gross und
    klein ist gleich. Eine **Allowlist**: was in ``MIME_ERLAUBT`` nicht
    steht, kommt nicht an."""
    if not isinstance(mime, str) or not mime.strip():
        return None
    haupt = mime.split(";", 1)[0].strip().lower()
    return MIME_ERLAUBT.get(haupt)


def _alter_s(iso, jetzt: datetime) -> float:
    """Sekunden seit ``iso``; ein unlesbarer Zeitpunkt gilt als alt -- er
    soll nichts aufhalten."""
    try:
        damals = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return float("inf")
    if damals.tzinfo is None:
        damals = damals.replace(tzinfo=timezone.utc)
    return (jetzt - damals).total_seconds()


def eingangspfad(audio_verz: str, chat_id: int, post_id: int, endung: str) -> Path:
    """Wohin ein hochgeladenes Segment gehoert."""
    return Path(audio_verz) / str(chat_id) / EINGANG_VERZ / f"{post_id}{endung}"


def datei_verweis(post_id: int, endung: str) -> str:
    """Die ``file_id`` einer hochgeladenen Aufnahme: ``"web:<id><endung>"``.

    Die **Endung wandert mit**, und das ist Falle 3: ``stt.mime_typ()``
    leitet den MIME-Typ aus der Dateiendung ab, und ein fest verdrahtetes
    ``audio/ogg`` fuer eine WebM-Datei wird von Infomaniak mit einer
    ``batch_id`` quittiert und bleibt dann dauerhaft ``pending`` -- im
    Betrieb nur als "haengt" sichtbar (89,7 s statt 2,0 s)."""
    return f"{_VERWEIS}{post_id}{endung}"


def lies_verweis(file_id: str) -> tuple[int, str] | None:
    """``"web:12.webm"`` -> ``(12, ".webm")``; None bei allem anderen.

    Tolerant wie ``knoepfe._id_aus_daten``: ein Verweis aus einer aelteren
    Fassung darf die Aufnahme-Pipeline nicht zum Absturz bringen."""
    if not isinstance(file_id, str) or not file_id.startswith(_VERWEIS):
        return None
    rest = file_id[len(_VERWEIS):]
    pfad = Path(rest)
    if not pfad.stem.isdigit():
        return None
    return int(pfad.stem), pfad.suffix


def _pruefe_daten(knoepfe) -> None:
    """Die 64-Byte-Grenze, obwohl sie im Web technisch nicht gilt.

    Zusage 1 (AGENTS.md) sagt, dass ein Knopf nur ``k:<id>`` traegt und der
    Wert in der Tabelle ``knopf`` steht. Die Pruefung hier weglassen hiesse,
    dass ein Verstoss dagegen erst im Telegram-Betrieb auffaellt -- also
    beim naechsten Workshop mit Telegram, nicht im Test."""
    for _, daten in knoepfe:
        if len(daten.encode("utf-8")) > CALLBACK_DATA_GRENZE:
            raise ValueError(f"callback_data zu lang: {len(daten)} Zeichen")


class WebKanal:
    """Ersetzt ``telegram.Telegram`` im Web-Kanal (``IT_KANAL=web``).

    Ein Prozess bedient genau EINE Gruppe -- ``chat_id`` im Konstruktor ist
    die, deren Eingang ``hole_updates`` liest. Die uebrigen Methoden nehmen
    ``chat_id`` als Parameter, damit die Signaturen denen von ``Telegram``
    gleichen; sie schreiben in die Gruppe, die ihnen genannt wird."""

    def __init__(self, conn, chat_id: int, audio_verz: str,
                 schritt_s: float = POLL_SCHRITT_S):
        self._conn = conn
        self._chat_id = int(chat_id)
        self._audio = Path(audio_verz)
        self._schritt = schritt_s
        self._stroeme: dict[tuple[int, int], strom_modul.Senke] = {}
        self._strom_sperre = threading.Lock()

    # -- Eingang -----------------------------------------------------------

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        """Der Long-Poll-Ersatz: liest ``web_post`` ab ``offset``, wartet in
        Schritten von ``POLL_SCHRITT_S`` bis ``timeout``, und liefert
        Telegram-foermige Updates.

        ``timeout=0`` fragt genau einmal (die Form, die Tests brauchen).

        Gewartet wird **zwischen** den Abfragen und nie mit einer gehaltenen
        Sperre: jeder ``repo``-Aufruf nimmt den modulweiten ``RLock`` und
        gibt ihn wieder her, sonst haenge der Webserver an unserem Schlaf.

        **Geliefert wird immer ein lueckenloses Praefix** (Abschlussreview C1,
        I1): ``bot.schleife`` rueckt den Offset je Update vor, eine
        zurueckgehaltene Zeile mit etwas Spaeterem dahinter waere danach fuer
        immer uebersprungen. Zurueckgehalten wird an zwei Stellen, beide mit
        Frist (``_lieferbar``)."""
        frist = time.monotonic() + max(0.0, float(timeout))
        while True:
            zeilen = repo.web_eingang(self._conn, self._chat_id, max(0, int(offset)))
            zeilen = self._lieferbar(zeilen)
            if zeilen:
                titel = self._titel()
                return [self._update(zeile, titel) for zeile in zeilen]
            if time.monotonic() >= frist:
                return []
            time.sleep(min(self._schritt, max(0.0, frist - time.monotonic())))

    def _lieferbar(self, zeilen) -> list:
        """Der Teil des Eingangs, der jetzt schon zum Bot darf -- von vorn bis
        zur ersten Zeile, die warten muss.

        1. **Eine Sprachzeile ohne ``datei``** (C1): der Webserver schreibt
           gerade die Datei. Wer jetzt liest, faende keinen Pfad.
        2. **Alles andere hinter einem Segment, das beim Bot noch nicht
           angekommen ist** (I1): ``bot.schleife`` gibt Segmente und Befehle
           in denselben Pool (``bot.POOL_GROESSE`` Faeden). Ohne Wartepunkt
           kann /fertig das letzte Segment ueberholen -- ``aufnahme.klasse_fuer``
           liest den Modus erst bei der Verarbeitung, und
           ``repo.hat_offene_teile`` sieht nur Zeilen, die es schon gibt; das
           Segment wuerde ein Gespraechsbeitrag statt des letzten Teils. Das
           gilt fuer jeden Nicht-Segment-Post (Text, Knopf, Befehl): auch
           "Aufnahme beenden" als Knopf und ein "fertig" im Text beenden den
           Modus. Segmente untereinander warten nicht -- sie lesen denselben
           Modus.

        Nur hier und nur im Web-Kanal: Telegram liefert seine Updates selbst,
        ``bot.schleife`` und ``aufnahme`` bleiben unveraendert (E1)."""
        jetzt = datetime.now(timezone.utc)
        bereit = []
        segment_im_stapel = False
        for zeile in zeilen:
            if zeile["typ"] == repo.WEB_TYP_SPRACHE:
                if not zeile["datei"]:
                    alter = _alter_s(zeile["erstellt_am"], jetzt)
                    if alter < DATEI_FRIST_S:
                        break
                    log.warning(
                        "Web-Aufnahme %s hat nach %.0f s noch keine Datei -- "
                        "geht trotzdem an den Bot (chat_id=%s)",
                        zeile["id"], alter, self._chat_id,
                    )
                segment_im_stapel = True
                bereit.append(zeile)
                continue
            if segment_im_stapel:
                # Ein Segment in DIESEM Stapel ist per Definition noch nicht
                # beim Bot -- der naechste Poll fragt nach.
                break
            if not self._segmente_angekommen(zeile, jetzt):
                break
            bereit.append(zeile)
        return bereit

    def _segmente_angekommen(self, zeile, jetzt: datetime) -> bool:
        """Sind alle Segmente vor ``zeile`` beim Bot angekommen (oder
        endgueltig gescheitert, oder ueber der Frist)?"""
        seit = (jetzt - timedelta(seconds=_NACHSCHAU_S)).isoformat(timespec="seconds")
        unterwegs = repo.web_segmente_unterwegs(
            self._conn, self._chat_id, int(zeile["id"]), seit,
        )
        if not unterwegs:
            return True
        if any(_alter_s(u["erstellt_am"], jetzt) < ANKUNFT_FRIST_S for u in unterwegs):
            return False
        log.warning(
            "Web-Post %s wartet nicht laenger auf Segment(e) %s -- ohne "
            "aufnahme-Zeile und ohne Vorfall nach %s s (chat_id=%s)",
            zeile["id"], ", ".join(str(u["id"]) for u in unterwegs),
            ANKUNFT_FRIST_S, self._chat_id,
        )
        return True

    def _titel(self) -> str | None:
        """Der Gruppentitel aus der Datenbank.

        Er MUSS mitkommen: ``bot.verarbeite_update`` reicht ``chat_titel`` an
        ``repo.sichere_gruppe`` weiter, und dessen
        ``ON CONFLICT DO UPDATE SET titel = excluded.titel`` setzte den Titel
        sonst bei jeder Nachricht auf NULL."""
        gruppe = repo.hole_gruppe(self._conn, self._chat_id)
        return gruppe["titel"] if gruppe is not None else None

    def _update(self, zeile, titel: str | None) -> dict:
        """Eine ``web_post``-Zeile als Telegram-Update.

        Zwei Formen, genau die zwei, die ``bot.schleife`` kennt: ein
        ``callback_query`` fuer einen Knopfdruck (``telegram.lies_knopfdruck``)
        und eine ``message`` fuer alles andere (``telegram.lies_nachricht``).
        Ein Knopfdruck ist keine Nachricht und darf nie in ``nachricht``
        landen -- sonst liest ihn der Erkenner als Gruppenbeitrag (AGENTS.md,
        die Weiche in ``bot.schleife``)."""
        post_id = int(zeile["id"])
        chat = {"id": int(zeile["chat_id"]), "type": "group"}
        if titel:
            chat["title"] = titel

        if zeile["typ"] == repo.WEB_TYP_KNOPF:
            knopf = {
                "id": f"w{post_id}",
                "data": zeile["daten"] or "",
                "message": {"message_id": zeile["bezug_message_id"], "chat": chat},
            }
            return {"update_id": post_id, "callback_query": knopf}

        nachricht = {
            "message_id": post_id,
            "chat": chat,
            "from": {"first_name": ABSENDER},
            "date": self._unix(zeile["erstellt_am"]),
        }
        if zeile["typ"] == repo.WEB_TYP_SPRACHE:
            # Aus der Spalte mime (C1) -- sie steht schon beim Anlegen der
            # Zeile, der Pfad erst danach. Der Pfad und ".ogg" sind nur noch
            # der Rueckfall fuer eine Zeile ohne bekannten Typ.
            endung = (
                endung_fuer_mime(zeile["mime"])
                or Path(zeile["datei"] or "").suffix
                or ".ogg"
            )
            nachricht["voice"] = {
                "file_id": datei_verweis(post_id, endung),
                "duration": zeile["dauer"],
                "mime_type": zeile["mime"],
                # Additiver Schluessel, den telegram.lies_nachricht mitnimmt
                # (Aufgabe 3): aufnahme.empfange braucht die Endung fuer den
                # Zielpfad, weil stt.mime_typ() daraus den MIME-Typ ableitet.
                "endung": endung,
                # Pausen-Schnitt (VAD) und Brainstorm-Flag (02.10.2026):
                # dieselbe additive Durchreiche wie ``endung``, aus den
                # gleichnamigen web_post-Spalten.
                "schnittgrund": zeile["schnittgrund"],
                "brainstorm": bool(zeile["brainstorm"]),
                # redeMs (Kanban-Karte Mithoeren SICHER, 03.10.2026):
                # dieselbe additive Durchreiche wie ``schnittgrund``, rein
                # diagnostisch.
                "rede_ms": zeile["rede_ms"],
            }
        else:
            nachricht["text"] = zeile["text"] or ""
        return {"update_id": post_id, "message": nachricht}

    @staticmethod
    def _unix(iso: str | None) -> int:
        """ISO 8601 -> Unix-Sekunden. ``telegram.lies_nachricht`` rechnet mit
        ``_iso()`` zurueck; ueber diesen Umweg bleibt die Zeitzone erhalten,
        ohne dass das Update-Format von Telegram abweicht."""
        if not iso:
            return int(datetime.now(timezone.utc).timestamp())
        try:
            return int(datetime.fromisoformat(iso).timestamp())
        except ValueError:
            return int(datetime.now(timezone.utc).timestamp())

    # -- Ausgang -----------------------------------------------------------

    def sende(self, chat_id: int, text: str, parse_mode=None, klartext=None,
              system: bool = False) -> int:
        """Eine Textnachricht. Liefert die ``message_id``.

        **Nicht geteilt**, anders als in Telegram (``teile_text``, 4000
        Zeichen): der Browser hat keine Laengengrenze, und ein Text, der in
        vier Zeilen zerfaellt, macht aus einer Bot-Antwort vier Blasen, unter
        deren letzter dann die Knoepfe haengen.

        ``klartext`` wird verworfen: er ist der Telegram-Rueckfall fuer
        HTTP 400, den es hier nicht gibt. Gespeichert wird die
        HTML-Fassung -- sie traegt mehr Information, und die Chatansicht
        filtert sie ohnehin serverseitig (Aufgabe 6).

        ``system`` (UX-Knoepfe-Karte, Abschnitt 3): eine Speicherquittung
        bekommt ``web_post.typ = WEB_TYP_SYSTEM`` statt ``WEB_TYP_TEXT`` --
        die Chatansicht stellt sie damit als gedaempfte Systemzeile statt
        als Sprechblase dar. Nur eine Anzeige-Unterscheidung: die Mitschrift
        in ``nachricht`` (fuer das Gespraechsmodell) ist davon unberuehrt."""
        typ = repo.WEB_TYP_SYSTEM if system else repo.WEB_TYP_TEXT
        return repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, typ, text=text,
        )

    def sende_mit_knoepfen(self, chat_id: int, text: str, knoepfe,
                           parse_mode=None, klartext=None,
                           system: bool = False) -> int:
        """Wie ``sende``, mit einer Leiste darunter -- je Eintrag
        ``(beschriftung, callback_data)``.

        Die Leiste steht in derselben Zeile wie der Text, und **hier** ist
        deshalb die Wahrheit darueber, was unter einer Nachricht gerade
        haengt. ``web_chat`` prueft einen Knopfdruck dagegen (Aufgabe 8) und
        nicht gegen ``knopf.message_id``: die ist nur gesetzt, wenn ein
        Aufrufer ``repo.merke_knopf_nachricht`` ruft, und das tun 22 von 47
        Sendestellen (``knoepfe.biete_einstieg`` zum Beispiel nicht).

        ``system`` wie in ``sende`` -- eine Notiert-Meldung mit Undo-Knopf
        bleibt eine Systemzeile, auch mit Tastatur darunter.

        UX-Knoepfe-Karte, Abschnitt 1: vor der ERSTEN Knopfnachricht, die
        eine Gruppe je bekommt, geht einmalig eine Systemzeile voraus --
        "Knoepfe sind Abkuerzungen". ``repo.beanspruche_abkuerzungen_hinweis``
        entscheidet bedingt (SQLite), kein Modellaufruf, kein zweiter Weg."""
        leiste = list(knoepfe)
        _pruefe_daten(leiste)
        if repo.beanspruche_abkuerzungen_hinweis(self._conn, chat_id):
            self.sende(chat_id, T.TEXT_ABKUERZUNG_HINWEIS, system=True)
        typ = repo.WEB_TYP_SYSTEM if system else repo.WEB_TYP_TEXT
        return repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, typ,
            text=text, knoepfe=leiste,
        )

    def sende_datei(self, chat_id: int, dateiname: str, inhalt, beschreibung: str = "") -> int:
        """Eine Datei (Telegram: ``sendDocument``) -- gebraucht fuer den
        Textbuch-Export in Phase 7.

        Im Browser wird daraus eine Zeile mit einem Herunterladen-Link; die
        Datei liegt unter ``IT_AUDIO/<chat_id>/web-ausgang/`` und wird von
        ``web_chat`` ausgeliefert (Aufgabe 6). Der Name wird gesaeubert: er
        kommt heute aus dem Code, aber aus ihm entsteht ein Pfad."""
        daten = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
        sauber = Path(str(dateiname)).name or "datei"
        post_id = repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, repo.WEB_TYP_DATEI,
            text=beschreibung or None, dateiname=sauber,
        )
        ziel = self._audio / str(chat_id) / AUSGANG_VERZ / f"{post_id}-{sauber}"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(daten)
        repo.setze_web_datei(self._conn, post_id, str(ziel))
        return post_id

    def sende_bild(self, chat_id: int, dateiname: str, inhalt: bytes,
                   beschreibung: str = "") -> int:
        """Eine Telefon-Organisationskarte (Telegram: ``sendPhoto``,
        UX-Knoepfe-Karte, Abschnitt 5).

        Anders als ``sende_datei``: die Datei wird **nicht** je Gruppe
        abgelegt, sie liegt schon unter ``interview_theater/static/handys/``
        und wird von dort ausgeliefert (``web_chat._blase_html`` /
        ``inhaltVon`` bauen die URL aus ``web_post.bild``). ``inhalt`` bleibt
        trotzdem Teil der Signatur -- nur so stimmt sie mit
        ``telegram.Telegram.sende_bild`` ueberein (``test_web_kanal_naht``),
        und der Aufrufer braucht die Bytes ohnehin fuer den Telegram-Weg."""
        return repo.lege_web_post_an(
            self._conn, chat_id, repo.RICHTUNG_AUS, repo.WEB_TYP_SYSTEM,
            text=beschreibung or None, bild=dateiname,
        )

    def beantworte_knopf(self, callback_query_id: str, text: str = "") -> None:
        """Das Gegenstueck zu ``answerCallbackQuery``: der Text wird an den
        Druck geschrieben, und der Browser holt ihn beim naechsten
        Zustands-Poll ab.

        Die Kennung ist ``"w<post_id>"`` (siehe ``_update``) -- es braucht
        keine eigene Spalte, um von ihr auf die Zeile zu kommen. Eine
        unbekannte Kennung ist kein Fehler: in Telegram antwortet die API auf
        einen alten Druck mit 400, und ``knoepfe.wirkung._beantworte``
        schluckt das."""
        if not isinstance(callback_query_id, str) or not callback_query_id.startswith("w"):
            return
        rest = callback_query_id[1:]
        if not rest.isdigit():
            return
        repo.setze_web_antwort(self._conn, int(rest), text)

    def aendere_text(self, chat_id: int, message_id: int, text: str) -> None:
        """``editMessageText`` -- die wechselnden Arbeitszeilen
        (``arbeitszeilen.py``). Ein Fehlschlag ist unkritisch und wird vom
        Aufrufer geschluckt, deshalb kein Rueckgabewert."""
        repo.aendere_web_text(self._conn, chat_id, message_id, text)

    def entferne_knoepfe(self, chat_id: int, message_id: int) -> None:
        """Nimmt die Leiste weg, nachdem ein Knopf gewirkt hat."""
        repo.setze_web_knoepfe(self._conn, chat_id, message_id, None)

    def aktualisiere_knoepfe(self, chat_id: int, message_id: int, knoepfe) -> None:
        """Tauscht die Leiste aus.

        Hat in ``interview_theater/`` seit dem 06.09.2026 keinen Aufrufer
        (die Fragenauswahl laeuft per Nummer im Text, ``knoepfe/fragen.py``)
        -- sie steht hier, weil die Flaeche vollstaendig sein soll und der
        naechste Toggle sie zurueckbringt."""
        leiste = list(knoepfe)
        _pruefe_daten(leiste)
        repo.setze_web_knoepfe(self._conn, chat_id, message_id, leiste)

    def loesche_nachrichten(self, chat_id: int, message_ids: list) -> int:
        """Nimmt bis zu 100 Nachrichten aus der Ansicht -- weich, mit
        ``geloescht_am``. Liefert die Zahl der uebergebenen ids, wie
        ``Telegram.loesche_nachrichten`` (der Aufrufer zaehlt keinen Erfolg
        je id)."""
        if not message_ids:
            return 0
        repo.loesche_web_posts(self._conn, chat_id, list(message_ids))
        return len(list(message_ids)[:100])

    def setze_befehle(self, befehle: list) -> None:
        """No-Op: im Browser gibt es kein Slash-Menue, und Slash-Befehle
        werden nicht beworben (AGENTS.md) -- beworben wird der Knopf. Die
        Methode existiert, damit ``bot.main`` unveraendert bleibt."""
        log.debug("setze_befehle im Web-Kanal ohne Wirkung (%s Befehle)", len(befehle))

    def tippt(self, chat_id: int) -> None:
        """Die Tippanzeige, als Zeitpunkt in ``gruppe.web_tippt_bis``.

        **Keine Zeile in ``web_post``:** ``arbeitszeilen.TIPP_S`` ist 4,0 s,
        ein vierminuetiger Szenenlauf gaebe 60 Zeilen, die je eine
        ``message_id`` aus der gemeinsamen Folge verbrauchen -- und eine
        Tippanzeige ist keine Nachricht."""
        bis = datetime.now(timezone.utc) + timedelta(seconds=TIPPT_GUELTIG_S)
        repo.setze_web_tippt(self._conn, chat_id, bis.isoformat(timespec="seconds"))

    def lade_datei(self, file_id: str, ziel) -> None:
        """Kopiert ein hochgeladenes Segment an seinen Platz.

        Das Gegenstueck zu ``Telegram.lade_datei`` (getFile + Download). Jede
        Ausnahme ist hier der richtige Ausgang: ``aufnahme._lade_mit_wiederholung``
        faengt sie, wiederholt mit ``stt.WARTEZEITEN`` und meldet danach der
        Gruppe, sie moege es nochmal schicken. Stillschweigend eine leere
        Datei anzulegen waere der falsche -- daraus wuerde ein Interview mit
        erfundenem Inhalt (gemessen 05.09.2026, N2)."""
        gelesen = lies_verweis(file_id)
        if gelesen is None:
            raise ValueError(f"kein Web-Dateiverweis: {file_id!r}")
        post_id, _endung = gelesen
        zeile = repo.hole_web_post(self._conn, post_id)
        if zeile is None or not zeile["datei"]:
            raise FileNotFoundError(f"Web-Aufnahme {post_id} ist nicht hinterlegt")
        if int(zeile["chat_id"]) != self._chat_id:
            # Die ids sind eine Folge ueber alle Gruppen: ein Verweis auf eine
            # fremde Zeile waere fremdes Material im eigenen Transkript (M4).
            raise ValueError(f"Web-Aufnahme {post_id} gehoert nicht zu dieser Gruppe")

        wurzel = self._audio.resolve()
        quelle = Path(zeile["datei"]).resolve()
        if not quelle.is_relative_to(wurzel):
            # Die Spalte wird vom Webserver geschrieben. Ein Pfad ausserhalb
            # von IT_AUDIO wuerde jede lesbare Datei des Servers in ein
            # Transkript verwandeln.
            raise ValueError(f"Web-Aufnahme {post_id} liegt ausserhalb von {wurzel}")

        ziel = Path(ziel)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(quelle.read_bytes())

    # --- Der laufende Text (30.09.2026, Karte W) ---------------------------

    def strom(self, chat_id: int, art: str):
        """Eine Senke fuer diesen Zug: was das Modell schreibt, geht gedrosselt
        in ``web_strom`` und von dort per SSE in den Browser.

        Der Kanal merkt sich die Senke je ``(chat_id, Thread)``, damit
        ``ablauf.antworte`` sie nach dem Versand ueber
        ``strom.schliesse(tg, chat_id, message_id)`` abschliessen kann -- ohne
        sie durch ``_erfrage_antwort`` und zwei Nachfassfunktionen
        durchzureichen (``ablauf.py`` ist Hotspot mehrerer Karten).

        **Je Thread, nicht je Gruppe** (Fix-Runde 1, Befund 1): ein Szenenlauf
        (eigener Thread, Minuten) und ein Gespraechszug ueberlappen im Betrieb
        regelmaessig. Mit einer Senke je ``chat_id`` brach der Gespraechszug
        den Szenenstrom ab, und das ``schliesse`` der Szene beendete die Zeile
        des Gespraechszugs ohne ``post_id`` -- beide Blasen blieben haengen.
        Gleichzeitige Stroeme einer Gruppe bestehen jetzt nebeneinander;
        Szenen- und Prosalauf schliessen zusaetzlich ueber die Senke selbst
        (``strom.schliesse(..., senke=...)``).

        ``telegram.Telegram`` hat diese Methode **nicht**: dort gibt es nichts
        zu streamen, und E1 sagt, dass der Telegram-Weg unveraendert bleibt."""
        schluessel = (chat_id, threading.get_ident())
        with self._strom_sperre:
            vorher = self._stroeme.pop(schluessel, None)
        if vorher is not None:
            # Nur ein liegengebliebener Strom DESSELBEN Threads -- der wird
            # nicht mehr beschrieben, sein Zug ist vorbei.
            vorher.abbruch()
        senke = strom_modul.Senke(
            lambda: repo.beginne_strom(self._conn, chat_id, art),
            lambda sid, text: repo.schreibe_strom(self._conn, sid, text),
            lambda sid, zustand, post_id: repo.beende_strom(
                self._conn, sid, zustand, post_id),
        )
        with self._strom_sperre:
            self._stroeme[schluessel] = senke
        return senke

    def strom_abschluss(self, chat_id: int, post_id: int | None = None,
                        abgebrochen: bool = False, senke=None) -> None:
        """Schliesst eine Senke ab: ``senke``, wenn genannt, sonst die, die
        dieser Thread fuer ``chat_id`` geoeffnet hat. Ohne laufenden Strom
        passiert nichts -- der Aufrufer weiss nicht, ob es einen gab, und soll
        es auch nicht wissen muessen."""
        with self._strom_sperre:
            if senke is None:
                senke = self._stroeme.pop((chat_id, threading.get_ident()), None)
            else:
                for schluessel, wert in list(self._stroeme.items()):
                    if wert is senke:
                        del self._stroeme[schluessel]
        if senke is None:
            return
        if abgebrochen:
            senke.abbruch()
        else:
            senke.fertig(post_id)
