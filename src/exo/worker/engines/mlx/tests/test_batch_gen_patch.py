"""Decoding with linear attention layers doesn't build up an ever-growing graph."""

import io
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast

import mlx.core as mx
import pytest
from mlx_lm.generate import GenerationBatch
from mlx_lm.models.cache import ArraysCache, CacheList

from exo.worker.engines.mlx.patches.opt_batch_gen import (
    _patched_step,  # pyright: ignore[reportPrivateUsage]
    set_needs_topk,
)

VOCAB = 32


@pytest.fixture(autouse=True)
def cpu_stream() -> Iterator[None]:
    with mx.stream(mx.Device(mx.cpu)):
        yield


class LinearAttentionModel:
    """Stands in for a model whose linear attention layers each move their cache on by the
    tokens they process, while only one of them is read to build the mask."""

    def __call__(
        self, inputs: mx.array, cache: list[ArraysCache | CacheList]
    ) -> mx.array:
        for layer_cache in cache:
            self._advance(layer_cache, inputs.shape[1])
        return mx.zeros((inputs.shape[0], inputs.shape[1], VOCAB))

    def _advance(self, cache: ArraysCache | CacheList, tokens: int) -> None:
        if isinstance(cache, ArraysCache):
            cache.advance(tokens)
        else:
            for inner in cache.caches:
                assert isinstance(inner, (ArraysCache, CacheList))
                self._advance(inner, tokens)


def greedy(logprobs: mx.array) -> mx.array:
    return mx.argmax(logprobs, axis=-1)


def graph_edges(array: mx.array) -> int:
    dot = io.StringIO()
    mx.export_to_dot(dot, array)  # pyright: ignore[reportUnknownMemberType]
    return dot.getvalue().count("->")


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("topk", [False, True])
def test_linear_attention_caches_do_not_grow_a_graph_while_decoding(
    nested: bool, topk: bool
) -> None:
    caches = [ArraysCache(2, left_padding=[0, 3]) for _ in range(4)]
    for layer_cache in caches:
        layer_cache.prepare(lengths=[5, 5])
    batch = SimpleNamespace(
        model=LinearAttentionModel(),
        prompt_cache=[CacheList(CacheList(*caches))] if nested else caches,
        logits_processors=None,
        samplers=None,
        fallback_sampler=greedy,
        uids=[0, 1],
        tokens=[[], []],
        _next_tokens=mx.array([1, 2]),
        _next_logprobs=mx.zeros((2, VOCAB)),
    )
    typed_batch = cast(GenerationBatch, cast(object, batch))
    set_needs_topk(typed_batch, topk)

    for _ in range(256):
        _patched_step(typed_batch)

    for layer_cache in caches:
        assert layer_cache.left_padding is not None
        assert layer_cache.lengths is not None
        # Each step's update was evaluated, so nothing chains back to earlier steps
        assert graph_edges(layer_cache.left_padding) == 0
        assert graph_edges(layer_cache.lengths) == 0
        assert layer_cache.left_padding.tolist() == [-256, -253]
        assert layer_cache.lengths.tolist() == [-251, -251]
