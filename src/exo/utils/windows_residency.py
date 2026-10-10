"""Pure ownership and memory planning for Windows CUDA residency."""

from dataclasses import dataclass
from typing import Literal, cast, final

type ComponentRole = Literal["head", "norm", "decoder", "embedding"]


@final
@dataclass(frozen=True)
class ComponentSpec:
    component_id: str
    aliases: tuple[str, ...]
    roles: frozenset[ComponentRole]
    byte_size: int
    decoder_index: int | None = None


@final
@dataclass(frozen=True)
class CapacitySnapshot:
    free_gpu_bytes: int
    host_available_bytes: int


@final
@dataclass(frozen=True)
class BudgetPolicy:
    """Reserves are unused device budgets; host load peak is extra transient RAM."""

    runtime_bytes: int
    kv_bytes: int
    workspace_bytes: int
    host_reserve_bytes: int
    host_limit_bytes: int
    host_load_peak_bytes: int


@final
@dataclass(frozen=True)
class ResidencyPlan:
    resident_component_ids: tuple[str, ...]
    overflow_component_ids: tuple[str, ...]
    persistent_gpu_bytes: int
    overflow_host_bytes: int
    initialization_gpu_peak_bytes: int
    steady_gpu_peak_bytes: int
    reserve_bytes: int
    required_gpu_bytes: int
    required_host_bytes: int


def plan_residency(
    components: tuple[ComponentSpec, ...],
    capacity: CapacitySnapshot,
    policy: BudgetPolicy,
) -> ResidencyPlan:
    """Plan unique storage owners, without allocating or querying either device.

    Caller supplies exact component ownership and a conservative cold-load host
    transient bound. Host limit caps only overflow canonical weights. GPU copy
    bounds include one output and two copy temporaries, including initialization.
    """
    _validate_components(components)
    _validate_nonnegative(
        capacity.free_gpu_bytes,
        capacity.host_available_bytes,
        policy.runtime_bytes,
        policy.kv_bytes,
        policy.workspace_bytes,
        policy.host_reserve_bytes,
        policy.host_limit_bytes,
        policy.host_load_peak_bytes,
    )
    head = next(component for component in components if "head" in component.roles)
    norm = next(component for component in components if "norm" in component.roles)
    decoders = tuple(
        sorted(
            (component for component in components if "decoder" in component.roles),
            key=lambda component: component.decoder_index
            if component.decoder_index is not None
            else -1,
        )
    )
    embedding = next(
        component for component in components if "embedding" in component.roles
    )
    reserve = policy.runtime_bytes + policy.kv_bytes + policy.workspace_bytes
    selected: ResidencyPlan | None = None
    for prefix in range(len(decoders) + 1):
        resident = (head, norm, *decoders[:prefix])
        overflow = (
            *decoders[prefix:],
            *((embedding,) if embedding is not head else ()),
        )
        candidate = _make_plan(resident, overflow, reserve, policy)
        if candidate.required_gpu_bytes <= capacity.free_gpu_bytes:
            selected = candidate
    if selected is None:
        raise MemoryError(
            "Insufficient dedicated GPU capacity for required head/norm and staging"
        )
    if embedding is not head:
        resident_ids = set(selected.resident_component_ids)
        resident = tuple(
            component
            for component in (head, norm, *decoders)
            if component.component_id in resident_ids
        )
        overflow = tuple(
            component
            for component in decoders
            if component.component_id not in resident_ids
        )
        with_embedding = _make_plan((*resident, embedding), overflow, reserve, policy)
        if with_embedding.required_gpu_bytes <= capacity.free_gpu_bytes:
            selected = with_embedding
    if (
        selected.overflow_host_bytes > policy.host_limit_bytes
        or selected.required_host_bytes > capacity.host_available_bytes
    ):
        raise MemoryError("Insufficient host capacity or overflow weight budget")
    return selected


def validate_stage_capacity(
    *, free_gpu_bytes: int, layer_bytes: int, reserve_bytes: int
) -> None:
    """Check current free bytes, excluding resident and already allocated KV bytes.

    reserve_bytes is the still-unused runtime/KV/workspace allowance, derived by
    the caller at this stage. Never add persistent allocations back to NVML free.
    """
    _validate_nonnegative(free_gpu_bytes, layer_bytes, reserve_bytes)
    if free_gpu_bytes < reserve_bytes + 3 * layer_bytes:
        raise MemoryError("Insufficient remaining dedicated GPU capacity for staging")


def _validate_nonnegative(*values: int) -> None:
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Memory budgets must be nonnegative integer bytes")


def _validate_components(components: tuple[ComponentSpec, ...]) -> None:
    identifiers: set[str] = set()
    roles: dict[ComponentRole, int] = {
        "head": 0,
        "norm": 0,
        "decoder": 0,
        "embedding": 0,
    }
    decoder_indices: list[int] = []
    for component in components:
        _validate_nonnegative(component.byte_size)
        if (
            not isinstance(cast(object, component.aliases), tuple)
            or not isinstance(cast(object, component.roles), frozenset)
            or component.roles
            not in (
                frozenset({"head"}),
                frozenset({"norm"}),
                frozenset({"decoder"}),
                frozenset({"embedding"}),
                frozenset({"head", "embedding"}),
            )
        ):
            raise ValueError("Invalid component roles or immutable aliases")
        for identifier in (component.component_id, *component.aliases):
            if (
                not isinstance(cast(object, identifier), str)
                or not identifier.strip()
                or identifier in identifiers
            ):
                raise ValueError(
                    "Component ownership identifiers must be nonempty and unique"
                )
            identifiers.add(identifier)
        for role in component.roles:
            roles[role] += 1
        if "decoder" in component.roles:
            if type(component.decoder_index) is not int or component.decoder_index < 0:
                raise ValueError("Decoder index must be a nonnegative integer")
            decoder_indices.append(component.decoder_index)
        elif component.decoder_index is not None:
            raise ValueError("Only decoder components may have a decoder index")
    if any(roles[role] != 1 for role in ("head", "norm", "embedding")):
        raise ValueError("Exactly one head, norm and embedding owner is required")
    if not decoder_indices or sorted(decoder_indices) != list(
        range(len(decoder_indices))
    ):
        raise ValueError("Decoder indices must be unique and consecutive from zero")


def _make_plan(
    resident: tuple[ComponentSpec, ...],
    overflow: tuple[ComponentSpec, ...],
    reserve: int,
    policy: BudgetPolicy,
) -> ResidencyPlan:
    persistent = 0
    initialization_peak = 0
    for component in resident:
        initialization_peak = max(
            initialization_peak, persistent + 3 * component.byte_size
        )
        persistent += component.byte_size
    largest_overflow = max(
        (component.byte_size for component in overflow if "decoder" in component.roles),
        default=0,
    )
    steady_peak = persistent + 3 * largest_overflow
    host = sum(component.byte_size for component in overflow)
    return ResidencyPlan(
        tuple(component.component_id for component in resident),
        tuple(component.component_id for component in overflow),
        persistent,
        host,
        initialization_peak,
        steady_peak,
        reserve,
        reserve + max(initialization_peak, steady_peak),
        host + policy.host_load_peak_bytes + policy.host_reserve_bytes,
    )
