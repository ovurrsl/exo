import importlib.util

# Image generation needs mflux, which exo does not install on Windows.
collect_ignore_glob = [] if importlib.util.find_spec("mflux") else ["test_*.py"]
