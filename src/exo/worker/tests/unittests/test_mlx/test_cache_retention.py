from collections.abc import Iterator

import mlx.core as mx
import pytest
from mlx_lm.models.cache import ArraysCache, KVCache

import exo.worker.engines.mlx.cache as cache_module
from exo.worker.engines.mlx.cache import CacheSnapshot, KVPrefixCache, get_prefix_length
from exo.worker.engines.mlx.types import Model


@pytest.fixture(autouse=True)
def cpu_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def no_cuda(_group: mx.distributed.Group | None) -> bool:
        return False

    monkeypatch.setattr(cache_module, "discover_cuda_cache_group", no_cuda)
    monkeypatch.setattr(cache_module, "get_memory_used_percentage", lambda: 0.0)
    with mx.stream(mx.Device(mx.cpu)):
        yield


def test_long_context_keeps_only_latest_sixteen_snapshots() -> None:
    cache = KVPrefixCache(None)
    snapshots = [CacheSnapshot([None], 4096 * (i + 1)) for i in range(64)]
    cache.add_kv_cache(mx.arange(10), [KVCache()], ssm_snapshots=snapshots)
    assert cache._snapshots[0] == snapshots[-16:]  # pyright: ignore[reportPrivateUsage]


def test_repeated_extension_replaces_same_position_without_retaining_duplicates() -> (
    None
):
    cache = KVPrefixCache(None)
    snapshots = [CacheSnapshot([None], i + 1) for i in range(16)]
    cache.add_kv_cache(mx.arange(20), [KVCache()], ssm_snapshots=snapshots)
    for _ in range(50):
        latest = CacheSnapshot([None], 16)
        cache.update_kv_cache(0, mx.arange(20), [KVCache()], [latest], restore_pos=16)
        retained = cache._snapshots[0]  # pyright: ignore[reportPrivateUsage]
        assert retained is not None
        assert len(retained) == 16
        assert retained[-1] is latest


def test_dropped_hybrid_restore_point_uses_cold_prefill() -> None:
    cache = KVPrefixCache(None)
    snapshots = [CacheSnapshot([None], i + 1) for i in range(64)]
    cache.add_kv_cache(mx.arange(70), [ArraysCache(2)], ssm_snapshots=snapshots)
    model = Model()
    model.layers = []
    _, remaining, matched, exact = cache.get_kv_cache(model, mx.arange(10))
    assert remaining.tolist() == list(range(10))
    assert matched is None
    assert not exact


@pytest.mark.parametrize(
    ("prompt", "cached", "expected"),
    [
        ([], [1], 0),
        ([1], [], 0),
        ([1, 2], [1, 2], 2),
        ([1, 2], [9, 2], 0),
        ([1, 2], [1, 9], 1),
        ([1], [1, 2], 1),
    ],
)
def test_prefix_lookup_needs_no_mlx_comparison_graph(
    monkeypatch: pytest.MonkeyPatch, prompt: list[int], cached: list[int], expected: int
) -> None:
    def reject_gpu_comparison(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Prefix lookup must compare materialized token IDs on CPU")

    a = mx.array(prompt, dtype=mx.int32)
    b = mx.array(cached, dtype=mx.int32)
    monkeypatch.setattr(mx, "equal", reject_gpu_comparison)
    monkeypatch.setattr(mx, "cumprod", reject_gpu_comparison)
    assert get_prefix_length(a, b) == expected
