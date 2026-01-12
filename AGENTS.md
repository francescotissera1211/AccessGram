# Repository Guidelines

## Project Structure & Module Organization
- `accessgram/` is the main package.
  - `core/` wraps Telethon and handles auth, client operations, and media.
  - `ui/` contains GTK4 windows, dialogs, and widgets.
  - `audio/` handles GStreamer-based playback/recording.
  - `accessibility/` provides screen reader announcements and focus helpers.
  - `utils/` contains config, formatting, and async/GLib bridging.
- There is no dedicated `tests/` directory in this repository.

## Build, Test, and Development Commands
Activate the virtual environment before running tools:
```bash
source venv/bin/activate
```
Run the application:
```bash
python -m accessgram
```
Install in editable mode with dev extras:
```bash
pip install -e ".[dev]"
```
Quality checks:
```bash
black accessgram/
ruff check accessgram/
mypy accessgram/
```

## Coding Style & Naming Conventions
- Python codebase; use 4-space indentation.
- Format with `black` and lint with `ruff`.
- Type hints are expected; use `mypy` to validate.
- Naming follows standard Python conventions: `snake_case` for functions/variables, `PascalCase` for classes.

## Testing Guidelines
- No automated test framework is configured in the current repo.
- When adding tests, place them in a new `tests/` directory and use clear, descriptive names (e.g., `test_client_auth.py`).
- Document any manual test steps in the PR description.

## Commit & Pull Request Guidelines
- Commit history uses short, imperative, present-tense subjects (e.g., “Add …”, “Fix …”).
- Keep commits focused on a single change set.
- PRs should include:
  - A brief summary of changes and rationale.
  - Manual verification steps (commands or UI flows).

## Configuration & Runtime Notes
- Config is stored at `~/.config/accessgram/config.json`.
- Telethon sessions and downloads live in `~/.local/share/accessgram/`.
- GTK accessibility announcements are routed through `accessgram/accessibility/announcer.py`.
