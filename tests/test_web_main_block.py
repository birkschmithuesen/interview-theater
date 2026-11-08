"""Der Webdienst startet mit ``python -m interview_theater.web``: dann laeuft
``main()`` aus dem ``if __name__ == "__main__"``-Block, BEVOR der Rest der
Datei ausgefuehrt ist. Was danach definiert wird, fehlt dem laufenden Server
(07.10.2026: ``_leseleiste_aus`` hinter dem Block -> jede Gruppenseite 500)."""

import ast
from pathlib import Path

import interview_theater.web as web


def test_main_block_steht_am_dateiende():
    baum = ast.parse(Path(web.__file__).read_text(encoding="utf-8"))
    koerper = baum.body
    start = next(
        i for i, knoten in enumerate(koerper)
        if isinstance(knoten, ast.If) and "__main__" in ast.unparse(knoten.test)
    )
    danach = [ast.unparse(k).splitlines()[0] for k in koerper[start + 1:]]
    assert danach == [], f"nach dem __main__-Block definiert: {danach}"
