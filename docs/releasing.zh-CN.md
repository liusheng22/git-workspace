# 发布流程

Git Workspace 在 PyPI 上的包名是 `git-workspace-tui`。安装后提供的命令是 `gws` 和 `g`。

## PyPI Trusted Publishing

PyPI 需要配置 Trusted Publisher，字段如下：

```text
Project name: git-workspace-tui
Owner: liusheng22
Repository name: git-workspace
Workflow name: publish.yml
Environment name: pypi
```

不要把 PyPI 密码或 API token 存到 GitHub secrets。当前发布工作流通过 PyPI Trusted Publishing 使用 GitHub OIDC 发布。

## 发布清单

1. 确认下一个版本号，例如 `0.1.1`。
2. 更新 `pyproject.toml` 里的 `version`。
3. 更新 `CHANGELOG.md`。
4. 如果安装、升级或发布流程有变化，同步更新文档。
5. 刷新 lockfile：

```bash
uv lock
```

6. 运行本地发布检查：

```bash
uv run ruff check .
uv run pytest
rm -rf dist
uv run python -m build
```

7. 确认构建产物 metadata：

```bash
python - <<'PY'
from pathlib import Path
from zipfile import ZipFile

for wheel in Path('dist').glob('*.whl'):
    print(wheel.name)
    with ZipFile(wheel) as zf:
        metadata_name = next(name for name in zf.namelist() if name.endswith('.dist-info/METADATA'))
        metadata = zf.read(metadata_name).decode()
        for line in metadata.splitlines():
            if line.startswith(('Name: ', 'Version: ')):
                print(line)
PY
```

8. 提交并推送 `main`：

```bash
git add pyproject.toml uv.lock CHANGELOG.md README.md README.zh-CN.md docs/
git commit -m "chore: release vX.Y.Z"
git push origin main
```

9. 等待 `main` 上的 `CI` workflow 通过。
10. 确认 `.github/workflows/publish.yml` 仍然会在发布前跑完整 CI 矩阵：Ubuntu、macOS，Python 3.11、3.12、3.13。`publish` job 必须保留 `needs: test`。
11. 创建并推送版本 tag：

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

12. 观察 tag 触发的 CI 和 Publish。只有 publish workflow 的所有矩阵任务都绿了，才允许上传 PyPI：

```bash
gh run list --repo liusheng22/git-workspace --limit 10
gh run watch <publish-run-id> --repo liusheng22/git-workspace --exit-status
```

13. 验证 PyPI：

```bash
python - <<'PY'
import json
import urllib.request

with urllib.request.urlopen('https://pypi.org/pypi/git-workspace-tui/json', timeout=10) as response:
    data = json.load(response)
print(data['info']['name'])
print(data['info']['version'])
print(data['info']['package_url'])
PY
```

14. 在干净工具环境验证安装：

```bash
uv tool install --force git-workspace-tui
gws --help
```

## 用户升级命令

使用 `uv` 安装的用户这样升级：

```bash
uv tool upgrade git-workspace-tui
```

使用 `pipx` 安装的用户这样升级：

```bash
pipx upgrade git-workspace-tui
```

## 失败处理

PyPI 版本不可覆盖。如果版本已经上传到 PyPI 但内容不对，修复代码后发布新版本，不要尝试覆盖同一个版本。

如果 tag workflow 在上传 PyPI 前失败，可以先修复 `main`，并且只在确认该版本没有发布到 PyPI 时删除本地和远端失败 tag，再从修复后的 commit 重新创建：

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```
