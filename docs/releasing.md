# Releasing

Git Workspace is published to PyPI as `git-workspace-tui`. The installed commands are `gws` and `g`.

## PyPI Trusted Publishing

PyPI should have a trusted publisher configured with these values:

```text
Project name: git-workspace-tui
Owner: liusheng22
Repository name: git-workspace
Workflow name: publish.yml
Environment name: pypi
```

Do not store PyPI passwords or API tokens in GitHub secrets. The publish workflow uses GitHub OIDC through PyPI Trusted Publishing.

## Release Checklist

1. Choose the next version, for example `0.1.1`.
2. Update `version` in `pyproject.toml`.
3. Update `CHANGELOG.md`.
4. Update documentation when install, upgrade, or workflow behavior changes.
5. Refresh the lockfile:

```bash
uv lock
```

6. Run the local release checks:

```bash
uv run ruff check .
uv run pytest
rm -rf dist
uv run python -m build
```

7. Confirm the built package metadata:

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

8. Commit and push `main`:

```bash
git add pyproject.toml uv.lock CHANGELOG.md README.md README.zh-CN.md docs/
git commit -m "chore: release vX.Y.Z"
git push origin main
```

9. Wait for the `CI` workflow on `main` to pass.
10. Create and push the version tag:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

11. Watch both workflows on the tag:

```bash
gh run list --repo liusheng22/git-workspace --limit 10
gh run watch <publish-run-id> --repo liusheng22/git-workspace --exit-status
```

12. Verify PyPI:

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

13. Verify install in a clean tool environment:

```bash
uv tool install --force git-workspace-tui
gws --help
```

## User Upgrade Commands

Users who installed with `uv` upgrade with:

```bash
uv tool upgrade git-workspace-tui
```

Users who installed with `pipx` upgrade with:

```bash
pipx upgrade git-workspace-tui
```

## Failure Handling

PyPI versions are immutable. If a release reaches PyPI with the wrong content, fix the repository and publish a new version. Do not try to overwrite the same version.

If the tag workflow fails before upload, fix the problem on `main`, delete the local and remote failed tag only when the tag did not publish to PyPI, then create it again from the fixed commit:

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```
