"""Punto de entrada de la aplicación."""
from __future__ import annotations

import locale
import sys

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from .constants import APP_NAME
from .window import AlyMusicPlayer


def main():
    app = QApplication(sys.argv)
    locale.setlocale(locale.LC_NUMERIC, "C")
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("aly-music-player")
    app.setStyle("Fusion")
    app.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))

    window = AlyMusicPlayer()
    window.show()
    sys.exit(app.exec())
