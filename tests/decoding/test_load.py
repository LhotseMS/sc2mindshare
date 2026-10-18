"""CR-042 (T3-2), first half: the decoding package skeleton and archive access.

The reader-registration hook is the second half; it waits for T10's reader/extensions.py (TD-2).
"""

import pytest
from sc2mindshare.decoding import DecodedReplay, load
from sc2mindshare.decoding.archive import read_member


def test_load_returns_a_decoded_replay_on_the_pinned_sc2reader(any_replay):
    decoded = load(any_replay)
    assert isinstance(decoded, DecodedReplay)
    from sc2reader.resources import Replay

    assert isinstance(decoded.replay, Replay)  # a Replay subclass that registers the stream 3 readers
    assert decoded.replay.frames > 0


def test_read_member_returns_raw_bytes(alcyone):
    decoded = load(alcyone)
    assert len(read_member(decoded.replay, "replay.smartcam.events")) == 11463
    assert read_member(decoded.replay, "replay.sync.history") == b""


def test_read_member_returns_none_for_an_absent_member(alcyone):
    decoded = load(alcyone)
    assert read_member(decoded.replay, "replay.no.such.member") is None


def test_decoded_replay_is_immutable(alcyone):
    decoded = load(alcyone)
    with pytest.raises(AttributeError):
        decoded.warnings = ("x",)  # type: ignore[misc]
