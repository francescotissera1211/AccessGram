"""Sound effects playback for AccessGram.

This module provides short UI sounds (message sent/received, system notification)
using GStreamer.

The implementation intentionally avoids shipping audio assets by generating tones
with `audiotestsrc`.
"""

from __future__ import annotations

import logging
from enum import Enum, auto

import gi

gi.require_version("Gst", "1.0")

from gi.repository import GLib, Gst

logger = logging.getLogger(__name__)


class SoundEvent(Enum):
    """High-level sound events."""

    MESSAGE_SENT = auto()
    MESSAGE_RECEIVED = auto()
    SYSTEM_NOTIFICATION = auto()


class SoundEffects:
    """Play short UI sound effects via GStreamer."""

    def __init__(self, *, enabled: bool = True, volume: float = 0.35) -> None:
        self._enabled = enabled
        self._volume = float(max(0.0, min(volume, 1.0)))

        self._pipeline: Gst.Pipeline | None = None
        self._bus: Gst.Bus | None = None
        self._bus_handler_ids: list[int] = []
        self._stop_timer_id: int | None = None

        self._gst_ready = False

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self._stop_current_sound()

    def set_volume(self, volume: float) -> None:
        self._volume = float(max(0.0, min(volume, 1.0)))

    def play(self, event: SoundEvent) -> None:
        """Play a sound for the given event."""
        if not self._enabled:
            return

        # Ensure we always touch GStreamer from the GTK main loop.
        GLib.idle_add(self._play_on_main, event)

    def _ensure_gst(self) -> bool:
        if self._gst_ready:
            return True

        try:
            Gst.init(None)
            self._gst_ready = True
            return True
        except Exception as exc:
            logger.debug("Failed to initialize GStreamer for sounds: %s", exc)
            return False

    def _pattern_for_event(self, event: SoundEvent) -> tuple[float, int]:
        # (frequency_hz, duration_ms)
        if event == SoundEvent.MESSAGE_SENT:
            return (988.0, 60)
        if event == SoundEvent.MESSAGE_RECEIVED:
            return (659.0, 90)
        if event == SoundEvent.SYSTEM_NOTIFICATION:
            return (440.0, 140)
        return (440.0, 80)

    def _play_on_main(self, event: SoundEvent) -> bool:
        if not self._ensure_gst():
            return False

        frequency_hz, duration_ms = self._pattern_for_event(event)
        self._start_tone(frequency_hz, duration_ms)
        return False

    def _start_tone(self, frequency_hz: float, duration_ms: int) -> None:
        self._stop_current_sound()

        pipeline_str = (
            f"audiotestsrc wave=sine freq={frequency_hz} is-live=true "
            "! audioconvert ! audioresample "
            f"! volume volume={self._volume} "
            "! autoaudiosink sync=false"
        )

        try:
            pipeline = Gst.parse_launch(pipeline_str)
            if not pipeline:
                raise RuntimeError("Failed to create sound pipeline")

            self._pipeline = pipeline

            bus = self._pipeline.get_bus()
            if bus:
                self._bus = bus
                bus.add_signal_watch()
                self._bus_handler_ids.append(bus.connect("message::error", self._on_gst_error))
                self._bus_handler_ids.append(bus.connect("message::eos", self._on_gst_eos))

            ret = self._pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Failed to start sound pipeline")

            self._stop_timer_id = GLib.timeout_add(int(duration_ms), self._stop_current_sound)

        except Exception as exc:
            logger.debug("Sound playback failed: %s", exc)
            self._stop_current_sound()

    def _on_gst_eos(self, bus: Gst.Bus, message: Gst.Message) -> None:
        self._stop_current_sound()

    def _on_gst_error(self, bus: Gst.Bus, message: Gst.Message) -> None:
        try:
            err, debug = message.parse_error()
            logger.debug("Sound pipeline error: %s (%s)", err, debug)
        except Exception:
            logger.debug("Sound pipeline error")
        self._stop_current_sound()

    def _stop_current_sound(self) -> bool:
        if self._stop_timer_id is not None:
            try:
                GLib.source_remove(self._stop_timer_id)
            except Exception:
                pass
            self._stop_timer_id = None

        if self._bus:
            for handler_id in self._bus_handler_ids:
                try:
                    self._bus.disconnect(handler_id)
                except Exception:
                    pass
            self._bus_handler_ids.clear()

            try:
                self._bus.remove_signal_watch()
            except Exception:
                pass

        self._bus = None

        if self._pipeline:
            try:
                self._pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass

        self._pipeline = None
        return False


_sound_effects: SoundEffects | None = None


def get_sound_effects() -> SoundEffects:
    """Get the shared sound effects instance."""
    global _sound_effects
    if _sound_effects is None:
        _sound_effects = SoundEffects()
    return _sound_effects
