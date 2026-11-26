"""Respuesta a las órdenes MPRIS y sincronización del estado."""
from __future__ import annotations

from pathlib import Path

from .constants import MPRIS_LOOP


class MprisControlsMixin:
    """Respuesta a las órdenes MPRIS y sincronización del estado."""

    def _mpris_set_shuffle(self, enabled: bool):
        if enabled:
            self.set_play_mode("shuffle")
        elif self.play_mode == "shuffle":
            self.set_play_mode("normal")

    def _mpris_set_loop(self, status: str):
        if status == "Track":
            self.set_play_mode("repeat_one")
        elif status == "Playlist":
            self.set_play_mode("repeat_all")
        elif self.play_mode in ("repeat_one", "repeat_all"):
            self.set_play_mode("normal")

    def _mpris_play(self):
        if self._prop("idle_active"):
            self.toggle_play_pause()
        else:
            self.player.pause = False
            self._set_playing(True)

    def _mpris_pause(self):
        if not self._prop("idle_active"):
            self.player.pause = True
            self._set_playing(False)

    def _mpris_stop(self):
        try:
            self.player.stop()
        except Exception:
            pass
        self._set_playing(False)

    def _mpris_seek_absolute(self, seconds: float):
        if self._prop("duration"):
            try:
                self.player.seek(max(0.0, min(float(seconds), float(self._prop("duration")))), "absolute")
                self.update_progress()
            except Exception:
                pass

    def _mpris_raise(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _sync_mpris(self):
        if not hasattr(self, "mpris"):
            return
        path = self.current_path or ""
        position = self._prop("time_pos") or 0.0
        duration = self._prop("duration") or 0.0
        paused = bool(self._prop("pause"))
        self.mpris.update(
            status="Stopped" if not path or self._prop("idle_active") else ("Paused" if paused else "Playing"),
            shuffle=self.play_mode == "shuffle",
            loop=MPRIS_LOOP[self.play_mode],
            volume=int(self._prop("volume") if self._prop("volume") is not None else self.volume_slider.value()),
            position=float(position), duration=float(duration),
            title=getattr(self.title_label, "_full", "") if hasattr(self, "title_label") else "",
            artist=getattr(self.artist_label, "_full", "") if hasattr(self, "artist_label") else "",
            uri=Path(path).resolve().as_uri() if path else "",
            art_url=getattr(self, "art_url", ""),
            can_next=len(self.playlist) > 1,
            can_previous=len(self.playlist) > 1,
            can_play=bool(path), can_pause=bool(path), can_seek=bool(path and duration > 0),
        )
