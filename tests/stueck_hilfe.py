"""Testhilfe Stueckmodell (Karte t_fd88600b): Karten und Szenen nur ueber
die Mutations-Schnittstelle anlegen -- nie Ort/Wer/Fragen ins Karten-JSON."""

from interview_theater import repo, stueck

KARTE = {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}


class TG:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **kw):
        self.gesendet.append(text)
        return len(self.gesendet)

    def entferne_knoepfe(self, *a, **k):
        pass


def lege_karte_an(conn, chat_id=1, nummer=1, *, ort=None, wer=None, fragen=(),
                  bestaetigt=False, **felder) -> int:
    sid = repo.stelle_szene_sicher(conn, chat_id, nummer)
    karte = dict(KARTE, **felder)
    if ort is not None:
        karte["ort"] = ort
    if wer is not None:
        karte["wer"] = wer
    karte["fragen"] = list(fragen)
    stueck.karte_aus_modell(conn, chat_id, szene=nummer, karte=karte,
                            ausloeser="erstentwurf")
    if bestaetigt:
        repo.setze_szenenkarte_bestaetigt(conn, sid)
    return sid
