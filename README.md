# sc2mindshare

StarCraft II replays to Mindshare graphs (JSON), without the Excel step. Work in progress (batch `cr-batch-2026-10`).

- `src/sc2mindshare/`: the new package, on the pinned upstream `sc2reader==1.9.0`.
- `legacy/`: the old sc2reader fork with Stefan's Mindshare layer, kept only to produce the legacy golden output until it is deleted (CR-025). Its upstream README is `legacy/README.rst`.
- `tests/`: the new suite, the goldens (`tests/golden/`), the VBA view reference port (`tests/reference/`) and upstream's v1.9.0 suite run against the pin (`tests/pin_conformance/`).
- `test_replays/`, `test_s2gs/`: upstream's replay corpus (data only).

Development: `docs/dev/environment.md`.

## Usage

One command builds the Mindshare JSON of a replay, with the battle intervals for the screenshot tool next to it:

```sh
sc2mindshare build "MS SC/Alcyone LE__lilTiGGer_vs_blacksquall/Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay" \
    --out out/graph.json --config-root "MS SC"
```

This writes `out/graph.json` (the Mindshare import document), `out/intervals.json` and `out/Intervals.csv` (the battle windows `execs/screenshotGame.py` reads), and `out/graph.log` (what the analysis printed while it ran). On Alcyone, `graph.json` is byte-identical to `tests/golden/alcyone/G-SNAP-1-compressed.json` (`--timeline linear`: `G-SNAP-1-linear.json`) and `Intervals.csv` to `Intervals-1.csv`. Exit codes: 0 built, 1 the analysis failed (traceback in the log), 2 a usage error. `--with-analysis` adds the analysis values stream 2 reads (unit lifecycles with the type at birth, type changes, upgrades, every PlayerStats sample, the supply history, Chrono Boosts, the game context and the time tables) as a top-level `analysis` object; it is not part of the Mindshare import format.

<!-- build --help -->
```text
usage: sc2mindshare build [-h] --out OUT [--timeline {compressed,linear}]
                          [--config-root CONFIG_ROOT] [--log LOG] [--with-analysis]
                          REPLAY

Build the Mindshare import document of REPLAY, and the battle intervals for the screenshot tool
(intervals.json and Intervals.csv, next to --out).

positional arguments:
  REPLAY                the .SC2Replay file

options:
  -h, --help            show this help message and exit
  --out OUT             the JSON file to write (graph.json)
  --timeline {compressed,linear}
                        compressed: empty 10 s windows take no space (default); linear: x is game
                        time
  --config-root CONFIG_ROOT
                        the folder with unitsInfo.csv, upgradesInfo.csv and TimeImageTracking.csv
                        (default: the MS_SC_ROOT environment variable)
  --log LOG             where the run log goes (default: <out>.log)
  --with-analysis       also write the analysis values stream 2 reads (supply, stats, unit
                        lifecycles...) as a top-level 'analysis' object (not part of the Mindshare
                        import format)
```
