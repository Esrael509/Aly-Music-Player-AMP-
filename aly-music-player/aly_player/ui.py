"""Construcción de la interfaz y aplicación del tema."""
from __future__ import annotations

import os

from PyQt6.QtCore import QDir, QFileSystemWatcher, Qt, QTimer
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QListWidget, QPushButton, QSlider, QStackedWidget, QTreeView, QVBoxLayout,
    QWidget,
)

from .constants import ART_SIZE, AUDIO_EXTS, SHORTCUTS, WAL_PATH
from .storage import load_pywal_theme
from .styles import QSS
from .widgets import ElidedLabel, ProgressBarWidget, SearchEdit, WaveformWidget


class UiMixin:
    """Construcción de la interfaz y aplicación del tema."""

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addWidget(self._build_browser(), stretch=2)
        layout.addWidget(self._build_controls(), stretch=1)

    def _build_browser(self) -> QFrame:
        self.browser = QFrame()
        self.browser.setObjectName("Browser")
        v = QVBoxLayout(self.browser)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)

        self.search = SearchEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Buscar canciones, artistas, álbumes, géneros…   ( / )")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.search_timer.start(120))
        self.search.returnPressed.connect(self._play_first_result)
        self.search.navigate.connect(self._focus_results)

        # Categorías en dos filas para mantener todos los accesos visibles.
        nav_grid = QVBoxLayout()
        nav_grid.setSpacing(5)
        self.nav_buttons: dict[str, QPushButton] = {}
        split_index = (len(self.CATEGORIES) + 1) // 2
        for row_index in range(2):
            nav_row = QHBoxLayout()
            nav_row.setSpacing(5)
            start = row_index * split_index
            end = start + split_index
            for key, label in self.CATEGORIES[start:end]:
                btn = QPushButton(label)
                btn.setObjectName("NavTab")
                btn.setCheckable(True)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.clicked.connect(lambda _checked, k=key: self.set_category(k))
                self.nav_buttons[key] = btn
                nav_row.addWidget(btn, stretch=1)
            nav_grid.addLayout(nav_row)
        self.nav_buttons["folders"].setChecked(True)

        # Barra contextual: botón volver, estado, crear playlist y vista lista/galería
        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)

        self.btn_back = QPushButton("← Atrás")
        self.btn_back.setObjectName("SmallBtn")
        self.btn_back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_back.clicked.connect(self._drill_up)
        self.btn_back.hide()

        self.status = QLabel("Indexando biblioteca…")
        self.status.setObjectName("Status")

        self.btn_play_all = QPushButton("▶ Todo")
        self.btn_play_all.setObjectName("SmallBtn")
        self.btn_play_all.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_play_all.setToolTip("Reproducir toda la lista actual")
        self.btn_play_all.clicked.connect(self._play_all_collection)
        self.btn_play_all.hide()

        self.btn_new_playlist = QPushButton("+ Nueva playlist")
        self.btn_new_playlist.setObjectName("SmallBtn")
        self.btn_new_playlist.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_new_playlist.clicked.connect(self._create_playlist_dialog)
        self.btn_new_playlist.hide()

        self.btn_view_mode = QPushButton("⊞ Galería")
        self.btn_view_mode.setObjectName("SmallBtn")
        self.btn_view_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_view_mode.setToolTip("Cambiar entre vista de lista y vista en galería (G)")
        self.btn_view_mode.clicked.connect(self.toggle_view_mode)

        sub_row.addWidget(self.btn_back)
        sub_row.addWidget(self.status, stretch=1)
        sub_row.addWidget(self.btn_play_all)
        sub_row.addWidget(self.btn_new_playlist)
        sub_row.addWidget(self.btn_view_mode)

        # 0: Árbol de carpetas
        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs |
                             QDir.Filter.Files)
        self.model.setNameFilters([f"*{e}" for e in AUDIO_EXTS])
        self.model.setNameFilterDisables(False)
        self.model.setReadOnly(True)
        self.model.setRootPath(self.root_dir)
        self.model.directoryLoaded.connect(self._on_dir_loaded)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(self.root_dir))
        for col in (1, 2, 3):
            self.tree.setColumnHidden(col, True)
        self.tree.setHeaderHidden(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(18)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setFrameShape(QFrame.Shape.NoFrame)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.activated.connect(self._on_tree_activated)

        # 1: Vista de categorías / colecciones / favoritos / playlists (Lista o Galería)
        self.collection_view = QListWidget()
        self.collection_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.collection_view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.collection_view.setFrameShape(QFrame.Shape.NoFrame)
        self.collection_view.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.collection_view.setMovement(QListWidget.Movement.Static)
        self.collection_view.setWordWrap(True)
        self.collection_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.collection_view.customContextMenuRequested.connect(self._on_collection_context_menu)
        self.collection_view.itemActivated.connect(self._on_collection_activated)

        # 2: Resultados de búsqueda
        self.results = QListWidget()
        self.results.setUniformItemSizes(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.results.setFrameShape(QFrame.Shape.NoFrame)
        self.results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self._on_results_context_menu)
        self.results.itemActivated.connect(self._on_result_activated)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.tree)             # 0
        self.stack.addWidget(self.collection_view)  # 1
        self.stack.addWidget(self.results)          # 2

        v.addWidget(self.search)
        v.addLayout(nav_grid)
        v.addLayout(sub_row)
        v.addWidget(self.stack, stretch=1)
        return self.browser

    def _build_controls(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ControlPanel")
        frame.setMinimumWidth(340)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(9)

        self.album_art = QLabel("♪")
        self.album_art.setObjectName("AlbumArt")
        self.album_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art.setFixedSize(ART_SIZE, ART_SIZE)

        self.title_label = ElidedLabel("Nada en reproducción")
        self.title_label.setObjectName("Title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist_label = ElidedLabel("Elige una canción")
        self.artist_label.setObjectName("Artist")
        self.artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Contenedor intercambiable: Forma de onda (0) / Barra de progreso (1)
        self.wave = WaveformWidget()
        self.wave.seek_requested.connect(self.seek_fraction)
        self.linear_progress = ProgressBarWidget()
        self.linear_progress.seek_requested.connect(self.seek_fraction)

        self.progress_stack = QStackedWidget()
        self.progress_stack.setFixedHeight(78)
        self.progress_stack.addWidget(self.wave)             # 0
        self.progress_stack.addWidget(self.linear_progress)  # 1

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("Time")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Una sola fila, todos con el mismo estilo y solo iconos:
        # favorito · anterior · play/pausa · siguiente · modo · onda/barra
        self.btn_fav = QPushButton("♡")
        self.btn_fav.setCheckable(True)
        self.btn_fav.setToolTip("Agregar o quitar de Favoritos (F)")
        self.btn_fav.clicked.connect(self.toggle_current_favorite)

        self.btn_prev = QPushButton("◀◀")
        self.btn_prev.setToolTip("Anterior (P)")
        self.btn_prev.clicked.connect(self.prev_track)
        self.btn_play = QPushButton("▶")
        self.btn_play.setToolTip("Reproducir / Pausa (Espacio)")
        self.btn_play.clicked.connect(self.toggle_play_pause)
        self.btn_next = QPushButton("▶▶")
        self.btn_next.setToolTip("Siguiente (N)")
        self.btn_next.clicked.connect(self.next_track)
        self.btn_mode = QPushButton()
        self.btn_mode.clicked.connect(self.cycle_play_mode)
        self.btn_progress_mode = QPushButton()
        self.btn_progress_mode.clicked.connect(self.toggle_progress_mode)

        transport = QHBoxLayout()
        transport.setSpacing(6)
        for b in (self.btn_fav, self.btn_prev, self.btn_play, self.btn_next,
                  self.btn_mode, self.btn_progress_mode):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if b is self.btn_play:
                transport.addWidget(b, stretch=1)
            else:
                b.setFixedWidth(42)
                transport.addWidget(b)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(max(0, min(100, int(self.config.get("volume", 80)))))
        self.volume_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume_slider.valueChanged.connect(self._set_volume)
        vol_row = QHBoxLayout()
        vol_lbl = QLabel("Vol")
        vol_lbl.setObjectName("Status")
        vol_row.addWidget(vol_lbl)
        vol_row.addWidget(self.volume_slider)

        self.shortcut_card = self._build_shortcut_card()

        v.addWidget(self.album_art, alignment=Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(self.title_label)
        v.addWidget(self.artist_label)
        v.addSpacing(2)
        v.addWidget(self.progress_stack)
        v.addWidget(self.time_label)
        v.addLayout(transport)
        v.addLayout(vol_row)
        v.addStretch()
        v.addWidget(self.shortcut_card)
        return frame

    @staticmethod
    def _build_shortcut_card() -> QFrame:
        """Tarjeta de atajos: dos columnas de «chips» de tecla + descripción."""
        card = QFrame()
        card.setObjectName("ShortcutCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        for i, (keys, desc) in enumerate(SHORTCUTS):
            cell = QWidget()
            row = QHBoxLayout(cell)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(3)
            for key in keys:
                chip = QLabel(key)
                chip.setObjectName("Kbd")
                row.addWidget(chip)
            row.addSpacing(3)
            label = QLabel(desc)
            label.setObjectName("KbdDesc")
            row.addWidget(label)
            row.addStretch()
            grid.addWidget(cell, i // 2, i % 2)
        return card

    def apply_theme(self):
        t = self.theme
        self.setStyleSheet(QSS.substitute(**t))
        self.wave.set_colors(t["card"], t["accent"], t["rest"])
        self.linear_progress.set_colors(t["card"], t["accent"], t["rest"])
        self._icon_cache.clear()
        if self.stack.currentIndex() == 1:
            self._render_collection()

    def _setup_pywal_watcher(self):
        self.theme_timer = QTimer(self)
        self.theme_timer.setSingleShot(True)
        self.theme_timer.timeout.connect(self._reload_theme)

        self.wal_watcher = QFileSystemWatcher(self)
        self._watch_wal()
        self.wal_watcher.fileChanged.connect(lambda _: self.theme_timer.start(150))
        self.wal_watcher.directoryChanged.connect(lambda _: self.theme_timer.start(150))

    def _watch_wal(self):
        watched = set(self.wal_watcher.files()) | set(self.wal_watcher.directories())
        for p in (WAL_PATH, os.path.dirname(WAL_PATH)):
            if p not in watched and os.path.exists(p):
                self.wal_watcher.addPath(p)

    def _reload_theme(self):
        self.theme = load_pywal_theme()
        self.apply_theme()
        self._watch_wal()
