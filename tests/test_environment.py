"""CR-009: the new package runs on the pinned upstream sc2reader, never on the old fork (TD-8, TD-9)."""

import importlib.util
import sys
import sysconfig
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]


def test_sc2reader_is_the_pinned_upstream_release_from_site_packages():
    import sc2reader

    site_packages = Path(sysconfig.get_paths()["purelib"]).resolve()
    assert sc2reader.__version__ == "1.9.0"
    assert site_packages in Path(sc2reader.__file__).resolve().parents
    assert CHECKOUT / "legacy" not in Path(sc2reader.__file__).resolve().parents


def test_the_fork_tree_is_not_importable():
    assert not (CHECKOUT / "sc2reader").exists()  # moved to legacy/ by CR-009
    assert not any(Path(p).resolve() == (CHECKOUT / "legacy").resolve() for p in sys.path if p)
    assert importlib.util.find_spec("execs") is None  # the fork's entry scripts live in legacy/execs


def test_sc2mindshare_is_installed_from_this_checkouts_src():
    import sc2mindshare

    assert Path(sc2mindshare.__file__).resolve().parent == (CHECKOUT / "src" / "sc2mindshare").resolve()
    assert sc2mindshare.__version__ == "0.1.0"


def test_package_data_is_shipped():
    from importlib.resources import files

    config = files("sc2mindshare") / "config"
    assert {p.name for p in config.iterdir() if p.name.endswith(".json")} == {
        "visuals.json",
        "details.json",
        "data_types.json",
    }


def test_interpreter_is_the_batch_interpreter():
    assert sys.version_info[:3] == (3, 14, 5)
