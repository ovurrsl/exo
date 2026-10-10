from collections.abc import Generator
from typing import cast

import mlx.core as mx
import pytest
from mlx_lm.tokenizer_utils import TokenizerWrapper

from exo.shared.types.common import ModelId
from exo.shared.types.events import Event
from exo.shared.types.tasks import TaskId
from exo.shared.types.worker.instances import BoundInstance
from exo.shared.types.worker.runner_response import ModelLoadingResponse
from exo.utils.channels import MpReceiver, MpSender
from exo.worker.engines.mlx import builder as builder_module
from exo.worker.engines.mlx.builder import MlxBuilder
from exo.worker.engines.mlx.types import Model
from exo.worker.engines.mlx.vision import VisionProcessor


@pytest.mark.parametrize("local_cuda", [True, False])
def test_singleton_discovers_cuda_cache_policy_before_loading(
    monkeypatch: pytest.MonkeyPatch, local_cuda: bool
) -> None:
    builder = MlxBuilder(
        ModelId("test/model"),
        cast(MpSender[Event], object()),
        cast(MpReceiver[TaskId], object()),
    )
    discoveries: list[mx.distributed.Group | None] = []

    def discover(group: mx.distributed.Group | None) -> bool:
        discoveries.append(group)
        return local_cuda

    def load(
        _bound_instance: BoundInstance, group: mx.distributed.Group | None
    ) -> Generator[
        ModelLoadingResponse,
        None,
        tuple[Model, TokenizerWrapper, VisionProcessor | None],
    ]:
        assert group is None
        assert builder.cuda_cache_group is local_cuda
        yield from ()
        return Model(), cast(TokenizerWrapper, object()), None

    monkeypatch.setattr(builder_module, "discover_cuda_cache_group", discover)
    monkeypatch.setattr(builder_module, "load_mlx_items", load)
    assert list(builder.load(cast(BoundInstance, object()))) == []
    assert discoveries == [None]


def test_distributed_loading_keeps_connect_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = cast(mx.distributed.Group, object())
    builder = MlxBuilder(
        ModelId("test/model"),
        cast(MpSender[Event], object()),
        cast(MpReceiver[TaskId], object()),
        group=group,
        cuda_cache_group=False,
    )

    def reject_discovery(_group: mx.distributed.Group | None) -> bool:
        raise AssertionError("Distributed policy was already established by connect")

    def load(
        _bound_instance: BoundInstance, selected_group: mx.distributed.Group | None
    ) -> Generator[
        ModelLoadingResponse,
        None,
        tuple[Model, TokenizerWrapper, VisionProcessor | None],
    ]:
        assert selected_group is group
        yield from ()
        return Model(), cast(TokenizerWrapper, object()), None

    monkeypatch.setattr(builder_module, "discover_cuda_cache_group", reject_discovery)
    monkeypatch.setattr(builder_module, "load_mlx_items", load)
    assert list(builder.load(cast(BoundInstance, object()))) == []
    assert not builder.cuda_cache_group
