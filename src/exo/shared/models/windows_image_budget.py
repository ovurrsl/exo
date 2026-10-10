"""Pinned Windows image-stage sizes; existing Mac storage accounting is separate."""

from dataclasses import dataclass
from typing import final

from exo.shared.types.common import ModelId
from exo.shared.types.memory import Memory

WINDOWS_IMAGE_CUDA_RESERVE = Memory.from_mb(2560)
_HOST_ACTIVATION_RESERVE_BYTES = 4 * 1024**3


@final
@dataclass(frozen=True)
class WindowsImageBudget:
    snapshot_revision: str
    layer_bytes: tuple[int, ...]
    replicated_transformer_bytes: int
    prompt_weight_bytes: int
    vae_weight_bytes: int
    total_host_weight_bytes: int

    @property
    def n_layers(self) -> int:
        return len(self.layer_bytes)

    def transformer_memory(self, start_layer: int, end_layer: int) -> Memory:
        if not 0 <= start_layer < end_layer <= self.n_layers:
            raise ValueError("Invalid contiguous transformer layer range")
        return Memory.from_bytes(
            self.replicated_transformer_bytes
            + sum(self.layer_bytes[start_layer:end_layer])
        )

    def minimum_gpu_memory(self, start_layer: int, end_layer: int) -> Memory:
        # Stages are sequential and inactive weights stay on the host. This
        # excludes the reserve already subtracted from Windows NodeMemory.
        return Memory.from_bytes(
            max(
                self.transformer_memory(start_layer, end_layer).in_bytes,
                self.prompt_weight_bytes,
                self.vae_weight_bytes,
            )
        )

    @property
    def minimum_host_memory(self) -> Memory:
        # Construction retains loaded parameters while producing canonical
        # copies, with temporary dtype conversion and encoder/VAE activations.
        return Memory.from_bytes(
            2 * self.total_host_weight_bytes + _HOST_ACTIVATION_RESERVE_BYTES
        )


_SCHNELL_4BIT = WindowsImageBudget(
    snapshot_revision="9eaa004ace32efb5b45b17f128d493ac614e8985",
    # Verified safetensors payloads: 19 double blocks, then 38 single blocks.
    # File headers are excluded; tied parameters can make actual loaded bytes
    # slightly smaller, so these values remain conservative upper bounds.
    layer_bytes=(191_288_320,) * 19 + (79_694_336,) * 38,
    replicated_transformer_bytes=30_351_488,
    prompt_weight_bytes=2_748_510_704,
    vae_weight_bytes=164_624_710,
    total_host_weight_bytes=9_606_349_750,
)


def get_windows_image_budget(model_id: ModelId) -> WindowsImageBudget | None:
    if model_id == "exolabs/FLUX.1-schnell-4bit":
        return _SCHNELL_4BIT
    return None
