"""CR-040 (T3-0): the stream 3 environment.

Guards that the decoding tests run against the pinned upstream sc2reader, never the
fork tree at the repository root (TD-8, TD-9), and that s2protocol's schemas for our
replays' builds load on this interpreter.
"""

import sys
import sysconfig
from pathlib import Path

import pytest
from decoding_support import load_tool

s2p = load_tool("s2p")


def test_sc2reader_is_the_pinned_upstream_release_not_the_fork():
    import sc2reader

    site_packages = Path(sysconfig.get_paths()["purelib"]).resolve()
    assert sc2reader.__version__ == "1.9.0"
    assert site_packages in Path(sc2reader.__file__).resolve().parents


def test_interpreter_is_the_batch_interpreter():
    assert sys.version_info[:3] == (3, 14, 5)


def test_s2protocol_versions_package_cannot_be_imported_on_python_3_12_plus():
    """Recorded fact, not a wish: s2protocol's versions/__init__.py imports `imp` (removed in 3.12).

    If this starts passing, a newer s2protocol fixed it and s2p.load_protocol can be simplified.
    """
    with pytest.raises(ModuleNotFoundError, match="imp"):
        import s2protocol.versions


@pytest.mark.parametrize("build", [83830, 92440])
def test_protocol_modules_for_our_builds_load(build):
    proto = s2p.load_protocol(build)
    assert callable(proto.decode_replay_game_events)
    assert callable(proto.decode_replay_tracker_events)


def test_protocol_choice_falls_back_to_the_newest_module_at_or_below_the_build():
    assert s2p.protocol_build_for(92440) == 92440
    assert s2p.protocol_build_for(83830) == 83830
    assert s2p.protocol_build_for(81433) == 81009  # s2protocol ships no 81433 module
    with pytest.raises(LookupError):
        s2p.protocol_build_for(10)
