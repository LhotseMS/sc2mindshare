"""The files moved verbatim from the legacy layer (analysis/LEGACY_PORT.txt) keep their ruff findings
for now, but the count may only fall (CR-011a; G3 as clarified, TD-46). Lower BASELINE when a
cleanup removes findings; never raise it.
"""

import subprocess
import sys
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
LIST = CHECKOUT / "src" / "sc2mindshare" / "analysis" / "LEGACY_PORT.txt"
BASELINE = 270  # at CR-011a (ruff 0.16.10, the repository's ruff.toml)


def ported_files():
    names = [line.strip() for line in LIST.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    return [CHECKOUT / n for n in names]


def test_every_listed_file_exists():
    assert all(p.is_file() for p in ported_files())


def test_ported_files_do_not_gain_ruff_findings():
    ruff = Path(sys.executable).parent / "ruff"
    result = subprocess.run(
        [
            str(ruff),
            "check",
            "--config",
            str(CHECKOUT / "ruff.toml"),
            "--output-format",
            "concise",
            "--quiet",
            *map(str, ported_files()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    findings = [line for line in result.stdout.splitlines() if line and ":" in line and not line.startswith("warning")]
    assert len(findings) <= BASELINE, f"{len(findings)} findings > baseline {BASELINE}"
