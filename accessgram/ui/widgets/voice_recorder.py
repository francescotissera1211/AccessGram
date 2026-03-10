"""Voice message recording widget for AccessGram.

Provides an accessible voice recording interface with
recording controls, duration display, and level indicator.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk

from accessgram.audio.recorder import RecorderState, get_recorder

logger = logging.getLogger(__name__)


class VoiceRecorderWidget(Gtk.Box):
    """Widget for recording voice messages.

    Shows a microphone button when idle, switches to recording
    controls while recording, and can optionally enter a review
    state before sending.
    """

    def __init__(
        self,
        on_recording_complete: Callable[[Path], None] | None = None,
        on_recording_cancelled: Callable[[], None] | None = None,
        shortcut_sends_immediately: bool = False,
    ) -> None:
        """Initialize the voice recorder widget.

        Args:
            on_recording_complete: Called with the recorded file path when done.
            on_recording_cancelled: Called when recording is cancelled.
            shortcut_sends_immediately: Whether the recording shortcut should
                send immediately when stopping instead of entering review mode.
        """
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._on_recording_complete = on_recording_complete
        self._on_recording_cancelled = on_recording_cancelled
        self._shortcut_sends_immediately = shortcut_sends_immediately
        self._recorder = get_recorder()
        self._duration_timer: int | None = None
        self._pending_output_path: Path | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        self.append(self._stack)

        # Idle state: microphone button
        self._idle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._record_button = Gtk.Button()
        self._record_button.set_icon_name("audio-input-microphone-symbolic")
        self._record_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Record voice message"],
        )
        self._record_button.connect("clicked", self._on_record_clicked)
        self._idle_box.append(self._record_button)
        self._stack.add_named(self._idle_box, "idle")

        # Recording state: cancel, duration, level, send
        self._recording_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._cancel_button = Gtk.Button()
        self._cancel_button.set_icon_name("process-stop-symbolic")
        self._cancel_button.add_css_class("destructive-action")
        self._cancel_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Cancel recording"],
        )
        self._cancel_button.connect("clicked", self._on_cancel_clicked)
        self._recording_box.append(self._cancel_button)

        indicator_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._recording_dot = Gtk.Label(label="•")
        self._recording_dot.add_css_class("error")
        indicator_box.append(self._recording_dot)

        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.set_width_chars(5)
        self._duration_label.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Recording duration"],
        )
        indicator_box.append(self._duration_label)

        self._recording_box.append(indicator_box)

        self._level_bar = Gtk.LevelBar()
        self._level_bar.set_min_value(0)
        self._level_bar.set_max_value(1)
        self._level_bar.set_value(0)
        self._level_bar.set_hexpand(True)
        self._level_bar.set_size_request(80, -1)
        self._level_bar.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Audio input level"],
        )
        self._recording_box.append(self._level_bar)

        self._send_button = Gtk.Button()
        self._send_button.set_icon_name("document-send-symbolic")
        self._send_button.add_css_class("suggested-action")
        self._send_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Send voice message"],
        )
        self._send_button.connect("clicked", self._on_send_clicked)
        self._recording_box.append(self._send_button)

        self._stack.add_named(self._recording_box, "recording")

        # Review state: discard or send the recorded voice message
        self._review_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._review_cancel_button = Gtk.Button()
        self._review_cancel_button.set_icon_name("process-stop-symbolic")
        self._review_cancel_button.add_css_class("destructive-action")
        self._review_cancel_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Discard recorded voice message"],
        )
        self._review_cancel_button.connect("clicked", self._on_review_cancel_clicked)
        self._review_box.append(self._review_cancel_button)

        self._review_label = Gtk.Label(label="Voice message ready")
        self._review_label.set_xalign(0)
        self._review_label.set_hexpand(True)
        self._review_label.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Voice message ready for review"],
        )
        self._review_box.append(self._review_label)

        self._review_send_button = Gtk.Button()
        self._review_send_button.set_icon_name("document-send-symbolic")
        self._review_send_button.add_css_class("suggested-action")
        self._review_send_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Send recorded voice message"],
        )
        self._review_send_button.connect("clicked", self._on_review_send_clicked)
        self._review_box.append(self._review_send_button)

        self._stack.add_named(self._review_box, "review")
        self._stack.set_visible_child_name("idle")

    def set_shortcut_sends_immediately(self, enabled: bool) -> None:
        """Set whether the shortcut should send immediately on stop."""
        self._shortcut_sends_immediately = bool(enabled)

    def _start_recording(self, *, focus_cancel: bool = True) -> bool:
        """Start recording and switch to the recording UI."""
        self._recorder.set_callbacks(
            on_state_changed=self._on_recorder_state_changed,
            on_level_changed=self._on_level_changed,
            on_error=self._on_recorder_error,
        )

        if self._recorder.start():
            self._pending_output_path = None
            self._stack.set_visible_child_name("recording")
            self._start_duration_timer()
            if focus_cancel:
                self._cancel_button.grab_focus()
            return True
        return False

    def _on_record_clicked(self, button: Gtk.Button) -> None:
        """Start recording from the button."""
        self._start_recording()

    def _cancel_recording(self) -> None:
        """Cancel an active recording."""
        self._stop_duration_timer()
        self._recorder.cancel()
        self._stack.set_visible_child_name("idle")
        self._reset_ui()
        self._pending_output_path = None

        if self._on_recording_cancelled:
            self._on_recording_cancelled()

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Cancel recording from the recording controls."""
        self._cancel_recording()

    def _finalize_recording_for_review(self) -> None:
        """Stop recording and enter review mode."""
        self._stop_duration_timer()
        output_path = self._recorder.stop()
        if not output_path:
            self._stack.set_visible_child_name("idle")
            self._reset_ui()
            return

        self._pending_output_path = output_path
        self._review_label.set_label(f"Voice message ready ({self._duration_label.get_label()})")
        self._stack.set_visible_child_name("review")
        self._level_bar.set_value(0)
        self._review_send_button.grab_focus()

    def _send_recording(self, output_path: Path | None) -> None:
        """Send a finished recording file if one exists."""
        self._stack.set_visible_child_name("idle")
        self._reset_ui()
        self._pending_output_path = None

        if output_path and self._on_recording_complete:
            self._on_recording_complete(output_path)

    def _on_send_clicked(self, button: Gtk.Button) -> None:
        """Stop recording and send immediately from the button."""
        self._stop_duration_timer()
        output_path = self._recorder.stop()
        self._send_recording(output_path)

    def _on_review_send_clicked(self, button: Gtk.Button) -> None:
        """Send a recording from review mode."""
        self._send_recording(self._pending_output_path)

    def _discard_pending_review(self) -> None:
        """Discard the reviewed recording and return to idle."""
        output_path = self._pending_output_path
        self._pending_output_path = None
        self._stack.set_visible_child_name("idle")
        self._reset_ui()

        if output_path and output_path.exists():
            try:
                output_path.unlink()
            except OSError as e:
                logger.warning("Failed to delete discarded recording: %s", e)

        if self._on_recording_cancelled:
            self._on_recording_cancelled()

    def _on_review_cancel_clicked(self, button: Gtk.Button) -> None:
        """Discard a recording from review mode."""
        self._discard_pending_review()

    def _on_recorder_state_changed(self, state: RecorderState) -> None:
        """Handle recorder state changes."""

        def update():
            if state == RecorderState.IDLE and self._stack.get_visible_child_name() == "recording":
                self._stack.set_visible_child_name("idle")
                self._stop_duration_timer()
                self._reset_ui()
            return False

        GLib.idle_add(update)

    def _on_level_changed(self, level: float) -> None:
        """Handle audio level changes."""

        def update():
            self._level_bar.set_value(level)
            return False

        GLib.idle_add(update)

    def _on_recorder_error(self, error: str) -> None:
        """Handle recorder errors."""
        logger.error("Recording error: %s", error)

        def update():
            self._stack.set_visible_child_name("idle")
            self._stop_duration_timer()
            self._reset_ui()
            self._pending_output_path = None
            return False

        GLib.idle_add(update)

    def _start_duration_timer(self) -> None:
        """Start the duration update timer."""
        self._stop_duration_timer()
        self._duration_timer = GLib.timeout_add(100, self._update_duration)

    def _stop_duration_timer(self) -> None:
        """Stop the duration update timer."""
        if self._duration_timer:
            GLib.source_remove(self._duration_timer)
            self._duration_timer = None

    def _update_duration(self) -> bool:
        """Update the duration display."""
        if self._recorder.state != RecorderState.RECORDING:
            return False

        duration = self._recorder.get_duration()
        mins = int(duration) // 60
        secs = int(duration) % 60
        self._duration_label.set_label(f"{mins}:{secs:02d}")
        self._duration_label.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [f"Recording duration: {mins} minutes {secs} seconds"],
        )
        return True

    def _reset_ui(self) -> None:
        """Reset UI to initial state."""
        self._duration_label.set_label("0:00")
        self._review_label.set_label("Voice message ready")
        self._level_bar.set_value(0)

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recorder.state == RecorderState.RECORDING

    @property
    def is_in_review(self) -> bool:
        """Check if a finished recording is awaiting review."""
        return self._pending_output_path is not None and self._stack.get_visible_child_name() == "review"

    def focus_review_controls(self) -> None:
        """Focus the review controls when a recording is awaiting review."""
        if self.is_in_review:
            self._review_send_button.grab_focus()

    def cancel_recording(self) -> None:
        """Cancel any active recording."""
        if self.is_recording:
            self._cancel_recording()

    def toggle_recording_shortcut(self) -> bool:
        """Handle the Ctrl+Shift+R shortcut.

        Returns:
            True if the shortcut changed or focused the recorder state.
        """
        if self.is_in_review:
            self.focus_review_controls()
            return True

        if self.is_recording:
            if self._shortcut_sends_immediately:
                self._on_send_clicked(self._send_button)
            else:
                self._finalize_recording_for_review()
            return True

        return self._start_recording(focus_cancel=False)
