# AccessGram

An accessible Telegram client for Linux, designed to work well with screen readers like Orca.

## Features

- Full keyboard navigation and screen reader support
- Private chats, groups, and channels
- Send and receive text messages
- Multi-line message composer with `Enter` to send and `Shift+Enter` for a new line
- Voice message recording and playback
- Keyboard shortcut flow for voice messages with optional review-before-send behaviour
- File uploads and downloads
- Search for users, groups, and channels
- View user profiles with keyboard-focusable, selectable profile fields
- Mute/unmute chats
- Message reply support with context display
- Read receipts (sent/seen status)
- Configurable sound effects with bundled Telegram-style defaults
- Current-chat typing / recording / uploading announcements for screen reader users
- Load older messages on demand instead of being limited to the first loaded page

## Installation

### System Dependencies

**Gentoo:**
```bash
emerge -av gtk:4 pygobject gst-plugins-base gst-plugins-good gst-plugins-bad
```

**Debian/Ubuntu:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
```

**Fedora:**
```bash
sudo dnf install python3-gobject gtk4 gstreamer1-plugins-base \
    gstreamer1-plugins-good gstreamer1-plugins-bad-free
```

**Arch:**
```bash
sudo pacman -S python-gobject gtk4 gst-plugins-base gst-plugins-good gst-plugins-bad
```

### Install AccessGram

```bash
pip install -e .
```

## Setup

1. Get API credentials from https://my.telegram.org
2. Run `python -m accessgram`
3. Enter your API credentials on first run

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | Search |
| `Ctrl+F` | Filter chat list |
| `Ctrl+Q` | Quit |
| `Ctrl+Shift+R` | Start/stop voice recording in the current chat |
| `Page Up` | Load older messages in the current chat |
| `Escape` | Go back / cancel active voice recording |
| `Enter` | Send message / activate |
| `Shift+Enter` | Insert a new line in the message composer |
| `Tab` | Navigate between areas |
| `Arrow Keys` | Navigate within lists |

## Accessibility and Preferences Notes

- Typing activity announcements are limited to the currently open chat to avoid screen reader spam.
- Typing activity timeout can be adjusted in Preferences.
- Voice recording shortcut behaviour can be configured in Preferences:
  - stop and review before sending
  - stop and send immediately
- Sound effects can be previewed, customised per event, or reset back to the bundled defaults.
- Profile fields such as bio, phone number, and username are keyboard-focusable and selectable for easier review and copying.

## License

MIT
