"""Sound effects playback for AccessGram.

This module provides short UI sounds (message sent/received, system notification)
using GStreamer.

Events without a custom sound file fall back to procedurally generated tones
via ``audiotestsrc``.  When a custom file is configured the module uses
``playbin`` so any format GStreamer can decode (WAV, OGG, MP3, FLAC, …) works.
"""

from __future__ import annotations

import logging
import os
from enum import Enum, auto
from pathlib import Path

import gi

gi.require_version("Gst", "1.0")

from gi.repository import GLib, Gst

logger = logging.getLogger(__name__)


class SoundEvent(Enum):
    """High-level sound events."""

    MESSAGE_SENT = auto()
    MESSAGE_RECEIVED = auto()
    MESSAGE_OTHER_CHAT = auto()
    SYSTEM_NOTIFICATION = auto()


# Human-readable labels for the preferences UI.
SOUND_EVENT_LABELS: dict[SoundEvent, str] = {
    SoundEvent.MESSAGE_SENT: "Message sent",
    SoundEvent.MESSAGE_RECEIVED: "Message received (active chat)",
    SoundEvent.MESSAGE_OTHER_CHAT: "Message in another chat",
    SoundEvent.SYSTEM_NOTIFICATION: "System notification",
}


_BUNDLED_SOUND_FILES: dict[SoundEvent, str] = {
    SoundEvent.MESSAGE_SENT: "telegram_sent.mp3",
    SoundEvent.MESSAGE_RECEIVED: "telegram_sent.mp3",
    SoundEvent.MESSAGE_OTHER_CHAT: "telegram_received.mp3",
    SoundEvent.SYSTEM_NOTIFICATION: "telegram_received.mp3",
}

_MAX_VOLUME = 3.0


class SoundEffects:
    """Play short UI sound effects via GStreamer."""

    def __init__(self, *, enabled: bool = True, volume: float = 1.0) -> None:
        self._enabled = enabled
        self._volume = float(max(0.0, min(volume, _MAX_VOLUME)))

        self._pipeline: Gst.Pipeline | None = None
        self._bus: Gst.Bus | None = None
        self._bus_handler_ids: list[int] = []
        self._stop_timer_id: int | None = None

        self._gst_ready = False

        # Per-event custom sound file paths.  Empty string = use default tone.
        self._custom_sounds: dict[SoundEvent, str] = {}

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self._stop_current_sound()

    def set_volume(self, volume: float) -> None:
        self._volume = float(max(0.0, min(volume, _MAX_VOLUME)))

    def set_custom_sound(self, event: SoundEvent, path: str) -> None:
        """Set a custom sound file for *event*.  Pass empty string to clear."""
        if path:
            self._custom_sounds[event] = path
        else:
            self._custom_sounds.pop(event, None)

    def clear_custom_sound(self, event: SoundEvent) -> None:
        """Remove custom sound for *event*, reverting to the bundled default sound."""
        self._custom_sounds.pop(event, None)

    def get_custom_sound(self, event: SoundEvent) -> str:
        """Return the custom sound path for *event*, or empty string."""
        return self._custom_sounds.get(event, "")

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
        # Procedural fallback if bundled files are unavailable.
        # (frequency_hz, duration_ms)
        if event == SoundEvent.MESSAGE_SENT:
            return (988.0, 60)
        if event == SoundEvent.MESSAGE_RECEIVED:
            return (659.0, 90)
        if event == SoundEvent.MESSAGE_OTHER_CHAT:
            return (523.0, 70)
        if event == SoundEvent.SYSTEM_NOTIFICATION:
            return (440.0, 140)
        return (440.0, 80)

    def _bundled_sound_path(self, event: SoundEvent) -> str:
        """Return the packaged default sound file for *event*, or empty string."""
        file_name = _BUNDLED_SOUND_FILES.get(event, "")
        if not file_name:
            return ""

        path = Path(__file__).resolve().parent / "sounds" / file_name
        if path.is_file():
            return str(path)
        return ""

    def _play_on_main(self, event: SoundEvent) -> bool:
        if not self._ensure_gst():
            return False

        custom_path = self._custom_sounds.get(event, "")
        if custom_path and os.path.isfile(custom_path):
            self._play_file(custom_path)
        else:
            bundled_path = self._bundled_sound_path(event)
            if bundled_path:
                self._play_file(bundled_path)
            else:
                frequency_hz, duration_ms = self._pattern_for_event(event)
                self._start_tone(frequency_hz, duration_ms)
        return False

    # -- File playback via playbin -----------------------------------------

    def _play_file(self, path: str) -> None:
        self._stop_current_sound()

        try:
            playbin = Gst.ElementFactory.make("playbin", "sound-playbin")
            if not playbin:
                raise RuntimeError("Could not create playbin element")

            uri = Gst.filename_to_uri(os.path.abspath(path))
            playbin.set_property("uri", uri)
            playbin.set_property("volume", self._volume)

            self._pipeline = playbin

            bus = self._pipeline.get_bus()
            if bus:
                self._bus = bus
                bus.add_signal_watch()
                self._bus_handler_ids.append(bus.connect("message::error", self._on_gst_error))
                self._bus_handler_ids.append(bus.connect("message::eos", self._on_gst_eos))

            ret = self._pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Failed to start file playback pipeline")

        except Exception as exc:
            logger.debug("Sound file playback failed: %s", exc)
            self._stop_current_sound()

    # -- Tone generation ---------------------------------------------------

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

    # -- GStreamer bus callbacks --------------------------------------------

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
