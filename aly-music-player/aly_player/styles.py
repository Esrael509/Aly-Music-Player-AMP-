"""Hoja de estilos (string.Template) con los colores de Pywal."""
from __future__ import annotations

from string import Template

from .constants import R_L, R_M, R_S, R_XL


QSS = Template(f"""
QMainWindow, QWidget#Root {{ background-color: $bg; }}
QLabel {{ color: $fg; background: transparent; }}
QLabel#Title {{ font-size: 17px; font-weight: bold; }}
QLabel#Artist, QLabel#Status, QLabel#Time {{ color: $dim; }}

/* Contenedores principales: {R_XL}px */
QFrame#Browser, QFrame#ControlPanel {{
    background-color: $bg; border: 2px solid $accent; border-radius: {R_XL}px;
}}

/* Caja de atajos: teclas como "chips" + descripción */
QFrame#ShortcutCard {{
    background-color: $card; border: 1px solid $dim; border-radius: {R_XL}px;
}}
QLabel#Kbd {{
    background-color: $hover; color: $fg; border: 1px solid $dim;
    border-bottom: 2px solid $dim; border-radius: 5px;
    padding: 1px 5px; font-size: 10px; font-weight: bold;
}}
QLabel#KbdDesc {{ color: $dim; font-size: 11px; }}

/* Carátula: {R_L}px */
QLabel#AlbumArt {{
    background-color: $accent; color: $bg; border-radius: {R_L}px;
    font-size: 80px; font-weight: bold;
}}
QLabel#AlbumArt[cover="true"] {{ background-color: transparent; }}

/* Buscador: {R_M}px */
QLineEdit#Search {{
    background-color: $card; color: $fg; border: 2px solid $dim; border-radius: {R_M}px;
    padding: 8px 12px; selection-background-color: $accent; selection-color: $bg;
}}
QLineEdit#Search:focus {{ border-color: $accent; }}

/* Árbol y listas: ítems de {R_S}px */
QTreeView, QListWidget {{ background: transparent; color: $fg; border: none; outline: 0; }}
QTreeView::item, QListWidget::item {{ padding: 6px 6px; border-radius: {R_S}px; }}
QTreeView::item:hover, QListWidget::item:hover {{ background-color: $hover; }}
QTreeView::item:selected, QListWidget::item:selected {{
    background-color: $accent; color: $bg;
}}
QTreeView::branch {{ background: transparent; }}

/* Botones: {R_S}px */
QPushButton {{
    background-color: transparent; color: $fg; border: 1px solid $accent;
    border-radius: {R_S}px; padding: 7px 12px; font-weight: bold;
}}
QPushButton:hover, QPushButton:focus {{ background-color: $accent; color: $bg; }}
QPushButton:pressed {{ background-color: $fg; color: $bg; }}

/* Botones de pestañas y controles compactos */
QPushButton#NavTab {{
    background-color: $card; color: $fg; border: 1px solid transparent;
    border-radius: {R_S}px; padding: 5px 9px; font-size: 12px; font-weight: bold;
}}
QPushButton#NavTab:hover {{ background-color: $hover; border-color: $dim; }}
QPushButton#NavTab:checked {{
    background-color: $accent; color: $bg; border-color: $accent;
}}

QPushButton#SmallBtn {{
    background-color: $card; color: $fg; border: 1px solid $dim;
    border-radius: {R_S}px; padding: 4px 9px; font-size: 11px; font-weight: bold;
}}
QPushButton#SmallBtn:hover {{ background-color: $accent; color: $bg; border-color: $accent; }}
QPushButton#SmallBtn:checked {{ background-color: $accent; color: $bg; border-color: $accent; }}

/* Slider de volumen: {R_S}px */
QSlider::groove:horizontal {{
    border: 1px solid $accent; height: 8px; background: $bg; border-radius: 4px;
}}
QSlider::sub-page:horizontal {{ background: $accent; border-radius: 4px; }}
QSlider::handle:horizontal {{
    background: $accent; width: 16px; margin: -5px 0; border-radius: {R_S}px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 0; }}
QScrollBar::handle:vertical {{ background: $dim; border-radius: {R_S}px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QToolTip {{ background-color: $bg; color: $fg; border: 1px solid $accent; padding: 4px 8px; }}
""")
