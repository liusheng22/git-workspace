# Changelog

## 0.1.3

- Stabilizes the TUI all-repository cancellation test on Linux CI while keeping the 0.1.2 cancellation behavior.

## 0.1.2

- Adds a hard-kill fallback when canceling TUI commands so shell wrappers cannot leave the TUI stuck in a running state.
- Keeps the TUI shell rc loading behavior from 0.1.1.

## 0.1.1

- Loads shell rc files for TUI child shell commands by default, so local aliases and functions work inside the TUI.
- Keeps CLI `gws exec` shell execution rc-free by default unless `exec.shell.loadRc: true` is configured.
- Adds `exec.shell.loadRc: false` support to disable TUI rc loading per workspace.
- Removes hidden shell startup environment hooks from command execution.

## 0.1.0

- Initial Git-aware multi-repo terminal implementation.
- Adds `gws` and `g` command entry points.
- Adds shell-first TUI execution with optional Git shortcut mode.
- Adds workspace configuration, status, plan, switch, pull, sync, and exec commands.
