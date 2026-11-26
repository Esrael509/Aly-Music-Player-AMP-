"""Ventana principal: ensambla los mixins, atajos, temporizadores y cierre."""
from __future__ import annotations

from collections import deque

import numpy as np
import os
import shutil
import threading

from collections import OrderedDict

from PyQt6.QtCore import pyqtSignal, Qt, QThreadPool, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import QMainWindow

from .constants import APP_NAME, PLAY_MODES, SEEK_STEP, default_music_directory
from .context_menus import ContextMenuMixin
from .favorites import FavoritesMixin
from .library import LibraryMixin
from .mpris import MprisBridge
from .mpris_controls import MprisControlsMixin
from .navigation import NavigationMixin
from .now_playing import NowPlayingMixin
from .playback import PlaybackMixin
from .storage import (
    load_pywal_theme, load_user_config, load_user_data, save_config,
    save_user_data,
)
from .ui import UiMixin
from .workers import WorkerSignals


class AlyMusicPlayer(UiMixin, LibraryMixin, FavoritesMixin, ContextMenuMixin, NavigationMixin, PlaybackMixin, NowPlayingMixin, MprisControlsMixin,
                    QMainWindow):
    track_finished = pyqtSignal()
    mpris_play = pyqtSignal()
    mpris_pause = pyqtSignal()
    mpris_play_pause = pyqtSignal()
    mpris_stop = pyqtSignal()
    mpris_next = pyqtSignal()
    mpris_previous = pyqtSignal()
    mpris_seek_relative = pyqtSignal(float)
    mpris_seek_absolute = pyqtSignal(float)
    mpris_volume = pyqtSignal(int)
    mpris_shuffle = pyqtSignal(bool)
    mpris_loop = pyqtSignal(str)
    mpris_raise = pyqtSignal()

    CATEGORIES = [
        ("folders", "Carpetas"),
        ("songs", "Canciones"),
        ("artists", "Artistas"),
        ("albums", "Álbumes"),
        ("genres", "Géneros"),
        ("recent", "Recientes"),
        ("most_played", "Más esc."),
        ("favorites", "Favoritos"),
        ("playlists", "Playlists"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1160, 760)
        self.setMinimumSize(860, 540)

        self.config = load_user_config()
        self.user_data = load_user_data()
        self.theme = load_pywal_theme()

        root = os.path.expanduser(
            str(self.config.get("default_directory") or default_music_directory())
        )
        if not os.path.isdir(root):
            root = default_music_directory()
            self.config["default_directory"] = root
            save_config(self.config)
        self.root_dir = root

        # Estado de reproducción
        self.playlist: list[str] = []
        self.index = -1
        self.current_path: str | None = None
        self.art_url = ""
        self._last_time_text = ""
        self.play_mode = self.config.get("play_mode", "normal")
        if self.play_mode not in PLAY_MODES:
            self.play_mode = "normal"
        self.progress_mode = self.config.get("progress_mode", "wave")
        if self.progress_mode not in ("wave", "bar"):
            self.progress_mode = "wave"

        # Biblioteca / navegación / vistas
        self.library: list[dict] = []
        self.meta_by_path: dict[str, dict] = {}
        self.library_ready = False
        self._scanning = False
        self.current_category = "folders"
        self.drill_key: str | None = None        # artista / álbum / género / playlist abierto
        self.view_mode = self.config.get("view_mode", "list")
        if self.view_mode not in ("list", "grid"):
            self.view_mode = "list"
        self.collection_items: list[dict] = []   # ítems actuales en collection_view
        self.result_paths: list[str] = []
        self._initial_select_done = False
        self._icon_cache: dict[tuple, QIcon | None] = {}
        self._collection_cache: dict[tuple, tuple[list[dict], str]] = {}
        self._cover_queue: deque[tuple[int, str, int]] = deque()
        self._applied_grid: bool | None = None

        # Ondas
        self.ffmpeg = shutil.which("ffmpeg")
        self.wave_cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self.wave_cancel: threading.Event | None = None

        self.pool = QThreadPool.globalInstance()
        self.signals = WorkerSignals(self)
        self.signals.scan_done.connect(self._on_scan_done)
        self.signals.wave_done.connect(self._on_wave_done)

        self.player = self._create_player()

        self._build_ui()
        self.mpris_play.connect(self._mpris_play)
        self.mpris_pause.connect(self._mpris_pause)
        self.mpris_play_pause.connect(self.toggle_play_pause)
        self.mpris_stop.connect(self._mpris_stop)
        self.mpris_next.connect(self.next_track)
        self.mpris_previous.connect(self.prev_track)
        self.mpris_seek_relative.connect(self.seek_relative)
        self.mpris_seek_absolute.connect(self._mpris_seek_absolute)
        self.mpris_volume.connect(self.volume_slider.setValue)
        self.mpris_shuffle.connect(self._mpris_set_shuffle)
        self.mpris_loop.connect(self._mpris_set_loop)
        self.mpris_raise.connect(self._mpris_raise)
        self.mpris = MprisBridge(self)
        self._setup_shortcuts()
        self._setup_timers()
        self._setup_pywal_watcher()
        self.apply_theme()

        self._sync_progress_mode_ui()
        self._sync_view_mode_ui()
        self._sync_play_mode_ui()
        self.start_scan()
        self.tree.setFocus()

    def _setup_shortcuts(self):
        def sc(key, slot, parent=self, ctx=Qt.ShortcutContext.WindowShortcut):
            s = QShortcut(QKeySequence(key), parent)
            s.setContext(ctx)
            s.activated.connect(slot)
            return s

        sc("Space", self.toggle_play_pause)
        sc("N", self.next_track)
        sc("P", self.prev_track)
        sc("Shift+Right", lambda: self.seek_relative(SEEK_STEP))
        sc("Shift+Left", lambda: self.seek_relative(-SEEK_STEP))
        sc("/", self.focus_search)
        sc("Ctrl+F", self.focus_search)
        sc("Escape", self.leave_search)
        sc("F5", self.start_scan)
        sc("W", self.toggle_progress_mode)
        sc("G", self.toggle_view_mode)
        sc("F", self.toggle_current_favorite)
        sc("R", self.cycle_play_mode)

        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        sc("J", lambda: self._move_selection(1), self.browser, ctx)
        sc("K", lambda: self._move_selection(-1), self.browser, ctx)
        sc("H", self._collapse_or_parent, self.browser, ctx)
        sc("L", self._expand_or_play, self.browser, ctx)

    def _setup_timers(self):
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_progress)

        self._cover_timer = QTimer(self)             # carga carátulas por tandas
        self._cover_timer.setInterval(0)
        self._cover_timer.timeout.connect(self._load_covers_chunk)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._run_search)

    def closeEvent(self, event):
        self.config["volume"] = self.volume_slider.value()
        self.config["progress_mode"] = self.progress_mode
        self.config["view_mode"] = self.view_mode
        self.config["play_mode"] = self.play_mode
        save_config(self.config)
        save_user_data(self.user_data)
        if self.wave_cancel:
            self.wave_cancel.set()
        self.pool.waitForDone(500)
        if hasattr(self, "mpris"):
            self.mpris.stop()
        try:
            self.player.terminate()
        except Exception:
            pass
        super().closeEvent(event)
