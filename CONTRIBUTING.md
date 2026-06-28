# Contributing

Thanks for helping improve Git Workspace.

## Development Setup

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

## Pull Requests

- Keep behavior changes covered by tests.
- Preserve the shell-first execution model unless the change explicitly targets Git mode.
- Avoid adding dependencies unless they materially improve reliability or portability.
- Do not rely on a specific user's shell configuration in tests.

## TUI Changes

For TUI changes, add or update headless Textual tests where possible. Important interactions include input focus, repository switching, command cancellation, and mode switching.

