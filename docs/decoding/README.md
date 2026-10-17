# Decoding (stream 3)

What a replay holds beyond what sc2reader exposes today, and the tools that measure it. Plan: `stream3-plan.md` (orchestrator `.scratch/plan/streams/`); tasks CR-040 onward.

## Environment (CR-040)

One venv per checkout (TD-11). Until T09 creates the `decode-dev` extra, the pins live in `tools/decoding/requirements.lock` (TD-8).

```sh
scripts/py-env /opt/homebrew/bin/python3.14 -m venv .venv
scripts/py-env .venv/bin/python -m pip install -r tools/decoding/requirements.lock
scripts/py-env .venv/bin/python scripts/package_ages.py tools/decoding/requirements.lock
scripts/py-env .venv/bin/pytest -p no:cacheprovider --import-mode=importlib --rootdir=tests/decoding tests/decoding
```

- Run the venv's `pytest` entry point, never `python -m pytest` from the checkout root: until T09 the root holds the fork's `sc2reader/`, which would shadow the pinned 1.9.0. `tests/decoding/test_environment.py` fails if that happens.
- **s2protocol** (5.0.16.97563.0) is a reference and test oracle only, never a runtime dependency. Its `s2protocol.versions` package imports `imp`, which Python 3.12 removed, so `tools/decoding/s2p.py` loads the per-build protocol modules by path. s2protocol has no module for every build (none for 81433); `s2p.protocol_build_for` picks the newest module at or below the replay's build.
- The replays are read from `<root>/MS SC/` (or `MS_SC_ROOT`) and never committed (D7a). The two extra ZvP replays are data points, never a golden (D5a).
