import importlib.util

# CPU-only test environments may omit the optional image dependencies.
collect_ignore_glob = [] if importlib.util.find_spec("mflux") else ["test_*.py"]
