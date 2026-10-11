import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import mlx.core as mx
import mlx.nn as nn
import pytest

from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.common import ModelId
from exo.shared.types.memory import Memory
from exo.shared.types.worker.shards import PipelineShardMetadata
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
    tmp_path: Path,
) -> None:
    (tmp_path / "config.json").write_text('{"model_type":"qwen3"}', encoding="utf-8")
    policy = WindowsTextOffloadPolicy(
        enabled=True, host_limit_bytes=100, stage_limit_bytes=50
    )
    model = nn.Module()
    calls: list[str] = []

    def load(
        path: Path, *, lazy: bool, strict: bool, model_config: dict[str, object]
    ) -> tuple[nn.Module, dict[str, object]]:
        assert path == tmp_path
        assert model_config == {"model_type": "qwen3", "model_file": None}
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
        result = utils_mlx.load_windows_offloaded_model(tmp_path, policy)
    assert result is model
    assert calls == ["cpu-load", "prepare"]


@pytest.mark.parametrize("model_file", ["custom.py", "../custom.py", None])
def test_offload_rejects_custom_model_before_execution(
    tmp_path: Path, model_file: str | None
) -> None:
    marker = tmp_path / "executed"
    (tmp_path / "custom.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "raise RuntimeError('custom model executed')\n",
        encoding="utf-8",
    )
    (tmp_path / "config.json").write_text(
        json.dumps({"model_type": "qwen3", "model_file": model_file}),
        encoding="utf-8",
    )
    with mx.stream(mx.Device(mx.cpu)):
        mx.save_safetensors(  # pyright: ignore[reportUnknownMemberType]
            str(tmp_path / "model.safetensors"), {"unused": mx.ones((1,))}
        )
    with pytest.raises(ValueError, match="built-in Qwen3"):
        utils_mlx.load_windows_offloaded_model(
            tmp_path, WindowsTextOffloadPolicy(enabled=True)
        )
    assert not marker.exists()


@pytest.mark.parametrize("config", [[], {"model_type": "qwen3_moe"}, {}])
def test_offload_rejects_non_qwen_config_before_loading(
    tmp_path: Path, config: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")

    def forbidden_load(*args: object, **kwargs: object) -> None:
        pytest.fail("unvalidated configuration reached model loader")

    monkeypatch.setattr(utils_mlx, "load_model", forbidden_load)
    with pytest.raises(ValueError, match="built-in Qwen3"):
        utils_mlx.load_windows_offloaded_model(
            tmp_path, WindowsTextOffloadPolicy(enabled=True)
        )


def test_offload_tokenizer_never_trusts_custom_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = cast(utils_mlx.TokenizerWrapper, object())

    def tokenizer(
        path: Path, *, tokenizer_config_extra: dict[str, bool]
    ) -> utils_mlx.TokenizerWrapper:
        assert path == tmp_path
        assert tokenizer_config_extra == {"trust_remote_code": False}
        return sentinel

    monkeypatch.setattr(utils_mlx, "load_tokenizer", tokenizer)
    assert utils_mlx.load_windows_offloaded_tokenizer(tmp_path) is sentinel


def test_offload_config_reread_cannot_enable_custom_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "executed"
    (tmp_path / "custom.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "raise RuntimeError('custom model executed')\n",
        encoding="utf-8",
    )
    (tmp_path / "config.json").write_text('{"model_type":"qwen3"}', encoding="utf-8")
    with mx.stream(mx.Device(mx.cpu)):
        mx.save_safetensors(  # pyright: ignore[reportUnknownMemberType]
            str(tmp_path / "model.safetensors"), {"unused": mx.ones((1,))}
        )
    original_load = utils_mlx.load_model

    def changed_config(
        path: Path, *, lazy: bool, strict: bool, model_config: dict[str, object]
    ) -> tuple[nn.Module, dict[str, object]]:
        (path / "config.json").write_text(
            '{"model_type":"custom","model_file":"custom.py"}', encoding="utf-8"
        )
        return original_load(path, lazy=lazy, strict=strict, model_config=model_config)

    monkeypatch.setattr(utils_mlx, "load_model", changed_config)
    # The built-in model rejects incomplete configuration, without importing
    # the custom module added after our initial validation.
    with pytest.raises(TypeError):
        utils_mlx.load_windows_offloaded_model(
            tmp_path, WindowsTextOffloadPolicy(enabled=True)
        )
    assert not marker.exists()


def test_offload_tokenizer_auto_map_cannot_execute_python(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    (tmp_path / "custom.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "raise RuntimeError('custom tokenizer executed')\n",
        encoding="utf-8",
    )
    (tmp_path / "config.json").write_text('{"model_type":"qwen3"}', encoding="utf-8")
    (tmp_path / "tokenizer_config.json").write_text(
        json.dumps(
            {
                "tokenizer_class": "CustomTokenizer",
                "auto_map": {"AutoTokenizer": ["custom.CustomTokenizer", None]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        utils_mlx.load_windows_offloaded_tokenizer(tmp_path)
    assert not marker.exists()


def test_offload_branch_bypasses_id_driven_custom_tokenizer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = ModelCard(
        model_id=ModelId("custom/kimi-k2-Qwen3-32B-4bit"),
        storage_size=Memory.from_gb(20),
        n_layers=1,
        hidden_size=64,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda],
        base_model="Qwen3 32B",
        quantization="4bit",
        trust_remote_code=True,
    )
    shard = PipelineShardMetadata(
        model_card=card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=1,
        n_layers=1,
    )
    bound = cast(
        utils_mlx.BoundInstance,
        cast(
            object,
            SimpleNamespace(
                bound_shard=shard,
                instance=SimpleNamespace(
                    shard_assignments=SimpleNamespace(node_to_runner={"one": "runner"})
                ),
            ),
        ),
    )
    model = cast(utils_mlx.Model, cast(object, nn.Module()))
    tokenizer = cast(utils_mlx.TokenizerWrapper, object())
    monkeypatch.setattr(utils_mlx.sys, "platform", "win32")

    def wired_limit(_: object) -> None:
        pass

    def weights_size(_: object) -> Memory:
        return Memory.from_gb(20)

    def model_path(_: object) -> Path:
        return tmp_path

    def loaded_model(*_: object) -> utils_mlx.Model:
        return model

    monkeypatch.setattr(utils_mlx, "set_wired_limit_for_model", wired_limit)
    monkeypatch.setattr(utils_mlx, "get_weights_size", weights_size)
    monkeypatch.setattr(utils_mlx, "build_model_path", model_path)
    monkeypatch.setattr(
        utils_mlx, "read_gpu_memory", lambda: SimpleNamespace(free=Memory.from_gb(1))
    )
    monkeypatch.setattr(
        utils_mlx,
        "read_windows_text_offload_policy",
        lambda: WindowsTextOffloadPolicy(enabled=True),
    )
    monkeypatch.setattr(utils_mlx, "load_windows_offloaded_model", loaded_model)
    calls: list[Path] = []

    def safe_tokenizer(path: Path) -> utils_mlx.TokenizerWrapper:
        calls.append(path)
        return tokenizer

    def forbidden_tokenizer(*args: object) -> None:
        pytest.fail("offload entered the model-ID custom Python dispatcher")

    monkeypatch.setattr(utils_mlx, "load_windows_offloaded_tokenizer", safe_tokenizer)
    monkeypatch.setattr(utils_mlx, "get_tokenizer", forbidden_tokenizer)
    loading = utils_mlx.load_mlx_items(bound, None)
    with pytest.raises(StopIteration) as stopped:
        while True:
            next(loading)
    assert cast(object, stopped.value.value) == (model, tokenizer, None)
    assert calls == [tmp_path]


@pytest.mark.parametrize("offloaded, expected_tokens", [(True, 2), (False, 50)])
def test_warmup_is_bounded_only_for_offloaded_model(
    monkeypatch: pytest.MonkeyPatch, offloaded: bool, expected_tokens: int
) -> None:
    model = (
        offload.WindowsQwen3OffloadModel.__new__(offload.WindowsQwen3OffloadModel)
        if offloaded
        else nn.Module()
    )
    requests: list[int | None] = []

    def generate(**kwargs: object) -> Iterator[generation.GenerationResponse]:
        params = cast(generation.TextGenerationTaskParams, kwargs["task"])
        requests.append(params.max_output_tokens)
        yield from []

    def template(**kwargs: object) -> str:
        return "warmup"

    monkeypatch.setattr(generation, "mlx_generate", generate)
    monkeypatch.setattr(generation, "apply_chat_template", template)
    generation.warmup_inference(
        cast(generation.Model, cast(object, model)),
        cast(utils_mlx.TokenizerWrapper, object()),
        None,
        ModelId("test/Qwen3"),
    )
    assert requests == [expected_tokens]
