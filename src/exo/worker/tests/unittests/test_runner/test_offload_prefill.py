from typing import cast
from unittest.mock import Mock

import pytest
from mlx_lm.tokenizer_utils import TokenizerWrapper

from exo.shared.types.common import ModelId
from exo.worker.engines.mlx.types import Model
from exo.worker.engines.mlx.windows_text_offload import WindowsQwen3OffloadModel
from exo.worker.runner import runner as runner_module
from exo.worker.runner.llm_inference import batch_generator
from exo.worker.runner.llm_inference.batch_generator import SequentialGenerator


@pytest.mark.parametrize("offloaded", [True, False])
def test_only_normal_engine_advertises_prefill_server(
    monkeypatch: pytest.MonkeyPatch, offloaded: bool
) -> None:
    engine = object.__new__(SequentialGenerator)
    model = (
        WindowsQwen3OffloadModel.__new__(WindowsQwen3OffloadModel)
        if offloaded
        else object()
    )
    engine.model = cast(Model, model)
    runner = object.__new__(runner_module.Runner)
    runner.generator = engine
    runner.device_rank = 0
    runner._prefill_server = None  # pyright: ignore[reportPrivateUsage]
    runner._prefill_server_port = None  # pyright: ignore[reportPrivateUsage]
    server_factory = Mock()
    monkeypatch.setattr(runner_module, "ENABLE_DISAGGREGATION", True)
    monkeypatch.setattr(runner_module, "random_ephemeral_port", lambda: 54321)
    monkeypatch.setattr(runner_module, "PrefillServer", server_factory)
    port = runner._start_prefill_server()  # pyright: ignore[reportPrivateUsage]
    if offloaded:
        assert port is None
        server_factory.assert_not_called()
    else:
        assert port == 54321
        server_factory.assert_called_once()


@pytest.mark.parametrize("offloaded", [True, False])
def test_offload_checks_cancellation_every_token_after_warmup(
    monkeypatch: pytest.MonkeyPatch, offloaded: bool
) -> None:
    engine = object.__new__(SequentialGenerator)
    engine.model = cast(
        Model,
        WindowsQwen3OffloadModel.__new__(WindowsQwen3OffloadModel)
        if offloaded
        else object(),
    )
    engine.tokenizer = cast(TokenizerWrapper, Mock())
    engine.group = None
    engine.model_id = ModelId("tiny")
    warmup = Mock(return_value=100)
    monkeypatch.setattr(batch_generator, "warmup_inference", warmup)
    engine.warmup()
    warmup.assert_called_once()
    assert engine.check_for_cancel_every == (1 if offloaded else 100)
