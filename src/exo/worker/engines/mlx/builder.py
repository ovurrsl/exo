import contextlib
import os
from collections.abc import Generator
from dataclasses import dataclass
from typing import cast

import mlx.core as mx
from mlx_lm.tokenizer_utils import TokenizerWrapper

from exo.shared.types.common import ModelId
from exo.shared.types.events import Event
from exo.shared.types.tasks import TaskId
from exo.shared.types.worker.instances import BoundInstance, MlxJacclInstance
from exo.shared.types.worker.runner_response import ModelLoadingResponse
from exo.utils.channels import MpReceiver, MpSender
from exo.worker.engines.base import Builder, Engine
from exo.worker.runner.bootstrap import logger
from exo.worker.runner.llm_inference.batch_generator import (
    BatchGenerator,
    SequentialGenerator,
)
from exo.worker.runner.llm_inference.tool_parsers import make_mlx_parser

from .cache import KVPrefixCache, discover_cuda_cache_group
from .snapshot_guard import verify_cuda_group_contract
from .types import Model
from .utils_mlx import (
    initialize_mlx,
    load_mlx_items,
)
from .vision import VisionProcessor
from .windows_text_offload import WindowsQwen3OffloadModel


@dataclass
class MlxBuilder(Builder):
    model_id: ModelId
    event_sender: MpSender[Event]
    cancel_receiver: MpReceiver[TaskId]
    inference_model: Model | None = None
    tokenizer: TokenizerWrapper | None = None
    group: mx.distributed.Group | None = None
    vision_processor: VisionProcessor | None = None
    cuda_cache_group: bool = False

    def connect(self, bound_instance: BoundInstance) -> None:
        self.group = initialize_mlx(bound_instance)
        self.cuda_cache_group = (
            False
            if isinstance(bound_instance.instance, MlxJacclInstance)
            else discover_cuda_cache_group(self.group)
        )

    def load(self, bound_instance: BoundInstance) -> Generator[ModelLoadingResponse]:
        if self.group is None:
            self.cuda_cache_group = discover_cuda_cache_group(None)
        if self.cuda_cache_group and self.group is not None:
            verify_cuda_group_contract(bound_instance, self.group)
        (
            self.inference_model,
            self.tokenizer,
            self.vision_processor,
        ) = yield from load_mlx_items(bound_instance, self.group)

    def close(self) -> None:
        with contextlib.suppress(NameError, AttributeError):
            del self.inference_model
        with contextlib.suppress(NameError, AttributeError):
            del self.tokenizer
        with contextlib.suppress(NameError, AttributeError):
            del self.group

    def build(
        self,
    ) -> Engine:
        assert self.inference_model
        assert self.tokenizer

        vision_processor = self.vision_processor

        tool_parser = None
        logger.info(
            f"model has_tool_calling={self.tokenizer.has_tool_calling} using tokens {self.tokenizer.tool_call_start}, {self.tokenizer.tool_call_end}"
        )
        if (
            self.tokenizer.tool_call_start
            and self.tokenizer.tool_call_end
            and self.tokenizer.tool_parser  # type: ignore
        ):
            tool_parser = make_mlx_parser(
                self.tokenizer.tool_call_start,
                self.tokenizer.tool_call_end,
                self.tokenizer.tool_parser,  # type: ignore
            )

        kv_prefix_cache = KVPrefixCache(self.group, cuda_group=self.cuda_cache_group)

        device_rank = 0 if self.group is None else self.group.rank()
        if os.environ.get("EXO_NO_BATCH") or isinstance(
            cast(object, self.inference_model), WindowsQwen3OffloadModel
        ):
            logger.info("using SequentialGenerator (batching disabled)")
            return SequentialGenerator(
                model=self.inference_model,
                tokenizer=self.tokenizer,
                group=self.group,
                tool_parser=tool_parser,
                kv_prefix_cache=kv_prefix_cache,
                model_id=self.model_id,
                device_rank=device_rank,
                cancel_receiver=self.cancel_receiver,
                event_sender=self.event_sender,
                vision_processor=vision_processor,
            )
        else:
            logger.info("using BatchGenerator")
            return BatchGenerator(
                model=self.inference_model,
                tokenizer=self.tokenizer,
                group=self.group,
                tool_parser=tool_parser,
                kv_prefix_cache=kv_prefix_cache,
                model_id=self.model_id,
                device_rank=device_rank,
                cancel_receiver=self.cancel_receiver,
                event_sender=self.event_sender,
                vision_processor=vision_processor,
            )
