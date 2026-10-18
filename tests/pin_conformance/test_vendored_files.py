"""The vendored upstream tests stay byte-identical to sc2reader v1.9.0 (32a0b83).

Checked by their git blob ids, which GitHub's tree API lists for the tag. A reformat (for
example a stray ``ruff format`` over ``tests/``) fails here.
"""

import hashlib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
UPSTREAM_BLOBS = {
    "test_replays.py": "607bec6ce5b1144ac4fdf54e47a18fd3250a8e03",  # test_replays/test_replays.py at v1.9.0
    "test_s2gs.py": "75a1daa9d440399b855b71f591a4e7fef278cfa9",  # test_s2gs/test_all.py at v1.9.0
}


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


@pytest.mark.parametrize(("name", "blob"), sorted(UPSTREAM_BLOBS.items()))
def test_vendored_file_is_upstreams(name, blob):
    assert git_blob_id((HERE / name).read_bytes()) == blob
