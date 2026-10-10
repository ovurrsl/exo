"""RAM-offload requests own fresh KV state instead of retaining prefix snapshots."""

from collections.abc import Callable, Generator
from types import SimpleNamespace
from typing import cast

import mlx.core as mx
import pytest
from mlx_lm.models.cache import KVCache
from mlx_lm.tokenizer_utils import TokenizerWrapper

from exo.shared.types.common import ModelId
from exo.shared.types.tasks import TextGeneration
from exo.shared.types.text_generation import TextGenerationTaskParams
from exo.shared.types.worker.runner_response import GenerationResponse
from exo.worker.engines.mlx.cache import KVPrefixCache
from exo.worker.engines.mlx.generator import generate
from exo.worker.engines.mlx.types import KVCacheType, Model
from exo.worker.runner.llm_inference import batch_generator

_REAL_PREFILL = generate.prefill


class OffloadModel:
    layers: list[object] = [object()]
    staging = SimpleNamespace(policy=SimpleNamespace(max_prefill_tokens=16))

    def settle_request(self) -> None:
        pass


class PrefixSpy:
    def __init__(self, matched_index: int | None) -> None:
        self.matched_index = matched_index
        self.calls: list[str] = []

    def get_kv_cache(
        self, model: object, prompt: mx.array, **kwargs: object
    ) -> tuple[KVCacheType, mx.array, int | None, bool]:
        self.calls.append("get")
        remaining = prompt[-500:] if self.matched_index is not None else prompt
        return [KVCache()], remaining, self.matched_index, False

    def add_kv_cache(self, *args: object, **kwargs: object) -> None:
        self.calls.append("add")

    def update_kv_cache(self, *args: object, **kwargs: object) -> None:
        self.calls.append("update")


@pytest.fixture
def fake_generation(monkeypatch: pytest.MonkeyPatch) -> list[KVCacheType]:
    monkeypatch.setattr(generate, "WindowsQwen3OffloadModel", OffloadModel)
    monkeypatch.setattr(mx, "reset_peak_memory", lambda: None)
    monkeypatch.setattr(mx, "get_peak_memory", lambda: 0)

    def synchronized(stream: object = None) -> None:
        pass

    monkeypatch.setattr(mx, "synchronize", synchronized)

    def encoded(*args: object) -> mx.array:
        return mx.array(list(range(2000)))

    def unchanged(tokens: mx.array, tokenizer: object) -> mx.array:
        return tokens

    def zero(*args: object) -> int:
        return 0

    def barrier(*args: object) -> None:
        pass

    def prefilled(*args: object) -> tuple[float, int, list[object]]:
        return 1.0, 1999, []

    monkeypatch.setattr(generate, "encode_prompt", encoded)
    monkeypatch.setattr(generate, "fix_unmatched_think_end_tokens", unchanged)
    monkeypatch.setattr(generate, "system_prompt_token_count", zero)
    monkeypatch.setattr(generate, "mx_barrier", barrier)
    monkeypatch.setattr(generate, "prefill", prefilled)
    caches_seen: list[KVCacheType] = []

    def stream(**kwargs: object) -> Generator[SimpleNamespace]:
        caches_seen.append(list(cast(KVCacheType, kwargs["prompt_cache"])))
        yield SimpleNamespace(
            text="hello",
            token=1,
            finish_reason="stop",
            prompt_tps=1.0,
            generation_tps=1.0,
            prompt_tokens=1,
            generation_tokens=1,
        )

    monkeypatch.setattr(generate, "stream_generate", stream)
    return caches_seen


def run_request(model: object, prefix: PrefixSpy) -> None:
    result = list(
        generate.mlx_generate(
            model=cast(Model, model),
            tokenizer=cast(TokenizerWrapper, object()),
            task=TextGenerationTaskParams(
                model=ModelId("qwen3"), input=[], temperature=0.0
            ),
            prompt="prompt",
            kv_prefix_cache=cast(KVPrefixCache, cast(object, prefix)),
            group=None,
        )
    )
    assert result[-1].finish_reason == "stop"


@pytest.mark.parametrize("matched_index", [None, 0])
def test_offload_bypasses_all_prefix_operations_and_owns_fresh_dense_cache(
    fake_generation: list[KVCacheType], matched_index: int | None
) -> None:
    prefix = PrefixSpy(matched_index)
    model = OffloadModel()
    with mx.stream(mx.Device(mx.cpu)):
        run_request(model, prefix)
        run_request(model, prefix)
    assert prefix.calls == []
    first, second = fake_generation
    assert first is not second
    assert first[0] is not second[0]
    assert type(first[0]) is KVCache
    assert type(second[0]) is KVCache


@pytest.mark.parametrize(
    "matched_index,expected", [(None, ["get", "add"]), (0, ["get", "update"])]
)
def test_ordinary_generation_keeps_prefix_reuse(
    fake_generation: list[KVCacheType], matched_index: int | None, expected: list[str]
) -> None:
    prefix = PrefixSpy(matched_index)
    with mx.stream(mx.Device(mx.cpu)):
        run_request(SimpleNamespace(layers=[object()]), prefix)
    assert prefix.calls == expected
    assert len(fake_generation) == 1


@pytest.mark.parametrize(
    "termination", ["close", "cancel", "prefill_cancel", "complete", "error"]
)
def test_offload_closes_decode_then_settles_before_cache_release(
    fake_generation: list[KVCacheType],
    monkeypatch: pytest.MonkeyPatch,
    termination: str,
) -> None:
    events: list[str] = []
    held: list[KVCacheType] = []
    exo_stream = object()
    mlx_stream = object()
    monkeypatch.setattr(generate, "generation_stream", exo_stream)
    monkeypatch.setattr(generate, "mlx_generation_stream", mlx_stream, raising=False)

    def synchronized(stream: object) -> None:
        assert held and held[0]
        assert stream is exo_stream or stream is mlx_stream
        events.append("exo_sync" if stream is exo_stream else "mlx_sync")

    monkeypatch.setattr(mx, "synchronize", synchronized)

    class SettlingModel(OffloadModel):
        def settle_request(self) -> None:
            assert held and held[0]
            events.append("settle")

    def prefill(*args: object) -> tuple[float, int, list[object]]:
        held.append(cast(KVCacheType, args[4]))
        if termination == "prefill_cancel":
            raise generate.PrefillCancelled()
        return 1.0, 1999, []

    def stream(**kwargs: object) -> Generator[SimpleNamespace]:
        try:
            if termination == "error":
                raise RuntimeError("decode failed")
            yield SimpleNamespace(
                text="hello",
                token=1,
                finish_reason="stop" if termination == "complete" else None,
                prompt_tps=1.0,
                generation_tps=1.0,
                prompt_tokens=1,
                generation_tokens=1,
            )
        finally:
            assert held[0]
            events.append("close")

    def cancelled() -> None:
        raise generate.PrefillCancelled()

    monkeypatch.setattr(generate, "prefill", prefill)
    monkeypatch.setattr(generate, "stream_generate", stream)
    request = generate.mlx_generate(
        model=cast(Model, cast(object, SettlingModel())),
        tokenizer=cast(TokenizerWrapper, object()),
        task=TextGenerationTaskParams(
            model=ModelId("qwen3"), input=[], temperature=0.0
        ),
        prompt="prompt",
        kv_prefix_cache=cast(KVPrefixCache, cast(object, PrefixSpy(None))),
        group=None,
        on_generation_token=cancelled if termination == "cancel" else None,
    )
    with mx.stream(mx.Device(mx.cpu)):
        if termination in ("cancel", "prefill_cancel"):
            with pytest.raises(generate.PrefillCancelled):
                next(request)
        elif termination == "error":
            with pytest.raises(RuntimeError, match="decode failed"):
                next(request)
        elif termination == "close":
            next(request)
            request.close()
        else:
            next(request)
            assert events == ["close", "exo_sync", "mlx_sync", "settle"]
            assert held[0] == []
            assert list(request) == []
    assert events == (
        ["exo_sync", "mlx_sync", "settle"]
        if termination == "prefill_cancel"
        else ["close", "exo_sync", "mlx_sync", "settle"]
    )
    assert held[0] == []


@pytest.mark.parametrize("offload", [False, True])
def test_sequential_close_closes_only_active_offload_request(
    monkeypatch: pytest.MonkeyPatch, offload: bool
) -> None:
    monkeypatch.setattr(batch_generator, "WindowsQwen3OffloadModel", OffloadModel)
    engine = object.__new__(batch_generator.SequentialGenerator)
    engine.model = cast(Model, OffloadModel() if offload else object())
    engine.tokenizer = cast(TokenizerWrapper, object())
    engine.group = None
    closed: list[bool] = []

    def request() -> Generator[GenerationResponse]:
        try:
            yield GenerationResponse(text="hello", token=1, usage=None)
        finally:
            closed.append(hasattr(engine, "model"))

    active = request()
    next(active)
    engine._active = (  # pyright: ignore[reportPrivateUsage]
        cast(TextGeneration, object()),
        active,
        batch_generator.GeneratorQueue(),
        iter([]),
    )
    engine.close()
    assert closed == ([True] if offload else [])
    if offload:
        assert engine._active is None  # pyright: ignore[reportPrivateUsage]
    active.close()


@pytest.mark.parametrize("cancel", [False, True])
def test_offload_prefill_explicitly_closes_its_stream(
    fake_generation: list[KVCacheType], monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    events: list[str] = []

    def no_pipeline(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(generate, "set_pipeline_prefill", no_pipeline)
    monkeypatch.setattr(generate, "set_pipeline_queue_sends", no_pipeline)

    def stream(**kwargs: object) -> Generator[SimpleNamespace]:
        try:
            cast(Callable[[int, int], None], kwargs["prompt_progress_callback"])(1, 2)
            yield SimpleNamespace()
        finally:
            events.append("close")

    def progress(processed: int, total: int) -> None:
        if cancel:
            raise generate.PrefillCancelled()

    monkeypatch.setattr(generate, "stream_generate", stream)
    # Use the real prefill implementation, rather than the request fixture stub.
    original_prefill = _REAL_PREFILL
    cache = KVCache()
    cache.offset = 2
    with mx.stream(mx.Device(mx.cpu)):
        if cancel:
            with pytest.raises(generate.PrefillCancelled):
                original_prefill(
                    cast(Model, cast(object, OffloadModel())),
                    cast(TokenizerWrapper, object()),
                    lambda x: x,
                    mx.array([1, 2]),
                    [cache],
                    None,
                    progress,
                    None,
                )
        else:
            original_prefill(
                cast(Model, cast(object, OffloadModel())),
                cast(TokenizerWrapper, object()),
                lambda x: x,
                mx.array([1, 2]),
                [cache],
                None,
                progress,
                None,
            )
    assert events == ["close"]


def test_ordinary_prefill_closes_iterator_before_cache_trim(
    fake_generation: list[KVCacheType], monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    def no_pipeline(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(generate, "set_pipeline_prefill", no_pipeline)
    monkeypatch.setattr(generate, "set_pipeline_queue_sends", no_pipeline)

    def stream(**kwargs: object) -> Generator[SimpleNamespace]:
        try:
            yield SimpleNamespace()
        finally:
            events.append("close")

    class OrderedCache(KVCache):
        def trim(self, n: int) -> int:
            assert events == ["close"]
            events.append("trim")
            return super().trim(n)

    monkeypatch.setattr(generate, "stream_generate", stream)
    cache = OrderedCache()
    cache.offset = 2
    with mx.stream(mx.Device(mx.cpu)):
        _REAL_PREFILL(
            cast(Model, cast(object, SimpleNamespace(layers=[object()]))),
            cast(TokenizerWrapper, object()),
            lambda x: x,
            mx.array([1, 2]),
            [cache],
            None,
            None,
            None,
        )
    assert events == ["close", "trim"]
