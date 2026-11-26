"""Reproducción con mpv: pistas, modos, volumen y progreso."""
from __future__ import annotations

import mpv
import os
import random

from PyQt6.QtCore import QTimer

from .constants import PLAY_MODES
from .utils import fmt_time


class PlaybackMixin:
    """Reproducción con mpv: pistas, modos, volumen y progreso."""

    def _create_player(self):
        player = mpv.MPV(ytdl=False, video=False, audio_display=False,
                         input_default_bindings=False, input_vo_keyboard=False, osc=False)
        try:
            player.volume = max(0, min(100, int(self.config.get("volume", 80))))
        except Exception:
            pass

        @player.event_callback("end-file")
        def _on_end(event):
            if self._is_eof(event):
                self.track_finished.emit()

        self.track_finished.connect(self._on_track_finished)
        return player

    @staticmethod
    def _is_eof(event) -> bool:
        try:
            reason = event.data.reason
        except Exception:
            try:
                reason = event.as_dict().get("reason")
            except Exception:
                return False
        return reason in (0, "eof", b"eof")

    def _prop(self, name: str):
        try:
            return getattr(self.player, name)
        except Exception:
            return None

    def play_playlist(self, paths: list[str], index: int):
        if 0 <= index < len(paths):
            self.playlist, self.index = paths, index
            self.play_track(paths[index])

    def play_track(self, path: str):
        if not os.path.isfile(path):
            self.status.setText("Archivo no encontrado")
            return
        self.current_path = path
        self._last_time_text = ""
        try:
            self.player.pause = False
            self.player.play(path)
        except Exception as e:
            print(f"Error de mpv: {e}")
            return
        self._record_play_stats(path)
        self._sync_fav_button()
        self._set_playing(True)
        self._load_metadata(path)
        self._request_waveform(path)
        if self.stack.currentIndex() == 1 and self.current_category in ("recent", "most_played"):
            self._render_collection()
        self._highlight_current(path)
        self._sync_mpris()

    # ---- modo de reproducción: normal → aleatorio → repetir lista → repetir pista
    def cycle_play_mode(self):
        modes = list(PLAY_MODES)
        self.set_play_mode(modes[(modes.index(self.play_mode) + 1) % len(modes)])

    def set_play_mode(self, mode: str):
        if mode in PLAY_MODES and mode != self.play_mode:
            self.play_mode = mode
            self._sync_play_mode_ui()

    def _sync_play_mode_ui(self):
        text, tip = PLAY_MODES[self.play_mode]
        self.btn_mode.setText(text)
        self.btn_mode.setToolTip(f"Modo: {tip} (R)\nClic para cambiar de modo")
        self._sync_mpris()

    def next_track(self):
        n = len(self.playlist)
        if not n:
            return
        if self.play_mode == "shuffle" and n > 1:
            i = random.randrange(n - 1)             # excluye la pista actual
            self.index = i + (i >= self.index)
        else:
            self.index = (self.index + 1) % n
        self.play_track(self.playlist[self.index])

    def prev_track(self):
        if not self.playlist:
            return
        if (self._prop("time_pos") or 0) > 3:
            self.seek_fraction(0.0)
            return
        self.index = (self.index - 1) % len(self.playlist)
        self.play_track(self.playlist[self.index])

    def _replay_current(self):
        try:
            self.player.pause = False
            self.player.play(self.current_path)
            self._set_playing(True)
        except Exception as e:
            print(f"No se pudo repetir la pista: {e}")

    def _on_track_finished(self):
        mode, n = self.play_mode, len(self.playlist)
        can_replay = bool(self.current_path and os.path.isfile(self.current_path))

        if can_replay and (mode == "repeat_one" or (mode == "repeat_all" and n <= 1)):
            self._replay_current()
        elif n > 1 and (mode != "normal" or self.index < n - 1):
            self.next_track()
        else:                                       # fin de la lista en modo normal
            self._set_playing(False)
            self.wave.set_progress(0.0)
            self.linear_progress.set_progress(0.0)
            self.time_label.setText("00:00 / 00:00")

    def toggle_play_pause(self):
        if self._prop("idle_active"):
            if self.current_path and self.playlist:
                self.play_track(self.current_path)
            else:
                view = self._active_view()
                if view is self.tree:
                    cur = self.tree.currentIndex()
                    if cur.isValid() and not self.model.isDir(cur):
                        self._play_from_tree(cur)
                elif view is self.collection_view:
                    item = self.collection_view.currentItem()
                    if item is not None:
                        self._on_collection_activated(item)
                elif view is self.results and self.result_paths:
                    self.play_playlist(list(self.result_paths),
                                       max(self.results.currentRow(), 0))
            return
        paused = not bool(self._prop("pause"))
        self.player.pause = paused
        self._set_playing(not paused)

    def _set_playing(self, playing: bool):
        self.btn_play.setText("❚❚" if playing else "▶")
        if playing:
            self.timer.start()
        else:
            self.timer.stop()
        self._sync_mpris()

    def _set_volume(self, value: int):
        try:
            self.player.volume = value
        except Exception:
            pass
        self._sync_mpris()

    def update_progress(self):
        if self._prop("idle_active"):
            return
        pos, dur = self._prop("time_pos"), self._prop("duration")
        if pos is None or not dur:
            return
        frac = pos / dur
        self.wave.set_progress(frac)
        self.linear_progress.set_progress(frac)
        text = f"{fmt_time(pos)} / {fmt_time(dur)}"
        if text != self._last_time_text:
            self._last_time_text = text
            self.time_label.setText(text)
        self.mpris.update(position=float(pos), duration=float(dur), can_seek=True)

    def seek_fraction(self, frac: float):
        dur = self._prop("duration")
        if not dur or self._prop("idle_active"):
            return
        try:
            self.player.seek(min(max(frac, 0.0), 1.0) * dur, "absolute")
        except Exception:
            return
        QTimer.singleShot(80, self.update_progress)

    def seek_relative(self, seconds: float):
        if self._prop("idle_active"):
            return
        try:
            self.player.seek(seconds, "relative")
        except Exception:
            return
        QTimer.singleShot(80, self.update_progress)
