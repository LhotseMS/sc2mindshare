# Development environment (sc2mindshare)

Everything stays inside the project root (the folder above this checkout that has a `.tools/` folder): no cache, temp file or config is written anywhere else.

- **Interpreter:** Homebrew Python 3.14.5 (`/opt/homebrew/bin/python3.14`). `scripts/py-env` stops if it changes.
- **One venv per checkout:** `.venv/` in the checkout (gitignored).
- **Every Python command goes through `scripts/py-env`**, which points pip, pytest, ruff, mypy, bytecode and `TMPDIR` at `<root>/.tools/` and sets pip's 14-day cutoff (`--uploaded-prior-to P14D`, also in `<root>/.tools/pip/pip.conf`).

```sh
scripts/py-env /opt/homebrew/bin/python3.14 -m venv .venv
scripts/py-env .venv/bin/python -m pip install -r requirements/dev.lock
scripts/py-env .venv/bin/python scripts/package_ages.py requirements/dev.lock
scripts/py-env .venv/bin/pytest -p no:cacheprovider --import-mode=importlib scripts/tests
```

- **Adding or updating a package:** add the direct name to `requirements/*.in`, install through `scripts/py-env` (the cutoff applies to the whole tree), `pip freeze --all --exclude pip` into the matching `.lock`, and paste the `scripts/package_ages.py` table into the task record. Any package under 14 days old stops the task.

## Legacy environment (until T24)

`scripts/legacy-env` (re)creates `<root>/.tools/venvs/legacy` from `requirements/legacy.lock` and puts this checkout's fork tree on its `sys.path` with a `.pth` file. It is used only to run the old code for the legacy golden; never install the new package into it. Baseline counts: `docs/dev/baselines.md`.
