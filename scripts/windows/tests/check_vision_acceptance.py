"""Offline hardware gate for exo's real vision path and CPU PyTorch BF16 reads."""

import argparse
import base64
import io
import json
import os
from importlib.metadata import version
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path", type=Path)
    parser.add_argument("--tokens", type=int, default=16)
    arguments = parser.parse_args()
    path = arguments.model_path.resolve()
    os.environ["EXO_MODELS_READ_ONLY_DIRS"] = str(path.parent)
    os.environ["EXO_HOME"] = str(path.parent / "vision-acceptance-home")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    # Keep this call before third-party imports; MLX-LM requires the shim.
    from exo.utils.rlimits import install_windows_resource_shim

    install_windows_resource_shim()
    import mlx.core as mx
    from mlx_lm.generate import generate
    from mlx_lm.utils import load_model
    from PIL import Image

    import exo  # noqa: F401
    from exo.shared.models.model_cards import ModelCard, ModelTask
    from exo.shared.types.backends import Backend
    from exo.shared.types.common import ModelId
    from exo.shared.types.memory import Memory
    from exo.shared.types.text_generation import (
        Base64Image,
        InputMessage,
        InputMessageContent,
        TextGenerationTaskParams,
    )
    from exo.shared.types.worker.shards import PipelineShardMetadata
    from exo.worker.engines.mlx.utils_mlx import get_tokenizer
    from exo.worker.engines.mlx.vision import VisionProcessor

    model_id = ModelId("mlx-community/Qwen3-VL-4B-Instruct-4bit")
    card = ModelCard(
        model_id=model_id,
        storage_size=Memory.from_bytes(3340000000),
        n_layers=36,
        hidden_size=2560,
        supports_tensor=True,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda],
    )
    assert card.vision is not None, "The real snapshot must detect its vision config"
    model, _ = load_model(path, lazy=True, strict=False)
    mx.eval(model.parameters())
    shard = PipelineShardMetadata(
        model_card=card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=36,
        n_layers=36,
    )
    tokenizer = get_tokenizer(path, shard)
    processor = VisionProcessor(card.vision, model_id)
    processor.load()
    buffer = io.BytesIO()
    Image.new("RGB", (112, 112), color=(240, 10, 10)).save(buffer, format="PNG")
    encoded = Base64Image(base64.b64encode(buffer.getvalue()).decode("ascii"))
    question = "What is the main color in this image? Answer with one color word."
    parameters = TextGenerationTaskParams(
        model=model_id,
        input=[InputMessage(role="user", content=InputMessageContent(question))],
        images=[encoded],
        max_output_tokens=arguments.tokens,
        enable_thinking=False,
    )
    result = processor.process(
        [encoded],
        [
            {
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": question}],
            }
        ],
        tokenizer,
        model,
        parameters,
    )
    assert result.embeddings.shape[1] == len(result.prompt_tokens)
    assert result.media_regions, "Vision cache identity must record the synthetic image"
    response = generate(
        model,
        tokenizer,
        prompt=result.prompt_tokens.tolist(),
        input_embeddings=result.embeddings[0],
        max_tokens=arguments.tokens,
        verbose=False,
    )
    print(
        json.dumps(
            {
                "mlx_version": version("mlx"),
                "prompt_tokens": len(result.prompt_tokens),
                "embedding_shape": result.embeddings.shape,
                "media_regions": len(result.media_regions),
                "response": response,
                "peak_gpu_bytes": mx.get_peak_memory(),
            }
        ),
        flush=True,
    )
    assert "red" in response.lower(), (
        f"Synthetic red image was misidentified: {response!r}"
    )


if __name__ == "__main__":
    main()
