"""Check and preserve the baseline macOS MLX source metadata after uv lock.

Run only while producing this Windows branch's lock; the source commit is the
authority. uv can reuse Windows-generated version metadata for the Mac git
source when resolving on Windows, even when its immutable commit is unchanged.
"""

import pathlib
import subprocess
import tomllib

lock_path = pathlib.Path("uv.lock")
baseline = tomllib.loads(
    subprocess.check_output(["git", "show", "HEAD:uv.lock"], text=True)
)
current = tomllib.loads(lock_path.read_text(encoding="utf-8"))
source = next(
    package
    for package in baseline["package"]
    if package["name"] == "mlx" and "git" in package["source"]
)
resolved = next(
    package
    for package in current["package"]
    if package["name"] == "mlx" and "git" in package["source"]
)
if source["source"] != resolved["source"]:
    raise SystemExit("macOS MLX source changed; refusing to rewrite its lock")
old_version, new_version = source["version"], resolved["version"]
lines = lock_path.read_text(encoding="utf-8").splitlines(keepends=True)
for index, line in enumerate(lines):
    if source["source"]["git"] in line:
        if "version = " in line:
            lines[index] = line.replace(
                f'version = "{new_version}"', f'version = "{old_version}"'
            )
        elif index > 0:
            lines[index - 1] = lines[index - 1].replace(
                f'version = "{new_version}"', f'version = "{old_version}"'
            )
lock_path.write_text("".join(lines), encoding="utf-8", newline="\n")
print(f"macOS MLX commit and version preserved: {old_version}")
