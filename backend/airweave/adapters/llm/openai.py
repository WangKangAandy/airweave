"""OpenAI-compatible LLM implementation.

Supports local OpenAI-compatible services (Ollama, vLLM, LM Studio) via base_url.
Also supports official OpenAI API when base_url is not set.
"""

import json
import time
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from airweave.adapters.llm.base import BaseLLM
from airweave.adapters.llm.exceptions import LLMTransientError
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMResponse, LLMToolCall
from airweave.core.config import settings

T = TypeVar("T", bound=BaseModel)


class OpenAILLM(BaseLLM):
    """OpenAI-compatible LLM provider (supports local services)."""

    # Known providers that don't support json_schema format
    # These providers only support the older json_object format
    _JSON_SCHEMA_UNSUPPORTED_PROVIDERS = {
        "deepseek.com",
        "deepseek",
        "groq.com",
        "groq",
        "cerebras.cloud",
        "cerebras",
        "together.xyz",
        "together",
    }

    def __init__(
        self,
        model_spec: LLMModelSpec,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the OpenAI client with optional base_url for local services."""
        super().__init__(model_spec, max_retries=max_retries)

        api_key = settings.OPENAI_API_KEY or "dummy"
        base_url = settings.OPENAI_BASE_URL

        try:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self.DEFAULT_TIMEOUT,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}") from e

        # Detect provider support for json_schema format
        self._supports_json_schema = self._detect_json_schema_support(base_url)

        self._logger.debug(
            f"[OpenAILLM] Initialized with model={model_spec.api_model_name}, "
            f"base_url={base_url}, context_window={model_spec.context_window}, "
            f"supports_json_schema={self._supports_json_schema}"
        )

    def _detect_json_schema_support(self, base_url: str | None) -> bool:
        """Detect if the API provider supports json_schema response format.

        Returns False for known incompatible providers (DeepSeek, Groq, Cerebras, etc.).
        Returns True for official OpenAI API and unknown providers (optimistic default).
        """
        if not base_url:
            # No base_url means official OpenAI API, which supports json_schema
            return True

        # Check if base_url contains any known unsupported provider domains
        base_url_lower = base_url.lower()
        for provider in self._JSON_SCHEMA_UNSUPPORTED_PROVIDERS:
            if provider in base_url_lower:
                return False

        # Default to True for unknown providers
        return True

    @property
    def _model_name(self) -> str:
        return settings.OPENAI_MODEL_OVERRIDE or self._model_spec.api_model_name

    def _prepare_schema(self, schema_json: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_strict_schema(schema_json)

    async def _call_api(
        self,
        prompt: str,
        schema: type[T],
        schema_json: dict[str, Any],
        system_prompt: str,
        thinking: bool = False,
    ) -> T:
        # Choose response format based on provider support
        if self._supports_json_schema:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__.lower(),
                    "strict": True,
                    "schema": schema_json,
                },
            }
        else:
            # Fallback to json_object format for providers that don't support json_schema
            response_format = {"type": "json_object"}

            # Modify system prompt to include schema instructions for json_object mode
            schema_instruction = json.dumps(schema_json, indent=2)
            system_prompt = (
                f"{system_prompt}\n\n"
                f"IMPORTANT: You must respond with a valid JSON object that matches this schema:\n"
                f"{schema_instruction}\n"
                f"Do not include any other text or markdown formatting."
            )

        api_start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format=response_format,
            max_tokens=self._model_spec.max_output_tokens,
        )
        api_time = time.monotonic() - api_start

        content = response.choices[0].message.content
        if not content:
            raise LLMTransientError("OpenAI returned empty response", provider=self._name)

        if response.usage:
            self._logger.debug(
                f"[OpenAILLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}"
            )

        return self._parse_json_response(content, schema)

    async def _call_api_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        thinking: bool = False,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        api_messages = [{"role": "system", "content": system_prompt}, *messages]

        api_start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model_name,
            messages=api_messages,
            tools=tools,
            tool_choice="required" if tools else "auto",
            temperature=0.3,
            max_tokens=max_tokens or self._model_spec.max_output_tokens,
        )
        api_time = time.monotonic() - api_start

        choice = response.choices[0]
        message = choice.message

        text = message.content if message.content else None
        thinking_text = getattr(message, "reasoning_content", None)

        tool_calls: list[LLMToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                arguments = tc.function.arguments
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                tool_calls.append(
                    LLMToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        prompt_tokens = 0
        completion_tokens = 0
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens or 0
            completion_tokens = response.usage.completion_tokens or 0
            self._logger.debug(
                f"[OpenAILLM] Tool call completed in {api_time:.2f}s, "
                f"tokens: prompt={prompt_tokens}, completion={completion_tokens}"
            )

        return LLMResponse(
            text=text,
            thinking=thinking_text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._logger.debug("[OpenAILLM] Client closed")
