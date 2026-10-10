import pytest

from exo.shared.models.windows_image_budget import get_windows_image_budget
from exo.shared.types.common import ModelId


def test_pinned_flux_blocks_use_their_actual_unequal_payload_sizes() -> None:
    budget = get_windows_image_budget(ModelId("exolabs/FLUX.1-schnell-4bit"))
    assert budget is not None
    assert budget.n_layers == 57
    assert budget.transformer_memory(0, 1).in_bytes == 191_288_320 + 30_351_488
    assert budget.transformer_memory(19, 20).in_bytes == 79_694_336 + 30_351_488
    assert budget.transformer_memory(18, 20).in_bytes == (
        191_288_320 + 79_694_336 + 30_351_488
    )
    assert budget.transformer_memory(0, 57).in_bytes == 6_693_214_336


def test_sequential_stages_do_not_sum_gpu_weights_but_preserve_host_reserve() -> None:
    budget = get_windows_image_budget(ModelId("exolabs/FLUX.1-schnell-4bit"))
    assert budget is not None
    assert budget.minimum_gpu_memory(0, 57).in_bytes == 6_693_214_336
    # A small shard would still need the full replicated prompt encoders.
    assert budget.minimum_gpu_memory(19, 20).in_bytes == 2_748_510_704
    assert budget.minimum_host_memory.in_bytes == 2 * 9_606_349_750 + 4 * 1024**3


@pytest.mark.parametrize("start,end", [(-1, 2), (1, 1), (2, 1), (0, 58)])
def test_invalid_contiguous_ranges_cannot_underestimate_weights(
    start: int, end: int
) -> None:
    budget = get_windows_image_budget(ModelId("exolabs/FLUX.1-schnell-4bit"))
    assert budget is not None
    with pytest.raises(ValueError, match="layer"):
        _ = budget.transformer_memory(start, end)


def test_other_image_variants_remain_unqualified() -> None:
    assert get_windows_image_budget(ModelId("exolabs/FLUX.1-dev-4bit")) is None
    assert get_windows_image_budget(ModelId("mlx-community/Qwen-Image-4bit")) is None
