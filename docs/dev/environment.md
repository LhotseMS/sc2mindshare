# Development environment (sc2mindshare)

Everything stays inside the project root (the folder above this checkout that has a `.tools/` folder): no cache, temp file or config is written anywhere else.

- **Interpreter:** Homebrew Python 3.14.5 (`/opt/homebrew/bin/python3.14`). `scripts/py-env` stops if it changes.
- **One venv per checkout:** `.venv/` in the checkout (gitignored).
- **Every Python command goes through `scripts/py-env`**, which points pip, pytest, ruff, mypy, bytecode and `TMPDIR` at `<root>/.tools/` and sets pip's 14-day cutoff (`--uploaded-prior-to P14D`, also in `<root>/.tools/pip/pip.conf`).

```sh
scripts/py-env /opt/homebrew/bin/python3.14 -m venv .venv
scripts/py-env .venv/bin/python -m pip install -r requirements/dev.lock
scripts/py-env .venv/bin/python scripts/package_ages.py requirements/dev.lock
scripts/gates
```

- **Adding or updating a package:** add the direct name to `requirements/*.in`, install through `scripts/py-env` (the cutoff applies to the whole tree), `pip freeze --all --exclude pip` into the matching `.lock`, and paste the `scripts/package_ages.py` table into the task record. Any package under 14 days old stops the task.

## Legacy environment (until T24)

`scripts/legacy-env` (re)creates **this checkout's** `.venv-legacy/` from `requirements/legacy.lock` and puts this checkout's fork tree on its `sys.path` with a `.pth` file (one per checkout, so it never points at another checkout's tree). It is used only to run the old code for the legacy golden; never install the new package into it. Baseline counts: `docs/dev/baselines.md`.

Run the old parser offline on replays (pass 1: no heatmaps, no uploads, every network connection blocked):

```sh
scripts/py-env .venv-legacy/bin/python scripts/run_legacy.py --support "<root>/MS SC" --out <root>/.tools/tmp/legacy-run <replay> [<replay> ...]
```

Per replay it writes `events.csv`, `Intervals.csv`, `run.log` and `summary.json` under `--out/<replay stem>/`. The legacy code reads its data root from `MS_SC_ROOT` (default `C:/MS SC`) and refuses media uploads unless `MS_UPLOADS_ENABLED=1`.

## Gates

`scripts/gates [PATH ...]` (default `scripts`) runs ruff check and ruff format with the repository's `ruff.toml`, `mypy --strict` on the non-test Python files, and pytest. G3 covers the files a task adds or changes only; the fork's own findings are the frozen baseline.

## Notes

- `scripts/package_ages.py` dates a release by its **newest** uploaded file (a late wheel makes the release younger, never older).
- `scripts/py-env` sets `PYTHONDONTWRITEBYTECODE=1`: an edit and its revert in the same second can otherwise leave a stale `.pyc` that runs the old code (seen during a sabotage check).
