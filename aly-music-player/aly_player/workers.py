"""Trabajos en segundo plano: indexado de la biblioteca y forma de onda."""
from __future__ import annotations

import json
import numpy as np
import os
import subprocess
import threading

from PyQt6.QtCore import pyqtSignal, QObject, QRunnable

from .constants import AUDIO_EXTS, CACHE_DIR, LIB_CACHE_FILE, WAVE_BINS
from .metadata import read_full_metadata
from .utils import fold


class WorkerSignals(QObject):
    scan_done = pyqtSignal(list)          # [dict_track, ...]
    wave_done = pyqtSignal(str, object)   # ruta, np.ndarray normalizado 0..1


class LibraryScanJob(QRunnable):
    """Indexa la biblioteca con metadatos (artista, álbum, género, carátula) usando caché."""

    def __init__(self, root: str, signals: WorkerSignals):
        super().__init__()
        self.root, self.signals = root, signals

    @staticmethod
    def _load_cache() -> dict:
        if os.path.exists(LIB_CACHE_FILE):
            try:
                with open(LIB_CACHE_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    return raw
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    @staticmethod
    def _save_cache(cache: dict) -> None:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(LIB_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except OSError:
            pass

    def _build_item(self, path: str, sig: str) -> dict:
        meta = read_full_metadata(path, extract_cover=True)
        rel = os.path.splitext(os.path.relpath(path, self.root))[0]
        hay = fold(" ".join((rel.replace(os.sep, " "), meta["title"], meta["artist"],
                             meta["album"], meta["genre"])))
        return {
            "sig": sig,
            "path": path,
            "title": meta["title"],
            "artist": meta["artist"],
            "album": meta["album"],
            "genre": meta["genre"],
            "cover_path": meta["cover_path"],
            "hay": hay,
        }

    def run(self):
        old_cache = self._load_cache()
        new_cache = {}
        entries = []

        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if not name.lower().endswith(AUDIO_EXTS):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    st = os.stat(path)
                    sig = f"{st.st_mtime_ns}:{st.st_size}"
                except OSError:
                    continue

                cached = old_cache.get(path)
                valid = (isinstance(cached, dict) and cached.get("sig") == sig
                         and not (cached.get("cover_path")
                                  and not os.path.isfile(cached["cover_path"])))
                item = dict(cached) if valid else self._build_item(path, sig)

                new_cache[path] = item
                entries.append(item)

        entries.sort(key=lambda e: (fold(e["artist"]), fold(e["album"]), fold(e["title"]), e["path"].lower()))
        self._save_cache(new_cache)
        self.signals.scan_done.emit(entries)


class WaveformJob(QRunnable):
    """Decodifica con ffmpeg a mono 8 kHz y reduce a picos por barra con numpy."""

    def __init__(self, path: str, ffmpeg: str, cancel: threading.Event,
                 signals: WorkerSignals):
        super().__init__()
        self.path, self.ffmpeg, self.cancel, self.signals = path, ffmpeg, cancel, signals

    def run(self):
        cmd = [self.ffmpeg, "-v", "error", "-nostdin", "-i", self.path, "-vn",
               "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            return
        chunks = []
        try:
            while True:
                buf = proc.stdout.read(1 << 20)
                if not buf:
                    break
                if self.cancel.is_set():
                    proc.kill()
                    return
                chunks.append(buf)
        finally:
            proc.stdout.close()
            proc.wait()

        raw = b"".join(chunks)
        raw = raw[: len(raw) // 2 * 2]
        if not raw:
            return
        data = np.frombuffer(raw, dtype=np.int16).astype(np.int32)
        bins = min(WAVE_BINS, len(data))
        edges = np.linspace(0, len(data), bins, endpoint=False).astype(np.int64)
        peaks = np.maximum.reduceat(np.abs(data), edges).astype(np.float32)
        peak_max = float(peaks.max())
        if peak_max > 0:
            peaks = np.power(peaks / peak_max, 0.7)
        if not self.cancel.is_set():
            self.signals.wave_done.emit(self.path, peaks)
