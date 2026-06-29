# Git Workspace

[English](README.md)

Git Workspace (`gws`) 是一个面向多 Git 仓库目录的终端工作台。它适合这种工作方式：一个目录下面放了很多 Git 项目，你经常要在这些仓库之间查看状态、pull、push、切分支、跑测试或构建。

![Git Workspace 解决的问题](docs/workspace-problem.zh-CN.svg)

## 60 秒上手

通过 PyPI 安装：

```bash
uv tool install git-workspace-tui
```

进入你的多仓库目录：

```bash
cd ~/Projects/workspace
gws
```

进入 TUI 后，第一行是 `ALL REPOS`。在这里输入命令，会依次在所有仓库里执行：

```text
ALL shell > git status -sb
```

按 `Tab` 移动到某个仓库行，就只在那个仓库里执行：

```text
api@main shell > pnpm test
```

## TUI 界面说明

![TUI 操作指引](docs/tui-preview.zh-CN.svg)

这个界面只有两个核心区域：

| 区域 | 含义 |
| --- | --- |
| 左侧 | 选择执行目标：`ALL REPOS` 或某一个仓库。 |
| 右侧 | 连续命令日志 + 一个输入框。 |

常用快捷键：

| 快捷键 | 作用 |
| --- | --- |
| `Tab` / `Shift+Tab` | 在 `ALL REPOS` 和仓库行之间移动。 |
| `Enter` | 在当前选中的目标里执行输入框命令。 |
| `Up` / `Down` | 命令历史。 |
| `Ctrl+C` | 有命令运行时取消命令；空闲时退出。 |
| `Ctrl+Q` | 退出。 |
| `:git` / `:shell` | 切换 Git 模式 / shell 模式。 |
| `:clear` / `:refresh` | 清空日志 / 刷新仓库状态。 |

## ALL REPOS 和单仓库

![执行目标模型](docs/target-model.zh-CN.svg)

`ALL REPOS` 是一个明确的执行目标，不是隐藏开关。

```text
ALL shell > git status -sb
ALL shell > git pull --ff-only
ALL shell > git push
```

仓库行用于单仓库操作：

```text
api@main shell > pnpm test
api@main shell > git checkout dev
api@dev shell > git pull --ff-only
```

## 命令是怎么执行的

![命令执行流](docs/command-flow.zh-CN.svg)

默认是 `shell` 模式，所以输入的命令会通过你的默认 shell，在目标仓库目录里执行。

```text
ALL shell > git status -sb
web@dev shell > npm run build
```

如果你想输入更短的 Git 子命令或 Git alias，可以切到 Git 模式：

```text
:git
ALL git > status -sb
api@main git > gco dev
:shell
```

在 TUI 里，Git Workspace 会通过一个子 shell 执行命令，并加载常见的 rc 文件，比如 `.zshrc` 或 `.bashrc`。这样本机 alias / function 可以继续使用，但加载范围限制在 TUI 的子进程里，不会去控制你已经打开的其它终端。如果 rc 文件有错误，Git Workspace 会忽略 rc 加载失败并继续执行命令。团队共享的快捷命令仍然建议放到 `workspace.yml` 或 Git 自己的 `alias.*` 配置里。

CLI 命令，比如 `gws exec`，默认不会加载 shell rc 文件。如果你想对某个工作区强制指定行为，可以显式配置：

```yaml
exec:
  shell:
    loadRc: true
```

如果你希望 TUI 执行命令时也不读取 shell 启动文件，可以配置 `loadRc: false`。

## CLI 安全工作流

![CLI 安全流](docs/cli-safety.zh-CN.svg)

TUI 里的 `ALL REPOS` 更像“多仓库终端”：你输入什么，就在每个仓库里执行什么。

如果要做更安全的分支 / pull 工作流，用 CLI 的 plan-aware 命令：

```bash
gws status
gws plan daily
gws switch daily
gws pull daily
gws sync daily
```

命令含义：

| 命令 | 用途 |
| --- | --- |
| `status` | 查看每个仓库的分支、目标分支、脏状态、upstream、ahead / behind。 |
| `plan` | 在修改仓库前先解释将要做什么。 |
| `switch` | 在安全时切到目标分支。 |
| `pull` | 只拉取已经在目标分支上的干净仓库。 |
| `sync` | 先切目标分支，再拉取安全仓库。 |
| `exec` | 跨仓库执行 shell 命令。 |

不进 TUI，也可以直接跨仓库执行命令：

```bash
gws exec -- pwd
gws exec -- git status -sb
gws exec daily -- pnpm test
```

## 配置模型

![配置模型](docs/config-model.zh-CN.svg)

没有配置文件时，Git Workspace 会自动发现当前目录下的直接子 Git 仓库。需要团队共享默认分支、profile、忽略规则和别名时，可以创建 `workspace.yml`。

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

`workspace.local.yml` 可以放本机私有覆盖配置，通常不应该提交到 Git。

## 安装方式

PyPI 包名是 `git-workspace-tui`。安装后提供的命令是 `gws` 和 `g`。

使用 `uv`：

```bash
uv tool install git-workspace-tui
```

使用 `pipx`：

```bash
pipx install git-workspace-tui
```

升级已有安装：

```bash
uv tool upgrade git-workspace-tui
```

如果你用 `pipx` 安装：

```bash
pipx upgrade git-workspace-tui
```

安装指定 PyPI 版本：

```bash
uv tool install 'git-workspace-tui==0.1.0'
```

从 GitHub 安装固定版本：

```bash
uv tool install git+https://github.com/liusheng22/git-workspace.git@v0.1.0
```

本地源码运行：

```bash
git clone https://github.com/liusheng22/git-workspace.git
cd git-workspace
uv sync --dev
uv run gws --help
```

`g` 也会作为 `gws` 的短命令一起安装：

```bash
g
g status
g plan
```

## 安全边界

- `ALL REPOS` 会在每个仓库里执行你的命令，它的语义接近“多仓库终端”。
- `plan`、`pull`、`sync` 会检查分支和脏工作区状态，更适合安全批量 Git 工作流。
- 脏工作区不会被自动修复。
- 不安全的切分支会被跳过。
- TUI 里的 shell 命令默认会在子进程里加载 shell rc 文件。如果你的 rc 文件有不希望在 Git Workspace 里触发的副作用，可以使用 `exec.shell.loadRc: false` 关闭。

不确定当前状态时，先运行：

```bash
gws status
gws plan
```

## 开发

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run python -m build
```

## 发布流程

版本发布由 GitHub Actions 处理：推送版本 tag 后自动发布到 PyPI。

```bash
# 更新 pyproject.toml、uv.lock、CHANGELOG.md 和文档后
uv lock
uv run ruff check .
uv run pytest
uv run python -m build
git commit -am "chore: release vX.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

发布工作流使用 PyPI Trusted Publishing，配置为仓库 `liusheng22/git-workspace`、workflow `publish.yml`、environment `pypi`。PyPI 版本不可覆盖；如果发错版本，只能修复后发布新版本。

完整维护者清单见 [docs/releasing.zh-CN.md](docs/releasing.zh-CN.md)。

当前主要支持 macOS 和 Linux。
