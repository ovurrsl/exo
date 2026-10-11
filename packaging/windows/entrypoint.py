"""Windows frozen entrypoint; multiprocessing must dispatch before importing Exo."""

import multiprocessing
import sys


def main() -> None:
    multiprocessing.freeze_support()
    if sys.argv[1:2] == ["-c"] and len(sys.argv) >= 3:
        code = sys.argv[2]
        sys.argv = ["-c", *sys.argv[3:]]
        namespace: dict[str, object] = {"__name__": "__main__"}
        exec(code, namespace, namespace)
        return
    if sys.argv[1:2] == ["--runtime-check"]:
        from check_mlx import main as check_main

        raise SystemExit(check_main(sys.argv[2:]))
    from exo.main import main as exo_main

    exo_main()


if __name__ == "__main__":
    main()
