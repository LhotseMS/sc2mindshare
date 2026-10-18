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


# Corpus sweep (CR-044 review): 341 of 343 corpus replays loaded; these 2 failed because their
# (listfile) is encrypted, which mpyq cannot read. They must load, with a warning instead.
ENCRYPTED_LISTFILE = ["1.1.3.16939/11.SC2Replay", "1.2.2.17811/4.SC2Replay"]


@pytest.mark.parametrize("relative", ENCRYPTED_LISTFILE)
def test_replays_with_an_encrypted_listfile_load_with_a_warning(relative):
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "test_replays" / relative
    if not path.exists():
        pytest.skip(f"corpus replay not in this checkout: {relative}")
    decoded = load(str(path))
    assert decoded.metadata.players == ()
    assert decoded.warnings == ("replay.gamemetadata.json unreadable: (listfile) is encrypted",)


def test_read_member_raises_a_typed_error_when_the_archive_cannot_tell():
    from types import SimpleNamespace

    from sc2mindshare.decoding.archive import MemberUnreadable

    class Archive:
        def read_file(self, name):
            if name == "(listfile)":
                raise NotImplementedError("Encryption is not supported yet.")

    with pytest.raises(MemberUnreadable, match="listfile"):
        read_member(SimpleNamespace(archive=Archive()), "replay.gamemetadata.json")
