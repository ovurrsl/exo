import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import mlx.core as mx
import mlx.nn as nn
import pytest

from exo.shared.types.common import ModelId
from exo.utils.windows_text_offload_config import WindowsTextOffloadPolicy
from exo.worker.engines.mlx import builder as builder_module
from exo.worker.engines.mlx import utils_mlx
from exo.worker.engines.mlx import windows_text_offload as offload
from exo.worker.engines.mlx.builder import MlxBuilder
from exo.worker.engines.mlx.generator import generate as generation
from exo.worker.engines.mlx.types import KVCacheType
from exo.worker.runner.llm_inference.batch_generator import SequentialGenerator


@pytest.mark.parametrize("partial_weights", [False, True])
def test_offload_loader_rejects_missing_weights(
    tmp_path: Path, partial_weights: bool
) -> None:
    config = {
        "model_type": "qwen3",
        "hidden_size": 64,
        "num_hidden_layers": 1,
        "intermediate_size": 128,
        "num_attention_heads": 4,
        "num_key_value_heads": 2,
        "rms_norm_eps": 1e-6,
        "vocab_size": 128,
        "max_position_embeddings": 128,
        "rope_theta": 10000.0,
        "head_dim": 16,
        "tie_word_embeddings": True,
    }
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    if partial_weights:
        with mx.stream(mx.Device(mx.cpu)):
            mx.save_safetensors(  # pyright: ignore[reportUnknownMemberType]
                str(tmp_path / "model.safetensors"),
                {
                    "model.norm.weight": mx.ones((64,)),
                },
            )
    with pytest.raises((ValueError, FileNotFoundError)):
        utils_mlx.load_windows_offloaded_model(
            tmp_path, WindowsTextOffloadPolicy(enabled=True)
        )


def test_offload_builder_disables_batching(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXO_NO_BATCH", raising=False)
    model = offload.WindowsQwen3OffloadModel.__new__(offload.WindowsQwen3OffloadModel)
    model["sentinel"] = True
    builder = MlxBuilder(
        ModelId("test/model"),
        cast(object, object()),  # type: ignore[arg-type]
        cast(object, object()),  # type: ignore[arg-type]
        inference_model=cast(utils_mlx.Model, cast(object, model)),
        tokenizer=cast(
            utils_mlx.TokenizerWrapper,
            cast(
                object,
                SimpleNamespace(
                    has_tool_calling=False,
                    tool_call_start=None,
                    tool_call_end=None,
                ),
            ),
        ),
    )
    selected: list[type] = []

    def sequential(**kwargs: object) -> SequentialGenerator:
        selected.append(SequentialGenerator)
        return cast(SequentialGenerator, object())

    monkeypatch.setattr(builder_module, "SequentialGenerator", sequential)
    builder.build()
    assert selected == [SequentialGenerator]


def test_offload_prefill_uses_staging_token_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = offload.WindowsQwen3OffloadModel.__new__(offload.WindowsQwen3OffloadModel)
    monkeypatch.setattr(
        model,
        "staging",
        SimpleNamespace(
            policy=WindowsTextOffloadPolicy(max_prefill_tokens=16),
        ),
        raising=False,
    )
    steps: list[int] = []

    def stream(**kwargs: object) -> Iterator[object]:
        steps.append(cast(int, kwargs["prefill_step_size"]))
        yield object()

    monkeypatch.setattr(generation, "stream_generate", stream)

    def noop(*args: object, **kwargs: object) -> None:
        pass

    def no_pipeline(_: object) -> bool:
        return False

    monkeypatch.setattr(generation, "set_pipeline_prefill", noop)
    monkeypatch.setattr(generation, "set_pipeline_queue_sends", noop)
    monkeypatch.setattr(generation, "_has_pipeline_communication_layer", no_pipeline)
    result = generation.prefill(
        cast(generation.Model, cast(object, model)),
        cast(utils_mlx.TokenizerWrapper, object()),
        lambda tokens: tokens,
        mx.array([1, 2, 3]),
        cast(KVCacheType, []),
        None,
        None,
        None,
    )
    assert result[1] == 3
    assert steps == [16]


def test_offload_loader_creates_lazy_cpu_weights_before_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = WindowsTextOffloadPolicy(
        enabled=True, host_limit_bytes=100, stage_limit_bytes=50
    )
    model = nn.Module()
    calls: list[str] = []

    def load(
        path: Path, *, lazy: bool, strict: bool
    ) -> tuple[nn.Module, dict[str, object]]:
        assert path == Path("test-model")
        assert lazy and strict
        assert mx.default_device() == mx.cpu
        calls.append("cpu-load")
        return model, {}

    def prepare(
        original: nn.Module,
        selected: WindowsTextOffloadPolicy,
        *,
        cpu_loaded: bool,
        world_size: int,
        vision: bool,
    ) -> offload.WindowsQwen3OffloadModel:
        assert original is model and selected is policy
        assert cpu_loaded and world_size == 1 and not vision
        calls.append("prepare")
        return cast(offload.WindowsQwen3OffloadModel, cast(object, model))

    monkeypatch.setattr(utils_mlx, "load_model", load)
    monkeypatch.setattr(offload, "prepare_windows_qwen3_offload", prepare)
    with mx.stream(mx.Device(mx.gpu)):
        result = utils_mlx.load_windows_offloaded_model(Path("test-model"), policy)
    assert result is model
    assert calls == ["cpu-load", "prepare"]
