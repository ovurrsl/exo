from collections.abc import Iterator

import mlx.core as mx
import pytest
from mlx_lm.models.cache import ArraysCache, KVCache

from exo.worker.engines.mlx import cache as cache_module
from exo.worker.engines.mlx.cache import CacheSnapshot, KVPrefixCache
from exo.worker.engines.mlx.vision import MediaRegion


@pytest.fixture(autouse=True)
def cpu_arrays(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(cache_module, "get_memory_used_percentage", lambda: 0.0)
    monkeypatch.setattr(
        cache_module, "_MAX_CUDA_PREFIX_CACHE_ENTRIES", 3, raising=False
    )
    with mx.stream(mx.Device(mx.cpu)):
        yield


def test_repeated_short_cuda_prompt_refreshes_one_entry() -> None:
    prefix = KVPrefixCache(None, cuda_group=True)
    for iteration in range(100):
        prefix.add_kv_cache(mx.arange(20), [], prefill_tps=float(iteration))
    assert len(prefix.caches) == 1
    assert prefix.prefill_tps == [99.0]
    assert prefix._last_used == [100]  # pyright: ignore[reportPrivateUsage]


def test_cuda_entry_bound_evicts_least_recently_used() -> None:
    prefix = KVPrefixCache(None, cuda_group=True)
    for token in (1, 2, 3, 1, 4, 5):
        prefix.add_kv_cache(mx.array([token, 9]), [])
    assert [tokens.tolist() for tokens in prefix.prompts] == [[1, 9], [4, 9], [5, 9]]
    assert len(prefix._identities) == 3  # pyright: ignore[reportPrivateUsage]
    assert len(prefix._snapshots) == 3  # pyright: ignore[reportPrivateUsage]
    assert len(prefix._media_regions) == 3  # pyright: ignore[reportPrivateUsage]
    assert len(prefix._last_used) == 3  # pyright: ignore[reportPrivateUsage]
    assert len(prefix.prefill_tps) == 3


def test_cuda_identity_includes_last_token_and_media_content() -> None:
    prefix = KVPrefixCache(None, cuda_group=True)
    first = [MediaRegion("first-image", 1, 3)]
    second = [MediaRegion("second-image", 1, 3)]
    prefix.add_kv_cache(mx.array([1, 2, 3, 4]), [], media_regions=first)
    prefix.add_kv_cache(mx.array([1, 2, 3, 5]), [], media_regions=first)
    prefix.add_kv_cache(mx.array([1, 2, 3, 4]), [], media_regions=second)
    assert len(prefix.caches) == 3
    assert len(set(prefix._identities)) == 3  # pyright: ignore[reportPrivateUsage]


def test_cuda_refresh_keeps_hybrid_restore_points_within_new_cache() -> None:
    prefix = KVPrefixCache(None, cuda_group=True)
    kv = KVCache()
    kv.offset = 19
    snapshots = [
        CacheSnapshot([None, ArraysCache(2)], position) for position in (5, 10, 19)
    ]
    prefix.add_kv_cache(mx.arange(20), [kv, ArraysCache(2)], snapshots)
    replacement = KVCache()
    replacement.offset = 10
    latest = CacheSnapshot([None, ArraysCache(2)], 10)
    prefix.add_kv_cache(mx.arange(20), [replacement, ArraysCache(2)], [latest])
    assert len(prefix.caches) == 1
    assert prefix._snapshots[0] == [snapshots[0], latest]  # pyright: ignore[reportPrivateUsage]


def test_mac_only_retention_keeps_legacy_behavior() -> None:
    prefix = KVPrefixCache(None)
    for _ in range(5):
        prefix.add_kv_cache(mx.arange(20), [])
    assert len(prefix.caches) == 5
