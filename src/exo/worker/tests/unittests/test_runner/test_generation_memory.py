"""Generation telemetry must retain MLX byte counts without a GB/GiB conversion."""

from dataclasses import dataclass
from typing import cast

import mlx.core as mx
import pytest
from mlx_lm.tokenizer_utils import StreamingDetokenizer

from exo.shared.types.common import ModelId
from exo.shared.types.text_generation import TextGenerationTaskParams
from exo.worker.engines.mlx.generator.batch_generate import (
    _EngineTask,  # pyright: ignore[reportPrivateUsage]
)
from exo.worker.tests.unittests.test_runner.test_batch_cancellation import (
    FakeMlxBatchGenerator,
    FakeResponse,
    engine,
)


@dataclass
class CompletedResponse(FakeResponse):
    token: int = 1


class Detokenizer:
    last_segment = "ok"

    def add_token(self, token: int) -> None:
        pass

    def finalize(self) -> None:
        pass


@pytest.mark.parametrize("peak_bytes", [0, 1_000_000_000, 8_964_930_516])
def test_batch_completion_reports_exact_peak_bytes(
    monkeypatch: pytest.MonkeyPatch, peak_bytes: int
) -> None:
    backend = FakeMlxBatchGenerator(
        generating=[0],
        waiting=[],
        responses=[CompletedResponse(uid=0, finish_reason="length")],
    )
    generator = engine(backend)
    detokenizer = Detokenizer()
    task = _EngineTask(
        uid=0,
        task_params=TextGenerationTaskParams(model=ModelId("test/telemetry"), input=[]),
        all_prompt_tokens=mx.array([1, 2]),
        prefix_hit_length=0,
        matched_index=None,
        detokenizer=cast(StreamingDetokenizer, cast(object, detokenizer)),
    )
    monkeypatch.setattr(generator, "_active_tasks", {0: task})
    monkeypatch.setattr(mx, "get_peak_memory", lambda: peak_bytes)

    results = generator.step()

    assert len(results) == 1
    stats = results[0][1].stats
    assert stats is not None
    assert stats.peak_memory_usage.in_bytes == peak_bytes
