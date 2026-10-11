"""Measure the actual console window of a frozen child of a hidden parent."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="exo-console-probe-") as temporary:
        result = Path(temporary) / "child.json"
        child_code = (
            "import ctypes,json; from pathlib import Path; "
            "kernel=ctypes.WinDLL('kernel32',use_last_error=True); "
            "kernel.GetConsoleWindow.restype=ctypes.c_void_p; "
            "window=kernel.GetConsoleWindow(); "
            "user=ctypes.WinDLL('user32'); user.IsWindowVisible.argtypes=[ctypes.c_void_p]; "
            f"Path({str(result)!r}).write_text(json.dumps({{'window':window,"
            "'visible':bool(window and user.IsWindowVisible(window))}))"
        )
        parent_code = (
            "import multiprocessing as mp; "
            f"child=mp.get_context('spawn').Process(target=exec,args=({child_code!r},)); "
            "child.start(); child.join(15); "
            "assert not child.is_alive() and child.exitcode==0"
        )
        completed = subprocess.run(
            [str(args.runtime.resolve()), "-c", parent_code],
            creationflags=subprocess.CREATE_NO_WINDOW,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise SystemExit(completed.stderr or completed.stdout)
        evidence = json.loads(result.read_text())
        print(json.dumps(evidence))
        if evidence["visible"]:
            raise SystemExit("A frozen worker created a visible console")


if __name__ == "__main__":
    main()
