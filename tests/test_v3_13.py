"""v3.13: demo --gov CLI + version bumps."""
from __future__ import annotations

import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charter


def test_version_is_v3_13():
    assert charter.__version__.startswith("3.15")


def test_repair_and_rerun_exported():
    assert callable(charter.repair_and_rerun)


def test_remote_backend_exports():
    assert callable(charter.make_remote_backend)
    assert hasattr(charter, "HTTPKeyValueBackend")
    assert hasattr(charter, "SemanticCacheBackend")


def test_demo_gov_cli():
    out = subprocess.run(
        [sys.executable, "-m", "charter.cli", "demo", "--gov"],
        capture_output=True, text=True, timeout=120,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert out.returncode == 0, out.stderr
    assert "governance demo complete" in out.stdout
