import sys
from unittest import mock

import pytest

from exo.utils.rlimits import install_windows_resource_shim, raise_nofile_limit


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX resource limits")
def test_raise_nofile_limit_raises_soft_limit_up_to_hard_limit():
    import resource

    with (
        mock.patch.object(resource, "getrlimit", return_value=(256, 4096)),
        mock.patch.object(resource, "setrlimit") as setrlimit,
    ):
        raise_nofile_limit(2048)
        raise_nofile_limit(65535)

    assert setrlimit.call_args_list == [
        mock.call(resource.RLIMIT_NOFILE, (2048, 4096)),
        mock.call(resource.RLIMIT_NOFILE, (4096, 4096)),
    ]


def test_raise_nofile_limit_does_not_touch_resource_on_windows():
    # A None entry makes `import resource` raise ImportError.
    with (
        mock.patch.dict(sys.modules, {"resource": None}),
        mock.patch.object(sys, "platform", "win32"),
    ):
        raise_nofile_limit(65535)


def test_windows_resource_shim_reports_the_ucrt_descriptor_cap():
    with mock.patch.dict(sys.modules), mock.patch.object(sys, "platform", "win32"):
        sys.modules.pop("resource", None)
        install_windows_resource_shim()

        import resource

        assert resource.getrlimit(resource.RLIMIT_NOFILE) == (8192, 8192)
        resource.setrlimit(resource.RLIMIT_NOFILE, (1, 1))
        assert resource.getrlimit(resource.RLIMIT_NOFILE) == (8192, 8192)


def test_resource_shim_is_only_installed_on_windows():
    for platform in ("darwin", "linux"):
        with (
            mock.patch.dict(sys.modules),
            mock.patch.object(sys, "platform", platform),
        ):
            sys.modules.pop("resource", None)
            install_windows_resource_shim()
            assert "resource" not in sys.modules
