"""Reject a changed browser archive before staging or running its contents."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bundle preparation")
def test_changed_webview_archive_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "changed.cab"
    archive.write_bytes(b"not the reviewed Microsoft browser runtime")
    powershell = shutil.which("pwsh")
    assert powershell is not None
    script = Path(__file__).resolve().parents[1] / "prepare-webview2.ps1"
    result = subprocess.run(
        [powershell, "-NoProfile", "-File", str(script), "-Archive", str(archive)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "WebView2 archive hash mismatch" in result.stderr
