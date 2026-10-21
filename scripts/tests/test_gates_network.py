"""D55a (CR-007): the gates leave out the tests marked ``network`` unless ``scripts/gates --network`` is asked for.

The network tests (upstream's map and s2gs downloads from Battle.net, ``tests/pin_conformance/conftest.py``
NETWORK_TESTS) need a third-party service and fail offline; they run only on the opt-in, with Stefan's OK when
sc2reader changes. The probe folder below has one network-marked test and one plain test, so the count of tests
run says which mode ran; neither test touches the network.
"""

import os
import subprocess
from pathlib import Path

import pytest

GATES = Path(__file__).resolve().parents[1] / "gates"

PROBE = """import pytest


@pytest.mark.network
def test_marked_network():
    pass


def test_plain():
    pass
"""


def _gates(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    probe = tmp_path / "probe"
    probe.mkdir(exist_ok=True)
    (probe / "test_probe.py").write_text(PROBE, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run([str(GATES), *args, str(probe)], capture_output=True, text=True, env=env, timeout=600, check=False)


def test_the_gates_leave_out_the_network_tests_by_default(tmp_path):
    run = _gates(tmp_path)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "1 passed, 1 deselected" in run.stdout
    assert "network tests left out" in run.stdout


def test_gates_network_runs_them_too(tmp_path):
    run = _gates(tmp_path, "--network")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "2 passed" in run.stdout and "deselected" not in run.stdout
    assert "network tests included" in run.stdout


@pytest.mark.parametrize(
    "args",
    [
        ("--offline",),  # an option other than --network
        ("--network", "-k"),  # --network followed by another option: only paths may follow it
        ("src", "--x"),  # an option after a path
    ],
)
def test_any_other_option_is_a_usage_error(tmp_path, args):
    run = _gates(tmp_path, *args)
    assert run.returncode == 2, run.stdout + run.stderr
    assert "unknown option" in run.stderr
