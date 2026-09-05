"""Simulierter Workshop: derselbe Codepfad wie der Live-Bot, ohne Telegram.

Telegram liefert Bot-Nachrichten nie an andere Bots (Bot-FAQ) -- ein
Testbot, der den Theaterbot bespielt, ist damit ausgeschlossen. Deshalb
faehrt der Simulator den Bot **im selben Prozess**: ``bot.verarbeite_update``
und ``bot._zug_und_erkenner`` wie im Betrieb, nur mit einer
``TelegramAttrappe`` statt Netz und mit einer Wegwerf-Datenbank.

Die Teilnehmerinnen spielt ein zweites Modell (``stimmen.py``, drei
Sprachprofile), das Material kommt aus erfundenen Interviewtranskripten
(``interviews/set{1,2,3}/*.md``), der Ablauf steht in ``skript.py``, die
Bewertung in ``kennzahlen.py`` (mechanisch) und ``richter.py`` (Modell).

Alles ist datengetrieben gehalten: die Phasen kommen aus ``phasen.PHASEN``,
die Arbeitsstandfelder aus ``PRAGMA table_info(arbeitsstand)``. Der
Simulator soll einen Umbau an Phasen und Feldern ueberleben, ohne dass
jemand ihn nachzieht.
"""
