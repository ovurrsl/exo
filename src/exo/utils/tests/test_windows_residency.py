from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from exo.utils.windows_residency import (
    BudgetPolicy,
    CapacitySnapshot,
    ComponentRole,
    ComponentSpec,
    plan_residency,
    validate_stage_capacity,
)


def components() -> tuple[ComponentSpec, ...]:
    return (
        ComponentSpec("head", (), frozenset({"head"}), 20),
        ComponentSpec("norm", (), frozenset({"norm"}), 5),
        *(
            ComponentSpec(f"layer{i}", (), frozenset({"decoder"}), 10, i)
            for i in range(4)
        ),
        ComponentSpec("embedding", (), frozenset({"embedding"}), 15),
    )


def policy() -> BudgetPolicy:
    return BudgetPolicy(10, 30, 10, 5, 100, 120)


def test_exact_literal_budget_and_ownership() -> None:
    plan = plan_residency(components(), CapacitySnapshot(125, 160), policy())
    assert plan.resident_component_ids == ("head", "norm", "layer0", "layer1")
    assert plan.overflow_component_ids == ("layer2", "layer3", "embedding")
    assert plan.persistent_gpu_bytes == 45
    assert plan.overflow_host_bytes == 35
    assert plan.initialization_gpu_peak_bytes == 65
    assert plan.steady_gpu_peak_bytes == 75
    assert plan.reserve_bytes == 50
    assert plan.required_gpu_bytes == 125
    assert plan.required_host_bytes == 160


@pytest.mark.parametrize(
    "free,prefix,embedding",
    [
        (110, 0, False),
        (124, 1, False),
        (125, 2, False),
        (135, 4, False),
        (160, 4, True),
    ],
)
def test_gpu_capacity_changes_prefix_without_skipping(
    free: int, prefix: int, embedding: bool
) -> None:
    plan = plan_residency(components(), CapacitySnapshot(free, 1000), policy())
    assert plan.resident_component_ids == (
        "head",
        "norm",
        *(f"layer{i}" for i in range(prefix)),
        *(("embedding",) if embedding else ()),
    )


def test_head_initialization_peak_is_required_even_without_resident_decoders() -> None:
    with pytest.raises(MemoryError, match="GPU"):
        plan_residency(components(), CapacitySnapshot(109, 1000), policy())


def test_kv_growth_shrinks_the_resident_prefix() -> None:
    plan = plan_residency(
        components(), CapacitySnapshot(125, 1000), replace(policy(), kv_bytes=40)
    )
    assert plan.resident_component_ids == ("head", "norm", "layer0")
    assert plan.required_gpu_bytes == 125


def test_tied_head_embedding_ownership_counts_once() -> None:
    tied = (
        ComponentSpec("head", ("embedding",), frozenset({"head", "embedding"}), 20),
        *components()[1:-1],
    )
    plan = plan_residency(tied, CapacitySnapshot(135, 125), policy())
    assert plan.resident_component_ids == (
        "head",
        "norm",
        "layer0",
        "layer1",
        "layer2",
        "layer3",
    )
    assert plan.persistent_gpu_bytes == 65
    assert plan.overflow_component_ids == ()
    assert plan.overflow_host_bytes == 0
    assert plan.required_host_bytes == 125


def test_input_order_does_not_change_the_plan() -> None:
    capacity = CapacitySnapshot(125, 1000)
    assert plan_residency(
        tuple(reversed(components())), capacity, policy()
    ) == plan_residency(components(), capacity, policy())


def test_host_peak_and_overflow_limit_are_independent() -> None:
    with pytest.raises(MemoryError, match="host"):
        plan_residency(components(), CapacitySnapshot(125, 159), policy())
    assert (
        plan_residency(
            components(),
            CapacitySnapshot(125, 160),
            replace(policy(), host_limit_bytes=35),
        ).overflow_host_bytes
        == 35
    )
    with pytest.raises(MemoryError, match="host"):
        plan_residency(
            components(),
            CapacitySnapshot(125, 160),
            replace(policy(), host_limit_bytes=34),
        )


def test_live_staging_uses_remaining_capacity_without_resident_or_kv_double_count() -> (
    None
):
    validate_stage_capacity(free_gpu_bytes=90, layer_bytes=10, reserve_bytes=60)
    with pytest.raises(MemoryError, match="GPU"):
        validate_stage_capacity(free_gpu_bytes=89, layer_bytes=10, reserve_bytes=60)


@pytest.mark.parametrize(
    "invalid",
    [
        ComponentSpec("", (), frozenset({"head"}), 20),
        ComponentSpec("head", ("head",), frozenset({"head"}), 20),
        ComponentSpec("head", ("duplicate", "duplicate"), frozenset({"head"}), 20),
        ComponentSpec("head", (), frozenset(), 20),
        ComponentSpec(
            "head", (), frozenset({cast(ComponentRole, cast(object, "unknown"))}), 20
        ),
        ComponentSpec("head", (), frozenset({"head"}), -1),
        ComponentSpec("head", (), frozenset({"head"}), 20, 0),
        ComponentSpec("head", (), frozenset({"head", "decoder"}), 20, 0),
    ],
)
def test_malformed_component_is_rejected(invalid: ComponentSpec) -> None:
    with pytest.raises(ValueError):
        plan_residency(
            (invalid, *components()[1:]), CapacitySnapshot(1000, 1000), policy()
        )


@pytest.mark.parametrize("index", [-1, 1, 9, None])
def test_decoder_indices_must_be_unique_and_consecutive(index: int | None) -> None:
    invalid = list(components())
    invalid[2] = replace(invalid[2], decoder_index=index)
    with pytest.raises(ValueError):
        plan_residency(tuple(invalid), CapacitySnapshot(1000, 1000), policy())


def test_alias_cannot_overlap_another_ownership_group() -> None:
    invalid = list(components())
    invalid[0] = replace(invalid[0], aliases=("embedding",))
    with pytest.raises(ValueError):
        plan_residency(tuple(invalid), CapacitySnapshot(1000, 1000), policy())


def test_mandatory_roles_and_decoder_are_required() -> None:
    for subset in (
        components()[1:],
        components()[:1] + components()[2:],
        components()[:2] + components()[-1:],
    ):
        with pytest.raises(ValueError):
            plan_residency(subset, CapacitySnapshot(1000, 1000), policy())


@pytest.mark.parametrize("field", ["free_gpu_bytes", "host_available_bytes"])
def test_negative_capacity_rejected(field: str) -> None:
    with pytest.raises(ValueError):
        plan_residency(
            components(), replace(CapacitySnapshot(1000, 1000), **{field: -1}), policy()
        )


@pytest.mark.parametrize(
    "field",
    [
        "runtime_bytes",
        "kv_bytes",
        "workspace_bytes",
        "host_reserve_bytes",
        "host_limit_bytes",
        "host_load_peak_bytes",
    ],
)
def test_negative_budget_rejected(field: str) -> None:
    with pytest.raises(ValueError):
        plan_residency(
            components(), CapacitySnapshot(1000, 1000), replace(policy(), **{field: -1})
        )


def test_plan_is_immutable() -> None:
    plan = plan_residency(components(), CapacitySnapshot(125, 160), policy())
    attribute = "persistent_gpu_bytes"
    with pytest.raises(FrozenInstanceError):
        setattr(plan, attribute, 0)


@pytest.mark.parametrize("field", ["free_gpu_bytes", "layer_bytes", "reserve_bytes"])
def test_negative_live_stage_budget_rejected(field: str) -> None:
    arguments = {"free_gpu_bytes": 90, "layer_bytes": 10, "reserve_bytes": 60}
    arguments[field] = -1
    with pytest.raises(ValueError):
        validate_stage_capacity(**arguments)


def test_full_gpu_residency_needs_no_canonical_host_weight_allowance() -> None:
    plan = plan_residency(
        components(), CapacitySnapshot(160, 125), replace(policy(), host_limit_bytes=0)
    )
    assert plan.overflow_host_bytes == 0
    assert plan.required_host_bytes == 125
