from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from exo.api import main as api_module
from exo.api.main import API
from exo.shared.models.model_cards import ModelCard, ModelTask, card_cache
from exo.shared.types.backends import Backend
from exo.shared.types.common import ModelId, NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.profiling import MemoryUsage, NodeIdentity
from exo.shared.types.state import State
from exo.utils.windows_text_offload_config import WindowsTextOffloadPolicy


@dataclass
class HostMemory:
    available: int


def model(name: str, size: int, *, base: str = "Qwen3 32B") -> ModelCard:
    return ModelCard(
        model_id=ModelId(name),
        storage_size=Memory.from_bytes(size),
        n_layers=40,
        hidden_size=4096,
        supports_tensor=True,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda],
        base_model=base,
        quantization="4bit",
    )


def local_api(available: int) -> API:
    api = object.__new__(API)
    api.node_id = NodeId("local")
    api.state = State(
        node_backends={api.node_id: [Backend.MlxCuda]},
        node_identities={api.node_id: NodeIdentity(os_version="Windows 11")},
        node_memory={
            api.node_id: MemoryUsage.from_bytes(
                ram_total=12 * 1024**3,
                ram_available=available,
                swap_total=0,
                swap_available=0,
            )
        },
    )
    return api


async def test_capacity_prefers_exact_vram_then_qualified_ram_offload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = local_api(2 * 1024**3)
    cards = [
        model("test/exact", 2 * 1024**3),
        model("test/offload", 20 * 1024**3),
        model("test/unsupported", 20 * 1024**3, base="Qwen3.5 27B"),
    ]
    monkeypatch.setattr(api_module.sys, "platform", "win32")
    monkeypatch.setattr(card_cache, "list_all", AsyncMock(return_value=cards))
    monkeypatch.setattr(
        api_module,
        "local_windows_text_offload_policy",
        lambda: WindowsTextOffloadPolicy(
            enabled=True, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1024**3
        ),
    )
    monkeypatch.setattr(
        api_module.psutil, "virtual_memory", lambda: HostMemory(64 * 1024**3)
    )
    response = await api.get_windows_model_capacity()
    assert response["models"]["test/exact"] == {
        "mode": "vram",
        "required_bytes": 2 * 1024**3,
        "available_bytes": 2 * 1024**3,
    }
    assert response["models"]["test/offload"] == {
        "mode": "ram_offload",
        "required_bytes": 3 * (20 * 1024**3 // 40),
        "available_bytes": 2 * 1024**3,
    }
    assert response["models"]["test/unsupported"]["mode"] == "unavailable"


@pytest.mark.parametrize(
    "platform,backend", [("darwin", Backend.MlxMetal), ("win32", Backend.MlxCpu)]
)
async def test_non_windows_cuda_returns_empty_without_catalog_reads(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    backend: Backend,
) -> None:
    api = local_api(2 * 1024**3)
    api.state = api.state.model_copy(update={"node_backends": {api.node_id: [backend]}})
    monkeypatch.setattr(api_module.sys, "platform", platform)
    catalog = AsyncMock()
    monkeypatch.setattr(card_cache, "list_all", catalog)
    assert await api.get_windows_model_capacity() == {"models": {}}
    catalog.assert_not_awaited()


@pytest.mark.parametrize(
    "enabled,host_available,gpu_available",
    [
        (False, 64 * 1024**3, 2 * 1024**3),
        (True, 1, 2 * 1024**3),
        (True, 64 * 1024**3, 1),
    ],
)
async def test_capacity_rejects_disabled_offload_or_insufficient_host_and_gpu(
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    host_available: int,
    gpu_available: int,
) -> None:
    api = local_api(gpu_available)
    monkeypatch.setattr(api_module.sys, "platform", "win32")
    monkeypatch.setattr(
        card_cache,
        "list_all",
        AsyncMock(return_value=[model("test/offload", 20 * 1024**3)]),
    )
    monkeypatch.setattr(
        api_module,
        "local_windows_text_offload_policy",
        lambda: WindowsTextOffloadPolicy(
            enabled=enabled, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1024**3
        ),
    )
    monkeypatch.setattr(
        api_module.psutil, "virtual_memory", lambda: HostMemory(host_available)
    )
    response = await api.get_windows_model_capacity()
    assert response["models"]["test/offload"]["mode"] == "unavailable"


def test_private_capacity_route_serializes_without_state_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = local_api(1)
    original_state = api.state
    api.app = FastAPI()
    monkeypatch.setattr(api_module.sys, "platform", "darwin")
    api._setup_routes()  # pyright: ignore[reportPrivateUsage]
    with TestClient(api.app) as client:
        response = client.get("/windows/model-capacity")
    assert response.status_code == 200
    assert response.json() == {"models": {}}
    assert api.state is original_state
