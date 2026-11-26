"""Utilidades pequeñas: texto sin acentos, formato de tiempo y mezcla de colores."""
from __future__ import annotations

import unicodedata

from PyQt6.QtGui import QColor


def fold(text: str) -> str:
    """Minúsculas y sin acentos, para que 'cancion' encuentre 'Canción'."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def mix(c1: str, c2: str, t: float) -> str:
    """Mezcla dos colores: t=0 -> c1, t=1 -> c2."""
    a, b = QColor(c1), QColor(c2)
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t)).name()
