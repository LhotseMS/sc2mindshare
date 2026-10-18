# sc2mindshare

StarCraft II replays to Mindshare graphs (JSON), without the Excel step. Work in progress (batch `cr-batch-2026-10`).

- `src/sc2mindshare/`: the new package, on the pinned upstream `sc2reader==1.9.0`.
- `legacy/`: the old sc2reader fork with Stefan's Mindshare layer, kept only to produce the legacy golden output until it is deleted (CR-025). Its upstream README is `legacy/README.rst`.
- `tests/`: the new suite, the goldens (`tests/golden/`), the VBA view reference port (`tests/reference/`) and upstream's v1.9.0 suite run against the pin (`tests/pin_conformance/`).
- `test_replays/`, `test_s2gs/`: upstream's replay corpus (data only).

Development: `docs/dev/environment.md`.
