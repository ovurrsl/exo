"""A failed runner must not be acknowledged as an empty HTTP 200 response."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from exo.api.main import API
from exo.api.types import ChatCompletionMessage, ChatCompletionRequest, ErrorResponse
from exo.shared.types.chunks import ErrorChunk
from exo.shared.types.commands import TextGeneration
from exo.shared.types.common import ModelId


def test_nonstreaming_runner_failure_returns_http_error() -> None:
    model = ModelId("test-org/test-model")
    api = object.__new__(API)
    api.app = FastAPI()
    api._setup_exception_handlers()  # pyright: ignore[reportPrivateUsage]
    api._send = AsyncMock()  # pyright: ignore[reportPrivateUsage]
    api._validate_model_has_instance = AsyncMock(return_value=model)  # pyright: ignore[reportPrivateUsage]

    async def failed_stream(
        text_generation: TextGeneration,
    ) -> AsyncGenerator[ErrorChunk, None]:
        yield ErrorChunk(
            model=text_generation.task_params.model, error_message="CUDA runner failed"
        )

    api._token_chunk_stream = failed_stream  # pyright: ignore[reportPrivateUsage]

    @api.app.get("/test-generation")
    async def generation():  # pyright: ignore[reportUnusedFunction]
        return await api.chat_completions(
            ChatCompletionRequest(
                model=model,
                messages=[ChatCompletionMessage(role="user", content="hello")],
                stream=False,
            )
        )

    response = TestClient(api.app, raise_server_exceptions=False).get(
        "/test-generation"
    )
    assert response.status_code == 500
    assert (
        ErrorResponse.model_validate_json(response.text).error.message
        == "CUDA runner failed"
    )
