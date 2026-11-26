"""Servidor MPRIS2 / D-Bus para playerctl, Quickshell, Rofi y teclas multimedia."""
from __future__ import annotations

from typing import TYPE_CHECKING

import asyncio
import hashlib
import os
import threading

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import PropertyAccess
from dbus_next.service import dbus_property, method, ServiceInterface

from .constants import APP_NAME

if TYPE_CHECKING:
    from .window import AlyMusicPlayer


class _MprisRoot(ServiceInterface):
    def __init__(self, bridge):
        super().__init__("org.mpris.MediaPlayer2")
        self._bridge = bridge

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return APP_NAME

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> "s":
        return "aly-music-player"

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":
        return ["file"]

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":
        return ["audio/mpeg", "audio/flac", "audio/ogg", "audio/wav", "audio/mp4"]

    @method()
    def Raise(self):
        self._bridge.app.mpris_raise.emit()

    @method()
    def Quit(self):
        pass


class _MprisPlayer(ServiceInterface):
    def __init__(self, bridge):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self._bridge = bridge

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        return self._bridge.state["status"]

    @dbus_property(access=PropertyAccess.READWRITE)
    def LoopStatus(self) -> "s":
        return self._bridge.state["loop"]

    @LoopStatus.setter
    def LoopStatus(self, value: "s"):
        self._bridge.app.mpris_loop.emit(str(value))

    @dbus_property(access=PropertyAccess.READWRITE)
    def Rate(self) -> "d":
        return 1.0

    @Rate.setter
    def Rate(self, value: "d"):
        pass

    @dbus_property(access=PropertyAccess.READWRITE)
    def Shuffle(self) -> "b":
        return self._bridge.state["shuffle"]

    @Shuffle.setter
    def Shuffle(self, value: "b"):
        self._bridge.app.mpris_shuffle.emit(bool(value))

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        return self._bridge.metadata_dict()

    @dbus_property(access=PropertyAccess.READWRITE)
    def Volume(self) -> "d":
        return max(0.0, min(1.0, self._bridge.state["volume"] / 100.0))

    @Volume.setter
    def Volume(self, value: "d"):
        self._bridge.app.mpris_volume.emit(int(round(max(0.0, min(1.0, float(value))) * 100)))

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        return int(max(0.0, self._bridge.state["position"]) * 1_000_000)

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return self._bridge.state["can_next"]

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return self._bridge.state["can_previous"]

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return self._bridge.state["can_play"]

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return self._bridge.state["can_pause"]

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return self._bridge.state["can_seek"]

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return True

    @method()
    def Next(self):
        self._bridge.app.mpris_next.emit()

    @method()
    def Previous(self):
        self._bridge.app.mpris_previous.emit()

    @method()
    def Pause(self):
        self._bridge.app.mpris_pause.emit()

    @method()
    def PlayPause(self):
        self._bridge.app.mpris_play_pause.emit()

    @method()
    def Stop(self):
        self._bridge.app.mpris_stop.emit()

    @method()
    def Play(self):
        self._bridge.app.mpris_play.emit()

    @method()
    def Seek(self, Offset: "x"):
        self._bridge.app.mpris_seek_relative.emit(float(Offset) / 1_000_000.0)

    @method()
    def SetPosition(self, TrackId: "o", Position: "x"):
        self._bridge.app.mpris_seek_absolute.emit(float(Position) / 1_000_000.0)

    @method()
    def OpenUri(self, Uri: "s"):
        pass


class MprisBridge:
    """Servidor MPRIS2 para Quickshell, playerctl y otros clientes."""

    BUS_NAME = "org.mpris.MediaPlayer2.aly_music_player"
    OBJECT_PATH = "/org/mpris/MediaPlayer2"

    def __init__(self, app: "AlyMusicPlayer"):
        self.app = app
        self.state = {
            "status": "Stopped",
            "shuffle": False,
            "loop": "None",
            "volume": 80,
            "position": 0.0,
            "duration": 0.0,
            "title": "",
            "artist": "",
            "uri": "",
            "art_url": "",
            "can_next": False,
            "can_previous": False,
            "can_play": False,
            "can_pause": False,
            "can_seek": False,
        }
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bus = None
        self._player_iface: _MprisPlayer | None = None
        self._ready = threading.Event()
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="AlyMprisDBus", daemon=True
        )
        self._thread.start()

    def metadata_dict(self) -> dict[str, Variant]:
        with self._lock:
            state = dict(self.state)

        uri = state["uri"]
        if not uri:
            return {
                "mpris:trackid": Variant(
                    "o", "/org/mpris/MediaPlayer2/TrackList/NoTrack"
                )
            }

        digest = hashlib.sha1(uri.encode("utf-8")).hexdigest()[:16]
        meta = {
            "mpris:trackid": Variant(
                "o", f"/org/mpris/MediaPlayer2/Track/{digest}"
            ),
            "xesam:url": Variant("s", uri),
            "xesam:title": Variant(
                "s", state["title"] or os.path.basename(uri)
            ),
            "xesam:artist": Variant(
                "as", [state["artist"] or "Artista desconocido"]
            ),
            "mpris:length": Variant(
                "x", int(max(0.0, state["duration"]) * 1_000_000)
            ),
        }
        if state["art_url"]:
            meta["mpris:artUrl"] = Variant("s", state["art_url"])
        return meta

    def _run(self):
        """Ejecuta el loop de D-Bus y lo cierra de forma ordenada."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            # _serve solo conecta y registra el servicio; después el loop
            # permanece vivo atendiendo mensajes D-Bus con run_forever().
            self._loop.run_until_complete(self._serve())
            self._loop.run_forever()
        except Exception as e:
            if not self._stopping.is_set():
                print(f"[Aly MPRIS] Error en servidor D-Bus: {e}", flush=True)
        finally:
            self._ready.clear()
            if self._loop and not self._loop.is_closed():
                # Cancelar y esperar las tareas pendientes antes de cerrar.
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    try:
                        self._loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )
                    except Exception:
                        pass
                try:
                    self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                except Exception:
                    pass
                self._loop.close()

    async def _serve(self):
        bus = await MessageBus().connect()
        self._bus = bus

        root_iface = _MprisRoot(self)
        self._player_iface = _MprisPlayer(self)
        bus.export(self.OBJECT_PATH, root_iface)
        bus.export(self.OBJECT_PATH, self._player_iface)

        reply = await bus.request_name(self.BUS_NAME)
        self._ready.set()
        print(
            f"[Aly MPRIS] Servicio registrado: {self.BUS_NAME} ({reply})",
            flush=True,
        )

        # Publica el estado completo al terminar el registro. Esto evita que
        # un cliente que se conecta justo al iniciar Aly se quede con el
        # estado inicial vacío hasta el siguiente cambio de canción.
        self._emit_properties(
            {
                "PlaybackStatus", "Shuffle", "LoopStatus", "Volume", "CanGoNext",
                "CanGoPrevious", "CanPlay", "CanPause", "CanSeek",
                "Metadata",
            }
        )

    def _emit_properties(self, keys: set[str]):
        if not self._player_iface:
            return

        with self._lock:
            state = dict(self.state)

        # dbus-next emit_properties_changed recibe valores Python normales.
        # Solo los valores internos de Metadata (a{sv}) deben ser Variants.
        # Envolver el dict completo en Variant("a{sv}", ...) causa el error
        # ARRAY type "a" with DICT_ENTRY child ... got Variant.
        prop_map = {
            "status": ("PlaybackStatus", state["status"]),
            "shuffle": ("Shuffle", state["shuffle"]),
            "loop": ("LoopStatus", state["loop"]),
            "volume": (
                "Volume",
                max(0.0, min(1.0, state["volume"] / 100.0)),
            ),
            "can_next": ("CanGoNext", state["can_next"]),
            "can_previous": ("CanGoPrevious", state["can_previous"]),
            "can_play": ("CanPlay", state["can_play"]),
            "can_pause": ("CanPause", state["can_pause"]),
            "can_seek": ("CanSeek", state["can_seek"]),
        }

        props = {
            prop_map[key][0]: prop_map[key][1]
            for key in keys if key in prop_map
        }
        if "Metadata" in keys:
            # Metadata es a{sv}: dict Python con Variants en cada entrada.
            props["Metadata"] = self.metadata_dict()

        if props:
            self._player_iface.emit_properties_changed(props, [])

    def update(self, **kwargs):
        changed = set()
        with self._lock:
            for key, value in kwargs.items():
                if key in self.state and self.state[key] != value:
                    self.state[key] = value
                    changed.add(key)

        if not changed or not self._ready.is_set() or not self._loop:
            return

        keys = set()
        key_map = {
            "status": "PlaybackStatus",
            "shuffle": "Shuffle",
            "loop": "LoopStatus",
            "volume": "Volume",
            "can_next": "CanGoNext",
            "can_previous": "CanGoPrevious",
            "can_play": "CanPlay",
            "can_pause": "CanPause",
            "can_seek": "CanSeek",
        }
        keys.update(key_map[key] for key in changed if key in key_map)
        if changed.intersection({"uri", "title", "artist", "duration", "art_url"}):
            keys.add("Metadata")

        if keys and not self._stopping.is_set():
            try:
                if self._loop and self._loop.is_running() and not self._loop.is_closed():
                    self._loop.call_soon_threadsafe(self._emit_properties, keys)
            except RuntimeError:
                # El loop puede estar entrando en su secuencia de cierre.
                pass

    async def _shutdown(self):
        """Desconecta D-Bus mientras el loop todavía puede procesar callbacks."""
        try:
            if self._bus:
                self._bus.disconnect()
                waiter = getattr(self._bus, "wait_for_disconnect", None)
                if callable(waiter):
                    try:
                        await asyncio.wait_for(waiter(), timeout=1.0)
                    except (asyncio.TimeoutError, Exception):
                        pass
        finally:
            if self._loop and self._loop.is_running():
                self._loop.stop()

    def stop(self):
        """Solicita el cierre sin cerrar el loop desde otro hilo."""
        if self._stopping.is_set():
            return
        self._stopping.set()
        self._ready.clear()

        loop = self._loop
        if not loop or loop.is_closed() or not loop.is_running():
            return

        try:
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._shutdown())
            )
        except RuntimeError:
            pass

        # Espera breve para permitir que el hilo libere el socket D-Bus.
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=1.5)
