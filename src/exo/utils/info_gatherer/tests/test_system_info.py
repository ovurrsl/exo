from exo.utils.info_gatherer.system_info import (
    _active_speeds_from_stats,  # pyright: ignore[reportPrivateUsage]
)


class _FakeStat:
    def __init__(self, speed: int) -> None:
        self.speed = speed


def test_active_speeds_from_stats_keeps_only_known_speeds() -> None:
    stats = {
        "en0": _FakeStat(speed=1000),
        # 0 is psutil's "couldn't determine this" sentinel - common for
        # Wi-Fi, especially on macOS - and should read as unknown, not 0.
        "en1": _FakeStat(speed=0),
        "lo0": _FakeStat(speed=0),
    }

    assert _active_speeds_from_stats(stats) == {"en0": 1000}


def test_active_speeds_from_stats_empty() -> None:
    assert _active_speeds_from_stats({}) == {}
