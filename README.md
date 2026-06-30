# Git Workspace

[中文文档](README.zh-CN.md)

Git Workspace (`gws`) is a Git-aware multi-repo terminal. It is built for one common developer setup: a single directory that contains many Git repositories.

![Why Git Workspace exists](docs/workspace-problem.svg)

## 60-Second Start

Install from PyPI:

```bash
uv tool install git-workspace-tui
```

Open the directory that contains your repos:

```bash
cd ~/Projects/workspace
gws
```

Inside the TUI, the first row is `ALL REPOS`. Type once there to run in every repo:

```text
ALL shell > git status -sb
```

Press `Tab` to move to one repo and run a focused command:

```text
api@main shell > pnpm test
```

## TUI Map

![TUI guide](docs/tui-preview.svg)

The TUI has only two concepts:

| Area | Meaning |
| --- | --- |
| Left panel | Choose the target: `ALL REPOS` or one repository. |
| Right panel | Continuous command log and one command input. |

Useful keys:

| Key | Action |
| --- | --- |
| `Tab` / `Shift+Tab` | Move through `ALL REPOS` and repository rows. |
| `Enter` | Run the input in the selected target. |
| `Up` / `Down` | Command history. |
| `Ctrl+C` | Cancel running command, or quit when idle. |
| `Ctrl+Q` | Quit. |
| `:git` / `:shell` | Switch execution mode. |
| `:clear` / `:refresh` | Clear log / refresh repos. |

Useful TUI commands:

| Command | Action |
| --- | --- |
| `:summary` | Reprint the latest batch result summary. |
| `:failed` | Show failed repos and make the next command target only those repos. |
| `:retry-failed` | Run the previous command again only in failed repos. |
| `:copy-failed` | Copy the failed-repo summary to the clipboard. |
| `:jump <repo>` | Select a repo and scroll back to its latest output. |
| `:all` | Return the target to `ALL REPOS`. |
| `:clear-summary` | Clear the latest batch summary and failed-repo target. |

## ALL REPOS vs One Repo

![Target model](docs/target-model.svg)

`ALL REPOS` is a real operating target, not a hidden mode.

```text
ALL shell > git status -sb
ALL shell > git pull --ff-only
ALL shell > git push
```

Repository rows are for focused work:

```text
api@main shell > pnpm test
api@main shell > git checkout dev
api@dev shell > git pull --ff-only
```

After an `ALL REPOS` command finishes, Git Workspace prints a summary so you can decide what to do next without reading the whole log:

```text
ALL shell > git pull --ff-only completed  ok:3  failed:2
repo                   status      time  note
api                    ok          1.2s  -
web                    failed      0.4s  local changes
server                 ok          2.8s  -
boss                   failed      1.1s  conflict
```

The summary is actionable:

```text
:failed        # show failures and make the next command run only there
git status -sb # runs only in failed repos after :failed
:retry-failed  # rerun the previous ALL command only in failed repos
:copy-failed   # copy a compact failure report
:jump web      # select web and scroll to its latest output
:all           # return to ALL REPOS
```

## Command Flow

![Command flow](docs/command-flow.svg)

Default mode is `shell`, so Git Workspace runs commands through your configured shell in the target repo directory.

```text
ALL shell > git status -sb
web@dev shell > npm run build
```

Use Git mode when you want shorter Git subcommands and Git aliases:

```text
:git
ALL git > status -sb
api@main git > gco dev
:shell
```

Inside the TUI, Git Workspace runs shell commands through a child shell that loads common rc files such as `.zshrc` or `.bashrc`. This keeps local aliases and functions available while keeping the loading scoped to the TUI child process, not your existing terminal tabs. If an rc file has errors, Git Workspace ignores the rc failure and continues running the command. Portable team shortcuts should still go in `workspace.yml` or Git's own `alias.*` config.

The TUI shows the shell rc status once, near the first shell command output:

```text
shell: zsh  rc: loaded (.zshenv, .zprofile, .zshrc)
```

If a startup file fails, the TUI keeps running and shows the ignored file:

```text
shell: zsh  rc: loaded (.zshenv)  failed (.zshrc) ignored
```

CLI commands such as `gws exec` do not load shell rc files by default. To force one behavior for a workspace, configure it explicitly:

```yaml
exec:
  shell:
    loadRc: true
```

Use `loadRc: false` if you want the TUI to run shell commands without reading shell startup files.

## CLI Safety Flow

![CLI safety flow](docs/cli-safety.svg)

The TUI `ALL REPOS` target is terminal-like: it runs the command you type in every repo.

For safer branch / pull workflows, use the plan-aware CLI commands:

```bash
gws status
gws plan daily
gws switch daily
gws pull daily
gws sync daily
```

Command meanings:

| Command | Purpose |
| --- | --- |
| `status` | Show branch, target, dirty state, upstream, ahead / behind. |
| `plan` | Explain actions before changing anything. |
| `switch` | Checkout target branches when safe. |
| `pull` | Pull clean repos already on target branch. |
| `sync` | Switch to target branches, then pull safe repos. |
| `exec` | Run a shell command across repos. |

Run any command across repos from the CLI:

```bash
gws exec -- pwd
gws exec -- git status -sb
gws exec daily -- pnpm test
```

## Configuration Model

![Configuration model](docs/config-model.svg)

Git Workspace works without a config by discovering Git repositories directly under the current directory. Add `workspace.yml` when you want shared defaults.

```yaml
workspace:
  root: .
  ignore:
    - node_modules
    - .cache
    - dist

repos:
  api:
    path: ./api
    default: main
  web:
    path: ./web
    default: dev

profiles:
  daily:
    api: main
    web: dev
    "*": main

aliases:
  gco: checkout
  gcb: checkout -b
  gl: pull
  gp: push

exec:
  defaultMode: shell
  gitShortcuts: true
  shell:
    loadRc: true
```

Use `workspace.local.yml` for machine-specific overrides. It should usually stay uncommitted.

## Install Options

The PyPI package name is `git-workspace-tui`. The installed commands are `gws` and `g`.

With `uv`:

```bash
uv tool install git-workspace-tui
```

With `pipx`:

```bash
pipx install git-workspace-tui
```

Upgrade an existing install:

```bash
uv tool upgrade git-workspace-tui
```

If you installed with `pipx`:

```bash
pipx upgrade git-workspace-tui
```

Install a specific PyPI version:

```bash
uv tool install 'git-workspace-tui==0.1.0'
```

Install a fixed version from GitHub:

```bash
uv tool install git+https://github.com/liusheng22/git-workspace.git@v0.1.0
```

From a local clone:

```bash
git clone https://github.com/liusheng22/git-workspace.git
cd git-workspace
uv sync --dev
uv run gws --help
```

`g` is also installed as a short alias for `gws`:

```bash
g
g status
g plan
```

## Safety Notes

- `ALL REPOS` runs your command in every repo. It intentionally behaves like a multi-repo terminal.
- `plan`, `pull`, and `sync` inspect branch and dirty state before changing repositories.
- Dirty worktrees are not auto-fixed.
- Unsafe branch switching is skipped.
- TUI shell commands load shell rc files inside a child process by default. Use `exec.shell.loadRc: false` if your rc files have side effects you do not want inside Git Workspace.

When in doubt:

```bash
gws status
gws plan
```

## Release Gate

PyPI publishing is guarded by the same matrix as CI: Ubuntu and macOS on Python 3.11, 3.12, and 3.13. The publish job runs only after every matrix job passes, then builds the package and publishes through PyPI Trusted Publishing.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run python -m build
```

## Release Process

Releases are published to PyPI by GitHub Actions when a version tag is pushed.

```bash
# after updating pyproject.toml, uv.lock, CHANGELOG.md, and docs
uv lock
uv run ruff check .
uv run pytest
uv run python -m build
git commit -am "chore: release vX.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The publish workflow uses PyPI Trusted Publishing with repository `liusheng22/git-workspace`, workflow `publish.yml`, and environment `pypi`. PyPI versions are immutable, so a failed or incorrect release must be fixed by publishing a new version.

See [docs/releasing.md](docs/releasing.md) for the full maintainer checklist.

Git Workspace currently targets macOS and Linux.
