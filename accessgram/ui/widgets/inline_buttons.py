"""Inline button widget for bot messages.

Provides an accessible grid of inline buttons that bots
attach to messages for interactive actions.
"""

import logging
import webbrowser
from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk

from accessgram.utils.async_bridge import create_task_with_callback

logger = logging.getLogger(__name__)


class InlineButtonWidget(Gtk.Box):
    """Widget displaying inline buttons from a bot message.

    Renders Telegram inline keyboard buttons in an accessible grid layout.
    Supports callback buttons, URL buttons, and switch inline buttons.
    """

    def __init__(
        self,
        message: Any,
        client: Any,
        on_callback_result: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the inline button widget.

        Args:
            message: The Telethon message with inline buttons.
            client: The AccessGramClient for handling button clicks.
            on_callback_result: Optional callback for displaying callback results.
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.message = message
        self._client = client
        self._on_callback_result = on_callback_result
        self._buttons: list[Gtk.Button] = []

        self.add_css_class("inline-buttons")
        self.set_margin_top(8)

        self._build_ui()
        self._update_accessibility()

    def _build_ui(self) -> None:
        """Build the button grid UI."""
        # Get buttons from message
        # message.buttons returns List[List[MessageButton]] - rows of buttons
        buttons = self.message.buttons
        if not buttons:
            return

        # Make this container non-focusable so focus goes to children
        self.set_focusable(False)

        # Determine max columns from button rows
        max_cols = max(len(row) for row in buttons if row) if buttons else 1

        # Use FlowBox for proper keyboard navigation
        # FlowBox is designed for navigable collections of widgets
        self._flowbox = Gtk.FlowBox()
        self._flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flowbox.set_homogeneous(True)
        self._flowbox.set_min_children_per_line(max_cols)
        self._flowbox.set_max_children_per_line(max_cols)
        self._flowbox.set_row_spacing(4)
        self._flowbox.set_column_spacing(4)
        self._flowbox.set_focusable(True)  # FlowBox should be focusable
        self._flowbox.set_can_focus(True)

        # Flatten button rows and add to flowbox
        for row_buttons in buttons:
            if not row_buttons:
                continue

            for msg_button in row_buttons:
                button = self._create_button(msg_button)
                if button:
                    button.set_hexpand(True)
                    # FlowBox wraps children in FlowBoxChild automatically
                    self._flowbox.append(button)
                    self._buttons.append(button)

        if self._buttons:  # Only add flowbox if it has buttons
            self.append(self._flowbox)

    def _create_button(self, msg_button: Any) -> Gtk.Button | None:
        """Create a GTK button for a Telegram inline button.

        Args:
            msg_button: The Telethon MessageButton object.

        Returns:
            A GTK Button configured for the button type, or None if unsupported.
        """
        button = Gtk.Button()
        button.set_focusable(True)  # Ensure button can receive focus

        # Get button text
        text = msg_button.text or "Button"
        button.set_label(text)

        # Add CSS class for styling
        button.add_css_class("inline-button")

        # Determine button type and configure accordingly
        button_type = self._get_button_type(msg_button)

        if button_type == "url":
            # URL button - opens a link
            url = msg_button.url
            button.add_css_class("inline-button-url")

            # Add link icon to indicate it opens externally
            content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            content_box.set_halign(Gtk.Align.CENTER)

            label = Gtk.Label(label=text)
            content_box.append(label)

            link_icon = Gtk.Image.new_from_icon_name("external-link-symbolic")
            link_icon.set_pixel_size(12)
            content_box.append(link_icon)

            button.set_child(content_box)

            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{text}, opens link"],
            )
            button.connect("clicked", self._on_url_clicked, url, text)

        elif button_type == "callback":
            # Callback button - sends data to bot
            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{text}, button"],
            )
            button.connect("clicked", self._on_callback_clicked, msg_button, text)

        elif button_type == "switch_inline":
            # Switch inline button - starts inline query
            query = msg_button.query or ""
            button.add_css_class("inline-button-switch")
            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{text}, inline query"],
            )
            button.connect("clicked", self._on_switch_inline_clicked, query, text)

        elif button_type == "switch_inline_self":
            # Switch inline in current chat
            query = getattr(msg_button, "same_peer", False)
            button.add_css_class("inline-button-switch")
            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{text}, inline query in this chat"],
            )
            button.connect("clicked", self._on_switch_inline_self_clicked, msg_button, text)

        elif button_type == "game":
            # Game button
            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{text}, play game"],
            )
            button.connect("clicked", self._on_game_clicked, msg_button, text)

        elif button_type == "webview":
            # Web view button
            button.add_css_class("inline-button-url")
            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{text}, opens web app"],
            )
            button.connect("clicked", self._on_webview_clicked, msg_button, text)

        else:
            # Unknown or unsupported button type
            button.set_sensitive(False)
            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{text}, unsupported button type"],
            )
            logger.debug("Unsupported button type for: %s", text)

        return button

    def _get_button_type(self, msg_button: Any) -> str:
        """Determine the type of inline button.

        Args:
            msg_button: The Telethon MessageButton object.

        Returns:
            String identifying the button type.
        """
        # Check for URL button
        if hasattr(msg_button, "url") and msg_button.url:
            return "url"

        # Check for callback button (has data attribute)
        if hasattr(msg_button, "data") and msg_button.data is not None:
            return "callback"

        # Check for switch inline button
        if hasattr(msg_button, "query") and msg_button.query is not None:
            # Check if it's switch_inline_self (same_peer)
            if getattr(msg_button, "same_peer", False):
                return "switch_inline_self"
            return "switch_inline"

        # Check for game button
        if hasattr(msg_button, "game") and msg_button.game:
            return "game"

        # Check for web view/web app button
        if hasattr(msg_button, "web_view") and msg_button.web_view:
            return "webview"

        # Check the button attribute directly for type info
        button_obj = getattr(msg_button, "button", None)
        if button_obj:
            type_name = type(button_obj).__name__
            if "Url" in type_name:
                return "url"
            elif "Callback" in type_name:
                return "callback"
            elif "SwitchInline" in type_name:
                return "switch_inline"
            elif "Game" in type_name:
                return "game"
            elif "WebView" in type_name:
                return "webview"

        return "unknown"

    def _on_url_clicked(self, button: Gtk.Button, url: str, text: str) -> None:
        """Handle URL button click.

        Args:
            button: The clicked button.
            url: The URL to open.
            text: The button text for announcements.
        """
        logger.info("Opening URL: %s", url)
        try:
            webbrowser.open(url)
            self._announce(f"Opened link: {text}")
        except Exception as e:
            logger.exception("Failed to open URL: %s", e)
            self._announce(f"Failed to open link: {text}")

    def _on_callback_clicked(
        self, button: Gtk.Button, msg_button: Any, text: str
    ) -> None:
        """Handle callback button click.

        Args:
            button: The clicked button.
            msg_button: The Telethon MessageButton object.
            text: The button text for announcements.
        """
        # Disable button to prevent double-clicks
        button.set_sensitive(False)

        # Show loading state
        original_child = button.get_child()
        if original_child:
            button.set_child(None)

        spinner = Gtk.Spinner()
        spinner.start()
        loading_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        loading_box.set_halign(Gtk.Align.CENTER)
        loading_box.append(spinner)
        loading_box.append(Gtk.Label(label=text))
        button.set_child(loading_box)

        self._announce(f"Pressing {text}")

        # Execute the callback asynchronously
        create_task_with_callback(
            self._click_button(msg_button),
            lambda result: self._on_callback_done(button, text, result, original_child),
            lambda error: self._on_callback_error(button, text, error, original_child),
        )

    async def _click_button(self, msg_button: Any) -> Any:
        """Click an inline button and return the result.

        Args:
            msg_button: The Telethon MessageButton to click.

        Returns:
            The callback query result from Telegram.
        """
        return await msg_button.click()

    def _on_callback_done(
        self,
        button: Gtk.Button,
        text: str,
        result: Any,
        original_child: Gtk.Widget | None,
    ) -> None:
        """Handle callback button completion.

        Args:
            button: The button that was clicked.
            text: The button text.
            result: The callback result from Telegram.
            original_child: The original button child widget.
        """
        # Restore button state
        button.set_sensitive(True)
        if original_child:
            button.set_child(original_child)
        else:
            button.set_label(text)

        # Handle the result
        if result:
            # result is typically a BotCallbackAnswer with message or alert
            message = getattr(result, "message", None)
            alert = getattr(result, "alert", False)
            url = getattr(result, "url", None)

            if url:
                # Bot wants to open a URL
                try:
                    webbrowser.open(url)
                    self._announce(f"Opened link from {text}")
                except Exception as e:
                    logger.exception("Failed to open callback URL: %s", e)

            if message:
                # Bot sent a message/notification
                if alert:
                    # Show as alert/notification
                    self._announce(f"Alert: {message}")
                else:
                    # Show as toast/notification
                    self._announce(message)

                # Pass to parent if callback is set
                if self._on_callback_result:
                    self._on_callback_result(message)
            else:
                self._announce(f"Pressed {text}")

        logger.debug("Button callback result: %s", result)

    def _on_callback_error(
        self,
        button: Gtk.Button,
        text: str,
        error: Exception,
        original_child: Gtk.Widget | None,
    ) -> None:
        """Handle callback button error.

        Args:
            button: The button that was clicked.
            text: The button text.
            error: The error that occurred.
            original_child: The original button child widget.
        """
        # Restore button state
        button.set_sensitive(True)
        if original_child:
            button.set_child(original_child)
        else:
            button.set_label(text)

        logger.exception("Button callback error: %s", error)
        self._announce(f"Failed to press {text}")

    def _on_switch_inline_clicked(
        self, button: Gtk.Button, query: str, text: str
    ) -> None:
        """Handle switch inline button click.

        Args:
            button: The clicked button.
            query: The inline query to start with.
            text: The button text for announcements.
        """
        # This would typically switch to inline query mode
        # For now, just announce that it's not fully supported
        self._announce(f"Inline query: {query or text}. Feature not fully supported yet.")
        logger.info("Switch inline requested with query: %s", query)

    def _on_switch_inline_self_clicked(
        self, button: Gtk.Button, msg_button: Any, text: str
    ) -> None:
        """Handle switch inline in current chat button click.

        Args:
            button: The clicked button.
            msg_button: The Telethon MessageButton object.
            text: The button text for announcements.
        """
        self._announce(f"Inline query in this chat: {text}. Feature not fully supported yet.")
        logger.info("Switch inline self requested: %s", text)

    def _on_game_clicked(self, button: Gtk.Button, msg_button: Any, text: str) -> None:
        """Handle game button click.

        Args:
            button: The clicked button.
            msg_button: The Telethon MessageButton object.
            text: The button text for announcements.
        """
        # Games typically open in a web view
        self._announce(f"Game: {text}. Games are not fully supported yet.")
        logger.info("Game button clicked: %s", text)

    def _on_webview_clicked(
        self, button: Gtk.Button, msg_button: Any, text: str
    ) -> None:
        """Handle web view button click.

        Args:
            button: The clicked button.
            msg_button: The Telethon MessageButton object.
            text: The button text for announcements.
        """
        # Web views/mini apps need special handling
        url = getattr(msg_button, "url", None)
        if url:
            try:
                webbrowser.open(url)
                self._announce(f"Opened web app: {text}")
            except Exception as e:
                logger.exception("Failed to open web view: %s", e)
                self._announce(f"Failed to open web app: {text}")
        else:
            self._announce(f"Web app: {text}. Web apps are not fully supported yet.")
        logger.info("Web view button clicked: %s", text)

    def _announce(self, message: str) -> None:
        """Announce a message to screen readers.

        Args:
            message: The message to announce.
        """
        # Find the main window to use its announcer
        widget = self.get_root()
        if widget and hasattr(widget, "announce"):
            widget.announce(message, Gtk.AccessibleAnnouncementPriority.MEDIUM)
        else:
            logger.debug("Screen reader announcement: %s", message)

    def _update_accessibility(self) -> None:
        """Update accessible properties for the button container."""
        button_count = len(self._buttons)
        if button_count == 0:
            return

        if button_count == 1:
            label = "1 action button"
        else:
            label = f"{button_count} action buttons"

        self.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [label],
        )

    def update_buttons(self, message: Any) -> None:
        """Update buttons when message is edited.

        Args:
            message: The updated message with new buttons.
        """
        self.message = message

        # Remove all existing button rows
        child = self.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.remove(child)
            child = next_child

        self._buttons.clear()

        # Rebuild UI with new buttons
        self._build_ui()
        self._update_accessibility()
