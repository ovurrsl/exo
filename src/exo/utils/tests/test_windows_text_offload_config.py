import sys

import pytest

from exo.utils import windows_text_offload_config as config


def test_disabled_and_mac_policy_do_not_read_host_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_query() -> int:
        raise AssertionError("Disabled offload must not query host memory")

    monkeypatch.setattr(config, "_available_host_memory", reject_query)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("EXO_WINDOWS_TEXT_OFFLOAD", raising=False)
    assert not config.read_windows_text_offload_policy().enabled
    monkeypatch.setenv("EXO_WINDOWS_TEXT_OFFLOAD", "true")
    monkeypatch.setattr(sys, "platform", "darwin")
    assert not config.read_windows_text_offload_policy().enabled


def test_enabled_policy_uses_host_budget_without_changing_gpu_reserve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("EXO_WINDOWS_TEXT_OFFLOAD", "true")
    monkeypatch.setattr(config, "_available_host_memory", lambda: 28 * 1024**3)
    monkeypatch.setenv("EXO_WINDOWS_TEXT_OFFLOAD_HOST_LIMIT_BYTES", str(30 * 1024**3))
    policy = config.read_windows_text_offload_policy()
    assert policy.enabled
    assert policy.host_limit_bytes == 24 * 1024**3
    assert policy.host_reserve_bytes == 4 * 1024**3
    assert policy.gpu_reserve_bytes == 2560 * 1024**2
    assert policy.stage_limit_bytes == 1024**3


@pytest.mark.parametrize("value", ["0", "-1", "oops", "1.5"])
def test_invalid_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("EXO_WINDOWS_TEXT_OFFLOAD", "1")
    monkeypatch.setenv("EXO_WINDOWS_TEXT_OFFLOAD_STAGE_LIMIT_BYTES", value)
    monkeypatch.setattr(config, "_available_host_memory", lambda: 28 * 1024**3)
    with pytest.raises(ValueError, match="EXO_WINDOWS_TEXT_OFFLOAD_STAGE_LIMIT_BYTES"):
        config.read_windows_text_offload_policy()
