from collections.abc import Callable
from typing import cast
from unittest import mock

import mlx.core as mx
import pytest

from exo.worker.engines.mlx import cache


class _TwoRanks:
    def size(self) -> int:
        return 2


def _group() -> mx.distributed.Group:
    return cast(mx.distributed.Group, cast(object, _TwoRanks()))


def _gather_peer(
    change: Callable[[list[int]], None],
) -> Callable[..., mx.array]:
    def gather(
        local: mx.array,
        *,
        group: mx.distributed.Group | None,
        stream: mx.Stream | mx.Device | None,
    ) -> mx.array:
        assert group is not None
        assert stream == mx.Device(mx.cpu)
        values = cast(list[int], local.tolist())
        peer = values.copy()
        change(peer)
        return mx.array(values + peer, dtype=mx.int32)

    return gather


def test_cpu_handshake_discovers_cuda_on_another_rank():
    def peer_cuda(values: list[int]) -> None:
        values[0] = 1

    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "is_cuda_device", lambda: False),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(peer_cuda)),
    ):
        assert cache.discover_cuda_cache_group(_group())


def test_mac_only_group_keeps_legacy_eviction_behavior():
    def peer_metal(values: list[int]) -> None:
        values[0] = 0

    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "is_cuda_device", lambda: False),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(peer_metal)),
    ):
        assert not cache.discover_cuda_cache_group(_group())
    prefix = cache.KVPrefixCache(_group())
    with mock.patch.object(mx.distributed, "all_gather", side_effect=AssertionError):
        prefix._evict_if_needed()  # pyright: ignore[reportPrivateUsage]


def test_empty_rank_participates_and_rejects_nonempty_peer():
    def peer_nonempty(values: list[int]) -> None:
        values[0] = 1

    prefix = cache.KVPrefixCache(_group(), cuda_group=True)
    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 0.0),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(peer_nonempty)),
        pytest.raises(RuntimeError, match="diverged"),
    ):
        prefix._evict_if_needed()  # pyright: ignore[reportPrivateUsage]


def test_same_counts_with_different_prompt_identity_are_rejected():
    def peer_identity(values: list[int]) -> None:
        values[-1] ^= 1

    prefix = cache.KVPrefixCache(_group(), cuda_group=True)
    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 0.0),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(peer_identity)),
        pytest.raises(RuntimeError, match="diverged"),
    ):
        prefix._evict_if_needed()  # pyright: ignore[reportPrivateUsage]


def test_peer_pressure_evicts_the_same_entries_on_a_rank_with_room():
    def peer_pressure(values: list[int]) -> None:
        values[2] = int(values[0] > 0)

    prefix = cache.KVPrefixCache(_group(), cuda_group=True)
    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 0.0),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(peer_pressure)),
    ):
        prefix.add_kv_cache(mx.array([1, 2], dtype=mx.int32), [])
        prefix._evict_if_needed()  # pyright: ignore[reportPrivateUsage]
    assert prefix.caches == []
    assert prefix.prompts == []


def test_lru_divergence_is_detected_before_removing_different_entries():
    def same_peer(_values: list[int]) -> None:
        pass

    def peer_lru(values: list[int]) -> None:
        values[-2] ^= 1

    prefix = cache.KVPrefixCache(_group(), cuda_group=True)
    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 0.0),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(same_peer)),
    ):
        prefix.add_kv_cache(mx.array([1, 2], dtype=mx.int32), [])
    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 1.0),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(peer_lru)),
        pytest.raises(RuntimeError, match="diverged"),
    ):
        prefix._evict_if_needed()  # pyright: ignore[reportPrivateUsage]
    assert len(prefix.caches) == 1


def test_entry_limit_uses_joint_lru_order_without_memory_pressure(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(cache, "_MAX_CUDA_PREFIX_CACHE_ENTRIES", 2)
    prefixes = [cache.KVPrefixCache(_group(), cuda_group=True) for _ in range(2)]
    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 0.0),
        mock.patch.object(
            mx.distributed, "all_gather", _gather_peer(lambda _values: None)
        ),
    ):
        for prefix in prefixes:
            for token in (1, 2, 1, 3):
                prefix.add_kv_cache(mx.array([token, 9]), [])
    assert [tokens.tolist() for tokens in prefixes[0].prompts] == [[1, 9], [3, 9]]
    assert prefixes[0]._identities == prefixes[1]._identities  # pyright: ignore[reportPrivateUsage]
    assert prefixes[0]._last_used == prefixes[1]._last_used  # pyright: ignore[reportPrivateUsage]


def test_identity_divergence_rejects_refresh_before_mutation():
    prefix = cache.KVPrefixCache(_group(), cuda_group=True)
    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 0.0),
        mock.patch.object(
            mx.distributed, "all_gather", _gather_peer(lambda _values: None)
        ),
    ):
        prefix.add_kv_cache(mx.array([1, 2]), [], prefill_tps=10.0)

    def peer_identity(values: list[int]) -> None:
        values[-1] ^= 1

    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(cache, "get_memory_used_percentage", lambda: 0.0),
        mock.patch.object(mx.distributed, "all_gather", _gather_peer(peer_identity)),
        pytest.raises(RuntimeError, match="diverged"),
    ):
        prefix.add_kv_cache(mx.array([1, 2]), [], prefill_tps=20.0)
    assert prefix.prefill_tps == [10.0]
