"""Strukturtest: jede oeffentliche ``repo``-Funktion, die SQL ausfuehrt, traegt
``@_gesperrt`` (AGENTS.md Falle 6) -- sonst schreibt ein Hintergrundthread
(z. B. die IT-Spiegelung des Stage Scripts) ohne ``repo._LOCK`` auf die
geteilte Verbindung ("cannot start a transaction within a transaction")."""

import ast
from pathlib import Path

from interview_theater import repo

#: Bewusst ohne Sperre: reine Lesefunktionen, die in einem schon gesperrten
#: Zusammenhang laufen bzw. nur lesen; ``stelle_web_token_sicher`` ist ein
#: atomares ``UPDATE ... WHERE web_token IS NULL`` im Startpfad.
_OHNE_SPERRE_ERLAUBT = {"stelle_web_token_sicher", "letzte_bot_nachricht_vor"}

_SQL = ("conn.execute", "conn.executemany", "conn.executescript", "conn.commit")


def test_oeffentliche_repo_funktionen_mit_sql_sind_gesperrt():
    baum = ast.parse(Path(repo.__file__).read_text(encoding="utf-8"))
    offen = []
    for n in baum.body:
        if not isinstance(n, ast.FunctionDef) or n.name.startswith("_"):
            continue
        dekoriert = any(getattr(d, "id", None) == "_gesperrt" for d in n.decorator_list)
        quelle = ast.unparse(n)
        if not dekoriert and any(s in quelle for s in _SQL) \
                and n.name not in _OHNE_SPERRE_ERLAUBT:
            offen.append(n.name)
    assert offen == []
