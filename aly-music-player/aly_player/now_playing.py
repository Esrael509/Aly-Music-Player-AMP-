"""Pista actual: carátula, metadatos, forma de onda y modo de progreso."""
from __future__ import annotations

import os
import threading

from pathlib import Path

from .constants import APP_NAME, ART_SIZE, R_L, WAVE_CACHE_SIZE
from .metadata import read_full_metadata, rounded_cover
from .storage import save_config
from .workers import WaveformJob


class NowPlayingMixin:
    """Pista actual: carátula, metadatos, forma de onda y modo de progreso."""

    def _load_metadata(self, path: str):
        meta = read_full_metadata(path, extract_cover=True)
        title = meta["title"]
        artist = meta["artist"]
        cover = meta["cover_bytes"]
        cover_path = meta["cover_path"]

        self.title_label.set_full_text(title)
        self.artist_label.set_full_text(artist or "Artista desconocido")
        self.setWindowTitle(f"{title} — {APP_NAME}")

        self.art_url = ""
        if cover_path and os.path.isfile(cover_path):
            self.art_url = Path(cover_path).resolve().as_uri()

        pixmap = rounded_cover(cover, ART_SIZE, R_L, self.devicePixelRatioF()) if cover else None
        if pixmap:
            self.album_art.setText("")
            self.album_art.setPixmap(pixmap)
        else:
            self.album_art.clear()
            self.album_art.setText("♪")
        self.album_art.setProperty("cover", bool(pixmap))
        self.album_art.style().unpolish(self.album_art)
        self.album_art.style().polish(self.album_art)

    def _request_waveform(self, path: str):
        if self.wave_cancel:
            self.wave_cancel.set()
        self.wave.set_progress(0.0)
        self.linear_progress.set_progress(0.0)
        cached = self.wave_cache.get(path)
        if cached is not None:
            self.wave_cache.move_to_end(path)
            self.wave.set_peaks(cached)
            return
        self.wave.set_peaks(None)
        if self.ffmpeg:
            self.wave_cancel = threading.Event()
            self.pool.start(WaveformJob(path, self.ffmpeg, self.wave_cancel, self.signals))

    def _on_wave_done(self, path: str, peaks):
        self.wave_cache[path] = peaks
        while len(self.wave_cache) > WAVE_CACHE_SIZE:
            self.wave_cache.popitem(last=False)
        if path == self.current_path:
            self.wave.set_peaks(peaks)

    def toggle_progress_mode(self):
        self.progress_mode = "bar" if self.progress_mode == "wave" else "wave"
        self.config["progress_mode"] = self.progress_mode
        save_config(self.config)
        self._sync_progress_mode_ui()

    def _sync_progress_mode_ui(self):
        is_wave = self.progress_mode == "wave"
        self.progress_stack.setCurrentIndex(0 if is_wave else 1)
        self.btn_progress_mode.setText("〜" if is_wave else "━")
        self.btn_progress_mode.setToolTip(
            "Forma de onda: clic para usar barra (W)" if is_wave
            else "Barra de progreso: clic para usar onda (W)")
