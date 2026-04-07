"""Model registry for LLM adapters.

Single source of truth for all provider-model combinations and their specifications.
The fallback chain (which combinations to use and in what order) is configured in
SearchConfig, not here. This module is purely a catalog.

Thinking/reasoning is controlled per-call via the `thinking` parameter on chat(),
not per-model. The ThinkingConfig tells providers *how* to toggle thinking (which
API parameter to use), but not *whether* to — that comes from the request.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Union

from airweave.adapters.tokenizer.registry import TokenizerEncoding, TokenizerType


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CEREBRAS = "cerebras"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    TOGETHER = "together"
    OPENAI = "openai"


class LLMModel(str, Enum):
    """Supported LLM models (global across providers).

    A model can be hosted by multiple providers (e.g., GPT_OSS_120B on both
    Cerebras and Groq). The MODEL_REGISTRY maps each (provider, model) pair
    to its provider-specific specification.

    Thinking is toggled per-call, so there are no separate -thinking variants.
    """

    GPT_OSS_120B = "gpt-oss-120b"
    ZAI_GLM_4_7 = "zai-glm-4.7"
    ZAI_GLM_5 = "zai-glm-5"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4.5"
    CLAUDE_SONNET_4_6 = "claude-sonnet-4.6"
    KIMI_K2_5 = "kimi-k2.5"
    QWEN_3_5 = "qwen-3.5"
    QWEN_3_5_DEDICATED = "qwen-3.5-dedicated"
    ZAI_GLM_5_DEDICATED = "zai-glm-5-dedicated"
    MINIMAX_M2_5 = "minimax-m2.5"
    GPT_4O_MINI = "gpt-4o-mini"


@dataclass(frozen=True)
class ThinkingConfig:
    """Model-specific thinking/reasoning API configuration.

    Tells providers which API parameter to use when toggling thinking on/off:
    - Together (GLM/Qwen/Kimi/MiniMax): reasoning={"enabled": True/False}
    - Cerebras GPT-OSS: reasoning_effort="high"/"low"
    - Cerebras GLM: disable_reasoning=True/False
    - Anthropic 4.6: adaptive thinking with effort="high"
    - Anthropic 4.5: no thinking support (param_name="_noop")

    The actual on/off decision comes from the `thinking` parameter on chat(),
    not from param_value here. param_value is unused in the per-call model.
    """

    param_name: str
    param_value: Union[str, bool, int]  # kept for backward compat, unused in per-call model
    effort: str | None = None


# Backwards compat alias
ReasoningConfig = ThinkingConfig


@dataclass(frozen=True)
class LLMModelSpec:
    """Immutable specification for an LLM model.

    frozen=True makes this hashable and prevents accidental mutation.
    """

    api_model_name: str
    context_window: int
    max_output_tokens: int
    required_tokenizer_type: TokenizerType
    required_tokenizer_encoding: TokenizerEncoding
    thinking_config: ThinkingConfig
    input_price_factor: float = 1.0
    output_price_factor: float = 1.0


# Registry: provider -> model -> spec
MODEL_REGISTRY: dict[LLMProvider, dict[LLMModel, LLMModelSpec]] = {
    LLMProvider.CEREBRAS: {
        LLMModel.GPT_OSS_120B: LLMModelSpec(
            api_model_name="gpt-oss-120b",
            context_window=131_000,
            max_output_tokens=40_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="reasoning_effort",
                param_value="high",
            ),
            input_price_factor=0.35,
            output_price_factor=0.75,
        ),
        LLMModel.ZAI_GLM_4_7: LLMModelSpec(
            api_model_name="zai-glm-4.7",
            context_window=131_000,
            max_output_tokens=40_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="disable_reasoning",
                param_value=False,
            ),
            input_price_factor=2.25,
            output_price_factor=2.75,
        ),
    },
    LLMProvider.GROQ: {
        LLMModel.GPT_OSS_120B: LLMModelSpec(
            api_model_name="openai/gpt-oss-120b",
            context_window=131_000,
            max_output_tokens=40_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="reasoning_effort",
                param_value="high",
            ),
            input_price_factor=0.15,
            output_price_factor=0.60,
        ),
    },
    LLMProvider.ANTHROPIC: {
        LLMModel.CLAUDE_SONNET_4_6: LLMModelSpec(
            api_model_name="claude-sonnet-4-6",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(
                param_name="adaptive_thinking",
                param_value=True,
                effort="high",
            ),
            input_price_factor=3.0,
            output_price_factor=15.0,
        ),
        LLMModel.CLAUDE_SONNET_4_5: LLMModelSpec(
            api_model_name="claude-sonnet-4-5-20250929",
            context_window=200_000,
            max_output_tokens=16_384,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="_noop", param_value=True),
            input_price_factor=3.0,
            output_price_factor=15.0,
        ),
    },
    LLMProvider.TOGETHER: {
        # ── Kimi K2.5 ──────────────────────────────────────────────
        LLMModel.KIMI_K2_5: LLMModelSpec(
            api_model_name="moonshotai/Kimi-K2.5",
            context_window=256_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
            input_price_factor=0.50,
            output_price_factor=2.80,
        ),
        # ── GLM-5 ─────────────────────────────────────────────────
        LLMModel.ZAI_GLM_5: LLMModelSpec(
            api_model_name="zai-org/GLM-5",
            context_window=200_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
            input_price_factor=1.0,
            output_price_factor=3.2,
        ),
        # ── Qwen 3.5 ──────────────────────────────────────────────
        LLMModel.QWEN_3_5: LLMModelSpec(
            api_model_name="Qwen/Qwen3.5-397B-A17B",
            context_window=256_000,
            max_output_tokens=81_920,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
            input_price_factor=0.6,
            output_price_factor=3.6,
        ),
        # ── MiniMax M2.5 ──────────────────────────────────────────
        LLMModel.MINIMAX_M2_5: LLMModelSpec(
            api_model_name="MiniMaxAI/MiniMax-M2.5",
            context_window=192_000,
            max_output_tokens=64_000,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="reasoning", param_value=False),
            input_price_factor=0.30,
            output_price_factor=1.20,
        ),
    },
    # ── OpenAI (local/Cloud) ──────────────────────────────────────
    LLMProvider.OPENAI: {
        LLMModel.GPT_4O_MINI: LLMModelSpec(
            api_model_name="gpt-4o-mini",
            context_window=128_000,
            max_output_tokens=16_384,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="_noop", param_value=False),
            input_price_factor=0.075,
            output_price_factor=0.3,
        ),
    },
}


# Maps each provider to the settings attribute name for its API key.
PROVIDER_API_KEY_SETTINGS: dict[LLMProvider, str] = {
    LLMProvider.CEREBRAS: "CEREBRAS_API_KEY",
    LLMProvider.GROQ: "GROQ_API_KEY",
    LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    LLMProvider.TOGETHER: "TOGETHER_API_KEY",
    LLMProvider.OPENAI: "OPENAI_API_KEY",
}


def get_model_spec(provider: LLMProvider, model: LLMModel) -> LLMModelSpec:
    """Get model spec with validation."""
    if provider not in MODEL_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")

    provider_models = MODEL_REGISTRY[provider]
    if model not in provider_models:
        available = [m.value for m in provider_models.keys()]
        raise ValueError(
            f"Model '{model.value}' not supported by {provider.value}. Available: {available}"
        )

    return provider_models[model]


def get_available_models(provider: LLMProvider) -> list[LLMModel]:
    """Get list of models available for a provider."""
    if provider not in MODEL_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}")
    return list(MODEL_REGISTRY[provider].keys())


def fetch_local_models(base_url: str, api_key: str | None = None) -> list[str]:
    """Fetch available models from a local OpenAI-compatible endpoint.

    Args:
        base_url: The base URL of the OpenAI-compatible API (e.g., http://localhost:11434/v1)
        api_key: Optional API key (some local LLMs don't require one)

    Returns:
        List of model IDs available at the endpoint
    """
    import requests

    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resp = requests.get(
            f"{base_url.rstrip('/')}/models",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return [model["id"] for model in data.get("data", [])]
        return []
    except Exception:
        return []


def create_local_model_spec(model_id: str) -> LLMModelSpec:
    """Create a model spec for a local OpenAI-compatible model.

    Uses conservative defaults suitable for most local models.
    The actual model capabilities may vary, but this should work
    for basic functionality.

    Args:
        model_id: The model ID (e.g., 'qwen2.5:7b-instruct')

    Returns:
        A LLMModelSpec with conservative defaults
    """
    model_id_lower = model_id.lower()

    is_embedding_model = any(
        keyword in model_id_lower
        for keyword in ["embed", "embedding", "bge", "e5", "rerank"]
    )

    if is_embedding_model:
        return LLMModelSpec(
            api_model_name=model_id,
            context_window=8192,
            max_output_tokens=4096,
            required_tokenizer_type=TokenizerType.TIKTOKEN,
            required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
            thinking_config=ThinkingConfig(param_name="_noop", param_value=False),
            input_price_factor=0.0,
            output_price_factor=0.0,
        )

    return LLMModelSpec(
        api_model_name=model_id,
        context_window=8192,
        max_output_tokens=4096,
        required_tokenizer_type=TokenizerType.TIKTOKEN,
        required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
        thinking_config=ThinkingConfig(param_name="_noop", param_value=False),
        input_price_factor=0.0,
        output_price_factor=0.0,
    )


def select_best_local_model(models: list[str]) -> str | None:
    """Select the best LLM model from a list of available models.

    Prefers chat/instruct models over embedding models.

    Args:
        models: List of model IDs from the OpenAI-compatible endpoint

    Returns:
        The selected model ID, or None if no suitable model found
    """
    if not models:
        return None

    embedding_keywords = ["embed", "embedding", "bge", "e5", "rerank"]
    llm_keywords = ["instruct", "chat", "gpt", "claude", "llama", "qwen", "glm", "mistral"]

    llm_models = []
    embedding_models = []

    for model in models:
        model_lower = model.lower()
        if any(kw in model_lower for kw in embedding_keywords):
            embedding_models.append(model)
        elif any(kw in model_lower for kw in llm_keywords):
            llm_models.append(model)

    if llm_models:
        return llm_models[0]

    if embedding_models:
        return embedding_models[0]

    return models[0]
