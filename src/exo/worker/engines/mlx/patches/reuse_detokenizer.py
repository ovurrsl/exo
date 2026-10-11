import copy
from typing import cast

from mlx_lm.tokenizer_utils import (
    BPEStreamingDetokenizer,
    SPMStreamingDetokenizer,
    StreamingDetokenizer,
    TokenizerWrapper,
)

_PROTOTYPE = "_exo_detokenizer_prototype"
_build = cast(property, TokenizerWrapper.detokenizer).fget


def _fresh_detokenizer(self: TokenizerWrapper) -> StreamingDetokenizer:
    prototype = cast(StreamingDetokenizer | None, self.__dict__.get(_PROTOTYPE))
    if prototype is None:
        assert _build is not None
        prototype = cast(StreamingDetokenizer, _build(self))
        # Naive has a read-only text property incompatible with shallow copying.
        # Custom classes retain their constructor and mutable-state semantics.
        if type(prototype) not in (BPEStreamingDetokenizer, SPMStreamingDetokenizer):
            return prototype
        self.__dict__[_PROTOTYPE] = prototype
    detokenizer = copy.copy(prototype)
    detokenizer.reset()
    return detokenizer


def patch_detokenizer() -> None:
    """Reuse immutable built-in vocabulary maps with fresh request state."""
    TokenizerWrapper.detokenizer = property(_fresh_detokenizer)  # pyright: ignore[reportAttributeAccessIssue]
